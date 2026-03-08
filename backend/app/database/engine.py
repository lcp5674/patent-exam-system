"""
数据库引擎 - 支持 MySQL / PostgreSQL / SQLite
通过 DATABASE_URL 环境变量自动检测数据库类型并配置连接参数
"""
from __future__ import annotations
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.pool import StaticPool, NullPool
from app.config import settings


def _build_engine_kwargs() -> dict:
    """根据数据库类型构建引擎参数"""
    url = settings.db.DATABASE_URL
    db_type = settings.db.db_type
    kwargs: dict = {"echo": settings.db.DB_ECHO}

    if db_type == "sqlite":
        # SQLite 使用 StaticPool 保证异步安全
        kwargs.update({
            "connect_args": {"check_same_thread": False},
            "poolclass": StaticPool,
        })
    elif db_type == "postgresql":
        kwargs.update({
            "pool_size": settings.db.DB_POOL_SIZE,
            "max_overflow": settings.db.DB_MAX_OVERFLOW,
            "pool_recycle": settings.db.DB_POOL_RECYCLE,
            "pool_pre_ping": True,
        })
    elif db_type == "mysql":
        kwargs.update({
            "pool_size": settings.db.DB_POOL_SIZE,
            "max_overflow": settings.db.DB_MAX_OVERFLOW,
            "pool_recycle": settings.db.DB_POOL_RECYCLE,
            "pool_pre_ping": True,
        })
    return kwargs


engine = create_async_engine(settings.db.DATABASE_URL, **_build_engine_kwargs())

async_session_factory = async_sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI 依赖注入 - 获取数据库会话"""
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db():
    """初始化数据库 - 创建所有表"""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def close_db():
    """关闭数据库连接"""
    await engine.dispose()
