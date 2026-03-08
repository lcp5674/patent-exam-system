"""专利申请相关 Pydantic 模型"""
from __future__ import annotations
from datetime import date, datetime
from typing import Optional, Any
from pydantic import BaseModel, ConfigDict, Field


class PatentCreate(BaseModel):
    application_number: Optional[str] = Field(None, max_length=50, description="申请号")
    title: str = Field(..., max_length=500, description="发明名称")
    applicant: str = Field(..., max_length=500, description="申请人")
    application_date: Optional[date] = None
    inventor: Optional[str] = None
    agent: Optional[str] = None
    priority_date: Optional[date] = None
    priority_number: Optional[str] = None
    ipc_classification: Optional[str] = None
    abstract: Optional[str] = None
    technical_field: Optional[str] = None


class PatentUpdate(BaseModel):
    title: Optional[str] = None
    applicant: Optional[str] = None
    inventor: Optional[str] = None
    agent: Optional[str] = None
    status: Optional[str] = None
    ipc_classification: Optional[str] = None
    abstract: Optional[str] = None
    technical_field: Optional[str] = None


class PatentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    application_number: str
    application_date: Optional[date] = None
    title: str
    applicant: str
    inventor: Optional[str] = None
    agent: Optional[str] = None
    status: str
    priority_date: Optional[date] = None
    priority_number: Optional[str] = None
    ipc_classification: Optional[str] = None
    file_path: Optional[str] = None
    abstract: Optional[str] = None
    technical_field: Optional[str] = None
    parsed_content: Optional[dict] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class PatentListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    application_number: str
    title: str
    applicant: str
    application_date: Optional[date] = None
    status: str
    ipc_classification: Optional[str] = None
    created_at: Optional[datetime] = None


class PatentSearchRequest(BaseModel):
    keyword: Optional[str] = None
    status: Optional[str] = None
    applicant: Optional[str] = None
    ipc_classification: Optional[str] = None
    date_from: Optional[date] = None
    date_to: Optional[date] = None


class PaginationParams(BaseModel):
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)


class PaginatedResponse(BaseModel):
    items: list[Any] = []
    total: int = 0
    page: int = 1
    page_size: int = 20
    total_pages: int = 0
