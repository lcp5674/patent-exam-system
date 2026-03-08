/**
 * RAG管理页面
 * RAG Management Page
 */
import { useState, useEffect } from "react";
import {
  Card, Tabs, Table, Button, Space, Tag, Modal, Form, Input, Select,
  Descriptions, Badge, Statistic, Row, Col, message, Drawer,
  Divider, Alert, InputNumber, Switch, Slider, Progress, List, Typography,
  Upload, Spin, Tooltip, Popconfirm, Empty, Checkbox, Radio, Collapse,
  UploadFile, Progress as UploadProgress
} from "antd";
import {
  SearchOutlined, SettingOutlined, DatabaseOutlined, FileTextOutlined,
  PlusOutlined, DeleteOutlined, ReloadOutlined, SyncOutlined,
  CheckCircleOutlined, CloseCircleOutlined, CloudServerOutlined,
  ApiOutlined, HistoryOutlined, SafetyCertificateOutlined, 
  ThunderboltOutlined, TagOutlined, UploadOutlined, LinkOutlined,
  GlobalOutlined, InboxOutlined, ExperimentOutlined, LoadingOutlined,
  EditOutlined, DownloadOutlined
} from "@ant-design/icons";
import type { ColumnsType } from "antd/es/table";
import { ragApi, RAGConfig, CollectionStats, RAGHealth, SearchHistory, KnowledgeBaseEntry, ChunkingConfig, ModelOption, AvailableModels, ModelTestResponse, FileUploadResponse, URLCrawlResponse, CustomModelConfig, PatentSourceConfig, PatentSourceConfigCreate, RagDocument } from "../services/ragApi";
import dayjs from "dayjs";
import { useSelector } from "react-redux";
import type { RootState } from "../store";

const { Title, Text, Paragraph } = Typography;
const { TextArea } = Input;
const { Dragger } = Upload;

// 向量数据库选项
const VECTOR_DB_OPTIONS = [
  { value: "qdrant", label: "Qdrant" },
  { value: "milvus", label: "Milvus" },
  { value: "weaviate", label: "Weaviate" },
  { value: "chroma", label: "Chroma" },
  { value: "faiss", label: "FAISS" },
];

// Embedding模型选项
const EMBEDDING_MODEL_OPTIONS = [
  { value: "bge-base-zh-v1.5", label: "BGE Base ZH v1.5" },
  { value: "bge-large-zh-v1.5", label: "BGE Large ZH v1.5" },
  { value: "bge-base-en-v1.5", label: "BGE Base EN v1.5" },
  { value: "text-embedding-ada-002", label: "OpenAI Ada-002" },
  { value: "m3e-base", label: "M3E Base" },
];

// 搜索类型选项
const SEARCH_TYPE_OPTIONS = [
  { value: "semantic", label: "语义搜索 (Semantic)" },
  { value: "keyword", label: "关键词搜索 (Keyword)" },
  { value: "hybrid", label: "混合搜索 (Hybrid)" },
];

interface DocumentIndexRequest {
  title?: string;
  abstract?: string;
  claims?: string[];
  description?: string;
  application_number?: string;
}

export default function RAGManagementPage() {
  const { user } = useSelector((state: RootState) => state.auth);
  // 使用用户ID或默认tenant ID
  const tenantId = user?.id?.toString() || "default";
  
  const [activeTab, setActiveTab] = useState("overview");
  
  // 健康状态
  const [health, setHealth] = useState<RAGHealth | null>(null);
  const [healthLoading, setHealthLoading] = useState(false);
  
  // 配置
  const [config, setConfig] = useState<RAGConfig | null>(null);
  const [configLoading, setConfigLoading] = useState(false);
  const [configSaving, setConfigSaving] = useState(false);
  
  // 可用模型
  const [availableModels, setAvailableModels] = useState<AvailableModels | null>(null);
  const [modelsLoading, setModelsLoading] = useState(false);
  
  // 模型测试
  const [modelTesting, setModelTesting] = useState(false);
  const [testResult, setTestResult] = useState<ModelTestResponse | null>(null);
  
  // 统计
  const [stats, setStats] = useState<CollectionStats | null>(null);
  const [statsLoading, setStatsLoading] = useState(false);
  
  // 文件列表 (上传的文件管理)
  const [documents, setDocuments] = useState<RagDocument[]>([]);
  const [documentsLoading, setDocumentsLoading] = useState(false);
  const [documentTotal, setDocumentTotal] = useState(0);
  
  // 搜索历史
  const [searchHistory, setSearchHistory] = useState<SearchHistory[]>([]);
  const [historyLoading, setHistoryLoading] = useState(false);
  
  // Drawer/Modal状态
  const [indexModal, setIndexModal] = useState(false);
  const [configModal, setConfigModal] = useState(false);
  const [testSearchDrawer, setTestSearchDrawer] = useState(false);
  const [searchResults, setSearchResults] = useState<any[]>([]);
  const [searching, setSearching] = useState(false);
  
  // 文件上传
  const [uploadModal, setUploadModal] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [uploadResult, setUploadResult] = useState<FileUploadResponse | null>(null);
  
  // URL爬取
  const [urlCrawlModal, setUrlCrawlModal] = useState(false);
  const [crawling, setCrawling] = useState(false);
  const [crawlResult, setCrawlResult] = useState<URLCrawlResponse | null>(null);
  
  // 专利爬取
  const [patentCrawlModal, setPatentCrawlModal] = useState(false);
  const [patentCrawling, setPatentCrawling] = useState(false);
  
  // 自定义模型配置
  const [customModels, setCustomModels] = useState<CustomModelConfig[]>([]);
  const [customModelsLoading, setCustomModelsLoading] = useState(false);
  const [customModelModal, setCustomModelModal] = useState(false);
  const [editingCustomModel, setEditingCustomModel] = useState<CustomModelConfig | null>(null);
  
  // 自定义Reranker模型配置
  const [customRerankers, setCustomRerankers] = useState<CustomModelConfig[]>([]);
  const [customRerankersLoading, setCustomRerankersLoading] = useState(false);
  const [customRerankerModal, setCustomRerankerModal] = useState(false);
  const [editingCustomReranker, setEditingCustomReranker] = useState<CustomModelConfig | null>(null);
  
  // 专利数据源配置
  const [patentSourceConfigs, setPatentSourceConfigs] = useState<PatentSourceConfig[]>([]);
  const [patentSourceConfigsLoading, setPatentSourceConfigsLoading] = useState(false);
  const [patentSourceModal, setPatentSourceModal] = useState(false);
  const [editingPatentSource, setEditingPatentSource] = useState<PatentSourceConfig | null>(null);
  
  const [indexForm] = Form.useForm();
  const [configForm] = Form.useForm();
  const [searchForm] = Form.useForm();
  const [uploadForm] = Form.useForm();
  const [urlCrawlForm] = Form.useForm();
  const [patentCrawlForm] = Form.useForm();
  const [customModelForm] = Form.useForm();
  const [customRerankerForm] = Form.useForm();
  const [patentSourceForm] = Form.useForm();

  useEffect(() => {
    loadHealth();
    loadConfig();
    loadStats();
    loadAvailableModels();
    loadCustomModels();
    loadCustomRerankers();
    loadPatentSourceConfigs();
    loadDocuments(); // 加载文件列表
  }, []);

  const loadHealth = async () => {
    setHealthLoading(true);
    try {
      const res = await ragApi.getHealth();
      setHealth(res);
    } catch (error) {
      console.error("加载健康状态失败:", error);
    } finally {
      setHealthLoading(false);
    }
  };

  const loadConfig = async () => {
    setConfigLoading(true);
    try {
      const res = await ragApi.getConfig();
      setConfig(res);
      configForm.setFieldsValue(res);
    } catch (error) {
      console.error("加载配置失败:", error);
    } finally {
      setConfigLoading(false);
    }
  };

  const loadStats = async () => {
    setStatsLoading(true);
    try {
      const res = await ragApi.getStats(tenantId);
      setStats(res);
    } catch (error) {
      console.error("加载统计失败:", error);
    } finally {
      setStatsLoading(false);
    }
  };

  const loadAvailableModels = async () => {
    setModelsLoading(true);
    try {
      const res = await ragApi.getAvailableModels();
      setAvailableModels(res);
    } catch (error) {
      console.error("加载可用模型失败:", error);
    } finally {
      setModelsLoading(false);
    }
  };

  const loadCustomModels = async () => {
    setCustomModelsLoading(true);
    try {
      const res = await ragApi.getCustomModels();
      setCustomModels(res.custom_configs || []);
    } catch (error) {
      console.error("加载自定义模型失败:", error);
    } finally {
      setCustomModelsLoading(false);
    }
  };

  const handleAddCustomModel = async () => {
    try {
      const values = await customModelForm.validateFields();
      if (editingCustomModel) {
        // 编辑模式
        await ragApi.updateCustomModel({ ...editingCustomModel, ...values });
        message.success("自定义模型更新成功");
      } else {
        // 添加模式
        await ragApi.addCustomModel(values);
        message.success("自定义模型添加成功");
      }
      setCustomModelModal(false);
      customModelForm.resetFields();
      setEditingCustomModel(null);
      loadCustomModels();
    } catch (error: any) {
      message.error((editingCustomModel ? "更新" : "添加") + "失败: " + (error.message || "未知错误"));
    }
  };

  const handleDeleteCustomModel = async (modelName: string) => {
    try {
      await ragApi.deleteCustomModel(modelName);
      message.success("删除成功");
      loadCustomModels();
    } catch (error: any) {
      message.error("删除失败: " + (error.message || "未知错误"));
    }
  };

  // 自定义Reranker模型配置
  const loadCustomRerankers = async () => {
    setCustomRerankersLoading(true);
    try {
      const res = await ragApi.getCustomRerankers();
      setCustomRerankers(res.custom_configs || []);
    } catch (error) {
      console.error("加载自定义Reranker失败:", error);
    } finally {
      setCustomRerankersLoading(false);
    }
  };

  const handleAddCustomReranker = async () => {
    try {
      const values = await customRerankerForm.validateFields();
      if (editingCustomReranker) {
        // 编辑模式
        await ragApi.updateCustomReranker({ ...editingCustomReranker, ...values });
        message.success("自定义Reranker模型更新成功");
      } else {
        // 添加模式
        await ragApi.addCustomReranker(values);
        message.success("自定义Reranker模型添加成功");
      }
      setCustomRerankerModal(false);
      customRerankerForm.resetFields();
      setEditingCustomReranker(null);
      loadCustomRerankers();
    } catch (error: any) {
      message.error((editingCustomReranker ? "更新" : "添加") + "失败: " + (error.message || "未知错误"));
    }
  };

  const handleDeleteCustomReranker = async (modelName: string) => {
    try {
      await ragApi.deleteCustomReranker(modelName);
      message.success("删除成功");
      loadCustomRerankers();
    } catch (error: any) {
      message.error("删除失败: " + (error.message || "未知错误"));
    }
  };

  // 专利数据源配置
  const loadPatentSourceConfigs = async () => {
    setPatentSourceConfigsLoading(true);
    try {
      const res = await ragApi.getPatentSourceConfigs(tenantId);
      setPatentSourceConfigs(res.configs || []);
    } catch (error) {
      console.error("加载数据源配置失败:", error);
    } finally {
      setPatentSourceConfigsLoading(false);
    }
  };

  const handleAddPatentSource = async () => {
    try {
      const values = await patentSourceForm.validateFields();
      if (editingPatentSource) {
        // 编辑模式
        await ragApi.updatePatentSourceConfig(editingPatentSource.id, values, tenantId);
        message.success("数据源配置更新成功");
      } else {
        // 添加模式
        await ragApi.createPatentSourceConfig(values, tenantId);
        message.success("数据源配置添加成功");
      }
      setPatentSourceModal(false);
      patentSourceForm.resetFields();
      setEditingPatentSource(null);
      loadPatentSourceConfigs();
    } catch (error: any) {
      message.error((editingPatentSource ? "更新" : "添加") + "失败: " + (error.message || "未知错误"));
    }
  };

  const handleDeletePatentSource = async (configId: number) => {
    try {
      await ragApi.deletePatentSourceConfig(configId, tenantId);
      message.success("删除成功");
      loadPatentSourceConfigs();
    } catch (error: any) {
      message.error("删除失败: " + (error.message || "未知错误"));
    }
  };

  const testModel = async (modelName: string, provider?: string, customConfig?: { api_url?: string; api_key?: string }) => {
    setModelTesting(true);
    setTestResult(null);
    try {
      const res = await ragApi.testEmbeddingModel({
        model_name: modelName,
        provider: provider,
        api_url: customConfig?.api_url,
        api_key: customConfig?.api_key
      });
      setTestResult(res);
    } catch (error: any) {
      message.error("模型测试失败: " + error.message);
    } finally {
      setModelTesting(false);
    }
  };

  const testReranker = async (modelName: string, provider?: string, customConfig?: { api_url?: string; api_key?: string }) => {
    setModelTesting(true);
    setTestResult(null);
    try {
      const res = await ragApi.testRerankerModel({
        model_name: modelName,
        provider: provider,
        api_url: customConfig?.api_url,
        api_key: customConfig?.api_key
      });
      setTestResult(res);
    } catch (error: any) {
      message.error("Reranker测试失败: " + error.message);
    } finally {
      setModelTesting(false);
    }
  };

  const loadDocuments = async (page = 1, pageSize = 20) => {
    setDocumentsLoading(true);
    try {
      const skip = (page - 1) * pageSize;
      const res = await ragApi.getFiles(tenantId, skip, pageSize);
      setDocuments(res.documents || []);
      setDocumentTotal(res.total || 0);
    } catch (error) {
      console.error("加载文件列表失败:", error);
      setDocuments([]);
      setDocumentTotal(0);
    } finally {
      setDocumentsLoading(false);
    }
  };

  // 处理删除文件
  const handleDeleteFile = async (fileId: number) => {
    try {
      await ragApi.deleteFile(fileId, tenantId);
      message.success("文件删除成功");
      loadDocuments();
      loadStats();
    } catch (error: any) {
      message.error("删除失败: " + (error.message || "未知错误"));
    }
  };

  // 处理重新索引
  const handleReindexFile = async (fileId: number) => {
    try {
      const res = await ragApi.reindexFile(fileId, tenantId);
      message.success(res.message || "重新索引成功");
      loadDocuments();
      loadStats();
    } catch (error: any) {
      message.error("重新索引失败: " + (error.message || "未知错误"));
    }
  };

  // 处理下载文件
  const handleDownloadFile = async (fileId: number, fileName: string) => {
    try {
      const blob = await ragApi.downloadFile(fileId, tenantId);
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = fileName;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
      message.success("文件下载成功");
    } catch (error: any) {
      message.error("下载失败: " + (error.message || "未知错误"));
    }
  };

  const loadSearchHistory = async () => {
    setHistoryLoading(true);
    try {
      const response = await ragApi.getSearchHistory(tenantId, 50);
      setSearchHistory(response.history);
    } catch (error) {
      console.error("加载搜索历史失败:", error);
      message.error("加载搜索历史失败");
    } finally {
      setHistoryLoading(false);
    }
  };

  const handleSaveConfig = async () => {
    try {
      const values = await configForm.validateFields();
      setConfigSaving(true);
      await ragApi.updateConfig(values);
      message.success("配置保存成功");
      setConfigModal(false);
      loadConfig();
    } catch (error) {
      message.error("配置保存失败");
    } finally {
      setConfigSaving(false);
    }
  };

  const handleIndexDocument = async () => {
    try {
      const values = await indexForm.validateFields();
      await ragApi.indexDocument(values);
      message.success("文档索引成功");
      setIndexModal(false);
      indexForm.resetFields();
      loadStats();
    } catch (error) {
      message.error("文档索引失败");
    }
  };

  const handleTestSearch = async () => {
    try {
      const values = await searchForm.validateFields();
      setSearching(true);
      const res = await ragApi.search({
        query: values.query,
        top_k: values.top_k || 10,
        search_type: values.search_type || "hybrid",
        use_rerank: values.use_rerank ?? true
      });
      setSearchResults(res.chunks || []);
    } catch (error) {
      message.error("搜索失败");
      setSearchResults([]);
    } finally {
      setSearching(false);
    }
  };

  // 文件上传处理
  const handleFileUpload = async (file: File) => {
    setUploading(true);
    setUploadProgress(50);
    setUploadResult(null);
    try {
      const res = await ragApi.uploadAndIndexFile(file, tenantId);
      setUploadProgress(100);
      setUploadResult({
        success: true,
        file_name: file.name,
        file_type: file.name.split('.').pop() || '',
        file_size: file.size,
        chunk_count: 1
      });
      message.success("文件上传并索引成功");
      loadStats();
      loadDocuments();
    } catch (error: any) {
      setUploadResult({
        success: false,
        file_name: file.name,
        file_type: file.name.split('.').pop() || '',
        file_size: file.size,
        chunk_count: 0,
        error: error.message
      });
      message.error("文件上传失败: " + error.message);
    } finally {
      setUploading(false);
    }
    return false; // 阻止默认上传行为
  };

  // URL爬取处理
  const handleURLCrawl = async () => {
    try {
      const values = await urlCrawlForm.validateFields();
      setCrawling(true);
      const res = await ragApi.crawlAndIndexURL(values, tenantId);
      setCrawlResult({
        success: res.success,
        url: values.url,
        content: res.message || `索引了 ${res.chunk_count} 个文档`
      });
      if (res.success) {
        message.success("URL爬取并索引成功");
        loadStats();
      }
    } catch (error: any) {
      message.error("URL爬取失败: " + error.message);
      setCrawlResult({
        success: false,
        url: "",
        content: error.message
      });
    } finally {
      setCrawling(false);
    }
  };

  // 专利数据爬取处理
  const handlePatentCrawl = async () => {
    try {
      const values = await patentCrawlForm.validateFields();
      setPatentCrawling(true);
      const res = await ragApi.crawlPatents({
        query: values.query,
        sources: values.sources,
        max_results: values.max_results || 20,
        auto_index: true
      }, tenantId);
      
      // 显示详细结果
      let resultMessage = `找到 ${res.total_found} 个专利, 索引了 ${res.indexed} 个`;
      if (res.message) {
        resultMessage += `\n${res.message}`;
      }
      message.success(resultMessage);
      setPatentCrawlModal(false);
      patentCrawlForm.resetFields();
      loadStats();
    } catch (error: any) {
      message.error("专利爬取失败: " + error.message);
    } finally {
      setPatentCrawling(false);
    }
  };

  // 标签页内容
  const overviewTab = (
    <div>
      <Row gutter={[16, 16]}>
        {/* 健康状态卡片 */}
        <Col xs={24} lg={12}>
          <Card 
            title={<><SafetyCertificateOutlined /> 系统健康状态</>} 
            loading={healthLoading}
            extra={<Button icon={<ReloadOutlined />} onClick={loadHealth}>刷新</Button>}
          >
            {health ? (
              <Descriptions column={1} bordered size="small">
                <Descriptions.Item label="状态">
                  <Badge 
                    status={health.status === "healthy" ? "success" : "error"} 
                    text={health.status === "healthy" ? "正常" : "异常"} 
                  />
                </Descriptions.Item>
                <Descriptions.Item label="向量数据库">
                  <Tag color={health.vector_db === "connected" ? "green" : "red"}>
                    {health.vector_db}
                  </Tag>
                </Descriptions.Item>
                <Descriptions.Item label="Embedding服务">
                  <Tag color={health.embedding_service === "ready" ? "green" : "orange"}>
                    {health.embedding_service}
                  </Tag>
                </Descriptions.Item>
                <Descriptions.Item label="可用数据源">
                  <Space wrap>
                    {health.connectors?.map((c: any) => (
                      <Tag 
                        key={c.name} 
                        color={c.available ? "green" : "default"}
                        icon={c.available ? <CheckCircleOutlined /> : <CloseCircleOutlined />}
                      >
                        {c.name.toUpperCase()}
                      </Tag>
                    ))}
                  </Space>
                </Descriptions.Item>
                <Descriptions.Item label="更新时间">
                  {dayjs(health.timestamp).format("YYYY-MM-DD HH:mm:ss")}
                </Descriptions.Item>
              </Descriptions>
            ) : (
              <Empty description="无法获取健康状态" />
            )}
          </Card>
        </Col>

        {/* 统计卡片 */}
        <Col xs={24} lg={12}>
          <Card 
            title={<><DatabaseOutlined /> 集合统计</>} 
            loading={statsLoading}
            extra={<Button icon={<ReloadOutlined />} onClick={loadStats}>刷新</Button>}
          >
            {stats ? (
              <Row gutter={16}>
                <Col span={8}>
                  <Statistic 
                    title="上传文件" 
                    value={stats.additional_info?.total_files ?? stats.document_count} 
                    prefix={<FileTextOutlined />} 
                  />
                </Col>
                <Col span={8}>
                  <Statistic 
                    title="已索引文件" 
                    value={stats.additional_info?.indexed_files ?? stats.document_count} 
                    prefix={<CheckCircleOutlined />} 
                    valueStyle={{ color: '#3f8600' }}
                  />
                </Col>
                <Col span={8}>
                  <Statistic 
                    title="向量块数量" 
                    value={stats.document_count} 
                    prefix={<DatabaseOutlined />} 
                    valueStyle={{ color: '#1890ff' }}
                  />
                </Col>
                <Col span={24} style={{ marginTop: 12 }}>
                  <Divider style={{ margin: "8px 0" }} />
                  <Space split={<Divider type="vertical" />}>
                    <Text type="secondary">集合名称: {stats.collection}</Text>
                    <Text type="secondary">后端存储: {stats.backend}</Text>
                    {stats.additional_info?.failed_files && stats.additional_info?.failed_files > 0 && (
                      <Text type="warning">失败文件: {stats.additional_info.failed_files}</Text>
                    )}
                  </Space>
                </Col>
              </Row>
            ) : (
              <Empty description="暂无统计数据" />
            )}
          </Card>
        </Col>

        {/* 快速操作 */}
        <Col span={24}>
          <Card title={<><ThunderboltOutlined /> 快速操作</>}>
            <Space wrap>
              <Button 
                type="primary" 
                icon={<PlusOutlined />} 
                onClick={() => setIndexModal(true)}
              >
                手动索引
              </Button>
              <Button 
                icon={<UploadOutlined />} 
                onClick={() => setUploadModal(true)}
              >
                上传文件
              </Button>
              <Button 
                icon={<LinkOutlined />} 
                onClick={() => setUrlCrawlModal(true)}
              >
                URL爬取
              </Button>
              <Button 
                icon={<GlobalOutlined />} 
                onClick={() => setPatentCrawlModal(true)}
              >
                专利数据
              </Button>
              <Button 
                icon={<SearchOutlined />} 
                onClick={() => {
                  loadSearchHistory();
                  setActiveTab("search");
                }}
              >
                测试搜索
              </Button>
              <Button 
                icon={<SyncOutlined />} 
                onClick={loadStats}
              >
                刷新统计
              </Button>
            </Space>
          </Card>
        </Col>
      </Row>
    </div>
  );

  const documentsTab = (
    <Card 
      title={<><FileTextOutlined /> 文件管理</>}
      extra={
        <Space>
          <Button icon={<ReloadOutlined />} onClick={() => loadDocuments()}>刷新</Button>
          <Button type="primary" icon={<UploadOutlined />} onClick={() => setUploadModal(true)}>
            上传文件
          </Button>
        </Space>
      }
    >
      <Table
        columns={[
          {
            title: "ID",
            dataIndex: "id",
            key: "id",
            width: 60,
          },
          {
            title: "文件名",
            dataIndex: "file_name",
            key: "file_name",
            ellipsis: true,
            render: (name: string) => <Text strong>{name}</Text>
          },
          {
            title: "文件类型",
            dataIndex: "file_type",
            key: "file_type",
            width: 100,
            render: (type: string) => <Tag>{type}</Tag>
          },
          {
            title: "文件大小",
            dataIndex: "file_size",
            key: "file_size",
            width: 100,
            render: (size: number) => {
              if (size < 1024) return `${size} B`;
              if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`;
              return `${(size / (1024 * 1024)).toFixed(1)} MB`;
            }
          },
          {
            title: "状态",
            dataIndex: "status",
            key: "status",
            width: 100,
            render: (status: string) => {
              const colorMap: Record<string, string> = {
                'completed': 'green',
                'indexing': 'processing',
                'pending': 'orange',
                'failed': 'red'
              };
              const textMap: Record<string, string> = {
                'completed': '已完成',
                'indexing': '索引中',
                'pending': '等待中',
                'failed': '失败'
              };
              return <Tag color={colorMap[status] || 'default'}>{textMap[status] || status}</Tag>;
            }
          },
          {
            title: "分块数",
            dataIndex: "chunk_count",
            key: "chunk_count",
            width: 80,
          },
          {
            title: "上传时间",
            dataIndex: "created_at",
            key: "created_at",
            width: 160,
            render: (date: string) => dayjs(date).format("YYYY-MM-DD HH:mm")
          },
          {
            title: "操作",
            key: "action",
            width: 200,
            render: (_: any, record: RagDocument) => (
              <Space>
                <Button 
                  size="small" 
                  type="link" 
                  icon={<DownloadOutlined />}
                  onClick={() => handleDownloadFile(record.id, record.file_name)}
                >
                  下载
                </Button>
                <Button 
                  size="small" 
                  type="link" 
                  icon={<SyncOutlined />}
                  onClick={() => handleReindexFile(record.id)}
                  disabled={record.status === 'indexing'}
                >
                  重建索引
                </Button>
                <Popconfirm
                  title="确定删除此文件?"
                  onConfirm={() => handleDeleteFile(record.id)}
                >
                  <Button size="small" type="link" danger icon={<DeleteOutlined />}>删除</Button>
                </Popconfirm>
              </Space>
            )
          }
        ]}
        dataSource={documents}
        loading={documentsLoading}
        rowKey="id"
        pagination={{
          total: documentTotal,
          onChange: loadDocuments,
          showSizeChanger: true,
          showTotal: (total) => `共 ${total} 个文件`
        }}
        locale={{ emptyText: "暂无上传的文件，点击\"上传文件\"按钮添加" }}
      />
    </Card>
  );

  const configTab = (
    <Card 
      title={<><SettingOutlined /> RAG配置</>}
      extra={<Button type="primary" onClick={() => setConfigModal(true)}>编辑配置</Button>}
    >
      {config ? (
        <Descriptions bordered column={2}>
          <Descriptions.Item label="向量数据库">{config.vector_db_type}</Descriptions.Item>
          <Descriptions.Item label="Embedding模型">{config.embedding_model}</Descriptions.Item>
          <Descriptions.Item label="Embedding维度">{config.embedding_dimension}</Descriptions.Item>
          <Descriptions.Item label="分块大小">{config.chunk_size}</Descriptions.Item>
          <Descriptions.Item label="分块重叠">{config.chunk_overlap}</Descriptions.Item>
          <Descriptions.Item label="检索Top K">{config.retrieval_top_k}</Descriptions.Item>
          <Descriptions.Item label="Rerank启用">
            <Switch checked={config.rerank_enabled} disabled />
          </Descriptions.Item>
          <Descriptions.Item label="混合搜索Alpha">{config.hybrid_search_alpha}</Descriptions.Item>
        </Descriptions>
      ) : (
        <Empty description="暂无配置信息" />
      )}
    </Card>
  );

  const searchTab = (
    <Card 
      title={<><SearchOutlined /> 测试搜索</>}
    >
      <Row gutter={16}>
        <Col span={8}>
          <Form form={searchForm} layout="vertical">
            <Form.Item 
              name="query" 
              label="搜索查询" 
              rules={[{ required: true, message: "请输入搜索查询" }]}
            >
              <TextArea 
                rows={4} 
                placeholder="输入要搜索的内容..." 
              />
            </Form.Item>
            
            <Form.Item name="search_type" label="搜索类型" initialValue="hybrid">
              <Select options={SEARCH_TYPE_OPTIONS} />
            </Form.Item>
            
            <Form.Item name="top_k" label="返回数量" initialValue={10}>
              <InputNumber min={1} max={100} style={{ width: "100%" }} />
            </Form.Item>
            
            <Form.Item name="use_rerank" label="启用Rerank" valuePropName="checked" initialValue={true}>
              <Switch />
            </Form.Item>
            
            <Form.Item>
              <Button 
                type="primary" 
                icon={<SearchOutlined />} 
                onClick={handleTestSearch}
                loading={searching}
                block
              >
                执行搜索
              </Button>
            </Form.Item>
          </Form>
        </Col>
        
        <Col span={16}>
          <Card 
            title="搜索结果" 
            extra={<Text type="secondary">共 {searchResults.length} 条结果</Text>}
          >
            {searchResults.length > 0 ? (
              <List
                itemLayout="vertical"
                dataSource={searchResults}
                renderItem={(item: any, index: number) => (
                  <List.Item
                    key={item.id || index}
                    extra={
                      <Space direction="vertical" align="end">
                        <Tag color="blue">Score: {(item.score * 100).toFixed(2)}%</Tag>
                        <Text type="secondary">{item.source}</Text>
                      </Space>
                    }
                  >
                    <List.Item.Meta
                      title={<Text strong>{item.metadata?.title || `结果 ${index + 1}`}</Text>}
                      description={
                        <Paragraph 
                          ellipsis={{ rows: 3, expandable: true, symbol: '展开' }}
                          copyable
                        >
                          {item.content}
                        </Paragraph>
                      }
                    />
                  </List.Item>
                )}
              />
            ) : (
              <Empty description="请输入查询并执行搜索" />
            )}
          </Card>
        </Col>
      </Row>
    </Card>
  );

  const historyTab = (
    <Card 
      title={<><HistoryOutlined /> 搜索历史</>}
      extra={<Button icon={<ReloadOutlined />} onClick={loadSearchHistory}>刷新</Button>}
    >
      <Table
        columns={[
          {
            title: "查询内容",
            dataIndex: "query",
            key: "query",
            ellipsis: true,
          },
          {
            title: "搜索类型",
            dataIndex: "search_type",
            key: "search_type",
            width: 120,
            render: (type: string) => (
              <Tag>
                {SEARCH_TYPE_OPTIONS.find(o => o.value === type)?.label || type}
              </Tag>
            )
          },
          {
            title: "结果数量",
            dataIndex: "result_count",
            key: "result_count",
            width: 100,
          },
          {
            title: "搜索时间",
            dataIndex: "timestamp",
            key: "timestamp",
            width: 180,
            render: (date: string) => dayjs(date).format("YYYY-MM-DD HH:mm:ss")
          }
        ]}
        dataSource={searchHistory}
        loading={historyLoading}
        rowKey="id"
        pagination={{
          showSizeChanger: true,
          showTotal: (total) => `共 ${total} 条`
        }}
      />
    </Card>
  );

  const tabItems = [
    { key: "overview", label: "概览", children: overviewTab },
    { key: "documents", label: "文档管理", children: documentsTab },
    { key: "config", label: "配置", children: configTab },
    { key: "models", label: "模型配置", children: (
      <Card 
        title={<><ApiOutlined /> 自定义Embedding模型配置</>}
        extra={
          <Button type="primary" icon={<PlusOutlined />} onClick={() => setCustomModelModal(true)}>
            添加自定义模型
          </Button>
        }
      >
        <Alert 
          message="自定义模型说明" 
          description="您可以添加自定义的Embedding模型，通过配置API URL和API Key来连接您自己的 embedding 服务。支持 OpenAI 兼容格式的API。" 
          type="info" 
          showIcon 
          style={{ marginBottom: 16 }}
        />
        
        <Table
          columns={[
            {
              title: "模型名称",
              dataIndex: "model_name",
              key: "model_name",
              render: (name: string) => <Text strong>{name}</Text>
            },
            {
              title: "提供商",
              dataIndex: "provider",
              key: "provider",
              render: (provider: string) => (
                <Tag color={provider === "custom" ? "purple" : "blue"}>{provider}</Tag>
              )
            },
            {
              title: "API URL",
              dataIndex: "api_url",
              key: "api_url",
              ellipsis: true,
              render: (url: string) => url || "-"
            },
            {
              title: "向量维度",
              dataIndex: "dimension",
              key: "dimension",
              render: (dim: number) => dim || 1536
            },
            {
              title: "状态",
              dataIndex: "enabled",
              key: "enabled",
              render: (enabled: boolean) => (
                <Badge status={enabled ? "success" : "default"} text={enabled ? "已启用" : "已禁用"} />
              )
            },
            {
              title: "操作",
              key: "action",
              render: (_: any, record: CustomModelConfig) => (
                <Space>
                  <Button 
                    size="small" 
                    type="link" 
                    icon={<ExperimentOutlined />}
                    onClick={() => testModel(record.model_name, record.provider, { api_url: record.api_url, api_key: record.api_key })}
                  >
                    测试
                  </Button>
                  <Button 
                    size="small" 
                    type="link" 
                    icon={<EditOutlined />}
                    onClick={() => {
                      setEditingCustomModel(record);
                      customModelForm.setFieldsValue(record);
                      setCustomModelModal(true);
                    }}
                  >
                    编辑
                  </Button>
                  <Popconfirm 
                    title="确认删除此模型？" 
                    onConfirm={() => handleDeleteCustomModel(record.model_name)}
                  >
                    <Button size="small" type="link" danger icon={<DeleteOutlined />}>
                      删除
                    </Button>
                  </Popconfirm>
                </Space>
              )
            }
          ]}
          dataSource={customModels}
          loading={customModelsLoading}
          rowKey="model_name"
          locale={{ emptyText: "暂无自定义模型配置" }}
          pagination={false}
        />
        
        {testResult && (
          <Alert 
            style={{ marginTop: 16 }}
            message={testResult.success ? "模型测试成功" : "模型测试失败"}
            description={
              testResult.success 
                ? `延迟: ${testResult.latency_ms}ms, 向量维度: ${testResult.embedding_dim}`
                : `错误: ${testResult.error}`
            }
            type={testResult.success ? "success" : "error"}
            showIcon
            closable
            onClose={() => setTestResult(null)}
          />
        )}
      </Card>
    )},
    { key: "rerankers", label: "Reranker配置", children: (
      <Card 
        title={<><ApiOutlined /> 自定义Reranker模型配置</>}
        extra={
          <Button type="primary" icon={<PlusOutlined />} onClick={() => setCustomRerankerModal(true)}>
            添加自定义Reranker
          </Button>
        }
      >
        <Alert 
          message="自定义Reranker说明" 
          description="您可以添加自定义的Reranker模型，通过配置API URL和API Key来连接您自己的 rerank 服务。支持 OpenAI 兼容格式的API。" 
          type="info" 
          showIcon 
          style={{ marginBottom: 16 }}
        />
        
        <Table
          columns={[
            {
              title: "模型名称",
              dataIndex: "model_name",
              key: "model_name",
              render: (name: string) => <Text strong>{name}</Text>
            },
            {
              title: "提供商",
              dataIndex: "provider",
              key: "provider",
              render: (provider: string) => (
                <Tag color={provider === "custom" ? "purple" : "blue"}>{provider}</Tag>
              )
            },
            {
              title: "API URL",
              dataIndex: "api_url",
              key: "api_url",
              ellipsis: true,
              render: (url: string) => url || "-"
            },
            {
              title: "状态",
              dataIndex: "enabled",
              key: "enabled",
              render: (enabled: boolean) => (
                <Badge status={enabled ? "success" : "default"} text={enabled ? "已启用" : "已禁用"} />
              )
            },
            {
              title: "操作",
              key: "action",
              render: (_: any, record: CustomModelConfig) => (
                <Space>
                  <Button 
                    size="small" 
                    type="link" 
                    icon={<ExperimentOutlined />}
                    onClick={() => testReranker(record.model_name, record.provider, { api_url: record.api_url, api_key: record.api_key })}
                  >
                    测试
                  </Button>
                  <Button 
                    size="small" 
                    type="link" 
                    icon={<EditOutlined />}
                    onClick={() => {
                      setEditingCustomReranker(record);
                      customRerankerForm.setFieldsValue(record);
                      setCustomRerankerModal(true);
                    }}
                  >
                    编辑
                  </Button>
                  <Popconfirm 
                    title="确认删除此Reranker模型？" 
                    onConfirm={() => handleDeleteCustomReranker(record.model_name)}
                  >
                    <Button size="small" type="link" danger icon={<DeleteOutlined />}>
                      删除
                    </Button>
                  </Popconfirm>
                </Space>
              )
            }
          ]}
          dataSource={customRerankers}
          loading={customRerankersLoading}
          rowKey="model_name"
          locale={{ emptyText: "暂无自定义Reranker模型配置" }}
          pagination={false}
        />
        
        {testResult && (
          <Alert 
            style={{ marginTop: 16 }}
            message={testResult.success ? "Reranker模型测试成功" : "Reranker模型测试失败"}
            description={
              testResult.success 
                ? `延迟: ${testResult.latency_ms}ms, 返回结果数: ${testResult.embedding_dim || 0}`
                : `错误: ${testResult.error}`
            }
            type={testResult.success ? "success" : "error"}
            showIcon
            closable
            onClose={() => setTestResult(null)}
          />
        )}
      </Card>
    )},
    { key: "search", label: "测试搜索", children: searchTab },
    { key: "history", label: "搜索历史", children: historyTab },
    { key: "patentSources", label: "专利数据源", children: (
      <Card 
        title={<><CloudServerOutlined /> 专利数据源API配置</>}
        extra={
          <Button type="primary" icon={<PlusOutlined />} onClick={() => setPatentSourceModal(true)}>
            添加数据源
          </Button>
        }
      >
        <Alert 
          message="数据源配置说明" 
          description="配置您自己的专利数据库API密钥。支持: 大为(dawei)、佰腾(baiten)、CNIPA、Lens等数据源。部分数据源需要商业API密钥。" 
          type="info" 
          showIcon 
          style={{ marginBottom: 16 }}
        />
        
        <Table
          columns={[
            {
              title: "数据源",
              dataIndex: "source_name",
              key: "source_name",
              render: (name: string) => (
                <Tag color={name === 'baiten' ? 'green' : name === 'dawei' ? 'blue' : name === 'lens' ? 'purple' : 'orange'}>
                  {name.toUpperCase()}
                </Tag>
              )
            },
            {
              title: "App ID",
              dataIndex: "app_id",
              key: "app_id",
              ellipsis: true,
              render: (id: string) => id || "-"
            },
            {
              title: "API地址",
              dataIndex: "api_url",
              key: "api_url",
              ellipsis: true,
              render: (url: string) => url || "默认"
            },
            {
              title: "状态",
              dataIndex: "is_enabled",
              key: "is_enabled",
              render: (enabled: boolean) => (
                <Badge status={enabled ? "success" : "default"} text={enabled ? "已启用" : "已禁用"} />
              )
            },
            {
              title: "操作",
              key: "action",
              render: (_: any, record: PatentSourceConfig) => (
                <Space>
                  <Button 
                    size="small" 
                    type="link" 
                    icon={<EditOutlined />}
                    onClick={() => {
                      setEditingPatentSource(record);
                      patentSourceForm.setFieldsValue(record);
                      setPatentSourceModal(true);
                    }}
                  >
                    编辑
                  </Button>
                  <Popconfirm 
                    title="确认删除此数据源配置？" 
                    onConfirm={() => handleDeletePatentSource(record.id)}
                  >
                    <Button size="small" type="link" danger icon={<DeleteOutlined />}>
                      删除
                    </Button>
                  </Popconfirm>
                </Space>
              )
            }
          ]}
          dataSource={patentSourceConfigs}
          loading={patentSourceConfigsLoading}
          rowKey="id"
          locale={{ emptyText: "暂无数据源配置" }}
          pagination={false}
        />
      </Card>
    )},
  ];

  return (
    <div style={{ padding: "24px" }}>
      <Title level={2} style={{ marginBottom: 24 }}>
        <DatabaseOutlined style={{ marginRight: 8 }} />
        RAG管理
      </Title>
      
      <Tabs 
        activeKey={activeTab} 
        onChange={setActiveTab} 
        items={tabItems}
        size="large"
      />
      
      {/* 索引文档Modal */}
      <Modal
        title="索引新文档"
        open={indexModal}
        onCancel={() => {
          setIndexModal(false);
          indexForm.resetFields();
        }}
        onOk={handleIndexDocument}
        width={700}
      >
        <Form form={indexForm} layout="vertical">
          <Form.Item name="application_number" label="申请号">
            <Input placeholder="例如: CN202110000001.0" />
          </Form.Item>
          <Form.Item name="title" label="标题" rules={[{ required: true }]}>
            <Input placeholder="文档标题" />
          </Form.Item>
          <Form.Item name="abstract" label="摘要">
            <TextArea rows={3} placeholder="专利摘要" />
          </Form.Item>
          <Form.Item name="description" label="详细说明">
            <TextArea rows={4} placeholder="专利详细说明" />
          </Form.Item>
          <Form.Item name="claims" label="权利要求">
            <TextArea rows={4} placeholder="权利要求书 (每行一条)" />
          </Form.Item>
        </Form>
      </Modal>
      
      {/* 配置编辑Modal */}
      <Modal
        title="编辑RAG配置"
        open={configModal}
        onCancel={() => {
          setConfigModal(false);
          setTestResult(null);
        }}
        onOk={handleSaveConfig}
        confirmLoading={configSaving}
        width={700}
      >
        <Spin spinning={modelsLoading}>
          <Form form={configForm} layout="vertical">
            <Divider>基础配置</Divider>
            <Form.Item name="vector_db_type" label="向量数据库" rules={[{ required: true }]}>
              <Select options={VECTOR_DB_OPTIONS} />
            </Form.Item>
            
            <Divider>Embedding模型配置</Divider>
            <Form.Item 
              name="embedding_model" 
              label="Embedding模型" 
              rules={[{ required: true }]}
              extra={
                <Space>
                  <Button 
                    size="small" 
                    icon={<ExperimentOutlined />} 
                    onClick={() => {
                      const model = configForm.getFieldValue('embedding_model');
                      if (model) testModel(model);
                    }}
                    loading={modelTesting}
                  >
                    测试连通性
                  </Button>
                  {testResult && (
                    <Tag color={testResult.success ? "green" : "red"}>
                      {testResult.success 
                        ? `✓ 成功 (${testResult.latency_ms}ms, ${testResult.embedding_dim}维)` 
                        : `✗ 失败: ${testResult.error}`}
                    </Tag>
                  )}
                </Space>
              }
            >
              <Select 
                options={
                  availableModels?.embedding_models.map(m => ({
                    value: m.value,
                    label: `${m.label} (${m.provider})`
                  })) || EMBEDDING_MODEL_OPTIONS
                }
                showSearch
                optionFilterProp="label"
              />
            </Form.Item>
            
            <Row gutter={16}>
              <Col span={12}>
                <Form.Item name="chunk_size" label="分块大小" rules={[{ required: true }]}>
                  <InputNumber min={100} max={2000} step={100} style={{ width: "100%" }} />
                </Form.Item>
              </Col>
              <Col span={12}>
                <Form.Item name="chunk_overlap" label="分块重叠" rules={[{ required: true }]}>
                  <InputNumber min={0} max={500} step={50} style={{ width: "100%" }} />
                </Form.Item>
              </Col>
            </Row>
            <Row gutter={16}>
              <Col span={12}>
                <Form.Item name="retrieval_top_k" label="检索Top K">
                  <InputNumber min={1} max={100} style={{ width: "100%" }} />
                </Form.Item>
              </Col>
              <Col span={12}>
                <Form.Item name="embedding_dimension" label="Embedding维度">
                  <InputNumber min={128} max={4096} step={128} style={{ width: "100%" }} />
                </Form.Item>
              </Col>
            </Row>
            
            <Divider>搜索配置</Divider>
            <Row gutter={16}>
              <Col span={12}>
                <Form.Item name="rerank_enabled" label="启用Rerank" valuePropName="checked">
                  <Switch />
                </Form.Item>
              </Col>
              <Col span={12}>
                <Form.Item name="hybrid_search_alpha" label="混合搜索Alpha (0-1)">
                  <Slider min={0} max={1} step={0.1} marks={{ 0: '0', 0.5: '0.5', 1: '1' }} />
                </Form.Item>
              </Col>
            </Row>
            
            {availableModels && availableModels.rerank_models.length > 0 && (
              <>
                <Divider>Rerank模型</Divider>
                <Alert 
                  message="可用Rerank模型" 
                  description={
                    <Space wrap style={{ marginTop: 8 }}>
                      {availableModels.rerank_models.map(m => (
                        <Tag key={m.value} color="blue">
                          {m.label} ({m.provider})
                        </Tag>
                      ))}
                    </Space>
                  }
                  type="info" 
                  showIcon 
                />
              </>
            )}
          </Form>
        </Spin>
      </Modal>

      {/* 文件上传Modal */}
      <Modal
        title={<><UploadOutlined /> 上传文件</>}
        open={uploadModal}
        onCancel={() => {
          setUploadModal(false);
          setUploadResult(null);
        }}
        footer={null}
        width={500}
      >
        <Dragger
          accept=".pdf,.docx,.doc,.txt,.xlsx,.xls,.pptx"
          beforeUpload={handleFileUpload}
          showUploadList={false}
          disabled={uploading}
        >
          <p className="ant-upload-drag-icon">
            <InboxOutlined />
          </p>
          <p className="ant-upload-text">点击或拖拽文件到此区域上传</p>
          <p className="ant-upload-hint">
            支持 PDF、Word、Excel、PowerPoint、TXT 文件
          </p>
        </Dragger>
        
        {uploading && (
          <div style={{ marginTop: 16 }}>
            <Spin indicator={<LoadingOutlined spin />} />
            <Text style={{ marginLeft: 8 }}>正在上传并索引...</Text>
          </div>
        )}
        
        {uploadResult && (
          <Alert 
            style={{ marginTop: 16 }}
            message={uploadResult.success ? "上传成功" : "上传失败"}
            description={uploadResult.success 
              ? `文件: ${uploadResult.file_name}, 大小: ${(uploadResult.file_size / 1024).toFixed(2)} KB`
              : uploadResult.error
            }
            type={uploadResult.success ? "success" : "error"}
            showIcon
          />
        )}
      </Modal>

      {/* URL爬取Modal */}
      <Modal
        title={<><LinkOutlined /> URL爬取</>}
        open={urlCrawlModal}
        onCancel={() => {
          setUrlCrawlModal(false);
          setCrawlResult(null);
          urlCrawlForm.resetFields();
        }}
        footer={null}
        width={500}
      >
        <Form form={urlCrawlForm} layout="vertical">
          <Form.Item 
            name="url" 
            label="URL地址" 
            rules={[
              { required: true, message: "请输入URL地址" },
              { type: "url", message: "请输入有效的URL" }
            ]}
          >
            <Input placeholder="https://example.com/article" prefix={<GlobalOutlined />} />
          </Form.Item>
          
          <Form.Item name="extract_images" label="选项" valuePropName="checked" initialValue={false}>
            <Checkbox>提取图片URL</Checkbox>
          </Form.Item>
          
          <Button 
            type="primary" 
            icon={<LinkOutlined />} 
            onClick={handleURLCrawl}
            loading={crawling}
            block
          >
            爬取并索引
          </Button>
        </Form>
        
        {crawlResult && (
          <Alert 
            style={{ marginTop: 16 }}
            message={crawlResult.success ? "爬取成功" : "爬取失败"}
            description={
              <div>
                <p style={{ marginBottom: 8 }}>{crawlResult.content}</p>
                {crawlResult.success && (
                  <Button type="link" onClick={() => {
                    setActiveTab("search");
                    setUrlCrawlModal(false);
                  }}>
                    前往搜索测试
                  </Button>
                )}
              </div>
            }
            type={crawlResult.success ? "success" : "error"}
            showIcon
          />
        )}
      </Modal>

      {/* 专利数据爬取Modal */}
      <Modal
        title={<><GlobalOutlined /> 专利数据爬取</>}
        open={patentCrawlModal}
        onCancel={() => {
          setPatentCrawlModal(false);
          patentCrawlForm.resetFields();
        }}
        footer={null}
        width={600}
      >
        <Form form={patentCrawlForm} layout="vertical">
          <Form.Item 
            name="query" 
            label="搜索关键词" 
            rules={[{ required: true, message: "请输入搜索关键词" }]}
          >
            <Input placeholder="例如: 人工智能, 机器学习" />
          </Form.Item>
          
          <Form.Item 
            name="sources" 
            label="数据源" 
            initialValue={["cnipa", "uspto"]}
          >
            <Checkbox.Group options={[
              { label: '中国CNIPA', value: 'cnipa' },
              { label: '美国USPTO', value: 'uspto' },
              { label: '欧洲EPO', value: 'epo' },
              { label: 'WIPO', value: 'wipo' },
              { label: '大为Dawei', value: 'dawei' },
            ]} />
          </Form.Item>
          
          <Form.Item name="max_results" label="每个数据源最大结果数" initialValue={20}>
            <InputNumber min={1} max={100} style={{ width: "100%" }} />
          </Form.Item>
          
          <Alert 
            style={{ marginBottom: 16 }}
            message="说明"
            description="系统将在各大专利数据库中搜索并自动索引到RAG系统"
            type="info"
            showIcon
          />
          
          <Button 
            type="primary" 
            icon={<GlobalOutlined />} 
            onClick={handlePatentCrawl}
            loading={patentCrawling}
            block
          >
            开始爬取并索引
          </Button>
        </Form>
      </Modal>

      {/* 自定义模型配置Modal */}
      <Modal
        title={<><ApiOutlined /> {editingCustomModel ? "编辑" : "添加"}自定义Embedding模型</>}
        open={customModelModal}
        onCancel={() => {
          setCustomModelModal(false);
          customModelForm.resetFields();
          setEditingCustomModel(null);
        }}
        onOk={handleAddCustomModel}
        width={600}
      >
        <Alert 
          message="支持的API格式"
          description="支持 OpenAI 兼容格式的 API（如 OpenAI、Azure OpenAI、LocalAI、Ollama 等）。请确保API服务支持 /v1/embeddings 端点。"
          type="info" 
          showIcon 
          style={{ marginBottom: 16 }}
        />
        
        <Form form={customModelForm} layout="vertical">
          <Form.Item 
            name="model_name" 
            label="模型名称" 
            rules={[{ required: true, message: "请输入模型名称" }]}
            extra="用于标识该模型的唯一名称"
          >
            <Input placeholder="例如: my-custom-embedding" />
          </Form.Item>
          
          <Form.Item 
            name="provider" 
            label="提供商" 
            initialValue="custom"
            rules={[{ required: true, message: "请选择提供商" }]}
          >
            <Select>
              <Select.Option value="custom">自定义 (Custom)</Select.Option>
              <Select.Option value="openai">OpenAI</Select.Option>
              <Select.Option value="huggingface">HuggingFace</Select.Option>
              <Select.Option value="zhipu">智谱AI</Select.Option>
              <Select.Option value="ollama">Ollama</Select.Option>
            </Select>
          </Form.Item>
          
          <Form.Item 
            name="api_url" 
            label="API URL"
            rules={[{ required: true, message: "请输入API URL" }]}
            extra="OpenAI兼容格式的API地址"
          >
            <Input placeholder="https://api.openai.com/v1" />
          </Form.Item>
          
          <Form.Item 
            name="api_key" 
            label="API Key"
            rules={[{ required: true, message: "请输入API Key" }]}
          >
            <Input.Password placeholder="请输入API Key" />
          </Form.Item>
          
          <Row gutter={16}>
            <Col span={12}>
              <Form.Item 
                name="dimension" 
                label="向量维度"
                initialValue={1536}
              >
                <InputNumber min={64} max={4096} step={128} style={{ width: "100%" }} />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item 
                name="enabled" 
                label="启用状态" 
                valuePropName="checked"
                initialValue={true}
              >
                <Switch checkedChildren="启用" unCheckedChildren="禁用" />
              </Form.Item>
            </Col>
          </Row>
        </Form>
      </Modal>

      {/* 自定义Reranker模型配置Modal */}
      <Modal
        title={<><ApiOutlined /> {editingCustomReranker ? "编辑" : "添加"}自定义Reranker模型</>}
        open={customRerankerModal}
        onCancel={() => {
          setCustomRerankerModal(false);
          customRerankerForm.resetFields();
          setEditingCustomReranker(null);
        }}
        onOk={handleAddCustomReranker}
        width={600}
      >
        <Alert 
          message="支持的API格式"
          description="支持 OpenAI 兼容格式的 API（如 OpenAI、Cohere、LocalAI 等）。请确保API服务支持 rerank 端点。"
          type="info" 
          showIcon 
          style={{ marginBottom: 16 }}
        />
        
        <Form form={customRerankerForm} layout="vertical">
          <Form.Item 
            name="model_name" 
            label="模型名称" 
            rules={[{ required: true, message: "请输入模型名称" }]}
            extra="用于标识该模型的唯一名称"
          >
            <Input placeholder="例如: my-custom-reranker" />
          </Form.Item>
          
          <Form.Item 
            name="provider" 
            label="提供商" 
            initialValue="custom"
            rules={[{ required: true, message: "请选择提供商" }]}
          >
            <Select>
              <Select.Option value="custom">自定义 (Custom)</Select.Option>
              <Select.Option value="openai">OpenAI</Select.Option>
              <Select.Option value="cohere">Cohere</Select.Option>
              <Select.Option value="huggingface">HuggingFace</Select.Option>
            </Select>
          </Form.Item>
          
          <Form.Item 
            name="api_url" 
            label="API URL"
            rules={[{ required: true, message: "请输入API URL" }]}
            extra="OpenAI兼容格式的API地址"
          >
            <Input placeholder="https://api.openai.com/v1" />
          </Form.Item>
          
          <Form.Item 
            name="api_key" 
            label="API Key"
            rules={[{ required: true, message: "请输入API Key" }]}
          >
            <Input.Password placeholder="请输入API Key" />
          </Form.Item>
          
          <Form.Item 
            name="enabled" 
            label="启用状态" 
            valuePropName="checked"
            initialValue={true}
          >
            <Switch checkedChildren="启用" unCheckedChildren="禁用" />
          </Form.Item>
        </Form>
      </Modal>

      {/* 专利数据源配置Modal */}
      <Modal
        title={<><CloudServerOutlined /> {editingPatentSource ? "编辑" : "添加"}专利数据源配置</>}
        open={patentSourceModal}
        onCancel={() => {
          setPatentSourceModal(false);
          patentSourceForm.resetFields();
          setEditingPatentSource(null);
        }}
        onOk={handleAddPatentSource}
        width={500}
      >
        <Alert 
          message="数据源配置说明" 
          description="配置您自己的专利数据库API密钥。每个数据源的API密钥可在对应的官网申请。" 
          type="info" 
          showIcon 
          style={{ marginBottom: 16 }}
        />
        
        <Form form={patentSourceForm} layout="vertical">
          <Form.Item 
            name="source_name" 
            label="数据源" 
            rules={[{ required: true, message: "请选择数据源" }]}
          >
            <Select placeholder="选择数据源">
              <Select.Option value="dawei">大为 (Dawei)</Select.Option>
              <Select.Option value="baiten">佰腾 (Baiten)</Select.Option>
              <Select.Option value="cnipa">中国国家知识产权局 (CNIPA)</Select.Option>
              <Select.Option value="lens">The Lens</Select.Option>
              <Select.Option value="soopat">SooPAT</Select.Option>
            </Select>
          </Form.Item>
          
          <Form.Item 
            name="app_id" 
            label="App ID"
            extra="部分数据源需要提供App ID"
          >
            <Input placeholder="请输入App ID (可选)" />
          </Form.Item>
          
          <Form.Item 
            name="api_key" 
            label="API Key"
            rules={[{ required: true, message: "请输入API Key" }]}
            extra="在对应数据源官网申请API密钥"
          >
            <Input.Password placeholder="请输入API Key" />
          </Form.Item>
          
          <Form.Item 
            name="api_url" 
            label="API 地址"
            extra="留空使用默认地址"
          >
            <Input placeholder="https://api.example.com/v1 (可选)" />
          </Form.Item>
          
          <Form.Item 
            name="is_enabled" 
            label="启用状态" 
            valuePropName="checked"
            initialValue={true}
          >
            <Switch checkedChildren="启用" unCheckedChildren="禁用" />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
}
