"""规则引擎 API"""
from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database.engine import get_db
from app.core.security import get_current_user
from app.database.models import ExaminationRule
from app.schemas.rule import RuleCreate, RuleUpdate, RuleResponse

router = APIRouter()

# 处理没有末尾斜杠的请求，重定向到正确路径
@router.get("", summary="获取规则列表（重定向）")
async def list_rules_redirect():
    """处理 /api/v1/rules 重定向到 /api/v1/rules/"""
    return Response(status_code=308, headers={"Location": "/api/v1/rules/"})

@router.get("/", summary="获取规则列表")
async def list_rules(rule_type: str | None = None, is_active: bool | None = None,
                     db: AsyncSession = Depends(get_db), user=Depends(get_current_user)):
    query = select(ExaminationRule)
    if rule_type:
        query = query.where(ExaminationRule.rule_type == rule_type)
    if is_active is not None:
        query = query.where(ExaminationRule.is_active == is_active)
    query = query.order_by(ExaminationRule.priority.desc())
    result = await db.execute(query)
    rules = [RuleResponse.model_validate(r).model_dump() for r in result.scalars().all()]
    return {"code": 200, "data": rules}

@router.post("/", summary="创建规则")
async def create_rule(data: RuleCreate, db: AsyncSession = Depends(get_db), user=Depends(get_current_user)):
    rule = ExaminationRule(**data.model_dump())
    db.add(rule)
    await db.flush()
    await db.refresh(rule)
    return {"code": 200, "data": RuleResponse.model_validate(rule).model_dump()}

@router.put("/{rule_id}", summary="更新规则")
async def update_rule(rule_id: int, data: RuleUpdate, db: AsyncSession = Depends(get_db), user=Depends(get_current_user)):
    result = await db.execute(select(ExaminationRule).where(ExaminationRule.id == rule_id))
    rule = result.scalar_one_or_none()
    if not rule:
        raise HTTPException(404, "规则不存在")
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(rule, k, v)
    await db.flush()
    return {"code": 200, "data": RuleResponse.model_validate(rule).model_dump()}

@router.delete("/{rule_id}", summary="删除规则")
async def delete_rule(rule_id: int, db: AsyncSession = Depends(get_db), user=Depends(get_current_user)):
    result = await db.execute(select(ExaminationRule).where(ExaminationRule.id == rule_id))
    rule = result.scalar_one_or_none()
    if not rule:
        raise HTTPException(404, "规则不存在")
    await db.delete(rule)
    await db.flush()
    return {"code": 200, "message": "规则删除成功"}

@router.get("/{rule_id}", summary="获取规则详情")
async def get_rule(rule_id: int, db: AsyncSession = Depends(get_db), user=Depends(get_current_user)):
    result = await db.execute(select(ExaminationRule).where(ExaminationRule.id == rule_id))
    rule = result.scalar_one_or_none()
    if not rule:
        raise HTTPException(404, "规则不存在")
    return {"code": 200, "data": RuleResponse.model_validate(rule).model_dump()}
