import api from "./api";

export interface ReportTemplate {
  id: number;
  template_name: string;
  template_type: string;
  content: string;
  section_config?: SectionConfig[];
  variables: Record<string, any>;
  is_default: boolean;
  created_at: string;
  updated_at: string;
}

export interface SectionConfig {
  id: string;
  enabled: boolean;
  order: number;
  custom_content?: string;
}

export interface SectionDefinition {
  id: string;
  name: string;
  description: string;
  has_custom_content: boolean;
  variables: string[];
  default_content: string;
}

export interface ReportHistory {
  id: number;
  opinion_type: string;
  content: string;
  status: string;
  template_id: number | null;
  examination_record_id: number | null;
  created_at: string;
}

export const reportApi = {
  // 生成报告
  generate: async (params: { 
    patent_id: number; 
    report_type: string; 
    examination_id?: number;
    template_id?: number;
  }) => {
    const { patent_id, report_type, examination_id, template_id } = params;
    let endpoint = "/reports/opinion-notice";
    let requestParams: any = { patent_id };
    
    if (report_type === "approval_notice") {
      endpoint = "/reports/grant-notice";
    } else if (report_type === "rejection_decision") {
      endpoint = "/reports/rejection-decision";
    }
    
    if (examination_id) requestParams.examination_id = examination_id;
    if (template_id) requestParams.template_id = template_id;
    
    const res = await api.post(endpoint, null, { params: requestParams });
    return res.data?.data || {};
  },
  
  // 获取模板列表
  getTemplates: async (templateType?: string): Promise<ReportTemplate[]> => {
    const params = templateType ? { template_type: templateType } : {};
    const res = await api.get("/reports/templates", { params });
    return res.data?.data || [];
  },
  
  // 获取单个模板
  getTemplate: async (templateId: number): Promise<ReportTemplate> => {
    const res = await api.get(`/reports/templates/${templateId}`);
    return res.data?.data;
  },
  
  // 创建模板
  createTemplate: async (template: {
    template_name: string;
    template_type: string;
    content?: string;
    section_config?: SectionConfig[];
    variables?: Record<string, any>;
    is_default?: boolean;
  }) => {
    const res = await api.post("/reports/templates", template);
    return res.data?.data;
  },
  
  // 更新模板
  updateTemplate: async (templateId: number, template: {
    template_name?: string;
    content?: string;
    section_config?: SectionConfig[];
    variables?: Record<string, any>;
    is_default?: boolean;
  }) => {
    const res = await api.put(`/reports/templates/${templateId}`, template);
    return res.data?.data;
  },
  
  // 删除模板
  deleteTemplate: async (templateId: number) => {
    const res = await api.delete(`/reports/templates/${templateId}`);
    return res.data?.data;
  },
  
  // 获取区块定义
  getSectionDefinitions: async (templateType: string = "opinion_notice"): Promise<SectionDefinition[]> => {
    const res = await api.get("/reports/sections", { params: { template_type: templateType } });
    return res.data?.data?.sections || [];
  },
  
  // 上传模板文件
  uploadTemplateFile: async (file: File, templateType: string, templateName?: string): Promise<any> => {
    const formData = new FormData();
    formData.append("file", file);
    if (templateType) formData.append("template_type", templateType);
    if (templateName) formData.append("template_name", templateName);
    
    const res = await api.post("/reports/templates/upload", formData, {
      headers: { "Content-Type": "multipart/form-data" },
    });
    return res.data?.data;
  },
  
  // 获取专利的报告历史
  getReportHistory: async (patentId: number): Promise<ReportHistory[]> => {
    const res = await api.get("/reports/history", { params: { patent_id: patentId } });
    return res.data?.data || [];
  },
  
  // 获取单个报告详情
  getReport: async (reportId: number): Promise<ReportHistory> => {
    const res = await api.get(`/reports/${reportId}`);
    return res.data?.data;
  },
};
