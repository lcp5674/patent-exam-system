"""工作流引擎服务"""
from __future__ import annotations
import logging
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_, text
from sqlalchemy.orm import selectinload
from app.database.models import (
    WorkflowDefinition, WorkflowInstance, WorkflowTask, 
    ApprovalRecord, User, PatentApplication
)
from app.schemas.workflow import (
    WorkflowDefinitionCreate, WorkflowDefinitionUpdate,
    WorkflowStartRequest, WorkflowTaskActionRequest,
    StageConfig, TransitionConfig
)
import json

logger = logging.getLogger(__name__)


class WorkflowService:
    """工作流引擎服务"""

    # 默认工作流模板
    DEFAULT_PATENT_EXAMINATION_WORKFLOW = {
        "stages": [
            {
                "stage_id": "submission",
                "name": "申请提交",
                "description": "专利申请提交",
                "task_type": "submission",
                "assignee_type": "role",
                "assignee_value": "applicant",
                "required_approvals": 1,
                "approval_levels": 1,
                "timeout_hours": 168,  # 7天
                "auto_complete": False,
                "condition": None
            },
            {
                "stage_id": "formal_review",
                "name": "形式审查",
                "description": "审查申请文件形式是否符合要求",
                "task_type": "review",
                "assignee_type": "role",
                "assignee_value": "examiner",
                "required_approvals": 1,
                "approval_levels": 1,
                "timeout_hours": 72,  # 3天
                "auto_complete": False,
                "condition": None
            },
            {
                "stage_id": "formal_approval",
                "name": "形式审查审批",
                "description": "形式审查结果审批",
                "task_type": "approval",
                "assignee_type": "role",
                "assignee_value": "senior_examiner",
                "required_approvals": 1,
                "approval_levels": 2,  # 二级审批
                "timeout_hours": 48,  # 2天
                "auto_complete": False,
                "condition": None
            },
            {
                "stage_id": "substantive_review",
                "name": "实质审查",
                "description": "审查发明新颖性、创造性、实用性",
                "task_type": "review",
                "assignee_type": "role",
                "assignee_value": "examiner",
                "required_approvals": 1,
                "approval_levels": 1,
                "timeout_hours": 240,  # 10天
                "auto_complete": False,
                "condition": None
            },
            {
                "stage_id": "substantive_approval",
                "name": "实质审查审批",
                "description": "实质审查结果审批",
                "task_type": "approval",
                "assignee_type": "role",
                "assignee_value": "senior_examiner",
                "required_approvals": 1,
                "approval_levels": 2,
                "timeout_hours": 72,
                "auto_complete": False,
                "condition": None
            },
            {
                "stage_id": "grant_decision",
                "name": "授权决定",
                "description": "做出授权决定",
                "task_type": "approval",
                "assignee_type": "role",
                "assignee_value": "chief_examiner",
                "required_approvals": 1,
                "approval_levels": 3,  # 三级审批
                "timeout_hours": 48,
                "auto_complete": False,
                "condition": None
            },
            {
                "stage_id": "patent_grant",
                "name": "专利授予",
                "description": "办理登记手续并授予专利权",
                "task_type": "verification",
                "assignee_type": "role",
                "assignee_value": "examiner",
                "required_approvals": 1,
                "approval_levels": 1,
                "timeout_hours": 24,
                "auto_complete": False,
                "condition": None
            }
        ],
        "transitions": [
            {"from_stage": "submission", "to_stage": "formal_review", "trigger": "manual", "required_roles": ["applicant"]},
            {"from_stage": "formal_review", "to_stage": "formal_approval", "trigger": "manual", "required_roles": ["examiner"]},
            {"from_stage": "formal_approval", "to_stage": "substantive_review", "trigger": "auto", "condition": {"decision": "approved"}},
            {"from_stage": "formal_approval", "to_stage": "formal_review", "trigger": "manual", "condition": {"decision": "rejected"}},
            {"from_stage": "substantive_review", "to_stage": "substantive_approval", "trigger": "manual", "required_roles": ["examiner"]},
            {"from_stage": "substantive_approval", "to_stage": "grant_decision", "trigger": "auto", "condition": {"decision": "approved"}},
            {"from_stage": "substantive_approval", "to_stage": "substantive_review", "trigger": "manual", "condition": {"decision": "rejected"}},
            {"from_stage": "grant_decision", "to_stage": "patent_grant", "trigger": "auto", "condition": {"decision": "approved"}},
            {"from_stage": "patent_grant", "to_stage": "completed", "trigger": "auto", "required_roles": ["examiner"]}
        ],
        "approval_rules": {
            "multi_level_enabled": True,
            "escalation_enabled": True,
            "escalation_timeout_hours": 24,
            "require_comment_on_reject": True,
            "allow_forward_after_reject": True
        }
    }

    @staticmethod
    async def create_workflow_definition(
        db: AsyncSession,
        data: WorkflowDefinitionCreate,
        user_id: int
    ) -> WorkflowDefinition:
        """创建工作流定义"""
        # 如果设为默认工作流，先取消其他默认
        if data.is_default:
            await db.execute(
                update(WorkflowDefinition)
                .where(WorkflowDefinition.workflow_type == data.workflow_type)
                .values(is_default=False)
            )
        
        workflow = WorkflowDefinition(
            tenant_id=None,
            name=data.name,
            description=data.description,
            workflow_type=data.workflow_type,
            version="1.0",
            is_active=True,
            is_default=data.is_default,
            stages=[s.model_dump() for s in data.stages],
            transitions=[t.model_dump() for t in data.transitions],
            assignments=data.assignments,
            timeout_config=data.timeout_config,
            approval_rules=data.approval_rules,
            auto_approve_conditions=data.auto_approve_conditions,
            created_by=user_id
        )
        db.add(workflow)
        await db.flush()
        
        # 如果是默认工作流类型，初始化默认工作流模板
        if data.workflow_type == "patent_examination" and data.is_default:
            await WorkflowService._init_default_workflow_templates(db, tenant_id=None)
        
        return workflow

    @staticmethod
    async def get_workflow_definitions(
        db: AsyncSession,
        tenant_id: Optional[int] = None,
        workflow_type: Optional[str] = None,
        is_active: Optional[bool] = None
    ) -> List[WorkflowDefinition]:
        """获取工作流定义列表"""
        query = select(WorkflowDefinition)
        
        if tenant_id is not None:
            query = query.where(WorkflowDefinition.tenant_id == tenant_id)
        if workflow_type:
            query = query.where(WorkflowDefinition.workflow_type == workflow_type)
        if is_active is not None:
            query = query.where(WorkflowDefinition.is_active == is_active)
        
        query = query.order_by(WorkflowDefinition.is_default.desc(), WorkflowDefinition.created_at.desc())
        result = await db.execute(query)
        return list(result.scalars().all())

    @staticmethod
    async def get_workflow_definition(
        db: AsyncSession,
        definition_id: int
    ) -> Optional[WorkflowDefinition]:
        """获取工作流定义详情"""
        result = await db.execute(
            select(WorkflowDefinition).where(WorkflowDefinition.id == definition_id)
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def get_default_workflow(
        db: AsyncSession,
        workflow_type: str,
        tenant_id: Optional[int] = None
    ) -> Optional[WorkflowDefinition]:
        """获取默认工作流"""
        # 先尝试租户级别默认
        result = await db.execute(
            select(WorkflowDefinition).where(
                and_(
                    WorkflowDefinition.workflow_type == workflow_type,
                    WorkflowDefinition.is_default == True,
                    or_(WorkflowDefinition.tenant_id == tenant_id, WorkflowDefinition.tenant_id == None)
                )
            ).order_by(WorkflowDefinition.tenant_id.desc())  # 租户级别优先
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def start_workflow(
        db: AsyncSession,
        data: WorkflowStartRequest,
        user_id: int,
        tenant_id: Optional[int] = None
    ) -> WorkflowInstance:
        """启动工作流实例"""
        # 获取工作流定义
        if data.workflow_type:
            definition = await WorkflowService.get_default_workflow(db, data.workflow_type, tenant_id)
            if not definition:
                # 使用默认模板
                definition = await WorkflowService._create_default_workflow(db, data.workflow_type, user_id)
        else:
            # 查找关联实体对应的默认工作流
            definition = await WorkflowService._get_entity_workflow(db, data.entity_type, tenant_id)

        if not definition:
            raise ValueError(f"无法找到工作流定义: {data.workflow_type or data.entity_type}")

        # 获取第一个阶段
        stages = definition.stages if isinstance(definition.stages, list) else json.loads(definition.stages) if definition.stages else []
        if not stages:
            raise ValueError("工作流定义中没有阶段")
        
        first_stage = stages[0]
        
        # 确定初始处理人
        assignee_id = data.initial_assignee_id
        if not assignee_id:
            assignee_id = await WorkflowService._resolve_assignee(
                db, first_stage, tenant_id, user_id
            )

        # 创建工作流实例
        instance = WorkflowInstance(
            tenant_id=tenant_id,
            workflow_definition_id=definition.id,
            entity_type=data.entity_type,
            entity_id=data.entity_id,
            status="in_progress",
            current_stage=first_stage["stage_id"],
            current_assignee_id=assignee_id,
            completed_stages={},
            stage_history=[{
                "stage_id": first_stage["stage_id"],
                "entered_at": datetime.now().isoformat(),
                "entered_by": user_id
            }],
            context_data=data.context_data or {},
            metadata={},
            started_at=datetime.now(),
            due_date=data.due_date,
            created_by=user_id
        )
        db.add(instance)
        await db.flush()

        # 创建第一个任务
        task = WorkflowTask(
            instance_id=instance.id,
            tenant_id=tenant_id,
            task_type=first_stage.get("task_type", "review"),
            task_name=first_stage.get("name", first_stage["stage_id"]),
            description=first_stage.get("description"),
            assignee_id=assignee_id,
            assignee_role=first_stage.get("assignee_value"),
            status="pending",
            priority="normal",
            approval_level=1 if first_stage.get("task_type") == "approval" else None,
            is_approval_task=first_stage.get("task_type") == "approval",
            due_date=datetime.now() + timedelta(hours=first_stage.get("timeout_hours", 72)) if first_stage.get("timeout_hours") else None
        )
        db.add(task)
        await db.flush()

        # 更新专利申请状态
        if data.entity_type == "patent_application":
            await db.execute(
                select(PatentApplication).where(PatentApplication.id == data.entity_id)
            )
            patent = (await db.execute(
                select(PatentApplication).where(PatentApplication.id == data.entity_id)
            )).scalar_one_or_none()
            if patent:
                patent.status = "in_examination"
                await db.flush()

        logger.info(f"工作流启动成功: instance_id={instance.id}, stage={first_stage['stage_id']}")
        return instance

    @staticmethod
    async def execute_task(
        db: AsyncSession,
        instance_id: int,
        task_id: int,
        user_id: int,
        data: WorkflowTaskActionRequest
    ) -> WorkflowInstance:
        """执行任务操作"""
        # 获取工作流实例
        result = await db.execute(
            select(WorkflowInstance)
            .options(selectinload(WorkflowInstance.definition))
            .where(WorkflowInstance.id == instance_id)
        )
        instance = result.scalar_one_or_none()
        if not instance:
            raise ValueError("工作流实例不存在")

        # 获取任务
        task_result = await db.execute(
            select(WorkflowTask).where(WorkflowTask.id == task_id)
        )
        task = task_result.scalar_one_or_none()
        if not task:
            raise ValueError("任务不存在")

        # 验证权限
        if task.assignee_id != user_id:
            user = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
            if not user or user.role not in ["admin", "senior_examiner", "chief_examiner"]:
                raise ValueError("无权限执行此任务")

        # 处理不同操作
        if data.action == "approve":
            task.status = "completed"
            task.approval_result = "approved"
            task.approval_comment = data.comment
            task.completed_at = datetime.now()
            
            # 记录审批
            await WorkflowService._record_approval(
                db, instance, task, user_id, "approved", data.comment, data.attachments
            )
            
            # 继续工作流
            instance = await WorkflowService._advance_workflow(
                db, instance, "approved", user_id, data.metadata
            )

        elif data.action == "reject":
            task.status = "rejected"
            task.approval_result = "rejected"
            task.approval_comment = data.comment
            task.completed_at = datetime.now()
            
            # 记录审批
            await WorkflowService._record_approval(
                db, instance, task, user_id, "rejected", data.comment, data.attachments
            )
            
            # 回退工作流
            instance = await WorkflowService._advance_workflow(
                db, instance, "rejected", user_id, data.metadata
            )

        elif data.action == "complete":
            task.status = "completed"
            task.completed_at = datetime.now()
            instance = await WorkflowService._advance_workflow(
                db, instance, "completed", user_id, data.metadata
            )

        elif data.action == "reassign":
            if not data.reassign_to:
                raise ValueError("必须指定重新分配的用户")
            task.assignee_id = data.reassign_to
            task.status = "pending"

        elif data.action == "request_changes":
            task.status = "rejected"
            task.approval_comment = f"请求修改: {data.comment}"
            task.completed_at = datetime.now()
            # TODO: 实现请求修改逻辑

        await db.flush()
        return instance

    @staticmethod
    async def get_workflow_instances(
        db: AsyncSession,
        tenant_id: Optional[int] = None,
        entity_type: Optional[str] = None,
        entity_id: Optional[int] = None,
        status: Optional[str] = None,
        assignee_id: Optional[int] = None,
        skip: int = 0,
        limit: int = 20
    ) -> tuple[List[WorkflowInstance], int]:
        """获取工作流实例列表"""
        query = select(WorkflowInstance).options(selectinload(WorkflowInstance.definition))
        
        if tenant_id is not None:
            query = query.where(WorkflowInstance.tenant_id == tenant_id)
        if entity_type:
            query = query.where(WorkflowInstance.entity_type == entity_type)
        if entity_id:
            query = query.where(WorkflowInstance.entity_id == entity_id)
        if status:
            query = query.where(WorkflowInstance.status == status)
        if assignee_id:
            query = query.where(WorkflowInstance.current_assignee_id == assignee_id)
        
        # 获取总数
        count_query = select(func.count()).select_from(query.subquery())
        total_result = await db.execute(count_query)
        total = total_result.scalar() or 0
        
        # 分页查询
        query = query.order_by(WorkflowInstance.created_at.desc()).offset(skip).limit(limit)
        result = await db.execute(query)
        instances = list(result.scalars().all())
        
        return instances, total

    @staticmethod
    async def get_workflow_instance(
        db: AsyncSession,
        instance_id: int
    ) -> Optional[WorkflowInstance]:
        """获取工作流实例详情"""
        result = await db.execute(
            select(WorkflowInstance)
            .options(
                selectinload(WorkflowInstance.definition),
                selectinload(WorkflowInstance.tasks)
            )
            .where(WorkflowInstance.id == instance_id)
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def get_user_tasks(
        db: AsyncSession,
        user_id: int,
        tenant_id: Optional[int] = None,
        status: Optional[str] = None
    ) -> List[WorkflowTask]:
        """获取用户任务列表"""
        user = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
        
        query = select(WorkflowTask).options(selectinload(WorkflowTask.instance))
        
        # 用户自己的任务 或者 角色匹配的任务
        conditions = [
            WorkflowTask.assignee_id == user_id,
            WorkflowTask.assignee_role == user.role if user else None
        ]
        conditions = [c for c in conditions if c is not None]
        
        query = query.where(or_(*conditions))
        
        if tenant_id is not None:
            query = query.where(WorkflowTask.tenant_id == tenant_id)
        if status:
            query = query.where(WorkflowTask.status == status)
        
        query = query.order_by(
            WorkflowTask.priority.desc(),
            WorkflowTask.due_date.asc().nullslast(),
            WorkflowTask.created_at.desc()
        )
        
        result = await db.execute(query)
        return list(result.scalars().all())

    @staticmethod
    async def get_workflow_stats(
        db: AsyncSession,
        tenant_id: Optional[int] = None
    ) -> dict:
        """获取工作流统计"""
        base_filter = [] if tenant_id is None else [WorkflowInstance.tenant_id == tenant_id]
        
        # 实例统计
        total_result = await db.execute(
            select(func.count(WorkflowInstance.id)).where(*base_filter)
        )
        total = total_result.scalar() or 0
        
        pending_result = await db.execute(
            select(func.count(WorkflowInstance.id)).where(
                *base_filter, WorkflowInstance.status == "pending"
            )
        )
        pending = pending_result.scalar() or 0
        
        in_progress_result = await db.execute(
            select(func.count(WorkflowInstance.id)).where(
                *base_filter, WorkflowInstance.status == "in_progress"
            )
        )
        in_progress = in_progress_result.scalar() or 0
        
        completed_result = await db.execute(
            select(func.count(WorkflowInstance.id)).where(
                *base_filter, WorkflowInstance.status == "completed"
            )
        )
        completed = completed_result.scalar() or 0
        
        cancelled_result = await db.execute(
            select(func.count(WorkflowInstance.id)).where(
                *base_filter, WorkflowInstance.status.in_(["cancelled", "paused"])
            )
        )
        cancelled = cancelled_result.scalar() or 0
        
        # 超期统计
        overdue_result = await db.execute(
            select(func.count(WorkflowInstance.id)).where(
                *base_filter,
                WorkflowInstance.status == "in_progress",
                WorkflowInstance.due_date < datetime.now()
            )
        )
        overdue = overdue_result.scalar() or 0
        
        # 任务统计
        task_base = [] if tenant_id is None else [WorkflowTask.tenant_id == tenant_id]
        
        pending_tasks_result = await db.execute(
            select(func.count(WorkflowTask.id)).where(
                *task_base, WorkflowTask.status.in_(["pending", "in_progress"])
            )
        )
        pending_tasks = pending_tasks_result.scalar() or 0
        
        completed_tasks_result = await db.execute(
            select(func.count(WorkflowTask.id)).where(
                *task_base, WorkflowTask.status == "completed"
            )
        )
        completed_tasks = completed_tasks_result.scalar() or 0
        
        # 平均完成时间 (简化实现)
        avg_hours = None
        
        return {
            "total_instances": total,
            "pending_instances": pending,
            "in_progress_instances": in_progress,
            "completed_instances": completed,
            "cancelled_instances": cancelled,
            "overdue_instances": overdue,
            "pending_tasks": pending_tasks,
            "completed_tasks": completed_tasks,
            "avg_completion_time_hours": round(avg_hours, 2) if avg_hours else None
        }

    # 内部辅助方法

    @staticmethod
    async def _advance_workflow(
        db: AsyncSession,
        instance: WorkflowInstance,
        trigger: str,
        user_id: int,
        metadata: Optional[dict] = None
    ) -> WorkflowInstance:
        """推进工作流到下一阶段"""
        # 获取工作流定义
        definition = instance.definition
        if not definition:
            result = await db.execute(
                select(WorkflowDefinition).where(WorkflowDefinition.id == instance.workflow_definition_id)
            )
            definition = result.scalar_one_or_none()
        
        if not definition:
            raise ValueError("工作流定义不存在")
        
        stages = definition.stages if isinstance(definition.stages, list) else json.loads(definition.stages) if definition.stages else []
        transitions = definition.transitions if isinstance(definition.transitions, list) else json.loads(definition.transitions) if definition.transitions else []
        
        current_stage = instance.current_stage
        
        # 查找下一个阶段
        next_stage = None
        for trans in transitions:
            if trans["from_stage"] == current_stage and trans["trigger"] == trigger:
                # 检查条件
                if trans.get("condition"):
                    condition_met = True
                    for k, v in trans["condition"].items():
                        if metadata and metadata.get(k) != v:
                            condition_met = False
                            break
                    if not condition_met:
                        continue
                next_stage_id = trans["to_stage"]
                # 查找阶段配置
                for stage in stages:
                    if stage["stage_id"] == next_stage_id:
                        next_stage = stage
                        break
                if next_stage:
                    break
        
        if not next_stage:
            # 工作流完成
            instance.status = "completed"
            instance.completed_at = datetime.now()
            await db.flush()
            
            # 更新专利状态
            if instance.entity_type == "patent_application":
                patent = (await db.execute(
                    select(PatentApplication).where(PatentApplication.id == instance.entity_id)
                )).scalar_one_or_none()
                if patent:
                    if trigger == "approved":
                        patent.status = "granted"
                    elif trigger == "rejected":
                        patent.status = "rejected"
                    await db.flush()
            
            return instance
        
        # 更新已完成阶段
        completed = instance.completed_stages or {}
        completed[current_stage] = {
            "exited_at": datetime.now().isoformat(),
            "exited_by": user_id,
            "trigger": trigger
        }
        instance.completed_stages = completed
        
        # 更新历史
        history = instance.stage_history or []
        history.append({
            "stage_id": next_stage["stage_id"],
            "entered_at": datetime.now().isoformat(),
            "entered_by": user_id
        })
        instance.stage_history = history
        
        # 创建新任务
        assignee_id = await WorkflowService._resolve_assignee(
            db, next_stage, instance.tenant_id, user_id
        )
        
        task = WorkflowTask(
            instance_id=instance.id,
            tenant_id=instance.tenant_id,
            task_type=next_stage.get("task_type", "review"),
            task_name=next_stage.get("name", next_stage["stage_id"]),
            description=next_stage.get("description"),
            assignee_id=assignee_id,
            assignee_role=next_stage.get("assignee_value"),
            status="pending",
            priority="normal",
            approval_level=1 if next_stage.get("task_type") == "approval" else None,
            is_approval_task=next_stage.get("task_type") == "approval",
            due_date=datetime.now() + timedelta(hours=next_stage.get("timeout_hours", 72)) if next_stage.get("timeout_hours") else None
        )
        db.add(task)
        
        # 更新实例
        instance.current_stage = next_stage["stage_id"]
        instance.current_assignee_id = assignee_id
        instance.status = "in_progress"
        instance.updated_at = datetime.now()
        
        await db.flush()
        return instance

    @staticmethod
    async def _resolve_assignee(
        db: AsyncSession,
        stage: dict,
        tenant_id: Optional[int],
        user_id: int
    ) -> Optional[int]:
        """解析任务分配"""
        assignee_type = stage.get("assignee_type", "role")
        assignee_value = stage.get("assignee_value")
        
        if assignee_type == "user" and assignee_value:
            return int(assignee_value)
        
        if assignee_type == "role" and assignee_value:
            # 查找该角色的用户
            result = await db.execute(
                select(User).where(
                    User.role == assignee_value,
                    User.is_active == True,
                    User.tenant_id == tenant_id
                ).limit(1)
            )
            user = result.scalar_one_or_none()
            if user:
                return user.id
        
        # 默认返回创建者
        return user_id

    @staticmethod
    async def _record_approval(
        db: AsyncSession,
        instance: WorkflowInstance,
        task: WorkflowTask,
        approver_id: int,
        decision: str,
        comment: Optional[str],
        attachments: Optional[dict]
    ):
        """记录审批"""
        user = (await db.execute(select(User).where(User.id == approver_id))).scalar_one_or_none()
        
        record = ApprovalRecord(
            tenant_id=instance.tenant_id,
            instance_id=instance.id,
            task_id=task.id,
            approval_level=task.approval_level or 1,
            approver_id=approver_id,
            approver_name=user.full_name if user else None,
            decision=decision,
            comment=comment,
            attachments=attachments,
            decided_at=datetime.now()
        )
        db.add(record)
        await db.flush()

    @staticmethod
    async def _get_entity_workflow(
        db: AsyncSession,
        entity_type: str,
        tenant_id: Optional[int]
    ) -> Optional[WorkflowDefinition]:
        """根据实体类型获取工作流"""
        workflow_type_map = {
            "patent_application": "patent_examination",
            "document": "document_review"
        }
        workflow_type = workflow_type_map.get(entity_type, "general")
        return await WorkflowService.get_default_workflow(db, workflow_type, tenant_id)

    @staticmethod
    async def _create_default_workflow(
        db: AsyncSession,
        workflow_type: str,
        user_id: int
    ) -> WorkflowDefinition:
        """创建默认工作流"""
        if workflow_type == "patent_examination":
            stages = WorkflowService.DEFAULT_PATENT_EXAMINATION_WORKFLOW["stages"]
            transitions = WorkflowService.DEFAULT_PATENT_EXAMINATION_WORKFLOW["transitions"]
            approval_rules = WorkflowService.DEFAULT_PATENT_EXAMINATION_WORKFLOW["approval_rules"]
        else:
            stages = []
            transitions = []
            approval_rules = {}
        
        workflow = WorkflowDefinition(
            tenant_id=None,
            name=f"默认{workflow_type}工作流",
            description="系统默认工作流",
            workflow_type=workflow_type,
            version="1.0",
            is_active=True,
            is_default=True,
            stages=stages,
            transitions=transitions,
            approval_rules=approval_rules,
            created_by=user_id
        )
        db.add(workflow)
        await db.flush()
        return workflow

    @staticmethod
    async def _init_default_workflow_templates(
        db: AsyncSession,
        tenant_id: Optional[int] = None
    ):
        """初始化默认工作流模板"""
        # 检查是否已存在
        result = await db.execute(
            select(WorkflowDefinition).where(
                WorkflowDefinition.workflow_type == "patent_examination",
                WorkflowDefinition.is_default == True
            )
        )
        existing = result.scalar_one_or_none()
        
        if not existing:
            # 将在第一次启动工作流时自动创建
            pass
