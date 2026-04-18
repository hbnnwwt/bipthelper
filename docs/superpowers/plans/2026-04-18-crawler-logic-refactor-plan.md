# 爬虫执行逻辑重构实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 重构 `crawl_list_page` 返回结构化结果，让调用方能区分"完成"和"停止"；同时重构前端速度计算为 per-config。

**Architecture:**
- 后端：`crawl_list_page` 返回 `CrawlResult` dataclass（含 `stopped` 标志），不再只返回 int
- 后端：调用方根据 `result.stopped` 正确写入 `status = "stopped"` 或 `"done"`
- 前端：基于 per-config 差值计算速度，删除无意义的全局 `crawlSpeed`

**Tech Stack:** FastAPI (backend), Vue3 (frontend, bundled), SQLite

---

## 文件变更总览

| 文件 | 操作 |
|------|------|
| `backend/services/crawler.py` | 修改 |
| `frontend/src/components/admin/CrawlerTab.vue` | 修改 |

---

### Task 1: `CrawlResult` dataclass 定义

**文件:**
- 修改: `backend/services/crawler.py:1-20`（imports 区域之后）

**步骤:**

- [ ] **Step 1: 在 `crawler.py` 顶部添加 dataclass 定义**

文件: `backend/services/crawler.py`，在 `USER_AGENTS` 列表之后（大约 line 29），添加：

```python
from dataclasses import dataclass

@dataclass
class CrawlResult:
    """crawl_list_page 的返回结果"""
    articles_crawled: int   # 本次爬取的文章数（含新爬和重复跳过）
    new_articles: int       # 本次新增的文章数
    pages_crawled: int      # 本次爬取的分页数
    stopped: bool           # 是否被用户主动停止
```

**验证：** `python -c "from services.crawler import CrawlResult; print(CrawlResult(0,0,0,False))"`

- [ ] **Step 2: 提交**

```bash
git add backend/services/crawler.py
git commit -m "feat: add CrawlResult dataclass for structured crawl_list_page return"
```

---

### Task 2: `crawl_list_page` 返回 `CrawlResult`

**文件:**
- 修改: `backend/services/crawler.py` — `crawl_list_page` 函数（大约 line 565）

**步骤:**

- [ ] **Step 1: 读取 crawl_list_page 函数签名和返回值**

找到当前 `def crawl_list_page(config, session) -> int:` 的位置，以及函数末尾 `return new_count` 的位置。

- [ ] **Step 2: 修改函数签名**

将:
```python
def crawl_list_page(config: CrawlConfig, session: Session) -> int:
```
改为:
```python
def crawl_list_page(config: CrawlConfig, session: Session) -> CrawlResult:
```

- [ ] **Step 3: 修改函数开头的局部变量**

在函数开头找到 `new_count = 0` 之后，添加:
```python
    stopped = False
```

- [ ] **Step 4: 修改 crawl_stop_requested break 处**

找到:
```python
        if crawl_stop_requested:
            logger.info("Crawl stopped by user")
            break
```
改为:
```python
        if crawl_stop_requested:
            logger.info("Crawl stopped by user")
            stopped = True
            break
```

- [ ] **Step 5: 修改函数末尾返回值**

找到:
```python
    logger.info(f"List page crawl complete. New articles: {new_count}, Total pages crawled: {page_count}")
    return new_count
```
改为:
```python
    logger.info(f"List page crawl complete. New articles: {new_count}, pages: {page_count}, stopped: {stopped}")
    return CrawlResult(
        articles_crawled=articles_crawled_count,
        new_articles=new_count,
        pages_crawled=page_count,
        stopped=stopped,
    )
```

- [ ] **Step 6: 验证**

Run: `cd backend && python -c "from services.crawler import crawl_list_page; import inspect; print(inspect.signature(crawl_list_page))"`
Expected: `config: CrawlConfig, session: Session) -> CrawlResult`

- [ ] **Step 7: 提交**

```bash
git add backend/services/crawler.py
git commit -m "feat: crawl_list_page returns CrawlResult instead of int

Now returns (articles_crawled, new_articles, pages_crawled, stopped)
instead of just new_count. Allows caller to distinguish completed vs stopped."
```

---

### Task 3: 更新 `_crawl_all_impl` 调用方

**文件:**
- 修改: `backend/services/crawler.py` — `_crawl_all_impl` 末尾

**步骤:**

- [ ] **Step 1: 找到 `new_count = crawl_list_page(config, session)` 调用**

在 `_crawl_all_impl` 中找到:
```python
        new_count = crawl_list_page(config, session)
        # 设置当前 config 状态为 done
        with _progress_lock:
            crawl_progress["configs"][i]["status"] = "done"
```

- [ ] **Step 2: 修改为使用 CrawlResult**

改为:
```python
        result = crawl_list_page(config, session)
        # 根据 result.stopped 决定状态
        with _progress_lock:
            crawl_progress["configs"][i]["status"] = "stopped" if result.stopped else "done"
```

- [ ] **Step 3: 验证**

`python -m py_compile backend/services/crawler.py` — 应无错误

- [ ] **Step 4: 提交**

```bash
git add backend/services/crawler.py
git commit -m "fix: use result.stopped to set correct config status in _crawl_all_impl"
```

---

### Task 4: 更新 `_crawl_configs_impl` 调用方

**文件:**
- 修改: `backend/services/crawler.py` — `_crawl_configs_impl` 末尾

**步骤:**

- [ ] **Step 1: 找到 `new_count = crawl_list_page(config, session)` 调用**

在 `_crawl_configs_impl` 中找到（逻辑与 `_crawl_all_impl` 相同）。

- [ ] **Step 2: 修改为使用 CrawlResult**

改为:
```python
        result = crawl_list_page(config, session)
        with _progress_lock:
            crawl_progress["configs"][i]["status"] = "stopped" if result.stopped else "done"
```

- [ ] **Step 3: 验证**

`python -m py_compile backend/services/crawler.py` — 应无错误

- [ ] **Step 4: 提交**

```bash
git add backend/services/crawler.py
git commit -m "fix: use result.stopped to set correct config status in _crawl_configs_impl"
```

---

### Task 5: 前端 — per-config 速度计算

**文件:**
- 修改: `frontend/src/components/admin/CrawlerTab.vue`

**步骤:**

- [ ] **Step 1: 删除全局 crawlSpeed 和相关变量**

找到并删除:
```javascript
// 速度计算：记录上次状态用于计算爬取速度
let lastArticlesCrawled = 0
let lastProgressTime = Date.now()
```

以及整个:
```javascript
const crawlSpeed = computed(() => {
  const now = Date.now()
  const timeDiff = (now - lastProgressTime) / 1000 // 秒
  if (timeDiff < 1) return 0
  const articlesDiff = crawlProgress.value.articles_crawled - lastArticlesCrawled
  if (articlesDiff < 0) {
    // 配置切换了，重置计数
    lastArticlesCrawled = crawlProgress.value.articles_crawled
    lastProgressTime = now
    return 0
  }
  const speed = Math.round(articlesDiff / timeDiff * 10) / 10
  lastArticlesCrawled = crawlProgress.value.articles_crawled
  lastProgressTime = now
  return speed
})
```

- [ ] **Step 2: 在 `overallPercent` computed 之后添加 per-config 速度 computed**

在 `overallPercent` computed 之后（大约 line 294），添加:
```javascript
// 当前正在爬取配置的速度（篇/秒）
const currentConfigSpeed = computed(() => {
  const { phase, configs } = crawlProgress.value
  if (phase !== 'running' || !configs?.length) return 0
  const running = configs.find(c => c.status === 'running')
  if (!running) return 0
  const elapsed = running.elapsed_seconds || 0
  if (elapsed < 1) return 0
  const diff = running.articles_crawled - (running.articles_crawled_at_start || 0)
  if (diff <= 0) return 0
  return Math.round(diff / elapsed * 10) / 10
})
```

- [ ] **Step 3: 在模板中显示当前配置速度**

在 `crawl-overall-progress` 的整体进度条旁边添加速度显示:

找到:
```html
<div class="overall-label">
  整体进度 · {{ crawlProgress.config_index }}/{{ crawlProgress.total_configs }} 个配置
</div>
```
在这行后面添加:
```html
<span v-if="currentConfigSpeed > 0" class="speed-label">
  · {{ currentConfigSpeed }} 篇/秒
</span>
```

以及添加 CSS:
```css
.speed-label {
  font-size: 0.75rem;
  color: var(--color-text-muted);
  margin-left: 0.5rem;
}
```

- [ ] **Step 4: 验证**

Build 确认无语法错误:
`cd frontend && npm run build`

- [ ] **Step 5: 提交**

```bash
git add frontend/src/components/admin/CrawlerTab.vue
git commit -m "fix: remove global crawlSpeed, use per-config speed from elapsed_seconds"
```

---

### Task 6: 端到端验证

**步骤:**

- [ ] **Step 1: 启动后端**

`cd backend && python -m uvicorn main:app --reload`

- [ ] **Step 2: 触发爬取，观察状态变化**

在管理页面触发爬取：
- 观察"整体进度"正确显示
- 观察停止时状态是否正确变为"stopped"而非"done"

- [ ] **Step 3: 提交**

```bash
git commit -m "test: verify crawl result status update E2E"
```

---

## 自检清单

- [ ] Task 1: `CrawlResult` dataclass 定义正确
- [ ] Task 2: `crawl_list_page` 返回 `CrawlResult`，所有返回路径都返回该类型
- [ ] Task 3: `_crawl_all_impl` 使用 `result.stopped` 设置状态
- [ ] Task 4: `_crawl_configs_impl` 使用 `result.stopped` 设置状态
- [ ] Task 5: 前端删除全局 `crawlSpeed`，使用 per-config 速度
- [ ] 端到端：停止时配置状态变为"stopped"
- [ ] Spec 覆盖完整：无遗漏需求
