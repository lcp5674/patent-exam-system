"""专利文档解析服务 - 支持 PDF / Word / 纯文本"""
from __future__ import annotations
import re
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

@dataclass
class PatentMetadata:
    application_number: str = ""
    application_date: str = ""
    title: str = ""
    applicant: str = ""
    inventor: str = ""
    agent: str = ""
    ipc_classification: str = ""

@dataclass
class ClaimFeature:
    claim_number: int = 0
    claim_type: str = "independent"   # independent / dependent
    preamble: str = ""                # 前序部分
    characterizing: str = ""          # 特征部分
    references: list[int] = field(default_factory=list)  # 引用的权利要求号
    full_text: str = ""

@dataclass
class PatentStructure:
    request_info: str = ""            # 请求书
    claims: list[ClaimFeature] = field(default_factory=list)
    description: dict = field(default_factory=dict)  # 各章节
    abstract: str = ""
    drawings_described: bool = False

@dataclass
class ParseResult:
    success: bool = True
    metadata: PatentMetadata = field(default_factory=PatentMetadata)
    structure: PatentStructure = field(default_factory=PatentStructure)
    full_text: str = ""
    error: str = ""


class DocumentParserService:
    """文档解析主服务"""

    async def parse_file(self, file_path: str) -> ParseResult:
        path = Path(file_path)
        if not path.exists():
            return ParseResult(success=False, error=f"文件不存在: {file_path}")
        suffix = path.suffix.lower()
        
        # 检测.doc文件是否实际上是文本文件
        if suffix == ".doc":
            try:
                # 尝试读取文件头判断是否是Office文档
                with open(path, "rb") as f:
                    header = f.read(4)
                # Office文档以PK (ZIP)开头，文本文件不是
                if not (header[:2] == b"PK" or header == b"\xd0\xcf\x11\xe0"):
                    # 不是真正的Office文档，可能是文本文件
                    suffix = ".txt"
            except Exception:
                pass
        
        try:
            if suffix == ".pdf":
                text = self._parse_pdf(path)
            elif suffix in (".doc", ".docx"):
                text = self._parse_docx(path)
            elif suffix == ".txt":
                text = self._parse_txt(path)
            else:
                return ParseResult(success=False, error=f"不支持的文件格式: {suffix}")
        except Exception as e:
            logger.error(f"文档解析失败: {e}")
            return ParseResult(success=False, error=str(e))

        metadata = self.extract_metadata(text, file_path)
        structure = self.extract_patent_structure(text)
        return ParseResult(success=True, metadata=metadata, structure=structure, full_text=text)

    def _parse_pdf(self, path: Path) -> str:
        try:
            import pdfplumber
            text_parts = []
            with pdfplumber.open(str(path)) as pdf:
                for page in pdf.pages:
                    t = page.extract_text()
                    if t:
                        text_parts.append(t)
            return "\n".join(text_parts)
        except ImportError:
            raise RuntimeError("需要安装 pdfplumber: pip install pdfplumber")

    def _parse_docx(self, path: Path) -> str:
        try:
            from docx import Document
            doc = Document(str(path))
            return "\n".join(p.text for p in doc.paragraphs if p.text.strip())
        except ImportError:
            raise RuntimeError("需要安装 python-docx: pip install python-docx")

    def _parse_txt(self, path: Path) -> str:
        import chardet
        raw = path.read_bytes()
        detected = chardet.detect(raw)
        encoding = detected.get("encoding", "utf-8") or "utf-8"
        return raw.decode(encoding, errors="replace")

    def extract_metadata(self, text: str, file_path: str = "") -> PatentMetadata:
        meta = PatentMetadata()
        
        # 申请号 - 多种模式
        patterns = [
            r'申请号[：:]\s*([\d\.CNcn]+)',
            r'专利号[：:]\s*([\d\.CNcn]+)',
            r'申请号\s*[:：]\s*([A-Z]{1,2}\d+[\d\-]+)',
        ]
        for p in patterns:
            m = re.search(p, text)
            if m: 
                meta.application_number = m.group(1).strip()
                break
        
        # 申请日
        m = re.search(r'申请日[：:]\s*([\d\-./年月日]+)', text)
        if m: meta.application_date = m.group(1).strip()
        
        # 发明名称 - 多种模式
        patterns = [
            r'(?:发明名称|名称|实用新型名称)[：:]\s*(.+?)(?:\n|$)',
            r'发明名称\s*[:：]\s*【?\d+】?\s*(.+?)(?:\n|$)',
        ]
        for p in patterns:
            m = re.search(p, text)
            if m: 
                meta.title = m.group(1).strip()
                if len(meta.title) > 3:
                    break
        
        # 如果没找到标题，尝试从摘要第一句提取
        if not meta.title:
            m = re.search(r'本发明公开了(?:一种)?(.+?)[，,]', text)
            if m:
                meta.title = m.group(1).strip()
        
        # 如果还没找到，使用文件名（去掉扩展名）
        if not meta.title:
            import os
            meta.title = os.path.basename(file_path) if 'file_path' in locals() else "未知专利"
        
        # 申请人 - 多种模式（增强版）
        patterns = [
            r'申请人[：:]\s*(.+?)(?:\n|$)',
            r'申请人\s*[:：]\s*【?\d+】?\s*(.+?)(?:\n|$)',
            r'申请单位[：:]\s*(.+?)(?:\n|$)',
            r'申请人\s*[:：]\s*\n?\s*(.+?)(?:\n|$)',
            r'专利申请人[：:]\s*(.+?)(?:\n|$)',
        ]
        for p in patterns:
            m = re.search(p, text, re.MULTILINE)
            if m: 
                meta.applicant = m.group(1).strip()
                # 清理多余字符
                meta.applicant = re.sub(r'【\d+】', '', meta.applicant).strip()
                # 处理多行情况
                meta.applicant = re.sub(r'\s+', '', meta.applicant)
                if len(meta.applicant) > 0:
                    break
        
        # 发明人 - 多种模式
        patterns = [
            r'发明人[：:]\s*(.+?)(?:\n|$)',
            r'发明人\s*[:：]\s*【?\d+】?\s*(.+?)(?:\n|$)',
            r'设计人[：:]\s*(.+?)(?:\n|$)',
            r'发明人\s*[:：]\s*\n?\s*(.+?)(?:\n|$)',
        ]
        for p in patterns:
            m = re.search(p, text, re.MULTILINE)
            if m: 
                meta.inventor = m.group(1).strip()
                # 清理多余字符
                meta.inventor = re.sub(r'【\d+】', '', meta.inventor).strip()
                # 处理多个发明人用逗号分隔的情况
                meta.inventor = re.sub(r'[、,，]', ', ', meta.inventor)
                if len(meta.inventor) > 0:
                    break
        
        # 代理人
        m = re.search(r'代理人[：:]\s*(.+?)(?:\n|$)', text)
        if m: meta.agent = m.group(1).strip()
        
        # IPC 分类
        patterns = [
            r'(?:IPC|分类号)[：:]\s*([\w/\s\.]+?)(?:\n|$)',
            r'国际专利分类[：:]\s*([\w/\s]+?)(?:\n|$)',
        ]
        for p in patterns:
            m = re.search(p, text)
            if m: 
                meta.ipc_classification = m.group(1).strip()
                break
        
        return meta

    def extract_patent_structure(self, text: str) -> PatentStructure:
        structure = PatentStructure()
        # 提取权利要求书 - 多种模式
        claims_match = re.search(r'权利要求书(.*?)(?=说明书|说明书摘要|$)', text, re.DOTALL)
        if claims_match:
            claims_text = claims_match.group(1).strip()
            structure.claims = self._parse_claims(claims_text)
        
        # 如果没找到权利要求书，尝试直接匹配编号的权利要求（如 1、2、...）
        if not structure.claims:
            # 查找所有编号的权利要求
            direct_claims_match = re.search(r'(?:^|\n)(\d+)[、\.].*?(?:其特征在于|包括|涉及).*?(?=\n\d+[、\.]|\n技术领域|$)', text, re.DOTALL | re.MULTILINE)
            if direct_claims_match:
                # 找到直接格式的权利要求
                claims_text = text[direct_claims_match.start():]
                structure.claims = self._parse_claims(claims_text)
        
        # 如果还没有，尝试简单模式 - 匹配 "数字、" 开头的行
        if not structure.claims:
            claims_lines = []
            for line in text.split('\n'):
                if re.match(r'^\d+[、\.]', line.strip()):
                    claims_lines.append(line.strip())
            if claims_lines:
                claims_text = '\n'.join(claims_lines)
                structure.claims = self._parse_claims(claims_text)
        # 提取说明书各部分
        sections = {
            "技术领域": r'技术领域(.*?)(?=背景技术|$)',
            "背景技术": r'背景技术(.*?)(?=发明内容|实用新型内容|$)',
            "发明内容": r'(?:发明内容|实用新型内容)(.*?)(?=附图说明|$)',
            "附图说明": r'附图说明(.*?)(?=具体实施方式|$)',
            "具体实施方式": r'具体实施方式(.*?)(?=权利要求|$)',
        }
        for name, pattern in sections.items():
            m = re.search(pattern, text, re.DOTALL)
            if m:
                structure.description[name] = m.group(1).strip()[:5000]
        structure.drawings_described = "附图说明" in structure.description
        # 摘要
        abs_match = re.search(r'(?:说明书摘要|摘要)(.*?)(?=$)', text, re.DOTALL)
        if abs_match:
            structure.abstract = abs_match.group(1).strip()[:2000]
        return structure

    def _parse_claims(self, claims_text: str) -> list[ClaimFeature]:
        claims = []
        # 按编号拆分
        parts = re.split(r'\n\s*(\d+)[\.\、]', claims_text)
        idx = 0
        for i in range(1, len(parts), 2):
            if i+1 < len(parts):
                num = int(parts[i])
                text = parts[i+1].strip()
                cf = ClaimFeature(claim_number=num, full_text=text)
                # 判断独立/从属
                dep_match = re.search(r'(?:根据|如)权利要求\s*(\d+)', text)
                if dep_match:
                    cf.claim_type = "dependent"
                    cf.references = [int(dep_match.group(1))]
                else:
                    cf.claim_type = "independent"
                # 拆分前序/特征
                char_match = re.search(r'其特征在于[：:,，]?\s*(.*)', text, re.DOTALL)
                if char_match:
                    cf.characterizing = char_match.group(1).strip()
                    cf.preamble = text[:char_match.start()].strip()
                claims.append(cf)
        if not claims and claims_text.strip():
            claims.append(ClaimFeature(claim_number=1, claim_type="independent", full_text=claims_text.strip()))
        return claims
