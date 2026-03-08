import { useState } from "react";
import { Outlet, useNavigate, useLocation } from "react-router-dom";
import { Layout, Menu, Avatar, Dropdown, Typography, theme } from "antd";
import {
  DashboardOutlined, FileTextOutlined, AuditOutlined, SettingOutlined,
  RobotOutlined, BarChartOutlined, ToolOutlined, UserOutlined, LogoutOutlined,
  MenuFoldOutlined, MenuUnfoldOutlined, TeamOutlined, ApartmentOutlined,
  ClusterOutlined, SyncOutlined,
} from "@ant-design/icons";
import { useDispatch, useSelector } from "react-redux";
import { logout } from "../../store/slices/authSlice";
import type { RootState } from "../../store";

const { Header, Sider, Content, Footer } = Layout;

export default function AppLayout() {
  const [collapsed, setCollapsed] = useState(false);
  const navigate = useNavigate();
  const location = useLocation();
  const dispatch = useDispatch();
  const user = useSelector((s: RootState) => s.auth.user);
  const { token: { colorBgContainer } } = theme.useToken();

  const menuItems = [
    { key: "/", icon: <DashboardOutlined />, label: "工作台" },
    { key: "/patents", icon: <FileTextOutlined />, label: "专利管理" },
    { key: "/examination-dashboard", icon: <AuditOutlined />, label: "审查工作台" },
    { key: "/rules", icon: <ToolOutlined />, label: "规则引擎" },
    { key: "/workflow", icon: <SyncOutlined />, label: "工作流引擎" },
    { key: "/rag", icon: <ClusterOutlined />, label: "RAG 管理" },
    { key: "/ai", icon: <RobotOutlined />, label: "AI 助手" },
    { key: "/reports", icon: <BarChartOutlined />, label: "报告中心" },
    // Show admin menus for admin role - in incognito mode after refresh, user will be null
    // but the backend will handle authorization, so we show the menu based on isAuthenticated
    ...(user?.role === "admin" ? [
      { key: "/users", icon: <TeamOutlined />, label: "用户管理" },
      { key: "/tenants", icon: <ApartmentOutlined />, label: "租户管理" },
    ] : []),
    { key: "/settings", icon: <SettingOutlined />, label: "系统设置" },
  ];

  const userMenu = {
    items: [
      { key: "profile", icon: <UserOutlined />, label: "个人信息" },
      { key: "logout", icon: <LogoutOutlined />, label: "退出登录", danger: true },
    ],
    onClick: ({ key }: { key: string }) => {
      if (key === "logout") { dispatch(logout()); navigate("/login"); }
      if (key === "profile") navigate("/settings");
    },
  };

  return (
    <Layout style={{ minHeight: "100vh" }}>
      <Sider trigger={null} collapsible collapsed={collapsed} width={260}
        style={{ background: colorBgContainer, borderRight: "1px solid #f0f0f0" }}>
        <div style={{ height: 60, display: "flex", alignItems: "center", justifyContent: "center",
                      borderBottom: "1px solid #f0f0f0", fontWeight: 700, fontSize: collapsed ? 14 : 16, color: "#1677ff" }}>
          {collapsed ? "专审" : "专利审查辅助系统"}
        </div>
        <Menu mode="inline" selectedKeys={[location.pathname]}
          items={menuItems} onClick={({ key }) => navigate(key)}
          style={{ border: "none", marginTop: 8 }} />
      </Sider>
      <Layout>
        <Header style={{ background: colorBgContainer, padding: "0 24px", display: "flex",
                         alignItems: "center", justifyContent: "space-between", borderBottom: "1px solid #f0f0f0" }}>
          <div style={{ cursor: "pointer", fontSize: 18 }} onClick={() => setCollapsed(!collapsed)}>
            {collapsed ? <MenuUnfoldOutlined /> : <MenuFoldOutlined />}
          </div>
          <Dropdown menu={userMenu}>
            <div style={{ cursor: "pointer", display: "flex", alignItems: "center", gap: 8 }}>
              <Avatar icon={<UserOutlined />} style={{ background: "#1677ff" }} />
              <span>{user?.full_name || user?.username || "用户"}</span>
            </div>
          </Dropdown>
        </Header>
        <Content style={{ margin: 24, padding: 24, background: colorBgContainer, borderRadius: 8, minHeight: 360 }}>
          <Outlet />
        </Content>
        <Footer style={{ textAlign: "center", padding: "12px 50px", color: "#999", fontSize: 12 }}>
          专利审查辅助系统 v1.0.0 | 数据库支持: MySQL / PostgreSQL / SQLite
        </Footer>
      </Layout>
    </Layout>
  );
}
