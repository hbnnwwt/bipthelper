from fastapi import APIRouter, Depends, HTTPException, Body
from typing import Optional
from pydantic import BaseModel
from sqlmodel import Session, select, func
from datetime import datetime, timezone, timedelta
from urllib.parse import urlparse
import secrets

from database import get_session
from models.user import User
from models.point_record import PointRecord
from models.crawl_config import CrawlConfig
from models.document import Document
from models.invite_code import InviteCode
from services.invite import code_status
from services.auth import get_current_admin
from services.audit import add_audit_log
from services.crawler import crawl_all, add_crawl_config, crawl_running, crawl_stop_requested, request_crawl_stop, crawl_progress, crawl_homepage_navigation
from services.log_store import log_store
from services.search import delete_document_from_index, index_document

router = APIRouter()

class BulkDeleteRequest(BaseModel):
    ids: list[str]

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

# --- 爬虫配置管理 ---

@router.get("/configs")
def list_configs(
    current_admin: User = Depends(get_current_admin),
    session: Session = Depends(get_session),
):
    """列出所有爬虫配置"""
    try:
        configs = session.exec(select(CrawlConfig)).all()
        return {
            "configs": [
                {
                    "id": c.id,
                    "name": c.name,
                    "url": c.url,
                    "selector": c.selector,
                    "category": c.category,
                    "parent_category": c.parent_category or "",
                    "sub_category": c.sub_category or "",
                    "is_list_page": c.is_list_page,
                    "article_selector": c.article_selector,
                    "link_prefix": c.link_prefix,
                    "pagination_selector": c.pagination_selector,
                    "pagination_max": c.pagination_max,
                    "enabled": c.enabled,
                    "last_crawl": c.last_crawl,
                    "initialized": c.initialized,
                }
                for c in configs
            ]
        }
    except Exception as e:
        logger.error(f"Failed to list configs: {e}")
        raise HTTPException(status_code=500, detail=f"获取配置列表失败: {str(e)}")

def _validate_selector(selector: str, field_name: str) -> bool:
    """验证 CSS 选择器不包含危险内容"""
    if not selector or not selector.strip():
        return True  # 空值跳过
    dangerous = ["<script", "javascript:", "onerror", "onclick", "onload", "onmouse", "onkey"]
    lower = selector.lower()
    for d in dangerous:
        if d in lower:
            raise HTTPException(status_code=400, detail=f"{field_name}: 选择器不能包含危险内容 '{d}'")
    return True

def _validate_url(url: str, field_name: str) -> bool:
    """验证 URL 格式"""
    try:
        u = urlparse(url)
        if u.scheme not in ("http", "https", ""):  # 空 scheme 允许（相对 URL）
            raise HTTPException(status_code=400, detail=f"{field_name}: 仅支持 http/https URL")
        return True
    except Exception:
        raise HTTPException(status_code=400, detail=f"{field_name}: URL 格式无效")

@router.post("/configs")
def create_config(
    name: str,
    url: str,
    selector: str = "body",
    category: Optional[str] = None,
    is_list_page: bool = True,
    article_selector: str = "a",
    link_prefix: Optional[str] = None,
    pagination_selector: str = "",
    pagination_max: int = 0,
    parent_category: Optional[str] = None,
    sub_category: Optional[str] = None,
    auto_interval_hours: int = 0,
    current_admin: User = Depends(get_current_admin),
    session: Session = Depends(get_session),
):
    """添加爬虫配置"""
    _validate_url(url, "列表页URL")
    _validate_selector(selector, "内容选择器")
    _validate_selector(article_selector, "文章链接选择器")
    if link_prefix:
        _validate_selector(link_prefix, "链接前缀")
    if pagination_selector:
        _validate_selector(pagination_selector, "分页选择器")
    config = add_crawl_config(
        name, url, selector, category, session,
        is_list_page=is_list_page,
        article_selector=article_selector,
        link_prefix=link_prefix,
        pagination_selector=pagination_selector,
        pagination_max=pagination_max,
        parent_category=parent_category,
        sub_category=sub_category,
        auto_interval_hours=auto_interval_hours,
    )
    add_audit_log(current_admin.id, current_admin.username, "add_config", config.id, f"添加配置: {config.name}", session)
    return {"id": config.id, "name": config.name, "url": config.url}

@router.put("/configs/{config_id}")
def update_config(
    config_id: str,
    name: Optional[str] = None,
    url: Optional[str] = None,
    selector: Optional[str] = None,
    category: Optional[str] = None,
    is_list_page: Optional[bool] = None,
    article_selector: Optional[str] = None,
    link_prefix: Optional[str] = None,
    pagination_selector: Optional[str] = None,
    pagination_max: Optional[int] = None,
    enabled: Optional[bool] = None,
    initialized: Optional[bool] = None,
    parent_category: Optional[str] = None,
    sub_category: Optional[str] = None,
    auto_interval_hours: Optional[int] = None,
    current_admin: User = Depends(get_current_admin),
    session: Session = Depends(get_session),
):
    """更新爬虫配置"""
    config = session.get(CrawlConfig, config_id)
    if not config:
        raise HTTPException(status_code=404, detail="Config not found")

    if url is not None:
        _validate_url(url, "列表页URL")
    if selector is not None:
        _validate_selector(selector, "内容选择器")
    if article_selector is not None:
        _validate_selector(article_selector, "文章链接选择器")
    if link_prefix is not None:
        _validate_selector(link_prefix, "链接前缀")
    if pagination_selector is not None:
        _validate_selector(pagination_selector, "分页选择器")

    if name is not None:
        config.name = name
    if url is not None:
        config.url = url
    if selector is not None:
        config.selector = selector
    if category is not None:
        config.category = category
    if is_list_page is not None:
        config.is_list_page = is_list_page
    if article_selector is not None:
        config.article_selector = article_selector
    if link_prefix is not None:
        config.link_prefix = link_prefix
    if pagination_selector is not None:
        config.pagination_selector = pagination_selector
    if pagination_max is not None:
        config.pagination_max = pagination_max
    if enabled is not None:
        config.enabled = enabled
    if initialized is not None:
        config.initialized = initialized
    if parent_category is not None:
        config.parent_category = parent_category
    if sub_category is not None:
        config.sub_category = sub_category
    if auto_interval_hours is not None:
        config.auto_interval_hours = auto_interval_hours

    session.add(config)
    session.commit()
    return {"message": "Config updated"}

@router.delete("/configs/{config_id}")
def delete_config(
    config_id: str,
    current_admin: User = Depends(get_current_admin),
    session: Session = Depends(get_session),
):
    """删除爬虫配置"""
    config = session.get(CrawlConfig, config_id)
    if not config:
        raise HTTPException(status_code=404, detail="Config not found")
    session.delete(config)
    session.commit()
    add_audit_log(current_admin.id, current_admin.username, "delete_config", config_id, f"删除配置: {config.name}", session)
    return {"message": "Config deleted"}

# --- 爬虫导航 ---

@router.get("/crawl/navigation")
def get_homepage_navigation(
    current_admin: User = Depends(get_current_admin),
    session: Session = Depends(get_session),
):
    """抓取首页导航菜单，返回大类/小类结构"""
    try:
        nav_items = crawl_homepage_navigation(session)
        return {"navigation": nav_items}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to fetch homepage navigation: {e}")
        raise HTTPException(status_code=500, detail=f"获取首页导航失败: {str(e)}")

@router.post("/crawl/configs/batch")
def batch_create_configs(
    navigation: list[dict] = Body(..., embed=True),
    current_admin: User = Depends(get_current_admin),
    session: Session = Depends(get_session),
):
    """
    批量创建爬虫配置。
    navigation 格式：
    [
      {
        "parent": "机关教辅",
        "subs": [
          {"name": "通知公告", "url": "https://..."},
          {"name": "部门文件", "url": "https://..."},
        ]
      },
      ...
    ]
    每个 sub 创建一个 CrawlConfig，parent_category=大类, sub_category=小类
    """
    try:
        created = []
        for item in navigation:
            parent = item.get("parent", "")
            subs = item.get("subs", [])
            for sub in subs:
                name = sub.get("name", "")
                url = sub.get("url", "")
                if not name or not url:
                    continue
                # 检查是否已存在相同 URL 的配置
                existing = session.exec(
                    select(CrawlConfig).where(CrawlConfig.url == url)
                ).first()
                if existing:
                    continue
                config = add_crawl_config(
                    name=name,
                    url=url,
                    selector="body",
                    category=name,
                    session=session,
                    is_list_page=True,
                    article_selector="ul.sub_list li a",
                    link_prefix=None,
                    pagination_selector="a[href*='index']",
                    pagination_max=0,
                    parent_category=parent,
                    sub_category=name,
                )
                created.append({"id": config.id, "name": config.name, "url": config.url, "parent": parent})
        add_audit_log(current_admin.id, current_admin.username, "batch_add_configs", None, f"批量创建 {len(created)} 个爬虫配置", session)
        return {"created": created, "count": len(created)}
    except HTTPException:
        raise
    except Exception as e:
        session.rollback()
        logger.error(f"Failed to batch create configs: {e}")
        raise HTTPException(status_code=500, detail=f"批量创建配置失败: {str(e)}")

@router.post("/crawl/trigger")
def trigger_crawl(
    config_ids: Optional[str] = None,  # 逗号分隔的ID列表，如 "id1,id2,id3"
    current_admin: User = Depends(get_current_admin),
    session: Session = Depends(get_session),
):
    """手动触发一次爬取（后台线程执行，不阻塞事件循环）"""
    if crawl_running:
        return {"message": "Crawl already running"}
    import threading
    from services.crawler import crawl_configs
    # 解析 config_ids
    target_ids = None
    if config_ids:
        target_ids = [cid.strip() for cid in config_ids.split(",") if cid.strip()]
    add_audit_log(current_admin.id, current_admin.username, "trigger_crawl", None,
                  f"手动触发爬取 {'指定配置' if target_ids else '全部配置'}", session)
    if target_ids:
        t = threading.Thread(target=crawl_configs, kwargs={"config_ids": target_ids, "session": None}, daemon=True)
    else:
        t = threading.Thread(target=crawl_all, kwargs={"session": None}, daemon=True)
    t.start()
    return {"message": "Crawl triggered (running in background)"}

@router.get("/logs")
def get_logs(
    current_admin: User = Depends(get_current_admin),
):
    """获取爬虫日志"""
    return {"logs": log_store.get_all()}

@router.delete("/logs")
def clear_logs(
    current_admin: User = Depends(get_current_admin),
):
    """清空日志"""
    log_store.clear()
    return {"message": "Logs cleared"}

@router.get("/crawl/status")
def get_crawl_status(
    current_admin: User = Depends(get_current_admin),
):
    """获取爬虫运行状态"""
    return {
        "running": crawl_running,
        "stop_requested": crawl_stop_requested,
        "log_count": log_store.count(),
    }

@router.get("/crawl/progress")
def get_crawl_progress(
    current_admin: User = Depends(get_current_admin),
):
    """获取爬取进度详情"""
    return crawl_progress

@router.post("/crawl/stop")
def stop_crawl(
    current_admin: User = Depends(get_current_admin),
):
    """请求停止爬取"""
    if not crawl_running:
        return {"message": "No crawl is running"}
    request_crawl_stop()
    add_audit_log(current_admin.id, current_admin.username, "stop_crawl", None, "请求停止爬取")
    return {"message": "Stop requested"}

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
