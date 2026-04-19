# 服务拆分设计：爬虫服务与搜索服务

## 目标

将 `backend/` 拆分为两个独立 FastAPI 服务：
- **crawler-service**（port 8001）— 爬虫管理 + 执行 + 向量化索引
- **search-service**（port 8000）— 聊天 / 搜索 / 前端静态文件

## 架构概览

```
┌──────────────────────┐       ┌──────────────────────┐
│   crawler-service    │       │   search-service     │
│   (port 8001)        │       │   (port 8000)        │
│                      │       │                      │
│  - 爬虫 CRUD API     │       │  - Chat API          │
│  - 爬取执行逻辑       │       │  - 搜索 API           │
│  - 向量化索引         │       │  - 管理 API (读)      │
│  - 爬取状态 SSE       │       │  - 前端静态文件       │
└──────────┬───────────┘       └──────────┬───────────┘
           │                               │
           ▼                               ▼
    ┌─────────────────────────────── shared ───────────────────────────────┐
    │           crawl.db          MeiliSearch        Qdrant       key.db   │
    └──────────────────────────────────────────────────────────────────────┘
```

**数据流向：**
```
crawler-service → crawl.db → MeiliSearch + Qdrant ← search-service
                                     ↑
                              chat / search 查询
```

**crawl.db 是共享读写**（crawler 写，search 只读配置/状态）
**MeiliSearch + Qdrant 由 crawler-service 写入，search-service 只读**

---

## 目录结构

```
backend/
├── crawler_service/           # 新目录：爬虫服务
│   ├── main.py               # FastAPI app (8001)，爬虫 HTTP 接口
│   ├── crawler.py             # 爬取逻辑（现有）
│   ├── routers/
│   │   └── crawl_admin.py     # 爬虫 CRUD + start/stop/status
│   └── requirements.txt
│
├── search_service/            # 新目录：搜索服务
│   ├── main.py               # FastAPI app (8000)，从现有 main.py 拆分
│   ├── routers/
│   │   ├── chat.py           # 聊天 API
│   │   ├── admin.py           # 管理 API（读写 crawl.db）
│   │   ├── auth.py            # 认证 API
│   │   └── points.py          # 积分 API
│   ├── services/
│   │   ├── rag.py
│   │   ├── search.py
│   │   └── ai/
│   │       ├── embedding.py
│   │       └── client.py
│   └── requirements.txt
│
├── models/                    # 两服务共享
├── database.py                 # 两服务共享（读写相同 db）
├── config.py
└── utils/
```

---

## API 路由设计

### crawler-service（8001）

| Method | Path | Description |
|--------|------|-------------|
| GET | `/admin/configs` | 获取爬虫配置列表 |
| POST | `/admin/configs` | 新建爬虫配置 |
| PUT | `/admin/configs/{id}` | 更新配置 |
| DELETE | `/admin/configs/{id}` | 删除配置 |
| GET | `/admin/crawl/status` | 全局爬取状态 |
| GET | `/admin/crawl/progress` | 当前进度（SSE） |
| POST | `/crawl/start` | 启动全量爬取 |
| POST | `/crawl/start-configs` | 按配置ID列表爬取 |
| POST | `/crawl/stop` | 停止爬取 |
| GET | `/health` | 健康检查 |

### search-service（8000）

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/auth/login` | 登录 |
| POST | `/api/auth/register` | 注册 |
| GET | `/api/auth/me` | 当前用户信息 |
| GET | `/api/chat/sessions` | 获取会话列表 |
| POST | `/api/chat/sessions` | 新建会话 |
| GET | `/api/chat/sessions/{id}/messages` | 获取消息 |
| POST | `/api/chat/sessions/{id}/messages` | 发送消息（SSE） |
| GET | `/api/search?q=` | 搜索文档 |
| GET | `/api/admin/users` | 用户列表（admin） |
| GET | `/api/admin/docs` | 文档列表 |
| GET | `/api/admin/crawl/status` | 爬取状态（读 crawl.db） |
| GET | `/api/admin/crawl/progress` | 爬取进度（读 crawl.db，SSE 代理到 8001） |
| POST | `/api/admin/configs` | 新建配置（透传到 8001） |
| PUT | `/api/admin/configs/{id}` | 更新配置（透传到 8001） |
| DELETE | `/api/admin/configs/{id}` | 删除配置（透传到 8001） |
| GET | `/health` | 健康检查 |

**说明：** search-service 的 `/api/admin/crawl/*` 是读写 crawl.db 或透传到 crawler-service。管理页面调 search-service（8000），后者透传到 crawler-service（8001）。

---

## 数据层

### 共享数据库

| 数据库 | crawler-service | search-service |
|--------|----------------|---------------|
| `crawl.db` | 读写 | 只读（配置/状态） |
| `key.db` | 只读（EmbeddingConfig） | 读写 |
| `app.db` | 不访问 | 读写 |
| MeiliSearch | 写 | 只读 |
| Qdrant | 写 | 只读 |

### crawler-service 的数据库访问

crawler-service 只读 `key.db` 中的 `EmbeddingConfig`（用于向量化配置），不访问 `app.db`。

### search-service 的数据库访问

search-service 完全不运行爬虫，通过 MeiliSearch / Qdrant 只读文档。不直接读写 `crawl.db`（管理配置透传到 crawler-service）。

---

## 前端集成

### 方案

前端编译后打包到 `search_service/assets/frontend/`。爬虫管理页面调 `http://localhost:8001` API。

**API 配置：**
```javascript
// api/index.js
const API_BASE = ''  // 当前域，同源
const CRAWLER_API = 'http://localhost:8001'  // 爬虫服务专用接口
```

爬虫管理页面（`CrawlerTab.vue`）中需要调爬虫 API 的地方：
```javascript
// 爬取状态/进度 SSE
const progressSource = new EventSource(`${CRAWLER_API}/admin/crawl/progress`)

// 启动爬取
await fetch(`${CRAWLER_API}/crawl/start`, { ... })
```

### 构建流程

```bash
# 构建前端
cd frontend && npm run build

# 复制到 search_service
cp -r dist ../search_service/assets/frontend
```

---

## search-service/main.py 结构

```python
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from pathlib import Path

app = FastAPI()

# 挂载前端静态文件
ASSETS_DIR = Path(__file__).resolve().parent / "assets" / "frontend"
if ASSETS_DIR.exists():
    app.mount("/", StaticFiles(directory=str(ASSETS_DIR), html=True), name="frontend")

# API routers
app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(chat.router, prefix="/api/chat", tags=["chat"])
app.include_router(search.router, prefix="/api/search", tags=["search"])
app.include_router(admin.router, prefix="/api/admin", tags=["admin"])
app.include_router(points.router, prefix="/api/points", tags=["points"])

# 爬虫管理透传
@app.get("/api/admin/crawl/status")
def proxy_crawl_status():
    return requests.get("http://localhost:8001/admin/crawl/status").json()
```

---

## 迁移步骤

### Phase 1：创建 crawler_service 目录结构

```
backend/
  crawler_service/
    main.py              # 爬虫 FastAPI app
    crawler.py           # 从 services/ 移入
    routers/
      __init__.py
      crawl_admin.py    # 爬虫 CRUD + 启动停止
    models/
      __init__.py
    database.py          # 复制，修改 bind（crawl.db 可写）
    requirements.txt
```

### Phase 2：创建 search_service 目录结构

```
backend/
  search_service/
    main.py             # 从 main.py 拆分，只保留 API + 静态文件
    routers/
      __init__.py
      chat.py            # 从 api/chat.py 移入
      auth.py            # 从 api/auth.py 移入
      admin.py           # 保留，管理读写
      points.py          # 从 api/points.py 移入
      search.py          # 新建，搜索接口
    services/
      rag.py             # 从 services/rag.py 移入
      search.py          # 从 services/search.py 移入
      ai/
        embedding.py      # 从 services/ai/embedding.py 移入
        client.py         # 从 services/ai/client.py 移入
    models/              # 共享模型（User, Document 等）
    database.py          # 复制，修改 bind（crawl.db 只读）
    requirements.txt
```

### Phase 3：API 透传

search-service 的 `/api/admin/crawl/*` 透传到 crawler-service：
- 使用 `httpx` 或 `requests` 同步转发
- 或通过 crawl.db 直接读取（状态、进度）

### Phase 4：前端适配

- 构建产物复制到 `search_service/assets/frontend/`
- `CrawlerTab.vue` 中爬取状态/启动调用改为 `http://localhost:8001`
- API base URL 保持同源

---

## 自检

- [ ] crawler-service 和 search-service 独立运行
- [ ] 共享 crawl.db / MeiliSearch / Qdrant / key.db
- [ ] search-service 不直接写 crawl.db（管理操作透传）
- [ ] 前端可访问爬虫管理页面
- [ ] 爬取执行链路完整（crawl → db → MeiliSearch → Qdrant）
- [ ] 不改变用户使用体验（仍是同一 URL 访问）
