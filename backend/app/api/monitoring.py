"""
监控管理 API
提供系统监控、告警和仪表板数据接口
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Optional, List, Dict, Any
from pydantic import BaseModel
from app.core.security import get_current_user
from app.monitoring.dashboard import monitoring_dashboard, SystemMetrics
from app.monitoring.alerts import alert_manager, Alert, AlertLevel

router = APIRouter()


# ============== Schemas ==============

class MetricsResponse(BaseModel):
    """指标响应"""
    code: int = 200
    data: Dict[str, Any]


class AlertResponse(BaseModel):
    """告警响应"""
    code: int = 200
    data: Dict[str, Any]


class AlertCheckRequest(BaseModel):
    """告警检查请求"""
    metrics: Dict[str, Any]


# ============== Dashboard Endpoints ==============

@router.get("/dashboard/metrics", summary="获取当前系统指标")
async def get_current_metrics(
    user=Depends(get_current_user)
):
    """获取当前系统指标"""
    metrics = monitoring_dashboard.get_current_metrics()
    return {
        "code": 200,
        "data": {
            "system": {
                "cpu_usage_percent": metrics.cpu_usage_percent,
                "memory_usage_percent": metrics.memory_usage_percent,
                "disk_usage_percent": metrics.disk_usage_percent,
                "disk_free_gb": metrics.disk_free_gb,
            },
            "network": {
                "received_mb": metrics.network_received_mb,
                "sent_mb": metrics.network_sent_mb,
            },
            "app": {
                "active_users": metrics.active_users,
                "api_requests_total": metrics.api_requests_total,
                "api_errors_total": metrics.api_errors_total,
                "api_response_time_ms": metrics.api_response_time_ms,
            },
            "db": {
                "connections_active": metrics.db_connections_active,
                "queries_total": metrics.db_queries_total,
            },
            "rag": {
                "recall_rate": metrics.rag_recall_rate,
                "precision_rate": metrics.rag_precision_rate,
                "query_time_ms": metrics.rag_query_time_ms,
                "vector_documents": metrics.vector_db_documents,
                "vector_collections": metrics.vector_db_collections,
            },
            "crawler": {
                "success_rate": metrics.crawler_success_rate,
                "failure_rate": metrics.crawler_failure_rate,
                "docs_crawled_today": metrics.crawler_docs_crawled_today,
                "last_run": metrics.crawler_last_run.isoformat() if metrics.crawler_last_run else None,
            },
            "agents": {
                "online_count": metrics.agent_online_count,
                "offline_count": metrics.agent_offline_count,
                "tasks_running": metrics.agent_tasks_running,
                "offline_minutes": metrics.agent_offline_minutes,
            },
            "celery": {
                "queue_length": metrics.celery_queue_length,
                "workers_active": metrics.celery_workers_active,
                "tasks_processed": metrics.celery_tasks_processed,
            },
            "vector_db": {
                "healthy": metrics.vector_db_healthy,
                "chromadb_collections": metrics.chromadb_collections,
            },
            "timestamp": metrics.timestamp.isoformat()
        }
    }


@router.get("/dashboard/metrics/collect", summary="收集系统指标")
async def collect_metrics(
    user=Depends(get_current_user)
):
    """手动触发收集系统指标"""
    metrics = await monitoring_dashboard.collect_metrics()
    return {
        "code": 200,
        "data": {
            "message": "Metrics collected successfully",
            "timestamp": metrics.timestamp.isoformat()
        }
    }


@router.get("/dashboard/summary", summary="获取指标摘要")
async def get_metrics_summary(
    hours: int = Query(24, ge=1, le=168, description="查询时间范围(小时)"),
    user=Depends(get_current_user)
):
    """获取指标统计摘要"""
    summary = monitoring_dashboard.get_metrics_summary(hours)
    if "error" in summary:
        raise HTTPException(status_code=404, detail=summary["error"])
    return {"code": 200, "data": summary}


@router.get("/dashboard/history", summary="获取指标历史")
async def get_metrics_history(
    hours: int = Query(24, ge=1, le=168, description="查询时间范围(小时)"),
    interval_minutes: int = Query(1, ge=1, le=60, description="采样间隔(分钟)"),
    user=Depends(get_current_user)
):
    """获取历史指标数据"""
    history = monitoring_dashboard.get_metrics_history(hours, interval_minutes)
    return {
        "code": 200,
        "data": {
            "total": len(history),
            "metrics": [
                {
                    "timestamp": m.timestamp.isoformat(),
                    "cpu": m.cpu_usage_percent,
                    "memory": m.memory_usage_percent,
                    "disk": m.disk_usage_percent,
                    "rag_recall": m.rag_recall_rate,
                    "rag_precision": m.rag_precision_rate,
                    "crawler_success_rate": m.crawler_success_rate,
                    "celery_queue": m.celery_queue_length,
                    "vector_db_healthy": m.vector_db_healthy,
                }
                for m in history
            ]
        }
    }


# ============== Alert Endpoints ==============

@router.get("/alerts/rules", summary="获取告警规则列表")
async def get_alert_rules(
    user=Depends(get_current_user)
):
    """获取所有告警规则"""
    rules = []
    for rule in alert_manager.rules:
        rules.append({
            "name": rule.name,
            "level": rule.level.value,
            "message_template": rule.message_template,
            "cooldown_seconds": rule.cooldown_seconds,
            "last_triggered": rule.last_triggered.isoformat() if rule.last_triggered else None,
        })
    return {"code": 200, "data": {"total": len(rules), "rules": rules}}


@router.post("/alerts/check", summary="检查告警")
async def check_alerts(
    request: AlertCheckRequest,
    user=Depends(get_current_user)
):
    """根据提供的指标数据检查是否触发告警"""
    alerts = alert_manager.check_alerts(request.metrics)
    return {
        "code": 200,
        "data": {
            "triggered_count": len(alerts),
            "alerts": [
                {
                    "level": a.level.value,
                    "title": a.title,
                    "message": a.message,
                    "source": a.source,
                    "timestamp": a.timestamp.isoformat(),
                }
                for a in alerts
            ]
        }
    }


@router.get("/alerts/history", summary="获取告警历史")
async def get_alert_history(
    level: Optional[str] = Query(None, description="告警级别过滤 (P0/P1/P2/P3)"),
    limit: int = Query(100, ge=1, le=1000, description="返回记录数"),
    user=Depends(get_current_user)
):
    """获取告警历史记录"""
    level_enum = None
    if level:
        try:
            level_enum = AlertLevel(f"P{level[1]}_EMERGENCY" if level == "P0" else 
                                   f"P{level[1]}_WARNING" if level == "P1" else
                                   f"P{level[1]}_REMINDER" if level == "P2" else
                                   f"P{level[1]}_INFO")
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid alert level")
    
    history = alert_manager.get_alert_history(level_enum, limit)
    return {
        "code": 200,
        "data": {
            "total": len(history),
            "alerts": [
                {
                    "level": a.level.value,
                    "title": a.title,
                    "message": a.message,
                    "source": a.source,
                    "timestamp": a.timestamp.isoformat(),
                }
                for a in history
            ]
        }
    }


@router.post("/alerts/test", summary="测试告警通知")
async def test_alert_notification(
    webhook_url: str = Query(..., description="Webhook URL"),
    notify_type: str = Query("webhook", description="通知类型: webhook/dingtalk/email"),
    user=Depends(get_current_user)
):
    """发送测试告警通知"""
    from app.monitoring.alerts import webhook_notify, dingtalk_notify, AlertLevel
    
    test_alert = Alert(
        level=AlertLevel.P2_REMINDER,
        title="测试告警",
        message="这是一条测试告警，用于验证通知渠道配置是否正确",
        source="monitoring",
    )
    
    try:
        if notify_type == "webhook":
            await webhook_notify(test_alert, webhook_url)
        elif notify_type == "dingtalk":
            await dingtalk_notify(test_alert, webhook_url)
        else:
            raise HTTPException(status_code=400, detail="Unsupported notification type")
        
        return {"code": 200, "data": {"message": "Test notification sent successfully"}}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Notification failed: {str(e)}")
