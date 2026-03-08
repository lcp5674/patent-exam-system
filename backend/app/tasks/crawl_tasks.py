"""
专利数据爬取任务模块
Celery 异步任务实现

功能:
- 全量专利数据爬取
- 增量专利数据更新
- 多数据源聚合爬取
- 状态管理和失败重试
"""
from __future__ import annotations
import os
import logging
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from functools import wraps
import json

from celery import shared_task
from app.tasks.celery_app import celery_app, TaskStatus, CustomRetry
from app.ai.patent_database_api import patent_aggregator, PatentDocument
from app.ai.rag.enterprise_vector_db import enterprise_vector_db
from app.database.engine import async_session_factory
from app.database.models import CrawlTask, PatentSourceConfig

logger = logging.getLogger(__name__)


# ----------------------
# 任务装饰器
# ----------------------

def track_task(task_func):
    """任务执行跟踪装饰器"""
    @wraps(task_func)
    def wrapper(*args, **kwargs):
        task_id = kwargs.get("task_id") or str(celery_app.current_task.request.id)
        task_name = task_func.__name__
        
        logger.info(f"任务开始: {task_name} [{task_id}]")
        start_time = datetime.now()
        
        try:
            result = task_func(*args, **kwargs)
            duration = (datetime.now() - start_time).total_seconds()
            logger.info(f"任务成功: {task_name} [{task_id}] 耗时: {duration:.2f}秒")
            
            # 记录任务完成状态到数据库（异步）
            celery_app.send_task(
                "app.tasks.crawl_tasks.update_task_status",
                args=[task_id, "SUCCESS", {"result": result, "duration": duration}],
                queue="crawl"
            )
            
            return result
            
        except Exception as e:
            duration = (datetime.now() - start_time).total_seconds()
            logger.error(f"任务失败: {task_name} [{task_id}] 耗时: {duration:.2f}秒, 错误: {e}")
            
            # 记录失败状态
            celery_app.send_task(
                "app.tasks.crawl_tasks.update_task_status",
                args=[task_id, "FAILURE", {"error": str(e), "duration": duration}],
                queue="crawl"
            )
            
            raise CustomRetry(
                f"任务执行失败: {str(e)}",
                delay=60,
                max_retries=3
            )
    
    return wrapper


# ----------------------
# 全量爬取任务
# ----------------------

@shared_task(
    name="app.tasks.crawl_tasks.full_patent_crawl",
    bind=True,
    max_retries=3,
    default_retry_delay=300
)
@track_task
def full_patent_crawl(
    self,
    queries: List[str],
    sources: Optional[List[str]] = None,
    max_results_per_source: int = 100,
    tenant_id: Optional[str] = None,
    index_to_rag: bool = True
) -> Dict[str, Any]:
    """
    全量专利数据爬取任务
    
    Args:
        queries: 搜索关键词列表
        sources: 数据源列表 (默认: dawei, cnipa, uspto, wipo, epo)
        max_results_per_source: 每个数据源最大结果数
        tenant_id: 租户ID
        index_to_rag: 是否索引到RAG系统
    
    Returns:
        爬取结果统计
    """
    logger.info(f"开始全量专利爬取: queries={queries}, sources={sources}")
    
    # 默认数据源
    if sources is None:
        sources = ["dawei", "cnipa", "uspto", "wipo", "epo"]
    
    # 统计信息
    stats = {
        "task_id": self.request.id,
        "query": queries[0] if queries else "all",
        "sources": sources,
        "start_time": datetime.now().isoformat(),
        "results": {},
        "total_found": 0,
        "indexed_count": 0,
        "errors": []
    }
    
    try:
        # 初始化专利聚合器
        patent_aggregator.initialize()
        
        # 加载用户配置的数据源（如果指定了租户ID）
        if tenant_id:
            try:
                patent_aggregator.load_user_configs(int(tenant_id))
            except Exception as e:
                logger.warning(f"加载租户 {tenant_id} 配置失败: {e}")
        
        # 对每个关键词进行搜索
        all_patents = []
        
        for query in queries:
            logger.info(f"搜索关键词: {query}")
            
            # 搜索所有数据源
            results = asyncio.run(patent_aggregator.search_all(
                query=query,
                sources=sources,
                max_results_per_source=max_results_per_source
            ))
            
            # 统计每个数据源的结果
            for source, patents in results.items():
                source_count = len(patents)
                stats["results"][source] = stats["results"].get(source, 0) + source_count
                all_patents.extend(patents)
                
                logger.info(f"  {source}: 找到 {source_count} 条专利")
            
            # 添加小延迟避免过载
            import time
            time.sleep(2)
        
        stats["total_found"] = len(all_patents)
        logger.info(f"共找到 {stats['total_found']} 条专利")
        
        # 索引到RAG系统
        if index_to_rag and all_patents:
            logger.info("开始索引专利到RAG系统...")
            
            indexed = 0
            batch_size = 50
            
            for i in range(0, len(all_patents), batch_size):
                batch = all_patents[i:i + batch_size]
                try:
                    # 转换为字典格式
                    docs = [p.to_dict() for p in batch]
                    
                    # 批量索引
                    index_results = asyncio.run(enterprise_vector_db.index_patent_batch(
                        documents=docs,
                        tenant_id=tenant_id
                    ))
                    
                    indexed_batch = sum(1 for v in index_results.values() if v)
                    indexed += indexed_batch
                    logger.info(f"  批次 {i//batch_size + 1}: 索引 {indexed_batch}/{len(batch)}")
                    
                    # 添加延迟
                    time.sleep(0.5)
                    
                except Exception as e:
                    logger.error(f"批次索引失败: {e}")
                    stats["errors"].append({
                        "batch": i // batch_size + 1,
                        "error": str(e)
                    })
            
            stats["indexed_count"] = indexed
            logger.info(f"成功索引 {indexed} 条专利")
        
        stats["end_time"] = datetime.now().isoformat()
        stats["duration"] = (datetime.now() - datetime.fromisoformat(stats["start_time"])).total_seconds()
        stats["status"] = "completed"
        
        return stats
        
    except Exception as e:
        stats["status"] = "failed"
        stats["error"] = str(e)
        stats["end_time"] = datetime.now().isoformat()
        raise


# ----------------------
# 增量爬取任务
# ----------------------

@shared_task(
    name="app.tasks.crawl_tasks.incremental_patent_crawl",
    bind=True,
    max_retries=3,
    default_retry_delay=180
)
@track_task
def incremental_patent_crawl(
    self,
    queries: List[str],
    sources: Optional[List[str]] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    max_results_per_source: int = 50,
    tenant_id: Optional[str] = None,
    index_to_rag: bool = True
) -> Dict[str, Any]:
    """
    增量专利数据爬取任务
    
    根据日期范围搜索新发布的专利
    
    Args:
        queries: 搜索关键词列表
        sources: 数据源列表
        date_from: 起始日期 (YYYY-MM-DD), 默认最近7天
        date_to: 结束日期 (YYYY-MM-DD)
        max_results_per_source: 每个数据源最大结果数
        tenant_id: 租户ID
        index_to_rag: 是否索引到RAG系统
    
    Returns:
        爬取结果统计
    """
    logger.info(f"开始增量专利爬取: queries={queries}, date_from={date_from}")
    
    # 计算默认日期范围 (最近7天)
    if date_from is None:
        date_from = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
    
    if date_to is None:
        date_to = datetime.now().strftime("%Y-%m-%d")
    
    # 默认数据源
    if sources is None:
        sources = ["dawei", "cnipa", "uspto", "wipo", "epo"]
    
    stats = {
        "task_id": self.request.id,
        "query": queries[0] if queries else "all",
        "sources": sources,
        "date_from": date_from,
        "date_to": date_to,
        "start_time": datetime.now().isoformat(),
        "results": {},
        "total_found": 0,
        "indexed_count": 0,
        "new_patents": 0,
        "errors": []
    }
    
    try:
        # 初始化专利聚合器
        patent_aggregator.initialize()
        
        if tenant_id:
            try:
                patent_aggregator.load_user_configs(int(tenant_id))
            except Exception as e:
                logger.warning(f"加载租户 {tenant_id} 配置失败: {e}")
        
        # 获取已索引的专利ID集合
        existing_ids = set()
        if index_to_rag:
            try:
                existing_docs = asyncio.run(enterprise_vector_db.get_all_document_ids(tenant_id))
                existing_ids = set(existing_docs)
                logger.info(f"已存在 {len(existing_ids)} 条专利")
            except Exception as e:
                logger.warning(f"获取已索引专利失败: {e}")
        
        # 搜索并过滤新专利
        all_new_patents = []
        
        for query in queries:
            logger.info(f"搜索关键词: {query} ({date_from} - {date_to})")
            
            results = asyncio.run(patent_aggregator.search_all(
                query=query,
                sources=sources,
                max_results_per_source=max_results_per_source,
                date_from=date_from,
                date_to=date_to
            ))
            
            for source, patents in results.items():
                # 过滤新专利
                new_patents = []
                for patent in patents:
                    # 使用申请号或公开号作为唯一标识
                    patent_id = patent.publication_number or patent.application_number
                    if patent_id and patent_id not in existing_ids:
                        new_patents.append(patent)
                
                stats["results"][source] = len(new_patents)
                stats["total_found"] += len(new_patents)
                all_new_patents.extend(new_patents)
                
                logger.info(f"  {source}: 新专利 {len(new_patents)} 条")
            
            import time
            time.sleep(1.5)
        
        stats["new_patents"] = len(all_new_patents)
        
        # 索引新专利
        if index_to_rag and all_new_patents:
            logger.info(f"开始索引 {len(all_new_patents)} 条新专利...")
            
            indexed = 0
            batch_size = 50
            
            for i in range(0, len(all_new_patents), batch_size):
                batch = all_new_patents[i:i + batch_size]
                try:
                    docs = [p.to_dict() for p in batch]
                    
                    index_results = asyncio.run(enterprise_vector_db.index_patent_batch(
                        documents=docs,
                        tenant_id=tenant_id
                    ))
                    
                    indexed_batch = sum(1 for v in index_results.values() if v)
                    indexed += indexed_batch
                    logger.info(f"  批次 {i//batch_size + 1}: 索引 {indexed_batch}/{len(batch)}")
                    
                    time.sleep(0.3)
                    
                except Exception as e:
                    logger.error(f"批次索引失败: {e}")
                    stats["errors"].append({
                        "batch": i // batch_size + 1,
                        "error": str(e)
                    })
            
            stats["indexed_count"] = indexed
        
        stats["end_time"] = datetime.now().isoformat()
        stats["duration"] = (datetime.now() - datetime.fromisoformat(stats["start_time"])).total_seconds()
        stats["status"] = "completed"
        
        return stats
        
    except Exception as e:
        stats["status"] = "failed"
        stats["error"] = str(e)
        stats["end_time"] = datetime.now().isoformat()
        raise


# ----------------------
# 快速增量爬取任务
# ----------------------

@shared_task(
    name="app.tasks.crawl_tasks.incremental_patent_crawl_fast",
    bind=True,
    max_retries=2,
    default_retry_delay=60
)
@track_task
def incremental_patent_crawl_fast(
    self,
    queries: List[str],
    max_results_per_source: int = 20,
    tenant_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    快速增量爬取任务 (每小时执行)
    
    用于关键关键词的实时监控
    
    Args:
        queries: 关键关键词列表
        max_results_per_source: 每个数据源最大结果数 (较少)
        tenant_id: 租户ID
    
    Returns:
        爬取结果统计
    """
    logger.info(f"开始快速增量爬取: queries={queries}")
    
    # 最近2小时的数据
    date_from = (datetime.now() - timedelta(hours=2)).strftime("%Y-%m-%d")
    
    stats = {
        "task_id": self.request.id,
        "queries": queries,
        "date_from": date_from,
        "start_time": datetime.now().isoformat(),
        "total_found": 0,
        "indexed_count": 0,
        "status": "completed"
    }
    
    try:
        all_new_patents = []
        
        for query in queries:
            results = asyncio.run(patent_aggregator.search_all(
                query=query,
                max_results_per_source=max_results_per_source
            ))
            
            for source, patents in results.items():
                all_new_patents.extend(patents)
        
        stats["total_found"] = len(all_new_patents)
        
        # 快速索引
        if all_new_patents:
            docs = [p.to_dict() for p in all_new_patents]
            index_results = asyncio.run(enterprise_vector_db.index_patent_batch(
                documents=docs,
                tenant_id=tenant_id
            ))
            stats["indexed_count"] = sum(1 for v in index_results.values() if v)
        
        stats["end_time"] = datetime.now().isoformat()
        stats["duration"] = (datetime.now() - datetime.fromisoformat(stats["start_time"])).total_seconds()
        
        return stats
        
    except Exception as e:
        stats["status"] = "failed"
        stats["error"] = str(e)
        stats["end_time"] = datetime.now().isoformat()
        raise


# ----------------------
# 任务状态管理
# ----------------------

@shared_task(
    name="app.tasks.crawl_tasks.update_task_status",
    bind=True
)
def update_task_status(
    self,
    task_id: str,
    status: str,
    payload: Dict[str, Any]
) -> bool:
    """
    更新任务状态到数据库
    
    Args:
        task_id: 任务ID
        status: 任务状态
        payload: 任务结果/错误信息
    
    Returns:
        是否成功
    """
    try:
        # 这里可以实现数据库更新逻辑
        # 目前记录到日志
        logger.info(f"任务状态更新: {task_id} -> {status}, payload: {payload}")
        return True
    except Exception as e:
        logger.error(f"更新任务状态失败: {e}")
        return False


@shared_task(
    name="app.tasks.crawl_tasks.get_crawl_statistics",
    bind=True
)
def get_crawl_statistics(
    self,
    tenant_id: Optional[str] = None,
    days: int = 7
) -> Dict[str, Any]:
    """
    获取爬取统计信息
    
    Args:
        tenant_id: 租户ID
        days: 统计天数
    
    Returns:
        统计信息
    """
    try:
        # 获取向量库统计
        vector_stats = asyncio.run(enterprise_vector_db.get_collection_stats(tenant_id=tenant_id))
        
        # 获取各数据源的爬取记录（如果有数据库表）
        crawl_stats = {
            "total_documents": vector_stats.get("document_count", 0),
            "vector_db": vector_stats.get("backend", "chroma"),
            "date_range_days": days,
            "sources": {}
        }
        
        return crawl_stats
        
    except Exception as e:
        logger.error(f"获取爬取统计失败: {e}")
        return {"error": str(e)}


# ----------------------
# 辅助任务
# ----------------------

@shared_task(
    name="app.tasks.crawl_tasks.test_crawl_task",
    bind=True
)
def test_crawl_task(
    self,
    query: str = "人工智能",
    source: str = "cnipa",
    max_results: int = 5
) -> Dict[str, Any]:
    """
    测试爬取任务
    
    Args:
        query: 测试查询
        source: 数据源
        max_results: 最大结果数
    
    Returns:
        测试结果
    """
    logger.info(f"执行测试爬取: query={query}, source={source}")
    
    try:
        results = asyncio.run(patent_aggregator.search_all(
            query=query,
            sources=[source],
            max_results_per_source=max_results
        ))
        
        return {
            "task_id": self.request.id,
            "query": query,
            "source": source,
            "results_count": len(results.get(source, [])),
            "status": "success"
        }
        
    except Exception as e:
        logger.error(f"测试爬取失败: {e}")
        return {
            "task_id": self.request.id,
            "query": query,
            "source": source,
            "status": "failed",
            "error": str(e)
        }
