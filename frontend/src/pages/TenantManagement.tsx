import { useState, useEffect } from "react";
import { useSelector } from "react-redux";
import {
  Card, Table, Button, Space, Tag, Modal, Form, Input, Select, 
  Typography, message, Popconfirm, Pagination, Row, Col, Switch, InputNumber
} from "antd";
import {
  TeamOutlined, PlusOutlined, EditOutlined, DeleteOutlined, 
  StopOutlined, CheckCircleOutlined, SearchOutlined
} from "@ant-design/icons";
import type { RootState } from "../store";
import { tenantApi, Tenant, TenantCreate, TenantUpdate } from "../services/tenantApi";

const { Title, Text } = Typography;
const { Option } = Select;

export default function TenantManagement() {
  const currentUser = useSelector((s: RootState) => s.auth.user);
  const [tenants, setTenants] = useState<Tenant[]>([]);
  const [loading, setLoading] = useState(false);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [keyword, setKeyword] = useState("");
  const [modalVisible, setModalVisible] = useState(false);
  const [editingTenant, setEditingTenant] = useState<Tenant | null>(null);
  const [form] = Form.useForm();

  useEffect(() => {
    if (currentUser?.role !== "admin") {
      return;
    }
    loadTenants();
  }, [currentUser, page, pageSize]);

  const loadTenants = async () => {
    if (currentUser?.role !== "admin") return;
    
    setLoading(true);
    try {
      const data = await tenantApi.list({
        page,
        page_size: pageSize,
        keyword: keyword || undefined,
      });
      setTenants(data.items || []);
      setTotal(data.total || 0);
    } catch (error: any) {
      message.error(error.message || "加载租户列表失败");
    } finally {
      setLoading(false);
    }
  };

  const handleSearch = () => {
    setPage(1);
    loadTenants();
  };

  const handleAdd = () => {
    setEditingTenant(null);
    form.resetFields();
    form.setFieldsValue({
      max_users: 10,
      max_patents: 1000,
    });
    setModalVisible(true);
  };

  const handleEdit = (tenant: Tenant) => {
    setEditingTenant(tenant);
    form.setFieldsValue({
      name: tenant.name,
      code: tenant.code,
      description: tenant.description,
      is_active: tenant.is_active,
      max_users: tenant.max_users,
      max_patents: tenant.max_patents,
    });
    setModalVisible(true);
  };

  const handleDelete = async (tenantId: number) => {
    try {
      await tenantApi.delete(tenantId);
      message.success("删除成功");
      loadTenants();
    } catch (error: any) {
      message.error(error.message || "删除失败");
    }
  };

  const handleToggleActive = async (tenant: Tenant) => {
    try {
      await tenantApi.update(tenant.id, { is_active: !tenant.is_active });
      message.success(tenant.is_active ? "已禁用" : "已启用");
      loadTenants();
    } catch (error: any) {
      message.error(error.message || "操作失败");
    }
  };

  const handleSubmit = async () => {
    try {
      const values = await form.validateFields();
      
      if (editingTenant) {
        const updateData: TenantUpdate = {
          name: values.name,
          description: values.description,
          is_active: values.is_active,
          max_users: values.max_users,
          max_patents: values.max_patents,
        };
        await tenantApi.update(editingTenant.id, updateData);
        message.success("更新成功");
      } else {
        const createData: TenantCreate = {
          name: values.name,
          code: values.code,
          description: values.description,
          max_users: values.max_users,
          max_patents: values.max_patents,
        };
        await tenantApi.create(createData);
        message.success("创建成功");
      }
      
      setModalVisible(false);
      loadTenants();
    } catch (error: any) {
      message.error(error.message || "操作失败");
    }
  };

  const columns = [
    {
      title: "ID",
      dataIndex: "id",
      key: "id",
      width: 60,
    },
    {
      title: "租户名称",
      dataIndex: "name",
      key: "name",
    },
    {
      title: "租户代码",
      dataIndex: "code",
      key: "code",
      render: (code: string) => <Tag color="blue">{code}</Tag>,
    },
    {
      title: "描述",
      dataIndex: "description",
      key: "description",
      ellipsis: true,
      render: (text: string) => text || "-",
    },
    {
      title: "状态",
      dataIndex: "is_active",
      key: "is_active",
      render: (isActive: boolean) => (
        <Tag color={isActive ? "success" : "default"}>
          {isActive ? "启用" : "禁用"}
        </Tag>
      ),
    },
    {
      title: "用户数/上限",
      dataIndex: "user_count",
      key: "user_limit",
      render: (_: any, record: Tenant) => `${record.user_count || 0}/${record.max_users}`,
    },
    {
      title: "专利数/上限",
      dataIndex: "max_patents",
      key: "patent_limit",
      render: (_: any, record: Tenant) => `-/${record.max_patents}`,
    },
    {
      title: "创建时间",
      dataIndex: "created_at",
      key: "created_at",
      render: (text: string) => text ? new Date(text).toLocaleString() : "-",
    },
    {
      title: "操作",
      key: "action",
      width: 150,
      render: (_: any, record: Tenant) => (
        <Space>
          <Button 
            type="link" 
            size="small" 
            icon={<EditOutlined />}
            onClick={() => handleEdit(record)}
          >
            编辑
          </Button>
          <Popconfirm
            title="确认删除此租户？"
            onConfirm={() => handleDelete(record.id)}
          >
            <Button 
              type="link" 
              danger 
              size="small" 
              icon={<DeleteOutlined />}
            >
              删除
            </Button>
          </Popconfirm>
        </Space>
      ),
    },
  ];

  if (currentUser?.role !== "admin") {
    return (
      <Card>
        <Text type="danger">您没有权限访问此页面</Text>
      </Card>
    );
  }

  return (
    <Space direction="vertical" size="middle" style={{ width: "100%" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <Title level={4} style={{ margin: 0 }}>租户管理</Title>
        <Button type="primary" icon={<PlusOutlined />} onClick={handleAdd}>
          添加租户
        </Button>
      </div>

      <Card size="small">
        <Row gutter={16}>
          <Col>
            <Input.Search
              placeholder="搜索租户名称/代码"
              allowClear
              enterButton={<SearchOutlined />}
              onSearch={(value) => {
                setKeyword(value);
                setPage(1);
              }}
              onChange={(e) => {
                if (!e.target.value) {
                  setKeyword("");
                  setPage(1);
                }
              }}
              style={{ width: 300 }}
            />
          </Col>
          <Col>
            <Button icon={<SearchOutlined />} onClick={handleSearch}>
              搜索
            </Button>
          </Col>
        </Row>
      </Card>

      <Card size="small">
        <Table
          columns={columns}
          dataSource={tenants}
          rowKey="id"
          loading={loading}
          pagination={false}
          size="small"
        />
        <div style={{ marginTop: 16, textAlign: "right" }}>
          <Pagination
            current={page}
            pageSize={pageSize}
            total={total}
            onChange={(p, ps) => {
              setPage(p);
              setPageSize(ps);
            }}
            showSizeChanger
            showTotal={(t) => `共 ${t} 条`}
          />
        </div>
      </Card>

      <Modal
        title={editingTenant ? "编辑租户" : "添加租户"}
        open={modalVisible}
        onOk={handleSubmit}
        onCancel={() => setModalVisible(false)}
        width={500}
      >
        <Form form={form} layout="vertical">
          <Form.Item
            name="name"
            label="租户名称"
            rules={[
              { required: true, message: "请输入租户名称" },
              { max: 50, message: "租户名称最长50个字符" }
            ]}
          >
            <Input placeholder="请输入租户名称" />
          </Form.Item>
          
          {!editingTenant && (
            <Form.Item
              name="code"
              label="租户代码"
              rules={[
                { required: true, message: "请输入租户代码" },
                { pattern: /^[a-z][a-z0-9_]{2,20}$/, message: "需以小写字母开头，仅包含小写字母、数字、下划线，长度3-20" }
              ]}
            >
              <Input placeholder="如：company_a" disabled={!!editingTenant} />
            </Form.Item>
          )}
          
          <Form.Item name="description" label="描述">
            <Input.TextArea rows={3} placeholder="请输入描述信息" />
          </Form.Item>
          
          <Row gutter={16}>
            <Col span={12}>
              <Form.Item name="max_users" label="最大用户数" initialValue={10}>
                <InputNumber min={1} max={1000} style={{ width: "100%" }} />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item name="max_patents" label="最大专利数" initialValue={1000}>
                <InputNumber min={1} max={100000} style={{ width: "100%" }} />
              </Form.Item>
            </Col>
          </Row>
          
          {editingTenant && (
            <Form.Item name="is_active" label="状态" valuePropName="checked">
              <Switch checkedChildren="启用" unCheckedChildren="禁用" />
            </Form.Item>
          )}
        </Form>
      </Modal>
    </Space>
  );
}
