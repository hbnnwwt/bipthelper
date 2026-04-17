from fastapi import APIRouter, Depends, Query, HTTPException
from sqlmodel import Session, select, update
from typing import List, Optional
from pydantic import BaseModel
from database import get_session
from models.crawl_config import CrawlConfig

router = APIRouter(prefix="/api/crawl-configs", tags=["爬虫配置管理"])

class CrawlConfigCreate(BaseModel):
    name: str
    url: str
    category: Optional[str] = None
    parent_category: Optional[str] = None
    sub_category: Optional[str] = None
    is_list_page: bool = True
    article_selector: str = "a"
    link_prefix: Optional[str] = None
    pagination_selector: str = ""
    pagination_max: int = 0
    selector: str = "body"

class CrawlConfigUpdate(BaseModel):
    enabled: Optional[bool] = None
    name: Optional[str] = None
    url: Optional[str] = None
    category: Optional[str] = None
    parent_category: Optional[str] = None
    sub_category: Optional[str] = None
    is_list_page: Optional[bool] = None
    article_selector: Optional[str] = None
    link_prefix: Optional[str] = None
    pagination_selector: Optional[str] = None
    pagination_max: Optional[int] = None
    selector: Optional[str] = None

@router.get("", response_model=List[CrawlConfig])
def list_crawl_configs(session: Session = Depends(get_session)):
    """获取所有爬虫配置"""
    configs = session.exec(select(CrawlConfig)).all()
    return configs

@router.get("/{config_id}", response_model=CrawlConfig)
def get_crawl_config(config_id: str, session: Session = Depends(get_session)):
    """获取单个爬虫配置"""
    config = session.get(CrawlConfig, config_id)
    if not config:
        raise HTTPException(status_code=404, detail="配置未找到")
    return config

@router.post("", response_model=CrawlConfig, status_code=201)
def create_crawl_config(config: CrawlConfigCreate, session: Session = Depends(get_session)):
    """创建爬虫配置"""
    db_config = CrawlConfig(**config.dict())
    session.add(db_config)
    session.commit()
    session.refresh(db_config)
    return db_config

@router.put("/{config_id}", response_model=CrawlConfig)
def update_crawl_config(
    config_id: str,
    config_update: CrawlConfigUpdate,
    session: Session = Depends(get_session)
):
    """更新爬虫配置"""
    config = session.get(CrawlConfig, config_id)
    if not config:
        raise HTTPException(status_code=404, detail="配置未找到")

    update_data = config_update.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(config, key, value)

    session.add(config)
    session.commit()
    session.refresh(config)
    return config

@router.put("/{config_id}/toggle")
def toggle_crawl_config(config_id: str, session: Session = Depends(get_session)):
    """切换配置启用状态"""
    config = session.get(CrawlConfig, config_id)
    if not config:
        raise HTTPException(status_code=404, detail="配置未找到")

    config.enabled = not config.enabled
    session.add(config)
    session.commit()
    session.refresh(config)
    return {"enabled": config.enabled}

@router.get("/navigation", response_model=List[dict])
def get_navigation_structure(session: Session = Depends(get_session)):
    """获取首页导航结构"""
    from services.crawler import crawl_homepage_navigation
    nav_items = crawl_homepage_navigation(session)
    return nav_items

@router.post("/batch", response_model=dict)
def create_crawl_configs_batch(
    config_list: List[CrawlConfigCreate],
    session: Session = Depends(get_session)
):
    """批量创建爬虫配置"""
    from services import crawler
    created_count = 0
    for config_data in config_list:
        config = CrawlConfig(**config_data.dict())
        session.add(config)
        created_count += 1
    session.commit()
    return {"message": f"已批量添加 {created_count} 个配置"}

@router.post("/start")
def start_crawl(config_ids: List[str], session: Session = Depends(get_session)):
    """启动爬取任务"""
    # 这里应该启动后台任务，实际实现可能需要使用Celery或类似的任务队列
    # 简化实现：直接调用爬虫逻辑
    from services import crawler
    for config_id in config_ids:
        config = session.get(CrawlConfig, config_id)
        if not config:
            raise HTTPException(status_code=404, detail=f"配置 {config_id} 未找到")

        # 启动爬取（这里简化处理，实际应该异步）
        crawler.crawl_configs([config_id], session)

    return {"message": f"已启动 {len(config_ids)} 个配置的爬取任务"}

@router.delete("/{config_id}", status_code=204)
def delete_crawl_config(config_id: str, session: Session = Depends(get_session)):
    """删除爬虫配置"""
    config = session.get(CrawlConfig, config_id)
    if not config:
        raise HTTPException(status_code=404, detail="配置未找到")

    session.delete(config)
    session.commit()