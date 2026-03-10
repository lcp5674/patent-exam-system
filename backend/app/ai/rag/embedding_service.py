"""
专利嵌入模型服务
Patent Embedding Service
支持多种嵌入模型，针对专利文档优化
"""
from __future__ import annotations
import logging
import hashlib
import asyncio
from typing import List, Optional, Dict, Any
from dataclasses import dataclass
from abc import ABC, abstractmethod
import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class EmbeddingResult:
    """嵌入结果"""
    text: str
    embedding: List[float]
    model: str
    dimension: int
    tokens: Optional[int] = None
    cache_hit: bool = False


class BaseEmbeddingModel(ABC):
    """嵌入模型基类"""
    
    @abstractmethod
    async def embed_texts(self, texts: List[str]) -> List[List[float]]:
        """嵌入文本列表"""
        pass
    
    @abstractmethod
    async def embed_query(self, query: str) -> List[float]:
        """嵌入查询"""
        pass
    
    @property
    @abstractmethod
    def dimension(self) -> int:
        """嵌入维度"""
        pass
    
    @property
    @abstractmethod
    def model_name(self) -> str:
        """模型名称"""
        pass


class SentenceTransformerEmbedding(BaseEmbeddingModel):
    """基于Sentence Transformers的嵌入模型"""
    
    def __init__(self, model_name: str, device: str = "cpu", dimension: int = 1024, hf_endpoint: str = None):
        self._model_name = model_name
        self._device = device
        self._dimension = dimension
        self._model = None
        self._hf_endpoint = hf_endpoint
    
    def _load_model(self):
        """延迟加载模型"""
        if self._model is None:
            try:
                from sentence_transformers import SentenceTransformer
                import os
                
                # 设置HuggingFace镜像
                if self._hf_endpoint:
                    os.environ['HF_ENDPOINT'] = self._hf_endpoint
                
                logger.info(f"加载嵌入模型: {self._model_name}, 设备: {self._device}, HF镜像: {self._hf_endpoint}")
                self._model = SentenceTransformer(self._model_name, device=self._device)
                self._dimension = self._model.get_sentence_embedding_dimension()
                logger.info(f"嵌入维度: {self._dimension}")
            except Exception as e:
                logger.error(f"加载嵌入模型失败: {e}")
                raise
    
    async def embed_texts(self, texts: List[str]) -> List[List[float]]:
        """嵌入文本列表"""
        self._load_model()
        loop = asyncio.get_event_loop()
        
        def _encode():
            embeddings = self._model.encode(
                texts,
                convert_to_numpy=True,
                normalize_embeddings=True,
                show_progress_bar=False
            )
            return embeddings.tolist()
        
        return await loop.run_in_executor(None, _encode)
    
    async def embed_query(self, query: str) -> List[float]:
        """嵌入查询"""
        results = await self.embed_texts([query])
        return results[0]
    
    @property
    def dimension(self) -> int:
        return self._dimension
    
    @property
    def model_name(self) -> str:
        return self._model_name


class OpenAIEmbedding(BaseEmbeddingModel):
    """OpenAI嵌入模型"""
    
    def __init__(self, api_key: str, model: str = "text-embedding-3-small", 
                 base_url: str = "https://api.openai.com/v1"):
        self._api_key = api_key
        self._model_name = model
        self._base_url = base_url
        self._dimension = 1536 if "small" in model else 3072
        self._client = None
    
    def _get_client(self):
        """获取OpenAI客户端"""
        if self._client is None:
            from openai import AsyncOpenAI
            self._client = AsyncOpenAI(
                api_key=self._api_key,
                base_url=self._base_url
            )
        return self._client
    
    async def embed_texts(self, texts: List[str]) -> List[List[float]]:
        """嵌入文本列表"""
        client = self._get_client()
        response = await client.embeddings.create(
            model=self._model_name,
            input=texts,
            encoding_format="float"
        )
        return [item.embedding for item in response.data]
    
    async def embed_query(self, query: str) -> List[float]:
        """嵌入查询"""
        results = await self.embed_texts([query])
        return results[0]
    
    @property
    def dimension(self) -> int:
        return self._dimension
    
    @property
    def model_name(self) -> str:
        return self._model_name


class ZhipuEmbedding(BaseEmbeddingModel):
    """智谱嵌入模型"""
    
    def __init__(self, api_key: str, model: str = "embedding-3"):
        self._api_key = api_key
        self._model_name = model
        self._dimension = 1024
        self._client = None
    
    def _get_client(self):
        """获取智谱客户端"""
        if self._client is None:
            from zhipuai import ZhipuAI
            self._client = ZhipuAI(api_key=self._api_key)
        return self._client
    
    async def embed_texts(self, texts: List[str]) -> List[List[float]]:
        """嵌入文本列表"""
        client = self._get_client()
        loop = asyncio.get_event_loop()
        
        def _encode():
            response = client.embeddings.create(
                model=self._model_name,
                input=texts
            )
            return [item.embedding for item in response.data]
        
        return await loop.run_in_executor(None, _encode)
    
    async def embed_query(self, query: str) -> List[float]:
        """嵌入查询"""
        results = await self.embed_texts([query])
        return results[0]
    
    @property
    def dimension(self) -> int:
        return self._dimension
    
    @property
    def model_name(self) -> str:
        return self._model_name


class OllamaEmbedding(BaseEmbeddingModel):
    """Ollama嵌入模型"""
    
    def __init__(self, model: str = "nomic-embed-text", base_url: str = "http://localhost:11434"):
        self._model_name = model
        self._base_url = base_url
        self._dimension = 768  # nomic-embed-text 默认维度
        self._client = None
    
    def _get_client(self):
        """获取Ollama客户端"""
        if self._client is None:
            from openai import AsyncOpenAI
            # Ollama兼容OpenAI API
            self._client = AsyncOpenAI(
                base_url=f"{self._base_url}/v1",
                api_key="ollama"  # Ollama不需要真实API Key
            )
        return self._client
    
    async def embed_texts(self, texts: List[str]) -> List[List[float]]:
        """嵌入文本列表"""
        client = self._get_client()
        try:
            response = await client.embeddings.create(
                model=self._model_name,
                input=texts,
                encoding_format="float"
            )
            return [item.embedding for item in response.data]
        except Exception as e:
            logger.error(f"Ollama嵌入失败: {e}")
            raise
    
    async def embed_query(self, query: str) -> List[float]:
        """嵌入查询"""
        results = await self.embed_texts([query])
        return results[0]
    
    @property
    def dimension(self) -> int:
        return self._dimension
    
    @property
    def model_name(self) -> str:
        return self._model_name


class PatentEmbeddingService:
    """专利嵌入服务 - 统一管理嵌入模型"""
    
    def __init__(self):
        self._models: Dict[str, BaseEmbeddingModel] = {}
        self._cache: Dict[str, EmbeddingResult] = {}
        self._default_model: Optional[str] = None
        self._settings = None
    
    def initialize(self, settings=None):
        """初始化嵌入服务"""
        if settings is None:
            from .config import get_rag_settings
            settings = get_rag_settings()
        self._settings = settings
        self._default_model = settings.EMBEDDING_MODEL
        self._cache_enabled = settings.EMBEDDING_CACHE_ENABLED
        
        logger.info(f"专利嵌入服务初始化, 默认模型: {self._default_model}")
    
    def _get_model(self, model_name: Optional[str] = None) -> BaseEmbeddingModel:
        """获取嵌入模型"""
        model_name = model_name or self._default_model
        if not model_name:
            raise ValueError("未配置嵌入模型")
        
        if model_name not in self._models:
            self._models[model_name] = self._create_model(model_name)
        
        return self._models[model_name]
    
    def _create_model(self, model_name: str) -> BaseEmbeddingModel:
        """
        创建嵌入模型
        
        优先级：
        1. 自定义模型配置（数据库中保存的用户配置）
        2. 系统环境变量配置（如果有对应的 API Key）
        3. 本地模型（HuggingFace）
        
        不再根据模型名称硬编码判断提供商，而是依赖用户配置。
        """
        
        # === 第1优先级：检查自定义模型配置 ===
        from .config import get_custom_model_config_sync
        custom_config = get_custom_model_config_sync(model_name)
        
        if custom_config and custom_config.get("api_url"):
            api_key = custom_config.get("api_key", "")
            base_url = custom_config.get("api_url", "https://api.openai.com/v1")
            # 移除末尾的 /embeddings，避免重复
            base_url = base_url.rstrip("/").rstrip("embeddings").rstrip("/")
            logger.info(f"使用自定义配置创建 Embedding 模型: {model_name}, URL: {base_url}")
            return OpenAIEmbedding(
                api_key=api_key,
                model=model_name,
                base_url=base_url
            )
        
        # === 第2优先级：系统环境变量配置 ===
        
        # 检查是否有 OpenAI 环境变量配置
        if self._settings.OPENAI_EMBEDDING_API_KEY:
            base_url = self._settings.OPENAI_EMBEDDING_BASE_URL
            logger.info(f"使用 OpenAI 环境变量配置创建 Embedding 模型: {model_name}")
            return OpenAIEmbedding(
                api_key=self._settings.OPENAI_EMBEDDING_API_KEY,
                model=model_name,
                base_url=base_url
            )
        
        # 检查是否有智谱环境变量配置
        if self._settings.ZHIPU_EMBEDDING_API_KEY:
            logger.info(f"使用智谱环境变量配置创建 Embedding 模型: {model_name}")
            return ZhipuEmbedding(
                api_key=self._settings.ZHIPU_EMBEDDING_API_KEY, 
                model="embedding-3"
            )
        
        # 检查是否有 Ollama 配置
        ollama_base_url = getattr(self._settings, 'OLLAMA_BASE_URL', None)
        if ollama_base_url:
            logger.info(f"使用 Ollama 配置创建 Embedding 模型: {model_name}, URL: {ollama_base_url}")
            return OllamaEmbedding(
                model=model_name,
                base_url=ollama_base_url
            )
        
        # === 第3优先级：没有配置任何在线嵌入 ===
        logger.error(f"未配置嵌入模型API，请设置环境变量: RAG_OPENAI_EMBEDDING_API_KEY 或 RAG_ZHIPU_EMBEDDING_API_KEY")
        raise ValueError(
            f"未配置嵌入模型: {model_name}。"
            "请设置以下环境变量之一: "
            "RAG_OPENAI_EMBEDDING_API_KEY (OpenAI), "
            "RAG_ZHIPU_EMBEDDING_API_KEY (智谱), "
            "或 RAG_OLLAMA_BASE_URL (Ollama)"
        )
    
    def _get_cache_key(self, text: str, model_name: str) -> str:
        """生成缓存键"""
        return hashlib.md5(f"{model_name}:{text}".encode()).hexdigest()
    
    async def embed_texts(
        self, 
        texts: List[str], 
        model: Optional[str] = None,
        use_cache: bool = True
    ) -> List[EmbeddingResult]:
        """嵌入文本列表"""
        model_name = model or self._default_model
        embedding_model = self._get_model(model_name)
        results = []
        texts_to_embed = []
        indices_to_embed = []
        
        # 检查缓存
        for i, text in enumerate(texts):
            if use_cache and self._cache_enabled:
                cache_key = self._get_cache_key(text, model_name)
                if cache_key in self._cache:
                    results.append(self._cache[cache_key])
                    continue
            
            texts_to_embed.append(text)
            indices_to_embed.append(i)
        
        # 嵌入未缓存的文本
        if texts_to_embed:
            embeddings = await embedding_model.embed_texts(texts_to_embed)
            
            for text, embedding in zip(texts_to_embed, embeddings):
                result = EmbeddingResult(
                    text=text,
                    embedding=embedding,
                    model=model_name,
                    dimension=len(embedding),
                    cache_hit=False
                )
                
                # 缓存结果
                if use_cache and self._cache_enabled:
                    cache_key = self._get_cache_key(text, model_name)
                    self._cache[cache_key] = result
                
                results.append(result)
        
        return results
    
    async def embed_query(self, query: str, model: Optional[str] = None) -> EmbeddingResult:
        """嵌入查询"""
        results = await self.embed_texts([query], model)
        return results[0]
    
    async def embed_patent_document(
        self,
        document: Dict[str, Any],
        model: Optional[str] = None
    ) -> Dict[str, EmbeddingResult]:
        """嵌入专利文档各部分"""
        sections = {}
        
        # 标题
        if document.get("title"):
            sections["title"] = await self.embed_query(document["title"], model)
        
        # 摘要
        if document.get("abstract"):
            sections["abstract"] = await self.embed_query(document["abstract"], model)
        
        # 权利要求
        if document.get("claims"):
            claims_text = "\n".join([
                claim.get("full_text", "") 
                for claim in document.get("claims", [])
                if claim.get("full_text")
            ])
            if claims_text:
                sections["claims"] = await self.embed_query(claims_text, model)
        
        # 技术领域
        if document.get("technical_field"):
            sections["technical_field"] = await self.embed_query(
                document["technical_field"], model
            )
        
        # 说明书
        if document.get("description"):
            desc_text = "\n".join([
                str(v) for v in document.get("description", {}).values()
                if v
            ])
            if desc_text:
                sections["description"] = await self.embed_query(desc_text, model)
        
        return sections
    
    def get_model_info(self, model_name: Optional[str] = None) -> Dict[str, Any]:
        """获取模型信息"""
        model = self._get_model(model_name)
        return {
            "model_name": model.model_name,
            "dimension": model.dimension,
            "cache_enabled": self._cache_enabled,
            "cache_size": len(self._cache)
        }
    
    def clear_cache(self):
        """清空缓存"""
        self._cache.clear()
        logger.info("嵌入缓存已清空")


# 全局实例
patent_embedding_service = PatentEmbeddingService()
