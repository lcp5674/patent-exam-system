"""
监控服务
Prometheus指标和健康检查
"""
from __future__ import annotations
import time
import logging
from typing import Optional, Dict, Any
from functools import wraps
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# 尝试导入prometheus_client
try:
    from prometheus_client import Counter, Histogram, Gauge, Info, generate_latest, CONTENT_TYPE_LATEST
    PROMETHEUS_AVAILABLE = True
except ImportError:
    PROMETHEUS_AVAILABLE = False
    Counter = Histogram = Gauge = Info = None


@dataclass
class Metrics:
    """应用指标"""
    # HTTP请求
    http_requests_total: Any = field(default=None)
    http_request_duration_seconds: Any = field(default=None)
    http_requests_in_progress: Any = field(default=None)
    
    # API调用
    api_calls_total: Any = field(default=None)
    api_call_duration_seconds: Any = field(default=None)
    
    # AI调用
    ai_requests_total: Any = field(default=None)
    ai_request_duration_seconds: Any = field(default=None)
    ai_requests_errors: Any = field(default=None)
    
    # RAG
    rag_queries_total: Any = field(default=None)
    rag_query_duration_seconds: Any = field(default=None)
    rag_chunks_retrieved: Any = field(default=None)
    
    # 专利数据库
    patent_searches_total: Any = field(default=None)
    patent_search_duration_seconds: Any = field(default=None)
    
    # 缓存
    cache_hits_total: Any = field(default=None)
    cache_misses_total: Any = field(default=None)
    
    # 数据库
    db_connections_active: Any = field(default=None)
    db_queries_total: Any = field(default=None)
    
    # 系统
    active_users: Any = field(default=None)
    queued_tasks: Any = field(default=None)


class MonitoringService:
    """监控服务"""
    
    def __init__(self):
        self._initialized = False
        self._metrics = None
        self._start_time = time.time()
    
    def initialize(self):
        """初始化监控指标"""
        if self._initialized or not PROMETHEUS_AVAILABLE:
            return
        
        try:
            self._metrics = Metrics()
            
            # HTTP请求指标
            self._metrics.http_requests_total = Counter(
                'http_requests_total',
                'Total HTTP requests',
                ['method', 'endpoint', 'status']
            )
            self._metrics.http_request_duration_seconds = Histogram(
                'http_request_duration_seconds',
                'HTTP request duration in seconds',
                ['method', 'endpoint']
            )
            self._metrics.http_requests_in_progress = Gauge(
                'http_requests_in_progress',
                'HTTP requests in progress'
            )
            
            # API调用指标
            self._metrics.api_calls_total = Counter(
                'api_calls_total',
                'Total API calls',
                ['endpoint', 'method']
            )
            self._metrics.api_call_duration_seconds = Histogram(
                'api_call_duration_seconds',
                'API call duration in seconds',
                ['endpoint', 'method']
            )
            
            # AI调用指标
            self._metrics.ai_requests_total = Counter(
                'ai_requests_total',
                'Total AI requests',
                ['provider', 'model', 'status']
            )
            self._metrics.ai_request_duration_seconds = Histogram(
                'ai_request_duration_seconds',
                'AI request duration in seconds',
                ['provider', 'model']
            )
            self._metrics.ai_requests_errors = Counter(
                'ai_requests_errors',
                'Total AI request errors',
                ['provider', 'error_type']
            )
            
            # RAG指标
            self._metrics.rag_queries_total = Counter(
                'rag_queries_total',
                'Total RAG queries',
                ['search_type', 'status']
            )
            self._metrics.rag_query_duration_seconds = Histogram(
                'rag_query_duration_seconds',
                'RAG query duration in seconds',
                ['search_type']
            )
            self._metrics.rag_chunks_retrieved = Histogram(
                'rag_chunks_retrieved',
                'RAG chunks retrieved per query',
                buckets=[1, 5, 10, 20, 50, 100]
            )
            
            # 专利搜索指标
            self._metrics.patent_searches_total = Counter(
                'patent_searches_total',
                'Total patent searches',
                ['source', 'status']
            )
            self._metrics.patent_search_duration_seconds = Histogram(
                'patent_search_duration_seconds',
                'Patent search duration in seconds',
                ['source']
            )
            
            # 缓存指标
            self._metrics.cache_hits_total = Counter(
                'cache_hits_total',
                'Total cache hits',
                ['cache_name']
            )
            self._metrics.cache_misses_total = Counter(
                'cache_misses_total',
                'Total cache misses',
                ['cache_name']
            )
            
            # 数据库指标
            self._metrics.db_connections_active = Gauge(
                'db_connections_active',
                'Active database connections'
            )
            self._metrics.db_queries_total = Counter(
                'db_queries_total',
                'Total database queries',
                ['query_type']
            )
            
            # 系统指标
            self._metrics.active_users = Gauge(
                'active_users',
                'Number of active users'
            )
            self._metrics.queued_tasks = Gauge(
                'queued_tasks',
                'Number of queued tasks'
            )
            
            self._initialized = True
            logger.info("监控服务初始化完成")
            
        except Exception as e:
            logger.error(f"监控服务初始化失败: {e}")
            self._initialized = False
    
    def record_http_request(
        self, 
        method: str, 
        endpoint: str, 
        status: int,
        duration: float
    ):
        """记录HTTP请求"""
        if not self._initialized or not self._metrics:
            return
        
        try:
            self._metrics.http_requests_total.labels(
                method=method,
                endpoint=endpoint,
                status=str(status)
            ).inc()
            
            self._metrics.http_request_duration_seconds.labels(
                method=method,
                endpoint=endpoint
            ).observe(duration)
        except Exception as e:
            logger.error(f"记录HTTP指标失败: {e}")
    
    def record_api_call(self, endpoint: str, method: str, duration: float):
        """记录API调用"""
        if not self._initialized or not self._metrics:
            return
        
        try:
            self._metrics.api_calls_total.labels(
                endpoint=endpoint,
                method=method
            ).inc()
            
            self._metrics.api_call_duration_seconds.labels(
                endpoint=endpoint,
                method=method
            ).observe(duration)
        except Exception as e:
            logger.error(f"记录API指标失败: {e}")
    
    def record_ai_request(
        self,
        provider: str,
        model: str,
        status: str,
        duration: float
    ):
        """记录AI请求"""
        if not self._initialized or not self._metrics:
            return
        
        try:
            self._metrics.ai_requests_total.labels(
                provider=provider,
                model=model,
                status=status
            ).inc()
            
            self._metrics.ai_request_duration_seconds.labels(
                provider=provider,
                model=model
            ).observe(duration)
        except Exception as e:
            logger.error(f"记录AI指标失败: {e}")
    
    def record_ai_error(self, provider: str, error_type: str):
        """记录AI错误"""
        if not self._initialized or not self._metrics:
            return
        
        try:
            self._metrics.ai_requests_errors.labels(
                provider=provider,
                error_type=error_type
            ).inc()
        except Exception as e:
            logger.error(f"记录AI错误失败: {e}")
    
    def record_rag_query(
        self,
        search_type: str,
        status: str,
        duration: float,
        chunks_retrieved: int = 0
    ):
        """记录RAG查询"""
        if not self._initialized or not self._metrics:
            return
        
        try:
            self._metrics.rag_queries_total.labels(
                search_type=search_type,
                status=status
            ).inc()
            
            self._metrics.rag_query_duration_seconds.labels(
                search_type=search_type
            ).observe(duration)
            
            if chunks_retrieved > 0:
                self._metrics.rag_chunks_retrieved.observe(chunks_retrieved)
        except Exception as e:
            logger.error(f"记录RAG指标失败: {e}")
    
    def record_patent_search(
        self,
        source: str,
        status: str,
        duration: float
    ):
        """记录专利搜索"""
        if not self._initialized or not self._metrics:
            return
        
        try:
            self._metrics.patent_searches_total.labels(
                source=source,
                status=status
            ).inc()
            
            self._metrics.patent_search_duration_seconds.labels(
                source=source
            ).observe(duration)
        except Exception as e:
            logger.error(f"记录专利搜索指标失败: {e}")
    
    def record_cache_hit(self, cache_name: str):
        """记录缓存命中"""
        if not self._initialized or not self._metrics:
            return
        
        try:
            self._metrics.cache_hits_total.labels(cache_name=cache_name).inc()
        except Exception as e:
            logger.error(f"记录缓存命中失败: {e}")
    
    def record_cache_miss(self, cache_name: str):
        """记录缓存未命中"""
        if not self._initialized or not self._metrics:
            return
        
        try:
            self._metrics.cache_misses_total.labels(cache_name=cache_name).inc()
        except Exception as e:
            logger.error(f"记录缓存未命中失败: {e}")
    
    def set_active_users(self, count: int):
        """设置活跃用户数"""
        if not self._initialized or not self._metrics:
            return
        
        try:
            self._metrics.active_users.set(count)
        except Exception as e:
            logger.error(f"设置活跃用户数失败: {e}")
    
    def set_queued_tasks(self, count: int):
        """设置排队任务数"""
        if not self._initialized or not self._metrics:
            return
        
        try:
            self._metrics.queued_tasks.set(count)
        except Exception as e:
            logger.error(f"设置排队任务数失败: {e}")
    
    def get_metrics(self) -> bytes:
        """获取Prometheus指标"""
        if not PROMETHEUS_AVAILABLE:
            return b""
        
        return generate_latest()
    
    def get_metrics_content_type(self) -> str:
        """获取指标内容类型"""
        return CONTENT_TYPE_LATEST
    
    def get_status(self) -> Dict[str, Any]:
        """获取系统状态"""
        uptime = time.time() - self._start_time
        
        return {
            "uptime_seconds": uptime,
            "prometheus_available": PROMETHEUS_AVAILABLE,
            "initialized": self._initialized,
        }


# 全局实例
monitoring = MonitoringService()


# ============== 便捷装饰器 ==============

def monitor_api_call(endpoint: str):
    """API调用监控装饰器"""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            start_time = time.time()
            status = "success"
            
            try:
                result = await func(*args, **kwargs)
                return result
            except Exception as e:
                status = "error"
                raise
            finally:
                duration = time.time() - start_time
                monitoring.record_api_call(endpoint, "POST", duration)
        
        return wrapper
    return decorator


def monitor_ai_request(provider: str, model: str):
    """AI请求监控装饰器"""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            start_time = time.time()
            status = "success"
            
            try:
                result = await func(*args, **kwargs)
                return result
            except Exception as e:
                status = "error"
                monitoring.record_ai_error(provider, type(e).__name__)
                raise
            finally:
                duration = time.time() - start_time
                monitoring.record_ai_request(provider, model, status, duration)
        
        return wrapper
    return decorator
