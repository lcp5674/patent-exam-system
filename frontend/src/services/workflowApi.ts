/**
 * 工作流和审批 API 服务
 */
import api from "./api";

// ============== Types ==============

// 工作流定义
export interface WorkflowDefinition {
  id: number;
  tenant_id: number | null;
  name: string;
  description: string | null;
  workflow_type: string;
  version: string;
  is_active: boolean;
  is_default: boolean;
  stages: any[];
  transitions: any[];
  assignments: any | null;
  timeout_config: any | null;
  approval_rules: any | null;
  created_by: number | null;
  created_at: string;
  updated_at: string;
}

// 工作流实例
export interface WorkflowInstance {
  id: number;
  tenant_id: number | null;
  workflow_definition_id: number;
  entity_type: string;
  entity_id: number;
  status: string;
  current_stage: string;
  current_assignee_id: number | null;
  completed_stages: any | null;
  stage_history: any[];
  context_data: any | null;
  metadata: any | null;
  started_at: string | null;
  completed_at: string | null;
  due_date: string | null;
  created_by: number | null;
  created_at: string;
  updated_at: string;
  tasks?: WorkflowTask[];
}

// 工作流任务
export interface WorkflowTask {
  id: number;
  instance_id: number;
  tenant_id: number | null;
  task_type: string;
  task_name: string;
  description: string | null;
  assignee_id: number | null;
  assignee_role: string | null;
  status: string;
  priority: string;
  approval_level: number | null;
  is_approval_task: boolean;
  approval_result: string | null;
  approval_comment: string | null;
  due_date: string | null;
  started_at: string | null;
  completed_at: string | null;
  created_at: string;
  updated_at: string;
  instance?: {
    id: number;
    entity_type: string;
    entity_id: number;
    current_stage: string;
    status: string;
  };
}

// 审批记录
export interface ApprovalRecord {
  id: number;
  tenant_id: number | null;
  instance_id: number;
  task_id: number | null;
  approval_level: number;
  approver_id: number;
  approver_name: string | null;
  decision: string;
  comment: string | null;
  attachments: any | null;
  decided_at: string;
  created_at: string;
}

// 工作流统计
export interface WorkflowStats {
  total_instances: number;
  pending_instances: number;
  in_progress_instances: number;
  completed_instances: number;
  cancelled_instances: number;
  overdue_instances: number;
  pending_tasks: number;
  completed_tasks: number;
  avg_completion_time_hours: number | null;
}

// ============== API =============

export const workflowApi = {
  // ========== 工作流定义 ==========
  
  // 获取工作流定义列表
  getDefinitions: async (params?: {
    workflow_type?: string;
    is_active?: boolean;
  }): Promise<{ code: number; data: WorkflowDefinition[] }> => {
    const res = await api.get("/workflow/definitions", { params });
    return res.data;
  },

  // 获取工作流定义详情
  getDefinition: async (id: number): Promise<{ code: number; data: WorkflowDefinition }> => {
    const res = await api.get(`/workflow/definitions/${id}`);
    return res.data;
  },

  // 创建工作流定义
  createDefinition: async (data: any): Promise<{ code: number; data: WorkflowDefinition }> => {
    const res = await api.post("/workflow/definitions", data);
    return res.data;
  },

  // 更新工作流定义
  updateDefinition: async (id: number, data: any): Promise<{ code: number; data: WorkflowDefinition }> => {
    const res = await api.put(`/workflow/definitions/${id}`, data);
    return res.data;
  },

  // 删除工作流定义
  deleteDefinition: async (id: number): Promise<{ code: number; message: string }> => {
    const res = await api.delete(`/workflow/definitions/${id}`);
    return res.data;
  },

  // ========== 工作流实例 ==========
  
  // 获取工作流实例列表
  getInstances: async (params?: {
    entity_type?: string;
    entity_id?: number;
    status?: string;
    assignee_id?: number;
    skip?: number;
    limit?: number;
  }): Promise<{ code: number; data: WorkflowInstance[]; total: number }> => {
    const res = await api.get("/workflow/instances", { params });
    return res.data;
  },

  // 获取工作流实例详情
  getInstance: async (id: number): Promise<{ code: number; data: WorkflowInstance }> => {
    const res = await api.get(`/workflow/instances/${id}`);
    return res.data;
  },

  // 启动工作流
  startWorkflow: async (data: {
    entity_type: string;
    entity_id: number;
    workflow_type?: string;
    context_data?: any;
    due_date?: string;
    initial_assignee_id?: number;
  }): Promise<{ code: number; data: WorkflowInstance }> => {
    const res = await api.post("/workflow/start", data);
    return res.data;
  },

  // ========== 任务管理 ==========
  
  // 获取当前用户任务
  getMyTasks: async (params?: {
    status?: string;
  }): Promise<{ code: number; data: WorkflowTask[] }> => {
    const res = await api.get("/workflow/tasks", { params });
    return res.data;
  },

  // 获取待审批列表
  getPendingApprovals: async (params?: {
    approval_level?: number;
    entity_type?: string;
    skip?: number;
    limit?: number;
  }): Promise<{ code: number; data: WorkflowTask[] }> => {
    const res = await api.get("/workflow/pending-approvals", { params });
    return res.data;
  },

  // 执行任务操作
  executeTaskAction: async (
    instanceId: number,
    taskId: number,
    data: {
      action: "approve" | "reject" | "complete" | "reassign" | "request_changes";
      comment?: string;
      attachments?: any;
      reassign_to?: number;
      metadata?: any;
    }
  ): Promise<{ code: number; data: any }> => {
    const res = await api.post(`/workflow/instances/${instanceId}/tasks/${taskId}/action`, data);
    return res.data;
  },

  // 批量审批
  batchApprove: async (taskIds: number[], comment?: string): Promise<{ code: number; message: string; data: any }> => {
    const res = await api.post("/workflow/tasks/batch-approve", { task_ids: taskIds, comment });
    return res.data;
  },

  // 批量驳回
  batchReject: async (taskIds: number[], comment: string): Promise<{ code: number; message: string; data: any }> => {
    const res = await api.post("/workflow/tasks/batch-reject", { task_ids: taskIds, comment });
    return res.data;
  },

  // ========== 审批记录 ==========
  
  // 获取审批记录
  getApprovalRecords: async (instanceId: number): Promise<{ code: number; data: ApprovalRecord[] }> => {
    const res = await api.get(`/workflow/approvals/${instanceId}`);
    return res.data;
  },

  // ========== 统计 ==========
  
  // 获取工作流统计
  getStats: async (): Promise<{ code: number; data: WorkflowStats }> => {
    const res = await api.get("/workflow/stats");
    return res.data;
  },

  // ========== 专利审查快捷操作 ==========
  
  // 启动专利审查工作流
  startPatentExamination: async (patentId: number): Promise<{ code: number; message: string; data: any }> => {
    const res = await api.post(`/workflow/patent/${patentId}/start-examination`);
    return res.data;
  },

  // 审批通过专利审查
  approvePatent: async (patentId: number, comment?: string): Promise<{ code: number; message: string; data: any }> => {
    const res = await api.post(`/workflow/patent/${patentId}/approve`, { comment });
    return res.data;
  },

  // 驳回专利审查
  rejectPatent: async (patentId: number, comment: string): Promise<{ code: number; message: string; data: any }> => {
    const res = await api.post(`/workflow/patent/${patentId}/reject`, { comment });
    return res.data;
  },
};
