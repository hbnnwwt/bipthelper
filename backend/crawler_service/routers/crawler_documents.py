import csv
import io
import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlmodel import Session, select, func, col

from database import get_session
from models.document import Document
from models.user import User
from services.auth import get_current_admin
from services.audit import add_audit_log
from services.search import delete_document_from_index, index_document

router = APIRouter()
logger = logging.getLogger(__name__)


class BulkDeleteRequest(BaseModel):
    ids: list[str]


@router.get("/documents/categories")
def get_document_categories(
    current_admin: User = Depends(get_current_admin),
    session: Session = Depends(get_session),
):
    """获取所有可用的文档分类列表（用于筛选器）"""
    parent_cats = session.exec(
        select(col(Document.parent_category))
        .where(col(Document.parent_category).isnot(None))
        .where(col(Document.parent_category) != "")
        .distinct()
    ).all()
    sub_cats = session.exec(
        select(col(Document.sub_category))
        .where(col(Document.sub_category).isnot(None))
        .where(col(Document.sub_category) != "")
        .distinct()
    ).all()
    cats = session.exec(
        select(col(Document.category))
        .where(col(Document.category).isnot(None))
        .where(col(Document.category) != "")
        .distinct()
    ).all()
    return {
        "parent_categories": sorted(set(parent_cats)),
        "sub_categories": sorted(set(sub_cats)),
        "categories": sorted(set(cats)),
    }


@router.get("/documents")
def list_documents(
    page: int = 1,
    page_size: int = 20,
    category: Optional[str] = None,
    parent_category: Optional[str] = None,
    keyword: Optional[str] = None,
    ai_status: Optional[str] = None,
    sort: Optional[str] = "updated_desc",
    current_admin: User = Depends(get_current_admin),
    session: Session = Depends(get_session),
):
    """列出已爬取的文档，支持分页、分类过滤、关键词搜索和排序"""
    if sort == "updated_asc":
        order_col = Document.updated_at.asc()
    elif sort == "publish_desc":
        order_col = Document.publish_date.desc().nullslast()
    elif sort == "publish_asc":
        order_col = Document.publish_date.asc().nullslast()
    else:
        order_col = Document.updated_at.desc()

    count_query = select(func.count()).select_from(Document)
    if category:
        count_query = count_query.where(Document.category == category)
    if parent_category:
        count_query = count_query.where(Document.parent_category == parent_category)
    if keyword:
        count_query = count_query.where(Document.title.contains(keyword))
    if ai_status:
        count_query = count_query.where(Document.ai_status == ai_status)
    total = session.exec(count_query).one()

    query = select(Document)
    if category:
        query = query.where(Document.category == category)
    if parent_category:
        query = query.where(Document.parent_category == parent_category)
    if keyword:
        query = query.where(Document.title.contains(keyword))
    if ai_status:
        query = query.where(Document.ai_status == ai_status)
    query = query.order_by(order_col)
    docs = session.exec(query.offset((page - 1) * page_size).limit(page_size)).all()
    return {
        "docs": [
            {
                "id": d.id,
                "title": d.title,
                "url": d.url,
                "category": d.category or "",
                "parent_category": d.parent_category or "",
                "sub_category": d.sub_category or "",
                "ai_status": d.ai_status,
                "ai_suggested_categories": d.ai_suggested_categories or "",
                "department": d.department or "",
                "publish_date": d.publish_date or "",
                "updated_at": d.updated_at,
            }
            for d in docs
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.get("/documents/export")
def export_documents(
    category: Optional[str] = None,
    parent_category: Optional[str] = None,
    keyword: Optional[str] = None,
    ai_status: Optional[str] = None,
    sort: Optional[str] = "updated_desc",
    current_admin: User = Depends(get_current_admin),
    session: Session = Depends(get_session),
):
    """导出文档为 CSV（支持过滤和排序）"""
    if sort == "updated_asc":
        order_col = Document.updated_at.asc()
    elif sort == "publish_desc":
        order_col = Document.publish_date.desc().nullslast()
    elif sort == "publish_asc":
        order_col = Document.publish_date.asc().nullslast()
    else:
        order_col = Document.updated_at.desc()

    query = select(Document)
    if category:
        query = query.where(Document.category == category)
    if parent_category:
        query = query.where(Document.parent_category == parent_category)
    if keyword:
        query = query.where(Document.title.contains(keyword))
    if ai_status:
        query = query.where(Document.ai_status == ai_status)
    query = query.order_by(order_col)
    docs = session.exec(query).all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["标题", "URL", "大类", "小类", "分类", "AI状态", "AI建议分类", "发布单位", "发布日期", "更新时间"])
    for d in docs:
        writer.writerow([
            d.title, d.url, d.parent_category or "", d.sub_category or "",
            d.category or "", d.ai_status, d.ai_suggested_categories or "",
            d.department or "", d.publish_date or "", d.updated_at,
        ])
    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=documents.csv"},
    )


@router.delete("/documents/{doc_id}")
def delete_document(
    doc_id: str,
    current_admin: User = Depends(get_current_admin),
    session: Session = Depends(get_session),
):
    """删除单个文档"""
    doc = session.get(Document, doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    delete_document_from_index(doc_id)
    session.delete(doc)
    session.commit()
    add_audit_log(current_admin.id, current_admin.username, "delete_doc", doc_id, f"删除文档: {doc.title[:30]}", session)
    return {"message": "Document deleted"}


@router.delete("/documents")
def delete_documents(
    req: BulkDeleteRequest = None,
    current_admin: User = Depends(get_current_admin),
    session: Session = Depends(get_session),
):
    """批量删除文档"""
    id_list = req.ids if req else []
    deleted_count = 0
    for doc_id in id_list:
        doc = session.get(Document, doc_id)
        if doc:
            delete_document_from_index(doc_id)
            session.delete(doc)
            deleted_count += 1
    session.commit()
    add_audit_log(current_admin.id, current_admin.username, "batch_delete_docs", None, f"批量删除 {len(id_list)} 个文档", session)
    return {"message": f"Deleted {deleted_count} documents", "deleted": deleted_count}


@router.post("/documents/{doc_id}/approve")
def approve_document_category(
    doc_id: str,
    categories: Optional[str] = None,
    current_admin: User = Depends(get_current_admin),
    session: Session = Depends(get_session),
):
    """采纳 AI 分类建议"""
    doc = session.get(Document, doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    if categories:
        target = categories
    elif doc.ai_suggested_categories:
        target = doc.ai_suggested_categories
    else:
        raise HTTPException(status_code=400, detail="No category to approve")
    doc.category = target
    doc.ai_status = "success"
    session.add(doc)
    session.commit()
    delete_document_from_index(doc_id)
    index_document(doc)
    add_audit_log(current_admin.id, current_admin.username, "approve_category", doc_id, f"采纳AI分类: {target}", session)
    return {"message": "Category approved", "category": target}


@router.put("/documents/{doc_id}/category")
def update_document_category(
    doc_id: str,
    category: str,
    current_admin: User = Depends(get_current_admin),
    session: Session = Depends(get_session),
):
    """手动更新文档分类"""
    doc = session.get(Document, doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    doc.category = category
    doc.ai_status = "success"
    session.add(doc)
    session.commit()
    delete_document_from_index(doc_id)
    index_document(doc)
    add_audit_log(current_admin.id, current_admin.username, "update_category", doc_id, f"手动分类: {category}", session)
    return {"message": "Category updated", "category": doc.category}


@router.get("/audit")
def list_audit_logs(
    page: int = 1,
    page_size: int = 50,
    action: Optional[str] = None,
    current_admin: User = Depends(get_current_admin),
    session: Session = Depends(get_session),
):
    """获取审计日志"""
    from models.audit_log import AuditLog as AL
    count_query = select(func.count()).select_from(AL)
    if action:
        count_query = count_query.where(AL.action == action)
    total = session.exec(count_query).one()

    query = select(AL)
    if action:
        query = query.where(AL.action == action)
    query = query.order_by(AL.created_at.desc())
    logs = session.exec(query.offset((page - 1) * page_size).limit(page_size)).all()

    return {
        "logs": [
            {
                "id": log.id,
                "username": log.username,
                "action": log.action,
                "target": log.target or "",
                "detail": log.detail or "",
                "created_at": log.created_at,
            }
            for log in logs
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
    }