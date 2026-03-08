"""爬虫工具模块"""
import asyncio
import time
import random
from typing import Optional, Callable, Any, Dict, List
import logging
from dataclasses import dataclass
import httpx
import redis.asyncio as redis

logger = logging.getLogger(__name__)


@dataclass
class ProxyInfo:
    """代理信息"""
    host: str
    port: int
    username: Optional[str] = None
    password: Optional[str] = None
    protocol: str = "http"

    @property
    def url(self) -> str:
        """获取代理URL"""
        if self.username and self.password:
            return f"{self.protocol}://{self.username}:{self.password}@{self.host}:{self.port}"
        return f"{self.protocol}://{self.host}:{self.port}"


class RateLimiter:
    """速率限制器"""

    def __init__(self, min_interval: float = 1.0, max_interval: Optional[float] = None):
        """
        初始化速率限制器

        Args:
            min_interval: 最小间隔（秒）
            max_interval: 最大间隔（秒），None表示固定间隔
        """
        self.min_interval = min_interval
        self.max_interval = max_interval or min_interval
        self.last_request_time = 0
        self.lock = asyncio.Lock()

    async def acquire(self):
        """获取请求许可"""
        async with self.lock:
            now = time.time()
            elapsed = now - self.last_request_time

            # 计算需要等待的时间
            if self.min_interval == self.max_interval:
                wait_time = max(0, self.min_interval - elapsed)
            else:
                min_wait = max(0, self.min_interval - elapsed)
                max_wait = max(0, self.max_interval - elapsed)
                wait_time = random.uniform(min_wait, max_wait)

            if wait_time > 0:
                logger.debug(f"速率限制：等待 {wait_time:.2f} 秒")
                await asyncio.sleep(wait_time)

            self.last_request_time = time.time()

    async def __aenter__(self):
        await self.acquire()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass


class RetryHandler:
    """重试处理器"""

    def __init__(self, max_retries: int = 3, backoff_factor: float = 1.0):
        """
        初始化重试处理器

        Args:
            max_retries: 最大重试次数
            backoff_factor: 退避因子
        """
        self.max_retries = max_retries
        self.backoff_factor = backoff_factor

    async def execute_with_retry(
            self,
            func: Callable,
            *args,
            **kwargs
    ) -> Any:
        """
        执行带重试的函数

        Args:
            func: 要执行的函数
            *args: 位置参数
            **kwargs: 关键字参数

        Returns:
            函数执行结果
        """
        last_exception = None

        for attempt in range(self.max_retries + 1):
            try:
                if asyncio.iscoroutinefunction(func):
                    result = await func(*args, **kwargs)
                else:
                    result = func(*args, **kwargs)

                if attempt > 0:
                    logger.info(f"第 {attempt + 1} 次重试成功")

                return result

            except Exception as e:
                last_exception = e
                logger.warning(f"第 {attempt + 1} 次尝试失败: {e}")

                if attempt < self.max_retries:
                    # 计算退避时间
                    backoff_time = self.backoff_factor * (2  ** attempt)
                    backoff_time = min(backoff_time, 60)  # 最多等待60秒
                    backoff_time = random.uniform(backoff_time * 0.5, backoff_time * 1.5)

                    logger.info(f"等待 {backoff_time:.2f} 秒后重试...")
                    await asyncio.sleep(backoff_time)

        # 所有重试都失败
        logger.error(f"所有 {self.max_retries + 1} 次尝试均失败")
        raise last_exception

    def should_retry(self, exception: Exception) -> bool:
        """
        判断是否应该重试

        Args:
            exception: 异常对象

        Returns:
            是否应该重试
        """
        # 网络错误应该重试
        if isinstance(exception, (httpx.NetworkError, httpx.TimeoutException)):
            return True

        # HTTP状态码判断
        if isinstance(exception, httpx.HTTPStatusError):
            status_code = exception.response.status_code
            # 5xx错误和429（请求过多）应该重试
            if status_code >= 500 or status_code == 429:
                return True

        return False


class ProxyManager:
    """代理管理器"""

    def __init__(self, redis_client: Optional[redis.Redis] = None):
        """
        初始化代理管理器

        Args:
            redis_client: Redis客户端（用于共享代理池）
        """
        self.redis_client = redis_client
        self.proxies: List[ProxyInfo] = []
        self.current_index = 0
        self.proxy_stats: Dict[str, Dict[str, Any]] = {}

    async def load_proxies_from_api(self, api_url: str) -> List[ProxyInfo]:
        """
        从API加载代理列表

        Args:
            api_url: API地址

        Returns:
            代理列表
        """
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(api_url, timeout=10)
                if response.status_code == 200:
                    data = response.json()
                    proxies = []

                    for proxy_data in data:
                        proxy = ProxyInfo(
                            host=proxy_data.get("host"),
                            port=proxy_data.get("port"),
                            username=proxy_data.get("username"),
                            password=proxy_data.get("password"),
                            protocol=proxy_data.get("protocol", "http")
                        )
                        proxies.append(proxy)

                    logger.info(f"从API加载了 {len(proxies)} 个代理")
                    return proxies

        except Exception as e:
            logger.error(f"加载代理失败: {e}")

        return []

    def add_proxy(self, proxy: ProxyInfo):
        """添加代理"""
        self.proxies.append(proxy)
        self.proxy_stats[proxy.url] = {
            "success_count": 0,
            "fail_count": 0,
            "last_used": None,
            "is_banned": False
        }

    async def get_proxy(self) -> Optional[ProxyInfo]:
        """
        获取可用代理（轮询）

        Returns:
            代理信息或None
        """
        if not self.proxies:
            return None

        # 找到下一个可用代理
        for _ in range(len(self.proxies)):
            proxy = self.proxies[self.current_index]
            self.current_index = (self.current_index + 1) % len(self.proxies)

            stats = self.proxy_stats.get(proxy.url, {})
            if not stats.get("is_banned", False):
                return proxy

        return None

    def mark_proxy_success(self, proxy_url: str):
        """标记代理成功"""
        if proxy_url in self.proxy_stats:
            self.proxy_stats[proxy_url]["success_count"] += 1
            self.proxy_stats[proxy_url]["last_used"] = time.time()

    def mark_proxy_failed(self, proxy_url: str):
        """标记代理失败"""
        if proxy_url in self.proxy_stats:
            self.proxy_stats[proxy_url]["fail_count"] += 1
            self.proxy_stats[proxy_url]["last_used"] = time.time()

            # 如果失败次数过多，标记为被封禁
            if self.proxy_stats[proxy_url]["fail_count"] > 5:
                self.proxy_stats[proxy_url]["is_banned"] = True
                logger.warning(f"代理 {proxy_url} 可能被封禁")

    def get_proxy_stats(self) -> Dict[str, Any]:
        """获取代理统计信息"""
        total = len(self.proxies)
        banned = sum(1 for stats in self.proxy_stats.values() if stats.get("is_banned", False))
        active = total - banned

        return {
            "total": total,
            "active": active,
            "banned": banned,
            "details": self.proxy_stats
        }

    async def close(self):
        """关闭连接"""
        if self.redis_client:
            await self.redis_client.close()


class ContentValidator:
    """内容验证器"""

    @staticmethod
    def validate_patent_content(content: str, min_length: int = 50) -> bool:
        """
        验证专利内容

        Args:
            content: 内容
            min_length: 最小长度

        Returns:
            是否有效
        """
        if not content:
            return False

        if len(content) < min_length:
            return False

        # 检查是否包含无意义字符
        meaningless_patterns = [
            r"^\s*$",  # 纯空白
            r"^\d+$",  # 纯数字
            r"^[\W_]+$",  # 纯特殊字符
        ]

        import re
        for pattern in meaningless_patterns:
            if re.match(pattern, content):
                return False

        return True

    @staticmethod
    def clean_text(text: str) -> str:
        """
        清理文本

        Args:
            text: 原始文本

        Returns:
            清理后的文本
        """
        if not text:
            return ""

        # 移除多余空白
        import re
        text = re.sub(r'\s+', ' ', text)
        text = text.strip()

        # 移除特殊字符（保留中文、英文、数字、标点）
        text = re.sub(r'[^\w\s\u4e00-\u9fff\u3000-\u303f\uff00-\uffef\.,;:!?"\'\-\(\)\[\]\{\}]', '', text)

        return text

    @staticmethod
    def extract_keywords(text: str, top_k: int = 10) -> List[str]:
        """
        提取关键词（简单实现）

        Args:
            text: 文本
            top_k: 关键词数量

        Returns:
            关键词列表
        """
        # 这里可以使用jieba或其他NLP库
        # 简单实现：返回高频词
        import re
        from collections import Counter

        # 分词
        words = re.findall(r'\b\w+\b', text.lower())

        # 过滤停用词
        stopwords = {
            'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with',
            'by', 'from', 'up', 'about', 'into', 'through', 'during', 'before', 'after', 'above',
            'below', 'between', 'among', 'be', 'is', 'are', 'was', 'were', 'being', 'been',
            'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could', 'should'
        }

        words = [word for word in words if word not in stopwords and len(word) > 2]

        # 统计词频
        counter = Counter(words)
        return [word for word, count in counter.most_common(top_k)]


class DataDeduplicator:
    """数据去重器"""

    def __init__(self, redis_client: Optional[redis.Redis] = None):
        """
        初始化去重器

        Args:
            redis_client: Redis客户端
        """
        self.redis_client = redis_client
        self.memory_cache: Dict[str, float] = {}
        self.cache_ttl = 3600  # 1小时

    async def is_duplicate(
            self,
            patent_number: str,
            content_hash: str
    ) -> bool:
        """
        判断是否重复

        Args:
            patent_number: 专利号
            content_hash: 内容哈希

        Returns:
            是否重复
        """
        key = f"patent:dedup:{patent_number}"

        if self.redis_client:
            # 使用Redis缓存
            stored_hash = await self.redis_client.get(key)
            if stored_hash and stored_hash.decode() == content_hash:
                return True

            # 存储新哈希
            await self.redis_client.setex(key, self.cache_ttl, content_hash)
        else:
            # 使用内存缓存
            import hashlib
            cache_key = hashlib.md5(f"{patent_number}:{content_hash}".encode()).hexdigest()

            if cache_key in self.memory_cache:
                return True

            self.memory_cache[cache_key] = time.time()

            # 清理过期缓存
            self._clean_memory_cache()

        return False

    def _clean_memory_cache(self):
        """清理内存缓存"""
        current_time = time.time()
        self.memory_cache = {
            k: v for k, v in self.memory_cache.items()
            if current_time - v < self.cache_ttl
        }

    async def mark_processed(self, patent_number: str):
        """
        标记已处理

        Args:
            patent_number: 专利号
        """
        key = f"patent:processed:{patent_number}"

        if self.redis_client:
            await self.redis_client.setex(key, self.cache_ttl, "1")

    async def is_processed(self, patent_number: str) -> bool:
        """
        判断是否已处理

        Args:
            patent_number: 专利号

        Returns:
            是否已处理
        """
        key = f"patent:processed:{patent_number}"

        if self.redis_client:
            return await self.redis_client.exists(key)

        return False
