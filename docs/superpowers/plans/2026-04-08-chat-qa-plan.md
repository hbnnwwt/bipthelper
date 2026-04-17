# 自然语言问答系统实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现自然语言问答系统（RAG），用户可多会话对话，系统返回答案 + 来源文档

**Architecture:** Qdrant 向量数据库存储文档块（512字符分块），检索 top-3 块构建 RAG Prompt 调用 LLM，回复存 SQLite 多会话

**Tech Stack:** Python (FastAPI, SQLModel), Vue 3 (Composition API), Qdrant (Docker), OpenAI-compatible embedding API

---

## 前置准备

实现前需先安装 qdrant 客户端依赖：

```bash
pip install qdrant-client
```

Docker compose 参考配置（部署时使用）：
```yaml
qdrant:
  image: qdrant/qdrant:v1.7.0
  ports:
    - "6333:6333"
    - "6334:6334"
  volumes:
    - ./data/qdrant:/qdrant/storage
```

---

## Task 1: 配置项 + 数据模型

### 1.1 config.py 新增配置项

**文件:** `backend/config.py`

在 `Settings` 类中添加：
```python
EMBEDDING_MODEL: str = "text-embedding-3-small"
EMBEDDING_CHUNK_SIZE: int = 512
EMBEDDING_CHUNK_OVERLAP: int = 50
QDRANT_URL: str = "http://localhost:6333"
QDRANT_COLLECTION: str = "document_chunks"
```

### 1.2 ChatSession + ChatMessage 模型

**文件:** `backend/models/chat.py`（新建）

```python
from sqlmodel import SQLModel, Field
from typing import Optional
from datetime import datetime, timezone

class ChatSession(SQLModel, table=True):
    __tablename__ = "chat_sessions"
    id: str = Field(primary_key=True)
    user_id: str = Field(index=True)
    title: str = ""
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

class ChatMessage(SQLModel, table=True):
    __tablename__ = "chat_messages"
    id: str = Field(primary_key=True)
    session_id: str = Field(index=True)
    role: str  # "user" 或 "assistant"
    content: str = ""
    sources: str = "[]"  # JSON 字符串
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
```

### 1.3 注册模型到 database

**文件:** `backend/database.py`

找到 `create_db_and_tables()` 函数，在 `SQLModel.metadata.create_all(engine)` 调用之前添加：
```python
from models.chat import ChatSession, ChatMessage
```

---

## Task 2: Qdrant 服务封装

### 2.1 Qdrant 客户端封装

**文件:** `backend/services/qdrant.py`（新建）

```python
import qdrant_client
from qdrant_client.models import Distance, VectorParams, PointStruct, Filter, FieldCondition, MatchText
from typing import Optional
import logging

from config import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)

_client = None

def get_qdrant_client() -> qdrant_client.QdrantClient:
    global _client
    if _client is None:
        _client = qdrant_client.QdrantClient(url=settings.QDRANT_URL)
    return _client

def ensure_collection():
    """确保 collection 存在，不存在则创建"""
    client = get_qdrant_client()
    collections = client.get_collections().collections
    collection_names = [c.name for c in collections]

    if settings.QDRANT_COLLECTION not in collection_names:
        client.create_collection(
            collection_name=settings.QDRANT_COLLECTION,
            vectors_config=VectorParams(
                size=1536,  # text-embedding-3-small
                distance=Distance.COSINE,
            ),
        )
        # 创建 payload 索引支持 text_search
        client.create_payload_index(
            collection_name=settings.QDRANT_COLLECTION,
            field_name="chunk_text",
            field_schema="text",
        )
        logger.info(f"Created Qdrant collection: {settings.QDRANT_COLLECTION}")

def upsert_points(points: list[PointStruct]):
    """批量写入向量点"""
    client = get_qdrant_client()
    client.upsert(
        collection_name=settings.QDRANT_COLLECTION,
        points=points,
    )

def search_points(query_vector: list[float], top_k: int = 3, score_threshold: float = 0.5) -> list[dict]:
    """向量相似度搜索，返回命中的块信息"""
    client = get_qdrant_client()
    results = client.search(
        collection_name=settings.QDRANT_COLLECTION,
        query_vector=query_vector,
        limit=top_k,
        score_threshold=score_threshold,
    )
    return [
        {
            "id": r.id,
            "score": r.score,
            "payload": r.payload,
        }
        for r in results
    ]

def delete_points_by_doc_id(doc_id: str):
    """删除指定文档的所有向量点"""
    client = get_qdrant_client()
    # Qdrant 支持按 payload 字段过滤删除
    from qdrant_client.models import Filter, FieldCondition, Match
    client.delete(
        collection_name=settings.QDRANT_COLLECTION,
        points_selector=Filter(
            must=[
                FieldCondition(key="doc_id", match=Match(value=doc_id))
            ]
        ),
    )
```

---

## Task 3: Embedding 服务（文档分块 + 向量生成）

### 3.1 Embedding 生成 + 文档分块

**文件:** `backend/services/ai/embedding.py`（新建）

```python
import logging
from typing import Optional
from services.ai.client import call_llm

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """你是一个文本嵌入模型。请将输入的文本转换为向量。"""

def chunk_text(text: str, chunk_size: int = 512, overlap: int = 50) -> list[str]:
    """
    按字符数分块，块之间有 overlap。
    丢弃不足 overlap 字符的尾部碎片。
    """
    if not text or len(text) <= chunk_size:
        return [text] if text else []

    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunk = text[start:end]
        chunks.append(chunk)
        start = end - overlap  # overlap 保证块之间有50字符重叠

    # 丢弃最后一块如果不足 overlap 字符
    if chunks and len(chunks[-1]) < overlap:
        chunks.pop()

    return chunks

def generate_embedding(text: str, model: str = "text-embedding-3-small") -> list[float]:
    """
    调用 LLM 兼容 API 生成文本 embedding。
    使用 text-embedding-3-small 的 input 格式（POST /embeddings）。
    """
    from services.ai.client import get_provider_config
    import httpx

    provider_config = get_provider_config("openai")  # 使用 openai provider 做 embedding
    if not provider_config or not provider_config.get("api_key"):
        raise ValueError("Embedding provider (openai) not configured")

    api_key = provider_config["api_key"]
    base_url = provider_config.get("base_url", "https://api.openai.com/v1")

    url = f"{base_url.rstrip('/')}/embeddings"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "input": text[:8191],  # embedding 输入限制
    }

    with httpx.Client(timeout=httpx.Timeout(10.0)) as client:
        resp = client.post(url, headers=headers, json=payload)
        resp.raise_for_status()
        result = resp.json()

    return result["data"][0]["embedding"]

def embed_document(doc_id: str, title: str, content: str, url: str,
                   category: str = "", department: str = "",
                   chunk_size: int = 512, overlap: int = 50) -> int:
    """
    将文档分块并生成向量，存入 Qdrant。
    返回成功入库的块数量。
    """
    from services.qdrant import upsert_points, ensure_collection
    from qdrant_client.models import PointStruct

    ensure_collection()

    chunks = chunk_text(content, chunk_size=chunk_size, overlap=overlap)
    if not chunks:
        return 0

    points = []
    for i, chunk in enumerate(chunks):
        try:
            vector = generate_embedding(chunk)
        except Exception as e:
            logger.warning(f"Failed to embed chunk {i} of doc {doc_id}: {e}")
            continue

        point_id = f"{doc_id}_{i}"
        point = PointStruct(
            id=point_id,
            vector=vector,
            payload={
                "doc_id": doc_id,
                "title": title,
                "chunk_text": chunk,
                "url": url,
                "category": category or "",
                "department": department or "",
            },
        )
        points.append(point)

    if points:
        upsert_points(points)
        logger.info(f"Embedded {len(points)} chunks for doc {doc_id}")

    return len(points)
```

---

## Task 4: RAG 服务（检索 + 构建 Prompt + 调用 LLM）

### 4.1 RAG 核心逻辑

**文件:** `backend/services/rag.py`（新建）

```python
import logging
import json
from typing import Optional

from services.qdrant import search_points
from services.ai.client import call_llm

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """你是一个学校信息助手，基于给定的文档内容回答用户问题。

规则：
1. 只根据提供的文档内容回答，不要编造
2. 如果文档中没有相关信息，回复"抱歉，知识库中没有找到相关内容"
3. 回答要简洁，直接给出答案
4. 在答案末尾注明参考来源的文档标题，格式：参考：《文档标题》
5. 不要在答案中重复问题"""

def retrieve_chunks(query: str, top_k: int = 3, score_threshold: float = 0.5) -> list[dict]:
    """从 Qdrant 检索最相关的文档块"""
    from services.ai.embedding import generate_embedding
    try:
        query_vector = generate_embedding(query)
        return search_points(query_vector, top_k=top_k, score_threshold=score_threshold)
    except Exception as e:
        logger.error(f"Vector search failed: {e}")
        return []

def build_rag_prompt(question: str, chunks: list[dict]) -> list[dict]:
    """构建 RAG 消息列表（system + user）"""
    if not chunks:
        return [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"问题：{question}\n\n抱歉，知识库中没有找到相关内容。"},
        ]

    docs_section = "参考文档：\n"
    for i, chunk in enumerate(chunks, 1):
        payload = chunk.get("payload", {})
        docs_section += f"---\n文档{i}：《{payload.get('title', '')}》\n{payload.get('chunk_text', '')}\n"

    user_content = f"""{docs_section}
---
问题：{question}"""

    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_content},
    ]

def answer_question(question: str, provider_id: str = "openai",
                    top_k: int = 3, score_threshold: float = 0.5) -> tuple[str, list[dict]]:
    """
    RAG 问答：检索相关块 → 构建 Prompt → 调用 LLM → 返回答案和来源。
    返回 (answer_text, sources_list)
    """
    chunks = retrieve_chunks(question, top_k=top_k, score_threshold=score_threshold)
    messages = build_rag_prompt(question, chunks)

    try:
        answer = call_llm(provider_id, messages)
    except Exception as e:
        logger.error(f"LLM call failed: {e}")
        raise

    sources = [
        {
            "doc_id": c["payload"].get("doc_id", ""),
            "title": c["payload"].get("title", ""),
            "url": c["payload"].get("url", ""),
            "snippet": c["payload"].get("chunk_text", "")[:200],
            "score": round(c["score"], 3),
        }
        for c in chunks
    ]

    return answer, sources
```

---

## Task 5: Chat API 路由

### 5.1 Chat 路由

**文件:** `backend/api/chat.py`（新建）

```python
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select
from typing import Optional
import uuid
from datetime import datetime, timezone

from database import get_session
from models.user import User
from models.chat import ChatSession, ChatMessage
from services.auth import get_current_user_from_cookie

router = APIRouter()

class CreateSessionRequest(BaseModel):
    title: Optional[str] = None

class SendMessageRequest(BaseModel):
    content: str

# --- 会话管理 ---

@router.get("/sessions")
def list_sessions(
    current_user: User = Depends(get_current_user_from_cookie),
    session: Session = Depends(get_session),
):
    """返回当前用户所有会话，按 updated_at 倒序"""
    sessions = session.exec(
        select(ChatSession)
        .where(ChatSession.user_id == current_user.id)
        .order_by(ChatSession.updated_at.desc())
    ).all()
    return {
        "sessions": [
            {"id": s.id, "title": s.title, "created_at": s.created_at, "updated_at": s.updated_at}
            for s in sessions
        ]
    }

@router.post("/sessions")
def create_session(
    body: CreateSessionRequest,
    current_user: User = Depends(get_current_user_from_cookie),
    session: Session = Depends(get_session),
):
    """创建新会话"""
    title = body.title or "新对话"
    new_session = ChatSession(
        id=str(uuid.uuid4()),
        user_id=current_user.id,
        title=title,
    )
    session.add(new_session)
    session.commit()
    return {"id": new_session.id, "title": new_session.title, "created_at": new_session.created_at}

@router.delete("/sessions/{session_id}")
def delete_session(
    session_id: str,
    current_user: User = Depends(get_current_user_from_cookie),
    session: Session = Depends(get_session),
):
    """删除会话及其所有消息"""
    chat_session = session.exec(
        select(ChatSession)
        .where(ChatSession.id == session_id, ChatSession.user_id == current_user.id)
    ).first()
    if not chat_session:
        raise HTTPException(status_code=404, detail="Session not found")

    # 删除所有消息
    messages = session.exec(
        select(ChatMessage).where(ChatMessage.session_id == session_id)
    ).all()
    for msg in messages:
        session.delete(msg)

    session.delete(chat_session)
    session.commit()
    return {"message": "Session deleted"}

@router.get("/sessions/{session_id}/messages")
def get_messages(
    session_id: str,
    current_user: User = Depends(get_current_user_from_cookie),
    session: Session = Depends(get_session),
):
    """返回会话所有消息，按 created_at 升序"""
    chat_session = session.exec(
        select(ChatSession)
        .where(ChatSession.id == session_id, ChatSession.user_id == current_user.id)
    ).first()
    if not chat_session:
        raise HTTPException(status_code=404, detail="Session not found")

    messages = session.exec(
        select(ChatMessage)
        .where(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.created_at.asc())
    ).all()
    return {
        "messages": [
            {
                "id": m.id,
                "role": m.role,
                "content": m.content,
                "sources": m.sources,
                "created_at": m.created_at,
            }
            for m in messages
        ]
    }

# --- 问答 ---

@router.post("/sessions/{session_id}/messages")
def send_message(
    session_id: str,
    body: SendMessageRequest,
    current_user: User = Depends(get_current_user_from_cookie),
    session: Session = Depends(get_session),
):
    """发送消息，触发 RAG 问答，返回助手回复"""
    chat_session = session.exec(
        select(ChatSession)
        .where(ChatSession.id == session_id, ChatSession.user_id == current_user.id)
    ).first()
    if not chat_session:
        raise HTTPException(status_code=404, detail="Session not found")

    user_content = body.content.strip()
    if not user_content:
        raise HTTPException(status_code=400, detail="消息内容不能为空")

    now = datetime.now(timezone.utc).isoformat()

    # 保存用户消息
    user_msg = ChatMessage(
        id=str(uuid.uuid4()),
        session_id=session_id,
        role="user",
        content=user_content,
    )
    session.add(user_msg)

    # 更新会话标题（首次用问题前30字）
    if not chat_session.title or chat_session.title == "新对话":
        chat_session.title = user_content[:30]
    chat_session.updated_at = now
    session.add(chat_session)
    session.commit()

    # 调用 RAG
    from services.rag import answer_question
    try:
        answer, sources = answer_question(user_content)
    except Exception as e:
        answer = f"抱歉，回答生成失败：{str(e)}"
        sources = []

    # 保存助手消息
    assistant_msg = ChatMessage(
        id=str(uuid.uuid4()),
        session_id=session_id,
        role="assistant",
        content=answer,
        sources=json.dumps(sources, ensure_ascii=False),
    )
    session.add(assistant_msg)
    chat_session.updated_at = datetime.now(timezone.utc).isoformat()
    session.commit()
    session.refresh(assistant_msg)

    return {
        "id": assistant_msg.id,
        "role": "assistant",
        "content": assistant_msg.content,
        "sources": assistant_msg.sources,
        "created_at": assistant_msg.created_at,
    }
```

### 5.2 注册路由到 main.py

**文件:** `backend/main.py`

在现有导入下添加：
```python
from api.chat import router as chat_router
```

在 app 初始化时（`app = FastAPI(...)` 之后）添加：
```python
app.include_router(chat_router, prefix="/api/chat", tags=["chat"])
```

---

## Task 6: 爬虫集成（文档入库时生成向量）

### 6.1 修改 crawl_article

**文件:** `backend/services/crawler.py`

在 `_crawl_article` 函数中，找到文档保存到数据库并索引到 Meilisearch **之后**（`index_document(doc)` 调用之后），添加：

```python
# 异步生成文档向量并存入 Qdrant
try:
    from services.ai.embedding import embed_document
    embed_document(
        doc_id=doc.id,
        title=doc.title,
        content=doc.content or "",
        url=doc.url,
        category=doc.category or "",
        department=doc.department or "",
    )
except Exception as e:
    logger.warning(f"Failed to embed document {doc.id}: {e}")
```

---

## Task 7: 前端路由

### 7.1 添加 /chat 路由

**文件:** `frontend/src/router/index.js`

在现有路由配置中添加：
```javascript
{
  path: '/chat',
  component: () => import('../views/Chat.vue'),
  meta: { requiresAuth: true },
},
```

---

## Task 8: Chat 主页面

### 8.1 Chat.vue

**文件:** `frontend/src/views/Chat.vue`（新建）

```
布局：左侧边栏（会话列表）+ 右侧主区域（消息列表 + 输入框）
组件拆分：
- SessionList.vue：会话列表，含新建/删除
- MessageList.vue：消息气泡渲染
- SourceList.vue：来源文档列表
```

完整代码：

```vue
<template>
  <div class="chat-layout">
    <!-- 左侧边栏 -->
    <aside class="sidebar">
      <div class="sidebar-header">
        <button class="btn-primary btn-new" @click="createSession">+ 新建会话</button>
      </div>
      <div class="session-list">
        <div
          v-for="s in sessions"
          :key="s.id"
          class="session-item"
          :class="{ active: currentSessionId === s.id }"
          @click="selectSession(s.id)"
        >
          <span class="session-title">{{ s.title || '新对话' }}</span>
          <button class="btn-icon" @click.stop="deleteSession(s.id)" title="删除">×</button>
        </div>
      </div>
    </aside>

    <!-- 主区域 -->
    <main class="chat-main">
      <!-- 消息列表 -->
      <div class="messages" ref="messagesEl">
        <div v-if="!currentSessionId" class="empty-hint">
          选择或新建一个会话开始对话
        </div>
        <div v-else-if="messages.length === 0" class="empty-hint">
          你好！可以问我关于学校通知、制度等任何问题
        </div>
        <div v-for="msg in messages" :key="msg.id" :class="['message', msg.role]">
          <div class="message-content">
            <span v-if="msg.role === 'user'">{{ msg.content }}</span>
            <div v-else>
              <p>{{ msg.content }}</p>
              <SourceList v-if="msg.sources && msg.sources.length > 0" :sources="msg.sources" />
            </div>
          </div>
        </div>
        <div v-if="loading" class="message assistant">
          <div class="message-content skeleton">
            <div class="skeleton-line"></div>
            <div class="skeleton-line short"></div>
            <div class="skeleton-line"></div>
          </div>
        </div>
      </div>

      <!-- 输入区 -->
      <div class="input-area">
        <textarea
          v-model="inputText"
          class="input-box"
          placeholder="输入问题..."
          rows="1"
          :disabled="!currentSessionId || loading"
          @keydown.enter.exact.prevent="sendMessage"
          @input="autoResize"
        ></textarea>
        <button class="btn-primary btn-send" @click="sendMessage" :disabled="!inputText.trim() || loading">发送</button>
      </div>
    </main>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import api from '../api'
import SourceList from '../components/chat/SourceList.vue'

const sessions = ref([])
const currentSessionId = ref(null)
const messages = ref([])
const inputText = ref('')
const loading = ref(false)
const messagesEl = ref(null)

onMounted(() => {
  loadSessions()
})

async function loadSessions() {
  const { data } = await api.get('/chat/sessions')
  sessions.value = data.sessions
  if (sessions.value.length > 0 && !currentSessionId.value) {
    selectSession(sessions.value[0].id)
  }
}

async function createSession() {
  const { data } = await api.post('/chat/sessions', { title: '新对话' })
  sessions.value.unshift(data)
  selectSession(data.id)
}

async function selectSession(id) {
  currentSessionId.value = id
  const { data } = await api.get(`/chat/sessions/${id}/messages`)
  messages.value = data.messages.map(m => ({
    ...m,
    sources: typeof m.sources === 'string' ? JSON.parse(m.sources || '[]') : m.sources,
  }))
  scrollBottom()
}

async function deleteSession(id) {
  if (!confirm('确定删除该会话？')) return
  await api.delete(`/chat/sessions/${id}`)
  sessions.value = sessions.value.filter(s => s.id !== id)
  if (currentSessionId.value === id) {
    currentSessionId.value = sessions.value[0]?.id || null
    messages.value = []
  }
}

async function sendMessage() {
  const content = inputText.value.trim()
  if (!content || loading.value || !currentSessionId.value) return

  inputText.value = ''
  loading.value = true

  // 先乐观显示用户消息
  messages.value.push({ id: 'tmp-user', role: 'user', content, sources: [] })

  try {
    const { data } = await api.post(`/chat/sessions/${currentSessionId.value}/messages`, { content })
    data.sources = typeof data.sources === 'string' ? JSON.parse(data.sources || '[]') : (data.sources || [])
    messages.value.push(data)
    // 更新会话标题
    const s = sessions.value.find(s => s.id === currentSessionId.value)
    if (s && !s.title) s.title = content.slice(0, 30)
  } catch (e) {
    console.error(e)
  } finally {
    loading.value = false
    scrollBottom()
  }
}

function scrollBottom() {
  setTimeout(() => {
    if (messagesEl.value) {
      messagesEl.value.scrollTop = messagesEl.value.scrollHeight
    }
  }, 50)
}

function autoResize(e) {
  e.target.style.height = 'auto'
  e.target.style.height = Math.min(e.target.scrollHeight, 120) + 'px'
}
</script>

<style scoped>
.chat-layout {
  display: flex;
  height: calc(100dvh - 56px);
}
.sidebar {
  width: 240px;
  border-right: 1px solid var(--color-border);
  display: flex;
  flex-direction: column;
  overflow: hidden;
}
.sidebar-header {
  padding: 12px;
  border-bottom: 1px solid var(--color-border);
}
.btn-new {
  width: 100%;
}
.session-list {
  flex: 1;
  overflow-y: auto;
}
.session-item {
  display: flex;
  align-items: center;
  padding: 10px 12px;
  cursor: pointer;
  border-bottom: 1px solid var(--color-border);
  gap: 8px;
}
.session-item:hover { background: var(--color-bg-hover); }
.session-item.active { background: var(--color-bg-active); }
.session-title {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 0.875rem;
}
.btn-icon {
  background: none;
  border: none;
  cursor: pointer;
  font-size: 1rem;
  color: var(--color-text-secondary);
  opacity: 0;
  transition: opacity 0.2s;
}
.session-item:hover .btn-icon { opacity: 1; }

.chat-main {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}
.messages {
  flex: 1;
  overflow-y: auto;
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.empty-hint {
  text-align: center;
  color: var(--color-text-secondary);
  margin-top: 40px;
}
.message {
  display: flex;
  max-width: 75%;
}
.message.user { align-self: flex-end; }
.message.assistant { align-self: flex-start; }
.message-content {
  padding: 10px 14px;
  border-radius: 12px;
  line-height: 1.5;
  font-size: 0.9375rem;
}
.message.user .message-content {
  background: var(--color-primary);
  color: #fff;
}
.message.assistant .message-content {
  background: var(--color-bg-hover);
}
.skeleton-line {
  height: 12px;
  background: var(--color-border);
  border-radius: 4px;
  margin-bottom: 8px;
  width: 100%;
}
.skeleton-line.short { width: 60%; }

.input-area {
  display: flex;
  gap: 8px;
  padding: 12px 16px;
  border-top: 1px solid var(--color-border);
}
.input-box {
  flex: 1;
  padding: 10px 12px;
  border: 1px solid var(--color-border);
  border-radius: 8px;
  resize: none;
  font-family: inherit;
  font-size: 0.9375rem;
  line-height: 1.5;
  max-height: 120px;
  overflow-y: auto;
}
.btn-send {
  align-self: flex-end;
}
</style>
```

---

## Task 9: SourceList 组件

### 9.1 SourceList.vue

**文件:** `frontend/src/components/chat/SourceList.vue`（新建）

```vue
<template>
  <div class="source-list" v-if="sources && sources.length > 0">
    <div class="source-label">来源：</div>
    <a
      v-for="s in sources"
      :key="s.doc_id"
      :href="s.url"
      target="_blank"
      class="source-item"
    >
      {{ s.title }}
      <span class="source-score">({{ Math.round(s.score * 100) }}%)</span>
    </a>
  </div>
</template>

<script setup>
defineProps({
  sources: {
    type: Array,
    default: () => [],
  },
})
</script>

<style scoped>
.source-list {
  margin-top: 8px;
  padding-top: 8px;
  border-top: 1px solid var(--color-border);
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.source-label {
  font-size: 0.75rem;
  color: var(--color-text-secondary);
  margin-bottom: 2px;
}
.source-item {
  font-size: 0.8125rem;
  color: var(--color-primary);
  text-decoration: none;
  display: flex;
  align-items: center;
  gap: 4px;
}
.source-item:hover { text-decoration: underline; }
.source-score {
  font-size: 0.75rem;
  color: var(--color-text-secondary);
}
</style>
```

---

## Task 10: 更新 task.md

**文件:** `docs/opencode/task.md`

在功能增强建议中添加新条目：
```
| F7 | MEDIUM | 自然语言问答系统（RAG + Qdrant 向量检索 + 多会话对话） |
```

---

## 依赖关系

```
Task 1 (config + models)
  ↓
Task 2 (qdrant.py)
  ↓
Task 3 (embedding.py) ← 依赖 Task 2
  ↓
Task 4 (rag.py) ← 依赖 Task 3
  ↓
Task 5 (chat API) ← 依赖 Task 4
  ↓
Task 6 (crawler 集成) ← 依赖 Task 3
Task 7 (frontend router) ← 独立
  ↓
Task 8 (Chat.vue) ← 依赖 Task 7
  ↓
Task 9 (SourceList.vue) ← 依赖 Task 8
  ↓
Task 10 (task.md)
```

---

## 验证步骤（实现完成后）

1. **启动 Qdrant**：`docker run -d -p 6333:6333 -p 6334:6334 qdrant/qdrant:v1.7.0`
2. **测试向量写入**：调用 `embed_document()` 入库一篇测试文档，确认 Qdrant 中有数据
3. **测试 RAG 检索**：调用 `answer_question()` 确认能返回答案和来源
4. **测试 API**：启动后端，`POST /api/chat/sessions` → `POST /api/chat/sessions/{id}/messages`
5. **测试前端**：打开 `/chat` 页面，创建会话，发送问题，验证答案和来源显示正确
6. **测试爬虫**：触发一次爬取，确认新文档自动生成向量并可检索
