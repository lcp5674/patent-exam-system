"""系统管理 API"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, text
from app.database.engine import get_db
from app.core.security import get_current_user, require_role
from app.database.models import PatentApplication, ExaminationRecord, AIModelUsage, AIProviderConfig
from app.schemas.common import AIProviderConfigSchema, AIProviderConfigUpdateSchema
from app.config import settings
import platform, os

router = APIRouter()

@router.get("/health", summary="系统健康检查")
async def health_check(db: AsyncSession = Depends(get_db)):
    db_ok = False
    try:
        await db.execute(text("SELECT 1"))
        db_ok = True
    except Exception:
        pass
    return {"code": 200, "data": {"status": "healthy" if db_ok else "degraded", "database": db_ok,
            "version": settings.app.APP_VERSION, "db_type": settings.db.db_type}}

@router.get("/info", summary="系统信息")
async def system_info(user=Depends(get_current_user)):
    return {"code": 200, "data": {
        "app_name": settings.app.APP_NAME, "version": settings.app.APP_VERSION,
        "environment": settings.app.APP_ENV, "database_type": settings.db.db_type,
        "python_version": platform.python_version(), "platform": platform.platform(),
    }}

@router.get("/metrics", summary="系统指标")
async def system_metrics(db: AsyncSession = Depends(get_db), user=Depends(get_current_user)):
    patent_count = (await db.execute(select(func.count()).select_from(PatentApplication))).scalar() or 0
    exam_count = (await db.execute(select(func.count()).select_from(ExaminationRecord))).scalar() or 0
    ai_count = (await db.execute(select(func.count()).select_from(AIModelUsage))).scalar() or 0
    return {"code": 200, "data": {"patent_count": patent_count, "examination_count": exam_count,
            "ai_usage_count": ai_count}}


# ─── AI 提供商配置管理（仅管理员可操作） ───────────────────────────────────────────────
@router.get("/ai-providers", summary="获取所有AI提供商配置", response_model=dict)
async def get_ai_providers(
    db: AsyncSession = Depends(get_db),
    current_user = Depends(require_role("admin"))
):
    """获取所有AI提供商配置，API密钥会脱敏显示"""
    result = await db.execute(select(AIProviderConfig).order_by(AIProviderConfig.priority.desc()))
    providers = result.scalars().all()
    
    # 脱敏API密钥，只显示前3位和后4位
    provider_list = []
    for provider in providers:
        provider_data = AIProviderConfigSchema.from_orm(provider).dict()
        if provider_data.get("api_key") and len(provider_data["api_key"]) > 7:
            provider_data["api_key"] = provider_data["api_key"][:3] + "*" * (len(provider_data["api_key"]) - 7) + provider_data["api_key"][-4:]
        provider_list.append(provider_data)
    
    return {"code": 200, "data": provider_list}


@router.get("/ai-providers/{provider_name}", summary="获取指定AI提供商配置", response_model=dict)
async def get_ai_provider(
    provider_name: str,
    db: AsyncSession = Depends(get_db),
    current_user = Depends(require_role("admin"))
):
    """获取指定AI提供商配置"""
    result = await db.execute(select(AIProviderConfig).where(AIProviderConfig.provider_name == provider_name))
    provider = result.scalar_one_or_none()
    
    if not provider:
        raise HTTPException(status_code=404, detail="AI提供商配置不存在")
    
    provider_data = AIProviderConfigSchema.from_orm(provider).dict()
    if provider_data.get("api_key") and len(provider_data["api_key"]) > 7:
        provider_data["api_key"] = provider_data["api_key"][:3] + "*" * (len(provider_data["api_key"]) - 7) + provider_data["api_key"][-4:]
    
    return {"code": 200, "data": provider_data}


@router.put("/ai-providers/{provider_name}", summary="更新AI提供商配置", response_model=dict)
async def update_ai_provider(
    provider_name: str,
    config_update: AIProviderConfigUpdateSchema,
    db: AsyncSession = Depends(get_db),
    current_user = Depends(require_role("admin"))
):
    """更新AI提供商配置，仅管理员可操作"""
    result = await db.execute(select(AIProviderConfig).where(AIProviderConfig.provider_name == provider_name))
    provider = result.scalar_one_or_none()
    
    if not provider:
        # 如果不存在则创建新配置
        provider = AIProviderConfig(provider_name=provider_name)
        db.add(provider)
    
    # 更新字段
    update_data = config_update.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(provider, field, value)
    
    # 如果设置为默认，取消其他所有的默认状态
    if provider.is_default:
        await db.execute(
            text("UPDATE ai_provider_configs SET is_default = false WHERE provider_name != :provider_name"),
            {"provider_name": provider_name}
        )
    
    await db.commit()
    await db.refresh(provider)
    
    # 返回脱敏后的数据
    provider_data = AIProviderConfigSchema.from_orm(provider).dict()
    if provider_data.get("api_key") and len(provider_data["api_key"]) > 7:
        provider_data["api_key"] = provider_data["api_key"][:3] + "*" * (len(provider_data["api_key"]) - 7) + provider_data["api_key"][-4:]
    
    return {"code": 200, "data": provider_data, "message": "配置更新成功"}


@router.post("/ai-providers/initialize", summary="初始化默认AI提供商配置", response_model=dict)
async def initialize_ai_providers(
    db: AsyncSession = Depends(get_db),
    current_user = Depends(require_role("admin"))
):
    """初始化系统默认支持的AI提供商配置"""
    default_providers = [
        {
            "provider_name": "doubao",
            "display_name": "豆包 (字节跳动)",
            "base_url": "https://ark.cn-beijing.volces.com/api/v3",
            "default_model": "doubao-seed-code",
            "is_enabled": True,
            "priority": 10
        },
        {
            "provider_name": "openai",
            "display_name": "OpenAI GPT",
            "base_url": "https://api.openai.com/v1",
            "default_model": "gpt-4",
            "is_enabled": False,
            "priority": 20
        },
        {
            "provider_name": "zhipu",
            "display_name": "智谱 AI",
            "base_url": "https://open.bigmodel.cn/api/paas/v4",
            "default_model": "glm-4",
            "is_enabled": False,
            "priority": 30
        },
        {
            "provider_name": "ollama",
            "display_name": "Ollama (本地模型)",
            "base_url": "http://localhost:11434",
            "default_model": "qwen2.5:7b",
            "is_enabled": False,
            "priority": 40
        }
    ]
    
    created_count = 0
    for provider_data in default_providers:
        result = await db.execute(
            select(AIProviderConfig).where(AIProviderConfig.provider_name == provider_data["provider_name"])
        )
        if not result.scalar_one_or_none():
            provider = AIProviderConfig(**provider_data)
            db.add(provider)
            created_count += 1
    
    await db.commit()
    return {"code": 200, "data": {"created_count": created_count}, "message": f"成功初始化 {created_count} 个AI提供商配置"}


# ─── 系统配置管理（仅管理员可操作） ───────────────────────────────────────────────
from pydantic import BaseModel
from typing import Optional, List
from app.database.models import SystemConfig

class SystemConfigSchema(BaseModel):
    id: int
    config_key: str
    config_value: Optional[str] = None
    config_type: Optional[str] = "string"
    category: Optional[str] = "general"
    description: Optional[str] = None
    is_sensitive: bool = False
    is_user_configurable: bool = False
    is_public: bool = False

    class Config:
        from_attributes = True

class SystemConfigCreateSchema(BaseModel):
    config_key: str
    config_value: Optional[str] = None
    config_type: Optional[str] = "string"
    category: Optional[str] = "general"
    description: Optional[str] = None
    is_sensitive: bool = False
    is_user_configurable: bool = False
    is_public: bool = False

class SystemConfigUpdateSchema(BaseModel):
    config_value: Optional[str] = None
    description: Optional[str] = None
    is_user_configurable: Optional[bool] = None
    is_public: Optional[bool] = None

@router.get("/configs", summary="获取所有系统配置")
async def get_system_configs(
    category: Optional[str] = None,
    include_sensitive: bool = False,
    db: AsyncSession = Depends(get_db),
    current_user = Depends(require_role("admin"))
):
    """获取所有系统配置（仅管理员），敏感配置默认不返回实际值"""
    query = select(SystemConfig).order_by(SystemConfig.category, SystemConfig.config_key)
    if category:
        query = query.where(SystemConfig.category == category)
    
    result = await db.execute(query)
    configs = result.scalars().all()
    
    config_list = []
    for config in configs:
        config_data = SystemConfigSchema.from_orm(config).model_dump()
        
        if config.is_sensitive and not include_sensitive:
            config_data["config_value"] = "***" if config.config_value else ""
        
        config_list.append(config_data)
    
    return {"code": 200, "data": config_list}

@router.get("/configs/categories", summary="获取配置分类")
async def get_config_categories(
    db: AsyncSession = Depends(get_db),
    current_user = Depends(require_role("admin"))
):
    """获取所有配置分类"""
    result = await db.execute(
        select(SystemConfig.category, func.count(SystemConfig.id).label("count"))
        .group_by(SystemConfig.category)
    )
    categories = [{"name": row[0] or "general", "count": row[1]} for row in result.all()]
    return {"code": 200, "data": categories}

@router.get("/configs/public", summary="获取公开配置")
async def get_public_configs(
    db: AsyncSession = Depends(get_db)
):
    """获取公开的系统配置（无需登录）"""
    result = await db.execute(
        select(SystemConfig).where(SystemConfig.is_public == True)
    )
    configs = result.scalars().all()
    
    config_dict = {c.config_key: c.config_value for c in configs}
    return {"code": 200, "data": config_dict}

@router.get("/configs/{config_key}", summary="获取单个配置")
async def get_system_config(
    config_key: str,
    include_value: bool = False,
    db: AsyncSession = Depends(get_db),
    current_user = Depends(require_role("admin"))
):
    """获取指定配置（管理员可查看敏感值）"""
    result = await db.execute(select(SystemConfig).where(SystemConfig.config_key == config_key))
    config = result.scalar_one_or_none()
    
    if not config:
        raise HTTPException(status_code=404, detail="配置不存在")
    
    config_data = SystemConfigSchema.from_orm(config).model_dump()
    
    if config.is_sensitive and not include_value:
        config_data["config_value"] = "***" if config.config_value else ""
    
    return {"code": 200, "data": config_data}

@router.post("/configs", summary="创建系统配置")
async def create_system_config(
    config_data: SystemConfigCreateSchema,
    db: AsyncSession = Depends(get_db),
    current_user = Depends(require_role("admin"))
):
    """创建新配置"""
    result = await db.execute(select(SystemConfig).where(SystemConfig.config_key == config_data.config_key))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="配置键已存在")
    
    config = SystemConfig(**config_data.model_dump())
    db.add(config)
    await db.commit()
    await db.refresh(config)
    
    return {"code": 200, "data": SystemConfigSchema.from_orm(config).model_dump(), "message": "配置创建成功"}

@router.put("/configs/{config_key}", summary="更新系统配置")
async def update_system_config(
    config_key: str,
    update_data: SystemConfigUpdateSchema,
    db: AsyncSession = Depends(get_db),
    current_user = Depends(require_role("admin"))
):
    """更新配置（管理员可更新敏感配置）"""
    result = await db.execute(select(SystemConfig).where(SystemConfig.config_key == config_key))
    config = result.scalar_one_or_none()
    
    if not config:
        raise HTTPException(status_code=404, detail="配置不存在")
    
    if config.is_sensitive and not current_user.role == "admin":
        raise HTTPException(status_code=403, detail="无权限更新敏感配置")
    
    update_dict = {k: v for k, v in update_data.model_dump().items() if v is not None}
    for field, value in update_dict.items():
        setattr(config, field, value)
    
    await db.commit()
    await db.refresh(config)
    
    result_data = SystemConfigSchema.from_orm(config).model_dump()
    if config.is_sensitive:
        result_data["config_value"] = "***" if config.config_value else ""
    
    return {"code": 200, "data": result_data, "message": "配置更新成功"}

@router.delete("/configs/{config_key}", summary="删除系统配置")
async def delete_system_config(
    config_key: str,
    db: AsyncSession = Depends(get_db),
    current_user = Depends(require_role("admin"))
):
    """删除配置"""
    result = await db.execute(select(SystemConfig).where(SystemConfig.config_key == config_key))
    config = result.scalar_one_or_none()
    
    if not config:
        raise HTTPException(status_code=404, detail="配置不存在")
    
    await db.delete(config)
    await db.commit()
    
    return {"code": 200, "message": "配置删除成功"}

@router.post("/configs/initialize", summary="初始化默认系统配置")
async def initialize_system_configs(
    db: AsyncSession = Depends(get_db),
    current_user = Depends(require_role("admin"))
):
    """初始化默认系统配置"""
    default_configs = [
        {"config_key": "admin_username", "config_value": "admin", "config_type": "string", "category": "security", "description": "管理员用户名", "is_sensitive": False, "is_user_configurable": True, "is_public": False},
        {"config_key": "default_password", "config_value": "admin123", "config_type": "string", "category": "security", "description": "默认密码", "is_sensitive": True, "is_user_configurable": False, "is_public": False},
        {"config_key": "jwt_secret_key", "config_value": "", "config_type": "string", "category": "security", "description": "JWT签名密钥", "is_sensitive": True, "is_user_configurable": False, "is_public": False},
        {"config_key": "aes_encryption_key", "config_value": "", "config_type": "string", "category": "security", "description": "AES加密密钥", "is_sensitive": True, "is_user_configurable": False, "is_public": False},
        {"config_key": "embedding_model", "config_value": "text-embedding-3-small", "config_type": "string", "category": "ai", "description": "嵌入模型", "is_sensitive": False, "is_user_configurable": True, "is_public": True},
        {"config_key": "embedding_dimension", "config_value": "1536", "config_type": "number", "category": "ai", "description": "嵌入向量维度", "is_sensitive": False, "is_user_configurable": True, "is_public": True},
        {"config_key": "embedding_api_key", "config_value": "", "config_type": "string", "category": "ai", "description": "嵌入模型API Key", "is_sensitive": True, "is_user_configurable": True, "is_public": False},
        {"config_key": "embedding_base_url", "config_value": "https://api.openai.com/v1", "config_type": "string", "category": "ai", "description": "嵌入API地址", "is_sensitive": False, "is_user_configurable": True, "is_public": True},
        {"config_key": "vector_db_type", "config_value": "chroma", "config_type": "string", "category": "database", "description": "向量数据库类型", "is_sensitive": False, "is_user_configurable": True, "is_public": True},
        {"config_key": "chroma_host", "config_value": "localhost", "config_type": "string", "category": "database", "description": "ChromaDB地址", "is_sensitive": False, "is_user_configurable": True, "is_public": True},
        {"config_key": "chroma_port", "config_value": "8000", "config_type": "number", "category": "database", "description": "ChromaDB端口", "is_sensitive": False, "is_user_configurable": True, "is_public": True},
        {"config_key": "milvus_host", "config_value": "localhost", "config_type": "string", "category": "database", "description": "Milvus地址", "is_sensitive": False, "is_user_configurable": True, "is_public": True},
        {"config_key": "milvus_port", "config_value": "19530", "config_type": "number", "category": "database", "description": "Milvus端口", "is_sensitive": False, "is_user_configurable": True, "is_public": True},
        {"config_key": "system_name", "config_value": "专利审查辅助系统", "config_type": "string", "category": "general", "description": "系统名称", "is_sensitive": False, "is_user_configurable": True, "is_public": True},
        {"config_key": "allow_registration", "config_value": "true", "config_type": "boolean", "category": "security", "description": "允许用户注册", "is_sensitive": False, "is_user_configurable": True, "is_public": True},
    ]
    
    created_count = 0
    for cfg in default_configs:
        result = await db.execute(select(SystemConfig).where(SystemConfig.config_key == cfg["config_key"]))
        if not result.scalar_one_or_none():
            config = SystemConfig(**cfg)
            db.add(config)
            created_count += 1
    
    await db.commit()
    return {"code": 200, "data": {"created_count": created_count}, "message": f"成功初始化 {created_count} 个系统配置"}
