"""
优先级队列
支持多优先级任务调度和动态权重调整
"""
import asyncio
import json
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, asdict
import logging

logger = logging.getLogger(__name__)


class Priority(Enum):
    """优先级枚举"""
    CRITICAL = 3
    HIGH = 2
    MEDIUM = 1
    LOW = 0


class TaskStatus(Enum):
    """任务状态"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class PriorityTask:
    """优先级任务"""
    task_id: str
    priority: int
    data: Dict[str, Any]
    created_at: datetime
    scheduled_at: Optional[datetime] = None
    status: TaskStatus = TaskStatus.PENDING
    retry_count: int = 0
    max_retries: int = 3
    # 动态权重相关
    base_priority: int = 0
    age_bonus: float = 0.0
    success_rate_bonus: float = 0.0
    value_bonus: float = 0.0

    @property
    def effective_priority(self) -> float:
        """计算有效优先级（包含动态调整）"""
        return (self.base_priority +
                self.age_bonus +
                self.success_rate_bonus +
                self.value_bonus)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        data = asdict(self)
        data['effective_priority'] = self.effective_priority
        return data


class DynamicPriorityQueue:
    """
    动态优先级队列
    支持基于多种因素的动态权重调整
    """

    def __init__(self, name: str = "default", redis_client=None):
        self.name = name
        self.redis_client = redis_client
        self._queue: Dict[str, PriorityTask] = {}
        self._sorted_keys: List[str] = []
        self._lock = asyncio.Lock()

        # 动态权重参数
        self.age_factor = 0.1  # 每小时的优先级提升
        self.value_factor = 0.5  # 高价值任务的权重
        self.success_rate_factor = 0.3  # 成功率权重

        logger.info(f"初始化动态优先级队列: {name}")

    async def put(self, task: PriorityTask) -> bool:
        """
        添加任务到队列

        Args:
            task: 优先级任务

        Returns:
            是否成功
        """
        async with self._lock:
            try:
                self._queue[task.task_id] = task
                await self._resort_queue()

                # 保存到Redis
                if self.redis_client:
                    await self._save_to_redis(task)

                logger.debug(f"任务加入队列: {task.task_id}, "
                           f"优先级: {task.priority}, "
                           f"有效优先级: {task.effective_priority:.2f}")

                return True

            except Exception as e:
                logger.error(f"添加任务失败: {e}")
                return False

    async def get(self, timeout: Optional[float] = None) -> Optional[PriorityTask]:
        """
        获取最高优先级任务

        Args:
            timeout: 超时时间（秒）

        Returns:
            优先级任务或None
        """
        start_time = asyncio.get_event_loop().time()

        while True:
            async with self._lock:
                # 更新所有任务的动态权重
                await self._update_all_dynamic_weights()
                await self._resort_queue()

                # 查找可执行任务
                for task_id in self._sorted_keys:
                    task = self._queue[task_id]
                    if task.status == TaskStatus.PENDING:
                        # 检查调度时间
                        if task.scheduled_at and task.scheduled_at > datetime.utcnow():
                            continue

                        # 标记为运行中
                        task.status = TaskStatus.RUNNING
                        logger.info(f"获取任务: {task_id}, "
                                  f"优先级: {task.priority}, "
                                  f"有效优先级: {task.effective_priority:.2f}")
                        return task

            # 检查超时
            if timeout is not None:
                elapsed = asyncio.get_event_loop().time() - start_time
                if elapsed >= timeout:
                    return None

            # 等待一段时间再重试
            await asyncio.sleep(0.1)

    async def complete(self, task_id: str, success: bool = True):
        """
        完成任务

        Args:
            task_id: 任务ID
            success: 是否成功
        """
        async with self._lock:
            task = self._queue.get(task_id)
            if task:
                task.status = TaskStatus.COMPLETED if success else TaskStatus.FAILED

                # 更新统计数据
                if success:
                    logger.info(f"任务完成: {task_id}")
                else:
                    logger.warning(f"任务失败: {task_id}")

                # 从队列移除
                if task_id in self._sorted_keys:
                    self._sorted_keys.remove(task_id)
                del self._queue[task_id]

                # 更新Redis
                if self.redis_client:
                    await self._remove_from_redis(task_id)

    async def update_priority(
            self,
            task_id: str,
            new_priority: int,
            reason: str = ""
    ) -> bool:
        """
        更新任务优先级

        Args:
            task_id: 任务ID
            new_priority: 新优先级
            reason: 原因

        Returns:
            是否成功
        """
        async with self._lock:
            task = self._queue.get(task_id)
            if not task:
                return False

            old_priority = task.priority
            task.priority = new_priority
            task.base_priority = new_priority

            await self._resort_queue()

            logger.info(f"更新任务优先级: {task_id}, "
                      f"{old_priority} -> {new_priority}, "
                      f"原因: {reason}")

            return True

    def qsize(self) -> int:
        """获取队列大小"""
        return len([t for t in self._queue.values()
                   if t.status == TaskStatus.PENDING])

    async def get_stats(self) -> Dict[str, Any]:
        """获取队列统计"""
        async with self._lock:
            pending = sum(1 for t in self._queue.values()
                         if t.status == TaskStatus.PENDING)
            running = sum(1 for t in self._queue.values()
                         if t.status == TaskStatus.RUNNING)
            completed = sum(1 for t in self._queue.values()
                           if t.status == TaskStatus.COMPLETED)
            failed = sum(1 for t in self._queue.values()
                        if t.status == TaskStatus.FAILED)

            # 计算平均优先级
            pending_tasks = [t for t in self._queue.values()
                           if t.status == TaskStatus.PENDING]
            avg_priority = sum(t.effective_priority for t in pending_tasks) / len(pending_tasks) if pending_tasks else 0

            return {
                "queue_name": self.name,
                "total_tasks": len(self._queue),
                "pending": pending,
                "running": running,
                "completed": completed,
                "failed": failed,
                "avg_priority": round(avg_priority, 2)
            }

    # 内部方法
    async def _update_all_dynamic_weights(self):
        """更新所有任务的动态权重"""
        current_time = datetime.utcnow()

        for task in self._queue.values():
            if task.status != TaskStatus.PENDING:
                continue

            # 1. 年龄加成（等待时间越长优先级越高）
            wait_hours = (current_time - task.created_at).total_seconds() / 3600
            task.age_bonus = wait_hours * self.age_factor

            # 2. 价值加成（从任务数据中计算）
            task.value_bonus = await self._calculate_value_bonus(task)

            # 3. 成功率加成（如果存在历史数据）
            task.success_rate_bonus = await self._calculate_success_rate_bonus(task)

    async def _calculate_value_bonus(self, task: PriorityTask) -> float:
        """计算任务价值加成"""
        try:
            # 从任务数据中提取价值指标
            data = task.data

            # 专利领域特征
            patent_features = data.get("patent_features", {})

            # 高价值指标（示例）
            bonus = 0.0

            # 专利引用次数
            citation_count = patent_features.get("citation_count", 0)
            if citation_count > 10:
                bonus += self.value_factor * 2
            elif citation_count > 5:
                bonus += self.value_factor * 1

            # 专利家族规模
            family_size = patent_features.get("family_size", 0)
            if family_size > 5:
                bonus += self.value_factor * 1.5

            # 申请人排名
            applicant_tier = patent_features.get("applicant_tier", 3)
            if applicant_tier <= 1:  # 顶级申请人
                bonus += self.value_factor * 2
            elif applicant_tier <= 2:
                bonus += self.value_factor * 1

            # 技术领域热度
            field_hotness = patent_features.get("field_hotness", 0)
            bonus += field_hotness * self.value_factor * 0.5

            return bonus

        except Exception as e:
            logger.debug(f"计算价值加成失败: {e}")
            return 0.0

    async def _calculate_success_rate_bonus(self, task: PriorityTask) -> float:
        """计算成功率加成"""
        try:
            # 这里可以从Redis或数据库获取历史成功率
            # 简化实现
            source = task.data.get("source", "")
            if source:
                # 模拟成功率查询
                success_rate = await self._get_source_success_rate(source)
                return (success_rate - 0.5) * self.success_rate_factor

            return 0.0

        except Exception as e:
            logger.debug(f"计算成功率加成失败: {e}")
            return 0.0

    async def _get_source_success_rate(self, source: str) -> float:
        """获取数据源成功率"""
        # 可以从历史数据中获取
        # 简化实现：返回模拟值
        success_rates = {
            "cnipa": 0.85,
            "uspto": 0.95,
            "epo": 0.90,
            "wipo": 0.88,
            "lens": 0.92
        }
        return success_rates.get(source, 0.85)

    async def _resort_queue(self):
        """重新排序队列"""
        # 按有效优先级排序（降序）
        sorted_items = sorted(
            self._queue.items(),
            key=lambda x: x[1].effective_priority,
            reverse=True
        )
        self._sorted_keys = [item[0] for item in sorted_items]

    async def _save_to_redis(self, task: PriorityTask):
        """保存任务到Redis"""
        if not self.redis_client:
            return

        try:
            key = f"priority_queue:{self.name}:{task.task_id}"
            await self.redis_client.setex(
                key,
                86400,  # 24小时过期
                json.dumps(task.to_dict())
            )

            # 添加到有序集合
            zkey = f"priority_queue:{self.name}:sorted"
            await self.redis_client.zadd(
                zkey,
                {task.task_id: task.effective_priority}
            )

        except Exception as e:
            logger.error(f"保存任务到Redis失败: {e}")

    async def _remove_from_redis(self, task_id: str):
        """从Redis移除任务"""
        if not self.redis_client:
            return

        try:
            # 删除任务数据
            key = f"priority_queue:{self.name}:{task_id}"
            await self.redis_client.delete(key)

            # 从有序集合移除
            zkey = f"priority_queue:{self.name}:sorted"
            await self.redis_client.zrem(zkey, task_id)

        except Exception as e:
            logger.error(f"从Redis移除任务失败: {e}")


class MultiQueueScheduler:
    """多队列调度器"""

    def __init__(self, redis_client=None):
        self.redis_client = redis_client
        self.queues: Dict[str, DynamicPriorityQueue] = {}
        self._running = False

    def create_queue(self, name: str) -> DynamicPriorityQueue:
        """创建队列"""
        if name not in self.queues:
            self.queues[name] = DynamicPriorityQueue(name, self.redis_client)
            logger.info(f"创建优先级队列: {name}")
        return self.queues[name]

    def get_queue(self, name: str) -> Optional[DynamicPriorityQueue]:
        """获取队列"""
        return self.queues.get(name)

    async def start_workers(self, queue_name: str, worker_count: int = 3):
        """启动工作进程"""
        queue = self.get_queue(queue_name)
        if not queue:
            raise ValueError(f"队列不存在: {queue_name}")

        tasks = []
        for i in range(worker_count):
            task = asyncio.create_task(
                self._worker(f"worker-{i}", queue),
                name=f"{queue_name}-worker-{i}"
            )
            tasks.append(task)
            logger.info(f"启动工作进程: {queue_name}-worker-{i}")

        return tasks

    async def _worker(self, worker_id: str, queue: DynamicPriorityQueue):
        """工作进程"""
        while self._running:
            try:
                # 获取任务（带超时）
                task = await queue.get(timeout=1.0)

                if not task:
                    continue

                logger.info(f"工作进程 {worker_id} 获取任务: {task.task_id}")

                # 处理任务（这里调用实际的处理器）
                success = await self._process_task(task)

                # 完成任务
                await queue.complete(task.task_id, success)

            except Exception as e:
                logger.error(f"工作进程 {worker_id} 异常: {e}")
                await asyncio.sleep(1)

    async def _process_task(self, task: PriorityTask) -> bool:
        """处理任务（由子类实现）"""
        try:
            # 根据任务类型分发
            task_type = task.data.get("type", "")

            if task_type == "crawl":
                return await self._process_crawl_task(task)
            elif task_type == "embedding":
                return await self._process_embedding_task(task)
            elif task_type == "index":
                return await self._process_index_task(task)
            else:
                logger.warning(f"未知任务类型: {task_type}")
                return False

        except Exception as e:
            logger.error(f"处理任务失败: {e}")
            return False

    async def _process_crawl_task(self, task: PriorityTask) -> bool:
        """处理爬取任务"""
        try:
            source = task.data.get("source")
            patent_number = task.data.get("patent_number")

            from .patent_crawler_agent import CrawlerFactory
            crawler = CrawlerFactory.get_crawler(source)

            if not crawler:
                return False

            # 获取专利详情
            patent = await crawler.get_patent_detail(patent_number)

            if patent:
                # TODO: 发送到Embedding队列
                logger.info(f"爬取成功: {patent_number}")
                return True

            return False

        except Exception as e:
            logger.error(f"爬取任务失败: {e}")
            return False

    async def _process_embedding_task(self, task: PriorityTask) -> bool:
        """处理Embedding任务"""
        try:
            # 从任务数据中获取专利信息
            patent_data = task.data.get("patent_data")

            if not patent_data:
                return False

            # TODO: 调用Embedding服务
            logger.info(f"Embedding处理: {patent_data.get('publication_number')}")

            return True

        except Exception as e:
            logger.error(f"Embedding任务失败: {e}")
            return False

    async def _process_index_task(self, task: PriorityTask) -> bool:
        """处理索引任务"""
        try:
            # TODO: 调用向量数据库索引服务
            logger.info(f"索引任务: {task.task_id}")
            return True

        except Exception as e:
            logger.error(f"索引任务失败: {e}")
            return False

    async def start(self):
        """启动调度器"""
        self._running = True
        logger.info("启动多队列调度器")

    async def stop(self):
        """停止调度器"""
        self._running = False
        logger.info("停止多队列调度器")

    def get_queue_stats(self) -> Dict[str, Any]:
        """获取所有队列统计"""
        stats = {}
        for name, queue in self.queues.items():
            stats[name] = asyncio.run(queue.get_stats())
        return stats


# 队列管理器实例
queue_manager = MultiQueueScheduler()
