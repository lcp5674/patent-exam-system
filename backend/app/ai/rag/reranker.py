"""
重排序服务
Reranker Service for RAG Pipeline
支持本地模型和API方式
"""
from __future__ import annotations
import logging
import asyncio
import httpx
from typing import List, Tuple, Optional
from dataclasses import dataclass
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)


@dataclass
class RerankResult:
    """重排序结果"""
    index: int
    text: str
    score: float
    original_score: float
    metadata: dict


class BaseReranker(ABC):
    """Reranker 基类"""
    
    @abstractmethod
    async def rerank(
        self,
        query: str,
        documents: List[Tuple[str, float, dict]],
        top_k: int = 5
    ) -> List[RerankResult]:
        """重排序文档"""
        pass


class LocalReranker(BaseReranker):
    """本地 HuggingFace Reranker"""
    
    def __init__(self, model_name: str = "BAAI/bge-reranker-large", device: str = "cpu"):
        self._model_name = model_name
        self._device = device
        self._model = None
        self._tokenizer = None
        self._initialized = False
    
    def _initialize(self):
        """延迟初始化模型"""
        if self._initialized:
            return
        
        try:
            from transformers import AutoModelForSequenceClassification, AutoTokenizer
            import torch
            
            logger.info(f"加载本地重排序模型: {self._model_name}")
            self._tokenizer = AutoTokenizer.from_pretrained(self._model_name)
            self._model = AutoModelForSequenceClassification.from_pretrained(self._model_name)
            self._model.to(self._device)
            self._model.eval()
            self._initialized = True
            logger.info("本地重排序模型加载完成")
        except ImportError:
            logger.warning("transformers库未安装，重排序功能将降级为简单排序")
            self._initialized = True
        except Exception as e:
            logger.warning(f"加载重排序模型失败: {e}，将使用备用排序方法")
            self._initialized = True
    
    async def rerank(
        self,
        query: str,
        documents: List[Tuple[str, float, dict]],
        top_k: int = 5
    ) -> List[RerankResult]:
        """重排序文档"""
        self._initialize()
        
        if not documents:
            return []
        
        # 如果模型未加载，使用简单排序
        if self._model is None:
            return self._simple_rerank(query, documents, top_k)
        
        # 使用模型重排序
        return await self._model_rerank(query, documents, top_k)
    
    def _simple_rerank(
        self,
        query: str,
        documents: List[Tuple[str, float, dict]],
        top_k: int
    ) -> List[RerankResult]:
        """简单重排序 - 基于关键词匹配"""
        query_terms = set(query.lower().split())
        results = []
        
        for i, (text, original_score, metadata) in enumerate(documents):
            # 计算关键词覆盖率
            text_terms = set(text.lower().split())
            overlap = len(query_terms & text_terms)
            keyword_score = overlap / max(len(query_terms), 1)
            
            # 综合分数
            final_score = 0.7 * original_score + 0.3 * keyword_score
            
            results.append(RerankResult(
                index=i,
                text=text,
                score=final_score,
                original_score=original_score,
                metadata=metadata
            ))
        
        # 按分数排序
        results.sort(key=lambda x: x.score, reverse=True)
        return results[:top_k]
    
    async def _model_rerank(
        self,
        query: str,
        documents: List[Tuple[str, float, dict]],
        top_k: int
    ) -> List[RerankResult]:
        """使用模型重排序"""
        import torch
        
        loop = asyncio.get_event_loop()
        
        def _compute_scores():
            scores = []
            with torch.no_grad():
                for text, _, _ in documents:
                    inputs = self._tokenizer(
                        query, text,
                        padding=True,
                        truncation=True,
                        max_length=512,
                        return_tensors="pt"
                    )
                    inputs = {k: v.to(self._device) for k, v in inputs.items()}
                    score = self._model(**inputs).logits.squeeze(-1).item()
                    scores.append(score)
            return scores
        
        scores = await loop.run_in_executor(None, _compute_scores)
        
        results = []
        for i, ((text, original_score, metadata), rerank_score) in enumerate(zip(documents, scores)):
            # 归一化分数
            normalized_score = 1 / (1 + (-rerank_score)) if rerank_score < 0 else rerank_score
            
            results.append(RerankResult(
                index=i,
                text=text,
                score=normalized_score,
                original_score=original_score,
                metadata=metadata
            ))
        
        results.sort(key=lambda x: x.score, reverse=True)
        return results[:top_k]


class APIReranker(BaseReranker):
    """API Reranker (支持 Cohere/OpenAI 兼容格式)"""
    
    def __init__(self, model_name: str, api_url: str, api_key: str = ""):
        self._model_name = model_name
        self._api_url = api_url.rstrip("/")
        self._api_key = api_key
        
        # 构建 rerank 端点 URL
        if self._api_url.endswith("/v1/rerank"):
            self._rerank_url = self._api_url
        elif self._api_url.endswith("/v1"):
            self._rerank_url = f"{self._api_url}/rerank"
        else:
            self._rerank_url = f"{self._api_url}/v1/rerank"
        
        logger.info(f"初始化 API Reranker: {self._rerank_url}, 模型: {model_name}")
    
    async def rerank(
        self,
        query: str,
        documents: List[Tuple[str, float, dict]],
        top_k: int = 5
    ) -> List[RerankResult]:
        """使用 API 进行重排序"""
        if not documents:
            return []
        
        headers = {"Content-Type": "application/json"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"
        
        # 提取文档文本
        doc_texts = [text for text, _, _ in documents]
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    self._rerank_url,
                    headers=headers,
                    json={
                        "query": query,
                        "documents": doc_texts,
                        "top_k": min(top_k, len(doc_texts)),
                        "model": self._model_name
                    }
                )
                
                if response.status_code == 200:
                    result = response.json()
                    results_list = result.get("results", [])
                    
                    rerank_results = []
                    for r in results_list:
                        idx = r.get("index", 0)
                        score = r.get("relevance_score", 0.0)
                        if idx < len(documents):
                            text, original_score, metadata = documents[idx]
                            rerank_results.append(RerankResult(
                                index=idx,
                                text=text,
                                score=score,
                                original_score=original_score,
                                metadata=metadata
                            ))
                    
                    # 按分数排序
                    rerank_results.sort(key=lambda x: x.score, reverse=True)
                    return rerank_results[:top_k]
                else:
                    logger.warning(f"Rerank API 返回错误: {response.status_code} - {response.text[:200]}")
                    # 降级为简单排序
                    return self._simple_rerank(query, documents, top_k)
                    
        except Exception as e:
            logger.warning(f"Rerank API 调用失败: {e}，降级为简单排序")
            return self._simple_rerank(query, documents, top_k)
    
    def _simple_rerank(
        self,
        query: str,
        documents: List[Tuple[str, float, dict]],
        top_k: int
    ) -> List[RerankResult]:
        """简单重排序 - 基于关键词匹配"""
        query_terms = set(query.lower().split())
        results = []
        
        for i, (text, original_score, metadata) in enumerate(documents):
            text_terms = set(text.lower().split())
            overlap = len(query_terms & text_terms)
            keyword_score = overlap / max(len(query_terms), 1)
            final_score = 0.7 * original_score + 0.3 * keyword_score
            
            results.append(RerankResult(
                index=i,
                text=text,
                score=final_score,
                original_score=original_score,
                metadata=metadata
            ))
        
        results.sort(key=lambda x: x.score, reverse=True)
        return results[:top_k]


class RerankerService:
    """
    重排序服务 - 统一管理 Reranker
    
    优先级：
    1. 自定义配置（API URL + API Key）
    2. 本地模型
    """
    
    def __init__(self, model_name: str = "BAAI/bge-reranker-large", device: str = "cpu",
                 api_url: str = None, api_key: str = None):
        self._model_name = model_name
        self._device = device
        self._api_url = api_url
        self._api_key = api_key
        self._reranker: Optional[BaseReranker] = None
    
    def _get_reranker(self) -> BaseReranker:
        """获取 Reranker 实例"""
        if self._reranker is None:
            # 如果有 API URL，使用 API Reranker
            if self._api_url:
                logger.info(f"使用 API Reranker: {self._api_url}")
                self._reranker = APIReranker(
                    model_name=self._model_name,
                    api_url=self._api_url,
                    api_key=self._api_key or ""
                )
            else:
                # 否则使用本地模型
                logger.info(f"使用本地 Reranker: {self._model_name}")
                self._reranker = LocalReranker(
                    model_name=self._model_name,
                    device=self._device
                )
        return self._reranker
    
    async def rerank(
        self,
        query: str,
        documents: List[Tuple[str, float, dict]],
        top_k: int = 5
    ) -> List[RerankResult]:
        """重排序文档"""
        reranker = self._get_reranker()
        return await reranker.rerank(query, documents, top_k)
    
    async def compute_relevance(
        self,
        query: str,
        document: str
    ) -> float:
        """计算查询与文档的相关性分数"""
        results = await self.rerank(query, [(document, 0.0, {})], top_k=1)
        return results[0].score if results else 0.0


# 全局实例
reranker_service: Optional[RerankerService] = None


def get_reranker_service(model_name: str = None) -> RerankerService:
    """
    获取重排序服务实例
    
    优先级：
    1. 检查自定义配置（数据库中保存的用户配置）
    2. 使用系统默认配置
    """
    global reranker_service
    
    from .config import get_rag_settings
    settings = get_rag_settings()
    
    target_model = model_name or settings.RERANKER_MODEL
    
    # 检查是否有自定义配置
    if target_model:
        from .config import get_custom_reranker_config_sync
        custom_config = get_custom_reranker_config_sync(target_model)
        
        if custom_config and custom_config.get("api_url"):
            logger.info(f"使用自定义 Reranker 配置: {target_model}")
            return RerankerService(
                model_name=target_model,
                api_url=custom_config.get("api_url"),
                api_key=custom_config.get("api_key"),
                device=settings.EMBEDDING_DEVICE
            )
    
    # 使用本地模型或已有的全局实例
    if reranker_service is None:
        reranker_service = RerankerService(
            model_name=target_model,
            device=settings.EMBEDDING_DEVICE
        )
    elif model_name and reranker_service._model_name != model_name:
        # 如果请求的模型名称不同，创建新实例
        reranker_service = RerankerService(
            model_name=target_model,
            device=settings.EMBEDDING_DEVICE
        )
    
    return reranker_service
