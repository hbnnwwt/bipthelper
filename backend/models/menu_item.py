from sqlmodel import SQLModel, Field
from datetime import datetime, timezone
import uuid

class MenuItem(SQLModel, table=True):
    __tablename__ = "menu_items"

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    doc_id: str = Field(index=True)
    category: str = ""
    sub_category: str = ""
    dish_name: str = Field(index=True)
    dish_category: str = ""
    meal_type: str = ""
    menu_date: str = Field(index=True)
    source_url: str = ""
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
