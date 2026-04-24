from fastapi import APIRouter, Depends, HTTPException, Body
from typing import Optional
from pydantic import BaseModel
from sqlmodel import Session, select, func
from datetime import datetime, timezone, timedelta
import logging

from database import get_session
from models.user import User
from models.point_record import PointRecord
from models.document import Document
from models.invite_code import InviteCode
from services.invite import code_status
from services.auth import get_current_admin
from services.audit import add_audit_log
from services.search import delete_document_from_index, index_document

logger = logging.getLogger(__name__)

router = APIRouter()

class BulkDeleteRequest(BaseModel):
    ids: list[str]

class DocumentUpdateRequest(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None
    category: Optional[str] = None
    parent_category: Optional[str] = None
    sub_category: Optional[str] = None
    department: Optional[str] = None
    publish_date: Optional[str] = None

# --- 用户管理 ---

@router.get("/users")
def list_users(
    current_admin: User = Depends(get_current_admin),
    session: Session = Depends(get_session),
):
    """列出所有用户"""
    users = session.exec(select(User)).all()
    return {
        "users": [
            {"id": u.id, "username": u.username, "role": u.role, "is_active": u.is_active, "points": u.points, "created_at": u.created_at}
            for u in users
        ]
    }

@router.put("/users/{user_id}/password")
def reset_user_password(
    user_id: str,
    password: str,
    current_admin: User = Depends(get_current_admin),
    session: Session = Depends(get_session),
):
    """重置用户密码（仅管理员可操作）"""
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if len(password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters")
    from services.auth import hash_password
    user.password_hash = hash_password(password)
    session.add(user)
    session.commit()
    add_audit_log(current_admin.id, current_admin.username, "reset_password", user_id, f"重置用户 {user.username} 的密码", session)
    return {"message": "Password updated"}

@router.post("/codes")
def create_code(
    type: str = Body(..., embed=True),
    username: Optional[str] = Body(None, embed=True),
    current_admin: User = Depends(get_current_admin),
    session: Session = Depends(get_session),
):
    """创建激活码（designated 或 anonymous）"""
    if type == "designated":
        if not username or not username.strip():
            raise HTTPException(status_code=400, detail="designated 类型必须提供 username")
        existing = session.exec(select(User).where(User.username == username.strip())).first()
        if existing:
            raise HTTPException(status_code=400, detail="该用户名已被注册")
    elif type != "anonymous":
        raise HTTPException(status_code=400, detail="type 必须是 designated 或 anonymous")

    expires_at = datetime.now(timezone.utc)
    expires_at = expires_at.replace(second=0, microsecond=0)
    expires_at = (expires_at + timedelta(days=7)).isoformat()

    code = InviteCode(
        code=InviteCode.generate_code(),
        code_type=type,
        designated_username=username.strip() if type == "designated" else None,
        created_by=current_admin.username,
        expires_at=expires_at,
    )
    session.add(code)
    session.commit()

    add_audit_log(
        current_admin.id, current_admin.username,
        "create_invite_code",
        code.code,
        f"创建{type}激活码: {code.code}"[:80],
        session
    )

    return {
        "code": code.code,
        "type": code.code_type,
        "designated_username": code.designated_username,
        "expires_at": code.expires_at,
        "created_by": code.created_by,
    }

@router.get("/codes")
def list_codes(
    current_admin: User = Depends(get_current_admin),
    session: Session = Depends(get_session),
):
    """列出所有激活码（含实时 status）"""
    codes = session.exec(select(InviteCode).order_by(InviteCode.created_at.desc())).all()
    return {
        "codes": [
            {
                "code": c.code,
                "type": c.code_type,
                "designated_username": c.designated_username,
                "created_by": c.created_by,
                "created_at": c.created_at,
                "expires_at": c.expires_at,
                "status": code_status(c),
                "used_by": c.used_by,
                "used_at": c.used_at,
            }
            for c in codes
        ]
    }

@router.delete("/codes/{code}")
def delete_code(
    code: str,
    current_admin: User = Depends(get_current_admin),
    session: Session = Depends(get_session),
):
    """删除激活码"""
    record = session.get(InviteCode, code)
    if not record:
        raise HTTPException(status_code=404, detail="激活码不存在")
    session.delete(record)
    session.commit()
    add_audit_log(
        current_admin.id, current_admin.username,
        "delete_invite_code", code,
        f"删除激活码: {code}",
        session
    )
    return {"message": "Code deleted"}

# --- 文档管理 ---

@router.get("/documents/categories")
def get_document_categories(
    current_admin: User = Depends(get_current_admin),
    session: Session = Depends(get_session),
):
    """获取所有可用的文档分类列表（用于筛选器）"""
    from sqlmodel import func, col, distinct
    # 获取所有不重复的大类
    parent_cats = session.exec(
        select(col(Document.parent_category))
        .where(col(Document.parent_category).isnot(None))
        .where(col(Document.parent_category) != "")
        .distinct()
    ).all()
    # 获取所有不重复的小类
    sub_cats = session.exec(
        select(col(Document.sub_category))
        .where(col(Document.sub_category).isnot(None))
        .where(col(Document.sub_category) != "")
        .distinct()
    ).all()
    # 获取所有不重复的分类
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
    # 排序
    if sort == "updated_asc":
        order_col = Document.updated_at.asc()
    elif sort == "publish_desc":
        order_col = Document.publish_date.desc().nullslast()
    elif sort == "publish_asc":
        order_col = Document.publish_date.asc().nullslast()
    else:  # default updated_desc
        order_col = Document.updated_at.desc()

    # 先构建带过滤条件的 count 查询
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

    # 再查询分页数据
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
    # 排序
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

    import csv
    import io
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["标题", "URL", "大类", "小类", "分类", "AI状态", "AI建议分类", "发布单位", "发布日期", "更新时间"])
    for d in docs:
        writer.writerow([
            d.title,
            d.url,
            d.parent_category or "",
            d.sub_category or "",
            d.category or "",
            d.ai_status,
            d.ai_suggested_categories or "",
            d.department or "",
            d.publish_date or "",
            d.updated_at,
        ])

    output.seek(0)
    from fastapi.responses import StreamingResponse
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=documents.csv"},
    )

@router.get("/documents/pending")
def list_pending_documents(
    page: int = 1,
    page_size: int = 20,
    current_admin: User = Depends(get_current_admin),
    session: Session = Depends(get_session),
):
    """列出待复核的文档（ai_status = pending 或 failed）"""
    count_query = select(func.count()).select_from(Document).where(
        Document.ai_status.in_(["pending", "failed"])
    )
    total = session.exec(count_query).one()

    query = select(Document).where(
        Document.ai_status.in_(["pending", "failed"])
    ).order_by(Document.updated_at.desc())

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

@router.post("/documents/{doc_id}/approve")
def approve_document_category(
    doc_id: str,
    categories: Optional[str] = None,
    current_admin: User = Depends(get_current_admin),
    session: Session = Depends(get_session),
):
    """采纳 AI 建议分类（或指定的 categories）"""
    doc = session.get(Document, doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    target = categories if categories else doc.ai_suggested_categories
    if not target:
        raise HTTPException(status_code=400, detail="No suggested categories to approve")

    doc.category = target
    doc.ai_status = "success"
    doc.ai_reviewed_at = datetime.now(timezone.utc).isoformat()
    session.add(doc)
    session.commit()
    add_audit_log(current_admin.id, current_admin.username, "approve_category", doc_id, f"采纳AI分类: {target}", session)

    # 重新索引
    delete_document_from_index(doc_id)
    index_document(doc)

    return {"message": "Category approved", "category": target}

@router.put("/documents/{doc_id}/category")
def update_document_category(
    doc_id: str,
    category: str,
    current_admin: User = Depends(get_current_admin),
    session: Session = Depends(get_session),
):
    """管理员手动指定分类"""
    if not category or not category.strip():
        raise HTTPException(status_code=400, detail="Category cannot be empty")

    doc = session.get(Document, doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    doc.category = category.strip()
    doc.ai_status = "manual"
    doc.ai_reviewed_at = datetime.now(timezone.utc).isoformat()
    session.add(doc)
    session.commit()
    add_audit_log(current_admin.id, current_admin.username, "update_category", doc_id, f"手动分类: {category}", session)

    # 重新索引
    delete_document_from_index(doc_id)
    index_document(doc)

    return {"message": "Category updated", "category": doc.category}

@router.put("/documents/{doc_id}")
def update_document(
    doc_id: str,
    data: DocumentUpdateRequest,
    current_admin: User = Depends(get_current_admin),
    session: Session = Depends(get_session),
):
    """更新文档全部字段"""
    doc = session.get(Document, doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    updated_fields = []
    if data.title is not None:
        doc.title = data.title
        updated_fields.append(f"title={data.title[:20]}...")
    if data.content is not None:
        doc.content = data.content
        updated_fields.append("content")
    if data.category is not None:
        doc.category = data.category
        updated_fields.append(f"category={data.category}")
    if data.parent_category is not None:
        doc.parent_category = data.parent_category
        updated_fields.append(f"parent_category={data.parent_category}")
    if data.sub_category is not None:
        doc.sub_category = data.sub_category
        updated_fields.append(f"sub_category={data.sub_category}")
    if data.department is not None:
        doc.department = data.department
        updated_fields.append(f"department={data.department}")
    if data.publish_date is not None:
        doc.publish_date = data.publish_date
        updated_fields.append(f"publish_date={data.publish_date}")

    doc.updated_at = datetime.now(timezone.utc).isoformat()
    if updated_fields:
        doc.ai_status = "manual"
        doc.ai_reviewed_at = datetime.now(timezone.utc).isoformat()

    session.add(doc)
    session.commit()
    add_audit_log(current_admin.id, current_admin.username, "update_document", doc_id,
                  f"更新文档字段: {', '.join(updated_fields)}", session)

    delete_document_from_index(doc_id)
    index_document(doc)

    return {"message": "Document updated", "doc_id": doc_id}

@router.delete("/documents/{doc_id}")
def delete_document(
    doc_id: str,
    current_admin: User = Depends(get_current_admin),
    session: Session = Depends(get_session),
):
    """删除文档（同时从数据库和搜索索引删除）"""
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

# --- 积分管理 ---

@router.get("/users/{user_id}/points")
def get_user_points(
    user_id: str,
    current_admin: User = Depends(get_current_admin),
    session: Session = Depends(get_session),
):
    """查看指定用户积分"""
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    return {
        "user_id": user.id,
        "username": user.username,
        "points": user.points,
        "last_checkin_date": user.last_checkin_date,
    }

@router.patch("/users/{user_id}/points")
def patch_user_points(
    user_id: str,
    delta: int | None = None,
    set_value: int | None = None,
    current_admin: User = Depends(get_current_admin),
    session: Session = Depends(get_session),
):
    """修改用户积分（delta 或 set）"""
    if delta is None and set_value is None:
        raise HTTPException(status_code=400, detail="必须提供 delta 或 set")
    if delta is not None and set_value is not None:
        raise HTTPException(status_code=400, detail="delta 和 set 不可同时提供")

    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")

    old_points = user.points
    if set_value is not None:
        user.points = set_value
    else:
        if user.points + delta < 0:
            raise HTTPException(status_code=400, detail="积分不足，无法扣除")
        user.points += delta

    record = PointRecord(
        user_id=user.id,
        amount=user.points - old_points,
        record_type="admin_set",
        note=f"Admin {current_admin.username} 修改",
    )
    session.add(user)
    session.add(record)
    try:
        session.commit()
    except Exception:
        session.rollback()
        raise HTTPException(status_code=400, detail="修改积分失败")

    return {
        "user_id": user.id,
        "username": user.username,
        "old_points": old_points,
        "new_points": user.points,
        "changed_by": current_admin.username,
    }
