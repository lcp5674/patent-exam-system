import { useState, useEffect } from "react";
import { useSelector } from "react-redux";
import {
  Card, Tabs, Form, Input, Button, Space, Typography, message, Descriptions,
  Switch, Table, Tag, Row, Col, Divider, Modal, Select, Popconfirm, Spin, Alert, InputNumber,
  List, Statistic, Radio,
} from "antd";
import {
  UserOutlined, LockOutlined, SettingOutlined, RobotOutlined,
  DatabaseOutlined, SaveOutlined, PlusOutlined, DeleteOutlined,
  CheckCircleOutlined, CloseCircleOutlined, EditOutlined, ApiOutlined,
  SearchOutlined, BarChartOutlined, CloudServerOutlined, GlobalOutlined, CodeOutlined,
} from "@ant-design/icons";
import type { RootState } from "../store";
import api from "../services/api";
import { aiApi, AIProviderConfig } from "../services/aiApi";
import { ragApi } from "../services/ragApi";
import { changeLanguage, getCurrentLanguage, supportedLanguages } from "../i18n";

const { Title, Text, Paragraph } = Typography;
const { Option } = Select;

// 语言选择器组件
function LanguageSelector() {
  const [currentLang, setCurrentLang] = useState(getCurrentLanguage());
  const [, forceUpdate] = useState({});

  const handleLanguageChange = (lang: string) => {
    changeLanguage(lang);
    setCurrentLang(lang);
    // 强制重新渲染以应用新语言
    forceUpdate({});
    message.success("语言已切换");
  };

  return (
    <Radio.Group
      value={currentLang}
      onChange={(e) => handleLanguageChange(e.target.value)}
      optionType="button"
      buttonStyle="solid"
    >
      {supportedLanguages.map((lang) => (
        <Radio.Button key={lang.code} value={lang.code}>
          <Space>
            <GlobalOutlined />
            {lang.nativeName}
          </Space>
        </Radio.Button>
      ))}
    </Radio.Group>
  );
}

const PROVIDER_TEMPLATES = [
  { provider_name: "openai", display_name: "OpenAI (GPT)", base_url: "https://api.openai.com/v1", default_model: "gpt-4o" },
  { provider_name: "doubao", display_name: "豆包 (Doubao)", base_url: "https://ark.cn-beijing.volces.com/api/v3", default_model: "doubao-pro-32k" },
  { provider_name: "minimax", display_name: "MiniMax", base_url: "https://api.minimax.chat/v1", default_model: "abab6.5s-chat" },
  { provider_name: "openrouter", display_name: "OpenRouter", base_url: "https://openrouter.ai/api/v1", default_model: "openai/gpt-4o" },
  { provider_name: "ollama", display_name: "Ollama (本地)", base_url: "http://localhost:11434", default_model: "qwen2.5:7b" },
  { provider_name: "zhipu", display_name: "智谱 AI (ChatGLM)", base_url: "https://open.bigmodel.cn/api/paas/v4", default_model: "glm-4" },
  { provider_name: "gemini", display_name: "Google Gemini", base_url: "https://generativelanguage.googleapis.com", default_model: "gemini-1.5-flash" },
];

export default function Settings() {
  const user = useSelector((s: RootState) => s.auth.user);
  const [profileForm] = Form.useForm();
  const [passwordForm] = Form.useForm();
  const [profileLoading, setProfileLoading] = useState(false);
  const [passwordLoading, setPasswordLoading] = useState(false);
  const [providers, setProviders] = useState<any[]>([]);
  const [providerConfigs, setProviderConfigs] = useState<AIProviderConfig[]>([]);
  const [systemInfo, setSystemInfo] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [configModal, setConfigModal] = useState<{ visible: boolean; config?: AIProviderConfig }>({ visible: false });
  const [configForm] = Form.useForm();
  const [testingProvider, setTestingProvider] = useState<string | null>(null);
  
  // RAG状态
  const [ragConfig, setRagConfig] = useState<any>(null);
  const [ragHealth, setRagHealth] = useState<any>(null);
  const [ragStats, setRagStats] = useState<any>(null);
  const [patentSources, setPatentSources] = useState<any[]>([]);
  const [ragLoading, setRagLoading] = useState(false);
  const [patentSearchResults, setPatentSearchResults] = useState<any>(null);
  const [patentSearchLoading, setPatentSearchLoading] = useState(false);

  useEffect(() => {
    loadProviders();
    loadProviderConfigs();
    loadSystemInfo();
    loadRAGConfig();
    loadRAGHealth();
    loadRAGStats();
    loadPatentSources();
  }, []);

  useEffect(() => {
    if (user) {
      profileForm.setFieldsValue({
        username: user.username,
        full_name: user.full_name,
        email: user.email,
      });
    }
  }, [user, profileForm]);

  const loadProviders = async () => {
    try {
      const res = await aiApi.getProviders();
      setProviders(res.providers || []);
    } catch {}
  };

  const loadProviderConfigs = async () => {
    setLoading(true);
    try {
      const configs = await aiApi.getProviderConfigs();
      setProviderConfigs(configs);
    } catch (error) {
      console.error("加载配置失败:", error);
    } finally {
      setLoading(false);
    }
  };

  const loadSystemInfo = async () => {
    try {
      const res = await api.get("/system/info");
      setSystemInfo(res.data);
    } catch {}
  };

  // RAG加载函数
  const loadRAGConfig = async () => {
    try {
      const config = await ragApi.getConfig();
      setRagConfig(config);
    } catch (error) {
      console.error("加载RAG配置失败:", error);
    }
  };

  const loadRAGHealth = async () => {
    try {
      const health = await ragApi.getHealth();
      setRagHealth(health);
    } catch (error) {
      console.error("加载RAG健康状态失败:", error);
    }
  };

  const loadRAGStats = async () => {
    try {
      const stats = await ragApi.getStats();
      setRagStats(stats);
    } catch (error) {
      console.error("加载RAG统计失败:", error);
    }
  };

  const loadPatentSources = async () => {
    try {
      const sources = await ragApi.getPatentSources();
      setPatentSources(sources.connectors || []);
    } catch (error) {
      console.error("加载专利数据源失败:", error);
    }
  };

  const handlePatentSearch = async (values: any) => {
    setPatentSearchLoading(true);
    try {
      const results = await ragApi.searchPatents({
        query: values.query,
        sources: values.sources,
        max_results: values.max_results || 10,
        auto_index: values.auto_index || false,
      });
      setPatentSearchResults(results);
      message.success(`找到 ${results.total_count} 条专利`);
    } catch (error: any) {
      message.error(error.message || "搜索失败");
    } finally {
      setPatentSearchLoading(false);
    }
  };

  const handleProfileUpdate = async (values: any) => {
    setProfileLoading(true);
    try {
      await api.put("/users/me", values);
      message.success("个人信息更新成功");
    } catch {
      message.error("更新失败");
    } finally {
      setProfileLoading(false);
    }
  };

  const handlePasswordChange = async (values: any) => {
    setPasswordLoading(true);
    try {
      await api.post("/users/change-password", {
        old_password: values.old_password,
        new_password: values.new_password,
      });
      message.success("密码修改成功");
      passwordForm.resetFields();
    } catch {
      message.error("密码修改失败");
    } finally {
      setPasswordLoading(false);
    }
  };

  const handleAddConfig = () => {
    configForm.resetFields();
    setConfigModal({ visible: true });
  };

  const handleEditConfig = (config: AIProviderConfig) => {
    configForm.setFieldsValue({
      ...config,
      api_key: config.api_key ? "••••••••" : "",
    });
    setConfigModal({ visible: true, config });
  };

  const handleSaveConfig = async () => {
    try {
      const values = await configForm.validateFields();
      
      if (values.api_key === "••••••••") {
        delete values.api_key;
      }
      
      if (configModal.config?.provider_name) {
        await aiApi.updateProviderConfig(configModal.config.provider_name, values);
        message.success("配置更新成功");
      } else {
        await aiApi.createProviderConfig(values);
        message.success("配置创建成功");
      }
      
      setConfigModal({ visible: false });
      loadProviderConfigs();
      loadProviders();
    } catch (error: any) {
      message.error(error.message || "保存失败");
    }
  };

  const handleDeleteConfig = async (providerName: string) => {
    try {
      await aiApi.deleteProviderConfig(providerName);
      message.success("配置已删除");
      loadProviderConfigs();
      loadProviders();
    } catch {
      message.error("删除失败");
    }
  };

  const handleTestProvider = async (providerName: string) => {
    setTestingProvider(providerName);
    try {
      const result = await aiApi.testProvider(providerName);
      if (result.status === "ok") {
        message.success("连接成功!");
      } else {
        message.error(result.message || "连接失败");
      }
    } catch (error: any) {
      message.error(error.message || "测试失败");
    } finally {
      setTestingProvider(null);
    }
  };

  const handleToggleEnabled = async (config: AIProviderConfig, checked: boolean) => {
    try {
      await aiApi.updateProviderConfig(config.provider_name, { is_enabled: checked });
      message.success(checked ? "已启用" : "已禁用");
      loadProviderConfigs();
      loadProviders();
    } catch {
      message.error("操作失败");
    }
  };

  const handleSetDefault = async (config: AIProviderConfig) => {
    try {
      await aiApi.updateProviderConfig(config.provider_name, { is_default: true });
      message.success("已设为默认");
      loadProviderConfigs();
    } catch {
      message.error("操作失败");
    }
  };

  const providerColumns = [
    { title: "提供商", dataIndex: "display_name", key: "display_name",
      render: (t: string, r: any) => <Text strong>{t || r.name}</Text> },
    { title: "标识", dataIndex: "provider_name", key: "provider_name",
      render: (t: string) => <Tag>{t}</Tag> },
    { title: "API Key", dataIndex: "api_key", key: "api_key",
      render: (k: string) => k ? <Text code>{k.length > 4 ? '••••' + k.slice(-4) : '••••'}</Text> : <Text type="secondary">未设置</Text> },
    { title: "状态", dataIndex: "is_enabled", key: "is_enabled",
      render: (a: boolean, r: any) => a
        ? <Tag color="success">已启用</Tag>
        : <Tag color="default">已禁用</Tag>,
    },
    { title: "可用", dataIndex: "is_available", key: "is_available",
      render: (a: boolean) => a
        ? <Tag color="success">可用</Tag>
        : <Tag color="default">未配置</Tag>,
    },
    { title: "默认", dataIndex: "is_default", key: "is_default",
      render: (a: boolean) => a
        ? <Tag color="blue">默认</Tag>
        : null,
    },
    { title: "操作", key: "action", width: 200,
      render: (_: any, r: AIProviderConfig) => (
        <Space>
          <Button type="link" size="small" icon={<EditOutlined />} onClick={() => handleEditConfig(r)}>
            编辑
          </Button>
          <Button type="link" size="small" icon={<CheckCircleOutlined />} 
            loading={testingProvider === r.provider_name}
            onClick={() => handleTestProvider(r.provider_name)}>
            测试
          </Button>
          <Popconfirm title="确认删除?" onConfirm={() => handleDeleteConfig(r.provider_name)}>
            <Button type="link" danger size="small" icon={<DeleteOutlined />}>
              删除
            </Button>
          </Popconfirm>
        </Space>
      ),
    },
  ];

  return (
    <Space direction="vertical" size="middle" style={{ width: "100%" }}>
      <Title level={4} style={{ margin: 0 }}>系统设置</Title>

      <Tabs defaultActiveKey="profile" items={[
        {
          key: "profile",
          label: <span><UserOutlined /> 个人信息</span>,
          children: (
            <Row gutter={24}>
              <Col xs={24} lg={12}>
                <Card title="基本信息" size="small">
                  <Form form={profileForm} layout="vertical" onFinish={handleProfileUpdate}>
                    <Form.Item name="username" label="用户名">
                      <Input disabled />
                    </Form.Item>
                    <Form.Item name="full_name" label="姓名">
                      <Input placeholder="请输入姓名" />
                    </Form.Item>
                    <Form.Item name="email" label="邮箱">
                      <Input placeholder="请输入邮箱" />
                    </Form.Item>
                    <Form.Item>
                      <Button type="primary" htmlType="submit" icon={<SaveOutlined />}
                        loading={profileLoading}>
                        保存修改
                      </Button>
                    </Form.Item>
                  </Form>
                </Card>
              </Col>
              <Col xs={24} lg={12}>
                <Card title="修改密码" size="small">
                  <Form form={passwordForm} layout="vertical" onFinish={handlePasswordChange}>
                    <Form.Item name="old_password" label="当前密码"
                      rules={[{ required: true, message: "请输入当前密码" }]}>
                      <Input.Password placeholder="当前密码" />
                    </Form.Item>
                    <Form.Item name="new_password" label="新密码"
                      rules={[
                        { required: true, message: "请输入新密码" },
                        { min: 6, message: "密码至少6位" },
                      ]}>
                      <Input.Password placeholder="新密码" />
                    </Form.Item>
                    <Form.Item name="confirm_password" label="确认新密码"
                      dependencies={["new_password"]}
                      rules={[
                        { required: true, message: "请确认新密码" },
                        ({ getFieldValue }) => ({
                          validator(_, value) {
                            if (!value || getFieldValue("new_password") === value) return Promise.resolve();
                            return Promise.reject(new Error("两次输入的密码不一致"));
                          },
                        }),
                      ]}>
                      <Input.Password placeholder="再次输入新密码" />
                    </Form.Item>
                    <Form.Item>
                      <Button type="primary" htmlType="submit" icon={<LockOutlined />}
                        loading={passwordLoading}>
                        修改密码
                      </Button>
                    </Form.Item>
                  </Form>
                </Card>
              </Col>
            </Row>
          ),
        },
        {
          key: "ai",
          label: <span><RobotOutlined /> AI 模型配置</span>,
          children: (
            <Spin spinning={loading}>
              <Space direction="vertical" size="middle" style={{ width: "100%" }}>
                {user?.role === "admin" && (
                  <Alert type="info" showIcon
                    message="AI 模型配置"
                    description="在此处配置您的 AI 模型 API Key。配置后将自动保存到数据库，无需修改后端代码。" />
                )}
                
                <Card 
                  title="已配置的 AI 提供商" 
                  size="small"
                  extra={
                    user?.role === "admin" && (
                      <Button type="primary" icon={<PlusOutlined />} onClick={handleAddConfig}>
                        添加配置
                      </Button>
                    )
                  }
                >
                  <Table 
                    columns={providerColumns} 
                    dataSource={providerConfigs} 
                    rowKey="provider_name"
                    pagination={false} 
                    size="small" 
                    locale={{ emptyText: "暂无配置，请添加 AI 提供商配置" }}
                  />
                </Card>

                <Card title="快速添加模板" size="small">
                  <Text type="secondary">点击以下模板快速添加常用 AI 提供商：</Text>
                  <Divider style={{ margin: "12px 0" }} />
                  <Space wrap>
                    {PROVIDER_TEMPLATES.map((t) => (
                      <Button 
                        key={t.provider_name}
                        icon={<ApiOutlined />}
                        onClick={() => {
                          configForm.setFieldsValue({
                            provider_name: t.provider_name,
                            display_name: t.display_name,
                            base_url: t.base_url,
                            default_model: t.default_model,
                            is_enabled: true,
                            is_default: false,
                            priority: 0,
                          });
                          setConfigModal({ visible: true });
                        }}
                      >
                        {t.display_name}
                      </Button>
                    ))}
                  </Space>
                </Card>

                <Card title="支持的功能" size="small">
                  <Descriptions column={{ xs: 1, sm: 2 }} bordered size="small">
                    <Descriptions.Item label="OpenAI (GPT)">GPT-4o, GPT-4, GPT-3.5</Descriptions.Item>
                    <Descriptions.Item label="豆包">Doubao Pro, Doubao Lite</Descriptions.Item>
                    <Descriptions.Item label="MiniMax">ABAB6.5, ABAB6</Descriptions.Item>
                    <Descriptions.Item label="OpenRouter">150+ 模型</Descriptions.Item>
                    <Descriptions.Item label="Ollama">本地部署模型</Descriptions.Item>
                    <Descriptions.Item label="智谱 AI">GLM-4, GLM-3</Descriptions.Item>
                    <Descriptions.Item label="Google Gemini">Gemini 2.0, Gemini 1.5</Descriptions.Item>
                  </Descriptions>
                </Card>
              </Space>
            </Spin>
          ),
        },
        {
          key: "system",
          label: <span><SettingOutlined /> 系统信息</span>,
          children: (
            <Space direction="vertical" size="middle" style={{ width: "100%" }}>
              <Card title="系统状态" size="small">
                {systemInfo ? (
                  <Descriptions column={{ xs: 1, sm: 2 }} bordered size="small">
                    <Descriptions.Item label="系统版本">{systemInfo.version || "1.0.0"}</Descriptions.Item>
                    <Descriptions.Item label="数据库类型">
                      <Tag color="blue">{systemInfo.database_type || "unknown"}</Tag>
                    </Descriptions.Item>
                    <Descriptions.Item label="运行状态">
                      <Tag color="success">正常运行</Tag>
                    </Descriptions.Item>
                    <Descriptions.Item label="API版本">{systemInfo.api_version || "v1"}</Descriptions.Item>
                  </Descriptions>
                ) : (
                  <Alert type="warning" message="无法获取系统信息，请确认后端服务是否正常运行" />
                )}
              </Card>
              <Card title="支持的数据库" size="small">
                <Row gutter={16}>
                  {[
                    { name: "SQLite", desc: "轻量级，适合开发和小型部署", color: "#1677ff" },
                    { name: "PostgreSQL", desc: "企业级，推荐生产环境使用", color: "#336791" },
                    { name: "MySQL", desc: "广泛使用的关系型数据库", color: "#4479A1" },
                  ].map((db) => (
                    <Col span={8} key={db.name}>
                      <Card size="small" style={{ borderTop: `3px solid ${db.color}`, textAlign: "center" }}>
                        <DatabaseOutlined style={{ fontSize: 28, color: db.color }} />
                        <Title level={5} style={{ marginTop: 8 }}>{db.name}</Title>
                        <Text type="secondary" style={{ fontSize: 12 }}>{db.desc}</Text>
                      </Card>
                    </Col>
                  ))}
                </Row>
              </Card>
            </Space>
          ),
        },
        // 语言设置标签页
        {
          key: "language",
          label: <span><SettingOutlined /> 语言设置</span>,
          children: (
            <Card title="界面语言" size="small">
              <Space direction="vertical" size="middle" style={{ width: "100%" }}>
                <Alert 
                  type="info" 
                  message="语言设置" 
                  description="选择系统界面显示的语言。更改后刷新页面生效。"
                />
                <Form layout="vertical">
                  <Form.Item label="选择语言">
                    <LanguageSelector />
                  </Form.Item>
                </Form>
              </Space>
            </Card>
          ),
        },
        // RAG配置标签页
        {
          key: "rag",
          label: <span><SearchOutlined /> RAG增强</span>,
          children: (
            <Spin spinning={ragLoading}>
              <Space direction="vertical" size="middle" style={{ width: "100%" }}>
                {/* RAG状态概览 */}
                <Row gutter={16}>
                  <Col xs={24} lg={8}>
                    <Card size="small" title="向量数据库">
                      <Descriptions column={1} size="small">
                        <Descriptions.Item label="类型">{ragHealth?.vector_db || ragConfig?.vector_db_type || "Chroma"}</Descriptions.Item>
                        <Descriptions.Item label="文档数">{ragStats?.document_count || 0}</Descriptions.Item>
                        <Descriptions.Item label="状态">
                          <Tag color={ragHealth?.status === "healthy" ? "green" : "red"}>
                            {ragHealth?.status === "healthy" ? "正常" : "异常"}
                          </Tag>
                        </Descriptions.Item>
                      </Descriptions>
                    </Card>
                  </Col>
                  <Col xs={24} lg={8}>
                    <Card size="small" title="嵌入模型">
                      <Descriptions column={1} size="small">
                        <Descriptions.Item label="模型">{ragConfig?.embedding_model || "-"}</Descriptions.Item>
                        <Descriptions.Item label="维度">{ragConfig?.embedding_dimension || "-"}</Descriptions.Item>
                        <Descriptions.Item label="分块大小">{ragConfig?.chunk_size || 512}</Descriptions.Item>
                      </Descriptions>
                    </Card>
                  </Col>
                  <Col xs={24} lg={8}>
                    <Card size="small" title="检索配置">
                      <Descriptions column={1} size="small">
                        <Descriptions.Item label="搜索类型">{ragConfig?.search_type || "hybrid"}</Descriptions.Item>
                        <Descriptions.Item label="Top K">{ragConfig?.retrieval_top_k || 10}</Descriptions.Item>
                        <Descriptions.Item label="重排序">
                          <Switch checked={ragConfig?.rerank_enabled} disabled />
                        </Descriptions.Item>
                      </Descriptions>
                    </Card>
                  </Col>
                </Row>

                {/* 专利数据源 */}
                <Card title="公开专利数据库" size="small">
                  <Row gutter={16}>
                    {patentSources.map((source: any) => (
                      <Col xs={12} sm={8} md={6} key={source.name}>
                        <Card size="small" hoverable style={{ textAlign: "center" }}>
                          <CloudServerOutlined style={{ fontSize: 24, color: source.available ? "#52c41a" : "#ff4d4f" }} />
                          <div style={{ marginTop: 8 }}>
                            <Text strong>{source.name.toUpperCase()}</Text>
                          </div>
                          <Tag color={source.available ? "success" : "default"} style={{ marginTop: 4 }}>
                            {source.available ? "可用" : "未配置"}
                          </Tag>
                        </Card>
                      </Col>
                    ))}
                  </Row>
                </Card>

                {/* 专利搜索 */}
                <Card 
                  title="公开专利搜索" 
                  size="small"
                  extra={
                    <Button 
                      type="link" 
                      icon={<SearchOutlined />}
                      onClick={() => loadPatentSources()}
                    >
                      刷新
                    </Button>
                  }
                >
                  <Form layout="vertical" onFinish={handlePatentSearch}>
                    <Row gutter={16}>
                      <Col xs={24} lg={12}>
                        <Form.Item name="query" label="搜索关键词" rules={[{ required: true }]}>
                          <Input placeholder="输入专利名称、关键词..." />
                        </Form.Item>
                      </Col>
                      <Col xs={12} lg={4}>
                        <Form.Item name="max_results" label="结果数" initialValue={10}>
                          <InputNumber min={1} max={50} style={{ width: "100%" }} />
                        </Form.Item>
                      </Col>
                      <Col xs={12} lg={4}>
                        <Form.Item name="auto_index" label="自动索引" valuePropName="checked" initialValue={false}>
                          <Switch checkedChildren="是" unCheckedChildren="否" />
                        </Form.Item>
                      </Col>
                      <Col xs={24} lg={4}>
                        <Form.Item label=" ">
                          <Button type="primary" htmlType="submit" loading={patentSearchLoading} icon={<SearchOutlined />}>
                            搜索
                          </Button>
                        </Form.Item>
                      </Col>
                    </Row>
                    <Form.Item name="sources" label="数据源" initialValue={["uspto"]}>
                      <Select mode="multiple" placeholder="选择数据源">
                        {patentSources.map((s: any) => (
                          <Option key={s.name} value={s.name} disabled={!s.available}>
                            {s.name.toUpperCase()} {!s.available && "(未配置)"}
                          </Option>
                        ))}
                      </Select>
                    </Form.Item>
                  </Form>

                  {/* 搜索结果 */}
                  {patentSearchResults && (
                    <div style={{ marginTop: 16 }}>
                      <Divider>搜索结果 ({patentSearchResults.total_count})</Divider>
                      {Object.entries(patentSearchResults.results).map(([source, patents]: [string, any]) => (
                        <Card key={source} size="small" title={`${source.toUpperCase()} (${patents.length})`} style={{ marginBottom: 8 }}>
                          {patents.length === 0 ? (
                            <Text type="secondary">无结果</Text>
                          ) : (
                            <List
                              size="small"
                              dataSource={patents.slice(0, 5)}
                              renderItem={(item: any) => (
                                <List.Item>
                                  <Space direction="vertical" size={0}>
                                    <Text strong>{item.title?.slice(0, 50) || "无标题"}...</Text>
                                    <Text type="secondary" style={{ fontSize: 12 }}>
                                      {item.publication_number} | {item.publication_date}
                                    </Text>
                                  </Space>
                                </List.Item>
                              )}
                            />
                          )}
                        </Card>
                      ))}
                    </div>
                  )}
                </Card>

                {/* RAG统计图表占位 */}
                <Card title="索引统计" size="small">
                  <Row gutter={16}>
                    <Col span={8}>
                      <Statistic title="总文档数" value={ragStats?.document_count || 0} />
                    </Col>
                    <Col span={8}>
                      <Statistic title="向量维度" value={ragConfig?.embedding_dimension || 1024} />
                    </Col>
                    <Col span={8}>
                      <Statistic title="检索延迟" value={ragStats?.latency_ms || 0} suffix="ms" />
                    </Col>
                  </Row>
                </Card>
              </Space>
            </Spin>
          ),
        },
        {
          key: "system",
          label: <span><SettingOutlined /> 系统配置</span>,
          children: (
            <SystemConfigTab />
          ),
        },
      ]} />

      <Modal
        title={configModal.config?.provider_name ? "编辑 AI 提供商配置" : "添加 AI 提供商配置"}
        open={configModal.visible}
        onOk={handleSaveConfig}
        onCancel={() => setConfigModal({ visible: false })}
        width={600}
        okText="保存"
        cancelText="取消"
      >
        <Form form={configForm} layout="vertical">
          <Form.Item name="provider_name" label="提供商标识"
            rules={[{ required: true, message: "请输入提供商标识" }]}>
            <Input placeholder="如: openai, doubao, minimax" disabled={!!configModal.config?.provider_name} />
          </Form.Item>
          
          <Form.Item name="display_name" label="显示名称"
            rules={[{ required: true, message: "请输入显示名称" }]}>
            <Input placeholder="如: OpenAI (GPT)" />
          </Form.Item>
          
          <Form.Item name="api_key" label="API Key"
            rules={[{ required: true, message: "请输入 API Key" }]}>
            <Input.Password placeholder="请输入 API Key（留空则使用环境变量）" />
          </Form.Item>
          
          <Form.Item name="base_url" label="API 地址">
            <Input placeholder="如: https://api.openai.com/v1" />
          </Form.Item>
          
          <Form.Item name="default_model" label="默认模型">
            <Input placeholder="如: gpt-4o" />
          </Form.Item>
          
          <Row gutter={16}>
            <Col span={12}>
              <Form.Item name="is_enabled" label="启用状态" valuePropName="checked">
                <Switch checkedChildren="启用" unCheckedChildren="禁用" />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item name="is_default" label="设为默认" valuePropName="checked">
                <Switch checkedChildren="默认" unCheckedChildren="非默认" />
              </Form.Item>
            </Col>
          </Row>
          
          <Form.Item name="priority" label="优先级">
            <InputNumber min={0} max={100} style={{ width: "100%" }} />
          </Form.Item>
        </Form>
      </Modal>
    </Space>
  );
}

interface SystemConfig {
  id: number;
  config_key: string;
  config_value: string;
  config_type: string;
  category: string;
  description: string;
  is_sensitive: boolean;
  is_user_configurable: boolean;
  is_public: boolean;
}

function SystemConfigTab() {
  const [configs, setConfigs] = useState<SystemConfig[]>([]);
  const [categories, setCategories] = useState<{name: string; count: number}[]>([]);
  const [loading, setLoading] = useState(false);
  const [selectedCategory, setSelectedCategory] = useState<string | null>(null);
  const [editModal, setEditModal] = useState<{ visible: boolean; config?: SystemConfig }>({ visible: false });
  const [editForm] = Form.useForm();
  const [saving, setSaving] = useState(false);
  const [initializing, setInitializing] = useState(false);

  useEffect(() => {
    loadCategories();
    loadConfigs();
  }, []);

  useEffect(() => {
    loadConfigs();
  }, [selectedCategory]);

  const loadCategories = async () => {
    try {
      const res = await api.get("/system/configs/categories");
      if (res.data?.code === 200) {
        setCategories(res.data.data || []);
      }
    } catch (error) {
      console.error("加载分类失败:", error);
    }
  };

  const loadConfigs = async () => {
    setLoading(true);
    try {
      const url = selectedCategory 
        ? `/system/configs?category=${selectedCategory}` 
        : "/system/configs";
      const res = await api.get(url);
      if (res.data?.code === 200) {
        setConfigs(res.data.data || []);
      }
    } catch (error) {
      console.error("加载配置失败:", error);
    } finally {
      setLoading(false);
    }
  };

  const handleEdit = (config: SystemConfig) => {
    setEditModal({ visible: true, config });
    editForm.setFieldsValue({
      config_value: config.is_sensitive ? "" : config.config_value,
      description: config.description,
      is_user_configurable: config.is_user_configurable,
      is_public: config.is_public,
    });
  };

  const handleSave = async (values: any) => {
    if (!editModal.config) return;
    
    setSaving(true);
    try {
      const res = await api.put(`/system/configs/${editModal.config.config_key}`, values);
      if (res.data?.code === 200) {
        message.success("配置更新成功");
        setEditModal({ visible: false });
        loadConfigs();
      } else {
        message.error(res.data?.message || "更新失败");
      }
    } catch (error: any) {
      message.error(error.response?.data?.detail || "更新失败");
    } finally {
      setSaving(false);
    }
  };

  const handleInitialize = async () => {
    setInitializing(true);
    try {
      const res = await api.post("/system/configs/initialize");
      if (res.data?.code === 200) {
        message.success(`成功初始化 ${res.data.data.created_count} 个配置`);
        loadConfigs();
        loadCategories();
      }
    } catch (error: any) {
      message.error(error.response?.data?.detail || "初始化失败");
    } finally {
      setInitializing(false);
    }
  };

  const getTypeTag = (type: string) => {
    const tags: Record<string, { color: string; text: string }> = {
      string: { color: "blue", text: "字符串" },
      number: { color: "green", text: "数字" },
      boolean: { color: "orange", text: "布尔" },
      json: { color: "purple", text: "JSON" },
    };
    const tag = tags[type] || { color: "default", text: type };
    return <Tag color={tag.color}>{tag.text}</Tag>;
  };

  const columns = [
    {
      title: "配置键",
      dataIndex: "config_key",
      key: "config_key",
      width: 200,
      render: (key: string, record: SystemConfig) => (
        <Space>
          <CodeOutlined />
          <Text code>{key}</Text>
          {record.is_sensitive && <Tag color="red">敏感</Tag>}
        </Space>
      ),
    },
    {
      title: "配置值",
      dataIndex: "config_value",
      key: "config_value",
      render: (value: string, record: SystemConfig) => (
        <Text style={{ maxWidth: 200 }} ellipsis>
          {record.is_sensitive ? "••••••••" : value || "-"}
        </Text>
      ),
    },
    {
      title: "类型",
      dataIndex: "config_type",
      key: "config_type",
      width: 80,
      render: (type: string) => getTypeTag(type),
    },
    {
      title: "分类",
      dataIndex: "category",
      key: "category",
      width: 100,
      render: (cat: string) => <Tag>{cat || "general"}</Tag>,
    },
    {
      title: "描述",
      dataIndex: "description",
      key: "description",
      ellipsis: true,
    },
    {
      title: "操作",
      key: "action",
      width: 120,
      render: (_: any, record: SystemConfig) => (
        <Space>
          <Button 
            type="link" 
            size="small" 
            icon={<EditOutlined />}
            onClick={() => handleEdit(record)}
          >
            编辑
          </Button>
        </Space>
      ),
    },
  ];

  return (
    <Space direction="vertical" size="middle" style={{ width: "100%" }}>
      <Row justify="space-between" align="middle">
        <Col>
          <Space>
            <Text strong>分类筛选:</Text>
            <Select
              style={{ width: 150 }}
              placeholder="选择分类"
              allowClear
              value={selectedCategory}
              onChange={setSelectedCategory}
            >
              {categories.map((cat) => (
                <Option key={cat.name} value={cat.name}>
                  {cat.name} ({cat.count})
                </Option>
              ))}
            </Select>
          </Space>
        </Col>
        <Col>
          <Button 
            icon={<SettingOutlined />} 
            onClick={handleInitialize}
            loading={initializing}
          >
            初始化默认配置
          </Button>
        </Col>
      </Row>

      <Table
        columns={columns}
        dataSource={configs}
        rowKey="id"
        loading={loading}
        pagination={{ pageSize: 20 }}
        size="small"
      />

      <Modal
        title={`编辑配置: ${editModal.config?.config_key}`}
        open={editModal.visible}
        onOk={() => editForm.submit()}
        onCancel={() => setEditModal({ visible: false })}
        confirmLoading={saving}
        width={500}
      >
        <Form form={editForm} layout="vertical" onFinish={handleSave}>
          <Form.Item name="config_value" label="配置值">
            <Input.Password 
              placeholder={editModal.config?.is_sensitive ? "留空保持原值" : "请输入配置值"} 
            />
          </Form.Item>
          
          <Form.Item name="description" label="描述">
            <Input.TextArea rows={2} placeholder="配置描述" />
          </Form.Item>
          
          <Form.Item name="is_user_configurable" label="用户可配置" valuePropName="checked">
            <Switch checkedChildren="是" unCheckedChildren="否" />
          </Form.Item>
          
          <Form.Item name="is_public" label="公开配置" valuePropName="checked">
            <Switch checkedChildren="是" unCheckedChildren="否" />
          </Form.Item>
        </Form>
      </Modal>
    </Space>
  );
}
