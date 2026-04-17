# 学校信息智能检索系统

## Windows 便携版（推荐）

参考 Exam_v5.0 的 python_portable 模式，零配置启动：

### 快速开始

```bash
# 1. 复制 python_portable（从 Exam_v5.0）
xcopy /E /I /Y "E:\code\Exam_v5.0\python_portable" "E:\code\bipthelper\python_portable"

# 2. 运行 setup.bat（自动下载 Python 依赖 + Meilisearch）
setup.bat

# 3. 运行系统
run.bat
```

### 批处理脚本说明

| 脚本 | 用途 |
|------|------|
| `setup.bat` | 下载 Python 便携版，安装依赖 |
| `run.bat` | 启动 Meilisearch + 后端 + 前端 |
| `dev.bat` | 开发模式（后端热重载 + 前端热重载）|
| `build.bat` | 构建前端生产版本 |

## 手动安装（Linux/macOS 或有 Python 环境）

### 环境要求

- Python 3.11+
- Node.js 18+
- Meilisearch（下载对应平台的二进制）

### 启动步骤

#### 1. Meilisearch

```bash
# macOS / Linux
curl -L https://install.meilisearch.com | sh
./meilisearch --http-addr 127.0.0.1:7700 --db-path ./data/meilisearch
```

#### 2. Backend

```bash
cd backend
pip install -r requirements.txt
```

**首次运行前**（Windows/Linux 需安装 Playwright 浏览器驱动）：

```bash
playwright install
# 或指定浏览器：playwright install chromium
```

**启动服务：**

```bash
uvicorn main:app --reload --port 8000
```

**初始账号：** `admin` / `admin123`

#### 3. Frontend (开发模式热重载)

```bash
dev.bat
```

访问 http://localhost:3000（前端 vite 开发服务器）

## 生产部署

### 前端构建

```bash
build.bat
```

前端构建产物输出到 `backend/assets/frontend/`，由 FastAPI 直接托管。

### 系统架构

```
浏览器 ──► FastAPI 后端 (8000)
              ├── /            (前端静态文件)
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
│   ├── assets/
│   │   └── frontend/     # 前端构建产物（自动生成）
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
