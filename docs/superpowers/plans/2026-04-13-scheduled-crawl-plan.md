# 爬虫定时任务实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为每个爬虫配置添加自动定时爬取功能，支持设置每隔X小时自动增量爬取一次。

**Architecture:** 后台定时器每60秒检查所有启用的配置，距离上次爬取时间超过设置间隔则触发增量爬取。定时任务在main.py启动时后台运行，不阻塞主线程。

**Tech Stack:** Python threading + APScheduler / 内置threading + time模块

---

## 文件结构

- Modify: `backend/models/crawl_config.py` — 新增 `auto_interval_hours` 字段
- Modify: `backend/services/crawler.py` — 新增定时调度器逻辑
- Modify: `backend/api/admin.py` — PUT API 支持更新 `auto_interval_hours`
- Modify: `backend/main.py` — 启动定时调度器
- Modify: `frontend/src/components/admin/CrawlerTab.vue` — 表格新增「自动间隔」列

---

### Task 1: 数据模型添加字段

**Files:**
- Modify: `backend/models/crawl_config.py:32`

- [ ] **Step 1: 添加字段**

在 `initialized: bool = False` 后面添加：

```python
auto_interval_hours: int = 0  # 自动爬取间隔（小时），0=关闭
```

- [ ] **Step 2: 提交**

```bash
git add backend/models/crawl_config.py
git commit -m "feat(crawler): add auto_interval_hours field to CrawlConfig"
```

---

### Task 2: 定时调度器逻辑

**Files:**
- Modify: `backend/services/crawler.py`

- [ ] **Step 1: 在文件顶部添加调度器相关常量和函数**

在 `crawl_lock` 旁边添加：

```python
# 定时调度器
_scheduler_thread = None
_scheduler_running = False

def _scheduled_crawl_check():
    """定时检查是否需要触发爬取（每60秒调用一次）"""
    global crawl_running
    from sqlmodel import select
    from database import create_session

    if crawl_running:
        return  # 正在爬取中，跳过

    with create_session() as session:
        from models.crawl_config import CrawlConfig
        configs = session.exec(select(CrawlConfig).where(CrawlConfig.enabled == True)).all()
        now = datetime.now()
        for config in configs:
            if config.auto_interval_hours <= 0:
                continue  # 关闭了自动爬取
            if not config.last_crawl:
                # 从未爬取过，跳过（让用户手动触发首次全量）
                continue
            last_crawl = datetime.fromisoformat(config.last_crawl)
            hours_since = (now - last_crawl).total_seconds() / 3600
            if hours_since >= config.auto_interval_hours:
                logger.info(f"[scheduler] Triggering incremental crawl for: {config.name}")
                # 临时设置 pagination_max=1 强制增量模式
                original_max = config.pagination_max
                config.pagination_max = 1
                session.add(config)
                session.commit()
                crawl_list_page(config, session)
                # 恢复原始值
                config.pagination_max = original_max
                session.add(config)
                session.commit()

def start_scheduler():
    """启动定时调度器（后台线程）"""
    global _scheduler_thread, _scheduler_running
    if _scheduler_running:
        return
    _scheduler_running = True

    def _run():
        while _scheduler_running:
            try:
                _scheduled_crawl_check()
            except Exception as e:
                logger.error(f"[scheduler] Error in scheduled check: {e}")
            time.sleep(60)  # 每60秒检查一次

    _scheduler_thread = threading.Thread(target=_run, daemon=True)
    _scheduler_thread.start()
    logger.info("[scheduler] Started")

def stop_scheduler():
    """停止定时调度器"""
    global _scheduler_running, _scheduler_thread
    _scheduler_running = False
    if _scheduler_thread:
        _scheduler_thread.join(timeout=5)
    logger.info("[scheduler] Stopped")
```

- [ ] **Step 2: 提交**

```bash
git add backend/services/crawler.py
git commit -m "feat(crawler): add scheduler for auto crawl"
```

---

### Task 3: 启动和停止调度器

**Files:**
- Modify: `backend/main.py`

- [ ] **Step 1: 导入并启动调度器**

在 `from services.crawler import crawl_all` 后面添加 `, start_scheduler, stop_scheduler`

在 `crawl_all()` 后台线程启动的代码旁边添加调度器启动：

```python
from services.crawler import crawl_all, start_scheduler, stop_scheduler
```

在 `threading.Thread(target=crawl_all, ...).start()` 后面添加：

```python
start_scheduler()
```

- [ ] **Step 2: 在应用关闭时停止调度器（可选）**

如果需要 graceful shutdown，可以在 lifespan 或 atexit 中调用 `stop_scheduler()`。如果当前没有 shutdown 逻辑，可以跳过这一步。

- [ ] **Step 3: 提交**

```bash
git add backend/main.py
git commit -m "feat(main): start scheduler on app startup"
```

---

### Task 4: API 支持更新 auto_interval_hours

**Files:**
- Modify: `backend/api/admin.py`

- [ ] **Step 1: 在 update_config 函数参数中添加 auto_interval_hours**

在 `sub_category: Optional[str] = None` 后面添加：

```python
auto_interval_hours: Optional[int] = None,
```

- [ ] **Step 2: 在 update_config 函数处理逻辑中添加**

在 `if sub_category is not None:` 后面添加：

```python
if auto_interval_hours is not None:
    config.auto_interval_hours = auto_interval_hours
```

- [ ] **Step 3: 在 add_crawl_config 函数中添加参数**

在 `add_crawl_config` 函数定义中添加 `auto_interval_hours: int = 0` 参数。

在 `add_crawl_config` 函数内部传递给 CrawlConfig 时添加 `auto_interval_hours=auto_interval_hours`。

- [ ] **Step 4: 提交**

```bash
git add backend/api/admin.py
git commit -m "feat(api): support updating auto_interval_hours for crawl configs"
```

---

### Task 5: 前端表格新增「自动间隔」列

**Files:**
- Modify: `frontend/src/components/admin/CrawlerTab.vue`

- [ ] **Step 1: 在表格表头中添加「自动间隔」列**

在表头的 `<th scope="col">模式</th>` 后面添加：

```html
<th scope="col">自动间隔</th>
```

- [ ] **Step 2: 在表格行中添加「自动间隔」单元格**

在模式 badge 后面添加：

```html
<td class="cell-interval">
  <select
    class="interval-select"
    :value="c.auto_interval_hours || 0"
    @change="updateInterval(c.id, Number($event.target.value))"
  >
    <option value="0">关闭</option>
    <option value="4">4小时</option>
    <option value="8">8小时</option>
    <option value="12">12小时</option>
    <option value="24">24小时</option>
  </select>
</td>
```

- [ ] **Step 3: 添加 updateInterval 函数**

在 `resetConfig` 函数附近添加：

```python
async function updateInterval(configId, hours) {
  try {
    await api.put(`/admin/configs/${configId}`, null, { params: { auto_interval_hours: hours } })
    await loadConfigs()
  } catch (e) { error('更新自动间隔失败') }
}
```

- [ ] **Step 4: 添加 CSS 样式**

在 `.mode-badge` 样式后面添加：

```css
/* ── Interval select ── */
.cell-interval {
  min-width: 90px;
}
.interval-select {
  font-size: 0.75rem;
  padding: 0.2rem 0.4rem;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  background: var(--color-bg);
  color: var(--color-text);
  cursor: pointer;
}
.interval-select:hover {
  border-color: var(--color-primary);
}
```

- [ ] **Step 5: 提交**

```bash
git add frontend/src/components/admin/CrawlerTab.vue
git commit -m "feat(frontend): add auto interval column to crawler config table"
```

---

## 自查清单

- [ ] `auto_interval_hours` 字段已添加到 CrawlConfig 模型
- [ ] 定时调度器每60秒检查所有配置
- [ ] 定时任务只触发增量爬取（pagination_max=1）
- [ ] `auto_interval_hours` 可通过 PUT API 更新
- [ ] 前端表格显示自动间隔并可切换
- [ ] 调度器在 main.py 启动时运行
- [ ] 所有改动已提交
