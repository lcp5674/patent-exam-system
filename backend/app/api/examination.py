"""审查操作 API"""
import json
import re
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from app.database.engine import get_db
from app.core.security import get_current_user
from app.services.exam_service import ExaminationService
from app.schemas.examination import ExaminationRecordResponse
from app.ai.provider_manager import provider_manager
from app.ai.prompts.patent_prompts import SYSTEM_PROMPT
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
    
    # 检查是否是绝对路径（Linux或Windows带盘符）
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
        r'```json\s*(.*?)\s*```',
        r'```\s*(.*?)\s*```',
        r'\{.*\}',
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

@router.post("/{patent_id}/formal", summary="执行形式审查")
async def run_formal(
    patent_id: int, 
    enable_llm: bool = False,
    llm_provider: str | None = None,
    db: AsyncSession = Depends(get_db), 
    user=Depends(get_current_user)
):
    """执行形式审查
    
    Args:
        patent_id: 专利ID
        enable_llm: 是否启用LLM增强（提升精确度、准确度、完整度）
        llm_provider: 指定的LLM提供商
    """
    try:
        result = await ExaminationService.run_formal_examination(
            patent_id, 
            db, 
            str(user.id),
            enable_llm_enhancement=enable_llm,
            llm_provider=llm_provider
        )
        return {"code": 200, "data": result}
    except ValueError as e:
        raise HTTPException(404, str(e))

@router.post("/{patent_id}/substantive", summary="执行实质审查（含AI辅助）")
async def run_substantive(
    patent_id: int, 
    provider: str | None = None,
    enable_llm: bool = True,
    db: AsyncSession = Depends(get_db), 
    user=Depends(get_current_user)
):
    """执行实质审查（含AI辅助）
    
    Args:
        patent_id: 专利ID
        provider: LLM提供商
        enable_llm: 是否启用LLM增强检查（提升精确度、准确度、完整度），默认启用
    """
    try:
        result = await ExaminationService.run_substantive_examination(
            patent_id, 
            db, 
            provider,
            enable_llm_enhancement=enable_llm
        )
        return {"code": 200, "data": result}
    except ValueError as e:
        raise HTTPException(404, str(e))

@router.post("/{patent_id}/one-click", summary="一键审查（完整流程）")
async def run_one_click_examination(
    patent_id: int, 
    provider: str | None = None,
    enable_llm: bool = True,
    db: AsyncSession = Depends(get_db), 
    user=Depends(get_current_user)
):
    """一键完成形式审查、实质审查、AI分析，返回完整审查结果
    
    Args:
        patent_id: 专利ID
        provider: LLM提供商
        enable_llm: 是否启用LLM增强检查（提升精确度、准确度、完整度），默认启用
    """
    from app.services.patent_service import PatentService
    
    result = {
        "patent_id": patent_id,
        "steps_completed": [],
        "formal_result": None,
        "substantive_result": None,
        "ai_analysis": None,
        "issues": [],
        "suggestions": [],
        "overall_status": "pending",
        "score": 0,
        "llm_enhancement_enabled": enable_llm,
    }
    
    # 步骤1: 形式审查（支持LLM增强）
    try:
        formal_result = await ExaminationService.run_formal_examination(
            patent_id, 
            db, 
            str(user.id),
            enable_llm_enhancement=enable_llm,
            llm_provider=provider
        )
        result["formal_result"] = formal_result
        result["steps_completed"].append("formal")
        
        # 收集形式审查问题
        rules = formal_result.get("results", []) if isinstance(formal_result, dict) else []
        for rule in rules:
            if not rule.get("passed"):
                for issue in rule.get("issues", []):
                    result["issues"].append({
                        "stage": "形式审查",
                        "rule": rule.get("display_name", rule.get("rule_name")),
                        "severity": issue.get("severity", "warning"),
                        "message": issue.get("description"),
                        "original_content": issue.get("original_content", ""),
                        "suggested_content": issue.get("suggested_content", ""),
                        "legal_basis": issue.get("legal_reference"),
                    })
                    result["suggestions"].append({
                        "issue": issue.get("description"),
                        "suggestion": issue.get("suggested_content") or _get_suggestion(rule.get("rule_name"), issue.get("severity")),
                    })
    except Exception as e:
        logger.warning(f"形式审查失败: {e}")
        result["formal_result"] = {"error": str(e)}
    
    # 步骤2: 实质审查（支持LLM增强）
    try:
        substantive_result = await ExaminationService.run_substantive_examination(
            patent_id, 
            db, 
            provider,
            enable_llm_enhancement=enable_llm
        )
        result["substantive_result"] = substantive_result
        result["steps_completed"].append("substantive")
        
        # 收集实质审查问题
        rules = substantive_result.get("results", []) if isinstance(substantive_result, dict) else []
        for rule in rules:
            if not rule.get("passed"):
                for issue in rule.get("issues", []):
                    result["issues"].append({
                        "stage": "实质审查",
                        "rule": rule.get("display_name", rule.get("rule_name")),
                        "severity": issue.get("severity", "warning"),
                        "message": issue.get("description"),
                        "original_content": issue.get("original_content", ""),
                        "suggested_content": issue.get("suggested_content", ""),
                        "legal_basis": issue.get("legal_reference"),
                    })
                    result["suggestions"].append({
                        "issue": issue.get("description"),
                        "suggestion": issue.get("suggested_content") or _get_suggestion(rule.get("rule_name"), issue.get("severity")),
                    })
    except Exception as e:
        logger.warning(f"实质审查失败: {e}")
        result["substantive_result"] = {"error": str(e)}
    
    # 步骤3: AI综合分析
    try:
        patent = await PatentService.get(patent_id, db)
        if patent:
            from app.services.document_parser import DocumentParserService
            from pathlib import Path
            
            # 获取完整的专利文档内容
            document_content = ""
            
            # 方法1: 尝试从parsed_content中获取完整内容
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
            
            # 方法2: 读取原始文件
            if not document_content or len(document_content) < 500:
                if patent.file_path:
                    # 转换路径为当前环境可用路径
                    container_file_path = convert_file_path(patent.file_path)
                    file_path = Path(container_file_path)
                    
                    logger.info(f"尝试读取专利文件: {file_path}")
                    
                    if file_path.exists():
                        try:
                            parser_service = DocumentParserService()
                            parse_result = await parser_service.parse_file(str(file_path))
                            
                            if parse_result.success:
                                content_parts = []
                                
                                if parse_result.metadata.application_number or parse_result.metadata.title:
                                    request_info = f"申请号: {parse_result.metadata.application_number}\n"
                                    request_info += f"专利名称: {parse_result.metadata.title}\n"
                                    request_info += f"申请人: {parse_result.metadata.applicant}\n"
                                    request_info += f"发明人: {parse_result.metadata.inventor}\n"
                                    request_info += f"代理人: {parse_result.metadata.agent}\n"
                                    request_info += f"IPC分类: {parse_result.metadata.ipc_classification}\n"
                                    content_parts.append(f"【请求书信息】\n{request_info}")
                                
                                if parse_result.structure.claims:
                                    claims_text = ""
                                    for claim in parse_result.structure.claims:
                                        if claim.full_text:
                                            claims_text += f"\n权利要求{claim.claim_number}: {claim.full_text}"
                                    if claims_text:
                                        content_parts.append(f"【权利要求书】\n{claims_text}")
                                
                                if parse_result.structure.description:
                                    for section, content in parse_result.structure.description.items():
                                        if content and len(str(content)) > 10:
                                            content_parts.append(f"【{section}】\n{content}")
                                
                                if parse_result.structure.abstract:
                                    content_parts.append(f"【摘要】\n{parse_result.structure.abstract}")
                                
                                if content_parts:
                                    document_content = "\n\n".join(content_parts)
                        except Exception as e:
                            logger.warning(f"解析专利文件失败: {e}")
            
            # 方法3: 使用数据库基本字段
            if not document_content or len(document_content) < 100:
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
            
            if not document_content:
                document_content = patent.title or "专利信息"
            
            messages = [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": f"""请对以下专利进行全面的审查分析，包括新颖性、创造性、实用性等方面：

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

请给出：1.发现的问题 2.修改建议 3.审查意见。请尽可能详细地分析专利的权利要求和说明书内容。"""}
            ]
            
            ai_resp = await provider_manager.chat(messages, provider=provider)
            
            # 解析JSON结构化数据
            parsed = parse_json_content(ai_resp.content)
            
            result["ai_analysis"] = {
                "content": ai_resp.content,
                "structured": parsed["structured"],
                "structured_data": parsed["data"],
                "model": ai_resp.model,
                "provider": ai_resp.provider,
                "tokens_used": ai_resp.input_tokens + ai_resp.output_tokens,
            }
            result["steps_completed"].append("ai_analysis")
            
            # 从AI分析中提取问题和建议
            result["suggestions"].append({
                "issue": "AI综合分析结果",
                "suggestion": ai_resp.content[:2000] if ai_resp.content else "无",
            })
    except Exception as e:
        logger.warning(f"AI分析失败: {e}")
        result["ai_analysis"] = {"error": str(e)}
    
    # 计算总体评分
    formal_rules = result["formal_result"].get("results", []) if isinstance(result["formal_result"], dict) else []
    substantive_rules = result["substantive_result"].get("results", []) if isinstance(result["substantive_result"], dict) else []
    
    formal_passed = len([r for r in formal_rules if r.get("passed")]) if formal_rules else 0
    formal_total = len(formal_rules) if formal_rules else 1
    substantive_passed = len([r for r in substantive_rules if r.get("passed")]) if substantive_rules else 0
    substantive_total = len(substantive_rules) if substantive_rules else 1
    
    formal_score = (formal_passed / formal_total * 40) if formal_total > 0 else 0
    substantive_score = (substantive_passed / substantive_total * 40) if substantive_total > 0 else 0
    ai_score = 20 if result.get("ai_analysis") and not result["ai_analysis"].get("error") else 0
    
    result["score"] = int(formal_score + substantive_score + ai_score)
    result["overall_status"] = "pass" if result["score"] >= 80 else "conditional_pass" if result["score"] >= 60 else "fail"
    
    return {"code": 200, "data": result}


def _get_suggestion(rule_name: str, severity: str) -> str:
    """根据规则名称和严重程度返回详细建议"""
    suggestions = {
        # 形式审查规则
        "missing_title": "请补充专利名称。专利名称应简洁、准确地反映发明创造的主题，不超过25个字。",
        "missing_applicant": "请补充申请人信息。申请人为自然人或法人的全称，与申请文件一致。",
        "missing_inventor": "请补充发明人信息。发明人应为对发明创造实质性特点做出贡献的自然人。",
        "missing_abstract": "请撰写摘要。摘要应简要说明发明或实用新型的技术领域、解决的技术问题、技术方案要点和主要用途，字数不超过300字。",
        "invalid_application_number": "申请号格式不正确，应为20位数字或CN+数字格式。",
        "missing_application_date": "请填写申请日。申请日是专利局收到专利申请文件的日期。",
        
        # 实质审查规则
        "invalid_claims": "请检查权利要求书。权利要求应当以说明书为依据，清楚、简要地限定要求专利保护的范围。",
        "insufficient_disclosure": "请补充说明书实施例。说明书应当对发明或实用新型作出清楚、完整的说明，以所属技术领域的技术人员能够实现为准。",
        "unity_defect": "请检查是否符合单一性要求。发明或者实用新型应当属于一个总的发明构思。",
        "lack_novelty": "根据审查意见，该申请缺乏新颖性。建议分析对比文件，明确本发明与现有技术的区别特征。",
        "lack_inventiveness": "根据审查意见，该申请缺乏创造性。请说明本发明具有突出的实质性特点和显著的技术效果。",
        "lack_practicality": "请说明本发明的实用性。本发明必须能够在产业上制造或使用，并能够产生积极效果。",
        "unclear_claim": "权利要求保护范围不清楚。请使用明确的技术术语，避免歧义。",
        "support_issue": "权利要求得不到说明书支持。请修改权利要求，使其与说明书的描述相一致。",
        
        # 格式规则
        "claim_format": "权利要求书格式不规范。请按照规定格式撰写独立权利要求和从属权利要求。",
        "drawing_missing": "请提供附图。发明专利申请必须有附图（特殊情况除外），实用新型必须有附图。",
        "description_incomplete": "说明书撰写不完整。请确保包含技术领域、背景技术、发明内容、具体实施方式等必要部分。",
    }
    
    # 通用建议
    default_suggestions = {
        "error": "该问题导致专利申请无法通过审查。请根据审查意见认真修改申请文件。",
        "warning": "建议按照审查意见进行修改，以提高专利授权可能性。",
        "info": "仅供参考的改进建议，可根据实际情况决定是否修改。",
    }
    
    rule_key = rule_name.lower().replace(" ", "_").replace("-", "_")
    
    # 精确匹配
    if rule_key in suggestions:
        return suggestions[rule_key]
    
    # 模糊匹配
    for key, value in suggestions.items():
        if key in rule_key or rule_key in key:
            return value
    
    return default_suggestions.get(severity, "请根据审查意见进行修改和完善。")


@router.get("/{patent_id}/history", summary="获取审查历史")
async def get_history(patent_id: int, db: AsyncSession = Depends(get_db), user=Depends(get_current_user)):
    records = await ExaminationService.get_history(patent_id, db)
    data = [ExaminationRecordResponse.model_validate(r).model_dump() for r in records]
    return {"code": 200, "data": data}
