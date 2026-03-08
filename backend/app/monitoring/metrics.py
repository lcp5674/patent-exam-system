"""
监控指标模块
提供统一的指标收集和跟踪接口
"""
from __future__ import annotations
import time
import psutil
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class MetricType(Enum):
    """指标类型"""
    COUNTER = "counter"        # 计数器（只增不减）
    GAUGE = "gauge"            # 仪表盘（可增可减）
    HISTOGRAM = "histogram"    # 直方图（分布统计）
    RATE = "rate"              # 速率（每秒变化）


@dataclass
class MetricValue:
    """指标值"""
    name: str
    value: float
    type: str
    timestamp: float = field(default_factory=time.time)
    tags: Dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class SystemResourceMetrics:
    """系统资源指标"""
    cpu_percent: float
    cpu_percent_per_cpu: List[float]
    memory_used_mb: float
    memory_available_mb: float
    memory_percent: float
    disk_used_gb: float
    disk_total_gb: float
    disk_percent: float
    network_sent_mb: float
    network_recv_mb: float
    load_avg: List[float]
    boot_time: float
    uptime_seconds: float

    @classmethod
    def collect(cls) -> "SystemResourceMetrics":
        """收集系统资源指标"""
        try:
            # CPU指标
            cpu_percent = psutil.cpu_percent(interval=0.1)
            cpu_per_cpu = psutil.cpu_percent(interval=0.1, percpu=True)

            # 内存指标
            memory = psutil.virtual_memory()
            memory_used_mb = memory.used / 1024 / 1024
            memory_available_mb = memory.available / 1024 / 1024

            # 磁盘指标
            disk = psutil.disk_usage('/')
            disk_used_gb = disk.used / 1024 / 1024 / 1024
            disk_total_gb = disk.total / 1024 / 1024 / 1024

            # 网络指标
            net = psutil.net_io_counters()
            network_sent_mb = net.bytes_sent / 1024 / 1024
            network_recv_mb = net.bytes_recv / 1024 / 1024

            # 负载
            load_avg = list(psutil.getloadavg()) if hasattr(psutil, 'getloadavg') else [0.0, 0.0, 0.0]

            # 运行时间
            boot_time = psutil.boot_time()
            uptime = time.time() - boot_time

            return cls(
                cpu_percent=cpu_percent,
                cpu_percent_per_cpu=cpu_per_cpu,
                memory_used_mb=memory_used_mb,
                memory_available_mb=memory_available_mb,
                memory_percent=memory.percent,
                disk_used_gb=disk_used_gb,
                disk_total_gb=disk_total_gb,
                disk_percent=disk.percent,
                network_sent_mb=network_sent_mb,
                network_recv_mb=network_recv_mb,
                load_avg=load_avg,
                boot_time=boot_time,
                uptime_seconds=uptime
            )
        except Exception as e:
            logger.error(f"收集系统资源指标失败: {e}")
            return cls(
                cpu_percent=0.0,
                cpu_percent_per_cpu=[],
                memory_used_mb=0.0,
                memory_available_mb=0.0,
                memory_percent=0.0,
                disk_used_gb=0.0,
                disk_total_gb=0.0,
                disk_percent=0.0,
                network_sent_mb=0.0,
                network_recv_mb=0.0,
                load_avg=[0.0, 0.0, 0.0],
                boot_time=0.0,
                uptime_seconds=0.0
            )


@dataclass
class RagPerformanceMetrics:
    """RAG性能指标"""
    total_queries: int = 0
    successful_queries: int = 0
    failed_queries: int = 0
    total_retrieval_time: float = 0.0
    avg_retrieval_time: float = 0.0
    avg_chunks_retrieved: float = 0.0
    token_usage_total: int = 0
    cache_hit_rate: float = 0.0

    def add_query(self, retrieval_time: float, chunks_retrieved: int = 0, success: bool = True, tokens: int = 0):
        """添加查询记录"""
        self.total_queries += 1
        if success:
            self.successful_queries += 1
            self.total_retrieval_time += retrieval_time
            self.avg_chunks_retrieved = (
                (self.avg_chunks_retrieved * (self.successful_queries - 1) + chunks_retrieved)
                / self.successful_queries
            )
        else:
            self.failed_queries += 1

        self.avg_retrieval_time = self.total_retrieval_time / self.successful_queries if self.successful_queries > 0 else 0.0
        self.token_usage_total += tokens
        self.cache_hit_rate = self._calculate_hit_rate()

    def _calculate_hit_rate(self) -> float:
        """计算缓存命中率"""
        if self.total_queries == 0:
            return 0.0
        return (self.total_queries - self.failed_queries) / self.total_queries

    @property
    def success_rate(self) -> float:
        """成功率"""
        return self.successful_queries / self.total_queries if self.total_queries > 0 else 0.0


@dataclass
class CrawlerMetrics:
    """爬虫指标"""
    source: str
    total_patents_crawled: int = 0
    successful_crawls: int = 0
    failed_crawls: int = 0
    total_crawl_time: float = 0.0
    avg_crawl_time: float = 0.0
    rate_limit_hits: int = 0
    last_crawl_time: Optional[float] = None
    daily_crawl_quota: int = 10000

    def add_crawl_result(self, success: bool, crawl_time: float = 0.0):
        """添加爬取结果"""
        if success:
            self.successful_crawls += 1
            self.total_patents_crawled += 1
            self.total_crawl_time += crawl_time
            self.avg_crawl_time = self.total_crawl_time / self.successful_crawls
        else:
            self.failed_crawls += 1
        self.last_crawl_time = time.time()

    @property
    def success_rate(self) -> float:
        """成功率"""
        total = self.successful_crawls + self.failed_crawls
        return self.successful_crawls / total if total > 0 else 0.0

    @property
    def crawl_speed(self) -> float:
        """爬取速度（专利/分钟）"""
        if self.total_crawl_time == 0:
            return 0.0
        return (self.total_patents_crawled / self.total_crawl_time) * 60


@dataclass
class AgentMetrics:
    """代理指标"""
    agent_type: str
    agent_id: str
    total_tasks: int = 0
    completed_tasks: int = 0
    failed_tasks: int = 0
    avg_task_duration: float = 0.0
    total_task_time: float = 0.0
    last_heartbeat: Optional[float] = None
    is_active: bool = False

    def add_task_result(self, success: bool, duration: float = 0.0):
        """添加任务结果"""
        self.total_tasks += 1
        if success:
            self.completed_tasks += 1
            self.total_task_time += duration
            self.avg_task_duration = self.total_task_time / self.completed_tasks
        else:
            self.failed_tasks += 1

    @property
    def success_rate(self) -> float:
        """成功率"""
        return self.completed_tasks / self.total_tasks if self.total_tasks > 0 else 0.0

    @property
    def uptime(self) -> float:
        """运行时间（秒）"""
        if self.last_heartbeat is None:
            return 0.0
        return time.time() - self.last_heartbeat


@dataclass
class CeleryTaskMetrics:
    """Celery任务指标"""
    total_tasks: int = 0
    pending_tasks: int = 0
    started_tasks: int = 0
    successful_tasks: int = 0
    failed_tasks: int = 0
    retried_tasks: int = 0
    rejected_tasks: int = 0
    avg_execution_time: float = 0.0
    total_execution_time: float = 0.0
    queue_length: int = 0
    worker_count: int = 0
    active_tasks: int = 0

    def add_task_event(self, status: str, duration: float = 0.0):
        """添加任务事件"""
        self.total_tasks += 1
        if status == 'pending':
            self.pending_tasks += 1
        elif status == 'started':
            self.started_tasks += 1
        elif status == 'success':
            self.successful_tasks += 1
            self.total_execution_time += duration
            self.avg_execution_time = self.total_execution_time / self.successful_tasks
        elif status == 'failed':
            self.failed_tasks += 1
        elif status == 'retry':
            self.retried_tasks += 1
        elif status == 'rejected':
            self.rejected_tasks += 1

    @property
    def success_rate(self) -> float:
        """成功率"""
        return self.successful_tasks / self.total_tasks if self.total_tasks > 0 else 0.0


class MetricsCollector:
    """指标收集器"""

    def __init__(self):
        self._rag_metrics = RagPerformanceMetrics()
        self._crawler_metrics: Dict[str, CrawlerMetrics] = {}
        self._agent_metrics: Dict[str, AgentMetrics] = {}
        self._celery_metrics = CeleryTaskMetrics()
        self._history: List[Dict[str, Any]] = []
        self._max_history_size = 1000
        self._start_time = time.time()

    # RAG指标
    def get_rag_metrics(self) -> RagPerformanceMetrics:
        """获取RAG指标"""
        return self._rag_metrics

    def record_rag_query(
        self,
        retrieval_time: float,
        chunks_retrieved: int = 0,
        success: bool = True,
        tokens: int = 0
    ):
        """记录RAG查询"""
        self._rag_metrics.add_query(retrieval_time, chunks_retrieved, success, tokens)

    # 爬虫指标
    def get_crawler_metrics(self, source: str) -> CrawlerMetrics:
        """获取爬虫指标"""
        if source not in self._crawler_metrics:
            self._crawler_metrics[source] = CrawlerMetrics(source=source)
        return self._crawler_metrics[source]

    def get_all_crawler_metrics(self) -> Dict[str, CrawlerMetrics]:
        """获取所有爬虫指标"""
        return self._crawler_metrics

    def record_crawl_result(self, source: str, success: bool, crawl_time: float = 0.0):
        """记录爬取结果"""
        metrics = self.get_crawler_metrics(source)
        metrics.add_crawl_result(success, crawl_time)

    # Agent指标
    def get_agent_metrics(self, agent_id: str) -> AgentMetrics:
        """获取代理指标"""
        if agent_id not in self._agent_metrics:
            self._agent_metrics[agent_id] = AgentMetrics(
                agent_type="generic",
                agent_id=agent_id
            )
        return self._agent_metrics[agent_id]

    def register_agent(self, agent_id: str, agent_type: str):
        """注册代理"""
        self._agent_metrics[agent_id] = AgentMetrics(
            agent_type=agent_type,
            agent_id=agent_id,
            last_heartbeat=time.time(),
            is_active=True
        )

    def update_agent_heartbeat(self, agent_id: str):
        """更新代理心跳"""
        if agent_id in self._agent_metrics:
            self._agent_metrics[agent_id].last_heartbeat = time.time()
            self._agent_metrics[agent_id].is_active = True

    def record_agent_task(self, agent_id: str, success: bool, duration: float = 0.0):
        """记录代理任务"""
        metrics = self.get_agent_metrics(agent_id)
        metrics.add_task_result(success, duration)

    # Celery指标
    def get_celery_metrics(self) -> CeleryTaskMetrics:
        """获取Celery任务指标"""
        return self._celery_metrics

    def record_celery_task(self, status: str, duration: float = 0.0):
        """记录Celery任务事件"""
        self._celery_metrics.add_task_event(status, duration)

    def update_celery_stats(self, queue_length: int, worker_count: int, active_tasks: int):
        """更新Celery统计信息"""
        self._celery_metrics.queue_length = queue_length
        self._celery_metrics.worker_count = worker_count
        self._celery_metrics.active_tasks = active_tasks

    # 系统资源指标
    def get_system_metrics(self) -> SystemResourceMetrics:
        """获取系统资源指标"""
        return SystemResourceMetrics.collect()

    # 历史数据
    def save_history(self):
        """保存当前指标到历史"""
        current_time = datetime.now()

        snapshot = {
            "timestamp": current_time.isoformat(),
            "system_metrics": self.get_system_metrics().__dict__,
            "rag_metrics": self._rag_metrics.__dict__,
            "crawler_metrics": {
                source: metrics.__dict__
                for source, metrics in self._crawler_metrics.items()
            },
            "agent_metrics": {
                agent_id: metrics.__dict__
                for agent_id, metrics in self._agent_metrics.items()
            },
            "celery_metrics": self._celery_metrics.__dict__
        }

        self._history.append(snapshot)

        # 限制历史记录大小
        if len(self._history) > self._max_history_size:
            self._history = self._history[-self._max_history_size:]

    def get_history(
        self,
        hours: int = 24,
        limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """获取历史数据"""
        cutoff_time = datetime.now() - timedelta(hours=hours)
        filtered = [
            entry for entry in self._history
            if datetime.fromisoformat(entry["timestamp"]) >= cutoff_time
        ]

        if limit:
            return filtered[-limit:]

        return filtered

    def get_statistics(self) -> Dict[str, Any]:
        """获取统计摘要"""
        history = self.get_history(hours=24)

        if not history:
            return {
                "uptime_seconds": time.time() - self._start_time,
                "data_points": 0
            }

        # 计算平均值
        avg_cpu = sum(h["system_metrics"]["cpu_percent"] for h in history) / len(history)
        avg_memory = sum(h["system_metrics"]["memory_percent"] for h in history) / len(history)

        return {
            "uptime_seconds": time.time() - self._start_time,
            "data_points": len(history),
            "avg_cpu_percent": round(avg_cpu, 2),
            "avg_memory_percent": round(avg_memory, 2),
            "total_rag_queries": self._rag_metrics.total_queries,
            "rag_success_rate": round(self._rag_metrics.success_rate * 100, 2),
            "total_patents_crawled": sum(m.total_patents_crawled for m in self._crawler_metrics.values()),
            "total_agent_tasks": sum(m.total_tasks for m in self._agent_metrics.values()),
            "celery_queue_length": self._celery_metrics.queue_length,
            "celery_worker_count": self._celery_metrics.worker_count,
        }

    def reset(self):
        """重置所有指标"""
        self._rag_metrics = RagPerformanceMetrics()
        self._crawler_metrics.clear()
        self._agent_metrics.clear()
        self._celery_metrics = CeleryTaskMetrics()
        self._history.clear()
        self._start_time = time.time()
        logger.info("指标收集器已重置")


# 全局实例
collector = MetricsCollector()


def get_collector() -> MetricsCollector:
    """获取全局指标收集器实例"""
    return collector
