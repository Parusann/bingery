"""Ollama implementation of AIProvider."""
from __future__ import annotations

import json
import os
import uuid
from typing import Any, Iterator

import requests

from utils.ai_provider import AIResponse, Message, ToolCall, ToolSchema


class OllamaProvider:
    def __init__(
        self,
        url: str | None = None,
        model: str | None = None,
        timeout: float = 120.0,
    ):
        self.url = (url or os.getenv("OLLAMA_URL", "http://localhost:11434")).rstrip("/")
        self.model = model or os.getenv("OLLAMA_MODEL", "gemma4:31b")
        self.timeout = timeout
        self._supports_native_tools: bool | None = None

    def chat(
        self,
        messages: list[Message],
        tools: list[ToolSchema] | None = None,
        system: str | None = None,
        max_tokens: int = 2048,
    ) -> AIResponse:
        ollama_messages = self._to_ollama_messages(messages, system)
        body: dict[str, Any] = {
            "model": self.model,
            "messages": ollama_messages,
            "stream": False,
            "options": {"num_predict": max_tokens},
        }
        if tools:
            body["tools"] = [self._to_ollama_tool(t) for t in tools]

        resp = requests.post(f"{self.url}/api/chat", json=body, timeout=self.timeout)
        resp.raise_for_status()
        data = resp.json()

        parsed = self._parse_response(data)
        if tools and not parsed.tool_calls and not parsed.text.strip():
            # Native tool call returned nothing usable — fallback path handled in Task 5.
            return self._prompt_fallback(messages, tools, system, max_tokens)
        return parsed

    def stream(
        self,
        messages: list[Message],
        tools: list[ToolSchema] | None = None,
        system: str | None = None,
        max_tokens: int = 2048,
    ) -> Iterator[str]:
        ollama_messages = self._to_ollama_messages(messages, system)
        body: dict[str, Any] = {
            "model": self.model,
            "messages": ollama_messages,
            "stream": True,
            "options": {"num_predict": max_tokens},
        }
        if tools:
            body["tools"] = [self._to_ollama_tool(t) for t in tools]

        with requests.post(f"{self.url}/api/chat", json=body, stream=True, timeout=self.timeout) as resp:
            resp.raise_for_status()
            for line in resp.iter_lines():
                if not line:
                    continue
                chunk = json.loads(line)
                piece = chunk.get("message", {}).get("content", "")
                if piece:
                    yield piece

    def _prompt_fallback(
        self,
        messages: list[Message],
        tools: list[ToolSchema],
        system: str | None,
        max_tokens: int,
    ) -> AIResponse:
        """Prompt-based tool use for models without native function-calling."""
        injected_system = _build_tool_prompt(system, tools)
        ollama_messages = self._to_ollama_messages(messages, injected_system)
        body: dict[str, Any] = {
            "model": self.model,
            "messages": ollama_messages,
            "stream": False,
            "options": {"num_predict": max_tokens},
        }
        resp = requests.post(f"{self.url}/api/chat", json=body, timeout=self.timeout)
        resp.raise_for_status()
        data = resp.json()

        text = data.get("message", {}).get("content", "") or ""
        call = _extract_tool_json(text)
        if call:
            return AIResponse(
                text="",
                tool_calls=[ToolCall(
                    id=f"ollama_fb_{uuid.uuid4().hex[:8]}",
                    name=call["tool"],
                    arguments=call.get("arguments", {}) or {},
                )],
                stop_reason="tool_use",
                usage={
                    "input": data.get("prompt_eval_count", 0),
                    "output": data.get("eval_count", 0),
                },
            )
        return AIResponse(
            text=text,
            tool_calls=[],
            stop_reason="stop" if data.get("done") else None,
            usage={
                "input": data.get("prompt_eval_count", 0),
                "output": data.get("eval_count", 0),
            },
        )

    @staticmethod
    def _to_ollama_messages(messages: list[Message], system: str | None) -> list[dict]:
        out: list[dict] = []
        if system:
            out.append({"role": "system", "content": system})
        for m in messages:
            if m.role == "tool":
                out.append({
                    "role": "tool",
                    "name": m.tool_name or "",
                    "content": m.content,
                })
            else:
                out.append({"role": m.role, "content": m.content})
        return out

    @staticmethod
    def _to_ollama_tool(t: ToolSchema) -> dict:
        return {
            "type": "function",
            "function": {
                "name": t.name,
                "description": t.description,
                "parameters": t.parameters,
            },
        }

    @staticmethod
    def _parse_response(data: dict) -> AIResponse:
        msg = data.get("message", {})
        text = msg.get("content", "") or ""
        tool_calls: list[ToolCall] = []
        for call in msg.get("tool_calls", []) or []:
            fn = call.get("function", {})
            args = fn.get("arguments", {})
            if isinstance(args, str):
                try:
                    args = json.loads(args)
                except json.JSONDecodeError:
                    args = {"_raw": args}
            tool_calls.append(ToolCall(
                id=call.get("id") or f"ollama_{uuid.uuid4().hex[:8]}",
                name=fn.get("name", ""),
                arguments=dict(args),
            ))
        usage = {
            "input": data.get("prompt_eval_count", 0),
            "output": data.get("eval_count", 0),
        }
        return AIResponse(
            text=text,
            tool_calls=tool_calls,
            stop_reason="stop" if data.get("done") else None,
            usage=usage,
        )


def _build_tool_prompt(system: str | None, tools: list[ToolSchema]) -> str:
    header = system.strip() if system else ""
    schema_block = json.dumps(
        [{"name": t.name, "description": t.description, "parameters": t.parameters} for t in tools],
        indent=2,
    )
    instructions = (
        "You can call ONE of the following tools by responding with a single JSON "
        "object on its own line formatted exactly as:\n"
        '{"tool": "<tool_name>", "arguments": { ...arguments... }}\n'
        "If no tool is needed, answer in plain prose without JSON.\n\n"
        f"Tools:\n{schema_block}"
    )
    return f"{header}\n\n{instructions}".strip()


def _extract_tool_json(text: str) -> dict | None:
    """Find the first JSON object in `text` that looks like a tool invocation."""
    start = text.find("{")
    while start != -1:
        depth = 0
        for end in range(start, len(text)):
            ch = text[end]
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    candidate = text[start:end + 1]
                    try:
                        parsed = json.loads(candidate)
                    except json.JSONDecodeError:
                        break
                    if isinstance(parsed, dict) and "tool" in parsed:
                        return parsed
                    break
        start = text.find("{", start + 1)
    return None
