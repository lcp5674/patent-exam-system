/**
 * i18n 国际化配置文件
 * 基于 react-i18next
 */
import i18n from 'i18next';
import { initReactI18next } from 'react-i18next';

import zhCN from './locales/zh-CN.json';
import enUS from './locales/en-US.json';

// 翻译资源
const resources = {
  'zh-CN': {
    translation: zhCN,
  },
  'en-US': {
    translation: enUS,
  },
};

// 初始化 i18next
i18n
  .use(initReactI18next)
  .init({
    resources,
    // 默认语言
    lng: 'zh-CN',
    // 语言回退
    fallbackLng: 'zh-CN',
    // 默认命名空间
    defaultNS: 'translation',
    // 命名空间列表
    ns: ['translation'],
    // 插值配置
    interpolation: {
      // React 已经安全处理了 XSS
      escapeValue: false,
    },
    // React i18next 选项
    react: {
      // 在组件卸载时使用后台语言
      useSuspense: false,
    },
  });

export default i18n;

// 支持的语言列表
export const supportedLanguages = [
  { code: 'zh-CN', name: '简体中文', nativeName: '简体中文' },
  { code: 'en-US', name: 'English', nativeName: 'English' },
];

// 获取当前语言
export const getCurrentLanguage = (): string => {
  return i18n.language || 'zh-CN';
};

// 切换语言
export const changeLanguage = (lang: string): void => {
  i18n.changeLanguage(lang);
};
