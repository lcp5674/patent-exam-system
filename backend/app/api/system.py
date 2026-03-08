"""系统管理 API"""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, text
from app.database.engine import get_db
from app.core.security import get_current_user, require_role
from app.database.models import PatentApplication, ExaminationRecord, AIModelUsage
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
