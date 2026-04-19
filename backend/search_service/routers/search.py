from fastapi import APIRouter, Depends, Query
from sqlmodel import Session, select

from database import get_session
from services.search import search_documents
from services.auth import get_current_user_from_cookie
from models.user import User
from models.document import Document

router = APIRouter()

@router.get("/recent")
def get_recent_documents(
    limit: int = Query(6, ge=1, le=20),
    current_user: User = Depends(get_current_user_from_cookie),
    session: Session = Depends(get_session),
):
    """获取最新文档，用于搜索为空时的推荐内容"""
    docs = session.exec(
        select(Document)
        .order_by(Document.updated_at.desc())
        .limit(limit)
    ).all()
    return {
        "docs": [
            {
                "id": d.id,
                "title": d.title,
                "url": d.url,
                "category": d.category or "",
                "department": d.department or "",
                "publish_date": d.publish_date or "",
            }
            for d in docs
        ]
    }

@router.get("")
def search(
    q: str = Query(..., min_length=1),
    category: str = None,
    department: str = None,
    start_date: str = None,
    end_date: str = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user_from_cookie),
):
    """搜索文档接口"""
    result = search_documents(
        query=q,
        category=category,
        department=department,
        start_date=start_date,
        end_date=end_date,
        page=page,
        page_size=page_size,
    )
    return result
