import api from "./api";
import type { User } from "../types";

export interface UserListParams {
  page?: number;
  page_size?: number;
  role?: string;
  is_active?: boolean;
  keyword?: string;
}

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export const userApi = {
  login: async (username: string, password: string) => {
    const res = await api.post("/users/login", { username, password });
    return res.data?.data;
  },
  register: async (data: any) => {
    const res = await api.post("/users/register", data);
    return res.data?.data;
  },
  refreshToken: async (refresh_token: string) => {
    const res = await api.post("/users/refresh", { refresh_token });
    return res.data?.data;
  },
  logout: async () => {
    const res = await api.post("/users/logout");
    return res.data;
  },
  getMe: async () => {
    const res = await api.get("/users/me");
    return res.data?.data;
  },
  changePassword: async (data: any) => {
    const res = await api.put("/users/me/password", data);
    return res.data;
  },
  
  // 用户管理（管理员）
  listUsers: async (params: UserListParams = {}) => {
    const res = await api.get("/users/", { params });
    return res.data?.data as PaginatedResponse<User>;
  },
  
  getUser: async (userId: number) => {
    const res = await api.get(`/users/${userId}`);
    return res.data?.data as User;
  },
  
  createUser: async (data: {
    username: string;
    password: string;
    email?: string;
    full_name?: string;
    department?: string;
    role?: string;
  }) => {
    const res = await api.post("/users/", data);
    return res.data?.data;
  },
  
  updateUser: async (userId: number, data: Partial<{
    email: string;
    full_name: string;
    department: string;
    role: string;
    is_active: boolean;
    password: string;
  }>) => {
    const res = await api.put(`/users/${userId}`, data);
    return res.data?.data;
  },
  
  deleteUser: async (userId: number) => {
    const res = await api.delete(`/users/${userId}`);
    return res.data;
  },
  
  toggleUserActive: async (userId: number) => {
    const res = await api.post(`/users/${userId}/toggle-active`);
    return res.data?.data;
  },
};
