"""
企业级RAG向量数据库服务
使用Milvus进行专利文档的向量存储和检索
"""
import os
import logging
from typing import List, Dict, Optional, Any
from dataclasses import dataclass
from pymilvus import connections, Collection, FieldSchema, DataType, CollectionSchema, utility

logger = logging.getLogger(__name__)

# 延迟导入，避免启动时出错
_milvus_connected = False
_collections: Dict[str, Collection] = {}


def get_milvus_connection():
    """获取Milvus连接"""
    global _milvus_connected
    if not _milvus_connected:
        try:
            from app.ai.rag.config import get_rag_settings
            settings = get_rag_settings()
            
            connections.connect(
                alias="default",
                host=settings.MILVUS_HOST,
                port=settings.MILVUS_PORT,
                user=settings.MILVUS_USER,
                password=settings.MILVUS_PASSWORD,
                db_name=settings.MILVUS_DB_NAME
            )
            _milvus_connected = True
            logger.info(f"Milvus连接成功: {settings.MILVUS_HOST}:{settings.MILVUS_PORT}")
        except Exception as e:
            logger.error(f"初始化Milvus失败: {e}")
            raise
    return connections.get_connection("default")


def get_patent_collection(tenant_id: str = None):
    """获取专利文档集合（支持租户隔离）"""
    # 使用与enterprise_vector_db一致的集合命名规则
    collection_name = _get_tenant_collection_name(tenant_id) if tenant_id else "patent_documents"
    
    if collection_name in _collections:
        return _collections[collection_name]
    
    get_milvus_connection()
    
    try:
        if utility.has_collection(collection_name):
            collection = Collection(collection_name)
            collection.load()
        else:
            # 创建集合schema
            fields = [
                FieldSchema(name="id", dtype=DataType.VARCHAR, is_primary=True, max_length=255),
                FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=1024),
                FieldSchema(name="content", dtype=DataType.VARCHAR, max_length=65535),
                FieldSchema(name="metadata", dtype=DataType.JSON),
            ]
            schema = CollectionSchema(fields, description="专利文档向量存储")
            collection = Collection(name=collection_name, schema=schema)
            
            # 创建IVF_FLAT索引
            index_params = {
                "metric_type": "COSINE",
                "index_type": "IVF_FLAT",
                "params": {"nlist": 1024}
            }
            collection.create_index(field_name="embedding", index_params=index_params)
            collection.load()
            logger.info(f"创建Milvus集合: {collection_name}")
        
        _collections[collection_name] = collection
        return collection
        
    except Exception as e:
        logger.error(f"获取Milvus集合失败 {collection_name}: {e}")
        raise


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
            contents = []
            metadatas = []
            embeddings_data = []
            
            for i, chunk in enumerate(chunks):
                chunk_id = f"{doc_id}_chunk_{i}"
                ids.append(chunk_id)
                contents.append(chunk)
                metadatas.append({
                    **metadata,
                    "chunk_index": i,
                    "total_chunks": len(chunks),
                    "doc_id": doc_id
                })
            
            # 获取嵌入向量
            embeddings = self.get_embeddings(chunks)
            
            # 添加到Milvus
            data = [ids, embeddings, contents, metadatas]
            collection.insert(data)
            collection.flush()
            
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
    
    def _build_filter_expression(self, filter_metadata: Dict[str, Any]) -> str:
        """构建Milvus过滤表达式"""
        expressions = []
        for key, value in filter_metadata.items():
            if isinstance(value, str):
                expressions.append(f'metadata["{key}"] == "{value}"')
            elif isinstance(value, (int, float, bool)):
                expressions.append(f'metadata["{key}"] == {value}')
            elif isinstance(value, list):
                # 处理列表类型的IN查询
                quoted_values = [f'"{v}"' if isinstance(v, str) else str(v) for v in value]
                expressions.append(f'metadata["{key}"] in [{", ".join(quoted_values)}]')
        
        return " && ".join(expressions) if expressions else ""
    
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
            
            # 搜索参数
            search_params = {
                "metric_type": "COSINE",
                "params": {"nprobe": 10}
            }
            
            # 执行搜索
            results = collection.search(
                data=[query_embedding],
                anns_field="embedding",
                param=search_params,
                limit=top_k,
                expr=self._build_filter_expression(filter_metadata) if filter_metadata else None,
                output_fields=["content", "metadata"]
            )
            
            search_results = []
            if results and len(results) > 0:
                for hit in results[0]:
                    search_results.append(SearchResult(
                        id=hit.id,
                        content=hit.entity.get("content"),
                        metadata=hit.entity.get("metadata"),
                        score=hit.score  # Milvus直接返回余弦相似度
                    ))
            
            return search_results
            
        except Exception as e:
            logger.error(f"向量搜索失败: {e}")
            return []
    
    async def delete_document(self, doc_id: str) -> bool:
        """删除文档"""
        try:
            collection = get_patent_collection()
            
            # 删除所有相关的chunk
            expr = f'metadata["doc_id"] == "{doc_id}"'
            collection.delete(expr)
            logger.info(f"文档 {doc_id} 已从向量库删除")
            
            return True
        except Exception as e:
            logger.error(f"删除文档失败: {e}")
            return False
    
    async def get_stats(self) -> Dict[str, Any]:
        """获取向量库统计"""
        try:
            collection = get_patent_collection()
            count = collection.num_entities
            return {
                "total_documents": count,
                "storage_type": "milvus"
            }
        except Exception as e:
            logger.error(f"获取统计失败: {e}")
            return {"total_documents": 0, "error": str(e)}


# 全局实例
vector_db_service = VectorDatabaseService()
