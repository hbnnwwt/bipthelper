# 双仓库完全解耦 - bipthelper 侧实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** bipthelper 暴露 `/api/documents` 系列接口给 bipt_info_organizer 调用，移除 crawler_service，完成双仓库解耦。

**Architecture:**
- 在 `search_service/routers/` 下新增 `organizer_docs.py`，提供文档推送/更新/删除接口，带 `X-Organizer-Key` 鉴权
- 移除 `backend/crawler_service/` 整个目录及所有前端静态资源
- 新增 `ORGANIZER_API_KEY` 配置项

**Tech Stack:** FastAPI, SQLModel, httpx (仅测试用)

---

## 文件变更总览

| 操作 | 路径 |
|------|------|
| 修改 | `backend/config.py` |
| 创建 | `backend/search_service/routers/organizer_docs.py` |
| 修改 | `backend/search_service/main.py` |
| 删除 | `backend/crawler_service/` (整个目录) |
| 修改 | `.gitignore` |

---

### Task 1: 添加 ORGANIZER_API_KEY 配置

**Files:**
- Modify: `backend/config.py:44` (在 Settings 类末尾添加)

- [ ] **Step 1: 添加配置项**

在 `config.py` 的 `Settings` 类中，`QDRANT_COLLECTION` 下方添加：

```python
    # Organizer API 鉴权
    ORGANIZER_API_KEY: str = ""
```

- [ ] **Step 2: 在 .env 示例中添加**

```bash
echo "ORGANIZER_API_KEY=your-secret-key-here" >> backend/.env
```

- [ ] **Step 3: 提交**

```bash
git add backend/config.py backend/.env
git commit -m "config: add ORGANIZER_API_KEY for bipt_info_organizer auth"
```

---

### Task 2: 创建 organizer_docs.py（文档推送接口）

**Files:**
- Create: `backend/search_service/routers/organizer_docs.py`

```python
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Header
from typing import Optional
from pydantic import BaseModel
from sqlmodel import Session, select

from database import get_session
from models.document import Document
from config import get_settings
from services.search import index_document

router = APIRouter()
settings = get_settings()


class DocumentIngest(BaseModel):
    """来自 bipt_info_organizer 的文档推送格式"""
    id: str
    title: str
    url: Optional[str] = ""
    content: Optional[str] = ""
    parent_category: Optional[str] = ""
    sub_category: Optional[str] = ""
    category: Optional[str] = ""
    department: Optional[str] = ""
    publish_date: Optional[str] = ""
    ai_suggested_categories: Optional[str] = ""
    ai_status: str = "pending"


def verify_organizer_key(x_organizer_key: str = Header(None)):
    if not settings.ORGANIZER_API_KEY:
        raise HTTPException(status_code=503, detail="Organizer API not configured")
    if x_organizer_key != settings.ORGANIZER_API_KEY:
        raise HTTPException(status_code=403, detail="Invalid organizer key")


@router.post("/documents")
def ingest_document(
    doc: DocumentIngest,
    session: Session = Depends(get_session),
    _: None = Depends(verify_organizer_key),
):
    """接收来自 bipt_info_organizer 的文档并建立索引"""
    existing = session.get(Document, doc.id)
    if existing:
        # 更新已有文档
        for key, value in doc.model_dump().items():
            if value is not None:
                setattr(existing, key, value)
        existing.updated_at = datetime.now(timezone.utc)
        session.add(existing)
        session.commit()
        index_document(existing)
        return {"message": "Document updated", "id": doc.id}

    # 新建文档
    db_doc = Document(**doc.model_dump())
    db_doc.updated_at = datetime.now(timezone.utc)
    session.add(db_doc)
    session.commit()
    index_document(db_doc)
    return {"message": "Document ingested", "id": doc.id}


@router.put("/documents/{doc_id}")
def update_document(
    doc_id: str,
    data: dict,
    session: Session = Depends(get_session),
    _: None = Depends(verify_organizer_key),
):
    """更新文档分类/元数据"""
    doc = session.get(Document, doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    for key, value in data.items():
        if hasattr(doc, key) and value is not None:
            setattr(doc, key, value)
    doc.updated_at = datetime.now(timezone.utc)
    session.add(doc)
    session.commit()
    from services.search import delete_document_from_index
    delete_document_from_index(doc_id)
    index_document(doc)
    return {"message": "Document updated", "id": doc_id}


@router.delete("/documents/{doc_id}")
def delete_document(
    doc_id: str,
    session: Session = Depends(get_session),
    _: None = Depends(verify_organizer_key),
):
    """删除文档"""
    doc = session.get(Document, doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    from services.search import delete_document_from_index
    delete_document_from_index(doc_id)
    session.delete(doc)
    session.commit()
    return {"message": "Document deleted", "id": doc_id}


@router.post("/documents/{doc_id}/approve")
def approve_document(
    doc_id: str,
    categories: Optional[str] = None,
    session: Session = Depends(get_session),
    _: None = Depends(verify_organizer_key),
):
    """采纳 AI 分类建议"""
    doc = session.get(Document, doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    target = categories if categories else doc.ai_suggested_categories
    if not target:
        raise HTTPException(status_code=400, detail="No suggested categories")
    doc.category = target
    doc.ai_status = "success"
    doc.ai_reviewed_at = datetime.now(timezone.utc).isoformat()
    session.add(doc)
    session.commit()
    from services.search import delete_document_from_index
    delete_document_from_index(doc_id)
    index_document(doc)
    return {"message": "Category approved", "category": target}


@router.get("/documents/categories")
def get_categories(
    session: Session = Depends(get_session),
    _: None = Depends(verify_organizer_key),
):
    """获取分类筛选数据（供 organizer 前端下拉框使用）"""
    parent_cats = session.exec(
        select(Document.parent_category).where(Document.parent_category.isnot(None)).where(Document.parent_category != "").distinct()
    ).all()
    sub_cats = session.exec(
        select(Document.sub_category).where(Document.sub_category.isnot(None)).where(Document.sub_category != "").distinct()
    ).all()
    cats = session.exec(
        select(Document.category).where(Document.category.isnot(None)).where(Document.category != "").distinct()
    ).all()
    return {
        "parent_categories": sorted(set(parent_cats)),
        "sub_categories": sorted(set(sub_cats)),
        "categories": sorted(set(cats)),
    }
```

- [ ] **Step 1: 创建 organizer_docs.py**

创建上述文件到 `backend/search_service/routers/organizer_docs.py`。

- [ ] **Step 2: 注册到 main.py**

修改 `backend/search_service/main.py`，添加 import 和 router 注册：

```python
from search_service.routers.organizer_docs import router as organizer_router
# ...
app.include_router(organizer_router, prefix="/api", tags=["organizer"])
```

- [ ] **Step 3: 验证启动**

```bash
cd backend && python -c "from search_service.main import app; print('OK')"
```

- [ ] **Step 4: 提交**

```bash
git add backend/search_service/routers/organizer_docs.py backend/search_service/main.py
git commit -m "feat: add organizer_docs API with X-Organizer-Key auth"
```

---

### Task 3: 验证 organizer API 可正常调用

**Files:**
- Test: 直接用 curl 测试接口

- [ ] **Step 1: 生成 API key**

```bash
cd backend && python -c "import secrets; print(secrets.token_hex(16))"
```

- [ ] **Step 2: 更新 .env**

```bash
# 将上方生成的 key 写入 backend/.env
ORGANIZER_API_KEY=上面生成的key
```

- [ ] **Step 3: 启动服务并测试**

```bash
python -m uvicorn search_service.main:app --port 8000
# 新开终端:
curl -X POST http://localhost:8000/api/documents \
  -H "X-Organizer-Key: your-key" \
  -H "Content-Type: application/json" \
  -d '{"id":"test-001","title":"测试文档","url":"http://example.com","content":"正文","category":"测试分类"}'
# 预期: {"message":"Document ingested","id":"test-001"}

curl http://localhost:8000/api/documents/categories -H "X-Organizer-Key: your-key"
# 预期: {"parent_categories":[],"sub_categories":[],"categories":["测试分类"]}
```

- [ ] **Step 4: 提交**

```bash
git add backend/.env
git commit -m "test: verify organizer API endpoints work correctly"
```

---

### Task 4: 移除 crawler_service

**Files:**
- Delete: `backend/crawler_service/` (整个目录)
- Modify: `.gitignore` (移除 crawler_service 相关条目)

- [ ] **Step 1: 删除目录**

```bash
rm -rf backend/crawler_service
```

- [ ] **Step 2: 检查 .gitignore**

确认 `.gitignore` 中没有特别针对 crawler_service 的条目（`assets/frontend` 应该是通配的，不需要改）。

- [ ] **Step 3: 确认服务仍可启动**

```bash
python -m uvicorn search_service.main:app --port 8000
# 确认启动成功，无 crawler_service 引用报错
```

- [ ] **Step 4: 提交**

```bash
git add -A backend/crawler_service
git commit -m "remove: delete crawler_service (replaced by bipt_info_organizer repo)"
```

---

### Task 5: 更新 build.bat（移除 crawler SPA 构建）

**Files:**
- Modify: `build.bat`

当前 build.bat 构建两个 SPA 并分别部署到 crawler_service 和 search_service。移除 crawler_service 相关行后变为单 SPA 构建。

- [ ] **Step 1: 读取当前 build.bat**

确认当前内容。

- [ ] **Step 2: 修改 build.bat**

移除所有 crawler_service 相关行，包括：
- "Step 4" 的 crawler SPA 构建
- "Step 5" 的 crawler SPA 部署
- dist-crawler 目录相关命令

修改后的 build.bat 应只构建 search SPA 并部署到 `backend/search_service/assets/frontend/`。

- [ ] **Step 3: 提交**

```bash
git add build.bat
git commit -m "build: remove crawler SPA from build script (decoupled to separate repo)"
```

---

## bipthelper 侧实施完毕检查清单

- [ ] ORGANIZER_API_KEY 配置已添加
- [ ] `/api/documents` POST/PUT/DELETE/approve/categories 接口正常
- [ ] crawler_service 目录已删除
- [ ] build.bat 已更新为单 SPA
- [ ] bipthelper 服务启动正常，无报错
- [ ] 已推送到 GitHub

---

## bipt_info_organizer 侧（新建仓库）

> 以下为 bipt_info_organizer 新仓库的实施计划，可在 bipthelper 侧完成后独立进行。

### Task 6: 创建 bipt_info_organizer 仓库

**Files:**
- Create: 完整仓库结构（见下方）

**目录结构：**

```
bipt_info_organizer/
├── backend/
│   ├── main.py
│   ├── config.py
│   ├── database.py
│   ├── models/
│   │   ├── __init__.py
│   │   ├── crawl_config.py
│   │   └── audit_log.py
│   ├── routers/
│   │   ├── __init__.py
│   │   ├── crawl_admin.py     # 从 crawler_service 复制，保留 SSE 状态
│   │   ├── auth.py            # 从 crawler_service 复制
│   │   ├── organizer_docs.py  # 调用 bipthelper API 的文档接口
│   │   └── audit.py           # 本地审计日志
│   ├── services/
│   │   ├── __init__.py
│   │   ├── crawler.py         # 从 backend/services/crawler.py 复制
│   │   └── helper_client.py   # 封装对 bipthelper 的 HTTP 调用
│   └── requirements.txt
├── frontend/
│   ├── index.html
│   ├── crawler-admin.html
│   ├── vite.config.js
│   ├── vite.crawler.config.js
│   └── src/
│       ├── main.js
│       ├── mainCrawler.js
│       ├── router.js
│       ├── routerCrawler.js
│       ├── api.js
│       ├── views/
│       │   ├── Login.vue
│       │   ├── Register.vue
│       │   └── Admin.vue
│       └── components/admin/
│           ├── CrawlerTab.vue
│           ├── DocsTab.vue
│           └── AuditTab.vue
├── scripts/
│   └── build.bat
├── README.md
└── .env
```

- [ ] **Step 1: 创建仓库目录**

```bash
mkdir -p bipt_info_organizer/backend/routers
mkdir -p bipt_info_organizer/backend/models
mkdir -p bipt_info_organizer/backend/services
mkdir -p bipt_info_organizer/frontend/src/views
mkdir -p bipt_info_organizer/frontend/src/components/admin
mkdir -p bipt_info_organizer/scripts
```

- [ ] **Step 2: 从 bipthelper 复制文件**

从 `crawler_service/` 复制：
- `routers/crawl_admin.py` → `backend/routers/`
- `routers/crawler_auth.py` → `backend/routers/auth.py`
- `routers/crawler_documents.py` → `backend/routers/organizer_docs.py`（需重写）

从 `backend/services/crawler.py` 复制 → `backend/services/`

- [ ] **Step 3: 创建 helper_client.py**

```python
import httpx
from config import get_settings

class HelperClient:
    def __init__(self):
        settings = get_settings()
        self.base_url = settings.BIPTHELPER_URL.rstrip("/")
        self.api_key = settings.ORGANIZER_API_KEY
        self._client = httpx.Client(timeout=30)

    def _headers(self):
        return {"X-Organizer-Key": self.api_key}

    def ingest_document(self, doc_data: dict):
        return self._client.post(f"{self.base_url}/api/documents", json=doc_data, headers=self._headers())

    def update_document(self, doc_id: str, data: dict):
        return self._client.put(f"{self.base_url}/api/documents/{doc_id}", json=data, headers=self._headers())

    def delete_document(self, doc_id: str):
        return self._client.delete(f"{self.base_url}/api/documents/{doc_id}", headers=self._headers())

    def get_categories(self):
        return self._client.get(f"{self.base_url}/api/documents/categories", headers=self._headers())

    def get_documents(self, params: dict):
        return self._client.get(f"{self.base_url}/api/documents", params=params, headers=self._headers())

    def approve_document(self, doc_id: str, categories: str = None):
        payload = {"categories": categories} if categories else {}
        return self._client.post(f"{self.base_url}/api/documents/{doc_id}/approve", json=payload, headers=self._headers())
```

- [ ] **Step 4: 重写 organizer_docs.py（本地路由）**

将 `organizer_docs.py`（原 crawler_documents.py）改为调用 `HelperClient`：

```python
from fastapi import APIRouter, Depends, HTTPException
from typing import Optional
from pydantic import BaseModel

from services.helper_client import HelperClient

router = APIRouter()
_helper = None

def get_helper():
    global _helper
    if _helper is None:
        _helper = HelperClient()
    return _helper


class BulkDeleteRequest(BaseModel):
    ids: list[str]


@router.get("/documents/categories")
def get_categories():
    client = get_helper()
    resp = client.get_categories()
    if resp.status_code != 200:
        raise HTTPException(status_code=502, detail="Failed to fetch categories from helper")
    return resp.json()


@router.get("/documents")
def list_documents(page: int = 1, page_size: int = 20, ...):
    client = get_helper()
    resp = client.get_documents({"page": page, "page_size": page_size, ...})
    return resp.json()


@router.delete("/documents/{doc_id}")
def delete_document(doc_id: str, ...):
    client = get_helper()
    resp = client.delete_document(doc_id)
    return resp.json()
```

- [ ] **Step 5: 创建 config.py**

```python
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    APP_NAME: str = "BIPTInfoOrganizer"
    BIPTHELPER_URL: str = "http://localhost:8000"
    ORGANIZER_API_KEY: str = ""
    CRAWL_INTERVAL_MINUTES: int = 60
    CRAWL_DELAY_SECONDS: float = 2.0
    CRAWL_ARTICLE_DELAY: float = 1.0

    class Config:
        env_file = ".env"

def get_settings():
    return Settings()
```

- [ ] **Step 6: 提交**

```bash
git init
git add .
git commit -m "initial: bipt_info_organizer with crawler and helper client"
```

---

### Task 7: 前端迁移（从 bipthelper 复制 crawler SPA）

**Files:**
- Create: `frontend/src/views/Admin.vue`（重命名为 organizer admin）
- Create: `frontend/src/components/admin/CrawlerTab.vue`、`DocsTab.vue`、`AuditTab.vue`
- Create: 路由配置、API 配置

从 bipthelper 的 `frontend/dist-crawler/` 或源码中获取 crawler SPA 代码，迁移到 bipt_info_organizer 前端。

- [ ] **Step 1: 复制源码**

从 `bipthelper/frontend/src/views/AdminCrawler.vue` 复制到 `bipt_info_organizer/frontend/src/views/Admin.vue`。

从 `bipthelper/frontend/src/components/admin/` 复制 crawler 相关组件。

- [ ] **Step 2: 创建 api.js**

```javascript
import axios from 'axios'

const api = axios.create({
  baseURL: '/api',
  timeout: 30000,
})

// 从 sessionStorage 读取 token
api.interceptors.request.use(config => {
  const token = sessionStorage.getItem('token')
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

export default api
```

- [ ] **Step 3: 更新 router.js**

路由配置指向本地 `/admin`、`/login`、`/register`。

- [ ] **Step 4: 提交**

---

### Task 8: 本地 SQLite（爬虫配置 + 审计日志）

bipt_info_organizer 需要本地数据库存储：
- 爬虫配置（CrawlConfig）
- 审计日志（AuditLog）

用户/积分等数据存在 bipthelper，不在 organizer 本地。

- [ ] **Step 1: 创建 backend/models/crawl_config.py**

```python
from sqlmodel import SQLModel, Field

class CrawlConfig(SQLModel, table=True):
    id: str = Field(primary_key=True)
    name: str
    list_url: str
    category_tag: str = ""
    parent_category: str = ""
    sub_category: str = ""
    crawl_mode: str = "auto"
    auto_interval_minutes: int = 60
    enabled: bool = True
    created_at: str = ""
    updated_at: str = ""
```

- [ ] **Step 2: 创建 backend/models/audit_log.py**

```python
from sqlmodel import SQLModel, Field

class AuditLog(SQLModel, table=True):
    id: str = Field(primary_key=True)
    username: str
    action: str
    target: str = ""
    detail: str = ""
    created_at: str = ""
```

- [ ] **Step 3: 创建 backend/database.py**

```python
import os
from sqlmodel import SQLModel, create_engine

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "organizer.db")
os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

engine = create_engine(f"sqlite:///{DB_PATH}", echo=False)

def create_db_and_tables():
    from models.crawl_config import CrawlConfig
    from models.audit_log import AuditLog
    SQLModel.metadata.create_all(engine)

def get_session():
    from sqlmodel import Session
    with Session(engine) as session:
        yield session
```

- [ ] **Step 4: 更新 main.py 的 lifespan**

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    create_db_and_tables()
    start_scheduler()
    yield
```

- [ ] **Step 5: 提交**

---

### Task 9: 回归测试

**Files:**
- Test: 手动测试完整数据流

测试步骤：

1. 启动 bipthelper（8000）
2. 启动 bipt_info_organizer（8001）
3. organizer 登录 → 添加爬虫配置 → 触发爬取
4. 验证文档通过 `/api/documents` 推送到 bipthelper
5. bipthelper 搜索页面能查到刚爬取的文档
6. organizer 文档管理 tab 能看到已推送的文档
7. organizer 更新分类 → 验证 bipthelper 端同步

- [ ] **Step 1: 测试**
- [ ] **Step 2: 提交**

---

**Plan complete.** bipthelper 侧（Task 1-5）完成后，再进行 bipt_info_organizer 侧（Task 6-9）。

**Two execution options:**

**1. Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

**Which approach?**