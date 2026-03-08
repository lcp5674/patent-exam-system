"""豆包 (Doubao / ByteDance Ark) 提供商适配器"""
from __future__ import annotations
from typing import Optional, AsyncIterator
import httpx, json, logging
from app.config import settings
from app.ai.adapter import AIProviderAdapter, AICompletionResponse

logger = logging.getLogger(__name__)

class DoubaoProvider(AIProviderAdapter):
    name = "doubao"
    display_name = "豆包 (Doubao)"

    def __init__(self):
        self.api_key = settings.ai.DOUBAO_API_KEY
        self.base_url = settings.ai.DOUBAO_BASE_URL.rstrip("/")
        self.default_model = settings.ai.DOUBAO_DEFAULT_MODEL
        self.timeout = settings.ai.AI_REQUEST_TIMEOUT

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
            input_tokens=usage.get("prompt_tokens", 0), output_tokens=usage.get("completion_tokens", 0),
            finish_reason=choice.get("finish_reason", ""), raw=data)

    async def chat_completion_stream(self, messages, model=None, temperature=0.7, max_tokens=4096) -> AsyncIterator[str]:
        model = model or self.default_model
        payload = {"model": model, "messages": messages, "temperature": temperature, "max_tokens": max_tokens, "stream": True}
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            async with client.stream("POST", f"{self.base_url}/chat/completions", headers=self._headers(), json=payload) as resp:
                async for line in resp.aiter_lines():
                    if line.startswith("data: ") and line != "data: [DONE]":
                        try:
                            chunk = json.loads(line[6:])
                            delta = chunk["choices"][0].get("delta", {})
                            if "content" in delta:
                                yield delta["content"]
                        except Exception:
                            continue

    async def health_check(self) -> bool:
        return bool(self.api_key and self.default_model)

    def get_available_models(self) -> list[str]:
        return [self.default_model] if self.default_model else []
