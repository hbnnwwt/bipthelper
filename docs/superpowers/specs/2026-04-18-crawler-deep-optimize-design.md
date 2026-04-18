# 爬虫深度优化设计

## 目标

优化爬虫的代码可维护性和爬取稳定性，不改变外部行为。

---

## 问题 1：`extract_main_content` 过长（~120行）

**现状：** 所有职责堆在一个函数里 — 标题提取、body选择、元素清理、表格处理、列表处理。

**方案：拆分为独立函数**

```python
def _extract_title(soup) -> str:
    """从 BeautifulSoup 对象提取标题"""

def _extract_body(soup, selector: str):
    """用备选选择器列表提取正文元素"""

def _clean_unwanted(main):
    """移除 script/style/nav/footer/header/按钮/功能链接"""

def _process_tables(main):
    """将表格转换为结构化文本"""

def _process_lists(main):
    """列表项前加短横线"""

def _cleanup_content(text: str) -> str:
    """清理多余空行，移除过短行"""

def extract_main_content(html: str, selector: str = "body") -> tuple[str, str]:
    soup = BeautifulSoup(html, "html.parser")
    title = _extract_title(soup)
    main = _extract_body(soup, selector)
    _clean_unwanted(main)
    _process_tables(main)
    _process_lists(main)
    content = _cleanup_content(main.get_text(separator="\n", strip=True))
    return title, content
```

---

## 问题 2：`crawl_list_page` 重试块重复

**现状：** 主路径和重试路径几乎完全相同，违反 DRY。

**方案：提取 `_fetch_list_page` 函数**

```python
def _fetch_list_page(page_url: str, config: CrawlConfig) -> tuple[httpx.Response, str]:
    """请求列表页，返回 (response, html)"""
    with httpx.Client(timeout=30.0, follow_redirects=True,
                     headers={"User-Agent": _random_ua()}) as client:
        response = client.get(page_url)
        response.raise_for_status()
        return response.text
```

主路径和重试路径都调用同一函数。重试时只需在外层捕获异常即可，不需要重复整个请求逻辑。

---

## 问题 3：`_crawl_all_impl` 和 `_crawl_configs_impl` 重复

**现状：** 两函数约 90% 代码相同。

**方案：提取 `_crawl_configs_iter` 共享实现**

```python
def _crawl_configs_iter(session: Session, configs: list[CrawlConfig]):
    """共同爬取逻辑：进度初始化、逐个爬取、状态更新"""
    # 包含 configs 初始化和循环体
    for i, config in enumerate(configs):
        # 停止检查、状态更新、调用 crawl_list_page
        result = crawl_list_page(config, session)
        with _progress_lock:
            crawl_progress["configs"][i]["status"] = "stopped" if result.stopped else "done"
```

两处调用：
```python
# crawl_all_impl
configs = session.exec(select(CrawlConfig).where(CrawlConfig.enabled == True)).all()
_crawl_configs_iter(session, configs)

# crawl_configs_impl
configs = [session.get(CrawlConfig, cid) for cid in config_ids]
configs = [c for c in configs if c]
_crawl_configs_iter(session, configs)
```

---

## 问题 4：per-domain 限速

**现状：** 连续爬同一域名的文章没有间隔，可能触发服务端限速。

**方案：维护 `_domain_last_crawl` 字典，每次爬取前检查并等待**

```python
_domain_last_crawl: dict[str, float] = {}  # domain -> 上次爬取时间戳
DOMAIN_MIN_DELAY = 2.0  # 秒

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

在 `crawl_article` 的 `httpx.get()` 之前调用。

---

## 自检

- [ ] 无 Placeholder/TODO
- [ ] 所有拆分不影响外部行为（内部重构）
- [ ] per-domain 限速不改变返回结果
- [ ] 拆分后的函数名称清晰、不歧义
