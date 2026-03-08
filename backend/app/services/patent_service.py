"""专利管理业务服务"""
from __future__ import annotations
import logging, shutil
from datetime import date, datetime
from pathlib import Path
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_
from app.database.models import PatentApplication
from app.schemas.patent import PatentCreate, PatentUpdate, PaginatedResponse, PatentSearchRequest
from app.config import settings
from .document_parser import DocumentParserService

logger = logging.getLogger(__name__)
parser = DocumentParserService()


class PatentService:

    @staticmethod
    async def create(data: PatentCreate, db: AsyncSession, user_id: int | None = None) -> PatentApplication:
        d = data.model_dump(exclude_unset=True)
        if not d.get("application_number"):
            import uuid
            d["application_number"] = f"CN{datetime.now().strftime('%Y%m%d')}{uuid.uuid4().hex[:6].upper()}"
        patent = PatentApplication(**d, created_by=user_id)
        db.add(patent)
        await db.flush()
        await db.refresh(patent)
        return patent

    @staticmethod
    async def get(patent_id: int, db: AsyncSession) -> PatentApplication | None:
        result = await db.execute(select(PatentApplication).where(PatentApplication.id == patent_id))
        return result.scalar_one_or_none()

    @staticmethod
    async def list_patents(db: AsyncSession, page: int = 1, page_size: int = 20,
                           status: str | None = None, keyword: str | None = None) -> PaginatedResponse:
        query = select(PatentApplication)
        count_query = select(func.count()).select_from(PatentApplication)
        if status:
            query = query.where(PatentApplication.status == status)
            count_query = count_query.where(PatentApplication.status == status)
        if keyword:
            like = f"%{keyword}%"
            filt = or_(PatentApplication.title.like(like), PatentApplication.applicant.like(like),
                       PatentApplication.application_number.like(like))
            query = query.where(filt)
            count_query = count_query.where(filt)
        total = (await db.execute(count_query)).scalar() or 0
        query = query.order_by(PatentApplication.created_at.desc()).offset((page-1)*page_size).limit(page_size)
        items = (await db.execute(query)).scalars().all()
        return PaginatedResponse(items=list(items), total=total, page=page, page_size=page_size,
                                 total_pages=(total + page_size - 1) // page_size)

    @staticmethod
    async def update(patent_id: int, data: PatentUpdate, db: AsyncSession) -> PatentApplication | None:
        patent = await PatentService.get(patent_id, db)
        if not patent:
            return None
        for k, v in data.model_dump(exclude_unset=True).items():
            setattr(patent, k, v)
        await db.flush()
        await db.refresh(patent)
        return patent

    @staticmethod
    async def delete(patent_id: int, db: AsyncSession) -> bool:
        patent = await PatentService.get(patent_id, db)
        if patent:
            # 删除关联的文件
            if patent.file_path:
                try:
                    file_path = Path(patent.file_path)
                    if file_path.exists():
                        file_path.unlink()
                except Exception as e:
                    logger.warning(f"删除专利文件失败: {e}")
            
            await db.delete(patent)
            return True
        return False

    @staticmethod
    async def import_file(file_path: str, original_filename: str, db: AsyncSession, user_id: int | None = None) -> PatentApplication:
        # 保存文件
        upload_dir = Path(settings.app.UPLOAD_DIR)
        upload_dir.mkdir(parents=True, exist_ok=True)
        dest = upload_dir / original_filename
        if str(file_path) != str(dest):
            shutil.copy2(file_path, dest)
        
        # 解析文档
        result = await parser.parse_file(str(dest))
        meta = result.metadata
        
        # 构建完整的parsed_content，存储所有内容
        parsed_content = {}
        
        # 1. 存储完整的权利要求书
        claims_list = []
        for claim in result.structure.claims:
            claims_list.append({
                "claim_number": claim.claim_number,
                "claim_type": claim.claim_type,
                "preamble": claim.preamble,
                "characterizing": claim.characterizing,
                "references": claim.references,
                "full_text": claim.full_text
            })
        parsed_content["claims"] = claims_list
        
        # 2. 存储完整的说明书各部分（不截断）
        parsed_content["description"] = result.structure.description
        
        # 3. 存储完整的摘要
        parsed_content["abstract"] = result.structure.abstract
        
        # 4. 存储请求书信息
        parsed_content["request_info"] = {
            "application_number": meta.application_number,
            "application_date": meta.application_date,
            "title": meta.title,
            "applicant": meta.applicant,
            "inventor": meta.inventor,
            "agent": meta.agent,
            "ipc_classification": meta.ipc_classification
        }
        
        # 5. 存储附图信息
        parsed_content["drawings_described"] = result.structure.drawings_described
        
        # 6. 存储全文（可选，用于检索）
        parsed_content["full_text_length"] = len(result.full_text)
        
        # 存储正确的容器路径（不是Windows路径）
        container_path = str(dest)
        
        patent = PatentApplication(
            application_number=meta.application_number or f"AUTO-{dest.stem[:20]}",
            title=meta.title or original_filename,
            applicant=meta.applicant or "待填写",
            inventor=meta.inventor or None,
            ipc_classification=meta.ipc_classification or None,
            file_path=container_path,
            abstract=result.structure.abstract[:2000] if result.structure.abstract else None,
            parsed_content=parsed_content,
            created_by=user_id,
        )
        db.add(patent)
        await db.flush()
        await db.refresh(patent)
        return patent

    @staticmethod
    async def get_statistics(db: AsyncSession) -> dict:
        total = (await db.execute(select(func.count()).select_from(PatentApplication))).scalar() or 0
        pending = (await db.execute(select(func.count()).select_from(PatentApplication).where(PatentApplication.status == "pending"))).scalar() or 0
        examining = (await db.execute(select(func.count()).select_from(PatentApplication).where(PatentApplication.status == "examining"))).scalar() or 0
        granted = (await db.execute(select(func.count()).select_from(PatentApplication).where(PatentApplication.status == "granted"))).scalar() or 0
        rejected = (await db.execute(select(func.count()).select_from(PatentApplication).where(PatentApplication.status == "rejected"))).scalar() or 0
        return {"total": total, "pending": pending, "examining": examining, "granted": granted, "rejected": rejected}
