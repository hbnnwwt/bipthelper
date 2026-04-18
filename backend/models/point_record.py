from sqlmodel import SQLModel, Field
from datetime import datetime, timezone
from typing import Optional
import uuid

from models._utils import _now

class PointRecord(SQLModel, table=True):
    __tablename__ = "point_records"

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    user_id: str = Field(index=True)
    amount: int  # 正=收入，负=消耗
    record_type: str  # "register" | "checkin" | "qa" | "admin_set"
    note: Optional[str] = Field(default="")
    created_at: str = Field(default_factory=_now)
