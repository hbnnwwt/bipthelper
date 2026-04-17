# AI 分类降级与人工复核队列

## Context

当前 `categorize_article(title, content)` 将全文发送给 LLM，token 消耗大且分类质量提升有限。学校通知的分类从标题即可判断（通知公告/规章制度/招标信息等标题本身已有明显语义）。同时，当 LLM 分类失败时系统静默吞掉错误，管理员无感知，无法复核。

本方案：
1. 分类输入从"标题 + 内容"简化为"仅标题"
2. 引入 `ai_status` 状态机跟踪分类结果
3. 提供人工复核队列，管理员可采纳 AI 建议或手动指定分类

---

## 1. 数据模型

### Document 模型变更

新增 3 个字段：

| 字段 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `ai_status` | `str` | `"pending"` | `pending` / `success` / `failed` / `manual` |
| `ai_suggested_categories` | `str` | `""` | LLM 返回的候选分类（逗号分隔），待审核时暂存 |
| `ai_reviewed_at` | `str` | `""` | 人工审核时间（ISO 格式） |

`category` 字段含义不变，始终存储"最终确认的分类"。

### ai_status 状态机

```
pending  → 爬虫刚写入，尚未调用 LLM（过渡态，实际处理在异步 hook 中完成）
success  → LLM 成功解析并返回了有效分类，已写入 category
failed   → LLM 调用异常或无法解析返回内容，category 保持 config.category 兜底
manual   → 管理员手动修改分类，覆盖了 AI 结果
```

> `pending` 态在爬虫进程中极短（异步 hook 同步完成），数据库中大多数文档最终是 `success` / `failed` / `manual` 三态之一。

---

## 2. 分类服务变更

### `services/ai/categorize.py`

**`categorize_article(title: str) -> list[str]`**

输入从 `(title, content)` 简化为仅 `title`。Prompt 模板也随之简化：

```python
DEFAULT_PROMPT_TEMPLATE = """你是一个学校信息分类专家。根据以下文章标题，判断它属于哪个分类。

可选分类：{categories}
标题：{title}

请返回JSON格式，只包含 categories 数组，不要其他内容。
格式：{{"categories": ["分类1", "分类2"]}}"""
```

调用处（爬虫 `crawl_article`）同步改为：
```python
cats = categorize_article(title)  # 不再传 content
```

### 分类结果处理

```python
def categorize_article(title: str) -> list[str]:
    # ... LLM 调用 ...
    categories = _parse_json_response(result)
    if categories:
        return categories
    # 解析失败返回空列表，caller 根据空列表判定为 failed
    return []
```

---

## 3. 爬虫集成变更

### `services/crawler.py` — `crawl_article`

```python
# 写入 DB — ai_status 初始为 pending
doc = Document(
    ...,
    category=config.category,       # 兜底分类
    ai_status="pending",
    ai_suggested_categories="",
)

# AI 分类（不阻塞）
try:
    cats = categorize_article(title)   # 仅传 title
    if cats:
        doc.category = ",".join(cats)
        doc.ai_status = "success"
        doc.ai_suggested_categories = ",".join(cats)
        index_document(doc)             # 更新索引
    else:
        doc.ai_status = "failed"
        doc.ai_suggested_categories = ""
except Exception as e:
    doc.ai_status = "failed"
    doc.ai_suggested_categories = ""
    logger.warning(f"AI categorization failed: {e}")
```

---

## 4. API 设计

### `GET /api/admin/documents`

现有接口新增 `ai_status` 和 `ai_suggested_categories` 字段：

```json
{
  "docs": [{
    "id": "...",
    "title": "...",
    "url": "...",
    "category": "通知公告",
    "ai_status": "success",
    "ai_suggested_categories": "通知公告,工作动态",
    "department": "人事处",
    "publish_date": "2026-04-01",
    "updated_at": "2026-04-07T..."
  }],
  "total": 120,
  "page": 1,
  "page_size": 20
}
```

新增查询参数：
- `?ai_status=pending|success|failed|manual` — 按 AI 分类状态过滤

### `GET /api/admin/documents/pending`

列出待复核文档（`ai_status = "pending"` 或 `"failed"`）：

```
GET /api/admin/documents/pending?page=1&page_size=20

Response: {
  "docs": [{ id, title, url, category, ai_suggested_categories, department, publish_date, updated_at }],
  "total": N,
  "page": 1,
  "page_size": 20
}
```

> `ai_status = "pending"` 的文档在爬虫同步完成后的瞬间会被更新为 `success` 或 `failed`，实际队列中主要是 `failed` 态。

### `POST /api/admin/documents/{id}/approve`

采纳 AI 建议分类：

```
POST /api/admin/documents/{id}/approve
Body: { categories: "通知公告,工作动态" }   // 可选；不传则使用 ai_suggested_categories

→ doc.category = categories 或 ai_suggested_categories
→ doc.ai_status = "success"
→ doc.ai_reviewed_at = now()
→ 重新索引
```

### `PUT /api/admin/documents/{id}/category`

管理员手动指定分类：

```
PUT /api/admin/documents/{id}/category
Body: { category: "规章制度" }

→ doc.category = input
→ doc.ai_status = "manual"
→ doc.ai_reviewed_at = now()
→ 重新索引
```

---

## 5. 前端变更

### Admin.vue — DocsTab 扩展

**新增字段输出**（列表接口已返回，无需额外请求）

**筛选栏新增筛选项**：
```html
<select v-model="docFilterAiStatus" @change="loadDocs">
  <option value="">全部分类状态</option>
  <option value="pending">待复核</option>
  <option value="failed">分类失败</option>
  <option value="success">AI成功</option>
  <option value="manual">手动分类</option>
</select>
```

**分类列改版**：
```html
<td>
  <span class="badge" :class="aiStatusBadge(d.ai_status)">{{ d.ai_status }}</span>
  <span class="category-text">{{ d.category }}</span>
  <span v-if="d.ai_suggested_categories && d.ai_status === 'failed'"
        class="suggestion">建议: {{ d.ai_suggested_categories }}</span>
</td>
```

**操作列新增**：
```html
<button v-if="d.ai_status === 'failed'"
        @click="approveCategory(d)"
        class="btn-ghost-xs">采纳AI</button>
<button @click="editCategory(d)"
        class="btn-ghost-xs">修改分类</button>
```

**内联编辑弹窗**（用现有 card 样式，不引入 modal）：
- 标题：修改分类
- 显示当前 `category` 和 `ai_suggested_categories`
- 输入框预填当前 category，可编辑
- 确认按钮调用 `PUT /admin/documents/{id}/category`
- 取消按钮关闭编辑状态

**`aiStatusBadge` helper**：
```javascript
function aiStatusBadge(status) {
  return { success: 'badge-success', failed: 'badge-warning',
           manual: 'badge-primary', pending: 'badge-muted' }[status] || 'badge-muted'
}
```

### API 调用变更

`loadDocs()` 新增 `docFilterAiStatus` 参数：
```javascript
if (docFilterAiStatus.value) params.ai_status = docFilterAiStatus.value
```

---

## 6. 错误处理

| 场景 | 行为 |
|------|------|
| LLM 超时/网络错误 | `except` 捕获，`ai_status=failed`，爬虫不中断 |
| LLM 返回无法解析 | `categorize_article` 返回空列表，`ai_status=failed` |
| 管理员采纳时文档已删除 | 返回 404，提示"文档不存在" |
| 重新索引失败 | `delete_document_from_index` + 重新 `index_document`，失败则记录 error log |

---

## 7. 文件变更清单

### 新建
- 无

### 修改
| 文件 | 变更 |
|------|------|
| `backend/models/document.py` | 新增 `ai_status`, `ai_suggested_categories`, `ai_reviewed_at` 字段 |
| `backend/services/ai/categorize.py` | `categorize_article(title)` 移除 content 参数；Prompt 简化为只送标题 |
| `backend/services/crawler.py` | `crawl_article` 中调用 `categorize_article(title)` 并处理 `ai_status` |
| `backend/api/admin.py` | `list_documents` 增加 `ai_status`/`ai_suggested_categories` 输出 + `ai_status` 查询过滤；新增 `pending` 列表接口、`approve`、`manual_category` 接口 |
| `frontend/src/views/Admin.vue` | DocsTab 增加状态筛选、badge 显示、AI 采纳按钮、内联编辑 |

---

## 8. 验证方案

1. 启动后端，确认 `/docs` 中 Document 模型有新增字段
2. 触发爬取，检查日志中 `AI categorization` 调用记录
3. 分类失败的文档在 Admin 文档列表中显示 `badge-warning`（failed 状态）
4. 点击"采纳AI"，确认分类更新并重新索引
5. 点击"修改分类"，手动输入分类，确认状态变为 `manual`
6. 搜索验证更新后的分类标签是否生效
