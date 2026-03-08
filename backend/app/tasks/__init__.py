"""
Celery 任务模块包初始化
提供任务管理相关的导入
"""
from typing import Dict, Any

from app.tasks.celery_app import (
    celery_app,
    TaskStatus,
    CustomRetry,
    get_worker_config,
    get_beat_config,
    get_flower_config,
    validate_celery_config
)

from app.tasks.crawl_tasks import (
    full_patent_crawl,
    incremental_patent_crawl,
    incremental_patent_crawl_fast,
    test_crawl_task,
    get_crawl_statistics,
    update_task_status
)

from app.tasks.rag_tasks import (
    evaluate_rag_performance,
    test_rag_accuracy,
    optimize_vector_database,
    rebuild_vector_database,
    update_metadata,
    cleanup_stale_vectors,
    rag_health_check
)

from app.tasks.cleanup_tasks import (
    cleanup_old_logs,
    cleanup_temp_files,
    cleanup_failed_tasks,
    cleanup_cache,
    cleanup_database,
    system_cleanup,
    get_cleanup_statistics
)

__all__ = [
    # Celery 配置
    "celery_app",
    "TaskStatus",
    "CustomRetry",
    "get_worker_config",
    "get_beat_config",
    "get_flower_config",
    "validate_celery_config",
    
    # 爬取任务
    "full_patent_crawl",
    "incremental_patent_crawl",
    "incremental_patent_crawl_fast",
    "test_crawl_task",
    "get_crawl_statistics",
    "update_task_status",
    
    # RAG 任务
    "evaluate_rag_performance",
    "test_rag_accuracy",
    "optimize_vector_database",
    "rebuild_vector_database",
    "update_metadata",
    "cleanup_stale_vectors",
    "rag_health_check",
    
    # 清理任务
    "cleanup_old_logs",
    "cleanup_temp_files",
    "cleanup_failed_tasks",
    "cleanup_cache",
    "cleanup_database",
    "system_cleanup",
    "get_cleanup_statistics",
]


def get_all_celery_tasks() -> Dict[str, Dict[str, Any]]:
    """
    获取所有已注册的 Celery 任务信息
    
    Returns:
        任务字典 {task_name: {task_info}}
    """
    return {
        "celery_app": {
            "name": celery_app.name,
            "main": celery_app.main,
            "broker": celery_app.conf.broker_url,
            "backend": celery_app.conf.result_backend,
            "timezone": celery_app.conf.timezone
        },
        "crawl_tasks": {
            "full_patent_crawl": {
                "name": "app.tasks.crawl_tasks.full_patent_crawl",
                "schedule": "每月1日凌晨2点",
                "max_retries": 3,
                "default_retry_delay": 300
            },
            "incremental_patent_crawl": {
                "name": "app.tasks.crawl_tasks.incremental_patent_crawl",
                "schedule": "每天凌晨1点",
                "max_retries": 3,
                "default_retry_delay": 300
            },
            "incremental_patent_crawl_fast": {
                "name": "app.tasks.crawl_tasks.incremental_patent_crawl_fast",
                "schedule": "每小时执行",
                "max_retries": 2,
                "default_retry_delay": 60
            }
        },
        "rag_tasks": {
            "evaluate_rag_performance": {
                "name": "app.tasks.rag_tasks.evaluate_rag_performance",
                "schedule": "每周日凌晨3点",
                "max_retries": 2,
                "default_retry_delay": 600
            },
            "optimize_vector_database": {
                "name": "app.tasks.rag_tasks.optimize_vector_database",
                "schedule": "每周日凌晨4点",
                "max_retries": 1,
                "default_retry_delay": 3600
            },
            "cleanup_stale_vectors": {
                "name": "app.tasks.rag_tasks.cleanup_stale_vectors",
                "schedule": "每天凌晨5点",
                "max_retries": 1,
                "default_retry_delay": 1800
            }
        },
        "cleanup_tasks": {
            "cleanup_old_logs": {
                "name": "app.tasks.cleanup_tasks.cleanup_old_logs",
                "schedule": "每天凌晨6点",
                "max_retries": 1,
                "default_retry_delay": 300
            },
            "cleanup_temp_files": {
                "name": "app.tasks.cleanup_tasks.cleanup_temp_files",
                "schedule": "每天凌晨6点半",
                "max_retries": 1,
                "default_retry_delay": 300
            },
            "cleanup_failed_tasks": {
                "name": "app.tasks.cleanup_tasks.cleanup_failed_tasks",
                "schedule": "每天凌晨7点",
                "max_retries": 1,
                "default_retry_delay": 180
            },
            "system_cleanup": {
                "name": "app.tasks.cleanup_tasks.system_cleanup",
                "schedule": "每周日凌晨2点",
                "max_retries": 1,
                "default_retry_delay": 600
            }
        }
    }
