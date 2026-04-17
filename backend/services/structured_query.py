import re
from typing import Literal, Optional
from datetime import datetime, timedelta

# 问句分类器
STAT_KEYWORDS = ["最多", "最少", "哪个", "哪天", "哪天没有", "连续", "一共", "统计", "汇总", "第几", "排名"]
RAG_KEYWORDS = ["是什么", "如何", "怎样", "为什么", "怎么办", "怎么", "请问", "告诉", "介绍"]

def classify(question: str) -> Literal["rag", "structured", "hybrid"]:
    """判断问句类型：RAG问答 / 统计查询 / 两者混合"""
    has_stat = any(k in question for k in STAT_KEYWORDS)
    has_rag = any(k in question for k in RAG_KEYWORDS)
    if has_stat and has_rag:
        return "hybrid"
    elif has_stat:
        return "structured"
    return "rag"

# 日期提取
DATE_RANGE_PATTERNS = [
    (r"(\d+)月(\d+)日以来", "month_day_since"),
    (r"(\d{4})年(\d{1,2})月(\d{1,2})日以来?", "full_since"),
    (r"(\d{4})年(\d{1,2})月", "year_month"),
    (r"(\d+)月以来", "month_only"),
]

def extract_date_range(question: str) -> tuple[str, str]:
    """返回 (start_date, end_date)，end_date 默认为今天"""
    today = datetime.now().date()
    end = today.isoformat()
    for pattern, style in DATE_RANGE_PATTERNS:
        m = re.search(pattern, question)
        if not m:
            continue
        if style == "month_only":
            month = int(m.group(1))
            year = today.year
            start = f"{year}-{month:02d}-01"
        elif style == "month_day_since":
            month, day = int(m.group(1)), int(m.group(2))
            year = today.year
            start = f"{year}-{month:02d}-{day:02d}"
        elif style == "full_since":
            year, month, day = int(m.group(1)), int(m.group(2)), int(m.group(3))
            start = f"{year}-{month:02d}-{day:02d}"
        elif style == "year_month":
            year, month = int(m.group(1)), int(m.group(2))
            start = f"{year}-{month:02d}-01"
        return start, end
    # 默认：最近30天
    start = (today - timedelta(days=30)).isoformat()
    return start, end

def build_structured_query(question: str, category: str, sub_category: str) -> Optional[dict]:
    """根据问句和文档类型构建结构化查询。返回 {"sql": str, "params": list} 或 None"""
    if not category or not sub_category:
        return None
    start_date, end_date = extract_date_range(question)
    if sub_category == "教工食堂菜谱":
        return build_menu_query(question, start_date, end_date)
    return None

def build_menu_query(question: str, start_date: str, end_date: str) -> dict:
    """构建菜谱统计查询"""
    meal_filter = None
    for meal in ["早餐", "午餐", "晚餐"]:
        if meal in question:
            meal_filter = meal
            break
    cat_filter = None
    for cat in ["热菜", "凉菜", "主食", "汤"]:
        if cat in question:
            cat_filter = cat
            break

    dimension = "dish_name"
    sql = f"""
        SELECT dish_name, COUNT(*) as cnt,
               GROUP_CONCAT(DISTINCT menu_date) as dates
        FROM menu_items
        WHERE menu_date >= ? AND menu_date <= ?
    """
    params = [start_date, end_date]
    if meal_filter:
        sql += " AND meal_type = ?"
        params.append(meal_filter)
    if cat_filter:
        sql += " AND dish_category = ?"
        params.append(cat_filter)
    sql += f" GROUP BY {dimension} ORDER BY cnt DESC LIMIT 10"
    return {"sql": sql.strip(), "params": params, "dimension": dimension}

def format_structured_result(rows: list, question: str, dimension: str) -> str:
    """将 SQL 结果格式化为自然语言回答"""
    if not rows:
        return "未找到符合条件的记录。"
    top = rows[0]
    text = f"「{top[dimension]}」出现次数最多，共 {top['cnt']} 次，"
    dates = (top.get("dates") or "").split(",")
    dates = [d for d in dates if d]
    if dates:
        text += f"提供的日期有：{', '.join(dates[:5])}"
        if len(dates) > 5:
            text += f" 等{len(dates)}天"
    return text
