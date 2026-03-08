import api from "./api";

export interface Tenant {
  id: number;
  name: string;
  code: string;
  description?: string;
  is_active: boolean;
  max_users: number;
  max_patents: number;
  user_count?: number;
  created_at?: string;
}

export interface TenantListParams {
  page?: number;
  page_size?: number;
  keyword?: string;
}

export interface TenantCreate {
  name: string;
  code: string;
  description?: string;
  max_users?: number;
  max_patents?: number;
}

export interface TenantUpdate {
  name?: string;
  description?: string;
  is_active?: boolean;
  max_users?: number;
  max_patents?: number;
}

export const tenantApi = {
  list: async (params: TenantListParams) => {
    const res = await api.get("/tenants/", { params: { page: params.page, page_size: params.page_size, keyword: params.keyword } });
    return res.data?.data || { items: [], total: 0, page: 1, page_size: 20, total_pages: 0 };
  },
  
  get: async (id: number) => {
    const res = await api.get(`/tenants/${id}`);
    return res.data?.data;
  },
  
  create: async (data: TenantCreate) => {
    const res = await api.post("/tenants/", data);
    return res.data?.data;
  },
  
  update: async (id: number, data: TenantUpdate) => {
    const res = await api.put(`/tenants/${id}`, data);
    return res.data?.data;
  },
  
  delete: async (id: number) => {
    const res = await api.delete(`/tenants/${id}`);
    return res.data;
  },
};
