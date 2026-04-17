import logging
import threading

logger = logging.getLogger(__name__)

PARSER_REGISTRY = {
    ("生活服务", "教工食堂菜谱"): "menu",
}


def get_parser_type(category: str, sub_category: str) -> str:
    key = (category, sub_category)
    if key in PARSER_REGISTRY:
        return PARSER_REGISTRY[key]
    for (cat, sub), ptype in PARSER_REGISTRY.items():
        if (cat == "*" or cat == category) and (sub == "*" or sub == sub_category):
            return ptype
    return "none"


def extract_structured(doc_id: str, category: str, sub_category: str,
                      content: str, source_url: str) -> list[dict]:
    parser_type = get_parser_type(category, sub_category)
    if parser_type == "menu":
        from services.parsers.menu_parser import parse_menu_content
        from models.menu_item import MenuItem
        items = parse_menu_content(content, doc_id, category, sub_category, source_url)
        return [_item_to_dict(item) for item in items]
    return []


def _item_to_dict(item) -> dict:
    return {
        "id": item.id,
        "doc_id": item.doc_id,
        "category": item.category,
        "sub_category": item.sub_category,
        "dish_name": item.dish_name,
        "dish_category": item.dish_category,
        "meal_type": item.meal_type,
        "menu_date": item.menu_date,
        "source_url": item.source_url,
        "created_at": item.created_at,
    }


def save_structured_items(items: list[dict]):
    if not items:
        return
    from database import create_session
    from models.menu_item import MenuItem
    with create_session() as session:
        for item_dict in items:
            session.add(MenuItem(**item_dict))
        session.commit()
    logger.info(f"[structured] Saved {len(items)} items")


def trigger_extraction(doc_id: str, category: str, sub_category: str,
                       content: str, source_url: str):
    """
    触发结构化提取（后台线程，不阻塞爬虫主线程）。
    在 crawler.py 的 crawl_article() 中调用。
    """
    def _do():
        try:
            items = extract_structured(doc_id, category, sub_category, content, source_url)
            save_structured_items(items)
        except Exception as e:
            logger.warning(f"[structured] Extraction failed for doc {doc_id}: {e}")
    t = threading.Thread(target=_do, daemon=True)
    t.start()
