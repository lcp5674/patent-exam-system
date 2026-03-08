import { useEffect, useState } from "react";
import { Row, Col, Card, Statistic, Typography, Table, Tag, Space, Progress, Spin } from "antd";
import {
  FileTextOutlined, AuditOutlined, CheckCircleOutlined, ClockCircleOutlined,
  RiseOutlined, RobotOutlined,
} from "@ant-design/icons";
import { patentApi } from "../services/patentApi";
import { useNavigate } from "react-router-dom";

const { Title, Text } = Typography;

interface DashboardStats {
  total_patents: number;
  pending_examination: number;
  completed_examination: number;
  ai_analyses_today: number;
  pass_rate: number;
  recent_patents: any[];
}

export default function Dashboard() {
  const [loading, setLoading] = useState(true);
  const [stats, setStats] = useState<DashboardStats>({
    total_patents: 0, pending_examination: 0, completed_examination: 0,
    ai_analyses_today: 0, pass_rate: 0, recent_patents: [],
  });
  const navigate = useNavigate();

  useEffect(() => {
    loadDashboard();
  }, []);

  const loadDashboard = async () => {
    try {
      const [statRes, listRes] = await Promise.all([
        patentApi.getStatistics().catch(() => ({
          total: 0, pending: 0, completed: 0, ai_today: 0, pass_rate: 0,
        })),
        patentApi.getList({ page: 1, page_size: 5 }).catch(() => ({ items: [], total: 0 })),
      ]);
      setStats({
        total_patents: statRes.total || 0,
        pending_examination: statRes.pending || 0,
        completed_examination: statRes.completed || 0,
        ai_analyses_today: statRes.ai_today || 0,
        pass_rate: statRes.pass_rate || 0,
        recent_patents: listRes.items || [],
      });
    } finally {
      setLoading(false);
    }
  };

  const statusColorMap: Record<string, string> = {
    draft: "default", pending: "processing", examining: "warning",
    completed: "success", granted: "success", approved: "success", rejected: "error",
  };
  const statusTextMap: Record<string, string> = {
    draft: "草稿", pending: "待审查", examining: "审查中",
    completed: "已完成", granted: "已授权", approved: "已通过", rejected: "已驳回",
  };

  const columns = [
    { title: "申请号", dataIndex: "application_number", key: "application_number",
      render: (t: string, r: any) => <a onClick={() => navigate(`/patents/${r.id}`)}>{t}</a> },
    { title: "专利名称", dataIndex: "title", key: "title", ellipsis: true },
    { title: "申请人", dataIndex: "applicant", key: "applicant" },
    { title: "状态", dataIndex: "status", key: "status",
      render: (s: string) => <Tag color={statusColorMap[s]}>{statusTextMap[s] || s}</Tag> },
    { title: "提交时间", dataIndex: "created_at", key: "created_at",
      render: (t: string) => t ? new Date(t).toLocaleDateString("zh-CN") : "-" },
  ];

  if (loading) return <Spin size="large" style={{ display: "block", margin: "120px auto" }} />;

  return (
    <Space direction="vertical" size="large" style={{ width: "100%" }}>
      <Title level={4} style={{ margin: 0 }}>工作台</Title>
      <Row gutter={[16, 16]}>
        <Col xs={24} sm={12} lg={6}>
          <Card hoverable>
            <Statistic title="专利总数" value={stats.total_patents}
              prefix={<FileTextOutlined style={{ color: "#1677ff" }} />} />
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <Card hoverable>
            <Statistic title="待审查" value={stats.pending_examination}
              prefix={<ClockCircleOutlined style={{ color: "#faad14" }} />} />
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <Card hoverable>
            <Statistic title="已完成" value={stats.completed_examination}
              prefix={<CheckCircleOutlined style={{ color: "#52c41a" }} />} />
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <Card hoverable>
            <Statistic title="今日AI分析" value={stats.ai_analyses_today}
              prefix={<RobotOutlined style={{ color: "#722ed1" }} />} />
          </Card>
        </Col>
      </Row>

      <Row gutter={[16, 16]}>
        <Col xs={24} lg={16}>
          <Card title="最近专利申请" extra={<a onClick={() => navigate("/patents")}>查看全部</a>}>
            <Table columns={columns} dataSource={stats.recent_patents}
              rowKey="id" pagination={false} size="small" />
          </Card>
        </Col>
        <Col xs={24} lg={8}>
          <Card title="审查通过率">
            <div style={{ textAlign: "center", padding: "20px 0" }}>
              <Progress type="dashboard" percent={stats.pass_rate}
                format={(p) => `${p}%`} strokeColor={{ "0%": "#108ee9", "100%": "#87d068" }} />
              <div style={{ marginTop: 16 }}>
                <Text type="secondary">基于已完成审查的统计</Text>
              </div>
            </div>
          </Card>
          <Card title="快速操作" style={{ marginTop: 16 }}>
            <Space direction="vertical" style={{ width: "100%" }}>
              <Card.Grid style={{ width: "50%", textAlign: "center", cursor: "pointer" }}
                onClick={() => navigate("/patents")}>
                <FileTextOutlined style={{ fontSize: 24, color: "#1677ff" }} />
                <div style={{ marginTop: 8 }}>专利管理</div>
              </Card.Grid>
              <Card.Grid style={{ width: "50%", textAlign: "center", cursor: "pointer" }}
                onClick={() => navigate("/ai")}>
                <RobotOutlined style={{ fontSize: 24, color: "#722ed1" }} />
                <div style={{ marginTop: 8 }}>AI 助手</div>
              </Card.Grid>
              <Card.Grid style={{ width: "50%", textAlign: "center", cursor: "pointer" }}
                onClick={() => navigate("/rules")}>
                <AuditOutlined style={{ fontSize: 24, color: "#faad14" }} />
                <div style={{ marginTop: 8 }}>规则引擎</div>
              </Card.Grid>
              <Card.Grid style={{ width: "50%", textAlign: "center", cursor: "pointer" }}
                onClick={() => navigate("/reports")}>
                <RiseOutlined style={{ fontSize: 24, color: "#52c41a" }} />
                <div style={{ marginTop: 8 }}>报告中心</div>
              </Card.Grid>
            </Space>
          </Card>
        </Col>
      </Row>
    </Space>
  );
}
