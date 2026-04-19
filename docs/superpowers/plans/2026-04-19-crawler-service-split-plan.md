# 服务拆分实现计划：crawler-service + search-service

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 `backend/` 拆分为两个独立 FastAPI 服务（crawler-service: 8001, search-service: 8000），共享 models/、database.py、config.py、requirements.txt。

**Architecture:**
- crawler-service：爬虫管理 API + 执行逻辑，不访问 app.db
- search-service：聊天/搜索 API + 前端静态文件，通过 crawl.db 或 HTTP 透传访问爬虫状态
- 共享：models/, database.py, config.py, limiter.py, requirements.txt, services/（部分）

**Tech Stack:** FastAPI, SQLModel, httpx, BeautifulSoup

---

## 文件归属总览

```
crawler_service/    ← 新目录
  main.py           ← 新建
  crawler.py        ← 从 services/crawler.py 移入
  routers/
    crawl_admin.py ← 从 api/admin.py 的爬虫部分拆分
    __init__.py
  database.py       ← 复制，crawl.db/key.db 可写
  models/          ← 共享（通过 symlink 或复制）
  services/
    structured_extractor.py  ← 从 services/ 移入
    parsers/       ← 从 services/parsers/ 移入
    search.py       ← 从 services/search.py 移入（embedding → MeiliSearch）
    ai/
      embedding.py ← 从 services/ai/embedding.py 移入
  requirements.shared.txt  ← 新建（crawler 专用依赖）

search_service/    ← 新目录
  main.py           ← 从 backend/main.py 拆分
  routers/
    chat.py         ← 从 api/chat.py 移入
    auth.py         ← 从 api/auth.py 移入
    admin.py        ← 从 api/admin.py 移入（保留用户管理，爬虫部分透传）
    points.py       ← 从 api/points.py 移入
    search.py       ← 新建（搜索接口）
    ai.py           ← 从 api/ai.py 移入
    __init__.py
  services/
    rag.py          ← 从 services/rag.py 移入
    auth.py         ← 从 services/auth.py 移入
    invite.py       ← 从 services/invite.py 移入
    audit.py        ← 从 services/audit.py 移入
    qdrant.py       ← 从 services/qdrant.py 移入
    structured_query.py ← 从 services/structured_query.py 移入
    ai/
      client.py     ← 从 services/ai/client.py 移入
      categorize.py ← 从 services/ai/categorize.py 移入
    __init__.py
  models/           ← 共享（通过 symlink 或复制）
  database.py       ← 复制，crawl.db 只读
  requirements.shared.txt ← 新建
  assets/           ← 前端 build 产物

共享（不移动）:
  backend/models/    ← 保持不动
  backend/database.py ← 保持不动，两服务 import 时用相对路径
  backend/config.py
  backend/limiter.py
  backend/requirements.txt
```

---

## Task 1: 创建 crawler_service 目录骨架

**Files:**
- Create: `backend/crawler_service/`
- Create: `backend/crawler_service/main.py`
- Create: `backend/crawler_service/requirements.txt`
- Create: `backend/crawler_service/routers/__init__.py`
- Create: `backend/crawler_service/routers/crawl_admin.py`

- [ ] **Step 1: 创建 crawler_service 目录**

```bash
mkdir -p backend/crawler_service/routers
mkdir -p backend/crawler_service/services/parsers
mkdir -p backend/crawler_service/services/ai
```

- [ ] **Step 2: 创建 `backend/crawler_service/main.py`**

```python
# crawler_service/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pathlib import Path
from contextlib import asynccontextmanager
import threading

from database import create_db_and_tables, engine
from services.crawler import crawl_all, start_scheduler
from routers.crawl_admin import router as crawl_admin_router

@asynccontextmanager
async def lifespan(app: FastAPI):
    create_db_and_tables()
    # 启动调度器（后台检查定时爬取）
    start_scheduler()
    yield

app = FastAPI(title="Crawler Service", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000", "http://localhost:8000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 爬虫管理 API
app.include_router(crawl_admin_router, prefix="/admin", tags=["crawler"])

@app.get("/health")
def health():
    return {"status": "ok", "service": "crawler"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
```

- [ ] **Step 3: 创建 `backend/crawler_service/requirements.txt`**

```
fastapi>=0.100
uvicorn[standard]>=0.20
sqlmodel>=0.0.14
httpx>=0.24
beautifulsoup4>=4.12
lxml>=4.9
playwright>=1.40
apScheduler>=3.10
python-multipart>=0.0.6
```

- [ ] **Step 4: 创建 `backend/crawler_service/routers/__init__.py`**

```python
```

- [ ] **Step 5: 验证 crawler_service 可启动**

```bash
cd backend
cp -r models crawler_service/
cp -r database.py crawler_service/
cp -r config.py crawler_service/
cp -r limiter.py crawler_service/
cp -r services/crawler.py crawler_service/
cp -r services/structured_extractor.py crawler_service/
cp -r services/parsers crawler_service/services/
cp -r services/search.py crawler_service/services/
cp -r services/ai/embedding.py crawler_service/services/ai/
cp -r services/ai/__init__.py crawler_service/services/ai/ 2>/dev/null || true
cp -r requirements.txt crawler_service/requirements.shared.txt

# 测试导入（不启动服务器）
cd crawler_service && python -c "from database import create_db_and_tables; print('OK')"
```

- [ ] **Step 6: 提交**

```bash
git add backend/crawler_service/
git commit -m "refactor: create crawler_service skeleton with main.py"
```

---

## Task 2: 拆分 crawler admin router

**Files:**
- Create: `backend/crawler_service/routers/crawl_admin.py`

**Context:** This file contains the crawler CRUD and crawl execution endpoints extracted from `backend/api/admin.py`.

- [ ] **Step 1: 从 `backend/api/admin.py` 提取爬虫相关函数到新文件**

Read `backend/api/admin.py` and extract these functions into `crawler_service/routers/crawl_admin.py`:
- `list_configs` (GET /admin/configs)
- `create_config` (POST /admin/configs)
- `update_config` (PUT /admin/configs/{id})
- `delete_config` (DELETE /admin/configs/{id})
- `get_crawl_status` (GET /admin/crawl/status)
- `get_crawl_progress` (GET /admin/crawl/progress, SSE)
- `start_crawl` (POST /crawl/start)
- `start_crawl_configs` (POST /crawl/start-configs)
- `stop_crawl` (POST /crawl/stop)

Also include the imports needed for these functions.

The new file should start with:
```python
from fastapi import APIRouter, Depends, HTTPException, Body
from typing import Optional
from pydantic import BaseModel
from sqlmodel import Session, select
import asyncio

from database import get_session
from models.crawl_config import CrawlConfig
from models.user import User
from services.auth import get_current_admin
from services.crawler import (
    crawl_all, crawl_configs, crawl_stop_requested, request_crawl_stop,
    crawl_progress, crawl_running, _progress_lock
)

router = APIRouter()
```

Also add these Pydantic models that admin.py uses:
```python
class BulkDeleteRequest(BaseModel):
    ids: list[str]
```

- [ ] **Step 2: 验证导入无错误**

```bash
cd backend/crawler_service && python -c "from routers.crawl_admin import router; print('OK')"
```

- [ ] **Step 3: 提交**

```bash
git add backend/crawler_service/routers/crawl_admin.py
git commit -m "refactor: extract crawl_admin router from admin.py"
```

---

## Task 3: 创建 search_service 目录骨架

**Files:**
- Create: `backend/search_service/main.py`
- Create: `backend/search_service/routers/__init__.py`
- Create: `backend/search_service/routers/chat.py`
- Create: `backend/search_service/routers/auth.py`
- Create: `backend/search_service/routers/admin.py`
- Create: `backend/search_service/routers/points.py`
- Create: `backend/search_service/routers/search.py`
- Create: `backend/search_service/routers/ai.py`

- [ ] **Step 1: 创建 search_service 目录**

```bash
mkdir -p backend/search_service/routers
mkdir -p backend/search_service/services/ai
mkdir -p backend/search_service/assets
```

- [ ] **Step 2: 创建 `backend/search_service/main.py`**

```python
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, Response
from pathlib import Path
from contextlib import asynccontextmanager

from database import create_db_and_tables, init_admin_user, engine
from limiter import limiter
from slowapi.errors import RateLimitExceeded
from routers.auth import router as auth_router
from routers.chat import router as chat_router
from routers.admin import router as admin_router
from routers.points import router as points_router
from routers.search import router as search_router
from routers.ai import router as ai_router

@asynccontextmanager
async def lifespan(app: FastAPI):
    create_db_and_tables()
    init_admin_user()
    yield

app = FastAPI(title="石化助手", lifespan=lifespan)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

FRONTEND_DIR = Path(__file__).resolve().parent / "assets" / "frontend"
ASSETS_DIR = FRONTEND_DIR / "assets"
AVATARS_DIR = Path(__file__).resolve().parent.parent / "assets" / "avatars"

@app.middleware("http")
async def spa_fallback_middleware(request: Request, call_next):
    path = request.url.path
    if path.startswith("/api/"):
        return await call_next(request)
    if path.startswith("/assets/"):
        relative_path = path[len("/assets/"):].lstrip("/")
        file_path = ASSETS_DIR / relative_path
        if file_path.is_file():
            return FileResponse(file_path)
        return await call_next(request)
    index_path = FRONTEND_DIR / "index.html"
    if index_path.is_file():
        return FileResponse(index_path)
    return await call_next(request)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router, prefix="/api/auth", tags=["auth"])
app.include_router(chat_router, prefix="/api/chat", tags=["chat"])
app.include_router(admin_router, prefix="/api/admin", tags=["admin"])
app.include_router(points_router, prefix="/api/points", tags=["points"])
app.include_router(search_router, prefix="/api/search", tags=["search"])
app.include_router(ai_router, prefix="/api/admin/ai", tags=["ai"])

if AVATARS_DIR.exists():
    app.mount("/avatars", StaticFiles(directory=str(AVATARS_DIR), html=False), name="avatars")

@app.get("/api/health")
def health():
    return {"status": "ok", "service": "search"}

@app.get("/favicon.ico", include_in_schema=False)
def favicon():
    return Response(status_code=204)

if ASSETS_DIR.exists():
    app.mount("/assets", StaticFiles(directory=str(ASSETS_DIR), html=False), name="assets")
```

- [ ] **Step 3: 复制共享文件到 search_service**

```bash
# 复制 models（通过 symlink 避免重复）
# Windows: use mklink /D
# Unix: use ln -s

# 或者直接复制（git 能跟踪）
cp -r backend/models backend/search_service/
cp backend/database.py backend/search_service/
cp backend/config.py backend/search_service/
cp backend/limiter.py backend/search_service/
cp backend/requirements.txt backend/search_service/requirements.shared.txt

# 复制 services（search service 需要的）
cp backend/services/rag.py backend/search_service/services/
cp backend/services/auth.py backend/search_service/services/
cp backend/services/invite.py backend/search_service/services/
cp backend/services/audit.py backend/search_service/services/
cp backend/services/qdrant.py backend/search_service/services/
cp backend/services/structured_query.py backend/search_service/services/
cp backend/services/__init__.py backend/search_service/services/
cp backend/services/ai/client.py backend/search_service/services/ai/
cp backend/services/ai/categorize.py backend/search_service/services/ai/
cp -r backend/services/ai/__init__.py backend/search_service/services/ai/

# 复制 API routers
cp backend/api/chat.py backend/search_service/routers/
cp backend/api/auth.py backend/search_service/routers/
cp backend/api/admin.py backend/search_service/routers/admin.py
cp backend/api/points.py backend/search_service/routers/
cp backend/api/search.py backend/search_service/routers/search.py
cp backend/api/ai.py backend/search_service/routers/ai.py
```

- [ ] **Step 4: 验证 search_service 可启动**

```bash
cd backend/search_service && python -c "from main import app; print('OK')"
```

Expected: 成功打印 "OK"

- [ ] **Step 5: 提交**

```bash
git add backend/search_service/
git commit -m "refactor: create search_service skeleton from existing backend"
```

---

## Task 4: 修正 search_service 中的模块路径

**Files:**
- Modify: `backend/search_service/services/rag.py`
- Modify: `backend/search_service/routers/chat.py`
- Modify: `backend/search_service/routers/admin.py`
- Modify: `backend/search_service/services/__init__.py`
- Modify: `backend/search_service/routers/__init__.py`

**Context:** After copying files into search_service/, the import paths are broken. For example, in `search_service/services/rag.py`, the import `from services.search import ...` should be `from services.search import ...` (relative from search_service), and `from services.ai.embedding import generate_embedding` should be from the local copy. Same for API routers importing from `services.` and `models.`.

This task fixes all broken import paths in the search_service copies.

- [ ] **Step 1: Fix rag.py imports**

In `search_service/services/rag.py`, fix:
```python
# Before (broken):
from services.search import ...
from services.ai.embedding import generate_embedding
from models.document import Document

# After:
from services.search import ...  # already in services/ of search_service
from services.ai.embedding import generate_embedding  # local copy
from models.document import Document  # local copy
```

The local copies use the same module names, so no change needed IF the Python path is set correctly. But since `search_service/` is not a package that `import services` works from, we need to add the parent to sys.path OR use relative imports.

**Best approach:** Add at the top of `search_service/main.py`:
```python
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
```

This makes `backend/` the root, so `from models.crawl_config import ...` still works (as `from models.crawl_config import ...` from backend/).

BUT WAIT - this causes conflicts: both crawler_service and search_service will have `backend/` in sys.path[0], and they'll import the same modules. This is actually OK since Python caches modules.

Actually, the cleanest approach for search_service is to NOT copy services/ai/embedding.py. Instead, keep using the ORIGINAL `backend/services/ai/embedding.py` from both services. The embedding module just needs `EmbeddingConfig` which is in `models/`.

Let me reconsider. The shared files should be:
- `models/` — shared, both import from original
- `database.py` — shared (but crawler_service needs read-write bind, search_service needs read-only bind)
- `config.py` — shared
- `limiter.py` — shared

The service-specific files should be copied/moved:
- `services/rag.py` → search_service (copy)
- `services/ai/embedding.py` → crawler_service (move, since it's only used by crawler)
- `services/ai/client.py` → search_service (copy, used by rag.py)

For `search_service`, the `services/` dir should ONLY contain files that are NOT in crawler_service:
- `services/rag.py`
- `services/auth.py`
- `services/invite.py`
- `services/audit.py`
- `services/qdrant.py`
- `services/structured_query.py`
- `services/ai/client.py`
- `services/ai/categorize.py`

Remove from search_service/services/ anything that belongs to crawler_service (embedding.py, search.py, structured_extractor.py, parsers/, crawler.py).

This is getting complex. Let me simplify: just remove embedding.py, search.py, crawler.py, structured_extractor.py, parsers/ from search_service/services/ since they're crawler-only.

**Step 1: Remove crawler-only files from search_service/services/**

```bash
# Remove crawler-only files from search_service
rm backend/search_service/services/embedding.py 2>/dev/null || true
rm backend/search_service/services/crawler.py 2>/dev/null || true
rm backend/search_service/services/structured_extractor.py 2>/dev/null || true
rm -rf backend/search_service/services/parsers 2>/dev/null || true
rm backend/search_service/services/search.py 2>/dev/null || true
```

**Step 2: Fix rag.py import of embedding**

In `search_service/services/rag.py`, the import `from services.ai.embedding import generate_embedding` should still work if we keep the original path... but embedding.py was moved to crawler_service.

The issue: `generate_embedding` is used in `rag.py` for hybrid search. But the embedding is done by crawler_service during crawling. For search_service to do hybrid search, it needs to call `generate_embedding` from embedding.py (which is now in crawler_service).

**Problem:** This creates a circular dependency or cross-service call.

**Solution:** `generate_embedding` should be kept in a shared location, OR search_service calls it via HTTP from crawler_service.

For simplicity in Phase 1: Keep `services/ai/embedding.py` in BOTH services (duplicate the file). Yes it's duplication, but it avoids complex shared module management.

Actually, the real question is: does `search_service` call `generate_embedding` directly, or only `crawler_service` does?

Looking at current code:
- `crawler.py` calls `embed_document()` from `services/ai/embedding.py` — this is write path
- `search_service/rag.py` calls `generate_embedding` from `services/ai/embedding.py` — this is read path (for query embedding)

So `generate_embedding` is used by BOTH services. The cleanest solution: keep `services/ai/embedding.py` in a shared location that both can import.

**Revised file structure:**

For BOTH services to import the same `embedding.py`:
- Keep `backend/services/ai/embedding.py` at original location
- Both `crawler_service/` and `search_service/` add `backend/` to sys.path
- This means sys.path manipulation in BOTH main.py files

**Step 3: Fix sys.path in both main.py files**

In BOTH `crawler_service/main.py` and `search_service/main.py`, add at top:
```python
import sys
from pathlib import Path
# Add backend/ parent to path so "from models import ..." and "from services import ..." work
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
```

This way both services import from the ORIGINAL `backend/models/`, `backend/services/`, `backend/database.py` etc. No file duplication needed.

**Step 4: Apply this to crawler_service too (undo unnecessary copies)**

```bash
# crawler_service should only have its own main.py and routers/
# Remove unnecessary copies
rm -rf backend/crawler_service/models 2>/dev/null || true
rm -rf backend/crawler_service/database.py 2>/dev/null || true
rm -rf backend/crawler_service/services 2>/dev/null || true
```

Wait - crawler_service copies would conflict. Let me re-plan.

**Revised clean structure:**

Both services add `backend/` to sys.path, importing from original files:
- `from models.crawl_config import CrawlConfig` → works from original backend/
- `from services.crawler import ...` → works from original backend/
- `from database import get_session` → works from original backend/

BUT: crawler_service modifies database bind (to make crawl.db writable) and search_service may need to set crawl.db as read-only. This is done via `create_session()` in database.py, which is shared.

The issue: `database.py` in original location has `_session_binds` that both services use. For crawler_service, it needs full access. For search_service, it needs crawl.db read-only.

**Solution:** `database.py` stays at original `backend/database.py`. The `_session_binds` dict determines routing by model class, not by service. Both services use the SAME routing logic. `Document` → `crawl_engine`, `User` → `engine`, etc.

For crawler_service to also WRITE to crawl.db, it just uses the same `Document` model → `crawl_engine`. No change needed. For search_service to READ crawl.db config, it can use `select(Document).where(...)` routed to `crawl_engine`.

So actually `database.py` doesn't need to be copied! Both services can import from `backend/database.py` directly. The routing by model class means both get the right engine.

**Final sys.path setup:**

In `crawler_service/main.py`:
```python
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # backend/ parent → backend/ is in path
```

In `search_service/main.py`:
```python
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # backend/ parent → backend/ is in path
```

This makes `from models import ...` and `from database import ...` and `from services.crawler import ...` all resolve to original backend/ files.

**Files to remove from crawler_service (undo unnecessary copies):**
```bash
rm -rf backend/crawler_service/models
rm -rf backend/crawler_service/database.py
rm -rf backend/crawler_service/services
```

**Files to remove from search_service:**
```bash
rm -rf backend/search_service/services  # re-add only needed ones
rm -rf backend/search_service/models
rm -rf backend/search_service/database.py
```

**Step 5: Create minimal search_service/services/ with only needed files**

search_service needs these from original services/:
- `rag.py` (copy, for search)
- `auth.py` (copy, for login)
- `invite.py` (copy, for registration)
- `audit.py` (copy)
- `qdrant.py` (copy)
- `structured_query.py` (copy)
- `ai/client.py` (copy)
- `ai/categorize.py` (copy)

```bash
mkdir -p backend/search_service/services/ai
# Copy needed files
cp backend/services/rag.py backend/search_service/services/
cp backend/services/auth.py backend/search_service/services/
cp backend/services/invite.py backend/search_service/services/
cp backend/services/audit.py backend/search_service/services/
cp backend/services/qdrant.py backend/search_service/services/
cp backend/services/structured_query.py backend/search_service/services/
cp backend/services/ai/client.py backend/search_service/services/ai/
cp backend/services/ai/categorize.py backend/search_service/services/ai/
cp backend/services/__init__.py backend/search_service/services/
cp backend/services/ai/__init__.py backend/search_service/services/ai/
```

Remove crawler-only files that may have been copied:
```bash
rm -f backend/search_service/services/embedding.py 2>/dev/null || true
rm -f backend/search_service/services/crawler.py 2>/dev/null || true
rm -f backend/search_service/services/structured_extractor.py 2>/dev/null || true
rm -rf backend/search_service/services/parsers 2>/dev/null || true
rm -f backend/search_service/services/search.py 2>/dev/null || true
```

**Step 6: Fix imports in search_service/services/rag.py**

In `search_service/services/rag.py`:
```python
# The file imports from "services.ai.embedding" which is in backend/services/ai/
# Since sys.path includes backend/, this should still work:
from services.ai.embedding import generate_embedding  # ✓ works via sys.path
from services.search import ...  # but search.py is in backend/services/ too → ✓ works
from models.document import Document  # → ✓ works
```

Actually, `from services.search import ...` works because `backend/services/search.py` exists. The copy in `search_service/services/search.py` would conflict. Delete it:
```bash
rm backend/search_service/services/search.py
```

**Step 7: Verify search_service imports**

```bash
cd backend/search_service && python -c "
import sys
sys.path.insert(0, '../')
from main import app
from routers.chat import router as chat_router
from routers.admin import router as admin_router
print('search_service OK')
"
```

Expected: "search_service OK"

- [ ] **Step 8: 提交**

```bash
git add backend/crawler_service/ backend/search_service/
git commit -m "refactor: create search_service skeleton, fix shared imports via sys.path"
```

---

## Task 5: crawler_service 补充完整 router

**Files:**
- Modify: `backend/crawler_service/main.py` — 添加缺失的 router
- Create: `backend/crawler_service/routers/crawl_admin.py`（已完成于 Task 2）

- [ ] **Step 1: 检查 crawler_service 是否缺 API**

In `crawler_service/main.py`, we only have `crawl_admin_router`. But crawler_service may need additional routers like `ai.py` (if it exposes AI config) or other admin endpoints.

Check `backend/api/admin.py` for any other endpoints needed by crawler_service:
- User management → NOT needed (belongs to search_service)
- Crawl config CRUD → YES (crawl_admin_router)
- Docs management → NOT needed (search only)
- AI config → maybe needed if crawler uses AI to categorize

For Phase 1, keep it minimal: only crawl_admin_router.

- [ ] **Step 2: 验证 crawler_service 独立启动**

```bash
cd backend/crawler_service && python -c "
import sys
sys.path.insert(0, '../')
from main import app
from routers.crawl_admin import router
print('crawler_service OK')
"
```

Expected: "crawler_service OK"

- [ ] **Step 3: 提交**

```bash
git add backend/crawler_service/main.py
git commit -m "refactor: add crawl_admin router to crawler_service"
```

---

## Task 6: 前端适配

**Files:**
- Modify: `frontend/src/api/index.js`
- Modify: `frontend/src/components/admin/CrawlerTab.vue`

- [ ] **Step 1: 添加 CRAWLER_API 配置**

In `frontend/src/api/index.js`, add:
```javascript
const CRAWLER_API = 'http://localhost:8001'
```

Update CrawlerTab.vue to use CRAWLER_API for SSE and fetch calls.

找到 `EventSource('/api/admin/crawl/progress')` 改为 `EventSource(`${CRAWLER_API}/admin/crawl/progress`)`
找到 `fetch('/api/admin/...` 改为 `fetch(`${CRAWLER_API}/...`) for crawl-related endpoints.

Note: The search-related admin endpoints (users, docs) should still use the default API_BASE (which is /api).

- [ ] **Step 2: 重新构建前端**

```bash
cd frontend && npm run build
```

- [ ] **Step 3: 复制到 search_service**

```bash
cp -r frontend/dist/. backend/search_service/assets/frontend/
```

- [ ] **Step 4: 提交**

```bash
git add backend/search_service/assets/
git commit -m "feat: copy frontend build to search_service assets"
```

---

## Task 7: 端到端验证

- [ ] **Step 1: 启动 crawler_service（后台）**

```bash
cd backend/crawler_service && python -m uvicorn main:app --host 0.0.0.0 --port 8001 &
```

- [ ] **Step 2: 启动 search_service（后台）**

```bash
cd backend/search_service && python -m uvicorn main:app --host 0.0.0.0 --port 8000 &
```

- [ ] **Step 3: 验证 health 端点**

```bash
curl http://localhost:8001/health
curl http://localhost:8000/api/health
```

Expected: `{"status":"ok","service":"crawler"}` and `{"status":"ok","service":"search"}`

- [ ] **Step 4: 验证 chat 页面可访问**

```bash
curl http://localhost:8000/
```
Expected: HTML page (SPA)

- [ ] **Step 5: 提交**

```bash
git commit -m "test: verify both services start and serve correctly"
```

---

## 依赖关系

Task 1 → Task 2 → Task 3 → Task 4 → Task 5 → Task 6 → Task 7

---

## 自检清单

- [ ] crawler_service 在 8001 端口独立启动
- [ ] search_service 在 8000 端口独立启动
- [ ] 两个服务共享 database.py 和 models/（通过 sys.path）
- [ ] crawler_service 不访问 app.db
- [ ] 前端构建后放入 search_service/assets/frontend/
- [ ] CrawlerTab.vue 中的爬取 API 调用 8001
- [ ] chat/search API 走 8000
- [ ] 两个服务 health check 都返回 200
