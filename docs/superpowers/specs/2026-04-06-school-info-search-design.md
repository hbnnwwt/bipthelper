# 学校信息智能检索系统设计

## 1. 项目概述

**项目名称：** SchoolInfoSearch
**项目类型：** 内网信息检索系统
**核心功能：** 爬取学校公开通知、规章制度等文档，提供全文检索 + 分类筛选 + 语义搜索
**用户规模：** 几千人内网用户
**部署环境：** 内网服务器，无需公网访问

## 2. 技术架构

```
┌─────────────────────────────────────────────────────┐
│                    Vue 3 前端                       │
│              (Vite + Vue Router + Pinia)            │
└─────────────────────┬───────────────────────────────┘
                      │ HTTP + JWT
┌─────────────────────▼───────────────────────────────┐
│                   FastAPI 服务                       │
│  ┌──────────┐  ┌──────────┐  ┌──────────────────┐  │
│  │ 用户模块  │  │ 搜索模块  │  │     爬虫模块      │  │
│  │ /auth/*  │  │ /search  │  │  APScheduler定时  │  │
│  └──────────┘  └──────────┘  └──────────────────┘  │
│                      │                               │
│         ┌────────────┼────────────┐                  │
│         ▼            ▼            ▼                  │
│    ┌─────────┐  ┌─────────┐  ┌─────────┐           │
│    │ Meilisearch│ │  SQLite  │  │ 文件存储 │           │
│    │ (全文索引) │  │ (用户/元数据)│  │ (原始HTML)│           │
│    └─────────┘  └─────────┘  └─────────┘           │
└─────────────────────────────────────────────────────┘
```

## 3. 模块设计

### 3.1 爬虫服务

**职责：** 增量抓取学校网站页面，解析内容，存储原始数据，更新搜索索引

**技术选型：**
- 基础爬取：Python + BeautifulSoup + requests
- JS 渲染支持：Playwright（可选，用于处理动态加载页面）
- 定时任务：APScheduler
- 增量检测：对比页面 hash 或最后修改时间

**输入：** 用户提供的网页列表（URL + 提取规则）
**输出：** 解析后的文档存入 SQLite，原始 HTML 存入文件存储

**数据模型：**
```python
Document:
  id: str (UUID)
  url: str
  title: str
  content: str (提取的正文)
  category: str (分类：通知/制度/其他)
  department: str (发布部门)
  publish_date: datetime
  created_at: datetime
  updated_at: datetime
  content_hash: str (用于增量检测)
```

### 3.2 搜索服务

**职责：** 提供全文检索、分类筛选、语义搜索接口

**技术选型：**
- 全文索引：Meilisearch（开源、易部署、支持 Docker）
- 筛选字段：category, department, publish_date
- 排序：按相关度 / 按发布时间

**Phase 1 实现：**
- 纯全文检索 + 分类/部门/时间筛选
- Meilisearch Filter 表达式支持多条件组合

**Phase 2 实现（预留）：**
- 本地 Embeddings：Sentence-Transformers
- 向量索引：FAISS
- 混合检索：关键词 + 语义相关性

### 3.3 用户认证

**职责：** 账号管理、登录认证、权限控制

**技术选型：**
- 数据库：SQLite
- 密码存储：bcrypt 哈希
- Token：JWT（JSON Web Token）

**账号策略：**
- 初期：邀请制（后台手动开通）
- 后期：开放注册网关（可配置开关）

**数据模型：**
```python
User:
  id: str (UUID)
  username: str (唯一)
  password_hash: str
  role: str (admin/user)
  invite_code: str (创建时关联邀请码)
  created_at: datetime
  is_active: bool
```

**接口：**
- `POST /auth/register` - 注册（邀请码模式）
- `POST /auth/login` - 登录，返回 JWT
- `POST /auth/logout` - 登出
- `GET /auth/me` - 获取当前用户信息

### 3.4 前端

**技术选型：**
- 框架：Vue 3 + Composition API + `<script setup>`
- 构建：Vite
- 路由：Vue Router
- 状态：Pinia
- HTTP：Axios
- UI 组件：自建或轻量组件库

**页面结构：**
- `/login` - 登录页
- `/register` - 注册页（邀请码）
- `/` - 首页（搜索框 + 结果列表）
- `/document/:id` - 文档详情页
- `/admin` - 管理后台（用户管理、爬虫状态、网页配置）

## 4. 数据流

### 4.1 爬取流程

```
1. 定时任务触发
2. 读取配置的 URL 列表
3. 对每个 URL：
   a. 获取页面内容
   b. 计算 content_hash
   c. 与上次抓取的 hash 对比
   d. 有变化 → 解析正文 → 更新数据库 → 更新 Meilisearch 索引
   e. 无变化 → 跳过
4. 记录抓取日志
```

### 4.2 搜索流程

```
1. 用户输入搜索词
2. JWT 验证
3. 查询 Meilisearch（filter + sort）
4. 返回分页结果
5. 前端渲染列表
```

## 5. 数据库设计

### SQLite 表

**documents**
| 字段 | 类型 | 说明 |
|------|------|------|
| id | TEXT PK | UUID |
| url | TEXT UNIQUE | 原始链接 |
| title | TEXT | 标题 |
| content | TEXT | 正文 |
| category | TEXT | 分类 |
| department | TEXT | 发布部门 |
| publish_date | TEXT | 发布日期 |
| created_at | TEXT | 创建时间 |
| updated_at | TEXT | 更新时间 |
| content_hash | TEXT | 内容哈希 |

**users**
| 字段 | 类型 | 说明 |
|------|------|------|
| id | TEXT PK | UUID |
| username | TEXT UNIQUE | 用户名 |
| password_hash | TEXT | 密码哈希 |
| role | TEXT | admin/user |
| invite_code | TEXT | 邀请码 |
| created_at | TEXT | 创建时间 |
| is_active | INTEGER | 是否激活 |

**crawl_configs**
| 字段 | 类型 | 说明 |
|------|------|------|
| id | TEXT PK | UUID |
| name | TEXT | 配置名称 |
| url | TEXT | 目标URL |
| selector | TEXT | CSS选择器/提取规则 |
| category | TEXT | 默认分类 |
| enabled | INTEGER | 是否启用 |
| last_hash | TEXT | 上次抓取hash |
| last_crawl | TEXT | 上次抓取时间 |

## 6. API 设计

### 认证接口

```
POST /api/auth/register
  Body: { username, password, invite_code }
  Response: { user, token }

POST /api/auth/login
  Body: { username, password }
  Response: { user, token }

GET /api/auth/me
  Headers: Authorization: Bearer <token>
  Response: { user }
```

### 搜索接口

```
GET /api/search
  Query: { q, category, department, start_date, end_date, page, page_size }
  Headers: Authorization: Bearer <token>
  Response: {
    total: int,
    page: int,
    page_size: int,
    results: [{ id, title, content_preview, category, department, publish_date, url }]
  }
```

### 管理接口

```
GET /api/admin/configs
  Response: { configs: [...] }

POST /api/admin/configs
  Body: { name, url, selector, category }

PUT /api/admin/configs/:id
  Body: { ... }

DELETE /api/admin/configs/:id

GET /api/admin/users
  Response: { users: [...] }

POST /api/admin/users/invite
  Body: { username }
  Response: { invite_code }
```

## 7. 部署架构

**内网部署：**
- 单台服务器运行所有服务
- Docker Compose 编排：FastAPI + Meilisearch + Vue 前端
- 前端静态文件由 Nginx 托管或 FastAPI 代理

**数据持久化：**
- SQLite 文件映射到宿主机 volume
- Meilisearch 数据映射到宿主机 volume
- 原始 HTML 文件存储映射到宿主机 volume

## 8. 两阶段规划

### Phase 1（现在）
- 爬虫：BeautifulSoup 增量抓取
- 搜索：Meilisearch 全文 + 筛选
- 用户：SQLite + JWT，邀请制
- 前端：Vue 3 基础搜索界面

### Phase 2（后期）
- 语义搜索：Sentence-Transformers Embeddings + FAISS
- 混合检索：关键词 + 语义相关性融合
- 搜索体验优化：自动补全、相关搜索、搜索建议

## 9. 风险与约束

**约束：**
- 无学校 API，数据来源依赖爬虫
- 需要学校网站结构相对稳定
- 内网部署，无公网访问

**风险：**
- 学校网站改版导致爬虫失效 → 预留 selector 配置化
- 增量检测依赖 hash，频繁改版会触发重复抓取 → 可配置抓取间隔
- Meilisearch 单机瓶颈 → Phase 2 可考虑分布式方案
