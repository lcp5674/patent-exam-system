import axios from "axios";

const api = axios.create({ 
  baseURL: "/api/v1", 
  timeout: 120000,
  maxRedirects: 0,
});

api.interceptors.request.use((config) => {
  const token = localStorage.getItem("access_token");
  // 确保token不为空才添加Authorization头
  if (token && token.trim() !== "") {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

api.interceptors.response.use(
  (resp) => resp,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem("access_token");
      window.location.href = "/login";
    }
    if (error.response?.status === 307 || error.response?.status === 308) {
      const token = localStorage.getItem("access_token");
      if (token) {
        const redirectUrl = error.response.headers.location;
        return api.get(redirectUrl, { headers: { Authorization: `Bearer ${token}` } });
      }
    }
    return Promise.reject(error);
  }
);

export default api;
