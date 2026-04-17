# 通用结构化查询框架实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 新增结构化查询框架，使系统能回答"4月以来哪个菜被提供最多"等统计类问题，同时保留现有 RAG 问答能力。

**Architecture:** 问句分类器判断走 RAG 还是 SQL，两路并行执行。统计类问题由 StructuredQueryBuilder 生成 SQL 查询结构化表，结果直接格式化返回。RAG 路径不受影响。框架可扩展，支持任意 (category, sub_category) 组合注册自己的结构化表和解析器。

**Tech Stack:** Python / SQLModel / SQLite / FastAPI / ThreadPoolExecutor

---

## 文件结构

```
backend/
  models/
    structured_definition.py   # 新增：StructuredDefinition 模型
    menu_item.py               # 新增：MenuItem 模型
  services/
    structured_query.py        # 新增：QuestionClassifier + StructuredQueryBuilder
    structured_extractor.py   # 新增：StructuredExtractor（解析器路由）
    parsers/
      menu_parser.py           # 新增：MenuParser（菜谱规则解析器）
      notice_parser.py         # 新增：NoticeParser（通知公告规则解析器）
  api/
    chat.py                    # 修改：集成两路查询路由
    structured.py              # 新增：结构化表定义管理接口
  database.py                  # 修改：新增 entity_fields 列、新表路由

data/
  key.db                       # 结构化定义表走 key.db（与 API Key 同库）
```

---

## Task 1: 数据模型

**Files:**
- Create: `backend/models/structured_definition.py`
- Create: `backend/models/menu_item.py`
- Modify: `backend/models/__init__.py`

---

- [ ] **Step 1: 创建 StructuredDefinition 模型**

Create: `backend/models/structured_definition.py`

```python
from sqlmodel import SQLModel, Field
from datetime import datetime, timezone

class StructuredDefinition(SQLModel, table=True):
    __tablename__ = "structured_definitions"

    id: str = Field(primary_key=True)  # "机关教辅_通知公告"
    category: str = Field(index=True)
    sub_category: str = Field(index=True)
    table_name: str                    # "notice_items"
    fields_schema: str = "[]"          # JSON list of field definitions
    parser_type: str = "llm"           # "rule" | "llm" | "hybrid"
    created_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
```

---

- [ ] **Step 2: 创建 MenuItem 模型**

Create: `backend/models/menu_item.py`

```python
from sqlmodel import SQLModel, Field
from datetime import datetime, timezone
import uuid

class MenuItem(SQLModel, table=True):
    __tablename__ = "menu_items"

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    doc_id: str = Field(index=True)
    category: str = ""
    sub_category: str = ""
    dish_name: str = Field(index=True)
    dish_category: str = ""   # "热菜" / "凉菜" / "主食" / "汤"
    meal_type: str = ""       # "早餐" / "午餐" / "晚餐"
    menu_date: str = Field(index=True)  # "2026-04-15"
    source_url: str = ""
    created_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
```

---

- [ ] **Step 3: 注册模型到 database.py**

Modify: `backend/database.py`

添加导入：
```python
from models.structured_definition import StructuredDefinition
from models.menu_item import MenuItem
```

在 `_session_binds` 中添加：
```python
StructuredDefinition: key_engine,
MenuItem: key_engine,
```

在 `create_db_and_tables()` 的 key_tables 添加：
```python
key_tables = [AIProvider.__table__, AICategoryScene.__table__, EmbeddingConfig.__table__,
              StructuredDefinition.__table__, MenuItem.__table__]
```

---

- [ ] **Step 4: 在 documents 表添加 entity_fields 列**

Modify: `backend/database.py` - 新增 migration 函数 `_migrate_entity_fields()`，在 `_migrate_document_columns()` 之后调用：

```python
def _migrate_entity_fields():
    """documents 表新增 entity_fields 列"""
    from sqlalchemy import text
    with crawl_engine.connect() as conn:
        try:
            result = conn.execute(text("PRAGMA table_info(documents)"))
            existing_cols = {row[1] for row in result}
        except Exception:
            existing_cols = set()
        if "entity_fields" not in existing_cols:
            conn.execute(text('ALTER TABLE documents ADD COLUMN entity_fields TEXT DEFAULT "{}"'))
            conn.commit()
```

在 `create_db_and_tables()` 最后调用此迁移。

---

- [ ] **Step 5: 提交**

```bash
git add backend/models/structured_definition.py backend/models/menu_item.py backend/database.py backend/models/__init__.py
git commit -m "feat(structured): add StructuredDefinition and MenuItem models"
```

---

## Task 2: StructuredQueryBuilder（SQL 生成层）

**Files:**
- Create: `backend/services/structured_query.py`
- Test: `tests/services/test_structured_query.py`（如果测试目录不存在则创建）

---

- [ ] **Step 1: 实现 QuestionClassifier**

Create: `backend/services/structured_query.py`

```python
import re
from typing import Literal

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
```

---

- [ ] **Step 2: 实现 StructuredQueryBuilder**

在 `structured_query.py` 中追加：

```python
from datetime import datetime, timedelta

# 日期提取：支持 "4月以来"、"4月15日"、"2026年4月" 等
DATE_RANGE_PATTERNS = [
    (r"(\d+)月(\d+)日以来", "month_day_since"),
    (r"(\d{4})年(\d{1,2})月(\d{1,2})日以来?", "full_since"),
    (r"(\d{4})年(\d{1,2})月", "year_month"),
    (r"(\d+)月以来", "month_only"),
    (r"(\d{4})-(\d{2})-(\d{2})", "iso_date"),
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


def build_structured_query(question: str, category: str, sub_category: str) -> dict | None:
    """
    根据问句和文档类型构建结构化查询。
    返回 {"sql": str, "params": list, "dimension": str, "date_col": str} 或 None。
    """
    if not category or not sub_category:
        return None

    # 日期范围
    start_date, end_date = extract_date_range(question)

    # 路由到对应表
    if sub_category == "教工食堂菜谱":
        return build_menu_query(question, start_date, end_date)

    # 其他类型暂不支持
    return None


def build_menu_query(question: str, start_date: str, end_date: str) -> dict:
    """构建菜谱统计查询"""
    # 提取 meal_type 过滤
    meal_filter = None
    for meal in ["早餐", "午餐", "晚餐"]:
        if meal in question:
            meal_filter = meal
            break

    # 提取 dish_category 过滤
    cat_filter = None
    for cat in ["热菜", "凉菜", "主食", "汤"]:
        if cat in question:
            cat_filter = cat
            break

    date_col = "menu_date"
    dimension = "dish_name"

    sql = f"""
        SELECT dish_name, COUNT(*) as cnt,
               GROUP_CONCAT(DISTINCT {date_col}) as dates
        FROM menu_items
        WHERE {date_col} >= ? AND {date_col} <= ?
    """
    params = [start_date, end_date]

    if meal_filter:
        sql += " AND meal_type = ?"
        params.append(meal_filter)
    if cat_filter:
        sql += " AND dish_category = ?"
        params.append(cat_filter)

    sql += f" GROUP BY {dimension} ORDER BY cnt DESC LIMIT 10"
    return {"sql": sql, "params": params, "dimension": dimension, "date_col": date_col}


def format_structured_result(rows: list, question: str, dimension: str) -> str:
    """将 SQL 结果格式化为自然语言回答"""
    if not rows:
        return "未找到符合条件的记录。"

    top = rows[0]
    text = f"{dimension}「{top[dimension]}」出现次数最多，共 {top['cnt']} 次，"
    dates = (top.get("dates") or "").split(",")
    if dates and dates[0]:
        text += f"提供的日期有：{', '.join(dates[:5])}"
        if len(dates) > 5:
            text += f" 等{len(dates)}天"
    return text
```

---

- [ ] **Step 3: 测试分类器**

```bash
# 在 tests/services/ 创建目录和测试文件
mkdir -p tests/services
```

Create: `tests/services/test_structured_query.py`

```python
import pytest
from backend.services.structured_query import classify, extract_date_range, build_menu_query, format_structured_result

def test_classify_stat():
    assert classify("4月以来哪个菜被提供最多") == "structured"
    assert classify("3月15日教工食堂有什么菜") == "rag"
    assert classify("4月以来哪个菜最多，哪些天提供了") == "hybrid"

def test_extract_date_range():
    start, end = extract_date_range("4月以来哪个菜被提供最多")
    assert start.startswith("2026-04")
    assert end >= start

def test_build_menu_query():
    q = build_menu_query("4月以来哪个菜被提供最多", "2026-04-01", "2026-04-15")
    assert "dish_name" in q["sql"]
    assert "GROUP BY dish_name" in q["sql"]
    assert q["params"] == ["2026-04-01", "2026-04-15"]
```

---

- [ ] **Step 4: 提交**

```bash
git add backend/services/structured_query.py tests/services/test_structured_query.py
git commit -m "feat(structured): add QuestionClassifier and StructuredQueryBuilder"
```

---

## Task 3: chat.py 集成两路查询路由

**Files:**
- Modify: `backend/api/chat.py`

---

- [ ] **Step 1: 修改 event_stream 添加结构化查询路径**

在 `backend/api/chat.py` 的 `event_stream()` 函数中，找到 Step 1 关键词提取之后，Step 2 检索之前，插入问句分类：

```python
# Step 1.5: 问句分类
from services.structured_query import classify as classify_question
classification = classify_question(user_content)
yield _emit({"type": "question_class", "classification": classification})
```

然后修改 Step 2 和 Step 3 部分，将：

```python
# Step 2: 检索文档
results = hybrid_retrieve(rewritten_q, keywords, top_k=5, date_filter=None)
```

改为：

```python
# Step 2: RAG 检索（始终执行）+ 结构化查询（分类为 structured/hybrid 时执行）
from concurrent.futures import ThreadPoolExecutor
from services.structured_query import build_structured_query, format_structured_result
import sqlite3

rag_results = []
struct_results = None
structured_answered = False

def do_rag():
    return hybrid_retrieve(rewritten_q, keywords, top_k=5, date_filter=None)

def do_structured():
    # 从 documents 表获取最近入库的 category/sub_category
    # 这里先用第一个检索结果的 category 作为查询维度
    return None  # 暂不执行，详细逻辑见下

with ThreadPoolExecutor(max_workers=2) as executor:
    rag_future = executor.submit(do_rag)
    if classification in ("structured", "hybrid"):
        struct_future = executor.submit(do_structured)
    else:
        struct_future = None

    rag_results = rag_future.result(timeout=15)
    if struct_future:
        struct_results = struct_future.result(timeout=10)
```

在生成回答前添加结构化结果判断：

```python
# Step 3: 生成回答
if classification == "structured" and struct_results:
    # 纯结构化查询，直接格式化结果
    answer = struct_results.get("answer", "抱歉，暂未找到数据")
    structured_answered = True
    gen_time = 0.0
elif classification == "hybrid" and struct_results:
    # 混合：RAG 结果 + 结构化上下文
    struct_context = struct_results.get("answer", "")
    # 将结构化结果附加到 RAG prompt
    rag_messages = build_rag_prompt(rewritten_q, rag_results,
                                   chat_history=chat_history if chat_history else None,
                                   extra_context=struct_context)
    answer = call_llm(provider_id, rag_messages)
    structured_answered = False
else:
    # 纯 RAG
    rag_messages = build_rag_prompt(rewritten_q, rag_results,
                                   chat_history=chat_history if chat_history else None)
    answer = call_llm(provider_id, rag_messages)
```

修改 `build_rag_prompt` 调用签名以支持 `extra_context`：

在 Task 4 中修改 `build_rag_prompt`，先完成 Task 4 再回到这里。

**注意：** Task 3 和 Task 4 有依赖，先完成 Task 4 再完成 Task 3 的剩余部分。

---

- [ ] **Step 2: 提交（Task 3 完成后）**

```bash
git add backend/api/chat.py
git commit -m "feat(chat): integrate structured query routing in event_stream"
```

---

## Task 4: build_rag_prompt 支持 extra_context

**Files:**
- Modify: `backend/services/rag.py`

---

- [ ] **Step 1: 修改 build_rag_prompt 函数签名**

在 `backend/services/rag.py` 中找到 `build_rag_prompt` 函数，修改签名：

```python
def build_rag_prompt(question: str, chunks: list[dict], max_tokens: int = 5000,
                     chat_history: list[dict] = None,
                     extra_context: str = None) -> list[dict]:
```

在 `docs_section` 之后、`user_content` 之前，如果 `extra_context` 有值，则追加：

```python
    if extra_context:
        docs_section += f"\n\n附加信息：\n{extra_context}\n"
```

---

- [ ] **Step 2: 提交**

```bash
git add backend/services/rag.py
git commit -m "feat(rag): build_rag_prompt supports extra_context parameter"
```

---

## Task 5: MenuParser（菜谱规则解析器）

**Files:**
- Create: `backend/services/parsers/menu_parser.py`

---

- [ ] **Step 1: 实现 MenuParser**

Create: `backend/services/parsers/__init__.py`（如果不存在）:

```python
```

Create: `backend/services/parsers/menu_parser.py`

```python
import re
import uuid
from models.menu_item import MenuItem

MEAL_TYPE_MAP = {
    "早餐": "早餐",
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
    content 是 extract_main_content() 输出的表格文本。
    格式示例：
      - 早餐
      - 番茄炒蛋
      - 红烧肉
      - 午餐
      - 宫保鸡丁
      ...
    """
    items = []
    current_meal = ""
    current_date = ""
    lines = content.split("\n")

    # 从 content 中尝试提取日期（通常在第一行或标题附近）
    date_match = re.search(r"(\d{4})[-年](\d{1,2})[-月](\d{1,2})", content)
    if date_match:
        y, m, d = date_match.groups()
        current_date = f"{y}-{int(m):02d}-{int(d):02d}"

    for line in lines:
        line = line.strip()
        if not line:
            continue

        # 跳过序号（如 "1."、"1、"）
        line_clean = re.sub(r"^\d+[.、)]\s*", "", line)
        # 跳过金额（如 "¥12.00"、"12元"）
        line_clean = re.sub(r"[\d.]+[元¥$]", "", line_clean).strip()

        # 检测餐次
        for kw, meal_type in MEAL_TYPE_MAP.items():
            if kw in line:
                current_meal = meal_type
                break

        # 检测菜品分类
        dish_category = ""
        for kw, cat in DISH_CATEGORY_MAP.items():
            if kw in line:
                dish_category = cat
                break

        # 过滤噪声行
        skip_words = ["浏览次数", "发布单位", "发布日期", "版权所有", "版权所有", "http",
                     "点击", "关闭", "打印", "保存", "栏目", "编辑", "来源", "作者"]
        if any(w in line_clean for w in skip_words):
            continue
        if len(line_clean) < 2:
            continue
        if re.match(r"^[A-Za-z]+://", line_clean):
            continue

        dish_name = line_clean
        if dish_name and current_meal:
            items.append(MenuItem(
                id=str(uuid.uuid4()),
                doc_id=doc_id,
                category=category,
                sub_category=sub_category,
                dish_name=dish_name,
                dish_category=dish_category or "热菜",  # 默认热菜
                meal_type=current_meal,
                menu_date=current_date,
                source_url=source_url,
            ))

    return items
```

---

- [ ] **Step 2: 提交**

```bash
git add backend/services/parsers/__init__.py backend/services/parsers/menu_parser.py
git commit -m "feat(structured): add MenuParser for canteen menu extraction"
```

---

## Task 6: StructuredExtractor（解析器路由 + 爬虫集成）

**Files:**
- Create: `backend/services/structured_extractor.py`

---

- [ ] **Step 1: 实现 StructuredExtractor 和解析器注册**

Create: `backend/services/structured_extractor.py`

```python
import logging
from typing import Optional
from services.parsers.menu_parser import parse_menu_content

logger = logging.getLogger(__name__)

# 解析器注册表：(category, sub_category) → parser_func
PARSER_REGISTRY = {
    ("生活服务", "教工食堂菜谱"): "menu",
    # 后续扩展：
    # ("机关教辅", "通知公告"): "notice",
    # ("*", "*"): "llm",  # 通配：其他类型走 LLM
}


def get_parser_type(category: str, sub_category: str) -> str:
    """根据 category+sub_category 查找解析器类型"""
    key = (category, sub_category)
    if key in PARSER_REGISTRY:
        return PARSER_REGISTRY[key]

    # 通配检查
    for (cat, sub), ptype in PARSER_REGISTRY.items():
        if cat == "*" or cat == category:
            if sub == "*" or sub == sub_category:
                return ptype
    return "none"


def extract_structured(doc_id: str, category: str, sub_category: str,
                      content: str, source_url: str) -> list[dict]:
    """
    入口：根据 category+sub_category 路由到对应解析器。
    返回 list[dict]，每个 dict 是一行结构化数据。
    """
    parser_type = get_parser_type(category, sub_category)

    if parser_type == "menu":
        from models.menu_item import MenuItem
        items = parse_menu_content(content, doc_id, category, sub_category, source_url)
        return [_item_to_dict(item) for item in items]

    elif parser_type == "llm":
        # TODO: Phase 3 实现
        pass

    # parser_type == "none" 或未知类型：跳过
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
    """将结构化数据写入数据库"""
    from database import create_session
    from models.menu_item import MenuItem

    if not items:
        return

    with create_session() as session:
        for item_dict in items:
            menu_item = MenuItem(**item_dict)
            session.add(menu_item)
        session.commit()
    logger.info(f"[structured] Saved {len(items)} items")


def trigger_extraction(doc_id: str, category: str, sub_category: str,
                       content: str, source_url: str):
    """
    触发结构化提取（后台线程，不阻塞爬虫主线程）。
    在 crawler.py 的 crawl_article() 中调用。
    """
    import threading
    def _do():
        try:
            items = extract_structured(doc_id, category, sub_category, content, source_url)
            save_structured_items(items)
        except Exception as e:
            logger.warning(f"[structured] Extraction failed for doc {doc_id}: {e}")
    t = threading.Thread(target=_do, daemon=True)
    t.start()
```

---

- [ ] **Step 2: 集成到 crawler.py**

Modify: `backend/services/crawler.py`，在 `crawl_article()` 函数中，文档保存后（`session.commit()` 之后）添加：

```python
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
```

---

- [ ] **Step 3: 提交**

```bash
git add backend/services/structured_extractor.py backend/services/crawler.py
git commit -m "feat(structured): add StructuredExtractor and crawler integration"
```

---

## Task 7: 验证端到端流程

**Files:**
- 无新增文件

---

- [ ] **Step 1: 手动测试验证**

启动后端服务后，用 curl 或前端测试以下场景：

**测试 1：纯 RAG 问答（不受影响）**
```
POST /api/chat/sessions/{id}/messages
{"content": "4月15日教工食堂有什么菜"}
```
预期：返回 RAG 回答（可能没有菜谱内容，因为之前内容提取失败）

**测试 2：结构化统计查询**
```
POST /api/chat/sessions/{id}/messages
{"content": "4月以来哪个菜被提供最多"}
```
预期：
- 分类为 "structured"
- 问句类型标记显示为统计
- 如果 menu_items 表有数据，返回格式化统计结果

**测试 3：混合查询**
```
POST /api/chat/sessions/{id}/messages
{"content": "4月以来哪个菜最多，这些菜营养如何"}
```
预期：分类为 "hybrid"，RAG 回答中附带结构化统计上下文

---

- [ ] **Step 2: 检查 menu_items 表数据**

如果爬虫已集成，验证是否有数据入库：

```python
# 用 python 检查
import sqlite3
conn = sqlite3.connect("data/key.db")
cur = conn.cursor()
cur.execute("SELECT COUNT(*) FROM menu_items")
print(cur.fetchone())
cur.execute("SELECT dish_name, COUNT(*) FROM menu_items GROUP BY dish_name ORDER BY COUNT(*) DESC LIMIT 5")
for row in cur.fetchall():
    print(row)
```

---

## 依赖关系

```
Task 1 (模型) ──→ Task 2 (QueryBuilder) ──→ Task 3 (chat.py集成, Task 4先完成)
Task 4 (build_rag_prompt) ──────────────────→ Task 3
Task 2 ──→ Task 5 (MenuParser)
Task 5 ──→ Task 6 (Extractor + crawler集成)
```

**执行顺序：** Task 1 → Task 2 → Task 4 → Task 3 → Task 5 → Task 6 → Task 7

---

## 自检清单

- [ ] Spec coverage: 每个 Section 都有对应 Task
- [ ] Placeholder scan: 无 TBD/TODO/placeholder 代码
- [ ] Type consistency: `build_rag_prompt` 的 `extra_context` 参数在 Task 3 和 Task 4 中一致
- [ ] Task 依赖：Task 3 在 Task 4 之后完成
