"""审查业务服务"""
from __future__ import annotations
import logging
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database.models import PatentApplication, ExaminationRecord
from .document_parser import DocumentParserService
from .rule_engine import RuleEngine

logger = logging.getLogger(__name__)
parser_svc = DocumentParserService()
rule_engine = RuleEngine()


class ExaminationService:

    @staticmethod
    async def run_formal_examination(
        patent_id: int, 
        db: AsyncSession, 
        examiner_id: str | None = None,
        enable_llm_enhancement: bool = False,
        llm_provider: str | None = None
    ) -> dict:
        """形式审查
        
        Args:
            patent_id: 专利ID
            db: 数据库会话
            examiner_id: 审查员ID
            enable_llm_enhancement: 是否启用LLM增强（提升精确度和准确度）
            llm_provider: 指定的LLM提供商
        """
        patent = (await db.execute(select(PatentApplication).where(PatentApplication.id == patent_id))).scalar_one_or_none()
        if not patent:
            raise ValueError("专利不存在")
        # 解析文档
        full_text = ""
        structure = None
        if patent.file_path:
            result = await parser_svc.parse_file(patent.file_path)
            full_text = result.full_text
            structure = result.structure
        if structure is None:
            from .document_parser import PatentStructure
            structure = PatentStructure()
        
        # 获取LLM provider_manager
        provider_manager = None
        if enable_llm_enhancement:
            try:
                from app.ai.provider_manager import provider_manager as pm
                provider_manager = pm
            except Exception as e:
                logger.warning(f"[ExaminationService] 获取LLM provider失败: {e}")
        
        # 执行动态规则（从数据库加载），支持LLM增强
        report = await rule_engine.execute_rules(
            str(patent_id), 
            structure, 
            full_text, 
            level=2, 
            db=db,
            provider_manager=provider_manager,
            enable_llm_comprehensive=enable_llm_enhancement,
            llm_provider=llm_provider
        )
        
        # 保存审查记录
        record = ExaminationRecord(
            application_id=patent_id, examiner_id=examiner_id, examination_type="formal",
            examination_step="形式审查 + 业务规则" + (" + LLM增强" if enable_llm_enhancement else ""), 
            status="completed",
            result=report.to_dict(), confidence_score=report.overall_score / 100.0,
            start_time=datetime.now(), end_time=datetime.now(),
        )
        db.add(record)
        patent.status = "examining"
        await db.flush()
        return report.to_dict()

    @staticmethod
    async def run_substantive_examination(
        patent_id: int, 
        db: AsyncSession, 
        provider: str | None = None,
        enable_llm_enhancement: bool = True
    ) -> dict:
        """实质审查 - 结合 AI 分析
        
        Args:
            patent_id: 专利ID
            db: 数据库会话
            provider: LLM提供商
            enable_llm_enhancement: 是否启用LLM增强检查（提升精确度、准确度、完整度）
        """
        patent = (await db.execute(select(PatentApplication).where(PatentApplication.id == patent_id))).scalar_one_or_none()
        if not patent:
            raise ValueError("专利不存在")
        # 先做形式审查
        full_text = ""
        structure = None
        if patent.file_path:
            result = await parser_svc.parse_file(patent.file_path)
            full_text = result.full_text
            structure = result.structure
        if structure is None:
            from .document_parser import PatentStructure
            structure = PatentStructure()
        
        # 获取LLM provider_manager
        provider_manager = None
        try:
            from app.ai.provider_manager import provider_manager as pm
            provider_manager = pm
        except Exception as e:
            logger.warning(f"[ExaminationService] 获取LLM provider失败: {e}")
        
        # 执行动态规则（从数据库加载），启用LLM增强
        # LLM增强：提升精确度（语义理解）、准确度（精确定位+个性化建议）、完整度（发现规则库外问题）
        report = await rule_engine.execute_rules(
            str(patent_id), 
            structure, 
            full_text, 
            level=2, 
            db=db,
            provider_manager=provider_manager,
            enable_llm_comprehensive=enable_llm_enhancement,
            llm_provider=provider
        )
        
        # AI 辅助分析（额外的权利要求审查）
        ai_analysis = {}
        try:
            from app.ai.provider_manager import provider_manager
            
            # 重新加载数据库配置，确保获取最新配置
            await provider_manager.reload_from_db(db)
            
            # 打印所有已加载的 provider 配置信息（不打印实际 key）
            logger.info(f"[AI] ========== AI Provider 配置信息 ==========")
            for config_name, config in provider_manager._db_configs.items():
                has_key = bool(config.api_key)
                key_preview = config.api_key[:10] + "..." if config.api_key and len(config.api_key) > 10 else "无"
                logger.info(f"[AI] Provider: {config_name}, is_enabled: {config.is_enabled}, is_default: {config.is_default}, has_api_key: {has_key}, api_key: {key_preview}, base_url: {config.base_url}")
            logger.info(f"[AI] ==========================================")
            
            from app.ai.prompts.patent_prompts import CLAIMS_REVIEW_PROMPT, SYSTEM_PROMPT
            claims_text = "\n".join(c.full_text for c in structure.claims) if structure.claims else "无权利要求"
            messages = [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": CLAIMS_REVIEW_PROMPT.format(claims=claims_text, description_summary=full_text[:3000])},
            ]
            
            # 尝试使用指定的 provider，如果失败则尝试其他有有效 API key 的 provider
            providers_to_try = []
            
            # 首先尝试用户指定的 provider（只有当它有有效 API key 时才添加）
            if provider:
                config = provider_manager._db_configs.get(provider)
                if config and config.api_key and config.is_enabled:
                    providers_to_try.append(provider)
                    logger.info(f"[AI] 用户指定 provider: {provider}, api_key存在: {bool(config.api_key)}")
                else:
                    logger.warning(f"[AI] 用户指定的 provider {provider} 没有有效 API Key 或未启用")
            
            # 添加数据库中默认的且有有效 API key 的 provider
            for config_name, config in provider_manager._db_configs.items():
                if config.is_enabled and config.api_key and config.is_default:
                    if config_name not in providers_to_try:
                        providers_to_try.append(config_name)
                        logger.info(f"[AI] 默认 provider: {config_name}, api_key存在: {bool(config.api_key)}")
                        break  # 只添加一个默认的
            
            # 如果没有默认的，添加所有有有效 API key 的 enabled providers
            if not providers_to_try:
                for config_name, config in provider_manager._db_configs.items():
                    if config.is_enabled and config.api_key:
                        if config_name not in providers_to_try:
                            providers_to_try.append(config_name)
                            logger.info(f"[AI] 候选 provider: {config_name}, api_key存在: {bool(config.api_key)}")
            
            logger.info(f"[AI] 最终将尝试的 providers: {providers_to_try}")
            
            last_error = None
            for prov in providers_to_try:
                try:
                    logger.info(f"[AI] 尝试使用提供商: {prov}")
                    resp = await provider_manager.chat(messages, provider=prov)
                    ai_analysis = {"ai_review": resp.content, "model": resp.model, "provider": resp.provider}
                    logger.info(f"[AI] 成功使用提供商: {prov}")
                    break
                except Exception as prov_error:
                    logger.warning(f"[AI] 提供商 {prov} 调用失败: {prov_error}")
                    last_error = prov_error
                    continue
            
            if not ai_analysis:
                raise last_error or Exception("没有可用的 AI 提供商")
                
        except Exception as e:
            logger.warning(f"AI 分析失败: {e}")
            ai_analysis = {"error": str(e)}

        result_data = report.to_dict()
        result_data["ai_analysis"] = ai_analysis

        record = ExaminationRecord(
            application_id=patent_id, examination_type="substantive",
            examination_step="实质审查（含AI辅助）" + (" + LLM增强" if enable_llm_enhancement else ""), 
            status="completed",
            result=result_data, confidence_score=report.overall_score / 100.0,
            ai_model_used=ai_analysis.get("model", ""),
            start_time=datetime.now(), end_time=datetime.now(),
        )
        db.add(record)
        patent.status = "completed"
        await db.flush()
        return result_data

    @staticmethod
    async def get_history(patent_id: int, db: AsyncSession) -> list:
        result = await db.execute(
            select(ExaminationRecord).where(ExaminationRecord.application_id == patent_id).order_by(ExaminationRecord.created_at.desc())
        )
        return list(result.scalars().all())
