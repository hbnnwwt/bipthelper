from sqlmodel import SQLModel, Field
from typing import Optional
from datetime import datetime, timezone
import uuid

def _now() -> str:
    return datetime.now(timezone.utc).isoformat()

class Document(SQLModel, table=True):
    __tablename__ = "documents"

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    url: str = Field(unique=True, index=True)
    title: str
    content: str
    category: Optional[str] = Field(default=None, index=True)
    parent_category: Optional[str] = Field(default=None, index=True)   # 大类
    sub_category: Optional[str] = Field(default=None, index=True)      # 小类
    department: Optional[str] = Field(default=None, index=True)
    publish_date: Optional[str] = Field(default=None)
    created_at: str = Field(default_factory=_now)
    updated_at: str = Field(default_factory=_now)
    content_hash: Optional[str] = Field(default=None, index=True)
    # === 新增字段 ===
    ai_status: str = Field(default="pending")            # pending / success / failed / manual
    ai_suggested_categories: str = Field(default="")      # LLM 返回的候选分类，逗号分隔
    ai_reviewed_at: str = Field(default="")              # 人工审核时间，ISO 格式
