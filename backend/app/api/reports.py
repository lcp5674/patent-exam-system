"""报告生成 API"""
import re
import json
from datetime import datetime
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from app.database.engine import get_db
from app.database.models import ExaminationRecord, DocumentTemplate, ExaminationOpinion
from app.core.security import get_current_user
from app.services.report_generator import ReportGenerator, SECTION_DEFINITIONS, GRANT_SECTION_DEFINITIONS, REJECTION_SECTION_DEFINITIONS
from app.services.patent_service import PatentService
from app.config import settings

router = APIRouter()
generator = ReportGenerator()


# ─── Pydantic Schemas ───────────────────────────────────────────
class SectionConfig(BaseModel):
    """区块配置"""
    id: str  # 区块ID，如 header, basic_info, issues 等
    enabled: bool = True
    order: int = 0
    custom_content: str | None = None  # 自定义内容（可选）


class TemplateCreate(BaseModel):
    template_name: str
    template_type: str  # opinion_notice / grant_notice / rejection
    content: str | None = None  # 传统变量式模板内容
    section_config: list[SectionConfig] | None = None  # 区块式配置
    variables: dict | None = None
    is_default: bool = False


class TemplateUpdate(BaseModel):
    template_name: str | None = None
    content: str | None = None
    section_config: list[SectionConfig] | None = None
    variables: dict | None = None
    is_default: bool | None = None


def clean_text(text):
    """清理文本中的转义字符"""
    if not text:
        return ""
    # 将 \n, \r, \t 等转换为实际字符
    if isinstance(text, str):
        text = text.replace('\\n', '\n').replace('\\r', '\r').replace('\\t', '\t')
    return text


@router.post("/opinion-notice", summary="生成审查意见通知书")
async def gen_opinion(
    patent_id: int, 
    examination_id: int = None,
    template_id: int = None,
    db: AsyncSession = Depends(get_db), 
    user=Depends(get_current_user)
):
    """生成审查意见通知书 - 从数据库获取审查结果"""
    patent = await PatentService.get(patent_id, db)
    if not patent:
        raise HTTPException(404, "专利不存在")
    
    # 获取审查记录
    if examination_id:
        # 如果指定了审查ID，使用指定的审查记录
        result = await db.execute(
            select(ExaminationRecord).where(ExaminationRecord.id == examination_id)
        )
        exam_record = result.scalar_one_or_none()
    else:
        # 否则获取该专利的最新审查记录（优先获取 formal/substantive 类型的记录）
        # 先尝试获取 formal 类型的记录
        result = await db.execute(
            select(ExaminationRecord)
            .where(
                ExaminationRecord.application_id == patent_id,
                ExaminationRecord.examination_type.in_(["formal", "substantive", "one_click"])
            )
            .order_by(desc(ExaminationRecord.created_at))
            .limit(1)
        )
        exam_record = result.scalar_one_or_none()
        
        # 如果没有 formal/substantive 记录，获取任何审查记录
        if not exam_record:
            result = await db.execute(
                select(ExaminationRecord)
                .where(ExaminationRecord.application_id == patent_id)
                .order_by(desc(ExaminationRecord.created_at))
                .limit(1)
            )
            exam_record = result.scalar_one_or_none()
    
    # 从审查结果中提取问题列表
    issues = []
    if exam_record and exam_record.result:
        exam_result = exam_record.result
        results = exam_result.get("results", [])
        
        # 从规则检查结果中提取未通过的问题
        for r in results:
            if not r.get("passed"):
                rule_name = r.get("display_name") or r.get("rule_name", "")
                rule_issues = r.get("issues", [])
                
                if rule_issues:
                    # 每个问题作为一条
                    for issue in rule_issues:
                        issues.append({
                            "rule_name": clean_text(rule_name),
                            "description": clean_text(issue.get("description", "")),
                            "legal_basis": clean_text(r.get("legal_basis", "")),
                            "suggestions": [clean_text(s) for s in r.get("suggestions", [])],
                            "severity": issue.get("severity", r.get("severity", "warning")),
                            "location": clean_text(issue.get("location", ""))
                        })
                else:
                    # 没有详细问题，使用规则名称
                    issues.append({
                        "rule_name": clean_text(rule_name),
                        "description": clean_text(f"规则检查未通过: {rule_name}"),
                        "legal_basis": clean_text(r.get("legal_basis", "")),
                        "suggestions": [clean_text(s) for s in r.get("suggestions", [])],
                        "severity": r.get("severity", "warning"),
                        "location": ""
                    })
        
        # 从AI分析中提取详细的问题和建议
        ai_analysis = exam_result.get("ai_analysis", {})
        if ai_analysis:
            ai_review = ai_analysis.get("ai_review", "")
            
            # 尝试解析AI分析结果中的JSON
            json_match = re.search(r'```json\s*(\{.*?\})\s*```', ai_review, re.DOTALL)
            if json_match:
                try:
                    ai_data = json.loads(json_match.group(1))
                    review_result = ai_data.get("审查结果", {})
                    problems = review_result.get("具体问题", [])
                    
                    for problem in problems:
                        problem_desc = problem.get("问题描述", "")
                        legal_basis = problem.get("法律依据", "")
                        suggestion = problem.get("修改建议", "")
                        problem_type = problem.get("问题类型", "AI审查")
                        
                        issues.append({
                            "rule_name": f"AI审查-{problem_type}",
                            "description": problem_desc,
                            "legal_basis": legal_basis if legal_basis else "专利法/专利审查指南",
                            "suggestions": [suggestion] if suggestion else [],
                            "severity": "warning",
                            "location": "权利要求书/说明书"
                        })
                    
                    # 添加总体评价
                    overall_summary = review_result.get("总体评价", "")
                    conclusion = review_result.get("审查结论", "")
                    if overall_summary:
                        issues.append({
                            "rule_name": "AI综合审查",
                            "description": f"总体评价: {overall_summary}",
                            "legal_basis": "AI智能分析",
                            "suggestions": [conclusion] if conclusion else [],
                            "severity": "info",
                            "location": "整体"
                        })
                except json.JSONDecodeError:
                    # JSON解析失败
                    pass
    
    # 如果没有审查记录，使用基本信息
    if not issues:
        issues = [{
            "rule_name": "待审查",
            "description": "该专利尚未进行审查，请先执行审查操作",
            "legal_basis": "",
            "suggestions": ["请先执行专利审查"],
            "severity": "info",
            "location": ""
        }]
    
    examiner = user.get("username", "系统审查员") if isinstance(user, dict) else "系统审查员"
    
    # 检查是否使用自定义模板
    template_content = None
    section_config = None
    if template_id:
        result = await db.execute(
            select(DocumentTemplate).where(DocumentTemplate.id == template_id)
        )
        template = result.scalar_one_or_none()
        if template:
            if template.template_type == "opinion_notice":
                # 检查是区块配置还是文本模板
                if template.variables and template.variables.get("section_config"):
                    section_config = template.variables.get("section_config")
                elif template.content:
                    template_content = template.content
    
    # 生成报告
    data = {
        "application_number": patent.application_number,
        "title": patent.title,
        "applicant": patent.applicant,
        "issues": issues,
        "examiner": examiner,
    }
    
    if section_config:
        # 使用区块配置生成
        report = generator.generate_from_sections(section_config, "opinion_notice", data)
    elif template_content:
        # 使用文本模板生成
        report = generator.generate_from_template(template_content, data)
    else:
        # 使用默认硬编码模板
        report = generator.generate_opinion_notice(
            patent.application_number, 
            patent.title, 
            patent.applicant, 
            issues,
            examiner=examiner
        )
    
    # 根据审查结果更新专利状态
    # 如果存在必须修改的问题，状态保持为 examining
    # 如果没有问题了，可以标记为 completed（待授权）
    error_issues = [i for i in issues if i.get("severity") == "error"]
    if len(error_issues) == 0:
        # 没有错误问题，更新状态为 completed
        patent.status = "completed"
        await db.flush()
    
    # 保存报告到数据库
    opinion = ExaminationOpinion(
        application_id=patent_id,
        examination_record_id=exam_record.id if exam_record else None,
        opinion_type="notice",
        content=report,
        template_id=template_id,
        status="finalized",
        created_by=user.get("id") if isinstance(user, dict) else None
    )
    db.add(opinion)
    await db.flush()
    await db.refresh(opinion)
    
    return {"code": 200, "data": {"content": report, "type": "opinion_notice", "issues_count": len(issues), "template_id": template_id, "report_id": opinion.id}}

@router.post("/grant-notice", summary="生成授权通知书")
async def gen_grant(
    patent_id: int, 
    examination_id: int = None,
    template_id: int = None,
    db: AsyncSession = Depends(get_db), 
    user=Depends(get_current_user)
):
    """生成授权通知书"""
    patent = await PatentService.get(patent_id, db)
    if not patent:
        raise HTTPException(404, "专利不存在")
    
    # 获取审查记录，检查是否通过
    exam_record = None
    if examination_id:
        result = await db.execute(
            select(ExaminationRecord).where(ExaminationRecord.id == examination_id)
        )
        exam_record = result.scalar_one_or_none()
    else:
        result = await db.execute(
            select(ExaminationRecord)
            .where(ExaminationRecord.application_id == patent_id)
            .order_by(desc(ExaminationRecord.created_at))
            .limit(1)
        )
        exam_record = result.scalar_one_or_none()
    
    # 检查是否通过审查
    is_passed = False
    if exam_record and exam_record.result:
        is_passed = exam_record.result.get("passed", False)
    
    if not is_passed:
        raise HTTPException(400, "该专利尚未通过审查，无法生成授权通知书")
    
    examiner = user.get("username", "系统审查员") if isinstance(user, dict) else "系统审查员"
    now = datetime.now().strftime("%Y年%m月%d日")
    
    # 检查是否使用自定义模板
    template_content = None
    if template_id:
        result = await db.execute(
            select(DocumentTemplate).where(DocumentTemplate.id == template_id)
        )
        template = result.scalar_one_or_none()
        if template and template.template_type == "grant_notice":
            template_content = template.content
    
    if template_content:
        data = {
            "application_number": patent.application_number,
            "title": patent.title,
            "applicant": patent.applicant,
            "examiner": examiner,
            "date": now,
        }
        report = generator.generate_from_template(template_content, data)
    else:
        report = generator.generate_grant_notice(patent.application_number, patent.title, patent.applicant, examiner)
    
    # 保存报告到数据库
    opinion = ExaminationOpinion(
        application_id=patent_id,
        examination_record_id=exam_record.id if exam_record else None,
        opinion_type="grant",
        content=report,
        template_id=template_id,
        status="finalized",
        created_by=user.get("id") if isinstance(user, dict) else None
    )
    db.add(opinion)
    await db.flush()
    await db.refresh(opinion)
    
    # 更新专利状态为已授权
    patent.status = "granted"
    await db.flush()
    
    return {"code": 200, "data": {"content": report, "type": "grant_notice", "template_id": template_id, "report_id": opinion.id}}

@router.post("/rejection-decision", summary="生成驳回决定书")
async def gen_rejection(
    patent_id: int, 
    examination_id: int = None,
    template_id: int = None,
    db: AsyncSession = Depends(get_db), 
    user=Depends(get_current_user)
):
    """生成驳回决定书"""
    patent = await PatentService.get(patent_id, db)
    if not patent:
        raise HTTPException(404, "专利不存在")
    
    # 获取审查记录
    exam_record = None
    if examination_id:
        result = await db.execute(
            select(ExaminationRecord).where(ExaminationRecord.id == examination_id)
        )
        exam_record = result.scalar_one_or_none()
    else:
        result = await db.execute(
            select(ExaminationRecord)
            .where(ExaminationRecord.application_id == patent_id)
            .order_by(desc(ExaminationRecord.created_at))
            .limit(1)
        )
        exam_record = result.scalar_one_or_none()
    
    # 从审查结果中提取驳回理由
    reasons = []
    if exam_record and exam_record.result:
        exam_result = exam_record.result
        results = exam_result.get("results", [])
        
        for r in results:
            if not r.get("passed") and r.get("severity") == "error":
                rule_name = r.get("display_name") or r.get("rule_name", "")
                issues = r.get("issues", [])
                
                if issues:
                    for issue in issues:
                        reasons.append(f"{rule_name}: {issue.get('description', '')}")
                else:
                    reasons.append(f"{rule_name}: 审查规则检查未通过")
    
    examiner = user.get("username", "系统审查员") if isinstance(user, dict) else "系统审查员"
    now = datetime.now().strftime("%Y年%m月%d日")
    
    # 检查是否使用自定义模板
    template_content = None
    if template_id:
        result = await db.execute(
            select(DocumentTemplate).where(DocumentTemplate.id == template_id)
        )
        template = result.scalar_one_or_none()
        if template and template.template_type == "rejection":
            template_content = template.content
    
    if template_content:
        reasons_text = "\n".join(f"{i+1}. {r}" for i, r in enumerate(reasons))
        data = {
            "application_number": patent.application_number,
            "title": patent.title,
            "applicant": patent.applicant,
            "reasons": reasons_text,
            "reasons_count": len(reasons),
            "examiner": examiner,
            "date": now,
        }
        report = generator.generate_from_template(template_content, data)
    else:
        report = generator.generate_rejection_decision(patent.application_number, patent.title, patent.applicant, reasons, examiner)
    
    # 保存报告到数据库
    opinion = ExaminationOpinion(
        application_id=patent_id,
        examination_record_id=exam_record.id if exam_record else None,
        opinion_type="rejection",
        content=report,
        template_id=template_id,
        status="finalized",
        created_by=user.get("id") if isinstance(user, dict) else None
    )
    db.add(opinion)
    await db.flush()
    await db.refresh(opinion)
    
    # 更新专利状态为已驳回
    patent.status = "rejected"
    await db.flush()
    
    return {"code": 200, "data": {"content": report, "type": "rejection_decision", "reasons_count": len(reasons), "template_id": template_id, "report_id": opinion.id}}


# ─── 报告历史 API ───────────────────────────────────────────

@router.get("/history", summary="获取专利的报告历史")
async def get_report_history(
    patent_id: int,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user)
):
    """获取指定专利的所有已生成报告"""
    result = await db.execute(
        select(ExaminationOpinion)
        .where(ExaminationOpinion.application_id == patent_id)
        .order_by(desc(ExaminationOpinion.created_at))
    )
    opinions = result.scalars().all()
    
    return {
        "code": 200,
        "data": [{
            "id": op.id,
            "opinion_type": op.opinion_type,
            "content": op.content,
            "status": op.status,
            "template_id": op.template_id,
            "examination_record_id": op.examination_record_id,
            "created_at": op.created_at.isoformat() if op.created_at else None,
        } for op in opinions]
    }


@router.get("/{report_id}", summary="获取报告详情")
async def get_report(
    report_id: int,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user)
):
    """获取指定报告的详细内容"""
    result = await db.execute(
        select(ExaminationOpinion).where(ExaminationOpinion.id == report_id)
    )
    opinion = result.scalar_one_or_none()
    
    if not opinion:
        raise HTTPException(404, "报告不存在")
    
    return {
        "code": 200,
        "data": {
            "id": opinion.id,
            "opinion_type": opinion.opinion_type,
            "content": opinion.content,
            "status": opinion.status,
            "template_id": opinion.template_id,
            "examination_record_id": opinion.examination_record_id,
            "created_at": opinion.created_at.isoformat() if opinion.created_at else None,
        }
    }


# ─── 模板管理 API ───────────────────────────────────────────

@router.get("/templates", summary="获取模板列表")
async def list_templates(
    template_type: str | None = None,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user)
):
    """获取所有报告模板，可按类型筛选"""
    query = select(DocumentTemplate)
    if template_type:
        query = query.where(DocumentTemplate.template_type == template_type)
    query = query.order_by(DocumentTemplate.is_default.desc(), DocumentTemplate.created_at.desc())
    
    result = await db.execute(query)
    templates = result.scalars().all()
    
    return {
        "code": 200,
        "data": [{
            "id": t.id,
            "template_name": t.template_name,
            "template_type": t.template_type,
            "content": t.content,
            "section_config": t.variables.get("section_config") if t.variables else None,
            "variables": t.variables,
            "is_default": t.is_default,
            "created_at": t.created_at.isoformat() if t.created_at else None,
            "updated_at": t.updated_at.isoformat() if t.updated_at else None,
        } for t in templates]
    }


@router.get("/templates/{template_id}", summary="获取模板详情")
async def get_template(
    template_id: int,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user)
):
    """获取指定模板的详情"""
    result = await db.execute(
        select(DocumentTemplate).where(DocumentTemplate.id == template_id)
    )
    template = result.scalar_one_or_none()
    
    if not template:
        raise HTTPException(404, "模板不存在")
    
    return {
        "code": 200,
        "data": {
            "id": template.id,
            "template_name": template.template_name,
            "template_type": template.template_type,
            "content": template.content,
            "variables": template.variables,
            "is_default": template.is_default,
            "created_at": template.created_at.isoformat() if template.created_at else None,
            "updated_at": template.updated_at.isoformat() if template.updated_at else None,
        }
    }


@router.post("/templates", summary="创建模板")
async def create_template(
    template: TemplateCreate,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user)
):
    """创建新的报告模板"""
    # 如果设为默认模板，取消其他同类型默认模板
    if template.is_default:
        result = await db.execute(
            select(DocumentTemplate).where(
                DocumentTemplate.template_type == template.template_type,
                DocumentTemplate.is_default == True
            )
        )
        for existing in result.scalars().all():
            existing.is_default = False
    
    new_template = DocumentTemplate(
        template_name=template.template_name,
        template_type=template.template_type,
        content=template.content or "",
        # 将 section_config 存入 variables 中
        variables={
            **(template.variables or {}),
            "section_config": [s.model_dump() for s in template.section_config] if template.section_config else None,
        } if template.section_config or template.variables else None,
        is_default=template.is_default,
    )
    db.add(new_template)
    await db.flush()
    await db.refresh(new_template)
    
    return {
        "code": 200,
        "data": {
            "id": new_template.id,
            "template_name": new_template.template_name,
            "template_type": new_template.template_type,
            "message": "模板创建成功"
        }
    }


@router.put("/templates/{template_id}", summary="更新模板")
async def update_template(
    template_id: int,
    template: TemplateUpdate,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user)
):
    """更新指定模板"""
    result = await db.execute(
        select(DocumentTemplate).where(DocumentTemplate.id == template_id)
    )
    existing = result.scalar_one_or_none()
    
    if not existing:
        raise HTTPException(404, "模板不存在")
    
    # 如果设为默认模板，取消其他同类型默认模板
    if template.is_default and not existing.is_default:
        other_result = await db.execute(
            select(DocumentTemplate).where(
                DocumentTemplate.template_type == existing.template_type,
                DocumentTemplate.is_default == True,
                DocumentTemplate.id != template_id
            )
        )
        for other in other_result.scalars().all():
            other.is_default = False
    
    if template.template_name is not None:
        existing.template_name = template.template_name
    if template.content is not None:
        existing.content = template.content
    if template.variables is not None:
        existing.variables = template.variables
    if template.is_default is not None:
        existing.is_default = template.is_default
    
    await db.flush()
    
    return {
        "code": 200,
        "data": {
            "id": existing.id,
            "template_name": existing.template_name,
            "message": "模板更新成功"
        }
    }


@router.delete("/templates/{template_id}", summary="删除模板")
async def delete_template(
    template_id: int,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user)
):
    """删除指定模板"""
    result = await db.execute(
        select(DocumentTemplate).where(DocumentTemplate.id == template_id)
    )
    template = result.scalar_one_or_none()
    
    if not template:
        raise HTTPException(404, "模板不存在")
    
    # 如果删除的是默认模板，需要提示用户
    was_default = template.is_default
    
    await db.delete(template)
    await db.flush()
    
    message = "模板删除成功"
    if was_default:
        message += "（注意：删除的是默认模板，请及时设置新的默认模板）"
    
    return {"code": 200, "data": {"message": message}}


# ─── 区块定义和模板文件上传 API ───────────────────────────────────────────

@router.get("/sections", summary="获取区块定义")
async def get_section_definitions(
    template_type: str = "opinion_notice"
):
    """获取指定类型报告的可用区块定义"""
    section_map = {
        "opinion_notice": SECTION_DEFINITIONS,
        "grant_notice": GRANT_SECTION_DEFINITIONS,
        "rejection": REJECTION_SECTION_DEFINITIONS,
    }
    
    sections = section_map.get(template_type, SECTION_DEFINITIONS)
    
    return {
        "code": 200,
        "data": {
            "template_type": template_type,
            "sections": [
                {
                    "id": sid,
                    "name": info["name"],
                    "description": info["description"],
                    "has_custom_content": "default_content" not in info,
                    "variables": info.get("variables", []),
                    "default_content": info.get("default_content", ""),
                }
                for sid, info in sections.items()
            ]
        }
    }


@router.post("/templates/upload", summary="上传模板文件")
async def upload_template_file(
    file: UploadFile = File(...),
    template_type: str = "opinion_notice",
    template_name: str | None = None,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user)
):
    """通过上传文件创建模板，支持 .txt, .md 文件"""
    # 读取文件内容
    content = ""
    filename = file.filename or "template.txt"
    
    if filename.endswith('.txt') or filename.endswith('.md'):
        # 文本文件直接读取
        content_bytes = await file.read()
        content = content_bytes.decode('utf-8')
    else:
        raise HTTPException(400, "不支持的文件格式，请上传 .txt 或 .md 文件")
    
    # 使用文件名作为模板名
    name = template_name or filename.rsplit('.', 1)[0]
    
    # 创建模板
    new_template = DocumentTemplate(
        template_name=name,
        template_type=template_type,
        content=content,
        variables={"source": "file", "filename": filename},
        is_default=False,
    )
    db.add(new_template)
    await db.flush()
    await db.refresh(new_template)
    
    return {
        "code": 200,
        "data": {
            "id": new_template.id,
            "template_name": new_template.template_name,
            "message": f"模板文件 '{filename}' 上传成功"
        }
    }
