"""
专利审查辅助系统 - FastAPI 主应用
Patent Examination Assistant System
"""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import socket
from app.config import settings
from app.database.engine import init_db, close_db
from app.database.migrations import run_migrations
from app.core.logging_config import setup_logging
from app.core.middleware import RequestLoggingMiddleware, ErrorHandlerMiddleware, RateLimitMiddleware, SecurityHeadersMiddleware
from app.api.router import api_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── 启动 ──
    setup_logging()
    settings.ensure_dirs()
    
    # 数据库迁移
    try:
        await run_migrations()
    except Exception as e:
        print(f"[警告] 数据库迁移失败: {e}")
    
    # 初始化 AI 提供商 (不阻塞启动)
    try:
        from app.ai.provider_manager import provider_manager
        await provider_manager.initialize()
    except socket.gaierror as e:
        print(f"[警告] AI提供商初始化失败 (DNS错误): {e}")
    except Exception as e:
        print(f"[警告] AI提供商初始化失败: {e}")
    
    # 从数据库加载 AI 配置
    try:
        from app.database.engine import async_session_factory
        async with async_session_factory() as db:
            await provider_manager.load_db_configs(db)
    except socket.gaierror as e:
        print(f"[警告] 加载AI配置失败 (DNS错误): {e}")
    except Exception as e:
        print(f"[警告] 加载AI配置失败: {e}")
    
    # 初始化预置专利审查规则
    try:
        from app.database.engine import async_session_factory
        async with async_session_factory() as db:
            from app.services.init_rules import init_patent_rules
            await init_patent_rules(db)
    except socket.gaierror as e:
        print(f"[警告] 初始化规则失败 (DNS错误): {e}")
    except Exception as e:
        print(f"[警告] 初始化规则失败: {e}")
    
    # 初始化默认管理员
    try:
        await _ensure_default_admin()
    except socket.gaierror as e:
        print(f"[警告] 初始化管理员失败 (DNS错误): {e}")
    except Exception as e:
        print(f"[警告] 初始化管理员失败: {e}")
    
    print(f"[启动] {settings.app.APP_NAME} v{settings.app.APP_VERSION} 已就绪")
    print(f"[数据库] 类型: {settings.db.db_type}")
    yield
    # ── 关闭 ──
    await close_db()
    print("[关闭] 系统已停止")


app = FastAPI(
    title=settings.app.APP_NAME,
    description="基于AI的实用新型专利审查辅助系统，支持文档解析、规则引擎、AI审查建议、报告生成等功能。",
    version=settings.app.APP_VERSION,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    redirect_slashes=False,
)

# 中间件
# CORS 配置
cors_origins = settings.app.CORS_ORIGINS
if isinstance(cors_origins, str):
    cors_origins = [o.strip() for o in cors_origins.split(",")]
    # 移除引号
    cors_origins = [o.strip("\"'") for o in cors_origins]

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(RateLimitMiddleware, requests_per_minute=60)
app.add_middleware(RequestLoggingMiddleware)
app.add_middleware(ErrorHandlerMiddleware)

# 初始化监控服务
from app.core.monitoring import monitoring
monitoring.initialize()

# 路由
app.include_router(api_router)


@app.get("/", tags=["根路径"])
async def root():
    return {"name": settings.app.APP_NAME, "version": settings.app.APP_VERSION, "docs": "/docs"}


@app.get("/metrics", tags=["监控"])
async def metrics():
    """Prometheus指标端点"""
    from app.core.monitoring import monitoring
    from fastapi import Response
    return Response(
        content=monitoring.get_metrics(),
        media_type=monitoring.get_metrics_content_type()
    )


@app.get("/health", tags=["监控"])
async def health_check():
    """健康检查端点"""
    from app.core.monitoring import monitoring
    status = monitoring.get_status()
    from app.core.cache import cache
    try:
        status["redis_connected"] = await cache.ping()
    except Exception as e:
        status["redis_connected"] = False
        status["redis_error"] = str(e)
    return status


async def _ensure_default_admin():
    """确保存在默认管理员账户"""
    import os
    from app.database.engine import async_session_factory
    from app.database.models import User
    from app.core.security import get_password_hash
    from sqlalchemy import select
    
    default_username = os.getenv("ADMIN_USERNAME", "admin")
    default_password = os.getenv("ADMIN_PASSWORD", "admin123")
    
    async with async_session_factory() as db:
        result = await db.execute(select(User).where(User.username == default_username))
        if result.scalar_one_or_none() is None:
            admin = User(username=default_username, password_hash=get_password_hash(default_password),
                        role="admin", full_name="系统管理员", email="admin@patent-exam.local")
            db.add(admin)
            await db.commit()
            print(f"[初始化] 已创建默认管理员账户 ({default_username}/{default_password})")
            print("[警告] 首次登录后请立即修改默认密码！")
