"""
清理任务模块
Celery 异步任务实现

功能:
- 清理旧日志文件
- 清理临时文件
- 清理失败任务记录
- 清理缓存数据
"""
from __future__ import annotations
import os
import logging
import shutil
import gzip
import json
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from functools import wraps
from pathlib import Path

from celery import shared_task
from app.tasks.celery_app import celery_app, TaskStatus, CustomRetry

logger = logging.getLogger(__name__)


# ----------------------
# 任务装饰器
# ----------------------

def track_cleanup_task(task_func):
    """清理任务执行跟踪装饰器"""
    @wraps(task_func)
    def wrapper(*args, **kwargs):
        task_id = kwargs.get("task_id") or str(celery_app.current_task.request.id)
        task_name = task_func.__name__
        
        logger.info(f"清理任务开始: {task_name} [{task_id}]")
        start_time = datetime.now()
        
        try:
            result = task_func(*args, **kwargs)
            duration = (datetime.now() - start_time).total_seconds()
            logger.info(f"清理任务成功: {task_name} [{task_id}] 耗时: {duration:.2f}秒")
            return result
            
        except Exception as e:
            duration = (datetime.now() - start_time).total_seconds()
            logger.error(f"清理任务失败: {task_name} [{task_id}] 耗时: {duration:.2f}秒, 错误: {e}")
            raise CustomRetry(
                f"清理任务执行失败: {str(e)}",
                delay=300,  # 清理任务失败后延迟重试
                max_retries=1
            )
    
    return wrapper


# ----------------------
# 日志清理任务
# ----------------------

@shared_task(
    name="app.tasks.cleanup_tasks.cleanup_old_logs",
    bind=True,
    max_retries=1
)
@track_cleanup_task
def cleanup_old_logs(
    self,
    days_to_keep: int = 7,
    compress_old: bool = True
) -> Dict[str, Any]:
    """
    清理旧日志文件
    
    Args:
        days_to_keep: 保留最近几天的日志
        compress_old: 是否压缩旧日志
    
    Returns:
        清理结果
    """
    logger.info(f"开始清理旧日志: days_to_keep={days_to_keep}, compress_old={compress_old}")
    
    results = {
        "task_id": self.request.id,
        "start_time": datetime.now().isoformat(),
        "days_to_keep": days_to_keep,
        "compress_old": compress_old,
        "cleaned": {
            "files_deleted": 0,
            "files_compressed": 0,
            "space_freed_mb": 0.0
        },
        "errors": []
    }
    
    try:
        # 日志目录
        log_dirs = [
            Path("./data/logs"),
            Path("./logs"),
            Path("/var/log/patent-exam"),
            Path("/app/logs"),
        ]
        
        cutoff_date = datetime.now() - timedelta(days=days_to_keep)
        
        for log_dir in log_dirs:
            if not log_dir.exists():
                logger.info(f"日志目录不存在，跳过: {log_dir}")
                continue
            
            logger.info(f"扫描日志目录: {log_dir}")
            
            total_size_freed = 0
            
            for log_file in log_dir.glob("**/*.log"):
                try:
                    file_mtime = datetime.fromtimestamp(log_file.stat().st_mtime)
                    
                    if file_mtime < cutoff_date:
                        file_size_mb = log_file.stat().st_size / 1024 / 1024
                        
                        if compress_old:
                            # 压缩旧日志
                            compressed_path = log_file.with_suffix(log_file.suffix + ".gz")
                            with open(log_file, 'rb') as f_in:
                                with gzip.open(compressed_path, 'wb') as f_out:
                                    shutil.copyfileobj(f_in, f_out)
                            log_file.unlink()
                            results["cleaned"]["files_compressed"] += 1
                            logger.info(f"压缩日志: {log_file.name} ({file_size_mb:.2f} MB -> {compressed_path.name})")
                        else:
                            # 删除旧日志
                            log_file.unlink()
                            results["cleaned"]["files_deleted"] += 1
                            total_size_freed += file_size_mb
                            logger.info(f"删除日志: {log_file.name} ({file_size_mb:.2f} MB)")
                            
                except Exception as e:
                    results["errors"].append(f"{log_file}: {str(e)}")
                    logger.error(f"处理日志文件失败 {log_file}: {e}")
            
            results["cleaned"]["space_freed_mb"] += total_size_freed
        
        results["end_time"] = datetime.now().isoformat()
        results["status"] = "completed"
        
        return results
        
    except Exception as e:
        results["status"] = "failed"
        results["error"] = str(e)
        results["end_time"] = datetime.now().isoformat()
        raise


# ----------------------
# 临时文件清理任务
# ----------------------

@shared_task(
    name="app.tasks.cleanup_tasks.cleanup_temp_files",
    bind=True,
    max_retries=1
)
@track_cleanup_task
def cleanup_temp_files(
    self,
    hours_old: int = 24,
    temp_dirs: Optional[List[str]] = None
) -> Dict[str, Any]:
    """
    清理临时文件
    
    Args:
        hours_old: 多少小时前的临时文件被视为过期
        temp_dirs: 要清理的临时目录列表
    
    Returns:
        清理结果
    """
    logger.info(f"开始清理临时文件: hours_old={hours_old}")
    
    if temp_dirs is None:
        temp_dirs = [
            "./data/temp",
            "./data/uploads/temp",
            "/tmp/patent-exam",
            "/app/data/temp",
        ]
    
    results = {
        "task_id": self.request.id,
        "start_time": datetime.now().isoformat(),
        "hours_old": hours_old,
        "temp_dirs": temp_dirs,
        "cleaned_count": 0,
        "space_freed_mb": 0.0,
        "errors": []
    }
    
    try:
        cutoff_time = datetime.now() - timedelta(hours=hours_old)
        
        for temp_dir in temp_dirs:
            temp_path = Path(temp_dir)
            
            if not temp_path.exists():
                logger.info(f"临时目录不存在: {temp_dir}")
                continue
            
            logger.info(f"扫描临时目录: {temp_dir}")
            
            # 清理过期文件
            for temp_file in temp_path.rglob("*"):
                try:
                    if temp_file.is_file():
                        file_mtime = datetime.fromtimestamp(temp_file.stat().st_mtime)
                        
                        if file_mtime < cutoff_time:
                            file_size_mb = temp_file.stat().st_size / 1024 / 1024
                            temp_file.unlink()
                            results["cleaned_count"] += 1
                            results["space_freed_mb"] += file_size_mb
                            logger.info(f"删除临时文件: {temp_file.name} ({file_size_mb:.2f} MB)")
                            
                    elif temp_file.is_dir():
                        # 如果目录也为空，则删除
                        try:
                            temp_file.rmdir()
                            logger.info(f"删除空目录: {temp_dir.name}")
                        except OSError:
                            # 目录非空，保留
                            pass
                            
                except Exception as e:
                    results["errors"].append(f"{temp_file}: {str(e)}")
                    logger.error(f"处理临时文件失败 {temp_file}: {e}")
        
        results["end_time"] = datetime.now().isoformat()
        results["status"] = "completed"
        
        return results
        
    except Exception as e:
        results["status"] = "failed"
        results["error"] = str(e)
        results["end_time"] = datetime.now().isoformat()
        raise


# ----------------------
# 失败任务清理任务
# ----------------------

@shared_task(
    name="app.tasks.cleanup_tasks.cleanup_failed_tasks",
    bind=True,
    max_retries=1
)
@track_cleanup_task
def cleanup_failed_tasks(
    self,
    days_to_keep: int = 3
) -> Dict[str, Any]:
    """
    清理失败的任务记录
    
    Args:
        days_to_keep: 保留最近几天的失败记录
    
    Returns:
        清理结果
    """
    logger.info(f"开始清理失败任务记录: days_to_keep={days_to_keep}")
    
    results = {
        "task_id": self.request.id,
        "start_time": datetime.now().isoformat(),
        "days_to_keep": days_to_keep,
        "cleaned_count": 0,
        "status": "completed"
    }
    
    try:
        # 获取 failed任务列表
        inspect = celery_app.control.inspect()
        
        if not inspect:
            logger.warning("无法获取任务列表")
            return results
        
        # 清理失败的任务结果
        task_ids_to_clean = []
        
        # 查询所有失败的任务
        failed_tasks = celery_app.control.inspect().get('active', {})
        
        if failed_tasks:
            for worker_name, tasks in failed_tasks.items():
                for task_id, task_info in tasks.items():
                    if task_info.get('time_start'):
                        start_time = datetime.fromtimestamp(task_info['time_start'])
                        
                        if (datetime.now() - start_time) > timedelta(days=days_to_keep):
                            # 确认为过期
                            try:
                                celery_app.control.revoke(task_id, terminate=True)
                                task_ids_to_clean.append(task_id)
                                logger.info(f"清除过期失败任务: {task_id}")
                            except Exception as e:
                                logger.error(f"清除任务失败 {task_id}: {e}")
                                results["errors"] = [f"{task_id}: {str(e)}"]
        
        # 清理过期的任务结果（结果数据）
        try:
            results["backend_cleaned"] = celery_app.control.purge()
            results["backend_cleaned_count"] = len(results.get("backend_cleaned", {}))
        except Exception as e:
            logger.warning(f"清理后端任务结果失败: {e}")
        
        results["cleaned_count"] = len(task_ids_to_clean)
        results["end_time"] = datetime.now().isoformat()
        
        return results
        
    except Exception as e:
        results["status"] = "failed"
        results["error"] = str(e)
        results["end_time"] = datetime.now().isoformat()
        raise


# ----------------------
# 缓存清理任务
# ----------------------

@shared_task(
    name="app.tasks.cleanup_tasks.cleanup_cache",
    bind=True,
    max_retries=1
)
@track_cleanup_task
def cleanup_cache(
    self,
    max_cache_size_mb: Optional[float] = 1024.0
) -> Dict[str, Any]:
    """
    清理缓存数据
    
    清理过期的缓存数据，释放内存
    
    Args:
        max_cache_size_mb: 最大缓存大小(MB)，超过此大小的缓存将被清理
    
    Returns:
        清理结果
    """
    logger.info(f"开始清理缓存: max_cache_size_mb={max_cache_size_mb}")
    
    results = {
        "task_id": self.request.id,
        "start_time": datetime.now().isoformat(),
        "max_cache_size_mb": max_cache_size_mb,
        "status": "completed"
    }
    
    try:
        # Redis 缓存清理
        try:
            import redis
            from app.config import DatabaseSettings
            
            # Redis 配置
            redis_client = redis.Redis(
                host=os.getenv("REDIS_HOST", "localhost"),
                port=int(os.getenv("REDIS_PORT", "6379")),
                db=0,
                decode_responses=True
            )
            
            # 获取所有键
            all_keys = redis_client.keys("*")
            
            # 估算内存使用
            cache_size = 0
            keys_to_delete = []
            
            for key in all_keys:
                try:
                    key_size = redis_client.memory_usage(key, "value") or 0
                    cache_size += key_size
                except Exception as e:
                    logger.warning(f"获取缓存大小失败 {key}: {e}")
            
            cache_size_mb = cache_size / 1024 / 1024
            
            # 如果超过阈值，清理最老的缓存
            if cache_size_mb > max_cache_size_mb:
                # 按TTL排序，删除没有TTL的旧数据
                deletable_keys = []
                for key in all_keys:
                    ttl = redis_client.ttl(key)
                    # TTL为-1表示永不过期
                    if ttl == -1:
                        deletable_keys.append((key, 0))
                
                # 保留最近访问的缓存（通过last access time估算）
                deletable_keys.sort(key=lambda x: x[1], reverse=True)
                
                # 删除最老的缓存直到大小符合要求
                deleted_count = 0
                while cache_size_mb > max_cache_size_mb * 0.8 and deletable_keys:
                    key_to_delete = deletable_keys.pop()[0]
                    key_size = redis_client.memory_usage(key_to_delete, "value") or 0
                    redis_client.delete(key_to_delete)
                    cache_size_mb -= key_size / 1024 / 1024
                    deleted_count += 1
                    logger.info(f"删除缓存: {key_to_delete}")
                
                results["redis_cache_size_mb"] = cache_size_mb
                results["deleted_cache_keys"] = deleted_count
            else:
                results["redis_cache_size_mb"] = cache_size_mb
            
            # 保存内存空间
            redis_client.save()
            
        except Exception as e:
            logger.warning(f"Redis缓存清理失败: {e}")
            results["redis_error"] = str(e)
        
        # 向量数据库缓存清理
        try:
            from app.ai.rag.enterprise_vector_db import enterprise_vector_db
            
            # 这里可以调用向量数据库的清理方法
            skipped = asyncio.run(enterprise_vector_db.cleanup_cache())
            results["vector_cache_cleanup"] = skipped
            
        except Exception as e:
            logger.warning(f"向量数据库缓存清理失败: {e}")
            results["vector_cache_error"] = str(e)
        
        results["end_time"] = datetime.now().isoformat()
        
        return results
        
    except Exception as e:
        results["status"] = "failed"
        results["error"] = str(e)
        results["end_time"] = datetime.now().isoformat()
        raise


# ----------------------
# 数据库清理任务
# ----------------------

@shared_task(
    name="app.tasks.cleanup_tasks.cleanup_database",
    bind=True,
    max_retries=1
)
@track_cleanup_task
def cleanup_database(
    self,
    vacuum_full: bool = False
) -> Dict[str, Any]:
    """
    数据库清理任务
    
    清理数据库碎片化空间
    
    Args:
        vacuum_full: 是否执行VACUUM FULL
    
    Returns:
        清理结果
    """
    logger.info(f"开始数据库清理: vacuum_full={vacuum_full}")
    
    results = {
        "task_id": self.request.id,
        "start_time": datetime.now().isoformat(),
        "vacuum_full": vacuum_full,
        "status": "completed"
    }
    
    try:
        # PostgreSQL VACUUM
        db_type = os.getenv("DB_TYPE", "sqlite")
        
        if db_type.startswith("postgresql"):
            try:
                import asyncio
                from sqlalchemy import text
                
                async def vacuum_db():
                    from app.database.engine import async_session_factory
                    async with async_session_factory() as db:
                        vacuum_type = "FULL" if vacuum_full else ""
                        await db.execute(text(f"VACUUM {vacuum_type};"))
                
                asyncio.run(vacuum_db())
                logger.info("PostgreSQL VACUUM 完成")
                
            except Exception as e:
                results["error"] = str(e)
                logger.error(f"PostgreSQL VACUUM 失败: {e}")
                
        elif db_type.startswith("sqlite"):
            # SQLite VACUUM
            db_path = os.getenv("DATABASE_PATH", "./data/patent_exam.db")
            try:
                conn = sqlite3.connect(db_path)
                cursor = conn.cursor()
                cursor.execute(f"VACUUM" + (" FULL" if vacuum_full else "") + ";")
                conn.commit()
                conn.close()
                logger.info("SQLite VACUUM 完成")
                
            except Exception as e:
                results["error"] = str(e)
                logger.error(f"SQLite VACUUM 失败: {e}")
        
        results["end_time"] = datetime.now().isoformat()
        
        return results
        
    except Exception as e:
        results["status"] = "failed"
        results["error"] = str(e)
        results["end_time"] = datetime.now().isoformat()
        raise


# ----------------------
# 系统清理任务 (综合)
# ----------------------

@shared_task(
    name="app.tasks.cleanup_tasks.system_cleanup",
    bind=True,
    max_retries=1
)
@track_cleanup_task
def system_cleanup(
    self
) -> Dict[str, Any]:
    """
    综合系统清理任务
    
    执行所有清理操作
    
    Returns:
        综合清理结果
    """
    logger.info("开始综合系统清理")
    
    results = {
        "task_id": self.request.id,
        "start_time": datetime.now().isoformat(),
        "operations": {},
        "status": "completed"
    }
    
    try:
        # 调用各个清理任务
        operations = {}
        
        # 清理日志 (保留7天)
        logs_result = cleanup_old_logs(days_to_keep=7, compress_old=True)
        operations["logs"] = logs_result
        
        # 清理临时文件 (24小时)
        temp_result = cleanup_temp_files(hours_old=24)
        operations["temp_files"] = temp_result
        
        # 清理失败任务 (3天)
        tasks_result = cleanup_failed_tasks(days_to_keep=3)
        operations["failed_tasks"] = tasks_result
        
        # 清理缓存
        cache_result = cleanup_cache(max_cache_size_mb=512)  # 512MB
        operations["cache"] = cache_result
        
        results["operations"] = operations
        results["total_space_freed_mb"] = (
            operations.get("logs", {}).get("cleaned", {}).get("space_freed_mb", 0) +
            operations.get("temp_files", {}).get("space_freed_mb", 0)
        )
        results["end_time"] = datetime.now().isoformat()
        
        logger.info(f"综合系统清理完成, 释放空间: {results['total_space_freed_mb']:.2f} MB")
        
        return results
        
    except Exception as e:
        results["status"] = "failed"
        results["error"] = str(e)
        results["end_time"] = datetime.now().isoformat()
        raise


# ----------------------
# 清理统计任务
# ----------------------

@shared_task(
    name="app.tasks.cleanup_tasks.get_cleanup_statistics",
    bind=True
)
def get_cleanup_statistics(
    self
) -> Dict[str, Any]:
    """
    获取清理统计信息
    
    Returns:
        清理统计
    """
    logger.info("获取清理统计信息")
    
    statistics = {
        "task_id": self.request.id,
        "timestamp": datetime.now().isoformat(),
        "disk_usage": {},
        "cache_usage": {},
        "log_info": {},
        "temporary_files": {}
    }
    
    try:
        # 磁盘使用情况
        disk_usage = shutil.disk_usage(".")
        statistics["disk_usage"] = {
            "total_gb": disk_usage.total / 1024 / 1024 / 1024,
            "used_gb": disk_usage.used / 1024 / 1024 / 1024,
            "free_gb": disk_usage.free / 1024 / 1024 / 1024,
            "usage_percent": (disk_usage.used / disk_usage.total) * 100
        }
        
        # 日志统计
        log_dirs = ["./logs", "./data/logs"]
        for log_dir in log_dirs:
            if Path(log_dir).exists():
                log_stats = {
                    "file_count": 0,
                    "total_size_mb": 0.0,
                    "oldest_file": None,
                    "newest_file": None
                }
                
                log_files = list(Path(log_dir).glob("*.log"))
                log_stats["file_count"] = len(log_files)
                
                for log_file in log_files:
                    file_size_mb = log_file.stat().st_size / 1024 / 1024
                    log_stats["total_size_mb"] += file_size_mb
                    
                    mtime = datetime.fromtimestamp(log_file.stat().st_mtime)
                    if log_stats["oldest_file"] is None or mtime < log_stats["oldest_file"]:
                        log_stats["oldest_file"] = log_file.name
                    if log_stats["newest_file"] is None or mtime > log_stats["newest_file"]:
                        log_stats["newest_file"] = log_file.name
                
                statistics["log_info"][log_dir] = log_stats
        
        return statistics
        
    except Exception as e:
        statistics["error"] = str(e)
        return statistics
