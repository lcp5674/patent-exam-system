"""爬虫基础模块"""
import asyncio
import random
import time
from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any, AsyncGenerator
from datetime import datetime, timedelta
import httpx
from bs4 import BeautifulSoup
import logging
from urllib.parse import urljoin, urlparse
import json
import hashlib

from .models import PatentDocument, CrawlTask, CrawlStatus, IncrementalUpdateRecord
from .config import config, USER_AGENTS
from .utils import RateLimiter, ProxyManager, RetryHandler

logger = logging.getLogger(__name__)


class BasePatentCrawler(ABC):
    """专利爬虫基类"""

    def __init__(self, source_name: str):
        """
        初始化爬虫

        Args:
            source_name: 数据来源名称
        """
        self.source_name = source_name
        self.rate_limiter = RateLimiter(
            min_interval=config.REQUEST_DELAY_MIN,
            max_interval=config.REQUEST_DELAY_MAX
        )
        self.proxy_manager = ProxyManager() if config.PROXY_ENABLED else None
        self.retry_handler = RetryHandler(max_retries=config.MAX_RETRIES)

        # HTTP客户端
        self.client: Optional[httpx.AsyncClient] = None
        self.session_cookies: Dict[str, str] = {}

        # 统计
        self.stats = {
            "requests_sent": 0,
            "requests_success": 0,
            "requests_failed": 0,
            "patents_found": 0,
            "last_request_time": None
        }

    @abstractmethod
    async def search_patents(
            self,
            query: str,
            max_results: int = 100,
            **kwargs
    ) -> List[PatentDocument]:
        """
        搜索专利

        Args:
            query: 搜索关键词
            max_results: 最大结果数
            **kwargs: 其他参数

        Returns:
            专利列表
        """
        pass

    @abstractmethod
    async def get_patent_detail(
            self,
            patent_number: str,
            **kwargs
    ) -> Optional[PatentDocument]:
        """
        获取专利详情

        Args:
            patent_number: 专利号
            **kwargs: 其他参数

        Returns:
            专利详情
        """
        pass

    @abstractmethod
    async def get_incremental_updates(
            self,
            since: datetime,
            **kwargs
    ) -> List[PatentDocument]:
        """
        获取增量更新

        Args:
            since: 起始时间
            **kwargs: 其他参数

        Returns:
            更新的专利列表
        """
        pass

    async def stream_search(
            self,
            query: str,
            batch_size: int = 50,
            **kwargs
    ) -> AsyncGenerator[List[PatentDocument], None]:
        """
        流式搜索（分批返回结果）

        Args:
            query: 搜索关键词
            batch_size: 每批数量
            **kwargs: 其他参数

        Yields:
            专利批次
        """
        offset = 0
        while True:
            batch = await self.search_patents(
                query,
                max_results=batch_size,
                offset=offset,
                **kwargs
            )

            if not batch:
                break

            yield batch
            offset += len(batch)

            if len(batch) < batch_size:
                break

    async def validate_patent(self, patent: PatentDocument) -> bool:
        """
        验证专利数据完整性

        Args:
            patent: 专利对象

        Returns:
            是否有效
        """
        # 检查必需字段
        if not patent.title or not patent.publication_number:
            return False

        # 检查数据质量
        if patent.title and len(patent.title) < 5:
            return False

        if patent.abstract and len(patent.abstract) < 10:
            return False

        return True

    async def calculate_content_hash(self, content: str) -> str:
        """
        计算内容哈希（用于变更检测）

        Args:
            content: 内容

        Returns:
            哈希值
        """
        return hashlib.sha256(content.encode()).hexdigest()

    async def detect_changes(
            self,
            patent: PatentDocument,
            previous_hash: Optional[str]
    ) -> bool:
        """
        检测专利内容是否变更

        Args:
            patent: 专利对象
            previous_hash: 之前的哈希值

        Returns:
            是否变更
        """
        if not previous_hash:
            return True

        # 组合关键字段计算哈希
        content = f"{patent.title}|{patent.abstract}|{patent.claims}|{patent.description}"
        current_hash = await self.calculate_content_hash(content)

        return current_hash != previous_hash

    async def get_client(self) -> httpx.AsyncClient:
        """获取HTTP客户端"""
        if self.client is None:
            # 请求配置
            limits = httpx.Limits(
                max_keepalive_connections=20,
                max_connections=100,
                keepalive_expiry=30.0
            )

            # 代理配置
            proxy = None
            if self.proxy_manager:
                proxy = await self.proxy_manager.get_proxy()

            # 创建客户端
            self.client = httpx.AsyncClient(
                limits=limits,
                proxy=proxy,
                timeout=config.TIMEOUT,
                follow_redirects=True
            )

        return self.client

    def get_random_user_agent(self) -> str:
        """获取随机User-Agent"""
        return random.choice(USER_AGENTS)

    async def make_request(
            self,
            method: str,
            url: str,
            **kwargs
    ) -> Optional[httpx.Response]:
        """
        发送HTTP请求（带重试和限速）

        Args:
            method: HTTP方法
            url: URL
            **kwargs: 其他参数

        Returns:
            响应对象
        """
        # 添加User-Agent
        headers = kwargs.get("headers", {})
        if "User-Agent" not in headers:
            headers["User-Agent"] = self.get_random_user_agent()
        kwargs["headers"] = headers

        # 限速
        async with self.rate_limiter:
            # 重试逻辑
            async def _do_request() -> Optional[httpx.Response]:
                try:
                    client = await self.get_client()
                    response = await client.request(method, url, **kwargs)

                    # 更新统计
                    self.stats["requests_sent"] += 1
                    self.stats["last_request_time"] = time.time()

                    if response.status_code == 200:
                        self.stats["requests_success"] += 1
                    else:
                        self.stats["requests_failed"] += 1

                    return response
                except Exception as e:
                    logger.error(f"请求失败: {url} - {e}")
                    self.stats["requests_failed"] += 1
                    return None

            # 执行重试
            return await self.retry_handler.execute_with_retry(_do_request)

    async def parse_html(self, html: str) -> BeautifulSoup:
        """
        解析HTML

        Args:
            html: HTML内容

        Returns:
            BeautifulSoup对象
        """
        return BeautifulSoup(html, 'html.parser')

    async def save_html_cache(
            self,
            patent_number: str,
            html: str,
            ttl: int = 3600
    ):
        """
        保存HTML缓存

        Args:
            patent_number: 专利号
            html: HTML内容
            ttl: 缓存时间（秒）
        """
        # 这里可以实现Redis或文件缓存
        pass

    async def load_html_cache(
            self,
            patent_number: str
    ) -> Optional[str]:
        """
        加载HTML缓存

        Args:
            patent_number: 专利号

        Returns:
            HTML内容或None
        """
        # 这里可以实现Redis或文件缓存
        return None

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return self.stats.copy()

    async def close(self):
        """关闭连接"""
        if self.client:
            await self.client.aclose()
            self.client = None

        if self.proxy_manager:
            await self.proxy_manager.close()


class AntiCrawlerMixin:
    """反爬虫策略混入类"""

    async def random_delay(self, min_seconds: float = 1.0, max_seconds: float = 3.0):
        """随机延迟"""
        delay = random.uniform(min_seconds, max_seconds)
        await asyncio.sleep(delay)

    async def simulate_human_behavior(self):
        """模拟人类行为"""
        # 随机延迟
        await self.random_delay()

        # 随机滚动（对于需要JS的情况）
        # 这里可以添加更多模拟行为

    async def handle_captcha(self, response: httpx.Response) -> bool:
        """
        处理验证码

        Args:
            response: 响应对象

        Returns:
            是否成功处理
        """
        # 实现验证码识别逻辑
        # 可以使用第三方服务或手动处理
        logger.warning("检测到验证码，需要人工处理")
        return False

    def add_cookies(self, cookies: Dict[str, str]):
        """添加Cookies"""
        self.session_cookies.update(cookies)

    def get_cookies(self) -> Dict[str, str]:
        """获取Cookies"""
        return self.session_cookies


class IncrementalCapableMixin:
    """增量更新能力混入类"""

    def __init__(self):
        self.update_records: Dict[str, IncrementalUpdateRecord] = {}

    async def get_last_update_time(self, source: str) -> Optional[datetime]:
        """
        获取最后更新时间

        Args:
            source: 数据来源

        Returns:
            最后更新时间
        """
        record = self.update_records.get(source)
        if record:
            return record.last_update_time
        return None

    async def update_incremental_record(
            self,
            source: str,
            last_patent_number: str,
            total_processed: int,
            success_count: int,
            failed_count: int
    ):
        """
        更新增量记录

        Args:
            source: 数据来源
            last_patent_number: 最后处理的专利号
            total_processed: 处理总数
            success_count: 成功数量
            failed_count: 失败数量
        """
        record = IncrementalUpdateRecord(
            source=source,
            last_update_time=datetime.utcnow(),
            last_patent_number=last_patent_number,
            total_processed=total_processed,
            success_count=success_count,
            failed_count=failed_count
        )

        self.update_records[source] = record

    async def should_full_crawl(self, source: str) -> bool:
        """
        判断是否需要全量爬取

        Args:
            source: 数据来源

        Returns:
            是否需要全量爬取
        """
        # 基于时间间隔判断
        last_update = await self.get_last_update_time(source)
        if not last_update:
            return True

        time_since_last = datetime.utcnow() - last_update
        return time_since_last.total_seconds() > config.FULL_CRAWL_INTERVAL
