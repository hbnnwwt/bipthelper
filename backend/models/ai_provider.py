from sqlmodel import SQLModel, Field
from typing import Optional
from datetime import datetime, timezone
import uuid

class AIProvider(SQLModel, table=True):
    __tablename__ = "ai_providers"

    id: str = Field(primary_key=True)  # 如 "openai", "siliconflow"
    name: str
    base_url: str = ""
    default_model: str = ""
    api_format: str = "openai"  # "openai" | "anthropic"
    api_key: Optional[str] = None
    is_enabled: bool = True
    is_default: bool = False
    updated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

class AICategoryScene(SQLModel, table=True):
    __tablename__ = "ai_category_scenes"

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    name: str                      # 场景名称，如"学校信息分类"
    provider_id: str               # 绑定的 AI Provider ID
    model: str = ""                # 覆盖 Provider 默认模型的字段
    prompt_template: str = ""      # LLM Prompt 模板
    default_categories: str = ""   # 逗号分隔的分类列表
    is_active: bool = True
    updated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
