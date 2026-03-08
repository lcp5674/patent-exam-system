"""  
公开专利数据库API服务 - 增强版  
支持: 中国(CNIPA/大为/佰腾/SooPAT), USPTO, EPO, WIPO  
"""
import httpx
import asyncio
import os
import json
import time
import random
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field
from abc import ABC, abstractmethod
import logging
from bs4 import BeautifulSoup
import re

logger = logging.getLogger(__name__)


class RateLimiter:
    """简单的速率限制器"""
    def __init__(self, min_interval: float = 1.0):
        self.min_interval = min_interval
        self.last_request_time = 0
        self.lock = asyncio.Lock()
    
    async def acquire(self):
        async with self.lock:
            now = time.time()
            elapsed = now - self.last_request_time
            if elapsed < self.min_interval:
                wait_time = self.min_interval - elapsed + random.uniform(0.1, 0.5)
                await asyncio.sleep(wait_time)
            self.last_request_time = time.time()
    
    async def __aenter__(self):
        await self.acquire()
        return self
    
    async def __aexit__(self, *args):
        pass


@dataclass
class PatentDocument:
    """专利文献数据结构"""
    application_number: Optional[str] = None
    publication_number: Optional[str] = None
    title: Optional[str] = None
    abstract: Optional[str] = None
    applicant: Optional[str] = None
    inventor: Optional[str] = None
    application_date: Optional[str] = None
    publication_date: Optional[str] = None
    ipc_classification: Optional[str] = None
    cpc_classification: Optional[str] = None
    patent_type: Optional[str] = None  # invention / utility / design
    source: str = "unknown"
    url: Optional[str] = None
    claims: Optional[str] = None
    description: Optional[str] = None
    assignee: Optional[str] = None
    agent: Optional[str] = None
    priority_number: Optional[str] = None
    family_id: Optional[str] = None
    raw_data: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "application_number": self.application_number,
            "publication_number": self.publication_number,
            "title": self.title,
            "abstract": self.abstract,
            "applicant": self.applicant,
            "inventor": self.inventor,
            "application_date": self.application_date,
            "publication_date": self.publication_date,
            "ipc_classification": self.ipc_classification,
            "cpc_classification": self.cpc_classification,
            "patent_type": self.patent_type,
            "source": self.source,
            "url": self.url,
            "assignee": self.assignee,
            "agent": self.agent,
        }


class PatentDatabaseAPI(ABC):
    """专利数据库API抽象基类"""
    
    @property
    @abstractmethod
    def name(self) -> str:
        pass
    
    @property
    def is_available(self) -> bool:
        return True
    
    @abstractmethod
    async def search(self, query: str, max_results: int = 10, **kwargs) -> List[PatentDocument]:
        pass
    
    @abstractmethod
    async def get_patent(self, patent_number: str) -> Optional[PatentDocument]:
        pass
    
    async def close(self):
        """关闭连接"""
        pass


class DaWeiPatentAPI(PatentDatabaseAPI):
    """大为专利数据库API (中国)
    
    需要商业API密钥: https://www.innojoy.com
    """
    
    def __init__(self, api_key: Optional[str] = None):
        self.base_url = "https://api.daweiip.com/v1"
        self.api_key = api_key or os.getenv("DAWEI_API_KEY", "")
        self._client: Optional[httpx.AsyncClient] = None
    
    @property
    def name(self) -> str:
        return "dawei"
    
    @property
    def is_available(self) -> bool:
        return bool(self.api_key)
    
    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(base_url=self.base_url, timeout=30.0)
        return self._client
    
    async def search(self, query: str, max_results: int = 10, **kwargs) -> List[PatentDocument]:
        results = []
        if not self.api_key:
            logger.warning("大为API未配置API密钥")
            return results
        
        try:
            client = await self._get_client()
            headers = {"Authorization": f"Bearer {self.api_key}"}
            
            response = await client.get(
                "/patent/search",
                params={"search": query, "pageSize": max_results},
                headers=headers
            )
            
            if response.status_code == 200:
                data = response.json()
                patents = data.get("data", [])
                for p in patents:
                    doc = self._parse_patent(p)
                    if doc:
                        results.append(doc)
            
            logger.info(f"大为搜索返回 {len(results)} 条")
        except Exception as e:
            logger.error(f"大为搜索失败: {e}")
        
        return results
    
    def _parse_patent(self, data: Dict[str, Any]) -> Optional[PatentDocument]:
        try:
            return PatentDocument(
                application_number=data.get("app_number"),
                publication_number=data.get("pub_number"),
                title=data.get("title"),
                abstract=data.get("abstract"),
                applicant=data.get("applicant"),
                inventor=data.get("inventor"),
                application_date=data.get("app_date"),
                publication_date=data.get("pub_date"),
                ipc_classification=data.get("ipc"),
                cpc_classification=data.get("cpc"),
                patent_type=self._convert_type(data.get("patent_type")),
                source=self.name,
                url=f"https://www.innojoy.com/patent/{data.get('pub_number')}.html",
                assignee=data.get("assignee"),
                agent=data.get("agent"),
                raw_data=data
            )
        except Exception as e:
            logger.error(f"解析专利失败: {e}")
            return None
    
    def _convert_type(self, ptype: Optional[str]) -> Optional[str]:
        type_map = {"发明": "invention", "实用新型": "utility", "外观设计": "design"}
        return type_map.get(ptype, ptype) if ptype else None
    
    async def get_patent(self, patent_number: str) -> Optional[PatentDocument]:
        if not self.api_key:
            return None
        results = await self.search(patent_number, max_results=1)
        return results[0] if results else None
    
    async def close(self):
        if self._client:
            await self._client.aclose()


class CNIPAOfficialAPI(PatentDatabaseAPI):
    """中国国家知识产权局(CNIPA) 专利搜索
    
    使用官网免费检索接口: https://www.cnipa.gov.cn
    注意: CNIPA网站有反爬机制，需要适当的请求间隔
    """
    
    def __init__(self, username: Optional[str] = None, password: Optional[str] = None):
        self.base_url = "https://www.cnipa.gov.cn"
        self.search_url = "https://pss-system.cnipa.gov.cn/sipopublicsearch/patentsearch/pageJsonAPP"
        self.username = username or os.getenv("CNIPA_USERNAME", "")
        self.password = password or os.getenv("CNIPA_PASSWORD", "")
        self._client: Optional[httpx.AsyncClient] = None
        self._rate_limiter = RateLimiter(min_interval=2.0)  # 反爬: 较长间隔
    
    @property
    def name(self) -> str:
        return "cnipa"
    
    @property
    def is_available(self) -> bool:
        return True  # 基础搜索无需登录
    
    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=30.0,
                follow_redirects=True,
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                    "Accept": "application/json, text/javascript, */*; q=0.01",
                    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
                    "Content-Type": "application/json",
                    "Origin": "https://www.cnipa.gov.cn",
                    "Referer": "https://www.cnipa.gov.cn/"
                }
            )
        return self._client
    
    async def search(self, query: str, max_results: int = 10, **kwargs) -> List[PatentDocument]:
        results = []
        try:
            async with self._rate_limiter:
                client = await self._get_client()
                
                # CNIPA搜索请求体
                search_data = {
                    "searchExp": query,
                    "pageSize": max_results,
                    "pageNow": 1,
                    "resultPagination": {"pageSize": max_results, "pageNow": 1},
                    "searchType": "Sino",
                    " patenttype": "",
                    "vipContent": ""
                }
                
                # 尝试使用CNIPA公开检索接口
                response = await client.post(
                    self.search_url,
                    json=search_data
                )
                
                if response.status_code == 200:
                    data = response.json()
                    patents = data.get("result", {}).get("searchResult", {}).get("patent", [])
                    
                    for p in patents:
                        doc = self._parse_patent(p)
                        if doc:
                            results.append(doc)
                    
                    logger.info(f"CNIPA搜索返回 {len(results)} 条结果")
                else:
                    # 如果API失败，尝试备用方法 - 抓取搜索页面
                    results = await self._search_fallback(query, max_results)
                    
        except httpx.HTTPStatusError as e:
            logger.warning(f"CNIPA API返回错误: {e.response.status_code}, 尝试备用方法")
            results = await self._search_fallback(query, max_results)
        except Exception as e:
            logger.error(f"CNIPA搜索失败: {e}")
            results = await self._search_fallback(query, max_results)
        
        return results
    
    async def _search_fallback(self, query: str, max_results: int) -> List[PatentDocument]:
        """备用搜索方法 - 使用网页抓取"""
        results = []
        try:
            client = await self._get_client()
            
            # 尝试访问CNIPA专利检索入口页面
            search_page_url = f"{self.base_url}/col/col151/index.html"
            response = await client.get(search_page_url)
            
            if response.status_code == 200:
                # 解析页面获取搜索表单
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # 构建搜索URL - CNIPA新版检索系统
                # 这里使用大为专利网的免费接口作为备用
                dawei_url = "https://www.dawei.io/api/patent/search"
                try:
                    async with self._rate_limiter:
                        resp = await client.get(
                            "https://www.dawei.io/openapi",
                            params={"keyword": query, "page": 1, "size": max_results},
                            timeout=15.0
                        )
                        if resp.status_code == 200:
                            data = resp.json()
                            patents = data.get("data", {}).get("list", [])
                            for p in patents:
                                doc = self._parse_patent(p)
                                if doc:
                                    results.append(doc)
                except Exception as e:
                    logger.debug(f"备用搜索失败: {e}")
                    
        except Exception as e:
            logger.error(f"CNIPA备用搜索失败: {e}")
            
        return results
    
    def _parse_patent(self, data: Dict[str, Any]) -> Optional[PatentDocument]:
        """解析CNIPA专利数据"""
        try:
            # 处理嵌套的数据结构
            if isinstance(data, dict):
                # 尝试多种可能的字段路径
                app_number = data.get("appNumber") or data.get("application_number") or \
                            data.get("APP_NUMBER") or data.get("applicantSn")
                pub_number = data.get("pubNumber") or data.get("publication_number") or \
                            data.get("PUB_NUMBER") or data.get("patentNo")
                title = data.get("title") or data.get("title") or data.get("TITLE") or \
                       data.get("patentName") or data.get("inventName")
                abstract = data.get("abstract") or data.get("abstract") or data.get("ABSTRACT")
                applicant = data.get("applicant") or data.get("applicants") or data.get("applicantName")
                inventor = data.get("inventor") or data.get("inventors") or data.get("inventorName")
                app_date = data.get("applicationDate") or data.get("application_date") or data.get("APP_DATE")
                pub_date = data.get("publicationDate") or data.get("publication_date") or data.get("PUB_DATE")
                ipc = data.get("ipc") or data.get("ipcMainClassification") or data.get("IPC")
                ptype = data.get("patentType") or data.get("patent_type") or data.get("type")
                
                return PatentDocument(
                    application_number=app_number,
                    publication_number=pub_number,
                    title=title,
                    abstract=abstract,
                    applicant=applicant,
                    inventor=inventor,
                    application_date=app_date,
                    publication_date=pub_date,
                    ipc_classification=ipc,
                    patent_type=self._convert_type(ptype),
                    source=self.name,
                    url=f"https://www.cnipa.gov.cn/patents/{pub_number}" if pub_number else None,
                    raw_data=data
                )
        except Exception as e:
            logger.debug(f"解析CNIPA专利失败: {e}")
            return None
    
    def _convert_type(self, ptype: Optional[str]) -> Optional[str]:
        """转换专利类型"""
        if not ptype:
            return None
        type_map = {
            "发明专利": "invention",
            "发明": "invention",
            "实用新型": "utility",
            "实用新型专利": "utility",
            "外观设计": "design",
            "外观设计专利": "design"
        }
        return type_map.get(ptype, ptype)
    
    async def get_patent(self, patent_number: str) -> Optional[PatentDocument]:
        """获取CNIPA专利详情"""
        results = await self.search(patent_number, max_results=1)
        return results[0] if results else None
    
    async def close(self):
        if self._client:
            await self._client.aclose()


class USPATentAPI(PatentDatabaseAPI):
    """USPTO PatentsView API (美国)
    
    免费公开API: https://search.patentsview.org
    支持搜索、获取详情、引用信息等
    """
    
    def __init__(self, api_key: Optional[str] = None):
        # 使用v1 API (更稳定)
        self.base_url = "https://search.patentsview.org/api/v1"
        self.api_key = api_key or os.getenv("USPTO_PV_API_KEY", "")
        self._client: Optional[httpx.AsyncClient] = None
    
    @property
    def name(self) -> str:
        return "uspto"
    
    @property
    def is_available(self) -> bool:
        return True
    
    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Accept": "application/json"
            }
            if self.api_key:
                headers["X-Api-Key"] = self.api_key
            self._client = httpx.AsyncClient(base_url=self.base_url, headers=headers, timeout=30.0)
        return self._client
    
    async def search(
        self, 
        query: str, 
        max_results: int = 10,
        patent_type: Optional[str] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        assignee: Optional[str] = None,
        inventor: Optional[str] = None,
        cpc: Optional[str] = None,
        **kwargs
    ) -> List[PatentDocument]:
        """USPTO PatentsView搜索
        
        支持参数:
        - query: 搜索关键词
        - patent_type: 专利类型 (utility, design, plant, reissue)
        - date_from: 开始日期 (YYYY-MM-DD)
        - date_to: 结束日期 (YYYY-MM-DD)
        - assignee: 受让人/公司
        - inventor: 发明人
        - cpc: CPC分类
        """
        results = []
        try:
            client = await self._get_client()
            
            # 使用简化的查询格式
            search_term = query.replace(" ", "+")
            
            # 直接使用URL查询参数
            params = {
                "q": f"{{\"patent_title\":\"{query}\"}}",
                "f": json.dumps(["patent_id", "patent_title", "patent_date", "patent_type", "patent_abstract", "filing_date", "application_id"]),
                "o": json.dumps({"per_page": max_results})
            }
            
            response = await client.get("/patents", params=params)
            
            logger.info(f"USPTO API请求: {response.url}")
            
            if response.status_code == 200:
                data = response.json()
                patents = data.get("patents", [])
                logger.info(f"USPTO返回原始数据: {data.keys()}")
                
                for p in patents:
                    # v2 API 字段在patent对象中
                    patent_data = p.get("patent", {}) if isinstance(p, dict) else p
                    
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
                    
                    doc = PatentDocument(
                        application_number=patent_data.get("application_id"),
                        publication_number=patent_data.get("patent_id"),
                        title=patent_data.get("patent_title"),
                        abstract=patent_data.get("patent_abstract"),
                        patent_type=patent_data.get("patent_type"),
                        application_date=patent_data.get("filing_date"),
                        publication_date=patent_data.get("patent_date"),
                        source=self.name,
                        url=f"https://patents.google.com/patent/US{patent_data.get('patent_id')}",
                        inventor=", ".join(inventor_names),
                        assignee=", ".join(assignee_names),
                        cpc_classification=";".join(cpc_ids[:5]) if cpc_ids else None,
                        ipc_classification=";".join(ipc_ids[:5]) if ipc_ids else None,
                        raw_data=patent_data
                    )
                    results.append(doc)
            
            logger.info(f"USPTO搜索返回 {len(results)} 条结果")
            
        except httpx.HTTPStatusError as e:
            logger.error(f"USPTO HTTP错误: {e.response.status_code} - {e.response.text}")
        except Exception as e:
            logger.error(f"USPTO搜索失败: {e}")
        
        return results
    
    async def get_patent(self, patent_number: str) -> Optional[PatentDocument]:
        """获取USPTO专利详情"""
        results = await self.search(patent_number, max_results=1)
        return results[0] if results else None
    
    async def get_citations(self, patent_id: str) -> List[Dict[str, str]]:
        """获取专利引用信息"""
        try:
            client = await self._get_client()
            
            q = json.dumps({"patent_id": patent_id})
            f = json.dumps(["patent_id", "citation_id", "citation_date", "citation_type"])
            o = json.dumps({"per_page": 100})
            
            response = await client.get("/us_patent_citation/", params={"q": q, "f": f, "o": o})
            
            if response.status_code == 200:
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
            logger.error(f"获取引用失败: {e}")
        
        return []
    
    async def get_family(self, patent_id: str) -> List[Dict[str, Any]]:
        """获取专利家族信息"""
        try:
            client = await self._get_client()
            
            q = json.dumps({"patent_id": patent_id})
            f = json.dumps(["patent_id", "family_id", "patent_title"])
            
            response = await client.get("/family/", params={"q": q, "f": f})
            
            if response.status_code == 200:
                data = response.json()
                return data.get("families", [])
        except Exception as e:
            logger.error(f"获取专利家族失败: {e}")
        
        return []
    
    async def close(self):
        if self._client:
            await self._client.aclose()


class WIPOPatentAPI(PatentDatabaseAPI):
    """WIPO PATENTSCOPE API (国际专利)
    
    官网: https://patentscope.wipo.int
    使用PATENTSCOPE Search Service API
    """
    
    def __init__(self):
        self.base_url = "https://patentscope.wipo.int"
        self.api_url = "https://patentscope-wipo.proxy. patentsearch.io"  # 使用代理或直接访问
        self._client: Optional[httpx.AsyncClient] = None
        self._rate_limiter = RateLimiter(min_interval=2.0)
    
    @property
    def name(self) -> str:
        return "wipo"
    
    @property
    def is_available(self) -> bool:
        return True
    
    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=30.0,
                follow_redirects=True,
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                    "Accept": "application/json, text/xml",
                }
            )
        return self._client
    
    async def search(self, query: str, max_results: int = 10, **kwargs) -> List[PatentDocument]:
        results = []
        try:
            async with self._rate_limiter:
                client = await self._get_client()
                
                # WIPO PATENTSCOPE 提供多种搜索方式
                # 1. 尝试使用PATENTSCOPE的Web Service API
                search_url = f"{self.base_url}/patentscope-api/search"
                
                # 构建查询
                search_data = {
                    "query": query,
                    "num-range": max_results,
                    "start": 0,
                    "display": "essentials"
                }
                
                try:
                    # 尝试POST请求
                    response = await client.post(
                        search_url,
                        json=search_data,
                        timeout=15.0
                    )
                    
                    if response.status_code == 200:
                        data = response.json()
                        results = self._parse_results(data)
                except Exception as e:
                    logger.debug(f"WIPO API请求失败: {e}")
                    
                # 2. 如果API失败，尝试网页抓取方式
                if not results:
                    results = await self._search_web(query, max_results)
                    
                logger.info(f"WIPO搜索返回 {len(results)} 条结果")
                
        except Exception as e:
            logger.error(f"WIPO搜索失败: {e}")
            results = await self._search_web(query, max_results)
            
        return results
    
    async def _search_web(self, query: str, max_results: int) -> List[PatentDocument]:
        """网页抓取方式搜索WIPO专利"""
        results = []
        try:
            client = await self._get_client()
            
            # 使用WIPO PATENTSCOPE网页搜索
            search_url = f"{self.base_url}/patentscope/searchresult"
            params = {"query": query, "num": max_results}
            
            response = await client.get(search_url, params=params)
            
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # 解析搜索结果
                result_blocks = soup.select('div[role="row"], tr.ps-grid-row, div.result-block')
                
                for block in result_blocks[:max_results]:
                    doc = self._parse_web_result(block)
                    if doc:
                        results.append(doc)
                        
        except Exception as e:
            logger.debug(f"WIPO网页搜索失败: {e}")
            
        return results
    
    def _parse_results(self, data: Dict[str, Any]) -> List[PatentDocument]:
        """解析API返回的结果"""
        results = []
        try:
            # 处理返回的专利列表
            records = data.get("records", {}).get("record", [])
            
            if not isinstance(records, list):
                records = [records]
                
            for record in records:
                doc = self._parse_patent_record(record)
                if doc:
                    results.append(doc)
                    
        except Exception as e:
            logger.debug(f"解析WIPO结果失败: {e}")
            
        return results
    
    def _parse_web_result(self, element) -> Optional[PatentDocument]:
        """解析网页元素"""
        try:
            # 尝试提取专利号
            pub_num_elem = element.select_one('a[href*="/patent/"]')
            if not pub_num_elem:
                return None
                
            href = pub_num_elem.get('href', '')
            pub_match = re.search(r'/patent/(\d+)', href)
            pub_number = pub_match.group(1) if pub_match else None
            
            title = pub_num_elem.get_text(strip=True)
            
            return PatentDocument(
                publication_number=pub_number,
                title=title,
                source=self.name,
                url=f"{self.base_url}{href}" if href else None
            )
            
        except Exception as e:
            logger.debug(f"解析WIPO网页结果失败: {e}")
            return None
    
    def _parse_patent_record(self, record: Dict[str, Any]) -> Optional[PatentDocument]:
        """解析单条专利记录"""
        try:
            bib = record.get("bibliographicData", {})
            
            app_num = bib.get("applicationNumber")
            pub_num = bib.get("publicationNumber")
            
            title = record.get("title", {})
            title = title.get("text") if isinstance(title, dict) else title
            
            abstract = record.get("abstract", {})
            abstract = abstract.get("text") if isinstance(abstract, dict) else abstract
            
            # 提取申请人
            applicants = bib.get("parties", {}).get("applicants", {})
            app_list = applicants.get("applicant", [])
            if isinstance(app_list, dict):
                app_list = [app_list]
            applicant = "; ".join([a.get("name", "") for a in app_list[:3]])
            
            # 提取发明人
            inventors = bib.get("parties", {}).get("inventors", {})
            inv_list = inventors.get("inventor", [])
            if isinstance(inv_list, dict):
                inv_list = [inv_list]
            inventor = "; ".join([i.get("name", "") for i in inv_list[:3]])
            
            # 提取日期
            app_date = bib.get("applicationDate")
            pub_date = bib.get("publicationDate")
            
            # 提取IPC分类
            ipc = bib.get("classifications", {}).get("ipc", {})
            ipc_list = ipc.get("classification", [])
            if isinstance(ipc_list, dict):
                ipc_list = [ipc_list]
            ipc_str = "; ".join([i.get("text", "") for i in ipc_list[:5]])
            
            return PatentDocument(
                application_number=app_num,
                publication_number=pub_num,
                title=title,
                abstract=abstract,
                applicant=applicant,
                inventor=inventor,
                application_date=app_date,
                publication_date=pub_date,
                ipc_classification=ipc_str,
                source=self.name,
                url=f"{self.base_url}/patent/registry/patent/pubnumber/{pub_num}" if pub_num else None
            )
            
        except Exception as e:
            logger.debug(f"解析WIPO记录失败: {e}")
            return None
    
    async def get_patent(self, patent_number: str) -> Optional[PatentDocument]:
        """获取WIPO专利详情"""
        results = await self.search(patent_number, max_results=1)
        return results[0] if results else None
    
    async def close(self):
        if self._client:
            await self._client.aclose()


class EPOPatentAPI(PatentDatabaseAPI):
    """欧洲专利局(EPO) Open Patent Services (OPS) API + Espacenet网页抓取
    
    官网: https://www.epo.org
    文档: https://developers.epo.org/
    免费使用，需要注册获取API Key
    也可以使用Espacenet网页搜索: https://worldwide.espacenet.com
    """
    
    def __init__(self, api_key: Optional[str] = None):
        self.base_url = "https://ops.epo.org"
        self.espacenet_url = "https://worldwide.espacenet.com"
        self.api_key = api_key or os.getenv("EPO_OPS_API_KEY", "")
        self._client: Optional[httpx.AsyncClient] = None
        self._rate_limiter = RateLimiter(min_interval=2.0)
    
    @property
    def name(self) -> str:
        return "epo"
    
    @property
    def is_available(self) -> bool:
        return True
    
    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=30.0,
                follow_redirects=True,
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                    "Accept": "application/json, text/xml, text/html",
                }
            )
        return self._client
    
    async def search(
        self, 
        query: str, 
        max_results: int = 10,
        **kwargs
    ) -> List[PatentDocument]:
        """EPO OPS API搜索 + Espacenet网页搜索
        
        优先尝试使用OPS API，失败则使用Espacenet网页抓取
        """
        results = []
        
        # 首先尝试OPS API
        try:
            results = await self._search_ops(query, max_results)
        except Exception as e:
            logger.debug(f"EPO OPS API搜索失败: {e}")
        
        # 如果OPS失败，使用Espacenet网页抓取
        if not results:
            try:
                results = await self._search_espacenet(query, max_results)
            except Exception as e:
                logger.debug(f"Espacenet网页搜索失败: {e}")
        
        logger.info(f"EPO搜索返回 {len(results)} 条结果")
        return results
    
    async def _search_ops(self, query: str, max_results: int) -> List[PatentDocument]:
        """使用EPO Open Patent Services API搜索"""
        results = []
        
        try:
            client = await self._get_client()
            
            # EPO OPS API - 公开检索接口
            # 使用REST API进行专利号查询
            search_url = f"{self.base_url}/3.2/rest-services/family-search"
            
            params = {
                "q": query,
                "Range": f"1-{max_results}"
            }
            
            if self.api_key:
                params["apikey"] = self.api_key
            
            response = await client.get(search_url, params=params)
            
            if response.status_code == 200:
                # 解析XML响应
                try:
                    from xml.etree import ElementTree
                    root = ElementTree.fromstring(response.text)
                    
                    # 提取专利文献
                    for doc in root.findall(".//"):
                        doc_data = {}
                        for child in doc:
                            doc_data[child.tag] = child.text
                        
                        if doc_data:
                            patent = self._parse_ops_result(doc_data)
                            if patent:
                                results.append(patent)
                                
                except Exception as e:
                    logger.debug(f"解析EPO XML失败: {e}")
                    
        except Exception as e:
            logger.debug(f"EPO OPS搜索失败: {e}")
            
        return results
    
    async def _search_espacenet(self, query: str, max_results: int) -> List[PatentDocument]:
        """使用Espacenet网页抓取搜索"""
        results = []
        
        try:
            async with self._rate_limiter:
                client = await self._get_client()
                
                # Espacenet搜索URL
                search_url = f"{self.espacenet_url}/patent/search"
                params = {
                    "query": query,
                    "num": max_results,
                    "facet": "off"
                }
                
                response = await client.get(search_url, params=params)
                
                if response.status_code == 200:
                    soup = BeautifulSoup(response.text, 'html.parser')
                    
                    # 解析搜索结果
                    result_tables = soup.select('table.resultsTable, div.result-item, tr[data-doc-id]')
                    
                    for item in result_tables[:max_results]:
                        doc = self._parse_espacenet_item(item)
                        if doc:
                            results.append(doc)
                            
                    # 备用解析方式
                    if not results:
                        links = soup.select('a[href*="/patent/publication/"]')
                        for link in links[:max_results]:
                            try:
                                href = link.get('href', '')
                                pub_match = re.search(r'publication/(\w+)', href)
                                pub_number = pub_match.group(1) if pub_match else None
                                
                                if pub_number and link.get_text(strip=True):
                                    results.append(PatentDocument(
                                        publication_number=pub_number,
                                        title=link.get_text(strip=True),
                                        source=self.name,
                                        url=f"{self.espacenet_url}{href}"
                                    ))
                            except Exception:
                                continue
                                
        except Exception as e:
            logger.debug(f"Espacenet抓取失败: {e}")
            
        return results
    
    def _parse_ops_result(self, data: Dict[str, Any]) -> Optional[PatentDocument]:
        """解析OPS API返回的结果"""
        try:
            pub_number = data.get("publicationNumber") or data.get("publication-number")
            app_number = data.get("applicationNumber") or data.get("application-number")
            title = data.get("title") or data.get("title")
            
            if not pub_number:
                return None
                
            return PatentDocument(
                application_number=app_number,
                publication_number=pub_number,
                title=title,
                source=self.name,
                url=f"{self.espacenet_url}/patent/publication/{pub_number}"
            )
            
        except Exception as e:
            logger.debug(f"解析OPS结果失败: {e}")
            return None
    
    def _parse_espacenet_item(self, element) -> Optional[PatentDocument]:
        """解析Espacenet网页元素"""
        try:
            # 尝试提取专利号和标题
            link = element.select_one('a[href*="/patent/publication/"]')
            if not link:
                return None
                
            href = link.get('href', '')
            pub_match = re.search(r'publication/(\w+)', href)
            pub_number = pub_match.group(1) if pub_match else None
            
            title = link.get_text(strip=True)
            
            # 尝试提取更多信息
            applicant = None
            applicant_elem = element.select_one('td.applicant, span.applicantName, div.applicant')
            if applicant_elem:
                applicant = applicant_elem.get_text(strip=True)
            
            return PatentDocument(
                publication_number=pub_number,
                title=title,
                applicant=applicant,
                source=self.name,
                url=f"{self.espacenet_url}{href}" if href else None
            )
            
        except Exception as e:
            logger.debug(f"解析Espacenet元素失败: {e}")
            return None
    
    async def get_patent(self, patent_number: str) -> Optional[PatentDocument]:
        """获取EPO专利详情"""
        results = await self.search(patent_number, max_results=1)
        return results[0] if results else None
    
    async def close(self):
        if self._client:
            await self._client.aclose()


class GooglePatentsFreeAPI(PatentDatabaseAPI):
    """Google Patents 搜索 (通过网页抓取)
    
    这是一个免费的方式获取专利信息
    注意: 不建议大规模使用，应遵守Google服务条款
    """
    
    def __init__(self):
        self.base_url = "https://patents.google.com"
        self._client: Optional[httpx.AsyncClient] = None
    
    @property
    def name(self) -> str:
        return "google"
    
    @property
    def is_available(self) -> bool:
        return True
    
    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=30.0,
                follow_redirects=True,
                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
            )
        return self._client
    
    async def search(
        self, 
        query: str, 
        max_results: int = 10,
        **kwargs
    ) -> List[PatentDocument]:
        """Google Patents搜索
        
        注意: 这是通过网页解析实现，可能不稳定
        建议使用商业API如Lens.org
        """
        results = []
        try:
            client = await self._get_client()
            
            # Google Patents搜索URL
            search_url = f"{self.base_url}/search"
            params = {"q": query, "num": min(max_results, 10)}
            
            # 实际生产应该使用官方API
            logger.info(f"Google Patents搜索: {query} (需要官方API)")
            
        except Exception as e:
            logger.error(f"Google Patents搜索失败: {e}")
        
        return results
    
    async def get_patent(self, patent_number: str) -> Optional[PatentDocument]:
        """获取专利详情"""
        return None
    
    async def close(self):
        if self._client:
            await self._client.aclose()


class LensOrgAPI(PatentDatabaseAPI):
    """The Lens API (全球专利)
    
    官网: https://www.lens.org
    提供免费和付费计划
    需要注册获取API Key
    """
    
    def __init__(self, api_key: Optional[str] = None):
        self.base_url = "https://api.lens.org"
        self.api_key = api_key or os.getenv("LENS_API_KEY", "")
        self._client: Optional[httpx.AsyncClient] = None
    
    @property
    def name(self) -> str:
        return "lens"
    
    @property
    def is_available(self) -> bool:
        return bool(self.api_key)
    
    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            headers = {}
            if self.api_key:
                headers["Authorization"] = f"Bearer {self.api_key}"
            headers["Content-Type"] = "application/json"
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                headers=headers,
                timeout=30.0
            )
        return self._client
    
    async def search(
        self, 
        query: str, 
        max_results: int = 10,
        **kwargs
    ) -> List[PatentDocument]:
        """The Lens搜索"""
        results = []
        
        if not self.api_key:
            logger.warning("The Lens API需要API Key")
            return results
        
        try:
            client = await self._get_client()
            
            # Lens搜索API
            search_query = {
                "query": query,
                "size": max_results
            }
            
            response = await client.post("/patent/search", json=search_query)
            
            if response.status_code == 200:
                data = response.json()
                hits = data.get("data", [])
                
                for hit in hits:
                    doc_data = hit.get("data", {})
                    
                    doc = PatentDocument(
                        publication_number=doc_data.get("lens_id", ""),
                        title=doc_data.get("title"),
                        abstract=doc_data.get("abstract"),
                        application_number=doc_data.get("application_reference", {}).get("doc_number"),
                        publication_date=doc_data.get("publication_date"),
                        source=self.name,
                        url=f"https://www.lens.org/lens/patent/{doc_data.get('lens_id')}",
                        raw_data=doc_data
                    )
                    results.append(doc)
                
                logger.info(f"Lens搜索返回 {len(results)} 条结果")
            
        except Exception as e:
            logger.error(f"Lens搜索失败: {e}")
        
        return results
    
    async def get_patent(self, patent_number: str) -> Optional[PatentDocument]:
        """获取Lens专利详情"""
        if not self.api_key:
            return None
        
        try:
            client = await self._get_client()
            
            response = await client.get(f"/patent/{patent_number}")
            
            if response.status_code == 200:
                data = response.json()
                doc_data = data.get("data", {})
                
                return PatentDocument(
                    publication_number=doc_data.get("lens_id", ""),
                    title=doc_data.get("title"),
                    abstract=doc_data.get("abstract"),
                    source=self.name,
                    url=f"https://www.lens.org/lens/patent/{doc_data.get('lens_id')}",
                    raw_data=doc_data
                )
        
        except Exception as e:
            logger.error(f"获取Lens专利详情失败: {e}")
        
        return None
    
    async def close(self):
        if self._client:
            await self._client.aclose()


class BaitenPatentAPI(PatentDatabaseAPI):
    """佰腾专利大数据平台API (中国)
    
    官网: https://open.baiten.cn
    需要注册获取API Key
    """
    
    def __init__(self, api_key: Optional[str] = None, app_id: Optional[str] = None):
        self.base_url = "https://api.baiten.cn"
        self.api_key = api_key or os.getenv("BAITEN_API_KEY", "")
        self.app_id = app_id or os.getenv("BAITEN_APP_ID", "")
        self._client: Optional[httpx.AsyncClient] = None
        self._rate_limiter = RateLimiter(min_interval=1.0)  # 反爬: 速率限制
    
    @property
    def name(self) -> str:
        return "baiten"
    
    @property
    def is_available(self) -> bool:
        return bool(self.api_key and self.app_id)
    
    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Accept": "application/json"
            }
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                headers=headers,
                timeout=30.0
            )
        return self._client
    
    async def search(
        self, 
        query: str, 
        max_results: int = 10,
        patent_type: Optional[str] = None,
        **kwargs
    ) -> List[PatentDocument]:
        """佰腾专利搜索
        
        支持参数:
        - query: 搜索关键词
        - patent_type: 专利类型 (发明, 实用新型, 外观设计)
        """
        results = []
        
        if not self.is_available:
            logger.warning("佰腾API未配置API Key或App ID")
            return results
        
        try:
            async with self._rate_limiter:
                client = await self._get_client()
                
                # 构建查询参数
                params = {
                    "appkey": self.app_id,
                    "sign": self._generate_sign(),
                    "keyword": query,
                    "pageSize": max_results,
                    "pageIndex": 1
                }
                
                if patent_type:
                    params["patentType"] = patent_type
                
                response = await client.get("/search", params=params)
                
                if response.status_code == 200:
                    data = response.json()
                    patents = data.get("data", {}).get("list", [])
                    
                    for p in patents:
                        doc = self._parse_patent(p)
                        if doc:
                            results.append(doc)
                    
                    logger.info(f"佰腾搜索返回 {len(results)} 条结果")
                else:
                    logger.warning(f"佰腾API返回: {response.status_code}")
        
        except Exception as e:
            logger.error(f"佰腾搜索失败: {e}")
        
        return results
    
    def _generate_sign(self) -> str:
        """生成签名"""
        import hashlib
        sign_str = f"{self.app_id}{self.api_key}"
        return hashlib.md5(sign_str.encode()).hexdigest()
    
    def _parse_patent(self, data: Dict[str, Any]) -> Optional[PatentDocument]:
        try:
            return PatentDocument(
                application_number=data.get("appNumber"),
                publication_number=data.get("pubNumber"),
                title=data.get("title"),
                abstract=data.get("abstract"),
                applicant=data.get("applicant"),
                inventor=data.get("inventor"),
                application_date=data.get("appDate"),
                publication_date=data.get("pubDate"),
                ipc_classification=data.get("ipc"),
                patent_type=self._convert_type(data.get("patentType")),
                source=self.name,
                url=f"https://www.baiten.cn/patent/{data.get('pubNumber')}",
                assignee=data.get("assignee"),
                agent=data.get("agent"),
                raw_data=data
            )
        except Exception as e:
            logger.error(f"解析佰腾专利失败: {e}")
            return None
    
    def _convert_type(self, ptype: Optional[str]) -> Optional[str]:
        type_map = {"发明": "invention", "实用新型": "utility", "外观设计": "design"}
        return type_map.get(ptype, ptype) if ptype else None
    
    async def get_patent(self, patent_number: str) -> Optional[PatentDocument]:
        """获取佰腾专利详情"""
        if not self.is_available:
            return None
        
        results = await self.search(patent_number, max_results=1)
        return results[0] if results else None
    
    async def close(self):
        if self._client:
            await self._client.aclose()


class SooPATScraperAPI(PatentDatabaseAPI):
    """SooPAT 专利搜索 (通过网页抓取)
    
    官网: https://www.soopat.com
    注意: 反爬机制较强，建议仅用于小规模测试
    """
    
    def __init__(self):
        self.base_url = "https://www.soopat.com"
        self._client: Optional[httpx.AsyncClient] = None
        self._rate_limiter = RateLimiter(min_interval=3.0)  # 反爬: 较长间隔
    
    @property
    def name(self) -> str:
        return "soopat"
    
    @property
    def is_available(self) -> bool:
        return True
    
    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=30.0,
                follow_redirects=True,
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
                }
            )
        return self._client
    
    async def search(
        self, 
        query: str, 
        max_results: int = 10,
        **kwargs
    ) -> List[PatentDocument]:
        """SooPAT 专利搜索
        
        注意: 通过网页解析实现，反爬较严格，可能不稳定
        """
        results = []
        
        try:
            async with self._rate_limiter:
                client = await self._get_client()
                
                # SooPAT搜索URL
                search_url = f"{self.base_url}/Home/Search"
                params = {" keywords": query}
                
                response = await client.get(search_url, params=params)
                
                if response.status_code == 200:
                    soup = BeautifulSoup(response.text, 'html.parser')
                    
                    # 解析搜索结果
                    patent_items = soup.select('div.patent-item, div.result-item, div[data-bid]')
                    
                    for item in patent_items[:max_results]:
                        doc = self._parse_patent_item(item)
                        if doc:
                            results.append(doc)
                    
                    if not results:
                        # 尝试备用解析方式
                        results = self._parse_alternative(soup, max_results)
                    
                    logger.info(f"SooPAT搜索返回 {len(results)} 条结果")
                else:
                    logger.warning(f"SooPAT返回: {response.status_code}")
        
        except Exception as e:
            logger.error(f"SooPAT搜索失败: {e}")
        
        return results
    
    def _parse_patent_item(self, item) -> Optional[PatentDocument]:
        """解析单个专利项"""
        try:
            # 尝试提取专利号和标题
            title_elem = item.select_one('div.title, a.title, h3, .patent-title')
            title = title_elem.get_text(strip=True) if title_elem else None
            
            # 提取链接获取专利号
            link = item.select_one('a[href*="/Patent/"]')
            if link:
                href = link.get('href', '')
                # 提取专利号
                pub_num = re.search(r'/Patent/(\w+)', href)
                publication_number = pub_num.group(1) if pub_num else None
            else:
                publication_number = None
            
            if not title and not publication_number:
                return None
            
            return PatentDocument(
                publication_number=publication_number,
                title=title,
                source=self.name,
                url=f"{self.base_url}{href}" if link else None
            )
        except Exception as e:
            logger.debug(f"解析SooPAT专利项失败: {e}")
            return None
    
    def _parse_alternative(self, soup, max_results: int) -> List[PatentDocument]:
        """备用解析方式"""
        results = []
        links = soup.select('a[href*="/Patent/"]')
        
        for link in links[:max_results]:
            try:
                href = link.get('href', '')
                pub_num = re.search(r'/Patent/(\w+)', href)
                if pub_num:
                    results.append(PatentDocument(
                        publication_number=pub_num.group(1),
                        title=link.get_text(strip=True),
                        source=self.name,
                        url=f"{self.base_url}{href}"
                    ))
            except Exception:
                continue
        
        return results
    
    async def get_patent(self, patent_number: str) -> Optional[PatentDocument]:
        """获取SooPAT专利详情"""
        try:
            async with self._rate_limiter:
                client = await self._get_client()
                
                detail_url = f"{self.base_url}/Patent/{patent_number}"
                response = await client.get(detail_url)
                
                if response.status_code == 200:
                    soup = BeautifulSoup(response.text, 'html.parser')
                    
                    # 解析详情页
                    title_elem = soup.select_one('h1, div.detail-title, .patent-detail-title')
                    title = title_elem.get_text(strip=True) if title_elem else None
                    
                    abstract_elem = soup.select_one('div.abstract, .patent-abstract')
                    abstract = abstract_elem.get_text(strip=True) if abstract_elem else None
                    
                    return PatentDocument(
                        publication_number=patent_number,
                        title=title,
                        abstract=abstract,
                        source=self.name,
                        url=detail_url
                    )
        except Exception as e:
            logger.error(f"获取SooPAT专利详情失败: {e}")
        
        return None
    
    async def close(self):
        if self._client:
            await self._client.aclose()


class PatentDatabaseAggregator:
    """专利数据库聚合器"""
    
    def __init__(self):
        self.databases: Dict[str, PatentDatabaseAPI] = {}
        self._initialized = False
    
    def initialize(self):
        if self._initialized:
            return
        
        # 中国专利 - SooPAT (网页抓取) - 无需配置
        self.databases["soopat"] = SooPATScraperAPI()
        
        # 美国专利 (USPTO PatentsView) - 无需配置
        uspto_key = os.getenv("USPTO_PV_API_KEY", "")
        self.databases["uspto"] = USPATentAPI(uspto_key)
        
        # 国际专利 - 无需配置
        self.databases["wipo"] = WIPOPatentAPI()
        
        # 欧洲专利
        epo_key = os.getenv("EPO_OPS_API_KEY", "")
        self.databases["epo"] = EPOPatentAPI(epo_key)
        
        # Google Patents (网页抓取方式) - 无需配置
        self.databases["google"] = GooglePatentsFreeAPI()
        
        self._initialized = True
        logger.info(f"专利数据库初始化(默认): {list(self.databases.keys())}")

    def load_user_configs(self, tenant_id: Optional[int] = None):
        """
        从数据库加载用户配置的API密钥
        """
        try:
            from sqlalchemy import select
            from app.database.models import PatentSourceConfig
            from app.database.engine import async_session_factory
            import asyncio
            
            # 同步方式获取配置
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            async def get_configs():
                async with async_session_factory() as db:
                    query = select(PatentSourceConfig).where(PatentSourceConfig.is_enabled == True)
                    if tenant_id:
                        query = query.where(PatentSourceConfig.tenant_id == tenant_id)
                    result = await db.execute(query)
                    return result.scalars().all()
            
            configs = loop.run_until_complete(get_configs())
            loop.close()
            
            for config in configs:
                if config.source_name == "dawei" and config.api_key:
                    self.databases["dawei"] = DaWeiPatentAPI(config.api_key)
                    logger.info(f"加载用户配置: dawei")
                elif config.source_name == "baiten" and config.api_key and config.app_id:
                    self.databases["baiten"] = BaitenPatentAPI(config.api_key, config.app_id)
                    logger.info(f"加载用户配置: baiten")
                elif config.source_name == "cnipa" and config.api_key:
                    # CNIPA 使用 api_key 字段存储用户名:密码
                    self.databases["cnipa"] = CNIPAOfficialAPI(config.api_key, "")
                    logger.info(f"加载用户配置: cnipa")
                elif config.source_name == "lens" and config.api_key:
                    self.databases["lens"] = LensOrgAPI(config.api_key)
                    logger.info(f"加载用户配置: lens")
            
            logger.info(f"专利数据库用户配置加载完成: {[c.source_name for c in configs]}")
        except Exception as e:
            logger.warning(f"加载用户配置失败: {e}")
    
    async def search_all(
        self, 
        query: str, 
        sources: Optional[List[str]] = None,
        max_results_per_source: int = 5
    ) -> Dict[str, List[PatentDocument]]:
        self.initialize()
        
        if sources is None:
            sources = list(self.databases.keys())
        
        tasks = []
        source_list = []
        for source in sources:
            if source in self.databases:
                db = self.databases[source]
                if db.is_available:
                    tasks.append(self._search_source(source, query, max_results_per_source))
                    source_list.append(source)
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        aggregated: Dict[str, List[PatentDocument]] = {}
        for source, result in zip(source_list, results):
            if isinstance(result, Exception):
                logger.error(f"搜索{source}失败: {result}")
                aggregated[source] = []
            elif isinstance(result, list):
                aggregated[source] = result
            else:
                aggregated[source] = []
        
        return aggregated
    
    async def _search_source(self, source: str, query: str, max_results: int) -> List[PatentDocument]:
        try:
            return await self.databases[source].search(query, max_results)
        except Exception as e:
            logger.error(f"搜索{source}失败: {e}")
            return []
    
    async def get_patent(self, patent_number: str, source: str) -> Optional[PatentDocument]:
        self.initialize()
        if source not in self.databases:
            return None
        return await self.databases[source].get_patent(patent_number)
    
    def list_sources(self) -> List[Dict[str, Any]]:
        self.initialize()
        return [{"name": db.name, "available": db.is_available} for db in self.databases.values()]
    
    async def close(self):
        for db in self.databases.values():
            try:
                if hasattr(db, 'close') and callable(getattr(db, 'close', None)):
                    await db.close()
            except Exception as e:
                logger.warning(f"关闭数据库连接失败: {e}")


# 全局实例
patent_aggregator = PatentDatabaseAggregator()
