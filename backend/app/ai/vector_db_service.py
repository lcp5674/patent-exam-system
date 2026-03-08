"""
企业级RAG向量数据库服务
使用ChromaDB进行专利文档的向量存储和检索
"""
import os
import logging
from typing import List, Dict, Optional, Any
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# 延迟导入，避免启动时出错
_chroma_client = None
_collection = None


def get_chroma_client():
    """获取ChromaDB客户端（使用HTTP客户端连接到ChromaDB服务器）"""
    global _chroma_client
    if _chroma_client is None:
        try:
            import chromadb
            # 使用HTTP客户端连接到ChromaDB服务器（与enterprise_vector_db一致）
            # 硬编码Docker内部主机名
            chroma_host = 'chromadb'
            chroma_port = 8000
            _chroma_client = chromadb.HttpClient(host=chroma_host, port=chroma_port)
            logger.info(f"ChromaDB HTTP连接: {chroma_host}:{chroma_port}")
        except Exception as e:
            logger.error(f"初始化ChromaDB失败: {e}")
            raise
    return _chroma_client


def get_patent_collection(tenant_id: str = None):
    """获取专利文档集合（支持租户隔离）"""
    # 使用与enterprise_vector_db一致的集合命名规则
    collection_name = _get_tenant_collection_name(tenant_id) if tenant_id else "patent_documents"
    
    client = get_chroma_client()
    try:
        collection = client.get_collection(collection_name)
    except Exception:
        collection = client.create_collection(
            name=collection_name,
            metadata={"description": "专利文档向量存储", "version": "1.0"}
        )
    return collection


def _get_tenant_collection_name(tenant_id: str = None, collection_type: str = "patents") -> str:
    """获取租户集合名称（与enterprise_vector_db一致）"""
    from app.ai.rag.config import get_rag_settings
    settings = get_rag_settings()
    if tenant_id and settings.TENANT_ISOLATION:
        return f"{tenant_id}_{collection_type}"
    return collection_type


@dataclass
class DocumentChunk:
    """文档片段"""
    id: str
    content: str
    metadata: Dict[str, Any]
    embedding: Optional[List[float]] = None


@dataclass
class SearchResult:
    """搜索结果"""
    id: str
    content: str
    metadata: Dict[str, Any]
    score: float


class VectorDatabaseService:
    """向量数据库服务 - 企业级RAG支持"""
    
    def __init__(self):
        self.embedding_service = None
        self._init_embedding_service()
    
    def _init_embedding_service(self):
        """初始化嵌入服务（支持自定义模型）"""
        try:
            from app.ai.rag.embedding_service import patent_embedding_service
            from app.ai.rag.config import get_rag_settings
            
            # 初始化设置
            settings = get_rag_settings()
            patent_embedding_service.initialize(settings)
            
            # 使用支持自定义模型的嵌入服务
            self.embedding_service = patent_embedding_service
            logger.info("嵌入服务初始化成功（支持自定义模型）")
        except Exception as e:
            logger.warning(f"嵌入服务初始化失败: {e}，将使用简单文本匹配")
            self.embedding_service = None
    
    def get_embeddings(self, texts: List[str]) -> List[List[float]]:
        """获取文本嵌入向量"""
        if self.embedding_service is None:
            # 返回零向量作为后备
            return [[0.0] * 1024 for _ in texts]
        
        try:
            import asyncio
            # 使用异步嵌入服务
            try:
                # 尝试获取运行中的事件循环
                loop = asyncio.get_running_loop()
                # 如果在异步上下文中，使用线程池执行
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as pool:
                    future = pool.submit(asyncio.run, self.embedding_service.embed_texts(texts, use_cache=True))
                    embedding_results = future.result()
                    return [e.embedding for e in embedding_results]
            except RuntimeError:
                # 没有运行中的循环，可以安全使用 asyncio.run
                embedding_results = asyncio.run(self.embedding_service.embed_texts(texts, use_cache=True))
                return [e.embedding for e in embedding_results]
        except Exception as e:
            logger.error(f"生成嵌入失败: {e}")
            return [[0.0] * 1024 for _ in texts]
    
    async def add_document(
        self,
        doc_id: str,
        content: str,
        metadata: Dict[str, Any],
        chunk_size: int = 500
    ) -> bool:
        """添加文档到向量库"""
        try:
            collection = get_patent_collection()
            
            # 将文档分块
            chunks = self._chunk_text(content, chunk_size)
            
            ids = []
            documents = []
            metadatas = []
            
            for i, chunk in enumerate(chunks):
                chunk_id = f"{doc_id}_chunk_{i}"
                ids.append(chunk_id)
                documents.append(chunk)
                metadatas.append({
                    **metadata,
                    "chunk_index": i,
                    "total_chunks": len(chunks),
                    "doc_id": doc_id
                })
            
            # 获取嵌入向量
            embeddings = self.get_embeddings(chunks)
            
            # 添加到ChromaDB
            collection.upsert(
                ids=ids,
                documents=documents,
                metadatas=metadatas,
                embeddings=embeddings
            )
            
            logger.info(f"文档 {doc_id} 已添加到向量库，共 {len(chunks)} 个片段")
            return True
            
        except Exception as e:
            logger.error(f"添加文档到向量库失败: {e}")
            return False
    
    def _chunk_text(self, text: str, chunk_size: int = 500) -> List[str]:
        """将文本分块"""
        # 简单按段落和句子分块
        paragraphs = text.split('\n\n')
        chunks = []
        current_chunk = ""
        
        for para in paragraphs:
            if len(current_chunk) + len(para) <= chunk_size:
                current_chunk += para + "\n\n"
            else:
                if current_chunk:
                    chunks.append(current_chunk.strip())
                current_chunk = para + "\n\n"
        
        if current_chunk:
            chunks.append(current_chunk.strip())
        
        # 如果仍然太大，按句子分割
        final_chunks = []
        for chunk in chunks:
            if len(chunk) > chunk_size:
                sentences = chunk.replace('. ', '.\n').split('\n')
                current = ""
                for sent in sentences:
                    if len(current) + len(sent) <= chunk_size:
                        current += sent + " "
                    else:
                        if current:
                            final_chunks.append(current.strip())
                        current = sent + " "
                if current:
                    final_chunks.append(current.strip())
            else:
                final_chunks.append(chunk)
        
        return final_chunks if final_chunks else [text[:chunk_size]]
    
    async def search(
        self,
        query: str,
        top_k: int = 5,
        filter_metadata: Optional[Dict[str, Any]] = None,
        tenant_id: str = None
    ) -> List[SearchResult]:
        """语义搜索"""
        try:
            collection = get_patent_collection(tenant_id)
            
            # 获取查询的嵌入向量
            query_embedding = self.get_embeddings([query])[0]
            
            # 搜索
            results = collection.query(
                query_embeddings=[query_embedding],
                n_results=top_k,
                where=filter_metadata,
                include=["documents", "metadatas", "distances"]
            )
            
            search_results = []
            if results and results.get("ids") and results["ids"][0]:
                for i, doc_id in enumerate(results["ids"][0]):
                    search_results.append(SearchResult(
                        id=doc_id,
                        content=results["documents"][0][i],
                        metadata=results["metadatas"][0][i],
                        score=1.0 - results["distances"][0][i]  # 转换为相似度
                    ))
            
            return search_results
            
        except Exception as e:
            logger.error(f"向量搜索失败: {e}")
            return []
    
    async def delete_document(self, doc_id: str) -> bool:
        """删除文档"""
        try:
            collection = get_patent_collection()
            
            # 查找所有相关的chunk
            results = collection.get(
                where={"doc_id": doc_id},
                include=[]
            )
            
            if results and results.get("ids"):
                collection.delete(ids=results["ids"])
                logger.info(f"文档 {doc_id} 已从向量库删除")
            
            return True
        except Exception as e:
            logger.error(f"删除文档失败: {e}")
            return False
    
    async def get_stats(self) -> Dict[str, Any]:
        """获取向量库统计"""
        try:
            collection = get_patent_collection()
            count = collection.count()
            return {
                "total_documents": count,
                "storage_type": "chroma_persistent"
            }
        except Exception as e:
            logger.error(f"获取统计失败: {e}")
            return {"total_documents": 0, "error": str(e)}


# 全局实例
vector_db_service = VectorDatabaseService()
