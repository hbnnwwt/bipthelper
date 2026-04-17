import re
import uuid
from models.menu_item import MenuItem

MEAL_TYPE_MAP = {
    "早餐": "早餐",
    "早饭": "早餐",
    "午饭": "午餐",
    "午餐": "午餐",
    "中餐": "午餐",
    "晚饭": "晚餐",
    "晚餐": "晚餐",
    "晚市": "晚餐",
}

DISH_CATEGORY_MAP = {
    "热菜": "热菜",
    "荤菜": "热菜",
    "凉菜": "凉菜",
    "冷菜": "凉菜",
    "冷盘": "凉菜",
    "主食": "主食",
    "米饭": "主食",
    "面食": "主食",
    "汤": "汤",
    "汤类": "汤",
    "饮品": "饮品",
    "饮料": "饮品",
}

def parse_menu_content(content: str, doc_id: str, category: str,
                       sub_category: str, source_url: str) -> list[MenuItem]:
    """
    解析菜谱文本内容，返回 MenuItem 列表。
    content 是 extract_main_content() 输出的表格文本（每行一个菜名或餐次标记）。
    """
    items = []
    current_meal = ""
    current_date = ""
    lines = content.split("\n")

    # 从 content 中尝试提取日期
    date_match = re.search(r"(\d{4})[-年](\d{1,2})[-月](\d{1,2})", content)
    if date_match:
        y, m, d = date_match.groups()
        current_date = f"{int(y)}-{int(m):02d}-{int(d):02d}"

    for line in lines:
        line = line.strip()
        if not line:
            continue

        # 跳过纯序号行
        if re.match(r"^[\d一二三四五六七八九十]+[.、)]\s*$", line):
            continue

        # 跳过金额行
        if re.search(r"^[\d.]+[元¥$]", line) or re.search(r"[元¥$][\d.]+$", line):
            continue

        # 检测餐次
        for kw, meal_type in MEAL_TYPE_MAP.items():
            if kw in line and len(line) < 10:
                current_meal = meal_type
                break

        # 检测菜品分类
        dish_category = ""
        for kw, cat in DISH_CATEGORY_MAP.items():
            if kw in line:
                dish_category = cat
                break

        # 清理行：去除序号前缀
        line_clean = re.sub(r"^[\d一二三四五六七八九十]+[.、)\s]*", "", line)
        # 去除金额后缀
        line_clean = re.sub(r"[\d.]+[元¥$]", "", line_clean).strip()
        # 去除 URL
        line_clean = re.sub(r"https?://\S+", "", line_clean).strip()

        # 过滤噪声行
        skip_words = ["浏览次数", "发布单位", "发布日期", "版权所有", "点击", "关闭",
                     "打印", "保存", "栏目", "编辑", "来源", "作者", "http"]
        if any(w in line_clean for w in skip_words):
            continue
        if len(line_clean) < 2:
            continue
        if re.match(r"^[A-Za-z]+://", line_clean):
            continue

        # 跳过餐次行本身（不是菜名）
        if line_clean in MEAL_TYPE_MAP or line_clean.rstrip("餐晚饭午餐") == "":
            continue

        dish_name = line_clean
        if dish_name and current_meal:
            items.append(MenuItem(
                id=str(uuid.uuid4()),
                doc_id=doc_id,
                category=category,
                sub_category=sub_category,
                dish_name=dish_name,
                dish_category=dish_category or "热菜",
                meal_type=current_meal,
                menu_date=current_date,
                source_url=source_url,
            ))

    return items
