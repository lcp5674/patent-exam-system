#!/usr/bin/env python3
"""数据库初始化脚本 - 创建表结构和默认数据"""

import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

async def main():
    from app.config import settings
    from app.database.engine import engine, async_session_factory, Base
    from app.database.models import User, ExaminationRule
    from app.core.security import get_password_hash

    print(f"[*] 数据库类型: {settings.db.db_type}")
    print(f"[*] 数据库URL: {settings.db.DATABASE_URL[:50]}...")

    # 确保目录存在
    settings.ensure_dirs()

    # 创建所有表
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("[+] 数据库表创建完成")

    # 创建默认管理员
    async with async_session_factory() as session:
        from sqlalchemy import select
        result = await session.execute(select(User).where(User.username == "admin"))
        admin = result.scalar_one_or_none()
        if not admin:
            admin = User(
                username="admin",
                password_hash=get_password_hash("admin123"),
                full_name="系统管理员",
                email="admin@patent-exam.local",
                role="admin",
                is_active=True,
            )
            session.add(admin)
            await session.commit()
            print("[+] 默认管理员创建成功 (admin/admin123)")
        else:
            print("[*] 管理员账户已存在")

    # 创建默认审查规则
    default_rules = [
        {"rule_name": "文档完整性检查", "rule_type": "formal", "rule_category": "level1",
         "description": "检查专利申请文件是否包含必要的组成部分", "priority": 100,
         "legal_basis": "专利法实施细则第17条"},
        {"rule_name": "格式规范性检查", "rule_type": "formal", "rule_category": "level1",
         "description": "检查文档格式是否符合专利局要求", "priority": 90,
         "legal_basis": "专利审查指南第一部分第一章"},
        {"rule_name": "权利要求书格式检查", "rule_type": "formal", "rule_category": "level1",
         "description": "检查权利要求书的撰写格式是否规范", "priority": 95,
         "legal_basis": "专利法实施细则第19-22条"},
        {"rule_name": "说明书章节完整性", "rule_type": "formal", "rule_category": "level1",
         "description": "检查说明书是否包含所有必要的章节", "priority": 85,
         "legal_basis": "专利法实施细则第17条"},
        {"rule_name": "附图要求检查", "rule_type": "formal", "rule_category": "level1",
         "description": "检查实用新型专利是否包含必要的附图", "priority": 80,
         "legal_basis": "专利法第27条"},
        {"rule_name": "客体适格性审查", "rule_type": "substantive", "rule_category": "level2",
         "description": "检查申请是否属于实用新型专利保护的客体", "priority": 100,
         "legal_basis": "专利法第2条第3款"},
        {"rule_name": "权利要求清晰性", "rule_type": "substantive", "rule_category": "level2",
         "description": "检查权利要求是否清楚、简明", "priority": 90,
         "legal_basis": "专利法第26条第4款"},
        {"rule_name": "权利要求支持性", "rule_type": "substantive", "rule_category": "level2",
         "description": "检查权利要求是否得到说明书的支持", "priority": 85,
         "legal_basis": "专利法第26条第4款"},
        {"rule_name": "说明书充分公开", "rule_type": "substantive", "rule_category": "level2",
         "description": "检查说明书是否充分公开了技术方案", "priority": 80,
         "legal_basis": "专利法第26条第3款"},
        {"rule_name": "单一性审查", "rule_type": "substantive", "rule_category": "level2",
         "description": "检查多项权利要求是否属于一个总的发明构思", "priority": 70,
         "legal_basis": "专利法第31条第1款"},
    ]

    async with async_session_factory() as session:
        from sqlalchemy import select
        result = await session.execute(select(ExaminationRule))
        existing = result.scalars().all()
        existing_names = {r.rule_name for r in existing}
        added = 0
        for rule_data in default_rules:
            if rule_data["rule_name"] not in existing_names:
                rule = ExaminationRule(**rule_data, is_active=True)
                session.add(rule)
                added += 1
        if added > 0:
            await session.commit()
        print(f"[+] 审查规则初始化完成 (新增 {added} 条，已有 {len(existing_names)} 条)")

    await engine.dispose()
    print("[+] 数据库初始化完成!")

if __name__ == "__main__":
    asyncio.run(main())
