import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { Card, Row, Col, Statistic, List, Tag, Button, Space, Typography, Empty, Badge, Spin, Select, DatePicker, Tabs } from "antd";
import { ExperimentOutlined, ClockCircleOutlined, CheckCircleOutlined, CloseCircleOutlined, PlayCircleOutlined, FileTextOutlined, ArrowRightOutlined } from "@ant-design/icons";
import { workflowApi } from "../services/workflowApi";
import { patentApi } from "../services/patentApi";
import dayjs from "dayjs";

const { Title, Text, Paragraph } = Typography;

interface TaskItem {
  id: number;
  task_name: string;
  task_type: string;
  status: string;
  assignee?: string;
  patent_id?: number;
  patent_name?: string;
  created_at: string;
  due_date?: string | null;
}

interface InstanceItem {
  id: number;
  workflow_definition_id: number;
  entity_type: string;
  entity_id: number;
  status: string;
  current_stage: string;
  started_at: string | null;
  completed_at?: string | null;
}

export default function ExaminationDashboard() {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [stats, setStats] = useState<any>({});
  const [pendingTasks, setPendingTasks] = useState<TaskItem[]>([]);
  const [instances, setInstances] = useState<InstanceItem[]>([]);
  const [recentPatents, setRecentPatents] = useState<any[]>([]);

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    setLoading(true);
    try {
      // 加载工作流统计
      const statsRes = await workflowApi.getStats();
      if (statsRes.code === 200) {
        setStats(statsRes.data);
      }
    } catch (e) {
      console.error("加载统计数据失败:", e);
    }
    try {
      // 加载待办任务
      const tasksRes = await workflowApi.getMyTasks({ status: "pending" });
      if (tasksRes.code === 200) {
        setPendingTasks(tasksRes.data || []);
      }
    } catch (e) {
      console.error("加载任务失败:", e);
    }
    try {
      // 加载工作流实例
      const instancesRes = await workflowApi.getInstances({ limit: 10 });
      if (instancesRes.code === 200) {
        setInstances(instancesRes.data || []);
      }
    } catch (e) {
      console.error("加载实例失败:", e);
    }
    try {
      // 加载最近的专利
      const patentsRes = await patentApi.getList({ page: 1, page_size: 10 });
      if (patentsRes.code === 200) {
        setRecentPatents(patentsRes.data || []);
      }
    } catch (e) {
      console.error("加载专利失败:", e);
    }
    setLoading(false);
  };

  const handleStartExam = (patentId: number) => {
    navigate(`/examination/${patentId}`);
  };

  const statusColors: Record<string, string> = {
    pending: "orange",
    in_progress: "blue",
    completed: "green",
    cancelled: "red",
    overdue: "red"
  };

  const statusLabels: Record<string, string> = {
    pending: "待处理",
    in_progress: "进行中",
    completed: "已完成",
    cancelled: "已取消",
    overdue: "已逾期"
  };

  const taskTypeLabels: Record<string, string> = {
    submission: "申请提交",
    review: "审查",
    approval: "审批",
    verification: "验证"
  };

  if (loading) {
    return <div style={{ display: "flex", justifyContent: "center", padding: 100 }}><Spin size="large" /></div>;
  }

  return (
    <div style={{ padding: "24px" }}>
      <Title level={2} style={{ marginBottom: 24 }}>
        <ExperimentOutlined style={{ marginRight: 8 }} />
        审查工作台
      </Title>

      <Row gutter={[16, 16]}>
        <Col xs={24} sm={12} md={6}>
          <Card>
            <Statistic
              title="待处理任务"
              value={stats.pending_tasks || 0}
              valueStyle={{ color: "#faad14" }}
              prefix={<ClockCircleOutlined />}
            />
          </Card>
        </Col>
        <Col xs={24} sm={12} md={6}>
          <Card>
            <Statistic
              title="进行中流程"
              value={stats.in_progress_instances || 0}
              valueStyle={{ color: "#1890ff" }}
              prefix={<PlayCircleOutlined />}
            />
          </Card>
        </Col>
        <Col xs={24} sm={12} md={6}>
          <Card>
            <Statistic
              title="已完成流程"
              value={stats.completed_instances || 0}
              valueStyle={{ color: "#52c41a" }}
              prefix={<CheckCircleOutlined />}
            />
          </Card>
        </Col>
        <Col xs={24} sm={12} md={6}>
          <Card>
            <Statistic
              title="已逾期任务"
              value={stats.overdue_instances || 0}
              valueStyle={{ color: "#ff4d4f" }}
              prefix={<CloseCircleOutlined />}
            />
          </Card>
        </Col>
      </Row>

      <Row gutter={[16, 16]} style={{ marginTop: 16 }}>
        <Col xs={24} lg={12}>
          <Card 
            title={<><ClockCircleOutlined /> 待审批任务</>}
            extra={<Button type="link" onClick={() => navigate("/workflow")}>查看全部</Button>}
          >
            {pendingTasks.length === 0 ? (
              <Empty description="暂无待处理任务" />
            ) : (
              <List
                dataSource={pendingTasks}
                renderItem={(task) => (
                  <List.Item
                    actions={[
                      <Button 
                        type="link" 
                        onClick={() => task.patent_id && navigate(`/examination/${task.patent_id}`)}
                        disabled={!task.patent_id}
                      >
                        处理 <ArrowRightOutlined />
                      </Button>
                    ]}
                  >
                    <List.Item.Meta
                      title={
                        <Space>
                          <Tag color={statusColors[task.status]}>{statusLabels[task.status]}</Tag>
                          <Text strong>{task.task_name}</Text>
                        </Space>
                      }
                      description={
                        <Space direction="vertical" size={0}>
                          {task.patent_name && <Text>专利: {task.patent_name}</Text>}
                          <Text type="secondary">
                            {task.created_at ? dayjs(task.created_at).format("YYYY-MM-DD HH:mm") : ""}
                          </Text>
                        </Space>
                      }
                    />
                  </List.Item>
                )}
              />
            )}
          </Card>
        </Col>

        <Col xs={24} lg={12}>
          <Card 
            title={<><FileTextOutlined /> 选择专利开始审查</>}
          >
            <List
              dataSource={recentPatents}
              renderItem={(patent) => (
                <List.Item
                  actions={[
                    <Button 
                      type="primary"
                      icon={<ExperimentOutlined />}
                      onClick={() => handleStartExam(patent.id)}
                    >
                      开始审查
                    </Button>
                  ]}
                >
                  <List.Item.Meta
                    title={patent.title || patent.application_number || `专利 #${patent.id}`}
                    description={
                      <Space>
                        <Tag>{patent.status || "待审查"}</Tag>
                        <Text type="secondary">
                          申请号: {patent.application_number || "-"}
                        </Text>
                      </Space>
                    }
                  />
                </List.Item>
              )}
              locale={{ emptyText: "暂无专利数据" }}
            />
            <div style={{ marginTop: 16, textAlign: "center" }}>
              <Button type="link" onClick={() => navigate("/patents")}>
                查看全部专利 <ArrowRightOutlined />
              </Button>
            </div>
          </Card>
        </Col>
      </Row>

      <Card 
        title={<><PlayCircleOutlined /> 进行中的工作流</>} 
        style={{ marginTop: 16 }}
        extra={<Button type="link" onClick={() => navigate("/workflow")}>查看全部</Button>}
      >
        {instances.filter(i => i.status === "in_progress").length === 0 ? (
          <Empty description="暂无进行中的工作流" />
        ) : (
          <List
            dataSource={instances.filter(i => i.status === "in_progress")}
            renderItem={(instance) => (
              <List.Item>
                <List.Item.Meta
                  title={`${instance.entity_type} - ${instance.current_stage}`}
                  description={
                    <Space>
                      <Tag color="blue">{statusLabels[instance.status]}</Tag>
                      <Text type="secondary">
                        开始时间: {instance.started_at ? dayjs(instance.started_at).format("YYYY-MM-DD HH:mm") : "-"}
                      </Text>
                    </Space>
                  }
                />
              </List.Item>
            )}
          />
        )}
      </Card>
    </div>
  );
}
