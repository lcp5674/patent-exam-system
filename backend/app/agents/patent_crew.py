#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
专利数据爬取和RAG增强的多Agent协作系统
基于CrewAI框架
"""

import os
import asyncio
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from dotenv import load_dotenv

from crewai import Agent, Crew, Process, Task
from crewai.project import CrewBase, agent, crew, task
from crewai_tools import BaseTool

from app.core.logging_config import setup_logging
from app.schemas.patent import PatentMetadata, PatentFullText
from app.ai.patent_dna.fingerprint import PatentFingerprint
from app.ai.patent_dna.similarity import PatentSimilarityEngine
from app.services.patent_datasource.datasource_config import DataSource

# 加载环境变量
load_dotenv()

# 配置日志
logger = setup_logging(__name__)


class PatentSearchTools:
    """专利搜索工具类"""

    @staticmethod
    def search_patents(query: str, source: str, limit: int = 100) -> List[Dict[str, Any]]:
        """
        搜索专利数据

        Args:
            query: 搜索关键词或查询语句
            source: 数据源（cnipa/uspto/epo/wipo）
            limit: 返回结果数量限制

        Returns:
            专利列表
        """
        # 这里实现具体的搜索逻辑
        # 返回示例数据格式
        return []

    @staticmethod
    def fetch_patent_detail(patent_id: str, source: str) -> Dict[str, Any]:
        """
        获取专利详细信息

        Args:
            patent_id: 专利ID
            source: 数据源

        Returns:
            专利详细信息
        """
        # 实现具体的专利详情获取逻辑
        return {}


class CrawlerTool(BaseTool):
    """专利爬取工具"""
    name: str = "Patent Crawler"
    description: str = "从各国专利局爬取公开的专利数据，支持CNIPA、USPTO、EPO、WIPO等数据源"

    def _run(self, source: str, query: str, limit: int = 100) -> List[Dict[str, Any]]:
        """执行爬取操作"""
        logger.info(f"[{source}] 开始爬取专利数据，查询: {query}, 限制: {limit}")

        # 根据数据源选择爬虫
        crawlers = {
            "cnipa": "app.agents.crawler.cnipa_crawler.CNIPACrawler",
            "uspto": "app.agents.crawler.uspto_crawler.USPTOCrawler",
            "epo": "app.agents.crawler.epo_crawler.EPOCrawler",
            "wipo": "app.agents.crawler.wipo_crawler.WIPOCrawler",
        }

        if source not in crawlers:
            raise ValueError(f"不支持的数据源: {source}")

        # 这里调用具体的爬虫实现
        # 返回爬取到的专利数据
        patents = PatentSearchTools.search_patents(query, source, limit)
        logger.info(f"[{source}] 爬取完成，获取 {len(patents)} 条专利")
        return patents


class EmbeddingTool(BaseTool):
    """Embedding生成工具"""
    name: str = "Embedding Generator"
    description: str = "将专利文本转换为向量表示，用于RAG检索和相似性计算"

    def _run(self, patents: List[Dict[str, Any]]) -> List[PatentFingerprint]:
        """生成专利指纹"""
        logger.info(f"开始生成 {len(patents)} 个专利的embedding")

        fingerprints = []
        for patent in patents:
            try:
                # 创建专利指纹
                fp = PatentFingerprint.from_patent_data(patent)
                fingerprints.append(fp)
            except Exception as e:
                logger.error(f"生成专利 {patent.get('patent_id')} 的embedding失败: {e}")

        logger.info(f"成功生成 {len(fingerprints)} 个embedding")
        return fingerprints


class VectorStoreTool(BaseTool):
    """向量存储工具"""
    name: str = "Vector Store"
    description: str = "将专利向量存储到ChromaDB，支持高效检索和相似性搜索"

    def __init__(self):
        super().__init__()
        from app.ai.patent_dna.vector_store import VectorStore
        self.vector_store = VectorStore()

    def _run(self, fingerprints: List[PatentFingerprint], collection_name: str) -> Dict[str, Any]:
        """存储到向量数据库"""
        logger.info(f"存储 {len(fingerprints)} 个专利向量到集合: {collection_name}")

        try:
            self.vector_store.add_documents(fingerprints, collection_name)
            logger.info("向量存储完成")
            return {
                "status": "success",
                "count": len(fingerprints),
                "collection": collection_name
            }
        except Exception as e:
            logger.error(f"向量存储失败: {e}")
            return {
                "status": "error",
                "error": str(e)
            }


@CrewBase
class PatentCrew:
    """专利数据爬取和RAG增强的Crew"""

    def __init__(self):
        # Agent配置
        self.agents_config_path = os.path.join(os.path.dirname(__file__), 'config', 'agents.yaml')
        self.tasks_config_path = os.path.join(os.path.dirname(__file__), 'config', 'tasks.yaml')

    @agent
    def senior_patent_researcher(self) -> Agent:
        """高级专利研究员"""
        return Agent(
            config=self.agents_config['senior_patent_researcher'],
            tools=[CrawlerTool()],
            verbose=True,
            allow_delegation=True
        )

    @agent
    def patent_data_engineer(self) -> Agent:
        """专利数据工程师"""
        return Agent(
            config=self.agents_config['patent_data_engineer'],
            tools=[EmbeddingTool(), VectorStoreTool()],
            verbose=True,
            allow_delegation=False
        )

    @agent
    def rag_optimization_specialist(self) -> Agent:
        """RAG优化专家"""
        return Agent(
            config=self.agents_config['rag_optimization_specialist'],
            tools=[EmbeddingTool(), VectorStoreTool()],
            verbose=True,
            allow_delegation=False
        )

    @agent
    def quality_assurance_reviewer(self) -> Agent:
        """质量保证审查员"""
        return Agent(
            config=self.agents_config['quality_assurance_reviewer'],
            tools=[EmbeddingTool(), VectorStoreTool()],
            verbose=True,
            allow_delegation=False
        )

    @task
    def discover_patents_task(self) -> Task:
        """发现专利数据任务"""
        return Task(
            config=self.tasks_config['discover_patents_task'],
            agent=self.senior_patent_researcher()
        )

    @task
    def process_and_embed_task(self) -> Task:
        """处理和嵌入数据任务"""
        return Task(
            config=self.tasks_config['process_and_embed_task'],
            agent=self.patent_data_engineer()
        )

    @task
    def optimize_rag_task(self) -> Task:
        """优化RAG任务"""
        return Task(
            config=self.tasks_config['optimize_rag_task'],
            agent=self.rag_optimization_specialist()
        )

    @task
    def quality_review_task(self) -> Task:
        """质量审查任务"""
        return Task(
            config=self.tasks_config['quality_review_task'],
            agent=self.quality_assurance_reviewer()
        )

    @crew
    def crew(self) -> Crew:
        """创建Crew"""
        return Crew(
            agents=self.agents,
            tasks=self.tasks,
            process=Process.sequential,
            verbose=2,
            memory=True,
            max_rpm=100
        )

    async def run_full_crawl(
        self,
        sources: List[str],
        query: str = "*",
        limit: int = 1000,
        collection_prefix: str = None
    ) -> Dict[str, Any]:
        """
        执行全量爬取

        Args:
            sources: 数据源列表 ["cnipa", "uspto", "epo", "wipo"]
            query: 查询语句
            limit: 每源爬取数量
            collection_prefix: 集合名称前缀

        Returns:
            执行结果
        """
        if collection_prefix is None:
            collection_prefix = f"patents_{datetime.now().strftime('%Y%m')}"

        logger.info(f"开始全量爬取: sources={sources}, query={query}, limit={limit}")

        results = {}
        for source in sources:
            try:
                # 执行爬取流程
                result = await self._crawl_source(source, query, limit, collection_prefix)
                results[source] = result
            except Exception as e:
                logger.error(f"爬取 {source} 失败: {e}")
                results[source] = {"status": "error", "error": str(e)}

        logger.info(f"全量爬取完成: {results}")
        return results

    async def run_incremental_crawl(
        self,
        sources: List[str],
        hours: int = 24
    ) -> Dict[str, Any]:
        """
        执行增量爬取

        Args:
            sources: 数据源列表
            hours: 爬取最近N小时的数据

        Returns:
            执行结果
        """
        logger.info(f"开始增量爬取: sources={sources}, hours={hours}")

        # 计算时间范围
        end_date = datetime.now()
        start_date = end_date - timedelta(hours=hours)

        results = {}
        for source in sources:
            try:
                # 构建时间范围查询
                query = self._build_time_range_query(start_date, end_date, source)
                collection_prefix = f"patents_incremental_{datetime.now().strftime('%Y%m%d_%H')}_{source}"

                result = await self._crawl_source(
                    source, query, limit=500, collection_prefix=collection_prefix
                )
                results[source] = result
            except Exception as e:
                logger.error(f"增量爬取 {source} 失败: {e}")
                results[source] = {"status": "error", "error": str(e)}

        logger.info(f"增量爬取完成: {results}")
        return results

    async def _crawl_source(
        self,
        source: str,
        query: str,
        limit: int,
        collection_prefix: str
    ) -> Dict[str, Any]:
        """爬取单个数据源"""
        # 使用CrewAI执行任务
        inputs = {
            "source": source,
            "query": query,
            "limit": limit,
            "collection_name": f"{collection_prefix}_{source}"
        }

        # 启动Crew
        result = await asyncio.to_thread(self.crew().kickoff, inputs=inputs)

        return {
            "status": "success",
            "result": result,
            "collection": inputs["collection_name"]
        }

    def _build_time_range_query(self, start: datetime, end: datetime, source: str) -> str:
        """构建时间范围查询"""
        # 根据不同数据源构建查询语句
        if source == "cnipa":
            return f"申请日:[{start.strftime('%Y%m%d')} TO {end.strftime('%Y%m%d')}]"
        elif source == "uspto":
            return f"APD/{start.strftime('%Y%m%d')}-{end.strftime('%Y%m%d')}"
        elif source == "epo":
            return f"pd within \"{start.strftime('%Y-%m-%d')} {end.strftime('%Y-%m-%d')}\""
        elif source == "wipo":
            return f"Date: [{start.strftime('%d/%m/%Y')} TO {end.strftime('%d/%m/%Y')}]"
        else:
            return "*"


# 单例实例
_patent_crew_instance = None


def get_patent_crew() -> PatentCrew:
    """获取PatentCrew单例实例"""
    global _patent_crew_instance
    if _patent_crew_instance is None:
        _patent_crew_instance = PatentCrew()
    return _patent_crew_instance


if __name__ == "__main__":
    # 测试运行
    async def test():
        crew = get_patent_crew()

        # 测试全量爬取
        result = await crew.run_full_crawl(
            sources=["cnipa"],
            query="人工智能 AND 机器学习",
            limit=10,
            collection_prefix="test_patents"
        )
        print("测试结果:", result)

    asyncio.run(test())
