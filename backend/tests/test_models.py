"""
数据库模型单元测试
"""
import pytest
from datetime import date, datetime
from sqlalchemy import select

from app.database.models import (
    User, Tenant, PatentApplication, ExaminationRule,
    ExaminationRecord, WorkflowDefinition, WorkflowInstance,
    WorkflowTask
)


@pytest.mark.unit
class TestUserModel:
    """用户模型测试"""

    @pytest.mark.asyncio
    async def test_create_user(self, test_db_session):
        """测试创建用户"""
        from app.core.security import get_password_hash

        user = User(
            username="testuser",
            password_hash=get_password_hash("password123"),
            role="examiner",
            email="test@example.com",
            full_name="测试用户"
        )
        test_db_session.add(user)
        await test_db_session.commit()

        # 验证创建成功
        result = await test_db_session.execute(
            select(User).where(User.username == "testuser")
        )
        db_user = result.scalar_one_or_none()

        assert db_user is not None
        assert db_user.username == "testuser"
        assert db_user.role == "examiner"
        assert db_user.is_active is True

    @pytest.mark.asyncio
    async def test_user_default_role(self, test_db_session):
        """测试用户默认角色"""
        from app.core.security import get_password_hash

        user = User(
            username="default_role_user",
            password_hash=get_password_hash("password123")
        )
        test_db_session.add(user)
        await test_db_session.commit()

        assert user.role == "examiner"


@pytest.mark.unit
class TestTenantModel:
    """租户模型测试"""

    @pytest.mark.asyncio
    async def test_create_tenant(self, test_db_session):
        """测试创建租户"""
        tenant = Tenant(
            name="测试租户",
            code="TEST001",
            description="测试用租户",
            max_users=100,
            max_patents=10000,
            is_active=True
        )
        test_db_session.add(tenant)
        await test_db_session.commit()

        result = await test_db_session.execute(
            select(Tenant).where(Tenant.code == "TEST001")
        )
        db_tenant = result.scalar_one_or_none()

        assert db_tenant is not None
        assert db_tenant.name == "测试租户"
        assert db_tenant.max_users == 100


@pytest.mark.unit
class TestPatentApplicationModel:
    """专利申请模型测试"""

    @pytest.mark.asyncio
    async def test_create_patent_application(self, test_db_session):
        """测试创建专利申请"""
        patent = PatentApplication(
            application_number="202410011234500001",
            title="测试专利",
            applicant="测试公司",
            inventor="张三",
            status="pending",
            application_date=date(2024, 10, 1),
            ipc_classification="G06F21/00"
        )
        test_db_session.add(patent)
        await test_db_session.commit()

        result = await test_db_session.execute(
            select(PatentApplication).where(
                PatentApplication.application_number == "202410011234500001"
            )
        )
        db_patent = result.scalar_one_or_none()

        assert db_patent is not None
        assert db_patent.title == "测试专利"
        assert db_patent.status == "pending"

    def test_default_status(self, test_db_session):
        """测试默认状态"""
        patent = PatentApplication(
            application_number="202410011234500002",
            title="测试专利2",
            applicant="测试公司2"
        )
        assert patent.status == "pending"


@pytest.mark.unit
class TestExaminationRuleModel:
    """审查规则模型测试"""

    @pytest.mark.asyncio
    async def test_create_rule(self, test_db_session):
        """测试创建审查规则"""
        rule = ExaminationRule(
            rule_name="测试规则",
            rule_type="formal",
            rule_category="level1",
            rule_content={"type": "required_field", "field": "title"},
            check_pattern="keyword",
            is_active=True,
            priority=10,
            legal_basis="专利法第26条"
        )
        test_db_session.add(rule)
        await test_db_session.commit()

        result = await test_db_session.execute(
            select(ExaminationRule).where(ExaminationRule.rule_name == "测试规则")
        )
        db_rule = result.scalar_one_or_none()

        assert db_rule is not None
        assert db_rule.is_active is True
        assert db_rule.priority == 10


@pytest.mark.unit
class TestWorkflowModels:
    """工作流模型测试"""

    @pytest.mark.asyncio
    async def test_create_workflow_definition(self, test_db_session):
        """测试创建工作流定义"""
        workflow = WorkflowDefinition(
            name="专利审查流程",
            description="标准专利审查工作流",
            workflow_type="patent_examination",
            stages={
                "stages": [
                    {"name": "形式审查", "type": "review"},
                    {"name": "实质审查", "type": "review"},
                    {"name": "授权", "type": "approval"}
                ]
            },
            transitions={
                "transitions": [
                    {"from": "形式审查", "to": "实质审查", "condition": "passed"},
                    {"from": "实质审查", "to": "授权", "condition": "approved"}
                ]
            },
            is_active=True
        )
        test_db_session.add(workflow)
        await test_db_session.commit()

        result = await test_db_session.execute(
            select(WorkflowDefinition).where(
                WorkflowDefinition.name == "专利审查流程"
            )
        )
        db_workflow = result.scalar_one_or_none()

        assert db_workflow is not None
        assert db_workflow.workflow_type == "patent_examination"
        assert db_workflow.is_active is True

    @pytest.mark.asyncio
    async def test_create_workflow_instance(self, test_db_session):
        """测试创建工作流实例"""
        # 先创建工作流定义
        workflow_def = WorkflowDefinition(
            name="测试工作流",
            workflow_type="general",
            stages={"stages": [{"name": "开始", "type": "start"}]},
            transitions={"transitions": []},
            is_active=True
        )
        test_db_session.add(workflow_def)
        await test_db_session.flush()

        # 创建实例
        instance = WorkflowInstance(
            workflow_definition_id=workflow_def.id,
            entity_type="patent_application",
            entity_id=1,
            current_stage="开始",
            status="pending"
        )
        test_db_session.add(instance)
        await test_db_session.commit()

        result = await test_db_session.execute(
            select(WorkflowInstance).where(
                WorkflowInstance.workflow_definition_id == workflow_def.id
            )
        )
        db_instance = result.scalar_one_or_none()

        assert db_instance is not None
        assert db_instance.status == "pending"