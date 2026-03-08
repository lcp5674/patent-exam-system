import { useState, useRef, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import {
  Card, Row, Col, Input, Button, Space, Typography, Select, Tag, Spin,
  message, List, Avatar, Divider, Tabs, Empty, Descriptions,
} from "antd";
import {
  SendOutlined, RobotOutlined, UserOutlined, ClearOutlined,
  ThunderboltOutlined, FileSearchOutlined, SafetyCertificateOutlined,
  BulbOutlined, ReloadOutlined,
} from "@ant-design/icons";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { aiApi } from "../services/aiApi";
import { patentApi } from "../services/patentApi";

const { Title, Text, Paragraph } = Typography;
const { TextArea } = Input;

interface ChatMessage {
  role: "user" | "assistant";
  content: string;
  timestamp: Date;
}

interface PatentOption {
  id: number;
  title: string;
  application_number: string;
  applicant: string;
}

const quickActions = [
  { key: "novelty", label: "新颖性分析", icon: <FileSearchOutlined />, prompt: "新颖性分析" },
  { key: "inventiveness", label: "创造性评估", icon: <BulbOutlined />, prompt: "创造性评估" },
  { key: "claims", label: "权利要求审查", icon: <SafetyCertificateOutlined />, prompt: "权利要求审查" },
  { key: "comprehensive", label: "综合评估", icon: <ThunderboltOutlined />, prompt: "综合评估" },
];

export default function AIAssistant() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [providers, setProviders] = useState<any[]>([]);
  const [selectedProvider, setSelectedProvider] = useState<string>("");
  const [selectedModel, setSelectedModel] = useState<string>("");
  const [patents, setPatents] = useState<PatentOption[]>([]);
  const [selectedPatent, setSelectedPatent] = useState<PatentOption | null>(null);
  const chatEndRef = useRef<HTMLDivElement>(null);
  const navigate = useNavigate();

  useEffect(() => {
    loadProviders();
    loadPatents();
  }, []);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const loadProviders = async () => {
    try {
      // 使用 getProviderConfigs 获取已配置的提供商，与系统设置保持同步
      const configs = await aiApi.getProviderConfigs();
      console.log("AI提供商配置返回:", configs);
      
      // 只显示已启用的提供商
      const enabledProviders = configs.filter((p: any) => p.is_enabled);
      console.log("已启用的提供商:", enabledProviders);
      setProviders(enabledProviders);
      
      if (enabledProviders.length > 0) {
        // 优先选择默认配置的提供商
        const defaultProvider = enabledProviders.find((p: any) => p.is_default === true);
        if (defaultProvider) {
          setSelectedProvider(defaultProvider.provider_name);
          setSelectedModel(defaultProvider.default_model || "");
        } else {
          // 如果没有设置默认，使用第一个可用的
          setSelectedProvider(enabledProviders[0].provider_name);
          setSelectedModel(enabledProviders[0].default_model || "");
        }
      } else {
        setSelectedProvider("");
        setSelectedModel("");
      }
    } catch {
      // Providers may not be configured yet
      setProviders([]);
      setSelectedProvider("");
      setSelectedModel("");
    }
  };

  const loadPatents = async () => {
    try {
      const res = await patentApi.getList({ page: 1, page_size: 100 });
      console.log("专利列表API返回:", res);
      // API返回格式: {data: {items: [...]}}
      const list = res.items || res.data?.items || [];
      console.log("专利列表数据:", list);
      setPatents(list.map((p: any) => ({
        id: p.id,
        title: p.title,
        application_number: p.application_number,
        applicant: p.applicant,
      })));
    } catch (err) {
      console.error("加载专利列表失败:", err);
      setPatents([]);
    }
  };

  const sendMessage = async (content?: string, actionType?: string) => {
    let text = content || input.trim();
    if (!text) return;
    if (!content) setInput("");

    // 如果选择了专利，添加专利信息到上下文
    let contextMessage = text;
    if (selectedPatent) {
      const patentInfo = `\n【当前专利信息】
- 专利名称: ${selectedPatent.title}
- 申请号: ${selectedPatent.application_number}
- 申请人: ${selectedPatent.applicant}`;
      
      if (actionType) {
        // 快速操作：根据选择的专利类型生成具体的问题
        const actionPrompts: Record<string, string> = {
          novelty: `请对专利"${selectedPatent.title}"（申请号：${selectedPatent.application_number}）进行新颖性分析，${patentInfo}\n\n请直接进行分析，给出：\n1. 法律依据\n2. 判断结论（具备/不具备新颖性）\n3. 详细说明`,
          inventiveness: `请对专利"${selectedPatent.title}"（申请号：${selectedPatent.application_number}）进行创造性评估，${patentInfo}\n\n请直接进行分析，给出：\n1. 法律依据\n2. 判断结论（具备/不具备创造性）\n3. 详细说明`,
          claims: `请审查专利"${selectedPatent.title}"（申请号：${selectedPatent.application_number}）的权利要求书，${patentInfo}\n\n请直接进行审查，给出：\n1. 权利要求是否清楚\n2. 权利要求是否得到说明书支持\n3. 独立权利要求是否符合单一性要求`,
          comprehensive: `请对专利"${selectedPatent.title}"（申请号：${selectedPatent.application_number}）进行全面综合评估，${patentInfo}\n\n请直接进行评估，给出：\n1. 形式问题\n2. 保护客体\n3. 新颖性/创造性初步判断\n4. 总体评价`,
        };
        contextMessage = actionPrompts[actionType] || text;
      } else {
        // 用户自定义消息
        contextMessage = text + patentInfo + "\n\n请根据以上专利信息回答问题。";
      }
    } else if (actionType) {
      // 没有选择专利，提示用户选择
      message.warning("请先选择要分析的专利");
      return;
    }

    // 验证当前提供商是否有效
    const currentProvider = providers.find(p => p.provider_name === selectedProvider);
    if (!currentProvider || !currentProvider.is_enabled) {
      message.error("AI提供商未配置或已禁用，请先在系统设置中配置");
      setLoading(false);
      return;
    }

    const userMsg: ChatMessage = { role: "user", content: contextMessage, timestamp: new Date() };
    setMessages((prev) => [...prev, userMsg]);
    setLoading(true);

    try {
      const res = await aiApi.chat({
        message: contextMessage,
        provider: selectedProvider,
        model: selectedModel,
        context: messages.slice(-10).map((m) => ({ role: m.role, content: m.content })),
      });
      const assistantMsg: ChatMessage = {
        role: "assistant",
        content: res.content || res.message || "抱歉，暂时无法处理您的请求。",
        timestamp: new Date(),
      };
      setMessages((prev) => [...prev, assistantMsg]);
    } catch (err: any) {
      const errMsg: ChatMessage = {
        role: "assistant",
        content: `请求失败: ${err?.response?.data?.detail || err?.message || "网络错误，请稍后重试"}`,
        timestamp: new Date(),
      };
      setMessages((prev) => [...prev, errMsg]);
    } finally {
      setLoading(false);
    }
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  // 获取当前提供商的默认模型
  const currentProviderDefaultModel = providers.find((p) => p.provider_name === selectedProvider)?.default_model || "";

  // 如果没有可用的AI提供商，显示提示
  const showProviderWarning = providers.length === 0;

  return (
    <Space direction="vertical" size="middle" style={{ width: "100%" }}>
      {showProviderWarning && (
        <Card>
          <Empty description={
            <span>
              暂无可用的 AI 提供商，请先在
              <a href="/settings" style={{ marginLeft: 8 }}>系统设置</a>
              中配置 AI 模型供应商
            </span>
          } />
        </Card>
      )}
      <Row justify="space-between" align="middle" style={{ marginBottom: 16 }}>
        <Col><Title level={4} style={{ margin: 0 }}>AI 助手</Title></Col>
        <Col>
          <Space>
            {/* 专利选择器 */}
            <Select
              value={selectedPatent?.id}
              style={{ width: 280 }}
              placeholder="选择要分析的专利（可选）"
              allowClear
              onChange={(val) => {
                if (val) {
                  const p = patents.find(p => p.id === val);
                  setSelectedPatent(p || null);
                } else {
                  setSelectedPatent(null);
                }
              }}
              options={patents.map(p => ({
                value: p.id,
                label: `${p.title} (${p.application_number})`
              }))}
              optionFilterProp="label"
              showSearch
              notFoundContent={patents.length === 0 ? "暂无专利" : undefined}
            />
            {/* 只有当有多个提供商时才显示选择器 */}
            {providers.length > 1 && (
              <>
                <Select value={selectedProvider} style={{ width: 160 }}
                  onChange={(v) => {
                    setSelectedProvider(v);
                    const p = providers.find((p: any) => p.provider_name === v);
                    if (p?.default_model) setSelectedModel(p.default_model);
                  }}
                  options={providers.map((p: any) => ({ 
                    value: p.provider_name, 
                    label: (
                      <span>
                        {p.display_name || p.provider_name}
                        {p.is_default && <Tag color="blue" style={{ marginLeft: 8 }}>默认</Tag>}
                      </span>
                    )
                  }))}
                  placeholder="选择AI提供商" />
                {currentProviderDefaultModel && (
                  <Tag color="green" style={{ marginLeft: 8 }}>
                    模型: {selectedModel || currentProviderDefaultModel}
                  </Tag>
                )}
              </>
            )}
            {/* 只有一个提供商时也显示选择器，方便用户看到当前选项 */}
            {providers.length === 1 && (
              <Select value={selectedProvider} style={{ width: 160 }}
                onChange={(v) => {
                  setSelectedProvider(v);
                  const p = providers.find((p: any) => p.provider_name === v);
                  if (p?.default_model) setSelectedModel(p.default_model);
                }}
                options={providers.map((p: any) => ({ 
                  value: p.provider_name, 
                  label: (
                    <span>
                      {p.display_name || p.provider_name}
                      {p.is_default && <Tag color="blue" style={{ marginLeft: 8 }}>默认</Tag>}
                    </span>
                  )
                }))}
                placeholder="选择AI提供商" />
            )}
          </Space>
        </Col>
      </Row>

      <Row gutter={16}>
        <Col xs={24} lg={18}>
          <Card
            styles={{
              body: {
                height: "calc(100vh - 380px)", minHeight: 400,
                display: "flex", flexDirection: "column",
              },
            }}
          >
            {/* Chat messages */}
            <div style={{ flex: 1, overflowY: "auto", paddingBottom: 16 }}>
              {messages.length === 0 ? (
                <div style={{ textAlign: "center", padding: "60px 0" }}>
                  <RobotOutlined style={{ fontSize: 48, color: "#1677ff", marginBottom: 16 }} />
                  <Title level={5} type="secondary">专利审查 AI 助手</Title>
                  <Paragraph type="secondary">
                    我可以帮助您进行专利文件分析、新颖性评估、创造性判断等工作。
                    <br />请输入问题或使用右侧的快速操作开始。
                  </Paragraph>
                </div>
              ) : (
                <List dataSource={messages} renderItem={(msg) => (
                  <List.Item style={{
                    justifyContent: msg.role === "user" ? "flex-end" : "flex-start",
                    border: "none", padding: "8px 0",
                  }}>
                    <Space align="start" direction={msg.role === "user" ? "horizontal" : "horizontal"}>
                      {msg.role === "assistant" && (
                        <Avatar icon={<RobotOutlined />} style={{ background: "#1677ff", flexShrink: 0 }} />
                      )}
                      <Card size="small" style={{
                        maxWidth: 600,
                        background: msg.role === "user" ? "#1677ff" : "#f5f5f5",
                        border: "none",
                      }}>
                        {msg.role === "assistant" ? (
                          <div style={{ 
                            color: "#333", 
                            fontSize: 14,
                            lineHeight: 1.6 
                          }}>
                            <ReactMarkdown 
                              remarkPlugins={[remarkGfm]}
                              components={{
                                table: ({node, ...props}) => (
                                  <table style={{borderCollapse: 'collapse', width: '100%', margin: '8px 0'}} {...props} />
                                ),
                                th: ({node, ...props}) => (
                                  <th style={{border: '1px solid #ddd', padding: '8px', background: '#f5f5f5', textAlign: 'left'}} {...props} />
                                ),
                                td: ({node, ...props}) => (
                                  <td style={{border: '1px solid #ddd', padding: '8px'}} {...props} />
                                ),
                                h1: ({node, ...props}) => (
                                  <h1 style={{fontSize: '1.4em', fontWeight: 600, margin: '12px 0 8px', color: '#1677ff'}} {...props} />
                                ),
                                h2: ({node, ...props}) => (
                                  <h2 style={{fontSize: '1.3em', fontWeight: 600, margin: '10px 0 6px', color: '#1677ff'}} {...props} />
                                ),
                                h3: ({node, ...props}) => (
                                  <h3 style={{fontSize: '1.2em', fontWeight: 600, margin: '8px 0 4px'}} {...props} />
                                ),
                                ul: ({node, ...props}) => (
                                  <ul style={{margin: '4px 0', paddingLeft: '20px'}} {...props} />
                                ),
                                ol: ({node, ...props}) => (
                                  <ol style={{margin: '4px 0', paddingLeft: '20px'}} {...props} />
                                ),
                                li: ({node, ...props}) => (
                                  <li style={{margin: '2px 0'}} {...props} />
                                ),
                                p: ({node, ...props}) => (
                                  <p style={{margin: '4px 0'}} {...props} />
                                ),
                              }}
                            >
                              {msg.content}
                            </ReactMarkdown>
                          </div>
                        ) : (
                          <Paragraph style={{
                            margin: 0, color: "#fff",
                            whiteSpace: "pre-wrap",
                          }}>
                            {msg.content}
                          </Paragraph>
                        )}
                        <Text style={{ fontSize: 11, color: msg.role === "user" ? "rgba(255,255,255,0.6)" : "#999" }}>
                          {msg.timestamp.toLocaleTimeString("zh-CN")}
                        </Text>
                      </Card>
                      {msg.role === "user" && (
                        <Avatar icon={<UserOutlined />} style={{ background: "#87d068", flexShrink: 0 }} />
                      )}
                    </Space>
                  </List.Item>
                )} />
              )}
              {loading && (
                <div style={{ padding: "8px 0" }}>
                  <Space>
                    <Avatar icon={<RobotOutlined />} style={{ background: "#1677ff" }} />
                    <Card size="small" style={{ background: "#f5f5f5", border: "none" }}>
                      <Spin size="small" /> <Text type="secondary" style={{ marginLeft: 8 }}>正在思考...</Text>
                    </Card>
                  </Space>
                </div>
              )}
              <div ref={chatEndRef} />
            </div>

            <Divider style={{ margin: "8px 0" }} />

            {/* Input area */}
            <Space.Compact style={{ width: "100%" }}>
              <TextArea
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={handleKeyPress}
                placeholder="输入您的问题... (Shift+Enter 换行)"
                autoSize={{ minRows: 1, maxRows: 4 }}
                style={{ borderRadius: "6px 0 0 6px" }}
              />
              <Button type="primary" icon={<SendOutlined />}
                onClick={() => sendMessage()} loading={loading}
                disabled={showProviderWarning}
                style={{ height: "auto", borderRadius: "0 6px 6px 0" }}>
                发送
              </Button>
            </Space.Compact>
          </Card>
        </Col>

        <Col xs={24} lg={6}>
          <Card title="快速操作" size="small">
            <Space direction="vertical" style={{ width: "100%" }}>
              {quickActions.map((action) => (
                <Button key={action.key} block icon={action.icon}
                  onClick={() => sendMessage(action.prompt, action.key)}
                  disabled={loading || showProviderWarning}>
                  {action.label}
                </Button>
              ))}
            </Space>
          </Card>
          <Card title="使用提示" size="small" style={{ marginTop: 16 }}>
            <List size="small" dataSource={[
              "请先选择要分析的专利",
              "然后点击快速操作进行分析",
              "或直接输入问题进行咨询",
              "支持对比分析多个专利",
              "可生成审查意见建议",
            ]} renderItem={(item) => (
              <List.Item style={{ padding: "4px 0", border: "none" }}>
                <Text type="secondary" style={{ fontSize: 12 }}>- {item}</Text>
              </List.Item>
            )} />
          </Card>
          <Card size="small" style={{ marginTop: 16 }}>
            <Space>
              <Button size="small" icon={<ClearOutlined />}
                onClick={() => setMessages([])}>
                清空对话
              </Button>
              <Button size="small" icon={<ReloadOutlined />}
                onClick={loadProviders}>
                刷新模型
              </Button>
            </Space>
          </Card>
        </Col>
      </Row>
    </Space>
  );
}
