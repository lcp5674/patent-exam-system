import { useState, useEffect } from "react";
import { useSearchParams } from "react-router-dom";
import {
  Card, Row, Col, Typography, Space, Button, Select, Form, Input, InputNumber,
  message, Spin, Divider, Table, Tag, Empty, Tabs, Timeline, Avatar, Modal, Switch,
  Upload, Alert, Checkbox,
} from "antd";
const { TextArea } = Input;
import {
  FileTextOutlined, FileDoneOutlined, CloseCircleOutlined,
  DownloadOutlined, PrinterOutlined, HistoryOutlined, CheckCircleOutlined, ClockCircleOutlined,
  PlusOutlined, EditOutlined, DeleteOutlined, SettingOutlined, UploadOutlined,
  ArrowUpOutlined, ArrowDownOutlined,
} from "@ant-design/icons";
import { reportApi, ReportTemplate, SectionConfig, ReportHistory } from "../services/reportApi";
import { examApi } from "../services/examApi";
import { patentApi } from "../services/patentApi";

const { Title, Paragraph, Text } = Typography;

const reportTypes = [
  { value: "examination_opinion", label: "审查意见通知书", icon: <FileTextOutlined />, color: "#1677ff" },
  { value: "approval_notice", label: "授权通知书", icon: <FileDoneOutlined />, color: "#52c41a" },
  { value: "rejection_decision", label: "驳回决定书", icon: <CloseCircleOutlined />, color: "#ff4d4f" },
];

// 默认模板内容
const defaultTemplates: Record<string, string> = {
  opinion_notice: `━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
           中华人民共和国国家知识产权局
              审查意见通知书
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

申请号：{{application_number}}
发明名称：{{title}}
申请人：{{applicant}}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

【审查意见】

经审查，该实用新型专利申请存在以下问题：
{{issues_text}}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

【审查结论】

{{conclusion}}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

【答复要求】

请申请人在收到本通知书之日起两个月内，针对上述审查意见，
对申请文件进行修改，或者对审查意见陈述意见。

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
审查员：{{examiner}}
日期：{{date}}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━`,
  grant_notice: `━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
           中华人民共和国国家知识产权局
               授权通知书
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

申请号：{{application_number}}
发明名称：{{title}}
申请人：{{applicant}}

【授权决定】

经审查，该实用新型专利申请符合《中华人民共和国专利法》
及《专利法实施细则》的有关规定，决定授予实用新型专利权。

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
审查员：{{examiner}}
日期：{{date}}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━`,
  rejection: `━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
           中华人民共和国国家知识产权局
              驳回决定书
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

申请号：{{application_number}}
发明名称：{{title}}
申请人：{{applicant}}

【驳回理由】
{{reasons}}

【复审程序告知】
申请人对本决定不服的，可以自收到本决定之日起三个月内，
向国家知识产权局请求复审。

审查员：{{examiner}}
日期：{{date}}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━`,
};

export default function Reports() {
  const [searchParams] = useSearchParams();
  const initialPatentId = searchParams.get("patent_id") || "";
  const [loading, setLoading] = useState(false);
  const [reportContent, setReportContent] = useState<string>("");
  const [reportHistory, setReportHistory] = useState<any[]>([]);
  const [savedReports, setSavedReports] = useState<ReportHistory[]>([]);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [selectedExamId, setSelectedExamId] = useState<number | null>(null);
  const [selectedReportId, setSelectedReportId] = useState<number | null>(null);
  const [activeTab, setActiveTab] = useState("generate");
  const [templates, setTemplates] = useState<ReportTemplate[]>([]);
  const [templatesLoading, setTemplatesLoading] = useState(false);
  const [templateModalVisible, setTemplateModalVisible] = useState(false);
  const [editingTemplate, setEditingTemplate] = useState<ReportTemplate | null>(null);
  const [patents, setPatents] = useState<any[]>([]);
  const [patentsLoading, setPatentsLoading] = useState(false);
  const [form] = Form.useForm();
  const [templateForm] = Form.useForm();

  // Fetch templates on load
  useEffect(() => {
    fetchTemplates();
    loadPatents();
  }, []);

  // 加载专利列表
  const loadPatents = async () => {
    setPatentsLoading(true);
    try {
      const res = await patentApi.getList({ page: 1, page_size: 100 });
      console.log("报告中心-专利列表API返回:", res);
      const list = res.items || res.data?.items || [];
      console.log("报告中心-专利列表数据:", list);
      setPatents(list);
    } catch (err) {
      console.error("Failed to fetch patents:", err);
    } finally {
      setPatentsLoading(false);
    }
  };

  // 从URL获取初始专利ID，如果没有则undefined
  const getInitialPatentId = () => {
    if (!initialPatentId) return undefined;
    const pid = Number(initialPatentId);
    return isNaN(pid) ? undefined : pid;
  };

  // 当从URL参数或下拉选择改变专利时，刷新历史记录和报告
  const [currentPatentId, setCurrentPatentId] = useState<number | undefined>(getInitialPatentId());

  // 当 currentPatentId 变化时，重新加载历史记录和报告
  useEffect(() => {
    if (!currentPatentId) {
      setReportHistory([]);
      setSavedReports([]);
      return;
    }
    
    const fetchHistory = async () => {
      setHistoryLoading(true);
      try {
        const historyData = await examApi.getHistory(currentPatentId);
        if (Array.isArray(historyData)) {
          setReportHistory(historyData);
        }
      } catch (err) {
        console.error("Failed to fetch history:", err);
      } finally {
        setHistoryLoading(false);
      }
    };
    
    const fetchSavedReports = async () => {
      try {
        const reports = await reportApi.getReportHistory(currentPatentId);
        setSavedReports(reports);
      } catch (err) {
        console.error("Failed to fetch saved reports:", err);
      }
    };
    
    fetchHistory();
    fetchSavedReports();
  }, [currentPatentId]);
  
  // 当专利选择改变时，更新 currentPatentId
  const handlePatentChange = (patentId: number | null | undefined) => {
    setCurrentPatentId(patentId ?? undefined);
  };

  const fetchTemplates = async () => {
    setTemplatesLoading(true);
    try {
      const data = await reportApi.getTemplates();
      setTemplates(data);
    } catch (err) {
      console.error("Failed to fetch templates:", err);
    } finally {
      setTemplatesLoading(false);
    }
  };

  const getTemplatesForType = (reportType: string): ReportTemplate[] => {
    const typeMap: Record<string, string> = {
      examination_opinion: "opinion_notice",
      approval_notice: "grant_notice",
      rejection_decision: "rejection",
    };
    const templateType = typeMap[reportType];
    return templates.filter(t => t.template_type === templateType);
  };

  const generateReport = async (values: any) => {
    setLoading(true);
    try {
      const res = await reportApi.generate({
        patent_id: Number(values.patent_id),
        report_type: values.report_type,
        examination_id: values.examination_id ? Number(values.examination_id) : undefined,
        template_id: values.template_id ? Number(values.template_id) : undefined,
      });
      setReportContent(res.content || res.report || "报告生成完成");
      message.success("报告生成成功");
      
      // 如果返回了 report_id，刷新保存的报告列表
      if (res.report_id) {
        const reports = await reportApi.getReportHistory(Number(values.patent_id));
        setSavedReports(reports);
        setSelectedReportId(res.report_id);
      }
    } catch {
      message.error("报告生成失败，请确认专利ID和审查记录是否存在");
    } finally {
      setLoading(false);
    }
  };

  const handleDownload = () => {
    if (!reportContent) return;
    const blob = new Blob([reportContent], { type: "text/plain;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `审查报告_${new Date().toISOString().slice(0, 10)}.txt`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const handlePrint = () => {
    if (!reportContent) return;
    const printWindow = window.open("", "_blank");
    if (printWindow) {
      printWindow.document.write(`
        <html><head><title>审查报告</title>
        <style>body{font-family:SimSun,serif;padding:40px;line-height:1.8;white-space:pre-wrap;}</style>
        </head><body>${reportContent}</body></html>
      `);
      printWindow.document.close();
      printWindow.print();
    }
  };

  // 在 Form 内部使用的 BlockEditor Wrapper
  const BlockEditorWrapper = () => {
    const wrapperTemplateType = Form.useWatch("template_type", templateForm) || "opinion_notice";
    
    const handleChange = (sections: SectionConfig[]) => {
      templateForm.setFieldValue("section_config", sections);
    };
    
    return <BlockEditor templateType={wrapperTemplateType} onChange={handleChange} />;
  };

  return (
    <Space direction="vertical" size="middle" style={{ width: "100%" }}>
      <Title level={4} style={{ margin: 0 }}>报告中心</Title>

      <Tabs defaultActiveKey="generate" items={[
        {
          key: "generate", label: "生成报告",
          children: (
            <Row gutter={16}>
              <Col xs={24} lg={8}>
                <Card title="报告参数" size="small">
                  <Form form={form} layout="vertical" onFinish={generateReport}
                    initialValues={{ patent_id: getInitialPatentId(), report_type: "examination_opinion" }}>
                    <Form.Item name="patent_id" label="选择专利" rules={[{ required: true, message: "请选择专利" }]}>
                      <Select
                        style={{ width: "100%" }}
                        placeholder={patentsLoading ? "加载中..." : "请选择要生成报告的专利"}
                        showSearch
                        optionFilterProp="label"
                        loading={patentsLoading}
                        onChange={handlePatentChange}
                        allowClear
                        notFoundContent={!patentsLoading && patents.length === 0 ? "暂无专利，请先上传专利文件" : undefined}
                        options={patents.map((p) => ({
                          value: p.id,
                          label: `${p.title} (${p.application_number})`,
                        }))}
                      />
                    </Form.Item>
                    <Form.Item name="report_type" label="报告类型" rules={[{ required: true }]}>
                      <Select options={reportTypes.map((t) => ({
                        value: t.value,
                        label: <Space>{t.icon}<span>{t.label}</span></Space>,
                      }))} />
                    </Form.Item>
                    <Form.Item name="examination_id" label="审查记录">
                      <Select 
                        style={{ width: "100%" }} 
                        placeholder="可选，选择要关联的审查记录"
                        allowClear
                        disabled={!currentPatentId}
                        loading={historyLoading}
                        options={reportHistory.map((exam) => ({
                          value: exam.id,
                          label: `${exam.examination_type === "formal" ? "形式审查" : exam.examination_type === "substantive" ? "实质审查" : "一键审查"} - ${exam.created_at ? new Date(exam.created_at).toLocaleString("zh-CN") : ""}`,
                        }))}
                      />
                    </Form.Item>
                    <Form.Item name="template_id" label="报告模板">
                      <Select 
                        placeholder="默认模板（系统内置）" 
                        allowClear
                        loading={templatesLoading}
                        options={[
                          { value: 0, label: "默认模板（系统内置）", isDefault: true },
                          ...getTemplatesForType(form.getFieldValue("report_type")).map(t => ({
                            value: t.id,
                            label: t.is_default ? `${t.template_name} ★` : t.template_name,
                          }))
                        ]}
                      />
                    </Form.Item>
                    <Form.Item>
                      <Button type="primary" htmlType="submit" block loading={loading}>
                        生成报告
                      </Button>
                    </Form.Item>
                  </Form>

                  <Divider />

                  <Title level={5}>报告类型说明</Title>
                  <Space direction="vertical" size="small" style={{ width: "100%" }}>
                    {reportTypes.map((rt) => (
                      <Card key={rt.value} size="small" style={{ borderLeft: `3px solid ${rt.color}` }}>
                        <Space>
                          {rt.icon}
                          <div>
                            <Text strong>{rt.label}</Text>
                            <br />
                            <Text type="secondary" style={{ fontSize: 12 }}>
                              {rt.value === "examination_opinion"
                                ? "审查过程中向申请人发出的审查意见"
                                : rt.value === "approval_notice"
                                  ? "审查通过后发出的授权通知"
                                  : "审查不通过时发出的驳回决定"}
                            </Text>
                          </div>
                        </Space>
                      </Card>
                    ))}
                  </Space>
                </Card>
              </Col>
              <Col xs={24} lg={16}>
                <Card title="报告预览"
                  extra={reportContent && (
                    <Space>
                      <Button size="small" icon={<DownloadOutlined />} onClick={handleDownload}>下载</Button>
                      <Button size="small" icon={<PrinterOutlined />} onClick={handlePrint}>打印</Button>
                    </Space>
                  )}
                  styles={{ body: { minHeight: 500 } }}>
                  {loading ? (
                    <div style={{ textAlign: "center", padding: "100px 0" }}>
                      <Spin size="large" />
                      <div style={{ marginTop: 16 }}><Text type="secondary">正在生成报告...</Text></div>
                    </div>
                  ) : reportContent ? (
                    <div style={{
                      whiteSpace: "pre-wrap", fontFamily: "SimSun, serif",
                      lineHeight: 1.8, padding: "16px", background: "#fafafa",
                      borderRadius: 8, maxHeight: "calc(100vh - 350px)", overflowY: "auto",
                    }}>
                      {reportContent}
                    </div>
                  ) : (
                    <Empty description="请在左侧设置参数后生成报告" style={{ padding: "100px 0" }} />
                  )}
                </Card>
              </Col>
            </Row>
          ),
        },
        {
          key: "history", label: <span><HistoryOutlined /> 历史报告</span>,
          children: historyLoading ? (
            <div style={{ textAlign: "center", padding: 50 }}>
              <Spin />
            </div>
          ) : (reportHistory.length === 0 && savedReports.length === 0) ? (
            <Card><Empty description="暂无审查记录或报告，请先执行审查" /></Card>
          ) : (
            <Row gutter={16}>
              <Col xs={24} lg={8}>
                {/* 左侧：审查记录和已生成报告列表 */}
                <Space direction="vertical" style={{ width: "100%" }} size="middle">
                  {/* 已生成的报告列表 */}
                  {savedReports.length > 0 && (
                    <Card title="已生成的报告" size="small" bodyStyle={{ padding: 0 }}>
                      <Timeline
                        style={{ padding: "16px" }}
                        items={savedReports.map((report) => ({
                          dot: report.opinion_type === "notice" ? <FileTextOutlined style={{ color: "#1677ff" }} /> :
                               report.opinion_type === "grant" ? <FileDoneOutlined style={{ color: "#52c41a" }} /> :
                               <CloseCircleOutlined style={{ color: "#ff4d4f" }} />,
                          children: (
                            <div
                              style={{
                                cursor: "pointer",
                                padding: "8px 12px",
                                borderRadius: 6,
                                background: selectedReportId === report.id ? "#e6f4ff" : "transparent",
                                border: selectedReportId === report.id ? "1px solid #1677ff" : "1px solid transparent",
                              }}
                              onClick={async () => {
                                setSelectedReportId(report.id);
                                setSelectedExamId(null);
                                // 获取报告内容
                                try {
                                  const detail = await reportApi.getReport(report.id);
                                  setReportContent(detail.content);
                                } catch (err) {
                                  console.error("Failed to get report:", err);
                                }
                              }}
                            >
                              <div style={{ fontWeight: selectedReportId === report.id ? 600 : 400 }}>
                                {report.opinion_type === "notice" ? "审查意见通知书" :
                                 report.opinion_type === "grant" ? "授权通知书" : "驳回决定书"}
                              </div>
                              <div style={{ fontSize: 12, color: "#888" }}>
                                {report.created_at ? new Date(report.created_at).toLocaleString("zh-CN") : ""}
                              </div>
                              <div style={{ marginTop: 4 }}>
                                <Tag color={report.opinion_type === "notice" ? "blue" :
                                           report.opinion_type === "grant" ? "green" : "red"}>
                                  {report.status === "finalized" ? "已生成" : report.status}
                                </Tag>
                              </div>
                            </div>
                          ),
                        }))}
                      />
                    </Card>
                  )}
                  
                  {/* 审查记录列表 */}
                  <Card title="审查记录" size="small" bodyStyle={{ padding: 0 }}>
                    <Timeline
                      style={{ padding: "16px" }}
                      items={reportHistory.map((exam) => ({
                        dot: exam.overall_result === "pass" ? <CheckCircleOutlined style={{ color: "#52c41a" }} /> :
                             exam.overall_result === "fail" ? <CloseCircleOutlined style={{ color: "#ff4d4f" }} /> :
                             <ClockCircleOutlined style={{ color: "#faad14" }} />,
                        children: (
                          <div
                            style={{
                              cursor: "pointer",
                              padding: "8px 12px",
                              borderRadius: 6,
                              background: selectedExamId === exam.id ? "#e6f4ff" : "transparent",
                              border: selectedExamId === exam.id ? "1px solid #1677ff" : "1px solid transparent",
                            }}
                            onClick={() => {
                              setSelectedExamId(exam.id);
                              setSelectedReportId(null);
                              setReportContent("");
                            }}
                          >
                            <div style={{ fontWeight: selectedExamId === exam.id ? 600 : 400 }}>
                              {exam.examination_type === "formal" ? "形式审查" : exam.examination_type === "substantive" ? "实质审查" : "一键审查"}
                            </div>
                            <div style={{ fontSize: 12, color: "#888" }}>
                              {exam.created_at ? new Date(exam.created_at).toLocaleString("zh-CN") : ""}
                            </div>
                            <div style={{ marginTop: 4 }}>
                              <Tag color={exam.overall_result === "pass" ? "success" :
                                         exam.overall_result === "fail" ? "error" : "warning"}>
                                {exam.overall_result === "pass" ? "通过" :
                                 exam.overall_result === "fail" ? "不通过" : "待定"}
                              </Tag>
                              {exam.score != null && <Tag>得分: {exam.score}</Tag>}
                            </div>
                          </div>
                        ),
                      }))}
                    />
                  </Card>
                </Space>
              </Col>
              <Col xs={24} lg={16}>
                <Card title="报告详情" size="small"
                  extra={reportContent && (
                    <Space>
                      <Button size="small" icon={<DownloadOutlined />} onClick={handleDownload}>下载</Button>
                      <Button size="small" icon={<PrinterOutlined />} onClick={handlePrint}>打印</Button>
                      <Button size="small" onClick={() => setActiveTab("generate")}>在新窗口查看</Button>
                    </Space>
                  )}
                >
                  {selectedReportId || selectedExamId ? (
                    <Space direction="vertical" style={{ width: "100%" }}>
                      {/* 如果选中了审查记录，显示生成按钮 */}
                      {selectedExamId && !selectedReportId && (
                        <Button type="primary" onClick={async () => {
                          const exam = reportHistory.find(e => e.id === selectedExamId);
                          if (exam && currentPatentId) {
                            setLoading(true);
                            try {
                              const res = await reportApi.generate({
                                patent_id: currentPatentId,
                                report_type: "examination_opinion",
                                examination_id: selectedExamId,
                              });
                              setReportContent(res.content || res.report || "报告生成完成");
                              message.success("报告生成成功");
                              // 刷新报告列表
                              const reports = await reportApi.getReportHistory(currentPatentId);
                              setSavedReports(reports);
                              if (res.report_id) {
                                setSelectedReportId(res.report_id);
                              }
                            } catch {
                              message.error("报告生成失败");
                            } finally {
                              setLoading(false);
                            }
                          }
                        }} icon={<FileTextOutlined />}>
                          生成审查报告
                        </Button>
                      )}
                      
                      {/* 如果有报告内容，显示预览 */}
                      {reportContent && (
                        <div style={{
                          whiteSpace: "pre-wrap", fontFamily: "SimSun, serif",
                          lineHeight: 1.8, padding: "16px", background: "#fafafa",
                          borderRadius: 8, maxHeight: "calc(100vh - 450px)", overflowY: "auto",
                        }}>
                          {reportContent}
                        </div>
                      )}
                      
                      {/* 如果选中了审查记录但没有报告内容，显示摘要 */}
                      {!reportContent && selectedExamId && (() => {
                        const exam = reportHistory.find(e => e.id === selectedExamId);
                        return exam?.summary ? (
                          <div style={{ background: "#fafafa", padding: 16, borderRadius: 8 }}>
                            <Text strong>审查摘要：</Text>
                            <Paragraph style={{ marginTop: 8, whiteSpace: "pre-wrap" }}>{exam.summary}</Paragraph>
                          </div>
                        ) : (
                          <Empty description="点击上方按钮生成审查报告" />
                        );
                      })()}
                    </Space>
                  ) : (
                    <Empty description="请选择左侧报告或审查记录查看详情" />
                  )}
                </Card>
              </Col>
            </Row>
          ),
        },
        {
          key: "templates", label: <span><SettingOutlined /> 模板管理</span>,
          children: (
            <Card>
              <Space style={{ marginBottom: 16 }}>
                <Button type="primary" icon={<PlusOutlined />} onClick={() => {
                  setEditingTemplate(null);
                  templateForm.resetFields();
                  templateForm.setFieldsValue({
                    template_type: "opinion_notice",
                    is_default: false,
                  });
                  setTemplateModalVisible(true);
                }}>
                  新建模板
                </Button>
                <Button icon={<DeleteOutlined />} onClick={fetchTemplates}>刷新</Button>
              </Space>
              <Table
                dataSource={templates}
                rowKey="id"
                loading={templatesLoading}
                columns={[
                  { title: "模板名称", dataIndex: "template_name", key: "template_name" },
                  { 
                    title: "类型", dataIndex: "template_type", key: "template_type",
                    render: (t: string) => {
                      const typeMap: Record<string, string> = {
                        opinion_notice: "审查意见通知书",
                        grant_notice: "授权通知书",
                        rejection: "驳回决定书",
                      };
                      return typeMap[t] || t;
                    }
                  },
                  { 
                    title: "默认", dataIndex: "is_default", key: "is_default",
                    render: (d: boolean) => d ? <Tag color="gold">默认</Tag> : "-"
                  },
                  { 
                    title: "创建时间", dataIndex: "created_at", key: "created_at",
                    render: (t: string) => t ? new Date(t).toLocaleString("zh-CN") : "-"
                  },
                  {
                    title: "操作", key: "action",
                    render: (_: any, record: ReportTemplate) => (
                      <Space>
                        <Button type="link" size="small" icon={<EditOutlined />} onClick={() => {
                          setEditingTemplate(record);
                          templateForm.setFieldsValue({
                            template_name: record.template_name,
                            template_type: record.template_type,
                            content: record.content,
                            is_default: record.is_default,
                          });
                          setTemplateModalVisible(true);
                        }}>编辑</Button>
                        <Button type="link" size="small" danger icon={<DeleteOutlined />} onClick={async () => {
                          if (confirm("确定要删除这个模板吗？")) {
                            try {
                              await reportApi.deleteTemplate(record.id);
                              message.success("模板删除成功");
                              fetchTemplates();
                            } catch {
                              message.error("模板删除失败");
                            }
                          }
                        }}>删除</Button>
                      </Space>
                    ),
                  },
                ]}
                pagination={{ pageSize: 10 }}
              />
            </Card>
          ),
        },
      ]} />

      {/* 模板创建/编辑弹窗 - 支持区块式和文件上传 */}
      <Modal
        title={editingTemplate ? "编辑模板" : "新建模板"}
        open={templateModalVisible}
        onOk={async () => {
          try {
            const values = await templateForm.validateFields();
            console.log("Form values:", values);
            const templateData: any = {
              template_name: values.template_name,
              template_type: values.template_type,
              is_default: values.is_default,
            };
            
            // 检查是否有区块配置，如果有就使用区块模式
            if (values.section_config && values.section_config.length > 0) {
              templateData.section_config = values.section_config;
              console.log("Using block template with sections:", values.section_config.length);
            } else {
              templateData.content = values.content || "";
              console.log("Using text template");
            }
            
            console.log("templateData:", templateData);
            
            if (editingTemplate) {
              await reportApi.updateTemplate(editingTemplate.id, templateData);
              message.success("模板更新成功");
            } else {
              await reportApi.createTemplate(templateData);
              message.success("模板创建成功");
            }
            setTemplateModalVisible(false);
            fetchTemplates();
          } catch {
            message.error("操作失败");
          }
        }}
        onCancel={() => setTemplateModalVisible(false)}
        width={900}
      >
        <Form form={templateForm} layout="vertical" initialValues={{ mode: 'text' }}>
          <Tabs 
            defaultActiveKey="text"
            items={[
              {
                key: "text",
                label: "📝 文本模板",
                children: (
                  <>
                    <Form.Item name="template_name" label="模板名称" rules={[{ required: true, message: "请输入模板名称" }]}>
                      <Input placeholder="例如：标准审查意见通知书" />
                    </Form.Item>
                    <Form.Item name="template_type" label="报告类型" rules={[{ required: true }]}>
                      <Select options={[
                        { value: "opinion_notice", label: "审查意见通知书" },
                        { value: "grant_notice", label: "授权通知书" },
                        { value: "rejection", label: "驳回决定书" },
                      ]} />
                    </Form.Item>
                    <Form.Item name="is_default" label="设为默认模板" valuePropName="checked">
                      <Switch /> <Text type="secondary" style={{ marginLeft: 8 }}>默认模板将作为生成报告时的首选</Text>
                    </Form.Item>
                    <Form.Item name="content" label="模板内容">
                      <TextArea rows={12} placeholder={`使用 {{变量名}} 格式插入变量，例如：
申请号：{{application_number}}
发明名称：{{title}}
申请人：{{applicant}}

可用变量：
- {{application_number}} 申请号
- {{title}} 发明名称  
- {{applicant}} 申请人
- {{examiner}} 审查员
- {{date}} 日期
- {{issues_text}} 问题列表
- {{conclusion}} 审查结论`} />
                    </Form.Item>
                    <Form.Item label="或上传模板文件">
                      <Upload
                        accept=".txt,.md"
                        showUploadList={false}
                        beforeUpload={async (file) => {
                          try {
                            const values = templateForm.getFieldsValue();
                            await reportApi.uploadTemplateFile(file, values.template_type || "opinion_notice", values.template_name);
                            message.success("文件上传成功，模板已创建");
                            setTemplateModalVisible(false);
                            fetchTemplates();
                          } catch {
                            message.error("文件上传失败");
                          }
                          return false;
                        }}
                      >
                        <Button icon={<UploadOutlined />}>上传 .txt 或 .md 文件作为模板</Button>
                      </Upload>
                      <Text type="secondary" style={{ display: "block", marginTop: 8 }}>
                        支持上传 .txt 或 .md 文件，系统将自动解析内容作为模板
                      </Text>
                    </Form.Item>
                  </>
                )
              },
              {
                key: "block",
                label: "🧱 区块模板",
                children: (
                  <>
                    <Alert 
                      message="区块式模板" 
                      description="通过勾选和拖拽区块来组合模板，更简单直观。系统会按照区块顺序自动生成报告内容。" 
                      type="info" 
                      showIcon 
                      style={{ marginBottom: 16 }}
                    />
                    <Form.Item name="template_name" label="模板名称" rules={[{ required: true, message: "请输入模板名称" }]}>
                      <Input placeholder="例如：简洁版审查意见通知书" />
                    </Form.Item>
                    <Form.Item name="template_type" label="报告类型" rules={[{ required: true }]}>
                      <Select options={[
                        { value: "opinion_notice", label: "审查意见通知书" },
                        { value: "grant_notice", label: "授权通知书" },
                        { value: "rejection", label: "驳回决定书" },
                      ]} onChange={() => templateForm.setFieldValue("section_config", [])} />
                    </Form.Item>
                    <Form.Item name="is_default" label="设为默认模板" valuePropName="checked">
                      <Switch /> <Text type="secondary" style={{ marginLeft: 8 }}>默认模板将作为生成报告时的首选</Text>
                    </Form.Item>
                    {/* 隐藏的section_config字段，确保在表单中注册 */}
                    <Form.Item name="section_config" hidden>
                      <Input />
                    </Form.Item>
                    
                    <Divider>选择区块</Divider>
                    <BlockEditorWrapper />
                  </>
                )
              },
            ]}
          />
        </Form>
      </Modal>
    </Space>
  );
}

// 区块编辑器组件
interface BlockEditorProps {
  templateType: string;
  onChange?: (sections: SectionConfig[]) => void;
}

function BlockEditor({ templateType: propTemplateType, onChange }: BlockEditorProps) {
  const [templateType, setTemplateType] = useState(propTemplateType || "opinion_notice");
  const [sections, setSections] = useState<SectionConfig[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (propTemplateType) {
      setTemplateType(propTemplateType);
    }
  }, [propTemplateType]);

  useEffect(() => {
    loadSections();
  }, [templateType]);

  const loadSections = async () => {
    setLoading(true);
    try {
      const defs = await reportApi.getSectionDefinitions(templateType);
      // 初始化所有区块为启用状态
      const initialSections = defs.map((d, idx) => ({
        id: d.id,
        enabled: true,
        order: idx,
        custom_content: "",
      }));
      setSections(initialSections);
      onChange?.(initialSections);
    } catch (err) {
      console.error("Failed to load sections:", err);
    } finally {
      setLoading(false);
    }
  };

  const toggleSection = (id: string) => {
    const newSections = sections.map(s => 
      s.id === id ? { ...s, enabled: !s.enabled } : s
    );
    setSections(newSections);
    onChange?.(newSections);
  };

  const moveSection = (id: string, direction: 'up' | 'down') => {
    const idx = sections.findIndex(s => s.id === id);
    if (idx === -1) return;
    if (direction === 'up' && idx === 0) return;
    if (direction === 'down' && idx === sections.length - 1) return;
    
    const newSections = [...sections];
    const swapIdx = direction === 'up' ? idx - 1 : idx + 1;
    [newSections[idx], newSections[swapIdx]] = [newSections[swapIdx], newSections[idx]];
    // 更新order
    newSections.forEach((s, i) => s.order = i);
    setSections(newSections);
    onChange?.(newSections);
  };

  const updateCustomContent = (id: string, content: string) => {
    const newSections = sections.map(s => 
      s.id === id ? { ...s, custom_content: content } : s
    );
    setSections(newSections);
    onChange?.(newSections);
  };

  if (loading) return <Spin />;

  const sectionNames: Record<string, string> = {
    header: "文件头部",
    basic_info: "基本信息",
    issues: "审查意见",
    conclusion: "审查结论",
    reply_requirement: "答复要求",
    footer: "文件尾部",
    grant_decision: "授权决定",
    reasons: "驳回理由",
    review_info: "复审程序告知",
  };

  return (
    <div>
      <Paragraph type="secondary" style={{ marginBottom: 16 }}>
        勾选要包含的区块，可以通过上下箭头调整顺序。启用"自定义"可以覆盖默认内容。
      </Paragraph>
      {sections.map((section, idx) => (
        <Card 
          key={section.id} 
          size="small" 
          style={{ marginBottom: 8, opacity: section.enabled ? 1 : 0.6 }}
        >
          <Row align="middle" gutter={12}>
            <Col>
              <Switch 
                checked={section.enabled} 
                onChange={() => toggleSection(section.id)}
              />
            </Col>
            <Col>
              <Space>
                <Button 
                  type="text" 
                  size="small" 
                  icon={<ArrowUpOutlined />} 
                  onClick={() => moveSection(section.id, 'up')}
                  disabled={idx === 0}
                />
                <Button 
                  type="text" 
                  size="small" 
                  icon={<ArrowDownOutlined />} 
                  onClick={() => moveSection(section.id, 'down')}
                  disabled={idx === sections.length - 1}
                />
              </Space>
            </Col>
            <Col flex={1}>
              <Text strong>{sectionNames[section.id] || section.id}</Text>
            </Col>
            <Col>
              <Checkbox 
                checked={!!section.custom_content}
                onChange={(e) => {
                  if (e.target.checked) {
                    updateCustomContent(section.id, "");
                  } else {
                    updateCustomContent(section.id, "");
                  }
                }}
              >
                自定义
              </Checkbox>
            </Col>
          </Row>
          {section.custom_content !== undefined && (
            <TextArea
              rows={2}
              value={section.custom_content}
              onChange={(e) => updateCustomContent(section.id, e.target.value)}
              placeholder="可选：输入自定义内容，使用 {{变量名}} 插入动态内容"
              style={{ marginTop: 8 }}
              disabled={!section.enabled}
            />
          )}
        </Card>
      ))}
      <Alert 
        message="提示" 
        description="区块将按照从上到下的顺序生成报告。未启用或自定义内容为空的区块将使用系统默认内容。" 
        type="info" 
        showIcon 
        style={{ marginTop: 16 }}
      />
    </div>
  );
}
