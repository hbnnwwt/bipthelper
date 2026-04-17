from sqlmodel import SQLModel, Field
from typing import Optional
from datetime import datetime, timezone


class EmbeddingConfig(SQLModel, table=True):
    __tablename__ = "embedding_config"

    id: int = Field(default=1, primary_key=True)  # Singleton row
    api_key: Optional[str] = None  # Encrypted via services.encryption
    base_url: str = ""
    model: str = "BAAI/bge-m3"
    updated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
