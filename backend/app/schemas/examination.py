"""审查记录与审查意见相关 Pydantic 模型"""
from __future__ import annotations
from datetime import datetime
from typing import Optional, Any
from pydantic import BaseModel, ConfigDict, Field


class ExaminationRecordResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    application_id: int
    examiner_id: Optional[str] = None
    examination_type: str
    examination_step: str
    status: str
    result: Optional[dict] = None
    confidence_score: Optional[float] = None
    ai_model_used: Optional[str] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    created_at: Optional[datetime] = None


class ExaminationStartRequest(BaseModel):
    examination_type: str = Field(..., description="审查类型: formal / substantive")
    examiner_id: Optional[str] = None


class OpinionCreateRequest(BaseModel):
    opinion_type: str = Field(..., description="意见类型: notice / grant / rejection")
    content: str = Field(..., description="意见内容")
    legal_basis: Optional[dict] = None
    prior_art_references: Optional[dict] = None
    template_id: Optional[int] = None


class OpinionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    application_id: int
    opinion_type: str
    content: str
    legal_basis: Optional[dict] = None
    prior_art_references: Optional[dict] = None
    status: str
    version: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class ExaminationResultResponse(BaseModel):
    patent_id: int
    examination_type: str
    overall_passed: bool
    overall_score: float
    results: list[dict] = []
    summary: str = ""
    timestamp: Optional[datetime] = None


class ChecklistItem(BaseModel):
    name: str
    description: str
    category: str
    checked: bool = False
    result: Optional[str] = None
    confidence: Optional[float] = None
