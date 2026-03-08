"""
多模态RAG服务
Multimodal RAG Service for Patent Images
支持图像OCR、图表理解、图纸分析
"""
from __future__ import annotations
import logging
import base64
import io
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class OCRResult:
    """OCR识别结果"""
    text: str
    confidence: float
    bounding_boxes: Optional[List[Dict[str, Any]]] = None
    language: Optional[str] = None


@dataclass
class ImageAnalysisResult:
    """图像分析结果"""
    description: str  # 图像描述
    extracted_text: str  # 提取的文本
    diagram_type: Optional[str] = None  # 图表类型 (flowchart, structure, circuit, etc.)
    key_elements: Optional[List[str]] = None  # 关键元素
    confidence: float = 0.0


class MultimodalService:
    """多模态RAG服务 - 支持专利图像处理"""
    
    def __init__(self):
        self._ocr_model = None
        self._vision_model = None
        self._initialized = False
    
    def initialize(self):
        """初始化模型"""
        if self._initialized:
            return
        
        # 尝试加载OCR模型 (PaddleOCR / EasyOCR)
        self._init_ocr()
        
        # 尝试加载视觉理解模型
        self._init_vision()
        
        self._initialized = True
        logger.info("多模态服务初始化完成")
    
    def _init_ocr(self):
        """初始化OCR模型"""
        try:
            # 尝试使用 PaddleOCR
            from paddleocr import PaddleOCR
            self._ocr_model = PaddleOCR(
                use_angle_cls=True,
                lang='ch',  # 中文+英文
                show_log=False,
                use_gpu=False
            )
            logger.info("PaddleOCR 加载成功")
            return
        except ImportError:
            pass
        except Exception as e:
            logger.warning(f"PaddleOCR 加载失败: {e}")
        
        try:
            # 备用: EasyOCR
            import easyocr
            self._ocr_model = easyocr.Reader(['ch_sim', 'en'], gpu=False)
            logger.info("EasyOCR 加载成功")
            return
        except ImportError:
            pass
        except Exception as e:
            logger.warning(f"EasyOCR 加载失败: {e}")
        
        logger.warning("无可用OCR模型，将使用备选方案")
    
    def _init_vision(self):
        """初始化视觉理解模型"""
        try:
            # 尝试使用 transformers 的视觉模型
            from transformers import AutoProcessor, AutoVisionModel
            # 使用轻量级模型
            self._vision_processor = AutoProcessor.from_pretrained("microsoft/trocr-base-handwritten")
            self._vision_model = AutoVisionModel.from_pretrained("microsoft/trocr-base-handwritten")
            logger.info("视觉理解模型加载成功")
        except Exception as e:
            logger.warning(f"视觉模型加载失败: {e}")
    
    async def extract_text_from_image(
        self,
        image_path: str,
        language: str = "ch+en"
    ) -> OCRResult:
        """
        从图像中提取文本
        
        Args:
            image_path: 图像文件路径
            language: 语言设置 (ch, en, ch+en)
            
        Returns:
            OCRResult: 识别结果
        """
        self.initialize()
        
        try:
            if hasattr(self, '_ocr_model') and self._ocr_model is not None:
                return await self._ocr_extract(image_path, language)
            else:
                return await self._fallback_extract(image_path)
        except Exception as e:
            logger.error(f"OCR识别失败: {e}")
            return OCRResult(text="", confidence=0.0)
    
    async def _ocr_extract(
        self,
        image_path: str,
        language: str
    ) -> OCRResult:
        """使用已加载的OCR模型提取文本"""
        import asyncio
        
        def _run_ocr():
            if hasattr(self._ocr_model, 'ocr'):
                # PaddleOCR
                result = self._ocr_model.ocr(image_path, cls=True)
                texts = []
                confidences = []
                boxes = []
                
                if result and result[0]:
                    for line in result[0]:
                        if line and len(line) >= 2:
                            texts.append(line[1][0])
                            confidences.append(line[1][1])
                            boxes.append({
                                'box': line[0],
                                'text': line[1][0]
                            })
                
                combined_text = '\n'.join(texts)
                avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0
                
                return OCRResult(
                    text=combined_text,
                    confidence=avg_confidence,
                    bounding_boxes=boxes,
                    language=language
                )
            elif hasattr(self._ocr_model, 'readtext'):
                # EasyOCR
                result = self._ocr_model.readtext(image_path)
                texts = []
                confidences = []
                
                for detection in result:
                    texts.append(detection[1])
                    confidences.append(detection[2])
                
                combined_text = '\n'.join(texts)
                avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0
                
                return OCRResult(
                    text=combined_text,
                    confidence=avg_confidence,
                    language=language
                )
            
            return OCRResult(text="", confidence=0.0)
        
        # 在线程池中运行OCR
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _run_ocr)
    
    async def _fallback_extract(
        self,
        image_path: str
    ) -> OCRResult:
        """备选方案: 使用基础图像处理"""
        try:
            # 尝试使用 PIL 简单处理
            from PIL import Image
            import pytesseract
            
            image = Image.open(image_path)
            text = pytesseract.image_to_string(image, lang='chi_sim+eng')
            
            return OCRResult(
                text=text.strip(),
                confidence=0.5,  # 保守估计
                language="ch+en"
            )
        except Exception as e:
            logger.warning(f"备选OCR方案也失败: {e}")
            return OCRResult(text="", confidence=0.0)
    
    async def analyze_patent_image(
        self,
        image_path: str,
        context: Optional[Dict[str, Any]] = None
    ) -> ImageAnalysisResult:
        """
        分析专利图像
        
        Args:
            image_path: 图像路径
            context: 额外上下文信息
            
        Returns:
            ImageAnalysisResult: 分析结果
        """
        self.initialize()
        
        # 1. 首先进行OCR提取
        ocr_result = await self.extract_text_from_image(image_path)
        
        # 2. 尝试识别图表类型
        diagram_type = await self._detect_diagram_type(image_path)
        
        # 3. 生成图像描述
        description = await self._generate_image_description(image_path, context)
        
        # 4. 提取关键元素
        key_elements = self._extract_key_elements(ocr_result.text, diagram_type)
        
        return ImageAnalysisResult(
            description=description,
            extracted_text=ocr_result.text,
            diagram_type=diagram_type,
            key_elements=key_elements,
            confidence=ocr_result.confidence
        )
    
    async def _detect_diagram_type(self, image_path: str) -> Optional[str]:
        """识别图表类型"""
        # 简单的规则-based 识别
        # 实际生产中可以使用图像分类模型
        
        diagram_keywords = {
            'flowchart': ['流程图', '流程', '步骤', 'flow', 'process'],
            'structure': ['结构', '组成', 'structure', 'composition'],
            'circuit': ['电路', '线路', 'circuit', 'electrical'],
            'mechanical': ['机械', '装置', 'mechanical', 'device'],
            'chemical': ['化学', '分子', 'chemical', 'molecular'],
        }
        
        # 这里简化处理，实际应该分析图像内容
        return None
    
    async def _generate_image_description(
        self,
        image_path: str,
        context: Optional[Dict[str, Any]]
    ) -> str:
        """生成图像描述"""
        # 尝试使用视觉模型生成描述
        # 这里简化处理
        
        if context and context.get('patent_title'):
            return f"专利附图: {context.get('patent_title')}"
        
        return "专利附图"
    
    def _extract_key_elements(
        self,
        text: str,
        diagram_type: Optional[str]
    ) -> List[str]:
        """提取关键元素"""
        if not text:
            return []
        
        # 简单的关键词提取
        elements = []
        lines = text.split('\n')
        
        for line in lines[:10]:  # 取前10行
            line = line.strip()
            if line and len(line) > 2:
                elements.append(line)
        
        return elements
    
    async def process_patent_drawing(
        self,
        file_path: str,
        patent_id: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        处理专利图纸
        
        Args:
            file_path: 图纸文件路径
            patent_id: 专利ID
            metadata: 元数据
            
        Returns:
            处理结果字典
        """
        result = await self.analyze_patent_image(
            file_path,
            {'patent_id': patent_id, **(metadata or {})}
        )
        
        return {
            'patent_id': patent_id,
            'file_path': file_path,
            'extracted_text': result.extracted_text,
            'description': result.description,
            'diagram_type': result.diagram_type,
            'key_elements': result.key_elements,
            'confidence': result.confidence,
            'processed_at': str(Path(file_path).stat().st_mtime) if Path(file_path).exists() else None
        }
    
    async def batch_process_images(
        self,
        image_paths: List[str],
        patent_id: str
    ) -> List[Dict[str, Any]]:
        """批量处理专利图纸"""
        results = []
        
        for image_path in image_paths:
            try:
                result = await self.process_patent_drawing(image_path, patent_id)
                results.append(result)
            except Exception as e:
                logger.error(f"处理图像失败 {image_path}: {e}")
                results.append({
                    'file_path': image_path,
                    'error': str(e)
                })
        
        return results


# 全局实例
multimodal_service: Optional[MultimodalService] = None


def get_multimodal_service() -> MultimodalService:
    """获取多模态服务实例"""
    global multimodal_service
    if multimodal_service is None:
        multimodal_service = MultimodalService()
    return multimodal_service
