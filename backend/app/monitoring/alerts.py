"""
监控告警模块
根据IMPLEMENTATION_SUMMARY.md要求的告警规则实现
"""
from __future__ import annotations
import asyncio
import logging
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime
import httpx

logger = logging.getLogger(__name__)


class AlertLevel(Enum):
    """告警级别"""
    P0_EMERGENCY = "P0"  # 紧急告警
    P1_WARNING = "P1"     # 警告
    P2_REMINDER = "P2"     # 提醒
    P3_INFO = "P3"         # 信息


@dataclass
class Alert:
    """告警数据"""
    level: AlertLevel
    title: str
    message: str
    source: str
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)


class AlertRule:
    """告警规则"""
    
    def __init__(
        self,
        name: str,
        level: AlertLevel,
        condition: Callable[[Dict[str, Any]], bool],
        message_template: str,
        cooldown_seconds: int = 300
    ):
        self.name = name
        self.level = level
        self.condition = condition
        self.message_template = message_template
        self.cooldown_seconds = cooldown_seconds
        self.last_triggered: Optional[datetime] = None
    
    def should_alert(self, metrics: Dict[str, Any]) -> bool:
        """检查是否触发告警"""
        # 检查冷却时间
        if self.last_triggered:
            elapsed = (datetime.now() - self.last_triggered).total_seconds()
            if elapsed < self.cooldown_seconds:
                return False
        
        # 检查条件
        try:
            return self.condition(metrics)
        except Exception as e:
            logger.error(f"告警规则 {self.name} 执行失败: {e}")
            return False
    
    def create_alert(self, metrics: Dict[str, Any]) -> Alert:
        """创建告警实例"""
        message = self.message_template.format(**metrics)
        return Alert(
            level=self.level,
            title=f"[{self.level.value}] {self.name}",
            message=message,
            source="monitoring",
            metadata=metrics
        )


class AlertManager:
    """告警管理器"""
    
    def __init__(self):
        self.rules: List[AlertRule] = []
        self.alert_history: List[Alert] = []
        self._notification_channels: Dict[str, Callable] = {}
        self._initialize_default_rules()
    
    def _initialize_default_rules(self):
        """初始化默认告警规则 - 按IMPLEMENTATION_SUMMARY.md要求"""
        
        # P0: 召回率 < 95%
        self.add_rule(AlertRule(
            name="RAG召回率过低",
            level=AlertLevel.P0_EMERGENCY,
            condition=lambda m: m.get("rag_recall_rate", 100) < 95,
            message_template="RAG召回率当前为 {rag_recall_rate}%，低于95%阈值",
            cooldown_seconds=300
        ))
        
        # P0: 准确率 < 95%
        self.add_rule(AlertRule(
            name="RAG准确率过低",
            level=AlertLevel.P0_EMERGENCY,
            condition=lambda m: m.get("rag_precision_rate", 100) < 95,
            message_template="RAG准确率当前为 {rag_precision_rate}%，低于95%阈值",
            cooldown_seconds=300
        ))
        
        # P1: 爬虫失败率 > 5%
        self.add_rule(AlertRule(
            name="爬虫失败率过高",
            level=AlertLevel.P1_WARNING,
            condition=lambda m: m.get("crawler_failure_rate", 0) > 5,
            message_template="爬虫失败率为 {crawler_failure_rate}%，超过5%阈值",
            cooldown_seconds=600
        ))
        
        # P0: Agent失联 > 5分钟
        self.add_rule(AlertRule(
            name="Agent失联",
            level=AlertLevel.P0_EMERGENCY,
            condition=lambda m: m.get("agent_offline_minutes", 0) > 5,
            message_template="Agent已失联 {agent_offline_minutes} 分钟",
            cooldown_seconds=60
        ))
        
        # P2: 磁盘使用率 > 85%
        self.add_rule(AlertRule(
            name="磁盘使用率过高",
            level=AlertLevel.P2_REMINDER,
            condition=lambda m: m.get("disk_usage_percent", 0) > 85,
            message_template="磁盘使用率为 {disk_usage_percent}%，超过85%阈值",
            cooldown_seconds=3600
        ))
        
        # P2: 内存使用率 > 90%
        self.add_rule(AlertRule(
            name="内存使用率过高",
            level=AlertLevel.P2_REMINDER,
            condition=lambda m: m.get("memory_usage_percent", 0) > 90,
            message_template="内存使用率为 {memory_usage_percent}%，超过90%阈值",
            cooldown_seconds=1800
        ))
        
        # P1: Celery队列积压
        self.add_rule(AlertRule(
            name="任务队列积压",
            level=AlertLevel.P1_WARNING,
            condition=lambda m: m.get("celery_queue_length", 0) > 1000,
            message_template="Celery队列积压 {celery_queue_length} 个任务",
            cooldown_seconds=600
        ))
        
        # P1: 向量数据库连接失败
        self.add_rule(AlertRule(
            name="向量数据库连接失败",
            level=AlertLevel.P1_WARNING,
            condition=lambda m: m.get("vector_db_healthy", True) is False,
            message_template="ChromaDB向量数据库连接失败",
            cooldown_seconds=300
        ))
        
        # P2: API响应时间过长
        self.add_rule(AlertRule(
            name="API响应时间过长",
            level=AlertLevel.P2_REMINDER,
            condition=lambda m: m.get("api_response_time_ms", 0) > 5000,
            message_template="API平均响应时间为 {api_response_time_ms}ms，超过5000ms阈值",
            cooldown_seconds=1800
        ))
        
        logger.info(f"已初始化 {len(self.rules)} 个告警规则")
    
    def add_rule(self, rule: AlertRule):
        """添加告警规则"""
        self.rules.append(rule)
    
    def remove_rule(self, name: str):
        """移除告警规则"""
        self.rules = [r for r in self.rules if r.name != name]
    
    def check_alerts(self, metrics: Dict[str, Any]) -> List[Alert]:
        """检查所有规则，返回触发的告警"""
        triggered_alerts = []
        
        for rule in self.rules:
            if rule.should_alert(metrics):
                alert = rule.create_alert(metrics)
                triggered_alerts.append(alert)
                rule.last_triggered = datetime.now()
                self.alert_history.append(alert)
                logger.warning(f"告警触发: {alert.title} - {alert.message}")
        
        # 发送告警通知
        for alert in triggered_alerts:
            self._send_notifications(alert)
        
        return triggered_alerts
    
    def register_notification_channel(
        self, 
        name: str, 
        handler: Callable[[Alert], None]
    ):
        """注册通知渠道"""
        self._notification_channels[name] = handler
    
    def _send_notifications(self, alert: Alert):
        """发送告警通知"""
        for name, handler in self._notification_channels.items():
            try:
                handler(alert)
            except Exception as e:
                logger.error(f"发送告警通知失败 [{name}]: {e}")
    
    def get_alert_history(
        self, 
        level: Optional[AlertLevel] = None,
        limit: int = 100
    ) -> List[Alert]:
        """获取告警历史"""
        history = self.alert_history
        if level:
            history = [a for a in history if a.level == level]
        return history[-limit:]


# Webhook通知
async def webhook_notify(alert: Alert, webhook_url: str):
    """发送Webhook通知"""
    try:
        async with httpx.AsyncClient() as client:
            await client.post(
                webhook_url,
                json={
                    "level": alert.level.value,
                    "title": alert.title,
                    "message": alert.message,
                    "timestamp": alert.timestamp.isoformat(),
                    "metadata": alert.metadata
                },
                timeout=10.0
            )
        logger.info(f"Webhook通知已发送: {alert.title}")
    except Exception as e:
        logger.error(f"Webhook通知发送失败: {e}")


# 钉钉通知
async def dingtalk_notify(alert: Alert, webhook_url: str):
    """发送钉钉通知"""
    try:
        async with httpx.AsyncClient() as client:
            await client.post(
                webhook_url,
                json={
                    "msgtype": "markdown",
                    "markdown": {
                        "title": alert.title,
                        "text": f"## {alert.title}\n\n{alert.message}\n\n时间: {alert.timestamp.strftime('%Y-%m-%d %H:%M:%S')}"
                    }
                },
                timeout=10.0
            )
        logger.info(f"钉钉通知已发送: {alert.title}")
    except Exception as e:
        logger.error(f"钉钉通知发送失败: {e}")


# 邮件通知
async def email_notify(
    alert: Alert, 
    smtp_config: Dict[str, Any],
    recipients: List[str]
):
    """发送邮件通知"""
    try:
        import smtplib
        from email.mime.text import MIMEText
        from email.mime.multipart import MIMEMultipart
        
        msg = MIMEMultipart()
        msg["From"] = smtp_config["from_addr"]
        msg["To"] = ", ".join(recipients)
        msg["Subject"] = f"[{alert.level.value}] {alert.title}"
        
        body = f"""
{alert.title}

级别: {alert.level.value}
时间: {alert.timestamp.strftime('%Y-%m-%d %H:%M:%S')}

{alert.message}

详细信息:
{alert.metadata}
"""
        msg.attach(MIMEText(body, "plain", "utf-8"))
        
        with smtplib.SMTP(
            smtp_config["host"], 
            smtp_config.get("port", 25)
        ) as server:
            if smtp_config.get("use_tls"):
                server.starttls()
            if smtp_config.get("username"):
                server.login(
                    smtp_config["username"], 
                    smtp_config["password"]
                )
            server.send_message(msg)
        
        logger.info(f"邮件通知已发送: {alert.title}")
    except Exception as e:
        logger.error(f"邮件通知发送失败: {e}")


# 全局告警管理器实例
alert_manager = AlertManager()
