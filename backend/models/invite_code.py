from sqlmodel import SQLModel, Field
from typing import Optional
from datetime import datetime, timezone
import secrets

from models._utils import _now

class InviteCode(SQLModel, table=True):
    __tablename__ = "invite_codes"

    code: str = Field(primary_key=True)  # e.g. "ACT-a3f8c2d1"
    code_type: str = Field(default="anonymous")  # "designated" | "anonymous"
    designated_username: Optional[str] = Field(default=None, index=True)  # 仅 designated
    created_by: str = Field(default="admin")
    created_at: str = Field(default_factory=_now)
    expires_at: str = Field(default_factory=lambda: _now())  # 创建时由服务层填充
    used_by: Optional[str] = Field(default=None, index=True)  # User.id
    used_at: Optional[str] = Field(default=None)

    @staticmethod
    def generate_code() -> str:
        return f"ACT-{secrets.token_hex(4).upper()}"  # 8 hex chars
