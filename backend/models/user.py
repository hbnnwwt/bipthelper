from sqlmodel import SQLModel, Field
from typing import Optional
from datetime import datetime, timezone
import uuid

from models._utils import _now

class User(SQLModel, table=True):
    __tablename__ = "users"

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    username: str = Field(unique=True, index=True)
    password_hash: str
    role: str = Field(default="user")  # admin or user
    invite_code: Optional[str] = Field(default=None, index=True)
    created_at: str = Field(default_factory=_now)
    is_active: bool = Field(default=True)
    points: int = Field(default=0)
    last_checkin_date: Optional[str] = Field(default=None)  # "YYYY-MM-DD" UTC
    nickname: Optional[str] = Field(default=None)
    phone: Optional[str] = Field(default=None)
    avatar_url: Optional[str] = Field(default=None)
