from sqlmodel import create_engine, Session, SQLModel
from pathlib import Path

# 导入所有模型，确保 SQLModel.metadata.create_all() 能创建所有表
from models.user import User                      # users
from models.document import Document               # documents
from models.crawl_config import CrawlConfig       # crawl_configs
from models.chat import ChatSession, ChatMessage   # chat_sessions, chat_messages
from models.ai_provider import AIProvider, AICategoryScene  # ai_providers, ai_category_scenes
from models.audit_log import AuditLog             # audit_logs
from models.invite_code import InviteCode         # invite_codes
from models.point_record import PointRecord        # point_records
from models.embedding_config import EmbeddingConfig
from models.structured_definition import StructuredDefinition
from models.menu_item import MenuItem
from models.document_fingerprint import DocumentFingerprint

DATA_DIR = Path(__file__).parent.parent / "data"
DATA_DIR.mkdir(exist_ok=True)

# === 三数据库分离 ===
# 用户数据：账号、聊天、积分等
engine = create_engine(
    f"sqlite:///{DATA_DIR / 'app.db'}",
    echo=False,
    connect_args={"check_same_thread": False}
)

# 爬取数据：文档、爬虫配置（独立文件，重置用户数据不影响爬取内容）
crawl_engine = create_engine(
    f"sqlite:///{DATA_DIR / 'crawl.db'}",
    echo=False,
    connect_args={"check_same_thread": False}
)

# API Key 数据：AI Provider、Embedding Config（独立文件，重置 app.db 不影响 Key）
key_engine = create_engine(
    f"sqlite:///{DATA_DIR / 'key.db'}",
    echo=False,
    connect_args={"check_same_thread": False}
)

# Session 绑定路由
_session_binds = {
    Document: crawl_engine,
    CrawlConfig: crawl_engine,
    AIProvider: key_engine,
    AICategoryScene: key_engine,
    EmbeddingConfig: key_engine,
    StructuredDefinition: key_engine,
    MenuItem: key_engine,
    DocumentFingerprint: key_engine,
}


def create_session(**kwargs) -> Session:
    """创建带双库路由的 Session（Document/CrawlConfig → crawl.db，其余 → app.db）"""
    return Session(engine, binds=_session_binds, **kwargs)


def create_db_and_tables():
    # 首次迁移：如果旧 app.db 里有 documents/crawl_configs，搬到 crawl.db
    _migrate_crawl_tables()

    # 各 engine 创建属于自己的表（SQLAlchemy 根据 bind 路由决定在哪个库建）
    # 三个 engine 都调用 create_all，让它们各自创建绑定到自己的表
    SQLModel.metadata.create_all(engine)
    SQLModel.metadata.create_all(crawl_engine)
    SQLModel.metadata.create_all(key_engine)

    # 迁移：为已存在的 documents 表添加新字段
    _migrate_document_columns()
    # 迁移：为已存在的 crawl_configs 表添加新字段
    _migrate_crawl_config_columns()
    # 迁移：为 structured_definitions/menu_items 表添加新字段（未来扩展用）
    _migrate_entity_fields()

def _migrate_crawl_tables():
    """如果旧 app.db 里有 documents/crawl_configs 表（含数据），迁移到 crawl.db"""
    from sqlalchemy import text, inspect

    try:
        inspector = inspect(engine)
        existing = inspector.get_table_names()
    except Exception:
        return

    if "documents" not in existing and "crawl_configs" not in existing:
        return  # 旧库里没有爬取表，无需迁移

    print("Migrating crawl tables from app.db to crawl.db ...")

    # 在 crawl.db 中创建目标表
    crawl_tables = [Document.__table__, CrawlConfig.__table__]
    SQLModel.metadata.create_all(crawl_engine, tables=crawl_tables)

    # 用 SQLite ATTACH 做跨库拷贝（零停机，一条 SQL）
    with crawl_engine.connect() as conn:
        app_db_path = str(DATA_DIR / "app.db").replace("\\", "/")
        conn.execute(text(f"ATTACH DATABASE '{app_db_path}' AS old_db"))

        if "documents" in existing:
            try:
                count = conn.execute(text("SELECT count(*) FROM old_db.documents")).scalar()
                if count and count > 0:
                    # 检查 crawl.db 中是否已有数据
                    existing_count = conn.execute(text("SELECT count(*) FROM documents")).scalar()
                    if not existing_count:
                        conn.execute(text("INSERT INTO documents SELECT * FROM old_db.documents"))
                        conn.commit()
                        print(f"  Migrated {count} documents")
            except Exception as e:
                print(f"  Skip documents migration: {e}")

        if "crawl_configs" in existing:
            try:
                count = conn.execute(text("SELECT count(*) FROM old_db.crawl_configs")).scalar()
                if count and count > 0:
                    existing_count = conn.execute(text("SELECT count(*) FROM crawl_configs")).scalar()
                    if not existing_count:
                        conn.execute(text("INSERT INTO crawl_configs SELECT * FROM old_db.crawl_configs"))
                        conn.commit()
                        print(f"  Migrated {count} crawl_configs")
            except Exception as e:
                print(f"  Skip crawl_configs migration: {e}")

        conn.execute(text("DETACH DATABASE old_db"))

    # 迁移完成后，从旧 app.db 删除已搬走的表
    with engine.connect() as conn:
        if "documents" in existing:
            try:
                conn.execute(text("DROP TABLE documents"))
                conn.commit()
                print("  Dropped documents from app.db")
            except Exception:
                pass
        if "crawl_configs" in existing:
            try:
                conn.execute(text("DROP TABLE crawl_configs"))
                conn.commit()
                print("  Dropped crawl_configs from app.db")
            except Exception:
                pass

    print("Crawl tables migration done.")

def _migrate_document_columns():
    """如果 documents 表缺少新增列，则 ALTER TABLE 添加"""
    from sqlalchemy import text
    with crawl_engine.connect() as conn:
        try:
            result = conn.execute(text("PRAGMA table_info(documents)"))
            existing_cols = {row[1] for row in result}
        except Exception:
            existing_cols = set()

        new_cols = {
            "ai_status": 'ADD COLUMN ai_status TEXT DEFAULT "pending"',
            "ai_suggested_categories": 'ADD COLUMN ai_suggested_categories TEXT DEFAULT ""',
            "ai_reviewed_at": 'ADD COLUMN ai_reviewed_at TEXT DEFAULT ""',
        }
        for col, ddl in new_cols.items():
            if col not in existing_cols:
                try:
                    conn.execute(text(f"ALTER TABLE documents {ddl}"))
                    conn.commit()
                except Exception:
                    pass

def _migrate_crawl_config_columns():
    """如果 crawl_configs 表缺少新增列，则 ALTER TABLE 添加"""
    from sqlalchemy import text
    with crawl_engine.connect() as conn:
        try:
            result = conn.execute(text("PRAGMA table_info(crawl_configs)"))
            existing_cols = {row[1] for row in result}
        except Exception:
            existing_cols = set()

        new_cols = {
            "auto_interval_hours": 'ADD COLUMN auto_interval_hours INTEGER DEFAULT 0',
        }
        for col, ddl in new_cols.items():
            if col not in existing_cols:
                try:
                    conn.execute(text(f"ALTER TABLE crawl_configs {ddl}"))
                    conn.commit()
                except Exception:
                    pass

def _migrate_entity_fields():
    """如果 structured_definitions/menu_items 表缺少新增列，则 ALTER TABLE 添加（未来扩展预留）"""
    from sqlalchemy import text
    with key_engine.connect() as conn:
        for table_name, new_cols in [
            ("structured_definitions", {}),
            ("menu_items", {}),
        ]:
            try:
                result = conn.execute(text(f"PRAGMA table_info({table_name})"))
                existing_cols = {row[1] for row in result}
            except Exception:
                existing_cols = set()

            for col, ddl in new_cols.items():
                if col not in existing_cols:
                    try:
                        conn.execute(text(f"ALTER TABLE {table_name} {ddl}"))
                        conn.commit()
                    except Exception:
                        pass

def get_session():
    with create_session() as session:
        yield session

def init_admin_user():
    """初始化 admin 用户（如果不存在）"""
    from sqlmodel import select
    from models.user import User
    from services.auth import hash_password

    with Session(engine) as session:
        existing = session.exec(select(User).where(User.username == "admin")).first()
        if not existing:
            admin = User(
                username="admin",
                password_hash=hash_password("admin123"),
                role="admin",
                is_active=True,
            )
            session.add(admin)
            session.commit()
            print("Admin user created: admin / admin123")
