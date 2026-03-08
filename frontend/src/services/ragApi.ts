import api from "./api";

// ============== Types ==============

export interface SearchRequest {
  query: string;
  top_k?: number;
  search_type?: "semantic" | "keyword" | "hybrid";
  use_rerank?: boolean;
  filters?: Record<string, any>;
}

export interface SearchResult {
  id: string;
  content: string;
  score: number;
  metadata: Record<string, any>;
  source: string;
}

export interface PatentSearchRequest {
  query: string;
  sources?: ("dawei" | "cnipa" | "uspto" | "wipo" | "epo" | "google" | "lens")[];
  max_results?: number;
  date_from?: string;
  date_to?: string;
  classifications?: string[];
  auto_index?: boolean;
}

export interface PatentSource {
  name: string;
  available: boolean;
}

export interface RAGConfig {
  vector_db_type: string;
  embedding_model: string;
  embedding_dimension: number;
  chunk_size: number;
  chunk_overlap: number;
  retrieval_top_k: number;
  rerank_enabled: boolean;
  hybrid_search_alpha: number;
}

export interface RAGHealth {
  status: string;
  vector_db: string;
  embedding_service: string;
  connectors: PatentSource[];
  timestamp: string;
}

export interface CollectionStats {
  collection: string;
  document_count: number;
  backend: string;
  additional_info?: Record<string, any>;
}

// RAG文件管理
export interface RagDocument {
  id: number;
  tenant_id?: number;
  file_name: string;
  file_type: string;
  file_size: number;
  file_path: string;
  chunk_count: number;
  indexed_count: number;
  status: string;
  error_message?: string;
  indexed_at?: string;
  created_at: string;
  updated_at?: string;
}

export interface RagDocumentListResponse {
  documents: RagDocument[];
  total: number;
}

export interface ReindexResponse {
  success: boolean;
  document_id: number;
  indexed_count: number;
  message: string;
}


// 可用模型选项
export interface ModelOption {
  value: string;
  label: string;
  provider: string;
  dimension?: number;
}

export interface AvailableModels {
  embedding_models: ModelOption[];
  rerank_models: ModelOption[];
}

export interface IndexDocumentRequest {
  document_id?: string;
  application_number?: string;
  title?: string;
  abstract?: string;
  claims?: string[];
  description?: string;
  technical_field?: string;
  metadata?: Record<string, any>;
}

export interface SearchResponse {
  query: string;
  chunks: SearchResult[];
  total: number;
  search_type: string;
  latency_ms: number;
  tenant_id?: string;
  citations?: any[];
  reference_list?: string;
  inline_citations?: string;
}

export interface PatentSearchResponse {
  query: string;
  results: Record<string, any[]>;
  total_count: number;
  sources_searched: string[];
}

// 文件上传响应
export interface FileUploadResponse {
  success: boolean;
  file_name: string;
  file_type: string;
  file_size: number;
  content?: string;
  chunk_count: number;
  error?: string;
}

// URL爬取请求
export interface URLCrawlRequest {
  url: string;
  extract_images?: boolean;
  max_depth?: number;
}

// URL爬取响应
export interface URLCrawlResponse {
  success: boolean;
  url: string;
  title?: string;
  content?: string;
  metadata?: Record<string, any>;
  images?: string[];
  error?: string;
}

// 模型测试请求（支持自定义URL和API Key）
export interface ModelTestRequest {
  model_name: string;
  provider?: string;
  test_text?: string;
  api_url?: string;
  api_key?: string;
}

// 模型测试响应
export interface ModelTestResponse {
  success: boolean;
  model_name: string;
  provider: string;
  latency_ms: number;
  embedding_dim?: number;
  sample_embedding?: number[];
  error?: string;
}

// 分块配置
export interface ChunkingConfig {
  chunk_size: number;
  chunk_overlap: number;
  split_by_sentence: boolean;
  min_chunk_size?: number;
  max_chunk_size?: number;
}

// 知识库条目
export interface KnowledgeBaseEntry {
  id: string;
  document_id: string;
  title: string;
  content: string;
  chunk_index: number;
  metadata: Record<string, any>;
  created_at: string;
}

// 搜索历史
export interface SearchHistory {
  id: string;
  query: string;
  search_type: string;
  result_count: number;
  timestamp: string;
}

// 自定义模型配置
export interface CustomModelConfig {
  model_name: string;
  provider: string;
  api_url?: string;
  api_key?: string;
  dimension?: number;
  enabled?: boolean;
}

// 专利数据源配置
export interface PatentSourceConfig {
  id: number;
  source_name: string;
  app_id?: string;
  api_url?: string;
  is_enabled: boolean;
  created_at: string;
  updated_at: string;
}

export interface PatentSourceConfigCreate {
  source_name: string;
  api_key?: string;
  app_id?: string;
  api_url?: string;
  is_enabled?: boolean;
}

export interface PatentSourceConfigUpdate {
  api_key?: string;
  app_id?: string;
  api_url?: string;
  is_enabled?: boolean;
}

// ============== API =============

export const ragApi = {
  // ========== 搜索 ==========
  
  // RAG搜索
  search: async (data: SearchRequest): Promise<SearchResponse> => {
    const res = await api.post("/rag/search", data);
    return res.data;
  },

  // ========== 索引管理 ==========
  
  // 索引文档
  indexDocument: async (data: IndexDocumentRequest): Promise<any> => {
    const res = await api.post("/rag/index", data);
    return res.data;
  },

  // 批量索引
  indexBatch: async (documents: IndexDocumentRequest[]): Promise<any> => {
    const res = await api.post("/rag/index/batch", { documents });
    return res.data;
  },

  // 删除文档
  deleteDocument: async (documentId: string): Promise<any> => {
    const res = await api.delete("/rag/documents", { data: { document_id: documentId } });
    return res.data;
  },

  // ========== 配置管理 ==========
  
  // 获取RAG配置
  getConfig: async (): Promise<RAGConfig> => {
    const res = await api.get("/rag/config");
    return res.data;
  },

  // 更新RAG配置
  updateConfig: async (config: Partial<RAGConfig>): Promise<any> => {
    const res = await api.put("/rag/config", config);
    return res.data;
  },

  // 获取可用模型列表
  getAvailableModels: async (): Promise<AvailableModels> => {
    const res = await api.get("/rag/models");
    return res.data;
  },

  // ========== 统计 ==========
  
  // 获取集合统计
  getStats: async (tenantId?: string): Promise<CollectionStats> => {
    const url = tenantId ? `/rag/stats?tenant_id=${tenantId}` : "/rag/stats";
    const res = await api.get(url);
    return res.data;
  },

  // 健康检查
  getHealth: async (): Promise<RAGHealth> => {
    const res = await api.get("/rag/health");
    return res.data;
  },

  // ========== 专利数据库 ==========
  
  // 专利数据库搜索
  searchPatents: async (data: PatentSearchRequest): Promise<PatentSearchResponse> => {
    const res = await api.post("/rag/patents/search", data);
    return res.data;
  },

  // 获取可用数据源
  getPatentSources: async (): Promise<{ connectors: PatentSource[] }> => {
    const res = await api.get("/rag/patents/sources");
    return res.data;
  },

  // 搜索并索引
  searchAndIndex: async (data: PatentSearchRequest): Promise<any> => {
    const res = await api.post("/rag/patents/search-and-index", data);
    return res.data;
  },

  // ========== 文件上传 ==========
  
  // 上传文本文件
  uploadTextFile: async (file: File): Promise<FileUploadResponse> => {
    const formData = new FormData();
    formData.append('file', file);
    const res = await api.post("/rag/upload/text", formData, {
      headers: { 'Content-Type': 'multipart/form-data' }
    });
    return res.data;
  },

  // 上传并索引文件
  uploadAndIndexFile: async (file: File, tenantId: string): Promise<any> => {
    const formData = new FormData();
    formData.append('file', file);
    const res = await api.post(`/rag/upload/file-and-index?tenant_id=${tenantId}`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' }
    });
    return res.data;
  },

  // ========== 文件管理 ==========
  
  // 获取文件列表
  getFiles: async (tenantId: string, skip = 0, limit = 50, status?: string): Promise<RagDocumentListResponse> => {
    let url = `/rag/files?tenant_id=${tenantId}&skip=${skip}&limit=${limit}`;
    if (status) {
      url += `&status=${status}`;
    }
    const res = await api.get(url);
    return res.data;
  },

  // 获取文件详情
  getFile: async (fileId: number, tenantId: string): Promise<RagDocument> => {
    const res = await api.get(`/rag/files/${fileId}?tenant_id=${tenantId}`);
    return res.data;
  },

  // 删除文件
  deleteFile: async (fileId: number, tenantId: string): Promise<any> => {
    const res = await api.delete(`/rag/files/${fileId}?tenant_id=${tenantId}`);
    return res.data;
  },

  // 重新索引文件
  reindexFile: async (fileId: number, tenantId: string): Promise<ReindexResponse> => {
    const res = await api.post(`/rag/files/${fileId}/reindex?tenant_id=${tenantId}`);
    return res.data;
  },

  // 下载文件
  downloadFile: async (fileId: number, tenantId: string): Promise<Blob> => {
    const res = await api.get(`/rag/files/${fileId}/download?tenant_id=${tenantId}`, {
      responseType: 'blob'
    });
    return res.data;
  },

  // ========== URL爬取 ==========
  
  // 爬取URL
  crawlURL: async (data: URLCrawlRequest): Promise<URLCrawlResponse> => {
    const res = await api.post("/rag/crawl/url", data);
    return res.data;
  },

  // 爬取URL并索引
  crawlAndIndexURL: async (data: URLCrawlRequest, tenantId: string): Promise<any> => {
    const res = await api.post(`/rag/crawl/url-and-index?tenant_id=${tenantId}`, data);
    return res.data;
  },

  // ========== 模型测试 ==========
  
  // 测试Embedding模型
  testEmbeddingModel: async (data: ModelTestRequest): Promise<ModelTestResponse> => {
    const res = await api.post("/rag/models/test", data);
    return res.data;
  },

  // 测试Reranker模型
  testRerankerModel: async (data: ModelTestRequest): Promise<ModelTestResponse> => {
    const res = await api.post("/rag/rerankers/test", data);
    return res.data;
  },

  // 爬取专利数据
  crawlPatents: async (data: PatentSearchRequest, tenantId: string): Promise<any> => {
    const res = await api.post(`/rag/patents/crawl?tenant_id=${tenantId}`, data);
    return res.data;
  },

  // ========== 多模态 ==========
  
  // OCR识别
  ocrImage: async (formData: FormData): Promise<any> => {
    const res = await api.post("/multimodal/ocr", formData, {
      headers: { 'Content-Type': 'multipart/form-data' }
    });
    return res.data;
  },

  // 图像分析
  analyzeImage: async (formData: FormData): Promise<any> => {
    const res = await api.post("/multimodal/analyze", formData, {
      headers: { 'Content-Type': 'multipart/form-data' }
    });
    return res.data;
  },

  // 批量处理图像
  batchProcessImages: async (patentId: string, formData: FormData): Promise<any> => {
    formData.append('patent_id', patentId);
    const res = await api.post("/multimodal/batch-process", formData, {
      headers: { 'Content-Type': 'multipart/form-data' }
    });
    return res.data;
  },

  // 多模态健康检查
  getMultimodalHealth: async (): Promise<any> => {
    const res = await api.get("/multimodal/health");
    return res.data;
  },

  // ========== 自定义模型配置 ==========
  
  // 获取自定义模型配置列表
  getCustomModels: async (): Promise<{ custom_configs: CustomModelConfig[] }> => {
    const res = await api.get("/rag/models/custom");
    return res.data;
  },

  // 添加自定义模型配置
  addCustomModel: async (config: CustomModelConfig): Promise<CustomModelConfig> => {
    const res = await api.post("/rag/models/custom", config);
    return res.data;
  },

  // 更新自定义模型配置
  updateCustomModel: async (config: CustomModelConfig): Promise<CustomModelConfig> => {
    const res = await api.put(`/rag/models/custom/${encodeURIComponent(config.model_name)}`, config);
    return res.data;
  },

  // 删除自定义模型配置
  deleteCustomModel: async (modelName: string): Promise<any> => {
    const res = await api.delete(`/rag/models/custom/${encodeURIComponent(modelName)}`);
    return res.data;
  },

  // ========== 自定义Reranker模型配置 ==========
  
  // 获取自定义Reranker模型配置列表
  getCustomRerankers: async (): Promise<{ custom_configs: CustomModelConfig[] }> => {
    const res = await api.get("/rag/rerankers/custom");
    return res.data;
  },

  // 添加自定义Reranker模型配置
  addCustomReranker: async (config: CustomModelConfig): Promise<CustomModelConfig> => {
    const res = await api.post("/rag/rerankers/custom", config);
    return res.data;
  },

  // 更新自定义Reranker模型配置
  updateCustomReranker: async (config: CustomModelConfig): Promise<CustomModelConfig> => {
    const res = await api.put(`/rag/rerankers/custom/${encodeURIComponent(config.model_name)}`, config);
    return res.data;
  },

  // 删除自定义Reranker模型配置
  deleteCustomReranker: async (modelName: string): Promise<any> => {
    const res = await api.delete(`/rag/rerankers/custom/${encodeURIComponent(modelName)}`);
    return res.data;
  },

  // ========== 专利数据源配置 ==========
  
  // 获取专利数据源配置列表
  getPatentSourceConfigs: async (tenantId: string): Promise<{ configs: PatentSourceConfig[], total: number }> => {
    const res = await api.get(`/rag/patents/source-configs?tenant_id=${tenantId}`);
    return res.data;
  },

  // 创建专利数据源配置
  createPatentSourceConfig: async (config: PatentSourceConfigCreate, tenantId: string): Promise<PatentSourceConfig> => {
    const res = await api.post(`/rag/patents/source-configs?tenant_id=${tenantId}`, config);
    return res.data;
  },

  // 更新专利数据源配置
  updatePatentSourceConfig: async (configId: number, config: PatentSourceConfigUpdate, tenantId: string): Promise<PatentSourceConfig> => {
    const res = await api.put(`/rag/patents/source-configs/${configId}?tenant_id=${tenantId}`, config);
    return res.data;
  },

  // 删除专利数据源配置
  deletePatentSourceConfig: async (configId: number, tenantId: string): Promise<any> => {
    const res = await api.delete(`/rag/patents/source-configs/${configId}?tenant_id=${tenantId}`);
    return res.data;
  },

  // ========== 搜索历史 ==========
  
  // 获取搜索历史
  getSearchHistory: async (tenantId: string, limit = 50): Promise<{ history: SearchHistory[], total: number }> => {
    const res = await api.get(`/rag/search-history?tenant_id=${tenantId}&limit=${limit}`);
    return res.data;
  },

  // 删除搜索历史
  deleteSearchHistory: async (historyId: string, tenantId: string): Promise<any> => {
    const res = await api.delete(`/rag/search-history/${historyId}?tenant_id=${tenantId}`);
    return res.data;
  },

  // 清空搜索历史
  clearSearchHistory: async (tenantId: string): Promise<any> => {
    const res = await api.delete(`/rag/search-history?tenant_id=${tenantId}`);
    return res.data;
  }
};
