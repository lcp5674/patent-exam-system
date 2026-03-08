"""
爬虫服务 - 支持全量爬取、增量同步、可视化配置
"""
import asyncio
import crontab
import json
from datetime import datetime, timedelta
from typing import Optional, List, Dict
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import desc, func

from app.models import CrawlTask, CrawlerConfig
from app.core.config import settings
from app.services.vector_service import VectorService
from crawler.patent_spider import PatentSpider

class CrawlerService:
    _current_task: Optional[asyncio.Task] = None
    _spider: Optional[PatentSpider] = None
    
    @classmethod
    async def get_status(cls, db: AsyncSession) -> Dict:
        """获取爬虫状态"""
        # 获取配置
        full_config = await cls._get_full_crawl_config(db)
        incremental_config = await cls._get_incremental_config(db)
        
        # 获取当前运行状态
        is_running = cls._current_task is not None and not cls._current_task.done()
        
        # 获取统计数据
        total_patents = await db.scalar(
            func.count(CrawlTask.id).filter(CrawlTask.status == "completed")
        ) or 0
        
        # 获取最后同步时间
        last_sync = await db.scalar(
            CrawlTask.query.filter(CrawlTask.task_type == "incremental")
            .order_by(desc(CrawlTask.end_time))
            .limit(1)
            .with_entities(CrawlTask.end_time)
        )
        
        # 获取当前任务
        current_task = None
        if is_running and cls._spider:
            current_task = {
                "task_id": cls._spider.task_id,
                "task_type": cls._spider.task_type,
                "status": cls._spider.status,
                "progress": cls._spider.progress,
                "total_count": cls._spider.total_count,
                "completed_count": cls._spider.completed_count,
                "start_time": cls._spider.start_time,
                "end_time": None,
                "error_message": None
            }
        
        return {
            "is_running": is_running,
            "current_task": current_task,
            "full_crawl_config": full_config,
            "incremental_config": incremental_config,
            "total_patents": total_patents,
            "last_sync_time": last_sync
        }
    
    @classmethod
    async def start_full_crawl(cls, config, db: AsyncSession, user_id: int) -> Dict:
        """启动全量爬取"""
        # 创建任务记录
        task = CrawlTask(
            task_type="full",
            status="running",
            created_by=user_id,
            start_time=datetime.now(),
            config=json.dumps(config.dict())
        )
        db.add(task)
        await db.commit()
        await db.refresh(task)
        
        # 启动爬虫
        cls._spider = PatentSpider(
            task_id=str(task.id),
            task_type="full",
            config=config.dict()
        )
        
        # 异步运行
        cls._current_task = asyncio.create_task(
            cls._run_crawl_task(task.id, config, db)
        )
        
        return {
            "task_id": str(task.id),
            "task_type": "full",
            "status": "running",
            "progress": 0.0,
            "total_count": 0,
            "completed_count": 0,
            "start_time": task.start_time,
            "end_time": None,
            "error_message": None
        }
    
    @classmethod
    async def stop_full_crawl(cls) -> bool:
        """停止全量爬取"""
        if cls._current_task and not cls._current_task.done():
            cls._current_task.cancel()
            if cls._spider:
                cls._spider.stop()
            return True
        return False
    
    @classmethod
    async def update_incremental_config(cls, config, db: AsyncSession) -> Dict:
        """更新增量爬取配置"""
        # 保存到数据库
        db_config = await db.scalar(CrawlerConfig.query.filter(CrawlerConfig.type == "incremental"))
        if not db_config:
            db_config = CrawlerConfig(type="incremental")
        
        db_config.config = json.dumps(config.dict())
        db_config.updated_at = datetime.now()
        db.add(db_config)
        await db.commit()
        
        return config.dict()
    
    @classmethod
    async def update_crontab(cls, config: Dict):
        """更新系统定时任务"""
        cron = crontab.CronTab(user='root')
        
        # 移除旧的专利爬取任务
        for job in cron:
            if job.comment == 'patent_daily_sync':
                cron.remove(job)
        
        if config.get("enabled", True):
            # 创建新任务
            job = cron.new(
                command=f"{settings.BACKEND_DIR}/venv/bin/python {settings.BACKEND_DIR}/crawler/daily_sync.py >> /var/log/patent_crawl.log 2>&1",
                comment='patent_daily_sync'
            )
            
            # 解析时间配置
            hour, minute = config.get("sync_time", "02:00").split(":")
            job.setall(f"{minute} {hour} * * *")
        
        cron.write()
    
    @classmethod
    async def run_incremental_sync(cls, db: AsyncSession, user_id: int) -> CrawlTask:
        """立即执行增量同步"""
        config = await cls._get_incremental_config(db)
        
        # 创建任务记录
        task = CrawlTask(
            task_type="incremental",
            status="running",
            created_by=user_id,
            start_time=datetime.now(),
            config=json.dumps(config)
        )
        db.add(task)
        await db.commit()
        await db.refresh(task)
        
        # 启动爬虫
        cls._spider = PatentSpider(
            task_id=str(task.id),
            task_type="incremental",
            config=config
        )
        
        # 异步运行
        cls._current_task = asyncio.create_task(
            cls._run_crawl_task(task.id, config, db)
        )
        
        return task
    
    @classmethod
    async def get_task_list(cls, page: int, page_size: int, db: AsyncSession) -> List[Dict]:
        """获取任务列表"""
        offset = (page - 1) * page_size
        tasks = await db.execute(
            CrawlTask.query.order_by(desc(CrawlTask.start_time))
            .offset(offset)
            .limit(page_size)
        )
        tasks = tasks.scalars().all()
        
        result = []
        for task in tasks:
            result.append({
                "task_id": str(task.id),
                "task_type": task.task_type,
                "status": task.status,
                "progress": task.progress,
                "total_count": task.total_count,
                "completed_count": task.completed_count,
                "start_time": task.start_time,
                "end_time": task.end_time,
                "error_message": task.error_message
            })
        
        return result
    
    @classmethod
    async def get_stats(cls, db: AsyncSession) -> Dict:
        """获取统计数据"""
        # 按类型统计
        stats = await db.execute("""
            SELECT task_type, status, COUNT(*) as count
            FROM crawl_tasks
            GROUP BY task_type, status
        """)
        
        result = {
            "total_tasks": 0,
            "completed_tasks": 0,
            "failed_tasks": 0,
            "full_crawl_count": 0,
            "incremental_crawl_count": 0,
            "total_patents_crawled": 0
        }
        
        for row in stats:
            result["total_tasks"] += row.count
            if row.status == "completed":
                result["completed_tasks"] += row.count
            elif row.status == "failed":
                result["failed_tasks"] += row.count
            
            if row.task_type == "full":
                result["full_crawl_count"] += row.count
            elif row.task_type == "incremental":
                result["incremental_crawl_count"] += row.count
        
        # 总爬取专利数
        result["total_patents_crawled"] = await db.scalar(
            func.sum(CrawlTask.completed_count).filter(CrawlTask.status == "completed")
        ) or 0
        
        return result
    
    @classmethod
    async def _run_crawl_task(cls, task_id: int, config: Dict, db: AsyncSession):
        """运行爬取任务"""
        try:
            # 运行爬虫
            patents = await cls._spider.run()
            
            # 向量化入库
            if config.get("auto_vectorize", True):
                vector_service = VectorService()
                for patent in patents:
                    await vector_service.add_patent(patent)
            
            # 更新任务状态
            task = await db.get(CrawlTask, task_id)
            task.status = "completed"
            task.end_time = datetime.now()
            task.completed_count = cls._spider.completed_count
            task.total_count = cls._spider.total_count
            task.progress = 100.0
            await db.commit()
            
        except Exception as e:
            # 记录错误
            task = await db.get(CrawlTask, task_id)
            task.status = "failed"
            task.end_time = datetime.now()
            task.error_message = str(e)
            await db.commit()
            raise
        finally:
            cls._current_task = None
            cls._spider = None
    
    @classmethod
    async def _get_full_crawl_config(cls, db: AsyncSession) -> Dict:
        """获取全量爬取配置"""
        config = await db.scalar(CrawlerConfig.query.filter(CrawlerConfig.type == "full"))
        if config:
            return json.loads(config.config)
        return {
            "start_year": 2020,
            "end_year": 2026,
            "tech_fields": None,
            "max_count": None,
            "auto_vectorize": True
        }
    
    @classmethod
    async def _get_incremental_config(cls, db: AsyncSession) -> Dict:
        """获取增量爬取配置"""
        config = await db.scalar(CrawlerConfig.query.filter(CrawlerConfig.type == "incremental"))
        if config:
            return json.loads(config.config)
        return {
            "enabled": True,
            "sync_time": "02:00",
            "sync_days": 1,
            "auto_vectorize": True,
            "retry_count": 3
        }
    
    @classmethod
    def is_running(cls) -> bool:
        """检查是否有任务正在运行"""
        return cls._current_task is not None and not cls._current_task.done()
