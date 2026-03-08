import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useDispatch } from "react-redux";
import { Form, Input, Button, Card, Typography, message, Space } from "antd";
import { UserOutlined, LockOutlined } from "@ant-design/icons";
import { setCredentials } from "../store/slices/authSlice";
import { userApi } from "../services/userApi";

const { Title, Text } = Typography;

export default function Login() {
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();
  const dispatch = useDispatch();

  const onFinish = async (values: { username: string; password: string }) => {
    setLoading(true);
    try {
      const res = await userApi.login(values.username, values.password);
      dispatch(setCredentials({ user: res.user, token: res.access_token }));
      message.success("登录成功");
      navigate("/");
    } catch (err: any) {
      message.error(err?.response?.data?.detail || "登录失败，请检查用户名和密码");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{
      minHeight: "100vh", display: "flex", alignItems: "center", justifyContent: "center",
      background: "linear-gradient(135deg, #667eea 0%, #764ba2 100%)",
    }}>
      <Card style={{ width: 420, borderRadius: 12, boxShadow: "0 20px 60px rgba(0,0,0,0.3)" }}>
        <Space direction="vertical" size="large" style={{ width: "100%", textAlign: "center" }}>
          <div>
            <Title level={3} style={{ marginBottom: 4, color: "#1677ff" }}>专利审查辅助系统</Title>
            <Text type="secondary">Utility Patent Examination Assistant</Text>
          </div>
          <Form name="login" onFinish={onFinish} size="large" style={{ textAlign: "left" }}>
            <Form.Item name="username" rules={[{ required: true, message: "请输入用户名" }]}>
              <Input prefix={<UserOutlined />} placeholder="用户名" autoFocus />
            </Form.Item>
            <Form.Item name="password" rules={[{ required: true, message: "请输入密码" }]}>
              <Input.Password prefix={<LockOutlined />} placeholder="密码" />
            </Form.Item>
            <Form.Item>
              <Button type="primary" htmlType="submit" block loading={loading}>
                登 录
              </Button>
            </Form.Item>
          </Form>
          <Text type="secondary" style={{ fontSize: 12 }}>
            默认管理员: admin / admin123
          </Text>
        </Space>
      </Card>
    </div>
  );
}
