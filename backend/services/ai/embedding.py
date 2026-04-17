import logging
import threading
import time
import uuid
from typing import Optional
import httpx

logger = logging.getLogger(__name__)

# 模块级 client 复用，避免每次创建开销
_http_client: Optional[httpx.Client] = None

# Embedding API 限速：保证两次调用之间至少间隔
_rate_lock = threading.Lock()
_last_call_time: float = 0.0
_EMBED_MIN_INTERVAL = 0.5  # 秒，两次调用最小间隔

def _get_http_client() -> httpx.Client:
    global _http_client
    if _http_client is None:
        transport = httpx.HTTPTransport(retries=2)
        _http_client = httpx.Client(transport=transport, timeout=httpx.Timeout(10.0))
    return _http_client

def chunk_text(text: str, chunk_size: int = 512, overlap: int = 50) -> list[str]:
    """
    按字符数分块，块之间有 overlap。
    丢弃不足 overlap 字符的尾部碎片。
    """
    if not text or len(text) <= chunk_size:
        return [text] if text else []

    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunk = text[start:end]
        chunks.append(chunk)
        start = end - overlap  # overlap 保证块之间有50字符重叠

    # 丢弃最后一块如果不足 overlap 字符
    if chunks and len(chunks[-1]) < overlap:
        chunks.pop()

    return chunks

def _get_embedding_config() -> dict | None:
    """从 DB 获取专用 embedding 配置，返回 {api_key, base_url, model} 或 None"""
    try:
        from database import get_session as _get_session
        from models.embedding_config import EmbeddingConfig
        from services.encryption import decrypt_value

        gen = _get_session()
        session = next(gen)
        try:
            config = session.get(EmbeddingConfig, 1)
            if config and config.api_key:
                return {
                    "api_key": decrypt_value(config.api_key),
                    "base_url": config.base_url,
                    "model": config.model or "BAAI/bge-m3",
                }
        finally:
            session.close()
    except Exception:
        pass
    return None


def generate_embedding(text: str, model: str = "BAAI/bge-m3") -> list[float]:
    """
    调用 LLM 兼容 API 生成文本 embedding。
    优先使用专用 embedding 配置，回退到默认 provider。
    内置限速，防止触发 API 频率限制。
    """
    global _last_call_time

    # 限速：保证调用间隔
    with _rate_lock:
        now = time.time()
        wait = _EMBED_MIN_INTERVAL - (now - _last_call_time)
        if wait > 0:
            time.sleep(wait)
        _last_call_time = time.time()

    from services.ai.client import get_default_provider

    # 1. 尝试专用 embedding 配置
    emb_config = _get_embedding_config()
    if emb_config:
        api_key = emb_config["api_key"]
        base_url = emb_config["base_url"] or "https://api.siliconflow.cn/v1"
        model = emb_config["model"]
    else:
        # 2. 回退到默认 provider
        default = get_default_provider()
        if not default or not default.get("api_key"):
            raise ValueError("Embedding provider not configured")
        api_key = default["api_key"]
        base_url = default.get("base_url", "https://api.openai.com/v1")

    url = f"{base_url.rstrip('/')}/embeddings"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "input": text[:8191],  # embedding 输入限制
    }

    resp = _get_http_client().post(url, headers=headers, json=payload)
    resp.raise_for_status()
    result = resp.json()

    return result["data"][0]["embedding"]

def embed_document(doc_id: str, title: str, content: str, url: str,
                   category: str = "", department: str = "",
                   parent_category: str = "", sub_category: str = "",
                   chunk_size: int = 512, overlap: int = 50) -> int:
    """
    将文档分块并生成向量，存入 Qdrant。
    返回成功入库的块数量。
    """
    from services.qdrant import upsert_points, ensure_collection
    from qdrant_client.models import PointStruct

    ensure_collection()

    chunks = chunk_text(content, chunk_size=chunk_size, overlap=overlap)
    if not chunks:
        return 0

    points = []
    for i, chunk in enumerate(chunks):
        try:
            vector = generate_embedding(chunk)
        except Exception as e:
            logger.warning(f"Failed to embed chunk {i} of doc {doc_id}: {e}")
            continue

        point_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"{doc_id}_{i}"))
        point = PointStruct(
            id=point_id,
            vector=vector,
            payload={
                "doc_id": doc_id,
                "title": title,
                "chunk_text": chunk,
                "url": url,
                "category": category or "",
                "department": department or "",
                "parent_category": parent_category or "",
                "sub_category": sub_category or "",
            },
        )
        points.append(point)

    if points:
        upsert_points(points)
        logger.info(f"Embedded {len(points)} chunks for doc {doc_id}")

    return len(points)
