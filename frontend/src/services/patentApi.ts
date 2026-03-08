import api from "./api";

export const patentApi = {
  getList: async (params: any) => {
    const res = await api.get("/patents/", { params: { page: params.page, page_size: params.page_size, status: params.status, keyword: params.search } });
    return res.data?.data || { items: [], total: 0 };
  },
  getDetail: async (id: number) => {
    const res = await api.get(`/patents/${id}`);
    return res.data?.data;
  },
  create: async (data: any) => {
    const res = await api.post("/patents/", data);
    return res.data?.data;
  },
  update: async (id: number, data: any) => {
    const res = await api.put(`/patents/${id}`, data);
    return res.data?.data;
  },
  delete: async (id: number) => {
    const res = await api.delete(`/patents/${id}`);
    return res.data;
  },
  importFile: async (file: File) => {
    const fd = new FormData();
    fd.append("file", file);
    const res = await api.post("/patents/import", fd, { headers: { "Content-Type": "multipart/form-data" } });
    return res.data?.data;
  },
  getStatistics: async () => {
    const res = await api.get("/patents/statistics");
    return res.data?.data || {};
  },
};
