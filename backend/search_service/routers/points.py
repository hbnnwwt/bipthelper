from fastapi import APIRouter, Depends, HTTPException, Request
from sqlmodel import Session, select
from sqlalchemy import func
from pydantic import BaseModel
from datetime import datetime, timezone

from database import get_session
from limiter import limiter
from models.user import User
from models.point_record import PointRecord
from services.auth import get_current_user_from_cookie

router = APIRouter()

@router.post("/checkin")
@limiter.limit("5/minute")
def checkin(
    request: Request,
    current_user: User = Depends(get_current_user_from_cookie),
    session: Session = Depends(get_session),
):
    """每日签到"""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    if current_user.last_checkin_date == today:
        raise HTTPException(status_code=400, detail="今日已签到")

    current_user.points += 5
    current_user.last_checkin_date = today
    record = PointRecord(
        user_id=current_user.id,
        amount=5,
        record_type="checkin",
        note="每日签到",
    )
    session.add(record)
    session.add(current_user)
    try:
        session.commit()
        session.refresh(current_user)
    except Exception:
        session.rollback()
        raise HTTPException(status_code=400, detail="签到失败，请重试")

    return {
        "points": current_user.points,
        "checked_in_today": True,
        "earned": 5,
    }

class PointRecordResponse(BaseModel):
    id: str
    amount: int
    record_type: str
    note: str
    created_at: str

class PaginatedRecords(BaseModel):
    records: list[PointRecordResponse]
    total: int
    page: int
    page_size: int

@router.get("/records", response_model=PaginatedRecords)
def list_records(
    page: int = 1,
    page_size: int = 20,
    current_user: User = Depends(get_current_user_from_cookie),
    session: Session = Depends(get_session),
):
    """积分明细（当前用户）"""
    offset = (page - 1) * page_size
    query = (
        select(PointRecord)
        .where(PointRecord.user_id == current_user.id)
        .order_by(PointRecord.created_at.desc())
    )
    total = session.scalar(select(func.count()).where(PointRecord.user_id == current_user.id))
    records = session.exec(query.offset(offset).limit(page_size)).all()
    return {
        "records": [
            {
                "id": r.id,
                "amount": r.amount,
                "record_type": r.record_type,
                "note": r.note,
                "created_at": r.created_at,
            }
            for r in records
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
    }
