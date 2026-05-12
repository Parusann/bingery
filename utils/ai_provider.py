"""Shared AI provider types, protocol, and factory."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any, Iterator, Literal, Protocol


Role = Literal["user", "assistant", "system", "tool"]


@dataclass
class Message:
    role: Role
    content: str
    tool_call_id: str | None = None
    tool_name: str | None = None


@dataclass
class ToolSchema:
    name: str
    description: str
    parameters: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self.parameters,
        }


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: dict[str, Any]


@dataclass
class AIResponse:
    text: str = ""
    tool_calls: list[ToolCall] = field(default_factory=list)
    stop_reason: str | None = None
    usage: dict[str, int] = field(default_factory=dict)


class AIProvider(Protocol):
    def chat(
        self,
        messages: list[Message],
        tools: list[ToolSchema] | None = None,
        system: str | None = None,
        max_tokens: int = 2048,
    ) -> AIResponse: ...

    def stream(
        self,
        messages: list[Message],
        tools: list[ToolSchema] | None = None,
        system: str | None = None,
        max_tokens: int = 2048,
    ) -> Iterator[str]: ...


def get_provider() -> AIProvider:
    """Return an `AIProvider` selected by the `AI_PROVIDER` env var."""
    name = (os.getenv("AI_PROVIDER") or "anthropic").strip().lower()

    if name == "anthropic":
        from utils.ai_providers.anthropic_provider import AnthropicProvider
        return AnthropicProvider()
    if name == "ollama":
        from utils.ai_providers.ollama_provider import OllamaProvider
        return OllamaProvider()

    raise ValueError(f"Unknown AI_PROVIDER: {name!r}. Expected 'anthropic' or 'ollama'.")
