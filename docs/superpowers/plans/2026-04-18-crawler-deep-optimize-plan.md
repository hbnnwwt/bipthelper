# 爬虫深度优化实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 代码重构（拆解过长函数、消除重复）+ per-domain 限速提升爬取稳定性。

**Architecture:**
- `extract_main_content` 拆为6个小函数 + 1个主函数
- `crawl_list_page` 重试逻辑通过 `_fetch_list_page` 消除重复
- `_crawl_all_impl` 和 `_crawl_configs_impl` 合并到 `_crawl_configs_iter`
- 新增 `_enforce_domain_delay` 实现 per-domain 限速

**Tech Stack:** FastAPI, BeautifulSoup, httpx

---

## 文件变更总览

| 文件 | 操作 |
|------|------|
| `backend/services/crawler.py` | 重构 |

---

### Task 1: 拆分 `extract_main_content`

**文件:**
- 修改: `backend/services/crawler.py`

**步骤:**

- [ ] **Step 1: 读取现有 `extract_main_content` 函数**

找到函数开始和结束行（大约 line 237-357）

- [ ] **Step 2: 在 `extract_main_content` 之前插入拆分的辅助函数**

按顺序添加：

```python
def _extract_title(soup) -> str:
    """从 BeautifulSoup 对象提取标题"""
    title = ""
    if soup.title:
        title = soup.title.string or ""
    h1 = soup.find("h1")
    if h1:
        title = h1.get_text(strip=True) or title
    return title

def _extract_body(soup, selector: str):
    """用备选选择器列表提取正文元素"""
    fallback_selectors = [selector, ".subArticleCon", "#content", ".content", ".article-body", "body"]
    main = None
    for sel in fallback_selectors:
        if not sel:
            continue
        main = soup.select_one(sel)
        if main and len(main.get_text(strip=True)) > 50:
            break
    if not main:
        main = soup.body
    return main

def _clean_unwanted(main):
    """移除 script/style/nav/footer/header/按钮/功能链接"""
    for tag in main.find_all(["script", "style", "nav", "footer", "header"]):
        tag.decompose()
    for tag in main.find_all(["p", "span", "div"]):
        text = tag.get_text(strip=True)
        if "浏览次数" in text or "发布单位" in text:
            tag.decompose()
    for tag in main.find_all(["button", "input"]):
        tag.decompose()
    for tag in main.find_all("a"):
        txt = tag.get_text(strip=True)
        if any(k in txt for k in ["保存", "关闭", "打印", "分享", "收藏"]):
            tag.decompose()

def _process_tables(main):
    """将表格转换为结构化文本"""
    for table in main.find_all("table"):
        try:
            rows = table.find_all("tr")
            if not rows:
                continue
            max_cols = 0
            for row in rows:
                col_count = sum(int(cell.get("colspan", 1)) for cell in row.find_all(["td", "th"]))
                max_cols = max(max_cols, col_count)
            if max_cols == 0:
                continue
            grid = []
            row_span_map = [None] * max_cols
            for row_el in rows:
                grid_row = ["" for _ in range(max_cols)]
                for col in range(max_cols):
                    if row_span_map[col]:
                        text, remaining = row_span_map[col]
                        grid_row[col] = text
                        row_span_map[col] = (text, remaining - 1) if remaining > 1 else None
                col_idx = 0
                for cell in row_el.find_all(["td", "th"]):
                    text = cell.get_text(strip=True)
                    rowspan = int(cell.get("rowspan", 1))
                    colspan = int(cell.get("colspan", 1))
                    while col_idx < max_cols and grid_row[col_idx]:
                        col_idx += 1
                    for c in range(colspan):
                        if col_idx + c < max_cols:
                            grid_row[col_idx + c] = text
                            if rowspan > 1:
                                row_span_map[col_idx + c] = (text, rowspan - 1)
                    col_idx += colspan
                grid.append(grid_row)
            lines = []
            for g_row in grid:
                cells = [t for t in g_row if t]
                if cells:
                    lines.append(" - " + "、".join(cells))
            if lines:
                table.replace_with(soup.new_string("\n".join(lines) + "\n"))
        except Exception:
            pass

def _process_lists(main):
    """列表项前加短横线"""
    for li in main.find_all("li"):
        text = li.get_text(strip=True)
        if text and not text.startswith("-") and not text.startswith("•"):
            li.replace_with(soup.new_string(f"  - {text}\n"))

def _cleanup_content(text: str) -> str:
    """清理多余空行，移除过短行"""
    text = re.sub(r"\n{3,}", "\n\n", text)
    lines = [line for line in text.split("\n") if line.strip() and len(line.strip()) > 1]
    return "\n".join(lines)
```

- [ ] **Step 3: 替换 `extract_main_content` 函数体**

将原函数体（约 120 行）替换为：

```python
def extract_main_content(html: str, selector: str = "body") -> tuple[str, str]:
    soup = BeautifulSoup(html, "html.parser")
    title = _extract_title(soup)
    main = _extract_body(soup, selector)
    if main:
        _clean_unwanted(main)
        _process_tables(main)
        _process_lists(main)
        content = _cleanup_content(main.get_text(separator="\n", strip=True))
        return title, content
    return title, soup.get_text(separator="\n", strip=True)
```

- [ ] **Step 4: 验证**

`cd backend && python -m py_compile services/crawler.py && echo "OK"`

- [ ] **Step 5: 提交**

```bash
git add backend/services/crawler.py
git commit -m "refactor: split extract_main_content into 6 helper functions

Extract _extract_title, _extract_body, _clean_unwanted, _process_tables,
_process_lists, _cleanup_content. Main function now composes them.
No behavior change."
```

---

### Task 2: 提取 `_fetch_list_page` 消除重试重复

**文件:**
- 修改: `backend/services/crawler.py`

**步骤:**

- [ ] **Step 1: 在 `crawl_article` 之前添加 `_fetch_list_page`**

在 `crawl_article` 函数定义之前添加：

```python
def _fetch_list_page(page_url: str) -> str:
    """请求列表页，返回 HTML 内容"""
    with httpx.Client(timeout=30.0, follow_redirects=True,
                      headers={"User-Agent": _random_ua()}) as client:
        response = client.get(page_url)
        response.raise_for_status()
        return response.text
```

- [ ] **Step 2: 替换 `crawl_list_page` 中的请求逻辑**

在主循环中，找到：
```python
with httpx.Client(timeout=30.0, follow_redirects=True, headers={"User-Agent": _random_ua()}) as client:
    response = client.get(page_url)
    response.raise_for_status()
    html = response.text
```
替换为：
```python
html = _fetch_list_page(page_url)
```

同样在重试路径中找到相同的 httpx 请求块，替换为：
```python
html = _fetch_list_page(page_url)
```

- [ ] **Step 3: 验证**

`cd backend && python -m py_compile services/crawler.py && echo "OK"`

- [ ] **Step 4: 提交**

```bash
git add backend/services/crawler.py
git commit -m "refactor: extract _fetch_list_page to eliminate duplicate HTTP logic

Replaces duplicated httpx.Client blocks in crawl_list_page main loop
and retry path with single _fetch_list_page() call."
```

---

### Task 3: 提取 `_crawl_configs_iter` 消除两函数重复

**文件:**
- 修改: `backend/services/crawler.py`

**步骤:**

- [ ] **Step 1: 在 `_crawl_all_impl` 之前添加 `_crawl_configs_iter`**

```python
def _crawl_configs_iter(session: Session, configs: list[CrawlConfig]):
    """共同爬取逻辑：进度初始化、逐个爬取、状态更新"""
    global crawl_progress
    total = len(configs)
    crawl_progress["total_configs"] = total
    crawl_progress["configs"] = [
        {
            "id": c.id,
            "name": c.name,
            "page": 0,
            "total_pages": 0,
            "articles_crawled": 0,
            "articles_crawled_at_start": 0,
            "articles_total": 0,
            "elapsed_seconds": 0,
            "status": "pending",
        }
        for c in configs
    ]
    for i, config in enumerate(configs):
        if crawl_stop_requested:
            with _progress_lock:
                crawl_progress["phase"] = "stopping"
                crawl_progress["configs"][i]["status"] = "stopped"
            logger.info("Crawl stopped by user (between configs)")
            break
        with _progress_lock:
            crawl_progress["phase"] = "running"
            crawl_progress["config_index"] = i + 1
            crawl_progress["current_config"] = config.name
            crawl_progress["current_config_id"] = config.id
            crawl_progress["page"] = 0
            crawl_progress["articles_crawled"] = 0
            crawl_progress["configs"][i]["status"] = "running"
            crawl_progress["configs"][i]["articles_crawled_at_start"] = crawl_progress["articles_crawled"]
        global _config_start_time
        _config_start_time = time.time()
        result = crawl_list_page(config, session)
        with _progress_lock:
            crawl_progress["configs"][i]["status"] = "stopped" if result.stopped else "done"
```

- [ ] **Step 2: 替换 `_crawl_all_impl` 函数体**

将 `_crawl_all_impl` 替换为：
```python
def _crawl_all_impl(session: Session):
    db_configs = session.exec(select(CrawlConfig).where(CrawlConfig.enabled == True)).all()
    _crawl_configs_iter(session, db_configs)
```

- [ ] **Step 3: 替换 `_crawl_configs_impl` 函数体**

将 `_crawl_configs_impl` 替换为：
```python
def _crawl_configs_impl(session: Session, config_ids: list[str]):
    db_configs = [session.get(CrawlConfig, cid) for cid in config_ids]
    db_configs = [c for c in db_configs if c is not None and c.enabled]
    _crawl_configs_iter(session, db_configs)
```

- [ ] **Step 4: 验证**

`cd backend && python -m py_compile services/crawler.py && echo "OK"`

- [ ] **Step 5: 提交**

```bash
git add backend/services/crawler.py
git commit -m "refactor: extract _crawl_configs_iter to eliminate duplicate crawl loop

_crawl_all_impl and _crawl_configs_impl now just build the config list
and delegate to _crawl_configs_iter. ~90 lines removed."
```

---

### Task 4: per-domain 限速

**文件:**
- 修改: `backend/services/crawler.py`

**步骤:**

- [ ] **Step 1: 在模块顶部添加限速相关变量**

在 `_crawl_lock` 附近添加：
```python
_domain_last_crawl: dict[str, float] = {}  # domain -> 上次爬取时间戳
DOMAIN_MIN_DELAY = 2.0  # 同一域名最小请求间隔（秒）
```

- [ ] **Step 2: 在 `_random_ua` 之后添加 `_enforce_domain_delay`**

```python
def _enforce_domain_delay(url: str):
    """确保同一域名的请求间隔至少 DOMAIN_MIN_DELAY 秒"""
    domain = urlparse(url).netloc
    now = time.time()
    if domain in _domain_last_crawl:
        elapsed = now - _domain_last_crawl[domain]
        if elapsed < DOMAIN_MIN_DELAY:
            time.sleep(DOMAIN_MIN_DELAY - elapsed)
    _domain_last_crawl[domain] = time.time()
```

- [ ] **Step 3: 在 `crawl_article` 的请求前调用**

在 `crawl_article` 中找到：
```python
time.sleep(_crawl_delay(settings.CRAWL_ARTICLE_DELAY))
with httpx.Client(timeout=30.0, follow_redirects=True, headers={"User-Agent": _random_ua()}) as client:
```
在这两行之间（在延时之后）添加：
```python
_enforce_domain_delay(url)
```

- [ ] **Step 4: 验证**

`cd backend && python -m py_compile services/crawler.py && echo "OK"`

- [ ] **Step 5: 提交**

```bash
git add backend/services/crawler.py
git commit -m "feat: add per-domain rate limiting to crawl_article

Enforce minimum 2-second delay between requests to the same domain
using _enforce_domain_delay. Prevents triggering server-side rate limits."
```

---

## 自检清单

- [ ] Task 1: `extract_main_content` 拆为7个函数，功能不变
- [ ] Task 2: `_fetch_list_page` 消除两处 httpx 请求重复
- [ ] Task 3: `_crawl_configs_iter` 消除两函数重复，`crawl_all` 和 `crawl_configs` 行为不变
- [ ] Task 4: per-domain 限速 2 秒，不改变返回结果
- [ ] 语法检查全部通过
