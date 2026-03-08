"""AI 提供商适配器基类"""
from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional, AsyncIterator


@dataclass
class AICompletionResponse:
    content: str = ""
    model: str = ""
    provider: str = ""
    input_tokens: int = 0
    output_tokens: int = 0
    finish_reason: str = ""
    raw: dict = field(default_factory=dict)


class AIProviderAdapter(ABC):
    """所有 AI 提供商必须实现此接口"""
    name: str = "base"
    display_name: str = "Base Provider"

    @abstractmethod
    async def chat_completion(
        self,
        messages: list[dict],
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        stream: bool = False,
    ) -> AICompletionResponse:
        ...

    @abstractmethod
    async def chat_completion_stream(
        self,
        messages: list[dict],
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> AsyncIterator[str]:
        ...

    @abstractmethod
    async def health_check(self) -> bool:
        ...

    @abstractmethod
    def get_available_models(self) -> list[str]:
        ...

    def estimate_tokens(self, text: str) -> int:
        """粗略估算 token 数量 (中文约 1.5 char/token)"""
        return max(1, int(len(text) / 1.5))
