"""
数据库模型定义 - 兼容 MySQL / PostgreSQL / SQLite
所有模型使用方言无关的 SQLAlchemy 类型
"""
from __future__ import annotations
import datetime
from typing import Optional
from sqlalchemy import (
    String, Integer, Float, Boolean, Text, DateTime, Date,
    ForeignKey, Index, JSON, LargeBinary, func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .engine import Base


# ─── 租户表 ───────────────────────────────────────────────
class Tenant(Base):
    __tablename__ = "tenants"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    max_users: Mapped[int] = mapped_column(Integer, default=10)
    max_patents: Mapped[int] = mapped_column(Integer, default=1000)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())


# ─── 用户表 ───────────────────────────────────────────────
class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("tenants.id"), nullable=True, index=True)
    username: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(50), default="examiner")  # admin / examiner / viewer
    email: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    full_name: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    department: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    tenant: Mapped[Optional[Tenant]] = relationship("Tenant", foreign_keys=[tenant_id])


# ─── 专利申请表 ───────────────────────────────────────────
class PatentApplication(Base):
    __tablename__ = "patent_applications"
    __table_args__ = (
        Index("idx_patent_status", "status"),
        Index("idx_patent_app_date", "application_date"),
        Index("idx_patent_ipc", "ipc_classification"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    # 注意: 不使用外键约束，因为tenant表可能为空，由应用层处理tenant逻辑
    tenant_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, index=True)
    application_number: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    application_date: Mapped[Optional[datetime.date]] = mapped_column(Date, nullable=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    applicant: Mapped[str] = mapped_column(String(500), nullable=False)
    inventor: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    agent: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="pending")  # pending/examining/granted/rejected
    priority_date: Mapped[Optional[datetime.date]] = mapped_column(Date, nullable=True)
    priority_number: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    ipc_classification: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    file_path: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    abstract: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    technical_field: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    parsed_content: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)  # 解析后的文档结构
    created_by: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    # 关联
    examination_records: Mapped[list["ExaminationRecord"]] = relationship(back_populates="application", cascade="all, delete-orphan")
    opinions: Mapped[list["ExaminationOpinion"]] = relationship(back_populates="application", cascade="all, delete-orphan")
    dna_fingerprint: Mapped[Optional["PatentDNAFingerprint"]] = relationship(back_populates="application", uselist=False)


# ─── 审查记录表 ───────────────────────────────────────────
class ExaminationRecord(Base):
    __tablename__ = "examination_records"
    __table_args__ = (
        Index("idx_exam_app_id", "application_id"),
        Index("idx_exam_status", "status"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    application_id: Mapped[int] = mapped_column(Integer, ForeignKey("patent_applications.id"), nullable=False)
    examiner_id: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    examination_type: Mapped[str] = mapped_column(String(50), nullable=False)  # formal / substantive
    examination_step: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="pending")  # pending / running / completed / failed
    result: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    confidence_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    ai_model_used: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    start_time: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, nullable=True)
    end_time: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, server_default=func.now())

    application: Mapped["PatentApplication"] = relationship(back_populates="examination_records")


# ─── 审查规则表 ───────────────────────────────────────────
class ExaminationRule(Base):
    __tablename__ = "examination_rules"
    __table_args__ = (
        Index("idx_rule_type", "rule_type"),
        Index("idx_rule_active", "is_active"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    rule_name: Mapped[str] = mapped_column(String(200), nullable=False)
    rule_type: Mapped[str] = mapped_column(String(50), nullable=False)  # formal / novelty / inventiveness / practicality
    rule_category: Mapped[str] = mapped_column(String(50), default="level1")  # level1 / level2 / level3
    rule_content: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    priority: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    version: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    legal_basis: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    
    # 新增丰富字段
    severity: Mapped[str] = mapped_column(String(20), default="warning")  # error/warning/info
    check_pattern: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)  # regex/keyword/ai/structural
    target_fields: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)  # 目标字段列表
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # 错误消息模板
    fix_suggestion: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # 修复建议
    ai_model: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)  # 使用的AI模型
    examples: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)  # 示例
    tags: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)  # 标签
    created_by: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id"), nullable=True)
    last_executed_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, nullable=True)
    execution_count: Mapped[int] = mapped_column(Integer, default=0)
    success_rate: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    avg_execution_time: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())


# ─── 对比文件表 ───────────────────────────────────────────
class PriorArtDocument(Base):
    __tablename__ = "prior_art_documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    document_number: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    publication_date: Mapped[Optional[datetime.date]] = mapped_column(Date, nullable=True)
    title: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    abstract: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    applicant: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    ipc_classification: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    document_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)  # patent / publication / standard
    source: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    file_path: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    relevance_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, server_default=func.now())


# ─── 审查意见表 ───────────────────────────────────────────
class ExaminationOpinion(Base):
    __tablename__ = "examination_opinions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    application_id: Mapped[int] = mapped_column(Integer, ForeignKey("patent_applications.id"), nullable=False)
    examination_record_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("examination_records.id"), nullable=True)
    opinion_type: Mapped[str] = mapped_column(String(50), nullable=False)  # notice / grant / rejection
    content: Mapped[str] = mapped_column(Text, nullable=False)
    legal_basis: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    prior_art_references: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    template_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="draft")  # draft / finalized / sent
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_by: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    application: Mapped["PatentApplication"] = relationship(back_populates="opinions")


# ─── 文档模板表 ───────────────────────────────────────────
class DocumentTemplate(Base):
    __tablename__ = "document_templates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    template_name: Mapped[str] = mapped_column(String(200), nullable=False)
    template_type: Mapped[str] = mapped_column(String(50), nullable=False)  # opinion_notice / grant_notice / rejection
    content: Mapped[str] = mapped_column(Text, nullable=False)
    variables: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)  # 模板变量定义
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())


# ─── 操作日志表 ───────────────────────────────────────────
class OperationLog(Base):
    __tablename__ = "operation_logs"
    __table_args__ = (
        Index("idx_log_user", "user_id"),
        Index("idx_log_type", "operation_type"),
        Index("idx_log_time", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    operation_type: Mapped[str] = mapped_column(String(100), nullable=False)
    operation_target: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    operation_details: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    ip_address: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)
    result: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    execution_time: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # 毫秒
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, server_default=func.now())

    @staticmethod
    async def log(
        db: "AsyncSession",
        user_id: int = None,
        operation_type: str = "",
        operation_target: str = None,
        operation_details: dict = None,
        ip_address: str = None,
        result: str = "success",
        error_message: str = None,
        execution_time: int = None
    ):
        """记录操作日志"""
        log_entry = OperationLog(
            user_id=user_id,
            operation_type=operation_type,
            operation_target=operation_target,
            operation_details=operation_details,
            ip_address=ip_address,
            result=result,
            error_message=error_message,
            execution_time=execution_time
        )
        db.add(log_entry)
        await db.flush()
        return log_entry


# ─── AI 模型使用记录表 ────────────────────────────────────
class AIModelUsage(Base):
    __tablename__ = "ai_model_usage"
    __table_args__ = (
        Index("idx_ai_model", "model_name"),
        Index("idx_ai_provider", "provider"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    model_name: Mapped[str] = mapped_column(String(100), nullable=False)
    model_version: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    provider: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    task_type: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    input_tokens: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    output_tokens: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    processing_time: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # 毫秒
    success: Mapped[bool] = mapped_column(Boolean, default=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, server_default=func.now())


# ─── AI 提供商配置表 (支持前端配置) ─────────────────────────
class AIProviderConfig(Base):
    __tablename__ = "ai_provider_configs"
    __table_args__ = (
        Index("idx_provider_name", "provider_name"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    provider_name: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    display_name: Mapped[str] = mapped_column(String(100), nullable=False)
    api_key: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    base_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    default_model: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    extra_config: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    priority: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())


# ─── 系统配置表 ───────────────────────────────────────────
class SystemConfig(Base):
    __tablename__ = "system_config"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    config_key: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    config_value: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    config_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    category: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_sensitive: Mapped[bool] = mapped_column(Boolean, default=False)
    is_user_configurable: Mapped[bool] = mapped_column(Boolean, default=False)
    is_public: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())


# ─── 自定义Embedding模型配置表 ─────────────────────────────
class CustomEmbeddingModelConfig(Base):
    __tablename__ = "custom_embedding_model_configs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    model_name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    provider: Mapped[str] = mapped_column(String(50), nullable=False)  # custom, openai, huggingface, zhipu, ollama
    api_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    api_key: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    dimension: Mapped[Optional[int]] = mapped_column(Integer, default=1536)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())


# ─── 自定义Reranker模型配置表 ───────────────────────────
class CustomRerankerModelConfig(Base):
    __tablename__ = "custom_reranker_model_configs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    model_name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    provider: Mapped[str] = mapped_column(String(50), nullable=False)  # custom, openai, cohere, huggingface
    api_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    api_key: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())


# ─── 专利数据源API配置表 ──────────────────────────────
class PatentSourceConfig(Base):
    __tablename__ = "patent_source_configs"
    __table_args__ = (
        Index("idx_source_active", "is_enabled"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    # 注意: 不使用外键约束，因为tenant表可能为空，由应用层处理tenant逻辑
    tenant_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, index=True)
    source_name: Mapped[str] = mapped_column(String(100), nullable=False)  # baiten, dawei, uspto, lens, cnipa, etc.
    source_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)  # cnipa/uspto/wo/enterprise
    base_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    api_key: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    app_id: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)  # For Baiten
    api_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)  # Custom API URL if needed
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    crawl_interval_hours: Mapped[int] = mapped_column(Integer, default=24)
    last_crawl_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, nullable=True)
    config_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    created_by: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    user: Mapped[Optional["User"]] = relationship("User")


# ─── RAG文件管理表 ─────────────────────────────────────
class RagDocument(Base):
    __tablename__ = "rag_documents"
    __table_args__ = (
        Index("idx_rag_doc_tenant", "tenant_id"),
        Index("idx_rag_doc_status", "status"),
    )
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    # 注意: 不使用外键约束，因为tenant表可能为空，由应用层处理tenant逻辑
    tenant_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, index=True)
    file_name: Mapped[str] = mapped_column(String(500), nullable=False)
    file_type: Mapped[str] = mapped_column(String(50), nullable=False)  # pdf, docx, txt, etc.
    file_size: Mapped[int] = mapped_column(Integer, nullable=False)  # bytes
    file_path: Mapped[str] = mapped_column(String(1000), nullable=False)  # 存储路径
    extracted_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # 提取的文本内容
    chunk_count: Mapped[int] = mapped_column(Integer, default=0)  # 分块数量
    indexed_count: Mapped[int] = mapped_column(Integer, default=0)  # 成功索引数量
    status: Mapped[str] = mapped_column(String(50), default="pending")  # pending, indexing, completed, failed
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    indexed_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, nullable=True)
    created_by: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())


# ─── 专利 DNA 指纹表 (技术壁垒核心) ─────────────────────
class PatentDNAFingerprint(Base):
    __tablename__ = "patent_dna_fingerprints"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    application_id: Mapped[int] = mapped_column(Integer, ForeignKey("patent_applications.id"), unique=True, nullable=False)
    fingerprint_vector: Mapped[Optional[bytes]] = mapped_column(LargeBinary, nullable=True)  # numpy 序列化向量
    structural_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    claim_features: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    technical_keywords: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    similarity_index: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    innovation_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    version: Mapped[str] = mapped_column(String(20), default="1.0")
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, server_default=func.now())

    application: Mapped["PatentApplication"] = relationship(back_populates="dna_fingerprint")


# ═══════════════════════════════════════════════════════════════════
# 工作流引擎模型
# ═══════════════════════════════════════════════════════════════════

class WorkflowDefinition(Base):
    """工作流定义"""
    __tablename__ = "workflow_definitions"
    __table_args__ = (
        Index("idx_workflow_tenant", "tenant_id"),
        Index("idx_workflow_type", "workflow_type"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    # 注意: 不使用外键约束，因为tenant表可能为空，由应用层处理tenant逻辑
    tenant_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    workflow_type: Mapped[str] = mapped_column(String(50), nullable=False)  # patent_examination / document_review / general
    version: Mapped[str] = mapped_column(String(20), default="1.0")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    
    # 工作流配置 (JSON)
    stages: Mapped[Optional[dict]] = mapped_column(JSON, nullable=False)  # 工作流阶段定义
    transitions: Mapped[Optional[dict]] = mapped_column(JSON, nullable=False)  # 状态转换规则
    assignments: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)  # 角色分配规则
    timeout_config: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)  # 超时配置
    
    # 审批规则
    approval_rules: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)  # 多级审批规则
    auto_approve_conditions: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)  # 自动审批条件
    
    created_by: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())


class WorkflowInstance(Base):
    """工作流实例"""
    __tablename__ = "workflow_instances"
    __table_args__ = (
        Index("idx_instance_workflow", "workflow_definition_id"),
        Index("idx_instance_entity", "entity_type", "entity_id"),
        Index("idx_instance_status", "status"),
        Index("idx_instance_assignee", "current_assignee_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    # 注意: 不使用外键约束，因为tenant表可能为空，由应用层处理tenant逻辑
    tenant_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, index=True)
    workflow_definition_id: Mapped[int] = mapped_column(Integer, ForeignKey("workflow_definitions.id"), nullable=False)
    
    # 关联实体 (专利申请/文档等)
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False)  # patent_application / document / general
    entity_id: Mapped[int] = mapped_column(Integer, nullable=False)
    
    # 流程状态
    status: Mapped[str] = mapped_column(String(50), default="pending")  # pending / in_progress / completed / cancelled / paused
    current_stage: Mapped[str] = mapped_column(String(100), nullable=False)
    current_assignee_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id"), nullable=True)
    
    # 进度追踪
    completed_stages: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)  # 已完成阶段
    stage_history: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)  # 阶段历史
    
    # 业务数据
    context_data: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)  # 上下文数据
    workflow_metadata: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)  # 额外元数据
    
    # 时间戳
    started_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, nullable=True)
    due_date: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, nullable=True)
    created_by: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    # 关联
    definition: Mapped[Optional[WorkflowDefinition]] = relationship("WorkflowDefinition")
    tasks: Mapped[list["WorkflowTask"]] = relationship(back_populates="instance", cascade="all, delete-orphan")


class WorkflowTask(Base):
    """工作流任务"""
    __tablename__ = "workflow_tasks"
    __table_args__ = (
        Index("idx_task_instance", "instance_id"),
        Index("idx_task_assignee", "assignee_id"),
        Index("idx_task_status", "status"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    instance_id: Mapped[int] = mapped_column(Integer, ForeignKey("workflow_instances.id"), nullable=False)
    # 注意: 不使用外键约束，因为tenant表可能为空，由应用层处理tenant逻辑
    tenant_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, index=True)
    
    # 任务信息
    task_type: Mapped[str] = mapped_column(String(50), nullable=False)  # review / approval / verification / submission
    task_name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # 分配信息
    assignee_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id"), nullable=True)
    assignee_role: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    
    # 任务状态
    status: Mapped[str] = mapped_column(String(50), default="pending")  # pending / in_progress / completed / rejected / cancelled
    priority: Mapped[str] = mapped_column(String(20), default="normal")  # low / normal / high / urgent
    
    # 审批信息
    approval_level: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # 审批层级
    is_approval_task: Mapped[bool] = mapped_column(Boolean, default=False)
    approval_result: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)  # approved / rejected
    approval_comment: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # 时间戳
    due_date: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, nullable=True)
    started_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    # 关联
    instance: Mapped["WorkflowInstance"] = relationship("WorkflowInstance", back_populates="tasks")


class ApprovalRecord(Base):
    """审批记录"""
    __tablename__ = "approval_records"
    __table_args__ = (
        Index("idx_approval_instance", "instance_id"),
        Index("idx_approval_approver", "approver_id"),
        Index("idx_approval_level", "approval_level"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    # 注意: 不使用外键约束，因为tenant表可能为空，由应用层处理tenant逻辑
    tenant_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, index=True)
    instance_id: Mapped[int] = mapped_column(Integer, ForeignKey("workflow_instances.id"), nullable=False)
    task_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("workflow_tasks.id"), nullable=True)
    
    # 审批信息
    approval_level: Mapped[int] = mapped_column(Integer, nullable=False)
    approver_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    approver_name: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    
    # 审批结果
    decision: Mapped[str] = mapped_column(String(50), nullable=False)  # approved / rejected / abstained
    comment: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    attachments: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)  # 附件
    
    # 时间戳
    decided_at: Mapped[datetime.datetime] = mapped_column(DateTime, server_default=func.now())
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, server_default=func.now())



# ─── 搜索历史表 ───────────────────────────────────────
class SearchHistory(Base):
    """RAG搜索历史记录"""
    __tablename__ = "search_history"
    __table_args__ = (
        Index("idx_search_tenant", "tenant_id"),
        Index("idx_search_timestamp", "timestamp"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    # 注意: 不使用外键约束，因为tenant表可能为空，由应用层处理tenant逻辑
    tenant_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, index=True)
    user_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id"), nullable=True)
    query: Mapped[str] = mapped_column(Text, nullable=False)
    search_type: Mapped[str] = mapped_column(String(50), default="hybrid")  # semantic/keyword/hybrid
    result_count: Mapped[int] = mapped_column(Integer, default=0)
    filters: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)  # 搜索过滤条件
    latency_ms: Mapped[Optional[float]] = mapped_column(Float, nullable=True)  # 搜索耗时
    timestamp: Mapped[datetime.datetime] = mapped_column(DateTime, server_default=func.now())
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, server_default=func.now())

    user: Mapped[Optional["User"]] = relationship("User")




# ─── 专利爬取任务表 ───────────────────────────────────────
class CrawlTask(Base):
    """专利数据爬取任务"""
    __tablename__ = "crawl_tasks"
    __table_args__ = (
        Index("idx_crawl_status", "status"),
        Index("idx_crawl_created", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, index=True)
    task_name: Mapped[str] = mapped_column(String(200), nullable=False)
    task_type: Mapped[str] = mapped_column(String(50), nullable=False)  # full/incremental/multi_source
    status: Mapped[str] = mapped_column(String(50), default="pending")  # pending/running/completed/failed
    source_config_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    total_patents: Mapped[int] = mapped_column(Integer, default=0)
    processed_patents: Mapped[int] = mapped_column(Integer, default=0)
    failed_patents: Mapped[int] = mapped_column(Integer, default=0)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    started_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, nullable=True)
    created_by: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())
