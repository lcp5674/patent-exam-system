"""审查规则引擎 - 动态规则体系（从数据库加载）"""
from __future__ import annotations
import re
import logging
import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from app.database.models import ExaminationRule
from .document_parser import PatentStructure, ClaimFeature

logger = logging.getLogger(__name__)


@dataclass
class RuleIssue:
    description: str = ""
    severity: str = "warning"  # error / warning / info
    location: str = ""
    legal_reference: str = ""
    # 新增：原始内容和建议修改内容
    original_content: str = ""  # 发现问题的原始内容片段
    suggested_content: str = ""  # 建议修改后的内容
    context_before: str = ""  # 问题内容前后的上下文
    context_after: str = ""


@dataclass
class RuleResult:
    rule_id: int = 0
    rule_name: str = ""
    display_name: str = ""  # 用于显示的中文名称
    rule_type: str = ""
    rule_category: str = ""
    level: int = 1
    passed: bool = True
    confidence: float = 1.0
    issues: list[RuleIssue] = field(default_factory=list)
    legal_basis: str = ""
    suggestions: list[str] = field(default_factory=list)
    check_pattern: str = ""
    severity: str = "warning"


@dataclass
class ExaminationReport:
    patent_id: str = ""
    results: list[RuleResult] = field(default_factory=list)
    overall_score: float = 100.0
    passed: bool = True
    summary: str = ""
    timestamp: str = ""
    rules_executed: int = 0

    def to_dict(self, include_details: bool = True) -> dict:
        """转换为字典，支持两种输出格式"""
        
        # 计算详细的得分统计
        total_rules = len(self.results)
        passed_rules = sum(1 for r in self.results if r.passed)
        failed_rules = total_rules - passed_rules
        
        # 按严重程度统计问题（只统计未通过的规则）
        error_count = sum(1 for r in self.results if not r.passed and r.severity == "error")
        warning_count = sum(1 for r in self.results if not r.passed and r.severity == "warning")
        # info级别的问题不计入统计，因为它们不影响通过/失败状态
        info_count = 0
        
        # 构建简洁格式（默认）
        result = {
            "patent_id": self.patent_id,
            "overall_score": self.overall_score,
            "passed": self.passed,
            "summary": self.summary,
            "timestamp": self.timestamp,
            "rules_executed": self.rules_executed,
            # 新增：得分详情
            "score_details": {
                "total_rules": total_rules,
                "passed": passed_rules,
                "failed": failed_rules,
                "pass_rate": round(passed_rules / total_rules * 100, 1) if total_rules > 0 else 0,
                "issues_by_severity": {
                    "error": error_count,
                    "warning": warning_count,
                    "info": info_count
                }
            }
        }
        
        # 如果需要详细信息
        if include_details:
            result["results"] = []
            for r in self.results:
                # 过滤issues：只显示error和warning级别的问题
                # info级别的问题作为附加信息，不阻塞审查
                filtered_issues = []
                if r.issues:
                    for i in r.issues:
                        # 只有error和warning才作为真正的问题
                        if i.severity in ("error", "warning"):
                            filtered_issues.append({
                                "description": i.description, 
                                "severity": i.severity, 
                                "location": i.location,
                                "legal_reference": i.legal_reference,
                                "original_content": i.original_content if i.original_content else None,
                                "suggested_content": i.suggested_content if i.suggested_content else None,
                                "context_before": i.context_before if i.context_before else None,
                                "context_after": i.context_after if i.context_after else None,
                            })
                        elif i.severity == "info" and not r.passed:
                            # info级别问题 + 规则未通过，也显示（但标记为info）
                            filtered_issues.append({
                                "description": i.description, 
                                "severity": i.severity, 
                                "location": i.location,
                                "legal_reference": i.legal_reference,
                                "original_content": i.original_content if i.original_content else None,
                                "suggested_content": i.suggested_content if i.suggested_content else None,
                                "context_before": i.context_before if i.context_before else None,
                                "context_after": i.context_after if i.context_after else None,
                            })
                
                result["results"].append({
                    "rule_id": r.rule_id,
                    "rule_name": r.rule_name,
                    "display_name": r.display_name or r.rule_name,
                    "rule_type": r.rule_type,
                    "rule_category": r.rule_category,
                    "level": r.level,
                    "passed": r.passed,
                    "confidence": r.confidence,
                    "severity": r.severity,
                    "issues": filtered_issues,
                    "legal_basis": r.legal_basis or None, 
                    "suggestions": r.suggestions if r.suggestions else [],
                    "check_pattern": r.check_pattern,
                    # 新增：规则得分说明
                    "score_explanation": self._explain_rule_score(r)
                })
        
        return result
    
    def _explain_rule_score(self, rule_result: "RuleResult") -> str:
        """解释单条规则的得分逻辑"""
        if rule_result.passed:
            return f"✓ 该规则检查通过 (置信度: {rule_result.confidence:.0%})"
        else:
            issues_count = len(rule_result.issues)
            severity = rule_result.severity
            if severity == "error":
                return f"✗ 发现{issues_count}个错误问题，需要修改"
            elif severity == "warning":
                return f"⚠ 发现{issues_count}个警告问题，建议优化"
            else:
                return f"ℹ 发现{issues_count}个提示信息，建议关注"
    
    def to_readable_summary(self) -> str:
        """生成人类可读的摘要"""
        lines = []
        lines.append("=" * 50)
        lines.append(f"专利审查报告")
        lines.append("=" * 50)
        lines.append(f"专利ID: {self.patent_id}")
        lines.append(f"审查时间: {self.timestamp}")
        lines.append("")
        
        # 得分概览
        lines.append(f"【总体评分】: {self.overall_score:.1f}分")
        lines.append(f"审查结论: {'通过' if self.passed else '需要修改'}")
        lines.append("")
        
        # 得分详情
        total_rules = len(self.results)
        passed_rules = sum(1 for r in self.results if r.passed)
        failed_rules = total_rules - passed_rules
        lines.append(f"【规则执行情况】")
        lines.append(f"  - 总规则数: {total_rules}")
        lines.append(f"  - 通过: {passed_rules}")
        lines.append(f"  - 未通过: {failed_rules}")
        lines.append(f"  - 通过率: {passed_rules/total_rules*100:.1f}%" if total_rules > 0 else "  - 通过率: N/A")
        lines.append("")
        
        # 未通过的规则详情
        failed_results = [r for r in self.results if not r.passed]
        if failed_results:
            lines.append(f"【需要关注的问题】")
            for r in failed_results:
                lines.append(f"  • {r.display_name or r.rule_name}")
                if r.issues:
                    for issue in r.issues:
                        lines.append(f"    - 问题: {issue.description}")
                        if issue.location:
                            lines.append(f"    - 位置: {issue.location}")
                        if issue.suggested_content:
                            lines.append(f"    - 建议: {issue.suggested_content}")
                lines.append("")
        
        # 建议
        all_suggestions = []
        for r in failed_results:
            all_suggestions.extend(r.suggestions)
        if all_suggestions:
            lines.append(f"【修改建议】")
            for suggestion in all_suggestions[:5]:  # 限制显示数量
                lines.append(f"  • {suggestion}")
        
        lines.append("=" * 50)
        return "\n".join(lines)


class RuleEngine:
    """动态审查规则引擎 - 从数据库加载规则"""

    def __init__(self):
        self._rules_cache: list[ExaminationRule] = []
        self._cache_time: datetime = None
        self._cache_ttl_seconds = 60  # 缓存1分钟

    async def _load_rules(self, db: AsyncSession, force_reload: bool = False) -> list[ExaminationRule]:
        """从数据库加载规则"""
        now = datetime.now()
        
        # 检查缓存
        if (not force_reload 
            and self._rules_cache 
            and self._cache_time 
            and (now - self._cache_time).total_seconds() < self._cache_ttl_seconds):
            return self._rules_cache
        
        # 从数据库加载活跃规则
        result = await db.execute(
            select(ExaminationRule)
            .where(ExaminationRule.is_active == True)
            .order_by(ExaminationRule.priority.desc())
        )
        rules = list(result.scalars().all())
        
        # 更新缓存
        self._rules_cache = rules
        self._cache_time = now
        logger.info(f"[RuleEngine] 加载了 {len(rules)} 条活跃规则")
        
        return rules

    async def execute_rules(
        self, 
        patent_id: str, 
        structure: PatentStructure, 
        full_text: str = "", 
        level: int = 2,
        db: AsyncSession = None,
        provider_manager = None,
        enable_llm_comprehensive: bool = False,
        llm_provider: str = None
    ) -> ExaminationReport:
        """执行规则检查 - 动态从数据库加载
        
        Args:
            patent_id: 专利ID
            structure: 专利文档结构
            full_text: 完整文本
            level: 规则级别 (1/2/3)
            db: 数据库会话
            provider_manager: AI提供商管理器（用于LLM增强检查）
            enable_llm_comprehensive: 是否启用LLM综合审查（提升完整度）
            llm_provider: 指定的LLM提供商
        """
        
        # 如果没有db session，使用内存中的备用规则
        if db is None:
            logger.warning("[RuleEngine] 未提供数据库会话，使用默认规则")
            return await self._execute_fallback_rules(patent_id, structure, full_text, level)
        
        # 动态加载规则
        rules = await self._load_rules(db)
        
        results: list[RuleResult] = []
        ai_rules_issues = {}  # 存储AI规则的结果
        
        # 先执行非AI规则
        for rule in rules:
            # 根据level过滤
            rule_level = 1 if rule.rule_category == "level1" else 2 if rule.rule_category == "level2" else 3
            if rule_level > level:
                continue
            
            check_pattern = rule.check_pattern or "keyword"
            
            # AI规则单独处理
            if check_pattern == "ai":
                if provider_manager:
                    issues = await self._check_ai(rule, structure, full_text, provider_manager)
                    ai_rules_issues[rule.id] = issues
                else:
                    ai_rules_issues[rule.id] = []
                continue
            
            # 执行规则检查
            result = await self._execute_single_rule(rule, structure, full_text)
            results.append(result)
            
            # 更新规则执行统计
            await self._update_rule_stats(db, rule.id)
        
        # 处理AI规则结果
        for rule in rules:
            check_pattern = rule.check_pattern or "keyword"
            if check_pattern != "ai":
                continue
            
            rule_level = 1 if rule.rule_category == "level1" else 2 if rule.rule_category == "level2" else 3
            if rule_level > level:
                continue
            
            issues = ai_rules_issues.get(rule.id, [])
            passed = len([i for i in issues if i.severity == "error"]) == 0
            display_name = self._generate_display_name(rule)
            
            result = RuleResult(
                rule_id=rule.id,
                rule_name=rule.rule_name,
                display_name=display_name,
                rule_type=rule.rule_type,
                rule_category=rule.rule_category,
                level=rule_level,
                passed=passed,
                confidence=0.9,  # LLM检查置信度较高
                issues=issues,
                legal_basis=rule.legal_basis or "",
                suggestions=rule.fix_suggestion.split("\n") if rule.fix_suggestion else [],
                check_pattern="ai",
                severity=rule.severity or "warning",
            )
            results.append(result)
            
            # 更新规则执行统计
            await self._update_rule_stats(db, rule.id)
        
        # 可选的LLM综合审查（提升完整度，发现规则库未覆盖的问题）
        if enable_llm_comprehensive and provider_manager:
            try:
                comprehensive_issues = await self.comprehensive_llm_review(
                    structure, full_text, provider_manager, llm_provider
                )
                
                if comprehensive_issues:
                    # 创建综合审查结果
                    comp_result = RuleResult(
                        rule_id=-1,  # 综合审查无对应规则
                        rule_name="AI综合审查",
                        display_name="AI综合审查（规则库外问题发现）",
                        rule_type="comprehensive",
                        rule_category="level3",
                        level=3,
                        passed=len([i for i in comprehensive_issues if i.severity == "error"]) == 0,
                        confidence=0.85,
                        issues=comprehensive_issues,
                        legal_basis="AI智能发现",
                        suggestions=["请根据AI审查意见修改"],
                        check_pattern="ai",
                        severity="info",
                    )
                    results.append(comp_result)
                    
            except Exception as e:
                logger.warning(f"[RuleEngine] 综合LLM审查失败: {e}")
        
        # 计算得分
        total = len(results)
        passed_count = sum(1 for r in results if r.passed)
        score = (passed_count / total * 100) if total > 0 else 0
        all_passed = all(r.passed for r in results)

        issues_summary = []
        for r in results:
            if not r.passed:
                issue_desc = "; ".join(i.description for i in r.issues)
                issues_summary.append(f"- {r.rule_name}: {issue_desc}")

        return ExaminationReport(
            patent_id=patent_id, 
            results=results, 
            overall_score=round(score, 1), 
            passed=all_passed,
            summary="\n".join(issues_summary) if issues_summary else "所有规则检查通过",
            timestamp=datetime.now().isoformat(),
            rules_executed=total,
        )

    def _calculate_confidence(
        self, 
        check_pattern: str, 
        issues: list[RuleIssue],
        rule_content: dict
    ) -> float:
        """
        动态计算规则检查的置信度
        
        置信度计算逻辑：
        - AI检查：默认0.9（较高）
        - 正则检查：默认0.85
        - 关键词检查：根据是否找到关键词和找到的数量动态调整
        - 结构化检查：根据检查结果动态调整
        - 问题数量越多，置信度越低
        """
        base_confidence = {
            "ai": 0.9,
            "regex": 0.85,
            "keyword": 0.8,
            "structural": 0.85,
            "length": 0.75,
        }.get(check_pattern, 0.8)
        
        # 根据问题数量调整
        error_count = sum(1 for i in issues if i.severity == "error")
        warning_count = sum(1 for i in issues if i.severity == "warning")
        info_count = sum(1 for i in issues if i.severity == "info")
        
        total_issues = error_count + warning_count + info_count
        
        # 有error级别问题，置信度大幅降低
        if error_count > 0:
            penalty = min(0.3, error_count * 0.1)
            confidence = base_confidence - penalty
        # 有warning级别问题，轻微降低
        elif warning_count > 0:
            penalty = min(0.15, warning_count * 0.05)
            confidence = base_confidence - penalty
        # 只有info级别问题，基本不影响
        elif info_count > 0:
            confidence = base_confidence
        # 没有问题，根据检查类型可能有小幅提升
        else:
            # 如果有文本内容作为支撑，置信度略高
            if rule_content.get("keywords") and len(rule_content.get("keywords", [])) > 0:
                confidence = min(0.95, base_confidence + 0.05)
            else:
                confidence = base_confidence
        
        return round(max(0.1, min(1.0, confidence)), 2)

    async def _execute_single_rule(
        self, 
        rule: ExaminationRule, 
        structure: PatentStructure, 
        full_text: str
    ) -> RuleResult:
        """执行单条规则"""
        
        check_pattern = rule.check_pattern or "keyword"
        rule_content = rule.rule_content or {}
        
        # 根据检查模式执行
        if check_pattern == "regex":
            issues = await self._check_regex(rule, full_text, structure, rule_content)
        elif check_pattern == "keyword":
            issues = await self._check_keyword(rule, full_text, structure, rule_content)
        elif check_pattern == "structural":
            issues = await self._check_structural(rule, structure, rule_content)
        elif check_pattern == "ai":
            # AI 检查需要传入 provider_manager
            issues = []  # AI检查在 execute_rules 中统一处理
        else:
            # 默认使用结构化检查
            issues = await self._check_structural(rule, structure, rule_content)
        
        # 判断是否通过：只有error级别的问题才导致不通过
        passed = len([i for i in issues if i.severity == "error"]) == 0
        
        # 动态计算置信度
        confidence = self._calculate_confidence(check_pattern, issues, rule_content)
        
        # 生成中文显示名称
        display_name = self._generate_display_name(rule)
        
        return RuleResult(
            rule_id=rule.id,
            rule_name=rule.rule_name,
            display_name=display_name,
            rule_type=rule.rule_type,
            rule_category=rule.rule_category,
            level=1 if rule.rule_category == "level1" else 2 if rule.rule_category == "level2" else 3,
            passed=passed,
            confidence=confidence,
            issues=issues,
            legal_basis=rule.legal_basis or "",
            suggestions=rule.fix_suggestion.split("\n") if rule.fix_suggestion else [],
            check_pattern=check_pattern,
            severity=rule.severity or "warning",
        )
    
    def _generate_display_name(self, rule: ExaminationRule) -> str:
        """生成中文显示名称"""
        # 规则名称通常是中文的，如果是英文则尝试翻译
        rule_name = rule.rule_name or ""
        
        # 如果已经是中文，直接返回
        if any('\u4e00' <= c <= '\u9fff' for c in rule_name):
            return rule_name
        
        # 否则添加中文前缀
        type_map = {
            "formal": "形式",
            "substantive": "实质",
            "subject_matter": "客体",
            "clarity": "清楚性",
            "support": "支持性",
            "sufficiency": "充分公开",
            "unity": "单一性",
            "dependency": "依赖关系",
            "drawings": "附图",
            "sequence": "序列表",
            "effect": "技术效果",
            "background": "背景技术",
            "essential": "必要特征",
            "embodiment": "实施方式",
            "correspondence": "对应性",
            "consistency": "一致性",
            "problem": "技术问题",
            "example": "实施例",
            "range": "数值范围",
            "marking": "附图标记",
            "abbreviation": "缩写",
            "scope": "保护范围",
            "novelty": "新颖性",
            "commerce": "商业宣传",
        }
        
        rule_type = rule.rule_type or ""
        type_prefix = type_map.get(rule_type, "")
        
        return f"{type_prefix}{rule_name}" if type_prefix else rule_name

    async def _check_regex(
        self, 
        rule: ExaminationRule, 
        text: str, 
        structure: PatentStructure,
        rule_content: dict
    ) -> list[RuleIssue]:
        """正则表达式检查"""
        issues = []
        pattern = rule_content.get("pattern", "")
        
        if not pattern:
            return issues
            
        try:
            regex = re.compile(pattern, re.IGNORECASE)
            matches = regex.finditer(text)
            
            if rule_content.get("should_match", True):
                if not regex.search(text):
                    issues.append(RuleIssue(
                        rule.error_message or f"未找到匹配项",
                        rule.severity or "warning",
                        rule_content.get("location", "全文"),
                        rule.legal_basis or ""
                    ))
            else:
                # 找到了不应该存在的内容，提取实际匹配的内容
                for match in regex.finditer(text):
                    matched_text = match.group()
                    # 获取上下文
                    start = max(0, match.start() - 50)
                    end = min(len(text), match.end() + 50)
                    context_before = text[start:match.start()]
                    context_after = text[match.end():end]
                    
                    issues.append(RuleIssue(
                        rule.error_message or f"发现不允许的内容: {matched_text[:50]}",
                        rule.severity or "warning",
                        rule_content.get("location", "全文"),
                        rule.legal_basis or "",
                        original_content=matched_text[:200],  # 限制长度
                        suggested_content=rule_content.get("suggested_replacement", "请删除或修改该内容"),
                        context_before=context_before,
                        context_after=context_after,
                    ))
        except re.error as e:
            logger.warning(f"[RuleEngine] 正则表达式错误: {e}")
            
        return issues

    async def _check_keyword(
        self, 
        rule: ExaminationRule, 
        text: str, 
        structure: PatentStructure,
        rule_content: dict
    ) -> list[RuleIssue]:
        """关键词检查"""
        issues = []
        keywords = rule_content.get("keywords", [])
        should_contain = rule_content.get("should_contain", True)
        target_field = rule_content.get("field", "full_text")
        
        # 获取要检查的文本
        if target_field == "title":
            check_text = ""  # title 在 metadata 中，不在 structure 中
        elif target_field == "abstract":
            check_text = structure.abstract or ""
        elif target_field == "claims":
            # 保留权利要求的编号和结构
            check_text = "\n".join(f"权利要求{c.claim_number}: {c.full_text}" for c in structure.claims) if structure.claims else ""
        elif target_field == "description":
            # 保留说明书的章节结构
            desc_parts = []
            for section_name, section_content in structure.description.items():
                if section_content:
                    desc_parts.append(f"【{section_name}】\n{section_content}")
            check_text = "\n\n".join(desc_parts)
        else:
            check_text = text
        
        # 智能规则触发优化：如果对应字段为空，跳过不相关规则
        # 避免在没有内容的情况下误触发错误
        if not check_text.strip():
            # 对于空文本，关键词类规则跳过
            return []
        
        # 记录检查的文本长度
        text_length = len(check_text)
        
        if should_contain:
            # 应该包含关键词：检查是否找到
            found_keywords = [kw for kw in keywords if kw in check_text]
            
            if not found_keywords:
                # 没找到任何关键词 - 记录问题
                # 尝试找到文本中相关的内容作为位置参考
                location_hint = self._find_relevant_section(target_field, structure, text)
                
                issues.append(RuleIssue(
                    description=rule.error_message or f"未找到必要关键词: {keywords}",
                    severity=rule.severity or "warning",
                    location=f"{target_field} (全文长度: {text_length}字符)",
                    legal_reference=rule.legal_basis or "",
                    original_content=f"期望关键词: {keywords}",
                    suggested_content=f"请在{location_hint}中添加相关技术描述",
                ))
            else:
                # 找到了关键词 - 记录找到的位置作为参考
                found_locations = []
                for kw in found_keywords:
                    idx = check_text.find(kw)
                    if idx >= 0:
                        # 提取上下文（更多字符以便理解）
                        start = max(0, idx - 100)
                        end = min(len(check_text), idx + len(kw) + 100)
                        context = check_text[start:end]
                        found_locations.append(f"位置{idx}: ...{context}...")
                
                # 找到关键词但规则仍需更多内容
                if len(found_keywords) < len(keywords):
                    missing = [kw for kw in keywords if kw not in found_keywords]
                    issues.append(RuleIssue(
                        description=f"部分关键词未找到: {missing}",
                        severity="info",
                        location=f"{target_field} (已找到: {len(found_keywords)}/{len(keywords)}个关键词)",
                        legal_reference=rule.legal_basis or "",
                        original_content=f"已找到: {found_keywords}, 缺失: {missing}",
                        suggested_content="建议补充缺失的关键词以增强描述",
                        context_before=f"已找到关键词的位置: {', '.join(found_locations[:2])}" if found_locations else "",
                    ))
        else:
            # 不应该包含关键词：检查是否包含禁用词
            found_keywords = [kw for kw in keywords if kw in check_text]
            
            if found_keywords:
                for kw in found_keywords:
                    # 找到关键词位置，提取上下文
                    idx = check_text.find(kw)
                    if idx >= 0:
                        start = max(0, idx - 80)
                        end = min(len(check_text), idx + len(kw) + 80)
                        context_before = check_text[start:idx]
                        context_after = check_text[idx + len(kw):end]
                        
                        issues.append(RuleIssue(
                            description=rule.error_message or f"发现禁用关键词: {found_keywords}",
                            severity=rule.severity or "warning",
                            location=f"{target_field} 位置约{idx}-{idx+len(kw)}字符",
                            legal_reference=rule.legal_basis or "",
                            original_content=kw,
                            suggested_content=rule_content.get("suggested_replacement", "请删除或替换该关键词"),
                            context_before=context_before,
                            context_after=context_after,
                        ))
        
        return issues
    
    def _find_relevant_section(self, target_field: str, structure: PatentStructure, full_text: str) -> str:
        """查找相关章节作为位置提示"""
        if target_field == "description":
            # 返回说明书中已有的章节
            if structure.description:
                sections = list(structure.description.keys())
                return f"说明书{', '.join(sections[:3])}章节" if sections else "说明书"
            return "说明书"
        elif target_field == "claims":
            count = len(structure.claims) if structure.claims else 0
            return f"权利要求书 (共{count}条)" if count > 0 else "权利要求书"
        elif target_field == "abstract":
            return "摘要"
        else:
            return target_field

    async def _check_structural(
        self, 
        rule: ExaminationRule, 
        structure: PatentStructure,
        rule_content: dict
    ) -> list[RuleIssue]:
        """结构化检查"""
        issues = []
        check_type = rule_content.get("type", "")
        
        # 智能规则触发优化：跳过不相关的结构检查
        # 1. 生物材料相关规则只有当专利属于生物领域时才触发
        if check_type in ["biological_material", "sequence_list", "genetic_resource"]:
            technical_field = (structure.technical_field or "").lower()
            if not any(keyword in technical_field for keyword in ["生物", "基因", "遗传", "蛋白", "核酸", "细胞", "微生物"]):
                return []
        
        # 2. PCT相关规则只有当是PCT申请时才触发
        if check_type == "pct_formal":
            if not structure.application_number or not structure.application_number.startswith("PCT"):
                return []
        
        if check_type == "document_completeness":
            # 文档完整性检查
            required = rule_content.get("required_fields", [])
            for field_name in required:
                if field_name == "claims" and not structure.claims:
                    issues.append(RuleIssue(
                        "缺少权利要求书", 
                        "error", 
                        "权利要求书", 
                        rule.legal_basis or "专利法第26条",
                        original_content="[无权利要求书]",
                        suggested_content="请添加权利要求书，包括独立权利要求和从属权利要求",
                    ))
                elif field_name == "description" and not structure.description:
                    issues.append(RuleIssue(
                        "缺少说明书", 
                        "error", 
                        "说明书", 
                        rule.legal_basis or "专利法第26条",
                        original_content="[无说明书]",
                        suggested_content="请添加完整的说明书，包括技术领域、背景技术、发明内容、具体实施方式等章节",
                    ))
                elif field_name == "abstract" and not structure.abstract:
                    issues.append(RuleIssue(
                        "缺少摘要", 
                        "warning", 
                        "摘要", 
                        rule.legal_basis or "专利法实施细则第23条",
                        original_content="[无摘要]",
                        suggested_content="请添加摘要，50-300字，简明扼要说明发明技术方案",
                    ))
                elif field_name == "drawings" and not structure.drawings_described:
                    issues.append(RuleIssue(
                        "缺少附图说明", 
                        "warning", 
                        "附图", 
                        rule.legal_basis or "专利法实施细则第17条",
                        original_content="[无附图]",
                        suggested_content="请提供说明书附图，清楚表达技术方案",
                    ))
                    
        elif check_type == "sections_completeness":
            # 章节完整性检查
            required_sections = rule_content.get("required_sections", [])
            desc_text = structure.description or {}
            for section in required_sections:
                section_content = desc_text.get(section, "")
                if not section_content:
                    issues.append(RuleIssue(
                        f"说明书缺少 [{section}] 部分",
                        rule.severity or "warning",
                        "说明书",
                        rule.legal_basis or "专利审查指南",
                        original_content="[无此章节]",
                        suggested_content=f"请添加 {section} 部分的内容",
                    ))
                elif len(section_content) < 50:
                    issues.append(RuleIssue(
                        f"说明书 [{section}] 部分内容过短（{len(section_content)}字）",
                        rule.severity or "warning",
                        "说明书",
                        rule.legal_basis or "专利审查指南",
                        original_content=section_content[:100] + "..." if len(section_content) > 100 else section_content,
                        suggested_content="请详细描述该部分内容，至少50字以上",
                    ))
                    
        elif check_type == "claims_structure":
            # 权利要求结构检查
            claims = structure.claims or []
            if not claims:
                issues.append(RuleIssue(
                    "未找到权利要求", 
                    "error", 
                    "权利要求书", 
                    rule.legal_basis or "专利法第26条",
                    original_content="[无权利要求]",
                    suggested_content="请添加权利要求书，包括独立权利要求和从属权利要求",
                ))
            else:
                # 检查独立权利要求
                has_independent = any(c.claim_type == "independent" for c in claims)
                if not has_independent:
                    issues.append(RuleIssue(
                        "未找到独立权利要求", 
                        "error", 
                        "权利要求书", 
                        rule.legal_basis or "专利审查指南",
                        original_content="[只有从属权利要求]",
                        suggested_content="请添加至少一个独立权利要求",
                    ))
                
                # 检查编号连续性
                nums = sorted([c.claim_number for c in claims])
                expected = list(range(1, len(nums) + 1))
                if nums != expected:
                    issues.append(RuleIssue(
                        f"权利要求编号不连续: {nums}", 
                        "warning", 
                        "权利要求书", 
                        rule.legal_basis or "专利审查指南",
                        original_content=str(nums),
                        suggested_content="请使用连续的阿拉伯数字编号：1, 2, 3...",
                    ))
                    
        elif check_type == "abstract_length":
            # 摘要长度检查
            abstract_len = len(structure.abstract or "")
            min_len = rule_content.get("min_length", 50)
            max_len = rule_content.get("max_length", 300)
            
            if abstract_len < min_len:
                issues.append(RuleIssue(
                    f"摘要内容过短（{abstract_len}字），少于{min_len}字", 
                    "warning", 
                    "摘要", 
                    rule.legal_basis or "专利法实施细则第23条",
                    original_content=structure.abstract or "[无摘要]",
                    suggested_content=f"请将摘要扩展至{min_len}-{max_len}字",
                ))
            elif abstract_len > max_len:
                issues.append(RuleIssue(
                    f"摘要内容过长（{abstract_len}字），超过{max_len}字", 
                    "error", 
                    "摘要", 
                    rule.legal_basis or "专利法实施细则第23条",
                    original_content=structure.abstract[:200] + "..." if len(structure.abstract or "") > 200 else structure.abstract,
                    suggested_content=f"请将摘要精简至{max_len}字以内",
                ))
        
        return issues

    async def _check_ai(
        self, 
        rule: ExaminationRule, 
        structure: PatentStructure,
        full_text: str,
        provider_manager=None
    ) -> list[RuleIssue]:
        """使用 LLM 进行语义级别的规则检查"""
        issues = []
        
        if provider_manager is None:
            logger.warning("[RuleEngine] 未配置 LLM 提供商，跳过 AI 检查")
            return issues
        
        rule_type = rule.rule_type or "formal"
        rule_content = rule.rule_content or {}
        
        # 构建检查上下文
        context = self._build_llm_context(structure, full_text)
        
        try:
            # 根据规则类型选择不同的 prompt
            from app.ai.prompts.rule_enhancement_prompts import (
                PATENT_EXAMINER_SYSTEM,
                get_llm_prompt
            )
            
            prompt = get_llm_prompt(rule_type, {
                **context,
                "rule_requirement": rule.description or rule.rule_name,
                "legal_basis": rule.legal_basis or "",
            })
            
            messages = [
                {"role": "system", "content": PATENT_EXAMINER_SYSTEM},
                {"role": "user", "content": prompt}
            ]
            
            # 使用规则指定的模型，或使用默认模型
            model = rule.ai_model or None
            response = await provider_manager.chat(messages, model=model)
            
            # 解析 LLM 响应
            issues = self._parse_llm_response(response.content, rule)
            
            logger.info(f"[RuleEngine] AI 检查完成，规则: {rule.rule_name}, 发现 {len(issues)} 个问题")
            
        except Exception as e:
            logger.warning(f"[RuleEngine] AI 检查失败: {rule.rule_name}, 错误: {e}")
        
        return issues

    def _build_llm_context(self, structure: PatentStructure, full_text: str) -> dict:
        """构建 LLM 检查所需的上下文"""
        # 获取权利要求文本
        claims_text = ""
        if structure.claims:
            claims_list = []
            for claim in structure.claims:
                claim_text = f"权利要求{claim.claim_number}: {claim.full_text}"
                if claim.claim_type:
                    claim_text += f" ({claim.claim_type})"
                claims_list.append(claim_text)
            claims_text = "\n".join(claims_list)
        
        # 获取说明书文本（限制长度以避免超限）
        description_text = ""
        if structure.description:
            desc_parts = []
            for section, content in structure.description.items():
                if content:
                    desc_parts.append(f"【{section}】\n{content[:500]}")
            description_text = "\n\n".join(desc_parts)
        
        return {
            "title": "",  # title 在 metadata 中，此处不可用
            "abstract": structure.abstract or "",
            "claims": claims_text,
            "description": description_text,
            "technical_field": "",  # title 在 metadata 中，此处不可用
        }

    def _parse_llm_response(self, response_content: str, rule: ExaminationRule) -> list[RuleIssue]:
        """解析 LLM 响应，提取问题和建议"""
        issues = []
        
        try:
            # 尝试提取 JSON
            # 查找 JSON 块
            json_start = response_content.find("```json")
            if json_start != -1:
                json_end = response_content.find("```", json_start + 7)
                json_str = response_content[json_start + 7:json_end].strip()
            else:
                # 尝试直接解析
                json_str = response_content.strip()
            
            data = json.loads(json_str)
            
            # 检查是否通过
            passed = data.get("passed", True)
            if passed:
                return issues
            
            # 解析问题列表
            issues_data = data.get("issues", [])
            for issue_data in issues_data:
                issue = RuleIssue(
                    description=issue_data.get("problem", ""),
                    severity=issue_data.get("severity", rule.severity or "warning"),
                    location=issue_data.get("location", ""),
                    legal_reference=issue_data.get("legal_reference", rule.legal_basis or ""),
                    original_content=issue_data.get("original_content", ""),
                    suggested_content=issue_data.get("suggested_content", ""),
                )
                issues.append(issue)
                
        except json.JSONDecodeError as e:
            logger.warning(f"[RuleEngine] 解析 LLM 响应失败: {e}")
            # 如果解析失败，尝试从文本中提取信息
            issues = self._parse_llm_text_fallback(response_content, rule)
        except Exception as e:
            logger.warning(f"[RuleEngine] 处理 LLM 响应失败: {e}")
        
        return issues

    def _parse_llm_text_fallback(self, text: str, rule: ExaminationRule) -> list[RuleIssue]:
        """当 JSON 解析失败时，从文本中提取信息"""
        issues = []
        
        # 简单的文本解析作为后备
        if "问题" in text or "不符合" in text or "不通过" in text.lower():
            issue = RuleIssue(
                description=f"AI 审查发现问题: {rule.rule_name}",
                severity=rule.severity or "warning",
                location="全文",
                legal_reference=rule.legal_basis or "",
                original_content=text[:200],
                suggested_content=rule.fix_suggestion or "请根据审查意见修改",
            )
            issues.append(issue)
        
        return issues

    async def comprehensive_llm_review(
        self,
        structure: PatentStructure,
        full_text: str,
        provider_manager=None,
        provider: str = None
    ) -> list[RuleIssue]:
        """全面的 LLM 审查 - 发现规则库未覆盖的问题"""
        issues = []
        
        if provider_manager is None:
            logger.warning("[RuleEngine] 未配置 LLM 提供商，跳过综合审查")
            return issues
        
        try:
            from app.ai.prompts.rule_enhancement_prompts import (
                PATENT_EXAMINER_SYSTEM,
                COMPREHENSIVE_REVIEW_PROMPT
            )
            
            context = self._build_llm_context(structure, full_text)
            
            prompt = COMPREHENSIVE_REVIEW_PROMPT.format(
                title=context["title"],
                abstract=context["abstract"],
                claims=context["claims"],
                description=context["description"],
            )
            
            messages = [
                {"role": "system", "content": PATENT_EXAMINER_SYSTEM},
                {"role": "user", "content": prompt}
            ]
            
            response = await provider_manager.chat(messages, provider=provider)
            
            # 解析响应
            issues = self._parse_comprehensive_response(response.content)
            
            logger.info(f"[RuleEngine] 综合 LLM 审查完成，发现 {len(issues)} 个额外问题")
            
        except Exception as e:
            logger.warning(f"[RuleEngine] 综合 LLM 审查失败: {e}")
        
        return issues

    def _parse_comprehensive_response(self, response_content: str) -> list[RuleIssue]:
        """解析综合审查响应"""
        issues = []
        
        try:
            # 查找 JSON
            json_start = response_content.find("```json")
            if json_start != -1:
                json_end = response_content.find("```", json_start + 7)
                json_str = response_content[json_start + 7:json_end].strip()
            else:
                json_str = response_content.strip()
            
            data = json.loads(json_str)
            
            issues_data = data.get("issues", [])
            for issue_data in issues_data:
                issue = RuleIssue(
                    description=issue_data.get("problem", ""),
                    severity=issue_data.get("severity", "warning"),
                    location=issue_data.get("location", ""),
                    legal_reference=issue_data.get("legal_reference", ""),
                    original_content=issue_data.get("original_content", ""),
                    suggested_content=issue_data.get("suggested_content", ""),
                )
                issues.append(issue)
                
        except Exception as e:
            logger.warning(f"[RuleEngine] 解析综合审查响应失败: {e}")
        
        return issues

    async def _update_rule_stats(self, db: AsyncSession, rule_id: int):
        """更新规则执行统计"""
        try:
            await db.execute(
                update(ExaminationRule)
                .where(ExaminationRule.id == rule_id)
                .values(
                    execution_count=ExaminationRule.execution_count + 1,
                    last_executed_at=datetime.now()
                )
            )
            await db.flush()
        except Exception as e:
            logger.warning(f"[RuleEngine] 更新规则统计失败: {e}")

    async def _execute_fallback_rules(
        self, 
        patent_id: str, 
        structure: PatentStructure, 
        full_text: str, 
        level: int
    ) -> ExaminationReport:
        """备用规则执行（当没有数据库连接时）"""
        # 这里可以保留一些基本的硬编码规则作为fallback
        results = []
        
        # 简单的文档完整性检查
        issues = []
        if not structure.claims:
            issues.append(RuleIssue("缺少权利要求书", "error", "权利要求书", "专利法第26条"))
        if not structure.description:
            issues.append(RuleIssue("缺少说明书", "error", "说明书", "专利法第26条"))
        
        results.append(RuleResult(
            rule_id=0,
            rule_name="文档完整性检查（静态）",
            rule_type="formal",
            rule_category="level1",
            level=1,
            passed=len(issues) == 0,
            confidence=0.95,
            issues=issues,
            legal_basis="专利法第26条",
            severity="error"
        ))

        return ExaminationReport(
            patent_id=patent_id,
            results=results,
            overall_score=50.0 if issues else 100.0,
            passed=len(issues) == 0,
            summary="规则引擎未连接数据库，仅执行基本检查",
            timestamp=datetime.now().isoformat(),
            rules_executed=len(results),
        )

    async def reload_rules(self, db: AsyncSession):
        """强制重新加载规则"""
        await self._load_rules(db, force_reload=True)
        logger.info("[RuleEngine] 规则已强制重新加载")


# 全局单例
rule_engine = RuleEngine()
