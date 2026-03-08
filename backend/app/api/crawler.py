"""
爬虫管理API - 支持可视化配置全量和增量爬取
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional, List, Dict
from datetime import date, datetime

from app.core.database import get_db
from app.core.auth import get_current_user
from app.services.crawler_service import CrawlerService

router = APIRouter(prefix="/api/v1/crawler", tags=["爬虫管理"])

class FullCrawlConfig(BaseModel):
    """全量爬取配置"""
    start_year: int = 2020
    end_year: int = 2026
    tech_fields: Optional[List[str]] = None
    max_count: Optional[int] = None
    auto_vectorize: bool = True

class IncrementalCrawlConfig(BaseModel):
    """增量爬取配置"""
    enabled: bool = True
    sync_time: str = "02:00"
    sync_days: int = 1
    auto_vectorize: bool = True
    retry_count: int = 3

class CrawlTaskResponse(BaseModel):
    """爬取任务响应"""
    task_id: str
    task_type: str
    status: str
    progress: float
    total_count: int
    completed_count: int
    start_time: Optional[datetime]
    end_time: Optional[datetime]
    error_message: Optional[str]

class CrawlerStatusResponse(BaseModel):
    """爬虫状态响应"""
    is_running: bool
    current_task: Optional[CrawlTaskResponse]
    full_crawl_config: FullCrawlConfig
    incremental_config: IncrementalCrawlConfig
    total_patents: int
    last_sync_time: Optional[datetime]

@router.get("/status", response_model=CrawlerStatusResponse)
async def get_crawler_status(
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """获取爬虫当前状态和配置"""
    return await CrawlerService.get_status(db)

@router.post("/full-crawl/start", response_model=CrawlTaskResponse)
async def start_full_crawl(
    config: FullCrawlConfig,
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """启动全量爬取任务"""
    if await CrawlerService.is_running():
        raise HTTPException(status_code=400, detail="已有爬取任务正在运行")
    
    return await CrawlerService.start_full_crawl(config, db, current_user.id)

@router.post("/full-crawl/stop")
async def stop_full_crawl(
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """停止全量爬取任务"""
    success = await CrawlerService.stop_full_crawl()
    if not success:
        raise HTTPException(status_code=400, detail="没有正在运行的全量爬取任务")
    return {"message": "全量爬取已停止"}

@router.put("/incremental/config", response_model=IncrementalCrawlConfig)
async def update_incremental_config(
    config: IncrementalCrawlConfig,
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """更新增量爬取配置"""
    updated_config = await CrawlerService.update_incremental_config(config, db)
    # 自动更新crontab定时任务
    await CrawlerService.update_crontab(updated_config)
    return updated_config

@router.post("/incremental/run-now")
async def run_incremental_now(
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """立即执行一次增量同步"""
    if await CrawlerService.is_running():
        raise HTTPException(status_code=400, detail="已有爬取任务正在运行")
    
    task = await CrawlerService.run_incremental_sync(db, current_user.id)
    return {"message": "增量同步已启动", "task_id": task.task_id}

@router.get("/tasks", response_model=List[CrawlTaskResponse])
async def get_crawl_tasks(
    page: int = 1,
    page_size: int = 20,
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """获取历史爬取任务列表"""
    return await CrawlerService.get_task_list(page, page_size, db)

@router.get("/stats")
async def get_crawler_stats(
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """获取爬取统计数据"""
    return await CrawlerService.get_stats(db)
