"""审查规则相关 Pydantic 模型"""
from __future__ import annotations
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field


class RuleCreate(BaseModel):
    rule_name: str = Field(..., max_length=200, description="规则名称")
    rule_type: str = Field(..., description="规则类型: formal/novelty/inventiveness/practicality/claims/description/drawings/unity")
    rule_category: str = Field(default="level1", description="规则级别: level1/level2/level3")
    rule_content: Optional[dict] = None
    priority: int = 0
    is_active: bool = True
    version: Optional[str] = None
    description: Optional[str] = None
    legal_basis: Optional[str] = None
    severity: str = Field(default="warning", description="严重程度: error/warning/info")
    check_pattern: Optional[str] = Field(None, description="检查模式: regex/keyword/ai/structural/template")
    target_fields: Optional[dict] = Field(None, description="目标字段列表")
    error_message: Optional[str] = Field(None, description="错误消息模板")
    fix_suggestion: Optional[str] = Field(None, description="修复建议")
    ai_model: Optional[str] = Field(None, description="使用的AI模型")
    examples: Optional[dict] = Field(None, description="示例")
    tags: Optional[dict] = Field(None, description="标签")


class RuleUpdate(BaseModel):
    rule_name: Optional[str] = None
    rule_type: Optional[str] = None
    rule_category: Optional[str] = None
    rule_content: Optional[dict] = None
    priority: Optional[int] = None
    is_active: Optional[bool] = None
    description: Optional[str] = None
    legal_basis: Optional[str] = None
    severity: Optional[str] = None
    check_pattern: Optional[str] = None
    target_fields: Optional[dict] = None
    error_message: Optional[str] = None
    fix_suggestion: Optional[str] = None
    ai_model: Optional[str] = None
    examples: Optional[dict] = None
    tags: Optional[dict] = None


class RuleResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    rule_name: str
    rule_type: str
    rule_category: str
    rule_content: Optional[dict] = None
    priority: int
    is_active: bool
    version: Optional[str] = None
    description: Optional[str] = None
    legal_basis: Optional[str] = None
    severity: str = "warning"
    check_pattern: Optional[str] = None
    target_fields: Optional[dict] = None
    error_message: Optional[str] = None
    fix_suggestion: Optional[str] = None
    ai_model: Optional[str] = None
    examples: Optional[dict] = None
    tags: Optional[dict] = None
    created_by: Optional[int] = None
    last_executed_at: Optional[datetime] = None
    execution_count: int = 0
    success_rate: Optional[float] = None
    avg_execution_time: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
