# BIPTHelper - 学校信息智能检索系统

基于 FastAPI + Vue 3 + Meilisearch + Qdrant 的智能问答检索平台。支持网页爬取、向量化检索、AI 对话问答和积分管理。

## 技术栈

- **后端**: FastAPI + SQLModel + Uvicorn
- **前端**: Vue 3 + Vite + Pinia
- **搜索引擎**: Meilisearch（全文检索）+ Qdrant（向量检索）
- **数据库**: SQLite
- **AI**: 支持 OpenAI 兼容 API，BGE-M3 向量模型
- **爬虫**: Playwright 无头浏览器

## 快速开始

### Windows 便携版

```bash
# 1. 运行 setup（安装依赖）
setup.bat

# 2. 启动系统
run.bat
```

### 手动安装

**环境要求**: Python 3.11+, Node.js 18+

```bash
# 安装后端依赖
cd backend
pip install -r requirements.txt
playwright install chromium

# 安装前端依赖
cd ../frontend
npm install
```

**启动各服务：**

```bash
# Meilisearch
meilisearch --http-addr 127.0.0.1:7700 --db-path ./data/meilisearch

# 后端（端口 8000）
cd backend
uvicorn main:app --reload --port 8000

# 前端开发服务器（端口 3000）
cd frontend
npm run dev
```

**初始账号**: `admin` / `admin123`

## 批处理脚本

| 脚本 | 用途 |
|------|------|
| `setup.bat` | 安装 Python 依赖 + 前端依赖 |
| `run.bat` | 启动 Meilisearch + 后端 + 前端 |
| `dev.bat` | 开发模式（热重载） |
| `build.bat` | 构建前端生产版本到 `backend/assets/frontend/` |

## 功能模块

| 模块 | 说明 |
|------|------|
| 用户认证 | 注册、登录、JWT Token |
| AI 对话 | 基于检索增强生成的智能问答 |
| 全文搜索 | Meilisearch 文档检索 |
| 向量检索 | Qdrant + BGE-M3 语义搜索 |
| 爬虫管理 | Playwright 网页爬取、定时任务 |
| 积分系统 | 用户积分管理 |
| 管理后台 | 用户管理、审计日志、邀请码、爬虫配置 |

## 系统架构

```
浏览器 ──► FastAPI (8000)
              ├── /              前端静态文件
              ├── /api/auth      认证
              ├── /api/search    搜索
              ├── /api/chat      AI 对话
              ├── /api/admin     管理后台
              ├── /api/ai        AI 配置
              ├── /api/points    积分
              └── /api/crawl     爬虫配置
              │
              ├── Meilisearch (7700)  全文索引
              ├── Qdrant (6333)       向量索引
              └── SQLite              用户/元数据
```

## 目录结构

```
bipthelper/
├── backend/
│   ├── main.py              FastAPI 入口
│   ├── config.py            配置（.env）
│   ├── database.py          SQLite 连接
│   ├── models/              数据模型
│   ├── api/                 API 路由
│   ├── services/            业务逻辑
│   │   ├── ai/              AI 客户端 + Embedding
│   │   ├── parsers/         页面解析器
│   │   ├── crawler.py       爬虫
│   │   ├── rag.py           RAG 检索增强
│   │   ├── search.py        搜索服务
│   │   └── qdrant.py        向量数据库
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── views/           页面组件
│   │   ├── components/      通用组件
│   │   ├── stores/          Pinia 状态
│   │   └── api/             API 调用
│   ├── index.html
│   └── package.json
├── config/                  Meilisearch/Qdrant 配置
├── data/                    运行时数据（gitignore）
└── vendor/                  便携版二进制（gitignore）
```

## 环境变量

在 `backend/.env` 中配置：

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `SECRET_KEY` | JWT 签名密钥 | 自动生成 |
| `MEILISEARCH_URL` | Meilisearch 地址 | `http://localhost:7700` |
| `QDRANT_URL` | Qdrant 地址 | `http://localhost:6333` |
