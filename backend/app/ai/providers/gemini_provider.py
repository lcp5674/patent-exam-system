"""Google Gemini 提供商适配器"""
from __future__ import annotations
from typing import Optional, AsyncIterator
import httpx
import json
import logging
from app.config import settings
from app.ai.adapter import AIProviderAdapter, AICompletionResponse

logger = logging.getLogger(__name__)


class GeminiProvider(AIProviderAdapter):
    name = "gemini"
    display_name = "Google Gemini"

    def __init__(self):
        self.api_key = settings.ai.GEMINI_API_KEY
        self.base_url = settings.ai.GEMINI_BASE_URL.rstrip("/")
        self.default_model = settings.ai.GEMINI_DEFAULT_MODEL
        self.timeout = settings.ai.AI_REQUEST_TIMEOUT

    def _headers(self) -> dict:
        return {"Content-Type": "application/json"}

    def _convert_messages(self, messages: list[dict]) -> list[dict]:
        """将 OpenAI 格式转换为 Gemini 格式"""
        converted = []
        for msg in messages:
            role = msg.get("role", "user")
            if role == "system":
                role = "user"
            converted.append({"role": role, "parts": [{"text": msg.get("content", "")}]})
        return converted

    async def chat_completion(self, messages, model=None, temperature=0.7, max_tokens=4096, stream=False) -> AICompletionResponse:
        model = model or self.default_model
        contents = self._convert_messages(messages)
        
        payload = {
            "contents": contents,
            "generationConfig": {
                "temperature": temperature,
                "maxOutputTokens": max_tokens,
                "topP": 0.95,
                "topK": 40,
            }
        }
        
        url = f"{self.base_url}/models/{model}:generateContent?key={self.api_key}"
        
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(url, headers=self._headers(), json=payload)
            resp.raise_for_status()
            data = resp.json()
        
        content = ""
        if "candidates" in data and len(data["candidates"]) > 0:
            candidate = data["candidates"][0]
            if "content" in candidate and "parts" in candidate["content"]:
                for part in candidate["content"]["parts"]:
                    content += part.get("text", "")
        
        usage = data.get("usageMetadata", {})
        
        return AICompletionResponse(
            content=content,
            model=model,
            provider=self.name,
            input_tokens=usage.get("promptTokenCount", 0),
            output_tokens=usage.get("candidatesTokenCount", 0),
            finish_reason="stop",
            raw=data,
        )

    async def chat_completion_stream(self, messages, model=None, temperature=0.7, max_tokens=4096) -> AsyncIterator[str]:
        model = model or self.default_model
        contents = self._convert_messages(messages)
        
        payload = {
            "contents": contents,
            "generationConfig": {
                "temperature": temperature,
                "maxOutputTokens": max_tokens,
                "topP": 0.95,
                "topK": 40,
                "stream": True,
            }
        }
        
        url = f"{self.base_url}/models/{model}:streamGenerateContent?key={self.api_key}"
        
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            async with client.stream("POST", url, headers=self._headers(), json=payload) as resp:
                async for line in resp.aiter_lines():
                    if line.strip():
                        try:
                            data = json.loads(line)
                            if "candidates" in data and len(data["candidates"]) > 0:
                                candidate = data["candidates"][0]
                                if "content" in candidate and "parts" in candidate["content"]:
                                    for part in candidate["content"]["parts"]:
                                        yield part.get("text", "")
                        except (json.JSONDecodeError, KeyError):
                            continue

    async def health_check(self) -> bool:
        if not self.api_key:
            return False
        try:
            url = f"{self.base_url}/models?key={self.api_key}"
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(url)
                return resp.status_code == 200
        except Exception:
            return False

    def get_available_models(self) -> list[str]:
        return [
            "gemini-2.0-flash",
            "gemini-2.0-flash-lite",
            "gemini-1.5-pro",
            "gemini-1.5-flash",
            "gemini-1.5-flash-8b",
            "gemini-pro",
            "gemini-pro-vision",
        ]
