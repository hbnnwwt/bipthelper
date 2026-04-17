from sqlmodel import SQLModel, Field
from typing import Optional
from datetime import datetime, timezone

class ChatSession(SQLModel, table=True):
    __tablename__ = "chat_sessions"
    id: str = Field(primary_key=True)
    user_id: str = Field(index=True)
    title: str = ""
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

class ChatMessage(SQLModel, table=True):
    __tablename__ = "chat_messages"
    id: str = Field(primary_key=True)
    session_id: str = Field(index=True)
    role: str  # "user" 或 "assistant"
    content: str = ""
    sources: str = "[]"  # JSON 字符串
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
