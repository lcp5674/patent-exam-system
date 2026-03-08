"""
RAG 评估模块
实现召回率、准确率等关键指标的评估计算
"""
from __future__ import annotations
import logging
import asyncio
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime
from dataclasses import dataclass, field
import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class EvaluationMetric:
    """评估指标"""
    metric_name: str
    value: float
    description: str
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class EvaluationResult:
    """评估结果"""
    evaluation_id: str
    timestamp: datetime
    metrics: List[EvaluationMetric] = field(default_factory=list)
    summary: Dict[str, Any] = field(default_factory=dict)
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class GroundTruthEntry:
    """真实答案条目 - 用于评估"""
    query: str
    relevant_doc_ids: List[str]  # 应该返回的文档ID列表
    query_type: str = "semantic"  # semantic | keyword | factual
    tenant_id: str = "default"


class RAGEvaluator:
    """RAG 评估器"""
    
    def __init__(self):
        self.ground_truth: List[GroundTruthEntry] = []
        self.history: List[EvaluationResult] = []
    
    def add_ground_truth(self, query: str, relevant_doc_ids: List[str], query_type: str = "semantic", tenant_id: str = "default"):
        """添加真实答案"""
        entry = GroundTruthEntry(
            query=query,
            relevant_doc_ids=relevant_doc_ids,
            query_type=query_type,
            tenant_id=tenant_id
        )
        self.ground_truth.append(entry)
    
    def calculate_recall_at_k(
        self,
        retrieved_ids: List[str],
        relevant_ids: List[str],
        k: int
    ) -> Dict[str, float]:
        """
        计算Recall@K
    
    Args:
        retrieved_ids: 检索到的文档ID列表
        relevant_ids: 相关文档ID列表
        k: Top-K值
    
    Returns:
        {"recall_at_{k}": value, "relevant_in_top_k": int}
    """
        if not relevant_ids:
            return {"recall_at_k": 0.0, "relevant_in_top_k": 0}
        
        # 取前K个检索结果
        top_k_retrieved = set(retrieved_ids[:k])
        relevant_in_top_k = len(top_k_retrieved & set(relevant_ids))
        recall = relevant_in_top_k / min(k, len(relevant_ids))
        
        return {
            f"recall_at_{k}": recall,
            "relevant_in_top_k": relevant_in_top_k
        }
    
    def calculate_precision_at_k(
        self,
        retrieved_ids: List[str],
        relevant_ids: List[str],
        k: int
    ) -> Dict[str, float]:
        """
        计算Precision@K
    
    Args:
        retrieved_ids: 检索到的文档ID列表
        relevant_ids: 相关文档ID列表
        k: Top-K值
    
    Returns:
        {"precision_at_{k}": value, "relevant_in_top_k": int}
    """
        if not retrieved_ids or k == 0:
            return {"precision_at_k": 0.0, "relevant_in_top_k": 0}
        
        # 取前K个检索结果
        top_k_retrieved = retrieved_ids[:k]
        relevant_in_top_k = len([rid for rid in top_k_retrieved if rid in relevant_ids])
        precision = relevant_in_top_k / min(k, len(top_k_retrieved))
        
        return {
            f"precision_at_{k}": precision,
            "relevant_in_top_k": relevant_in_top_k
        }
    
    def calculate_mrr(
        self,
        retrieved_ids: List[str],
        relevant_ids: List[str]
    ) -> float:
        """
        计算平均倒数排名 (Mean Reciprocal Rank)
        
    Args:
        retrieved_ids: 检索到的文档ID列表
        relevant_ids: 相关文档ID列表
    
    Returns:
        MRR值
    """
        if not relevant_ids:
            return 0.0
        
        mrr_sum = 0.0
        
        relevant_set = set(relevant_ids)
        
        try:
            for rank, rid in enumerate(retrieved_ids, 1):
                if rid in relevant_set:
                    mrr_sum += 1.0 / rank
            
            return mrr_sum / len(relevant_ids)
        except Exception:
            return 0.0
    
    def calculate_hit_rate(
        self,
        retrieved_ids: List[str],
        relevant_ids: List[str]
    ) -> float:
        """计算命中率"""
        if not relevant_ids:
            return 0.0
        
        relevant_set = set(relevant_ids)
        hits = len([rid for rid in retrieved_ids if rid in relevant_set])
        return hits / len(retrieved_ids) if retrieved_ids else 0.0
    
    async def evaluate_retrieval(
        self,
        query: str,
        retrieved_results: List[Dict[str, Any]],
        ground_truth: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        评估单次检索结果
        
        Args:
            query: 查询
            retrieved_results: 检索结果列表
            ground_truth: 真实答案 (如果不提供则使用内部ground truth)
        
        Returns:
        评估指标
        """
        retrieved_ids = [r.get("id", r.get("doc_id", "")) for r in retrieved_results]
        scores = [r.get("score", r.get("rerank_score", 0)) for r in retrieved_results]
        
        # 查找对应的ground truth
        relevant_ids = []
        if ground_truth:
            relevant_ids = ground_truth.get("relevant_doc_ids", [])
        else:
            # 查找匹配的ground truth
            entry = next((gt for gt in self.ground_truth if gt.query.lower() == query.lower() or query.lower() in gt.query.lower()), None)
            if entry:
                relevant_ids = entry.relevant_doc_ids
        
        # 计算各级指标
        metrics = {}
        
        # Recall@1, @5, @10
        for k in [1, 5, 10]:
            recall_metrics = self.calculate_recall_at_k(retrieved_ids, relevant_ids, k)
            metrics.update(recall_metrics)
        
        # Precision@1, @5, @10
        for k in [1, 5, 10]:
            precision_metrics = self.calculate_precision_at_k(retrieved_ids, relevant_ids, k)
            metrics.update(precision_metrics)
        
        # MRR
        metrics["mrr"] = self.calculate_mrr(retrieved_ids, relevant_ids)
        
        # 命中率
        metrics["hit_rate"] = self.calculate_hit_rate(retrieved_ids, relevant_ids)
        
        # 平均相关分数
        metrics["avg_relevance_score"] = np.mean(scores) if scores else 0.0
        
        return {
            "query": query,
            "metrics": metrics,
            "retrieved_count": len(retrieved_ids),
            "relevant_count": len(relevant_ids),
            "timestamp": datetime.now().isoformat()
        }
    
    async def batch_evaluate(
        self,
        evaluation_pairs: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        批量评估
        
        Args:
            evaluation_pairs: 评估对列表 [{"query": "...", "retrieved": [...], "relevant": [...]}]
        
        Returns:
        批量评估统计
        """
        all_metrics = []
        
        for pair in evaluation_pairs:
            result = await self.evaluate_retrieval(
                query=pair.get("query", ""),
                retrieved_results=pair.get("retrieved", []),
                ground_truth=pair.get("ground_truth")
            )
            all_metrics.append(result)
        
        # 汇总统计
        summary = {
            "total_queries": len(all_metrics),
            "avg_recall_at_10": np.mean([m["metrics"].get("recall_at_10", 0) for m in all_metrics]),
            "avg_precision_at_10": np.mean([m["metrics"].get("precision_at_10", 0) for m in all_metrics]),
            "avg_mrr": np.mean([m["metrics"].get("mrr", 0) for m in all_metrics]),
            "avg_hit_rate": np.mean([m["metrics"].get("hit_rate", 0) for m in all_metrics])
        }
        
        # 95% 目标检查
        summary["meets_95_percent_target"] = {
            "recall_95": summary["avg_recall_at_10"] >= 0.95,
            "precision_95": summary["avg_precision_at_10"] >= 0.95,
            "status": "PASS" if (
                summary["avg_recall_at_10"] >= 0.95 and 
                summary["avg_precision_at_10"] >= 0.95
            ) else "FAIL"
        }
        
        return {
            "evaluation_id": f"eval_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            "timestamp": datetime.now().isoformat(),
            "individual_results": all_metrics,
            "summary": summary
        }


class RAGBenchmark:
    """RAG 基准测试集"""
    
    PATENT_DOMAIN_TEST_QUERIES = [
        {
            "query": "人工智能深度学习算法在图像识别中的应用",
            "relevant_keywords": ["深度学习", "图像识别", "卷积神经网络", "CNN", "图像处理"],
            "expected_recall_at_10": 0.95
        },
        {
            "query": "区块链技术在供应链管理中的应用",
            "relevant_keywords": ["区块链", "供应链", "分布式账本", "智能合约", "溯源"],
            "expected_recall_at_10": 0.95
        },
        {
            "query": "量子通信技术的研究进展",
            "relevant_keywords": ["量子", "量子通信", "量子加密", "密钥分发"],
            "expected_recall_at_10": 0.95
        },
    ]
    
    @classmethod
    def get_benchmark_queries(cls) -> List[str]:
        """获取基准测试查询"""
        return [q["query"] for q in cls.PATENT_DOMAIN_TEST_QUERIES]


# 全局评估器实例
evaluator = RAGEvaluator()
