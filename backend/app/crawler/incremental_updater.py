"""增量更新调度器"""
import asyncio
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Set
import logging
import json
from dataclasses import dataclass, asdict
from enum import Enum

from .models import PatentDocument, IncrementalUpdateRecord, PriorityLevel, CrawlStatus
from .config import config
from .patent_crawler_agent import CrawlerFactory, BasePatentCrawler
from .utils import DataDeduplicator

logger = logging.getLogger(__name__)


class UpdateStrategy(Enum):
    """更新策略"""
    CONTINUOUS = "continuous"  # 持续更新
    SCHEDULED = "scheduled"    # 定时更新
    ADAPTIVE = "adaptive"      # 自适应更新


@dataclass
class UpdateTask:
    """更新任务"""
    source: str
    since: datetime
    priority: PriorityLevel
    created_at: datetime
    max_results: int = 1000
    status: CrawlStatus = CrawlStatus.PENDING
    progress: float = 0.0
    processed_count: int = 0
    success_count: int = 0
    failed_count: int = 0

    @property
    def task_id(self) -> str:
        return f"{self.source}_{self.since.isoformat()}"


class IncrementalUpdater:
    """增量更新管理器"""

    def __init__(self, redis_client=None):
        self.redis_client = redis_client
        self.crawler_factory = CrawlerFactory
        self.deduplicator = DataDeduplicator(redis_client)

        # 更新历史
        self.update_history: Dict[str, List[IncrementalUpdateRecord]] = {}
        self.active_tasks: Dict[str, UpdateTask] = {}

        # 配置
        self.update_strategy = UpdateStrategy.ADAPTIVE
        self.batch_size = 100
        self.max_concurrent_updates = 3
        self.update_semaphore = asyncio.Semaphore(self.max_concurrent_updates)

        # 统计
        self.stats = {
            "total_updates": 0,
            "successful_updates": 0,
            "failed_updates": 0,
            "total_patents_processed": 0,
            "start_time": datetime.utcnow()
        }

    async def schedule_incremental_update(
            self,
            source: str,
            since: Optional[datetime] = None,
            priority: PriorityLevel = PriorityLevel.MEDIUM,
            max_results: int = 1000
    ) -> str:
        """
        调度增量更新任务

        Args:
            source: 数据来源
            since: 起始时间（None表示从上一次更新开始）
            priority: 优先级
            max_results: 最大处理数量

        Returns:
            任务ID
        """
        # 确定起始时间
        if since is None:
            last_update = await self.get_last_update_time(source)
            if last_update:
                since = last_update
            else:
                # 默认：过去7天
                since = datetime.utcnow() - timedelta(days=7)

        # 创建任务
        task = UpdateTask(
            source=source,
            since=since,
            priority=priority,
            created_at=datetime.utcnow(),
            max_results=max_results
        )

        self.active_tasks[task.task_id] = task

        logger.info(f"调度增量更新任务: {task.task_id}, "
                   f"来源: {source}, 起始: {since}")

        return task.task_id

    async def execute_update(self, task_id: str) -> IncrementalUpdateRecord:
        """
        执行更新任务

        Args:
            task_id: 任务ID

        Returns:
            更新记录
        """
        task = self.active_tasks.get(task_id)
        if not task:
            raise ValueError(f"任务不存在: {task_id}")

        async with self.update_semaphore:
            return await self._execute_update_task(task)

    async def _execute_update_task(self, task: UpdateTask) -> IncrementalUpdateRecord:
        """执行更新任务"""
        task.status = CrawlStatus.IN_PROGRESS
        start_time = time.time()

        try:
            # 获取爬虫
            crawler = self.crawler_factory.get_crawler(task.source)
            if not crawler:
                raise ValueError(f"不支持的来源: {task.source}")

            logger.info(f"开始增量更新: {task.source}, 起始: {task.since}")

            # 获取增量数据
            patents = await crawler.get_incremental_updates(
                task.since,
                max_results=task.max_results
            )

            if not patents:
                logger.info(f"{task.source} 没有新数据")
                return IncrementalUpdateRecord(
                    source=task.source,
                    last_update_time=datetime.utcnow(),
                    total_processed=0,
                    success_count=0,
                    failed_count=0
                )

            # 批量处理
            processed_count = 0
            success_count = 0
            failed_count = 0
            last_patent_number = None

            for i in range(0, len(patents), self.batch_size):
                batch = patents[i:i + self.batch_size]

                # 处理批次
                batch_result = await self._process_batch(crawler, batch, task.source)

                processed_count += len(batch)
                success_count += batch_result["success"]
                failed_count += batch_result["failed"]

                if batch_result["last_patent_number"]:
                    last_patent_number = batch_result["last_patent_number"]

                # 更新进度
                task.progress = min(processed_count / len(patents), 1.0)
                task.processed_count = processed_count
                task.success_count = success_count
                task.failed_count = failed_count

                logger.debug(f"批次处理完成: {processed_count}/{len(patents)}, "
                           f"成功: {success_count}, 失败: {failed_count}")

            # 完成任务
            task.status = CrawlStatus.COMPLETED
            task.progress = 1.0

            # 创建更新记录
            record = IncrementalUpdateRecord(
                source=task.source,
                last_update_time=datetime.utcnow(),
                last_patent_number=last_patent_number,
                total_processed=processed_count,
                success_count=success_count,
                failed_count=failed_count
            )

            # 保存记录
            await self._save_update_record(record)

            # 更新统计
            self.stats["total_updates"] += 1
            self.stats["successful_updates"] += 1
            self.stats["total_patents_processed"] += success_count

            elapsed = time.time() - start_time
            logger.info(f"增量更新完成: {task.source}, "
                       f"处理: {processed_count}, "
                       f"成功: {success_count}, "
                       f"失败: {failed_count}, "
                       f"耗时: {elapsed:.2f}秒")

            return record

        except Exception as e:
            task.status = CrawlStatus.FAILED
            logger.error(f"增量更新失败: {task.source} - {e}")

            self.stats["failed_updates"] += 1

            raise

    async def _process_batch(
            self,
            crawler: BasePatentCrawler,
            patents: List[PatentDocument],
            source: str
    ) -> Dict[str, Any]:
        """处理批次"""
        success = 0
        failed = 0
        last_patent_number = None

        for patent in patents:
            try:
                # 检查是否需要处理
                if not patent.publication_number:
                    failed += 1
                    continue

                # 变更检测
                if await self._need_update(patent):
                    # TODO: 发送到Embedding Pipeline
                    logger.debug(f"需要更新专利: {patent.publication_number}")

                success += 1
                last_patent_number = patent.publication_number

            except Exception as e:
                logger.error(f"处理专利失败 {patent.publication_number}: {e}")
                failed += 1

        return {
            "success": success,
            "failed": failed,
            "last_patent_number": last_patent_number
        }

    async def _need_update(self, patent: PatentDocument) -> bool:
        """判断是否需要更新"""
        if not patent.publication_number:
            return False

        # 计算内容哈希
        content = f"{patent.title}{patent.abstract}{patent.claims}{patent.description}"
        content_hash = await crawler.calculate_content_hash(content)

        # 检查是否变更
        key = f"patent:hash:{patent.publication_number}"

        if self.redis_client:
            stored_hash = await self.redis_client.get(key)
            if stored_hash and stored_hash.decode() == content_hash:
                return False

            # 存储新哈希
            await self.redis_client.set(key, content_hash)
        else:
            # 内存存储（简化）
            if not hasattr(self, '_content_hashes'):
                self._content_hashes = {}

            if self._content_hashes.get(patent.publication_number) == content_hash:
                return False

            self._content_hashes[patent.publication_number] = content_hash

        return True

    async def run_continuous_updates(self):
        """运行持续更新（守护进程）"""
        logger.info("启动持续增量更新服务...")

        while True:
            try:
                # 检查每个启用来源
                for source in config.ENABLED_SOURCES:
                    if await self.should_update(source):
                        # 调度更新任务
                        await self.schedule_incremental_update(
                            source=source,
                            priority=PriorityLevel.MEDIUM
                        )

                # 处理待执行任务
                await self.process_pending_tasks()

                # 等待下一次检查
                await asyncio.sleep(config.UPDATE_CHECK_INTERVAL)

            except Exception as e:
                logger.error(f"持续更新服务异常: {e}")
                await asyncio.sleep(60)  # 等待1分钟后重试

    async def process_pending_tasks(self):
        """处理待执行任务"""
        pending_tasks = [
            task for task in self.active_tasks.values()
            if task.status == CrawlStatus.PENDING
        ]

        if not pending_tasks:
            return

        # 按优先级排序
        pending_tasks.sort(key=lambda t: t.priority.value, reverse=True)

        # 并发执行
        tasks = []
        for task in pending_tasks:
            task_future = asyncio.create_task(self.execute_update(task.task_id))
            tasks.append(task_future)

        # 等待完成
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # 处理结果
        for i, result in enumerate(results):
            task = pending_tasks[i]
            if isinstance(result, Exception):
                logger.error(f"任务 {task.task_id} 执行失败: {result}")
            else:
                logger.info(f"任务 {task.task_id} 执行成功")

    async def should_update(self, source: str) -> bool:
        """
        判断是否需要更新

        Args:
            source: 数据来源

        Returns:
            是否需要更新
        """
        last_update = await self.get_last_update_time(source)

        if not last_update:
            return True

        # 检查时间间隔
        time_since_last = datetime.utcnow() - last_update
        return time_since_last.total_seconds() >= config.UPDATE_CHECK_INTERVAL

    async def get_last_update_time(self, source: str) -> Optional[datetime]:
        """获取最后更新时间"""
        if self.redis_client:
            key = f"update:last_time:{source}"
            timestamp = await self.redis_client.get(key)
            if timestamp:
                return datetime.fromtimestamp(float(timestamp))

        # 从内存获取
        history = self.update_history.get(source, [])
        if history:
            return history[-1].last_update_time

        return None

    async def _save_update_record(self, record: IncrementalUpdateRecord):
        """保存更新记录"""
        source = record.source

        if source not in self.update_history:
            self.update_history[source] = []

        self.update_history[source].append(record)

        # 限制历史记录数量
        if len(self.update_history[source]) > 100:
            self.update_history[source] = self.update_history[source][-100:]

        # 保存到Redis
        if self.redis_client:
            key = f"update:history:{source}"
            await self.redis_client.lpush(key, json.dumps(asdict(record)))
            await self.redis_client.ltrim(key, 0, 99)

            # 保存最后更新时间
            await self.redis_client.set(
                f"update:last_time:{source}",
                record.last_update_time.timestamp()
            )

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            **self.stats,
            "active_tasks": len(self.active_tasks),
            "update_history": {
                source: len(history)
                for source, history in self.update_history.items()
            }
        }

    def get_task_status(self, task_id: str) -> Optional[UpdateTask]:
        """获取任务状态"""
        return self.active_tasks.get(task_id)


# 全局实例
incremental_updater = IncrementalUpdater()


# 用于后台运行的守护进程
async def run_incremental_update_daemon():
    """运行增量更新守护进程"""
    updater = IncrementalUpdater()

    # 启动所有启用来源的初始更新
    for source in config.ENABLED_SOURCES:
        await updater.schedule_incremental_update(source)

    # 运行持续更新
    await updater.run_continuous_updates()


# 用于CLI的手动更新
async def manual_incremental_update(source: str, since_days: int = 7):
    """手动触发增量更新"""
    updater = IncrementalUpdater()

    since = datetime.utcnow() - timedelta(days=since_days)
    task_id = await updater.schedule_incremental_update(
        source=source,
        since=since
    )

    # 执行更新
    try:
        record = await updater.execute_update(task_id)
        print(f"增量更新完成: {source}")
        print(f"处理数量: {record.total_processed}")
        print(f"成功: {record.success_count}")
        print(f"失败: {record.failed_count}")

        return record
    except Exception as e:
        print(f"增量更新失败: {e}")
        return None


if __name__ == "__main__":
    # 测试用例
    import asyncio

    async def test():
        # 手动更新测试
        result = await manual_incremental_update("uspto", since_days=1)
        if result:
            print(f"测试成功: {result}")

    asyncio.run(test())
