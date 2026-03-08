"""
Redis客户端包装器
提供单例模式的Redis连接管理
"""

import redis
import redis.asyncio as aioredis
import asyncio
from functools import wraps
from typing import Optional, Union
from app.config import settings


class AsyncRedisClient:
    """异步Redis客户端包装器"""

    _instance: Optional['AsyncRedisClient'] = None
    _lock = asyncio.Lock()

    def __init__(self):
        self._client: Optional[aioredis.Redis] = None
        self._pool: Optional[aioredis.ConnectionPool] = None

    async def initialize(self):
        """初始化Redis连接池"""
        if self._client is None:
            self._pool = aioredis.ConnectionPool.from_url(
                f"redis://:{settings.cache.REDIS_PASSWORD}@{settings.cache.REDIS_HOST}:{settings.cache.REDIS_PORT}/{settings.cache.REDIS_DB}",
                max_connections=settings.cache.REDIS_MAX_CONNECTIONS,
                decode_responses=True
            )
            self._client = aioredis.Redis.from_pool(self._pool)

    async def close(self):
        """关闭Redis连接"""
        if self._client:
            await self._client.close()
        if self._pool:
            await self._pool.disconnect()

    @property
    def client(self) -> aioredis.Redis:
        """获取Redis客户端"""
        if self._client is None:
            raise RuntimeError("Redis client not initialized. Call initialize() first.")
        return self._client

    @classmethod
    async def get_instance(cls) -> 'AsyncRedisClient':
        """获取单例实例"""
        if cls._instance is None:
            async with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
                    await cls._instance.initialize()
        return cls._instance


# 全局Redis客户端实例
redis_client: Optional[AsyncRedisClient] = None


async def get_redis_client() -> aioredis.Redis:
    """获取Redis客户端"""
    global redis_client
    if redis_client is None:
        redis_client = await AsyncRedisClient.get_instance()
    return redis_client.client


async def init_redis():
    """初始化Redis连接"""
    global redis_client
    redis_client = await AsyncRedisClient.get_instance()
    return redis_client


async def close_redis():
    """关闭Redis连接"""
    global redis_client
    if redis_client:
        await redis_client.close()
        redis_client = None
