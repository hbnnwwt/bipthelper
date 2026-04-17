# 对话式混合搜索设计文档

**日期：** 2026-04-10
**状态：** 已确认

## 背景

现有系统有两条独立路径：搜索页（MeiliSearch 关键词匹配返回结果列表）和对话页（RAG 向量检索 + LLM 生成回答）。用户希望以对话形式进行搜索，将关键词检索和语义检索结合，回答附带具体来源链接。

## 未来演进方向（记录）

以下三种方案作为后续迭代参考，当前仅实现方案 A。

| 方案 | 描述 | 适用场景 |
|------|------|----------|
| **方案 A（当前）** | 改造现有 RAG 流程，加入混合检索 + 引用式链接 | 当前实现 |
| **方案 B：搜索 Agent** | 独立搜索 Agent，ReAct 模式让 LLM 自主决定搜索策略，多轮搜索 | 需要更智能的多轮搜索能力时 |
| **方案 C：流式管道** | SSE 流式响应，先返回关键词提取状态，再返回搜索结果，最后流式输出回答 | 需要更好的用户体验和过程感时 |

---

## 方案 A 设计

### 1. 整体数据流

```
用户输入问题
    │
    ▼
┌─────────────────────┐
│ 1. LLM 提取关键词    │  ← 调用默认 AI provider，返回 3-5 个搜索词
└─────────┬───────────┘
          │
          ▼
┌─────────────────────────────────────┐
│ 2. 双路并行检索                       │
│   ├─ MeiliSearch（关键词）→ Top 5    │
│   └─ Qdrant 向量检索     → Top 5    │
└─────────┬───────────────────────────┘
          │
          ▼
┌─────────────────────┐
│ 3. 合并去重 + 排序   │  ← 按 doc_id 去重，综合分数排序，取 Top 8
└─────────┬───────────┘
          │
          ▼
┌──────────────────────────────────────┐
│ 4. LLM 生成回答                       │
│   - system prompt 要求引用式输出 [1][2] │
│   - 上下文携带来源元数据（标题、URL）    │
└─────────┬────────────────────────────┘
          │
          ▼
┌──────────────────────────────────────┐
│ 5. 返回给前端                          │
│   - answer: 带 [1][2] 引用的回答文本    │
│   - sources: 完整来源列表（标题+URL+分数）│
│   - fallback: 降级标记                  │
└──────────────────────────────────────┘
```

### 2. 关键词提取（extract_keywords）

新增函数 `extract_keywords(question: str) -> list[str]`

- 调用默认 AI provider，专门 prompt 要求提取 3-5 个搜索关键词
- temperature = 0，max_tokens = 100
- 返回 JSON 数组格式，解析后返回 `list[str]`

**Prompt 模板：**
```
你是一个关键词提取器。从用户的问题中提取3-5个最适合搜索引擎搜索的关键词。
只返回JSON数组，不要其他内容。
示例：["食堂", "营业时间", "开放"]
```

**降级策略：**
- LLM 调用失败或解析失败 → 直接用原问题作为搜索词
- 设置 `fallback = "keyword_extraction_failed"`
- 前端显示黄色提示条：「关键词提取未生效，使用了原始问题搜索，结果可能不够精准」
- 降级提示条可关闭

### 3. 混合检索与合并（hybrid_retrieve）

新增函数 `hybrid_retrieve(question: str, keywords: list[str]) -> list[dict]`

**双路检索：**
- MeiliSearch 路径：用 keywords 拼成空格分隔的搜索词，调 `search_documents()`，取 top 5
- Qdrant 路径：用原始 question 生成 embedding，调 `search_points()`，取 top 5

**分数归一化：**
- 各自归一化到 `[0, 1]` 区间：`score / max_score_in_batch`

**时效性排序：**

合并去重后的最终排序使用综合分数：

```
final_score = normalized_score * 0.6 + recency_score * 0.4
```

时效性分数基于 `publish_date`：
| 时间范围 | recency_score |
|----------|---------------|
| 30 天内 | 1.0 |
| 90 天内 | 0.8 |
| 180 天内 | 0.6 |
| 365 天内 | 0.4 |
| 更早 | 0.2 |
| 无日期 | 0.5（中性值） |

- MeiliSearch 侧自带 `publish_date:desc` 排序权重
- Qdrant 侧 chunk payload 中已有 `publish_date`

**合并去重：**
- 以 `doc_id` 为 key 去重
- 同一 doc_id 出现两次时，取归一化分数较高的那个
- 最终按综合分数降序排序，取 Top 8

**返回结构：**
```python
{
    "doc_id": str,
    "title": str,
    "url": str,
    "content": str,      # MeiliSearch 用 snippet，Qdrant 用 chunk_text
    "score": float,      # 归一化后的分数
    "source": str,       # "keyword" | "vector" | "both"
    "publish_date": str  # 原始发布日期
}
```

降级标记由 `answer_question()` 统一包装返回。

### 4. LLM 回答生成（带引用式链接）

**修改 `build_rag_prompt()`：**

System prompt：
```
你是一个信息检索助手。根据提供的参考资料回答用户问题。

规则：
1. 回答必须基于提供的参考资料，不要编造信息
2. 引用资料时使用 [1]、[2] 等编号标注来源
3. 如果资料不足以回答问题，明确告知用户
4. 回答末尾不需要列出参考文献，系统会自动生成
```

User message 结构：
```
参考资料：
[1] 标题：xxx | URL：xxx
内容：xxx

[2] 标题：xxx | URL：xxx
内容：xxx
...

用户问题：xxx
```

**返回数据结构：**

`answer_question()` 返回：
```python
{
    "answer": str,           # LLM 回答，带 [1][2] 引用
    "sources": [             # 完整来源列表，按编号顺序
        {
            "index": 1,      # 对应 [1]
            "title": str,
            "url": str,
            "snippet": str,  # 摘录片段
            "score": float,
            "source": str,   # "keyword" | "vector" | "both"
            "publish_date": str
        }
    ],
    "fallback": None | str   # 降级标记，如 "keyword_extraction_failed"
}
```

**sources 编号逻辑：** 先按综合分数排序选 top 8，然后按它们在 prompt 中出现的顺序编号。

### 5. 前端改动

**改动文件：`Chat.vue` + `SourceList.vue`**

**5.1 消息气泡中渲染引用链接：**
- `[1]`、`[2]` 等标记渲染为可点击角标
- 点击角标滚动到底部来源列表对应条目，或直接在新标签页打开 URL
- 正则替换 `[数字]` 为 `<a>` 标签，映射到 sources 数组

**5.2 底部来源列表（SourceList.vue 改造）：**
- 每条来源显示：编号角标 + 标题（可点击跳转）+ URL + 相关度百分比 + 来源 tag
- 来源 tag 颜色：
  - "keyword" → 蓝色 tag "关键词"
  - "vector" → 绿色 tag "语义"
  - "both" → 橙色 tag "双重"

**5.3 降级提示条：**
- `fallback` 不为空时，在来源列表上方显示黄色提示条
- 文案：「关键词提取未生效，使用了原始问题搜索，结果可能不够精准」
- 可关闭

**5.4 历史消息兼容：**
- 旧格式 sources（无 index/source 字段）按旧样式渲染
- 前端判断依据：sources 中是否有 `index` 字段

### 6. API 层改动

**改动文件：`backend/api/chat.py`**

`POST /api/chat/sessions/{session_id}/messages` 处理逻辑：
1. 保存用户消息（不变）
2. 调用改造后的 `answer_question()`
3. 保存 assistant 消息，`sources` 字段存新格式 JSON
4. 扣减积分（不变）

### 7. 路由与页面调整

**路由变更：**
- `/` → `Chat.vue`（对话页作为主页）
- `/search` → `Home.vue`（搜索页挪到这里）

**导航栏调整：**
- 保留「搜索」入口（图标或文字），跳转到 `/search`

**改动文件：**
- `frontend/src/router/index.js` —— 路由规则调整
- `frontend/src/App.vue` 或导航组件 —— 链接更新

---

## 改动清单

| 层 | 文件 | 改动 |
|----|------|------|
| 后端服务 | `services/rag.py` | 新增 `extract_keywords()`、`hybrid_retrieve()`，改造 `build_rag_prompt()`、`answer_question()` |
| 后端 API | `api/chat.py` | 适配新返回格式 |
| 前端 | `views/Chat.vue` | 引用角标渲染 + 降级提示条 |
| 前端 | `components/chat/SourceList.vue` | 新来源列表样式（编号、来源 tag、日期） |
| 前端 | `router/index.js` | 路由规则调整 |
| 前端 | 导航组件 | 链接更新 |

**不动的部分：** 搜索页功能、会话管理、积分、爬虫、MeiliSearch/Qdrant 基础服务
