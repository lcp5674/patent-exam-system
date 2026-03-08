"""用户与认证相关 Pydantic 模型"""
from __future__ import annotations
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field


class UserCreate(BaseModel):
    username: str = Field(..., min_length=3, max_length=100)
    password: str = Field(..., min_length=6, max_length=128)
    email: Optional[str] = None
    full_name: Optional[str] = None
    department: Optional[str] = None
    role: str = "examiner"


class UserUpdate(BaseModel):
    email: Optional[str] = None
    full_name: Optional[str] = None
    department: Optional[str] = None


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    username: str
    role: str
    email: Optional[str] = None
    full_name: Optional[str] = None
    department: Optional[str] = None
    is_active: bool
    created_at: Optional[datetime] = None


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class PasswordChangeRequest(BaseModel):
    old_password: str
    new_password: str = Field(..., min_length=8)


class RefreshTokenRequest(BaseModel):
    refresh_token: str


class UserUpdateRequest(BaseModel):
    email: Optional[str] = None
    full_name: Optional[str] = None
    department: Optional[str] = None
    role: Optional[str] = None
    is_active: Optional[bool] = None
    password: Optional[str] = Field(None, min_length=8)
