"""工作流引擎 Schema 定义"""
from __future__ import annotations
from datetime import datetime
from typing import Optional, List, Any, Union
from pydantic import BaseModel, Field, field_validator


class StageConfig(BaseModel):
    """工作流阶段配置"""
    stage_id: str
    name: str
    description: Optional[str] = None
    task_type: str  # review / approval / verification / submission
    assignee_type: str = "role"  # role / user / round_robin / auto
    assignee_value: Optional[str] = None  # 角色名/用户ID/轮询组ID
    required_approvals: int = 1  # 需要的审批数量
    approval_levels: int = 1  # 审批层级数
    timeout_hours: Optional[int] = None  # 超时时间(小时)
    auto_complete: bool = False  # 是否自动完成
    condition: Optional[dict] = None  # 进入条件


class TransitionConfig(BaseModel):
    """状态转换配置"""
    from_stage: str
    to_stage: str
    trigger: str  # manual / auto / condition
    condition: Optional[dict] = None
    required_roles: Optional[List[str]] = None


class WorkflowDefinitionCreate(BaseModel):
    """创建工作流定义"""
    name: str
    description: Optional[str] = None
    workflow_type: str  # patent_examination / document_review / general
    stages: List[StageConfig]
    transitions: List[TransitionConfig]
    assignments: Optional[dict] = None
    timeout_config: Optional[dict] = None
    approval_rules: Optional[dict] = None
    auto_approve_conditions: Optional[dict] = None
    is_default: bool = False


class WorkflowDefinitionUpdate(BaseModel):
    """更新工作流定义"""
    name: Optional[str] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None
    stages: Optional[List[StageConfig]] = None
    transitions: Optional[List[TransitionConfig]] = None
    assignments: Optional[dict] = None
    timeout_config: Optional[dict] = None
    approval_rules: Optional[dict] = None
    auto_approve_conditions: Optional[dict] = None


class WorkflowDefinitionResponse(BaseModel):
    """工作流定义响应"""
    id: int
    tenant_id: Optional[int]
    name: str
    description: Optional[str]
    workflow_type: str
    version: str
    is_active: bool
    is_default: bool
    stages: Union[dict, list]  # Accept both dict and list formats
    transitions: Union[dict, list]  # Accept both dict and list formats
    assignments: Optional[dict]
    timeout_config: Optional[dict]
    approval_rules: Optional[dict]
    auto_approve_conditions: Optional[dict]
    created_by: Optional[int]
    created_at: datetime
    updated_at: datetime

    @field_validator('stages', 'transitions', mode='before')
    @classmethod
    def convert_to_dict(cls, v):
        """Convert list to dict if needed for backward compatibility"""
        if v is None:
            return {}
        if isinstance(v, list):
            # Convert list to dict using stage_id as key
            if v and isinstance(v[0], dict) and 'stage_id' in v[0]:
                return {item['stage_id']: item for item in v}
            elif v and isinstance(v[0], dict) and 'from_stage' in v[0]:
                # For transitions, create compound key
                return {f"{item['from_stage']}_to_{item['to_stage']}": item for item in v}
            return {}
        return v

    class Config:
        from_attributes = True


class WorkflowStartRequest(BaseModel):
    """启动工作流请求"""
    entity_type: str  # patent_application / document / general
    entity_id: int
    workflow_type: Optional[str] = None  # 如果不指定，则使用默认工作流
    context_data: Optional[dict] = None
    due_date: Optional[datetime] = None
    initial_assignee_id: Optional[int] = None


class WorkflowTaskActionRequest(BaseModel):
    """执行任务操作请求"""
    action: str  # approve / reject / complete / reassign / request_changes
    comment: Optional[str] = None
    attachments: Optional[dict] = None
    reassign_to: Optional[int] = None
    metadata: Optional[dict] = None


class WorkflowInstanceResponse(BaseModel):
    """工作流实例响应"""
    id: int
    tenant_id: Optional[int]
    workflow_definition_id: int
    entity_type: str
    entity_id: int
    status: str
    current_stage: str
    current_assignee_id: Optional[int]
    completed_stages: Optional[dict]
    stage_history: Optional[List[dict]]
    context_data: Optional[dict]
    metadata: Optional[dict]
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    due_date: Optional[datetime]
    created_by: Optional[int]
    created_at: datetime
    updated_at: datetime
    definition: Optional[WorkflowDefinitionResponse] = None
    tasks: List["WorkflowTaskResponse"] = []

    class Config:
        from_attributes = True


class WorkflowTaskResponse(BaseModel):
    """工作流任务响应"""
    id: int
    instance_id: int
    tenant_id: Optional[int]
    task_type: str
    task_name: str
    description: Optional[str]
    assignee_id: Optional[int]
    assignee_role: Optional[str]
    status: str
    priority: str
    approval_level: Optional[int]
    is_approval_task: bool
    approval_result: Optional[str]
    approval_comment: Optional[str]
    due_date: Optional[datetime]
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ApprovalRecordResponse(BaseModel):
    """审批记录响应"""
    id: int
    tenant_id: Optional[int]
    instance_id: int
    task_id: Optional[int]
    approval_level: int
    approver_id: int
    approver_name: Optional[str]
    decision: str
    comment: Optional[str]
    attachments: Optional[dict]
    decided_at: datetime
    created_at: datetime

    class Config:
        from_attributes = True


class WorkflowStatsResponse(BaseModel):
    """工作流统计响应"""
    total_instances: int
    pending_instances: int
    in_progress_instances: int
    completed_instances: int
    cancelled_instances: int
    overdue_instances: int
    pending_tasks: int
    completed_tasks: int
    avg_completion_time_hours: Optional[float]


# 更新前向引用
WorkflowInstanceResponse.model_rebuild()
WorkflowTaskResponse.model_rebuild()
