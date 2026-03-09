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
