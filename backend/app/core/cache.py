"""
Redis缓存服务
提供高性能缓存支持
"""
from __future__ import annotations
import json
import logging
import os
from typing import Optional, Any, List
from datetime import timedelta
from functools import wraps

import redis.asyncio as aioredis
from redis.asyncio import Redis

logger = logging.getLogger(__name__)

# 全局Redis客户端
_redis_client: Optional[Redis] = None


class RedisCache:
    """Redis缓存管理器"""
    
    def __init__(self):
        self._client: Optional[Redis] = None
        self._settings = None
    
    def _get_settings(self):
        """获取缓存配置"""
        if self._settings is None:
            from app.config import CacheSettings
            self._settings = CacheSettings()
        return self._settings
    
    async def get_client(self) -> Redis:
        """获取Redis客户端"""
        if self._client is None:
            settings = self._get_settings()
            
            # 构建Redis URL
            if settings.REDIS_PASSWORD:
                redis_url = f"redis://:{settings.REDIS_PASSWORD}@{settings.REDIS_HOST}:{settings.REDIS_PORT}/{settings.REDIS_DB}"
            else:
                redis_url = f"redis://{settings.REDIS_HOST}:{settings.REDIS_PORT}/{settings.REDIS_DB}"
            
            self._client = aioredis.from_url(
                redis_url,
                encoding="utf-8",
                decode_responses=True,
                max_connections=settings.REDIS_MAX_CONNECTIONS,
            )
            logger.info(f"Redis连接: {settings.REDIS_HOST}:{settings.REDIS_PORT}")
        
        return self._client
    
    async def close(self):
        """关闭连接"""
        if self._client:
            await self._client.close()
            self._client = None
    
    # ============== 基础操作 ==============
    
    async def get(self, key: str) -> Optional[str]:
        """获取值"""
        try:
            client = await self.get_client()
            return await client.get(key)
        except Exception as e:
            logger.error(f"Redis get失败: {e}")
            return None
    
    async def set(
        self, 
        key: str, 
        value: Any, 
        expire: Optional[int] = None
    ) -> bool:
        """设置值"""
        try:
            client = await self.get_client()
            if isinstance(value, (dict, list)):
                value = json.dumps(value, ensure_ascii=False)
            if expire:
                await client.setex(key, expire, value)
            else:
                await client.set(key, value)
            return True
        except Exception as e:
            logger.error(f"Redis set失败: {e}")
            return False
    
    async def delete(self, key: str) -> bool:
        """删除键"""
        try:
            client = await self.get_client()
            await client.delete(key)
            return True
        except Exception as e:
            logger.error(f"Redis delete失败: {e}")
            return False
    
    async def exists(self, key: str) -> bool:
        """检查键是否存在"""
        try:
            client = await self.get_client()
            return await client.exists(key) > 0
        except Exception as e:
            logger.error(f"Redis exists失败: {e}")
            return False
    
    async def expire(self, key: str, seconds: int) -> bool:
        """设置过期时间"""
        try:
            client = await self.get_client()
            return await client.expire(key, seconds)
        except Exception as e:
            logger.error(f"Redis expire失败: {e}")
            return False
    
    async def ttl(self, key: str) -> int:
        """获取剩余过期时间"""
        try:
            client = await self.get_client()
            return await client.ttl(key)
        except Exception as e:
            logger.error(f"Redis ttl失败: {e}")
            return -2
    
    # ============== 模式匹配 ==============
    
    async def keys(self, pattern: str) -> List[str]:
        """查找匹配的键"""
        try:
            client = await self.get_client()
            return await client.keys(pattern)
        except Exception as e:
            logger.error(f"Redis keys失败: {e}")
            return []
    
    async def delete_pattern(self, pattern: str) -> int:
        """删除匹配的所有键"""
        try:
            client = await self.get_client()
            keys = await client.keys(pattern)
            if keys:
                return await client.delete(*keys)
            return 0
        except Exception as e:
            logger.error(f"Redis delete_pattern失败: {e}")
            return 0
    
    # ============== 计数器 ==============
    
    async def incr(self, key: str, amount: int = 1) -> int:
        """递增计数器"""
        try:
            client = await self.get_client()
            return await client.incr(key, amount)
        except Exception as e:
            logger.error(f"Redis incr失败: {e}")
            return 0
    
    async def decr(self, key: str, amount: int = 1) -> int:
        """递减计数器"""
        try:
            client = await self.get_client()
            return await client.decr(key, amount)
        except Exception as e:
            logger.error(f"Redis decr失败: {e}")
            return 0
    
    # ============== 哈希操作 ==============
    
    async def hget(self, key: str, field: str) -> Optional[str]:
        """获取哈希字段值"""
        try:
            client = await self.get_client()
            return await client.hget(key, field)
        except Exception as e:
            logger.error(f"Redis hget失败: {e}")
            return None
    
    async def hset(self, key: str, field: str, value: Any) -> bool:
        """设置哈希字段值"""
        try:
            client = await self.get_client()
            if isinstance(value, (dict, list)):
                value = json.dumps(value, ensure_ascii=False)
            await client.hset(key, field, value)
            return True
        except Exception as e:
            logger.error(f"Redis hset失败: {e}")
            return False
    
    async def hgetall(self, key: str) -> dict:
        """获取所有哈希字段"""
        try:
            client = await self.get_client()
            return await client.hgetall(key)
        except Exception as e:
            logger.error(f"Redis hgetall失败: {e}")
            return {}
    
    async def hdel(self, key: str, *fields: str) -> int:
        """删除哈希字段"""
        try:
            client = await self.get_client()
            return await client.hdel(key, *fields)
        except Exception as e:
            logger.error(f"Redis hdel失败: {e}")
            return 0
    
    # ============== 列表操作 ==============
    
    async def lpush(self, key: str, *values: Any) -> int:
        """推送到列表头部"""
        try:
            client = await self.get_client()
            serialized = []
            for v in values:
                if isinstance(v, (dict, list)):
                    serialized.append(json.dumps(v, ensure_ascii=False))
                else:
                    serialized.append(str(v))
            return await client.lpush(key, *serialized)
        except Exception as e:
            logger.error(f"Redis lpush失败: {e}")
            return 0
    
    async def lrange(self, key: str, start: int = 0, end: int = -1) -> List[str]:
        """获取列表范围"""
        try:
            client = await self.get_client()
            return await client.lrange(key, start, end)
        except Exception as e:
            logger.error(f"Redis lrange失败: {e}")
            return []
    
    # ============== 缓存装饰器 ==============
    
    def cached(self, expire: int = 300, key_prefix: str = ""):
        """缓存装饰器
        
        用法:
        @cache.cached(expire=60, key_prefix="user:")
        async def get_user(user_id: int):
            ...
        """
        def decorator(func):
            @wraps(func)
            async def wrapper(*args, **kwargs):
                # 生成缓存键
                cache_key = f"{key_prefix}{func.__name__}"
                if args:
                    cache_key += f":{':'.join(str(a) for a in args)}"
                if kwargs:
                    cache_key += f":{':'.join(f'{k}={v}' for k, v in sorted(kwargs.items()))}"
                
                # 尝试从缓存获取
                cached = await self.get(cache_key)
                if cached:
                    try:
                        return json.loads(cached)
                    except json.JSONDecodeError:
                        return cached
                
                # 执行函数
                result = await func(*args, **kwargs)
                
                # 存入缓存
                await self.set(cache_key, result, expire)
                
                return result
            
            return wrapper
        return decorator
    
    # ============== 健康检查 ==============
    
    async def ping(self) -> bool:
        """健康检查"""
        try:
            client = await self.get_client()
            return await client.ping()
        except Exception as e:
            logger.error(f"Redis ping失败: {e}")
            return False
    
    async def info(self) -> dict:
        """获取Redis信息"""
        try:
            client = await self.get_client()
            return await client.info()
        except Exception as e:
            logger.error(f"Redis info失败: {e}")
            return {}


# 全局实例
cache = RedisCache()


# ============== 便捷函数 ==============

async def get_cached(key: str, default: Any = None) -> Any:
    """获取缓存值"""
    value = await cache.get(key)
    if value is None:
        return default
    try:
        return json.loads(value)
    except (json.JSONDecodeError, TypeError):
        return value


async def set_cached(key: str, value: Any, expire: Optional[int] = None) -> bool:
    """设置缓存值"""
    return await cache.set(key, value, expire)


async def delete_cached(key: str) -> bool:
    """删除缓存"""
    return await cache.delete(key)


async def invalidate_pattern(pattern: str) -> int:
    """使匹配的所有缓存失效"""
    return await cache.delete_pattern(pattern)
