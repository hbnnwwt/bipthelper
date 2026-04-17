import logging
import time as _time
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlmodel import Session, select, delete
import uuid
from datetime import datetime, timezone
import json

from database import create_session, get_session
from models.user import User
from models.chat import ChatSession, ChatMessage
from models.point_record import PointRecord
from services.auth import get_current_user_from_cookie
from limiter import limiter

router = APIRouter()

logger = logging.getLogger(__name__)

class CreateSessionRequest(BaseModel):
    title: Optional[str] = None

class SendMessageRequest(BaseModel):
    content: str

# --- 会话管理 ---

@router.get("/sessions")
def list_sessions(
    current_user: User = Depends(get_current_user_from_cookie),
    session: Session = Depends(get_session),
):
    """返回当前用户所有会话，按 updated_at 倒序"""
    sessions = session.exec(
        select(ChatSession)
        .where(ChatSession.user_id == current_user.id)
        .order_by(ChatSession.updated_at.desc())
    ).all()
    return {
        "sessions": [
            {"id": s.id, "title": s.title, "created_at": s.created_at, "updated_at": s.updated_at}
            for s in sessions
        ]
    }

@router.post("/sessions")
def create_chat_session(
    body: CreateSessionRequest,
    current_user: User = Depends(get_current_user_from_cookie),
    session: Session = Depends(get_session),
):
    """创建新会话"""
    title = body.title or "新对话"
    new_session = ChatSession(
        id=str(uuid.uuid4()),
        user_id=current_user.id,
        title=title,
    )
    session.add(new_session)
    session.commit()
    return {"id": new_session.id, "title": new_session.title, "created_at": new_session.created_at}

@router.delete("/sessions/{session_id}")
def delete_session(
    session_id: str,
    current_user: User = Depends(get_current_user_from_cookie),
    session: Session = Depends(get_session),
):
    """删除会话及其所有消息"""
    chat_session = session.exec(
        select(ChatSession)
        .where(ChatSession.id == session_id, ChatSession.user_id == current_user.id)
    ).first()
    if not chat_session:
        raise HTTPException(status_code=404, detail="Session not found")

    session.exec(
        delete(ChatMessage).where(ChatMessage.session_id == session_id)
    )
    session.delete(chat_session)
    session.commit()
    return {"message": "Session deleted"}

@router.get("/sessions/{session_id}/messages")
def get_messages(
    session_id: str,
    current_user: User = Depends(get_current_user_from_cookie),
    session: Session = Depends(get_session),
):
    """返回会话所有消息，按 created_at 升序"""
    chat_session = session.exec(
        select(ChatSession)
        .where(ChatSession.id == session_id, ChatSession.user_id == current_user.id)
    ).first()
    if not chat_session:
        raise HTTPException(status_code=404, detail="Session not found")

    messages = session.exec(
        select(ChatMessage)
        .where(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.created_at.asc())
    ).all()
    return {
        "messages": [
            {
                "id": m.id,
                "role": m.role,
                "content": m.content,
                "sources": m.sources,
                "created_at": m.created_at,
            }
            for m in messages
        ]
    }

# --- 问答 ---

def _emit(data: dict) -> str:
    return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"

@router.post("/sessions/{session_id}/messages")
@limiter.limit("10/minute")
def send_message(
    request: Request,
    session_id: str,
    body: SendMessageRequest,
    current_user: User = Depends(get_current_user_from_cookie),
):
    """SSE 流式：逐步返回 RAG 中间结果和最终答案"""

    # 校验
    user_content = body.content.strip()
    if not user_content:
        raise HTTPException(status_code=400, detail="消息内容不能为空")
    if len(user_content) > 1000:
        raise HTTPException(status_code=400, detail="消息内容不能超过1000字")

    with create_session() as session:
        chat_session = session.exec(
            select(ChatSession)
            .where(ChatSession.id == session_id, ChatSession.user_id == current_user.id)
        ).first()
        if not chat_session:
            raise HTTPException(status_code=404, detail="Session not found")

    # 积分不足 → 也走 SSE，保持前端统一
    if current_user.points < 1:
        def _no_points():
            msg_id = str(uuid.uuid4())
            now = datetime.now(timezone.utc).isoformat()
            with create_session() as s:
                s.add(ChatMessage(id=str(uuid.uuid4()), session_id=session_id, role="user", content=user_content))
                hint = ChatMessage(id=msg_id, session_id=session_id, role="assistant",
                                   content="你的积分不足，暂时无法提问。可以通过每日签到获取积分，或联系管理员。", sources="{}")
                s.add(hint)
                cs = s.exec(select(ChatSession).where(ChatSession.id == session_id)).first()
                if cs:
                    cs.updated_at = now
                    s.add(cs)
                s.commit()
            yield _emit({"type": "answer", "content": hint.content, "sources": [], "total_time": 0})
            yield _emit({"type": "done", "id": msg_id, "created_at": now})
        return StreamingResponse(_no_points(), media_type="text/event-stream",
                                 headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

    # 预扣积分 + 保存用户消息
    with create_session() as session:
        user = session.get(User, current_user.id)
        user.points -= 1
        session.add(PointRecord(user_id=user.id, amount=-1, record_type="qa", note="问答消耗"))
        session.add(user)
        session.add(ChatMessage(id=str(uuid.uuid4()), session_id=session_id, role="user", content=user_content))
        cs = session.exec(select(ChatSession).where(ChatSession.id == session_id)).first()
        if cs:
            if not cs.title or cs.title == "新对话":
                cs.title = user_content[:30]
            cs.updated_at = datetime.now(timezone.utc).isoformat()
            session.add(cs)
        session.commit()

    # SSE 流式生成器
    def event_stream():
        from services.rag import _sanitize_question, extract_keywords, hybrid_retrieve, build_rag_prompt, rewrite_with_context, _extract_date_from_query
        from services.ai.client import call_llm, get_default_provider
        from services.structured_query import classify as classify_question, build_structured_query, format_structured_result

        total_start = _time.time()
        answer = ""
        sources = []
        fb = None
        error_occurred = False
        kw_time = None
        ret_time = None
        gen_time = None
        rewrite_time = 0
        keywords = []
        results = []

        try:
            # 加载聊天历史（用于上下文关联）
            chat_history = []
            with create_session() as hist_session:
                hist_msgs = hist_session.exec(
                    select(ChatMessage)
                    .where(ChatMessage.session_id == session_id)
                    .order_by(ChatMessage.created_at.desc())
                    .limit(6)  # 最近 3 轮（6 条消息）
                ).all()
                # 反转顺序，从旧到新
                chat_history = [
                    {"role": m.role, "content": m.content}
                    for m in reversed(hist_msgs)
                ]

            safe_q = _sanitize_question(user_content)

            # Step 0: 结合上下文扩展查询（仅在有历史时执行，轻量级 jieba 操作）
            rewrite_time = 0
            rewritten_q = safe_q
            if chat_history:
                t0 = _time.time()
                rewritten_q = rewrite_with_context(safe_q, chat_history)
                rewrite_time = round(_time.time() - t0, 3)
                if rewritten_q != safe_q:
                    yield _emit({"type": "context_expand", "original": safe_q, "expanded": rewritten_q, "time": rewrite_time})

            # Step 1: 提取关键词（使用扩展后的查询）
            yield _emit({"type": "stage", "stage": "keywords", "message": "正在提取关键词..."})
            t0 = _time.time()
            keywords, fb = extract_keywords(rewritten_q)
            kw_time = round(_time.time() - t0, 3)
            yield _emit({"type": "keywords", "keywords": keywords, "time": kw_time})

            # 提取日期用于过滤
            date_filter = _extract_date_from_query(rewritten_q)
            if date_filter:
                yield _emit({"type": "date_extracted", "date": date_filter})

            # Step 1.5: 问句分类
            classification = classify_question(user_content)
            yield _emit({"type": "question_class", "classification": classification})

            # Step 2: RAG 检索（始终执行）+ 结构化查询（分类为 structured/hybrid 时执行）
            yield _emit({"type": "stage", "stage": "retrieval", "message": "正在检索相关文档..."})
            t0 = _time.time()
            from concurrent.futures import ThreadPoolExecutor

            rag_results = []
            struct_results = None

            def do_rag():
                return hybrid_retrieve(rewritten_q, keywords, top_k=5, date_filter=None)

            def do_structured():
                doc_id = rag_results[0].get("doc_id") if rag_results else None
                if not doc_id:
                    return None
                try:
                    from database import create_session
                    from models.document import Document
                    with create_session() as session:
                        doc = session.get(Document, doc_id)
                        if not doc:
                            return None
                        category = doc.category or ""
                        sub_category = doc.sub_category or ""
                    result = build_structured_query(rewritten_q, category, sub_category)
                    if not result:
                        return None
                    sql = result["sql"]
                    params = result["params"]
                    dimension = result.get("dimension", "dish_name")
                    import sqlite3
                    from pathlib import Path
                    key_db_path = Path(__file__).parent.parent.parent / "data" / "key.db"
                    conn = sqlite3.connect(str(key_db_path))
                    conn.row_factory = sqlite3.Row
                    cur = conn.cursor()
                    cur.execute(sql, params)
                    rows = [dict(row) for row in cur.fetchall()]
                    conn.close()
                    answer_text = format_structured_result(rows, rewritten_q, dimension)
                    return {"answer": answer_text, "question": rewritten_q}
                except Exception:
                    return None

            with ThreadPoolExecutor(max_workers=2) as executor:
                rag_future = executor.submit(do_rag)
                if classification in ("structured", "hybrid"):
                    struct_future = executor.submit(do_structured)
                else:
                    struct_future = None

                rag_results = rag_future.result(timeout=15)
                if struct_future:
                    struct_results = struct_future.result(timeout=10)

            results = rag_results
            ret_time = round(_time.time() - t0, 2)
            yield _emit({"type": "retrieval", "count": len(results), "time": ret_time})

            # 处理结构化查询结果
            structured_answer = None
            if classification == "structured" and struct_results:
                structured_answer = struct_results.get("answer")
            elif classification == "hybrid" and struct_results:
                structured_answer = struct_results.get("answer")

            # Step 3: 生成回答（携带聊天历史）
            yield _emit({"type": "stage", "stage": "generating", "message": "正在生成回答..."})
            t0 = _time.time()
            provider = get_default_provider()
            provider_id = provider["id"] if provider else "openai"
            if classification == "structured" and structured_answer:
                answer = structured_answer
                gen_time = 0.0
            elif classification == "hybrid" and structured_answer:
                rag_messages = build_rag_prompt(
                    rewritten_q, results,
                    chat_history=chat_history if chat_history else None,
                    extra_context=structured_answer
                )
                answer = call_llm(provider_id, rag_messages)
            else:
                rag_messages = build_rag_prompt(
                    rewritten_q, results,
                    chat_history=chat_history if chat_history else None
                )
                answer = call_llm(provider_id, rag_messages)
            gen_time = round(_time.time() - t0, 2)

            sources = [
                {"index": i, "doc_id": r.get("doc_id", ""), "title": r.get("title", ""),
                 "url": r.get("url", ""), "snippet": r.get("content", "")[:200],
                 "score": round(r.get("final_score", r.get("norm_score", 0)), 3),
                 "source": r.get("source", "unknown"), "publish_date": r.get("publish_date")}
                for i, r in enumerate(results, 1)
            ]

            total_time = round(_time.time() - total_start, 2)
            yield _emit({
                "type": "answer", "content": answer, "sources": sources,
                "fallback": "keyword_extraction_failed" if fb else None,
                "gen_time": gen_time, "total_time": total_time,
                "timing": {"keywords": kw_time, "retrieval": ret_time, "generating": gen_time, "total": total_time, "rewrite": rewrite_time},
                "kw_detail": "、".join(keywords[:5]),
                "ret_detail": f"{len(results)} 条文档",
            })

        except Exception as e:
            logger.error(f"[chat] RAG error: {e}")
            error_occurred = True
            answer = f"回答生成失败: {str(e)[:100]}"
            yield _emit({"type": "error", "message": str(e)[:200]})

        # 保存助手消息
        msg_id = str(uuid.uuid4())
        msg_created = datetime.now(timezone.utc).isoformat()
        try:
            with create_session() as session:
                source_data = {
                    "sources": sources,
                    "fallback": fb,
                    "timing": {
                        "keywords": kw_time,
                        "retrieval": ret_time,
                        "generating": gen_time,
                        "rewrite": rewrite_time,
                        "total": round(_time.time() - total_start, 2),
                    },
                    "kw_detail": "、".join(keywords[:5]) if keywords else None,
                    "ret_detail": f"{len(results)} 条文档" if results else None,
                }
                assistant_msg = ChatMessage(
                    id=msg_id, session_id=session_id, role="assistant",
                    content=answer, sources=json.dumps(source_data, ensure_ascii=False),
                )
                session.add(assistant_msg)
                cs = session.exec(select(ChatSession).where(ChatSession.id == session_id)).first()
                if cs:
                    cs.updated_at = datetime.now(timezone.utc).isoformat()
                    session.add(cs)
                session.commit()

                # RAG 失败 → 退回积分
                if error_occurred:
                    user = session.get(User, current_user.id)
                    if user:
                        user.points += 1
                        session.add(user)
                        session.add(PointRecord(user_id=user.id, amount=1, record_type="admin_set", note="RAG失败退回"))
                        session.commit()
        except Exception as e:
            logger.error(f"[chat] Save error: {e}")

        total_time = round(_time.time() - total_start, 2)
        yield _emit({"type": "done", "id": msg_id, "created_at": msg_created,
                      "total_time": total_time, "error": error_occurred})

    return StreamingResponse(event_stream(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
