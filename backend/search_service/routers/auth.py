import os
from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, Body, Depends, HTTPException, Request, UploadFile, File, Header, Cookie
from fastapi.responses import JSONResponse
from fastapi.security import OAuth2PasswordRequestForm
from sqlmodel import Session, select

from database import get_session
from limiter import limiter
from models.invite_code import InviteCode
from models.point_record import PointRecord
from models.user import User
from services.auth import hash_password, verify_password, create_access_token, get_current_user_from_cookie
from services.invite import generate_username, is_valid_username, code_status

router = APIRouter()

@router.post("/register")
@limiter.limit("5/minute")
def register(
    request: Request,
    password: str = Body(..., embed=True),
    invite_code: str = Body(..., embed=True),
    username: Optional[str] = Body(None, embed=True),
    session: Session = Depends(get_session),
):

    # 1. 激活码存在性校验
    code_record = session.get(InviteCode, invite_code)
    if not code_record:
        raise HTTPException(status_code=400, detail="激活码不存在")

    # 2. 状态校验（used / expired）
    status = code_status(code_record)
    if status == "used":
        raise HTTPException(status_code=400, detail="激活码已被使用")
    if status == "expired":
        raise HTTPException(status_code=400, detail="激活码已过期")

    # 3. designated 类型：username 必须匹配
    final_username = username
    if code_record.code_type == "designated":
        if not final_username or final_username.strip() != code_record.designated_username:
            raise HTTPException(status_code=400, detail="激活码与用户名不匹配")
        final_username = final_username.strip()
    else:  # anonymous
        if final_username:
            final_username = final_username.strip()
            if not is_valid_username(final_username):
                raise HTTPException(status_code=400, detail="用户名最少6位字母数字组合")
            # 检查全局唯一
            existing = session.exec(select(User).where(User.username == final_username)).first()
            if existing:
                raise HTTPException(status_code=400, detail="该用户名已被占用")
        else:
            # 自动生成
            final_username = generate_username()
            # 极低概率重复，再生成一次
            existing = session.exec(select(User).where(User.username == final_username)).first()
            if existing:
                final_username = generate_username()

    # 4. 密码校验
    if len(password) < 6:
        raise HTTPException(status_code=400, detail="密码最少6位")

    # 5. 创建用户 + 积分 + 激活码 — 全部在一个事务中
    try:
        new_user = User(
            username=final_username,
            password_hash=hash_password(password),
            role="user",
            is_active=True,
            points=10,  # 初始积分
        )
        session.add(new_user)
        session.flush()  # Get ID

        # 6. 更新激活码状态
        code_record.used_by = new_user.id
        code_record.used_at = datetime.now(timezone.utc).isoformat()
        session.add(code_record)

        # 7. 写入注册积分记录
        register_record = PointRecord(
            user_id=new_user.id,
            amount=10,
            record_type="register",
            note="注册激活",
        )
        session.add(register_record)

        session.commit()  # Single atomic commit
        session.refresh(new_user)
    except Exception:
        session.rollback()
        raise HTTPException(status_code=500, detail="注册失败，请重试")

    # 8. 生成 token
    token = create_access_token(data={"sub": new_user.username})
    response = JSONResponse({
        "user": {
            "id": new_user.id,
            "username": new_user.username,
            "role": new_user.role,
            "points": new_user.points,
        },
        "token": token
    })
    is_secure = request.url.scheme == "https"
    response.set_cookie(
        key="access_token", value=token,
        httponly=True, secure=is_secure, samesite="lax",
        max_age=60 * 60 * 24 * 7, path="/",
    )
    return response

@router.post("/login")
@limiter.limit("5/minute")
def login(request: Request, form_data: OAuth2PasswordRequestForm = Depends(), session: Session = Depends(get_session)):
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
        secure=request.url.scheme == "https",
        samesite="lax",
        max_age=60 * 60 * 24 * 7,
        path="/",
    )
    return response

@router.get("/me")
def get_me(
    authorization: Optional[str] = Header(None),
    access_token: Optional[str] = Cookie(None),
    session: Session = Depends(get_session),
):
    # Support both Authorization header (Bearer token) and httpOnly cookie
    token = access_token
    if authorization:
        token = authorization.replace("Bearer ", "")

    credentials_exception = HTTPException(
        status_code=401,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    if not token:
        raise credentials_exception

    from jose import JWTError, jwt
    from config import get_settings
    settings = get_settings()

    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    from sqlmodel import select
    user = session.exec(select(User).where(User.username == username)).first()
    if user is None or not user.is_active:
        raise credentials_exception

    current_user = user
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    checked_in_today = current_user.last_checkin_date == today
    return {
        "id": current_user.id,
        "username": current_user.username,
        "role": current_user.role,
        "points": current_user.points,
    }

@router.put("/password")
def change_password(
    old_password: str = Body(..., embed=True),
    new_password: str = Body(..., embed=True),
    current_user: User = Depends(get_current_user_from_cookie),
    session: Session = Depends(get_session),
):
    """当前用户修改自己的密码"""
    if len(new_password) < 6:
        raise HTTPException(status_code=400, detail="新密码至少6个字符")
    if not verify_password(old_password, current_user.password_hash):
        raise HTTPException(status_code=401, detail="旧密码不正确")
    current_user.password_hash = hash_password(new_password)
    session.add(current_user)
    session.commit()
    return {"message": "密码修改成功"}

@router.put("/profile")
def update_profile(
    nickname: Optional[str] = Body(None, embed=True),
    phone: Optional[str] = Body(None, embed=True),
    current_user: User = Depends(get_current_user_from_cookie),
    session: Session = Depends(get_session),
):
    """Update nickname and/or phone"""
    if nickname is not None:
        nickname = nickname.strip()
        if len(nickname) > 20:
            raise HTTPException(status_code=400, detail="昵称不能超过20个字符")
        current_user.nickname = nickname or None
    if phone is not None:
        phone = phone.strip()
        if phone and not phone.isdigit():
            raise HTTPException(status_code=400, detail="手机号格式不正确")
        if len(phone) > 15:
            raise HTTPException(status_code=400, detail="手机号格式不正确")
        current_user.phone = phone or None
    session.add(current_user)
    session.commit()
    session.refresh(current_user)
    return {
        "nickname": current_user.nickname,
        "phone": current_user.phone,
    }

ALLOWED_EXTENSIONS = {"jpg", "jpeg", "png", "webp"}
MAX_AVATAR_SIZE = 2 * 1024 * 1024  # 2MB

@router.post("/avatar")
def upload_avatar(
    request: Request,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user_from_cookie),
    session: Session = Depends(get_session),
):
    """Upload avatar image. Accepts JPEG, PNG, WebP. Max 2MB."""
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided")
    ext = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"File type not allowed. Use: {', '.join(ALLOWED_EXTENSIONS)}")

    content = file.file.read()
    if len(content) > MAX_AVATAR_SIZE:
        raise HTTPException(status_code=400, detail="File too large. Max 2MB")

    avatars_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets", "avatars")
    os.makedirs(avatars_dir, exist_ok=True)

    for old_ext in ALLOWED_EXTENSIONS:
        old_path = os.path.join(avatars_dir, f"{current_user.id}.{old_ext}")
        if os.path.exists(old_path):
            os.remove(old_path)

    filename = f"{current_user.id}.{ext}"
    filepath = os.path.join(avatars_dir, filename)
    with open(filepath, "wb") as f:
        f.write(content)

    avatar_url = f"/avatars/{filename}"
    current_user.avatar_url = avatar_url
    session.add(current_user)
    session.commit()

    return {"avatar_url": avatar_url}

@router.post("/logout")
def logout():
    """清除 httpOnly cookie 实现登出"""
    response = JSONResponse({"message": "Logged out successfully"})
    response.delete_cookie(key="access_token", path="/")
    return response
