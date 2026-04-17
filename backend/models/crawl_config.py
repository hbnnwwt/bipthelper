from sqlmodel import SQLModel, Field
from typing import Optional
from datetime import datetime
import uuid

class CrawlConfig(SQLModel, table=True):
    __tablename__ = "crawl_configs"

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    name: str                      # 配置名称，如"通知公告"
    url: str                       # 起始URL（列表页）
    category: Optional[str] = None # 默认分类
    parent_category: Optional[str] = None  # 大类，如"机关教辅"
    sub_category: Optional[str] = None    # 小类，如"通知公告"

    # 文章内容提取（用于单个文章页面）
    selector: str = "body"          # CSS选择器，提取文章正文

    # 列表页配置
    is_list_page: bool = True      # 是否为列表页
    article_selector: str = "a"    # 列表中选择文章链接的选择器
    link_prefix: Optional[str] = None  # 文章链接的前缀（如完整URL需要补充）

    # 分页配置
    pagination_selector: str = ""   # 分页选择器，如"a.next"或".pagination a"
    pagination_max: int = 0         # 最大页数，0=不限制

    # 状态
    enabled: bool = True
    last_hash: Optional[str] = None
    last_crawl: Optional[str] = None
    initialized: bool = False      # 是否已完成首次全量爬取
    auto_interval_hours: int = 0  # 自动爬取间隔（小时），0=关闭
