"""API 路由总注册"""
from fastapi import APIRouter
from . import patents, examination, rules, ai_service, documents, reports, users, system, tenants, rag, workflow, multimodal, monitoring

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(patents.router, prefix="/patents", tags=["专利管理"])
api_router.include_router(examination.router, prefix="/examination", tags=["审查操作"])
api_router.include_router(rules.router, prefix="/rules", tags=["规则引擎"])
api_router.include_router(ai_service.router, prefix="/ai", tags=["AI 服务"])
api_router.include_router(documents.router, prefix="/documents", tags=["文档管理"])
api_router.include_router(reports.router, prefix="/reports", tags=["报告中心"])
api_router.include_router(users.router, prefix="/users", tags=["用户管理"])
api_router.include_router(system.router, prefix="/system", tags=["系统管理"])
api_router.include_router(tenants.router, prefix="/tenants", tags=["租户管理"])
api_router.include_router(rag.router, prefix="/rag", tags=["RAG增强"])
api_router.include_router(workflow.router, prefix="/workflow", tags=["工作流引擎"])
api_router.include_router(multimodal.router, prefix="/multimodal", tags=["多模态RAG"])
api_router.include_router(monitoring.router, prefix="/monitoring", tags=["系统监控"])
