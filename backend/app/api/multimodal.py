"""
多模态RAG API路由
Multimodal RAG API Routes
支持图像OCR、图纸分析
"""
from __future__ import annotations
import logging
from typing import List, Optional
from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from pydantic import BaseModel

from app.ai.rag.multimodal_service import get_multimodal_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/multimodal", tags=["多模态RAG"])


# ============== Schemas ==============

class OCRRequest(BaseModel):
    """OCR请求"""
    image_url: Optional[str] = None
    language: str = "ch+en"


class OCRResponse(BaseModel):
    """OCR响应"""
    text: str
    confidence: float
    language: str
    bounding_boxes: Optional[List[dict]] = None


class ImageAnalysisRequest(BaseModel):
    """图像分析请求"""
    image_url: Optional[str] = None
    patent_id: Optional[str] = None
    metadata: Optional[dict] = None


class ImageAnalysisResponse(BaseModel):
    """图像分析响应"""
    extracted_text: str
    description: str
    diagram_type: Optional[str]
    key_elements: List[str]
    confidence: float


class BatchProcessRequest(BaseModel):
    """批量处理请求"""
    patent_id: str
    image_urls: List[str]


# ============== API Endpoints ==============

@router.post("/ocr", response_model=OCRResponse)
async def extract_text_from_image(
    image: UploadFile = File(..., description="图像文件"),
    language: str = Form("ch+en", description="语言设置: ch, en, ch+en")
):
    """
    从图像中提取文本 (OCR)
    
    支持格式: PNG, JPG, JPEG, TIFF, BMP
    """
    multimodal = get_multimodal_service()
    
    # 保存上传的图像
    import tempfile
    import os
    
    suffix = os.path.splitext(image.filename)[1] if image.filename else '.png'
    
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        content = await image.read()
        tmp.write(content)
        tmp_path = tmp.name
    
    try:
        result = await multimodal.extract_text_from_image(tmp_path, language)
        
        return OCRResponse(
            text=result.text,
            confidence=result.confidence,
            language=result.language or language,
            bounding_boxes=result.bounding_boxes
        )
    finally:
        # 清理临时文件
        try:
            os.unlink(tmp_path)
        except:
            pass


@router.post("/analyze", response_model=ImageAnalysisResponse)
async def analyze_patent_image(
    image: UploadFile = File(..., description="专利图像文件"),
    patent_id: Optional[str] = Form(None, description="专利ID"),
    metadata: Optional[str] = Form(None, description="元数据JSON字符串")
):
    """
    分析专利图像
    
    返回: 提取的文本、图像描述、图表类型、关键元素
    """
    import json
    multimodal = get_multimodal_service()
    
    # 解析元数据
    meta_dict = {}
    if metadata:
        try:
            meta_dict = json.loads(metadata)
        except:
            pass
    
    if patent_id:
        meta_dict['patent_id'] = patent_id
    
    # 保存上传的图像
    import tempfile
    import os
    
    suffix = os.path.splitext(image.filename)[1] if image.filename else '.png'
    
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        content = await image.read()
        tmp.write(content)
        tmp_path = tmp.name
    
    try:
        result = await multimodal.analyze_patent_image(tmp_path, meta_dict)
        
        return ImageAnalysisResponse(
            extracted_text=result.extracted_text,
            description=result.description,
            diagram_type=result.diagram_type,
            key_elements=result.key_elements or [],
            confidence=result.confidence
        )
    finally:
        try:
            os.unlink(tmp_path)
        except:
            pass


@router.post("/batch-process")
async def batch_process_patent_images(
    patent_id: str = Form(..., description="专利ID"),
    images: List[UploadFile] = File(..., description="专利图像列表")
):
    """
    批量处理专利图像
    
    一次上传多个图像文件进行批量OCR和分析
    """
    import tempfile
    import os
    
    multimodal = get_multimodal_service()
    results = []
    
    for image in images:
        suffix = os.path.splitext(image.filename)[1] if image.filename else '.png'
        
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            content = await image.read()
            tmp.write(content)
            tmp_path = tmp.name
        
        try:
            result = await multimodal.process_patent_drawing(
                tmp_path,
                patent_id,
                {'filename': image.filename}
            )
            results.append(result)
        except Exception as e:
            logger.error(f"处理图像失败 {image.filename}: {e}")
            results.append({
                'filename': image.filename,
                'error': str(e)
            })
        finally:
            try:
                os.unlink(tmp_path)
            except:
                pass
    
    return {
        "code": 200,
        "data": {
            "patent_id": patent_id,
            "total": len(images),
            "processed": len([r for r in results if 'error' not in r]),
            "results": results
        }
    }


@router.get("/health")
async def health_check():
    """多模态服务健康检查"""
    multimodal = get_multimodal_service()
    multimodal.initialize()
    
    return {
        "code": 200,
        "data": {
            "status": "healthy",
            "ocr_available": multimodal._ocr_model is not None,
            "vision_available": multimodal._vision_model is not None
        }
    }
