import api from "./api";

export interface AIProviderConfig {
  id?: number;
  provider_name: string;
  display_name: string;
  api_key?: string;
  base_url?: string;
  default_model?: string;
  is_enabled: boolean;
  is_default: boolean;
  extra_config?: Record<string, any>;
  priority: number;
}

export const aiApi = {
  chat: async (data: any) => {
    const res = await api.post("/ai/chat", {
      message: data.message,
      provider: data.provider,
      model: data.model,
      history: data.context || [],
    });
    return res.data?.data || {};
  },
  analyze: async (data: any) => {
    const res = await api.post("/ai/analyze", data);
    return res.data?.data || {};
  },
  // 流式分析 - 返回EventSource用于实时进度
  analyzeStream: (data: any, onMessage: (data: any) => void, onError?: (error: any) => void) => {
    const token = localStorage.getItem("access_token");
    const url = `${window.location.origin}/api/v1/ai/analyze/stream`;
    
    // 如果没有token，直接报错
    if (!token) {
      onError?.(new Error("未登录或登录已过期"));
      return { close: () => {} };
    }
    
    // 使用fetch + ReadableStream实现流式读取
    const fetchStream = async () => {
      try {
        console.log("开始流式请求, token:", token ? "存在" : "不存在");
        
        const response = await fetch(url, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "Authorization": `Bearer ${token}`,
          },
          body: JSON.stringify(data),
        });
        
        console.log("响应状态:", response.status);
        
        if (!response.ok) {
          throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        const reader = response.body?.getReader();
        const decoder = new TextDecoder();
        
        if (!reader) {
          throw new Error("No reader available");
        }
        
        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          
          const chunk = decoder.decode(value, { stream: true });
          const lines = chunk.split("\n");
          
          for (const line of lines) {
            if (line.startsWith("data: ")) {
              try {
                const jsonStr = line.slice(6);
                if (jsonStr === "[DONE]") {
                  continue;
                }
                const parsed = JSON.parse(jsonStr);
                onMessage(parsed);
              } catch (e) {
                // 忽略解析错误
              }
            }
          }
        }
      } catch (error) {
        console.error("流式请求失败:", error);
        onError?.(error);
      }
    };
    
    // 启动fetch流
    fetchStream();
    
    return {
      close: () => {},
    };
  },
  getProviders: async () => {
    const res = await api.get("/ai/providers");
    return { providers: res.data?.data || [] };
  },
  
  // 提供商配置管理
  getProviderConfigs: async () => {
    const res = await api.get("/ai/providers/config");
    return res.data?.data || [];
  },
  
  createProviderConfig: async (config: AIProviderConfig) => {
    const res = await api.post("/ai/providers/config", config);
    return res.data?.data;
  },
  
  updateProviderConfig: async (providerName: string, config: Partial<AIProviderConfig>) => {
    const res = await api.put(`/ai/providers/config/${providerName}`, config);
    return res.data?.data;
  },
  
  deleteProviderConfig: async (providerName: string) => {
    const res = await api.delete(`/ai/providers/config/${providerName}`);
    return res.data;
  },
  
  testProvider: async (providerName: string) => {
    const res = await api.post(`/ai/providers/config/${providerName}/test`);
    return res.data?.data || {};
  },
};
