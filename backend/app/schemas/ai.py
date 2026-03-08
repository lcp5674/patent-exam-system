"""AI 服务相关 Pydantic 模型"""
from __future__ import annotations
from typing import Optional
from pydantic import BaseModel, Field


class AIAnalyzeRequest(BaseModel):
    patent_id: int
    analysis_type: str = Field(..., description="分析类型: structure / novelty / inventiveness / practicality / claims / description / subject_matter / unity")
    provider: Optional[str] = None
    model: Optional[str] = None
    additional_context: Optional[str] = None


class AIChatRequest(BaseModel):
    message: str
    patent_id: Optional[int] = None
    provider: Optional[str] = None
    model: Optional[str] = None
    history: list[dict] = []


class AIResponse(BaseModel):
    content: str
    model: str
    provider: str
    tokens_used: Optional[int] = None
    confidence: Optional[float] = None
    analysis_type: Optional[str] = None
    structured_result: Optional[dict] = None


class AIProviderInfo(BaseModel):
    name: str
    display_name: str
    is_available: bool
    models: list[str] = []
    default_model: str = ""


class AIProviderConfigUpdate(BaseModel):
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    default_model: Optional[str] = None
    extra_config: Optional[dict] = None


class AIProviderConfigSchema(BaseModel):
    """AI 提供商配置 schema"""
    id: Optional[int] = None
    provider_name: str
    display_name: str
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    default_model: Optional[str] = None
    is_enabled: bool = True
    is_default: bool = False
    extra_config: Optional[dict] = None
    priority: int = 0

    model_config = {"from_attributes": True}


class AIProviderConfigCreate(BaseModel):
    """创建 AI 提供商配置"""
    provider_name: str
    display_name: str
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    default_model: Optional[str] = None
    is_enabled: bool = True
    is_default: bool = False
    extra_config: Optional[dict] = None
    priority: int = 0


class AIProviderConfigUpdateFull(BaseModel):
    """更新 AI 提供商配置"""
    display_name: Optional[str] = None
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    default_model: Optional[str] = None
    is_enabled: Optional[bool] = None
    is_default: Optional[bool] = None
    extra_config: Optional[dict] = None
    priority: Optional[int] = None


class AIUsageStats(BaseModel):
    total_requests: int = 0
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    avg_processing_time: float = 0.0
    success_rate: float = 0.0
    by_provider: dict = {}
    by_task_type: dict = {}
