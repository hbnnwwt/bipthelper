import logging
import re
import json
import time
from typing import Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone, timedelta

from services.qdrant import search_points
from services.ai.client import call_llm

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────
# 日期提取（用于搜索过滤）
# ─────────────────────────────────────────────

# 相对时间词汇映射
_RELATIVE_DATE_MAP = {
    "今天": 0, "今日": 0, "今儿": 0,
    "明天": 1, "明日": 1, "明儿": 1, "明天": 1,
    "后天": 2, "后日": 2, "后天": 2, "大后天": 3,
    "昨天": -1, "昨日": -1, "昨儿": -1,
    "前天": -2, "前日": -2, "大前天": -3,
}

_WEEKDAY_OFFSET = {
    "周一": 0, "星期一": 0, "礼拜一": 0, "一": 0,
    "周二": 1, "星期二": 1, "礼拜二": 1, "二": 1,
    "周三": 2, "星期三": 2, "礼拜三": 2, "三": 2,
    "周四": 3, "星期四": 3, "礼拜四": 3, "四": 3,
    "周五": 4, "星期五": 4, "礼拜五": 4, "五": 4,
    "周六": 5, "星期六": 5, "礼拜六": 5, "六": 5,
    "周日": 6, "星期日": 6, "礼拜日": 6, "周天": 6, "天": 6,
}


def _extract_date_from_query(question: str) -> Optional[str]:
    """
    从用户问题中提取日期，返回 ISO 格式的日期字符串。
    支持：
    1. 绝对日期："4月15日"、"2026年4月15日"
    2. 相对日期："今天"、"明天"、"后天"、"昨天"、"前天"
    3. 下周/本周/上周："下周一"、"本周五"、"上周三"
    """
    now = datetime.now()
    today = now.date()

    # 1. 检查相对时间词汇（今天、明天等）
    for word, offset in _RELATIVE_DATE_MAP.items():
        if word in question:
            target = today + timedelta(days=offset)
            return target.isoformat()

    # 2. 检查"下周X"、"本週X"、"上週X"
    week_patterns = [
        (r"下[周个礼](一|二|三|四|五|六|天|日|末)", 7),
        (r"这?[周个礼](一|二|三|四|五|六|天|日|末)", 0),
        (r"上[周个礼](一|二|三|四|五|六|天|日|末)", -7),
    ]
    for pattern, base_offset in week_patterns:
        match = re.search(pattern, question)
        if match:
            weekday_str = match.group(1)
            if weekday_str in ("末", "日", "天"):
                weekday_str = "日"
            target_weekday = _WEEKDAY_OFFSET.get(weekday_str)
            if target_weekday is not None:
                # 计算目标日期
                days_ahead = target_weekday - today.weekday()
                if days_ahead < 0:
                    days_ahead += 7
                target = today + timedelta(days=base_offset + days_ahead)
                return target.isoformat()

    # 3. 匹配中文日期格式：YYYY年M月D日 或 M月D日
    patterns = [
        # 完整日期 "2026年4月15日"
        (r"(\d{4})年(\d{1,2})月(\d{1,2})日?",
         lambda m: f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"),
        # 只有月和日 "4月15日" → 使用当前年份
        (r"(\d{1,2})月(\d{1,2})日?",
         lambda m: f"{now.year}-{int(m.group(1)):02d}-{int(m.group(2)):02d}"),
    ]
    for pattern, formatter in patterns:
        match = re.search(pattern, question)
        if match:
            try:
                return formatter(match)
            except (ValueError, TypeError):
                pass
    return None

# ─────────────────────────────────────────────
# jieba 关键词提取（替代 LLM 调用，~50s → <100ms）
# ─────────────────────────────────────────────
_jieba = None
_jieba_analyser = None

# 启动时预加载 jieba 词典
try:
    import jieba
    import jieba.analyse
    _jieba = jieba
    _jieba_analyser = jieba.analyse
    # 预加载停用词（如果文件存在）
    import os
    stop_words_path = os.path.join("data", "stopwords.txt")
    if os.path.exists(stop_words_path):
        _jieba_analyser.set_stop_words(stop_words_path)
except Exception as e:
    logger.warning(f"[rag] jieba init failed: {e}")


# 常见停用词（jieba 默认词库不含这些，需手动过滤）
_STOP_WORDS = {
    "什么", "怎么", "为什么", "有没有", "如何", "呢", "啊", "吧", "呀",
    "的", "了", "是", "在", "和", "与", "或", "就", "都", "也",
    "有", "没有", "一个", "一些", "这个", "那个", "这些", "那些",
    "吗", "哪", "哪里", "谁", "几", "多", "少",
}


def _simple_tokenize(text: str) -> list[str]:
    """简单中文分词（jieba 不可用时的降级方案）"""
    # 移除标点符号和空格，按字/词粗略分割
    cleaned = re.sub(r'[^\w\u4e00-\u9fff]', ' ', text)
    tokens = [t.strip() for t in cleaned.split() if len(t.strip()) >= 2]
    return [t for t in tokens if t not in _STOP_WORDS][:10]


def extract_keywords(question: str) -> tuple[list[str], bool]:
    """
    用 jieba TF-IDF 提取关键词（本地，<100ms）。
    特殊处理：
    1. 先提取日期（包括相对日期如"今天"、"明天"和绝对日期如"4月15日"），避免被 jieba 拆碎
    2. 过滤常见停用词（什么、怎么、呢等）
    3. 将日期作为第一个关键词放回
    """
    try:
        if _jieba_analyser is not None:
            # 1. 提取日期（包括相对和绝对日期）
            date_str = _extract_date_from_query(question)
            # 2. 从问题中移除日期相关词汇，避免 jieba 拆碎
            text_for_jieba = question
            if date_str:
                # 移除绝对日期 "YYYY年M月D日" 或 "M月D日"
                text_for_jieba = re.sub(r"\d{4}年\d{1,2}月\d{1,2}日?", "", text_for_jieba)
                text_for_jieba = re.sub(r"\d{1,2}月\d{1,2}日?", "", text_for_jieba)
                # 移除相对日期词汇
                for word in list(_RELATIVE_DATE_MAP.keys()):
                    text_for_jieba = text_for_jieba.replace(word, "")
                # 移除"下周一"、"本周五"等
                text_for_jieba = re.sub(r"[上下本这]?[周个礼][一二三四五六天日末]", "", text_for_jieba)

            # 3. jieba TF-IDF
            keywords = _jieba_analyser.extract_tags(text_for_jieba, topK=5)

            # 4. 过滤停用词
            filtered = [k.strip() for k in keywords if k.strip() and k not in _STOP_WORDS]

            # 5. 日期作为第一个关键词
            if date_str:
                # 保留原始中文日期格式（更适合 MeiliSearch 全文匹配标题）
                dt = datetime.strptime(date_str, "%Y-%m-%d")
                cn_date = f"{dt.month}月{dt.day}日"
                if cn_date not in filtered:
                    filtered.insert(0, cn_date)

            if filtered:
                return filtered, False
    except Exception as e:
        logger.warning(f"[rag] jieba keyword extraction failed: {e}")

    # 降级方案：简单分词
    tokens = _simple_tokenize(question)
    if tokens:
        return tokens, False
    return [question], True


def rewrite_with_context(question: str, chat_history: list[dict]) -> str:
    """
    轻量级查询改写：基于历史消息做关键词扩展，不调用 LLM。
    1. 从最近历史的用户消息中提取关键词
    2. 将关键词附加到当前问题，增强检索效果
    3. 返回改写后的查询字符串
    """
    if not chat_history or len(chat_history) == 0:
        return question

    # 只取最近 2 轮用户消息
    user_msgs = [m.get("content", "") for m in chat_history[-4:] if m.get("role") == "user"]
    if not user_msgs:
        return question

    # 从历史消息中提取关键词
    history_text = " ".join(user_msgs)
    try:
        if _jieba_analyser is not None:
            history_keywords = _jieba_analyser.extract_tags(history_text, topK=5)
            # 过滤掉当前问题中已有的词
            current_words = set(extract_keywords(question)[0])
            new_keywords = [k for k in history_keywords if k not in current_words]
            if new_keywords:
                # 将新关键词附加到问题中
                return question + " " + " ".join(new_keywords[:3])
    except Exception as e:
        logger.warning(f"[rag] Context keyword extraction failed: {e}")

    return question

SYSTEM_PROMPT = """你是一个学校信息助手，基于资料回答用户问题。

规则：
1. 回答简洁自然，开头不要使用"根据现有资料""依据资料""基于参考资料"等机械表述
2. 引用资料时使用 [1]、[2] 等编号标注来源，编号对应参考资料的序号
3. 如果资料不足以回答问题，明确告知用户
4. 回答要简洁，直接给出答案
5. 回答末尾不需要列出参考文献，系统会自动生成
6. 不要在答案中重复问题"""

# Prompt 注入防御：过滤用户输入中的指令性内容
_INJECTION_PATTERNS = [
    re.compile(r"忽略[你我前上述]?所有?[的]?(指令|规则|指示|说明|提示)", re.I),
    re.compile(r"ignore[sd]?[ly]?[ing]?[eds]?[ing]?", re.I),
    re.compile(r"disregard[sd]?[ing]?", re.I),
    re.compile(r"system[:：]", re.I),
    re.compile(r"^\s*you\s+are\s+a", re.I),
    re.compile(r"^\s*你\s*是", re.I),
    re.compile(r"忘记[你前上述]?[的]?指令", re.I),
]

def _sanitize_question(question: str) -> str:
    """防御 prompt 注入：移除或转义用户输入中的指令性片段"""
    text = question
    for pattern in _INJECTION_PATTERNS:
        text = pattern.sub("[已过滤]", text)
    # 限制总长度，避免超长输入
    return text.strip()[:500]

def _estimate_tokens(text: str) -> int:
    """粗略估算 token 数（中文约 2 字符 ≈ 1 token，英文约 4 字符 ≈ 1 token）"""
    chinese = len(re.findall(r"[\u4e00-\u9fff]", text))
    ascii_len = len(re.sub(r"[\u4e00-\u9fff]", "", text))
    return chinese // 2 + ascii_len // 4

class RagError(Exception):
    """RAG 流程中的各类错误，带具体类型标识"""
    RETRIEVAL = "retrieval"
    LLM_CALL = "llm"
    def __init__(self, error_type: str, message: str):
        self.error_type = error_type
        self.message = message
        super().__init__(message)


def _compute_recency_score(publish_date: str | None) -> float:
    """根据发布日期计算时效性分数"""
    if not publish_date:
        return 0.5
    try:
        from datetime import datetime, timezone
        dt = datetime.fromisoformat(publish_date.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        days = (datetime.now(timezone.utc) - dt).days
        if days <= 30:
            return 1.0
        elif days <= 90:
            return 0.8
        elif days <= 180:
            return 0.6
        elif days <= 365:
            return 0.4
        else:
            return 0.2
    except Exception:
        return 0.5


def _keyword_search(keywords: list[str], top_k: int, date_filter: str = None) -> list[dict]:
    """关键词检索（MeiliSearch）"""
    from services.search import search_documents
    try:
        query_str = " ".join(keywords)
        start_date = None
        end_date = None
        date_range_days = 3  # 日期前后浮动天数

        if date_filter:
            dt = datetime.strptime(date_filter, "%Y-%m-%d")
            start_date_dt = dt - timedelta(days=date_range_days)
            end_date_dt = dt + timedelta(days=date_range_days)
            start_date = start_date_dt.strftime("%Y-%m-%d")
            end_date = end_date_dt.strftime("%Y-%m-%d")

        search_res = search_documents(query_str, start_date=start_date, end_date=end_date, page=1, page_size=top_k)
        results = []
        for hit in search_res.get("results", []):
            # 如果指定了日期过滤，检查 publish_date 是否在浮动范围内
            if date_filter:
                pub_date = hit.get("publish_date", "")
                # 尝试解析 ISO 格式 "2026-04-15"
                in_range = False
                if pub_date:
                    try:
                        pub_dt = datetime.strptime(pub_date[:10], "%Y-%m-%d")
                        in_range = start_date_dt <= pub_dt <= end_date_dt
                    except ValueError:
                        # 尝试中文格式 "2026年4月15日"
                        cn_match = re.match(r"(\d{4})年(\d{1,2})月(\d{1,2})日?", pub_date)
                        if cn_match:
                            y, m, d = cn_match.groups()
                            pub_dt = datetime(int(y), int(m), int(d))
                            in_range = start_date_dt <= pub_dt <= end_date_dt
                if not in_range:
                    continue
            raw_content = hit.get("content", "")
            results.append({
                "doc_id": str(hit.get("id", "")),
                "title": hit.get("title", ""),
                "url": hit.get("url", ""),
                "content": raw_content,
                "raw_score": hit.get("_rankingScore", hit.get("_relevanceScore", 1.0)),
                "source": "keyword",
                "publish_date": hit.get("publish_date"),
            })
        return results
    except Exception as e:
        logger.warning(f"[rag] MeiliSearch retrieval failed: {e}")
        return []


def _vector_search(question: str, top_k: int) -> list[dict]:
    """向量检索（Qdrant）"""
    from services.ai.embedding import generate_embedding
    try:
        query_vector = generate_embedding(question)
        raw_hits = search_points(query_vector, top_k=top_k, score_threshold=0.3)
        results = []
        for hit in raw_hits:
            payload = hit.get("payload", {})
            results.append({
                "doc_id": str(payload.get("doc_id", "")),
                "title": payload.get("title", ""),
                "url": payload.get("url", ""),
                "content": payload.get("chunk_text", ""),
                "raw_score": hit.get("score", 0.0),
                "source": "vector",
                "publish_date": payload.get("publish_date"),
            })
        return results
    except Exception as e:
        logger.warning(f"[rag] Qdrant retrieval failed: {e}")
        return []


def hybrid_retrieve(question: str, keywords: list[str], top_k: int = 5, date_filter: str = None) -> list[dict]:
    """双路混合检索：MeiliSearch 关键词 + Qdrant 向量，并行执行，合并去重，综合排序。"""
    # 并行执行两路检索
    keyword_results = []
    vector_results = []

    with ThreadPoolExecutor(max_workers=2) as executor:
        future_keyword = executor.submit(_keyword_search, keywords, top_k, date_filter)
        future_vector = executor.submit(_vector_search, question, top_k)

        keyword_results = future_keyword.result(timeout=15)  # 15s 超时
        vector_results = future_vector.result(timeout=15)

    if not keyword_results and not vector_results:
        raise RagError(RagError.RETRIEVAL, "Both keyword and vector retrieval returned no results")

    def normalize_batch(items):
        if not items:
            return items
        max_score = max(item["raw_score"] for item in items)
        if max_score > 0:
            for item in items:
                item["norm_score"] = item["raw_score"] / max_score
        else:
            for item in items:
                item["norm_score"] = 0.0
        return items

    normalize_batch(keyword_results)
    normalize_batch(vector_results)

    merged = {}
    for item in keyword_results + vector_results:
        doc_id = item["doc_id"]
        if not doc_id:
            continue
        if doc_id in merged:
            existing = merged[doc_id]
            if item["norm_score"] > existing["norm_score"]:
                item["source"] = "both"
                merged[doc_id] = item
            else:
                existing["source"] = "both"
        else:
            merged[doc_id] = item

    for item in merged.values():
        recency = _compute_recency_score(item.get("publish_date"))
        item["final_score"] = item["norm_score"] * 0.6 + recency * 0.4

    sorted_results = sorted(merged.values(), key=lambda x: x["final_score"], reverse=True)
    return sorted_results[:8]


def retrieve_chunks(query: str, top_k: int = 3, score_threshold: float = 0.5) -> list[dict]:
    """从 Qdrant 检索最相关的文档块"""
    from services.ai.embedding import generate_embedding
    try:
        query_vector = generate_embedding(query)
        return search_points(query_vector, top_k=top_k, score_threshold=score_threshold)
    except Exception as e:
        logger.error(f"[rag] Vector retrieval failed for query '{query[:50]}': {e}")
        raise RagError(RagError.RETRIEVAL, str(e)) from e

def build_rag_prompt(question: str, chunks: list[dict], max_tokens: int = 5000,
                     chat_history: list[dict] = None,
                     extra_context: str = None) -> list[dict]:
    """构建 RAG 消息列表（system + user），按综合分数排序，带编号的引用式格式。
    如果提供 chat_history，会在问题前附加对话上下文。"""
    if not chunks:
        return [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"问题：{question}\n\n抱歉，知识库中没有找到相关内容。"},
        ]

    docs_parts = []
    current_tokens = 0
    for i, chunk in enumerate(chunks, 1):
        content_text = chunk.get("content", "")
        title = chunk.get("title", "")
        url = chunk.get("url", "")
        header = f"[{i}] 标题：{title} | URL：{url}\n"
        body = f"内容：{content_text}\n"
        section = header + body
        section_tokens = _estimate_tokens(section)

        if current_tokens + section_tokens > max_tokens - 200:
            remaining = max_tokens - current_tokens - _estimate_tokens(header) - 50
            if remaining > 100:
                docs_parts.append(header + f"内容：{content_text[:remaining * 2]}\n")
                current_tokens += remaining
            break

        docs_parts.append(section)
        current_tokens += section_tokens

    docs_section = "参考资料：\n" + "\n".join(docs_parts)

    if extra_context:
        docs_section += f"\n\n附加信息：\n{extra_context}\n"

    # 附加聊天历史上下文
    context_prefix = ""
    if chat_history:
        recent = chat_history[-3:]  # 最近 3 轮
        history_lines = []
        for m in recent:
            role_label = "用户" if m.get("role") == "user" else "助手"
            history_lines.append(f"{role_label}: {m.get('content', '')[:150]}")
        context_prefix = "对话历史：\n" + "\n".join(history_lines) + "\n\n"

    user_content = f"{docs_section}\n---\n{context_prefix}问题：{question}"

    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_content},
    ]

def answer_question(question: str, provider_id: str = None,
                    top_k: int = 5, score_threshold: float = 0.3) -> dict:
    """
    混合检索 RAG 问答：关键词提取 → 双路检索 → 合并 → LLM 生成引用式回答。
    返回 {"answer": str, "sources": list, "fallback": str | None}
    """
    safe_question = _sanitize_question(question)

    keywords, fallback = extract_keywords(safe_question)

    # 提取日期用于过滤
    date_filter = _extract_date_from_query(safe_question)
    if date_filter:
        logger.info(f"[rag] Date extracted: {date_filter}")

    # 使用默认 provider
    if provider_id is None:
        from services.ai.client import get_default_provider
        default = get_default_provider()
        provider_id = default["id"] if default else "openai"

    try:
        results = hybrid_retrieve(safe_question, keywords, top_k=top_k, date_filter=None)
    except Exception as e:
        logger.error(f"[rag] Hybrid retrieval failed: {e}")
        raise RagError(RagError.RETRIEVAL, str(e)) from e

    messages = build_rag_prompt(safe_question, results)

    try:
        answer = call_llm(provider_id, messages)
    except Exception as e:
        logger.error(f"[rag] LLM call failed: {e}")
        raise RagError(RagError.LLM_CALL, str(e)) from e

    sources = [
        {
            "index": i,
            "doc_id": r.get("doc_id", ""),
            "title": r.get("title", ""),
            "url": r.get("url", ""),
            "snippet": r.get("content", "")[:200],
            "score": round(r.get("final_score", r.get("norm_score", 0)), 3),
            "source": r.get("source", "unknown"),
            "publish_date": r.get("publish_date"),
        }
        for i, r in enumerate(results, 1)
    ]

    return {
        "answer": answer,
        "sources": sources,
        "fallback": "keyword_extraction_failed" if fallback else None,
    }
