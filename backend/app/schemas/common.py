"""通用 Schema"""
from pydantic import BaseModel, Field
from typing import Optional, Generic, TypeVar, Dict, Any

T = TypeVar('T')

class PaginatedResponse(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int
    page_size: int
    total_pages: int


class DeleteResponse(BaseModel):
    id: int
    deleted: bool = True


class StatusResponse(BaseModel):
    status: str
    message: Optional[str] = None


class AIProviderConfigSchema(BaseModel):
    """AI提供商配置Schema"""
    id: Optional[int] = None
    provider_name: str = Field(..., description="提供商标识，如 doubao, openai")
    display_name: str = Field(..., description="显示名称，如 豆包, OpenAI")
    api_key: Optional[str] = Field(None, description="API密钥，返回时会脱敏")
    base_url: Optional[str] = Field(None, description="API基础地址")
    default_model: Optional[str] = Field(None, description="默认模型")
    is_enabled: bool = Field(True, description="是否启用")
    is_default: bool = Field(False, description="是否为默认提供商")
    extra_config: Optional[Dict[str, Any]] = Field(None, description="额外配置")
    priority: int = Field(0, description="优先级")

    class Config:
        from_attributes = True


class AIProviderConfigUpdateSchema(BaseModel):
    """AI提供商配置更新Schema"""
    display_name: Optional[str] = None
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    default_model: Optional[str] = None
    is_enabled: Optional[bool] = None
    is_default: Optional[bool] = None
    extra_config: Optional[Dict[str, Any]] = None
    priority: Optional[int] = None
