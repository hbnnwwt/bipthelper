from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from database import get_session
from models.user import User
from services.auth import get_current_admin

router = APIRouter()


@router.get("/users")
def list_users(
    current_admin: User = Depends(get_current_admin),
    session: Session = Depends(get_session),
):
    """列出所有用户（crawler_service 最小化实现）"""
    users = session.exec(select(User)).all()
    return {
        "users": [
            {"id": u.id, "username": u.username, "role": u.role, "is_active": u.is_active, "points": u.points, "created_at": u.created_at}
            for u in users
        ]
    }
