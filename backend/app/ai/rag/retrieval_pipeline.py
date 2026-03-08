"""
企业级RAG检索管道
Hybrid Search + Reranking Pipeline
支持混合语义搜索和关键词搜索，结合重排序
"""
import logging
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class RetrievalChunk:
    """检索结果片段"""
    id: str
    content: str
    metadata: Dict[str, Any]
    score: float
    rerank_score: Optional[float] = None
    source: str = "semantic"  # semantic, keyword, hybrid


@dataclass
class RetrievalResult:
    """检索结果集"""
    query: str
    chunks: List[RetrievalChunk]
    total: int
    search_type: str  # semantic, keyword, hybrid
    latency_ms: float = 0.0
    tenant_id: Optional[str] = None


class BM25KeywordSearch:
    """BM25关键词搜索实现"""
    
    def __init__(self, k1: float = 1.5, b: float = 0.75):
        self.k1 = k1
        self.b = b
        self.doc_lengths: List[int] = []
        self.avg_doc_length: float = 0.0
        self.doc_freq: Dict[str, int] = {}  # 词项文档频率
        self.doc_term_freqs: List[Dict[str, int]] = []  # 每个文档的词项频率
        self.corpus: List[str] = []
        self.doc_ids: List[str] = []
        self.doc_metadatas: List[Dict[str, Any]] = []
    
    def index(self, documents: List[Dict[str, Any]]):
        """建立BM25索引"""
        self.corpus = [doc["content"] for doc in documents]
        self.doc_ids = [doc["id"] for doc in documents]
        self.doc_metadatas = [doc.get("metadata", {}) for doc in documents]
        
        import jieba
        jieba.setLogLevel(jieba.logging.INFO)
        
        # 计算文档长度
        self.doc_lengths = []
        for doc in self.corpus:
            tokens = list(jieba.cut(doc))
            self.doc_lengths.append(len(tokens))
        
        self.avg_doc_length = sum(self.doc_lengths) / len(self.doc_lengths) if self.doc_lengths else 0
        
        # 计算词项频率和文档频率
        self.doc_term_freqs = []
        for doc in self.corpus:
            tokens = list(jieba.cut(doc))
            term_freq = {}
            for token in tokens:
                term_freq[token] = term_freq.get(token, 0) + 1
                self.doc_freq[token] = self.doc_freq.get(token, 0) + 1
            self.doc_term_freqs.append(term_freq)
        
        logger.info(f"BM25索引建立完成: {len(documents)} 文档")
    
    def search(self, query: str, top_k: int = 10) -> List[RetrievalChunk]:
        """BM25搜索"""
        import jieba
        query_tokens = list(jieba.cut(query))
        N = len(self.corpus)
        
        scores = []
        for i, doc in enumerate(self.corpus):
            score = 0.0
            doc_len = self.doc_lengths[i]
            term_freqs = self.doc_term_freqs[i]
            
            for token in query_tokens:
                if token in term_freqs:
                    tf = term_freqs[token]
                    df = self.doc_freq.get(token, 0)
                    if df > 0:
                        # IDF计算
                        idf = np.log((N - df + 0.5) / (df + 0.5) + 1)
                        # BM25公式
                        numerator = tf * (self.k1 + 1)
                        denominator = tf + self.k1 * (1 - self.b + self.b * doc_len / self.avg_doc_length)
                        score += idf * numerator / denominator
            
            scores.append((i, score))
        
        # 排序并返回top_k
        scores.sort(key=lambda x: x[1], reverse=True)
        
        results = []
        for i, score in scores[:top_k]:
            if score > 0:
                results.append(RetrievalChunk(
                    id=self.doc_ids[i],
                    content=self.corpus[i],
                    metadata=self.doc_metadatas[i],
                    score=score,
                    source="keyword"
                ))
        
        return results


class HybridSearchEngine:
    """混合搜索引擎 - 结合语义搜索和BM25"""
    
    def __init__(self):
        self.bm25 = None
        self.vector_service = None
        self.reranker = None
        self._initialized = False
    
    def initialize(self):
        """初始化搜索引擎"""
        if self._initialized:
            return
        
        # 导入必要的服务
        from app.ai.vector_db_service import vector_db_service
        self.vector_service = vector_db_service
        
        # 导入RAG配置
        from app.ai.rag.config import get_rag_settings
        self.settings = get_rag_settings()
        
        self._initialized = True
        logger.info("混合搜索引擎初始化完成")
    
    async def search(
        self,
        query: str,
        top_k: int = 10,
        tenant_id: Optional[str] = None,
        search_type: str = "hybrid",  # semantic, keyword, hybrid
        use_rerank: bool = True,
        filter_metadata: Optional[Dict[str, Any]] = None
    ) -> RetrievalResult:
        """执行检索"""
        import time
        start_time = time.time()
        
        self.initialize()
        
        if search_type == "semantic":
            # 仅语义搜索
            chunks = await self._semantic_search(query, top_k, tenant_id, filter_metadata)
        elif search_type == "keyword":
            # 仅关键词搜索
            chunks = await self._keyword_search(query, top_k, tenant_id)
        else:
            # 混合搜索
            semantic_chunks = await self._semantic_search(
                query, top_k * 2, tenant_id, filter_metadata
            )
            keyword_chunks = await self._keyword_search(
                query, top_k * 2, tenant_id
            )
            chunks = self._merge_results(
                semantic_chunks, 
                keyword_chunks, 
                alpha=self.settings.HYBRID_SEARCH_ALPHA if self.settings else 0.7
            )
        
        # 重排序
        if use_rerank and chunks:
            chunks = await self._rerank(query, chunks)
            chunks = chunks[:top_k]
        
        latency = (time.time() - start_time) * 1000
        
        return RetrievalResult(
            query=query,
            chunks=chunks,
            total=len(chunks),
            search_type=search_type,
            latency_ms=latency,
            tenant_id=tenant_id
        )
    
    async def _semantic_search(
        self,
        query: str,
        top_k: int,
        tenant_id: Optional[str],
        filter_metadata: Optional[Dict[str, Any]]
    ) -> List[RetrievalChunk]:
        """语义搜索"""
        # 添加租户过滤
        if tenant_id and filter_metadata is None:
            filter_metadata = {"tenant_id": tenant_id}
        elif tenant_id and filter_metadata:
            filter_metadata["tenant_id"] = tenant_id
        
        results = await self.vector_service.search(
            query=query,
            top_k=top_k,
            filter_metadata=filter_metadata,
            tenant_id=tenant_id
        )
        
        return [
            RetrievalChunk(
                id=r.id,
                content=r.content,
                metadata=r.metadata,
                score=r.score,
                source="semantic"
            )
            for r in results
        ]
    
    async def _keyword_search(
        self,
        query: str,
        top_k: int,
        tenant_id: Optional[str]
    ) -> List[RetrievalChunk]:
        """关键词搜索"""
        # 动态创建BM25索引（生产环境应该持久化）
        if not self.bm25:
            # 获取所有文档建立索引
            try:
                from app.ai.vector_db_service import get_patent_collection
                collection = get_patent_collection(tenant_id)
                results = collection.get(include=["documents", "metadatas"])
                
                if results and results.get("documents"):
                    documents = []
                    for i, doc in enumerate(results["documents"]):
                        documents.append({
                            "id": results["ids"][i],
                            "content": doc,
                            "metadata": results["metadatas"][i]
                        })
                    
                    self.bm25 = BM25KeywordSearch(
                        k1=self.settings.BM25_K1 if self.settings else 1.5,
                        b=self.settings.BM25_B if self.settings else 0.75
                    )
                    self.bm25.index(documents)
            except Exception as e:
                logger.warning(f"BM25索引建立失败: {e}")
                return []
        
        if self.bm25:
            return self.bm25.search(query, top_k)
        return []
    
    def _merge_results(
        self,
        semantic_chunks: List[RetrievalChunk],
        keyword_chunks: List[RetrievalChunk],
        alpha: float = 0.7
    ) -> List[RetrievalChunk]:
        """合并语义和关键词搜索结果"""
        # 归一化分数
        def normalize(scores: List[float]) -> List[float]:
            if not scores:
                return []
            max_score = max(scores)
            min_score = min(scores)
            if max_score == min_score:
                return [1.0] * len(scores)
            return [(s - min_score) / (max_score - min_score) for s in scores]
        
        # 构建合并后的字典
        merged: Dict[str, RetrievalChunk] = {}
        
        # 添加语义搜索结果
        if semantic_chunks:
            norm_scores = normalize([c.score for c in semantic_chunks])
            for chunk, norm_score in zip(semantic_chunks, norm_scores):
                chunk.score = alpha * norm_score
                merged[chunk.id] = chunk
        
        # 合并关键词结果
        if keyword_chunks:
            norm_scores = normalize([c.score for c in keyword_chunks])
            for chunk, norm_score in zip(keyword_chunks, norm_scores):
                if chunk.id in merged:
                    # 已有结果，更新分数
                    existing = merged[chunk.id]
                    existing.score = existing.score + (1 - alpha) * norm_score
                    existing.source = "hybrid"
                else:
                    chunk.score = (1 - alpha) * norm_score
                    merged[chunk.id] = chunk
        
        # 排序返回
        result = list(merged.values())
        result.sort(key=lambda x: x.score, reverse=True)
        return result
    
    async def _rerank(
        self,
        query: str,
        chunks: List[RetrievalChunk]
    ) -> List[RetrievalChunk]:
        """重排序"""
        try:
            from app.ai.rag.reranker import get_reranker_service
            reranker = get_reranker_service()
            if reranker:
                return await reranker.rerank(query, chunks)
        except Exception as e:
            logger.warning(f"重排序失败: {e}")
        return chunks


# 全局实例
hybrid_search_engine = HybridSearchEngine()
