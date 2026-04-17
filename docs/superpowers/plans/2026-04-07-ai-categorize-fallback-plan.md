# AI 分类降级与人工复核队列实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 给 Document 模型增加 `ai_status`/`ai_suggested_categories`/`ai_reviewed_at` 字段；将分类输入从"标题+正文"简化为"仅标题"；爬虫失败时静默降级改为记录状态并提供人工复核队列。

**Architecture:**
- Document 模型新增 3 字段，`crawl_article` 中同步调用 `categorize_article(title)` 并根据结果更新 `ai_status`
- `categorize_article` 签名从 `(title, content)` 简化为 `title`，Prompt 只送标题
- Admin API 新增 3 个端点；`list_documents` 增加 `ai_status` 过滤和字段输出
- Admin.vue DocsTab 扩展：状态筛选、badge、采纳/修改按钮

**Tech Stack:** FastAPI + SQLModel, Vue 3 (Composition API), SQLite

---

## File Map

```
backend/models/document.py          — 新增 3 字段
backend/services/ai/categorize.py  — 签名变更 + Prompt 简化
backend/services/crawler.py        — crawl_article 调用处更新
backend/api/admin.py               — API 扩展
frontend/src/views/Admin.vue       — UI 扩展
```

---

## Task 1: Document 模型新增字段

**Files:**
- Modify: `backend/models/document.py`

- [ ] **Step 1: 添加 ai_status 等字段**

```python
from sqlmodel import SQLModel, Field
from typing import Optional
from datetime import datetime, timezone
import uuid

def _now() -> str:
    return datetime.now(timezone.utc).isoformat()

class Document(SQLModel, table=True):
    __tablename__ = "documents"

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    url: str = Field(unique=True, index=True)
    title: str
    content: str
    category: Optional[str] = Field(default=None, index=True)
    department: Optional[str] = Field(default=None, index=True)
    publish_date: Optional[str] = Field(default=None)
    created_at: str = Field(default_factory=_now)
    updated_at: str = Field(default_factory=_now)
    content_hash: Optional[str] = Field(default=None, index=True)

    # === 新增字段 ===
    ai_status: str = Field(default="pending")            # pending / success / failed / manual
    ai_suggested_categories: str = Field(default="")      # LLM 返回的候选分类，逗号分隔
    ai_reviewed_at: str = Field(default="")              # 人工审核时间，ISO 格式
```

- [ ] **Step 2: 确认迁移**

> SQLite 不支持 ALTER TABLE 加 NOT NULL 字段，新字段有 default 值所以现有数据库无需迁移。确认 `backend/database.py` 中 `create_db_and_tables` 使用 `SQLModel.metadata.create_all()`，会自动处理新字段。

- [ ] **Step 3: 提交**

```bash
git add backend/models/document.py
git commit -m "feat: add ai_status, ai_suggested_categories, ai_reviewed_at to Document model"
```

---

## Task 2: categorize_article 签名简化（移除 content 参数）

**Files:**
- Modify: `backend/services/ai/categorize.py:8-15`

- [ ] **Step 1: 更新 Prompt 模板和函数签名**

```python
# 文件：backend/services/ai/categorize.py

DEFAULT_PROMPT_TEMPLATE = """你是一个学校信息分类专家。根据以下文章标题，判断它属于哪个分类。

可选分类：{categories}
标题：{title}

请返回JSON格式，只包含 categories 数组，不要其他内容。
格式：{{"categories": ["分类1", "分类2"]}}"""

def categorize_article(title: str) -> list[str]:
    """
    使用 LLM 对文章标题进行分类，返回分类标签列表。
    如果没有配置 AI 场景，返回空列表。
    """
    scene = get_active_scene()
    if not scene:
        return []

    try:
        provider_config = get_provider_config(scene.provider_id)
        if not provider_config or not provider_config.get("api_key"):
            logger.warning(f"Provider {scene.provider_id} not configured for categorization")
            return []

        # 构建 prompt（只送标题，不送正文）
        categories = scene.default_categories or DEFAULT_CATEGORIES
        prompt = scene.prompt_template or DEFAULT_PROMPT_TEMPLATE

        user_content = prompt.format(
            categories=categories,
            title=title or "",
        )

        messages = [{"role": "user", "content": user_content}]
        model = scene.model or None

        result = call_llm(scene.provider_id, messages, model=model)

        # 解析 JSON 返回
        parsed = _parse_json_response(result)
        if parsed:
            logger.info(f"AI categorized article '{title[:30]}' as: {parsed}")

        return parsed

    except Exception as e:
        logger.error(f"AI categorization failed for '{title[:30]}': {e}")
        return []
```

> `content` 参数从函数签名和调用处全部移除。`_parse_json_response` 和 `get_active_scene` 不变，复用现有代码。

- [ ] **Step 2: 提交**

```bash
git add backend/services/ai/categorize.py
git commit -m "feat: simplify categorize_article to title-only input"
```

---

## Task 3: crawl_article 集成 ai_status 状态处理

**Files:**
- Modify: `backend/services/crawler.py:167-241`

找到现有 `crawl_article` 函数中调用 `categorize_article` 的那段，替换为：

```python
# AI 智能分类（同步执行，结果写入 ai_status）
try:
    cats = categorize_article(title)  # 只传 title，不传 content
    if cats:
        doc.category = ",".join(cats)
        doc.ai_status = "success"
        doc.ai_suggested_categories = ",".join(cats)
    else:
        doc.ai_status = "failed"
        doc.ai_suggested_categories = ""
except Exception as e:
    doc.ai_status = "failed"
    doc.ai_suggested_categories = ""
    logger.warning(f"AI categorization skipped: {e}")

session.add(doc)
session.commit()
index_document(doc)
```

> 注意：`index_document(doc)` 在 `session.commit()` 之后调用，此时 `doc.category` 和 `ai_status` 均已更新，会被正确索引。

同时移除函数开头的 `from services.ai.categorize import categorize_article` 导入（如果存在），确认已存在即可。

- [ ] **Step 1: 提交**

```bash
git add backend/services/crawler.py
git commit -m "feat: integrate ai_status in crawl_article, title-only categorization"
```

---

## Task 4: admin.py API 扩展

**Files:**
- Modify: `backend/api/admin.py`

### 4a. `list_documents` 更新

在 `list_documents` 函数中：

**查询参数**新增 `ai_status: Optional[str] = None`

**count 查询**（在 keyword 过滤后）添加：
```python
if ai_status:
    count_query = count_query.where(Document.ai_status == ai_status)
```

**数据查询**同样添加过滤：
```python
if ai_status:
    query = query.where(Document.ai_status == ai_status)
```

**返回字段**新增两个字段：
```python
return {
    "docs": [
        {
            "id": d.id,
            "title": d.title,
            "url": d.url,
            "category": d.category or "",
            "ai_status": d.ai_status,
            "ai_suggested_categories": d.ai_suggested_categories or "",
            "department": d.department or "",
            "publish_date": d.publish_date or "",
            "updated_at": d.updated_at,
        }
        for d in docs
    ],
    ...
}
```

### 4b. 新增 `GET /admin/documents/pending`

```python
@router.get("/documents/pending")
def list_pending_documents(
    page: int = 1,
    page_size: int = 20,
    current_admin: User = Depends(get_current_admin),
    session: Session = Depends(get_session),
):
    """列出待复核的文档（ai_status = pending 或 failed）"""
    count_query = select(func.count()).select_from(Document).where(
        Document.ai_status.in_(["pending", "failed"])
    )
    total = session.exec(count_query).one()

    query = select(Document).where(
        Document.ai_status.in_(["pending", "failed"])
    ).order_by(Document.updated_at.desc())

    docs = session.exec(query.offset((page - 1) * page_size).limit(page_size)).all()

    return {
        "docs": [
            {
                "id": d.id,
                "title": d.title,
                "url": d.url,
                "category": d.category or "",
                "ai_status": d.ai_status,
                "ai_suggested_categories": d.ai_suggested_categories or "",
                "department": d.department or "",
                "publish_date": d.publish_date or "",
                "updated_at": d.updated_at,
            }
            for d in docs
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
    }
```

### 4c. 新增 `POST /admin/documents/{doc_id}/approve`

```python
@router.post("/documents/{doc_id}/approve")
def approve_document_category(
    doc_id: str,
    categories: Optional[str] = None,
    current_admin: User = Depends(get_current_admin),
    session: Session = Depends(get_session),
):
    """采纳 AI 建议分类（或指定的 categories）"""
    doc = session.get(Document, doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    target = categories if categories else doc.ai_suggested_categories
    if not target:
        raise HTTPException(status_code=400, detail="No suggested categories to approve")

    doc.category = target
    doc.ai_status = "success"
    doc.ai_reviewed_at = datetime.now(timezone.utc).isoformat()
    session.add(doc)
    session.commit()

    # 重新索引
    delete_document_from_index(doc_id)
    index_document(doc)

    return {"message": "Category approved", "category": target}
```

### 4d. 新增 `PUT /admin/documents/{doc_id}/category`

```python
@router.put("/documents/{doc_id}/category")
def update_document_category(
    doc_id: str,
    category: str,
    current_admin: User = Depends(get_current_admin),
    session: Session = Depends(get_session),
):
    """管理员手动指定分类"""
    if not category or not category.strip():
        raise HTTPException(status_code=400, detail="Category cannot be empty")

    doc = session.get(Document, doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    doc.category = category.strip()
    doc.ai_status = "manual"
    doc.ai_reviewed_at = datetime.now(timezone.utc).isoformat()
    session.add(doc)
    session.commit()

    # 重新索引
    delete_document_from_index(doc_id)
    index_document(doc)

    return {"message": "Category updated", "category": doc.category}
```

> 顶部导入确认已有 `from datetime import datetime, timezone`；`func` 已在文件头部 `from sqlmodel import Session, select, func` 导入；`delete_document_from_index` 和 `index_document` 已在顶部导入。

- [ ] **Step 1: 提交**

```bash
git add backend/api/admin.py
git commit -m "feat: extend admin API with ai_status filtering, pending list, approve, manual category"
```

---

## Task 5: Admin.vue DocsTab UI 扩展

**Files:**
- Modify: `frontend/src/views/Admin.vue`

### 5a. 数据新增

在 `<script setup>` 的 Documents 区段数据定义处新增：

```javascript
const docFilterAiStatus = ref('')
const editingDocId = ref(null)
const editCategoryInput = ref('')
```

### 5b. computed 新增

```javascript
const aiStatusBadge = (status) => ({
  success: 'badge-success',
  failed: 'badge-warning',
  manual: 'badge-primary',
  pending: 'badge-muted',
}[status] || 'badge-muted')
```

### 5c. loadDocs 更新

在 `loadDocs()` 函数的 params 构建处添加：

```javascript
if (docFilterAiStatus.value) params.ai_status = docFilterAiStatus.value
```

### 5d. approveCategory 和 editCategory 函数

在 `batchDeleteDocs` 后新增：

```javascript
async function approveCategory(d) {
  try {
    await api.post(`/admin/documents/${d.id}/approve`)
    success('已采纳 AI 分类')
    await loadDocs()
  } catch (e) { error(e.response?.data?.detail || '采纳失败') }
}

function editCategory(d) {
  editingDocId.value = d.id
  editCategoryInput.value = d.category || ''
}

async function confirmEditCategory() {
  if (!editingDocId.value || !editCategoryInput.value.trim()) return
  try {
    await api.put(`/admin/documents/${editingDocId.value}/category`, null, {
      params: { category: editCategoryInput.value.trim() }
    })
    success('分类已修改')
    editingDocId.value = null
    editCategoryInput.value = ''
    await loadDocs()
  } catch (e) { error(e.response?.data?.detail || '修改失败') }
}

function cancelEditCategory() {
  editingDocId.value = null
  editCategoryInput.value = ''
}
```

### 5e. 模板更新 — 筛选栏

在现有 `<div class="filter-bar">` 中的 `<select v-model="docFilterCategory">` 之后添加：

```html
<select v-model="docFilterAiStatus" @change="docPage = 1; loadDocs()" class="filter-select">
  <option value="">AI状态</option>
  <option value="pending">待复核</option>
  <option value="failed">分类失败</option>
  <option value="success">AI成功</option>
  <option value="manual">手动分类</option>
</select>
```

### 5f. 模板更新 — 分类列

将原有的：
```html
<td><span class="badge badge-muted">{{ d.category || '—' }}</span></td>
```

替换为：
```html
<td>
  <div style="display:flex; align-items:center; gap:0.35rem; flex-wrap:wrap">
    <span class="badge" :class="aiStatusBadge(d.ai_status)">{{ d.ai_status }}</span>
    <span class="category-text">{{ d.category || '—' }}</span>
  </div>
  <div v-if="d.ai_suggested_categories && d.ai_status === 'failed'"
       style="font-size:0.75rem; color:var(--color-text-muted); margin-top:2px">
    建议: {{ d.ai_suggested_categories }}
  </div>
</td>
```

### 5g. 模板更新 — 操作列

将原有的：
```html
<td><button @click="deleteDoc(d.id)" ...>删除</button></td>
```

替换为：
```html
<td style="display:flex; gap:2px; align-items:center">
  <button v-if="d.ai_status === 'failed'" @click="approveCategory(d)"
          class="btn-ghost-xs" title="采纳AI建议">采纳AI</button>
  <button @click="editCategory(d)" class="btn-ghost-xs">修改分类</button>
  <button @click="deleteDoc(d.id)" class="btn-ghost-xs btn-text-danger">删除</button>
</td>
```

### 5h. 模板更新 — 内联编辑卡片

在 `<div class="card">`（表格所在 card）的 `</table>` 之后、`<div v-if="totalDocs > docPageSize">` 之前添加：

```html
<!-- 内联分类编辑 -->
<div v-if="editingDocId" class="inline-edit-card">
  <div class="inline-edit-header">
    <span class="inline-edit-title">修改分类</span>
    <button @click="cancelEditCategory" class="btn-ghost-xs">取消</button>
  </div>
  <div class="inline-edit-body">
    <input v-model="editCategoryInput" type="text" class="input"
           placeholder="输入分类名称" @keyup.enter="confirmEditCategory" />
    <button @click="confirmEditCategory" class="btn-primary btn-sm">确认</button>
  </div>
</div>
```

### 5i. 样式新增

在 `Admin.vue` 作用域样式末尾添加：

```css
/* Inline edit */
.inline-edit-card {
  margin-top: var(--space-3);
  padding: var(--space-3);
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
}
.inline-edit-header {
  display: flex; align-items: center; justify-content: space-between;
  margin-bottom: var(--space-3);
}
.inline-edit-title { font-size: 0.875rem; font-weight: 600; }
.inline-edit-body { display: flex; gap: var(--space-2); align-items: center; }
.inline-edit-body .input { flex: 1; }
```

- [ ] **Step 1: 提交**

```bash
git add frontend/src/views/Admin.vue
git commit -m "feat: add ai_status UI to Admin docs tab — badges, approve, inline edit"
```

---

## 验证步骤

1. 启动后端，确认 Document 模型迁移成功（无报错）
2. 触发爬取（`POST /admin/crawl/trigger`），观察日志中 `AI categorization` 输出
3. 分类失败的文档在 Admin 文档列表显示 `badge-warning`（failed 态）并显示 AI 建议分类
4. 点击"采纳AI"，确认分类更新，badge 变为 `badge-success`
5. 点击"修改分类"，内联编辑出现，输入新分类，确认 badge 变为 `badge-primary`（manual 态）
6. 搜索验证更新后的分类标签在搜索结果中正确过滤

---

## 完成后

- [ ] 更新 `docs/opencode/task.md`：L7 从"待处理"改为"已完成"，L8 提升至 L7 之后
- [ ] 提交: `git add docs/opencode/task.md && git commit -m "docs: mark L7 complete in task.md"`
