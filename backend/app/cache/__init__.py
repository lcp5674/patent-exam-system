"""
Redis缓存模块
提供缓存装饰器和Redis客户端包装
"""

from .client import get_redis_client, redis_client
from .decorators import cache, cache_key_pattern
from .utils import generate_cache_key, clear_cache

__all__ = ["get_redis_client", "redis_client", "cache", "cache_key_pattern",
           "generate_cache_key", "clear_cache"]
