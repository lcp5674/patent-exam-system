"""
测试配置和fixtures
"""
import sys
import os
import pytest
from pathlib import Path

# 添加应用到路径
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

# 设置测试环境变量
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("DEBUG", "true")
os.environ.setdefault("LOG_LEVEL", "ERROR")


@pytest.fixture(scope="session")
def test_db_url():
    """使用内存SQLite作为测试数据库"""
    return "sqlite+aiosqlite:///:memory:"


@pytest.fixture
async def test_db_engine(test_db_url):
    """创建测试数据库引擎"""
    from sqlalchemy.ext.asyncio import create_async_engine
    from sqlalchemy.orm import sessionmaker
    from app.database.engine import Base

    engine = create_async_engine(
        test_db_url,
        echo=False,
        connect_args={"check_same_thread": False}
    )

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await engine.dispose()


@pytest.fixture
async def test_db_session(test_db_engine):
    """创建测试数据库会话"""
    from sqlalchemy.ext.asyncio import AsyncSession

    async_session_factory = sessionmaker(
        test_db_engine, class_=AsyncSession, expire_on_commit=False
    )

    async with async_session_factory() as session:
        yield session


@pytest.fixture
def sample_user_data():
    """示例用户数据"""
    return {
        "username": "test_user",
        "password": "Test123456!",
        "email": "test@example.com",
        "full_name": "测试用户",
        "role": "examiner"
    }


@pytest.fixture
def sample_patent_data():
    """示例专利申请数据"""
    return {
        "application_number": "2024100100001",
        "title": "一种基于人工智能的专利审查方法",
        "applicant": "测试有限公司",
        "inventor": "张三",
        "agent": "李四",
        "technical_field": "人工智能",
        "abstract": "本发明公开了一种基于人工智能的专利审查方法，通过自然语言处理技术对专利文献进行自动分析。",
        "ipc_classification": "G06F21/00"
    }


@pytest.fixture
def sample_rule_data():
    """示例审查规则数据"""
    return {
        "rule_name": "发明名称长度检查",
        "rule_type": "formal",
        "rule_category": "level1",
        "rule_content": {
            "type": "string_length",
            "min_length": 5,
            "max_length": 50,
            "field": "title"
        },
        "check_pattern": "length",
        "severity": "error",
        "is_active": True,
        "priority": 10,
        "legal_basis": "专利法第26条第1款"
    }