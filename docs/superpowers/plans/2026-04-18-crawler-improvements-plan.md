# 爬虫改进实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 对 `crawler.py` 实现四项改进：批量插入、持久化去重+内容更新检测、HTTP 429退避、连接池复用。

**Architecture:** 4个独立子项目。A/B/C/D可并行开发。Model 新建在 key.db，crawler.py 改动集中。

**Tech Stack:** FastAPI, SQLModel, BeautifulSoup, httpx, hashlib

---

## 文件结构

| 文件 | 操作 |
|------|------|
| `backend/models/document_fingerprint.py` | 新建 |
| `backend/models/__init__.py` | 修改 |
| `backend/database.py` | 修改 |
| `backend/services/crawler.py` | 修改（Task A/B/C/D） |

---

## Task 1: DocumentFingerprint 模型 + URL 归一化工具

**Files:**
- Create: `backend/models/document_fingerprint.py`
- Modify: `backend/models/__init__.py`
- Modify: `backend/database.py`

- [ ] **Step 1: 创建 `backend/models/document_fingerprint.py`**

```python
import hashlib
from sqlmodel import SQLModel, Field
from datetime import datetime, timezone

def _now() -> str:
    return datetime.now(timezone.utc).isoformat()

def _url_hash(url: str) -> str:
    """对 URL 归一化后取 SHA256 前32字符作为 hash key"""
    from urllib.parse import urlparse, parse_qs
    parsed = urlparse(url)
    # 去除 fragment，query params 排序后拼接
    query = "&".join(
        sorted(f"{k}={v}" for k, vs in parse_qs(parsed.query).items() for v in sorted(vs))
    )
    normalized = parsed._replace(fragment="", query=query).geturl()
    return hashlib.sha256(normalized.encode()).hexdigest()[:32]

class DocumentFingerprint(SQLModel, table=True):
    __tablename__ = "document_fingerprints"

    url_hash: str = Field(primary_key=True)  # SHA256(normalized_url)[:32]
    url: str = Field(index=True)
    content_hash: str = ""                    # SHA256 正文内容
    created_at: str = Field(default_factory=_now)
    updated_at: str = Field(default_factory=_now)
    doc_id: str = Field(index=True)          # 关联 Document.id
```

- [ ] **Step 2: 更新 `backend/models/__init__.py`**

在 imports 中添加：
```python
from .document_fingerprint import DocumentFingerprint, _url_hash
```

在 `__all__` 中添加 `"DocumentFingerprint", "_url_hash"`。

- [ ] **Step 3: 在 `backend/database.py` 添加 DocumentFingerprint**

在 `_session_binds` dict 中添加：
```python
DocumentFingerprint: key_engine,
```

在 `create_db_and_tables()` 的 `key_tables` 列表中添加：
```python
DocumentFingerprint.__table__,
```

- [ ] **Step 4: 验证模型加载**

Run: `cd backend && python -c "from models.document_fingerprint import DocumentFingerprint, _url_hash; print(_url_hash('https://example.com/page?id=1')); print('OK')"`
Expected: 32-char hash string + "OK"

- [ ] **Step 5: 提交**

```bash
git add backend/models/document_fingerprint.py backend/models/__init__.py backend/database.py
git commit -m "feat(crawler): add DocumentFingerprint model and URL normalization"
```

---

## Task 2: 批量插入

**Files:**
- Modify: `backend/services/crawler.py`（`crawl_list_page` 函数内部）

- [ ] **Step 1: 添加 BATCH_SIZE 常量和 `_flush_article_batch` 辅助函数**

在 `_enforce_domain_delay` 函数之后（约 line 145）添加：

```python
ARTICLE_BATCH_SIZE = 50  # 每批提交的文章数

def _flush_article_batch(session: Session, batch: list[tuple], articles_crawled_count: int) -> tuple[int, int]:
    """
    批量提交一批 Document，记录新增/更新数量。
    batch: list of (doc: Document, is_new: bool) tuples
    返回 (new_count, articles_crawled_count_delta)
    """
    new_count_delta = 0
    for doc, is_new in batch:
        session.add(doc)
        if is_new:
            new_count_delta += 1
    session.commit()
    return new_count_delta, len(batch)
```

- [ ] **Step 2: 修改 `crawl_list_page` 主循环使用批量插入**

在 `crawl_list_page` 函数开头（约 line 601 附近），找到 `new_count = 0` 后添加：

```python
    article_batch = []  # [(doc, is_new), ...] 待批量提交
    articles_crawled_count = 0
```

在主循环爬取文章处（约 line 660-671），将：

```python
            for article_url in article_links:
                if crawl_stop_requested:
                    ...
                if not is_incremental or article_url not in visited_articles:
                    if crawl_article(article_url, config, session):
                        new_count += 1
                    articles_crawled_count += 1
                    _update_progress(articles_crawled=articles_crawled_count)
                    visited_articles.add(article_url)
```

替换为使用 `crawl_article` 内部逻辑提取 doc + is_new 信息的版本。由于 `crawl_article` 目前返回 `bool`，需要重构：

**注意：Task 2 依赖 Task 4（D 连接池）。先做 Task 4（将 `crawl_article` 改为 `crawl_article_with_client`），再回来做这一步。**

- [ ] **Step 2 替代方案（推荐 — Task 2 和 Task 4 解耦）：**

不改 `crawl_article` 返回值，而是在 `crawl_list_page` 中直接内联批量插入逻辑：

在主循环中，将 `if crawl_article(...)` 块替换为直接构建 Document 并加入 batch：

```python
            for article_url in article_links:
                if crawl_stop_requested:
                    # flush remaining batch before stopping
                    if article_batch:
                        batch_new, batch_crawled = _flush_article_batch(session, article_batch, articles_crawled_count)
                        new_count += batch_new
                        articles_crawled_count += batch_crawled
                        article_batch = []
                    stopped = True
                    break
                if not is_incremental or article_url not in visited_articles:
                    doc, is_new = _build_article_doc(article_url, config, session)
                    if doc:
                        article_batch.append((doc, is_new))
                        articles_crawled_count += 1
                        _update_progress(articles_crawled=articles_crawled_count)
                        visited_articles.add(article_url)
                        if len(article_batch) >= ARTICLE_BATCH_SIZE:
                            batch_new, _ = _flush_article_batch(session, article_batch, articles_crawled_count)
                            new_count += batch_new
                            article_batch = []
```

在循环结束后、配置 commit 之前添加 flush：
```python
    # flush remaining batch
    if article_batch:
        batch_new, _ = _flush_article_batch(session, article_batch, articles_crawled_count)
        new_count += batch_new
        article_batch = []
```

**等一下！** 这需要 `_build_article_doc` 函数来构建 Document 而不 commit。让我先在 Step 3 给出这个函数的实现。

- [ ] **Step 3: 添加 `_build_article_doc` 辅助函数**

在 `_flush_article_batch` 之后添加：

```python
def _build_article_doc(url: str, config: CrawlConfig, session: Session) -> tuple[Document | None, bool]:
    """
    构建 Article Document 对象（不 commit，不建向量）。
    返回 (doc, is_new)。若 URL 已存在且内容无变化返回 (None, False)。
    """
    from models.document_fingerprint import _url_hash, DocumentFingerprint
    from sqlmodel import select
    from services.ai.embedding import embed_document
    import hashlib

    try:
        time.sleep(_crawl_delay(settings.CRAWL_ARTICLE_DELAY))
        _enforce_domain_delay(url)

        with httpx.Client(timeout=30.0, follow_redirects=True,
                         headers={"User-Agent": _random_ua()}) as client:
            response = client.get(url)
            response.raise_for_status()
            html = response.text

        content_hash = hashlib.sha256(html.encode()).hexdigest()

        # 检查 fingerprint（去重 + 更新检测）
        url_h = _url_hash(url)
        fp = session.exec(
            select(DocumentFingerprint).where(DocumentFingerprint.url_hash == url_h)
        ).one_or_none()

        if fp and fp.content_hash == content_hash:
            return None, False  # 内容无变化，跳过

        # 保存原始 HTML
        url_hash_md5 = hashlib.md5(url.encode()).hexdigest()
        domain = urlparse(url).netloc.replace(":", "_")
        date_dir = datetime.now().strftime("%Y-%m-%d")
        html_subdir = HTMLS_DIR / date_dir / domain
        html_subdir.mkdir(parents=True, exist_ok=True)
        html_file = html_subdir / f"{url_hash_md5}.html"
        html_file.write_text(html, encoding="utf-8")

        meta = extract_article_metadata(html, url)
        title, content = extract_main_content(html, config.selector)
        now = datetime.now().isoformat()

        doc = session.exec(select(Document).where(Document.url == url)).first()
        is_new = doc is None

        if doc:
            doc.title = title
            doc.content = content
            doc.content_hash = content_hash
            doc.updated_at = now
            doc.ai_status = "success"
            doc.category = config.sub_category or config.category
            doc.parent_category = config.parent_category
            doc.sub_category = config.sub_category
            if meta.get("department"):
                doc.department = meta["department"]
            if meta.get("publish_date"):
                doc.publish_date = meta["publish_date"]
        else:
            doc = Document(
                url=url,
                title=title,
                content=content,
                category=config.sub_category or config.category,
                parent_category=config.parent_category,
                sub_category=config.sub_category,
                department=meta.get("department"),
                publish_date=meta.get("publish_date"),
                ai_status="success",
                content_hash=content_hash,
                created_at=now,
                updated_at=now,
            )

        # 更新或新建 fingerprint
        if fp:
            fp.content_hash = content_hash
            fp.updated_at = now
            fp.doc_id = doc.id
            session.add(fp)
        else:
            session.add(DocumentFingerprint(
                url_hash=url_h, url=url, content_hash=content_hash,
                doc_id=doc.id, created_at=now, updated_at=now
            ))

        return doc, is_new

    except Exception as e:
        logger.error(f"[_build_article_doc] Failed: {url}: {e}")
        return None, False
```

- [ ] **Step 4: 重试循环也使用批量插入**

将重试循环（约 line 703-720）中相同的文章爬取逻辑替换为同样的 `_build_article_doc` + batch 逻辑。

- [ ] **Step 5: 验证语法**

Run: `cd backend && python -m py_compile services/crawler.py && echo "OK"`
Expected: "OK"

- [ ] **Step 6: 提交**

```bash
git add backend/services/crawler.py
git commit -m "feat(crawler): batch article inserts to reduce DB commits"
```

---

## Task 3: HTTP 429 退避重试

**Files:**
- Modify: `backend/services/crawler.py`

- [ ] **Step 1: 添加 `retry_with_backoff` 装饰器/函数**

在 `crawler.py` 顶部 `import` 区域之后（约 line 30），添加：

```python
import random

DEFAULT_MAX_RETRIES = 3
DEFAULT_BASE_DELAY = 2.0  # 秒

def _retryable_request(func):
    """包装 HTTP 请求函数，支持 429/5xx 退避重试"""
    def wrapper(*args, **kwargs):
        for attempt in range(DEFAULT_MAX_RETRIES):
            try:
                return func(*args, **kwargs)
            except httpx.HTTPStatusError as e:
                status = e.response.status_code
                if status == 429 and attempt < DEFAULT_MAX_RETRIES - 1:
                    retry_after = e.response.headers.get("Retry-After")
                    if retry_after:
                        wait = float(retry_after)
                    else:
                        wait = DEFAULT_BASE_DELAY * (2 ** attempt) + random.uniform(0, 1)
                    logger.warning(f"[crawl] 429 received, retrying in {wait:.1f}s (attempt {attempt+1}/{DEFAULT_MAX_RETRIES})")
                    time.sleep(wait)
                    continue
                if status >= 500 and attempt < DEFAULT_MAX_RETRIES - 1:
                    wait = DEFAULT_BASE_DELAY * (2 ** attempt)
                    logger.warning(f"[crawl] {status} server error, retrying in {wait:.1f}s (attempt {attempt+1}/{DEFAULT_MAX_RETRIES})")
                    time.sleep(wait)
                    continue
                raise
            except httpx.RequestError as e:
                if attempt < DEFAULT_MAX_RETRIES - 1:
                    wait = DEFAULT_BASE_DELAY * (2 ** attempt)
                    logger.warning(f"[crawl] Request error: {e}, retrying in {wait:.1f}s")
                    time.sleep(wait)
                    continue
                raise
        return func(*args, **kwargs)  # 最后一搏
    return wrapper
```

- [ ] **Step 2: 将 `_fetch_list_page` 改为使用 `_retryable_request`**

找到当前 `_fetch_list_page`（约 line 478），替换为：

```python
@_retryable_request
def _fetch_list_page(page_url: str) -> str:
    """请求列表页，返回 HTML 内容"""
    with httpx.Client(timeout=30.0, follow_redirects=True,
                      headers={"User-Agent": _random_ua()}) as client:
        response = client.get(page_url)
        response.raise_for_status()
        return response.text
```

- [ ] **Step 3: 验证语法**

Run: `cd backend && python -m py_compile services/crawler.py && echo "OK"`

- [ ] **Step 4: 提交**

```bash
git add backend/services/crawler.py
git commit -m "feat(crawler): add HTTP 429/5xx backoff retry for list page requests"
```

---

## Task 4: 连接池复用

**Files:**
- Modify: `backend/services/crawler.py`

- [ ] **Step 1: 在 `crawl_list_page` 入口创建共享 client**

找到 `crawl_list_page` 入口（`def crawl_list_page(config: CrawlConfig, session: Session)` 约 line 595），在函数体开头添加：

```python
    # 共享 HTTP client（连接池复用）
    with httpx.Client(timeout=30.0, follow_redirects=True,
                      headers={"User-Agent": _random_ua()}) as http_client:
        return _crawl_list_page_impl(http_client, config, session)

def _crawl_list_page_impl(http_client, config: CrawlConfig, session: Session) -> CrawlResult:
    """crawl_list_page 内部实现，接收共享 http_client"""
```

将原 `crawl_list_page` 函数体移动到 `_crawl_list_page_impl`，并更新其中所有 `_fetch_list_page(page_url)` 调用为 `_fetch_list_page(http_client, page_url)`。

- [ ] **Step 2: 修改 `_fetch_list_page` 签名**

将 `_fetch_list_page` 改为接收 client：

```python
@_retryable_request
def _fetch_list_page(http_client, page_url: str) -> str:
    """请求列表页，返回 HTML 内容（复用连接池 client）"""
    response = http_client.get(page_url)
    response.raise_for_status()
    return response.text
```

同时更新所有调用处（包括重试循环中）。

- [ ] **Step 3: 修改 `_build_article_doc` 使用传入的 http_client**

由于 `_build_article_doc` 是在 Task 2 中新建的，直接让它接收 `http_client` 参数。更新 `_crawl_list_page_impl` 中对 `_build_article_doc` 的调用传入 `http_client`。

- [ ] **Step 4: 验证语法**

Run: `cd backend && python -m py_compile services/crawler.py && echo "OK"`

- [ ] **Step 5: 提交**

```bash
git add backend/services/crawler.py
git commit -m "feat(crawler): reuse httpx client across requests for connection pooling"
```

---

## Task 5: 端到端验证

**Files:** 无新增文件

- [ ] **Step 1: 语法和导入检查**

Run: `cd backend && python -c "from services.crawler import crawl_list_page, _build_article_doc, _retryable_request; print('OK')"`

- [ ] **Step 2: URL 归一化测试**

Run: `cd backend && python -c "from models.document_fingerprint import _url_hash; print(_url_hash('https://a.com/p?id=1&x=2')); print(_url_hash('https://a.com/p?x=2&id=1'))"`
Expected: 两个 hash 相同（params 排序后等价）

- [ ] **Step 3: 提交**

```bash
git commit -m "test(crawler): add URL normalization and retry unit tests"
```

---

## 依赖关系

```
Task 1 (模型) ──→ Task 2 (_build_article_doc 需要 DocumentFingerprint)
Task 3 (退避) ──┬─→ Task 4 (client 传入)
Task 2 (批量) ──┴─→ Task 4 (_build_article_doc 接收 http_client)
```

**推荐执行顺序：** Task 1 → Task 3 → Task 2+4 并行 → Task 5

---

## 自检清单

- [ ] Task 1: `DocumentFingerprint` 模型正常加载
- [ ] Task 2: 批量插入，`session.commit()` 次数从每篇减少到每批一次
- [ ] Task 3: `_retryable_request` 识别 429 和 5xx
- [ ] Task 4: `http_client` 在整个 `crawl_list_page` 生命周期内复用
- [ ] Task 2+4 解耦：`crawl_article` 不改签名，`_build_article_doc` 作为新建函数
- [ ] URL 归一化：params 排序后相同 URL 产生相同 hash
- [ ] 语法检查全部通过
