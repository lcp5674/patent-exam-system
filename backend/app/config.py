"""
专利审查辅助系统 - 全局配置
支持 MySQL / PostgreSQL / SQLite 多数据库后端
支持多种 AI 大模型提供商
"""
from __future__ import annotations
import os
from pathlib import Path
from typing import Optional
from pydantic_settings import BaseSettings
from pydantic import Field


BASE_DIR = Path(__file__).resolve().parent.parent


class DatabaseSettings(BaseSettings):
    """数据库配置 - 兼容 MySQL / PostgreSQL / SQLite"""
    DATABASE_URL: str = Field(
        default=f"sqlite+aiosqlite:///{BASE_DIR / 'data' / 'patent_exam.db'}",
        description="数据库连接字符串"
    )
    DB_ECHO: bool = False
    DB_POOL_SIZE: int = 20  # 优化：增加连接池大小，支持高并发
    DB_MAX_OVERFLOW: int = 30  # 优化：增加最大溢出连接数
    DB_POOL_RECYCLE: int = 3600

    @property
    def db_type(self) -> str:
        url = self.DATABASE_URL.lower()
        if "postgresql" in url or "postgres" in url:
            return "postgresql"
        elif "mysql" in url:
            return "mysql"
        return "sqlite"

    model_config = {"env_prefix": "", "env_file": ".env", "extra": "ignore"}


class SecuritySettings(BaseSettings):
    SECRET_KEY: str = Field(
        default="",
        description="JWT签名密钥，未设置时自动生成"
    )
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    AES_KEY: str = Field(
        default="",
        description="AES加密密钥，未设置时自动生成"
    )

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        import secrets
        if not self.SECRET_KEY:
            self.SECRET_KEY = secrets.token_hex(32)
            print("[警告] SECRET_KEY 未设置，已自动生成。请在生产环境中设置 SECURITY_SECRET_KEY 环境变量")
        if not self.AES_KEY:
            self.AES_KEY = secrets.token_hex(16)
            print("[警告] AES_KEY 未设置，已自动生成。请在生产环境中设置 SECURITY_AES_KEY 环境变量")

    model_config = {"env_prefix": "", "env_file": ".env", "extra": "ignore"}


class AIProviderSettings(BaseSettings):
    """AI 大模型提供商配置"""
    DEFAULT_AI_PROVIDER: str = "ollama"

    # OpenAI / GPT
    OPENAI_API_KEY: str = ""
    OPENAI_BASE_URL: str = "https://api.openai.com/v1"
    OPENAI_DEFAULT_MODEL: str = "gpt-4"

    # 豆包 (Doubao / ByteDance Ark)
    DOUBAO_API_KEY: str = ""
    DOUBAO_BASE_URL: str = "https://ark.cn-beijing.volces.com/api/v3"
    DOUBAO_DEFAULT_MODEL: str = ""

    # MiniMax
    MINIMAX_API_KEY: str = ""
    MINIMAX_GROUP_ID: str = ""
    MINIMAX_BASE_URL: str = "https://api.minimax.chat/v1"
    MINIMAX_DEFAULT_MODEL: str = "abab6.5s-chat"

    # OpenRouter
    OPENROUTER_API_KEY: str = ""
    OPENROUTER_BASE_URL: str = "https://openrouter.ai/api/v1"
    OPENROUTER_DEFAULT_MODEL: str = "openai/gpt-4o"

    # Ollama (本地模型)
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_DEFAULT_MODEL: str = "qwen2.5:7b"

    # 智谱 AI (Zhipu / ChatGLM)
    ZHIPU_API_KEY: str = ""
    ZHIPU_BASE_URL: str = "https://open.bigmodel.cn/api/paas/v4"
    ZHIPU_DEFAULT_MODEL: str = "glm-4"

    # Google Gemini
    GEMINI_API_KEY: str = ""
    GEMINI_BASE_URL: str = "https://generativelanguage.googleapis.com"
    GEMINI_DEFAULT_MODEL: str = "gemini-1.5-flash"

    # NVIDIA NIM (NVIDIA Inference Microservices)
    NVIDIA_API_KEY: str = ""
    NVIDIA_BASE_URL: str = "https://integrate.api.nvidia.com/v1"
    NVIDIA_DEFAULT_MODEL: str = "nvidia/llama-3.1-nemotron-70b-instruct"

    # 通用 AI 配置
    AI_REQUEST_TIMEOUT: int = 30  # 优化：缩短超时时间，提升用户体验
    AI_MAX_RETRIES: int = 3
    AI_RATE_LIMIT_PER_MINUTE: int = 100  # 优化：提高调用频率限制，支持高并发

    model_config = {"env_prefix": "", "env_file": ".env", "extra": "ignore"}


class AppSettings(BaseSettings):
    APP_NAME: str = "专利审查辅助系统"
    APP_VERSION: str = "1.0.0"
    APP_ENV: str = "development"
    DEBUG: bool = True
    LOG_LEVEL: str = "INFO"

    UPLOAD_DIR: str = os.environ.get("UPLOAD_DIR", str(BASE_DIR / "data" / "uploads"))
    MAX_UPLOAD_SIZE_MB: int = 50
    LOG_DIR: str = str(BASE_DIR / "data" / "logs")
    PATENT_DNA_STORAGE_PATH: str = str(BASE_DIR / "data" / "patent_dna")
    BACKUP_DIR: str = str(BASE_DIR / "data" / "backups")

    CORS_ORIGINS: str = "http://localhost:3000,http://localhost:5173,http://localhost:8080"

    model_config = {"env_prefix": "", "env_file": ".env", "extra": "ignore"}


class CacheSettings(BaseSettings):
    """Redis缓存配置"""
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_PASSWORD: str = ""
    REDIS_DB: int = 0
    REDIS_MAX_CONNECTIONS: int = 100  # 优化：增加最大连接数，支持高并发
    
    # 缓存配置
    CACHE_DEFAULT_TTL: int = 300  # 默认5分钟
    CACHE_USER_TTL: int = 3600     # 用户信息1小时
    CACHE_QUERY_TTL: int = 1800   # 查询缓存30分钟
    CACHE_ENABLED: bool = True
    
    model_config = {"env_prefix": "", "env_file": ".env", "extra": "ignore"}


class MonitoringSettings(BaseSettings):
    """监控配置"""
    METRICS_ENABLED: bool = True
    METRICS_PORT: int = 9090
    
    # OpenTelemetry
    OTEL_ENABLED: bool = False
    OTEL_EXPORTER_ENDPOINT: str = "http://localhost:4317"
    
    model_config = {"env_prefix": "", "env_file": ".env", "extra": "ignore"}


class Settings:
    """聚合配置"""
    def __init__(self):
        self.db = DatabaseSettings()
        self.security = SecuritySettings()
        self.ai = AIProviderSettings()
        self.app = AppSettings()
        self.cache = CacheSettings()
        self.monitoring = MonitoringSettings()
        self._ai_provider_cache = {}
        self._cache_updated_at = 0

    def ensure_dirs(self):
        for d in [self.app.UPLOAD_DIR, self.app.LOG_DIR,
                  self.app.PATENT_DNA_STORAGE_PATH, self.app.BACKUP_DIR]:
            Path(d).mkdir(parents=True, exist_ok=True)
    
    async def load_ai_provider_configs(self, db_session = None):
        """从数据库加载AI提供商配置，覆盖环境变量配置"""
        import time
        # 缓存5分钟
        if self._cache_updated_at > time.time() - 300 and self._ai_provider_cache:
            return self._ai_provider_cache
        
        if not db_session:
            # 如果没有提供数据库会话，返回缓存或环境变量配置
            return self._ai_provider_cache or self._get_env_ai_configs()
        
        from app.database.models import AIProviderConfig
        result = await db_session.execute(select(AIProviderConfig).where(AIProviderConfig.is_enabled == True))
        providers = result.scalars().all()
        
        configs = {}
        default_provider = None
        
        for provider in providers:
            configs[provider.provider_name] = {
                "api_key": provider.api_key,
                "base_url": provider.base_url,
                "default_model": provider.default_model,
                "is_enabled": provider.is_enabled,
                "priority": provider.priority
            }
            if provider.is_default:
                default_provider = provider.provider_name
        
        # 如果没有默认提供商，使用环境变量配置
        if not default_provider:
            default_provider = self.ai.DEFAULT_AI_PROVIDER
        
        self._ai_provider_cache = {
            "providers": configs,
            "default_provider": default_provider
        }
        self._cache_updated_at = time.time()
        
        return self._ai_provider_cache
    
    def _get_env_ai_configs(self):
        """从环境变量获取AI配置"""
        return {
            "providers": {
                "doubao": {
                    "api_key": self.ai.DOUBAO_API_KEY,
                    "base_url": self.ai.DOUBAO_BASE_URL,
                    "default_model": self.ai.DOUBAO_DEFAULT_MODEL,
                    "is_enabled": bool(self.ai.DOUBAO_API_KEY),
                    "priority": 10
                },
                "openai": {
                    "api_key": self.ai.OPENAI_API_KEY,
                    "base_url": self.ai.OPENAI_BASE_URL,
                    "default_model": self.ai.OPENAI_DEFAULT_MODEL,
                    "is_enabled": bool(self.ai.OPENAI_API_KEY),
                    "priority": 20
                }
            },
            "default_provider": self.ai.DEFAULT_AI_PROVIDER
        }
    
    def clear_ai_config_cache(self):
        """清除AI配置缓存"""
        self._ai_provider_cache = {}
        self._cache_updated_at = 0


settings = Settings()
