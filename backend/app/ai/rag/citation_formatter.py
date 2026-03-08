"""
引用格式化服务
Citation Formatting Service for RAG Results
"""
from __future__ import annotations
import logging
from typing import List, Optional, Dict, Any
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class Citation:
    """引用信息"""
    source_id: str
    source_type: str  # patent / paper / document / web
    title: str
    authors: Optional[List[str]] = None
    publication_date: Optional[str] = None
    source: Optional[str] = None  # USPTO / CNIPA / WIPO / etc.
    patent_number: Optional[str] = None
    application_number: Optional[str] = None
    url: Optional[str] = None
    abstract: Optional[str] = None
    relevance_score: Optional[float] = None
    excerpt: Optional[str] = None  # 相关片段


class CitationFormatter:
    """引用格式化服务"""
    
    # 引用格式模板
    CITATION_STYLES = {
        "patent": {
            "uspto": "[{patent_number}] {authors}. {title}. US Patent {patent_number}, {publication_date}.",
            "cnipa": "[{patent_number}] {authors}. {title}. CN Patent {patent_number}, {publication_date}.",
            "wipo": "[{patent_number}] {authors}. {title}. WO Patent {patent_number}, {publication_date}.",
            "epo": "[{patent_number}] {authors}. {title}. EP Patent {patent_number}, {publication_date}.",
            "default": "[{patent_number}] {authors}. {title}. {patent_number}, {publication_date}."
        },
        "paper": {
            "default": "[{source}] {authors} ({publication_date}). {title}. {source}."
        },
        "document": {
            "default": "[{source_id}] {title}. {publication_date or 'n.d.'}."
        },
        "web": {
            "default": "[{source}] {title}. Retrieved from {url}, {publication_date}."
        }
    }
    
    @staticmethod
    def format_citation(
        citation: Citation,
        style: str = "patent",
        source_key: str = "default"
    ) -> str:
        """
        格式化单个引用
        
        Args:
            citation: 引用信息
            style: 引用类型 (patent/paper/document/web)
            source_key: 来源标识
            
        Returns:
            格式化的引用字符串
        """
        # 获取格式化模板
        style_templates = CitationFormatter.CITATION_STYLES.get(style, {})
        template = style_templates.get(source_key, style_templates.get("default", "[{title}]"))
        
        # 准备格式化数据
        authors = ", ".join(citation.authors) if citation.authors else "Unknown"
        
        data = {
            "patent_number": citation.patent_number or citation.source_id,
            "application_number": citation.application_number or "",
            "authors": authors,
            "title": citation.title or "Untitled",
            "publication_date": citation.publication_date or "n.d.",
            "source": citation.source or "Unknown Source",
            "url": citation.url or "",
            "source_id": citation.source_id
        }
        
        try:
            return template.format(**data)
        except KeyError as e:
            logger.warning(f"引用格式化模板缺少字段: {e}")
            return f"[{citation.title or citation.source_id}]"
    
    @staticmethod
    def format_citations(
        citations: List[Citation],
        style: str = "patent",
        numbered: bool = True
    ) -> List[str]:
        """
        格式化多个引用
        
        Args:
            citations: 引用列表
            style: 引用类型
            numbered: 是否编号
            
        Returns:
            格式化的引用列表
        """
        results = []
        
        for i, citation in enumerate(citations):
            formatted = CitationFormatter.format_citation(citation, style)
            
            if numbered:
                # 添加编号
                results.append(f"[{i+1}] {formatted}")
            else:
                results.append(formatted)
        
        return results
    
    @staticmethod
    def format_reference_list(
        citations: List[Citation],
        style: str = "patent",
        include_scores: bool = False
    ) -> str:
        """
        生成参考文献列表
        
        Args:
            citations: 引用列表
            style: 引用类型
            include_scores: 是否包含相关性分数
            
        Returns:
            格式化的参考文献列表
        """
        formatted = CitationFormatter.format_citations(citations, style, numbered=True)
        
        if include_scores:
            for i, citation in enumerate(citations):
                if citation.relevance_score is not None:
                    formatted[i] += f" (相关度: {citation.relevance_score:.2%})"
        
        return "\n".join(formatted)
    
    @staticmethod
    def create_citation_from_chunk(
        chunk_text: str,
        metadata: Dict[str, Any],
        relevance_score: Optional[float] = None
    ) -> Citation:
        """
        从检索片段创建引用
        
        Args:
            chunk_text: 检索片段文本
            metadata: 元数据
            relevance_score: 相关性分数
            
        Returns:
            Citation 对象
        """
        return Citation(
            source_id=metadata.get("id", metadata.get("source_id", "unknown")),
            source_type=metadata.get("source_type", "document"),
            title=metadata.get("title", metadata.get("patent_title", "Unknown Title")),
            authors=metadata.get("authors", metadata.get("inventor")),
            publication_date=metadata.get("publication_date", metadata.get("date")),
            source=metadata.get("source", metadata.get("database")),
            patent_number=metadata.get("patent_number"),
            application_number=metadata.get("application_number"),
            url=metadata.get("url"),
            abstract=metadata.get("abstract"),
            relevance_score=relevance_score,
            excerpt=chunk_text
        )
    
    @staticmethod
    def create_inline_citations(
        citations: List[Citation],
        max_citations: int = 5
    ) -> str:
        """
        创建行内引用标记
        
        Args:
            citations: 引用列表
            max_citations: 最大引用数量
            
        Returns:
            行内引用字符串，如 [1,2,3,4,5]
        """
        if not citations:
            return ""
        
        # 按相关性排序
        sorted_citations = sorted(
            citations, 
            key=lambda x: x.relevance_score or 0, 
            reverse=True
        )
        
        # 取前N个
        top_citations = sorted_citations[:max_citations]
        
        # 生成引用编号
        citation_indices = [i + 1 for i, _ in enumerate(citations) if any(c.source_id == citations[i].source_id for c in top_citations)]
        
        # 去重并保持顺序
        seen = set()
        unique_indices = []
        for idx in citation_indices:
            if idx not in seen:
                seen.add(idx)
                unique_indices.append(idx)
        
        if len(unique_indices) > max_citations:
            unique_indices = unique_indices[:max_citations]
        
        return f"[{','.join(map(str, sorted(unique_indices)))}]"


class CitationManager:
    """引用管理器 - 管理RAG结果的引用"""
    
    def __init__(self):
        self.citations: List[Citation] = []
        self._source_map: Dict[str, int] = {}  # source_id -> citation_index
    
    def add_citation(
        self,
        source_id: str,
        source_type: str,
        title: str,
        **kwargs
    ) -> int:
        """
        添加引用
        
        Returns:
            引用索引（从1开始）
        """
        # 检查是否已存在
        if source_id in self._source_map:
            return self._source_map[source_id] + 1
        
        citation = Citation(
            source_id=source_id,
            source_type=source_type,
            title=title,
            **kwargs
        )
        
        self.citations.append(citation)
        self._source_map[source_id] = len(self.citations) - 1
        
        return len(self.citations)
    
    def get_citation_index(self, source_id: str) -> Optional[int]:
        """获取引用索引"""
        if source_id in self._source_map:
            return self._source_map[source_id] + 1
        return None
    
    def format_all(self, style: str = "patent") -> List[str]:
        """格式化所有引用"""
        return CitationFormatter.format_citations(self.citations, style)
    
    def format_reference_list(self, style: str = "patent", include_scores: bool = False) -> str:
        """生成参考文献列表"""
        return CitationFormatter.format_reference_list(self.citations, style, include_scores)
    
    def get_unique_sources(self) -> List[str]:
        """获取唯一来源列表"""
        return list(self._source_map.keys())


# 全局引用管理器实例
citation_manager: Optional[CitationManager] = None


def get_citation_manager() -> CitationManager:
    """获取引用管理器实例"""
    global citation_manager
    if citation_manager is None:
        citation_manager = CitationManager()
    return citation_manager
