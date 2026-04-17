# 自然语言问答系统设计文档

> 生成时间: 2026-04-08
> 状态: 已批准，待实现

---

## 一、目标

在现有文档检索基础上，增加自然语言问答能力。用户可以用自然语言提问，系统不仅返回相关文档列表，还直接返回一个基于文档内容的答案，并标注来源。

**核心价值：** 用户不再需要自己从搜索结果中找答案，系统直接给出答案并注明出处。

---

## 二、技术方案

### 2.1 整体架构

```
用户提问
  ↓
向量检索（Qdrant）→ 取 top-K 相关文档块
  ↓
构建 RAG Prompt → 文档块内容 + 问题 + 系统指令
  ↓
调用 LLM（复用现有 AIProvider）→ 生成答案
  ↓
返回：答案文字 + 来源文档列表（含标题、URL、摘要片段）
```

### 2.2 向量数据库选型

**Qdrant**（自托管，Docker 部署）

- 轻量，Rust 实现，性能好
- 支持 metadata payload 过滤（category/department）
- 已有 Meilisearch 自托管经验，运维负担可控

Docker compose 配置：
```yaml
qdrant:
  image: qdrant/qdrant:v1.7.0
  ports:
    - "6333:6333"
    - "6334:6334"
  volumes:
    - ./data/qdrant:/qdrant/storage
```

Collection 配置：
- `vector_size`: 1536（text-embedding-3-small）
- `on_disk_payload`: true
- `text_index` on `chunk_text` field

---

## 三、数据模型

### 3.1 数据库表

**`ChatSession`** — 会话
| 字段 | 类型 | 说明 |
|------|------|------|
| id | str (uuid) | 主键 |
| user_id | str | 所属用户 |
| title | str | 会话标题（取首条问题的前30字） |
| created_at | str | ISO8601 |
| updated_at | str | ISO8601 |

**`ChatMessage`** — 消息
| 字段 | 类型 | 说明 |
|------|------|------|
| id | str (uuid) | 主键 |
| session_id | str | 所属会话 |
| role | str | "user" 或 "assistant" |
| content | str | 消息内容（LLM 回复或用户问题） |
| sources | str | JSON 数组，来源文档列表 |
| created_at | str | ISO8601 |

`sources` JSON 格式：
```json
[
  {
    "doc_id": "doc-uuid",
    "title": "关于2024年暑期安排的通知",
    "url": "https://...",
    "snippet": "暑假从7月15日开始，至8月31日结束。",
    "score": 0.87
  }
]
```

### 3.2 Qdrant Point

每篇文档入库时，按 512 字符切块（overlap 50 字符），每块生成一条 Point：

```
Point {
  id: str           # "{doc_id}_{chunk_index}"
  vector: float[1536]  # embedding
  payload: {
    "doc_id": str,
    "title": str,
    "chunk_text": str,
    "url": str,
    "category": str,
    "department": str
  }
}
```

---

## 四、文档入库流程（改动）

现有爬虫 `crawl_article` 入库流程保持不变，新增以下步骤：

```
保存 Document 到 SQLite（已有）
    ↓
索引到 Meilisearch（已有）
    ↓
[新增] 文档分块 → 调用 embedding API → 存入 Qdrant
```

**分块策略：**
- 块大小：512 字符
- overlap：50 字符（保证块之间语义连贯）
- 丢弃不足 50 字符的尾部碎片块

**Embedding 模型：**
- 使用现有 `AIProvider` 体系，选择配置了 embedding 能力的 Provider
- 优先使用 OpenAI `text-embedding-3-small`（1536 维，性价比最高）
- API Key 配置在现有的 AI Provider 管理界面（复用 AISettings）

**新增配置项（config.py）：**
```python
EMBEDDING_PROVIDER_ID: str = "openai"  # 用于生成 embedding 的 provider
EMBEDDING_MODEL: str = "text-embedding-3-small"
EMBEDDING_CHUNK_SIZE: int = 512
EMBEDDING_CHUNK_OVERLAP: int = 50
QDRANT_URL: str = "http://localhost:6333"
QDRANT_COLLECTION: str = "document_chunks"
```

---

## 五、API 设计

### 5.1 会话管理

**`GET /api/chat/sessions`**
- 返回当前用户所有会话列表，按 `updated_at` 倒序

**`POST /api/chat/sessions`**
- 创建新会话，返回 `{id, title, created_at}`

**`DELETE /api/chat/sessions/{session_id}`**
- 删除会话及其所有消息

**`GET /api/chat/sessions/{session_id}/messages`**
- 返回该会话所有消息，按 `created_at` 升序

### 5.2 问答

**`POST /api/chat/sessions/{session_id}/messages`**

Request:
```json
{
  "content": "今年暑假什么时候开始？"
}
```

Response:
```json
{
  "id": "msg-uuid",
  "role": "assistant",
  "content": "根据《2024年暑期工作安排的通知》，暑假从7月15日（星期一）开始，至8月31日结束。全体教职工请于9月1日返校报到。",
  "sources": [
    {
      "doc_id": "doc-uuid-1",
      "title": "2024年暑期工作安排的通知",
      "url": "https://...",
      "snippet": "暑假从7月15日开始，至8月31日结束。",
      "score": 0.91
    }
  ],
  "created_at": "2026-04-08T10:30:00Z"
}
```

**认证：** 所有接口均需登录，使用 `get_current_user_from_cookie`（复用现有认证体系）。

### 5.3 错误处理

| 情况 | 处理 |
|------|------|
| Qdrant 不可用 | 返回 503，前端提示"检索服务暂时不可用" |
| LLM API Key 未配置 | 返回 400，前端提示"请先配置 AI Provider" |
| 没有可用的向量数据 | LLM 回复"知识库中暂无相关内容" |
| LLM 调用超时（>30s） | 返回 504，前端提示"回答生成超时" |

---

## 六、RAG Prompt 设计

### 系统指令（system prompt）
```
你是一个学校信息助手，基于给定的文档内容回答用户问题。

规则：
1. 只根据提供的文档内容回答，不要编造
2. 如果文档中没有相关信息，回复"抱歉，知识库中没有找到相关内容"
3. 回答要简洁，直接给出答案
4. 在答案末尾注明参考来源的文档标题
5. 不要在答案中重复问题
```

### 用户消息构建
```
参考文档：
---
文档1：《{title1}》
{chunk_text1}
---
文档2：《{title2}》
{chunk_text2}
---
文档3：《{title3}》
{chunk_text3}
---

问题：{question}
```

### 向量检索参数
- `top_k`: 3（取前 3 个最相关块）
- `score_threshold`: 0.5（低于此分数的块不参与回答）

---

## 七、前端设计

### 7.1 路由

- `/chat` — 聊天页面（使用 Home layout，包含 header + 侧边栏）

### 7.2 布局

```
┌──────────────────────────────────────────────────────┐
│ 石化助手            [用户]  [主题切换]  [管理]  [登出] │  ← header
├────────────┬─────────────────────────────────────────┤
│            │                                         │
│ 会话列表   │  消息区域                                 │
│            │                                         │
│ [+ 新建]   │  [用户消息]                              │
│            │                                         │
│ 会话1      │  [助手消息]                              │
│   - 暑假?  │    答案文字...                           │
│   - 中秋?  │    来源：                                │
│ 会话2      │    · 2024年暑期安排的通知 →              │
│   ...      │    · 关于暑假安排的规定 →                │
│            │                                         │
│            │  [输入框: 输入问题...] [发送]            │
└────────────┴─────────────────────────────────────────┘
```

### 7.3 消息气泡

**用户消息**：右对齐，蓝色/主题色背景
**助手消息**：左对齐，浅灰背景，底部附来源列表

来源列表样式：
```
来源：
· 2024年暑期工作安排的通知 (相似度 91%) → [跳转链接]
```

点击"跳转链接" → 在新标签页打开原文 URL。

### 7.4 状态处理

- **加载中**：助手消息显示骨架屏（3行灰色占位）
- **空会话**：显示引导文案"你好！可以问我关于学校通知、制度等任何问题"
- **错误**：Toast 提示，不打断输入框内容

---

## 八、文件变更清单

### 新建

| 文件 | 说明 |
|------|------|
| `backend/models/chat.py` | ChatSession, ChatMessage 模型 |
| `backend/api/chat.py` | 会话和问答 API 路由 |
| `backend/services/embedding.py` | embedding 生成服务（调用 LLM） |
| `backend/services/rag.py` | RAG 核心逻辑：检索 → 构建 Prompt → 调用 LLM |
| `backend/services/qdrant.py` | Qdrant 客户端封装 |
| `frontend/src/views/Chat.vue` | 聊天主页面 |
| `frontend/src/components/chat/SessionList.vue` | 左侧会话列表组件 |
| `frontend/src/components/chat/MessageList.vue` | 消息列表组件 |
| `frontend/src/components/chat/SourceList.vue` | 来源列表组件 |

### 修改

| 文件 | 说明 |
|------|------|
| `backend/services/crawler.py` | 入库流程新增：分块 → embedding → 存入 Qdrant |
| `backend/models/document.py` | 可选：新增 `embedding_available` 标记（爬虫入库时设为 true） |
| `backend/api/chat.py` | 新增 chat.router（会话管理和问答 API） |
| `backend/main.py` | 注册 chat.router；启动时检查 Qdrant 连通性 |
| `backend/config.py` | 新增 `EMBEDDING_*`, `QDRANT_*` 配置项 |
| `frontend/src/router/index.js` | 添加 `/chat` 路由 |

---

## 九、非功能性考虑

### 性能
- Embedding 生成在爬虫入库时同步进行，不影响用户查询延迟
- LLM 调用设置 30s 超时，避免阻塞
- 向量检索 <100ms，Qdrant 本地部署延迟可控

### 成本
- 文档入库：每块 512 字符约 170 tokens，按 `text-embedding-3-small` 计费
- 问答：每次问答约 1500-3000 tokens 输入（3个文档块 + 对话历史） + ~500 tokens 输出
- 按内部用户规模（估算百人级），月费用可控

### 数据安全
- 会话数据与用户绑定，只能查看自己的会话
- 来源文档 URL 均为内部系统 URL，无外泄风险

### 依赖项
- Qdrant 自托管（Docker）
- 向量生成依赖现有 AIProvider（需配置 OpenAI 或兼容 API）
- 不引入新的外部服务

---

## 十、验证计划

1. 启动 Qdrant，手动入库一篇测试文档，验证向量检索能返回相关内容
2. 调用 `POST /chat/sessions/{id}/messages`，验证能返回答案和来源
3. 在前端聊天界面测试：正常问答、多轮追问、新建会话、删除会话
4. 爬虫入库流程验证：文档入库后自动生成向量并可检索
5. 错误场景验证：Qdrant 不可用、LLM 未配置、无相关文档时的表现
