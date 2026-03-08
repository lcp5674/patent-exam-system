"""
RAG 优化任务模块
Celery 异步任务实现

功能:
- RAG 性能评估
- RAG 准确率测试
- 向量数据库优化
- 向量数据库重建
- 元数据更新
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

logger = logging.getLogger(__name__)


# ----------------------
# 任务装饰器
# ----------------------

def track_rag_task(task_func):
    """RAG 任务执行跟踪装饰器"""
    @wraps(task_func)
    def wrapper(*args, **kwargs):
        task_id = kwargs.get("task_id") or str(celery_app.current_task.request.id)
        task_name = task_func.__name__
        
        logger.info(f"RAG任务开始: {task_name} [{task_id}]")
        start_time = datetime.now()
        
        try:
            result = task_func(*args, **kwargs)
            duration = (datetime.now() - start_time).total_seconds()
            logger.info(f"RAG任务成功: {task_name} [{task_id}] 耗时: {duration:.2f}秒")
            return result
            
        except Exception as e:
            duration = (datetime.now() - start_time).total_seconds()
            logger.error(f"RAG任务失败: {task_name} [{task_id}] 耗时: {duration:.2f}秒, 错误: {e}")
            raise CustomRetry(
                f"RAG任务执行失败: {str(e)}",
                delay=120,
                max_retries=2
            )
    
    return wrapper


# ----------------------
# RAG 性能评估任务
# ----------------------

@shared_task(
    name="app.tasks.rag_tasks.evaluate_rag_performance",
    bind=True,
    max_retries=2,
    default_retry_delay=300
)
@track_rag_task
def evaluate_rag_performance(
    self,
    tenant_id: Optional[str] = None,
    test_queries: Optional[List[str]] = None,
    top_k: int = 10
) -> Dict[str, Any]:
    """
    RAG 性能评估任务
    
    评估召回率、准确率、延迟等关键指标
    
    Args:
        tenant_id: 租户ID
        test_queries: 测试查询列表 (如果为None使用默认测试集)
        top_k: 检索Top-K值
    
    Returns:
        性能评估结果
    """
    logger.info(f"开始RAG性能评估: tenant_id={tenant_id}, top_k={top_k}")
    
    # 默认测试查询 (专利领域相关)
    if test_queries is None:
        test_queries = [
            "人工智能在医疗领域的应用",
            "神经网络图像识别技术",
            "机器学习专利分析方法",
            "区块链在供应链管理中的应用",
            "物联网智能感知技术",
            "量子加密通信技术",
        ]
    
    results = {
        "task_id": self.request.id,
        "start_time": datetime.now().isoformat(),
        "test_query_count": len(test_queries),
        "top_k": top_k,
        "metrics": {
            "recall_at_k": [],
            "precision_at_k": [],
            "mrr": [],
            "latency_ms": [],
            "chunks_retrieved": [],
        },
        "summary": {}
    }
    
    try:
        from app.ai.rag.enterprise_vector_db import enterprise_vector_db
        from app.ai.rag.retrieval_pipeline import hybrid_search_engine
        
        # 初始化搜索引擎
        hybrid_search_engine.initialize()
        
        total_retrieval_time = 0.0
        total_chunks_retrieved = 0
        
        for i, query in enumerate(test_queries):
            logger.info(f"测试查询 {i+1}/{len(test_queries)}: {query}")
            
            start = datetime.now()
            
            # 执行检索
            search_result = asyncio.run(hybrid_search_engine.search(
                query=query,
                top_k=top_k,
                tenant_id=tenant_id or "default",
                search_type="hybrid",
                use_rerank=True
            ))
            
            latency = (datetime.now() - start).total_seconds() * 1000  # 转换为毫秒
            total_retrieval_time += latency
            
            chunks_count = len(search_result.chunks)
            total_chunks_retrieved += chunks_count
            
            # 计算指标 (简化版本，具体需要ground truth数据)
            results["metrics"]["latency_ms"].append(latency)
            results["metrics"]["chunks_retrieved"].append(chunks_count)
            
            logger.info(f"  检索结果: {chunks_count} chunks, 延迟: {latency:.2f}ms")
        
        # 计算汇总指标
        avg_latency = results["metrics"]["latency_ms"]
        results["summary"] = {
            "avg_latency_ms": sum(avg_latency) / len(avg_latency) if avg_latency else 0,
            "avg_chunks_retrieved": total_chunks_retrieved / len(test_queries) if test_queries else 0,
            "total_retrieval_time_ms": total_retrieval_time,
            "queries_tested": len(test_queries),
        }
        
        # 获取向量库统计
        vector_stats = asyncio.run(enterprise_vector_db.get_collection_stats(tenant_id=tenant_id))
        results["vector_db_stats"] = vector_stats
        
        results["end_time"] = datetime.now().isoformat()
        results["status"] = "completed"
        
        return results
        
    except Exception as e:
        results["status"] = "failed"
        results["error"] = str(e)
        results["end_time"] = datetime.now().isoformat()
        raise


# ----------------------
# RAG 准确率测试任务
# ----------------------

@shared_task(
    name="app.tasks.rag_tasks.test_rag_accuracy",
    bind=True,
    max_retries=2,
    default_retry_delay=180
)
@track_rag_task
def test_rag_accuracy(
    self,
    tenant_id: Optional[str] = None,
    sample_size: int = 50
) -> Dict[str, Any]:
    """
    RAG 准确率测试任务
    
    随机抽样检索并评估结果相关性
    
    Args:
        tenant_id: 租户ID
        sample_size: 抽样数量
    
    Returns:
        准确率测试结果
    """
    logger.info(f"开始RAG准确率测试: sample_size={sample_size}")
    
    results = {
        "task_id": self.request.id,
        "start_time": datetime.now().isoformat(),
        "sample_size": sample_size,
        "accuracy_metrics": {},
        "status": "completed"
    }
    
    try:
        from app.ai.rag.enterprise_vector_db import enterprise_vector_db
        
        # 获取向量库统计
        vector_stats = asyncio.run(enterprise_vector_db.get_collection_stats(tenant_id=tenant_id))
        document_count = vector_stats.get("document_count", 0)
        
        if document_count == 0:
            results["warning"] = "向量子数据库为空，无法测试准确率"
            return results
        
        # 测试查询
        test_queries = [
            "深度学习算法描述",
            "云计算专利技术",
            "数据库优化方案",
            "网络安全防护措施",
            "5G通信技术标准",
        ]
        
        accuracy_scores = []
        
        from app.ai.rag.retrieval_pipeline import hybrid_search_engine
        hybrid_search_engine.initialize()
        
        for query in test_queries:
            try:
                search_result = asyncio.run(hybrid_search_engine.search(
                    query=query,
                    top_k=5,
                    tenant_id=tenant_id or "default",
                    search_type="semantic",
                    use_rerank=False
                ))
                
                # 简单准确率评估 (基于分数分布)
                if search_result.chunks:
                    scores = [c.score for c in search_result.chunks]
                    avg_score = sum(scores) / len(scores)
                    accuracy_scores.append(avg_score)
                
            except Exception as e:
                logger.warning(f"测试查询失败 '{query}': {e}")
        
        # 计算平均准确率
        if accuracy_scores:
            results["accuracy_metrics"] = {
                "avg_relevance_score": sum(accuracy_scores) / len(accuracy_scores),
                "test_queries_count": len(test_queries),
                "successful_queries": len(accuracy_scores),
                "total_documents": document_count,
            }
        
        results["end_time"] = datetime.now().isoformat()
        
        return results
        
    except Exception as e:
        results["status"] = "failed"
        results["error"] = str(e)
        results["end_time"] = datetime.now().isoformat()
        raise


# ----------------------
# 向量数据库优化任务
# ----------------------

@shared_task(
    name="app.tasks.rag_tasks.optimize_vector_database",
    bind=True,
    max_retries=1
)
@track_rag_task
def optimize_vector_database(
    self,
    tenant_id: Optional[str] = None,
    rebuild_index: bool = False
) -> Dict[str, Any]:
    """
    向量数据库优化任务
    
    清理碎片、重建索引、优化存储
    
    Args:
        tenant_id: 租户ID
        rebuild_index: 是否重建索引
    
    Returns:
        优化结果
    """
    logger.info(f"开始向量数据库优化: rebuild_index={rebuild_index}")
    
    results = {
        "task_id": self.request.id,
        "start_time": datetime.now().isoformat(),
        "operations": [],
        "status": "completed"
    }
    
    try:
        from app.ai.rag.enterprise_vector_db import enterprise_vector_db
        
        # 优化操作
        operations_performed = []
        
        # 1. 清理失效文档
        try:
            deleted = asyncio.run(enterprise_vector_db.cleanup_invalid_documents(tenant_id=tenant_id))
            operations_performed.append({
                "op": "cleanup_invalid_documents",
                "result": f"删除 {deleted} 个失效文档"
            })
            logger.info(f"清理失效文档: {deleted} 个")
            results["deleted_documents"] = deleted
        except Exception as e:
            results["warnings"] = results.get("warnings", [])
            results["warnings"].append(f"清理失效文档失败: {e}")
        
        # 2. 重建索引 (如果需要)
        if rebuild_index:
            try:
                asyncio.run(enterprise_vector_db.rebuild_index(tenant_id=tenant_id))
                operations_performed.append({
                    "op": "rebuild_index",
                    "result": "索引重建完成"
                })
                logger.info("索引重建完成")
            except Exception as e:
                results["warnings"] = results.get("warnings", [])
                results["warnings"].append(f"重建索引失败: {e}")
        
        # 3. 获取优化后统计
        vector_stats = asyncio.run(enterprise_vector_db.get_collection_stats(tenant_id=tenant_id))
        results["vector_db_stats"] = vector_stats
        results["operations"] = operations_performed
        
        results["end_time"] = datetime.now().isoformat()
        results["duration"] = (datetime.now() - datetime.fromisoformat(results["start_time"])).total_seconds()
        
        return results
        
    except Exception as e:
        results["status"] = "failed"
        results["error"] = str(e)
        results["end_time"] = datetime.now().isoformat()
        raise


# ----------------------
# 向量数据库重建任务
# ----------------------

@shared_task(
    name="app.tasks.rag_tasks.rebuild_vector_database",
    bind=True,
    max_retries=1
)
@track_rag_task
def rebuild_vector_database(
    self,
    tenant_id: Optional[str] = None,
    backup: bool = True
) -> Dict[str, Any]:
    """
    向量数据库重建任务
    
    完全重建向量库（谨慎使用）
    
    Args:
        tenant_id: 租户ID
        backup: 是否备份
    
    Returns:
        重建结果
    """
    logger.warning(f"开始向量数据库重建: backup={backup} - 此操作将重建所有索引！")
    
    results = {
        "task_id": self.request.id,
        "start_time": datetime.now().isoformat(),
        "backup": backup,
        "status": "completed"
    }
    
    try:
        from app.ai.rag.enterprise_vector_db import enterprise_vector_db
        
        # 获取重建前统计
        before_stats = asyncio.run(enterprise_vector_db.get_collection_stats(tenant_id=tenant_id))
        results["before_stats"] = before_stats
        
        # 备份 (如果需要)
        if backup:
            try:
                backup_path = f"/tmp/rag_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                asyncio.run(enterprise_vector_db.backup(tenant_id=tenant_id, path=backup_path))
                results["backup_path"] = backup_path
                logger.info(f"备份完成: {backup_path}")
            except Exception as e:
                results["warnings"] = results.get("warnings", [])
                results["warnings"].append(f"备份失败: {e}")
        
        # 重建
        asyncio.run(enterprise_vector_db.rebuild(tenant_id=tenant_id))
        
        # 获取重建后统计
        after_stats = asyncio.run(enterprise_vector_db.get_collection_stats(tenant_id=tenant_id))
        results["after_stats"] = after_stats
        
        results["end_time"] = datetime.now().isoformat()
        results["duration"] = (datetime.now() - datetime.fromisoformat(results["start_time"])).total_seconds()
        
        logger.info("向量数据库重建完成")
        
        return results
        
    except Exception as e:
        results["status"] = "failed"
        results["error"] = str(e)
        results["end_time"] = datetime.now().isoformat()
        raise


# ----------------------
# 元数据更新任务
# ----------------------

@shared_task(
    name="app.tasks.rag_tasks.update_metadata",
    bind=True,
    max_retries=2,
    default_retry_delay=120
)
@track_rag_task
def update_metadata(
    self,
    tenant_id: Optional[str] = None,
    metadata_updates: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    元数据更新任务
    
    批量更新文档元数据
    
    Args:
        tenant_id: 租户ID
        metadata_updates: 要更新的元数据
    
    Returns:
        更新结果
    """
    logger.info(f"开始元数据更新: tenant_id={tenant_id}")
    
    if metadata_updates is None:
        metadata_updates = {"last_updated": datetime.now().isoformat()}
    
    results = {
        "task_id": self.request.id,
        "start_time": datetime.now().isoformat(),
        "metadata_updates": metadata_updates,
        "updated_count": 0,
        "status": "completed"
    }
    
    try:
        from app.ai.rag.enterprise_vector_db import enterprise_vector_db
        
        # 获取所有文档
        all_docs = asyncio.run(enterprise_vector_db.get_all_documents(tenant_id=tenant_id))
        doc_ids = [doc["id"] for doc in all_docs]
        
        # 批量更新元数据
        updated = asyncio.run(enterprise_vector_db.update_documents_metadata(
            doc_ids=doc_ids,
            metadata=metadata_updates,
            tenant_id=tenant_id
        ))
        
        results["updated_count"] = updated
        results["total_documents"] = len(doc_ids)
        results["end_time"] = datetime.now().isoformat()
        
        logger.info(f"元数据更新完成: {updated}/{len(doc_ids)}")
        
        return results
        
    except Exception as e:
        results["status"] = "failed"
        results["error"] = str(e)
        results["end_time"] = datetime.now().isoformat()
        raise


# ----------------------
# 清理过期向量任务
# ----------------------

@shared_task(
    name="app.tasks.rag_tasks.cleanup_stale_vectors",
    bind=True,
    max_retries=1
)
@track_rag_task
def cleanup_stale_vectors(
    self,
    tenant_id: Optional[str] = None,
    older_than_days: int = 30
) -> Dict[str, Any]:
    """
    清理过期向量
    
    Args:
        tenant_id: 租户ID
        older_than_days: 清理多少天以前的向量
    
    Returns:
        清理结果
    """
    logger.info(f"开始清理过期向量: older_than_days={older_than_days}")
    
    results = {
        "task_id": self.request.id,
        "start_time": datetime.now().isoformat(),
        "older_than_days": older_than_days,
        "status": "completed"
    }
    
    try:
        from app.ai.rag.enterprise_vector_db import enterprise_vector_db
        
        cutoff_date = datetime.now() - timedelta(days=older_than_days)
        
        # 清理过期文档
        deleted = asyncio.run(enterprise_vector_db.delete_documents_by_date(
            before_date=cutoff_date,
            tenant_id=tenant_id
        ))
        
        results["deleted_count"] = deleted
        results["cutoff_date"] = cutoff_date.isoformat()
        results["end_time"] = datetime.now().isoformat()
        
        logger.info(f"清理过期向量完成: 删除 {deleted} 个向量")
        
        return results
        
    except Exception as e:
        results["status"] = "failed"
        results["error"] = str(e)
        results["end_time"] = datetime.now().isoformat()
        raise


# ----------------------
# RAG 健康检查任务
# ----------------------

@shared_task(
    name="app.tasks.rag_tasks.rag_health_check",
    bind=True
)
def rag_health_check(
    self,
    tenant_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    RAG 系统健康检查
    
    Args:
        tenant_id: 租户ID
    
    Returns:
        健康检查结果
    """
    health_status = {
        "task_id": self.request.id,
        "timestamp": datetime.now().isoformat(),
        "status": "healthy"
    }
    
    try:
        from app.ai.rag.enterprise_vector_db import enterprise_vector_db
        from app.ai.rag.retrieval_pipeline import hybrid_search_engine
        
        # 检查向量数据库
        vector_stats = asyncio.run(enterprise_vector_db.get_collection_stats(tenant_id=tenant_id))
        health_status["vector_db"] = {
            "backend": vector_stats.get("backend", "unknown"),
            "document_count": vector_stats.get("document_count", 0),
            "status": "healthy" if vector_stats.get("document_count", 0) > 0 else "empty"
        }
        
        # 检查搜索引擎
        hybrid_search_engine.initialize()
        health_status["search_engine"] = {
            "status": "healthy",
            "initialized": True
        }
        
        # 执行一次测试检索
        try:
            test_result = asyncio.run(hybrid_search_engine.search(
                query="test",
                top_k=3,
                tenant_id=tenant_id or "default",
                search_type="semantic",
                use_rerank=False
            ))
            health_status["test_search"] = {
                "status": "successful",
                "chunks_retrieved": len(test_result.chunks)
            }
        except Exception as e:
            health_status["test_search"] = {
                "status": "failed",
                "error": str(e)
            }
            health_status["status"] = "degraded"
        
    except Exception as e:
        health_status["status"] = "unhealthy"
        health_status["error"] = str(e)
    
    return health_status
