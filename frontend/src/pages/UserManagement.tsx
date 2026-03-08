import { useState, useEffect } from "react";
import { useSelector } from "react-redux";
import {
  Card, Table, Button, Space, Tag, Modal, Form, Input, Select, 
  Typography, message, Popconfirm, Pagination, Row, Col, Switch, InputNumber
} from "antd";
import {
  UserOutlined, PlusOutlined, EditOutlined, DeleteOutlined, 
  StopOutlined, CheckCircleOutlined, SearchOutlined
} from "@ant-design/icons";
import type { RootState } from "../store";
import { userApi, UserListParams } from "../services/userApi";
import type { User } from "../types";

const { Title, Text } = Typography;
const { Option } = Select;

export default function UserManagement() {
  const currentUser = useSelector((s: RootState) => s.auth.user);
  const [users, setUsers] = useState<User[]>([]);
  const [loading, setLoading] = useState(false);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [keyword, setKeyword] = useState("");
  const [roleFilter, setRoleFilter] = useState<string | undefined>();
  const [isActiveFilter, setIsActiveFilter] = useState<boolean | undefined>();
  const [modalVisible, setModalVisible] = useState(false);
  const [editingUser, setEditingUser] = useState<User | null>(null);
  const [form] = Form.useForm();

  useEffect(() => {
    if (currentUser?.role !== "admin") {
      return;
    }
    loadUsers();
  }, [currentUser, page, pageSize, roleFilter, isActiveFilter]);

  const loadUsers = async () => {
    if (currentUser?.role !== "admin") return;
    
    setLoading(true);
    try {
      const params: UserListParams = {
        page,
        page_size: pageSize,
        keyword: keyword || undefined,
        role: roleFilter,
        is_active: isActiveFilter,
      };
      const data = await userApi.listUsers(params);
      setUsers(data.items || []);
      setTotal(data.total || 0);
    } catch (error: any) {
      message.error(error.message || "加载用户列表失败");
    } finally {
      setLoading(false);
    }
  };

  const handleSearch = () => {
    setPage(1);
    loadUsers();
  };

  const handleAdd = () => {
    setEditingUser(null);
    form.resetFields();
    setModalVisible(true);
  };

  const handleEdit = (user: User) => {
    setEditingUser(user);
    form.setFieldsValue({
      username: user.username,
      email: user.email,
      full_name: user.full_name,
      department: user.department,
      role: user.role,
      is_active: user.is_active,
    });
    setModalVisible(true);
  };

  const handleDelete = async (userId: number) => {
    try {
      await userApi.deleteUser(userId);
      message.success("删除成功");
      loadUsers();
    } catch (error: any) {
      message.error(error.message || "删除失败");
    }
  };

  const handleToggleActive = async (user: User) => {
    try {
      await userApi.toggleUserActive(user.id);
      message.success(user.is_active ? "已禁用" : "已启用");
      loadUsers();
    } catch (error: any) {
      message.error(error.message || "操作失败");
    }
  };

  const handleSubmit = async () => {
    try {
      const values = await form.validateFields();
      
      if (editingUser) {
        await userApi.updateUser(editingUser.id, values);
        message.success("更新成功");
      } else {
        await userApi.createUser(values);
        message.success("创建成功");
      }
      
      setModalVisible(false);
      loadUsers();
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
      title: "用户名",
      dataIndex: "username",
      key: "username",
    },
    {
      title: "姓名",
      dataIndex: "full_name",
      key: "full_name",
    },
    {
      title: "邮箱",
      dataIndex: "email",
      key: "email",
    },
    {
      title: "角色",
      dataIndex: "role",
      key: "role",
      render: (role: string) => (
        <Tag color={role === "admin" ? "red" : role === "examiner" ? "blue" : "default"}>
          {role === "admin" ? "管理员" : role === "examiner" ? "审查员" : role}
        </Tag>
      ),
    },
    {
      title: "状态",
      dataIndex: "is_active",
      key: "is_active",
      render: (isActive: boolean, record: User) => (
        <Switch
          checked={isActive}
          checkedChildren="启用"
          unCheckedChildren="禁用"
          onChange={() => handleToggleActive(record)}
          disabled={record.id === currentUser?.id}
        />
      ),
    },
    {
      title: "部门",
      dataIndex: "department",
      key: "department",
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
      render: (_: any, record: User) => (
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
            title="确认删除此用户？"
            onConfirm={() => handleDelete(record.id)}
            disabled={record.id === currentUser?.id}
          >
            <Button 
              type="link" 
              danger 
              size="small" 
              icon={<DeleteOutlined />}
              disabled={record.id === currentUser?.id}
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
        <Title level={4} style={{ margin: 0 }}>用户管理</Title>
        <Button type="primary" icon={<PlusOutlined />} onClick={handleAdd}>
          添加用户
        </Button>
      </div>

      <Card size="small">
        <Row gutter={16}>
          <Col>
            <Input.Search
              placeholder="搜索用户名/姓名/邮箱"
              allowClear
              enterButton={<SearchOutlined />}
              onSearch={(value) => {
                setKeyword(value);
                setPage(1);
              }}
              style={{ width: 300 }}
            />
          </Col>
          <Col>
            <Select
              placeholder="角色"
              allowClear
              onChange={(value) => {
                setRoleFilter(value);
                setPage(1);
              }}
              style={{ width: 120 }}
            >
              <Option value="admin">管理员</Option>
              <Option value="examiner">审查员</Option>
              <Option value="viewer">查看者</Option>
            </Select>
          </Col>
          <Col>
            <Select
              placeholder="状态"
              allowClear
              onChange={(value) => {
                setIsActiveFilter(value);
                setPage(1);
              }}
              style={{ width: 100 }}
            >
              <Option value={true}>启用</Option>
              <Option value={false}>禁用</Option>
            </Select>
          </Col>
        </Row>
      </Card>

      <Card size="small">
        <Table
          columns={columns}
          dataSource={users}
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
        title={editingUser ? "编辑用户" : "添加用户"}
        open={modalVisible}
        onOk={handleSubmit}
        onCancel={() => setModalVisible(false)}
        width={500}
      >
        <Form form={form} layout="vertical">
          <Form.Item
            name="username"
            label="用户名"
            rules={[
              { required: true, message: "请输入用户名" },
              { min: 3, max: 50, message: "用户名长度为3-50个字符" }
            ]}
          >
            <Input disabled={!!editingUser} placeholder="请输入用户名" />
          </Form.Item>
          
          {!editingUser && (
            <Form.Item
              name="password"
              label="密码"
              rules={[
                { required: true, message: "请输入密码" },
                { min: 8, message: "密码至少8位，需包含大小写字母、数字和特殊字符" }
              ]}
            >
              <Input.Password placeholder="请输入密码" />
            </Form.Item>
          )}
          
          <Form.Item name="full_name" label="姓名">
            <Input placeholder="请输入姓名" />
          </Form.Item>
          
          <Form.Item name="email" label="邮箱">
            <Input placeholder="请输入邮箱" />
          </Form.Item>
          
          <Form.Item name="department" label="部门">
            <Input placeholder="请输入部门" />
          </Form.Item>
          
          <Form.Item name="role" label="角色" rules={[{ required: true }]}>
            <Select placeholder="请选择角色">
              <Option value="admin">管理员</Option>
              <Option value="examiner">审查员</Option>
              <Option value="viewer">查看者</Option>
            </Select>
          </Form.Item>
          
          {editingUser && (
            <Form.Item name="is_active" label="状态" valuePropName="checked">
              <Switch checkedChildren="启用" unCheckedChildren="禁用" />
            </Form.Item>
          )}
        </Form>
      </Modal>
    </Space>
  );
}
