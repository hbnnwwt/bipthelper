# 爬虫改进设计

## 目标

对 `crawler.py` 进行四项改进：批量插入、持久化去重+内容更新检测、HTTP 429退避、连接池复用。

## 项目分解

本设计包含 4 个相互独立的改进项，可并行实现：

| # | 子项目 | 优先级 | 范围 |
|---|--------|--------|------|
| A | 批量插入 | P1 | `crawl_list_page` 中文章批量 `session.add()` 后一次 `commit()` |
| B | 持久化去重 + 内容更新检测 | P1 | 新建 `Document Fingerprint` 表，URL 归一化，hash 比对更新 |
| C | HTTP 429 退避重试 | P1 | `crawl_article` + `_fetch_list_page` 识别 429，增加 exp backoff |
| D | 连接池复用 | P2 | 复用单个 `httpx.Client`，通过 context manager 管理 |

---

## 子项目 A：批量插入

**现状：** 每篇文章单独 `session.add()` + `session.commit()`，N 次 DB 写入。

**方案：** 积累一批文章（每批 50 篇或每页完成），统一 `session.add()` 后一次 `commit()`。

```python
# crawl_list_page 主循环中
article_batch = []
BATCH_SIZE = 50

for url in urls:
    article_batch.append(article_data)
    if len(article_batch) >= BATCH_SIZE:
        _flush_batch(session, article_batch)
        article_batch = []

# 页尾 flush
if article_batch:
    _flush_batch(session, article_batch)

def _flush_batch(session, batch):
    for doc_data in batch:
        session.add(Document(**doc_data))
    session.commit()
```

**影响范围：** `crawl_list_page` 函数内部，不改接口。

---

## 子项目 B：持久化去重 + 内容更新检测

**现状：** `visited_articles` 是内存 Set，进程重启后丢失；URL 未归一化；`content_hash` 计算了但从不比对。

**方案：**

### B1. 新建 `DocumentFingerprint` 表（key.db）

```python
class DocumentFingerprint(SQLModel, table=True):
    __tablename__ = "document_fingerprints"

    url_hash: str = Field(primary_key=True)  # SHA256(normalized_url)
    url: str = Field(index=True)
    content_hash: str                          # SHA256(正文内容)
    created_at: str = Field(default_factory=_now)
    updated_at: str = Field(default_factory=_now)
    doc_id: str = Field(index=True)            # 关联 Document.id
```

### B2. URL 归一化

```python
from urllib.parse import urlparse, parse_qs, unquote

def normalize_url(url: str) -> str:
    """归一化：去除 fragment、排序 query params"""
    parsed = urlparse(url)
    # 去除 fragment
    # decode query params 并排序
    normalized = parsed._replace(
        fragment="",
        query="&".join(sorted(f"{k}={v}" for k, vs in parse_qs(parsed.query).items() for v in vs))
    )
    return normalized.geturl()

def url_hash(url: str) -> str:
    import hashlib
    return hashlib.sha256(normalize_url(url).encode()).hexdigest()
```

### B3. 内容更新检测

爬取文章时：
1. 计算 `content_hash`
2. 查询 `DocumentFingerprint`，若 `url_hash` 已存在且 `content_hash == stored`：跳过（无变化）
3. 若 `content_hash` 不同：更新 fingerprint，`doc.updated_at = now()`（触发向量更新）
4. 若 `url_hash` 不存在：新建 fingerprint + Document

```python
def _check_and_save_article(session, url, content_hash, doc_data):
    url_h = url_hash(url)
    fp = session.exec(select(DocumentFingerprint).where(DocumentFingerprint.url_hash == url_h)).one_or_none()

    if fp:
        if fp.content_hash == content_hash:
            return None  # 内容无变化，跳过
        # 内容更新了
        fp.content_hash = content_hash
        fp.updated_at = _now()
        doc_data["updated_at"] = _now()
        session.add(fp)

    new_fp = DocumentFingerprint(url_hash=url_h, url=url, content_hash=content_hash, doc_id=doc_data["id"])
    session.add(new_fp)
    return doc_data
```

---

## 子项目 C：HTTP 429 退避重试

**现状：** 请求失败只重试 2 次，无区分 429，无退避。

**方案：** 在 `crawl_article` 和 `_fetch_list_page` 的请求外层包装 `retry_with_backoff`。

```python
import random

DEFAULT_MAX_RETRIES = 3
DEFAULT_BASE_DELAY = 2.0  # 秒

def retry_with_backoff(func, max_retries=DEFAULT_MAX_RETRIES, base_delay=DEFAULT_BASE_DELAY):
    """对 HTTP 请求函数包装退避重试，识别 429 和 5xx"""
    for attempt in range(max_retries):
        try:
            return func()
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 429 and attempt < max_retries - 1:
                # Retry-After header 优先，否则 exp backoff
                retry_after = e.response.headers.get("Retry-After")
                if retry_after:
                    wait = float(retry_after)
                else:
                    wait = base_delay * (2 ** attempt) + random.uniform(0, 1)
                logger.warning(f"[crawl] 429 received, retrying in {wait:.1f}s (attempt {attempt+1}/{max_retries})")
                time.sleep(wait)
                continue
            if e.response.status_code >= 500 and attempt < max_retries - 1:
                wait = base_delay * (2 ** attempt)
                time.sleep(wait)
                continue
            raise
```

---

## 子项目 D：连接池复用

**现状：** 每次请求 `with httpx.Client(...) as client: client.get()`，每次都新建连接。

**方案：** 传入共享的 client 实例，在 `crawl_list_page` 级别创建一次。

```python
# crawl_list_page 入口
with httpx.Client(timeout=30.0, follow_redirects=True,
                  headers={"User-Agent": _random_ua()}) as http_client:
    for page_num in range(...):
        _fetch_list_page_with_client(http_client, page_url)
        for url in article_urls:
            crawl_article_with_client(http_client, url, config, session)

def _fetch_list_page_with_client(client, page_url) -> str:
    response = client.get(page_url)
    response.raise_for_status()
    return response.text

def crawl_article_with_client(client, url, config, session):
    # 不再自己创建 httpx.Client，复用传入的
    _enforce_domain_delay(url)
    with client as c:
        response = c.get(url)
    ...
```

**注意：** `httpx.Client` 本身支持连接池（HTTP/1.1 keep-alive），通过 `with` 复用同一个实例即可。

---

## 自检

- [ ] 子项目 A/B/C/D 相互独立，可并行实现
- [ ] B 中 `DocumentFingerprint` 使用 key.db（与现有 `StructuredDefinition`/`MenuItem` 同库）
- [ ] C 退避不改变正常情况下的返回结果
- [ ] D 不改变函数签名，只改内部实现
- [ ] 无 placeholder / TBD
