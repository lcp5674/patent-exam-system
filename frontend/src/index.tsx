import React from "react";
import ReactDOM from "react-dom/client";
import { Provider } from "react-redux";
import { BrowserRouter } from "react-router-dom";
import { ConfigProvider } from "antd";
import zhCN from "antd/locale/zh_CN";
import enUS from "antd/locale/en_US";
import { store } from "./store";
import App from "./App";
import "./i18n";

// 获取保存的语言设置
const getAntdLocale = () => {
  const savedLang = localStorage.getItem('language');
  if (savedLang === 'en-US') {
    return enUS;
  }
  return zhCN;
};

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <Provider store={store}>
      <BrowserRouter>
        <ConfigProvider locale={getAntdLocale()} theme={{ token: { colorPrimary: "#1677ff" } }}>
          <App />
        </ConfigProvider>
      </BrowserRouter>
    </Provider>
  </React.StrictMode>
);
