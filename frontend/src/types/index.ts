// ─── 通用类型 ─────────────────────────────────────────
export interface ApiResponse<T = any> {
  code: number;
  message?: string;
  data: T;
}

export interface PaginatedData<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

// ─── 用户 ─────────────────────────────────────────────
export interface User {
  id: number;
  username: string;
  role: string;
  email?: string;
  full_name?: string;
  department?: string;
  is_active: boolean;
  created_at?: string;
}

export interface LoginRequest { username: string; password: string; }
export interface LoginResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
  user: User;
}

// ─── 专利 ─────────────────────────────────────────────
export interface Patent {
  id: number;
  application_number: string;
  application_date?: string;
  title: string;
  applicant: string;
  inventor?: string;
  agent?: string;
  status: string;
  priority_date?: string;
  ipc_classification?: string;
  file_path?: string;
  abstract?: string;
  technical_field?: string;
  parsed_content?: any;
  created_at?: string;
  updated_at?: string;
}

// ─── 审查 ─────────────────────────────────────────────
export interface ExaminationRecord {
  id: number;
  application_id: number;
  examination_type: string;
  examination_step: string;
  status: string;
  result?: any;
  confidence_score?: number;
  ai_model_used?: string;
  start_time?: string;
  end_time?: string;
  created_at?: string;
}

// ─── 规则 ─────────────────────────────────────────────
export interface Rule {
  id: number;
  rule_name: string;
  rule_type: string;
  rule_category: string;
  rule_content?: any;
  priority: number;
  is_active: boolean;
  description?: string;
  legal_basis?: string;
}

// ─── AI ───────────────────────────────────────────────
export interface AIProvider {
  name: string;
  display_name: string;
  is_available: boolean;
  is_enabled?: boolean;
  models: string[];
  default_model?: string;
  base_url?: string;
}

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

export interface PatentStatistics {
  total: number;
  pending: number;
  examining: number;
  granted: number;
  rejected: number;
}
