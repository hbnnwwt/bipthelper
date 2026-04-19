import asyncio
import json
import threading
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, HTTPException, Body
from fastapi.responses import StreamingResponse
from typing import Optional
from pydantic import BaseModel
from sqlmodel import Session, select

from database import get_session
from models.crawl_config import CrawlConfig
from models.user import User
from services.auth import get_current_admin
from services.audit import add_audit_log
from services.crawler import (
    crawl_all, crawl_configs, crawl_stop_requested, request_crawl_stop,
    crawl_progress, crawl_running, _progress_lock, add_crawl_config,
)

router = APIRouter()


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
        raise HTTPException(status_code=500, detail=f"获取配置列表失败: {str(e)}")


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


# --- 爬虫控制 ---

@router.get("/crawl/status")
def get_crawl_status():
    """获取爬虫运行状态（公开接口）"""
    return {
        "running": crawl_running,
        "stop_requested": crawl_stop_requested,
    }


@router.get("/crawl/progress")
async def get_crawl_progress():
    """获取爬取进度详情（SSE）"""
    async def event_generator():
        last_seen = {}
        while True:
            progress = crawl_progress.copy()
            if progress != last_seen.get("progress"):
                last_seen["progress"] = progress
                yield f"event: progress\ndata: {json.dumps(progress)}\n\n"
            await asyncio.sleep(1)

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.post("/crawl/start")
def start_crawl(
    config_ids: Optional[str] = None,
    current_admin: User = Depends(get_current_admin),
    session: Session = Depends(get_session),
):
    """手动触发一次爬取（后台线程执行，不阻塞事件循环）"""
    if crawl_running:
        raise HTTPException(status_code=400, detail="Crawl already running")
    target_ids = None
    if config_ids:
        target_ids = [cid.strip() for cid in config_ids.split(",") if cid.strip()]
    add_audit_log(current_admin.id, current_admin.username, "trigger_crawl", None,
                  f"手动触发爬取 {'指定配置' if target_ids else '全部配置'}", session)
    if target_ids:
        threading.Thread(target=crawl_configs, kwargs={"config_ids": target_ids, "session": None}, daemon=True).start()
    else:
        threading.Thread(target=crawl_all, kwargs={"session": None}, daemon=True).start()
    return {"status": "started"}


@router.post("/crawl/stop")
def stop_crawl(
    current_admin: User = Depends(get_current_admin),
    session: Session = Depends(get_session),
):
    """请求停止爬取"""
    if not crawl_running:
        return {"message": "No crawl is running"}
    request_crawl_stop()
    add_audit_log(current_admin.id, current_admin.username, "stop_crawl", None, "请求停止爬取", session)
    return {"message": "Stop requested"}
