"""NVIDIA NIM (NVIDIA Inference Microservices) 提供商适配器"""
from __future__ import annotations
from typing import Optional, AsyncIterator
import httpx
import json
import logging
from app.config import settings
from app.ai.adapter import AIProviderAdapter, AICompletionResponse

logger = logging.getLogger(__name__)


class NVIDIAProvider(AIProviderAdapter):
    """NVIDIA NIM 提供商 - 支持 NVIDIA GPU Cloud 和本地部署的 NIM"""
    name = "nvidia"
    display_name = "NVIDIA NIM"

    def __init__(self):
        self.api_key = settings.ai.NVIDIA_API_KEY
        self.base_url = settings.ai.NVIDIA_BASE_URL.rstrip("/")
        self.default_model = settings.ai.NVIDIA_DEFAULT_MODEL
        self.timeout = settings.ai.AI_REQUEST_TIMEOUT

    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}

    async def chat_completion(
        self, 
        messages, 
        model=None, 
        temperature=0.7, 
        max_tokens=4096, 
        stream=False,
        **kwargs
    ) -> AICompletionResponse:
        """调用 NVIDIA NIM API"""
        model = model or self.default_model
        
        # NVIDIA NIM 使用兼容 OpenAI 的 API 格式
        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": False
        }
        
        # 添加额外参数
        if kwargs.get("top_p"):
            payload["top_p"] = kwargs["top_p"]
        if kwargs.get("frequency_penalty"):
            payload["frequency_penalty"] = kwargs["frequency_penalty"]
        if kwargs.get("presence_penalty"):
            payload["presence_penalty"] = kwargs["presence_penalty"]
        
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(
                f"{self.base_url}/chat/completions", 
                headers=self._headers(), 
                json=payload
            )
            resp.raise_for_status()
            data = resp.json()
        
        choice = data["choices"][0]
        usage = data.get("usage", {})
        
        return AICompletionResponse(
            content=choice["message"]["content"],
            model=data.get("model", model),
            provider=self.name,
            input_tokens=usage.get("prompt_tokens", 0),
            output_tokens=usage.get("completion_tokens", 0),
            finish_reason=choice.get("finish_reason", ""),
            raw=data,
        )

    async def chat_completion_stream(
        self, 
        messages, 
        model=None, 
        temperature=0.7, 
        max_tokens=4096
    ) -> AsyncIterator[str]:
        """流式调用 NVIDIA NIM API"""
        model = model or self.default_model
        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True
        }
        
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            async with client.stream(
                "POST", 
                f"{self.base_url}/chat/completions", 
                headers=self._headers(), 
                json=payload
            ) as resp:
                async for line in resp.aiter_lines():
                    if line.startswith("data: ") and line != "data: [DONE]":
                        try:
                            chunk = json.loads(line[6:])
                            delta = chunk["choices"][0].get("delta", {})
                            if "content" in delta:
                                yield delta["content"]
                        except (json.JSONDecodeError, KeyError):
                            continue

    async def health_check(self) -> bool:
        """检查 NVIDIA NIM 服务是否可用"""
        if not self.api_key:
            return False
        try:
            # 尝试调用模型列表接口
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(
                    f"{self.base_url}/models",
                    headers=self._headers()
                )
                return resp.status_code == 200
        except Exception as e:
            logger.warning(f"[NVIDIA] 健康检查失败: {e}")
            return False

    def get_available_models(self) -> list[str]:
        """返回 NVIDIA NIM 支持的模型列表"""
        return [
            # Nemotron 系列 (NVIDIA 官方)
            "nvidia/llama-3.1-nemotron-70b-instruct",
            "nvidia/llama-3.1-nemotron-51b-instruct",
            "nvidia/llama-3.1-nemotron-8b-instruct",
            # Mistral 系列
            "mistralai/mixtral-8x7b-instruct-v0.1",
            "mistralai/mistral-7b-instruct-v0.3",
            # Llama 3.x 系列
            "meta/llama-3.3-70b-instruct",
            "meta/llama-3.1-70b-instruct",
            "meta/llama-3.1-8b-instruct",
            # Qwen 系列
            "qwen/qwen2.5-72b-instruct",
            "qwen/qwen2.5-32b-instruct",
            "qwen/qwen2.5-14b-instruct",
            "qwen/qwen2.5-7b-instruct",
            # Phi 系列 (Microsoft)
            "microsoft/phi-3.5-mini-instruct",
            "microsoft/phi-3-mini-128k-instruct",
            # 其他常用模型
            "google/gemma-2-27b-it",
            "google/gemma-2-9b-it",
            "ai21/jamba-1.5-large-instruct",
            "ai21/jamba-1.5-mini-instruct",
        ]
