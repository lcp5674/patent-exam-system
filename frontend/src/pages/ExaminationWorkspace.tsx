import { useEffect, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import {
  Card, Row, Col, Button, Space, Typography, Spin, message, Tag, Tabs,
  Steps, Descriptions, List, Progress, Alert, Collapse, Divider, Empty, Select, Switch,
} from "antd";
import {
  ArrowLeftOutlined, PlayCircleOutlined, CheckCircleOutlined,
  CloseCircleOutlined, WarningOutlined, FileSearchOutlined,
  ExperimentOutlined, RobotOutlined, FileDoneOutlined, ThunderboltOutlined,
  BulbOutlined,
} from "@ant-design/icons";
import { patentApi } from "../services/patentApi";
import { examApi, OneClickExamResult } from "../services/examApi";
import { aiApi } from "../services/aiApi";
import { PatentAnalysisReport } from "../components/PatentAnalysisReport";

const { Title, Text, Paragraph } = Typography;
const { Option } = Select;

interface ExamResult {
  rule_name: string;
  display_name?: string;
  passed: boolean;
  confidence: number;
  issues: {
    severity: string;
    description?: string;
    message?: string;
    location?: string;
    legal_reference?: string;
    legal_basis?: string;
    original_content?: string;
    suggested_content?: string;
    context_before?: string;
    context_after?: string;
  }[];
  suggestions?: string[];
}

export default function ExaminationWorkspace() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [patent, setPatent] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [examRunning, setExamRunning] = useState(false);
  const [aiLoading, setAiLoading] = useState(false);
  const [aiProgress, setAiProgress] = useState<string>("");
  const [oneClickRunning, setOneClickRunning] = useState(false);
  const [currentStep, setCurrentStep] = useState(0);
  const [formalResult, setFormalResult] = useState<any>(null);
  const [substantiveResult, setSubstantiveResult] = useState<any>(null);
  const [aiAnalysis, setAiAnalysis] = useState<string>("");
  const [aiStructuredData, setAiStructuredData] = useState<any>(null);
  const [aiIsStructured, setAiIsStructured] = useState<boolean>(false);
  const [oneClickResult, setOneClickResult] = useState<OneClickExamResult | null>(null);
  const [selectedProvider, setSelectedProvider] = useState<string>("");
  const [enableLlm, setEnableLlm] = useState<boolean>(true);
  const [providers, setProviders] = useState<any[]>([]);

  useEffect(() => {
    if (id) {
      loadPatent(id);
      loadExamHistory(id);
    }
    loadProviders();
  }, [id]);

  const loadProviders = async () => {
    try {
      const res = await aiApi.getProviders();
      const list = res.providers || res || [];
      const enabledProviders = list.filter((p: any) => p.is_enabled);
      setProviders(enabledProviders);
    } catch {
      setProviders([]);
    }
  };

  const loadPatent = async (pid: string) => {
    setLoading(true);
    try {
      const p = await patentApi.getDetail(Number(pid));
      setPatent(p);
    } catch {
      message.error("加载专利信息失败");
    } finally {
      setLoading(false);
    }
  };

  const loadExamHistory = async (pid: string) => {
    try {
      const history = await examApi.getHistory(Number(pid));
      if (history && history.length > 0) {
        // 按时间排序，取最新的记录
        const sorted = [...history].sort((a, b) => 
          new Date(b.created_at || 0).getTime() - new Date(a.created_at || 0).getTime()
        );
        
        // 查找最近的形式审查记录
        const formalRecord = sorted.find(r => r.examination_type === "formal" && r.status === "completed");
        if (formalRecord?.result) {
          setFormalResult(formalRecord.result);
          setCurrentStep(1);
        }
        
        // 查找最近的实质审查记录
        const substantiveRecord = sorted.find(r => r.examination_type === "substantive" && r.status === "completed");
        if (substantiveRecord?.result) {
          setSubstantiveResult(substantiveRecord.result);
          setCurrentStep(2);
        }
        
        // 查找最近的AI分析记录
        const aiRecord = sorted.find(r => r.examination_type === "ai_analysis" && r.status === "completed");
        if (aiRecord?.result?.content) {
          setAiAnalysis(aiRecord.result.content);
          setAiStructuredData(aiRecord.result.structured_data || null);
          setAiIsStructured(aiRecord.result.structured === true);
          setCurrentStep(3);
        }
      }
    } catch {
      // History load failed, user can start fresh examination
    }
  };

  const runFormalExam = async () => {
    if (!id) return;
    setExamRunning(true);
    try {
      const res = await examApi.runFormal(Number(id), enableLlm, selectedProvider || undefined);
      setFormalResult(res);
      setCurrentStep(1);
      message.success("形式审查完成");
    } catch {
      message.error("形式审查执行失败");
    } finally {
      setExamRunning(false);
    }
  };

  const runSubstantiveExam = async () => {
    if (!id) return;
    setExamRunning(true);
    try {
      const res = await examApi.runSubstantive(Number(id), selectedProvider || undefined, enableLlm);
      setSubstantiveResult(res);
      setCurrentStep(2);
      message.success("实质审查完成");
    } catch {
      message.error("实质审查执行失败");
    } finally {
      setExamRunning(false);
    }
  };

  const runOneClickExam = async () => {
    if (!id) return;
    setOneClickRunning(true);
    try {
      const res = await examApi.runOneClick(Number(id), selectedProvider || undefined, enableLlm);
      setFormalResult(res.formal_result);
      setSubstantiveResult(res.substantive_result);
      if (res.ai_analysis?.content) {
        setAiAnalysis(res.ai_analysis.content);
        try {
          const parsed = JSON.parse(res.ai_analysis.content);
          setAiStructuredData(parsed);
          setAiIsStructured(true);
        } catch {
          setAiIsStructured(false);
        }
      }
      setCurrentStep(3);
      message.success("一键审查完成");
    } catch (err: any) {
      message.error(err?.response?.data?.detail || "一键审查执行失败");
    } finally {
      setOneClickRunning(false);
    }
  };

  const runAiAnalysis = async () => {
    if (!id) return;
    setAiLoading(true);
    setAiProgress("正在连接AI服务...");
    setAiAnalysis("");
    
    try {
      // 使用流式API获取实时进度
      await new Promise<void>((resolve, reject) => {
        aiApi.analyzeStream(
          {
            patent_id: Number(id),
            analysis_type: "comprehensive",
            provider: selectedProvider || undefined,
          },
          (data) => {
            if (data.status === "started") {
              setAiProgress("AI正在分析专利文档...");
            } else if (data.status === "streaming") {
              // 实时显示部分结果
              setAiProgress("AI正在生成分析报告...");
            } else if (data.status === "completed") {
              // 保存完整结果
              setAiAnalysis(data.content || "");
              setAiStructuredData(data.structured_data || null);
              setAiIsStructured(data.structured === true);
              setCurrentStep(3);
              setAiProgress("");
              message.success("AI分析完成");
              resolve();
            }
          },
          (error) => {
            console.error("AI分析失败:", error);
            message.error("AI分析执行失败");
            reject(error);
          }
        );
      });
    } catch {
      // 错误已在上方处理
    } finally {
      setAiLoading(false);
      setAiProgress("");
    }
  };

  const severityColor = (s: string) =>
    s === "error" ? "#ff4d4f" : s === "warning" ? "#faad14" : "#1677ff";
  const severityText = (s: string) =>
    s === "error" ? "严重" : s === "warning" ? "警告" : "建议";

  const renderExamResult = (result: any, title: string) => {
    if (!result) return <Empty description={`请先运行${title}`} />;
    // 兼容 results 和 rules 两种字段名
    const rules: ExamResult[] = result.results || result.rules || result || [];
    const passed = rules.filter((r) => r.passed).length;
    const total = rules.length;
    const overallPassed = result.overall_result === "pass" || result.passed === true || passed === total;

    return (
      <Space direction="vertical" size="middle" style={{ width: "100%" }}>
        <Alert
          type={overallPassed ? "success" : "warning"}
          message={`${title}结果: ${overallPassed ? "通过" : "存在问题"}`}
          description={`共 ${total} 项检查，通过 ${passed} 项，未通过 ${total - passed} 项${result.score != null ? `，得分: ${result.score}` : ""}`}
          showIcon
        />
        <Collapse
          items={rules.map((rule, idx) => ({
            key: String(idx),
            label: (
              <Space>
                {rule.passed ? <CheckCircleOutlined style={{ color: "#52c41a" }} /> : <CloseCircleOutlined style={{ color: "#ff4d4f" }} />}
                <span>{rule.display_name || rule.rule_name}</span>
                <Progress percent={Math.round(rule.confidence * 100)} size="small" style={{ width: 80 }} showInfo={false} />
                <Text type="secondary">{Math.round(rule.confidence * 100)}%</Text>
              </Space>
            ),
            children: rule.issues && rule.issues.length > 0 ? (
              <List dataSource={rule.issues} renderItem={(issue) => (
                <List.Item style={{ flexDirection: "column", alignItems: "flex-start", padding: "12px 0" }}>
                  <Space direction="vertical" size="small" style={{ width: "100%" }}>
                    <List.Item.Meta
                      avatar={<Tag color={severityColor(issue.severity)}>{severityText(issue.severity)}</Tag>}
                      title={issue.description || issue.message}
                      description={
                        <Space direction="vertical" size={0}>
                          {issue.location && <Text type="secondary">位置: {issue.location}</Text>}
                          {issue.legal_reference && <Text type="secondary">法律依据: {issue.legal_reference}</Text>}
                        </Space>
                      }
                    />
                    {/* 显示原始内容和建议修改内容 */}
                    {(issue.original_content || issue.suggested_content) && (
                      <Card size="small" style={{ width: "100%", marginTop: 8, background: "#fafafa" }}>
                        <Space direction="vertical" size="middle" style={{ width: "100%" }}>
                          {issue.original_content && issue.original_content !== "[无权利要求书]" && issue.original_content !== "[无说明书]" && issue.original_content !== "[无摘要]" && issue.original_content !== "[无附图]" && issue.original_content !== "[无此章节]" && issue.original_content !== "[无权利要求]" && issue.original_content !== "[只有从属权利要求]" && (
                            <div>
                              <Text strong style={{ color: "#ff4d4f", display: "block", marginBottom: 4 }}>⚠️ 原始内容:</Text>
                              <pre style={{ 
                                background: "#fff1f0", 
                                padding: 8, 
                                borderRadius: 4, 
                                border: "1px solid #ffa39e",
                                margin: 0,
                                maxHeight: 150,
                                overflow: "auto",
                                fontSize: 12,
                                whiteSpace: "pre-wrap",
                                wordBreak: "break-word",
                              }}>
                                {issue.context_before && <Text type="secondary">{issue.context_before}</Text>}
                                <Text strong style={{ background: "#ffccc7", padding: "0 2px" }}>{issue.original_content}</Text>
                                {issue.context_after && <Text type="secondary">{issue.context_after}</Text>}
                              </pre>
                            </div>
                          )}
                          {issue.suggested_content && (
                            <div>
                              <Text strong style={{ color: "#52c41a", display: "block", marginBottom: 4 }}>✓ 建议修改:</Text>
                              <pre style={{ 
                                background: "#f6ffed", 
                                padding: 8, 
                                borderRadius: 4, 
                                border: "1px solid #b7eb8f",
                                margin: 0,
                                fontSize: 12,
                                whiteSpace: "pre-wrap",
                                wordBreak: "break-word",
                              }}>
                                {issue.suggested_content}
                              </pre>
                            </div>
                          )}
                        </Space>
                      </Card>
                    )}
                  </Space>
                </List.Item>
              )} />
            ) : rule.suggestions && rule.suggestions.length > 0 ? (
              <List 
                size="small"
                dataSource={rule.suggestions} 
                renderItem={(suggestion) => (
                  <List.Item>
                    <Space>
                      <BulbOutlined style={{ color: "#1890ff" }} />
                      <Text>{suggestion}</Text>
                    </Space>
                  </List.Item>
                )} 
              />
            ) : (
              <Text type="success">检查通过，未发现问题</Text>
            ),
          }))}
        />
      </Space>
    );
  };

  if (loading) return <Spin size="large" style={{ display: "block", margin: "120px auto" }} />;
  if (!patent) return <Empty description="专利不存在" />;

  return (
    <Space direction="vertical" size="middle" style={{ width: "100%" }}>
      <Row justify="space-between" align="middle">
        <Col>
          <Space>
            <Button icon={<ArrowLeftOutlined />} onClick={() => navigate(`/patents/${id}`)}>返回</Button>
            <Title level={4} style={{ margin: 0 }}>审查工作台</Title>
          </Space>
        </Col>
      </Row>

      <Card size="small">
        <Descriptions column={{ xs: 1, sm: 2, lg: 4 }} size="small">
          <Descriptions.Item label="专利名称">{patent.title}</Descriptions.Item>
          <Descriptions.Item label="申请号">{patent.application_number || "-"}</Descriptions.Item>
          <Descriptions.Item label="申请人">{patent.applicant || "-"}</Descriptions.Item>
          <Descriptions.Item label="类型">{patent.patent_type === "utility_model" ? "实用新型" : patent.patent_type}</Descriptions.Item>
        </Descriptions>
      </Card>

      <Row gutter={16}>
        <Col xs={24} lg={6}>
          <Card title="审查流程" size="small">
            <Steps direction="vertical" current={currentStep} size="small" items={[
              { title: "形式审查", icon: <FileSearchOutlined />, description: "文档完整性与格式" },
              { title: "实质审查", icon: <ExperimentOutlined />, description: "规则引擎深度检查" },
              { title: "AI 智能分析", icon: <RobotOutlined />, description: "AI 辅助综合评估" },
              { title: "生成报告", icon: <FileDoneOutlined />, description: "输出审查意见书" },
            ]} />
            <Divider />
            <Space direction="vertical" style={{ width: "100%" }}>
              <Alert
                type="info"
                message="一键审查"
                description="自动完成形式审查、实质审查、AI分析，生成完整审查报告"
                style={{ marginBottom: 8 }}
              />
              <Select
                placeholder="选择AI提供商（可选）"
                value={selectedProvider}
                onChange={setSelectedProvider}
                allowClear
                style={{ width: "100%", marginBottom: 8 }}
              >
                <Option value="">默认提供商</Option>
                {providers.map((p: any) => (
                  <Option key={p.name} value={p.name}>
                    {p.display_name || p.name}
                    {p.is_default && <Tag color="blue" style={{ marginLeft: 8 }}>默认</Tag>}
                  </Option>
                ))}
              </Select>
              <div style={{ 
                display: 'flex', 
                alignItems: 'center', 
                justifyContent: 'space-between',
                padding: '8px 12px',
                background: enableLlm ? '#e6f4ff' : '#f5f5f5',
                borderRadius: 6,
                marginBottom: 8,
                border: `1px solid ${enableLlm ? '#91d5ff' : '#d9d9d9'}`
              }}>
                <Space>
                  <RobotOutlined style={{ color: enableLlm ? '#1677ff' : '#8c8c8c' }} />
                  <Text strong style={{ color: enableLlm ? '#1677ff' : '#8c8c8c' }}>LLM 增强</Text>
                </Space>
                <Switch 
                  checked={enableLlm} 
                  onChange={setEnableLlm}
                  checkedChildren="开"
                  unCheckedChildren="关"
                />
              </div>
              <Text type="secondary" style={{ display: 'block', marginBottom: 8, fontSize: 12 }}>
                {enableLlm 
                  ? "✓ 启用：使用 LLM 提升审查精确度、准确度和完整度"
                  : "关闭：仅使用静态规则检查"}
              </Text>
              <Button type="primary" danger block icon={<ThunderboltOutlined />}
                loading={oneClickRunning} onClick={runOneClickExam}>
                一键审查（完整流程）
              </Button>
              <Divider style={{ margin: "8px 0" }} />
              <Button type="primary" block icon={<FileSearchOutlined />}
                loading={examRunning && currentStep === 0} onClick={runFormalExam}>
                运行形式审查
              </Button>
              <Button block icon={<ExperimentOutlined />}
                loading={examRunning && currentStep === 1} onClick={runSubstantiveExam}
                disabled={!formalResult}>
                运行实质审查
              </Button>
              <Button block icon={<RobotOutlined />}
                loading={aiLoading} onClick={runAiAnalysis}>
                AI 智能分析
              </Button>
              {aiProgress && (
                <Alert 
                  message={aiProgress} 
                  type="info" 
                  showIcon 
                  style={{ marginTop: 8 }}
                />
              )}
              <Button block icon={<FileDoneOutlined />}
                onClick={() => navigate(`/reports?patent_id=${id}`)}
                disabled={!formalResult && !substantiveResult}>
                生成审查报告
              </Button>
            </Space>
          </Card>
        </Col>
        <Col xs={24} lg={18}>
          <Tabs defaultActiveKey="formal" items={[
            {
              key: "formal", label: "形式审查结果",
              children: renderExamResult(formalResult, "形式审查"),
            },
            {
              key: "substantive", label: "实质审查结果",
              children: renderExamResult(substantiveResult, "实质审查"),
            },
            {
              key: "ai", label: "AI 分析报告",
              children: aiAnalysis ? (
                aiIsStructured && aiStructuredData ? (
                  // 结构化渲染
                  <PatentAnalysisReport data={aiStructuredData} rawContent={aiAnalysis} />
                ) : (
                  // 纯文本渲染（向后兼容）
                  <Card>
                    <Paragraph style={{ whiteSpace: "pre-wrap" }}>{aiAnalysis}</Paragraph>
                  </Card>
                )
              ) : (
                <Empty description="请先运行AI分析" />
              ),
            },
          ]} />
        </Col>
      </Row>
    </Space>
  );
}
