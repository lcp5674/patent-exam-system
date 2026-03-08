import axios from 'axios';

const API_BASE = '/api';

export const agentApi = {
  // Agent状态
  getAgentStatus: () => axios.get(`${API_BASE}/agents/status`),
  
  // 爬取任务
  triggerFullCrawl: (data: any) => axios.post(`${API_BASE}/crawl/full`, data),
  triggerIncrementalCrawl: (data: any) => axios.post(`${API_BASE}/crawl/incremental`, data),
  getTaskList: () => axios.get(`${API_BASE}/crawl/tasks`),
  getTaskDetail: (id: string) => axios.get(`${API_BASE}/crawl/tasks/${id}`),
  
  // RAG管理
  getCollections: () => axios.get(`${API_BASE}/rag/collections`),
  testRetrieval: (data: any) => axios.post(`${API_BASE}/rag/test-retrieval`, data),
  
  // 监控
  getMetrics: () => axios.get(`${API_BASE}/monitoring/metrics`),
  getHealth: () => axios.get(`${API_BASE}/monitoring/health`),
};

export default agentApi;
