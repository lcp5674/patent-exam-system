"""
数据库迁移脚本 - 添加 SearchHistory 表
运行此脚本将创建 search_history 表
"""
import asyncio
import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
# 添加项目根目录到 Python 路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import text
from app.database.engine import async_session_factory, engine


async def create_search_history_table():
    """创建搜索历史表"""
    async with engine.begin() as conn:
        # 检查表是否已存在
        result = await conn.execute(
            text("SELECT name FROM sqlite_master WHERE type='table' AND name='search_history'")
        )
        exists = result.fetchone()

        if exists:
            print("⚠️  SearchHistory 表已存在，跳过创建")
            return

        # 创建表
        create_sql = """
        CREATE TABLE search_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tenant_id INTEGER,
            user_id INTEGER,
            query TEXT NOT NULL,
            search_type VARCHAR(50) DEFAULT 'hybrid' NOT NULL,
            result_count INTEGER DEFAULT 0 NOT NULL,
            filters JSON,
            latency_ms REAL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
            FOREIGN KEY(user_id) REFERENCES users(id)
        );
        """

        # 创建索引
        create_indexes = [
            "CREATE INDEX idx_search_tenant ON search_history(tenant_id);",
            "CREATE INDEX idx_search_timestamp ON search_history(timestamp);"
        ]

        await conn.execute(text(create_sql))
        for idx_sql in create_indexes:
            await conn.execute(text(idx_sql))

        print("✓ SearchHistory 表创建成功")
        print("✓ 索引创建成功")


async def main():
    """主函数"""
    print("=" * 50)
    print("数据库迁移: 添加 SearchHistory 表")
    print("=" * 50)

    try:
        await create_search_history_table()
        print("\n✓ 迁移完成")
    except Exception as e:
        print(f"\n✗ 迁移失败: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
