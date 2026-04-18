# 爬虫配置页面优化实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 解决爬虫配置页面两大痛点——进度看不清、列表太长找不到配置；同时清理无认证的安全隐患。

**Architecture:**
- 后端：删除 `crawl_config.py`，合并到 `admin.py`；扩展 `crawl_progress` 结构增加逐配置明细
- 前端：配置列表三级过滤 + 进度展示改为读 `configs` 字段

**Tech Stack:** FastAPI (backend), Vue3 (frontend, bundled), SQLite

---

## 文件变更总览

| 文件 | 操作 |
|------|------|
| `backend/api/crawl_config.py` | 删除 |
| `backend/main.py` | 删除 `include_router(crawl_config.router)` |
| `backend/services/crawler.py` | 修改 `crawl_progress` 初始化/重置、增加 `configs` 字段、更新逻辑 |
| `assets/frontend/assets/Admin-_jmAQ1DG.js` | 三级过滤 + 进度展示改为读 `configs` |

---

### Task 1: 删除无认证的 crawl_config.py

**文件:**
- 删除: `backend/api/crawl_config.py`
- 修改: `backend/main.py:83-89`（删除 `include_router(crawl_config.router...` 行）

**步骤:**

- [ ] **Step 1: 确认 frontend 未使用 `/api/crawl-configs`**

Run: `grep -o '/api/crawl-configs' assets/frontend/assets/Admin-_jmAQ1DG.js`
Expected: 无输出（已确认：frontend 只用 `/admin/configs`）

- [ ] **Step 2: 从 main.py 移除 crawl_config router**

文件: `backend/main.py:83-89`

删除这行:
```python
app.include_router(crawl_config.router, prefix="/api/crawl-configs", tags=["crawl_configs"])
```

- [ ] **Step 3: 删除 crawl_config.py**

Run: `rm backend/api/crawl_config.py`

- [ ] **Step 4: 启动服务验证无报错**

Run: `cd backend && python -c "from main import app; print('OK')"`
Expected: `OK`（无 import 错误）

- [ ] **Step 5: 提交**

```bash
git add backend/main.py backend/api/crawl_config.py
git commit -m "fix: remove unauthenticated crawl_config router

Was a security hole - anyone could read/write all crawl configs without auth.
Admin.py already has complete CRUD with proper admin authentication."
```

---

### Task 2: 扩展 crawl_progress 增加 configs 明细

**文件:**
- 修改: `backend/services/crawler.py:120-130`（`crawl_progress` 初始化）
- 修改: `backend/services/crawler.py:166-176`（`reset_crawl_state`）
- 修改: `backend/services/crawler.py:748-758`（`crawl_all` 结束时）
- 修改: `backend/services/crawler.py:799-809`（`crawl_configs` 结束时）
- 修改: `backend/services/crawler.py:760-777`（`_crawl_all_impl` 配置切换时）
- 修改: `backend/services/crawler.py:998-1016`（`_crawl_configs_impl` 配置切换时）

**步骤:**

- [ ] **Step 1: 修改 crawl_progress 初始化（两处：行120和reset_crawl_state）**

文件: `backend/services/crawler.py:120-130`

将:
```python
crawl_progress = {
    "phase": "idle",
    "current_config": "",
    "current_config_id": None,
    "config_index": 0,
    "total_configs": 0,
    "page": 0,
    "total_pages": 0,
    "articles_crawled": 0,
    "articles_total": 0,
}
```

改为:
```python
crawl_progress = {
    "phase": "idle",
    "total_configs": 0,
    "configs": [],  # list of {id, name, page, total_pages, articles_crawled, articles_total, status}
    # 以下字段保留，兼容旧前端
    "current_config": "",
    "current_config_id": None,
    "config_index": 0,
    "page": 0,
    "total_pages": 0,
    "articles_crawled": 0,
    "articles_total": 0,
}
```

同步修改 `reset_crawl_state` 中重置的 dict 格式（行166-176），以及 `crawl_all` 和 `crawl_configs` 结束时重置的 dict 格式（行748-758 和 799-809）。

- [ ] **Step 2: 修改 _crawl_all_impl，在配置切换时初始化 configs 条目**

文件: `backend/services/crawler.py:763-777`

在循环开始前（`for i, config in enumerate(configs):` 之前）初始化 `configs` 列表:
```python
crawl_progress["total_configs"] = total
crawl_progress["configs"] = [
    {
        "id": c.id,
        "name": c.name,
        "page": 0,
        "total_pages": 0,
        "articles_crawled": 0,
        "articles_total": 0,
        "status": "pending",
    }
    for c in configs
]
```

在进入每个配置爬取时（循环内第一行）更新状态:
```python
crawl_progress["phase"] = "running"
crawl_progress["config_index"] = i + 1
crawl_progress["current_config"] = config.name
crawl_progress["current_config_id"] = config.id
# 更新当前配置条目的状态
crawl_progress["configs"][i]["status"] = "running"
```

在同一位置也更新全局 page/articles 重置（已有），但新增：当配置完成爬取时（循环末尾），将状态改为 `"done"`:
```python
# 循环末尾，在 new_count = crawl_list_page(config, session) 之后
crawl_progress["configs"][i]["status"] = "done"
```

- [ ] **Step 3: 修改 _crawl_configs_impl，同样增加 configs 初始化和状态更新**

文件: `backend/services/crawler.py:998-1016`

逻辑与 `_crawl_all_impl` 完全相同，确保配置切换时 configs[i] 状态同步更新。

- [ ] **Step 4: 在爬取过程中更新 page/articles**

文件: `backend/services/crawler.py:612-614`（crawl_list_page 中已有）

在 `crawl_progress["page"] = page_count` 等已有行之后，新增:
```python
# 更新当前配置的进度
config_idx = crawl_progress["config_index"] - 1
if 0 <= config_idx < len(crawl_progress["configs"]):
    crawl_progress["configs"][config_idx]["page"] = page_count
    crawl_progress["configs"][config_idx]["total_pages"] = crawl_progress["total_pages"]
    crawl_progress["configs"][config_idx]["articles_crawled"] = articles_crawled_count
    crawl_progress["configs"][config_idx]["articles_total"] = total_articles
```

同样在重试成功更新 total_pages/articles_total 处（行683-684）也追加对 configs 的更新。

- [ ] **Step 5: 验证**

Run: `cd backend && python -c "from services.crawler import crawl_progress; print(crawl_progress.keys()); print(len(crawl_progress['configs']))"`
Expected: 打印 dict_keys 不含错误，且 configs 长度为 0

- [ ] **Step 6: 提交**

```bash
git add backend/services/crawler.py
git commit -m "feat: extend crawl_progress with per-config明细

Adds 'configs' list to crawl_progress: each entry tracks id, name,
page, total_pages, articles_crawled, articles_total, status.
Frontend can now display per-config progress bars instead of
guessing from current_config_id."
```

---

### Task 3: 前端三级过滤

**文件:**
- 修改: `assets/frontend/assets/Admin-_jmAQ1DG.js` — `CrawlerTab` 组件

**步骤:**

- [ ] **Step 1: 确认过滤相关代码位置**

在 Admin-_jmAQ1DG.js 中搜索 `class:"config-list"` 附近，找到配置列表渲染部分（Ce 类名变量）。

- [ ] **Step 2: 增加三个 filter state**

在 `CrawlerTab` 的 `setup` 中（`const T=H` 那行之后）增加:
```javascript
const filterSearch = c("")
const filterParent = c("")
const filterSub = c("")
```

- [ ] **Step 3: 增加 computed 提取过滤选项**

在已有 `I` (overall progress) computed 之后增加:
```javascript
const parentOptions = ft(() => [...new Set(_.value.map(n => n.parent_category).filter(Boolean))])
const subOptions = ft(() => {
  if (!filterParent.value) return [...new Set(_.value.map(n => n.sub_category).filter(Boolean))]
  return [...new Set(_.value.filter(n => n.parent_category === filterParent.value).map(n => n.sub_category).filter(Boolean))]
})
const filteredConfigs = ft(() => {
  let list = _.value
  if (filterSearch.value) list = list.filter(n => n.name.includes(filterSearch.value))
  if (filterParent.value) list = list.filter(n => n.parent_category === filterParent.value)
  if (filterSub.value) list = list.filter(n => n.sub_category === filterSub.value)
  return list
})
```

- [ ] **Step 4: 在配置表格上方插入过滤栏**

找到 `class:"config-list-header"` 所在 div，在其之前插入:
```html
<div class="config-filters">
  <input v-model="filterSearch" type="search" placeholder="搜索配置名称..." class="filter-input" />
  <select v-model="filterParent" class="filter-select">
    <option value="">全部大类</option>
    <option v-for="p in parentOptions" :key="p" :value="p">{{p}}</option>
  </select>
  <select v-model="filterSub" class="filter-select" :disabled="!filterParent">
    <option value="">全部分类</option>
    <option v-for="s in subOptions" :key="s" :value="s">{{s}}</option>
  </select>
  <span class="filter-count">{{filteredConfigs.length}} / {{_.value.length}}</span>
</div>
```

- [ ] **Step 5: 将列表渲染中的 `_.value` 替换为 `filteredConfigs`**

找到 `N(_.value, l=>` 这段（配置表格 tbody 渲染），改为 `N(filteredConfigs, l=>`。

- [ ] **Step 6: 防抖搜索**

找到 `class:"filter-input"` 的 input，添加 `@input` 或使用 `v-model` 的 `lazy` 修饰器：
```html
<input v-model.lazy="filterSearch" ... />
```
（300ms 防抖可通过 `watch(filterSearch, ot => setTimeout(() => filterSearch.value = ot, 300))` 实现，或直接用 `v-model.lazy`）

- [ ] **Step 7: 验证本地运行**

启动前端 dev server，确认配置列表过滤正常运作。

- [ ] **Step 8: 提交**

```bash
git add assets/frontend/assets/Admin-_jmAQ1DG.js
git commit -m "feat(crawler): add 3-level filter to config list

Search by name + filter by parent_category + filter by sub_category.
Filter count shown as 'X / Y'. Filters run client-side on already
loaded configs."
```

---

### Task 4: 前端进度展示改为逐配置明细

**文件:**
- 修改: `assets/frontend/assets/Admin-_jmAQ1DG.js` — `CrawlerTab` 组件

**步骤:**

- [ ] **Step 1: 确认当前进度条渲染逻辑**

在 Admin-_jmAQ1DG.js 中找到 `j(l.id)` 函数（单配置进度百分比）和 `I.value` computed（整体进度）。

当前 `j(id)` 的逻辑是：
```javascript
function j(n) {
  const {phase, current_config_id, articles_crawled, articles_total, total_pages, page} = C.value
  return e !== "running" || l !== n ? 0 : ...
}
```

即通过 `current_config_id === l.id` 来判断该行是否在爬取中。

- [ ] **Step 2: 修改 j 函数从 configs[i] 读取进度**

将函数改为直接从 `C.value.configs` 中查找:
```javascript
function j(n) {
  const cfg = C.value.configs?.find(c => c.id === n)
  if (!cfg) return 0
  if (cfg.status === "done") return 100
  if (cfg.status === "running") {
    if (cfg.articles_total > 0) return Math.round(cfg.articles_crawled / cfg.articles_total * 100)
    if (cfg.total_pages > 0) return Math.round(cfg.page / cfg.total_pages * 100)
    return 5 // 开始但未获取到总数，显示 5% 而非 0
  }
  return 0
}
```

同时更新行内状态显示（`C.value.phase==="running"&&C.value.current_config_id===l.id`）改为 `C.value.configs?.find(c=>c.id===l.id)?.status === "running"`。

- [ ] **Step 3: 将 I (overall progress) 改为从 configs 计算**

当前 `I` computed（行数较大）是计算整体进度百分比，改为从 configs 列表计算:
```javascript
const I = ft(() => {
  const {phase, configs} = C.value
  if (phase !== "running" || !configs?.length) return 0
  const doneCount = configs.filter(c => c.status === "done").length
  const runningIdx = configs.findIndex(c => c.status === "running")
  if (runningIdx < 0) return Math.round(doneCount / configs.length * 100)
  const running = configs[runningIdx]
  const doneFrac = doneCount / configs.length
  const runningFrac = running.articles_total > 0
    ? running.articles_crawled / running.articles_total / configs.length
    : running.total_pages > 0
    ? running.page / running.total_pages / configs.length
    : 0
  return Math.round((doneFrac + runningFrac) * 100)
})
```

- [ ] **Step 4: 验证**

确认整体进度条和各行进度条均正确显示。

- [ ] **Step 5: 提交**

```bash
git add assets/frontend/assets/Admin-_jmAQ1DG.js
git commit -m "feat(crawler): read per-config progress from configs field

Progress bars now read directly from crawl_progress.configs[i]
instead of inferring from current_config_id. Each config shows
its own page count, article count, and status (pending/running/done)."
```

---

### Task 5: 端到端测试

**步骤:**

- [ ] **Step 1: 启动后端**

Run: `cd backend && python -m uvicorn main:app --reload`

- [ ] **Step 2: 测试 API 正常**

访问 `GET /api/admin/configs` 确认返回配置列表（需带 admin token）。

- [ ] **Step 3: 测试进度 API**

访问 `GET /api/admin/crawl/progress` 确认返回结构包含 `configs` 字段。

- [ ] **Step 4: 触发一次爬取，观察进度页面**

手动触发爬取，观察前端：
- 整体进度条是否正确
- 每个配置的行进度条是否显示
- 配置列表过滤是否正常工作

- [ ] **Step 5: 提交**

```bash
git commit -m "test: verify crawler config page optimization E2E

- crawl_config.py removed (no more unauthenticated access)
- crawl_progress.configs populated correctly
- config list filter working
- per-config progress bars displaying correctly"
```

---

## 自检清单

- [ ] Task 1: `crawl_config.py` 删除后启动无报错
- [ ] Task 2: `crawl_progress['configs']` 结构正确，有 `id/name/page/total_pages/articles_crawled/articles_total/status`
- [ ] Task 3: 三级过滤在本地执行，无需重新请求
- [ ] Task 4: 每行进度条从 `configs[i]` 读取，无需 `current_config_id` 匹配
- [ ] Task 5: 端到端测试通过
- [ ] 旧字段（`current_config_id` 等）保留，兼容旧前端（如有）
- [ ] Spec 覆盖完整：无遗漏需求
