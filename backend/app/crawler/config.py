"""爬虫配置文件"""
import os
from typing import Dict, List, Optional
try:
    from pydantic import BaseSettings
except ImportError:
    from pydantic_settings import BaseSettings

class CrawlerConfig(BaseSettings):
    """爬虫配置类"""

    # 数据库配置
    MONGODB_URI: str = os.getenv("MONGODB_URI", "mongodb://localhost:27017/")
    MONGODB_DB: str = os.getenv("MONGODB_DB", "patent_data")

    # Redis配置（用于分布式锁和缓存）
    REDIS_HOST: str = os.getenv("REDIS_HOST", "localhost")
    REDIS_PORT: int = int(os.getenv("REDIS_PORT", 6379))
    REDIS_PASSWORD: Optional[str] = os.getenv("REDIS_PASSWORD")
    REDIS_DB: int = int(os.getenv("REDIS_DB", 0))

    # 向量数据库配置
    MILVUS_URI: str = os.getenv("MILVUS_URI", "http://localhost:19530")
    MILVUS_COLLECTION: str = os.getenv("MILVUS_COLLECTION", "patents")

    # 代理配置
    PROXY_ENABLED: bool = os.getenv("PROXY_ENABLED", "false").lower() == "true"
    PROXY_POOL_API: str = os.getenv("PROXY_POOL_API", "")

    # 反爬配置
    REQUEST_DELAY_MIN: float = float(os.getenv("REQUEST_DELAY_MIN", "1.0"))
    REQUEST_DELAY_MAX: float = float(os.getenv("REQUEST_DELAY_MAX", "3.0"))
    MAX_RETRIES: int = int(os.getenv("MAX_RETRIES", "3"))
    TIMEOUT: int = int(os.getenv("TIMEOUT", "30"))

    # 并发控制
    MAX_CONCURRENT_REQUESTS: int = int(os.getenv("MAX_CONCURRENT_REQUESTS", "5"))

    # 增量更新配置
    UPDATE_CHECK_INTERVAL: int = int(os.getenv("UPDATE_CHECK_INTERVAL", "3600"))  # 秒
    FULL_CRAWL_INTERVAL: int = int(os.getenv("FULL_CRAWL_INTERVAL", "86400"))  # 秒

    # 数据存储配置
    RAW_DATA_RETENTION_DAYS: int = int(os.getenv("RAW_DATA_RETENTION_DAYS", "30"))
    EMBEDDING_BATCH_SIZE: int = int(os.getenv("EMBEDDING_BATCH_SIZE", "100"))

    # 专利来源配置
    ENABLED_SOURCES: List[str] = os.getenv("ENABLED_SOURCES", "cnipa,uspto,epo,wipo,lens").split(",")

    # 质量阈值
    MIN_EMBEDDING_CONFIDENCE: float = float(os.getenv("MIN_EMBEDDING_CONFIDENCE", "0.8"))
    MIN_CRAWLER_SUCCESS_RATE: float = float(os.getenv("MIN_CRAWLER_SUCCESS_RATE", "0.95"))

    class Config:
        env_file = ".env"
        case_sensitive = True

# 专利分类配置
IPC_CLASSIFICATIONS = {
    "A": "人类生活必需",
    "B": "作业、运输",
    "C": "化学、冶金",
    "D": "纺织、造纸",
    "E": "固定建筑物",
    "F": "机械工程、照明、加热、武器",
    "G": "物理",
    "H": "电学"
}

# 专利类型映射
PATENT_TYPES = {
    "invention": "发明专利",
    "utility": "实用新型专利",
    "design": "外观设计专利"
}

# USPTO专利类型映射
USPTO_PATENT_TYPES = {
    "utility": "实用专利",
    "design": "设计专利",
    "plant": "植物专利",
    "reissue": "再公告专利"
}

# 爬虫User-Agent列表
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/122.0",
]

# 导出配置
config = CrawlerConfig()
