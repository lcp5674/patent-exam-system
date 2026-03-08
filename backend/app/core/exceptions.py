"""自定义异常层级"""

class PatentExamException(Exception):
    def __init__(self, message: str = "", error_code: str = "UNKNOWN", details: dict | None = None, http_status: int = 500):
        self.message = message
        self.error_code = error_code
        self.details = details or {}
        self.http_status = http_status
        super().__init__(self.message)

    def to_dict(self) -> dict:
        return {"code": self.http_status, "error_code": self.error_code, "message": self.message, "details": self.details}


class DocumentParseError(PatentExamException):
    def __init__(self, message="文档解析失败", **kw):
        super().__init__(message, error_code="DOC_PARSE_ERROR", http_status=422, **kw)

class RuleEngineError(PatentExamException):
    def __init__(self, message="规则引擎错误", **kw):
        super().__init__(message, error_code="RULE_ENGINE_ERROR", http_status=500, **kw)

class AIProviderError(PatentExamException):
    def __init__(self, message="AI 提供商错误", **kw):
        super().__init__(message, error_code="AI_PROVIDER_ERROR", http_status=502, **kw)

class AIAuthError(AIProviderError):
    def __init__(self, message="AI 认证失败", **kw):
        super().__init__(message, **kw)
        self.error_code = "AI_AUTH_ERROR"
        self.http_status = 401

class AIRateLimitError(AIProviderError):
    def __init__(self, message="AI 请求频率超限", **kw):
        super().__init__(message, **kw)
        self.error_code = "AI_RATE_LIMIT"
        self.http_status = 429

class AuthenticationError(PatentExamException):
    def __init__(self, message="认证失败", **kw):
        super().__init__(message, error_code="AUTH_ERROR", http_status=401, **kw)

class AuthorizationError(PatentExamException):
    def __init__(self, message="权限不足", **kw):
        super().__init__(message, error_code="FORBIDDEN", http_status=403, **kw)

class NotFoundError(PatentExamException):
    def __init__(self, message="资源不存在", **kw):
        super().__init__(message, error_code="NOT_FOUND", http_status=404, **kw)

class ValidationError(PatentExamException):
    def __init__(self, message="参数校验失败", **kw):
        super().__init__(message, error_code="VALIDATION_ERROR", http_status=422, **kw)
