"""文档管理 API"""
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
from pathlib import Path
from app.database.engine import get_db
from app.core.security import get_current_user
from app.services.document_parser import DocumentParserService
from app.config import settings
import shutil

router = APIRouter()
parser = DocumentParserService()

@router.post("/upload", summary="上传文档")
async def upload_doc(file: UploadFile = File(...), user=Depends(get_current_user)):
    upload_dir = Path(settings.app.UPLOAD_DIR)
    upload_dir.mkdir(parents=True, exist_ok=True)
    dest = upload_dir / (file.filename or "file")
    with open(dest, "wb") as f:
        shutil.copyfileobj(file.file, f)
    return {"code": 200, "data": {"file_path": str(dest), "filename": file.filename, "size": file.size}}

@router.post("/parse", summary="解析文档")
async def parse_doc(file_path: str, user=Depends(get_current_user)):
    result = await parser.parse_file(file_path)
    if not result.success:
        raise HTTPException(422, result.error)
    return {"code": 200, "data": {
        "metadata": result.metadata.__dict__,
        "claims_count": len(result.structure.claims),
        "sections": list(result.structure.description.keys()),
        "abstract": result.structure.abstract[:500],
        "text_length": len(result.full_text),
    }}
