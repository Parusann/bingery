"""Anthropic implementation of AIProvider."""
from __future__ import annotations

import os
from typing import Any, Iterator

import anthropic

from utils.ai_provider import AIResponse, Message, ToolCall, ToolSchema


class AnthropicProvider:
    def __init__(self, api_key: str | None = None, model: str | None = None):
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        if not self.api_key:
            raise RuntimeError("ANTHROPIC_API_KEY is not set")
        self.model = model or os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-6")

    def chat(
        self,
        messages: list[Message],
        tools: list[ToolSchema] | None = None,
        system: str | None = None,
        max_tokens: int = 2048,
    ) -> AIResponse:
        client = anthropic.Anthropic(api_key=self.api_key)

        kwargs: dict[str, Any] = {
            "model": self.model,
            "max_tokens": max_tokens,
            "messages": self._to_anthropic_messages(messages),
        }
        if system:
            kwargs["system"] = system
        if tools:
            kwargs["tools"] = [self._to_anthropic_tool(t) for t in tools]

        resp = client.messages.create(**kwargs)
        return self._parse_response(resp)

    def stream(self, messages, tools=None, system=None, max_tokens=2048) -> Iterator[str]:
        client = anthropic.Anthropic(api_key=self.api_key)
        kwargs: dict[str, Any] = {
            "model": self.model,
            "max_tokens": max_tokens,
            "messages": self._to_anthropic_messages(messages),
        }
        if system:
            kwargs["system"] = system
        if tools:
            kwargs["tools"] = [self._to_anthropic_tool(t) for t in tools]

        with client.messages.stream(**kwargs) as stream:
            for chunk in stream.text_stream:
                yield chunk

    @staticmethod
    def _to_anthropic_messages(messages: list[Message]) -> list[dict]:
        out = []
        for m in messages:
            if m.role == "tool":
                out.append({
                    "role": "user",
                    "content": [{
                        "type": "tool_result",
                        "tool_use_id": m.tool_call_id,
                        "content": m.content,
                    }],
                })
            else:
                out.append({"role": m.role, "content": m.content})
        return out

    @staticmethod
    def _to_anthropic_tool(t: ToolSchema) -> dict:
        return {
            "name": t.name,
            "description": t.description,
            "input_schema": t.parameters,
        }

    @staticmethod
    def _parse_response(resp) -> AIResponse:
        text_parts = []
        tool_calls: list[ToolCall] = []
        for block in resp.content:
            if block.type == "text":
                text_parts.append(block.text)
            elif block.type == "tool_use":
                tool_calls.append(ToolCall(
                    id=block.id,
                    name=block.name,
                    arguments=dict(block.input),
                ))
        return AIResponse(
            text="".join(text_parts),
            tool_calls=tool_calls,
            stop_reason=getattr(resp, "stop_reason", None),
            usage={
                "input": getattr(resp.usage, "input_tokens", 0),
                "output": getattr(resp.usage, "output_tokens", 0),
            },
        )
