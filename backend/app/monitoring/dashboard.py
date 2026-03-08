"""
监控仪表板模块
提供系统监控数据的收集和展示接口
"""
from __future__ import annotations
import asyncio
import logging
import os
import time
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum

logger = logging.getLogger(__name__)


class MetricType(Enum):
    """指标类型"""
    COUNTER = "counter"          # 计数器
    GAUGE = "gauge"              # 仪表
    HISTOGRAM = "histogram"       # 直方图
    RATE = "rate"                # 速率


@dataclass
class SystemMetrics:
    """系统指标数据"""
    # 系统资源
    cpu_usage_percent: float = 0.0
    memory_usage_percent: float = 0.0
    disk_usage_percent: float = 0.0
    disk_free_gb: float = 0.0
    
    # 网络
    network_received_mb: float = 0.0
    network_sent_mb: float = 0.0
    
    # 应用
    active_users: int = 0
    api_requests_total: int = 0
    api_errors_total: int = 0
    api_response_time_ms: float = 0.0
    
    # 数据库
    db_connections_active: int = 0
    db_queries_total: int = 0
    
    # RAG指标
    rag_recall_rate: float = 0.0
    rag_precision_rate: float = 0.0
    rag_query_time_ms: float = 0.0
    vector_db_documents: int = 0
    vector_db_collections: int = 0
    
    # 爬虫指标
    crawler_success_rate: float = 100.0
    crawler_failure_rate: float = 0.0
    crawler_docs_crawled_today: int = 0
    crawler_last_run: Optional[datetime] = None
    
    # Agent指标
    agent_online_count: int = 0
    agent_offline_count: int = 0
    agent_tasks_running: int = 0
    agent_offline_minutes: int = 0
    
    # Celery指标
    celery_queue_length: int = 0
    celery_workers_active: int = 0
    celery_tasks_processed: int = 0
    
    # 向量数据库
    vector_db_healthy: bool = True
    chromadb_collections: int = 0
    
    # 时间戳
    timestamp: datetime = field(default_factory=datetime.now)


class MonitoringDashboard:
    """监控仪表板"""
    
    def __init__(self):
        self._metrics_history: List[SystemMetrics] = []
        self._max_history_size = 1440  # 保留24小时数据(每分钟一条)
    
    async def collect_metrics(self) -> SystemMetrics:
        """收集当前系统指标"""
        metrics = SystemMetrics()
        
        try:
            # 收集系统资源指标
            await self._collect_system_metrics(metrics)
            
            # 收集应用指标
            await self._collect_app_metrics(metrics)
            
            # 收集RAG指标
            await self._collect_rag_metrics(metrics)
            
            # 收集爬虫指标
            await self._collect_crawler_metrics(metrics)
            
            # 收集Agent指标
            await self._collect_agent_metrics(metrics)
            
            # 收集Celery指标
            await self._collect_celery_metrics(metrics)
            
            # 收集向量数据库指标
            await self._collect_vector_db_metrics(metrics)
            
        except Exception as e:
            logger.error(f"收集监控指标失败: {e}")
        
        # 保存到历史记录
        self._metrics_history.append(metrics)
        if len(self._metrics_history) > self._max_history_size:
            self._metrics_history.pop(0)
        
        return metrics
    
    async def _collect_system_metrics(self, metrics: SystemMetrics):
        """收集系统资源指标"""
        try:
            import psutil
            
            metrics.cpu_usage_percent = psutil.cpu_percent(interval=0.1)
            memory = psutil.virtual_memory()
            metrics.memory_usage_percent = memory.percent
            
            disk = psutil.disk_usage('/')
            metrics.disk_usage_percent = disk.percent
            metrics.disk_free_gb = disk.free / (1024 ** 3)
            
            net_io = psutil.net_io_counters()
            metrics.network_received_mb = net_io.bytes_recv / (1024 ** 2)
            metrics.network_sent_mb = net_io.bytes_sent / (1024 ** 2)
            
        except ImportError:
            logger.warning("psutil未安装，使用默认系统指标")
        except Exception as e:
            logger.error(f"收集系统指标失败: {e}")
    
    async def _collect_app_metrics(self, metrics: SystemMetrics):
        """收集应用指标"""
        try:
            # 从Redis获取应用指标
            from app.core.cache import cache
            import json
            
            # 获取API请求统计
            api_stats = await cache.get("metrics:api:stats")
            if api_stats:
                data = json.loads(api_stats)
                metrics.api_requests_total = data.get("total", 0)
                metrics.api_errors_total = data.get("errors", 0)
            
            # 获取活跃用户数
            active_sessions = await cache.get("metrics:active_users")
            if active_sessions:
                metrics.active_users = int(active_sessions)
                
        except Exception as e:
            logger.debug(f"收集应用指标失败: {e}")
    
    async def _collect_rag_metrics(self, metrics: SystemMetrics):
        """收集RAG指标"""
        try:
            from app.ai.rag.enterprise_vector_db import enterprise_vector_db
            
            # 获取RAG性能数据
            stats = await enterprise_vector_db.get_collection_stats()
            metrics.vector_db_documents = stats.get("document_count", 0)
            
            # 从缓存获取性能指标
            from app.core.cache import cache
            import json
            
            rag_perf = await cache.get("metrics:rag:performance")
            if rag_perf:
                data = json.loads(rag_perf)
                metrics.rag_recall_rate = data.get("recall_rate", 0)
                metrics.rag_precision_rate = data.get("precision_rate", 0)
                metrics.rag_query_time_ms = data.get("avg_query_time_ms", 0)
                
        except Exception as e:
            logger.debug(f"收集RAG指标失败: {e}")
    
    async def _collect_crawler_metrics(self, metrics: SystemMetrics):
        """收集爬虫指标"""
        try:
            from app.core.cache import cache
            import json
            
            # 获取爬虫统计
            crawler_stats = await cache.get("metrics:crawler:stats")
            if crawler_stats:
                data = json.loads(crawler_stats)
                metrics.crawler_success_rate = data.get("success_rate", 100)
                metrics.crawler_failure_rate = data.get("failure_rate", 0)
                metrics.crawler_docs_crawled_today = data.get("docs_today", 0)
                
                last_run = data.get("last_run")
                if last_run:
                    metrics.crawler_last_run = datetime.fromisoformat(last_run)
                    
        except Exception as e:
            logger.debug(f"收集爬虫指标失败: {e}")
    
    async def _collect_agent_metrics(self, metrics: SystemMetrics):
        """收集Agent指标"""
        try:
            from app.core.cache import cache
            import json
            
            # 获取Agent状态
            agent_status = await cache.get("metrics:agents:status")
            if agent_status:
                data = json.loads(agent_status)
                metrics.agent_online_count = data.get("online", 0)
                metrics.agent_offline_count = data.get("offline", 0)
                metrics.agent_tasks_running = data.get("tasks_running", 0)
                metrics.agent_offline_minutes = data.get("offline_minutes", 0)
                    
        except Exception as e:
            logger.debug(f"收集Agent指标失败: {e}")
    
    async def _collect_celery_metrics(self, metrics: SystemMetrics):
        """收集Celery指标"""
        try:
            from app.core.cache import cache
            import json
            
            # 获取Celery队列长度
            queue_length = await cache.get("metrics:celery:queue_length")
            if queue_length:
                metrics.celery_queue_length = int(queue_length)
                
            # 获取活跃Worker数
            workers = await cache.get("metrics:celery:workers")
            if workers:
                metrics.celery_workers_active = int(workers)
                    
        except Exception as e:
            logger.debug(f"收集Celery指标失败: {e}")
    
    async def _collect_vector_db_metrics(self, metrics: SystemMetrics):
        """收集向量数据库指标"""
        try:
            from app.ai.rag.enterprise_vector_db import enterprise_vector_db
            
            # 检查ChromaDB健康状态
            from app.ai.rag.config import get_rag_settings
            settings = get_rag_settings()
            
            if settings.VECTOR_DB_TYPE == "chroma":
                import httpx
                try:
                    async with httpx.AsyncClient() as client:
                        response = await client.get(
                            f"http://{settings.CHROMADB_HOST}:{settings.CHROMADB_PORT}/api/v1/heartbeat",
                            timeout=5.0
                        )
                        metrics.vector_db_healthy = response.status_code == 200
                except:
                    metrics.vector_db_healthy = False
                    
                # 获取集合数量
                try:
                    async with httpx.AsyncClient() as client:
                        response = await client.get(
                            f"http://{settings.CHROMADB_HOST}:{settings.CHROMADB_PORT}/api/v1/collections",
                            timeout=5.0
                        )
                        if response.status_code == 200:
                            data = response.json()
                            metrics.chromadb_collections = len(data.get("collections", []))
                except:
                    pass
                    
        except Exception as e:
            logger.debug(f"收集向量数据库指标失败: {e}")
    
    def get_current_metrics(self) -> SystemMetrics:
        """获取最新指标"""
        if self._metrics_history:
            return self._metrics_history[-1]
        return SystemMetrics()
    
    def get_metrics_history(
        self, 
        hours: int = 24,
        interval_minutes: int = 1
    ) -> List[SystemMetrics]:
        """获取历史指标"""
        cutoff = datetime.now() - timedelta(hours=hours)
        return [m for m in self._metrics_history if m.timestamp >= cutoff]
    
    def get_metrics_summary(self, hours: int = 24) -> Dict[str, Any]:
        """获取指标摘要"""
        history = self.get_metrics_history(hours)
        
        if not history:
            return {"error": "No data available"}
        
        # 计算统计信息
        cpu_values = [m.cpu_usage_percent for m in history]
        memory_values = [m.memory_usage_percent for m in history]
        disk_values = [m.disk_usage_percent for m in history]
        
        return {
            "period_hours": hours,
            "data_points": len(history),
            "system": {
                "cpu": {
                    "current": cpu_values[-1] if cpu_values else 0,
                    "avg": sum(cpu_values) / len(cpu_values) if cpu_values else 0,
                    "max": max(cpu_values) if cpu_values else 0,
                    "min": min(cpu_values) if cpu_values else 0,
                },
                "memory": {
                    "current": memory_values[-1] if memory_values else 0,
                    "avg": sum(memory_values) / len(memory_values) if memory_values else 0,
                    "max": max(memory_values) if memory_values else 0,
                },
                "disk": {
                    "current": disk_values[-1] if disk_values else 0,
                    "avg": sum(disk_values) / len(disk_values) if disk_values else 0,
                    "max": max(disk_values) if disk_values else 0,
                }
            },
            "rag": {
                "recall_rate": history[-1].rag_recall_rate if history else 0,
                "precision_rate": history[-1].rag_precision_rate if history else 0,
                "vector_documents": history[-1].vector_db_documents if history else 0,
            },
            "crawler": {
                "success_rate": history[-1].crawler_success_rate if history else 100,
                "failure_rate": history[-1].crawler_failure_rate if history else 0,
                "docs_today": history[-1].crawler_docs_crawled_today if history else 0,
            },
            "agents": {
                "online": history[-1].agent_online_count if history else 0,
                "offline": history[-1].agent_offline_count if history else 0,
                "tasks_running": history[-1].agent_tasks_running if history else 0,
            },
            "celery": {
                "queue_length": history[-1].celery_queue_length if history else 0,
                "workers_active": history[-1].celery_workers_active if history else 0,
            },
            "vector_db": {
                "healthy": history[-1].vector_db_healthy if history else False,
                "collections": history[-1].chromadb_collections if history else 0,
            }
        }


# 全局仪表板实例
monitoring_dashboard = MonitoringDashboard()
