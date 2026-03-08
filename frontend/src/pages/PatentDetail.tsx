import { useEffect, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import {
  Card, Descriptions, Tag, Typography, Space, Button, Tabs, Spin, message,
  Timeline, Empty, Divider, Row, Col, Collapse, Modal, Popconfirm,
} from "antd";
import {
  ArrowLeftOutlined, ExperimentOutlined, FileTextOutlined, HistoryOutlined,
  CheckCircleOutlined, CloseCircleOutlined, WarningOutlined, InfoCircleOutlined,
  PlayCircleOutlined, SyncOutlined,
} from "@ant-design/icons";
import { patentApi } from "../services/patentApi";
import { examApi } from "../services/examApi";
import { workflowApi } from "../services/workflowApi";

const { Title, Paragraph, Text } = Typography;

const statusColorMap: Record<string, string> = {
  draft: "default", pending: "processing", examining: "warning",
  completed: "success", granted: "success", approved: "success", rejected: "error",
};
const statusTextMap: Record<string, string> = {
  draft: "草稿", pending: "待审查", examining: "审查中",
  completed: "已完成", granted: "已授权", approved: "已通过", rejected: "已驳回",
};

export default function PatentDetail() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [patent, setPatent] = useState<any>(null);
  const [examHistory, setExamHistory] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [workflowLoading, setWorkflowLoading] = useState(false);

  useEffect(() => {
    if (id) loadPatent(id);
  }, [id]);

  const loadPatent = async (pid: string) => {
    setLoading(true);
    try {
      const [p, history] = await Promise.all([
        patentApi.getDetail(Number(pid)),
        examApi.getHistory(Number(pid)).catch(() => []),
      ]);
      setPatent(p);
      setExamHistory(history || []);
    } catch {
      message.error("加载专利详情失败");
    } finally {
      setLoading(false);
    }
  };

  // 启动审查工作流
  const handleStartWorkflow = async () => {
    if (!patent?.id) return;
    setWorkflowLoading(true);
    try {
      const res = await workflowApi.startPatentExamination(patent.id);
      if (res.code === 200) {
        message.success("审查工作流已启动");
        loadPatent(String(patent.id)); // 刷新专利状态
      }
    } catch (error: any) {
      message.error(error.message || "启动工作流失败");
    } finally {
      setWorkflowLoading(false);
    }
  };

  if (loading) return <Spin size="large" style={{ display: "block", margin: "120px auto" }} />;
  if (!patent) return <Empty description="专利不存在" />;

  const claimsList: string[] = [];

  // description from parsed_content
  const descriptionSections = patent.parsed_content?.structure || {};

  const resultIcon = (r: string) => {
    if (r === "pass") return <CheckCircleOutlined style={{ color: "#52c41a" }} />;
    if (r === "fail") return <CloseCircleOutlined style={{ color: "#ff4d4f" }} />;
    return <WarningOutlined style={{ color: "#faad14" }} />;
  };

  return (
    <Space direction="vertical" size="middle" style={{ width: "100%" }}>
      <Row justify="space-between" align="middle">
        <Col>
          <Space>
            <Button icon={<ArrowLeftOutlined />} onClick={() => navigate("/patents")}>返回列表</Button>
            <Title level={4} style={{ margin: 0 }}>{patent.title}</Title>
            <Tag color={statusColorMap[patent.status]}>{statusTextMap[patent.status] || patent.status}</Tag>
          </Space>
        </Col>
        <Col>
          <Space>
            <Button 
              type="primary" 
              icon={<PlayCircleOutlined />} 
              onClick={handleStartWorkflow}
              loading={workflowLoading}
            >
              启动审查工作流
            </Button>
            <Button type="primary" icon={<ExperimentOutlined />}
              onClick={() => navigate(`/examination/${patent.id}`)}>
              开始审查
            </Button>
          </Space>
        </Col>
      </Row>

      <Tabs defaultActiveKey="info" items={[
        {
          key: "info", label: <span><FileTextOutlined /> 基本信息</span>,
          children: (
            <Space direction="vertical" size="middle" style={{ width: "100%" }}>
              <Card>
                <Descriptions column={{ xs: 1, sm: 2, lg: 3 }} bordered size="small">
                  <Descriptions.Item label="申请号">{patent.application_number || "-"}</Descriptions.Item>
                  <Descriptions.Item label="专利类型">{patent.patent_type === "utility_model" ? "实用新型" : patent.patent_type === "invention" ? "发明" : "外观设计"}</Descriptions.Item>
                  <Descriptions.Item label="申请日">{patent.application_date || "-"}</Descriptions.Item>
                  <Descriptions.Item label="申请人">{patent.applicant || "-"}</Descriptions.Item>
                  <Descriptions.Item label="发明人">{patent.inventor || "-"}</Descriptions.Item>
                  <Descriptions.Item label="代理机构">{patent.agent || "-"}</Descriptions.Item>
                  <Descriptions.Item label="IPC分类号" span={3}>{patent.ipc_classification || "-"}</Descriptions.Item>
                </Descriptions>
              </Card>

              {patent.abstract && (
                <Card title="摘要" size="small">
                  <Paragraph>{patent.abstract}</Paragraph>
                </Card>
              )}

              {claimsList.length > 0 && (
                <Card title={`权利要求书 (${claimsList.length} 项)`} size="small">
                  <Collapse items={claimsList.map((c, i) => ({
                    key: String(i),
                    label: `权利要求 ${i + 1}`,
                    children: <Paragraph style={{ whiteSpace: "pre-wrap" }}>{c.trim()}</Paragraph>,
                  }))} />
                </Card>
              )}

              {Object.keys(descriptionSections).length > 0 && (
                <Card title="说明书" size="small">
                  <Collapse items={Object.entries(descriptionSections).map(([key, val]) => ({
                    key,
                    label: key,
                    children: <Paragraph style={{ whiteSpace: "pre-wrap" }}>{val as string}</Paragraph>,
                  }))} />
                </Card>
              )}
            </Space>
          ),
        },
        {
          key: "history", label: <span><HistoryOutlined /> 审查记录</span>,
          children: examHistory.length === 0 ? (
            <Empty description="暂无审查记录" />
          ) : (
            <Timeline items={examHistory.map((exam) => ({
              dot: resultIcon(exam.overall_result || "pending"),
              children: (
                <Card size="small" style={{ marginBottom: 8 }}>
                  <Row justify="space-between">
                    <Col>
                      <Space>
                        <Text strong>{exam.examination_type === "formal" ? "形式审查" : "实质审查"}</Text>
                        <Tag color={exam.overall_result === "pass" ? "success" : exam.overall_result === "fail" ? "error" : "warning"}>
                          {exam.overall_result === "pass" ? "通过" : exam.overall_result === "fail" ? "不通过" : "待定"}
                        </Tag>
                        {exam.score != null && <Text type="secondary">得分: {exam.score}</Text>}
                      </Space>
                    </Col>
                    <Col>
                      <Text type="secondary">{exam.created_at ? new Date(exam.created_at).toLocaleString("zh-CN", { year: "numeric", month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit", second: "2-digit" }) : ""}</Text>
                    </Col>
                  </Row>
                  {exam.summary && (
                    <Paragraph type="secondary" style={{ marginTop: 8, marginBottom: 0 }} ellipsis={{ rows: 3, expandable: true }}>
                      {exam.summary}
                    </Paragraph>
                  )}
                </Card>
              ),
            }))} />
          ),
        },
      ]} />
    </Space>
  );
}
