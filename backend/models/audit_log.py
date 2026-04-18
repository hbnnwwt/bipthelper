from sqlmodel import SQLModel, Field
from typing import Optional
from datetime import datetime, timezone
import uuid

from models._utils import _now

class AuditLog(SQLModel, table=True):
    __tablename__ = "audit_logs"

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    user_id: str
    username: str
    action: str                          # 操作类型
    target: Optional[str] = None         # 操作对象 ID
    detail: Optional[str] = None        # 详细描述
    created_at: str = Field(default_factory=_now)
