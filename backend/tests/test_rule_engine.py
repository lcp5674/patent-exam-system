"""
规则引擎单元测试
"""
import pytest
from datetime import datetime

from app.database.models import ExaminationRule
from app.services.rule_engine import (
    RuleEngine, RuleIssue, RuleResult, ExaminationReport
)
from app.services.document_parser import PatentStructure, ClaimFeature


@pytest.mark.unit
class TestRuleEngineUnits:
    """规则引擎单元测试"""

    def test_rule_issue_creation(self):
        """测试RuleIssue创建"""
        issue = RuleIssue(
            description="缺少标题",
            severity="error",
            location="专利名称",
            legal_reference="专利法第26条第1款"
        )

        assert issue.description == "缺少标题"
        assert issue.severity == "error"
        assert issue.location == "专利名称"

    def test_rule_result_creation(self):
        """测试RuleResult创建"""
        result = RuleResult(
            rule_id=1,
            rule_name="形式审查规则",
            rule_type="formal",
            passed=True,
            confidence=0.95,
            issues=[]
        )

        assert result.passed is True
        assert result.confidence == 0.95

    def test_examination_report_creation(self):
        """测试ExaminationReport创建"""
        report = ExaminationReport(
            patent_id="2024100100001",
            results=[],
            overall_score=100.0,
            passed=True,
            summary="所有检查通过",
            timestamp=datetime.now().isoformat(),
            rules_executed=5
        )

        assert report.passed is True
        assert report.overall_score == 100.0
        assert report.rules_executed == 5

    def test_report_to_dict(self):
        """测试报告转换为字典"""
        report = ExaminationReport(
            patent_id="2024100100001",
            results=[],
            overall_score=100.0,
            passed=True,
            summary="所有检查通过",
            timestamp=datetime.now().isoformat(),
            rules_executed=5
        )

        result_dict = report.to_dict()

        assert result_dict["patent_id"] == "2024100100001"
        assert result_dict["overall_score"] == 100.0
        assert result_dict["passed"] is True
        # 检查新增的得分详情
        assert "score_details" in result_dict
        assert result_dict["score_details"]["total_rules"] == 0


@pytest.mark.unit
class TestDocumentStructure:
    """文档结构测试"""

    def test_patent_structure_creation(self):
        """测试PatentStructure创建"""
        structure = PatentStructure(
            request_info="测试专利信息",
            abstract="这是摘要内容",
            claims=[
                ClaimFeature(
                    claim_number=1,
                    claim_type="independent",
                    full_text="权利要求1的技术方案..."
                )
            ],
            description={
                "技术领域": "本发明涉及人工智能领域",
                "背景技术": "现有技术..."
            }
        )

        assert structure.request_info == "测试专利信息"
        assert len(structure.claims) == 1
        assert structure.claims[0].claim_number == 1

    def test_claim_feature_types(self):
        """测试权利要求类型"""
        independent_claim = ClaimFeature(
            claim_number=1,
            claim_type="independent",
            full_text="独立权利要求"
        )
        dependent_claim = ClaimFeature(
            claim_number=2,
            claim_type="dependent",
            full_text="从属权利要求"
        )

        assert independent_claim.claim_type == "independent"
        assert dependent_claim.claim_type == "dependent"


@pytest.mark.unit
class TestRuleEngineIntegration:
    """规则引擎集成测试"""

    @pytest.mark.asyncio
    async def test_execute_fallback_rules(self):
        """测试备用规则执行"""
        engine = RuleEngine()

        structure = PatentStructure(
            request_info="测试专利",
            abstract="这是摘要内容",
            claims=[],
            description={}
        )

        # 没有数据库连接时应使用备用规则
        # 由于测试环境无规则，返回fallback结果
        result = await engine._execute_fallback_rules(
            "test_patent_001",
            structure,
            "完整文本内容",
            level=1
        )

        assert isinstance(result, ExaminationReport)
        # 备用规则应该报告缺少权利要求和说明书
        assert result.passed is False
        assert len(result.results) > 0


@pytest.mark.unit
class TestKeywordChecking:
    """关键词检查测试"""

    @pytest.mark.asyncio
    async def test_keyword_contains(self):
        """测试关键词包含检查"""
        rule = ExaminationRule(
            rule_name="技术领域关键词检查",
            rule_type="formal",
            rule_content={
                "keywords": ["人工智能", "机器学习"],
                "should_contain": True,
                "field": "description"
            },
            check_pattern="keyword",
            severity="warning"
        )

        engine = RuleEngine()

        structure = PatentStructure(
            request_info="测试",
            abstract="测试摘要",
            claims=[],
            description={"技术领域": "本发明涉及人工智能和机器学习技术"}
        )

        text = "本发明涉及人工智能和机器学习技术领域"

        # 模拟检查
        issues = await engine._check_keyword(
            rule, text, structure, rule.rule_content or {}
        )

        assert len(issues) == 0  # 应该找到关键词

    @pytest.mark.asyncio
    async def test_keyword_not_contains(self):
        """测试关键词不包含检查"""
        rule = ExaminationRule(
            rule_name="禁用词检查",
            rule_type="formal",
            rule_content={
                "keywords": ["商业广告"],
                "should_contain": False,
                "field": "description"
            },
            check_pattern="keyword",
            severity="error"
        )

        engine = RuleEngine()

        structure = PatentStructure(
            request_info="测试专利",
            abstract="测试摘要",
            claims=[],
            description={"发明内容": "这是一个商业广告专利"}
        )

        text = "这是一个商业广告专利"

        issues = await engine._check_keyword(
            rule, text, structure, rule.rule_content or {}
        )

        assert len(issues) > 0
        assert issues[0].severity == "error"


@pytest.mark.unit
class TestStructuralChecking:
    """结构化检查测试"""

    @pytest.mark.asyncio
    async def test_document_completeness_check(self):
        """测试文档完整性检查"""
        rule = ExaminationRule(
            rule_name="文档完整性检查",
            rule_type="formal",
            rule_content={
                "type": "document_completeness",
                "required_fields": ["claims", "description", "abstract"]
            },
            check_pattern="structural",
            severity="error"
        )

        engine = RuleEngine()

        # 不完整的文档结构
        structure = PatentStructure(
            request_info="测试专利",
            abstract=None,  # 缺少摘要
            claims=[],  # 缺少权利要求
            description={}  # 缺少说明书
        )

        issues = await engine._check_structural(
            rule, structure, rule.rule_content or {}
        )

        # 应该检测到多个问题
        assert len(issues) >= 1
        # 问题应该是error级别
        error_issues = [i for i in issues if i.severity == "error"]
        assert len(error_issues) >= 1

    @pytest.mark.asyncio
    async def test_claims_structure_check(self):
        """测试权利要求结构检查"""
        rule = ExaminationRule(
            rule_name="权利要求结构检查",
            rule_type="formal",
            rule_content={
                "type": "claims_structure"
            },
            check_pattern="structural",
            severity="error"
        )

        engine = RuleEngine()

        # 没有权利要求
        structure = PatentStructure(
            request_info="测试专利",
            abstract="测试",
            claims=[],
            description={"技术领域": "测试"}
        )

        issues = await engine._check_structural(
            rule, structure, rule.rule_content or {}
        )

        assert len(issues) > 0
        assert any("权利要求" in i.description for i in issues)


@pytest.mark.unit
class TestRegexChecking:
    """正则表达式检查测试"""

    @pytest.mark.asyncio
    async def test_regex_should_not_contain(self):
        """测试正则不应包含内容检查"""
        rule = ExaminationRule(
            rule_name="禁用字符检查",
            rule_type="formal",
            rule_content={
                "pattern": r"[a-zA-Z]",  # 不应包含英文字母
                "should_match": False,
                "location": "全文",
                "suggested_replacement": "使用中文代替"
            },
            check_pattern="regex",
            error_message="发现不应存在的英文字符"
        )

        engine = RuleEngine()

        structure = PatentStructure(
            request_info="Test Patent",  # 含英文字母
            abstract="Abstract",
            claims=[],
            description={}
        )

        issues = await engine._check_regex(
            rule, "Test Patent contains ABC", structure, rule.rule_content or {}
        )

        assert len(issues) > 0