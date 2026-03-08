"""工作流引擎 API 路由"""
from __future__ import annotations
import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.database.engine import get_db
from app.core.security import get_current_user
from app.database.models import User, WorkflowTask
from app.services.workflow_service import WorkflowService
from app.schemas.workflow import (
    WorkflowDefinitionCreate, WorkflowDefinitionUpdate, WorkflowDefinitionResponse,
    WorkflowStartRequest, WorkflowTaskActionRequest,
    WorkflowInstanceResponse, WorkflowTaskResponse, ApprovalRecordResponse,
    WorkflowStatsResponse
)
from sqlalchemy import select, or_

logger = logging.getLogger(__name__)
router = APIRouter(tags=["工作流引擎"])


# 工作流定义管理
@router.post("/definitions", summary="创建工作流定义")
async def create_workflow_definition(
    data: WorkflowDefinitionCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """创建新的工作流定义"""
    try:
        workflow = await WorkflowService.create_workflow_definition(db, data, user.id)
        await db.commit()
        return {"code": 200, "data": WorkflowDefinitionResponse.model_validate(workflow).model_dump()}
    except Exception as e:
        await db.rollback()
        logger.error(f"创建工作流定义失败: {e}")
        raise HTTPException(400, str(e))


@router.get("/definitions", summary="获取工作流定义列表")
async def list_workflow_definitions(
    workflow_type: Optional[str] = Query(None, description="工作流类型"),
    is_active: Optional[bool] = Query(None, description="是否激活"),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """获取工作流定义列表"""
    workflows = await WorkflowService.get_workflow_definitions(
        db, 
        tenant_id=user.tenant_id,
        workflow_type=workflow_type,
        is_active=is_active
    )
    data = [WorkflowDefinitionResponse.model_validate(w).model_dump() for w in workflows]
    return {"code": 200, "data": data}


@router.get("/definitions/{definition_id}", summary="获取工作流定义详情")
async def get_workflow_definition(
    definition_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """获取工作流定义详情"""
    workflow = await WorkflowService.get_workflow_definition(db, definition_id)
    if not workflow:
        raise HTTPException(404, "工作流定义不存在")
    return {"code": 200, "data": WorkflowDefinitionResponse.model_validate(workflow).model_dump()}


@router.put("/definitions/{definition_id}", summary="更新工作流定义")
async def update_workflow_definition(
    definition_id: int,
    data: WorkflowDefinitionUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """更新工作流定义"""
    from sqlalchemy import update
    from app.database.models import WorkflowDefinition
    
    update_data = data.model_dump(exclude_unset=True)
    if "stages" in update_data:
        update_data["stages"] = [s.model_dump() if hasattr(s, 'model_dump') else s for s in update_data["stages"]]
    if "transitions" in update_data:
        update_data["transitions"] = [t.model_dump() if hasattr(t, 'model_dump') else t for t in update_data["transitions"]]
    
    await db.execute(
        update(WorkflowDefinition)
        .where(WorkflowDefinition.id == definition_id)
        .values(**update_data)
    )
    await db.commit()
    
    workflow = await WorkflowService.get_workflow_definition(db, definition_id)
    return {"code": 200, "data": WorkflowDefinitionResponse.model_validate(workflow).model_dump()}


@router.delete("/definitions/{definition_id}", summary="删除工作流定义")
async def delete_workflow_definition(
    definition_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """删除工作流定义（软删除）"""
    from sqlalchemy import update
    from app.database.models import WorkflowDefinition
    
    await db.execute(
        update(WorkflowDefinition)
        .where(WorkflowDefinition.id == definition_id)
        .values(is_active=False)
    )
    await db.commit()
    return {"code": 200, "message": "工作流定义已删除"}


# 工作流实例管理
@router.post("/start", summary="启动工作流")
async def start_workflow(
    data: WorkflowStartRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """启动一个新的工作流实例"""
    try:
        instance = await WorkflowService.start_workflow(
            db, data, user.id, user.tenant_id
        )
        await db.commit()
        
        full_instance = await WorkflowService.get_workflow_instance(db, instance.id)
        
        response_data = {
            "id": full_instance.id,
            "tenant_id": full_instance.tenant_id,
            "workflow_definition_id": full_instance.workflow_definition_id,
            "entity_type": full_instance.entity_type,
            "entity_id": full_instance.entity_id,
            "status": full_instance.status,
            "current_stage": full_instance.current_stage,
            "current_assignee_id": full_instance.current_assignee_id,
            "completed_stages": full_instance.completed_stages,
            "stage_history": full_instance.stage_history,
            "context_data": full_instance.context_data,
            "workflow_metadata": full_instance.workflow_metadata,
            "started_at": full_instance.started_at.isoformat() if full_instance.started_at else None,
            "completed_at": full_instance.completed_at.isoformat() if full_instance.completed_at else None,
            "due_date": full_instance.due_date.isoformat() if full_instance.due_date else None,
            "created_by": full_instance.created_by,
            "created_at": full_instance.created_at.isoformat(),
            "updated_at": full_instance.updated_at.isoformat(),
        }
        
        return {"code": 200, "data": response_data}
    except Exception as e:
        await db.rollback()
        logger.error(f"启动工作流失败: {e}")
        raise HTTPException(400, str(e))


@router.get("/instances", summary="获取工作流实例列表")
async def list_workflow_instances(
    entity_type: Optional[str] = Query(None, description="实体类型"),
    entity_id: Optional[int] = Query(None, description="实体ID"),
    status: Optional[str] = Query(None, description="状态"),
    assignee_id: Optional[int] = Query(None, description="处理人ID"),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """获取工作流实例列表"""
    instances, total = await WorkflowService.get_workflow_instances(
        db,
        tenant_id=user.tenant_id,
        entity_type=entity_type,
        entity_id=entity_id,
        status=status,
        assignee_id=assignee_id,
        skip=skip,
        limit=limit
    )
    
    data = []
    for inst in instances:
        tasks_result = await db.execute(
            select(WorkflowTask).where(WorkflowTask.instance_id == inst.id)
        )
        tasks = list(tasks_result.scalars().all())
        
        data.append({
            "id": inst.id,
            "tenant_id": inst.tenant_id,
            "workflow_definition_id": inst.workflow_definition_id,
            "entity_type": inst.entity_type,
            "entity_id": inst.entity_id,
            "status": inst.status,
            "current_stage": inst.current_stage,
            "current_assignee_id": inst.current_assignee_id,
            "completed_stages": inst.completed_stages,
            "stage_history": inst.stage_history,
            "context_data": inst.context_data,
            "workflow_metadata": inst.workflow_metadata,
            "started_at": inst.started_at.isoformat() if inst.started_at else None,
            "completed_at": inst.completed_at.isoformat() if inst.completed_at else None,
            "due_date": inst.due_date.isoformat() if inst.due_date else None,
            "created_by": inst.created_by,
            "created_at": inst.created_at.isoformat(),
            "updated_at": inst.updated_at.isoformat(),
            "tasks": [WorkflowTaskResponse.model_validate(t).model_dump() for t in tasks]
        })
    
    return {"code": 200, "data": data, "total": total}


@router.get("/instances/{instance_id}", summary="获取工作流实例详情")
async def get_workflow_instance(
    instance_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """获取工作流实例详情"""
    instance = await WorkflowService.get_workflow_instance(db, instance_id)
    if not instance:
        raise HTTPException(404, "工作流实例不存在")
    
    response_data = {
        "id": instance.id,
        "tenant_id": instance.tenant_id,
        "workflow_definition_id": instance.workflow_definition_id,
        "entity_type": instance.entity_type,
        "entity_id": instance.entity_id,
        "status": instance.status,
        "current_stage": instance.current_stage,
        "current_assignee_id": instance.current_assignee_id,
        "completed_stages": instance.completed_stages,
        "stage_history": instance.stage_history,
        "context_data": instance.context_data,
        "metadata": instance.metadata,
        "started_at": instance.started_at.isoformat() if instance.started_at else None,
        "completed_at": instance.completed_at.isoformat() if instance.completed_at else None,
        "due_date": instance.due_date.isoformat() if instance.due_date else None,
        "created_by": instance.created_by,
        "created_at": instance.created_at.isoformat(),
        "updated_at": instance.updated_at.isoformat(),
        "tasks": [WorkflowTaskResponse.model_validate(t).model_dump() for t in instance.tasks]
    }
    
    return {"code": 200, "data": response_data}


# 任务管理
@router.get("/tasks", summary="获取当前用户任务列表")
async def get_user_tasks(
    status: Optional[str] = Query(None, description="任务状态"),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """获取当前用户的任务列表"""
    tasks = await WorkflowService.get_user_tasks(
        db, user.id, user.tenant_id, status
    )
    
    data = []
    for task in tasks:
        task_dict = WorkflowTaskResponse.model_validate(task).model_dump()
        if task.instance:
            task_dict["instance"] = {
                "id": task.instance.id,
                "entity_type": task.instance.entity_type,
                "entity_id": task.instance.entity_id,
                "current_stage": task.instance.current_stage,
                "status": task.instance.status
            }
        data.append(task_dict)
    
    return {"code": 200, "data": data}


@router.post("/instances/{instance_id}/tasks/{task_id}/action", summary="执行任务操作")
async def execute_task_action(
    instance_id: int,
    task_id: int,
    data: WorkflowTaskActionRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """执行任务操作（审批/拒绝/完成/转交）"""
    try:
        instance = await WorkflowService.execute_task(
            db, instance_id, task_id, user.id, data
        )
        await db.commit()
        
        full_instance = await WorkflowService.get_workflow_instance(db, instance_id)
        
        response_data = {
            "id": full_instance.id,
            "status": full_instance.status,
            "current_stage": full_instance.current_stage,
            "current_assignee_id": full_instance.current_assignee_id,
            "completed_stages": full_instance.completed_stages,
            "stage_history": full_instance.stage_history,
            "completed_at": full_instance.completed_at.isoformat() if full_instance.completed_at else None,
            "tasks": [WorkflowTaskResponse.model_validate(t).model_dump() for t in full_instance.tasks]
        }
        
        return {"code": 200, "data": response_data}
    except Exception as e:
        await db.rollback()
        logger.error(f"执行任务操作失败: {e}")
        raise HTTPException(400, str(e))


@router.get("/approvals/{instance_id}", summary="获取审批记录")
async def get_approval_records(
    instance_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """获取工作流实例的审批记录"""
    from app.database.models import ApprovalRecord
    
    result = await db.execute(
        select(ApprovalRecord)
        .where(ApprovalRecord.instance_id == instance_id)
        .order_by(ApprovalRecord.approval_level, ApprovalRecord.decided_at)
    )
    records = list(result.scalars().all())
    
    data = [ApprovalRecordResponse.model_validate(r).model_dump() for r in records]
    return {"code": 200, "data": data}


# 批量审批
@router.post("/tasks/batch-approve", summary="批量审批任务")
async def batch_approve_tasks(
    task_ids: list[int],
    comment: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """批量审批多个任务"""
    from app.database.models import WorkflowTask, WorkflowInstance
    from sqlalchemy import select
    
    results = []
    errors = []
    
    for task_id in task_ids:
        try:
            # 获取任务
            task_result = await db.execute(
                select(WorkflowTask).where(WorkflowTask.id == task_id)
            )
            task = task_result.scalar_one_or_none()
            
            if not task:
                errors.append({"task_id": task_id, "error": "任务不存在"})
                continue
            
            # 获取实例
            instance_result = await db.execute(
                select(WorkflowInstance).where(WorkflowInstance.id == task.instance_id)
            )
            instance = instance_result.scalar_one_or_none()
            
            if not instance:
                errors.append({"task_id": task_id, "error": "工作流实例不存在"})
                continue
            
            # 执行审批
            action_request = WorkflowTaskActionRequest(
                action="approve",
                comment=comment
            )
            
            await WorkflowService.execute_task(
                db, instance.id, task.id, user.id, action_request
            )
            
            results.append({"task_id": task_id, "status": "approved"})
            
        except Exception as e:
            errors.append({"task_id": task_id, "error": str(e)})
    
    await db.commit()
    
    return {
        "code": 200,
        "message": f"批量审批完成: {len(results)}成功, {len(errors)}失败",
        "data": {
            "succeeded": results,
            "failed": errors
        }
    }


@router.post("/tasks/batch-reject", summary="批量驳回任务")
async def batch_reject_tasks(
    task_ids: list[int],
    comment: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """批量驳回多个任务"""
    from app.database.models import WorkflowTask, WorkflowInstance
    
    if not comment:
        raise HTTPException(400, "驳回时必须填写意见")
    
    results = []
    errors = []
    
    for task_id in task_ids:
        try:
            task_result = await db.execute(
                select(WorkflowTask).where(WorkflowTask.id == task_id)
            )
            task = task_result.scalar_one_or_none()
            
            if not task:
                errors.append({"task_id": task_id, "error": "任务不存在"})
                continue
            
            instance_result = await db.execute(
                select(WorkflowInstance).where(WorkflowInstance.id == task.instance_id)
            )
            instance = instance_result.scalar_one_or_none()
            
            if not instance:
                errors.append({"task_id": task_id, "error": "工作流实例不存在"})
                continue
            
            action_request = WorkflowTaskActionRequest(
                action="reject",
                comment=comment
            )
            
            await WorkflowService.execute_task(
                db, instance.id, task.id, user.id, action_request
            )
            
            results.append({"task_id": task_id, "status": "rejected"})
            
        except Exception as e:
            errors.append({"task_id": task_id, "error": str(e)})
    
    await db.commit()
    
    return {
        "code": 200,
        "message": f"批量驳回完成: {len(results)}成功, {len(errors)}失败",
        "data": {
            "succeeded": results,
            "failed": errors
        }
    }


# 获取待审批列表
@router.get("/pending-approvals", summary="获取待审批列表")
async def get_pending_approvals(
    approval_level: Optional[int] = Query(None, description="审批层级"),
    entity_type: Optional[str] = Query(None, description="实体类型"),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """获取当前用户的待审批任务列表"""
    from app.database.models import WorkflowTask, WorkflowInstance
    from sqlalchemy import select, and_
    
    # 获取用户角色对应的待审批任务
    conditions = [
        WorkflowTask.status.in_(["pending", "in_progress"]),
        or_(
            WorkflowTask.assignee_id == user.id,
            WorkflowTask.assignee_role == user.role
        )
    ]
    
    if approval_level is not None:
        conditions.append(WorkflowTask.approval_level == approval_level)
    if entity_type:
        # 需要关联查询
        pass
    
    query = select(WorkflowTask).where(and_(*conditions)).offset(skip).limit(limit)
    result = await db.execute(query)
    tasks = list(result.scalars().all())
    
    # 获取实例信息
    data = []
    for task in tasks:
        task_dict = WorkflowTaskResponse.model_validate(task).model_dump()
        
        instance_result = await db.execute(
            select(WorkflowInstance).where(WorkflowInstance.id == task.instance_id)
        )
        instance = instance_result.scalar_one_or_none()
        if instance:
            task_dict["instance"] = {
                "id": instance.id,
                "entity_type": instance.entity_type,
                "entity_id": instance.entity_id,
                "current_stage": instance.current_stage,
                "status": instance.status
            }
        
        data.append(task_dict)
    
    return {"code": 200, "data": data}


# 统计
@router.get("/stats", summary="获取工作流统计")
async def get_workflow_stats(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """获取工作流统计信息"""
    stats = await WorkflowService.get_workflow_stats(db, user.tenant_id)
    return {"code": 200, "data": stats}


# 专利审查工作流快捷操作
@router.post("/patent/{patent_id}/start-examination", summary="启动专利审查工作流")
async def start_patent_examination(
    patent_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """快捷操作：为专利申请启动审查工作流"""
    from app.database.models import PatentApplication
    
    patent = (await db.execute(
        select(PatentApplication).where(PatentApplication.id == patent_id)
    )).scalar_one_or_none()
    
    if not patent:
        raise HTTPException(404, "专利申请不存在")
    
    request = WorkflowStartRequest(
        entity_type="patent_application",
        entity_id=patent_id,
        workflow_type="patent_examination"
    )
    
    try:
        instance = await WorkflowService.start_workflow(
            db, request, user.id, user.tenant_id
        )
        await db.commit()
        
        return {
            "code": 200, 
            "message": "专利审查工作流已启动",
            "data": {
                "instance_id": instance.id,
                "current_stage": instance.current_stage,
                "status": instance.status
            }
        }
    except Exception as e:
        await db.rollback()
        logger.error(f"启动专利审查工作流失败: {e}")
        raise HTTPException(400, str(e))


@router.post("/patent/{patent_id}/approve", summary="审批通过专利审查")
async def approve_patent_examination(
    patent_id: int,
    comment: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """快捷操作：审批通过当前专利审查阶段"""
    from app.database.models import WorkflowInstance, WorkflowTask
    
    result = await db.execute(
        select(WorkflowInstance).where(
            WorkflowInstance.entity_type == "patent_application",
            WorkflowInstance.entity_id == patent_id,
            WorkflowInstance.status == "in_progress"
        )
    )
    instance = result.scalar_one_or_none()
    
    if not instance:
        raise HTTPException(404, "没有进行中的专利审查工作流")
    
    task_result = await db.execute(
        select(WorkflowTask).where(
            WorkflowTask.instance_id == instance.id,
            WorkflowTask.status.in_(["pending", "in_progress"])
        )
    )
    task = task_result.scalar_one_or_none()
    
    if not task:
        raise HTTPException(404, "没有待处理的任务")
    
    action_request = WorkflowTaskActionRequest(
        action="approve",
        comment=comment
    )
    
    try:
        await WorkflowService.execute_task(
            db, instance.id, task.id, user.id, action_request
        )
        await db.commit()
        
        updated_instance = await WorkflowService.get_workflow_instance(db, instance.id)
        
        return {
            "code": 200,
            "message": "审批已通过",
            "data": {
                "instance_id": updated_instance.id,
                "current_stage": updated_instance.current_stage,
                "status": updated_instance.status
            }
        }
    except Exception as e:
        await db.rollback()
        logger.error(f"审批失败: {e}")
        raise HTTPException(400, str(e))


@router.post("/patent/{patent_id}/reject", summary="驳回专利审查")
async def reject_patent_examination(
    patent_id: int,
    comment: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """快捷操作：驳回当前专利审查阶段"""
    from app.database.models import WorkflowInstance, WorkflowTask
    
    if not comment:
        raise HTTPException(400, "驳回时必须填写意见")
    
    result = await db.execute(
        select(WorkflowInstance).where(
            WorkflowInstance.entity_type == "patent_application",
            WorkflowInstance.entity_id == patent_id,
            WorkflowInstance.status == "in_progress"
        )
    )
    instance = result.scalar_one_or_none()
    
    if not instance:
        raise HTTPException(404, "没有进行中的专利审查工作流")
    
    task_result = await db.execute(
        select(WorkflowTask).where(
            WorkflowTask.instance_id == instance.id,
            WorkflowTask.status.in_(["pending", "in_progress"])
        )
    )
    task = task_result.scalar_one_or_none()
    
    if not task:
        raise HTTPException(404, "没有待处理的任务")
    
    action_request = WorkflowTaskActionRequest(
        action="reject",
        comment=comment
    )
    
    try:
        await WorkflowService.execute_task(
            db, instance.id, task.id, user.id, action_request
        )
        await db.commit()
        
        updated_instance = await WorkflowService.get_workflow_instance(db, instance.id)
        
        return {
            "code": 200,
            "message": "已驳回",
            "data": {
                "instance_id": updated_instance.id,
                "current_stage": updated_instance.current_stage,
                "status": updated_instance.status
            }
        }
    except Exception as e:
        await db.rollback()
        logger.error(f"驳回失败: {e}")
        raise HTTPException(400, str(e))
