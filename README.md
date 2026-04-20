# BIPTHelper - 学校信息智能检索系统

基于 FastAPI + Vue 3 + Meilisearch + Qdrant 的智能问答检索平台。支持网页爬取、向量化检索、AI 对话问答和积分管理。

## 技术栈

- **后端**: FastAPI + SQLModel + Uvicorn
- **前端**: Vue 3 + Vite + Pinia（双 SPA 架构）
- **搜索引擎**: Meilisearch（全文检索）+ Qdrant（向量检索）
- **数据库**: SQLite
- **AI**: 支持 OpenAI 兼容 API，BGE-M3 向量模型
- **爬虫**: Playwright 无头浏览器

## 系统架构（双服务分离）

```
search_service (8000)          crawler_service (8001)
┌──────────────────────┐        ┌──────────────────────┐
│  搜索前台 SPA         │        │  爬虫管理 SPA         │
│  · 首页搜索           │        │  · 爬虫配置           │
│  · AI 对话            │        │  · 文档管理           │
│  · 用户管理           │        │  · 审计日志           │
│  · 激活码             │        │                      │
│  · AI 配置            │        │                      │
│  · 审计日志           │        │                      │
└──────────────────────┘        └──────────────────────┘
         │                               │
         └───────── 共享数据库 ──────────┘
```

## 快速开始

### Windows 便携版

```bash
# 1. 安装依赖
setup.bat

# 2. 启动系统（search 8000 + crawler 8001）
run.bat
```

### 手动启动

**环境要求**: Python 3.11+, Node.js 18+

```bash
# 1. 安装依赖
setup.bat

# 2. 启动 Meilisearch
vendor\meilisearch.exe --http-addr 127.0.0.1:7700 --db-path ./data/meilisearch

# 3. 启动 search_service (8000)
cd backend
python -m uvicorn search_service.main:app --host 127.0.0.1 --port 8000

# 4. 启动 crawler_service (8001)
python -m uvicorn crawler_service.main:app --host 127.0.0.1 --port 8001

# 5. 访问
#   搜索前台: http://localhost:8000
#   爬虫后台: http://localhost:8001
```

**初始账号**: `admin` / `admin123`

## 批处理脚本

| 脚本 | 用途 |
|------|------|
| `setup.bat` | 安装 Python 依赖 + 前端依赖 |
| `run.bat` | 启动 Meilisearch + 两个后端服务 |
| `build.bat` | 构建双 SPA 到各服务 assets 目录 |

## 功能模块

| 模块 | 服务 | 说明 |
|------|------|------|
| 全文搜索 | search_service | Meilisearch 文档检索 |
| AI 对话 | search_service | RAG 检索增强生成 |
| 用户管理 | search_service | 用户认证、积分 |
| 管理后台 | search_service | 激活码、AI 配置、审计日志 |
| 爬虫配置 | crawler_service | 定时爬取任务管理 |
| 文档管理 | crawler_service | 文档分类、AI 辅助标注 |
| 操作审计 | crawler_service | 爬虫操作记录 |

## 目录结构

```
bipthelper/
├── backend/
│   ├── search_service/           # 搜索服务 (8000)
│   │   ├── main.py               # FastAPI 入口
│   │   ├── routers/              # API 路由
│   │   │   ├── auth.py           # 登录/注册
│   │   │   ├── search.py         # 搜索 API
│   │   │   ├── chat.py           # AI 对话
│   │   │   └── admin.py          # 管理后台
│   │   └── assets/frontend/      # 搜索 SPA 静态文件
│   ├── crawler_service/          # 爬虫服务 (8001)
│   │   ├── main.py               # FastAPI 入口
│   │   ├── routers/              # API 路由
│   │   │   ├── crawl_admin.py    # 爬虫状态/SSE
│   │   │   ├── crawler_auth.py   # 爬虫登录
│   │   │   ├── crawler_admin.py  # 用户列表
│   │   │   └── crawler_documents.py  # 文档管理
│   │   └── assets/frontend/      # 爬虫 SPA 静态文件
│   ├── services/                 # 共享业务逻辑
│   │   ├── auth.py               # JWT / Cookie 认证
│   │   ├── crawler.py            # 爬虫核心
│   │   ├── search.py             # Meilisearch
│   │   └── audit.py              # 审计日志
│   ├── models/                   # 数据模型
│   └── database.py               # SQLite 连接
├── frontend/
│   ├── src/
│   │   ├── views/                # 页面 (Admin.vue, AdminCrawler.vue, Home.vue, Chat.vue...)
│   │   ├── components/           # 组件 (admin/, chat/, search/)
│   │   ├── stores/               # Pinia 状态
│   │   ├── api/                  # API 调用
│   │   ├── router.js             # 搜索服务路由
│   │   └── routerCrawler.js     # 爬虫服务路由
│   ├── index.html                # 搜索 SPA 入口
│   ├── crawler-admin.html        # 爬虫 SPA 入口
│   ├── vite.config.js            # Vite 配置（多入口）
│   └── vite.crawler.config.js   # 爬虫 SPA 独立配置
├── config/                       # Meilisearch/Qdrant 配置
├── data/                         # 运行时数据
└── vendor/                       # 便携版二进制（gitignore）
```

## 环境变量

在 `backend/.env` 中配置：

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `SECRET_KEY` | JWT 签名密钥 | 自动生成 |
| `MEILISEARCH_URL` | Meilisearch 地址 | `http://localhost:7700` |
| `QDRANT_URL` | Qdrant 地址 | `http://localhost:6333` |