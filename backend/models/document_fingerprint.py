import hashlib
from sqlmodel import SQLModel, Field
from datetime import datetime, timezone

def _now() -> str:
    return datetime.now(timezone.utc).isoformat()

def _url_hash(url: str) -> str:
    """对 URL 归一化后取 SHA256 前32字符作为 hash key"""
    from urllib.parse import urlparse, parse_qs
    parsed = urlparse(url)
    # 去除 fragment，query params 排序后拼接
    query = "&".join(
        sorted(f"{k}={v}" for k, vs in parse_qs(parsed.query).items() for v in sorted(vs))
    )
    normalized = parsed._replace(fragment="", query=query).geturl()
    return hashlib.sha256(normalized.encode()).hexdigest()[:32]

class DocumentFingerprint(SQLModel, table=True):
    __tablename__ = "document_fingerprints"

    url_hash: str = Field(primary_key=True)  # SHA256(normalized_url)[:32]
    url: str = Field(index=True)
    content_hash: str = ""                    # SHA256 正文内容
    created_at: str = Field(default_factory=_now)
    updated_at: str = Field(default_factory=_now)
    doc_id: str = Field(index=True)          # 关联 Document.id