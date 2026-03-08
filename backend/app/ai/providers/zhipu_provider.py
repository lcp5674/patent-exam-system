"""智谱 AI (Zhipu / ChatGLM) 提供商适配器"""
from __future__ import annotations
from typing import Optional, AsyncIterator
import httpx, json, logging, time, hashlib, hmac, base64
from app.config import settings
from app.ai.adapter import AIProviderAdapter, AICompletionResponse

logger = logging.getLogger(__name__)

class ZhipuProvider(AIProviderAdapter):
    name = "zhipu"
    display_name = "智谱 AI (ChatGLM)"

    def __init__(self):
        self.api_key = settings.ai.ZHIPU_API_KEY
        self.base_url = settings.ai.ZHIPU_BASE_URL.rstrip("/")
        self.default_model = settings.ai.ZHIPU_DEFAULT_MODEL
        self.timeout = settings.ai.AI_REQUEST_TIMEOUT

    def _generate_token(self) -> str:
        """生成智谱 API JWT Token"""
        if not self.api_key or "." not in self.api_key:
            return self.api_key
        api_id, api_secret = self.api_key.split(".", 1)
        now = int(time.time())
        payload = json.dumps({"api_key": api_id, "exp": now + 3600, "timestamp": now}, separators=(",", ":"))
        return f"Bearer {api_id}.{base64.b64encode(payload.encode()).decode()}"

    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}

    async def chat_completion(self, messages, model=None, temperature=0.7, max_tokens=4096, stream=False) -> AICompletionResponse:
        model = model or self.default_model
        payload = {"model": model, "messages": messages, "temperature": temperature, "max_tokens": max_tokens}
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(f"{self.base_url}/chat/completions", headers=self._headers(), json=payload)
            resp.raise_for_status()
            data = resp.json()
        choice = data["choices"][0]
        usage = data.get("usage", {})
        return AICompletionResponse(content=choice["message"]["content"], model=model, provider=self.name,
            input_tokens=usage.get("prompt_tokens", 0), output_tokens=usage.get("completion_tokens", 0), raw=data)

    async def chat_completion_stream(self, messages, model=None, temperature=0.7, max_tokens=4096) -> AsyncIterator[str]:
        model = model or self.default_model
        payload = {"model": model, "messages": messages, "temperature": temperature, "max_tokens": max_tokens, "stream": True}
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            async with client.stream("POST", f"{self.base_url}/chat/completions", headers=self._headers(), json=payload) as resp:
                async for line in resp.aiter_lines():
                    if line.startswith("data: ") and line != "data: [DONE]":
                        try:
                            yield json.loads(line[6:])["choices"][0]["delta"].get("content", "")
                        except Exception:
                            continue

    async def health_check(self) -> bool:
        return bool(self.api_key)

    def get_available_models(self) -> list[str]:
        return ["glm-4", "glm-4-flash", "glm-3-turbo"]
