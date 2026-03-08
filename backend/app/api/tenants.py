"""租户管理 API"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.database.engine import get_db
from app.database.models import Tenant, User
from app.core.security import get_current_user
from pydantic import BaseModel
from typing import Optional
import re

router = APIRouter()


class TenantCreate(BaseModel):
    name: str
    code: str
    description: Optional[str] = None
    max_users: int = 10
    max_patents: int = 1000


class TenantUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None
    max_users: Optional[int] = None
    max_patents: Optional[int] = None


class TenantResponse(BaseModel):
    id: int
    name: str
    code: str
    description: Optional[str]
    is_active: bool
    max_users: int
    max_patents: int
    created_at: Optional[str] = None

    class Config:
        from_attributes = True

# 注意：具体路径必须在带参数路径之前定义

@router.get("/", summary="获取租户列表")
async def list_tenants(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    keyword: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user)
):
    if user.role != "admin":
        raise HTTPException(403, "权限不足")
    
    query = select(Tenant)
    count_query = select(func.count()).select_from(Tenant)
    
    if keyword:
        like = f"%{keyword}%"
        filt = (Tenant.name.like(like) | Tenant.code.like(like))
        query = query.where(filt)
        count_query = count_query.where(filt)
    
    total = (await db.execute(count_query)).scalar() or 0
    query = query.order_by(Tenant.created_at.desc()).offset((page-1)*page_size).limit(page_size)
    items = (await db.execute(query)).scalars().all()
    
    return {
        "code": 200,
        "data": {
            "items": [TenantResponse.model_validate(t).model_dump() for t in items],
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": (total + page_size - 1) // page_size
        }
    }


@router.post("/", summary="创建租户")
async def create_tenant(
    data: TenantCreate,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user)
):
    if user.role != "admin":
        raise HTTPException(403, "权限不足")
    
    # 验证租户代码格式
    if not re.match(r'^[a-z][a-z0-9_]{2,20}$', data.code):
        raise HTTPException(400, "租户代码需以小写字母开头，仅包含小写字母、数字、下划线，长度3-20")
    
    # 检查唯一性
    result = await db.execute(select(Tenant).where(Tenant.code == data.code))
    if result.scalar_one_or_none():
        raise HTTPException(400, "租户代码已存在")
    
    tenant = Tenant(**data.model_dump())
    db.add(tenant)
    await db.commit()
    await db.refresh(tenant)
    
    return {"code": 200, "data": TenantResponse.model_validate(tenant).model_dump()}


@router.get("/{tenant_id}", summary="获取租户详情")
async def get_tenant(
    tenant_id: int,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user)
):
    if user.role != "admin":
        raise HTTPException(403, "权限不足")
    
    result = await db.execute(select(Tenant).where(Tenant.id == tenant_id))
    tenant = result.scalar_one_or_none()
    if not tenant:
        raise HTTPException(404, "租户不存在")
    
    # 获取用户数量
    user_count = await db.execute(
        select(func.count()).select_from(User).where(User.tenant_id == tenant_id)
    )
    
    data = TenantResponse.model_validate(tenant).model_dump()
    data["user_count"] = user_count.scalar() or 0
    
    return {"code": 200, "data": data}


@router.put("/{tenant_id}", summary="更新租户")
async def update_tenant(
    tenant_id: int,
    data: TenantUpdate,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user)
):
    if user.role != "admin":
        raise HTTPException(403, "权限不足")
    
    result = await db.execute(select(Tenant).where(Tenant.id == tenant_id))
    tenant = result.scalar_one_or_none()
    if not tenant:
        raise HTTPException(404, "租户不存在")
    
    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(tenant, key, value)
    
    await db.commit()
    await db.refresh(tenant)
    
    return {"code": 200, "data": TenantResponse.model_validate(tenant).model_dump()}


@router.delete("/{tenant_id}", summary="删除租户")
async def delete_tenant(
    tenant_id: int,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user)
):
    if user.role != "admin":
        raise HTTPException(403, "权限不足")
    
    result = await db.execute(select(Tenant).where(Tenant.id == tenant_id))
    tenant = result.scalar_one_or_none()
    if not tenant:
        raise HTTPException(404, "租户不存在")
    
    # 检查是否有用户
    user_count_result = await db.execute(
        select(func.count()).select_from(User).where(User.tenant_id == tenant_id)
    )
    user_count_val = user_count_result.scalar()
    if user_count_val and user_count_val > 0:
        raise HTTPException(400, "该租户下存在用户，无法删除")
    
    await db.delete(tenant)
    await db.commit()
    
    return {"code": 200, "message": "删除成功"}
