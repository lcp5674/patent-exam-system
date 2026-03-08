"""
Celery 主配置文件
专利审查系统 - 异步任务调度

功能:
- 专利数据全量爬取
- 专利数据增量更新
- RAG 性能评估和优化
- 系统日志清理
- 向量数据库维护
"""
from __future__ import annotations
import os
import logging
import asyncio
from celery import Celery, schedules
from celery.app.amqp import Queue
from celery.schedules import crontab
from app.config import DatabaseSettings, AIProviderSettings

logger = logging.getLogger(__name__)

# ----------------------
# Celery 应用配置
# ----------------------

# Redis 配置
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
REDIS_DB = int(os.getenv("REDIS_DB", "0"))
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD", "")

# 构建 Redis URL
if REDIS_PASSWORD:
    broker_url = f"redis://:{REDIS_PASSWORD}@{REDIS_HOST}:{REDIS_PORT}/{REDIS_DB}"
    result_backend = f"redis://:{REDIS_PASSWORD}@{REDIS_HOST}:{REDIS_PORT}/{REDIS_DB}"
else:
    broker_url = f"redis://{REDIS_HOST}:{REDIS_PORT}/{REDIS_DB}"
    result_backend = f"redis://{REDIS_HOST}:{REDIS_PORT}/{REDIS_DB}"

# 创建 Celery 应用
celery_app = Celery(
    "patent_exam_celery",
    broker=broker_url,
    backend=result_backend,
    include=[
        "app.tasks.crawl_tasks",
        "app.tasks.rag_tasks",
        "app.tasks.cleanup_tasks",
    ]
)

# ----------------------
# Celery 配置选项
# ----------------------

celery_app.conf.update(
    # -------------- 任务设置 --------------
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Asia/Shanghai",
    enable_utc=True,
    task_track_STARTED=True,
    task_time_limit=3600,  # 任务超时: 1小时
    task_soft_time_limit=3300,  # 软超时: 55分钟
    task_acks_late=True,  # 任务完成后才确认
    task_reject_on_worker_lost=True,  # Worker 丢失时拒绝任务
    task_ignore_result=False,  # 保留结果

    # -------------- 任务路由 --------------
    task_routes={
        "app.tasks.crawl_tasks.*": {"queue": "crawl"},
        "app.tasks.rag_tasks.*": {"queue": "rag"},
        "app.tasks.cleanup_tasks.*": {"queue": "cleanup"},
    },

    # -------------- Worker 配置 --------------
    worker_prefetch_multiplier=4,
    worker_log_format="[%(asctime)s: %(levelname)s/%(processName)s] %(message)s",
    worker_task_log_format="[%(asctime)s: %(levelname)s/%(processName)s][%(task_name)s(%(task_id)s)] %(message)s",

    # -------------- 结果配置 --------------
    result_expires=86400,  # 结果保存 1 天
    result_extended=True,
    result_compression="gzip",

    # -------------- 重试配置 --------------
    task_default_rate_limit="10/m",  # 默认速率限制
    task_default_retry_delay=60,  # 默认重试延迟
    task_default_max_retries=3,  # 默认最大重试次数

    # -------------- Beat 调度器配置 --------------
    # beat_scheduler="django_celery_beat.schedulers:DatabaseScheduler",  # Django专用,已禁用
    beat_schedule_filename="/tmp/celerybeat-schedule",

    # -------------- 安全配置 --------------
    task_send_sent_event=True,
    worker_send_sent_event=True,

    # -------------- 监控配置 --------------
    worker_send_task_events=True,
)

# ----------------------
# 定时任务配置 (Beat Schedule)
# ----------------------

# 注意: cron_time 使用时区: Asia/Shanghai
celery_app.conf.beat_schedule = {
    # -------------- 专利爬取任务 --------------
    # 全量爬取: 每月1日凌晨2:00
    "patent-full-crawl-monthly": {
        "task": "app.tasks.crawl_tasks.full_patent_crawl",
        "schedule": crontab(hour=2, minute=0, day_of_month=1),
        "options": {
            "queue": "crawl",
            "expires": 86400 * 2,  # 2天过期
        },
    },

    # 增量爬取: 每6小时执行一次 (00:00, 06:00, 12:00, 18:00)
    "patent-incremental-crawl-6h": {
        "task": "app.tasks.crawl_tasks.incremental_patent_crawl",
        "schedule": crontab(hour="*/6", minute=0),
        "options": {
            "queue": "crawl",
            "expires": 86400,  # 1天过期
        },
    },

    # 增量爬取 (快速): 每小时执行一次 (用于关键关键词监控)
    "patent-incremental-crawl-1h": {
        "task": "app.tasks.crawl_tasks.incremental_patent_crawl_fast",
        "schedule": crontab(minute=0),  # 每小时整点
        "options": {
            "queue": "crawl",
            "expires": 7200,  # 2小时过期
        },
    },

    # -------------- RAG 优化任务 --------------
    # RAG 性能评估: 每天03:00
    "rag-performance-evaluation-daily": {
        "task": "app.tasks.rag_tasks.evaluate_rag_performance",
        "schedule": crontab(hour=3, minute=0),
        "options": {
            "queue": "rag",
            "expires": 86400,
        },
    },

    # RAG 准确率测试: 每6小时
    "rag-accuracy-test-6h": {
        "task": "app.tasks.rag_tasks.test_rag_accuracy",
        "schedule": crontab(hour="*/6", minute=30),
        "options": {
            "queue": "rag",
            "expires": 43200,
        },
    },

    # 向量库优化: 每周日 04:00
    "vector-db-optimize-weekly": {
        "task": "app.tasks.rag_tasks.optimize_vector_database",
        "schedule": crontab(hour=4, minute=0, day_of_week=0),
        "options": {
            "queue": "rag",
            "expires": 86400 * 2,
        },
    },

    # 向量库重构: 每月15日 05:00
    "vector-db-rebuild-monthly": {
        "task": "app.tasks.rag_tasks.rebuild_vector_database",
        "schedule": crontab(hour=5, minute=0, day_of_month=15),
        "options": {
            "queue": "rag",
            "expires": 86400 * 3,
        },
    },

    # -------------- 清理任务 --------------
    # 日志清理: 每周一凌晨4:00
    "cleanup-logs-weekly": {
        "task": "app.tasks.cleanup_tasks.cleanup_old_logs",
        "schedule": crontab(hour=4, minute=0, day_of_week=1),
        "options": {
            "queue": "cleanup",
            "expires": 86400 * 2,
        },
    },

    # 临时文件清理: 每天凌晨5:00
    "cleanup-temp-files-daily": {
        "task": "app.tasks.cleanup_tasks.cleanup_temp_files",
        "schedule": crontab(hour=5, minute=0),
        "options": {
            "queue": "cleanup",
            "expires": 86400,
        },
    },

    # 失败任务清理: 每周二凌晨2:00
    "cleanup-failed-tasks-weekly": {
        "task": "app.tasks.cleanup_tasks.cleanup_failed_tasks",
        "schedule": crontab(hour=2, minute=0, day_of_week=2),
        "options": {
            "queue": "cleanup",
            "expires": 86400 * 3,
        },
    },

    # 缓存清理: 每天凌晨6:00
    "cleanup-cache-daily": {
        "task": "app.tasks.cleanup_tasks.cleanup_cache",
        "schedule": crontab(hour=6, minute=0),
        "options": {
            "queue": "cleanup",
            "expires": 86400,
        },
    },
}

# ----------------------
# 队列配置
# ----------------------

# 声明使用的队列 (使用 Queue 对象)
celery_app.conf.task_default_queue = "default"
celery_app.conf.task_queues = (
    Queue("default", exchange="default", routing_key="default"),
    Queue("crawl", exchange="crawl", routing_key="crawl"),
    Queue("rag", exchange="rag", routing_key="rag"),
    Queue("cleanup", exchange="cleanup", routing_key="cleanup"),
)

# ----------------------
# 启动配置辅助函数
# ----------------------


def get_worker_config(count: int = 1, queue: str = "default"):
    """
    获取 Worker 启动配置

    Args:
        count: Worker 数量
        queue: 队列名称

    Returns:
        Worker 配置字符串
    """
    return f"celery -A app.tasks.celery_app worker -l INFO -c {count} -Q {queue}"


def get_beat_config():
    """
    获取 Beat 启动配置

    Returns:
        Beat 配置字符串
    """
    return "celery -A app.tasks.celery_app beat -l INFO"


def get_flower_config(port: int = 5555):
    """
    获取 Flower 监控配置

    Args:
        port: Flower 端口

    Returns:
        Flower 配置字符串
    """
    return f"celery -A app.tasks.celery_app flower --port={port}"


# ----------------------
# 任务状态管理 --------------
# ----------------------


class TaskStatus:
    """任务状态常量"""
    PENDING = "PENDING"
    STARTED = "STARTED"
    SUCCESS = "SUCCESS"
    FAILURE = "FAILURE"
    RETRY = "RETRY"
    REVOKED = "REVOKED"


# ----------------------
# 错误处理和重试策略
# ---------------------


class CustomRetry(Exception):
    """自定义重试异常"""
    def __init__(self, message: str, delay: int = 60, max_retries: int = 3):
        self.message = message
        self.delay = delay
        self.max_retries = max_retries
        super().__init__(message)


# ----------------------
# 配置验证 --------------------
# ----------------------


def validate_celery_config() -> dict:
    """
    验证 Celery 配置

    Returns:
        配置验证结果
    """
    config_status = {
        "valid": True,
        "errors": [],
        "warnings": [],
        "config": {
            "broker_url": broker_url,
            "result_backend": result_backend,
            "timezone": celery_app.conf.timezone,
            "task_count": len(celery_app.conf.beat_schedule),
        }
    }

    # 检查 Redis 连接
    try:
        import redis
        redis_client = redis.Redis(
            host=REDIS_HOST,
            port=REDIS_PORT,
            db=REDIS_DB,
            password=REDIS_PASSWORD,
            decode_responses=True
        )
        # 测试连接
        config_valid = redis_client.ping()

        if not config_valid:
            config_status["valid"] = False
            config_status["errors"].append("Redis 连接失败")

    except Exception as e:
        config_status["valid"] = False
        config_status["errors"].append(f"Redis 配置错误: {str(e)}")

    # 检查任务数量
    if len(celery_app.conf.beat_schedule) == 0:
        config_status["warnings"].append("未配置任何定时任务")

    return config_status


# ----------------------
# 模块导入完成通知
# ----------------------

if __name__ == "__main__":
    logger.info("=" * 50)
    logger.info("Celery 应用已初始化")
    logger.info(f"Broker URL: {broker_url}")
    logger.info(f"Result Backend: {result_backend}")
    logger.info(f"定时任务数量: {len(celery_app.conf.beat_schedule)}")
    logger.info("=" * 50)

    # 验证配置
    config_result = validate_celery_config()
    if config_result["valid"]:
        logger.info("✅ Celery 配置验证通过")
    else:
        logger.error(f"❌ Celery 配置验证失败: {config_result['errors']}")

    for warning in config_result["warnings"]:
        logger.warning(f"⚠️  {warning}")
