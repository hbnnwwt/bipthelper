import json
import os
import logging
import httpx
from typing import Optional

PROVIDERS_JSON = os.path.join(os.path.dirname(__file__), "providers.json")

logger = logging.getLogger(__name__)

def _load_providers_json():
    """加载默认 providers JSON 模板"""
    if not os.path.exists(PROVIDERS_JSON):
        return {}
    with open(PROVIDERS_JSON, "r", encoding="utf-8") as f:
        return json.load(f)

def get_provider_config(provider_id: str) -> Optional[dict]:
    """
    获取 Provider 配置。
    优先级：数据库中已保存 > JSON 模板
    返回包含 apiKey 的完整配置对象。
    """
    from models.ai_provider import AIProvider
    from database import engine
    from sqlmodel import Session

    # 从 DB 查找
    with Session(engine) as session:
        provider = session.get(AIProvider, provider_id)
        if provider:
            from services.encryption import decrypt_value
            api_key = ""
            if provider.api_key:
                try:
                    api_key = decrypt_value(provider.api_key)
                except Exception:
                    api_key = provider.api_key
            return {
                "id": provider.id,
                "name": provider.name,
                "base_url": provider.base_url or "",
                "default_model": provider.default_model or "",
                "api_format": provider.api_format or "openai",
                "api_key": api_key,
                "is_enabled": provider.is_enabled,
                "is_default": provider.is_default,
            }

    # 从 JSON 模板查找
    data = _load_providers_json()
    providers = data.get("providers", [])
    for p in providers:
        if p.get("id") == provider_id:
            return {
                "id": p.get("id"),
                "name": p.get("name", provider_id),
                "base_url": p.get("baseUrl", ""),
                "default_model": p.get("defaultModel", ""),
                "api_format": p.get("apiFormat", "openai"),
                "api_key": "",
                "is_enabled": True,
                "is_default": False,
            }

    return None

def get_default_provider() -> Optional[dict]:
    """获取默认 Provider 配置"""
    from models.ai_provider import AIProvider
    from database import engine
    from sqlmodel import Session, select

    # 从 DB 找 is_default
    with Session(engine) as session:
        provider = session.exec(
            select(AIProvider).where(AIProvider.is_default == True)
        ).first()
        if provider:
            return get_provider_config(provider.id)

    # 从 JSON 找 defaultProvider
    data = _load_providers_json()
    default_id = data.get("defaultProvider")
    if default_id:
        return get_provider_config(default_id)

    return None

def _create_httpx_client() -> httpx.Client:
    """创建带重试的 httpx client"""
    transport = httpx.HTTPTransport(retries=2)
    return httpx.Client(transport=transport, timeout=httpx.Timeout(10.0, read=120.0))

def call_openai_api(provider_config: dict, messages: list, model: str = None) -> str:
    """调用 OpenAI 兼容格式 API"""
    api_key = provider_config.get("api_key", "")
    base_url = provider_config.get("base_url", "https://api.openai.com/v1")
    model = model or provider_config.get("default_model", "gpt-4o")

    if not api_key:
        raise ValueError(f"Provider {provider_config['id']} has no API key")

    url = f"{base_url.rstrip('/')}/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "messages": messages,
        "max_tokens": 1024,
        "temperature": 0.3,
    }

    with _create_httpx_client() as client:
        resp = client.post(url, headers=headers, json=payload)
        resp.raise_for_status()
        result = resp.json()

    choices = result.get("choices")
    if choices and len(choices) > 0:
        content = choices[0].get("message", {}).get("content", "")
        if content:
            return content
    return ""

def call_anthropic_api(provider_config: dict, messages: list, model: str = None) -> str:
    """调用 Anthropic 兼容格式 API (Claude/MiniMax等)"""
    api_key = provider_config.get("api_key", "")
    base_url = provider_config.get("base_url", "https://api.anthropic.com/v1")
    model = model or provider_config.get("default_model", "claude-sonnet-4-20250514")

    if not api_key:
        raise ValueError(f"Provider {provider_config['id']} has no API key")

    url = f"{base_url.rstrip('/')}/messages"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "anthropic-version": "2023-06-01",
    }

    # 转换 messages：分离 system 和 user/assistant
    system_content = ""
    claude_messages = []
    for msg in messages:
        if msg["role"] == "system":
            system_content = msg["content"]
        else:
            role = "user" if msg["role"] == "user" else "assistant"
            claude_messages.append({"role": role, "content": msg["content"]})

    payload = {
        "model": model,
        "messages": claude_messages,
        "max_tokens": 1024,
    }
    if system_content:
        payload["system"] = system_content

    with _create_httpx_client() as client:
        resp = client.post(url, headers=headers, json=payload)
        resp.raise_for_status()
        result = resp.json()

    for item in result.get("content", []):
        if item.get("type") == "text":
            return item["text"]
    return ""

def call_llm(provider_id: str, messages: list, model: str = None) -> str:
    """通用 LLM 调用接口"""
    provider = get_provider_config(provider_id)
    if not provider:
        raise ValueError(f"Provider {provider_id} not found")

    if not provider.get("api_key"):
        raise ValueError(f"Provider {provider_id} has no API key configured")

    api_format = provider.get("api_format", "openai")

    if api_format == "anthropic":
        return call_anthropic_api(provider, messages, model)
    else:
        return call_openai_api(provider, messages, model)

def test_provider(provider_id: str) -> tuple[bool, str]:
    """测试 Provider 连接，返回 (success, message)"""
    try:
        provider = get_provider_config(provider_id)
        if not provider:
            return False, f"Provider {provider_id} not found"

        if not provider.get("api_key"):
            return False, "API key is not configured"

        messages = [{"role": "user", "content": "Hello, respond with OK."}]
        result = call_llm(provider_id, messages)
        return True, result[:100] if result else "OK"
    except Exception as e:
        return False, str(e)
