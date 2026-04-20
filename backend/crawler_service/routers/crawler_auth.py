from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.responses import JSONResponse
from sqlmodel import Session, select

from database import get_session
from models.user import User
from services.auth import verify_password, create_access_token, get_current_user_from_cookie

router = APIRouter()


@router.post("/login")
def login(
    request: Request,
    form_data: OAuth2PasswordRequestForm = Depends(),
    session: Session = Depends(get_session),
):
    """登录（crawler_service 专用）"""
    user = session.exec(select(User).where(User.username == form_data.username)).first()
    if not user or not verify_password(form_data.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Incorrect username or password")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="User account is inactive")

    token = create_access_token(data={"sub": user.username})
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    response = JSONResponse({
        "user": {"id": user.id, "username": user.username, "role": user.role},
        "token": token,
        "points": user.points,
        "last_checkin_date": user.last_checkin_date,
        "checked_in_today": user.last_checkin_date == today,
    })
    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        max_age=7 * 24 * 60 * 60,
        samesite="lax",
    )
    return response


@router.get("/me")
def get_me(
    current_user: User = Depends(get_current_user_from_cookie),
):
    """获取当前用户信息"""
    return {
        "id": current_user.id,
        "username": current_user.username,
        "role": current_user.role,
        "points": current_user.points,
    }


@router.post("/logout")
def logout():
    """登出"""
    response = JSONResponse({"message": "ok"})
    response.delete_cookie("access_token")
    return response
