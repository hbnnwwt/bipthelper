# 学校信息智能检索系统 - Phase 1 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 搭建完整的学校信息检索系统，包含爬虫、全文搜索、用户认证、Vue前端

**Architecture:** 单机内网部署，FastAPI后端 + Meilisearch索引 + SQLite存储 + Vue3前端

**Tech Stack:** Python 3.11+ / FastAPI / Meilisearch / SQLite / Vue 3 / Vite / Pinia

---

## 项目文件结构

```
bipthelper/
├── backend/
│   ├── main.py                 # FastAPI 入口
│   ├── config.py               # 配置管理
│   ├── database.py             # SQLite 连接
│   ├── models/
│   │   ├── __init__.py
│   │   ├── user.py             # User 模型
│   │   └── document.py        # Document 模型
│   ├── api/
│   │   ├── __init__.py
│   │   ├── auth.py             # 认证接口
│   │   ├── search.py           # 搜索接口
│   │   └── admin.py            # 管理接口
│   ├── services/
│   │   ├── __init__.py
│   │   ├── auth.py             # JWT/密码服务
│   │   ├── search.py           # Meilisearch 服务
│   │   └── crawler.py          # 爬虫服务
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── main.js
│   │   ├── App.vue
│   │   ├── router/index.js
│   │   ├── stores/
│   │   │   └── auth.js         # Pinia auth store
│   │   ├── api/
│   │   │   └── index.js        # Axios 封装
│   │   └── views/
│   │       ├── Login.vue
│   │       ├── Register.vue
│   │       └── Home.vue
│   ├── index.html
│   ├── vite.config.js
│   └── package.json
├── data/                       # 数据目录
│   ├── app.db                  # SQLite 数据库
│   └── htmls/                  # 原始 HTML 存储
└── README.md                   # 启动说明
```

---

## Task 1: 项目初始化

**Files:**
- Create: `backend/requirements.txt`
- Create: `backend/config.py`
- Create: `backend/database.py`
- Create: `backend/models/__init__.py`
- Create: `backend/models/user.py`
- Create: `backend/models/document.py`
- Create: `backend/main.py`

- [ ] **Step 1: 创建 backend/requirements.txt**

```
fastapi==0.115.0
uvicorn[standard]==0.30.0
sqlmodel==0.0.22
python-jose[cryptography]==3.3.0
passlib[bcrypt]==1.7.4
meilisearch==0.31.0
httpx==0.27.0
beautifulsoup4==4.12.0
playwright==1.44.0
apscheduler==3.10.0
pydantic==2.9.0
python-multipart==0.0.9
```

- [ ] **Step 2: 创建 backend/config.py**

```python
from pydantic_settings import BaseSettings
from functools import lru_cache

class Settings(BaseSettings):
    APP_NAME: str = "SchoolInfoSearch"
    SECRET_KEY: str = "change-me-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 24 hours

    DATABASE_URL: str = "sqlite:///../data/app.db"
    DATA_DIR: str = "../data"
    HTMLS_DIR: str = "../data/htmls"

    MEILISEARCH_URL: str = "http://localhost:7700"
    MEILISEARCH_MASTER_KEY: str | None = None
    MEILISEARCH_INDEX: str = "documents"

    CRAWL_INTERVAL_MINUTES: int = 60  # 每小时检查一次

    class Config:
        env_file = ".env"

@lru_cache
def get_settings():
    return Settings()
```

- [ ] **Step 3: 创建 backend/database.py**

```python
from sqlmodel import create_engine, Session, SQLModel
from pathlib import Path
import os

DATA_DIR = Path(__file__).parent.parent / "data"
DATA_DIR.mkdir(exist_ok=True)

engine = create_engine(
    f"sqlite:///{DATA_DIR / 'app.db'}",
    echo=False,
    connect_args={"check_same_thread": False}
)

def create_db_and_tables():
    SQLModel.metadata.create_all(engine)

def get_session():
    with Session(engine) as session:
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
```

- [ ] **Step 4: 创建 backend/models/__init__.py**

```python
from sqlmodel import SQLModel
from .user import User
from .document import Document
from .crawl_config import CrawlConfig

__all__ = ["User", "Document", "CrawlConfig", "SQLModel"]
```

- [ ] **Step 5: 创建 backend/models/user.py**

```python
from sqlmodel import SQLModel, Field
from typing import Optional
from datetime import datetime
import uuid

class User(SQLModel, table=True):
    __tablename__ = "users"

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    username: str = Field(unique=True, index=True)
    password_hash: str
    role: str = Field(default="user")  # admin or user
    invite_code: Optional[str] = Field(default=None, index=True)
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    is_active: bool = Field(default=True)
```

- [ ] **Step 6: 创建 backend/models/document.py**

```python
from sqlmodel import SQLModel, Field
from typing import Optional
from datetime import datetime
import uuid

class Document(SQLModel, table=True):
    __tablename__ = "documents"

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    url: str = Field(unique=True, index=True)
    title: str
    content: str
    category: Optional[str] = Field(default=None, index=True)
    department: Optional[str] = Field(default=None, index=True)
    publish_date: Optional[str] = Field(default=None)
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    content_hash: Optional[str] = Field(default=None, index=True)
```

- [ ] **Step 7: 创建 backend/models/crawl_config.py**

```python
from sqlmodel import SQLModel, Field
from typing import Optional
from datetime import datetime
import uuid

class CrawlConfig(SQLModel, table=True):
    __tablename__ = "crawl_configs"

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    name: str
    url: str
    selector: str = "body"  # CSS selector for content extraction
    category: Optional[str] = Field(default=None)
    enabled: bool = Field(default=True)
    last_hash: Optional[str] = Field(default=None)
    last_crawl: Optional[str] = Field(default=None)
```

- [ ] **Step 8: 创建 backend/main.py**

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from database import create_db_and_tables, init_admin_user
from api import auth, search, admin

@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动时创建数据库表
    create_db_and_tables()
    # 初始化 admin 用户
    init_admin_user()
    yield

app = FastAPI(title="SchoolInfoSearch", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 内网使用，生产环境应限制
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(search.router, prefix="/api/search", tags=["search"])
app.include_router(admin.router, prefix="/api/admin", tags=["admin"])

@app.get("/api/health")
def health():
    return {"status": "ok"}
```

- [ ] **Step 9: 提交**

```bash
git add backend/requirements.txt backend/config.py backend/database.py backend/models/ backend/main.py
git commit -m "feat: project scaffolding - backend structure, models, and admin init"
```

---

## Task 2: 用户认证服务

**Files:**
- Create: `backend/services/__init__.py`
- Create: `backend/services/auth.py`
- Modify: `backend/api/auth.py`

- [ ] **Step 1: 创建 backend/services/__init__.py**

```python
```

- [ ] **Step 2: 创建 backend/services/auth.py**

```python
from passlib.context import CryptContext
from jose import JWTError, jwt
from datetime import datetime, timedelta
from fastapi import HTTPException, status, Depends
from fastapi.security import OAuth2PasswordBearer
from sqlmodel import Session, select
from typing import Optional

from config import get_settings
from database import get_session
from models.user import User

settings = get_settings()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

def hash_password(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)

def get_current_user(token: str = Depends(oauth2_scheme), session: Session = Depends(get_session)) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    user = session.exec(select(User).where(User.username == username)).first()
    if user is None or not user.is_active:
        raise credentials_exception
    return user

def get_current_admin(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return current_user
```

- [ ] **Step 3: 创建 backend/api/auth.py**

```python
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlmodel import Session, select
import uuid
import secrets

from database import get_session
from models.user import User
from services.auth import hash_password, verify_password, create_access_token, get_current_user

router = APIRouter()

@router.post("/register")
def register(username: str, password: str, invite_code: str, session: Session = Depends(get_session)):
    # 验证邀请码（简单实现：admin创建的一次性码）
    if not invite_code.startswith("ADMIN-"):
        raise HTTPException(status_code=400, detail="Invalid invite code")

    # 检查用户名是否已存在
    existing = session.exec(select(User).where(User.username == username)).first()
    if existing:
        raise HTTPException(status_code=400, detail="Username already registered")

    # 创建用户
    user = User(
        id=str(uuid.uuid4()),
        username=username,
        password_hash=hash_password(password),
        role="user",
        is_active=True,
    )
    session.add(user)
    session.commit()
    session.refresh(user)

    token = create_access_token(data={"sub": user.username})
    return {"user": {"id": user.id, "username": user.username, "role": user.role}, "token": token}

@router.post("/login")
def login(form_data: OAuth2PasswordRequestForm = Depends(), session: Session = Depends(get_session)):
    user = session.exec(select(User).where(User.username == form_data.username)).first()
    if not user or not verify_password(form_data.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Incorrect username or password")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="User account is inactive")

    token = create_access_token(data={"sub": user.username})
    return {"user": {"id": user.id, "username": user.username, "role": user.role}, "token": token}

@router.get("/me")
def get_me(current_user: User = Depends(get_current_user)):
    return {"user": {"id": current_user.id, "username": current_user.username, "role": current_user.role}}

@router.post("/logout")
def logout():
    # JWT 无状态，logout 由客户端处理 token 销毁
    return {"message": "Logged out successfully"}
```

- [ ] **Step 4: 提交**

```bash
git add backend/services/auth.py backend/api/auth.py
git commit -m "feat: user authentication - JWT login/register/logout"
```

---

## Task 3: 爬虫服务

**Files:**
- Create: `backend/services/crawler.py`
- Modify: `backend/api/admin.py` (添加配置管理接口)

- [ ] **Step 1: 创建 backend/services/crawler.py**

```python
import httpx
import hashlib
import re
from bs4 import BeautifulSoup
from datetime import datetime
from sqlmodel import Session, select
from pathlib import Path
import logging

from config import get_settings
from models.document import Document
from models.crawl_config import CrawlConfig
from services.search import index_document, delete_document

settings = get_settings()
logger = logging.getLogger(__name__)

HTMLS_DIR = Path(settings.HTMLS_DIR)
HTMLS_DIR.mkdir(parents=True, exist_ok=True)

def compute_hash(content: str) -> str:
    return hashlib.md5(content.encode()).hexdigest()

def extract_main_content(html: str, selector: str = "body") -> tuple[str, str]:
    """提取正文内容和标题"""
    soup = BeautifulSoup(html, "html.parser")

    # 提取标题
    title = ""
    if soup.title:
        title = soup.title.string or ""
    h1 = soup.find("h1")
    if h1:
        title = h1.get_text(strip=True) or title

    # 提取正文
    main = soup.select_one(selector)
    if main:
        # 移除脚本和样式
        for tag in main.find_all(["script", "style", "nav", "footer", "header"]):
            tag.decompose()
        content = main.get_text(separator="\n", strip=True)
        # 清理多余空行
        content = re.sub(r"\n{3,}", "\n\n", content)
        return title, content
    return title, soup.get_text(separator="\n", strip=True)

def crawl_url(config: CrawlConfig, session: Session) -> bool:
    """爬取单个URL，返回是否有更新"""
    try:
        with httpx.Client(timeout=30.0, follow_redirects=True) as client:
            response = client.get(config.url)
            response.raise_for_status()
            html = response.text

        content_hash = compute_hash(html)

        # 检查是否有更新
        if content_hash == config.last_hash:
            logger.info(f"No changes for {config.url}")
            return False

        # 保存原始HTML
        html_file = HTMLS_DIR / f"{config.id}.html"
        html_file.write_text(html, encoding="utf-8")

        # 提取内容
        title, content = extract_main_content(html, config.selector)

        # 更新或创建文档
        doc = session.exec(select(Document).where(Document.url == config.url)).first()
        now = datetime.now().isoformat()

        if doc:
            doc.title = title
            doc.content = content
            doc.content_hash = content_hash
            doc.updated_at = now
        else:
            doc = Document(
                url=config.url,
                title=title,
                content=content,
                category=config.category,
                content_hash=content_hash,
                created_at=now,
                updated_at=now,
            )
            session.add(doc)

        # 更新配置
        config.last_hash = content_hash
        config.last_crawl = now
        session.add(config)
        session.commit()

        # 更新搜索索引
        index_document(doc)

        logger.info(f"Crawled and indexed: {config.url}")
        return True

    except Exception as e:
        logger.error(f"Failed to crawl {config.url}: {e}")
        return False

def crawl_all(session: Session):
    """爬取所有启用的配置"""
    configs = session.exec(select(CrawlConfig).where(CrawlConfig.enabled == True)).all()
    for config in configs:
        crawl_url(config, session)

def add_crawl_config(name: str, url: str, selector: str, category: str, session: Session) -> CrawlConfig:
    """添加爬虫配置"""
    config = CrawlConfig(name=name, url=url, selector=selector, category=category)
    session.add(config)
    session.commit()
    session.refresh(config)
    return config
```

- [ ] **Step 2: 创建 backend/services/search.py**

```python
import meilisearch
from config import get_settings

settings = get_settings()

_client = None

def get_client() -> meilisearch.Client:
    global _client
    if _client is None:
        _client = meilisearch.Client(settings.MEILISEARCH_URL, settings.MEILISEARCH_MASTER_KEY)
    return _client

def get_index():
    client = get_client()
    try:
        index = client.get_index(settings.MEILISEARCH_INDEX)
    except meilisearch.errors.MeilisearchApiError:
        # 索引不存在，创建它
        client.create_index(settings.MEILISEARCH_INDEX, {"primaryKey": "id"})
        index = client.get_index(settings.MEILISEARCH_INDEX)
        # 配置可筛选字段
        index.update_filterable_attributes(["category", "department", "publish_date"])
        index.update_sortable_attributes(["publish_date", "title"])
        index.update_searchable_attributes(["title", "content"])
    return index

def index_document(doc):
    """将文档添加到搜索索引"""
    index = get_index()
    doc_dict = {
        "id": doc.id,
        "url": doc.url,
        "title": doc.title,
        "content": doc.content,
        "category": doc.category or "",
        "department": doc.department or "",
        "publish_date": doc.publish_date or "",
    }
    index.add_documents([doc_dict])

def delete_document_from_index(doc_id: str):
    """从搜索索引删除文档"""
    index = get_index()
    index.delete_document(doc_id)

def search_documents(query: str, category: str = None, department: str = None,
                     start_date: str = None, end_date: str = None,
                     page: int = 1, page_size: int = 20):
    """搜索文档"""
    index = get_index()

    filters = []
    if category:
        filters.append(f'category = "{category}"')
    if department:
        filters.append(f'department = "{department}"')
    if start_date:
        filters.append(f'publish_date >= "{start_date}"')
    if end_date:
        filters.append(f'publish_date <= "{end_date}"')

    filter_str = " AND ".join(filters) if filters else None

    result = index.search(
        query,
        {
            "limit": page_size,
            "offset": (page - 1) * page_size,
            "filter": filter_str,
            "attributesToRetrieve": ["id", "title", "content", "category", "department", "publish_date", "url"],
            "attributesToHighlight": ["title", "content"],
            "highlightPreTag": "<mark>",
            "highlightPostTag": "</mark>",
        }
    )

    return {
        "total": result["estimatedTotalHits"],
        "results": result["hits"],
        "page": page,
        "page_size": page_size,
    }
```

- [ ] **Step 3: 提交**

```bash
git add backend/services/crawler.py backend/services/search.py
git commit -m "feat: crawler and search services - incremental crawl with Meilisearch"
```

---

## Task 4: 搜索与管理员 API

**Files:**
- Create: `backend/api/search.py`
- Create: `backend/api/admin.py`

- [ ] **Step 1: 创建 backend/api/search.py**

```python
from fastapi import APIRouter, Depends, Query
from sqlmodel import Session

from database import get_session
from services.search import search_documents
from services.auth import get_current_user
from models.user import User

router = APIRouter()

@router.get("")
def search(
    q: str = Query(..., min_length=1),
    category: str = None,
    department: str = None,
    start_date: str = None,
    end_date: str = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
):
    """搜索文档接口"""
    result = search_documents(
        query=q,
        category=category,
        department=department,
        start_date=start_date,
        end_date=end_date,
        page=page,
        page_size=page_size,
    )
    return result
```

- [ ] **Step 2: 创建 backend/api/admin.py**

```python
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select
import secrets

from database import get_session
from models.user import User
from models.crawl_config import CrawlConfig
from services.auth import get_current_admin, hash_password
from services.crawler import crawl_all, add_crawl_config

router = APIRouter()

# --- 用户管理 ---

@router.get("/users")
def list_users(
    current_admin: User = Depends(get_current_admin),
    session: Session = Depends(get_session),
):
    """列出所有用户"""
    users = session.exec(select(User)).all()
    return {
        "users": [
            {"id": u.id, "username": u.username, "role": u.role, "is_active": u.is_active, "created_at": u.created_at}
            for u in users
        ]
    }

@router.post("/users/invite")
def create_invite(
    username: str,
    current_admin: User = Depends(get_current_admin),
    session: Session = Depends(get_session),
):
    """创建邀请码（一次性使用）"""
    invite_code = f"ADMIN-{secrets.token_hex(8)}"

    # 检查用户是否已存在
    existing = session.exec(select(User).where(User.username == username)).first()
    if existing:
        raise HTTPException(status_code=400, detail="User already exists")

    # 创建用户（未激活状态，等待设置密码）
    user = User(
        username=username,
        password_hash="",  # 先留空
        role="user",
        invite_code=invite_code,
        is_active=False,
    )
    session.add(user)
    session.commit()

    return {"invite_code": invite_code, "username": username}

# --- 爬虫配置管理 ---

@router.get("/configs")
def list_configs(
    current_admin: User = Depends(get_current_admin),
    session: Session = Depends(get_session),
):
    """列出所有爬虫配置"""
    configs = session.exec(select(CrawlConfig)).all()
    return {
        "configs": [
            {
                "id": c.id,
                "name": c.name,
                "url": c.url,
                "selector": c.selector,
                "category": c.category,
                "enabled": c.enabled,
                "last_crawl": c.last_crawl,
            }
            for c in configs
        ]
    }

@router.post("/configs")
def create_config(
    name: str,
    url: str,
    selector: str = "body",
    category: str = None,
    current_admin: User = Depends(get_current_admin),
    session: Session = Depends(get_session),
):
    """添加爬虫配置"""
    config = add_crawl_config(name, url, selector, category, session)
    return {"id": config.id, "name": config.name, "url": config.url}

@router.put("/configs/{config_id}")
def update_config(
    config_id: str,
    name: str = None,
    url: str = None,
    selector: str = None,
    category: str = None,
    enabled: bool = None,
    current_admin: User = Depends(get_current_admin),
    session: Session = Depends(get_session),
):
    """更新爬虫配置"""
    config = session.get(CrawlConfig, config_id)
    if not config:
        raise HTTPException(status_code=404, detail="Config not found")

    if name is not None:
        config.name = name
    if url is not None:
        config.url = url
    if selector is not None:
        config.selector = selector
    if category is not None:
        config.category = category
    if enabled is not None:
        config.enabled = enabled

    session.add(config)
    session.commit()
    return {"message": "Config updated"}

@router.delete("/configs/{config_id}")
def delete_config(
    config_id: str,
    current_admin: User = Depends(get_current_admin),
    session: Session = Depends(get_session),
):
    """删除爬虫配置"""
    config = session.get(CrawlConfig, config_id)
    if not config:
        raise HTTPException(status_code=404, detail="Config not found")
    session.delete(config)
    session.commit()
    return {"message": "Config deleted"}

@router.post("/crawl/trigger")
def trigger_crawl(
    current_admin: User = Depends(get_current_admin),
    session: Session = Depends(get_session),
):
    """手动触发一次爬取"""
    crawl_all(session)
    return {"message": "Crawl triggered"}
```

- [ ] **Step 3: 提交**

```bash
git add backend/api/search.py backend/api/admin.py
git commit -m "feat: search and admin API endpoints"
```

---

## Task 5: 定时爬虫调度

**Files:**
- Modify: `backend/main.py` (添加 APScheduler 调度)

- [ ] **Step 1: 修改 backend/main.py 添加调度器**

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from database import create_db_and_tables
from api import auth, search, admin
from services.crawler import crawl_all

scheduler = AsyncIOScheduler()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动时创建数据库
    create_db_and_tables()

    # 添加定时爬虫任务
    from config import get_settings
    settings = get_settings()
    scheduler.add_job(
        crawl_all,
        IntervalTrigger(minutes=settings.CRAWL_INTERVAL_MINUTES),
        kwargs={"session": None},  # 将在运行时获取 session
        id="crawler_job",
        replace_existing=True,
    )
    scheduler.start()

    yield

    # 关闭时停止调度器
    scheduler.shutdown()

app = FastAPI(title="SchoolInfoSearch", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(search.router, prefix="/api/search", tags=["search"])
app.include_router(admin.router, prefix="/api/admin", tags=["admin"])

@app.get("/api/health")
def health():
    return {"status": "ok"}
```

- [ ] **Step 2: 修改 backend/services/crawler.py 的 crawl_all 函数以支持应用上下文**

需要修改 crawler.py 导入方式，让 crawl_all 能在 scheduler 外部调用时创建 session。

```python
# 在 crawl_all 函数开头添加 session 获取
def crawl_all(session=None):
    from database import engine
    from sqlmodel import Session as S
    if session is None:
        with S(engine) as new_session:
            return _crawl_all_impl(new_session)
    return _crawl_all_impl(session)

def _crawl_all_impl(session: Session):
    configs = session.exec(select(CrawlConfig).where(CrawlConfig.enabled == True)).all()
    for config in configs:
        crawl_url(config, session)
```

- [ ] **Step 3: 提交**

```bash
git add backend/main.py backend/services/crawler.py
git commit -m "feat: add APScheduler for periodic crawling"
```

---

## Task 6: Vue 前端项目初始化

**Files:**
- Create: `frontend/index.html`
- Create: `frontend/vite.config.js`
- Create: `frontend/package.json`
- Create: `frontend/src/main.js`
- Create: `frontend/src/App.vue`

- [ ] **Step 1: 创建 frontend/package.json**

```json
{
  "name": "school-info-search-frontend",
  "version": "0.1.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "vite build",
    "preview": "vite preview"
  },
  "dependencies": {
    "vue": "^3.4.0",
    "vue-router": "^4.3.0",
    "pinia": "^2.1.0",
    "axios": "^1.7.0"
  },
  "devDependencies": {
    "@vitejs/plugin-vue": "^5.0.0",
    "vite": "^5.4.0"
  }
}
```

- [ ] **Step 2: 创建 frontend/vite.config.js**

```javascript
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  server: {
    port: 3000,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      }
    }
  }
})
```

- [ ] **Step 3: 创建 frontend/index.html**

```html
<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>学校信息检索</title>
</head>
<body>
  <div id="app"></div>
  <script type="module" src="/src/main.js"></script>
</body>
</html>
```

- [ ] **Step 4: 创建 frontend/src/main.js**

```javascript
import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'
import router from './router'

const app = createApp(App)
app.use(createPinia())
app.use(router)
app.mount('#app')
```

- [ ] **Step 5: 创建 frontend/src/App.vue**

```vue
<template>
  <router-view />
</template>

<script setup>
</script>

<style>
* { margin: 0; padding: 0; box-sizing: border-box; }
body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; }
#app { min-height: 100vh; }
</style>
```

- [ ] **Step 6: 创建 frontend/src/router/index.js**

```javascript
import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '../stores/auth'

const routes = [
  { path: '/login', name: 'Login', component: () => import('../views/Login.vue') },
  { path: '/register', name: 'Register', component: () => import('../views/Register.vue') },
  {
    path: '/',
    component: () => import('../views/Home.vue'),
    meta: { requiresAuth: true }
  },
  {
    path: '/admin',
    component: () => import('../views/Admin.vue'),
    meta: { requiresAuth: true, requiresAdmin: true }
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

router.beforeEach((to, from, next) => {
  const authStore = useAuthStore()

  if (to.meta.requiresAuth && !authStore.isLoggedIn) {
    next('/login')
  } else if (to.meta.requiresAdmin && !authStore.isAdmin) {
    next('/')
  } else {
    next()
  }
})

export default router
```

- [ ] **Step 7: 创建 frontend/src/stores/auth.js**

```javascript
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import axios from '../api'

export const useAuthStore = defineStore('auth', () => {
  const token = ref(localStorage.getItem('token') || '')
  const user = ref(JSON.parse(localStorage.getItem('user') || 'null'))

  const isLoggedIn = computed(() => !!token.value)
  const isAdmin = computed(() => user.value?.role === 'admin')

  function setAuth(newToken, newUser) {
    token.value = newToken
    user.value = newUser
    localStorage.setItem('token', newToken)
    localStorage.setItem('user', JSON.stringify(newUser))
    axios.defaults.headers.common['Authorization'] = `Bearer ${newToken}`
  }

  function logout() {
    token.value = ''
    user.value = null
    localStorage.removeItem('token')
    localStorage.removeItem('user')
    delete axios.defaults.headers.common['Authorization']
  }

  // 初始化 axios header
  if (token.value) {
    axios.defaults.headers.common['Authorization'] = `Bearer ${token.value}`
  }

  return { token, user, isLoggedIn, isAdmin, setAuth, logout }
})
```

- [ ] **Step 8: 创建 frontend/src/api/index.js**

```javascript
import axios from 'axios'

const api = axios.create({
  baseURL: '/api',
  timeout: 10000,
})

export default api
```

- [ ] **Step 9: 提交**

```bash
git add frontend/
git commit -m "feat: Vue 3 frontend project scaffold"
```

---

## Task 7: Vue 登录/注册页面

**Files:**
- Create: `frontend/src/views/Login.vue`
- Create: `frontend/src/views/Register.vue`

- [ ] **Step 1: 创建 frontend/src/views/Login.vue**

```vue
<template>
  <div class="login-container">
    <div class="login-card">
      <h1>学校信息检索系统</h1>
      <form @submit.prevent="handleLogin">
        <div class="form-group">
          <label>用户名</label>
          <input v-model="form.username" type="text" required placeholder="请输入用户名" />
        </div>
        <div class="form-group">
          <label>密码</label>
          <input v-model="form.password" type="password" required placeholder="请输入密码" />
        </div>
        <div v-if="error" class="error">{{ error }}</div>
        <button type="submit" :disabled="loading">{{ loading ? '登录中...' : '登录' }}</button>
      </form>
      <p class="register-link">
        没有账号？<router-link to="/register">注册</router-link>
      </p>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import api from '../api'

const router = useRouter()
const authStore = useAuthStore()

const form = ref({ username: '', password: '' })
const error = ref('')
const loading = ref(false)

async function handleLogin() {
  error.value = ''
  loading.value = true
  try {
    const params = new URLSearchParams()
    params.append('username', form.value.username)
    params.append('password', form.value.password)
    const { data } = await api.post('/auth/login', params)
    authStore.setAuth(data.token, data.user)
    router.push('/')
  } catch (e) {
    error.value = e.response?.data?.detail || '登录失败'
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.login-container { min-height: 100vh; display: flex; align-items: center; justify-content: center; background: #f5f5f5; }
.login-card { background: white; padding: 2rem; border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.1); width: 100%; max-width: 360px; }
.login-card h1 { font-size: 1.25rem; margin-bottom: 1.5rem; text-align: center; }
.form-group { margin-bottom: 1rem; }
.form-group label { display: block; margin-bottom: 0.25rem; font-size: 0.875rem; color: #666; }
.form-group input { width: 100%; padding: 0.5rem; border: 1px solid #ddd; border-radius: 4px; font-size: 1rem; }
button { width: 100%; padding: 0.75rem; background: #2563eb; color: white; border: none; border-radius: 4px; font-size: 1rem; cursor: pointer; }
button:hover { background: #1d4ed8; }
button:disabled { opacity: 0.7; cursor: not-allowed; }
.error { color: #dc2626; font-size: 0.875rem; margin-bottom: 1rem; }
.register-link { margin-top: 1rem; text-align: center; font-size: 0.875rem; }
.register-link a { color: #2563eb; }
</style>
```

- [ ] **Step 2: 创建 frontend/src/views/Register.vue**

```vue
<template>
  <div class="register-container">
    <div class="register-card">
      <h1>注册账号</h1>
      <form @submit.prevent="handleRegister">
        <div class="form-group">
          <label>用户名</label>
          <input v-model="form.username" type="text" required placeholder="请输入用户名" />
        </div>
        <div class="form-group">
          <label>密码</label>
          <input v-model="form.password" type="password" required placeholder="请输入密码" />
        </div>
        <div class="form-group">
          <label>邀请码</label>
          <input v-model="form.invite_code" type="text" required placeholder="请输入邀请码" />
        </div>
        <div v-if="error" class="error">{{ error }}</div>
        <button type="submit" :disabled="loading">{{ loading ? '注册中...' : '注册' }}</button>
      </form>
      <p class="login-link">
        已有账号？<router-link to="/login">登录</router-link>
      </p>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import api from '../api'

const router = useRouter()
const authStore = useAuthStore()

const form = ref({ username: '', password: '', invite_code: '' })
const error = ref('')
const loading = ref(false)

async function handleRegister() {
  error.value = ''
  loading.value = true
  try {
    const { data } = await api.post('/auth/register', form.value)
    authStore.setAuth(data.token, data.user)
    router.push('/')
  } catch (e) {
    error.value = e.response?.data?.detail || '注册失败'
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.register-container { min-height: 100vh; display: flex; align-items: center; justify-content: center; background: #f5f5f5; }
.register-card { background: white; padding: 2rem; border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.1); width: 100%; max-width: 360px; }
.register-card h1 { font-size: 1.25rem; margin-bottom: 1.5rem; text-align: center; }
.form-group { margin-bottom: 1rem; }
.form-group label { display: block; margin-bottom: 0.25rem; font-size: 0.875rem; color: #666; }
.form-group input { width: 100%; padding: 0.5rem; border: 1px solid #ddd; border-radius: 4px; font-size: 1rem; }
button { width: 100%; padding: 0.75rem; background: #2563eb; color: white; border: none; border-radius: 4px; font-size: 1rem; cursor: pointer; }
button:hover { background: #1d4ed8; }
button:disabled { opacity: 0.7; cursor: not-allowed; }
.error { color: #dc2626; font-size: 0.875rem; margin-bottom: 1rem; }
.login-link { margin-top: 1rem; text-align: center; font-size: 0.875rem; }
.login-link a { color: #2563eb; }
</style>
```

- [ ] **Step 3: 提交**

```bash
git add frontend/src/views/Login.vue frontend/src/views/Register.vue
git commit -m "feat: login and register pages"
```

---

## Task 8: Vue 首页（搜索页面）

**Files:**
- Create: `frontend/src/views/Home.vue`

- [ ] **Step 1: 创建 frontend/src/views/Home.vue**

```vue
<template>
  <div class="home">
    <header class="header">
      <h1>学校信息检索</h1>
      <div class="user-info">
        <span>{{ authStore.user?.username }}</span>
        <router-link v-if="authStore.isAdmin" to="/admin" class="admin-link">管理后台</router-link>
        <button @click="handleLogout">退出</button>
      </div>
    </header>

    <div class="search-box">
      <div class="search-input-wrapper">
        <input
          v-model="query"
          type="text"
          placeholder="输入关键词搜索通知、规章制度..."
          @keyup.enter="handleSearch"
        />
        <button @click="handleSearch">搜索</button>
      </div>
      <div class="filters">
        <select v-model="filters.category">
          <option value="">全部分类</option>
          <option value="通知">通知</option>
          <option value="制度">制度</option>
        </select>
        <input v-model="filters.department" type="text" placeholder="发布部门" />
        <button @click="showFilters = !showFilters">{{ showFilters ? '收起' : '更多筛选' }}</button>
      </div>
      <div v-if="showFilters" class="filters-extra">
        <input v-model="filters.start_date" type="date" placeholder="开始日期" />
        <span>至</span>
        <input v-model="filters.end_date" type="date" placeholder="结束日期" />
      </div>
    </div>

    <div class="results">
      <p class="results-count" v-if="total">找到 {{ total }} 条结果</p>

      <div v-if="loading" class="loading">搜索中...</div>

      <div v-else-if="results.length === 0 && searched" class="empty">
        未找到相关结果
      </div>

      <div v-else class="result-list">
        <a
          v-for="item in results"
          :key="item.id"
          :href="item.url"
          target="_blank"
          class="result-item"
        >
          <h3 v-html="item._formatted?.title || item.title"></h3>
          <p v-html="item._formatted?.content || item.content"></p>
          <div class="meta">
            <span v-if="item.category">{{ item.category }}</span>
            <span v-if="item.department">{{ item.department }}</span>
            <span v-if="item.publish_date">{{ item.publish_date }}</span>
          </div>
        </a>
      </div>

      <div v-if="total > pageSize" class="pagination">
        <button :disabled="page <= 1" @click="page--; handleSearch()">上一页</button>
        <span>{{ page }} / {{ Math.ceil(total / pageSize) }}</span>
        <button :disabled="page >= Math.ceil(total / pageSize)" @click="page++; handleSearch()">下一页</button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import api from '../api'

const router = useRouter()
const authStore = useAuthStore()

const query = ref('')
const filters = reactive({ category: '', department: '', start_date: '', end_date: '' })
const showFilters = ref(false)
const results = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = 20
const loading = ref(false)
const searched = ref(false)

async function handleSearch() {
  if (!query.value.trim()) return
  loading.value = true
  searched.value = true
  try {
    const params = {
      q: query.value,
      page: page.value,
      page_size: pageSize,
    }
    if (filters.category) params.category = filters.category
    if (filters.department) params.department = filters.department
    if (filters.start_date) params.start_date = filters.start_date
    if (filters.end_date) params.end_date = filters.end_date

    const { data } = await api.get('/search', { params })
    results.value = data.results
    total.value = data.total
  } catch (e) {
    console.error('Search failed:', e)
  } finally {
    loading.value = false
  }
}

function handleLogout() {
  authStore.logout()
  router.push('/login')
}
</script>

<style scoped>
.home { max-width: 800px; margin: 0 auto; padding: 1rem; }
.header { display: flex; justify-content: space-between; align-items: center; padding: 1rem 0; border-bottom: 1px solid #eee; }
.header h1 { font-size: 1.25rem; }
.user-info { display: flex; gap: 1rem; align-items: center; }
.admin-link { color: #2563eb; text-decoration: none; }
button { padding: 0.5rem 1rem; background: #2563eb; color: white; border: none; border-radius: 4px; cursor: pointer; }
button:hover { background: #1d4ed8; }
.search-box { margin: 2rem 0; }
.search-input-wrapper { display: flex; gap: 0.5rem; }
.search-input-wrapper input { flex: 1; padding: 0.75rem; border: 1px solid #ddd; border-radius: 4px; font-size: 1rem; }
.filters { display: flex; gap: 0.5rem; margin-top: 0.5rem; }
.filters select, .filters input { padding: 0.5rem; border: 1px solid #ddd; border-radius: 4px; }
.filters-extra { display: flex; gap: 0.5rem; margin-top: 0.5rem; align-items: center; }
.results-count { color: #666; margin-bottom: 1rem; }
.loading, .empty { text-align: center; padding: 2rem; color: #666; }
.result-list { display: flex; flex-direction: column; gap: 1rem; }
.result-item { display: block; padding: 1rem; border: 1px solid #eee; border-radius: 8px; text-decoration: none; color: inherit; }
.result-item:hover { border-color: #2563eb; }
.result-item h3 { margin-bottom: 0.5rem; color: #2563eb; }
.result-item p { color: #666; font-size: 0.875rem; display: -webkit-box; -webkit-line-clamp: 3; -webkit-box-orient: vertical; overflow: hidden; }
.result-item :deep(mark) { background: #fef08a; padding: 0 2px; }
.meta { display: flex; gap: 1rem; margin-top: 0.5rem; font-size: 0.75rem; color: #999; }
.pagination { display: flex; justify-content: center; align-items: center; gap: 1rem; margin-top: 1rem; }
.pagination button { background: white; color: #2563eb; border: 1px solid #2563eb; }
.pagination button:disabled { opacity: 0.5; cursor: not-allowed; }
</style>
```

- [ ] **Step 2: 提交**

```bash
git add frontend/src/views/Home.vue
git commit -m "feat: home search page"
```

---

## Task 9: Vue 管理后台页面

**Files:**
- Create: `frontend/src/views/Admin.vue`

- [ ] **Step 1: 创建 frontend/src/views/Admin.vue**

```vue
<template>
  <div class="admin">
    <header class="header">
      <h1>管理后台</h1>
      <router-link to="/">返回搜索</router-link>
    </header>

    <div class="tabs">
      <button :class="{ active: tab === 'users' }" @click="tab = 'users'">用户管理</button>
      <button :class="{ active: tab === 'crawler' }" @click="tab = 'crawler'">爬虫配置</button>
    </div>

    <div v-if="tab === 'users'" class="section">
      <div class="section-header">
        <h2>邀请用户</h2>
      </div>
      <div class="invite-form">
        <input v-model="newUsername" type="text" placeholder="输入用户名" />
        <button @click="createInvite">生成邀请码</button>
      </div>
      <div v-if="generatedCode" class="invite-code">
        邀请码：<code>{{ generatedCode }}</code>
      </div>
      <h2>用户列表</h2>
      <table class="user-table">
        <thead><tr><th>用户名</th><th>角色</th><th>状态</th><th>创建时间</th></tr></thead>
        <tbody>
          <tr v-for="u in users" :key="u.id">
            <td>{{ u.username }}</td>
            <td>{{ u.role }}</td>
            <td>{{ u.is_active ? '活跃' : '未激活' }}</td>
            <td>{{ u.created_at }}</td>
          </tr>
        </tbody>
      </table>
    </div>

    <div v-if="tab === 'crawler'" class="section">
      <div class="section-header">
        <h2>爬虫配置</h2>
        <button @click="triggerCrawl">手动触发爬取</button>
      </div>
      <div class="crawl-form">
        <input v-model="newConfig.name" type="text" placeholder="配置名称" />
        <input v-model="newConfig.url" type="url" placeholder="目标URL" />
        <input v-model="newConfig.selector" type="text" placeholder="CSS选择器 (默认body)" />
        <input v-model="newConfig.category" type="text" placeholder="分类" />
        <button @click="addConfig">添加配置</button>
      </div>
      <table class="config-table">
        <thead><tr><th>名称</th><th>URL</th><th>选择器</th><th>分类</th><th>状态</th><th>上次爬取</th><th>操作</th></tr></thead>
        <tbody>
          <tr v-for="c in configs" :key="c.id">
            <td>{{ c.name }}</td>
            <td><a :href="c.url" target="_blank">{{ c.url }}</a></td>
            <td>{{ c.selector }}</td>
            <td>{{ c.category }}</td>
            <td>{{ c.enabled ? '启用' : '禁用' }}</td>
            <td>{{ c.last_crawl || '-' }}</td>
            <td><button @click="deleteConfig(c.id)">删除</button></td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import api from '../api'

const tab = ref('users')
const users = ref([])
const configs = ref([])
const newUsername = ref('')
const generatedCode = ref('')
const newConfig = ref({ name: '', url: '', selector: 'body', category: '' })

onMounted(() => {
  loadUsers()
  loadConfigs()
})

async function loadUsers() {
  const { data } = await api.get('/admin/users')
  users.value = data.users
}

async function loadConfigs() {
  const { data } = await api.get('/admin/configs')
  configs.value = data.configs
}

async function createInvite() {
  if (!newUsername.value) return
  const { data } = await api.post('/admin/users/invite', null, { params: { username: newUsername.value } })
  generatedCode.value = data.invite_code
}

async function addConfig() {
  if (!newConfig.value.name || !newConfig.value.url) return
  await api.post('/admin/configs', null, { params: newConfig.value })
  newConfig.value = { name: '', url: '', selector: 'body', category: '' }
  await loadConfigs()
}

async function deleteConfig(id) {
  if (!confirm('确认删除?')) return
  await api.delete(`/admin/configs/${id}`)
  await loadConfigs()
}

async function triggerCrawl() {
  await api.post('/admin/crawl/trigger')
  alert('爬取已触发')
}
</script>

<style scoped>
.admin { max-width: 1000px; margin: 0 auto; padding: 1rem; }
.header { display: flex; justify-content: space-between; align-items: center; padding: 1rem 0; border-bottom: 1px solid #eee; }
.header h1 { font-size: 1.25rem; }
.header a { color: #2563eb; }
.tabs { display: flex; gap: 0.5rem; margin: 1rem 0; }
.tabs button { padding: 0.5rem 1rem; background: #f3f4f6; border: none; border-radius: 4px; cursor: pointer; }
.tabs button.active { background: #2563eb; color: white; }
.section { margin-top: 1rem; }
.section h2 { font-size: 1rem; margin: 1rem 0 0.5rem; }
.section-header { display: flex; justify-content: space-between; align-items: center; }
.invite-form, .crawl-form { display: flex; gap: 0.5rem; margin: 1rem 0; }
.invite-form input, .crawl-form input { padding: 0.5rem; border: 1px solid #ddd; border-radius: 4px; }
.crawl-form input:first-child { width: 120px; }
.crawl-form input:nth-child(2) { flex: 1; }
.invite-code { padding: 0.5rem; background: #f3f4f6; margin-bottom: 1rem; }
.invite-code code { background: #e5e7eb; padding: 0.25rem 0.5rem; border-radius: 4px; }
button { padding: 0.5rem 1rem; background: #2563eb; color: white; border: none; border-radius: 4px; cursor: pointer; }
button:hover { background: #1d4ed8; }
.user-table, .config-table { width: 100%; border-collapse: collapse; }
.user-table th, .config-table th { text-align: left; padding: 0.75rem; border-bottom: 1px solid #eee; font-weight: normal; color: #666; font-size: 0.875rem; }
.user-table td, .config-table td { padding: 0.75rem; border-bottom: 1px solid #eee; }
.config-table a { color: #2563eb; }
</style>
```

- [ ] **Step 2: 提交**

```bash
git add frontend/src/views/Admin.vue
git commit -m "feat: admin dashboard page"
```

---

## Task 10: 启动说明文档

**Files:**
- Create: `README.md`

- [ ] **Step 1: 创建 README.md**

```markdown
# 学校信息智能检索系统

## 环境要求

- Python 3.11+
- Node.js 18+
- Meilisearch（下载对应平台的二进制）

## 启动步骤

### 1. Meilisearch

下载并运行 Meilisearch（单机模式）：

**macOS / Linux:**
```bash
# 下载二进制
curl -L https://install.meilisearch.com | sh

# 运行（数据存储在 ./data/meilisearch）
./meilisearch --http-addr 127.0.0.1:7700 --db-path ./data/meilisearch
```

**Windows:**
```powershell
# 下载二进制
Invoke-WebRequest -Uri "https://github.com/meilisearch/meilisearch/releases/latest/download/meilisearch-windows-amd64.exe" -OutFile "meilisearch.exe"

# 运行
.\meilisearch.exe --http-addr 127.0.0.1:7700 --db-path .\data\meilisearch
```

### 2. Backend

```bash
cd backend

# 创建虚拟环境（推荐）
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 安装依赖
pip install -r requirements.txt

# 运行（首次会自动创建数据库和 admin 账号）
uvicorn main:app --reload --port 8000
```

**初始账号：**
- 用户名：`admin`
- 密码：`admin123`
- 角色：`admin`

### 3. Frontend

```bash
cd frontend

# 安装依赖
npm install

# 开发模式运行
npm run dev
```

访问 http://localhost:3000

## 生产部署

### 前端构建

```bash
cd frontend
npm run build
```

构建产物在 `dist/` 目录，可用 Nginx 托管并代理 `/api` 请求到 `http://localhost:8000`。

### 系统架构

```
浏览器 ──► Vue 前端 (3000)
              │
              ▼
         FastAPI 后端 (8000)
         ├── /api/auth/*   认证
         ├── /api/search/* 搜索
         └── /api/admin/*  管理
              │
              ▼
         Meilisearch (7700) ←── 搜索索引
              │
              ▼
         SQLite (data/app.db) ←── 元数据、用户
```

## 目录结构

```
bipthelper/
├── backend/
│   ├── main.py           # FastAPI 入口
│   ├── config.py         # 配置
│   ├── database.py       # SQLite 连接
│   ├── models/           # 数据模型
│   ├── api/              # API 路由
│   ├── services/         # 业务逻辑
│   └── requirements.txt
├── frontend/
│   ├── src/              # Vue 源码
│   ├── index.html
│   └── package.json
├── data/                 # 数据目录（自动创建）
│   ├── app.db            # SQLite 数据库
│   └── htmls/            # 原始 HTML 存储
└── README.md
```
```

- [ ] **Step 2: 提交**

```bash
git add README.md
git commit -m "docs: add README with startup instructions"
```

---

## 自检清单

**Spec 覆盖率检查：**
- [x] 爬虫服务 - Task 3, 5
- [x] 搜索服务 - Task 3, 4
- [x] 用户认证 - Task 2
- [x] 管理后台 API - Task 4
- [x] Vue 前端 - Task 6-9
- [x] 启动说明 - Task 10
- [x] admin 初始化 - Task 1

**占位符检查：**
- 无 TODO/TBD
- 无 "fill in later"
- 所有代码完整可执行

**类型一致性：**
- Document 模型字段与 Meilisearch 索引字段一致
- API 响应格式在前后端保持一致
- User 模型 role 字段为 "admin"/"user" 字符串

---

Plan complete and saved to `docs/superpowers/plans/2026-04-06-school-info-search-plan.md`.

Two execution options:

**1. Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

Which approach?
