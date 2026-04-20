from pydantic_settings import BaseSettings
from functools import lru_cache
import secrets
import os

# 手动读取 .env 中的 SECRET_KEY（避免 pydantic_settings 的 env_file 读取时机问题）
_env_path = os.path.join(os.path.dirname(__file__), ".env")
_existing_key = ""
if os.path.exists(_env_path):
    with open(_env_path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip().startswith("SECRET_KEY="):
                _existing_key = line.strip().split("=", 1)[1].strip()
                break

class Settings(BaseSettings):
    APP_NAME: str = "SchoolInfoSearch"
    SECRET_KEY: str = _existing_key  # 优先使用 .env 中已有的值
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 24 hours

    DATA_DIR: str = "../data"
    HTMLS_DIR: str = "../data/htmls"

    MEILISEARCH_URL: str = "http://localhost:7700"
    MEILISEARCH_MASTER_KEY: str | None = None
    MEILISEARCH_INDEX: str = "documents"

    CRAWL_INTERVAL_MINUTES: int = 60  # 每小时检查一次

    # 爬虫限速
    CRAWL_DELAY_SECONDS: float = 2.0   # 页面间延时（秒）
    CRAWL_ARTICLE_DELAY: float = 1.0   # 文章间延时（秒）

    # Embedding 配置
    EMBEDDING_MODEL: str = "BAAI/bge-m3"
    EMBEDDING_CHUNK_SIZE: int = 512
    EMBEDDING_CHUNK_OVERLAP: int = 50
    EMBEDDING_VECTOR_SIZE: int = 1024

    # Qdrant 配置
    QDRANT_URL: str = "http://localhost:6333"
    QDRANT_COLLECTION: str = "document_chunks"

    # Organizer API 鉴权
    ORGANIZER_API_KEY: str = ""

    class Config:
        env_file = ".env"

    def model_post_init(self, __context):
        # 如果 .env 中没有有效的 SECRET_KEY，生成并持久化
        if not self.SECRET_KEY:
            self.SECRET_KEY = secrets.token_hex(32)
            env_path = os.path.join(os.path.dirname(__file__), ".env")
            try:
                with open(env_path, "w", encoding="utf-8") as f:
                    f.write(f"SECRET_KEY={self.SECRET_KEY}\n")
            except OSError:
                pass
            # print(f"SECRET_KEY not configured. Generated and saved to .env:")
            # print(f"SECRET_KEY={self.SECRET_KEY}")

@lru_cache
def get_settings():
    return Settings()
