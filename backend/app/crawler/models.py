"""数据模型定义"""
from datetime import datetime
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field
from enum import Enum

class PatentStatus(str, Enum):
    """专利状态"""
    PENDING = "pending"  # 申请中
    PUBLISHED = "published"  # 已公布
    GRANTED = "granted"  # 已授权
    EXPIRED = "expired"  # 已过期
    REJECTED = "rejected"  # 被驳回
    WITHDRAWN = "withdrawn"  # 撤回

class PriorityLevel(str, Enum):
    """优先级级别"""
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"

class CrawlStatus(str, Enum):
    """爬取状态"""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"

class PatentDocument(BaseModel):
    """专利文档模型"""
    application_number: Optional[str] = Field(None, description="申请号")
    publication_number: Optional[str] = Field(None, description="公开号/公告号")
    title: Optional[str] = Field(None, description="标题")
    abstract: Optional[str] = Field(None, description="摘要")
    claims: Optional[str] = Field(None, description="权利要求书")
    description: Optional[str] = Field(None, description="说明书")

    applicant: Optional[str] = Field(None, description="申请人")
    inventor: Optional[str] = Field(None, description="发明人")
    assignee: Optional[str] = Field(None, description="受让人")
    agent: Optional[str] = Field(None, description="代理人")

    application_date: Optional[datetime] = Field(None, description="申请日期")
    publication_date: Optional[datetime] = Field(None, description="公开日期")
    priority_date: Optional[datetime] = Field(None, description="优先权日期")
    grant_date: Optional[datetime] = Field(None, description="授权日期")

    ipc_classification: Optional[str] = Field(None, description="IPC分类号")
    cpc_classification: Optional[str] = Field(None, description="CPC分类号")
    us_classification: Optional[str] = Field(None, description="美国分类号")

    patent_type: Optional[str] = Field(None, description="专利类型")
    status: Optional[PatentStatus] = Field(None, description="专利状态")

    source: str = Field(..., description="数据来源")
    url: Optional[str] = Field(None, description="源URL")

    family_id: Optional[str] = Field(None, description="专利家族ID")
    priority_number: Optional[str] = Field(None, description="优先权号")

    # 元数据
    created_at: datetime = Field(default_factory=datetime.utcnow, description="创建时间")
    updated_at: datetime = Field(default_factory=datetime.utcnow, description="更新时间")
    version: int = Field(default=1, description="版本号")

    # 原始数据
    raw_data: Dict[str, Any] = Field(default_factory=dict, description="原始数据")

    # 摘要
    generated_summary: Optional[str] = Field(None, description="生成的摘要")
    key_points: List[str] = Field(default_factory=list, description="关键点")
    technical_field: Optional[str] = Field(None, description="技术领域")

    class Config:
        use_enum_values = True

class CrawlTask(BaseModel):
    """爬取任务模型"""
    task_id: str = Field(..., description="任务ID")
    source: str = Field(..., description="数据来源")
    patent_number: Optional[str] = Field(None, description="专利号")
    query: Optional[str] = Field(None, description="搜索查询")

    priority: PriorityLevel = Field(default=PriorityLevel.MEDIUM, description="优先级")
    status: CrawlStatus = Field(default=CrawlStatus.PENDING, description="状态")

    # 重试相关
    retry_count: int = Field(default=0, description="重试次数")
    max_retries: int = Field(default=3, description="最大重试次数")

    # 时间相关
    scheduled_at: datetime = Field(default_factory=datetime.utcnow, description="计划执行时间")
    started_at: Optional[datetime] = Field(None, description="开始时间")
    completed_at: Optional[datetime] = Field(None, description="完成时间")

    # 结果
    result: Optional[PatentDocument] = Field(None, description="爬取结果")
    error_message: Optional[str] = Field(None, description="错误信息")

    created_by: Optional[str] = Field(None, description="创建者")

    class Config:
        use_enum_values = True

class IncrementalUpdateRecord(BaseModel):
    """增量更新记录"""
    source: str = Field(..., description="数据来源")
    last_update_time: datetime = Field(..., description="最后更新时间")
    last_patent_number: Optional[str] = Field(None, description="最后处理的专利号")
    total_processed: int = Field(default=0, description="处理总数")
    success_count: int = Field(default=0, description="成功数量")
    failed_count: int = Field(default=0, description="失败数量")

    # 哈希记录（用于变更检测）
    content_hashes: Dict[str, str] = Field(default_factory=dict, description="内容哈希")

    class Config:
        use_enum_values = True

class VectorIndexRecord(BaseModel):
    """向量索引记录"""
    patent_number: str = Field(..., description="专利号")
    vector_id: str = Field(..., description="向量ID")
    embedding_model: str = Field(..., description="Embedding模型")
    chunk_index: int = Field(..., description="分块索引")
    chunk_text: str = Field(..., description="分块文本")

    # 元数据
    title_embedding: Optional[List[float]] = Field(None, description="标题向量")
    abstract_embedding: Optional[List[float]] = Field(None, description="摘要向量")
    claims_embedding: Optional[List[float]] = Field(None, description="权利要求向量")
    full_text_embedding: Optional[List[float]] = Field(None, description="全文向量")

    # 检索评分
    quality_score: Optional[float] = Field(None, description="质量评分")
    retrieval_count: int = Field(default=0, description="被检索次数")

    indexed_at: datetime = Field(default_factory=datetime.utcnow, description="索引时间")

    class Config:
        use_enum_values = True

class RetrievalResult(BaseModel):
    """检索结果模型"""
    patent: PatentDocument = Field(..., description="专利文档")
    similarity_score: float = Field(..., description="相似度分数")
    relevance_score: float = Field(..., description="相关性分数")
    ranking_score: float = Field(..., description="排名分数")

    # 匹配详情
    matched_chunks: List[Dict[str, Any]] = Field(default_factory=list, description="匹配的分块")
    matched_fields: List[str] = Field(default_factory=list, description="匹配的字段")
    matched_keywords: List[str] = Field(default_factory=list, description="匹配的关键词")

    # 解释性
    explanation: Optional[str] = Field(None, description="匹配解释")
    confidence: float = Field(..., description="置信度")

    class Config:
        use_enum_values = True

class RAGQuery(BaseModel):
    """RAG查询请求"""
    query: str = Field(..., description="查询文本")
    query_type: str = Field(..., description="查询类型（审查、建议、分析等）")

    # 过滤条件
    ipc_classes: Optional[List[str]] = Field(None, description="IPC分类")
    cpc_classes: Optional[List[str]] = Field(None, description="CPC分类")
    date_from: Optional[datetime] = Field(None, description="开始日期")
    date_to: Optional[datetime] = Field(None, description="结束日期")
    sources: Optional[List[str]] = Field(None, description="数据来源")
    patent_types: Optional[List[str]] = Field(None, description="专利类型")

    # 检索参数
    top_k: int = Field(default=10, description="返回结果数")
    min_score: float = Field(default=0.6, description="最小分数阈值")
    enable_reranking: bool = Field(default=True, description="启用重排序")
    enable_query_expansion: bool = Field(default=True, description="启用查询扩展")
    return_explanations: bool = Field(default=True, description="返回解释")

    class Config:
        use_enum_values = True

class RAGResponse(BaseModel):
    """RAG查询响应"""
    query: str = Field(..., description="原始查询")
    results: List[RetrievalResult] = Field(..., description="检索结果")

    # 聚合信息
    summary: Optional[str] = Field(None, description="结果摘要")
    key_insights: List[str] = Field(default_factory=list, description="关键洞察")

    # 统计信息
    total_results: int = Field(..., description="总结果数")
    sources_used: List[str] = Field(default_factory=list, description="使用的数据源")
    query_time_ms: float = Field(..., description="查询耗时（毫秒）")

    # 质量指标
    avg_confidence: float = Field(..., description="平均置信度")
    recall_estimated: float = Field(..., description="预估召回率")

    class Config:
        use_enum_values = True
