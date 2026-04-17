# 对话式混合搜索 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 Chat 页面的 RAG 流程从纯向量检索改造为关键词+向量混合检索，回答带引用式链接，并将 Chat 设为默认主页。

**Architecture:** 在 `rag.py` 中新增关键词提取和混合检索函数，改造 prompt 为引用式输出。前端重写 `SourceList.vue` 支持编号角标和来源 tag，`Chat.vue` 渲染引用链接并处理降级提示。路由将 `/` 指向 Chat，搜索页挪到 `/search`。

**Tech Stack:** Python 3.12 / FastAPI / MeiliSearch / Qdrant / Vue 3 Composition API

---

### Task 1: 后端 — 新增关键词提取函数

**Files:**
- Modify: `backend/services/rag.py` (在 `retrieve_chunks` 函数之前插入新函数)

- [ ] **Step 1: 在 rag.py 添加 `extract_keywords` 函数**

在 `rag.py` 第 52 行（`retrieve_chunks` 函数之前）插入：

```python
def extract_keywords(question: str) -> tuple[list[str], bool]:
    """用 LLM 从用户问题中提取搜索关键词。返回 (keywords, fallback)。
    fallback=True 表示关键词提取失败，降级为原问题搜索。"""
    from services.ai.client import call_llm, get_default_provider

    prompt = [
        {"role": "system", "content": "你是一个关键词提取器。从用户的问题中提取3-5个最适合搜索引擎搜索的关键词。只返回JSON数组，不要其他内容。示例：[\"食堂\", \"营业时间\", \"开放\"]"},
        {"role": "user", "content": question},
    ]

    try:
        provider = get_default_provider()
        provider_id = provider["id"] if provider else "openai"
        raw = call_llm(provider_id, prompt)
        # 尝试解析 JSON 数组
        import json
        text = raw.strip()
        # 去掉可能的 markdown 代码块标记
        if text.startswith("```"):
            text = text.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
        keywords = json.loads(text)
        if isinstance(keywords, list) and len(keywords) > 0:
            return [str(k).strip() for k in keywords if str(k).strip()], False
    except Exception as e:
        logger.warning(f"[rag] Keyword extraction failed, falling back: {e}")

    # 降级：直接用原问题
    return [question], True
```

- [ ] **Step 2: 验证语法正确**

Run: `cd E:/code/bipthelper/backend && python -c "import ast; ast.parse(open('services/rag.py').read()); print('OK')"`

---

### Task 2: 后端 — 新增混合检索函数

**Files:**
- Modify: `backend/services/rag.py` (在 `extract_keywords` 函数之后插入)

- [ ] **Step 1: 在 rag.py 添加 `hybrid_retrieve` 函数和辅助函数**

在 `extract_keywords` 函数之后、`retrieve_chunks` 函数之前插入：

```python
def _compute_recency_score(publish_date: str | None) -> float:
    """根据发布日期计算时效性分数"""
    if not publish_date:
        return 0.5
    try:
        from datetime import datetime, timezone
        dt = datetime.fromisoformat(publish_date.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        days = (datetime.now(timezone.utc) - dt).days
        if days <= 30:
            return 1.0
        elif days <= 90:
            return 0.8
        elif days <= 180:
            return 0.6
        elif days <= 365:
            return 0.4
        else:
            return 0.2
    except Exception:
        return 0.5


def hybrid_retrieve(question: str, keywords: list[str], top_k: int = 5) -> list[dict]:
    """双路混合检索：MeiliSearch 关键词 + Qdrant 向量，合并去重，综合排序。"""
    from services.search import search_documents
    from services.ai.embedding import generate_embedding

    keyword_results = []
    vector_results = []

    # 路径1: MeiliSearch 关键词搜索
    try:
        query_str = " ".join(keywords)
        search_res = search_documents(query_str, page=1, page_size=top_k)
        for hit in search_res.get("results", []):
            keyword_results.append({
                "doc_id": str(hit.get("id", "")),
                "title": hit.get("title", ""),
                "url": hit.get("url", ""),
                "content": hit.get("_formatted", {}).get("content", hit.get("content", ""))[:300],
                "raw_score": hit.get("_rankingScore", hit.get("_relevanceScore", 1.0)),
                "source": "keyword",
                "publish_date": hit.get("publish_date"),
            })
    except Exception as e:
        logger.warning(f"[rag] MeiliSearch retrieval failed: {e}")

    # 路径2: Qdrant 向量检索
    try:
        query_vector = generate_embedding(question)
        raw_hits = search_points(query_vector, top_k=top_k, score_threshold=0.3)
        for hit in raw_hits:
            payload = hit.get("payload", {})
            vector_results.append({
                "doc_id": str(payload.get("doc_id", "")),
                "title": payload.get("title", ""),
                "url": payload.get("url", ""),
                "content": payload.get("chunk_text", "")[:300],
                "raw_score": hit.get("score", 0.0),
                "source": "vector",
                "publish_date": payload.get("publish_date"),
            })
    except Exception as e:
        logger.warning(f"[rag] Qdrant retrieval failed: {e}")

    # 如果双路都失败，抛出异常
    if not keyword_results and not vector_results:
        raise RagError(RagError.RETRIEVAL, "Both keyword and vector retrieval returned no results")

    # 分数归一化：各路内部归一化到 [0, 1]
    def normalize_batch(items):
        if not items:
            return items
        max_score = max(item["raw_score"] for item in items)
        if max_score > 0:
            for item in items:
                item["norm_score"] = item["raw_score"] / max_score
        else:
            for item in items:
                item["norm_score"] = 0.0
        return items

    normalize_batch(keyword_results)
    normalize_batch(vector_results)

    # 合并去重，以 doc_id 为 key
    merged = {}
    for item in keyword_results + vector_results:
        doc_id = item["doc_id"]
        if not doc_id:
            continue
        if doc_id in merged:
            existing = merged[doc_id]
            # 取归一化分数较高的，标记为 "both"
            if item["norm_score"] > existing["norm_score"]:
                item["source"] = "both"
                merged[doc_id] = item
            else:
                existing["source"] = "both"
        else:
            merged[doc_id] = item

    # 综合排序：relevance * 0.6 + recency * 0.4
    for item in merged.values():
        recency = _compute_recency_score(item.get("publish_date"))
        item["final_score"] = item["norm_score"] * 0.6 + recency * 0.4

    sorted_results = sorted(merged.values(), key=lambda x: x["final_score"], reverse=True)
    return sorted_results[:8]
```

- [ ] **Step 2: 验证语法正确**

Run: `cd E:/code/bipthelper/backend && python -c "import ast; ast.parse(open('services/rag.py').read()); print('OK')"`

---

### Task 3: 后端 — 改造 build_rag_prompt 为引用式输出

**Files:**
- Modify: `backend/services/rag.py:10-17` (SYSTEM_PROMPT 常量)
- Modify: `backend/services/rag.py:63-103` (build_rag_prompt 函数)

- [ ] **Step 1: 替换 SYSTEM_PROMPT**

将 `SYSTEM_PROMPT` 常量（第 10-17 行）替换为：

```python
SYSTEM_PROMPT = """你是一个学校信息检索助手，基于提供的参考资料回答用户问题。

规则：
1. 回答必须基于提供的参考资料，不要编造信息
2. 引用资料时使用 [1]、[2] 等编号标注来源，编号对应参考资料的序号
3. 如果资料不足以回答问题，明确告知用户
4. 回答要简洁，直接给出答案
5. 回答末尾不需要列出参考文献，系统会自动生成
6. 不要在答案中重复问题"""
```

- [ ] **Step 2: 替换 build_rag_prompt 函数**

将 `build_rag_prompt` 函数（第 63-103 行）替换为：

```python
def build_rag_prompt(question: str, chunks: list[dict], max_tokens: int = 3000) -> list[dict]:
    """构建 RAG 消息列表（system + user），按综合分数排序，带编号的引用式格式。"""
    if not chunks:
        return [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"问题：{question}\n\n抱歉，知识库中没有找到相关内容。"},
        ]

    # 构建带编号的参考资料节
    docs_parts = []
    current_tokens = 0
    for i, chunk in enumerate(chunks, 1):
        content_text = chunk.get("content", "")
        title = chunk.get("title", "")
        url = chunk.get("url", "")
        header = f"[{i}] 标题：{title} | URL：{url}\n"
        body = f"内容：{content_text}\n"
        section = header + body
        section_tokens = _estimate_tokens(section)

        if current_tokens + section_tokens > max_tokens - 200:
            remaining = max_tokens - current_tokens - _estimate_tokens(header) - 50
            if remaining > 100:
                docs_parts.append(header + f"内容：{content_text[:remaining * 2]}\n")
                current_tokens += remaining
            break

        docs_parts.append(section)
        current_tokens += section_tokens

    docs_section = "参考资料：\n" + "\n".join(docs_parts)
    user_content = f"{docs_section}\n---\n问题：{question}"

    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_content},
    ]
```

- [ ] **Step 3: 验证语法正确**

Run: `cd E:/code/bipthelper/backend && python -c "import ast; ast.parse(open('services/rag.py').read()); print('OK')"`

---

### Task 4: 后端 — 重写 answer_question 使用新流程

**Files:**
- Modify: `backend/services/rag.py:105-135` (answer_question 函数)

- [ ] **Step 1: 替换 answer_question 函数**

将 `answer_question` 函数替换为：

```python
def answer_question(question: str, provider_id: str = "openai",
                    top_k: int = 5, score_threshold: float = 0.3) -> dict:
    """
    混合检索 RAG 问答：关键词提取 → 双路检索 → 合并 → LLM 生成引用式回答。
    返回 {"answer": str, "sources": list, "fallback": str | None}
    """
    safe_question = _sanitize_question(question)

    # 1. 提取关键词
    keywords, fallback = extract_keywords(safe_question)

    # 2. 混合检索
    try:
        results = hybrid_retrieve(safe_question, keywords, top_k=top_k)
    except Exception as e:
        logger.error(f"[rag] Hybrid retrieval failed: {e}")
        raise RagError(RagError.RETRIEVAL, str(e)) from e

    # 3. 构建 prompt
    messages = build_rag_prompt(safe_question, results)

    # 4. 调用 LLM
    try:
        answer = call_llm(provider_id, messages)
    except Exception as e:
        logger.error(f"[rag] LLM call failed: {e}")
        raise RagError(RagError.LLM_CALL, str(e)) from e

    # 5. 构建 sources 列表，编号与 prompt 中顺序一致
    sources = [
        {
            "index": i,
            "doc_id": r.get("doc_id", ""),
            "title": r.get("title", ""),
            "url": r.get("url", ""),
            "snippet": r.get("content", "")[:200],
            "score": round(r.get("final_score", r.get("norm_score", 0)), 3),
            "source": r.get("source", "unknown"),
            "publish_date": r.get("publish_date"),
        }
        for i, r in enumerate(results, 1)
    ]

    return {
        "answer": answer,
        "sources": sources,
        "fallback": "keyword_extraction_failed" if fallback else None,
    }
```

- [ ] **Step 2: 验证语法正确**

Run: `cd E:/code/bipthelper/backend && python -c "import ast; ast.parse(open('services/rag.py').read()); print('OK')"`

---

### Task 5: 后端 — 适配 chat.py API 返回格式

**Files:**
- Modify: `backend/api/chat.py:175-209` (send_message 函数中 RAG 调用和返回部分)

- [ ] **Step 1: 修改 send_message 函数中的 RAG 调用和返回**

将 `chat.py` 第 175-209 行替换为：

```python
    # 调用 RAG，区分错误类型
    from services.rag import answer_question, RagError as RAGErr
    try:
        result = answer_question(user_content)
        answer = result["answer"]
        sources = result["sources"]
        fallback = result.get("fallback")
    except Exception as e:
        logger.error(f"[chat] RAG error for session {session_id}: {e}")
        error_type = getattr(e, "error_type", None) if isinstance(e, RAGErr) else "unknown"
        detail = f"抱歉，回答生成失败（类型：{error_type}）：{str(e)[:100]}"
        answer = detail
        sources = []
        fallback = None
        # RAG 失败，回滚积分记账
        session.rollback()
        session.refresh(current_user)
        raise HTTPException(status_code=500, detail="回答生成失败，积分已退回")

    # 保存助手消息
    source_data = {"sources": sources, "fallback": fallback}
    assistant_msg = ChatMessage(
        id=str(uuid.uuid4()),
        session_id=session_id,
        role="assistant",
        content=answer,
        sources=json.dumps(source_data, ensure_ascii=False),
    )
    session.add(assistant_msg)
    chat_session.updated_at = datetime.now(timezone.utc).isoformat()
    session.commit()  # RAG 成功，提交积分扣减 + 消息
    session.refresh(assistant_msg)

    # 解析 sources 字段返回给前端
    parsed_sources = json.loads(assistant_msg.sources) if isinstance(assistant_msg.sources, str) else assistant_msg.sources

    return {
        "id": assistant_msg.id,
        "role": "assistant",
        "content": assistant_msg.content,
        "sources": parsed_sources.get("sources", []),
        "fallback": parsed_sources.get("fallback"),
        "created_at": assistant_msg.created_at,
    }
```

- [ ] **Step 2: 验证语法正确**

Run: `cd E:/code/bipthelper/backend && python -c "import ast; ast.parse(open('api/chat.py').read()); print('OK')"`

---

### Task 6: 前端 — 路由调整，Chat 设为默认主页

**Files:**
- Modify: `frontend/src/router/index.js`

- [ ] **Step 1: 修改路由配置**

将 `router/index.js` 第 4-40 行的 `routes` 数组替换为：

```javascript
const routes = [
  { path: '/login', name: 'Login', component: () => import('../views/Login.vue') },
  { path: '/register', name: 'Register', component: () => import('../views/Register.vue') },
  {
    path: '/',
    component: () => import('../views/Chat.vue'),
    meta: { requiresAuth: true }
  },
  {
    path: '/search',
    name: 'Search',
    component: () => import('../views/Home.vue'),
    meta: { requiresAuth: true }
  },
  {
    path: '/admin',
    component: () => import('../views/Admin.vue'),
    meta: { requiresAuth: true, requiresAdmin: true }
  },
  {
    path: '/admin/ai',
    component: () => import('../views/AISettings.vue'),
    meta: { requiresAuth: true, requiresAdmin: true }
  },
  {
    path: '/points',
    name: 'Points',
    component: () => import('../views/Points.vue'),
    meta: { requiresAuth: true }
  },
  {
    path: '/profile',
    name: 'Profile',
    component: () => import('../views/Profile.vue'),
    meta: { requiresAuth: true }
  },
  { path: '/:pathMatch(.*)*', redirect: '/' }
]
```

关键变更：`/` 从 Home.vue 改为 Chat.vue，新增 `/search` 指向 Home.vue。

---

### Task 7: 前端 — Chat.vue 添加导航链接和搜索入口

**Files:**
- Modify: `frontend/src/views/Chat.vue`

- [ ] **Step 1: 在 sidebar-header 中添加搜索入口链接**

在 `Chat.vue` 模板的 sidebar-header 区域（第 20-27 行），在 `sidebar-label` 和 `btn-new-chat` 之间添加一个搜索链接按钮：

将第 20-27 行：
```html
      <div class="sidebar-header">
        <span class="sidebar-label">对话</span>
        <button class="btn-new-chat" @click="createSession" title="新建会话" aria-label="新建会话">
```

替换为：
```html
      <div class="sidebar-header">
        <div class="sidebar-header-left">
          <router-link to="/search" class="btn-icon-sm" title="搜索" aria-label="搜索">
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <circle cx="11" cy="11" r="8"/><path d="m21 21-4.35-4.35"/>
            </svg>
          </router-link>
          <span class="sidebar-label">对话</span>
        </div>
        <button class="btn-new-chat" @click="createSession" title="新建会话" aria-label="新建会话">
```

- [ ] **Step 2: 在 mobile-nav 中添加搜索链接**

将第 59-66 行：
```html
      <header class="mobile-nav">
        <button class="btn-menu" @click="sidebarOpen = true" aria-label="打开会话列表">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <line x1="3" y1="6" x2="21" y2="6"/><line x1="3" y1="12" x2="21" y2="12"/><line x1="3" y1="18" x2="21" y2="18"/>
          </svg>
        </button>
        <span class="mobile-nav-title">{{ currentSessionId ? (sessions.find(s => s.id === currentSessionId)?.title || '新对话') : '石化助手' }}</span>
      </header>
```

替换为：
```html
      <header class="mobile-nav">
        <button class="btn-menu" @click="sidebarOpen = true" aria-label="打开会话列表">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <line x1="3" y1="6" x2="21" y2="6"/><line x1="3" y1="12" x2="21" y2="12"/><line x1="3" y1="18" x2="21" y2="18"/>
          </svg>
        </button>
        <span class="mobile-nav-title">{{ currentSessionId ? (sessions.find(s => s.id === currentSessionId)?.title || '新对话') : '石化助手' }}</span>
        <router-link to="/search" class="btn-icon-sm" title="搜索" aria-label="搜索">
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <circle cx="11" cy="11" r="8"/><path d="m21 21-4.35-4.35"/>
          </svg>
        </router-link>
      </header>
```

- [ ] **Step 3: 添加导航按钮的 CSS 样式**

在 `<style scoped>` 中 `.btn-new-chat` 样式块之后（约第 338 行后）添加：

```css
.sidebar-header-left {
  display: flex;
  align-items: center;
  gap: 8px;
}

.btn-icon-sm {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 26px;
  height: 26px;
  border-radius: 6px;
  color: var(--color-text-muted);
  text-decoration: none;
  transition: color var(--transition-fast), background var(--transition-fast);
}
.btn-icon-sm:hover {
  color: var(--color-primary);
  background: var(--color-surface-hover);
}
```

---

### Task 8: 前端 — 重写 SourceList.vue

**Files:**
- Modify: `frontend/src/components/chat/SourceList.vue` (完整重写)

- [ ] **Step 1: 完整替换 SourceList.vue**

将整个文件替换为：

```vue
<template>
  <div class="source-list" v-if="sources && sources.length > 0">
    <!-- 降级提示 -->
    <div v-if="fallback" class="fallback-notice">
      <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
        <circle cx="12" cy="12" r="10"/><path d="M12 8v4M12 16h.01"/>
      </svg>
      <span>关键词提取未生效，使用了原始问题搜索，结果可能不够精准</span>
      <button class="fallback-close" @click="dismissFallback = true" aria-label="关闭提示">&times;</button>
    </div>

    <div class="source-label">来源：</div>
    <div v-for="s in sources" :key="s.doc_id || s.index" class="source-item">
      <a :href="s.url" target="_blank" class="source-link">
        <span v-if="s.index" class="source-index">[{{ s.index }}]</span>
        {{ s.title }}
      </a>
      <div class="source-meta">
        <span v-if="s.score" class="source-score">{{ Math.round(s.score * 100) }}%</span>
        <span v-if="s.source" class="source-tag" :class="'tag-' + s.source">
          {{ sourceLabel(s.source) }}
        </span>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'

const props = defineProps({
  sources: {
    type: Array,
    default: () => [],
  },
  fallback: {
    type: String,
    default: null,
  },
})

const dismissFallback = ref(false)

function sourceLabel(source) {
  const labels = { keyword: '关键词', vector: '语义', both: '双重' }
  return labels[source] || source
}
</script>

<style scoped>
.source-list {
  margin-top: 8px;
  padding-top: 8px;
  border-top: 1px solid var(--color-border);
  display: flex;
  flex-direction: column;
  gap: 6px;
}

/* 降级提示 */
.fallback-notice {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 10px;
  border-radius: 6px;
  background: #fef3cd;
  color: #856404;
  font-size: 0.75rem;
  line-height: 1.4;
}
[data-theme="dark"] .fallback-notice {
  background: #3d3415;
  color: #f0d060;
}
.fallback-close {
  margin-left: auto;
  background: none;
  border: none;
  color: inherit;
  cursor: pointer;
  font-size: 1rem;
  line-height: 1;
  padding: 0 2px;
}

.source-label {
  font-size: 0.75rem;
  color: var(--color-text-secondary);
  margin-bottom: 2px;
}

.source-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.source-link {
  font-size: 0.8125rem;
  color: var(--color-primary);
  text-decoration: none;
  display: flex;
  align-items: center;
  gap: 4px;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.source-link:hover { text-decoration: underline; }

.source-index {
  font-weight: 600;
  font-size: 0.75rem;
  color: var(--color-primary);
  flex-shrink: 0;
}

.source-meta {
  display: flex;
  align-items: center;
  gap: 4px;
  flex-shrink: 0;
}

.source-score {
  font-size: 0.6875rem;
  color: var(--color-text-secondary);
}

.source-tag {
  font-size: 0.625rem;
  font-weight: 600;
  padding: 1px 5px;
  border-radius: 3px;
  text-transform: uppercase;
  letter-spacing: 0.03em;
}
.tag-keyword {
  background: #e0edff;
  color: #1a56db;
}
.tag-vector {
  background: #e6f9ed;
  color: #15803d;
}
.tag-both {
  background: #fff3e0;
  color: #c2410c;
}
[data-theme="dark"] .tag-keyword {
  background: #1e3a5f;
  color: #7cb3f0;
}
[data-theme="dark"] .tag-vector {
  background: #1a3d2a;
  color: #6ee7a0;
}
[data-theme="dark"] .tag-both {
  background: #3d2a15;
  color: #f0a060;
}
</style>
```

---

### Task 9: 前端 — Chat.vue 渲染引用链接 + 处理降级提示

**Files:**
- Modify: `frontend/src/views/Chat.vue`

- [ ] **Step 1: 修改消息气泡渲染，支持引用链接**

将第 106-109 行：
```html
            <div class="message-bubble">
              <p class="message-text">{{ msg.content }}</p>
            </div>
            <SourceList v-if="msg.role === 'assistant' && msg.sources && msg.sources.length > 0" :sources="msg.sources" class="message-sources" />
```

替换为：
```html
            <div class="message-bubble">
              <p class="message-text" v-html="renderContent(msg)"></p>
            </div>
            <SourceList v-if="msg.role === 'assistant' && msg.sources && msg.sources.length > 0" :sources="msg.sources" :fallback="msg.fallback" class="message-sources" />
```

- [ ] **Step 2: 在 script 中添加 renderContent 函数**

在 `autoResize` 函数之后（第 277 行后），添加：

```javascript
function renderContent(msg) {
  if (msg.role !== 'assistant' || !msg.sources || msg.sources.length === 0) {
    // 对非 assistant 消息或无来源的消息，转义 HTML 后返回
    const div = document.createElement('div')
    div.textContent = msg.content
    return div.innerHTML
  }
  // 转义基础内容防止 XSS
  const div = document.createElement('div')
  div.textContent = msg.content
  let html = div.innerHTML
  // 将 [1]、[2] 等替换为可点击的引用链接
  html = html.replace(/\[(\d+)\]/g, (match, num) => {
    const idx = parseInt(num)
    const source = msg.sources.find(s => s.index === idx)
    if (source && source.url) {
      return `<a href="${source.url}" target="_blank" rel="noopener" class="cite-link">${match}</a>`
    }
    return match
  })
  return html
}
```

- [ ] **Step 3: 添加引用链接 CSS 样式**

在 `<style scoped>` 中 `.message-text` 样式之后（约第 511 行后）添加：

```css
.cite-link {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 0.6875rem;
  font-weight: 600;
  min-width: 18px;
  height: 18px;
  padding: 0 3px;
  border-radius: 3px;
  background: var(--color-primary-muted);
  color: var(--color-primary);
  text-decoration: none;
  vertical-align: super;
  line-height: 1;
  transition: background var(--transition-fast);
}
.cite-link:hover {
  background: var(--color-primary);
  color: white;
}
```

- [ ] **Step 4: 修改 selectSession 和 sendMessage 中 sources 解析逻辑**

将 `selectSession` 函数（第 193-201 行）替换为：

```javascript
async function selectSession(id) {
  currentSessionId.value = id
  const { data } = await api.get(`/chat/sessions/${id}/messages`)
  messages.value = data.messages.map(m => {
    let parsed = m.sources
    if (typeof parsed === 'string') {
      try { parsed = JSON.parse(parsed || '{}') } catch { parsed = {} }
    }
    // 兼容旧格式：如果 parsed 是数组，说明是旧格式
    if (Array.isArray(parsed)) {
      return { ...m, sources: parsed, fallback: null }
    }
    return {
      ...m,
      sources: parsed.sources || parsed || [],
      fallback: parsed.fallback || null,
    }
  })
  scrollBottom()
}
```

将 `sendMessage` 函数（第 234-264 行）替换为：

```javascript
async function sendMessage() {
  const content = inputText.value.trim()
  if (!content || loading.value || !currentSessionId.value) return

  inputText.value = ''
  loading.value = true

  const tempId = crypto.randomUUID()
  messages.value.push({ id: tempId, role: 'user', content, sources: [], fallback: null, _failed: false })
  scrollBottom()

  try {
    const { data } = await api.post(`/chat/sessions/${currentSessionId.value}/messages`, { content })
    const idx = messages.value.findIndex(m => m.id === tempId)
    if (idx !== -1) {
      messages.value.splice(idx, 1, { id: tempId, role: 'user', content, sources: [], fallback: null })
    }
    messages.value.push({
      id: data.id,
      role: 'assistant',
      content: data.content,
      sources: data.sources || [],
      fallback: data.fallback || null,
    })
    const s = sessions.value.find(s => s.id === currentSessionId.value)
    if (s && !s.title) s.title = content.slice(0, 30)
  } catch (e) {
    const idx = messages.value.findIndex(m => m.id === tempId)
    if (idx !== -1) messages.value[idx] = { ...messages.value[idx], _failed: true }
    console.error(e)
    toast.error('发送失败，请检查网络后重试')
  } finally {
    loading.value = false
    scrollBottom()
  }
}
```

---

### Task 10: 前端 — Home.vue 添加对话入口链接

**Files:**
- Modify: `frontend/src/views/Home.vue`

- [ ] **Step 1: 在 Home.vue 导航栏中添加「对话」链接**

在 Home.vue header-nav 中（约第 22 行 `showPasswordChange` 按钮之前），添加一个对话入口链接：

在第 22 行之前插入：
```html
          <router-link to="/" class="nav-link">
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>
            </svg>
            对话
          </router-link>
```

由于 `/` 现在指向 Chat.vue，这个链接会跳转到对话主页。

---

### Task 11: 提交

- [ ] **Step 1: 构建前端并验证**

Run: `cd E:/code/bipthelper/frontend && npm run build`

- [ ] **Step 2: 将构建产物复制到后端静态目录**

Run: `xcopy /E /Y "E:\code\bipthelper\frontend\dist\*" "E:\code\bipthelper\backend\assets\frontend\"`

- [ ] **Step 3: 验证后端启动无报错**

Run: `cd E:/code/bipthelper/backend && python -c "from services.rag import answer_question, extract_keywords, hybrid_retrieve; print('All imports OK')"`

- [ ] **Step 4: Commit**

```bash
git add backend/services/rag.py backend/api/chat.py frontend/src/router/index.js frontend/src/views/Chat.vue frontend/src/components/chat/SourceList.vue frontend/src/views/Home.vue backend/assets/frontend/
git commit -m "feat: hybrid search with keyword+vector retrieval and citation-style links"
```
