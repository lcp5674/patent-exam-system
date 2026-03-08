"""
数据库迁移工具 - 自动建表
生产环境建议使用 Alembic 进行版本化迁移
"""
from .engine import engine, Base
from . import models  # noqa: F401 确保所有模型被导入


async def run_migrations():
    """在应用启动时执行自动迁移"""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("[DB] 数据库表初始化完成")
