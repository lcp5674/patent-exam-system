"""
缓存装饰器
提供方法级别的Redis缓存
"""

import asyncio
import hashlib
import json
import pickle
from typing import Optional, Any, Callable, Union
from functools import wraps
from app.cache.utils import generate_cache_key
from app.config import settings


class CacheDecorator:
    """异步缓存装饰器"""

    def __init__(
        self,
        ttl: int = None,
        key_pattern: str = None,
        unless: Callable = None,
        fallback: Callable = None
    ):
        self.ttl = ttl or settings.cache.CACHE_DEFAULT_TTL
        self.key_pattern = key_pattern
        self.unless = unless
        self.fallback = fallback

    def __call__(self, func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # 检查缓存是否启用
            if not settings.cache.CACHE_ENABLED:
                return await func(*args, **kwargs)

            # 检查unless条件
            if self.unless and self.unless(*args, **kwargs):
                return await func(*args, **kwargs)

            # 生成缓存键
            cache_key = self._get_cache_key(func, args, kwargs)

            try:
                # 尝试从缓存获取
                from app.cache.client import get_redis_client
                redis = await get_redis_client()

                cached_value = await redis.get(cache_key)
                if cached_value is not None:
                    return pickle.loads(cached_value)

                # 执行函数
                result = await func(*args, **kwargs)

                # 存储到缓存
                if result is not None:
                    serialized = pickle.dumps(result)
                    await redis.setex(cache_key, self.ttl, serialized)

                return result

            except Exception as e:
                # 缓存错误不影响主流程
                if self.fallback:
                    return await self.fallback(e, *args, **kwargs)
                else:
                    return await func(*args, **kwargs)

        # 为清除缓存提供cache_key方法
        wrapper.cache_key = lambda *args, **kwargs: self._get_cache_key(func, args, kwargs)

        return wrapper

    def _get_cache_key(self, func: Callable, args: tuple, kwargs: dict) -> str:
        """生成缓存键"""
        if self.key_pattern:
            # 使用自定义键模式
            return self.key_pattern.format(*args, **kwargs)
        else:
            # 自动生成缓存键
            return generate_cache_key(func.__name__, args, kwargs)


class ConditionalCacheDecorator(CacheDecorator):
    """条件缓存装饰器"""

    def __init__(self, condition: Callable, **kwargs):
        super().__init__(**kwargs)
        self.condition = condition

    def __call__(self, func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # 检查条件
            if not self.condition(*args, **kwargs):
                return await func(*args, **kwargs)

            return await super().__call__(func)(*args, **kwargs)

        return wrapper


def cache(
    ttl: int = None,
    key_pattern: str = None,
    unless: Callable = None,
    fallback: Callable = None
):
    """通用缓存装饰器

    Args:
        ttl: 缓存过期时间（秒）
        key_pattern: 自定义缓存键模式
        unless: 条件函数，返回True时不使用缓存
        fallback: 缓存出错时的回退函数

    Example:
        @cache(ttl=300)
        async def get_patent_list(filters):
            # 自动缓存5分钟
            pass

        @cache(key_pattern="user_{user_id}")
        async def get_user_profile(user_id):
            # 使用自定义缓存键
            pass
    """
    return CacheDecorator(ttl=ttl, key_pattern=key_pattern, unless=unless, fallback=fallback)


def cache_key_pattern(pattern: str):
    """使用键模式的缓存装饰器"""
    def decorator(func: Callable) -> Callable:
        return CacheDecorator(key_pattern=pattern)(func)
    return decorator


def conditional_cache(condition: Callable, ttl: int = None):
    """条件缓存装饰器

    Example:
        def is_cacheable(user_id):
            return user_id > 1000  # 只缓存新用户

        @conditional_cache(is_cacheable, ttl=300)
        async def get_user_data(user_id):
            pass
    """
    return ConditionalCacheDecorator(condition=condition, ttl=ttl)