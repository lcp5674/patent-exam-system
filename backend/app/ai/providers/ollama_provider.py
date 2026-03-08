"""Ollama 本地模型提供商适配器"""
from __future__ import annotations
from typing import Optional, AsyncIterator
import httpx, json, logging
from app.config import settings
from app.ai.adapter import AIProviderAdapter, AICompletionResponse

logger = logging.getLogger(__name__)

class OllamaProvider(AIProviderAdapter):
    name = "ollama"
    display_name = "Ollama (本地模型)"

    def __init__(self):
        self.base_url = settings.ai.OLLAMA_BASE_URL.rstrip("/")
        self.default_model = settings.ai.OLLAMA_DEFAULT_MODEL
        self.timeout = settings.ai.AI_REQUEST_TIMEOUT

    async def chat_completion(self, messages, model=None, temperature=0.7, max_tokens=4096, stream=False) -> AICompletionResponse:
        model = model or self.default_model
        payload = {"model": model, "messages": messages, "stream": False,
                   "options": {"temperature": temperature, "num_predict": max_tokens}}
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(f"{self.base_url}/api/chat", json=payload)
            resp.raise_for_status()
            data = resp.json()
        return AICompletionResponse(content=data.get("message", {}).get("content", ""), model=model,
            provider=self.name, input_tokens=data.get("prompt_eval_count", 0),
            output_tokens=data.get("eval_count", 0), raw=data)

    async def chat_completion_stream(self, messages, model=None, temperature=0.7, max_tokens=4096) -> AsyncIterator[str]:
        model = model or self.default_model
        payload = {"model": model, "messages": messages, "stream": True,
                   "options": {"temperature": temperature, "num_predict": max_tokens}}
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            async with client.stream("POST", f"{self.base_url}/api/chat", json=payload) as resp:
                async for line in resp.aiter_lines():
                    if line.strip():
                        try:
                            data = json.loads(line)
                            content = data.get("message", {}).get("content", "")
                            if content:
                                yield content
                        except Exception:
                            continue

    async def health_check(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                resp = await client.get(f"{self.base_url}/api/tags")
                return resp.status_code == 200
        except Exception:
            return False

    def get_available_models(self) -> list[str]:
        return ["qwen2.5:7b", "qwen2.5:14b", "llama3:8b", "chatglm3:6b", "deepseek-coder:6.7b"]
