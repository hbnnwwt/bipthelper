from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Header
from typing import Optional
from pydantic import BaseModel
from sqlmodel import Session, select

from database import get_session
from models.document import Document
from config import get_settings
from services.search import index_document, delete_document_from_index

router = APIRouter()
settings = get_settings()


class DocumentIngest(BaseModel):
    """来自 bipt_info_organizer 的文档推送格式"""
    id: str
    title: str
    url: Optional[str] = ""
    content: Optional[str] = ""
    parent_category: Optional[str] = ""
    sub_category: Optional[str] = ""
    category: Optional[str] = ""
    department: Optional[str] = ""
    publish_date: Optional[str] = ""
    ai_suggested_categories: Optional[str] = ""
    ai_status: str = "pending"


def verify_organizer_key(x_organizer_key: str = Header(None)):
    if not settings.ORGANIZER_API_KEY:
        raise HTTPException(status_code=503, detail="Organizer API not configured")
    if x_organizer_key != settings.ORGANIZER_API_KEY:
        raise HTTPException(status_code=403, detail="Invalid organizer key")


@router.post("/documents")
def ingest_document(
    doc: DocumentIngest,
    session: Session = Depends(get_session),
    _: None = Depends(verify_organizer_key),
):
    """接收来自 bipt_info_organizer 的文档并建立索引"""
    existing = session.get(Document, doc.id)
    if existing:
        for key, value in doc.model_dump().items():
            if value is not None:
                setattr(existing, key, value)
        existing.updated_at = datetime.now(timezone.utc)
        session.add(existing)
        session.commit()
        index_document(existing)
        return {"message": "Document updated", "id": doc.id}

    db_doc = Document(**doc.model_dump())
    db_doc.updated_at = datetime.now(timezone.utc)
    session.add(db_doc)
    session.commit()
    index_document(db_doc)
    return {"message": "Document ingested", "id": doc.id}


@router.put("/documents/{doc_id}")
def update_document(
    doc_id: str,
    data: dict,
    session: Session = Depends(get_session),
    _: None = Depends(verify_organizer_key),
):
    """更新文档分类/元数据"""
    doc = session.get(Document, doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    for key, value in data.items():
        if hasattr(doc, key) and value is not None:
            setattr(doc, key, value)
    doc.updated_at = datetime.now(timezone.utc)
    session.add(doc)
    session.commit()
    delete_document_from_index(doc_id)
    index_document(doc)
    return {"message": "Document updated", "id": doc_id}


@router.delete("/documents/{doc_id}")
def delete_document(
    doc_id: str,
    session: Session = Depends(get_session),
    _: None = Depends(verify_organizer_key),
):
    """删除文档"""
    doc = session.get(Document, doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    delete_document_from_index(doc_id)
    session.delete(doc)
    session.commit()
    return {"message": "Document deleted", "id": doc_id}


@router.post("/documents/{doc_id}/approve")
def approve_document(
    doc_id: str,
    categories: Optional[str] = None,
    session: Session = Depends(get_session),
    _: None = Depends(verify_organizer_key),
):
    """采纳 AI 分类建议"""
    doc = session.get(Document, doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    target = categories if categories else doc.ai_suggested_categories
    if not target:
        raise HTTPException(status_code=400, detail="No suggested categories")
    doc.category = target
    doc.ai_status = "success"
    doc.ai_reviewed_at = datetime.now(timezone.utc).isoformat()
    session.add(doc)
    session.commit()
    delete_document_from_index(doc_id)
    index_document(doc)
    return {"message": "Category approved", "category": target}


@router.get("/documents/categories")
def get_categories(
    session: Session = Depends(get_session),
    _: None = Depends(verify_organizer_key),
):
    """获取分类筛选数据"""
    parent_cats = session.exec(
        select(Document.parent_category)
        .where(Document.parent_category.isnot(None))
        .where(Document.parent_category != "")
        .distinct()
    ).all()
    sub_cats = session.exec(
        select(Document.sub_category)
        .where(Document.sub_category.isnot(None))
        .where(Document.sub_category != "")
        .distinct()
    ).all()
    cats = session.exec(
        select(Document.category)
        .where(Document.category.isnot(None))
        .where(Document.category != "")
        .distinct()
    ).all()
    return {
        "parent_categories": sorted(set(parent_cats)),
        "sub_categories": sorted(set(sub_cats)),
        "categories": sorted(set(cats)),
    }