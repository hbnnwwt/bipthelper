import json
import os
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from database import get_session
from models.user import User
from models.ai_provider import AIProvider
from services.auth import get_current_admin
from services.ai.client import test_provider, get_default_provider
from services.encryption import encrypt_value, decrypt_value
from models.embedding_config import EmbeddingConfig

router = APIRouter()
logger = logging.getLogger(__name__)

# AI providers JSON 模板路径
_ai_services_dir = Path(__file__).resolve().parent.parent / "services" / "ai"
PROVIDERS_JSON = _ai_services_dir / "providers.json"

# --- Provider 管理 ---

@router.get("/providers")
def list_providers(
    current_admin: User = Depends(get_current_admin),
    session: Session = Depends(get_session),
):
    """列出所有 AI Provider（含 hasKey 标记）"""
    db_providers = session.exec(select(AIProvider)).all()
    db_map = {p.id: p for p in db_providers}

    # 从 JSON 模板加载
    if os.path.exists(PROVIDERS_JSON):
        with open(PROVIDERS_JSON, "r", encoding="utf-8") as f:
            data = json.load(f)
        json_providers = data.get("providers", [])
    else:
        json_providers = []

    # 合并：DB 中的覆盖 JSON 中的
    all_ids = set(k for k in db_map.keys())
    for p in json_providers:
        all_ids.add(p["id"])

    result = []
    for pid in all_ids:
        if pid in db_map:
            p = db_map[pid]
            result.append({
                "id": p.id,
                "name": p.name,
                "base_url": p.base_url,
                "default_model": p.default_model,
                "api_format": p.api_format,
                "has_api_key": bool(p.api_key),
                "is_enabled": p.is_enabled,
                "is_default": p.is_default,
            })
        else:
            # JSON 模板中的默认值（不含 key）
            json_p = next((x for x in json_providers if x["id"] == pid), None)
            if json_p:
                result.append({
                    "id": json_p["id"],
                    "name": json_p.get("name", pid),
                    "base_url": json_p.get("baseUrl", ""),
                    "default_model": json_p.get("defaultModel", ""),
                    "api_format": json_p.get("apiFormat", "openai"),
                    "has_api_key": False,
                    "is_enabled": True,
                    "is_default": False,
                })

    return {"providers": result}

@router.post("/providers")
def save_provider(
    id: str,
    name: str,
    api_key: str = "",
    base_url: str = "",
    default_model: str = "",
    api_format: str = "openai",
    is_default: bool = False,
    current_admin: User = Depends(get_current_admin),
    session: Session = Depends(get_session),
):
    """创建/更新 Provider 配置"""
    # 如果设为默认，先清除其他默认
    if is_default:
        existing = session.exec(select(AIProvider)).all()
        for p in existing:
            p.is_default = False
            session.add(p)

    # 查找或创建
    provider = session.get(AIProvider, id)
    encrypted_key = None
    if api_key:
        encrypted_key = encrypt_value(api_key)
    if provider:
        # 如果 api_key 为空但已有 key，保留已有 key
        if not api_key and provider.api_key:
            encrypted_key = provider.api_key
        provider.name = name
        provider.base_url = base_url
        provider.default_model = default_model
        provider.api_format = api_format
        provider.api_key = encrypted_key if encrypted_key else None
        provider.is_enabled = True
        provider.is_default = is_default
        provider.updated_at = datetime.now(timezone.utc).isoformat()
    else:
        provider = AIProvider(
            id=id,
            name=name,
            base_url=base_url,
            default_model=default_model,
            api_format=api_format,
            api_key=encrypted_key if encrypted_key else None,
            is_enabled=True,
            is_default=is_default,
            updated_at=datetime.now(timezone.utc).isoformat(),
        )
    session.add(provider)
    session.commit()

    return {"id": id, "name": name, "has_api_key": bool(api_key)}

@router.delete("/providers/{provider_id}")
def delete_provider(
    provider_id: str,
    current_admin: User = Depends(get_current_admin),
    session: Session = Depends(get_session),
):
    """删除 Provider"""
    provider = session.get(AIProvider, provider_id)
    if provider:
        session.delete(provider)
        session.commit()
    return {"message": "Deleted"}

@router.post("/providers/{provider_id}/test")
def test_provider_endpoint(
    provider_id: str,
    current_admin: User = Depends(get_current_admin),
):
    """测试 Provider 连接"""
    success, message = test_provider(provider_id)
    return {"success": success, "message": message}

# --- Embedding 配置 ---

@router.get("/embedding-config")
def get_embedding_config(
    current_admin: User = Depends(get_current_admin),
    session: Session = Depends(get_session),
):
    """获取 Embedding 配置（API Key 仅返回 has_key 标记）"""
    config = session.get(EmbeddingConfig, 1)
    if not config:
        return {"api_key_configured": False, "base_url": "", "model": "BAAI/bge-m3"}
    return {
        "api_key_configured": bool(config.api_key),
        "base_url": config.base_url,
        "model": config.model,
    }

@router.put("/embedding-config")
def save_embedding_config(
    api_key: Optional[str] = None,
    base_url: Optional[str] = None,
    model: Optional[str] = None,
    current_admin: User = Depends(get_current_admin),
    session: Session = Depends(get_session),
):
    """保存 Embedding 配置"""
    config = session.get(EmbeddingConfig, 1)
    if not config:
        config = EmbeddingConfig(id=1)
        session.add(config)
        session.flush()

    if api_key is not None:
        config.api_key = encrypt_value(api_key) if api_key else None
    if base_url is not None:
        config.base_url = base_url
    if model is not None:
        config.model = model
    config.updated_at = datetime.now(timezone.utc).isoformat()

    session.add(config)
    session.commit()
    return {"message": "Embedding 配置已保存", "api_key_configured": bool(config.api_key)}

@router.post("/embedding-test")
def test_embedding(
    current_admin: User = Depends(get_current_admin),
    session: Session = Depends(get_session),
):
    """测试 Embedding 配置是否可用"""
    config = session.get(EmbeddingConfig, 1)

    if config and config.api_key:
        # 使用专用 embedding 配置
        api_key = decrypt_value(config.api_key)
        base_url = config.base_url or "https://api.siliconflow.cn/v1"
        model = config.model or "BAAI/bge-m3"
    else:
        # 回退到默认 provider
        from services.ai.client import get_default_provider
        default = get_default_provider()
        if not default or not default.get("api_key"):
            return {"success": False, "message": "未配置 Embedding API Key，也未找到默认 Provider"}
        api_key = default["api_key"]
        base_url = default.get("base_url", "https://api.siliconflow.cn/v1")
        model = config.model if config else "BAAI/bge-m3"

    url = f"{base_url.rstrip('/')}/embeddings"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {"model": model, "input": "test"}

    try:
        import httpx
        with httpx.Client(timeout=15.0) as client:
            resp = client.post(url, headers=headers, json=payload)
            resp.raise_for_status()
            data = resp.json()
            dim = len(data["data"][0]["embedding"])
            return {"success": True, "message": f"连接成功，向量维度: {dim}，模型: {model}"}
    except Exception as e:
        return {"success": False, "message": f"连接失败: {str(e)}"}
