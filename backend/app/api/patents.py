"""专利管理 API"""
from fastapi import APIRouter, Depends, UploadFile, File, Query, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from app.database.engine import get_db
from app.core.security import get_current_user
from app.services.patent_service import PatentService
from app.schemas.patent import PatentCreate, PatentUpdate, PatentResponse, PatentListItem, PaginatedResponse
from app.config import settings
from pathlib import Path
import shutil

router = APIRouter()

@router.post("/", response_model=dict, summary="创建专利申请")
async def create_patent(data: PatentCreate, db: AsyncSession = Depends(get_db), user=Depends(get_current_user)):
    patent = await PatentService.create(data, db, user.id)
    return {"code": 200, "message": "创建成功", "data": PatentResponse.model_validate(patent).model_dump()}

@router.get("/", response_model=dict, summary="获取专利列表")
async def list_patents(page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100),
                       status: str | None = None, keyword: str | None = None,
                       db: AsyncSession = Depends(get_db), user=Depends(get_current_user)):
    result = await PatentService.list_patents(db, page, page_size, status, keyword)
    items = [PatentListItem.model_validate(p).model_dump() for p in result.items]
    return {"code": 200, "data": {"items": items, "total": result.total, "page": result.page, "page_size": result.page_size, "total_pages": result.total_pages}}

@router.get("/statistics", response_model=dict, summary="获取专利统计")
async def get_statistics(db: AsyncSession = Depends(get_db), user=Depends(get_current_user)):
    stats = await PatentService.get_statistics(db)
    return {"code": 200, "data": stats}

@router.get("/{patent_id}", response_model=dict, summary="获取专利详情")
async def get_patent(patent_id: int, db: AsyncSession = Depends(get_db), user=Depends(get_current_user)):
    patent = await PatentService.get(patent_id, db)
    if not patent:
        raise HTTPException(404, "专利不存在")
    return {"code": 200, "data": PatentResponse.model_validate(patent).model_dump()}

@router.put("/{patent_id}", response_model=dict, summary="更新专利")
async def update_patent(patent_id: int, data: PatentUpdate, db: AsyncSession = Depends(get_db), user=Depends(get_current_user)):
    patent = await PatentService.update(patent_id, data, db)
    if not patent:
        raise HTTPException(404, "专利不存在")
    return {"code": 200, "message": "更新成功", "data": PatentResponse.model_validate(patent).model_dump()}

@router.delete("/{patent_id}", response_model=dict, summary="删除专利")
async def delete_patent(patent_id: int, db: AsyncSession = Depends(get_db), user=Depends(get_current_user)):
    success = await PatentService.delete(patent_id, db)
    if not success:
        raise HTTPException(404, "专利不存在")
    return {"code": 200, "message": "删除成功"}

@router.post("/import", response_model=dict, summary="导入专利文档")
async def import_patent(file: UploadFile = File(...), db: AsyncSession = Depends(get_db), user=Depends(get_current_user)):
    if file.size and file.size > settings.app.MAX_UPLOAD_SIZE_MB * 1024 * 1024:
        raise HTTPException(413, f"文件大小超过限制 ({settings.app.MAX_UPLOAD_SIZE_MB}MB)")
    upload_dir = Path(settings.app.UPLOAD_DIR)
    upload_dir.mkdir(parents=True, exist_ok=True)
    dest = upload_dir / (file.filename or "uploaded_file")
    with open(dest, "wb") as f:
        shutil.copyfileobj(file.file, f)
    patent = await PatentService.import_file(str(dest), file.filename or "uploaded_file", db, user.id)
    return {"code": 200, "message": "导入成功", "data": PatentResponse.model_validate(patent).model_dump()}
