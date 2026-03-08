"""
企业级专利数据库集成服务
支持 USPTO PatentsView, EPO, CNIPA, WIPO, Google Patents
"""
from __future__ import annotations
import httpx
import asyncio
import logging
import os
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field
from datetime import datetime
from abc import ABC, abstractmethod
import json

logger = logging.getLogger(__name__)


@dataclass
class PatentDocument:
    """专利文献数据结构"""
    id: str
    application_number: Optional[str] = None
    publication_number: Optional[str] = None
    title: Optional[str] = None
    abstract: Optional[str] = None
    claims: Optional[List[str]] = None
    description: Optional[str] = None
    applicant: Optional[str] = None
    assignee: Optional[str] = None
    inventor: Optional[str] = None
    application_date: Optional[str] = None
    publication_date: Optional[str] = None
    grant_date: Optional[str] = None
    ipc_classification: Optional[List[str]] = None
    cpc_classification: Optional[List[str]] = None
    uspc_classification: Optional[List[str]] = None
    patent_type: Optional[str] = None  # invention / utility / design / plant
    status: Optional[str] = None
    source: str = "unknown"
    url: Optional[str] = None
    family_id: Optional[str] = None
    citations: Optional[List[Dict[str, str]]] = None
    cited_by: Optional[List[Dict[str, str]]] = None
    raw_data: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "application_number": self.application_number,
            "publication_number": self.publication_number,
            "title": self.title,
            "abstract": self.abstract,
            "claims": self.claims,
            "description": self.description,
            "applicant": self.applicant,
            "assignee": self.assignee,
            "inventor": self.inventor,
            "application_date": self.application_date,
            "publication_date": self.publication_date,
            "grant_date": self.grant_date,
            "ipc_classification": self.ipc_classification,
            "cpc_classification": self.cpc_classification,
            "patent_type": self.patent_type,
            "status": self.status,
            "source": self.source,
            "url": self.url,
        }


@dataclass
class SearchParams:
    """搜索参数"""
    query: str
    max_results: int = 20
    filters: Dict[str, Any] = field(default_factory=dict)
    date_from: Optional[str] = None
    date_to: Optional[str] = None
    classifications: Optional[List[str]] = None
    inventors: Optional[List[str]] = None
    assignees: Optional[List[str]] = None


class PatentDatabaseConnector(ABC):
    """专利数据库连接器抽象基类"""
    
    @property
    @abstractmethod
    def name(self) -> str:
        """数据库名称"""
        pass
    
    @property
    @abstractmethod
    def is_available(self) -> bool:
        """是否可用"""
        pass
    
    @abstractmethod
    async def search(self, params: SearchParams) -> List[PatentDocument]:
        """搜索专利"""
        pass
    
    @abstractmethod
    async def get_patent(self, patent_id: str) -> Optional[PatentDocument]:
        """获取专利详情"""
        pass
    
    @abstractmethod
    async def get_citations(self, patent_id: str) -> List[Dict[str, str]]:
        """获取引用文献"""
        pass


class USPTOPatentsViewConnector(PatentDatabaseConnector):
    """USPTO PatentsView API连接器
    
    PatentsView是美国专利商标局提供的免费专利数据API
    文档: https://search.patentsview.org/docs/
    """
    
    def __init__(self, api_key: Optional[str] = None):
        self.base_url = "https://search.patentsview.org/api/v1"
        self.api_key = api_key or os.getenv("USPTO_PV_API_KEY", "")
        self._client: Optional[httpx.AsyncClient] = None
    
    @property
    def name(self) -> str:
        return "uspto_patentsview"
    
    @property
    def is_available(self) -> bool:
        return True  # PatentsView是免费公开API
    
    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            headers = {}
            if self.api_key:
                headers["X-Api-Key"] = self.api_key
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                headers=headers,
                timeout=30.0
            )
        return self._client
    
    async def search(self, params: SearchParams) -> List[PatentDocument]:
        """搜索美国专利"""
        results = []
        try:
            client = await self._get_client()
            
            # 构建查询
            query_parts = []
            if params.query:
                query_parts.append({"_text_any": {"patent_title": params.query}})
            
            # 添加日期过滤
            if params.date_from or params.date_to:
                date_filter = {}
                if params.date_from:
                    date_filter["patent_date"] = {"$gte": params.date_from}
                if params.date_to:
                    date_filter.setdefault("patent_date", {})["$lte"] = params.date_to
                query_parts.append(date_filter)
            
            # 添加分类过滤
            if params.classifications:
                for cls in params.classifications:
                    query_parts.append({"cpc_subgroup_id": cls})
            
            query = {"$and": query_parts} if len(query_parts) > 1 else (query_parts[0] if query_parts else {})
            
            # 请求字段
            fields = [
                "patent_id", "patent_title", "patent_date", "patent_type",
                "patent_abstract", "inventors", "assignees", "cpcs", "ipcs"
            ]
            
            response = await client.get(
                "/patent/",
                params={
                    "q": json.dumps(query),
                    "f": json.dumps(fields),
                    "o": json.dumps({"per_page": params.max_results})
                }
            )
            
            if response.status_code == 200:
                data = response.json()
                patents = data.get("patents", [])
                
                for p in patents:
                    doc = PatentDocument(
                        id=p.get("patent_id", ""),
                        publication_number=p.get("patent_id"),
                        title=p.get("patent_title"),
                        abstract=p.get("patent_abstract"),
                        patent_type=p.get("patent_type"),
                        publication_date=p.get("patent_date"),
                        source=self.name,
                        url=f"https://patents.google.com/patent/US{p.get('patent_id')}",
                        ipc_classification=[ipc.get("ipc_class_id") for ipc in p.get("ipcs", [])],
                        cpc_classification=[cpc.get("cpc_group_id") for cpc in p.get("cpcs", [])],
                        inventor=", ".join([inv.get("inventor_first_name", "") + " " + inv.get("inventor_last_name", "") for inv in p.get("inventors", [])]),
                        assignee=", ".join([a.get("assignee_organization", "") for a in p.get("assignees", [])]),
                        raw_data=p
                    )
                    results.append(doc)
                    
                logger.info(f"USPTO PatentsView搜索返回 {len(results)} 条结果")
            
        except Exception as e:
            logger.error(f"USPTO PatentsView搜索失败: {e}")
        
        return results
    
    async def get_patent(self, patent_id: str) -> Optional[PatentDocument]:
        """获取美国专利详情"""
        try:
            client = await self._get_client()
            
            response = await client.get(
                "/patent/",
                params={
                    "q": json.dumps({"patent_id": patent_id}),
                    "f": json.dumps([
                        "patent_id", "patent_title", "patent_date", "patent_type",
                        "patent_abstract", "inventors", "assignees", "cpcs", "ipcs",
                        "uspcs", "application_number", "application_date"
                    ])
                }
            )
            
            if response.status_code == 200:
                data = response.json()
                patents = data.get("patents", [])
                
                if patents:
                    p = patents[0]
                    return PatentDocument(
                        id=p.get("patent_id", ""),
                        application_number=p.get("application_number"),
                        publication_number=p.get("patent_id"),
                        title=p.get("patent_title"),
                        abstract=p.get("patent_abstract"),
                        patent_type=p.get("patent_type"),
                        application_date=p.get("application_date"),
                        publication_date=p.get("patent_date"),
                        source=self.name,
                        url=f"https://patents.google.com/patent/US{p.get('patent_id')}",
                        raw_data=p
                    )
                    
        except Exception as e:
            logger.error(f"获取美国专利详情失败: {e}")
        
        return None
    
    async def get_citations(self, patent_id: str) -> List[Dict[str, str]]:
        """获取引用文献"""
        try:
            client = await self._get_client()
            
            response = await client.get(
                "/us_patent_citation/",
                params={
                    "q": json.dumps({"patent_id": patent_id}),
                    "f": json.dumps(["patent_id", "citation_id", "citation_date"])
                }
            )
            
            if response.status_code == 200:
                data = response.json()
                citations = data.get("us_patent_citations", [])
                return [
                    {"patent_id": c.get("citation_id"), "date": c.get("citation_date")}
                    for c in citations
                ]
                
        except Exception as e:
            logger.error(f"获取引用文献失败: {e}")
        
        return []
    
    async def close(self):
        if self._client:
            await self._client.aclose()
            self._client = None


class GooglePatentsConnector(PatentDatabaseConnector):
    """Google Patents API连接器 (通过公开接口)"""
    
    def __init__(self):
        self.base_url = "https://patents.google.com"
        self._client: Optional[httpx.AsyncClient] = None
    
    @property
    def name(self) -> str:
        return "google_patents"
    
    @property
    def is_available(self) -> bool:
        return True
    
    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=30.0)
        return self._client
    
    async def search(self, params: SearchParams) -> List[PatentDocument]:
        """通过Google Patents搜索"""
        # Google Patents没有公开的REST API，需要使用其他方式
        # 这里提供占位实现，实际生产环境可以使用:
        # 1. Lens.org API (免费注册)
        # 2. 自己的爬虫服务
        # 3. 商业API
        
        logger.warning("Google Patents搜索需要商业API或爬虫服务")
        return []
    
    async def get_patent(self, patent_id: str) -> Optional[PatentDocument]:
        """获取专利详情"""
        # 占位实现
        return None
    
    async def get_citations(self, patent_id: str) -> List[Dict[str, str]]:
        """获取引用文献"""
        return []
    
    async def close(self):
        if self._client:
            await self._client.aclose()


class LensPatentConnector(PatentDatabaseConnector):
    """The Lens专利数据库连接器
    
    The Lens提供免费API访问
    文档: https://www.lens.org/lens/api
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
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                headers=headers,
                timeout=30.0
            )
        return self._client
    
    async def search(self, params: SearchParams) -> List[PatentDocument]:
        """搜索专利"""
        results = []
        
        if not self.api_key:
            logger.warning("Lens API未配置API Key")
            return results
        
        try:
            client = await self._get_client()
            
            query = {
                "query": {
                    "bool": {
                        "must": [
                            {"match": {"title": params.query}}
                        ]
                    }
                },
                "size": params.max_results
            }
            
            response = await client.post("/patent/search", json=query)
            
            if response.status_code == 200:
                data = response.json()
                hits = data.get("data", [])
                
                for hit in hits:
                    doc_data = hit.get("data", {})
                    
                    doc = PatentDocument(
                        id=doc_data.get("lens_id", ""),
                        publication_number=doc_data.get("publication_reference", {}).get("doc_number"),
                        title=doc_data.get("title"),
                        abstract=doc_data.get("abstract"),
                        application_number=doc_data.get("application_reference", {}).get("doc_number"),
                        publication_date=doc_data.get("publication_date"),
                        source=self.name,
                        url=f"https://www.lens.org/lens/patent/{doc_data.get('lens_id')}",
                        raw_data=doc_data
                    )
                    
                    # 提取分类
                    if doc_data.get("classifications_cpc"):
                        doc.cpc_classification = [c.get("symbol") for c in doc_data["classifications_cpc"]]
                    if doc_data.get("classifications_ipc"):
                        doc.ipc_classification = [c.get("symbol") for c in doc_data["classifications_ipc"]]
                    
                    results.append(doc)
                    
                logger.info(f"Lens搜索返回 {len(results)} 条结果")
                
        except Exception as e:
            logger.error(f"Lens专利搜索失败: {e}")
        
        return results
    
    async def get_patent(self, patent_id: str) -> Optional[PatentDocument]:
        """获取专利详情"""
        if not self.api_key:
            return None
            
        try:
            client = await self._get_client()
            
            response = await client.get(f"/patent/{patent_id}")
            
            if response.status_code == 200:
                data = response.json()
                doc_data = data.get("data", {})
                
                return PatentDocument(
                    id=doc_data.get("lens_id", ""),
                    publication_number=doc_data.get("publication_reference", {}).get("doc_number"),
                    title=doc_data.get("title"),
                    abstract=doc_data.get("abstract"),
                    application_number=doc_data.get("application_reference", {}).get("doc_number"),
                    publication_date=doc_data.get("publication_date"),
                    source=self.name,
                    url=f"https://www.lens.org/lens/patent/{doc_data.get('lens_id')}",
                    raw_data=doc_data
                )
                
        except Exception as e:
            logger.error(f"获取Lens专利详情失败: {e}")
        
        return None
    
    async def get_citations(self, patent_id: str) -> List[Dict[str, str]]:
        """获取引用文献"""
        return []
    
    async def close(self):
        if self._client:
            await self._client.aclose()


class PatentDatabaseService:
    """专利数据库服务 - 统一接口"""
    
    def __init__(self):
        self._connectors: Dict[str, PatentDatabaseConnector] = {}
        self._initialized = False
    
    def initialize(self):
        """初始化专利数据库连接器"""
        if self._initialized:
            return
        
        # 注册USPTO PatentsView
        self._connectors["uspto"] = USPTOPatentsViewConnector()
        
        # 注册Google Patents
        self._connectors["google"] = GooglePatentsConnector()
        
        # 注册Lens (如果配置了API Key)
        lens_key = os.getenv("LENS_API_KEY", "")
        if lens_key:
            self._connectors["lens"] = LensPatentConnector(lens_key)
        
        self._initialized = True
        logger.info(f"专利数据库服务初始化完成，可用连接器: {list(self._connectors.keys())}")
    
    def get_connector(self, name: str) -> Optional[PatentDatabaseConnector]:
        """获取指定连接器"""
        return self._connectors.get(name)
    
    def list_connectors(self) -> List[Dict[str, Any]]:
        """列出所有连接器"""
        return [
            {"name": conn.name, "available": conn.is_available}
            for conn in self._connectors.values()
        ]
    
    async def search(
        self,
        query: str,
        sources: Optional[List[str]] = None,
        max_results: int = 20,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        classifications: Optional[List[str]] = None
    ) -> Dict[str, List[PatentDocument]]:
        """搜索多个专利数据库"""
        self.initialize()
        
        if sources is None:
            sources = list(self._connectors.keys())
        
        params = SearchParams(
            query=query,
            max_results=max_results,
            date_from=date_from,
            date_to=date_to,
            classifications=classifications
        )
        
        tasks = []
        source_list = []
        
        for source in sources:
            if source in self._connectors:
                connector = self._connectors[source]
                if connector.is_available:
                    tasks.append(self._search_source(connector, params))
                    source_list.append(source)
        
        results_list = await asyncio.gather(*tasks, return_exceptions=True)
        
        aggregated: Dict[str, List[PatentDocument]] = {}
        for source, result in zip(source_list, results_list):
            if isinstance(result, Exception):
                logger.error(f"搜索{source}失败: {result}")
                aggregated[source] = []
            else:
                aggregated[source] = result
        
        return aggregated
    
    async def _search_source(
        self,
        connector: PatentDatabaseConnector,
        params: SearchParams
    ) -> List[PatentDocument]:
        """搜索单个数据源"""
        try:
            return await connector.search(params)
        except Exception as e:
            logger.error(f"搜索{connector.name}失败: {e}")
            return []
    
    async def get_patent(
        self,
        patent_id: str,
        source: str = "uspto"
    ) -> Optional[PatentDocument]:
        """获取专利详情"""
        self.initialize()
        
        connector = self._connectors.get(source)
        if not connector:
            return None
        
        return await connector.get_patent(patent_id)
    
    async def get_citations(
        self,
        patent_id: str,
        source: str = "uspto"
    ) -> List[Dict[str, str]]:
        """获取引用文献"""
        self.initialize()
        
        connector = self._connectors.get(source)
        if not connector:
            return []
        
        return await connector.get_citations(patent_id)
    
    async def search_and_index(
        self,
        query: str,
        sources: Optional[List[str]] = None,
        tenant_id: Optional[str] = None,
        max_results: int = 50
    ) -> Dict[str, Any]:
        """搜索并索引到RAG系统"""
        # 执行搜索
        results = await self.search(query, sources, max_results)
        
        # 收集所有结果
        all_patents = []
        for source, patents in results.items():
            all_patents.extend(patents)
        
        # 索引到向量数据库
        if all_patents:
            from app.ai.rag.enterprise_vector_db import enterprise_vector_db
            
            index_results = await enterprise_vector_db.index_patent_batch(
                [p.to_dict() for p in all_patents],
                tenant_id=tenant_id
            )
            
            return {
                "total_found": len(all_patents),
                "indexed": sum(1 for v in index_results.values() if v),
                "sources": {k: len(v) for k, v in results.items()},
                "index_results": index_results
            }
        
        return {"total_found": 0, "indexed": 0, "sources": {}}
    
    async def close(self):
        """关闭所有连接"""
        for connector in self._connectors.values():
            if hasattr(connector, 'close'):
                await connector.close()


# 全局实例
patent_database_service = PatentDatabaseService()
