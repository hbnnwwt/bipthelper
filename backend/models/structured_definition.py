from sqlmodel import SQLModel, Field
from datetime import datetime, timezone

class StructuredDefinition(SQLModel, table=True):
    __tablename__ = "structured_definitions"

    id: str = Field(primary_key=True)
    category: str = Field(index=True)
    sub_category: str = Field(index=True)
    table_name: str
    fields_schema: str = "[]"
    parser_type: str = "llm"
    created_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
