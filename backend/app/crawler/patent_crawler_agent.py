"""专利爬虫Agent实现"""
import asyncio
import json
import re
import time
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
import logging
from urllib.parse import urljoin
import httpx
from bs4 import BeautifulSoup

from .base_crawler import BasePatentCrawler, AntiCrawlerMixin, IncrementalCapableMixin
from .models import PatentDocument, PatentStatus
from .config import config
from .utils import ContentValidator
from app.ai.patent_database_api import patent_aggregator

logger = logging.getLogger(__name__)


class CNIPACrawler(BasePatentCrawler, AntiCrawlerMixin, IncrementalCapableMixin):
    """中国国家知识产权局爬虫

    CNIPA官网: https://pss-system.cnipa.gov.cn
    注意：由于反爬严格，建议使用官方API或商业服务
    """

    BASE_URL = "https://pss-system.cnipa.gov.cn"
    SEARCH_URL = f"{BASE_URL}/search/taishou"
    DETAIL_URL = f"{BASE_URL}/search/detail"

    def __init__(self):
        super().__init__("cnipa")
        super(BasePatentCrawler, self).__init__()

    async def search_patents(
            self,
            query: str,
            max_results: int = 100,
            patent_type: Optional[str] = None,
            date_from: Optional[datetime] = None,
            date_to: Optional[datetime] = None,
            **kwargs
    ) -> List[PatentDocument]:
        """搜索中国专利"""
        patents = []

        try:
            # 使用聚合器的API（如果有配置）
            if patent_aggregator.databases.get("cnipa"):
                results = await patent_aggregator.search_all(
                    query,
                    sources=["cnipa"],
                    max_results_per_source=max_results
                )
                return results.get("cnipa", [])

            # 网页爬取方式（仅供参考，实际使用需要处理反爬）
            logger.warning("CNIPA反爬严格，建议使用官方API或商业服务")

            # 构建搜索参数
            params = {
                "search_condition": json.dumps({
                    "searchExp": query,
                    "searchType": "申请号,公开号,申请人,发明人,专利代理机构,代理人,发明名称,摘要,权利要求,说明书"
                }),
                "pageNum": 1,
                "pageSize": min(max_results, 50)
            }

            if patent_type:
                params["patent_type"] = patent_type

            # 执行搜索
            response = await self.make_request("GET", self.SEARCH_URL, params=params)

            if response and response.status_code == 200:
                data = response.json()
                items = data.get("data", {}).get("items", [])

                for item in items[:max_results]:
                    patent = await self._parse_search_item(item)
                    if patent and await self.validate_patent(patent):
                        patents.append(patent)

                logger.info(f"CNIPA搜索完成：找到 {len(patents)} 条专利")

        except Exception as e:
            logger.error(f"CNIPA搜索失败: {e}")

        return patents

    async def get_patent_detail(
            self,
            patent_number: str,
            **kwargs
    ) -> Optional[PatentDocument]:
        """获取专利详情"""
        try:
            # 检查缓存
            cached = await self.load_html_cache(patent_number)
            if cached:
                return await self._parse_detail_html(cached, patent_number)

            # 获取详情页
            params = {"patentNumber": patent_number}
            response = await self.make_request("GET", self.DETAIL_URL, params=params)

            if response and response.status_code == 200:
                # 保存缓存
                await self.save_html_cache(patent_number, response.text)
                return await self._parse_detail_html(response.text, patent_number)

        except Exception as e:
            logger.error(f"获取CNIPA专利详情失败 {patent_number}: {e}")

        return None

    async def get_incremental_updates(
            self,
            since: datetime,
            **kwargs
    ) -> List[PatentDocument]:
        """获取增量更新"""
        patents = []

        try:
            # 按公开日期范围搜索
            query = f"公开日: {since.strftime('%Y%m%d')}-"
            results = await self.search_patents(query, **kwargs)

            # 过滤日期
            for patent in results:
                if patent.publication_date and patent.publication_date >= since:
                    patents.append(patent)

            logger.info(f"CNIPA增量更新：{len(patents)} 条新专利")

        except Exception as e:
            logger.error(f"CNIPA增量更新失败: {e}")

        return patents

    async def _parse_search_item(self, item: Dict[str, Any]) -> Optional[PatentDocument]:
        """解析搜索项"""
        try:
            return PatentDocument(
                application_number=item.get("applicationNumber"),
                publication_number=item.get("publicationNumber"),
                title=item.get("title"),
                abstract=item.get("abstract"),
                applicant=item.get("applicant"),
                inventor=item.get("inventor"),
                application_date=self._parse_date(item.get("applicationDate")),
                publication_date=self._parse_date(item.get("publicationDate")),
                ipc_classification=item.get("ipcClassification"),
                patent_type=self._convert_patent_type(item.get("patentType")),
                source=self.source_name,
                url=f"{self.BASE_URL}/search/detail/{item.get('publicationNumber')}"
            )
        except Exception as e:
            logger.error(f"解析CNIPA搜索项失败: {e}")
            return None

    async def _parse_detail_html(self, html: str, patent_number: str) -> Optional[PatentDocument]:
        """解析详情页HTML"""
        try:
            soup = await self.parse_html(html)

            # 提取基本信息
            title_elem = soup.select_one(".title, h1")
            title = title_elem.get_text(strip=True) if title_elem else ""

            abstract_elem = soup.select_one(".abstract, .summary")
            abstract = abstract_elem.get_text(strip=True) if abstract_elem else ""

            # 提取权利要求
            claims_elem = soup.select_one(".claims")
            claims = claims_elem.get_text(strip=True) if claims_elem else ""

            # 提取说明书
            description_elem = soup.select_one(".description")
            description = description_elem.get_text(strip=True) if description_elem else ""

            return PatentDocument(
                publication_number=patent_number,
                title=title,
                abstract=abstract,
                claims=claims,
                description=description,
                source=self.source_name,
                url=f"{self.DETAIL_URL}/{patent_number}"
            )
        except Exception as e:
            logger.error(f"解析CNIPA详情页失败 {patent_number}: {e}")
            return None

    def _parse_date(self, date_str: Optional[str]) -> Optional[datetime]:
        """解析日期"""
        if not date_str:
            return None

        try:
            # 支持多种格式
            patterns = ["%Y%m%d", "%Y-%m-%d", "%Y/%m/%d"]
            for pattern in patterns:
                try:
                    return datetime.strptime(date_str, pattern)
                except:
                    continue
        except Exception as e:
            logger.error(f"日期解析失败 {date_str}: {e}")

        return None

    def _convert_patent_type(self, type_str: Optional[str]) -> str:
        """转换专利类型"""
        type_map = {
            "发明": "invention",
            "实用新型": "utility",
            "外观设计": "design"
        }
        return type_map.get(type_str, "unknown")


class USPTOCrawler(BasePatentCrawler, IncrementalCapableMixin):
    """美国专利商标局爬虫

    USPTO PatentsView API: https://search.patentsview.org
    """

    API_BASE = "https://search.patentsview.org/api/v1"

    def __init__(self):
        super().__init__("uspto")
        super(BasePatentCrawler, self).__init__()
        self.api_key = os.getenv("USPTO_API_KEY", "")

    async def search_patents(
            self,
            query: str,
            max_results: int = 100,
            patent_type: Optional[str] = None,
            date_from: Optional[datetime] = None,
            date_to: Optional[datetime] = None,
            **kwargs
    ) -> List[PatentDocument]:
        """搜索美国专利"""
        patents = []

        try:
            # 使用聚合器的USPTO API
            if patent_aggregator.databases.get("uspto"):
                results = await patent_aggregator.search_all(
                    query,
                    sources=["uspto"],
                    max_results_per_source=max_results
                )
                return results.get("uspto", [])

            # 构建查询
            search_query = {
                "patent_title": query
            }

            # 添加日期过滤
            if date_from or date_to:
                date_filter = {}
                if date_from:
                    date_filter["gte"] = date_from.strftime("%Y-%m-%d")
                if date_to:
                    date_filter["lte"] = date_to.strftime("%Y-%m-%d")
                search_query["patent_date"] = date_filter

            # 发送请求
            response = await self._make_api_request("/patents", {
                "q": json.dumps(search_query),
                "f": json.dumps([
                    "patent_id", "patent_title", "patent_date", "patent_type",
                    "patent_abstract", "filing_date", "application_id"
                ]),
                "o": json.dumps({"per_page": min(max_results, 100)})
            })

            if response and response.status_code == 200:
                data = response.json()
                patent_list = data.get("patents", [])

                for patent_data in patent_list[:max_results]:
                    patent = await self._parse_patent_data(patent_data)
                    if patent and await self.validate_patent(patent):
                        patents.append(patent)

                logger.info(f"USPTO搜索完成：找到 {len(patents)} 条专利")

        except Exception as e:
            logger.error(f"USPTO搜索失败: {e}")

        return patents

    async def get_patent_detail(
            self,
            patent_number: str,
            include_family: bool = False,
            include_citations: bool = False,
            **kwargs
    ) -> Optional[PatentDocument]:
        """获取专利详情"""
        try:
            # 获取基本信息
            response = await self._make_api_request("/patents", {
                "q": json.dumps({"patent_id": patent_number}),
                "f": json.dumps([
                    "patent_id", "patent_title", "patent_date", "patent_type",
                    "patent_abstract", "filing_date", "application_id",
                    "inventors", "assignees", "cpcs", "ipcs"
                ])
            })

            if not response or response.status_code != 200:
                return None

            data = response.json()
            patents = data.get("patents", [])

            if not patents:
                return None

            patent = await self._parse_patent_data(patents[0])

            if not patent:
                return None

            # 获取额外信息
            if include_family:
                patent.raw_data["family"] = await self._get_patent_family(patent_number)

            if include_citations:
                patent.raw_data["citations"] = await self._get_patent_citations(patent_number)

            return patent

        except Exception as e:
            logger.error(f"获取USPTO专利详情失败 {patent_number}: {e}")

        return None

    async def get_incremental_updates(
            self,
            since: datetime,
            **kwargs
    ) -> List[PatentDocument]:
        """获取增量更新"""
        patents = []

        try:
            # 按申请日期搜索
            search_query = {
                "filing_date": {
                    "gte": since.strftime("%Y-%m-%d")
                }
            }

            response = await self._make_api_request("/patents", {
                "q": json.dumps(search_query),
                "f": json.dumps(["patent_id", "patent_title", "filing_date"]),
                "o": json.dumps({"per_page": 1000})
            })

            if response and response.status_code == 200:
                data = response.json()
                patent_list = data.get("patents", [])

                for patent_data in patent_list:
                    patent = await self.get_patent_detail(
                        patent_data.get("patent_id"),
                        **kwargs
                    )
                    if patent:
                        patents.append(patent)

                logger.info(f"USPTO增量更新：{len(patents)} 条新专利")

        except Exception as e:
            logger.error(f"USPTO增量更新失败: {e}")

        return patents

    async def _make_api_request(self, endpoint: str, params: Dict[str, Any]) -> Optional[httpx.Response]:
        """发送API请求"""
        url = f"{self.API_BASE}{endpoint}"

        headers = {}
        if self.api_key:
            headers["X-Api-Key"] = self.api_key

        return await self.make_request("GET", url, params=params, headers=headers)

    async def _parse_patent_data(self, data: Dict[str, Any]) -> Optional[PatentDocument]:
        """解析专利数据"""
        try:
            patent_data = data.get("patent", {}) if isinstance(data, dict) else data

            # 提取发明人
            inventors = patent_data.get("inventors", [])
            inventor_names = []
            for inv in inventors:
                inv_data = inv.get("inventor", {}) if isinstance(inv, dict) else inv
                name = f"{inv_data.get('inventor_first_name', '')} {inv_data.get('inventor_last_name', '')}".strip()
                if name:
                    inventor_names.append(name)

            # 提取受让人
            assignees = patent_data.get("assignees", [])
            assignee_names = []
            for a in assignees:
                assignee_data = a.get("assignee", {}) if isinstance(a, dict) else a
                org = assignee_data.get("assignee_organization")
                if org:
                    assignee_names.append(org)

            # 提取CPC分类
            cpcs = patent_data.get("cpcs", [])
            cpc_ids = []
            for c in cpcs:
                cpc_data = c.get("cpc_group", {}) if isinstance(c, dict) else c
                cid = cpc_data.get("cpc_group_id")
                if cid:
                    cpc_ids.append(cid)

            # 提取IPC分类
            ipcs = patent_data.get("ipcs", [])
            ipc_ids = []
            for i in ipcs:
                ipc_data = i.get("ipc_main_group", {}) if isinstance(i, dict) else i
                iid = ipc_data.get("ipc_class_id")
                if iid:
                    ipc_ids.append(iid)

            return PatentDocument(
                application_number=patent_data.get("application_id"),
                publication_number=patent_data.get("patent_id"),
                title=patent_data.get("patent_title"),
                abstract=patent_data.get("patent_abstract"),
                patent_type=patent_data.get("patent_type"),
                application_date=self._parse_date(patent_data.get("filing_date")),
                publication_date=self._parse_date(patent_data.get("patent_date")),
                source=self.source_name,
                url=f"https://patents.google.com/patent/US{patent_data.get('patent_id')}",
                inventor=", ".join(inventor_names),
                assignee=", ".join(assignee_names),
                cpc_classification=";".join(cpc_ids[:5]) if cpc_ids else None,
                ipc_classification=";".join(ipc_ids[:5]) if ipc_ids else None,
                raw_data=patent_data
            )
        except Exception as e:
            logger.error(f"解析USPTO专利数据失败: {e}")
            return None

    async def _get_patent_family(self, patent_number: str) -> List[Dict[str, Any]]:
        """获取专利家族"""
        try:
            response = await self._make_api_request("/family", {
                "q": json.dumps({"patent_id": patent_number}),
                "f": json.dumps(["patent_id", "family_id", "patent_title"])
            })

            if response and response.status_code == 200:
                data = response.json()
                return data.get("families", [])

        except Exception as e:
            logger.error(f"获取专利家族失败 {patent_number}: {e}")

        return []

    async def _get_patent_citations(self, patent_number: str) -> List[Dict[str, str]]:
        """获取专利引用"""
        try:
            response = await self._make_api_request("/us_patent_citation", {
                "q": json.dumps({"patent_id": patent_number}),
                "f": json.dumps(["citation_id", "citation_date", "citation_type"])
            })

            if response and response.status_code == 200:
                data = response.json()
                citations = data.get("us_patent_citations", [])
                return [
                    {
                        "patent_id": c.get("citation_id"),
                        "date": c.get("citation_date"),
                        "type": c.get("citation_type")
                    }
                    for c in citations
                ]

        except Exception as e:
            logger.error(f"获取专利引用失败 {patent_number}: {e}")

        return []

    def _parse_date(self, date_str: Optional[str]) -> Optional[datetime]:
        """解析日期"""
        if not date_str:
            return None

        try:
            # ISO格式
            if "T" in date_str:
                return datetime.fromisoformat(date_str.replace("Z", "+00:00"))

            # 其他格式
            patterns = ["%Y-%m-%d", "%Y%m%d"]
            for pattern in patterns:
                try:
                    return datetime.strptime(date_str[:10], pattern)
                except:
                    continue
        except Exception as e:
            logger.error(f"日期解析失败 {date_str}: {e}")

        return None


class EPOCrawler(BasePatentCrawler, IncrementalCapableMixin):
    """欧洲专利局爬虫

    EPO OPS API: https://ops.epo.org
    """

    API_BASE = "https://ops.epo.org/3.2"

    def __init__(self):
        super().__init__("epo")
        super(BasePatentCrawler, self).__init__()
        self.consumer_key = os.getenv("EPO_CONSUMER_KEY", "")
        self.consumer_secret = os.getenv("EPO_CONSUMER_SECRET", "")
        self.access_token = None
        self.token_expires = 0

    async def _get_access_token(self) -> Optional[str]:
        """获取OAuth访问令牌"""
        # 实现OAuth认证逻辑
        # EPO OPS API需要OAuth 2.0认证
        logger.warning("EPO OPS API需要OAuth认证，请先配置consumer key和secret")
        return None

    async def search_patents(
            self,
            query: str,
            max_results: int = 100,
            **kwargs
    ) -> List[PatentDocument]:
        """搜索欧洲专利"""
        patents = []

        try:
            # 使用聚合器的EPO API
            if patent_aggregator.databases.get("epo"):
                results = await patent_aggregator.search_all(
                    query,
                    sources=["epo"],
                    max_results_per_source=max_results
                )
                return results.get("epo", [])

            # 实现EPO搜索逻辑
            # 注意：EPO OPS API使用CQL查询语言
            logger.info("EPO搜索功能需要OAuth认证")

        except Exception as e:
            logger.error(f"EPO搜索失败: {e}")

        return patents

    async def get_patent_detail(
            self,
            patent_number: str,
            **kwargs
    ) -> Optional[PatentDocument]:
        """获取专利详情"""
        try:
            # 实现EPO详情获取逻辑
            pass
        except Exception as e:
            logger.error(f"获取EPO专利详情失败 {patent_number}: {e}")

        return None

    async def get_incremental_updates(
            self,
            since: datetime,
            **kwargs
    ) -> List[PatentDocument]:
        """获取增量更新"""
        return []


class WIPOCrawler(BasePatentCrawler, IncrementalCapableMixin):
    """WIPO专利爬虫

    WIPO PATENTSCOPE: https://patentscope.wipo.int
    """

    BASE_URL = "https://patentscope.wipo.int"
    SEARCH_API = f"{BASE_URL}/search/en/result.jsf"

    def __init__(self):
        super().__init__("wipo")
        super(BasePatentCrawler, self).__init__()

    async def search_patents(
            self,
            query: str,
            max_results: int = 100,
            **kwargs
    ) -> List[PatentDocument]:
        """搜索国际专利"""
        patents = []

        try:
            # 使用聚合器的WIPO API
            if patent_aggregator.databases.get("wipo"):
                results = await patent_aggregator.search_all(
                    query,
                    sources=["wipo"],
                    max_results_per_source=max_results
                )
                return results.get("wipo", [])

            # 实现WIPO搜索逻辑
            logger.info("WIPO搜索功能需要实现PATENTSCOPE API集成")

        except Exception as e:
            logger.error(f"WIPO搜索失败: {e}")

        return patents

    async def get_patent_detail(
            self,
            patent_number: str,
            **kwargs
    ) -> Optional[PatentDocument]:
        """获取专利详情"""
        try:
            # 实现WIPO详情获取逻辑
            pass
        except Exception as e:
            logger.error(f"获取WIPO专利详情失败 {patent_number}: {e}")

        return None

    async def get_incremental_updates(
            self,
            since: datetime,
            **kwargs
    ) -> List[PatentDocument]:
        """获取增量更新"""
        return []


# 爬虫工厂
class CrawlerFactory:
    """爬虫工厂类"""

    _crawlers = {
        "cnipa": CNIPACrawler,
        "uspto": USPTOCrawler,
        "epo": EPOCrawler,
        "wipo": WIPOCrawler,
    }

    @classmethod
    def get_crawler(cls, source: str) -> Optional[BasePatentCrawler]:
        """
        获取爬虫实例

        Args:
            source: 数据来源

        Returns:
            爬虫实例
        """
        crawler_class = cls._crawlers.get(source.lower())
        if crawler_class:
            return crawler_class()
        return None

    @classmethod
    def list_available_sources(cls) -> List[str]:
        """列出可用数据来源"""
        return list(cls._crawlers.keys())

    @classmethod
    def register_crawler(cls, source: str, crawler_class: type):
        """注册新爬虫"""
        cls._crawlers[source.lower()] = crawler_class


# 代理映射（兼容现有的patent_aggregator）
crawler_factory = CrawlerFactory

# 代理映射（兼容现有的patent_aggregator）
crawler_factory = CrawlerFactory


if __name__ == "__main__":
    """爬虫Agent入口点"""
    import signal
    import sys
    
    logger.info("启动专利爬虫Agent...")
    
    def signal_handler(sig, frame):
        logger.info("收到停止信号，正在退出...")
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # 初始化爬虫工厂
    factory = CrawlerFactory()
    logger.info(f"可用爬虫: {factory.list_available_sources()}")
    
    # 保持运行
    logger.info("专利爬虫Agent已启动，等待任务...")
    while True:
        import time
        time.sleep(60)