import qdrant_client
from qdrant_client.models import Distance, VectorParams, PointStruct, Filter, FieldCondition, Match
from typing import Optional
import logging
import threading

from config import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)

_client = None
_client_lock = threading.Lock()

def get_qdrant_client() -> qdrant_client.QdrantClient:
    global _client
    if _client is None:
        with _client_lock:
            if _client is None:  # Double-checked locking
                _client = qdrant_client.QdrantClient(url=settings.QDRANT_URL)
    return _client

_ensure_lock = threading.Lock()
_collection_ready = False

def ensure_collection():
    """确保 collection 存在，不存在则创建（线程安全，只检查一次）"""
    global _collection_ready
    if _collection_ready:
        return
    with _ensure_lock:
        if _collection_ready:
            return
        client = get_qdrant_client()
        collections = client.get_collections().collections
        collection_names = [c.name for c in collections]

        if settings.QDRANT_COLLECTION not in collection_names:
            client.create_collection(
                collection_name=settings.QDRANT_COLLECTION,
                vectors_config=VectorParams(
                    size=settings.EMBEDDING_VECTOR_SIZE,
                    distance=Distance.COSINE,
                ),
            )
            # 创建 payload 索引支持 text_search
            client.create_payload_index(
                collection_name=settings.QDRANT_COLLECTION,
                field_name="chunk_text",
                field_schema="text",
            )
            logger.info(f"Created Qdrant collection: {settings.QDRANT_COLLECTION}")
        _collection_ready = True

def upsert_points(points: list[PointStruct]):
    """批量写入向量点"""
    client = get_qdrant_client()
    client.upsert(
        collection_name=settings.QDRANT_COLLECTION,
        points=points,
    )

def search_points(query_vector: list[float], top_k: int = 3, score_threshold: float = 0.5) -> list[dict]:
    """向量相似度搜索，返回命中的块信息"""
    client = get_qdrant_client()
    results = client.search(
        collection_name=settings.QDRANT_COLLECTION,
        query_vector=query_vector,
        limit=top_k,
        score_threshold=score_threshold,
    )
    return [
        {
            "id": r.id,
            "score": r.score,
            "payload": r.payload,
        }
        for r in results
    ]

def delete_points_by_doc_id(doc_id: str):
    """删除指定文档的所有向量点"""
    client = get_qdrant_client()
    client.delete(
        collection_name=settings.QDRANT_COLLECTION,
        points_selector=Filter(
            must=[
                FieldCondition(key="doc_id", match=Match(value=doc_id))
            ]
        ),
    )