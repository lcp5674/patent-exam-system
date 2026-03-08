import api from "./api";

export interface OneClickExamResult {
  patent_id: number;
  steps_completed: string[];
  formal_result: any;
  substantive_result: any;
  ai_analysis: any;
  issues: Array<{
    stage: string;
    rule: string;
    severity: string;
    message: string;
    legal_basis?: string;
  }>;
  suggestions: Array<{
    issue: string;
    suggestion: string;
  }>;
  overall_status: string;
  score: number;
}

export const examApi = {
  runFormal: async (patentId: number, enableLlm: boolean = false, provider?: string) => {
    const res = await api.post(`/examination/${patentId}/formal`, null, { 
      params: { enable_llm: enableLlm, llm_provider: provider } 
    });
    return res.data?.data;
  },
  runSubstantive: async (patentId: number, provider?: string, enableLlm: boolean = true) => {
    const res = await api.post(`/examination/${patentId}/substantive`, null, { 
      params: { provider, enable_llm: enableLlm } 
    });
    return res.data?.data;
  },
  runOneClick: async (patentId: number, provider?: string, enableLlm: boolean = true): Promise<OneClickExamResult> => {
    const res = await api.post(`/examination/${patentId}/one-click`, null, { 
      params: { provider, enable_llm: enableLlm } 
    });
    return res.data?.data;
  },
  getHistory: async (patentId: number) => {
    const res = await api.get(`/examination/${patentId}/history`);
    return res.data?.data || [];
  },
};
