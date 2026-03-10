"""
企业级RAG配置模块
Enterprise RAG Configuration Module
支持多种向量数据库后端和嵌入模型
"""
from __future__ import annotations
import os
import json
import logging
from typing import Optional, Literal, List
from pydantic_settings import BaseSettings
from pydantic import Field
from pathlib import Path

logger = logging.getLogger(__name__)

# 向量数据库类型
VectorDBType = Literal["chroma", "milvus", "qdrant", "pgvector", "weaviate"]

# 嵌入模型类型
EmbeddingModelType = Literal[
    "paraphrase-multilingual-MiniLM-L12-v2",  # 轻量级多语言
    "BAAI/bge-large-zh-v1.5",  # 中文优化
    "BAAI/bge-m3",  # 多语言大模型
    "text-embedding-3-small",  # OpenAI
    "text-embedding-3-large",  # OpenAI大模型
    "zhipu-embedding-3",  # 智谱
]


class RAGSettings(BaseSettings):
    """企业级RAG配置"""
    
    # ─── 向量数据库配置 ─────────────────────────────────────────
    VECTOR_DB_TYPE: VectorDBType = Field(
        default="chroma",
        description="向量数据库类型: chroma, milvus, qdrant, pgvector, weaviate"
    )
    
    # ChromaDB 服务器配置
    CHROMA_HOST: str = Field(
        default="localhost",
        description="ChromaDB服务器地址"
    )
    CHROMA_PORT: int = Field(
        default=8000,
        description="ChromaDB服务器端口"
    )
    
    # ChromaDB 本地配置
    CHROMA_PERSIST_DIR: str = Field(
        default="",
        description="ChromaDB持久化目录"
    )
    
    # Milvus 配置
    MILVUS_HOST: str = Field(default="localhost", description="Milvus服务地址")
    MILVUS_PORT: int = Field(default=19530, description="Milvus端口")
    MILVUS_USER: str = Field(default="", description="Milvus用户名")
    MILVUS_PASSWORD: str = Field(default="", description="Milvus密码")
    MILVUS_DB_NAME: str = Field(default="patent_rag", description="Milvus数据库名")
    
    # Qdrant 配置
    QDRANT_HOST: str = Field(default="localhost", description="Qdrant服务地址")
    QDRANT_PORT: int = Field(default=6333, description="Qdrant端口")
    QDRANT_API_KEY: str = Field(default="", description="Qdrant API Key")
    QDRANT_GRPC_PORT: int = Field(default=6334, description="Qdrant gRPC端口")
    
    # pgvector 配置 (使用现有PostgreSQL)
    PGVECTOR_COLLECTION: str = Field(default="patent_vectors", description="pgvector集合名")
    
    # Weaviate 配置
    WEAVIATE_URL: str = Field(default="http://localhost:8080", description="Weaviate服务地址")
    WEAVIATE_API_KEY: str = Field(default="", description="Weaviate API Key")
    
    # ─── 嵌入模型配置 ─────────────────────────────────────────
    EMBEDDING_MODEL: EmbeddingModelType = Field(
        default="text-embedding-3-small",
        description="嵌入模型类型"
    )
    EMBEDDING_DIMENSION: int = Field(
        default=1536,
        description="嵌入向量维度 (text-embedding-3-small: 1536, text-embedding-3-large: 3072, bge-large-zh: 1024)"
    )
    EMBEDDING_BATCH_SIZE: int = Field(
        default=32,
        description="嵌入批处理大小"
    )
    EMBEDDING_DEVICE: str = Field(
        default="cpu",
        description="嵌入设备: cpu, cuda, mps"
    )
    
    # OpenAI 嵌入配置
    OPENAI_EMBEDDING_API_KEY: str = Field(default="", description="OpenAI嵌入API Key")
    OPENAI_EMBEDDING_BASE_URL: str = Field(
        default="https://api.openai.com/v1",
        description="OpenAI嵌入API基础URL"
    )
    
    # 智谱嵌入配置
    ZHIPU_EMBEDDING_API_KEY: str = Field(default="", description="智谱嵌入API Key")
    
    # HuggingFace 配置
    HF_ENDPOINT: str = Field(
        default="https://hf-mirror.com",
        description="HuggingFace镜像源 (默认使用 hf-mirror.com)"
    )
    
    # Ollama 配置
    OLLAMA_BASE_URL: str = Field(
        default="http://localhost:11434",
        description="Ollama服务地址"
    )
    
    # ─── 检索配置 ─────────────────────────────────────────────
    RETRIEVAL_TOP_K: int = Field(default=10, description="检索返回文档数")
    RERANK_TOP_K: int = Field(default=5, description="重排序后返回文档数")
    HYBRID_SEARCH_ALPHA: float = Field(
        default=0.7,
        description="混合检索权重 (语义搜索权重, 关键词搜索权重为1-alpha)"
    )
    
    # BM25 配置 (关键词搜索)
    BM25_K1: float = Field(default=1.5, description="BM25 k1参数")
    BM25_B: float = Field(default=0.75, description="BM25 b参数")
    
    # ─── 分块配置 ─────────────────────────────────────────────
    CHUNK_SIZE: int = Field(default=512, description="文档分块大小(字符)")
    CHUNK_OVERLAP: int = Field(default=50, description="分块重叠大小")
    CHUNK_MIN_SIZE: int = Field(default=100, description="最小分块大小")
    
    # 按章节分块
    CHUNK_BY_SECTION: bool = Field(default=True, description="是否按专利章节分块")
    
    # ─── 重排序配置 ─────────────────────────────────────────
    RERANKER_MODEL: str = Field(
        default="BAAI/bge-reranker-large",
        description="重排序模型"
    )
    RERANK_ENABLED: bool = Field(default=True, description="是否启用重排序")
    
    # ─── 多租户配置 ─────────────────────────────────────────
    TENANT_ISOLATION: bool = Field(default=True, description="是否启用租户隔离")
    DEFAULT_TENANT_COLLECTION: str = Field(default="default", description="默认租户集合")
    
    # ─── 缓存配置 ─────────────────────────────────────────────
    EMBEDDING_CACHE_ENABLED: bool = Field(default=True, description="是否启用嵌入缓存")
    EMBEDDING_CACHE_TTL: int = Field(default=86400, description="嵌入缓存TTL(秒)")
    QUERY_CACHE_ENABLED: bool = Field(default=True, description="是否启用查询缓存")
    QUERY_CACHE_TTL: int = Field(default=3600, description="查询缓存TTL(秒)")
    
    # ─── 性能配置 ─────────────────────────────────────────────
    MAX_CONCURRENT_EMBEDDINGS: int = Field(default=10, description="最大并发嵌入数")
    INDEX_BUILD_BATCH_SIZE: int = Field(default=100, description="索引构建批处理大小")
    
    model_config = {"env_prefix": "RAG_", "env_file": ".env", "extra": "ignore"}
    
    def get_chroma_persist_dir(self) -> str:
        """获取ChromaDB持久化目录"""
        if self.CHROMA_PERSIST_DIR:
            return self.CHROMA_PERSIST_DIR
        from app.config import BASE_DIR
        return str(BASE_DIR / "data" / "vector_store")


# 全局配置实例
_rag_settings: Optional[RAGSettings] = None


def get_rag_settings() -> RAGSettings:
    """获取RAG配置实例"""
    global _rag_settings
    if _rag_settings is None:
        _rag_settings = RAGSettings()
    return _rag_settings


def save_rag_settings():
    """保存RAG配置到环境变量(运行时)"""
    # 注意: 这个函数只保存到运行时配置，不会持久化到文件
    # 实际生产环境应该将配置保存到数据库或配置文件
    pass


# 可用的Embedding模型列表
AVAILABLE_EMBEDDING_MODELS = [
    # 开源模型
    {"value": "paraphrase-multilingual-MiniLM-L12-v2", "label": "MiniLM L12 (多语言)", "provider": "huggingface", "dimension": 384},
    {"value": "BAAI/bge-base-zh-v1.5", "label": "BGE Base ZH v1.5", "provider": "huggingface", "dimension": 768},
    {"value": "BAAI/bge-large-zh-v1.5", "label": "BGE Large ZH v1.5", "provider": "huggingface", "dimension": 1024},
    {"value": "BAAI/bge-m3", "label": "BGE M3 (多语言)", "provider": "huggingface", "dimension": 1024},
    {"value": "m3e-base", "label": "M3E Base", "provider": "huggingface", "dimension": 768},
    # OpenAI
    {"value": "text-embedding-3-small", "label": "OpenAI Text Embedding 3 Small", "provider": "openai", "dimension": 1536},
    {"value": "text-embedding-3-large", "label": "OpenAI Text Embedding 3 Large", "provider": "openai", "dimension": 3072},
    {"value": "text-embedding-ada-002", "label": "OpenAI Ada 002", "provider": "openai", "dimension": 1536},
    # 智谱
    {"value": "zhipu-embedding-3", "label": "智谱 Embedding 3", "provider": "zhipu", "dimension": 1024},
    # Ollama (本地)
    {"value": "nomic-embed-text", "label": "Nomic Embed Text (Ollama)", "provider": "ollama", "dimension": 768},
    {"value": "mxbai-embed-large", "label": "MXBai Embed Large (Ollama)", "provider": "ollama", "dimension": 1024},
    # 自定义模型 (用户可配置)
    {"value": "custom-openai", "label": "自定义 OpenAI 兼容模型", "provider": "custom", "dimension": 1536, "custom": True},
    {"value": "custom-ollama", "label": "自定义 Ollama 模型", "provider": "custom", "dimension": 768, "custom": True},
    {"value": "custom-api", "label": "自定义 API 模型", "provider": "custom", "dimension": 1024, "custom": True},
]


# 自定义模型配置存储 (PostgreSQL数据库)
# 简单的同步缓存，用于避免async问题
_custom_config_cache: dict = {}


def get_custom_model_config_sync(model_name: str) -> Optional[dict]:
    """同步获取自定义模型配置（先从缓存，缓存为空则从数据库）"""
    # 先从缓存获取
    config = _custom_config_cache.get(model_name)
    if config:
        return config
    
    # 缓存没有，从数据库同步获取
    import asyncio
    try:
        # 创建新的事件循环来执行异步函数
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            config = loop.run_until_complete(get_custom_model_config(model_name))
            if config:
                _custom_config_cache[model_name] = config
            return config
        finally:
            loop.close()
    except Exception as e:
        logger.warning(f"同步获取Embedding配置失败: {e}")
        return None


async def get_custom_model_config(model_name: str) -> Optional[dict]:
    """获取自定义模型配置"""
    # 首先尝试从缓存获取
    config = get_custom_model_config_sync(model_name)
    if config:
        return config
    
    # 如果缓存没有，从数据库加载
    from app.database.models import CustomEmbeddingModelConfig
    from app.database import get_db
    from sqlalchemy import select
    
    async for db in get_db():
        result = await db.execute(
            select(CustomEmbeddingModelConfig).where(CustomEmbeddingModelConfig.model_name == model_name)
        )
        config = result.scalar_one_or_none()
        if config:
            config_dict = {
                "model_name": config.model_name,
                "provider": config.provider,
                "api_url": config.api_url,
                "api_key": config.api_key,
                "dimension": config.dimension,
                "enabled": config.enabled,
                "description": config.description,
            }
            # 更新缓存
            _custom_config_cache[model_name] = config_dict
            return config_dict
    return None


async def set_custom_model_config(model_name: str, config: dict):
    """设置自定义模型配置"""
    # 更新缓存
    _custom_config_cache[model_name] = config
    
    # 保存到数据库
    from app.database.models import CustomEmbeddingModelConfig
    from app.database import get_db
    from sqlalchemy import select
    
    async for db in get_db():
        result = await db.execute(
            select(CustomEmbeddingModelConfig).where(CustomEmbeddingModelConfig.model_name == model_name)
        )
        existing = result.scalar_one_or_none()
        
        if existing:
            existing.provider = config.get("provider", "custom")
            existing.api_url = config.get("api_url")
            existing.api_key = config.get("api_key")
            existing.dimension = config.get("dimension", 1536)
            existing.enabled = config.get("enabled", True)
            existing.description = config.get("description")
        else:
            new_config = CustomEmbeddingModelConfig(
                model_name=model_name,
                provider=config.get("provider", "custom"),
                api_url=config.get("api_url"),
                api_key=config.get("api_key"),
                dimension=config.get("dimension", 1536),
                enabled=config.get("enabled", True),
                description=config.get("description"),
            )
            db.add(new_config)
        await db.commit()


async def delete_custom_model_config(model_name: str):
    """删除自定义模型配置"""
    # 从缓存删除
    _custom_config_cache.pop(model_name, None)
    
    # 从数据库删除
    from app.database.models import CustomEmbeddingModelConfig
    from app.database import get_db
    from sqlalchemy import select
    
    async for db in get_db():
        result = await db.execute(
            select(CustomEmbeddingModelConfig).where(CustomEmbeddingModelConfig.model_name == model_name)
        )
        config = result.scalar_one_or_none()
        if config:
            await db.delete(config)
            await db.commit()


async def list_custom_model_configs() -> List[dict]:
    """列出所有自定义模型配置"""
    # 尝试从缓存返回
    if _custom_config_cache:
        return list(_custom_config_cache.values())
    
    # 从数据库加载
    from app.database.models import CustomEmbeddingModelConfig
    from app.database import get_db
    
    async for db in get_db():
        from sqlalchemy import select
        result = await db.execute(select(CustomEmbeddingModelConfig))
        configs = result.scalars().all()
        result_list = [
            {
                "model_name": c.model_name,
                "provider": c.provider,
                "api_url": c.api_url,
                "api_key": c.api_key,
                "dimension": c.dimension,
                "enabled": c.enabled,
                "description": c.description,
            }
            for c in configs
        ]
        # 更新缓存
        for c in result_list:
            _custom_config_cache[c["model_name"]] = c
        return result_list
    return []

# 可用的Rerank模型列表
AVAILABLE_RERANK_MODELS = [
    {"value": "BAAI/bge-reranker-base", "label": "BGE Reranker Base", "provider": "huggingface"},
    {"value": "BAAI/bge-reranker-large", "label": "BGE Reranker Large", "provider": "huggingface"},
    {"value": "BAAI/bge-reranker-v2-minicpm20", "label": "BGE Reranker v2 MiniCPM20", "provider": "huggingface"},
    {"value": "cohere-rerank-multilingual-v3.0", "label": "Cohere Rerank Multilingual", "provider": "cohere"},
    {"value": "openai-rerank", "label": "OpenAI Rerank", "provider": "openai"},
]


# 自定义Reranker模型配置缓存
_reranker_config_cache: dict = {}


def get_custom_reranker_config_sync(model_name: str) -> Optional[dict]:
    """同步获取自定义Reranker模型配置（先从缓存，缓存为空则从数据库）"""
    # 先从缓存获取
    config = _reranker_config_cache.get(model_name)
    if config:
        return config
    
    # 缓存没有，尝试从数据库获取
    # 注意：在异步上下文中无法创建新的事件循环，所以这里简单地返回None
    # 调用方应该使用异步版本的 get_custom_reranker_config
    import asyncio
    try:
        # 检查是否在异步上下文中
        asyncio.get_running_loop()
        # 如果在异步上下文中，返回None，让调用方使用异步版本
        return None
    except RuntimeError:
        # 没有运行中的循环，可以安全创建新循环
        pass
    
    try:
        # 创建新的事件循环来执行异步函数
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            config = loop.run_until_complete(get_custom_reranker_config(model_name))
            if config:
                _reranker_config_cache[model_name] = config
            return config
        finally:
            loop.close()
    except Exception as e:
        logger.warning(f"同步获取Reranker配置失败: {e}")
        return None


# ========== 自定义Reranker模型配置 (PostgreSQL数据库) ==========
async def get_custom_reranker_config(model_name: str) -> Optional[dict]:
    """获取自定义Reranker模型配置"""
    from app.database.models import CustomRerankerModelConfig
    from app.database import get_db
    
    async for db in get_db():
        from sqlalchemy import select
        result = await db.execute(
            select(CustomRerankerModelConfig).where(CustomRerankerModelConfig.model_name == model_name)
        )
        config = result.scalar_one_or_none()
        if config:
            return {
                "model_name": config.model_name,
                "provider": config.provider,
                "api_url": config.api_url,
                "api_key": config.api_key,
                "enabled": config.enabled,
                "description": config.description,
            }
    return None


async def set_custom_reranker_config(model_name: str, config: dict):
    """设置自定义Reranker模型配置"""
    # 更新缓存
    _reranker_config_cache[model_name] = config
    
    from app.database.models import CustomRerankerModelConfig
    from app.database import get_db
    from sqlalchemy import select
    
    async for db in get_db():
        result = await db.execute(
            select(CustomRerankerModelConfig).where(CustomRerankerModelConfig.model_name == model_name)
        )
        existing = result.scalar_one_or_none()
        
        if existing:
            existing.provider = config.get("provider", "custom")
            existing.api_url = config.get("api_url")
            existing.api_key = config.get("api_key")
            existing.enabled = config.get("enabled", True)
            existing.description = config.get("description")
        else:
            new_config = CustomRerankerModelConfig(
                model_name=model_name,
                provider=config.get("provider", "custom"),
                api_url=config.get("api_url"),
                api_key=config.get("api_key"),
                enabled=config.get("enabled", True),
                description=config.get("description"),
            )
            db.add(new_config)
        await db.commit()


async def delete_custom_reranker_config(model_name: str):
    """删除自定义Reranker模型配置"""
    from app.database.models import CustomRerankerModelConfig
    from app.database import get_db
    from sqlalchemy import select
    
    async for db in get_db():
        result = await db.execute(
            select(CustomRerankerModelConfig).where(CustomRerankerModelConfig.model_name == model_name)
        )
        config = result.scalar_one_or_none()
        if config:
            await db.delete(config)
            await db.commit()


async def list_custom_reranker_configs() -> List[dict]:
    """列出所有自定义Reranker模型配置"""
    from app.database.models import CustomRerankerModelConfig
    from app.database import get_db
    
    async for db in get_db():
        from sqlalchemy import select
        result = await db.execute(select(CustomRerankerModelConfig))
        configs = result.scalars().all()
        return [
            {
                "model_name": c.model_name,
                "provider": c.provider,
                "api_url": c.api_url,
                "api_key": c.api_key,
                "enabled": c.enabled,
                "description": c.description,
            }
            for c in configs
        ]
    return []
