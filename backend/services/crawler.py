import httpx
import hashlib
import random
import re
import time
import threading
from bs4 import BeautifulSoup
from datetime import datetime
from sqlmodel import Session, select
from pathlib import Path
from urllib.parse import urljoin, urlparse, parse_qs
import logging
from dataclasses import dataclass

from config import get_settings
from database import create_session
from models.document import Document
from models.crawl_config import CrawlConfig
from services.search import index_document
from services import log_store  # noqa: ensures log handler is registered

# 爬虫限速工具
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
]


@dataclass
class CrawlResult:
    """crawl_list_page 的返回结果"""
    articles_crawled: int   # 本次爬取的文章数（含新爬和重复跳过）
    new_articles: int       # 本次新增的文章数
    pages_crawled: int      # 本次爬取的分页数
    stopped: bool           # 是否被用户主动停止


def _crawl_delay(base: float) -> float:
    """在基础延时上叠加 ±30% 随机抖动，模拟人类浏览节奏"""
    return base * random.uniform(0.7, 1.3)


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
                try:
                    crawl_list_page(config, session)
                finally:
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

def _random_ua() -> str:
    return random.choice(USER_AGENTS)


settings = get_settings()
logger = logging.getLogger(__name__)

# 爬虫运行状态（线程安全）
_crawl_lock = threading.Lock()
_progress_lock = threading.Lock()
crawl_running = False
crawl_stop_requested = False

# 定时调度器
_scheduler_thread = None
_scheduler_running = False

# 爬取进度（线程安全，由 crawler 线程更新，API 线程读取）
crawl_progress = {
    "phase": "idle",        # idle | running | stopping
    "current_config": "",
    "current_config_id": None,
    "config_index": 0,
    "total_configs": 0,
    "configs": [],          # 每个配置的明细状态
    "page": 0,
    "total_pages": 0,          # 当前配置的总页数（解析分页控件获取）
    "articles_crawled": 0,
    "articles_total": 0,       # 当前配置预估的总文章数
}

def request_crawl_stop():
    """请求停止爬取"""
    global crawl_stop_requested
    crawl_stop_requested = True
    logger.info("Crawl stop requested")

def reset_crawl_state():
    """重置爬虫状态"""
    global crawl_running, crawl_stop_requested, crawl_progress
    with _progress_lock:
        crawl_running = False
        crawl_stop_requested = False
        crawl_progress = {
            "phase": "idle",
            "current_config": "",
            "current_config_id": None,
            "config_index": 0,
            "total_configs": 0,
            "configs": [],
            "page": 0,
            "total_pages": 0,
            "articles_crawled": 0,
            "articles_total": 0,
        }

def _update_progress(page: int = None, total_pages: int = None,
                      articles_crawled: int = None, articles_total: int = None):
    """更新 crawl_progress 顶层字段（线程安全）"""
    with _progress_lock:
        if page is not None:
            crawl_progress["page"] = page
        if total_pages is not None:
            crawl_progress["total_pages"] = total_pages
        if articles_crawled is not None:
            crawl_progress["articles_crawled"] = articles_crawled
        if articles_total is not None:
            crawl_progress["articles_total"] = articles_total
        idx = crawl_progress["config_index"] - 1
        if idx >= 0 and idx < len(crawl_progress["configs"]):
            if page is not None:
                crawl_progress["configs"][idx]["page"] = page
            if total_pages is not None:
                crawl_progress["configs"][idx]["total_pages"] = total_pages
            if articles_total is not None:
                crawl_progress["configs"][idx]["articles_total"] = articles_total
            if articles_crawled is not None:
                crawl_progress["configs"][idx]["articles_crawled"] = articles_crawled

HTMLS_DIR = Path(settings.HTMLS_DIR)
HTMLS_DIR.mkdir(parents=True, exist_ok=True)

def compute_hash(content: str) -> str:
    return hashlib.md5(content.encode()).hexdigest()

def extract_article_metadata(html: str, base_url: str) -> dict:
    """从文章页面提取元数据（标题、发布时间、发布单位）"""
    soup = BeautifulSoup(html, "html.parser")

    # 提取标题
    title = ""
    if soup.title:
        title = soup.title.string or ""
    h1 = soup.find("h1")
    if h1:
        title = h1.get_text(strip=True) or title

    # 提取元数据行，如"发布单位：国实处 发布日期：2026年4月03日 浏览次数： 168"
    department = None
    publish_date = None
    meta = soup.find(string=re.compile("发布单位："))
    if meta:
        meta_text = meta.strip()
        dept_match = re.search(r"发布单位：([^ ]+)", meta_text)
        if dept_match:
            department = dept_match.group(1)
        date_match = re.search(r"发布日期[：:]([^ ]+)", meta_text)
        if date_match:
            raw_date = date_match.group(1).strip()
            # 将中文日期转为 ISO 格式（"2026年4月03日" → "2026-04-03"）
            iso_match = re.match(r"(\d{4})年(\d{1,2})月(\d{1,2})日?", raw_date)
            if iso_match:
                y, m, d = iso_match.groups()
                publish_date = f"{y}-{int(m):02d}-{int(d):02d}"
            else:
                publish_date = raw_date

    return {
        "title": title,
        "department": department,
        "publish_date": publish_date,
    }

def extract_main_content(html: str, selector: str = "body") -> tuple[str, str]:
    """提取正文内容和标题"""
    soup = BeautifulSoup(html, "html.parser")

    # 提取标题
    title = ""
    if soup.title:
        title = soup.title.string or ""
    h1 = soup.find("h1")
    if h1:
        title = h1.get_text(strip=True) or title

    # 提取正文（支持备选选择器，兼容不同页面结构）
    fallback_selectors = [selector, ".subArticleCon", "#content", ".content", ".article-body", "body"]
    main = None
    for sel in fallback_selectors:
        if not sel:
            continue
        main = soup.select_one(sel)
        if main and len(main.get_text(strip=True)) > 50:
            break  # 找到内容足够丰富的元素
    if not main:
        main = soup.body  # 最终降级到 body
    if main:
        # 移除脚本和样式
        for tag in main.find_all(["script", "style", "nav", "footer", "header"]):
            tag.decompose()

        # 移除元数据行（如"发布单位：xxx 发布日期：xxx 浏览次数：168"）
        for tag in main.find_all(["p", "span", "div"]):
            text = tag.get_text(strip=True)
            if "浏览次数" in text or "发布单位" in text:
                tag.decompose()

        # 移除按钮和功能链接（如"保存信息"、"关闭窗口"、"打印"等）
        for tag in main.find_all(["button", "input"]):
            tag.decompose()
        for tag in main.find_all("a"):
            txt = tag.get_text(strip=True)
            if any(k in txt for k in ["保存", "关闭", "打印", "分享", "收藏"]):
                tag.decompose()

        # 表格内容：转换为结构化文本格式，保留行列关系
        # 处理 rowspan/colspan：先构建单元格矩阵，追踪跨行单元格
        for table in main.find_all("table"):
            try:
                rows = table.find_all("tr")
                if not rows:
                    continue

                # 计算最大列数
                max_cols = 0
                for row in rows:
                    col_count = sum(int(cell.get("colspan", 1)) for cell in row.find_all(["td", "th"]))
                    max_cols = max(max_cols, col_count)

                if max_cols == 0:
                    continue

                # grid[row][col] = text，row_span_map[col] = (text, remaining_rows)
                grid = []
                row_span_map = [None] * max_cols  # 上方单元格 rowspan 状态

                for row_el in rows:
                    grid_row = [""] * max_cols

                    # 第1步：填入上方跨行单元格
                    for col in range(max_cols):
                        if row_span_map[col]:
                            text, remaining = row_span_map[col]
                            grid_row[col] = text
                            row_span_map[col] = (text, remaining - 1) if remaining > 1 else None

                    # 第2步：填入当前行单元格
                    col_idx = 0
                    for cell in row_el.find_all(["td", "th"]):
                        text = cell.get_text(strip=True)
                        rowspan = int(cell.get("rowspan", 1))
                        colspan = int(cell.get("colspan", 1))

                        # 跳过已被占的列（包括上方跨行下来的）
                        while col_idx < max_cols and grid_row[col_idx]:
                            col_idx += 1

                        for c in range(colspan):
                            if col_idx + c < max_cols:
                                grid_row[col_idx + c] = text
                                if rowspan > 1:
                                    row_span_map[col_idx + c] = (text, rowspan - 1)
                        col_idx += colspan

                    grid.append(grid_row)

                # 输出
                lines = []
                for g_row in grid:
                    cells = [t for t in g_row if t]
                    if cells:
                        lines.append(" - " + "、".join(cells))
                if lines:
                    table.replace_with(soup.new_string("\n".join(lines) + "\n"))
            except Exception:
                pass

        # 列表项：每项前加短横线，保持缩进可读性
        for li in main.find_all("li"):
            text = li.get_text(strip=True)
            if text and not text.startswith("-") and not text.startswith("•"):
                li.replace_with(soup.new_string(f"  - {text}\n"))

        content = main.get_text(separator="\n", strip=True)

        # 清理多余空行
        content = re.sub(r"\n{3,}", "\n\n", content)

        # 移除过短且无意义的行（纯空格/标点）
        lines = [line for line in content.split("\n") if line.strip() and len(line.strip()) > 1]
        content = "\n".join(lines)

        return title, content
    return title, soup.get_text(separator="\n", strip=True)

def resolve_url(link: str, base_url: str, link_prefix: str = None) -> str:
    """将相对URL解析为绝对URL"""
    # 先用 urljoin 基本解析
    full_url = urljoin(base_url, link)

    # 如果有额外的前缀需要补充
    if link_prefix and full_url.startswith("/"):
        full_url = link_prefix + full_url

    return full_url

def extract_article_links(html: str, base_url: str, article_selector: str, link_prefix: str = None) -> list[str]:
    """从列表页提取文章链接"""
    soup = BeautifulSoup(html, "html.parser")
    links = []

    for a in soup.select(article_selector):
        href = a.get("href", "")
        if href and not href.startswith(("#", "javascript:", "mailto:")):
            full_url = resolve_url(href, base_url, link_prefix)
            # 只接受 http/https URL，防止链式攻击
            if full_url and full_url.startswith(("http://", "https://")):
                links.append(full_url)

    # 去重并保持顺序
    seen = set()
    unique_links = []
    for link in links:
        if link not in seen:
            seen.add(link)
            unique_links.append(link)

    return unique_links

def extract_page_number(url: str) -> int:
    """从 URL 中提取页码：index.htm=1, index1.htm=2, index2.htm=3 ..."""
    match = re.search(r'index(\d+)?\.htm', url)
    if match:
        num = match.group(1)
        return int(num) + 1 if num else 1
    return 1

def extract_next_page_link(html: str, base_url: str, pagination_selector: str) -> str | None:
    """从列表页提取下一页链接"""
    soup = BeautifulSoup(html, "html.parser")
    candidates = soup.select(pagination_selector)

    current_page = extract_page_number(base_url)
    best_candidate = None
    best_page_num = 9999  # 初始化为很大的值

    logger.info(f"[pagination] current_url={base_url}, current_page={current_page}, candidates={len(candidates)}")
    for link in candidates:
        href = link.get("href", "")
        # 跳过父目录链接和空链接
        if not href or ".." in href:
            continue
        resolved = urljoin(base_url, href)
        if resolved == base_url:
            continue
        candidate_page = extract_page_number(resolved)
        logger.info(f"[pagination] candidate href={href}, resolved={resolved}, page={candidate_page}")
        # 选页码比当前页大的候选，取页码最小的那一个（下一页，而不是尾页）
        if candidate_page > current_page and candidate_page < best_page_num:
            best_page_num = candidate_page
            best_candidate = resolved
            logger.info(f"[pagination] selected next page: {resolved} (page {candidate_page})")

    return best_candidate

def extract_total_pages(html: str) -> int:
    """
    从列表页解析总页数。
    常见格式："共100页"、"1/367"、"100页"、"pageCount: 100" 等。
    如果解析失败返回 0（表示未知）。
    """
    # 多种常见格式
    patterns = [
        r"<span>(\d+)/(\d+)</span>",  # <span>1/367</span> - 取第二个数字
        r"共(\d+)页",        # 共100页
        r"(\d+)\s*页",      # 100页
        r"总\s*:\s*(\d+)",  # 总 : 100
        r"pageCount\s*:\s*(\d+)",  # pageCount: 100
        r"totalPages\s*:\s*(\d+)",  # totalPages: 100
        r"total\s*=\s*(\d+)",  # total=100
    ]
    for pattern in patterns:
        match = re.search(pattern, html)
        if match:
            result = int(match.group(2)) if len(match.groups()) >= 2 else int(match.group(1))
            logger.info(f"[extract] total_pages matched pattern '{pattern[:30]}...' -> {result}")
            return result
    logger.warning(f"[extract] total_pages: no pattern matched in HTML")
    return 0


def extract_total_articles(html: str) -> int:
    """
    从列表页解析总文章数。
    常见格式："总数：<span>7332</span>"、"total: 7332" 等。
    如果解析失败返回 0（表示未知）。
    """
    patterns = [
        r"总数[：:]?\s*<span>(\d+)</span>",  # 总数：<span>7332</span> 或 总数：<span>7332</span>
        r"总数[：:]?\s*(\d+)",              # 总数：7332
        r"total[:\s]+(\d+)",               # total: 7332
        r"totalCount\s*:\s*(\d+)",         # totalCount: 7332
    ]
    for pattern in patterns:
        match = re.search(pattern, html)
        if match:
            result = int(match.group(1))
            logger.info(f"[extract] total_articles matched pattern '{pattern[:30]}...' -> {result}")
            return result
    logger.warning(f"[extract] total_articles: no pattern matched in HTML")
    return 0

def crawl_article(url: str, config: CrawlConfig, session: Session) -> bool:
    """爬取单个文章页面，返回是否成功"""
    try:
        time.sleep(_crawl_delay(settings.CRAWL_ARTICLE_DELAY))
        with httpx.Client(timeout=30.0, follow_redirects=True, headers={"User-Agent": _random_ua()}) as client:
            response = client.get(url)
            response.raise_for_status()
            html = response.text

        content_hash = compute_hash(html)

        # 保存原始HTML（按日期/域名分目录）
        url_hash = hashlib.md5(url.encode()).hexdigest()
        domain = urlparse(url).netloc.replace(":", "_")
        date_dir = datetime.now().strftime("%Y-%m-%d")
        html_subdir = HTMLS_DIR / date_dir / domain
        html_subdir.mkdir(parents=True, exist_ok=True)
        html_file = html_subdir / f"{url_hash}.html"
        html_file.write_text(html, encoding="utf-8")

        # 提取元数据（标题、发布时间、发布单位）
        meta = extract_article_metadata(html, url)

        # 提取正文内容（使用配置的选择器）
        title, content = extract_main_content(html, config.selector)

        # 更新或创建文档（不检查是否更新，直接覆盖）
        doc = session.exec(select(Document).where(Document.url == url)).first()
        now = datetime.now().isoformat()

        if doc:
            # 直接更新
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

        session.add(doc)
        session.commit()
        index_document(doc)

        # 后台触发结构化提取
        try:
            from services.structured_extractor import trigger_extraction
            trigger_extraction(
                doc_id=doc.id,
                category=doc.category or "",
                sub_category=doc.sub_category or "",
                content=content or "",
                source_url=url,
            )
        except Exception as e:
            logger.warning(f"[crawl] Failed to trigger structured extraction: {e}")

        # 后台线程生成文档向量（不阻塞爬虫主线程）
        try:
            from services.ai.embedding import embed_document
            doc_id = doc.id
            title = doc.title
            content = doc.content or ""
            url = doc.url
            category = doc.category or ""
            department = doc.department or ""
            parent_category = doc.parent_category or ""
            sub_category = doc.sub_category or ""

            def _embed():
                try:
                    embed_document(doc_id=doc_id, title=title, content=content,
                                   url=url, category=category, department=department,
                                   parent_category=parent_category, sub_category=sub_category)
                except Exception as e:
                    logger.warning(f"[embed] Failed to embed doc {doc_id}: {e}")

            t = threading.Thread(target=_embed, daemon=True)
            t.start()
        except Exception as e:
            logger.warning(f"Failed to spawn embedding thread for {doc.id}: {e}")

        logger.info(f"Crawled and indexed: {url} | {meta.get('department')} | {meta.get('publish_date')}")
        return True
    except Exception as e:
        logger.error(f"[crawl_article] Failed to crawl article {url}: {e}")
        return False

def crawl_list_page(config: CrawlConfig, session: Session) -> CrawlResult:
    """爬取列表页及其分页，返回新增/更新的文章数量"""
    if not config.is_list_page:
        # 非列表页，直接爬取单个URL
        return 1 if crawl_article(config.url, config, session) else 0

    visited_pages = set()  # 已访问的分页页
    visited_articles = set()  # 已爬取的文章URL（当前会话）
    new_count = 0
    stopped = False

    # 全量模式：不加载历史 URL，重新爬取所有文章
    # 增量模式：从数据库加载已爬取的文章URL（按分类过滤）
    is_incremental = config.initialized and config.pagination_max > 0
    if is_incremental:
        existing_docs = session.exec(select(Document.url).where(Document.category == config.category)).all()
        visited_articles.update(existing_docs)

    page_url = config.url
    page_count = 0
    total_pages = 0       # 总页数（解析分页控件获取）
    total_articles = 0    # 总文章数（解析获取）
    articles_crawled_count = 0  # 当前配置已爬取的文章数（实时更新）

    # 全量模式：使用用户设置的 pagination_max，0 表示不限制
    # 增量模式：只爬第1页（获取最新文章）
    if is_incremental:
        max_pages = 1
    else:
        max_pages = config.pagination_max if config.pagination_max > 0 else 999

    logger.info(f"Crawl mode: {'incremental' if is_incremental else 'full'}, max_pages={max_pages}")

    while page_url and page_url not in visited_pages and page_count < max_pages:
        if crawl_stop_requested:
            logger.info("Crawl stopped by user")
            stopped = True
            break
        visited_pages.add(page_url)
        page_count += 1
        _update_progress(page=page_count, total_pages=total_pages, articles_total=total_articles)
        # 第一页不延时，之后翻页前延时
        if page_count > 1:
            time.sleep(_crawl_delay(settings.CRAWL_DELAY_SECONDS))
        logger.info(f"Crawling list page {page_count}: {page_url}")

        try:
            with httpx.Client(timeout=30.0, follow_redirects=True, headers={"User-Agent": _random_ua()}) as client:
                response = client.get(page_url)
                response.raise_for_status()
                html = response.text

            # 解析总页数和总文章数（仅在第一页时）
            if page_count == 1:
                total_pages = extract_total_pages(html)
                total_articles = extract_total_articles(html)
                _update_progress(total_pages=total_pages, articles_total=total_articles)
                logger.info(f"Parsed total pages: {total_pages}, total articles: {total_articles}")

            # 提取文章链接
            article_links = extract_article_links(html, page_url, config.article_selector, config.link_prefix)
            logger.info(f"Found {len(article_links)} article links on page {page_count}, visited={len(visited_articles)}")

            # 爬取每篇文章
            if not article_links:
                logger.warning(f"[crawl] No article links found! selector='{config.article_selector}', link_prefix='{config.link_prefix}'")

            # 爬取每篇文章
            for article_url in article_links:
                if crawl_stop_requested:
                    logger.info("Crawl stopped by user")
                    stopped = True
                    break
                # 全量模式：所有文章都爬取；增量模式：跳过已爬取的
                if not is_incremental or article_url not in visited_articles:
                    if crawl_article(article_url, config, session):
                        new_count += 1
                    articles_crawled_count += 1
                    _update_progress(articles_crawled=articles_crawled_count)
                    visited_articles.add(article_url)
                elif is_incremental:
                    logger.info(f"Skipping already crawled: {article_url}")

            # 提取下一页链接
            if config.pagination_selector:
                next_url = extract_next_page_link(html, page_url, config.pagination_selector)
                page_url = next_url
            else:
                page_url = None

        except Exception as e:
            logger.error(f"Failed to crawl list page {page_url}: {e}")
            # 异常时尝试重试（最多 2 次）
            retry_count = 0
            max_retries = 2
            retry_success = False
            while retry_count < max_retries and not retry_success:
                retry_count += 1
                logger.info(f"Retrying page {page_count} ({retry_count}/{max_retries}): {page_url}")
                time.sleep(_crawl_delay(settings.CRAWL_DELAY_SECONDS) * 2)
                try:
                    with httpx.Client(timeout=30.0, follow_redirects=True, headers={"User-Agent": _random_ua()}) as client:
                        response = client.get(page_url)
                        response.raise_for_status()
                        html = response.text

                    if page_count == 1:
                        total_pages = extract_total_pages(html)
                        total_articles = extract_total_articles(html)
                        _update_progress(total_pages=total_pages, articles_total=total_articles)

                    article_links = extract_article_links(html, page_url, config.article_selector, config.link_prefix)
                    logger.info(f"Retry success: found {len(article_links)} article links on page {page_count}")

                    for article_url in article_links:
                        if crawl_stop_requested:
                            stopped = True
                            break
                        # 全量模式：所有文章都爬取；增量模式：跳过已爬取的
                        if not is_incremental or article_url not in visited_articles:
                            if crawl_article(article_url, config, session):
                                new_count += 1
                            articles_crawled_count += 1
                            _update_progress(articles_crawled=articles_crawled_count)
                            visited_articles.add(article_url)

                    if config.pagination_selector:
                        next_url = extract_next_page_link(html, page_url, config.pagination_selector)
                        page_url = next_url
                    else:
                        page_url = None
                    retry_success = True
                except Exception as retry_e:
                    logger.error(f"Retry {retry_count} failed: {retry_e}")
                    if retry_count >= max_retries:
                        logger.warning(f"Max retries reached, skipping page {page_count}")
                        page_url = None

    # 更新配置
    config.last_crawl = datetime.now().isoformat()
    # 首次全量爬取完成后，标记为已初始化（保持用户原始 pagination_max 设置）
    if not config.initialized:
        config.initialized = True
        logger.info(f"First fullcrawl complete. Marked as initialized (pagination_max={config.pagination_max})")
    session.add(config)
    session.commit()

    logger.info(f"List page crawl complete. New articles: {new_count}, pages: {page_count}, stopped: {stopped}")
    return CrawlResult(
        articles_crawled=articles_crawled_count,
        new_articles=new_count,
        pages_crawled=page_count,
        stopped=stopped,
    )

def crawl_all(session=None):
    """爬取所有启用的配置（线程安全）"""
    global crawl_running
    with _crawl_lock:
        if crawl_running:
            logger.warning("Crawl already running, skipping")
            return False
        crawl_running = True
    try:
        if session is None:
            with create_session() as new_session:
                _crawl_all_impl(new_session)
        else:
            _crawl_all_impl(session)
        return True
    finally:
        with _crawl_lock:
            global crawl_progress
            crawl_running = False
            crawl_stop_requested = False
        with _progress_lock:
            crawl_progress = {
                "phase": "idle",
                "current_config": "",
                "current_config_id": None,
                "config_index": 0,
                "total_configs": 0,
                "configs": [],
                "page": 0,
                "total_pages": 0,
                "articles_crawled": 0,
                "articles_total": 0,
            }

def _crawl_all_impl(session: Session):
    """实际爬取逻辑"""
    global crawl_progress
    db_configs = session.exec(select(CrawlConfig).where(CrawlConfig.enabled == True)).all()
    total = len(db_configs)
    crawl_progress["total_configs"] = total
    # 初始化 configs 明细列表
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
        for c in db_configs
    ]
    for i, config in enumerate(db_configs):
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
            crawl_progress["articles_crawled"] = 0  # 重置，开始新配置
            # 设置当前 config 状态为 running
            crawl_progress["configs"][i]["status"] = "running"
        result = crawl_list_page(config, session)
        # 根据 result.stopped 决定状态
        with _progress_lock:
            crawl_progress["configs"][i]["status"] = "stopped" if result.stopped else "done"


def crawl_configs(config_ids: list[str], session=None):
    """爬取指定的一组配置（线程安全）"""
    global crawl_running
    with _crawl_lock:
        if crawl_running:
            logger.warning("Crawl already running, skipping")
            return False
        crawl_running = True
    try:
        if session is None:
            with create_session() as new_session:
                _crawl_configs_impl(new_session, config_ids)
        else:
            _crawl_configs_impl(session, config_ids)
        return True
    finally:
        with _crawl_lock:
            global crawl_progress
            crawl_running = False
            crawl_stop_requested = False
        with _progress_lock:
            crawl_progress = {
                "phase": "idle",
                "current_config": "",
                "current_config_id": None,
                "config_index": 0,
                "total_configs": 0,
                "configs": [],
                "page": 0,
                "total_pages": 0,
                "articles_crawled": 0,
                "articles_total": 0,
            }


def _crawl_configs_impl(session: Session, config_ids: list[str]):
    """爬取指定配置的内部实现"""
    global crawl_progress
    db_configs = [session.get(CrawlConfig, cid) for cid in config_ids]
    db_configs = [c for c in db_configs if c is not None and c.enabled]
    total = len(db_configs)
    crawl_progress["total_configs"] = total
    # 初始化 configs 明细列表
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
        for c in db_configs
    ]
    for i, config in enumerate(db_configs):
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
            crawl_progress["articles_crawled"] = 0  # 重置，开始新配置
            # 设置当前 config 状态为 running
            crawl_progress["configs"][i]["status"] = "running"
        new_count = crawl_list_page(config, session)
        # 设置当前 config 状态为 done
        with _progress_lock:
            crawl_progress["configs"][i]["status"] = "done"

def add_crawl_config(name: str, url: str, selector: str, category: str, session: Session,
                     is_list_page: bool = True, article_selector: str = "a",
                     link_prefix: str = None, pagination_selector: str = "",
                     pagination_max: int = 0,
                     parent_category: str = None, sub_category: str = None,
                     auto_interval_hours: int = 0) -> CrawlConfig:
    """添加爬虫配置"""
    config = CrawlConfig(
        name=name,
        url=url,
        selector=selector,
        category=category,
        is_list_page=is_list_page,
        article_selector=article_selector,
        link_prefix=link_prefix,
        pagination_selector=pagination_selector,
        pagination_max=pagination_max,
        parent_category=parent_category,
        sub_category=sub_category,
        auto_interval_hours=auto_interval_hours,
    )
    session.add(config)
    session.commit()
    session.refresh(config)
    return config

# ─────────────────────────────────────────────
# 首页导航解析：爬取 info.bipt.edu.cn 的导航菜单，提取所有大类和小类
# ─────────────────────────────────────────────

HOMEPAGE_URL = "https://info.bipt.edu.cn/"
# 基础路径前缀（用于补全相对链接）
BASE_PREFIX = "https://info.bipt.edu.cn/"


def parse_homepage_navigation(html: str, base_url: str = HOMEPAGE_URL) -> list[dict]:
    """
    解析首页导航菜单，返回结构化的大类/小类列表。
    返回格式：
    [
      {
        "parent": "机关教辅",        # 大类名称
        "subs": [
          {"name": "通知公告", "url": "https://info.bipt.edu.cn/jgjf/bctzgg/index.htm"},
          {"name": "部门文件", "url": "https://info.bipt.edu.cn/jgjf/bcbmwj/index.htm"},
        ]
      },
      ...
    ]
    """
    soup = BeautifulSoup(html, "html.parser")
    nav_items = []

    # 定位 #nav > li
    nav_list = soup.select("#nav > li")
    for li in nav_list:
        # 提取大类名称（a 标签文字，跳过纯子栏目链接）
        a_tag = li.select_one("a[href]")
        if not a_tag:
            continue
        parent_name = a_tag.get_text(strip=True)
        if not parent_name or parent_name == "首页":
            continue

        # 提取小类
        subs = []
        sub_dl = li.select("div.subNav dl dd a")
        for sub_a in sub_dl:
            sub_name = sub_a.get_text(strip=True)
            sub_href = sub_a.get("href", "")
            if not sub_name or not sub_href:
                continue
            # 补全相对链接
            full_url = urljoin(base_url, sub_href)
            subs.append({"name": sub_name, "url": full_url})

        # 跳过无小类的导航项（如"机构导航"、"热点链接"）
        if not subs:
            continue

        nav_items.append({
            "parent": parent_name,
            "subs": subs,
        })

    return nav_items


def crawl_homepage_navigation(session: Session) -> list[dict]:
    """
    抓取首页并解析导航结构，返回 nav_items。
    仅解析，不创建配置。
    """
    logger.info(f"Fetching homepage navigation: {HOMEPAGE_URL}")
    with httpx.Client(timeout=30.0, follow_redirects=True, headers={"User-Agent": _random_ua()}) as client:
        response = client.get(HOMEPAGE_URL)
        response.raise_for_status()
        html = response.text

    nav_items = parse_homepage_navigation(html, HOMEPAGE_URL)
    logger.info(f"Parsed {len(nav_items)} top-level categories from homepage")
    for item in nav_items:
        logger.info(f"  [{item['parent']}] {len(item['subs'])} sub-categories")
    return nav_items
