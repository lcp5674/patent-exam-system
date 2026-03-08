"""FastAPI 中间件"""
import time
import uuid
import logging
from collections import defaultdict
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse
from app.core.exceptions import PatentExamException
from app.config import settings

logger = logging.getLogger(__name__)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request_id = str(uuid.uuid4())[:8]
        start = time.time()
        response = await call_next(request)
        duration = round((time.time() - start) * 1000, 2)
        logger.info(f"[{request_id}] {request.method} {request.url.path} -> {response.status_code} ({duration}ms)")
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Response-Time"] = f"{duration}ms"
        return response


class ErrorHandlerMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        try:
            return await call_next(request)
        except PatentExamException as e:
            return JSONResponse(status_code=e.http_status, content=e.to_dict())
        except Exception as e:
            logger.exception(f"未处理的异常: {e}")
            return JSONResponse(status_code=500, content={"code": 500, "message": "服务器内部错误", "error_code": "INTERNAL_ERROR"})


class RateLimitMiddleware(BaseHTTPMiddleware):
    """API 限流中间件"""
    def __init__(self, app, requests_per_minute: int = 60):
        super().__init__(app)
        self.requests_per_minute = requests_per_minute
        self.requests = defaultdict(list)
    
    async def dispatch(self, request: Request, call_next):
        # 跳过限流的路径
        skip_paths = ["/docs", "/redoc", "/openapi.json", "/health"]
        if any(request.url.path.startswith(p) for p in skip_paths):
            return await call_next(request)
        
        client_ip = request.client.host
        now = time.time()
        
        # 清理超过1分钟的请求记录
        self.requests[client_ip] = [t for t in self.requests[client_ip] if now - t < 60]
        
        if len(self.requests[client_ip]) >= self.requests_per_minute:
            logger.warning(f"Rate limit exceeded for {client_ip}")
            return JSONResponse(
                status_code=429,
                content={
                    "code": 429,
                    "message": "请求过于频繁，请稍后再试",
                    "error_code": "RATE_LIMIT_EXCEEDED"
                }
            )
        
        self.requests[client_ip].append(now)
        return await call_next(request)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """安全头中间件"""
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        return response
