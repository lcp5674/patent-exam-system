"""AI 提供商管理器 - 统一管理多个大模型提供商"""
from __future__ import annotations
import logging
from typing import Optional, AsyncIterator
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.config import settings
from app.database.models import AIProviderConfig
from .adapter import AIProviderAdapter, AICompletionResponse

logger = logging.getLogger(__name__)


class ProviderManager:
    def __init__(self):
        self._providers: dict[str, AIProviderAdapter] = {}
        self._db_configs: dict[str, AIProviderConfig] = {}
        self._initialized = False

    async def initialize(self):
        """初始化所有已配置的提供商"""
        if self._initialized:
            return

        from .providers.openai_provider import OpenAIProvider
        from .providers.doubao_provider import DoubaoProvider
        from .providers.minimax_provider import MiniMaxProvider
        from .providers.openrouter_provider import OpenRouterProvider
        from .providers.ollama_provider import OllamaProvider
        from .providers.zhipu_provider import ZhipuProvider
        from .providers.gemini_provider import GeminiProvider
        from .providers.nvidia_provider import NVIDIAProvider

        provider_classes = [OpenAIProvider, DoubaoProvider, MiniMaxProvider, OpenRouterProvider, OllamaProvider, ZhipuProvider, GeminiProvider, NVIDIAProvider]
        for cls in provider_classes:
            try:
                provider = cls()
                self._providers[provider.name] = provider
                logger.info(f"[AI] 已注册提供商: {provider.display_name}")
            except Exception as e:
                logger.warning(f"[AI] 注册提供商失败 {cls.__name__}: {e}")

        self._initialized = True

    async def load_db_configs(self, db: AsyncSession):
        """从数据库加载配置"""
        result = await db.execute(select(AIProviderConfig))
        configs = result.scalars().all()
        for config in configs:
            self._db_configs[config.provider_name] = config
        logger.info(f"[AI] 从数据库加载了 {len(configs)} 个提供商配置")

    async def reload_from_db(self, db: AsyncSession):
        """从数据库重新加载配置"""
        await self.load_db_configs(db)
        
        # 同时存储小写版本的配置映射，用于大小写不敏感查找
        db_configs_lower = {name.lower(): (name, config) for name, config in self._db_configs.items()}
        
        for name_lower, (original_name, config) in db_configs_lower.items():
            if config.is_enabled:
                self._apply_config(original_name, config)
            else:
                # 尝试删除 provider（大小写不敏感）
                provider_found = False
                for pname in list(self._providers.keys()):
                    if pname.lower() == name_lower:
                        del self._providers[pname]
                        provider_found = True
                        break
                if not provider_found:
                    logger.warning(f"[AI] 提供商 {original_name} 未注册，无法删除")

    def _apply_config(self, name: str, config: AIProviderConfig):
        """应用数据库配置到提供商"""
        # 大小写不敏感匹配
        provider_name_lower = name.lower()
        provider = None
        
        # 先精确匹配
        if name in self._providers:
            provider = self._providers[name]
        else:
            # 大小写不敏感匹配
            for pname, p in self._providers.items():
                if pname.lower() == provider_name_lower:
                    provider = p
                    break
        
        if not provider:
            logger.warning(f"[AI] 提供商 {name} 未注册，无法应用配置")
            logger.warning(f"[AI] 可用的提供商: {list(self._providers.keys())}")
            return
        
        logger.info(f"[AI] 找到提供商: {name}, provider: {provider}")
        
        # 打印配置信息（注意：不要打印实际的 api_key）
        logger.info(f"[AI] 数据库配置: api_key exists={bool(config.api_key)}, base_url={config.base_url}, default_model={config.default_model}, is_enabled={config.is_enabled}, is_default={config.is_default}")
        
        # 使用 setattr 避免 __dict__ 问题
        if config.api_key:
            setattr(provider, 'api_key', config.api_key)
            logger.info(f"[AI] 已设置 api_key (长度: {len(config.api_key)})")
        else:
            logger.warning(f"[AI] 数据库中 {name} 的 api_key 为空!")
            
        if config.base_url:
            setattr(provider, 'base_url', config.base_url.rstrip("/"))
            logger.info(f"[AI] 已设置 base_url: {config.base_url}")
        if config.default_model:
            setattr(provider, 'default_model', config.default_model)
            logger.info(f"[AI] 已设置 default_model: {config.default_model}")
        if config.extra_config:
            for key, value in config.extra_config.items():
                setattr(provider, key, value)
        
        logger.info(f"[AI] 已应用 {name} 的数据库配置")

    def get_provider(self, name: Optional[str] = None) -> AIProviderAdapter:
        logger.info(f"[AI] get_provider called with name: {name}")
        logger.info(f"[AI] Available providers: {list(self._providers.keys())}")
        logger.info(f"[AI] DB configs: {list(self._db_configs.keys())}")
        
        # 如果没有指定，使用默认提供商
        if not name:
            for provider_name, config in self._db_configs.items():
                if config.is_default:
                    name = provider_name
                    break
            name = name or settings.ai.DEFAULT_AI_PROVIDER
        
        logger.info(f"[AI] Final provider name to use: {name}")
        
        # 应用数据库配置（无论是否显式指定）
        name_lower = name.lower()
        for config_name, config in self._db_configs.items():
            if config_name.lower() == name_lower and config.is_enabled:
                logger.info(f"[AI] Found DB config for: {config_name}")
                self._apply_config(config_name, config)
                break
        
        # 大小写不敏感查找 provider
        name_lower = name.lower()
        provider = None
        
        # 先精确匹配
        if name in self._providers:
            provider = self._providers[name]
            logger.info(f"[AI] Found provider by exact match: {name}")
        else:
            # 大小写不敏感匹配
            for pname, p in self._providers.items():
                if pname.lower() == name_lower:
                    provider = p
                    logger.info(f"[AI] Found provider by case-insensitive match: {pname}")
                    break
        
        if provider is None:
            error_msg = f"AI 提供商 '{name}' 不存在或未配置。可用: {list(self._providers.keys())}"
            logger.error(f"[AI] {error_msg}")
            raise ValueError(error_msg)
        
        return provider

    def list_providers(self) -> list[dict]:
        result = []
        for name, p in self._providers.items():
            config = self._db_configs.get(name)
            is_enabled = config.is_enabled if config else True
            is_available = bool(config and config.api_key) if config else bool(getattr(p, 'api_key', None))
            
            # 尝试健康检查
            try:
                import asyncio
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    is_available = is_available
                else:
                    is_available = asyncio.run(p.health_check()) if is_available else False
            except:
                is_available = is_available
            
            result.append({
                "name": name,
                "display_name": p.display_name,
                "models": p.get_available_models(),
                "is_enabled": is_enabled,
                "is_available": is_available,
                "default_model": config.default_model if config else getattr(p, 'default_model', ''),
                "base_url": config.base_url if config else getattr(p, 'base_url', ''),
            })
        return result

    async def chat(self, messages: list[dict], provider: Optional[str] = None, model: Optional[str] = None, **kwargs) -> AICompletionResponse:
        """统一聊天接口 - 支持自动降级"""
        p = self.get_provider(provider)
        
        # 检查当前 provider 是否有有效的 api_key
        api_key = getattr(p, 'api_key', None)
        
        # 如果没有 api_key，直接尝试降级
        if not api_key:
            logger.warning(f"[AI] 提供商 {p.name} 没有配置 API Key，尝试降级")
            fallback_p = self._try_fallback_provider(provider, messages, model, **kwargs)
            if fallback_p:
                return await fallback_p.chat_completion(messages, model=model, **kwargs)
            raise ValueError(f"提供商 {p.name} 没有配置 API Key，且没有可用的备用提供商")
        
        try:
            return await p.chat_completion(messages, model=model, **kwargs)
        except Exception as e:
            error_str = str(e)
            logger.error(f"[AI] {p.name} 调用失败: {e}, 尝试降级")
            
            # 只有在认证错误（无 API Key 或 401/403）时才降级，不要在 404 时降级
            # 404 通常表示 API 端点不可用或服务已下线
            is_auth_error = "401" in error_str or "403" in error_str or "Illegal header" in error_str or "no API key" in error_str.lower()
            is_not_found = "404" in error_str
            
            if is_not_found:
                logger.warning(f"[AI] {p.name} 返回 404，服务可能已下线或不可用，不尝试降级")
                raise
            
            # 认证错误或未知错误时尝试降级
            fallback_p = self._try_fallback_provider(p.name, messages, model, **kwargs)
            if fallback_p:
                return await fallback_p.chat_completion(messages, model=model, **kwargs)
            raise

    def _try_fallback_provider(self, current_provider: Optional[str], messages: list[dict], model: Optional[str] = None, **kwargs) -> Optional[AIProviderAdapter]:
        """尝试找到一个有有效 API Key 的备用提供商"""
        tried = {current_provider} if current_provider else set()
        
        # 首先尝试数据库中标记为默认的且有 api_key 的 provider
        for config_name, config in self._db_configs.items():
            if config.is_default and config.api_key and config.is_enabled:
                name_lower = config_name.lower()
                for pname, p in self._providers.items():
                    if pname.lower() == name_lower and pname not in tried:
                        api_key = getattr(p, 'api_key', None)
                        if api_key:
                            logger.info(f"[AI] 降级到默认提供商: {config_name}")
                            return p
                        # 尝试应用配置
                        self._apply_config(config_name, config)
                        api_key = getattr(p, 'api_key', None)
                        if api_key:
                            logger.info(f"[AI] 降级到默认提供商: {config_name}")
                            return p
        
        # 遍历所有有有效 api_key 的 provider
        for pname, p in self._providers.items():
            if pname in tried:
                continue
            # 检查 provider 是否有有效的 api_key
            api_key = getattr(p, 'api_key', None)
            if not api_key:
                # 尝试从数据库配置获取
                config = self._db_configs.get(pname)
                if config and config.api_key and config.is_enabled:
                    self._apply_config(pname, config)
                    api_key = getattr(p, 'api_key', None)
            
            if api_key:
                logger.info(f"[AI] 降级到备用提供商: {pname}")
                return p
        
        return None

    async def stream(self, messages: list[dict], provider: Optional[str] = None, model: Optional[str] = None, **kwargs) -> AsyncIterator[str]:
        """流式聊天接口"""
        p = self.get_provider(provider)
        
        # 检查当前 provider 是否有有效的 api_key
        api_key = getattr(p, 'api_key', None)
        
        if not api_key:
            raise ValueError(f"提供商 {p.name} 没有配置 API Key")
        
        try:
            async for chunk in p.chat_completion_stream(messages, model=model, **kwargs):
                yield chunk
        except Exception as e:
            logger.error(f"[AI] {p.name} 流式调用失败: {e}")
            raise


# 全局单例
provider_manager = ProviderManager()
