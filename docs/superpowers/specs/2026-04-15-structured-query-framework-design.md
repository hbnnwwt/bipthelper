# 通用结构化查询框架设计

**日期：** 2026-04-15
**状态：** 已确认

## 背景

当前系统是纯 RAG 架构，只能回答"根据文档内容回答"的问题，无法处理统计类查询（如"4月以来哪个菜被提供最多"）。需要新增一套结构化查询框架，支持任意文档类型的统计、聚合、分析类问题，同时保留现有 RAG 能力。

## 设计目标

1. 通用结构化查询框架，可扩展到任何文档类型
2. 统计类查询走 SQL，不走 LLM 生成
3. 现有 RAG 问答不受影响，两路并行执行
4. 用户无感知，问句分类器自动路由

## 整体架构

```
用户问句
    │
    ▼
┌─────────────────────────┐
│  问句分类器               │
│  (关键词 + 意图识别)       │
└──────┬──────────────────┘
       ├─ RAG 类问题 ──→ hybrid_retrieve → LLM 生成
       │
       └─ 统计类问题 ──→ 结构化查询路由 ──→ SQL 执行 ─┐
                                                       │
                                            LLM 综合回答（可选）
```

**核心原则：**
- 问句分类器决定走 RAG 还是 SQL，两路并行
- 结构化层完全独立于 RAG 层，结果可合并
- 每个 `(category, sub_category)` 组合映射到一个结构化表

---

## 1. 数据层设计

### 1.1 文档原始字段扩展

`documents` 表新增 `entity_fields` JSONB 列，存储该文档的结构化提取结果原始 JSON。

```sql
ALTER TABLE documents ADD COLUMN entity_fields TEXT DEFAULT "{}";
```

### 1.2 结构化定义注册表

所有结构化表的元数据在此注册，用于路由和 schema 感知。

```sql
CREATE TABLE structured_definitions (
    id TEXT PRIMARY KEY,           -- 如 "机关教辅_通知公告"
    category TEXT NOT NULL,
    sub_category TEXT NOT NULL,
    table_name TEXT NOT NULL,      -- 如 "notice_items"
    fields_schema TEXT NOT NULL,  -- JSON: [{"name": "effective_date", "type": "date"}, ...]
    parser_type TEXT DEFAULT "llm",  -- "rule" | "llm" | "hybrid"
    created_at TEXT,
    UNIQUE(category, sub_category)
);
```

### 1.3 每种文档类型的结构化表

每个 `(category, sub_category)` 组合有独立的结构化表，SQL 聚合高效。

**示例：`menu_items`（教工食堂菜谱）**

```sql
CREATE TABLE menu_items (
    id TEXT PRIMARY KEY,
    doc_id TEXT,                   -- 关联 documents.id
    category TEXT,
    sub_category TEXT,
    dish_name TEXT NOT NULL,       -- "番茄炒蛋"
    dish_category TEXT,            -- "热菜" / "凉菜" / "主食"
    meal_type TEXT,               -- "早餐" / "午餐" / "晚餐"
    menu_date TEXT,               -- 菜谱日期 "2026-04-15"
    source_url TEXT,
    created_at TEXT
);
```

**示例：`notice_items`（通知公告）**

```sql
CREATE TABLE notice_items (
    id TEXT PRIMARY KEY,
    doc_id TEXT,
    category TEXT,
    sub_category TEXT,
    title TEXT,
    issuer TEXT,
    effective_date TEXT,
    source_url TEXT,
    created_at TEXT
);
```

---

## 2. 解析器架构

### 2.1 三层解析器

```
爬虫文档入库
    │
    ▼
┌─────────────────────────────────┐
│  StructuredExtractor            │
│  1. 查 structured_definitions   │
│  2. 根据 category+sub_category  │
│     路由到对应解析器             │
└────────────┬────────────────────┘
             │
     ┌───────┴───────┐
     ▼               ▼
 RuleParser     LLMParser
 (规则提取)    (LLM 提取)
     │               │
     └───────┬───────┘
             ▼
     写入对应结构化表
```

### 2.2 解析器注册机制

```python
PARSERS = {
    ("机关教辅", "通知公告"): NoticeParser(),       # 规则：从 meta 提取 issuer/effective_date
    ("生活服务", "教工食堂菜谱"): MenuParser(),     # 规则：从表格提取 dish_name/meal_type
    ("教学科研", "*"): GenericLLMParser(),           # 通配：其他类型走 LLM
}
```

### 2.3 RuleParser 实现

**MenuParser（菜谱）：**
- 解析 `extract_main_content()` 输出的表格文本
- 用规则匹配 "早餐"、"午餐"、"晚餐" 分类
- 从菜名行提取菜名，去除序号、金额等噪音

**NoticeParser（通知公告）：**
- 从 `meta` 中提取 `issuer`（发布单位）
- 从标题或正文提取 `effective_date`（生效日期）

### 2.4 LLMParser 实现

对无规则解析器的类型，调用 LLM 提取结构化字段：

```python
{
    "model": "xxx",
    "messages": [
        {"role": "system", "content": "你是结构化信息提取器..."},
        {"role": "user", "content": f"从以下文档提取JSON：\n{content}"}
    ]
}
```

---

## 3. 问句分类器

```python
def classify(question: str) -> str:
    """
    返回: "rag" | "structured" | "hybrid"

    规则：
    - 统计类关键词：最多、最少、哪个、哪天、连续、一共、统计
    - RAG 类关键词：是什么、如何、怎样、为什么
    - 两者皆有：hybrid
    """
```

---

## 4. 路由与查询层

### 4.1 QuestionRouter

```python
def route(question: str) -> str:
    classification = classify(question)
    if classification == "rag":
        return "rag"
    elif classification == "structured":
        return "structured"
    else:
        return "hybrid"  # 两路都执行，结果合并
```

### 4.2 StructuredQueryBuilder

从问句中提取查询条件，生成 SQL：

```python
# 提取日期范围："4月以来" → ("2026-04-01", "2026-04-15")
date_range = extract_date_range(question)

# 提取聚合维度："哪个菜被提供最多" → "dish_name"
dimension = extract_aggregation_dimension(question)

# 提取过滤条件："午餐" → meal_type = "午餐"
filters = extract_filters(question)

# 生成 SQL
sql = f"SELECT {dimension}, COUNT(*) as cnt, GROUP_CONCAT({date_col}) as dates FROM {table} WHERE ..."
```

### 4.3 查询结果格式化

```json
{
    "type": "stat",
    "question": "4月以来哪个菜被提供最多",
    "sql": "SELECT dish_name, COUNT(*) as cnt FROM menu_items WHERE ...",
    "result": [
        {"dish_name": "番茄炒蛋", "count": 12, "dates": ["4-01","4-03","4-08",...]},
        {"dish_name": "红烧肉", "count": 8, "dates": [...]}
    ]
}
```

---

## 5. 现有系统集成

### 5.1 爬虫集成

`crawl_article()` 函数中，文档保存后：

```python
# 后台线程触发结构化提取（不阻塞爬虫主线程）
def _extract_structured(doc_id, category, sub_category, content):
    extractor = get_extractor(category, sub_category)
    entities = extractor.extract(content)
    save_structured(doc_id, entities)
```

### 5.2 对话 API 集成

`chat.py` 的 `event_stream()` 中：

```python
classification = classify(user_content)

# RAG 路径（始终执行）
rag_future = executor.submit(hybrid_retrieve, ...)

# 结构化路径（分类为 structured 或 hybrid 时执行）
struct_future = None
if classification in ("structured", "hybrid"):
    struct_future = executor.submit(structured_query, user_content)

# 等待结果，分类生成
rag_results = rag_future.result()
struct_results = struct_future.result() if struct_future else None

if classification == "rag":
    answer = call_llm(rag_messages)
elif classification == "structured":
    answer = format_structured_answer(struct_results)
else:  # hybrid
    answer = call_llm(rag_messages, structured_context=struct_results)
```

---

## 6. 不支持的文档类型

对于还没有定义结构化表的 `(category, sub_category)`，统计类问题返回：
> "抱歉，[分类名称] 类内容暂不支持统计查询，请联系管理员配置提取规则。"

不阻塞 RAG 问答，现有功能不受影响。

---

## 7. 数据库变更

| 操作 | 文件 |
|------|------|
| 新增 `structured_definitions` 表 | `database.py` |
| 新增各类型结构化表（如 `menu_items`） | 单独 migration |
| `documents` 表新增 `entity_fields` 列 | `database.py` |
| 新增 `key.db` 路由 | `database.py` |

---

## 8. 文件变更清单

| 层级 | 文件 | 变更 |
|------|------|------|
| Model | `models/structured_definition.py` | 新增 `StructuredDefinition` 模型 |
| Model | `models/menu_item.py` | 新增 `MenuItem` 模型 |
| Service | `services/structured_extractor.py` | 新增 `StructuredExtractor`、`RuleParser`、`LLMParser` |
| Service | `services/structured_query.py` | 新增 `QuestionClassifier`、`StructuredQueryBuilder` |
| Service | `services/parsers/menu_parser.py` | 新增 `MenuParser` |
| Service | `services/parsers/notice_parser.py` | 新增 `NoticeParser` |
| API | `api/chat.py` | 集成两路查询路由 |
| Database | `database.py` | 新增 `entity_fields` 列、新表路由到 `key.db` |
| API | `api/structured.py` | 新增管理接口（配置结构化表定义） |

---

## 9. 迁移计划

**Phase 1（基础框架）：**
- 新增 `structured_definitions` 表
- 实现 `QuestionClassifier`
- 实现 `StructuredQueryBuilder`（SQL 生成）
- 集成进 `chat.py` 路由
- RAG 路径照常，结构化路径返回格式化的 SQL 结果

**Phase 2（菜谱解析）：**
- 新增 `menu_items` 表
- 实现 `MenuParser`（规则解析表格内容）
- 爬虫集成触发结构化提取
- 验证 "4月以来哪个菜被提供最多" 类问题

**Phase 3（扩展）：**
- 新增 `notice_items` 表
- 实现 `NoticeParser`
- 实现 `LLMParser` 作为通配解析器
- 管理接口：增删结构化表定义
