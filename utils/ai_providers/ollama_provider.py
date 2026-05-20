"""Ollama implementation of AIProvider."""
from __future__ import annotations

import json
import os
import uuid
from typing import Any, Iterator

import requests

from utils.ai_provider import (
    AIResponse,
    Message,
    ProviderUnavailableError,
    ToolCall,
    ToolSchema,
)


# Exceptions that mean "Ollama is unreachable" — we swallow these into a
# typed ProviderUnavailableError so the chatbot route can return a 503
# instead of a generic 500. Includes the cases that show up when the home
# PC is asleep, the cloudflared tunnel is down, or Cloudflare Access
# rejects the service token.
_UNAVAILABLE_EXC = (
    requests.exceptions.ConnectionError,
    requests.exceptions.Timeout,
    requests.exceptions.ChunkedEncodingError,
)


def _resolve_base_url(explicit: str | None) -> str:
    """Pick the Ollama base URL.

    Accepts either `OLLAMA_BASE_URL` (the documented variable) or the
    older `OLLAMA_URL` for back-compat. Trailing slash stripped.
    """
    raw = (
        explicit
        or os.getenv("OLLAMA_BASE_URL")
        or os.getenv("OLLAMA_URL")
        or "http://localhost:11434"
    )
    return raw.rstrip("/")


def _resolve_extra_headers() -> dict[str, str]:
    """Build the extra-headers dict sent on every Ollama request.

    Two ways to populate:
    1. `OLLAMA_EXTRA_HEADERS` — JSON object, e.g.
       `{"CF-Access-Client-Id": "...", "CF-Access-Client-Secret": "..."}`.
    2. The Cloudflare-Access shortcut pair:
       `OLLAMA_CF_ACCESS_CLIENT_ID` + `OLLAMA_CF_ACCESS_CLIENT_SECRET`.

    Both can be set; CF-Access values override matching keys in the JSON.
    """
    headers: dict[str, str] = {}
    raw_json = os.getenv("OLLAMA_EXTRA_HEADERS")
    if raw_json:
        try:
            parsed = json.loads(raw_json)
            if isinstance(parsed, dict):
                headers.update({str(k): str(v) for k, v in parsed.items()})
        except json.JSONDecodeError:
            pass  # ignore malformed; better to fail open than refuse to start
    cf_id = os.getenv("OLLAMA_CF_ACCESS_CLIENT_ID")
    cf_secret = os.getenv("OLLAMA_CF_ACCESS_CLIENT_SECRET")
    if cf_id and cf_secret:
        headers["CF-Access-Client-Id"] = cf_id
        headers["CF-Access-Client-Secret"] = cf_secret
    return headers


class OllamaProvider:
    def __init__(
        self,
        url: str | None = None,
        model: str | None = None,
        timeout: float = 120.0,
    ):
        self.url = _resolve_base_url(url)
        self.model = model or os.getenv("OLLAMA_MODEL", "gemma4:31b")
        self.timeout = timeout
        self.extra_headers = _resolve_extra_headers()
        self._supports_native_tools: bool | None = None

    def _post(self, path: str, *, json_body: dict[str, Any], stream: bool = False):
        """POST to Ollama with headers + offline-aware error handling."""
        try:
            return requests.post(
                f"{self.url}{path}",
                json=json_body,
                headers=self.extra_headers or None,
                stream=stream,
                timeout=self.timeout,
            )
        except _UNAVAILABLE_EXC as exc:
            raise ProviderUnavailableError(
                f"Ollama at {self.url} is unreachable: {type(exc).__name__}"
            ) from exc

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

        resp = self._post("/api/chat", json_body=body)
        if resp.status_code in (502, 503, 504):
            raise ProviderUnavailableError(
                f"Ollama gateway returned {resp.status_code}"
            )
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

        with self._post("/api/chat", json_body=body, stream=True) as resp:
            if resp.status_code in (502, 503, 504):
                raise ProviderUnavailableError(
                    f"Ollama gateway returned {resp.status_code}"
                )
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
        resp = self._post("/api/chat", json_body=body)
        if resp.status_code in (502, 503, 504):
            raise ProviderUnavailableError(
                f"Ollama gateway returned {resp.status_code}"
            )
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
