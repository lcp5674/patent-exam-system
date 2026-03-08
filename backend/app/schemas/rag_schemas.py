"""
RAG API Schema定义
"""
from __future__ import annotations
from typing import Optional, List, Dict, Any, Literal
from pydantic import BaseModel, Field
from datetime import datetime


# ============== 请求模型 ==============

class SearchRequest(BaseModel):
    """搜索请求"""
    query: str = Field(..., description="搜索查询", min_length=1)
    top_k: int = Field(default=10, ge=1, le=100, description="返回结果数量")
    search_type: Literal["semantic", "keyword", "hybrid"] = Field(
        default="hybrid", description="搜索类型"
    )
    use_rerank: bool = Field(default=True, description="是否使用重排序")
    filters: Optional[Dict[str, Any]] = Field(default=None, description="元数据过滤条件")


class IndexDocumentRequest(BaseModel):
    """索引文档请求"""
    document_id: Optional[str] = Field(default=None, description="文档ID")
    application_number: Optional[str] = Field(default=None, description="申请号")
    title: Optional[str] = Field(default=None, description="标题")
    abstract: Optional[str] = Field(default=None, description="摘要")
    claims: Optional[List[str]] = Field(default=None, description="权利要求")
    description: Optional[str] = Field(default=None, description="说明书")
    technical_field: Optional[str] = Field(default=None, description="技术领域")
    metadata: Optional[Dict[str, Any]] = Field(default=None, description="额外元数据")


class IndexBatchRequest(BaseModel):
    """批量索引请求"""
    documents: List[IndexDocumentRequest] = Field(..., min_length=1, description="文档列表")


class PatentSearchRequest(BaseModel):
    """专利数据库搜索请求"""
    query: str = Field(..., description="搜索查询", min_length=1)
    sources: Optional[List[str]] = Field(
        default=["uspto"], description="数据源"
    )
    max_results: int = Field(default=20, ge=1, le=100, description="每个数据源最大结果数")
    date_from: Optional[str] = Field(default=None, description="起始日期 (YYYY-MM-DD)")
    date_to: Optional[str] = Field(default=None, description="结束日期 (YYYY-MM-DD)")
    classifications: Optional[List[str]] = Field(default=None, description="专利分类")
    auto_index: bool = Field(default=False, description="是否自动索引到RAG系统")


class PatentDetailRequest(BaseModel):
    """获取专利详情请求"""
    patent_id: str = Field(..., description="专利ID")
    source: Literal["uspto", "google", "lens"] = Field(default="uspto", description="数据源")


class GetCitationsRequest(BaseModel):
    """获取引用文献请求"""
    patent_id: str = Field(..., description="专利ID")
    source: Literal["uspto", "google", "lens"] = Field(default="uspto", description="数据源")


class DeleteDocumentRequest(BaseModel):
    """删除文档请求"""
    document_id: str = Field(..., description="文档ID")


# ============== 响应模型 ==============

class SearchChunk(BaseModel):
    """搜索结果片段"""
    id: str
    content: str
    score: float = Field(description="相关性分数")
    metadata: Dict[str, Any]
    source: str = Field(default="semantic", description="来源类型")


class SearchResponse(BaseModel):
    """搜索响应"""
    query: str
    chunks: List[SearchChunk]
    total: int
    search_type: str
    latency_ms: float
    tenant_id: Optional[str] = None
    # 引用相关字段
    citations: Optional[List[Dict[str, Any]]] = Field(default=None, description="格式化的引用列表")
    reference_list: Optional[str] = Field(default=None, description="参考文献列表")
    inline_citations: Optional[str] = Field(default=None, description="行内引用标记")


class PatentDocumentResponse(BaseModel):
    """专利文档响应"""
    id: str
    application_number: Optional[str] = None
    publication_number: Optional[str] = None
    title: Optional[str] = None
    abstract: Optional[str] = None
    claims: Optional[List[str]] = None
    applicant: Optional[str] = None
    assignee: Optional[str] = None
    inventor: Optional[str] = None
    application_date: Optional[str] = None
    publication_date: Optional[str] = None
    ipc_classification: Optional[List[str]] = None
    cpc_classification: Optional[List[str]] = None
    patent_type: Optional[str] = None
    source: str
    url: Optional[str] = None


class PatentSearchResponse(BaseModel):
    """专利搜索响应"""
    query: str
    results: Dict[str, List[PatentDocumentResponse]] = Field(
        description="按数据源分组的结果"
    )
    total_count: int
    sources_searched: List[str]


class PatentSearchAndIndexResponse(BaseModel):
    """专利搜索并索引响应"""
    total_found: int
    indexed: int
    sources: Dict[str, int]
    index_results: Optional[Dict[str, bool]] = None
    message: Optional[str] = None


class IndexResponse(BaseModel):
    """索引响应"""
    success: bool
    document_id: str
    chunk_count: int
    message: str


class IndexBatchResponse(BaseModel):
    """批量索引响应"""
    total: int
    successful: int
    failed: int
    results: Dict[str, bool]


class CollectionStatsResponse(BaseModel):
    """集合统计响应"""
    collection: str
    document_count: int
    backend: str
    additional_info: Optional[Dict[str, Any]] = None


class ConnectorInfo(BaseModel):
    """连接器信息"""
    name: str
    available: bool


class DatabaseConnectorsResponse(BaseModel):
    """数据库连接器列表响应"""
    connectors: List[ConnectorInfo]


class RAGConfigResponse(BaseModel):
    """RAG配置响应"""
    vector_db_type: str
    embedding_model: str
    embedding_dimension: int
    chunk_size: int
    chunk_overlap: int
    retrieval_top_k: int
    rerank_enabled: bool
    hybrid_search_alpha: float


class ModelOption(BaseModel):
    """模型选项"""
    value: str
    label: str
    provider: str
    dimension: Optional[int] = None


class AvailableModelsResponse(BaseModel):
    """可用模型列表响应"""
    embedding_models: List[ModelOption]
    rerank_models: List[ModelOption]


class DeleteResponse(BaseModel):
    """删除响应"""
    success: bool
    document_id: str
    message: str


class RAGHealthResponse(BaseModel):
    """RAG健康检查响应"""
    status: str
    vector_db: str
    embedding_service: str
    connectors: List[ConnectorInfo]
    timestamp: str


# ============== 文件上传和URL爬取模型 ==============

class URLCrawlRequest(BaseModel):
    """URL爬取请求"""
    url: str = Field(..., description="要爬取的URL", min_length=1)
    extract_images: bool = Field(default=False, description="是否提取图片")
    max_depth: int = Field(default=1, ge=1, le=3, description="爬取深度")


class URLCrawlResponse(BaseModel):
    """URL爬取响应"""
    success: bool
    url: str
    title: Optional[str] = None
    content: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    images: Optional[List[str]] = None
    error: Optional[str] = None


class FileUploadResponse(BaseModel):
    """文件上传响应"""
    success: bool
    file_name: str
    file_type: str
    file_size: int
    content: Optional[str] = None
    chunk_count: int = 0
    document_id: Optional[int] = None  # 新增：返回创建的文档ID
    error: Optional[str] = None


class RagDocumentResponse(BaseModel):
    """RAG文档响应"""
    id: int
    tenant_id: Optional[int] = None
    file_name: str
    file_type: str
    file_size: int
    file_path: str
    chunk_count: int = 0
    indexed_count: int = 0
    status: str
    error_message: Optional[str] = None
    indexed_at: Optional[str] = None
    created_at: str
    updated_at: Optional[str] = None


class RagDocumentListResponse(BaseModel):
    """RAG文档列表响应"""
    documents: List[RagDocumentResponse]
    total: int


class ReindexResponse(BaseModel):
    """重新索引响应"""
    success: bool
    document_id: int
    indexed_count: int
    message: str


class ModelTestRequest(BaseModel):
    """模型测试请求"""
    model_name: str = Field(..., description="模型名称")
    provider: Optional[str] = Field(default=None, description="模型提供商")
    test_text: str = Field(default="这是一个测试文本，用于验证模型连接性。", description="测试文本")
    # 自定义配置
    api_url: Optional[str] = Field(default=None, description="自定义API URL (用于OpenAI兼容API)")
    api_key: Optional[str] = Field(default=None, description="自定义API Key")


class ModelTestResponse(BaseModel):
    """模型测试响应"""
    success: bool
    model_name: str
    provider: str
    latency_ms: float
    embedding_dim: Optional[int] = None
    sample_embedding: Optional[List[float]] = None
    error: Optional[str] = None


class CustomModelConfig(BaseModel):
    """自定义模型配置"""
    model_name: str = Field(..., description="模型名称")
    provider: str = Field(..., description="模型提供商")
    api_url: Optional[str] = Field(default=None, description="API URL (OpenAI兼容)")
    api_key: Optional[str] = Field(default=None, description="API Key")
    dimension: Optional[int] = Field(default=None, description="向量维度")
    enabled: bool = Field(default=True, description="是否启用")


class ModelConfigListResponse(BaseModel):
    """模型配置列表响应"""
    custom_configs: List[CustomModelConfig]


# ============== 专利全量/增量爬取模型 ==============

class PatentFullCrawlRequest(BaseModel):
    """专利全量爬取请求"""
    sources: List[str] = Field(
        default=["soopat"], 
        description="数据源列表 (dawei/baiten/soopat/uspto/wipo/epo/google/lens)"
    )
    query: str = Field(..., description="搜索关键词", min_length=1)
    max_results: int = Field(default=100, ge=1, le=1000, description="每个数据源最大结果数")
    tenant_id: str = Field(..., description="租户ID")
    batch_size: int = Field(default=50, ge=10, le=100, description="批量索引大小")


class PatentIncrementalCrawlRequest(BaseModel):
    """专利增量爬取请求"""
    sources: List[str] = Field(
        default=["soopat"], 
        description="数据源列表"
    )
    query: str = Field(..., description="搜索关键词", min_length=1)
    date_from: Optional[str] = Field(default=None, description="起始日期 (YYYY-MM-DD), 默认最近7天")
    max_results: int = Field(default=50, ge=1, le=500, description="每个数据源最大结果数")
    tenant_id: str = Field(..., description="租户ID")


class PatentCrawlStatusResponse(BaseModel):
    """专利爬取状态响应"""
    status: str  # pending, running, completed, failed
    total_found: int
    indexed: int
    failed: int
    sources: Dict[str, int]
    message: Optional[str] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    errors: Optional[List[Dict[str, str]]] = None


# ─── 专利数据源配置 Schema ─────────────────────────────


class PatentSourceConfigCreate(BaseModel):
    """创建专利数据源配置"""
    source_name: str = Field(..., description="数据源名称: baiten, dawei, uspto, lens")
    api_key: Optional[str] = Field(default=None, description="API密钥")
    app_id: Optional[str] = Field(default=None, description="App ID (仅 Baiten 需要)")
    api_url: Optional[str] = Field(default=None, description="自定义API地址")
    is_enabled: bool = Field(default=True, description="是否启用")


class PatentSourceConfigUpdate(BaseModel):
    """更新专利数据源配置"""
    api_key: Optional[str] = Field(default=None, description="API密钥")
    app_id: Optional[str] = Field(default=None, description="App ID (仅 Baiten 需要)")
    api_url: Optional[str] = Field(default=None, description="自定义API地址")
    is_enabled: Optional[bool] = Field(default=None, description="是否启用")


class PatentSourceConfigResponse(BaseModel):
    """专利数据源配置响应"""
    id: int
    source_name: str
    app_id: Optional[str] = None
    api_url: Optional[str] = None
    is_enabled: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class PatentSourceConfigListResponse(BaseModel):
    """专利数据源配置列表响应"""
    configs: List[PatentSourceConfigResponse]
    total: int
