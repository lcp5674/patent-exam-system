import { useEffect, useState, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import {
  Table, Card, Button, Input, Space, Tag, Typography, Upload, message, Modal,
  Form, Select, Row, Col, Tooltip, Popconfirm,
} from "antd";
import {
  PlusOutlined, UploadOutlined, SearchOutlined, ReloadOutlined,
  EyeOutlined, EditOutlined, DeleteOutlined, ExperimentOutlined,
  PlayCircleOutlined
} from "@ant-design/icons";
import { patentApi } from "../services/patentApi";
import { workflowApi } from "../services/workflowApi";
import type { Patent } from "../types";

const { Title } = Typography;

const statusOptions = [
  { value: "", label: "全部状态" },
  { value: "draft", label: "草稿" },
  { value: "pending", label: "待审查" },
  { value: "examining", label: "审查中" },
  { value: "approved", label: "已通过" },
  { value: "rejected", label: "已驳回" },
];

const statusColorMap: Record<string, string> = {
  draft: "default", pending: "processing", examining: "warning",
  completed: "success", granted: "success", approved: "success", rejected: "error",
};
const statusTextMap: Record<string, string> = {
  draft: "草稿", pending: "待审查", examining: "审查中",
  completed: "已完成", granted: "已授权", approved: "已通过", rejected: "已驳回",
};

export default function PatentList() {
  const [patents, setPatents] = useState<Patent[]>([]);
  const [loading, setLoading] = useState(false);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(15);
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [createVisible, setCreateVisible] = useState(false);
  const [createLoading, setCreateLoading] = useState(false);
  const [form] = Form.useForm();
  const navigate = useNavigate();

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const res = await patentApi.getList({
        page, page_size: pageSize,
        search: search || undefined,
        status: statusFilter || undefined,
      });
      setPatents(res.items || []);
      setTotal(res.total || 0);
    } catch {
      message.error("加载专利列表失败");
    } finally {
      setLoading(false);
    }
  }, [page, pageSize, search, statusFilter]);

  useEffect(() => { loadData(); }, [loadData]);

  const handleCreate = async (values: any) => {
    setCreateLoading(true);
    try {
      await patentApi.create(values);
      message.success("专利创建成功");
      setCreateVisible(false);
      form.resetFields();
      loadData();
    } catch {
      message.error("创建失败");
    } finally {
      setCreateLoading(false);
    }
  };

  const handleDelete = async (id: number) => {
    // 立即从本地状态移除，实现即时无感知刷新
    setPatents(prev => prev.filter(p => p.id !== id));
    try {
      await patentApi.delete(id);
      message.success("删除成功");
    } catch {
      // 如果删除失败，恢复数据并重新加载
      message.error("删除失败");
      loadData();
    }
  };

  const handleImport = async (file: File) => {
    try {
      await patentApi.importFile(file);
      message.success("导入成功");
      // 重新加载数据以显示新导入的专利
      loadData();
    } catch {
      message.error("导入失败");
    }
    return false;
  };

  // 启动专利审查工作流
  const handleStartWorkflow = async (id: number) => {
    try {
      const res = await workflowApi.startPatentExamination(id);
      if (res.code === 200) {
        message.success("审查工作流已启动");
        loadData();
      }
    } catch (error: any) {
      message.error(error.message || "启动工作流失败");
    }
  };

  const columns = [
    {
      title: "申请号", dataIndex: "application_number", key: "application_number", width: 180,
      render: (t: string, r: any) => (
        <a onClick={() => navigate(`/patents/${r.id}`)} style={{ fontFamily: "monospace" }}>{t || "-"}</a>
      ),
    },
    { title: "专利名称", dataIndex: "title", key: "title", ellipsis: true, width: 280 },
    { title: "申请人", dataIndex: "applicant", key: "applicant", width: 150, ellipsis: true },
    { title: "发明人", dataIndex: "inventor", key: "inventor", width: 120, ellipsis: true },
    {
      title: "状态", dataIndex: "status", key: "status", width: 100,
      render: (s: string) => <Tag color={statusColorMap[s]}>{statusTextMap[s] || s}</Tag>,
    },
    {
      title: "提交时间", dataIndex: "created_at", key: "created_at", width: 160,
      render: (t: string) => t ? new Date(t).toLocaleString("zh-CN", { year: "numeric", month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit", second: "2-digit" }) : "-",
    },
    {
      title: "操作", key: "action", width: 240, fixed: "right" as const,
      render: (_: any, record: any) => (
        <Space size="small">
          <Tooltip title="查看详情">
            <Button type="link" size="small" icon={<EyeOutlined />}
              onClick={() => navigate(`/patents/${record.id}`)} />
          </Tooltip>
          <Tooltip title="启动审查工作流">
            <Button type="link" size="small" icon={<PlayCircleOutlined />}
              onClick={() => handleStartWorkflow(record.id)} />
          </Tooltip>
          <Tooltip title="开始审查">
            <Button type="link" size="small" icon={<ExperimentOutlined />}
              onClick={() => navigate(`/examination/${record.id}`)} />
          </Tooltip>
          <Tooltip title="编辑">
            <Button type="link" size="small" icon={<EditOutlined />}
              onClick={() => navigate(`/patents/${record.id}`)} />
          </Tooltip>
          <Popconfirm title="确认删除？" onConfirm={() => handleDelete(record.id)}>
            <Tooltip title="删除">
              <Button type="link" size="small" danger icon={<DeleteOutlined />} />
            </Tooltip>
          </Popconfirm>
        </Space>
      ),
    },
  ];

  return (
    <Space direction="vertical" size="middle" style={{ width: "100%" }}>
      <Row justify="space-between" align="middle">
        <Col><Title level={4} style={{ margin: 0 }}>专利管理</Title></Col>
        <Col>
          <Space>
            <Upload beforeUpload={handleImport} showUploadList={false}
              accept=".pdf,.docx,.doc,.txt">
              <Button icon={<UploadOutlined />}>导入专利</Button>
            </Upload>
            <Button type="primary" icon={<PlusOutlined />}
              onClick={() => setCreateVisible(true)}>新建专利</Button>
          </Space>
        </Col>
      </Row>

      <Card size="small">
        <Space wrap>
          <Input.Search placeholder="搜索申请号/名称/申请人" allowClear
            style={{ width: 300 }} prefix={<SearchOutlined />}
            onSearch={(v) => { setSearch(v); setPage(1); }} />
          <Select options={statusOptions} value={statusFilter} style={{ width: 140 }}
            onChange={(v) => { setStatusFilter(v); setPage(1); }} />
          <Button icon={<ReloadOutlined />} onClick={loadData}>刷新</Button>
        </Space>
      </Card>

      <Card styles={{ body: { padding: 0 } }}>
        <Table columns={columns} dataSource={patents} rowKey="id" loading={loading}
          scroll={{ x: 1100 }}
          pagination={{
            current: page, pageSize, total, showSizeChanger: true,
            showTotal: (t) => `共 ${t} 条`,
            onChange: (p, ps) => { setPage(p); setPageSize(ps); },
          }} />
      </Card>

      <Modal title="新建专利申请" open={createVisible} onCancel={() => setCreateVisible(false)}
        footer={null} width={640} destroyOnHidden>
        <Form form={form} layout="vertical" onFinish={handleCreate}>
          <Form.Item name="title" label="专利名称" rules={[{ required: true, message: "请输入专利名称" }]}>
            <Input placeholder="请输入实用新型专利名称" />
          </Form.Item>
          <Row gutter={16}>
            <Col span={12}>
              <Form.Item name="application_number" label="申请号">
                <Input placeholder="如：CN202310001234.5" />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item name="patent_type" label="专利类型" initialValue="utility_model">
                <Select options={[
                  { value: "utility_model", label: "实用新型" },
                  { value: "invention", label: "发明" },
                  { value: "design", label: "外观设计" },
                ]} />
              </Form.Item>
            </Col>
          </Row>
          <Row gutter={16}>
            <Col span={12}>
              <Form.Item name="applicant" label="申请人" rules={[{ required: true }]}>
                <Input placeholder="申请人名称" />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item name="inventor" label="发明人">
                <Input placeholder="发明人姓名" />
              </Form.Item>
            </Col>
          </Row>
          <Form.Item name="abstract" label="摘要">
            <Input.TextArea rows={4} placeholder="请输入专利摘要" />
          </Form.Item>
          <Form.Item style={{ textAlign: "right", marginBottom: 0 }}>
            <Space>
              <Button onClick={() => setCreateVisible(false)}>取消</Button>
              <Button type="primary" htmlType="submit" loading={createLoading}>创建</Button>
            </Space>
          </Form.Item>
        </Form>
      </Modal>
    </Space>
  );
}
