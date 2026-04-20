# 信息组织器与检索系统完全解耦

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:writing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将现有单仓库双服务拆分为两个完全独立的 Git 仓库，通过 REST API 解耦。

**Architecture:**

- `bipthelper` (已有仓库) — 负责搜索、AI、文档存储、用户管理、积分、激活码。存储权威数据（Document、User、积分等）。
- `bipt_info_organizer` (新建仓库) — 负责信息采集（爬虫/导入）、文档分类、AI 辅助标注、本地配置和审计日志。数据通过 HTTP API 推送给 bipthelper。

两者通过 bipthelper 的 `/api/documents` 系列接口通信，organizer 不直接访问数据库。

---

## 一、数据归属

| 数据 | 存储位置 | 拥有方 |
|------|---------|--------|
| Document（文档内容/分类/元数据） | bipthelper SQLite + Meilisearch | helper |
| CrawlConfig（爬虫配置） | organizer 本地 SQLite | organizer |
| AuditLog（操作日志） | organizer 本地 SQLite | organizer |
| User / 积分 / 激活码 | bipthelper SQLite | helper |

---

## 二、bipthelper 暴露的 API（organizer 调用）

| 方法 | 路径 | 用途 |
|------|------|------|
| POST | `/api/documents` | 推送新文档（来自爬取/导入） |
| PUT | `/api/documents/{id}` | 更新分类/元数据 |
| GET | `/api/documents` | 查询文档列表（分页/过滤） |
| DELETE | `/api/documents/{id}` | 删除文档 |
| GET | `/api/documents/categories` | 获取分类筛选数据 |
| POST | `/api/documents/{id}/approve` | 采纳 AI 分类建议 |

这些接口在 bipthelper 的 `search_service/routers/admin.py` 中已存在，organizer 通过 HTTP 调用。

---

## 三、bipthelper 改动

### 3.1 移除 crawler_service

删除整个 `backend/crawler_service/` 目录及其前端资产。

### 3.2 暴露 organizer API

将 admin.py 中的文档管理接口（见上表）提取为独立 router `organizer_docs.py`，为每个接口增加 `X-Organizer-Key` 头验证（防止滥用）。

接口格式：

```python
@router.post("/documents")
def ingest_document(
    doc: DocumentIngest,
    organizer_key: str = Header(None),  # 验证来自 orgnizer 的请求
    session: Session = Depends(get_session),
):
    """接收来自 bipt_info_organizer 的文档推送"""
    if organizer_key != settings.ORGANIZER_API_KEY:
        raise HTTPException(status_code=403, detail="Invalid organizer key")
    ...
```

### 3.3 新增 /api/documents/export

organizer 需要导出 CSV，通过此接口获取全部文档列表（分页）。

---

## 四、bipt_info_organizer 结构

### 4.1 目录结构

```
bipt_info_organizer/
├── backend/
│   ├── main.py               # FastAPI 入口，端口 8001
│   ├── config.py              # 配置（BIPTHELPER_URL 等）
│   ├── database.py            # 本地 SQLite（配置、日志）
│   ├── models/
│   │   ├── crawl_config.py   # 爬虫配置模型
│   │   └── audit_log.py      # 本地审计日志
│   ├── routers/
│   │   ├── crawl_admin.py    # 爬虫状态/SSE（保持现有）
│   │   ├── organizer_docs.py # 调用 bipthelper API 操作文档
│   │   ├── auth.py           # 登录登出
│   │   └── audit.py          # 本地审计日志（自己记录）
│   ├── services/
│   │   ├── crawler.py        # Playwright 爬虫（保持现有）
│   │   └── helper_client.py  # 调用 bipthelper API 的客户端
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── views/
│   │   │   ├── Login.vue
│   │   │   ├── Register.vue
│   │   │   └── Admin.vue      # 爬虫配置 / 文档管理 / 审计日志
│   │   ├── components/admin/
│   │   ├── router.js
│   │   └── api.js             # 调用本地 backend
│   ├── index.html
│   ├── crawler-admin.html
│   └── vite.config.js
├── scripts/
│   └── build.bat
├── README.md
└── .env
```

### 4.2 helper_client.py

封装所有对 bipthelper 的调用：

```python
import httpx
from config import get_settings

class HelperClient:
    def __init__(self):
        settings = get_settings()
        self.base_url = settings.BIPTHELPER_URL
        self.api_key = settings.ORGANIZER_API_KEY

    def ingest_document(self, doc_data):
        return httpx.post(f"{self.base_url}/api/documents",
                          json=doc_data,
                          headers={"X-Organizer-Key": self.api_key})

    def update_document(self, doc_id, data):
        return httpx.put(f"{self.base_url}/api/documents/{doc_id}",
                         json=data,
                         headers={"X-Organizer-Key": self.api_key})

    def delete_document(self, doc_id):
        return httpx.delete(f"{self.base_url}/api/documents/{doc_id}",
                           headers={"X-Organizer-Key": self.api_key})

    def get_documents(self, params):
        return httpx.get(f"{self.base_url}/api/documents",
                         params=params,
                         headers={"X-Organizer-Key": self.api_key})
```

### 4.3 organizer_docs.py

将现有 crawler_documents.py 改造为调用 helper API 而非直接操作数据库：

```python
@router.get("/documents")
def list_documents(...):
    """从 bipthelper 获取文档列表（透传）"""
    client = get_helper_client()
    resp = client.get_documents({...})
    return resp.json()
```

### 4.4 前端

Admin.vue 三个 tab：
- 爬虫配置 — 爬虫管理
- 文档管理 — 查看/操作从 bipthelper 同步来的文档
- 审计日志 — 本地记录

前端通过 `/api/admin/*` 调用本地 backend，再由 backend 调 bipthelper。

---

## 五、关键配置

### bipthelper .env
```
ORGANIZER_API_KEY=xxx  # 预共享密钥
```

### bipt_info_organizer .env
```
BIPTHELPER_URL=http://localhost:8000
ORGANIZER_API_KEY=xxx  # 与 bipthelper 一致
```

---

## 六、实施顺序

1. **改造 bipthelper**：新增 `/api/documents` 推送接口、`X-Organizer-Key` 验证、移除 crawler_service
2. **创建 bipt_info_organizer 仓库**：复制 crawler_service，重构 `organizer_docs.py` 和 `helper_client.py` 调用 bipthelper API
3. **前端**：从 bipthelper 的 frontend/dist 复制 crawler SPA 到 organizer；更新 build.bat
4. **数据迁移**：将现有 Document 从 bipthelper 导出/导入测试
5. **回归测试**：两个系统分别运行，验证文档推送流程