"""AI 服务 API"""
import json
import re
import os
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database.engine import get_db
from app.database.models import AIProviderConfig
from app.core.security import get_current_user
from app.ai.provider_manager import provider_manager
from app.ai.prompts.patent_prompts import *
from app.schemas.ai import (
    AIAnalyzeRequest, AIChatRequest, AIResponse, 
    AIProviderConfigSchema, AIProviderConfigCreate, AIProviderConfigUpdateFull
)
from app.config import settings
import logging

logger = logging.getLogger(__name__)
router = APIRouter()


def convert_file_path(file_path: str) -> str:
    """
    将文件路径转换为当前环境可访问的路径
    支持:
    - Windows路径 (F:/xxx/backend/data/uploads/xxx.doc) -> 容器路径 (/app/data/uploads/xxx.doc)
    - Linux路径 (/xxx/backend/data/uploads/xxx.doc) -> 保持不变
    - 本地开发模式 (相对路径或绝对路径)
    """
    if not file_path:
        return file_path
    
    # 获取上传目录配置
    upload_dir = settings.app.UPLOAD_DIR
    
    # 提取文件名
    filename = Path(file_path).name
    
    # 检查是否包含反斜杠（Windows路径）
    if '\\' in file_path:
        # Windows路径情况 - 直接使用文件名构建容器路径
        # 数据库中存储的Windows路径在容器中不可用
        # 文件已保存在 /app/data/uploads/ 目录
        return f"{upload_dir}/{filename}"
    
    # 检查是否是绝对路径（Linux）
    if Path(file_path).is_absolute():
        # 检查文件是否存在
        if Path(file_path).exists():
            return file_path
        # 文件不存在，尝试使用upload_dir
        return f"{upload_dir}/{filename}"
    
    # 相对路径，直接使用
    return file_path


def parse_json_content(content: str) -> dict:
    """
    尝试从AI返回的内容中解析JSON数据
    支持多种JSON格式：纯JSON、Markdown代码块包裹的JSON
    """
    # 尝试直接解析
    try:
        return {"structured": True, "data": json.loads(content), "raw": content}
    except json.JSONDecodeError:
        pass
    
    # 尝试从Markdown代码块中提取JSON
    json_patterns = [
        r'```json\s*(.*?)\s*```',  # ```json ... ```
        r'```\s*(.*?)\s*```',      # ``` ... ```
        r'\{.*\}',                  # 尝试找到JSON对象
    ]
    
    for pattern in json_patterns:
        matches = re.findall(pattern, content, re.DOTALL)
        for match in matches:
            try:
                data = json.loads(match)
                return {"structured": True, "data": data, "raw": content}
            except json.JSONDecodeError:
                continue
    
    # 尝试查找独立的JSON数组
    array_pattern = r'\[[\s\S]*\]'
    matches = re.findall(array_pattern, content)
    for match in matches:
        try:
            data = json.loads(match)
            return {"structured": True, "data": data, "raw": content}
        except json.JSONDecodeError:
            continue
    
    # 无法解析，返回原始内容
    return {"structured": False, "data": None, "raw": content}


@router.post("/chat", summary="AI 聊天")
async def chat(
    request: AIChatRequest,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user)
):
    """AI 聊天接口 - 处理通用对话和专利相关问题"""
    from app.ai.prompts.patent_prompts import SYSTEM_PROMPT
    
    # 构建消息列表
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    
    # 添加历史消息
    for msg in request.history[-10:]:  # 最多保留10条历史
        messages.append({"role": msg.get("role", "user"), "content": msg.get("content", "")})
    
    # 添加当前消息
    messages.append({"role": "user", "content": request.message})
    
    try:
        # 调用 AI
        response = await provider_manager.chat(
            messages=messages,
            provider=request.provider,
            model=request.model
        )
        
        return {
            "code": 200,
            "data": {
                "content": response.content,
                "model": response.model or request.model or "default",
                "provider": response.provider or request.provider or "default",
            }
        }
    except Exception as e:
        logger.error(f"AI聊天失败: {e}")
        raise HTTPException(500, f"AI服务调用失败: {str(e)}")


@router.get("/providers", summary="获取 AI 提供商列表")
async def list_providers(user=Depends(get_current_user)):
    return {"code": 200, "data": provider_manager.list_providers()}


@router.get("/providers/config", summary="获取所有 AI 提供商配置")
async def list_provider_configs(db: AsyncSession = Depends(get_db), user=Depends(get_current_user)):
    """获取所有已配置的 AI 提供商（从数据库）"""
    result = await db.execute(select(AIProviderConfig).order_by(AIProviderConfig.priority))
    configs = result.scalars().all()
    return {"code": 200, "data": [AIProviderConfigSchema.model_validate(c) for c in configs]}


@router.post("/providers/config", summary="创建 AI 提供商配置")
async def create_provider_config(
    config: AIProviderConfigCreate,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user)
):
    """创建新的 AI 提供商配置"""
    if user.role not in ["admin"]:
        raise HTTPException(403, "只有管理员可以配置 AI 提供商")
    
    existing = await db.execute(
        select(AIProviderConfig).where(AIProviderConfig.provider_name == config.provider_name)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(400, f"提供商 {config.provider_name} 已存在")
    
    if config.is_default:
        await db.execute(select(AIProviderConfig).where(AIProviderConfig.is_default == True))
        result = await db.execute(select(AIProviderConfig).where(AIProviderConfig.is_default == True))
        for row in result.scalars():
            row.is_default = False
    
    db_config = AIProviderConfig(**config.model_dump())
    db.add(db_config)
    await db.commit()
    await db.refresh(db_config)
    
    await provider_manager.reload_from_db(db)
    
    return {"code": 200, "data": AIProviderConfigSchema.model_validate(db_config)}


@router.put("/providers/config/{provider_name}", summary="更新 AI 提供商配置")
async def update_provider_config(
    provider_name: str,
    config: AIProviderConfigUpdateFull,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user)
):
    """更新 AI 提供商配置"""
    if user.role not in ["admin"]:
        raise HTTPException(403, "只有管理员可以配置 AI 提供商")
    
    result = await db.execute(
        select(AIProviderConfig).where(AIProviderConfig.provider_name == provider_name)
    )
    db_config = result.scalar_one_or_none()
    if not db_config:
        raise HTTPException(404, f"提供商 {provider_name} 不存在")
    
    update_data = config.model_dump(exclude_unset=True)
    if "is_default" in update_data and update_data["is_default"]:
        result_all = await db.execute(select(AIProviderConfig).where(AIProviderConfig.is_default == True))
        for row in result_all.scalars():
            if row.id != db_config.id:
                row.is_default = False
    
    for key, value in update_data.items():
        setattr(db_config, key, value)
    
    await db.commit()
    await db.refresh(db_config)
    
    await provider_manager.reload_from_db(db)
    
    return {"code": 200, "data": AIProviderConfigSchema.model_validate(db_config)}


@router.delete("/providers/config/{provider_name}", summary="删除 AI 提供商配置")
async def delete_provider_config(
    provider_name: str,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user)
):
    """删除 AI 提供商配置"""
    if user.role not in ["admin"]:
        raise HTTPException(403, "只有管理员可以配置 AI 提供商")
    
    result = await db.execute(
        select(AIProviderConfig).where(AIProviderConfig.provider_name == provider_name)
    )
    db_config = result.scalar_one_or_none()
    if not db_config:
        raise HTTPException(404, f"提供商 {provider_name} 不存在")
    
    await db.delete(db_config)
    await db.commit()
    
    await provider_manager.reload_from_db(db)
    
    return {"code": 200, "message": f"提供商 {provider_name} 已删除"}


@router.post("/providers/config/{provider_name}/test", summary="测试 AI 提供商连接")
async def test_provider_config(
    provider_name: str,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user)
):
    """测试 AI 提供商连接是否正常"""
    result = await db.execute(
        select(AIProviderConfig).where(AIProviderConfig.provider_name == provider_name)
    )
    config = result.scalar_one_or_none()
    if not config:
        raise HTTPException(404, f"提供商 {provider_name} 不存在")
    
    try:
        # 重新加载数据库配置
        await provider_manager.reload_from_db(db)
        
        # 获取配置后的 provider
        provider = provider_manager.get_provider(provider_name)
        
        # 真正测试连接
        is_healthy = await provider.health_check()
        return {"code": 200, "data": {"status": "ok" if is_healthy else "error", "message": "连接成功" if is_healthy else "连接失败"}}
    except Exception as e:
        return {"code": 200, "data": {"status": "error", "message": str(e)}}
async def ai_chat(req: AIChatRequest, db: AsyncSession = Depends(get_db), user=Depends(get_current_user)):
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    for h in req.history[-10:]:
        messages.append(h)
    messages.append({"role": "user", "content": req.message})
    try:
        resp = await provider_manager.chat(messages, provider=req.provider, model=req.model)
        return {"code": 200, "data": {"content": resp.content, "model": resp.model, "provider": resp.provider,
                                      "tokens_used": resp.input_tokens + resp.output_tokens}}
    except ValueError as e:
        # Provider not configured
        return {"code": 503, "data": {"content": f"AI 服务暂不可用: {e}\n\n请在系统设置中配置 AI 提供商的 API Key。",
                                      "model": "none", "provider": "none", "tokens_used": 0}}
    except Exception as e:
        logger.warning(f"AI chat failed: {e}")
        return {"code": 503, "data": {"content": f"AI 服务调用失败: {e}\n\n请检查 AI 提供商配置是否正确，或网络连接是否正常。",
                                      "model": "none", "provider": "none", "tokens_used": 0}}

@router.post("/analyze", summary="AI 分析专利")
async def ai_analyze(req: AIAnalyzeRequest, db: AsyncSession = Depends(get_db), user=Depends(get_current_user)):
    from app.services.patent_service import PatentService
    from app.services.document_parser import DocumentParserService
    from pathlib import Path
    from app.database.models import ExaminationRecord
    from datetime import datetime
    
    patent = await PatentService.get(req.patent_id, db)
    if not patent:
        raise HTTPException(404, "专利不存在")
    
    # 获取完整的专利文档内容
    document_content = ""
    
    # 方法1: 尝试从parsed_content中获取完整内容
    if patent.parsed_content:
        parsed = patent.parsed_content
        parts = []
        
        # 检查parsed_content是否有完整内容
        has_full_content = False
        
        # 请求书信息
        if parsed.get("request_info"):
            parts.append(f"【请求书信息】\n{parsed.get('request_info')}")
            has_full_content = True
        
        # 权利要求书
        if parsed.get("claims"):
            claims_text = ""
            claims = parsed.get("claims", [])
            if isinstance(claims, list) and len(claims) > 0:
                for claim in claims:
                    if isinstance(claim, dict) and claim.get("full_text"):
                        claims_text += f"\n权利要求{claim.get('claim_number', '')}: {claim.get('full_text', '')}"
                    elif isinstance(claim, str):
                        claims_text += f"\n{claim}"
                if claims_text:
                    parts.append(f"【权利要求书】\n{claims_text}")
                    has_full_content = True
        
        # 说明书各部分
        if parsed.get("description"):
            desc = parsed.get("description", {})
            if isinstance(desc, dict) and desc:
                for key, value in desc.items():
                    if value and len(str(value)) > 50:  # 有实质内容
                        parts.append(f"【{key}】\n{value}")
                        has_full_content = True
        
        # 摘要
        if parsed.get("abstract"):
            parts.append(f"【摘要】\n{parsed.get('abstract')}")
            has_full_content = True
        
        # 如果有足够的内容
        if has_full_content and len(parts) >= 2:
            document_content = "\n\n".join(parts)
    
    # 方法2: 如果parsed_content内容不足，尝试读取原始文件
    if not document_content or len(document_content) < 500:
        if patent.file_path:
            # 转换Windows路径为容器内路径
            container_file_path = convert_file_path(patent.file_path)
            file_path = Path(container_file_path)
            
            logger.info(f"尝试读取专利文件: {file_path}")
            
            if file_path.exists():
                try:
                    # 使用DocumentParserService解析文件
                    parser_service = DocumentParserService()
                    parse_result = await parser_service.parse_file(str(file_path))
                    
                    if parse_result.success:
                        # 构建完整的文档内容
                        content_parts = []
                        
                        # 添加请求书信息
                        if parse_result.metadata.application_number or parse_result.metadata.title:
                            request_info = f"申请号: {parse_result.metadata.application_number}\n"
                            request_info += f"专利名称: {parse_result.metadata.title}\n"
                            request_info += f"申请人: {parse_result.metadata.applicant}\n"
                            request_info += f"发明人: {parse_result.metadata.inventor}\n"
                            request_info += f"代理人: {parse_result.metadata.agent}\n"
                            request_info += f"IPC分类: {parse_result.metadata.ipc_classification}\n"
                            content_parts.append(f"【请求书信息】\n{request_info}")
                        
                        # 添加权利要求书
                        if parse_result.structure.claims:
                            claims_text = ""
                            for claim in parse_result.structure.claims:
                                if claim.full_text:
                                    claims_text += f"\n权利要求{claim.claim_number}: {claim.full_text}"
                            if claims_text:
                                content_parts.append(f"【权利要求书】\n{claims_text}")
                        
                        # 添加说明书各部分
                        if parse_result.structure.description:
                            for section, content in parse_result.structure.description.items():
                                if content and len(str(content)) > 10:
                                    content_parts.append(f"【{section}】\n{content}")
                        
                        # 添加摘要
                        if parse_result.structure.abstract:
                            content_parts.append(f"【摘要】\n{parse_result.structure.abstract}")
                        
                        if content_parts:
                            document_content = "\n\n".join(content_parts)
                except Exception as e:
                    logger.warning(f"解析专利文件失败: {e}")
    
    # 不再限制文档内容长度，保持完整内容以获得更准确的AI分析
    # 注意：如果文档过长可能导致AI处理时间较长
    
    # 方法3: 如果仍然没有内容，直接读取原始文件
    if not document_content or len(document_content) < 100:
        if patent.file_path:
            # 转换路径
            container_file_path = convert_file_path(patent.file_path)
            file_path = Path(container_file_path)
            
            # 尝试多种可能的文件扩展名
            possible_paths = [file_path]
            
            # 如果是.doc文件，也尝试.txt版本
            if file_path.suffix.lower() == '.doc':
                txt_path = file_path.with_suffix('.txt')
                possible_paths.append(txt_path)
            
            # 尝试读取任一存在的文件
            for try_path in possible_paths:
                if try_path.exists():
                    try:
                        # 尝试作为文本文件读取
                        raw_content = try_path.read_text(encoding='utf-8', errors='ignore')
                        if raw_content and len(raw_content) > 100:
                            document_content = f"""【专利文档内容】
{raw_content}
"""
                            logger.info(f"直接读取文件内容: {try_path.name}, {len(raw_content)} 字符")
                            break
                    except Exception as e:
                        logger.warning(f"读取文件内容失败: {e}")
        content_parts = []
        if patent.title:
            content_parts.append(f"专利名称: {patent.title}")
        if patent.applicant:
            content_parts.append(f"申请人: {patent.applicant}")
        if patent.inventor:
            content_parts.append(f"发明人: {patent.inventor}")
        if patent.abstract:
            content_parts.append(f"摘要: {patent.abstract}")
        if patent.technical_field:
            content_parts.append(f"技术领域: {patent.technical_field}")
        
        if content_parts:
            document_content = "\n".join(content_parts)
    
    # 最终后备
    if not document_content:
        document_content = patent.title or "专利信息"
    
    # 根据分析类型选择提示词
    prompt_map = {
        "novelty": NOVELTY_ASSESSMENT_PROMPT, "inventiveness": INVENTIVENESS_ASSESSMENT_PROMPT,
        "practicality": PRACTICALITY_ASSESSMENT_PROMPT, "claims": CLAIMS_REVIEW_PROMPT,
        "description": DESCRIPTION_REVIEW_PROMPT, "subject_matter": SUBJECT_MATTER_PROMPT,
        "unity": UNITY_ASSESSMENT_PROMPT,
    }
    template = prompt_map.get(req.analysis_type, DOCUMENT_ANALYSIS_PROMPT)
    
    try:
        prompt = template.format(
            claims=document_content, prior_art="暂无", technical_field=patent.technical_field or "",
            technical_solution=document_content, description=document_content, description_summary=document_content,
            document_content=document_content, ipc_classification=patent.ipc_classification or "",
            application_number=patent.application_number, title=patent.title,
            applicant=patent.applicant, examination_results="")
    except KeyError as e:
        # Template may have extra placeholders; use safe format
        prompt = f"""请对以下专利进行{req.analysis_type}分析：

【专利名称】
{patent.title}

【申请号】
{patent.application_number}

【申请人】
{patent.applicant}

【发明人】
{patent.inventor or '无'}

【技术领域】
{patent.technical_field or '无'}

【专利文档内容】
{document_content}

请给出详细的分析结果，包括：1.发现的问题 2.修改建议 3.审查意见"""

    messages = [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": prompt}]
    try:
        resp = await provider_manager.chat(messages, provider=req.provider, model=req.model)
        
        # 尝试解析JSON内容
        parsed = parse_json_content(resp.content)
        
        # 准备返回数据
        result_data = {
            "content": parsed["raw"], 
            "structured": parsed["structured"],
            "structured_data": parsed["data"],
            "model": resp.model, 
            "provider": resp.provider,
            "analysis_type": req.analysis_type, 
            "tokens_used": resp.input_tokens + resp.output_tokens
        }
        
        # 保存到数据库
        try:
            # 先删除该专利之前的AI分析记录
            from sqlalchemy import delete
            await db.execute(
                delete(ExaminationRecord).where(
                    ExaminationRecord.application_id == req.patent_id,
                    ExaminationRecord.examination_type == "ai_analysis"
                )
            )
            
            # 创建新的AI分析记录
            exam_record = ExaminationRecord(
                application_id=req.patent_id,
                examination_type="ai_analysis",
                examination_step="AI智能分析",
                status="completed",
                result=result_data,
                confidence_score=0.8,
                ai_model_used=resp.model,
                start_time=datetime.now(),
                end_time=datetime.now(),
            )
            db.add(exam_record)
            await db.flush()
        except Exception as save_err:
            logger.warning(f"保存AI分析记录失败: {save_err}")
        
        return {"code": 200, "data": result_data}
    except ValueError as e:
        return {"code": 503, "data": {"content": f"AI 服务暂不可用: {e}\n\n请在系统设置中配置 AI 提供商的 API Key。",
                                      "structured": False,
                                      "structured_data": None,
                                      "model": "none", "provider": "none",
                                      "analysis_type": req.analysis_type, "tokens_used": 0}}
    except Exception as e:
        logger.warning(f"AI analyze failed: {e}")
        return {"code": 503, "data": {"content": f"AI 分析失败: {e}\n\n请检查 AI 提供商配置是否正确，或网络连接是否正常。",
                                      "structured": False,
                                      "structured_data": None,
                                      "model": "none", "provider": "none",
                                      "analysis_type": req.analysis_type, "tokens_used": 0}}

    except Exception as e:
        logger.warning(f"AI analyze failed: {e}")
        return {"code": 503, "data": {"content": f"AI 分析失败: {e}\n\n请检查 AI 提供商配置是否正确，或网络连接是否正常。",
                                      "structured": False,
                                      "structured_data": None,
                                      "model": "none", "provider": "none",
                                      "analysis_type": req.analysis_type, "tokens_used": 0}}

from fastapi.responses import StreamingResponse

@router.get("/providers", summary="获取 AI 提供商列表")
async def list_providers(user=Depends(get_current_user)):
    return {"code": 200, "data": provider_manager.list_providers()}


@router.post("/analyze/stream", summary="流式AI 分析专利")
async def ai_analyze_stream(req: AIAnalyzeRequest, db: AsyncSession = Depends(get_db), user=Depends(get_current_user)):
    """流式AI分析接口 - 通过SSE返回实时进度"""
    from app.services.patent_service import PatentService
    from app.services.document_parser import DocumentParserService
    from pathlib import Path
    from app.database.models import ExaminationRecord
    from datetime import datetime
    import json
    
    patent = await PatentService.get(req.patent_id, db)
    if not patent:
        raise HTTPException(404, "专利不存在")
    
    # 获取文档内容
    document_content = ""
    if patent.parsed_content:
        parsed = patent.parsed_content
        parts = []
        has_full_content = False
        
        if parsed.get("request_info"):
            parts.append(f"【请求书信息】\n{parsed.get('request_info')}")
            has_full_content = True
        
        if parsed.get("claims"):
            claims_text = ""
            claims = parsed.get("claims", [])
            if isinstance(claims, list) and len(claims) > 0:
                for claim in claims:
                    if isinstance(claim, dict) and claim.get("full_text"):
                        claims_text += f"\n权利要求{claim.get('claim_number', '')}: {claim.get('full_text', '')}"
                    elif isinstance(claim, str):
                        claims_text += f"\n{claim}"
                if claims_text:
                    parts.append(f"【权利要求书】\n{claims_text}")
                    has_full_content = True
        
        if parsed.get("description"):
            desc = parsed.get("description", {})
            if isinstance(desc, dict) and desc:
                for key, value in desc.items():
                    if value and len(str(value)) > 50:
                        parts.append(f"【{key}】\n{value}")
                        has_full_content = True
        
        if parsed.get("abstract"):
            parts.append(f"【摘要】\n{parsed.get('abstract')}")
            has_full_content = True
        
        if has_full_content and len(parts) >= 2:
            document_content = "\n\n".join(parts)
    
    if not document_content or len(document_content) < 500:
        if patent.file_path:
            container_file_path = convert_file_path(patent.file_path)
            file_path = Path(container_file_path)
            if file_path.exists():
                try:
                    parser_service = DocumentParserService()
                    parse_result = await parser_service.parse_file(str(file_path))
                    if parse_result.success:
                        content_parts = []
                        # 正确访问: parse_result.structure.request_info
                        if parse_result.structure and parse_result.structure.request_info:
                            content_parts.append(f"【请求书信息】\n{parse_result.structure.request_info}")
                        if parse_result.structure and parse_result.structure.claims:
                            for i, claim in enumerate(parse_result.structure.claims, 1):
                                content_parts.append(f"【权利要求{i}】\n{claim.full_text}")
                        if parse_result.structure and parse_result.structure.description:
                            content_parts.append(f"【说明书】\n{json.dumps(parse_result.structure.description, ensure_ascii=False)[:5000]}")
                        if parse_result.structure and parse_result.structure.abstract:
                            content_parts.append(f"【摘要】\n{parse_result.structure.abstract}")
                        document_content = "\n".join(content_parts)
                except Exception as e:
                    logger.warning(f"读取专利文件失败: {e}")
    
    if not document_content:
        document_content = patent.title or "专利信息"
    
    # 构建提示词
    prompt_map = {
        "novelty": NOVELTY_ASSESSMENT_PROMPT, "inventiveness": INVENTIVENESS_ASSESSMENT_PROMPT,
        "practicality": PRACTICALITY_ASSESSMENT_PROMPT, "claims": CLAIMS_REVIEW_PROMPT,
        "description": DESCRIPTION_REVIEW_PROMPT, "subject_matter": SUBJECT_MATTER_PROMPT,
        "unity": UNITY_ASSESSMENT_PROMPT,
    }
    template = prompt_map.get(req.analysis_type, DOCUMENT_ANALYSIS_PROMPT)
    
    try:
        prompt = template.format(
            claims=document_content, prior_art="暂无", technical_field=patent.technical_field or "",
            technical_solution=document_content, description=document_content, description_summary=document_content,
            document_content=document_content, ipc_classification=patent.ipc_classification or "",
            application_number=patent.application_number, title=patent.title,
            applicant=patent.applicant, examination_results="")
    except KeyError:
        prompt = f"""请对以下专利进行{req.analysis_type}分析：

【专利名称】
{patent.title}

【申请号】
{patent.application_number}

【申请人】
{patent.applicant}

【发明人】
{patent.inventor or '无'}

【技术领域】
{patent.technical_field or '无'}

【专利文档内容】
{document_content}

请给出详细的分析结果，包括：1.发现的问题 2.修改建议 3.审查意见"""

    messages = [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": prompt}]
    
    async def generate():
        full_content = ""
        try:
            yield "data: {\"status\": \"started\", \"message\": \"开始分析...\"}\n\n"
            
            async for chunk in provider_manager.stream(messages, provider=req.provider, model=req.model):
                full_content += chunk
                yield f"data: {{\"status\": \"streaming\", \"content\": {json.dumps(chunk)}}}\n\n"
            
            parsed = parse_json_content(full_content)
            
            try:
                from sqlalchemy import delete
                await db.execute(
                    delete(ExaminationRecord).where(
                        ExaminationRecord.application_id == req.patent_id,
                        ExaminationRecord.examination_type == "ai_analysis"
                    )
                )
                
                result_data = {
                    "content": parsed["raw"],
                    "structured": parsed["structured"],
                    "structured_data": parsed["data"],
                    "model": req.model or "default",
                    "provider": req.provider or "default",
                    "analysis_type": req.analysis_type,
                    "tokens_used": len(full_content) // 4
                }
                
                exam_record = ExaminationRecord(
                    application_id=req.patent_id,
                    examination_type="ai_analysis",
                    examination_step="AI智能分析",
                    status="completed",
                    result=result_data,
                    confidence_score=0.8,
                    ai_model_used=req.model or "default",
                    start_time=datetime.now(),
                    end_time=datetime.now(),
                )
                db.add(exam_record)
                await db.flush()
                await db.commit()
            except Exception as save_err:
                logger.warning(f"保存AI分析记录失败: {save_err}")
            
            yield f"data: {{\"status\": \"completed\", \"content\": {json.dumps(parsed['raw'])}, \"structured\": {json.dumps(parsed['structured'])}, \"structured_data\": {json.dumps(parsed['data'])}}}\n\n"
            
        except Exception as e:
            logger.error(f"流式AI分析失败: {e}")
            yield f"data: {{\"status\": \"error\", \"message\": {json.dumps(str(e))}}}\n\n"
        
        yield "data: [DONE]\n\n"
    
    return StreamingResponse(generate(), media_type="text/event-stream", headers={
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "X-Accel-Buffering": "no",
    })


# ─── RAG 向量搜索接口 ─────────────────────────────────────────────

@router.post("/rag/search", summary="RAG向量搜索")
async def rag_search(
    query: str,
    top_k: int = 5,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user)
):
    """基于语义理解的RAG向量搜索"""
    try:
        from app.ai.vector_db_service import vector_db_service
        
        # 执行向量搜索
        results = await vector_db_service.search(
            query=query,
            top_k=top_k
        )
        
        return {
            "code": 200,
            "data": {
                "query": query,
                "results": [
                    {
                        "id": r.id,
                        "content": r.content,
                        "metadata": r.metadata,
                        "score": r.score
                    }
                    for r in results
                ],
                "total": len(results)
            }
        }
    except Exception as e:
        logger.error(f"RAG搜索失败: {e}")
        return {"code": 500, "message": f"搜索失败: {str(e)}"}


@router.post("/rag/index-patent/{patent_id}", summary="索引专利到向量库")
async def rag_index_patent(
    patent_id: int,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user)
):
    """将专利文档索引到向量库"""
    try:
        from app.ai.vector_db_service import vector_db_service
        from app.services.patent_service import PatentService
        
        # 获取专利
        patent = await PatentService.get(patent_id, db)
        if not patent:
            raise HTTPException(404, "专利不存在")
        
        # 构建文档内容
        content_parts = []
        if patent.title:
            content_parts.append(f"专利名称: {patent.title}")
        if patent.abstract:
            content_parts.append(f"摘要: {patent.abstract}")
        if patent.technical_field:
            content_parts.append(f"技术领域: {patent.technical_field}")
        if patent.parsed_content:
            import json
            content_parts.append(f"详细内容: {json.dumps(patent.parsed_content, ensure_ascii=False)[:5000]}")
        
        content = "\n\n".join(content_parts)
        
        # 索引到向量库
        success = await vector_db_service.add_document(
            doc_id=str(patent_id),
            content=content,
            metadata={
                "patent_id": patent_id,
                "title": patent.title or "",
                "application_number": patent.application_number or "",
                "applicant": patent.applicant or "",
                "ipc_classification": patent.ipc_classification or ""
            }
        )
        
        if success:
            return {"code": 200, "message": "专利已索引到向量库"}
        else:
            return {"code": 500, "message": "索引失败"}
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"索引专利失败: {e}")
        return {"code": 500, "message": f"索引失败: {str(e)}"}


@router.get("/rag/stats", summary="获取向量库统计")
async def rag_stats(user=Depends(get_current_user)):
    """获取向量库统计信息"""
    try:
        from app.ai.vector_db_service import vector_db_service
        stats = await vector_db_service.get_stats()
        return {"code": 200, "data": stats}
    except Exception as e:
        logger.error(f"获取统计失败: {e}")
        return {"code": 500, "data": {"error": str(e)}} 


# ─── 公开专利数据库搜索接口 ─────────────────────────────────────────────

@router.get("/patent/search-external", summary="搜索公开专利数据库")
async def search_external_patents(
    query: str,
    sources: str = "cnipa,uspto,epo,wipo",
    max_results: int = 10,
    user=Depends(get_current_user)
):
    """搜索公开专利数据库"""
    try:
        from app.ai.patent_database_api import patent_aggregator
        
        source_list = [s.strip() for s in sources.split(",") if s.strip()]
        
        results = await patent_aggregator.search_all(
            query=query,
            sources=source_list,
            max_results_per_source=max_results
        )
        
        all_patents = []
        for source, patents in results.items():
            for p in patents:
                all_patents.append({
                    "source": source,
                    "application_number": p.application_number,
                    "title": p.title,
                    "abstract": p.abstract,
                    "applicant": p.applicant,
                    "ipc_classification": p.ipc_classification
                })
        
        return {
            "code": 200,
            "data": {
                "query": query,
                "results": all_patents,
                "total": len(all_patents)
            }
        }
    except Exception as e:
        logger.error(f"搜索公开专利失败: {e}")
        return {"code": 500, "message": f"搜索失败: {str(e)}"}
