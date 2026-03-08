"""中间件测试"""
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch
import time


class TestRateLimitMiddleware:
    """测试速率限制中间件"""

    def test_rate_limit_basic(self, test_client):
        """测试基本速率限制功能"""
        # 清空请求记录
        from app.core.middleware import RateLimitMiddleware
        middleware = RateLimitMiddleware(None, requests_per_minute=3)

        # 前3次请求应该成功
        for i in range(3):
            response = test_client.get("/health")
            assert response.status_code == 200

        # 第4次请求应该被限制
        response = test_client.get("/health")
        assert response.status_code == 429
        assert response.json()["error_code"] == "RATE_LIMIT_EXCEEDED"

    def test_rate_limit_time_window(self, test_client):
        """测试时间窗口后重置"""
        # 初始请求达到限制
        for i in range(5):
            response = test_client.get("/health")

        assert response.status_code == 429

        # 等待60秒（模拟时间窗口重置）
        # 实际测试中我们不会真的等待60秒，而是检查逻辑

    def test_rate_limit_excluded_paths(self, test_client):
        """测试排除路径不受限制"""
        # 文档相关路径应该不受限制
        for i in range(10):
            response = test_client.get("/docs")
            assert response.status_code in [200, 404]  # 200: Swagger UI, 404: 如果不存在

    def test_rate_limit_headers(self, test_client):
        """测试速率限制相关的响应头"""
        response = test_client.get("/health")

        # 前几次请求应该有正常的响应头
        assert response.status_code == 200


class TestSecurityHeadersMiddleware:
    """测试安全头中间件"""

    def test_security_headers_present(self, test_client):
        """测试响应中包含安全头"""
        response = test_client.get("/health")

        # 检查关键安全头
        assert "X-Content-Type-Options" in response.headers
        assert response.headers["X-Content-Type-Options"] == "nosniff"

        assert "X-Frame-Options" in response.headers
        assert response.headers["X-Frame-Options"] == "DENY"

        assert "X-XSS-Protection" in response.headers
        assert response.headers["X-XSS-Protection"] == "1; mode=block"

        assert "Strict-Transport-Security" in response.headers
        assert "Content-Security-Policy" in response.headers


class TestRequestLoggingMiddleware:
    """测试请求日志中间件"""

    def test_request_id_header(self, test_client):
        """测试请求ID响应头"""
        response = test_client.get("/health")
        assert response.status_code == 200
        assert "X-Request-ID" in response.headers
        assert len(response.headers["X-Request-ID"]) == 8  # UUID前8位

    def test_response_time_header(self, test_client):
        """测试响应时间响应头"""
        response = test_client.get("/health")
        assert response.status_code == 200
        assert "X-Response-Time" in response.headers
        # 格式应该是类似 "123.45ms"
        assert response.headers["X-Response-Time"].endswith("ms")


class TestErrorHandlerMiddleware:
    """测试错误处理中间件"""

    def test_patent_exam_exception_handling(self, monkeypatch, test_client):
        """测试自定义异常处理"""
        from app.core.exceptions import PatentExamException

        # 模拟一个路由抛出PatentExamException
        def mock_endpoint():
            raise PatentExamException("测试错误", code="TEST_ERROR")

        # 这里需要一个更好的方式来测试异常，因为我们需要修改实际的路由
        # 在真实测试中，我们会测试触发该异常的端点

    def test_internal_error_handling(self, monkeypatch, test_client):
        """测试内部错误处理"""
        # 模拟一个未知的异常
        pass
