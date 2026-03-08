"""
企业级RAG向量数据库服务
支持多租户隔离、混合搜索、增量索引
"""
from __future__ import annotations
import os
import logging
import asyncio
from typing import List, Dict, Optional, Any, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from abc import ABC, abstractmethod
import json

logger = logging.getLogger(__name__)


@dataclass
class Document:
    """文档数据结构"""
    id: str
    content: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    embedding: Optional[List[float]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "content": self.content,
            "metadata": self.metadata,
        }


@dataclass
class SearchResult:
    """搜索结果"""
    id: str
    content: str
    metadata: Dict[str, Any]
    score: float
    highlights: Optional[List[str]] = None


class VectorStoreBackend(ABC):
    """向量存储后端抽象基类"""
    
    @abstractmethod
    async def create_collection(self, name: str, metadata: Dict[str, Any] = None) -> bool:
        """创建集合"""
        pass
    
    @abstractmethod
    async def delete_collection(self, name: str) -> bool:
        """删除集合"""
        pass
    
    @abstractmethod
    async def add_documents(
        self,
        collection: str,
        documents: List[Document],
        embeddings: List[List[float]]
    ) -> bool:
        """添加文档"""
        pass
    
    @abstractmethod
    async def search(
        self,
        collection: str,
        query_embedding: List[float],
        top_k: int = 10,
        filter_metadata: Optional[Dict[str, Any]] = None
    ) -> List[SearchResult]:
        """语义搜索"""
        pass
    
    @abstractmethod
    async def delete_documents(self, collection: str, doc_ids: List[str]) -> bool:
        """删除文档"""
        pass
    
    @abstractmethod
    async def get_stats(self, collection: str) -> Dict[str, Any]:
        """获取统计信息"""
        pass


class ChromaBackend(VectorStoreBackend):
    """ChromaDB后端"""
    
    def __init__(self, host: str = None, port: int = None, persist_dir: str = None):
        self.host = host
        self.port = port
        self.persist_dir = persist_dir
        self._client = None
        self._collections: Dict[str, Any] = {}
    
    def _get_client(self):
        """获取ChromaDB客户端"""
        if self._client is None:
            import chromadb
            if self.host and self.port:
                # 服务器模式
                self._client = chromadb.HttpClient(
                    host=self.host,
                    port=self.port
                )
                logger.info(f"ChromaDB服务器模式: {self.host}:{self.port}")
            else:
                # 嵌入式模式
                os.makedirs(self.persist_dir, exist_ok=True)
                self._client = chromadb.PersistentClient(path=self.persist_dir)
                logger.info(f"ChromaDB嵌入式模式: {self.persist_dir}")
        return self._client
    
    def _get_collection(self, name: str):
        """获取或创建集合"""
        if name not in self._collections:
            client = self._get_client()
            try:
                self._collections[name] = client.get_collection(name)
            except Exception:
                self._collections[name] = client.create_collection(
                    name=name,
                    metadata={"hnsw:space": "cosine"}
                )
        return self._collections[name]
    
    async def create_collection(self, name: str, metadata: Dict[str, Any] = None) -> bool:
        """创建集合"""
        try:
            client = self._get_client()
            collection = client.create_collection(
                name=name,
                metadata=metadata or {"hnsw:space": "cosine"}
            )
            self._collections[name] = collection
            logger.info(f"创建集合: {name}")
            return True
        except Exception as e:
            logger.error(f"创建集合失败: {e}")
            return False
    
    async def delete_collection(self, name: str) -> bool:
        """删除集合"""
        try:
            client = self._get_client()
            client.delete_collection(name)
            if name in self._collections:
                del self._collections[name]
            logger.info(f"删除集合: {name}")
            return True
        except Exception as e:
            logger.error(f"删除集合失败: {e}")
            return False
    
    async def add_documents(
        self,
        collection: str,
        documents: List[Document],
        embeddings: List[List[float]]
    ) -> bool:
        """添加文档"""
        try:
            coll = self._get_collection(collection)
            
            ids = [doc.id for doc in documents]
            contents = [doc.content for doc in documents]
            metadatas = [doc.metadata for doc in documents]
            
            coll.upsert(
                ids=ids,
                documents=contents,
                metadatas=metadatas,
                embeddings=embeddings
            )
            
            logger.info(f"添加 {len(documents)} 文档到集合 {collection}")
            return True
        except Exception as e:
            logger.error(f"添加文档失败: {e}")
            return False
    
    async def search(
        self,
        collection: str,
        query_embedding: List[float],
        top_k: int = 10,
        filter_metadata: Optional[Dict[str, Any]] = None
    ) -> List[SearchResult]:
        """语义搜索"""
        try:
            coll = self._get_collection(collection)
            
            results = coll.query(
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
                        content=results["documents"][0][i] if results["documents"] else "",
                        metadata=results["metadatas"][0][i] if results["metadatas"] else {},
                        score=1.0 - results["distances"][0][i] if results["distances"] else 0.0
                    ))
            
            return search_results
        except Exception as e:
            logger.error(f"搜索失败: {e}")
            return []
    
    async def delete_documents(self, collection: str, doc_ids: List[str]) -> bool:
        """删除文档"""
        try:
            coll = self._get_collection(collection)
            coll.delete(ids=doc_ids)
            logger.info(f"从 {collection} 删除 {len(doc_ids)} 文档")
            return True
        except Exception as e:
            logger.error(f"删除文档失败: {e}")
            return False
    
    async def get_stats(self, collection: str) -> Dict[str, Any]:
        """获取统计信息"""
        try:
            coll = self._get_collection(collection)
            count = coll.count()
            return {
                "collection": collection,
                "document_count": count,
                "backend": "chroma"
            }
        except Exception as e:
            return {"error": str(e)}


class EnterpriseVectorDBService:
    """企业级向量数据库服务"""
    
    def __init__(self):
        self._backend: Optional[VectorStoreBackend] = None
        self._embedding_service = None
        self._settings = None
        self._initialized = False
    
    async def initialize(self):
        """初始化服务"""
        if self._initialized:
            return
        
        from app.ai.rag.config import get_rag_settings
        self._settings = get_rag_settings()
        
        # 初始化后端
        backend_type = self._settings.VECTOR_DB_TYPE
        
        if backend_type == "chroma":
            # 优先使用服务器模式
            if self._settings.CHROMA_HOST:
                self._backend = ChromaBackend(
                    host=self._settings.CHROMA_HOST,
                    port=self._settings.CHROMA_PORT
                )
                logger.info(f"ChromaDB服务器模式: {self._settings.CHROMA_HOST}:{self._settings.CHROMA_PORT}")
            else:
                persist_dir = self._settings.get_chroma_persist_dir()
                self._backend = ChromaBackend(persist_dir=persist_dir)
                logger.info(f"ChromaDB嵌入式模式: {persist_dir}")
        else:
            # 默认使用Chroma嵌入式
            persist_dir = self._settings.get_chroma_persist_dir()
            self._backend = ChromaBackend(persist_dir=persist_dir)
        
        # 初始化嵌入服务
        from app.ai.rag.embedding_service import patent_embedding_service
        patent_embedding_service.initialize(self._settings)
        self._embedding_service = patent_embedding_service
        
        self._initialized = True
        logger.info(f"企业级向量数据库服务初始化完成，后端: {backend_type}")
    
    def _get_tenant_collection(self, tenant_id: str, collection_type: str = "patents") -> str:
        """获取租户集合名称"""
        if tenant_id and self._settings and self._settings.TENANT_ISOLATION:
            return f"{tenant_id}_{collection_type}"
        return collection_type
    
    async def create_tenant_collection(
        self,
        tenant_id: str,
        collection_type: str = "patents"
    ) -> bool:
        """为租户创建集合"""
        collection_name = self._get_tenant_collection(tenant_id, collection_type)
        return await self._backend.create_collection(
            collection_name,
            metadata={"tenant_id": tenant_id, "type": collection_type}
        )
    
    async def index_patent_document(
        self,
        document: Dict[str, Any],
        tenant_id: Optional[str] = None,
        collection_type: str = "patents"
    ) -> bool:
        """索引专利文档"""
        await self.initialize()
        
        # 分块文档
        chunks = self._chunk_patent_document(document)
        
        # 获取嵌入
        texts = [chunk["content"] for chunk in chunks]
        embedding_results = await self._embedding_service.embed_texts(texts)
        
        # 创建文档对象
        documents = []
        embeddings = []
        
        doc_id = document.get("id") or document.get("application_number", "unknown")
        
        for i, (chunk, emb_result) in enumerate(zip(chunks, embedding_results)):
            chunk_id = f"{doc_id}_chunk_{i}"
            metadata = {
                **chunk.get("metadata", {}),
                "doc_id": doc_id,
                "chunk_index": i,
                "tenant_id": tenant_id or "default",
                "indexed_at": datetime.utcnow().isoformat()
            }
            
            documents.append(Document(
                id=chunk_id,
                content=chunk["content"],
                metadata=metadata
            ))
            embeddings.append(emb_result.embedding)
        
        # 获取集合名称
        collection_name = self._get_tenant_collection(tenant_id or "default", collection_type)
        
        # 添加到向量库
        return await self._backend.add_documents(collection_name, documents, embeddings)
    
    def _chunk_patent_document(
        self,
        document: Dict[str, Any],
        chunk_size: int = 512,
        overlap: int = 50
    ) -> List[Dict[str, Any]]:
        """分块专利文档"""
        chunks = []
        
        # 获取分块配置
        if self._settings:
            chunk_size = self._settings.CHUNK_SIZE
            overlap = self._settings.CHUNK_OVERLAP
        
        doc_id = document.get("id") or document.get("application_number", "unknown")
        
        # 按章节分块
        if self._settings and self._settings.CHUNK_BY_SECTION:
            # 标题
            if document.get("title"):
                chunks.append({
                    "content": document["title"],
                    "metadata": {"section": "title", "doc_id": doc_id}
                })
            
            # 摘要
            if document.get("abstract"):
                chunks.append({
                    "content": document["abstract"],
                    "metadata": {"section": "abstract", "doc_id": doc_id}
                })
            
            # 权利要求
            if document.get("claims"):
                claims_text = document["claims"]
                if isinstance(claims_text, list):
                    claims_text = "\n".join([str(c) for c in claims_text])
                chunks.append({
                    "content": claims_text,
                    "metadata": {"section": "claims", "doc_id": doc_id}
                })
            
            # 技术领域
            if document.get("technical_field"):
                chunks.append({
                    "content": document["technical_field"],
                    "metadata": {"section": "technical_field", "doc_id": doc_id}
                })
            
            # 说明书
            if document.get("description"):
                desc = document["description"]
                if isinstance(desc, dict):
                    desc_text = "\n".join([str(v) for v in desc.values()])
                else:
                    desc_text = str(desc)
                
                # 长文本需要进一步分块
                desc_chunks = self._split_text(desc_text, chunk_size, overlap)
                for i, chunk_text in enumerate(desc_chunks):
                    chunks.append({
                        "content": chunk_text,
                        "metadata": {"section": "description", "chunk": i, "doc_id": doc_id}
                    })
        else:
            # 简单分块
            full_text = self._get_full_text(document)
            text_chunks = self._split_text(full_text, chunk_size, overlap)
            for i, chunk_text in enumerate(text_chunks):
                chunks.append({
                    "content": chunk_text,
                    "metadata": {"chunk": i, "doc_id": doc_id}
                })
        
        return chunks
    
    def _get_full_text(self, document: Dict[str, Any]) -> str:
        """获取文档全文"""
        parts = []
        
        if document.get("title"):
            parts.append(f"标题: {document['title']}")
        if document.get("abstract"):
            parts.append(f"摘要: {document['abstract']}")
        if document.get("technical_field"):
            parts.append(f"技术领域: {document['technical_field']}")
        if document.get("claims"):
            claims = document["claims"]
            if isinstance(claims, list):
                claims = "\n".join([str(c) for c in claims])
            parts.append(f"权利要求: {claims}")
        if document.get("description"):
            desc = document["description"]
            if isinstance(desc, dict):
                desc = "\n".join([str(v) for v in desc.values()])
            parts.append(f"说明书: {desc}")
        
        return "\n\n".join(parts)
    
    def _split_text(
        self,
        text: str,
        chunk_size: int = 512,
        overlap: int = 50
    ) -> List[str]:
        """分割文本"""
        if len(text) <= chunk_size:
            return [text]
        
        chunks = []
        start = 0
        
        while start < len(text):
            end = start + chunk_size
            
            # 尝试在句子边界分割
            if end < len(text):
                # 查找最近的句子结束符
                for sep in ["。", "！", "？", "\n", ".", "!", "?"]:
                    last_sep = text.rfind(sep, start, end)
                    if last_sep > start + chunk_size // 2:
                        end = last_sep + 1
                        break
            
            chunk = text[start:end].strip()
            if chunk:
                chunks.append(chunk)
            
            start = end - overlap if end < len(text) else end
        
        return chunks
    
    async def search(
        self,
        query: str,
        top_k: int = 10,
        tenant_id: Optional[str] = None,
        collection_type: str = "patents",
        filter_metadata: Optional[Dict[str, Any]] = None
    ) -> List[SearchResult]:
        """语义搜索"""
        await self.initialize()
        
        # 获取查询嵌入
        query_result = await self._embedding_service.embed_query(query)
        
        # 获取集合名称
        collection_name = self._get_tenant_collection(tenant_id or "default", collection_type)
        
        # 执行搜索
        return await self._backend.search(
            collection=collection_name,
            query_embedding=query_result.embedding,
            top_k=top_k,
            filter_metadata=filter_metadata
        )
    
    async def hybrid_search(
        self,
        query: str,
        top_k: int = 10,
        tenant_id: Optional[str] = None,
        alpha: float = 0.7
    ) -> List[SearchResult]:
        """混合搜索 (语义 + 关键词)"""
        await self.initialize()
        
        from app.ai.rag.retrieval_pipeline import hybrid_search_engine
        
        result = await hybrid_search_engine.search(
            query=query,
            top_k=top_k,
            tenant_id=tenant_id,
            search_type="hybrid"
        )
        
        return [
            SearchResult(
                id=chunk.id,
                content=chunk.content,
                metadata=chunk.metadata,
                score=chunk.rerank_score or chunk.score
            )
            for chunk in result.chunks
        ]
    
    async def delete_document(
        self,
        doc_id: str,
        tenant_id: Optional[str] = None,
        collection_type: str = "patents"
    ) -> bool:
        """删除文档"""
        await self.initialize()
        
        collection_name = self._get_tenant_collection(tenant_id or "default", collection_type)
        
        # 查找所有相关的chunk
        # 注意：需要根据实际后端实现调整
        return await self._backend.delete_documents(collection_name, [doc_id])
    
    async def get_collection_stats(
        self,
        tenant_id: Optional[str] = None,
        collection_type: str = "patents"
    ) -> Dict[str, Any]:
        """获取集合统计"""
        await self.initialize()
        
        collection_name = self._get_tenant_collection(tenant_id or "default", collection_type)
        stats = await self._backend.get_stats(collection_name)
        
        # 添加数据库中的文档统计
        try:
            from sqlalchemy import select, func
            from app.database.engine import async_session_factory
            from app.database.models import RagDocument
            
            async with async_session_factory() as db:
                # 统计已上传文件总数
                total_query = select(func.count()).select_from(RagDocument)
                if tenant_id:
                    total_query = total_query.where(RagDocument.tenant_id == int(tenant_id))
                total_result = await db.execute(total_query)
                total_files = total_result.scalar() or 0
                
                # 统计已索引文件数
                indexed_query = select(func.count()).select_from(RagDocument).where(
                    RagDocument.status == "completed"
                )
                if tenant_id:
                    indexed_query = indexed_query.where(RagDocument.tenant_id == int(tenant_id))
                indexed_result = await db.execute(indexed_query)
                indexed_files = indexed_result.scalar() or 0
                
                # 添加到统计信息
                stats["total_files"] = total_files
                stats["indexed_files"] = indexed_files
                stats["failed_files"] = total_files - indexed_files
        except Exception as e:
            # 如果数据库查询失败，记录日志但不中断
            import logging
            logging.getLogger(__name__).warning(f"获取文件统计失败: {e}")
        
        return stats
    
    async def index_patent_batch(
        self,
        documents: List[Dict[str, Any]],
        tenant_id: Optional[str] = None,
        collection_type: str = "patents"
    ) -> Dict[str, bool]:
        """批量索引专利文档"""
        results = {}
        
        for doc in documents:
            doc_id = doc.get("id") or doc.get("application_number", "unknown")
            success = await self.index_patent_document(doc, tenant_id, collection_type)
            results[doc_id] = success
        
        return results


# 全局实例
enterprise_vector_db = EnterpriseVectorDBService()
