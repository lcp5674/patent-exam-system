"""
缓存工具函数
"""

import hashlib
import inspect
import json
import pickle
from typing import Any, Optional, Tuple
from functools import wraps


def generate_cache_key(func_name: str, args: tuple, kwargs: dict) -> str:
    """生成缓存键

    基于函数名、参数生成唯一缓存键
    """
    # 创建键组件
    key_components = [func_name]

    # 添加位置参数
    for arg in args:
        key_components.append(_serialize_for_key(arg))

    # 添加关键字参数（排序确保一致性）
    for key in sorted(kwargs.keys()):
        key_components.append(f"{key}={_serialize_for_key(kwargs[key])}")

    # 合并并生成哈希
    cache_key = ":".join(key_components)

    # 使用MD5生成固定长度的键（避免过长）
    return f"patent_cache:{hashlib.md5(cache_key.encode()).hexdigest()}"


def _serialize_for_key(value: Any) -> str:
    """序列化值为字符串用于缓存键"""
    if value is None:
        return "None"

    if isinstance(value, (str, int, float, bool)):
        return str(value)

    # 对于复杂对象，使用pickle序列化后哈希
    try:
        serialized = pickle.dumps(value)
        return hashlib.md5(serialized).hexdigest()[:8]
    except:
        # 如果无法序列化，使用类型和ID
        return f"{type(value).__name__}:{id(value)}"


async def clear_cache(pattern: str = "patent_cache:*"):
    """清除匹配的缓存项

    Args:
        pattern: 要清除的缓存键模式

    Example:
        # 清除所有缓存
        await clear_cache()

        # 清除特定函数的缓存
        await clear_cache("patent_cache:*get_patent_list*")
    """
    from app.cache.client import get_redis_client

    redis = await get_redis_client()

    # 查找匹配的键
    keys = await redis.keys(pattern)

    if keys:
        await redis.delete(*keys)

    return len(keys)


async def get_cache_info(key: str) -> Optional[dict]:
    """获取缓存项信息

    Args:
        key: 缓存键

    Returns:
        包含TTL和大小的字典，或None
    """
    from app.cache.client import get_redis_client
    from datetime import timedelta

    redis = await get_redis_client()

    # 检查键是否存在
    if not await redis.exists(key):
        return None

    # 获取TTL（秒）
    ttl = await redis.ttl(key)

    # 获取值大小
    value = await redis.get(key)
    size = len(value) if value else 0

    return {
        "key": key,
        "ttl": ttl,
        "size_bytes": size,
        "exists": True
    }


def make_hash_key(namespace: str, key: str) -> str:
    """生成带命名空间的缓存键"""
    return f"{namespace}:{key}"


class CacheStatistics:
    """缓存统计"""

    def __init__(self):
        self.hits = 0
        self.misses = 0
        self.errors = 0

    @property
    def hit_rate(self) -> float:
        """缓存命中率"""
        total = self.hits + self.misses
        if total == 0:
            return 0.0
        return self.hits / total

    def reset(self):
        """重置统计"""
        self.hits = 0
        self.misses = 0
        self.errors = 0


# 全局缓存统计实例
cache_stats = CacheStatistics()
