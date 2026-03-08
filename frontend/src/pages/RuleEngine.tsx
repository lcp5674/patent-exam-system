import { useEffect, useState, useCallback } from "react";
import {
  Card, Table, Button, Space, Typography, Tag, Modal, Form, Input, Select,
  Switch, message, Popconfirm, Row, Col, Tooltip, Tabs, InputNumber, Collapse,
} from "antd";
import {
  PlusOutlined, EditOutlined, DeleteOutlined, ReloadOutlined,
  CheckCircleOutlined, StopOutlined, ThunderboltOutlined, SettingOutlined,
} from "@ant-design/icons";
import api from "../services/api";

const { Title, Text, Paragraph } = Typography;
const { TextArea } = Input;

interface Rule {
  id: number;
  rule_name: string;
  rule_type: string;
  rule_category: string;
  rule_content: Record<string, any>;
  priority: number;
  is_active: boolean;
  version: string;
  description: string;
  legal_basis: string;
  severity: string;
  check_pattern: string;
  target_fields: Record<string, any>;
  error_message: string;
  fix_suggestion: string;
  ai_model: string;
  examples: Record<string, any>;
  tags: Record<string, any>;
  execution_count: number;
  success_rate: number;
  avg_execution_time: number;
  created_at: string;
}

const categoryOptions = [
  { value: "formal", label: "形式审查" },
  { value: "substantive", label: "实质审查" },
  { value: "claims", label: "权利要求" },
  { value: "description", label: "说明书" },
  { value: "drawings", label: "附图" },
  { value: "unity", label: "单一性" },
  { value: "novelty", label: "新颖性" },
  { value: "inventiveness", label: "创造性" },
  { value: "practicality", label: "实用性" },
];

const severityOptions = [
  { value: "error", label: "严重" },
  { value: "warning", label: "警告" },
  { value: "info", label: "建议" },
];

const checkPatternOptions = [
  { value: "regex", label: "正则表达式" },
  { value: "keyword", label: "关键词匹配" },
  { value: "ai", label: "AI智能分析" },
  { value: "structural", label: "结构检查" },
  { value: "template", label: "模板匹配" },
];

const targetFieldOptions = [
  { value: "title", label: "专利名称" },
  { value: "abstract", label: "摘要" },
  { value: "claims", label: "权利要求书" },
  { value: "description", label: "说明书" },
  { value: "drawings", label: "附图说明" },
  { value: "applicant", label: "申请人" },
  { value: "inventor", label: "发明人" },
  { value: "agent", label: "代理人" },
];

export default function RuleEngine() {
  const [rules, setRules] = useState<Rule[]>([]);
  const [loading, setLoading] = useState(false);
  const [modalVisible, setModalVisible] = useState(false);
  const [modalTab, setModalTab] = useState("basic");
  const [editingRule, setEditingRule] = useState<Rule | null>(null);
  const [saving, setSaving] = useState(false);
  const [form] = Form.useForm();

  const loadRules = useCallback(async () => {
    setLoading(true);
    try {
      const res = await api.get("/rules/");
      const data = res.data;
      // 处理多种可能的返回格式: {code: 200, data: [...]} 或直接 [...]
      const rulesArray = Array.isArray(data) ? data : 
                         Array.isArray(data?.data) ? data.data : 
                         Array.isArray(data?.items) ? data.items : 
                         [];
      setRules(rulesArray);
    } catch {
      message.error("加载规则列表失败");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { loadRules(); }, [loadRules]);

  const openCreate = () => {
    setEditingRule(null);
    form.resetFields();
    form.setFieldsValue({ 
      rule_category: "level1", 
      severity: "warning", 
      is_active: true, 
      rule_type: "formal",
      check_pattern: "regex",
      priority: 0,
      target_fields: [],
    });
    setModalTab("basic");
    setModalVisible(true);
  };

  const openEdit = (rule: Rule) => {
    setEditingRule(rule);
    form.setFieldsValue({
      ...rule,
      target_fields: rule.target_fields?.fields || [],
    });
    setModalTab("basic");
    setModalVisible(true);
  };

  const handleSave = async (values: any) => {
    const data = {
      ...values,
      target_fields: values.target_fields ? { fields: values.target_fields } : null,
    };
    setSaving(true);
    try {
      if (editingRule) {
        await api.put(`/rules/${editingRule.id}`, data);
        message.success("规则更新成功");
      } else {
        await api.post("/rules", data);
        message.success("规则创建成功");
      }
      setModalVisible(false);
      loadRules();
    } catch {
      message.error("保存失败");
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (id: number) => {
    try {
      await api.delete(`/rules/${id}`);
      message.success("删除成功");
      loadRules();
    } catch {
      message.error("删除失败");
    }
  };

  const toggleActive = async (rule: Rule) => {
    try {
      await api.put(`/rules/${rule.id}`, { ...rule, is_active: !rule.is_active });
      message.success(rule.is_active ? "规则已禁用" : "规则已启用");
      loadRules();
    } catch {
      message.error("操作失败");
    }
  };

  const severityColor = (s: string) =>
    s === "error" ? "red" : s === "warning" ? "orange" : "blue";

  const columns = [
    { title: "规则名称", dataIndex: "rule_name", key: "rule_name", width: 180,
      render: (t: string) => <Text strong>{t}</Text> },
    { title: "分类", dataIndex: "rule_type", key: "rule_type", width: 100,
      render: (c: string) => {
        const opt = categoryOptions.find((o) => o.value === c);
        return <Tag>{opt?.label || c}</Tag>;
      },
    },
    { title: "等级", dataIndex: "rule_category", key: "rule_category", width: 90,
      render: (c: string) => {
        const colors: Record<string, string> = { level1: "green", level2: "orange", level3: "purple" };
        return <Tag color={colors[c] || "default"}>{c === "level1" ? "一级" : c === "level2" ? "二级" : "三级"}</Tag>;
      },
    },
    { title: "严重度", dataIndex: "severity", key: "severity", width: 80,
      render: (s: string) => <Tag color={severityColor(s)}>{s === "error" ? "严重" : s === "warning" ? "警告" : "建议"}</Tag> },
    { title: "检查模式", dataIndex: "check_pattern", key: "check_pattern", width: 90,
      render: (p: string) => {
        const opt = checkPatternOptions.find((o) => o.value === p);
        return <Tag>{opt?.label || p || "-"}</Tag>;
      },
    },
    { title: "描述", dataIndex: "description", key: "description", ellipsis: true },
    { title: "法律依据", dataIndex: "legal_basis", key: "legal_basis", width: 150, ellipsis: true },
    { title: "执行次数", dataIndex: "execution_count", key: "execution_count", width: 80,
      render: (c: number) => <Text type="secondary">{c || 0}</Text> },
    { title: "状态", dataIndex: "is_active", key: "is_active", width: 70,
      render: (a: boolean, r: Rule) => (
        <Switch checked={a} size="small" onChange={() => toggleActive(r)}
          checkedChildren={<CheckCircleOutlined />} unCheckedChildren={<StopOutlined />} />
      ),
    },
    {
      title: "操作", key: "action", width: 120,
      render: (_: any, record: Rule) => (
        <Space size="small">
          <Tooltip title="编辑">
            <Button type="link" size="small" icon={<EditOutlined />} onClick={() => openEdit(record)} />
          </Tooltip>
          <Popconfirm title="确认删除该规则？" onConfirm={() => handleDelete(record.id)}>
            <Tooltip title="删除">
              <Button type="link" size="small" danger icon={<DeleteOutlined />} />
            </Tooltip>
          </Popconfirm>
        </Space>
      ),
    },
  ];

  const level1Rules = rules.filter((r) => r.rule_category === "level1");
  const level2Rules = rules.filter((r) => r.rule_category === "level2");

  const modalTabs = [
    { key: "basic", label: "基本信息" },
    { key: "check", label: "检查配置" },
    { key: "message", label: "消息设置" },
    { key: "advanced", label: "高级设置" },
  ];

  return (
    <Space direction="vertical" size="middle" style={{ width: "100%" }}>
      <Row justify="space-between" align="middle">
        <Col>
          <Space>
            <Title level={4} style={{ margin: 0 }}>规则引擎</Title>
            <Tag icon={<ThunderboltOutlined />} color="blue">
              {rules.filter((r) => r.is_active).length} / {rules.length} 规则已启用
            </Tag>
          </Space>
        </Col>
        <Col>
          <Space>
            <Button icon={<ReloadOutlined />} onClick={loadRules}>刷新</Button>
            <Button type="primary" icon={<PlusOutlined />} onClick={openCreate}>添加规则</Button>
          </Space>
        </Col>
      </Row>

      <Tabs defaultActiveKey="all" items={[
        { key: "all", label: `全部规则 (${rules.length})`,
          children: <Card styles={{ body: { padding: 0 } }}>
            <Table columns={columns} dataSource={rules} rowKey="id" loading={loading} size="small"
              pagination={{ pageSize: 20, showTotal: (t) => `共 ${t} 条` }} />
          </Card>,
        },
        { key: "level1", label: `一级规则 (${level1Rules.length})`,
          children: <Card styles={{ body: { padding: 0 } }}>
            <Table columns={columns} dataSource={level1Rules} rowKey="id" loading={loading} size="small"
              pagination={false} />
          </Card>,
        },
        { key: "level2", label: `二级规则 (${level2Rules.length})`,
          children: <Card styles={{ body: { padding: 0 } }}>
            <Table columns={columns} dataSource={level2Rules} rowKey="id" loading={loading} size="small"
              pagination={false} />
          </Card>,
        },
      ]} />

      <Modal title={editingRule ? "编辑规则" : "新建规则"} open={modalVisible}
        onCancel={() => setModalVisible(false)} footer={null} width={800} destroyOnHidden>
        <Tabs activeKey={modalTab} onChange={setModalTab} items={modalTabs} />
        <Form form={form} layout="vertical" onFinish={handleSave} style={{ marginTop: 16 }}>
          {modalTab === "basic" && (
            <>
              <Row gutter={16}>
                <Col span={12}>
                  <Form.Item name="rule_name" label="规则标识" rules={[{ required: true, message: "请输入规则标识" }]}>
                    <Input placeholder="如: document_completeness" disabled={!!editingRule} />
                  </Form.Item>
                </Col>
                <Col span={12}>
                  <Form.Item name="version" label="版本号">
                    <Input placeholder="如: v1.0" />
                  </Form.Item>
                </Col>
              </Row>
              <Row gutter={16}>
                <Col span={8}>
                  <Form.Item name="rule_type" label="规则类型" rules={[{ required: true }]}>
                    <Select options={categoryOptions} />
                  </Form.Item>
                </Col>
                <Col span={8}>
                  <Form.Item name="rule_category" label="规则等级" rules={[{ required: true }]}>
                    <Select options={[
                      { value: "level1", label: "一级 (基础)" },
                      { value: "level2", label: "二级 (进阶)" },
                      { value: "level3", label: "三级 (AI辅助)" },
                    ]} />
                  </Form.Item>
                </Col>
                <Col span={8}>
                  <Form.Item name="severity" label="严重程度" rules={[{ required: true }]}>
                    <Select options={severityOptions} />
                  </Form.Item>
                </Col>
              </Row>
              <Row gutter={16}>
                <Col span={12}>
                  <Form.Item name="priority" label="优先级">
                    <InputNumber min={0} max={100} style={{ width: "100%" }} />
                  </Form.Item>
                </Col>
                <Col span={12}>
                  <Form.Item name="is_active" label="启用状态" valuePropName="checked">
                    <Switch checkedChildren="启用" unCheckedChildren="禁用" />
                  </Form.Item>
                </Col>
              </Row>
              <Form.Item name="description" label="规则描述">
                <TextArea rows={2} placeholder="规则功能描述" />
              </Form.Item>
              <Form.Item name="legal_basis" label="法律依据">
                <Input placeholder="如: 专利法第26条第3款" />
              </Form.Item>
            </>
          )}

          {modalTab === "check" && (
            <>
              <Form.Item name="check_pattern" label="检查模式">
                <Select options={checkPatternOptions} placeholder="选择检查方式" />
              </Form.Item>
              <Form.Item name="target_fields" label="目标字段">
                <Select mode="multiple" options={targetFieldOptions} placeholder="选择要检查的字段" />
              </Form.Item>
              <Form.Item name="rule_content" label="检查逻辑 (JSON)">
                <TextArea rows={4} placeholder='{"type": "regex", "pattern": "...", "flags": "i"}' />
              </Form.Item>
              <Form.Item name="ai_model" label="AI模型">
                <Select options={[
                  { value: "gpt-4", label: "GPT-4" },
                  { value: "gpt-3.5-turbo", label: "GPT-3.5" },
                  { value: "claude-3", label: "Claude-3" },
                  { value: "local", label: "本地模型" },
                ]} placeholder="选择AI模型(可选)" allowClear />
              </Form.Item>
            </>
          )}

          {modalTab === "message" && (
            <>
              <Form.Item name="error_message" label="错误消息模板">
                <TextArea rows={3} placeholder="如: {field}不符合要求：{reason}" />
              </Form.Item>
              <Form.Item name="fix_suggestion" label="修复建议">
                <TextArea rows={3} placeholder="如: 请补充{field}内容，确保符合专利法规定" />
              </Form.Item>
              <Form.Item name="tags" label="标签 (JSON)">
                <TextArea rows={2} placeholder='["形式错误", "必填项"]' />
              </Form.Item>
              <Form.Item name="examples" label="示例 (JSON)">
                <TextArea rows={4} placeholder='{"correct": "...", "incorrect": "..."}' />
              </Form.Item>
            </>
          )}

          {modalTab === "advanced" && (
            <>
              <Row gutter={16}>
                <Col span={8}>
                  <Form.Item name="execution_count" label="执行次数">
                    <InputNumber min={0} style={{ width: "100%" }} disabled />
                  </Form.Item>
                </Col>
                <Col span={8}>
                  <Form.Item name="success_rate" label="成功率(%)">
                    <InputNumber min={0} max={100} style={{ width: "100%" }} disabled />
                  </Form.Item>
                </Col>
                <Col span={8}>
                  <Form.Item name="avg_execution_time" label="平均执行时间(ms)">
                    <InputNumber min={0} style={{ width: "100%" }} disabled />
                  </Form.Item>
                </Col>
              </Row>
              <Paragraph type="secondary" style={{ fontSize: 12 }}>
                高级设置包含规则的执行统计信息，这些字段由系统自动维护。
              </Paragraph>
            </>
          )}

          <Form.Item style={{ textAlign: "right", marginBottom: 0, marginTop: 16 }}>
            <Space>
              <Button onClick={() => setModalVisible(false)}>取消</Button>
              <Button type="primary" htmlType="submit" loading={saving}>保存</Button>
            </Space>
          </Form.Item>
        </Form>
      </Modal>
    </Space>
  );
}
