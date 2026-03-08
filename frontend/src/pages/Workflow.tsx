/**
 * 工作流管理页面
 * Workflow Management Page
 */
import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import {
  Card, Tabs, Table, Button, Space, Tag, Modal, Form, Input, Select,
  Descriptions, Timeline, Badge, Statistic, Row, Col, message, Drawer,
  Divider, Alert, Popconfirm, Typography, Empty, List, Avatar, Steps,
  InputNumber, Checkbox, DatePicker, notification, Switch
} from "antd";
import {
  PlayCircleOutlined, CheckCircleOutlined, CloseCircleOutlined,
  ClockCircleOutlined, DashboardOutlined, HistoryOutlined,
  SettingOutlined, FileTextOutlined, UserOutlined, TeamOutlined,
  PlusOutlined, SearchOutlined, ReloadOutlined, SyncOutlined,
  ArrowRightOutlined, BankOutlined, AuditOutlined, EditOutlined, DeleteOutlined
} from "@ant-design/icons";
import type { ColumnsType } from "antd/es/table";
import { workflowApi, WorkflowDefinition, WorkflowInstance, WorkflowTask, WorkflowStats, ApprovalRecord } from "../services/workflowApi";
import dayjs from "dayjs";

const { Title, Text, Paragraph } = Typography;
const { Step } = Steps;
const { TextArea } = Input;

// 工作流类型映射
const WORKFLOW_TYPE_MAP: Record<string, string> = {
  patent_examination: "专利审查",
  document_review: "文档审批",
  general: "通用流程"
};

// 状态颜色映射
const STATUS_COLORS: Record<string, string> = {
  pending: "default",
  in_progress: "processing",
  completed: "success",
  cancelled: "error",
  paused: "warning",
  rejected: "error",
  approved: "success"
};

// 任务状态映射
const TASK_STATUS_MAP: Record<string, { text: string; color: string }> = {
  pending: { text: "待处理", color: "default" },
  in_progress: { text: "处理中", color: "processing" },
  completed: { text: "已完成", color: "success" },
  rejected: { text: "已驳回", color: "error" },
  cancelled: { text: "已取消", color: "default" }
};

export default function WorkflowPage() {
  const navigate = useNavigate();
  const [activeTab, setActiveTab] = useState("overview");
  
  // 统计数据
  const [stats, setStats] = useState<WorkflowStats | null>(null);
  const [statsLoading, setStatsLoading] = useState(false);
  
  // 待办任务
  const [pendingTasks, setPendingTasks] = useState<WorkflowTask[]>([]);
  const [tasksLoading, setTasksLoading] = useState(false);
  
  // 工作流实例
  const [instances, setInstances] = useState<WorkflowInstance[]>([]);
  const [instancesLoading, setInstancesLoading] = useState(false);
  const [instanceTotal, setInstanceTotal] = useState(0);
  
  // 工作流定义
  const [definitions, setDefinitions] = useState<WorkflowDefinition[]>([]);
  const [definitionsLoading, setDefinitionsLoading] = useState(false);
  
  // 审批记录
  const [approvalRecords, setApprovalRecords] = useState<ApprovalRecord[]>([]);
  const [approvalLoading, setApprovalLoading] = useState(false);
  
  // Drawer状态
  const [instanceDrawer, setInstanceDrawer] = useState<{ visible: boolean; instance: WorkflowInstance | null }>({ visible: false, instance: null });
  const [approveModal, setApproveModal] = useState<{ visible: boolean; task: WorkflowTask | null }>({ visible: false, task: null });
  
  // 工作流定义编辑状态
  const [definitionModal, setDefinitionModal] = useState<{ visible: boolean; editData: WorkflowDefinition | null }>({ visible: false, editData: null });
  const [definitionForm] = Form.useForm();

  const [approveForm] = Form.useForm();

  useEffect(() => {
    loadStats();
    loadPendingTasks();
    loadInstances();
    loadDefinitions();
  }, []);

  const loadStats = async () => {
    setStatsLoading(true);
    try {
      const res = await workflowApi.getStats();
      if (res.code === 200) {
        setStats(res.data);
      }
    } catch (error) {
      console.error("加载统计失败:", error);
    } finally {
      setStatsLoading(false);
    }
  };

  const loadPendingTasks = async () => {
    setTasksLoading(true);
    try {
      const res = await workflowApi.getPendingApprovals();
      if (res.code === 200) {
        setPendingTasks(res.data);
      }
    } catch (error) {
      console.error("加载待办任务失败:", error);
    } finally {
      setTasksLoading(false);
    }
  };

  const loadInstances = async (params?: any) => {
    setInstancesLoading(true);
    try {
      const res = await workflowApi.getInstances(params);
      if (res.code === 200) {
        setInstances(res.data as WorkflowInstance[]);
        setInstanceTotal(res.total);
      }
    } catch (error) {
      console.error("加载工作流实例失败:", error);
    } finally {
      setInstancesLoading(false);
    }
  };

  const loadDefinitions = async () => {
    setDefinitionsLoading(true);
    try {
      const res = await workflowApi.getDefinitions();
      if (res.code === 200) {
        setDefinitions(res.data);
      }
    } catch (error) {
      console.error("加载工作流定义失败:", error);
    } finally {
      setDefinitionsLoading(false);
    }
  };

  const loadApprovalRecords = async (instanceId: number) => {
    setApprovalLoading(true);
    try {
      const res = await workflowApi.getApprovalRecords(instanceId);
      if (res.code === 200) {
        setApprovalRecords(res.data);
      }
    } catch (error) {
      console.error("加载审批记录失败:", error);
    } finally {
      setApprovalLoading(false);
    }
  };

  // 打开工作流定义弹窗
  const openDefinitionModal = (record?: WorkflowDefinition) => {
    if (record) {
      definitionForm.setFieldsValue({
        ...record,
        is_default: record.is_default || false,
        is_active: record.is_active !== false,
      });
      setDefinitionModal({ visible: true, editData: record });
    } else {
      definitionForm.resetFields();
      setDefinitionModal({ visible: true, editData: null });
    }
  };

  // 保存工作流定义
  const saveDefinition = async () => {
    try {
      const values = await definitionForm.validateFields();
      const data = {
        ...values,
        workflow_type: values.workflow_type || "general",
        // 添加后端需要的必填字段（字典类型）
        stages: {},
        transitions: {},
      };
      
      let res;
      if (definitionModal.editData) {
        res = await workflowApi.updateDefinition(definitionModal.editData.id, data);
      } else {
        res = await workflowApi.createDefinition(data);
      }
      
      if (res.code === 200) {
        message.success(definitionModal.editData ? "更新成功" : "创建成功");
        setDefinitionModal({ visible: false, editData: null });
        definitionForm.resetFields();
        loadDefinitions();
      }
    } catch (error: any) {
      message.error(error.message || "操作失败");
    }
  };

  // 删除工作流定义
  const handleDeleteDefinition = async (id: number) => {
    try {
      const res = await workflowApi.deleteDefinition(id);
      if (res.code === 200) {
        message.success("删除成功");
        loadDefinitions();
      }
    } catch (error: any) {
      message.error(error.message || "删除失败");
    }
  };

  // 审批通过
  const handleApprove = async (task: WorkflowTask) => {
    setApproveModal({ visible: true, task });
  };

  const submitApprove = async () => {
    try {
      const values = await approveForm.validateFields();
      if (!approveModal.task) return;
      
      const res = await workflowApi.executeTaskAction(
        approveModal.task.instance_id,
        approveModal.task.id,
        { action: "approve", comment: values.comment }
      );
      
      if (res.code === 200) {
        message.success("审批已通过");
        setApproveModal({ visible: false, task: null });
        approveForm.resetFields();
        loadPendingTasks();
        loadInstances();
        loadStats();
      }
    } catch (error: any) {
      message.error(error.message || "操作失败");
    }
  };

  // 审批驳回
  const handleReject = async (task: WorkflowTask) => {
    Modal.confirm({
      title: "确认驳回",
      content: (
        <div>
          <p>请输入驳回原因:</p>
          <TextArea
            id="reject-reason"
            rows={3}
            placeholder="请输入驳回原因"
          />
        </div>
      ),
      onOk: async () => {
        const reasonInput = document.getElementById("reject-reason") as HTMLTextAreaElement;
        if (!reasonInput?.value) {
          message.warning("请输入驳回原因");
          return Promise.reject();
        }
        
        try {
          const res = await workflowApi.executeTaskAction(
            task.instance_id,
            task.id,
            { action: "reject", comment: reasonInput.value }
          );
          
          if (res.code === 200) {
            message.success("已驳回");
            loadPendingTasks();
            loadInstances();
            loadStats();
          }
        } catch (error: any) {
          message.error(error.message || "操作失败");
        }
      }
    });
  };

  // 查看实例详情
  const viewInstanceDetail = async (instance: any) => {
    setInstanceDrawer({ visible: true, instance });
    await loadApprovalRecords(instance.id);
  };

  // 待办任务表格列
  const taskColumns: ColumnsType<WorkflowTask> = [
    {
      title: "任务名称",
      dataIndex: "task_name",
      key: "task_name",
      render: (text, record) => (
        <Space>
          {record.is_approval_task && <AuditOutlined style={{ color: "#faad14" }} />}
          {text}
        </Space>
      )
    },
    {
      title: "任务类型",
      dataIndex: "task_type",
      key: "task_type",
      render: (type) => (
        <Tag color="blue">{type}</Tag>
      )
    },
    {
      title: "所属流程",
      dataIndex: ["instance", "entity_type"],
      key: "entity_type",
      render: (type, record) => (
        <Space direction="vertical" size={0}>
          <Tag>{WORKFLOW_TYPE_MAP[type] || type}</Tag>
          <Text type="secondary" style={{ fontSize: 12 }}>
            ID: {record.instance?.entity_id}
          </Text>
        </Space>
      )
    },
    {
      title: "当前阶段",
      dataIndex: ["instance", "current_stage"],
      key: "current_stage",
      render: (stage) => <Tag>{stage}</Tag>
    },
    {
      title: "状态",
      dataIndex: "status",
      key: "status",
      render: (status) => {
        const info = TASK_STATUS_MAP[status] || { text: status, color: "default" };
        return <Badge status={info.color as any} text={info.text} />;
      }
    },
    {
      title: "截止日期",
      dataIndex: "due_date",
      key: "due_date",
      render: (date) => date ? dayjs(date).format("YYYY-MM-DD HH:mm") : "-"
    },
    {
      title: "操作",
      key: "action",
      render: (_, record) => (
        <Space>
          {record.instance && (
            <Button
              type="link"
              size="small"
              onClick={() => viewInstanceDetail(record.instance!)}
            >
              详情
            </Button>
          )}
          {record.status === "pending" && (
            <>
              <Button
                type="link"
                size="small"
                icon={<CheckCircleOutlined />}
                onClick={() => handleApprove(record)}
              >
                通过
              </Button>
              <Button
                type="link"
                size="small"
                danger
                icon={<CloseCircleOutlined />}
                onClick={() => handleReject(record)}
              >
                驳回
              </Button>
            </>
          )}
        </Space>
      )
    }
  ];

  // 实例表格列
  const instanceColumns: ColumnsType<WorkflowInstance> = [
    {
      title: "ID",
      dataIndex: "id",
      key: "id",
      width: 60
    },
    {
      title: "流程类型",
      dataIndex: "entity_type",
      key: "entity_type",
      render: (type) => WORKFLOW_TYPE_MAP[type] || type
    },
    {
      title: "关联ID",
      dataIndex: "entity_id",
      key: "entity_id",
      render: (id, record) => (
        <Button type="link" onClick={() => navigate(`/patents/${id}`)}>
          {id}
        </Button>
      )
    },
    {
      title: "当前阶段",
      dataIndex: "current_stage",
      key: "current_stage",
      render: (stage) => <Tag color="blue">{stage}</Tag>
    },
    {
      title: "状态",
      dataIndex: "status",
      key: "status",
      render: (status) => (
        <Tag color={STATUS_COLORS[status] || "default"}>
          {status === "in_progress" ? "进行中" : status === "completed" ? "已完成" : status}
        </Tag>
      )
    },
    {
      title: "开始时间",
      dataIndex: "started_at",
      key: "started_at",
      render: (date) => date ? dayjs(date).format("YYYY-MM-DD HH:mm") : "-"
    },
    {
      title: "截止日期",
      dataIndex: "due_date",
      key: "due_date",
      render: (date) => date ? (
        <Text type={dayjs(date).isBefore(dayjs()) ? "danger" : undefined}>
          {dayjs(date).format("YYYY-MM-DD HH:mm")}
        </Text>
      ) : "-"
    },
    {
      title: "操作",
      key: "action",
      render: (_, record) => (
        <Button type="link" onClick={() => viewInstanceDetail(record)}>
          查看详情
        </Button>
      )
    }
  ];

  return (
    <div style={{ padding: 24 }}>
      <Space direction="vertical" size="large" style={{ width: "100%" }}>
        <Title level={3} style={{ margin: 0 }}>
          <BankOutlined /> 工作流管理
        </Title>

        <Tabs
          activeKey={activeTab}
          onChange={setActiveTab}
          items={[
            // 概览
            {
              key: "overview",
              label: <span><DashboardOutlined /> 概览</span>,
              children: (
                <Row gutter={[16, 16]}>
                  <Col xs={24} sm={12} lg={6}>
                    <Card>
                      <Statistic
                        title="总流程数"
                        value={stats?.total_instances || 0}
                        prefix={<FileTextOutlined />}
                      />
                    </Card>
                  </Col>
                  <Col xs={24} sm={12} lg={6}>
                    <Card>
                      <Statistic
                        title="进行中"
                        value={stats?.in_progress_instances || 0}
                        prefix={<SyncOutlined spin />}
                        valueStyle={{ color: "#1890ff" }}
                      />
                    </Card>
                  </Col>
                  <Col xs={24} sm={12} lg={6}>
                    <Card>
                      <Statistic
                        title="待审批"
                        value={stats?.pending_tasks || 0}
                        prefix={<ClockCircleOutlined />}
                        valueStyle={{ color: "#faad14" }}
                      />
                    </Card>
                  </Col>
                  <Col xs={24} sm={12} lg={6}>
                    <Card>
                      <Statistic
                        title="已完成"
                        value={stats?.completed_instances || 0}
                        prefix={<CheckCircleOutlined />}
                        valueStyle={{ color: "#52c41a" }}
                      />
                    </Card>
                  </Col>
                  
                  <Col xs={24}>
                    <Card title="待审批任务">
                      <Table
                        columns={taskColumns}
                        dataSource={pendingTasks}
                        loading={tasksLoading}
                        rowKey="id"
                        pagination={{ pageSize: 5 }}
                        locale={{ emptyText: "暂无待审批任务" }}
                      />
                    </Card>
                  </Col>
                </Row>
              )
            },
            
            // 流程实例
            {
              key: "instances",
              label: <span><HistoryOutlined /> 流程实例</span>,
              children: (
                <Card>
                  <Table
                    columns={instanceColumns}
                    dataSource={instances}
                    loading={instancesLoading}
                    rowKey="id"
                    pagination={{
                      total: instanceTotal,
                      pageSize: 10,
                      showTotal: (total) => `共 ${total} 条`
                    }}
                  />
                </Card>
              )
            },
            
            // 工作流定义
            {
              key: "definitions",
              label: <span><SettingOutlined /> 流程定义</span>,
              children: (
                <Card
                  extra={
                    <Button type="primary" icon={<PlusOutlined />} onClick={() => openDefinitionModal()}>
                      新建工作流
                    </Button>
                  }
                >
                  <List
                    loading={definitionsLoading}
                    dataSource={definitions}
                    renderItem={(item) => (
                      <List.Item
                        actions={[
                          <Button type="link" key="edit" icon={<EditOutlined />} onClick={() => openDefinitionModal(item)}>
                            编辑
                          </Button>,
                          <Popconfirm title="确认删除此工作流定义？" onConfirm={() => handleDeleteDefinition(item.id)}>
                            <Button type="link" danger key="delete" icon={<DeleteOutlined />}>
                              删除
                            </Button>
                          </Popconfirm>
                        ]}
                      >
                        <List.Item.Meta
                          avatar={<Avatar icon={<FileTextOutlined />} />}
                          title={item.name}
                          description={
                            <Space>
                              <Tag>{WORKFLOW_TYPE_MAP[item.workflow_type] || item.workflow_type}</Tag>
                              <Tag color={item.is_active ? "green" : "red"}>
                                {item.is_active ? "激活" : "禁用"}
                              </Tag>
                              <Tag color={item.is_default ? "blue" : "default"}>
                                {item.is_default ? "默认" : ""}
                              </Tag>
                              {item.description && <Text type="secondary">{item.description}</Text>}
                            </Space>
                          }
                        />
                      </List.Item>
                    )}
                    locale={{ emptyText: "暂无工作流定义" }}
                  />
                </Card>
              )
            }
          ]}
        />
      </Space>

      {/* 实例详情抽屉 */}
      <Drawer
        title="流程详情"
        placement="right"
        width={600}
        open={instanceDrawer.visible}
        onClose={() => setInstanceDrawer({ visible: false, instance: null })}
      >
        {instanceDrawer.instance && (
          <Space direction="vertical" style={{ width: "100%" }} size="middle">
            <Descriptions bordered column={1} size="small">
              <Descriptions.Item label="流程ID">{instanceDrawer.instance?.id}</Descriptions.Item>
              <Descriptions.Item label="流程类型">
                {WORKFLOW_TYPE_MAP[instanceDrawer.instance?.entity_type || ''] || instanceDrawer.instance?.entity_type}
              </Descriptions.Item>
              <Descriptions.Item label="关联ID">
                <Button type="link" onClick={() => navigate(`/patents/${instanceDrawer.instance?.entity_id}`)}>
                  {instanceDrawer.instance?.entity_id}
                </Button>
              </Descriptions.Item>
              <Descriptions.Item label="当前阶段">
                <Tag color="blue">{instanceDrawer.instance?.current_stage}</Tag>
              </Descriptions.Item>
              <Descriptions.Item label="状态">
                <Tag color={STATUS_COLORS[instanceDrawer.instance?.status || '']}>
                  {instanceDrawer.instance?.status}
                </Tag>
              </Descriptions.Item>
              <Descriptions.Item label="开始时间">
                {instanceDrawer.instance?.started_at ? dayjs(instanceDrawer.instance.started_at).format("YYYY-MM-DD HH:mm") : "-"}
              </Descriptions.Item>
              <Descriptions.Item label="完成时间">
                {instanceDrawer.instance.completed_at ? dayjs(instanceDrawer.instance.completed_at).format("YYYY-MM-DD HH:mm") : "-"}
              </Descriptions.Item>
            </Descriptions>

            <Divider>阶段进度</Divider>
            <Steps
              current={instanceDrawer.instance.stage_history?.length || 0}
              direction="vertical"
              size="small"
            >
              {instanceDrawer.instance.stage_history?.map((stage: any, index: number) => (
                <Step
                  key={index}
                  title={stage.stage_id}
                  description={stage.entered_at ? dayjs(stage.entered_at).format("YYYY-MM-DD HH:mm") : ""}
                />
              ))}
              <Step
                title={instanceDrawer.instance.current_stage}
                status="process"
                description="当前阶段"
              />
            </Steps>

            <Divider>审批记录</Divider>
            <Timeline
              items={approvalRecords.map((record) => ({
                color: record.decision === "approved" ? "green" : "red",
                children: (
                  <div>
                    <Text strong>{record.approver_name || `审批人 #${record.approver_id}`}</Text>
                    <br />
                    <Text>
                      {record.decision === "approved" ? "✅ 批准" : "❌ 驳回"}
                      {record.comment && ` - ${record.comment}`}
                    </Text>
                    <br />
                    <Text type="secondary" style={{ fontSize: 12 }}>
                      {dayjs(record.decided_at).format("YYYY-MM-DD HH:mm:ss")}
                    </Text>
                  </div>
                )
              }))}
            />
          </Space>
        )}
      </Drawer>

      {/* 审批弹窗 */}
      <Modal
        title="审批通过"
        open={approveModal.visible}
        onOk={submitApprove}
        onCancel={() => {
          setApproveModal({ visible: false, task: null });
          approveForm.resetFields();
        }}
      >
        <Form form={approveForm} layout="vertical">
          <Form.Item name="comment" label="审批意见">
            <TextArea rows={3} placeholder="请输入审批意见（可选）" />
          </Form.Item>
        </Form>
      </Modal>

      {/* 工作流定义编辑弹窗 */}
      <Modal
        title={definitionModal.editData ? "编辑工作流定义" : "新建工作流定义"}
        open={definitionModal.visible}
        onOk={saveDefinition}
        onCancel={() => {
          setDefinitionModal({ visible: false, editData: null });
          definitionForm.resetFields();
        }}
        width={640}
      >
        <Form form={definitionForm} layout="vertical">
          <Form.Item name="name" label="工作流名称" rules={[{ required: true, message: "请输入工作流名称" }]}>
            <Input placeholder="如：专利审查工作流" />
          </Form.Item>
          
          <Form.Item name="description" label="描述">
            <TextArea rows={2} placeholder="工作流描述（可选）" />
          </Form.Item>
          
          <Form.Item name="workflow_type" label="工作流类型" rules={[{ required: true, message: "请选择工作流类型" }]}>
            <Select placeholder="选择工作流类型">
              <Select.Option value="patent_examination">专利审查</Select.Option>
              <Select.Option value="document_review">文档审批</Select.Option>
              <Select.Option value="general">通用流程</Select.Option>
            </Select>
          </Form.Item>
          
          <Row gutter={16}>
            <Col span={12}>
              <Form.Item name="is_default" label="设为默认" valuePropName="checked">
                <Switch />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item name="is_active" label="激活状态" valuePropName="checked">
                <Switch defaultChecked />
              </Form.Item>
            </Col>
          </Row>
          
          <Alert
            message="提示"
            description="新建工作流后，需要在专利详情页手动启动审查工作流才能生效。默认专利审查工作流包含7个阶段：申请提交、形式审查、形式审查审批、实质审查、实质审查审批、授权决定、专利授予。"
            type="info"
            showIcon
            style={{ marginBottom: 16 }}
          />
        </Form>
      </Modal>
    </div>
  );
}
