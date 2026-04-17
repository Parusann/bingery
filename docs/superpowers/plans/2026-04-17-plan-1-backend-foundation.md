# Bingery Backend Foundation — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Introduce a provider-agnostic AI layer (Ollama + Anthropic, switchable via env), add Collection / CollectionItem models, and expose new backend endpoints for Stats, Collections, Activity, Seasonal, and Compare features. The existing `static/index.html` keeps working throughout.

**Architecture:** A thin `AIProvider` protocol with two implementations, selected at runtime by `AI_PROVIDER` env var. Tool definitions live in a provider-neutral JSON Schema module; each provider adapts them. Data model gains two SQLAlchemy tables (`Collection`, `CollectionItem`). Five new Flask blueprints expose feature endpoints. All existing endpoints, models, and code paths are preserved.

**Tech Stack:** Python 3.11+, Flask 3, SQLAlchemy, Flask-JWT-Extended, pytest + pytest-flask, `responses` for HTTP mocking, existing `anthropic` SDK, plain `requests` for Ollama.

**Spec reference:** `docs/superpowers/specs/2026-04-17-bingery-revamp-design.md`

---

## File Structure Map

**Created**
- `utils/ai_provider.py` — shared types, `AIProvider` protocol, `get_provider()` factory.
- `utils/ai_providers/__init__.py` — package marker.
- `utils/ai_providers/anthropic_provider.py` — `AnthropicProvider` implementation.
- `utils/ai_providers/ollama_provider.py` — `OllamaProvider` implementation with native + fallback paths.
- `utils/ai_tools.py` — single JSON-Schema tool definitions.
- `utils/tokens.py` — `generate_share_token()` helper.
- `routes/collections.py` — Collections CRUD + items + public share.
- `routes/stats.py` — Stats dashboard payloads.
- `routes/activity.py` — Activity feed.
- `routes/seasonal.py` — Seasonal calendar.
- `routes/compare.py` — Compare view.
- `tests/conftest.py` — shared pytest fixtures.
- `tests/test_ai_provider.py`, `tests/test_anthropic_provider.py`, `tests/test_ollama_provider.py`, `tests/test_ai_tools.py`.
- `tests/test_collections.py`, `tests/test_stats.py`, `tests/test_activity.py`, `tests/test_seasonal.py`, `tests/test_compare.py`.
- `tests/test_chatbot_integration.py`.
- `pytest.ini` — configuration.
- `.env.example` — document both provider configs.

**Modified**
- `requirements.txt` — add pytest, pytest-flask, responses.
- `models.py` — append `Collection`, `CollectionItem` models.
- `routes/chatbot.py` — rewire to use `AIProvider`.
- `app.py` — register new blueprints.

---

## Task 1: Add test dependencies and pytest configuration

**Files:**
- Modify: `requirements.txt`
- Create: `pytest.ini`
- Create: `tests/__init__.py`
- Create: `tests/conftest.py`

- [ ] **Step 1: Append test deps to `requirements.txt`**

Open `requirements.txt` and append these three lines at the end:

```
pytest==8.1.1
pytest-flask==1.3.0
responses==0.25.0
```

- [ ] **Step 2: Create `pytest.ini`**

```ini
[pytest]
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
filterwarnings =
    ignore::DeprecationWarning:flask_sqlalchemy.*
    ignore::DeprecationWarning:sqlalchemy.*
```

- [ ] **Step 3: Create `tests/__init__.py`** (empty file)

- [ ] **Step 4: Create `tests/conftest.py`**

```python
"""Shared pytest fixtures for Bingery backend tests."""
import os
import pytest

# Ensure tests do not pick up developer env vars.
os.environ.setdefault("AI_PROVIDER", "anthropic")
os.environ.setdefault("ANTHROPIC_API_KEY", "test-key")
os.environ.setdefault("JWT_SECRET_KEY", "test-jwt-secret")
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")


@pytest.fixture
def app():
    from app import create_app
    from models import db

    flask_app = create_app()
    flask_app.config.update(
        TESTING=True,
        SQLALCHEMY_DATABASE_URI="sqlite:///:memory:",
        JWT_SECRET_KEY="test-jwt-secret",
    )

    with flask_app.app_context():
        db.create_all()
        yield flask_app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def auth_headers(app):
    """Return headers with a JWT for a fresh test user."""
    from flask_jwt_extended import create_access_token
    from flask_bcrypt import Bcrypt
    from models import db, User

    bcrypt = Bcrypt(app)
    user = User(
        username="tester",
        email="tester@example.com",
        password=bcrypt.generate_password_hash("password").decode("utf-8"),
    )
    db.session.add(user)
    db.session.commit()

    with app.app_context():
        token = create_access_token(identity=str(user.id))

    return {"Authorization": f"Bearer {token}"}, user
```

- [ ] **Step 5: Install and smoke-test**

```bash
pip install -r requirements.txt
python -m pytest --collect-only
```

Expected: `collected 0 items` (no tests yet; confirms pytest discovers the `tests/` dir).

- [ ] **Step 6: Commit**

```bash
git add requirements.txt pytest.ini tests/__init__.py tests/conftest.py
git commit -m "Add pytest and test scaffolding"
```

---

## Task 2: AI provider shared types and factory

**Files:**
- Create: `utils/ai_provider.py`
- Create: `tests/test_ai_provider.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_ai_provider.py`:

```python
"""Tests for AI provider shared types and factory."""
import os
import pytest

from utils.ai_provider import (
    Message,
    ToolSchema,
    ToolCall,
    AIResponse,
    get_provider,
)


def test_message_is_simple_container():
    m = Message(role="user", content="hello")
    assert m.role == "user"
    assert m.content == "hello"


def test_tool_schema_round_trips_to_dict():
    schema = ToolSchema(
        name="search",
        description="search titles",
        parameters={"type": "object", "properties": {"q": {"type": "string"}}},
    )
    d = schema.to_dict()
    assert d["name"] == "search"
    assert d["parameters"]["properties"]["q"]["type"] == "string"


def test_ai_response_defaults_are_safe():
    r = AIResponse(text="hi")
    assert r.text == "hi"
    assert r.tool_calls == []
    assert r.stop_reason is None


def test_factory_returns_anthropic_by_default(monkeypatch):
    monkeypatch.setenv("AI_PROVIDER", "anthropic")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "k")
    provider = get_provider()
    assert provider.__class__.__name__ == "AnthropicProvider"


def test_factory_returns_ollama(monkeypatch):
    monkeypatch.setenv("AI_PROVIDER", "ollama")
    monkeypatch.setenv("OLLAMA_MODEL", "gemma4:31b")
    provider = get_provider()
    assert provider.__class__.__name__ == "OllamaProvider"


def test_factory_rejects_unknown_provider(monkeypatch):
    monkeypatch.setenv("AI_PROVIDER", "nonsense")
    with pytest.raises(ValueError, match="Unknown AI_PROVIDER"):
        get_provider()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_ai_provider.py -v`
Expected: All 6 fail with `ModuleNotFoundError: utils.ai_provider`.

- [ ] **Step 3: Create `utils/ai_provider.py`**

```python
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
```

- [ ] **Step 4: Create `utils/ai_providers/__init__.py`** (empty file)

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m pytest tests/test_ai_provider.py -v`

Expected: 4 pass (the tests that don't require the concrete providers); 2 fail on `ImportError: AnthropicProvider` / `OllamaProvider`. That is acceptable — these tests will re-run in Tasks 3 and 4 and go green then.

Temporarily skip the factory tests so the suite is green before moving on. Add `@pytest.mark.skip(reason="provider class added in later task")` above `test_factory_returns_anthropic_by_default` and `test_factory_returns_ollama`.

Run again: `python -m pytest tests/test_ai_provider.py -v`
Expected: 4 passed, 2 skipped.

- [ ] **Step 6: Commit**

```bash
git add utils/ai_provider.py utils/ai_providers/__init__.py tests/test_ai_provider.py
git commit -m "Introduce AIProvider protocol and shared types"
```

---

## Task 3: AnthropicProvider

**Files:**
- Create: `utils/ai_providers/anthropic_provider.py`
- Create: `tests/test_anthropic_provider.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_anthropic_provider.py`:

```python
"""Tests for AnthropicProvider."""
from unittest.mock import MagicMock, patch
import pytest

from utils.ai_provider import Message, ToolSchema
from utils.ai_providers.anthropic_provider import AnthropicProvider


def _fake_text_response(text: str):
    block = MagicMock()
    block.type = "text"
    block.text = text
    resp = MagicMock()
    resp.content = [block]
    resp.stop_reason = "end_turn"
    resp.usage.input_tokens = 3
    resp.usage.output_tokens = 5
    return resp


def _fake_tool_response(name: str, args: dict, call_id: str = "call_1"):
    tool_block = MagicMock()
    tool_block.type = "tool_use"
    tool_block.id = call_id
    tool_block.name = name
    tool_block.input = args
    resp = MagicMock()
    resp.content = [tool_block]
    resp.stop_reason = "tool_use"
    resp.usage.input_tokens = 3
    resp.usage.output_tokens = 5
    return resp


@patch("utils.ai_providers.anthropic_provider.anthropic.Anthropic")
def test_chat_returns_text(anthropic_cls):
    client = anthropic_cls.return_value
    client.messages.create.return_value = _fake_text_response("hello world")

    provider = AnthropicProvider(api_key="k")
    out = provider.chat([Message(role="user", content="hi")])

    assert out.text == "hello world"
    assert out.tool_calls == []
    assert out.stop_reason == "end_turn"
    assert out.usage == {"input": 3, "output": 5}


@patch("utils.ai_providers.anthropic_provider.anthropic.Anthropic")
def test_chat_passes_system_and_tools(anthropic_cls):
    client = anthropic_cls.return_value
    client.messages.create.return_value = _fake_text_response("ok")

    provider = AnthropicProvider(api_key="k")
    tool = ToolSchema(
        name="search_db",
        description="search local DB",
        parameters={"type": "object", "properties": {"q": {"type": "string"}}},
    )
    provider.chat(
        [Message(role="user", content="hi")],
        tools=[tool],
        system="you are helpful",
    )

    kwargs = client.messages.create.call_args.kwargs
    assert kwargs["system"] == "you are helpful"
    assert kwargs["tools"] == [
        {
            "name": "search_db",
            "description": "search local DB",
            "input_schema": {"type": "object", "properties": {"q": {"type": "string"}}},
        }
    ]


@patch("utils.ai_providers.anthropic_provider.anthropic.Anthropic")
def test_chat_parses_tool_call(anthropic_cls):
    client = anthropic_cls.return_value
    client.messages.create.return_value = _fake_tool_response("search_db", {"q": "frieren"})

    provider = AnthropicProvider(api_key="k")
    out = provider.chat([Message(role="user", content="find")], tools=[])

    assert out.tool_calls[0].name == "search_db"
    assert out.tool_calls[0].arguments == {"q": "frieren"}
    assert out.tool_calls[0].id == "call_1"
    assert out.stop_reason == "tool_use"


def test_provider_requires_api_key(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="ANTHROPIC_API_KEY"):
        AnthropicProvider()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_anthropic_provider.py -v`
Expected: `ModuleNotFoundError: utils.ai_providers.anthropic_provider`.

- [ ] **Step 3: Create `utils/ai_providers/anthropic_provider.py`**

```python
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
```

- [ ] **Step 4: Un-skip the factory test for Anthropic**

In `tests/test_ai_provider.py` remove the `@pytest.mark.skip` above `test_factory_returns_anthropic_by_default`.

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m pytest tests/test_anthropic_provider.py tests/test_ai_provider.py -v`
Expected: all pass (one factory test still skipped — the Ollama one).

- [ ] **Step 6: Commit**

```bash
git add utils/ai_providers/anthropic_provider.py tests/test_anthropic_provider.py tests/test_ai_provider.py
git commit -m "Implement AnthropicProvider"
```

---

## Task 4: OllamaProvider — native tool calling path

**Files:**
- Create: `utils/ai_providers/ollama_provider.py`
- Create: `tests/test_ollama_provider.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_ollama_provider.py`:

```python
"""Tests for OllamaProvider — native tool-calling path."""
import json
import responses

from utils.ai_provider import Message, ToolSchema
from utils.ai_providers.ollama_provider import OllamaProvider


OLLAMA_URL = "http://localhost:11434/api/chat"


@responses.activate
def test_chat_returns_text():
    responses.post(
        OLLAMA_URL,
        json={"message": {"role": "assistant", "content": "hello there"}, "done": True},
    )

    provider = OllamaProvider(url="http://localhost:11434", model="gemma4:31b")
    out = provider.chat([Message(role="user", content="hi")])

    assert out.text == "hello there"
    assert out.tool_calls == []


@responses.activate
def test_chat_sends_tools_in_request():
    responses.post(
        OLLAMA_URL,
        json={"message": {"role": "assistant", "content": "ok"}, "done": True},
    )
    tool = ToolSchema(
        name="search_db",
        description="search",
        parameters={"type": "object", "properties": {"q": {"type": "string"}}},
    )

    provider = OllamaProvider(url="http://localhost:11434", model="gemma4:31b")
    provider.chat([Message(role="user", content="hi")], tools=[tool])

    body = json.loads(responses.calls[0].request.body)
    assert body["model"] == "gemma4:31b"
    assert body["tools"][0]["function"]["name"] == "search_db"
    assert body["tools"][0]["function"]["parameters"]["properties"]["q"]["type"] == "string"


@responses.activate
def test_chat_parses_native_tool_calls():
    responses.post(
        OLLAMA_URL,
        json={
            "message": {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {
                        "function": {
                            "name": "search_db",
                            "arguments": {"q": "frieren"},
                        }
                    }
                ],
            },
            "done": True,
        },
    )

    tool = ToolSchema(name="search_db", description="", parameters={"type": "object"})
    provider = OllamaProvider(url="http://localhost:11434", model="gemma4:31b")
    out = provider.chat([Message(role="user", content="find")], tools=[tool])

    assert len(out.tool_calls) == 1
    assert out.tool_calls[0].name == "search_db"
    assert out.tool_calls[0].arguments == {"q": "frieren"}


@responses.activate
def test_chat_includes_system_prompt():
    responses.post(
        OLLAMA_URL,
        json={"message": {"role": "assistant", "content": "ok"}, "done": True},
    )

    provider = OllamaProvider(url="http://localhost:11434", model="gemma4:31b")
    provider.chat([Message(role="user", content="hi")], system="be terse")

    body = json.loads(responses.calls[0].request.body)
    assert body["messages"][0] == {"role": "system", "content": "be terse"}
    assert body["messages"][1] == {"role": "user", "content": "hi"}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_ollama_provider.py -v`
Expected: `ModuleNotFoundError: utils.ai_providers.ollama_provider`.

- [ ] **Step 3: Create `utils/ai_providers/ollama_provider.py`**

```python
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

    # Fallback path placeholder; real implementation added in Task 5.
    def _prompt_fallback(self, messages, tools, system, max_tokens) -> AIResponse:
        return AIResponse(text="", tool_calls=[])

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
```

- [ ] **Step 4: Un-skip the Ollama factory test**

In `tests/test_ai_provider.py`, remove the `@pytest.mark.skip` above `test_factory_returns_ollama`.

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m pytest tests/test_ollama_provider.py tests/test_ai_provider.py -v`
Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add utils/ai_providers/ollama_provider.py tests/test_ollama_provider.py tests/test_ai_provider.py
git commit -m "Implement OllamaProvider with native tool-calling path"
```

---

## Task 5: OllamaProvider prompt-JSON fallback

**Files:**
- Modify: `utils/ai_providers/ollama_provider.py`
- Modify: `tests/test_ollama_provider.py`

- [ ] **Step 1: Append failing tests to `tests/test_ollama_provider.py`**

```python
# --- Fallback path ---

@responses.activate
def test_fallback_triggers_when_native_returns_no_tool_call():
    # Primary call: native tools requested but model returns nothing usable.
    responses.post(
        OLLAMA_URL,
        json={"message": {"role": "assistant", "content": ""}, "done": True},
    )
    # Secondary call: prompt-JSON path. Model emits a JSON object as text.
    responses.post(
        OLLAMA_URL,
        json={
            "message": {
                "role": "assistant",
                "content": 'I will look it up. {"tool": "search_db", "arguments": {"q": "frieren"}}',
            },
            "done": True,
        },
    )

    tool = ToolSchema(
        name="search_db",
        description="search",
        parameters={"type": "object", "properties": {"q": {"type": "string"}}},
    )
    provider = OllamaProvider(url="http://localhost:11434", model="gemma4:31b")
    out = provider.chat([Message(role="user", content="find")], tools=[tool])

    assert len(out.tool_calls) == 1
    assert out.tool_calls[0].name == "search_db"
    assert out.tool_calls[0].arguments == {"q": "frieren"}


@responses.activate
def test_fallback_returns_plain_text_if_no_json_found():
    # Primary empty.
    responses.post(
        OLLAMA_URL,
        json={"message": {"role": "assistant", "content": ""}, "done": True},
    )
    # Fallback with plain prose answer.
    responses.post(
        OLLAMA_URL,
        json={"message": {"role": "assistant", "content": "i do not need a tool, the answer is 42"}, "done": True},
    )

    tool = ToolSchema(name="search_db", description="x", parameters={"type": "object"})
    provider = OllamaProvider(url="http://localhost:11434", model="gemma4:31b")
    out = provider.chat([Message(role="user", content="?")], tools=[tool])

    assert out.text == "i do not need a tool, the answer is 42"
    assert out.tool_calls == []
```

- [ ] **Step 2: Run to verify failure**

Run: `python -m pytest tests/test_ollama_provider.py::test_fallback_triggers_when_native_returns_no_tool_call tests/test_ollama_provider.py::test_fallback_returns_plain_text_if_no_json_found -v`
Expected: FAIL — fallback currently returns empty `AIResponse`.

- [ ] **Step 3: Replace `_prompt_fallback` and add a JSON extractor**

In `utils/ai_providers/ollama_provider.py`, **replace** the placeholder `_prompt_fallback` with:

```python
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
```

Then at module level (below the class) add:

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_ollama_provider.py -v`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add utils/ai_providers/ollama_provider.py tests/test_ollama_provider.py
git commit -m "Add prompt-JSON tool-use fallback to OllamaProvider"
```

---

## Task 6: Centralized tool definitions

**Files:**
- Create: `utils/ai_tools.py`
- Create: `tests/test_ai_tools.py`

- [ ] **Step 1: Write failing test**

Create `tests/test_ai_tools.py`:

```python
"""Tests for the shared tool registry."""
from utils.ai_provider import ToolSchema
from utils.ai_tools import ALL_TOOLS, TOOL_NAMES


def test_all_tools_are_tool_schema_instances():
    assert len(ALL_TOOLS) >= 5
    for t in ALL_TOOLS:
        assert isinstance(t, ToolSchema)
        assert t.name
        assert t.description
        assert t.parameters.get("type") == "object"


def test_expected_tool_names_present():
    expected = {
        "search_anime_database",
        "get_user_taste_profile",
        "get_user_watchlist",
        "get_anime_details",
        "search_anilist",
    }
    assert expected.issubset(set(TOOL_NAMES))
```

- [ ] **Step 2: Run to verify failure**

Run: `python -m pytest tests/test_ai_tools.py -v`
Expected: `ModuleNotFoundError: utils.ai_tools`.

- [ ] **Step 3: Create `utils/ai_tools.py`**

```python
"""Single source of truth for AI tool definitions, provider-neutral."""
from utils.ai_provider import ToolSchema


SEARCH_ANIME_DATABASE = ToolSchema(
    name="search_anime_database",
    description=(
        "Search the local Bingery database for anime matching a title, genre, "
        "minimum score, or ordering. Use this when recommending anime that the "
        "user may have access to within the app."
    ),
    parameters={
        "type": "object",
        "properties": {
            "title": {"type": "string", "description": "Substring to search for in titles."},
            "genre": {"type": "string", "description": "Official genre name."},
            "min_score": {"type": "number", "description": "Minimum community score (0–10)."},
            "sort": {
                "type": "string",
                "enum": ["score", "year", "popularity"],
                "description": "Sort order.",
            },
            "limit": {"type": "integer", "minimum": 1, "maximum": 20, "default": 5},
        },
    },
)

GET_USER_TASTE_PROFILE = ToolSchema(
    name="get_user_taste_profile",
    description=(
        "Return the logged-in user's top genres, average score, total rated "
        "count, and preferred year range. Use this before making personalized "
        "recommendations."
    ),
    parameters={"type": "object", "properties": {}},
)

GET_USER_WATCHLIST = ToolSchema(
    name="get_user_watchlist",
    description=(
        "Return the list of anime the user has already rated or added to their "
        "watchlist, so you can avoid recommending duplicates."
    ),
    parameters={"type": "object", "properties": {}},
)

GET_ANIME_DETAILS = ToolSchema(
    name="get_anime_details",
    description="Fetch full details on a specific anime by its Bingery database id.",
    parameters={
        "type": "object",
        "properties": {
            "anime_id": {"type": "integer", "description": "Internal database id."},
        },
        "required": ["anime_id"],
    },
)

SEARCH_ANILIST = ToolSchema(
    name="search_anilist",
    description=(
        "Search the live AniList GraphQL API for anime that are not yet in the "
        "local database. Use sparingly; prefer search_anime_database when possible."
    ),
    parameters={
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Free-text search query."},
            "limit": {"type": "integer", "minimum": 1, "maximum": 10, "default": 5},
        },
        "required": ["query"],
    },
)

ALL_TOOLS: list[ToolSchema] = [
    SEARCH_ANIME_DATABASE,
    GET_USER_TASTE_PROFILE,
    GET_USER_WATCHLIST,
    GET_ANIME_DETAILS,
    SEARCH_ANILIST,
]

TOOL_NAMES: list[str] = [t.name for t in ALL_TOOLS]
```

- [ ] **Step 4: Run tests**

Run: `python -m pytest tests/test_ai_tools.py -v`
Expected: pass.

- [ ] **Step 5: Commit**

```bash
git add utils/ai_tools.py tests/test_ai_tools.py
git commit -m "Centralize AI tool definitions"
```

---

## Task 7: Rewire chatbot route to use the provider abstraction

**Files:**
- Modify: `routes/chatbot.py`
- Create: `tests/test_chatbot_integration.py`

- [ ] **Step 1: Write failing integration test**

Create `tests/test_chatbot_integration.py`:

```python
"""Integration tests for /api/chat/message routed through AIProvider."""
from unittest.mock import patch

from utils.ai_provider import AIResponse, ToolCall


@patch("routes.chatbot.get_provider")
def test_chat_message_returns_provider_text(get_provider_mock, client):
    get_provider_mock.return_value.chat.return_value = AIResponse(text="hello from provider")

    resp = client.post("/api/chat/message", json={"message": "hi"})

    assert resp.status_code == 200
    body = resp.get_json()
    assert body["response"] == "hello from provider"


@patch("routes.chatbot.get_provider")
def test_chat_message_executes_tool_then_replies(get_provider_mock, client, app):
    from models import db, Anime
    with app.app_context():
        a = Anime(
            mal_id=1, title_romaji="Frieren", synopsis="x", year=2023,
            episodes=28, studio="Madhouse", cover_image_url="", source="ORIGINAL",
            status="FINISHED", format="TV",
        )
        db.session.add(a)
        db.session.commit()

    provider = get_provider_mock.return_value
    provider.chat.side_effect = [
        AIResponse(
            text="",
            tool_calls=[ToolCall(id="c1", name="search_anime_database", arguments={"title": "Frieren"})],
            stop_reason="tool_use",
        ),
        AIResponse(text="Frieren is wonderful."),
    ]

    resp = client.post("/api/chat/message", json={"message": "tell me about frieren"})

    assert resp.status_code == 200
    assert "Frieren is wonderful" in resp.get_json()["response"]
    assert provider.chat.call_count == 2


def test_chat_message_requires_body(client):
    resp = client.post("/api/chat/message", json={})
    assert resp.status_code == 400
```

- [ ] **Step 2: Run test to see failure (existing chatbot implementation is Anthropic-specific)**

Run: `python -m pytest tests/test_chatbot_integration.py -v`
Expected: FAIL — current route imports `anthropic` directly and does not go through `get_provider`.

- [ ] **Step 3: Rewire `routes/chatbot.py`**

Replace the contents of `routes/chatbot.py` with:

```python
"""Chatbot route — provider-agnostic via utils.ai_provider."""
from __future__ import annotations

import json
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity, verify_jwt_in_request
from flask_jwt_extended.exceptions import NoAuthorizationError

from utils.ai_provider import Message, get_provider
from utils.ai_tools import ALL_TOOLS
from routes.chatbot_tools import execute_tool, BINGERY_SYSTEM


chatbot_bp = Blueprint("chatbot", __name__)

MAX_TOOL_LOOPS = 5


def _optional_user_id() -> int | None:
    """Return the JWT user id if a valid token is present, otherwise None."""
    try:
        verify_jwt_in_request(optional=True)
    except NoAuthorizationError:
        return None
    ident = get_jwt_identity()
    return int(ident) if ident else None


@chatbot_bp.route("/message", methods=["POST"])
def chat_message():
    data = request.get_json(silent=True) or {}
    user_msg = (data.get("message") or "").strip()
    if not user_msg:
        return jsonify({"error": "`message` is required"}), 400

    history = data.get("history") or []
    user_id = _optional_user_id()

    messages: list[Message] = []
    for m in history:
        role = m.get("role", "user")
        content = m.get("content", "")
        if role in ("user", "assistant", "system"):
            messages.append(Message(role=role, content=content))
    messages.append(Message(role="user", content=user_msg))

    system = BINGERY_SYSTEM
    if user_id:
        system += f"\n\n[authenticated user id: {user_id}]"

    provider = get_provider()

    for _ in range(MAX_TOOL_LOOPS):
        resp = provider.chat(messages=messages, tools=ALL_TOOLS, system=system)

        if resp.tool_calls:
            # Append the assistant's tool-use turn.
            messages.append(Message(
                role="assistant",
                content=json.dumps([
                    {"name": c.name, "arguments": c.arguments, "id": c.id}
                    for c in resp.tool_calls
                ]),
            ))
            for call in resp.tool_calls:
                result = execute_tool(call.name, call.arguments, user_id)
                messages.append(Message(
                    role="tool",
                    tool_call_id=call.id,
                    tool_name=call.name,
                    content=json.dumps(result),
                ))
            continue

        return jsonify({
            "response": resp.text,
            "stop_reason": resp.stop_reason,
        })

    return jsonify({
        "response": "I kept reaching for tools but never settled. Try asking a narrower question.",
        "stop_reason": "loop_limit",
    })


@chatbot_bp.route("/quick-recommend", methods=["GET"])
@jwt_required()
def quick_recommend():
    user_id = int(get_jwt_identity())
    provider = get_provider()
    messages = [Message(
        role="user",
        content="Recommend one anime I would probably love based on my taste profile, in 2-3 sentences.",
    )]
    system = BINGERY_SYSTEM + f"\n\n[authenticated user id: {user_id}]"
    resp = provider.chat(messages=messages, tools=ALL_TOOLS, system=system)
    return jsonify({"response": resp.text})
```

- [ ] **Step 4: Extract prompt + `execute_tool` into `routes/chatbot_tools.py`**

Create `routes/chatbot_tools.py`. Copy the `BINGERY_SYSTEM` constant (currently at `routes/chatbot.py:24`) and the `execute_tool` function (currently at `routes/chatbot.py:139`) into this new file verbatim.

Required imports for the new file:

```python
"""System prompt and tool-execution dispatcher for the chatbot."""
from models import db, Anime, User, Rating, FanGenreVote, Genre
from sqlalchemy import func
from utils.anilist import search_anilist as anilist_search
```

Leave the body of `BINGERY_SYSTEM` and `execute_tool` unchanged aside from imports.

- [ ] **Step 5: Run tests**

Run: `python -m pytest tests/test_chatbot_integration.py tests/test_anthropic_provider.py tests/test_ollama_provider.py tests/test_ai_tools.py tests/test_ai_provider.py -v`
Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add routes/chatbot.py routes/chatbot_tools.py tests/test_chatbot_integration.py
git commit -m "Route chatbot through AIProvider abstraction"
```

---

## Task 8: Add Collection and CollectionItem models

**Files:**
- Modify: `models.py`
- Create: `utils/tokens.py`
- Create: `tests/test_collection_models.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_collection_models.py`:

```python
"""Tests for Collection and CollectionItem models."""
import pytest

from models import db, User, Anime, Collection, CollectionItem


def _make_user_and_anime(app):
    with app.app_context():
        user = User(username="u", email="u@e.com", password="pw")
        a1 = Anime(mal_id=1, title_romaji="A", synopsis="", year=2020, episodes=12,
                   studio="S", cover_image_url="", source="ORIGINAL",
                   status="FINISHED", format="TV")
        a2 = Anime(mal_id=2, title_romaji="B", synopsis="", year=2021, episodes=24,
                   studio="S", cover_image_url="", source="ORIGINAL",
                   status="FINISHED", format="TV")
        db.session.add_all([user, a1, a2])
        db.session.commit()
        return user.id, a1.id, a2.id


def test_create_collection_with_items(app):
    uid, aid1, aid2 = _make_user_and_anime(app)
    with app.app_context():
        c = Collection(user_id=uid, name="Cozy Rewatches", color="amber", icon="flame")
        db.session.add(c)
        db.session.commit()

        db.session.add(CollectionItem(collection_id=c.id, anime_id=aid1))
        db.session.add(CollectionItem(collection_id=c.id, anime_id=aid2))
        db.session.commit()

        items = CollectionItem.query.filter_by(collection_id=c.id).all()
        assert len(items) == 2


def test_collection_item_unique_constraint(app):
    uid, aid1, _ = _make_user_and_anime(app)
    with app.app_context():
        c = Collection(user_id=uid, name="x")
        db.session.add(c)
        db.session.commit()
        db.session.add(CollectionItem(collection_id=c.id, anime_id=aid1))
        db.session.commit()

        with pytest.raises(Exception):
            db.session.add(CollectionItem(collection_id=c.id, anime_id=aid1))
            db.session.commit()
        db.session.rollback()


def test_collection_to_dict_includes_items_count(app):
    uid, aid1, _ = _make_user_and_anime(app)
    with app.app_context():
        c = Collection(user_id=uid, name="x", color="violet", icon="star", description="d")
        db.session.add(c)
        db.session.commit()
        db.session.add(CollectionItem(collection_id=c.id, anime_id=aid1))
        db.session.commit()
        d = c.to_dict()
        assert d["name"] == "x"
        assert d["color"] == "violet"
        assert d["icon"] == "star"
        assert d["items_count"] == 1
        assert d["is_public"] is False
        assert d["share_token"] is None
```

- [ ] **Step 2: Run tests to verify failure**

Run: `python -m pytest tests/test_collection_models.py -v`
Expected: `ImportError: cannot import name 'Collection' from 'models'`.

- [ ] **Step 3: Create `utils/tokens.py`**

```python
"""Helpers for generating URL-safe random tokens."""
import secrets


def generate_share_token(length: int = 16) -> str:
    """Return a URL-safe random token of roughly `length` characters."""
    return secrets.token_urlsafe(length)[:length]
```

- [ ] **Step 4: Append models to `models.py`**

Append to the end of `models.py`:

```python
class Collection(db.Model):
    __tablename__ = "collections"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    name = db.Column(db.String(80), nullable=False)
    description = db.Column(db.String(500))
    color = db.Column(db.String(16), default="amber")
    icon = db.Column(db.String(32), default="bookmark")
    is_public = db.Column(db.Boolean, default=False, nullable=False)
    share_token = db.Column(db.String(32), unique=True, nullable=True)
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())
    updated_at = db.Column(
        db.DateTime,
        default=db.func.current_timestamp(),
        onupdate=db.func.current_timestamp(),
    )

    user = db.relationship("User", backref=db.backref("collections", lazy="dynamic"))
    items = db.relationship(
        "CollectionItem",
        backref="collection",
        cascade="all, delete-orphan",
        lazy="dynamic",
    )

    def to_dict(self, include_items: bool = False):
        d = {
            "id": self.id,
            "user_id": self.user_id,
            "name": self.name,
            "description": self.description,
            "color": self.color,
            "icon": self.icon,
            "is_public": self.is_public,
            "share_token": self.share_token,
            "items_count": self.items.count(),
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
        if include_items:
            d["items"] = [i.to_dict() for i in self.items]
        return d


class CollectionItem(db.Model):
    __tablename__ = "collection_items"
    __table_args__ = (
        db.UniqueConstraint("collection_id", "anime_id", name="uq_collection_anime"),
    )

    id = db.Column(db.Integer, primary_key=True)
    collection_id = db.Column(db.Integer, db.ForeignKey("collections.id"), nullable=False)
    anime_id = db.Column(db.Integer, db.ForeignKey("anime.id"), nullable=False)
    note = db.Column(db.String(500))
    added_at = db.Column(db.DateTime, default=db.func.current_timestamp())

    anime = db.relationship("Anime")

    def to_dict(self):
        return {
            "id": self.id,
            "collection_id": self.collection_id,
            "anime_id": self.anime_id,
            "note": self.note,
            "added_at": self.added_at.isoformat() if self.added_at else None,
            "anime": self.anime.to_dict(include_community=False) if self.anime else None,
        }
```

Note: the table name for `Anime` in the existing code is `anime` (lowercase). Verify the `ForeignKey("anime.id")` matches the existing `Anime.__tablename__`. If the existing `Anime` class uses a different tablename, update the foreign key accordingly before continuing.

- [ ] **Step 5: Run tests**

Run: `python -m pytest tests/test_collection_models.py -v`
Expected: pass.

- [ ] **Step 6: Commit**

```bash
git add models.py utils/tokens.py tests/test_collection_models.py
git commit -m "Add Collection and CollectionItem models"
```

---

## Task 9: Collections blueprint — list and create

**Files:**
- Create: `routes/collections.py`
- Create: `tests/test_collections.py`
- Modify: `app.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_collections.py`:

```python
"""Tests for /api/collections endpoints."""


def test_list_collections_empty(client, auth_headers):
    headers, _user = auth_headers
    resp = client.get("/api/collections", headers=headers)
    assert resp.status_code == 200
    assert resp.get_json() == {"collections": []}


def test_list_collections_requires_auth(client):
    resp = client.get("/api/collections")
    assert resp.status_code == 401


def test_create_collection(client, auth_headers):
    headers, _user = auth_headers
    resp = client.post(
        "/api/collections",
        headers=headers,
        json={"name": "Cozy", "color": "amber", "icon": "flame", "description": "warm picks"},
    )
    assert resp.status_code == 201
    body = resp.get_json()
    assert body["collection"]["name"] == "Cozy"
    assert body["collection"]["color"] == "amber"
    assert body["collection"]["icon"] == "flame"
    assert body["collection"]["items_count"] == 0


def test_create_collection_requires_name(client, auth_headers):
    headers, _user = auth_headers
    resp = client.post("/api/collections", headers=headers, json={})
    assert resp.status_code == 400
```

- [ ] **Step 2: Run to verify failure**

Run: `python -m pytest tests/test_collections.py -v`
Expected: 404s — blueprint not registered.

- [ ] **Step 3: Create `routes/collections.py`** (starter with list + create)

```python
"""Collections routes."""
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity

from models import db, Collection


collections_bp = Blueprint("collections", __name__)


@collections_bp.route("", methods=["GET"])
@jwt_required()
def list_collections():
    user_id = int(get_jwt_identity())
    rows = Collection.query.filter_by(user_id=user_id).order_by(Collection.updated_at.desc()).all()
    return jsonify({"collections": [c.to_dict() for c in rows]})


@collections_bp.route("", methods=["POST"])
@jwt_required()
def create_collection():
    user_id = int(get_jwt_identity())
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    if not name:
        return jsonify({"error": "`name` is required"}), 400
    if len(name) > 80:
        return jsonify({"error": "`name` must be 80 characters or fewer"}), 400

    c = Collection(
        user_id=user_id,
        name=name,
        description=(data.get("description") or "")[:500] or None,
        color=(data.get("color") or "amber")[:16],
        icon=(data.get("icon") or "bookmark")[:32],
    )
    db.session.add(c)
    db.session.commit()
    return jsonify({"collection": c.to_dict()}), 201
```

- [ ] **Step 4: Register blueprint in `app.py`**

Open `app.py` and inside `create_app()` where other blueprints are registered (search for `register_blueprint`), add:

```python
    from routes.collections import collections_bp
    app.register_blueprint(collections_bp, url_prefix="/api/collections")
```

- [ ] **Step 5: Run tests**

Run: `python -m pytest tests/test_collections.py -v`
Expected: pass (at least the 4 existing tests).

- [ ] **Step 6: Commit**

```bash
git add routes/collections.py tests/test_collections.py app.py
git commit -m "Add collections list and create endpoints"
```

---

## Task 10: Collections blueprint — detail, update, delete

**Files:**
- Modify: `routes/collections.py`
- Modify: `tests/test_collections.py`

- [ ] **Step 1: Append failing tests to `tests/test_collections.py`**

```python
def _create(client, headers, **kwargs):
    payload = {"name": "Test"}
    payload.update(kwargs)
    r = client.post("/api/collections", headers=headers, json=payload)
    return r.get_json()["collection"]


def test_get_collection_detail(client, auth_headers):
    headers, _ = auth_headers
    c = _create(client, headers, name="Cozy")
    r = client.get(f"/api/collections/{c['id']}", headers=headers)
    assert r.status_code == 200
    body = r.get_json()["collection"]
    assert body["name"] == "Cozy"
    assert body["items"] == []


def test_update_collection(client, auth_headers):
    headers, _ = auth_headers
    c = _create(client, headers, name="Old")
    r = client.patch(
        f"/api/collections/{c['id']}",
        headers=headers,
        json={"name": "New", "color": "violet"},
    )
    assert r.status_code == 200
    body = r.get_json()["collection"]
    assert body["name"] == "New"
    assert body["color"] == "violet"


def test_delete_collection(client, auth_headers):
    headers, _ = auth_headers
    c = _create(client, headers, name="GoAway")
    r = client.delete(f"/api/collections/{c['id']}", headers=headers)
    assert r.status_code == 204
    r2 = client.get(f"/api/collections/{c['id']}", headers=headers)
    assert r2.status_code == 404


def test_cannot_access_other_users_collection(app, client, auth_headers):
    from models import db, User, Collection
    headers, _owner = auth_headers
    with app.app_context():
        other = User(username="other", email="o@e.com", password="pw")
        db.session.add(other)
        db.session.commit()
        c = Collection(user_id=other.id, name="Not Yours")
        db.session.add(c)
        db.session.commit()
        cid = c.id
    r = client.get(f"/api/collections/{cid}", headers=headers)
    assert r.status_code == 404
```

- [ ] **Step 2: Run to verify failure**

Run: `python -m pytest tests/test_collections.py -v`
Expected: new tests 404.

- [ ] **Step 3: Append to `routes/collections.py`**

```python
def _owned_or_404(user_id: int, collection_id: int) -> Collection:
    c = Collection.query.filter_by(id=collection_id, user_id=user_id).first()
    if not c:
        from flask import abort
        abort(404)
    return c


@collections_bp.route("/<int:collection_id>", methods=["GET"])
@jwt_required()
def get_collection(collection_id: int):
    user_id = int(get_jwt_identity())
    c = _owned_or_404(user_id, collection_id)
    return jsonify({"collection": c.to_dict(include_items=True)})


@collections_bp.route("/<int:collection_id>", methods=["PATCH"])
@jwt_required()
def update_collection(collection_id: int):
    user_id = int(get_jwt_identity())
    c = _owned_or_404(user_id, collection_id)
    data = request.get_json(silent=True) or {}

    if "name" in data:
        name = (data["name"] or "").strip()
        if not name or len(name) > 80:
            return jsonify({"error": "invalid `name`"}), 400
        c.name = name
    if "description" in data:
        c.description = (data["description"] or "")[:500] or None
    if "color" in data:
        c.color = (data["color"] or "amber")[:16]
    if "icon" in data:
        c.icon = (data["icon"] or "bookmark")[:32]

    db.session.commit()
    return jsonify({"collection": c.to_dict()})


@collections_bp.route("/<int:collection_id>", methods=["DELETE"])
@jwt_required()
def delete_collection(collection_id: int):
    user_id = int(get_jwt_identity())
    c = _owned_or_404(user_id, collection_id)
    db.session.delete(c)
    db.session.commit()
    return "", 204
```

- [ ] **Step 4: Run tests**

Run: `python -m pytest tests/test_collections.py -v`
Expected: pass.

- [ ] **Step 5: Commit**

```bash
git add routes/collections.py tests/test_collections.py
git commit -m "Add collection detail, update, and delete"
```

---

## Task 11: Collections items — add and remove

**Files:**
- Modify: `routes/collections.py`
- Modify: `tests/test_collections.py`

- [ ] **Step 1: Append failing tests**

Append to `tests/test_collections.py`:

```python
def _make_anime(app, title="Frieren"):
    from models import db, Anime
    with app.app_context():
        a = Anime(
            mal_id=42, title_romaji=title, synopsis="", year=2023, episodes=28,
            studio="Madhouse", cover_image_url="", source="ORIGINAL",
            status="FINISHED", format="TV",
        )
        db.session.add(a)
        db.session.commit()
        return a.id


def test_add_anime_to_collection(client, auth_headers, app):
    headers, _ = auth_headers
    c = _create(client, headers, name="Picks")
    aid = _make_anime(app)

    r = client.post(
        f"/api/collections/{c['id']}/items",
        headers=headers,
        json={"anime_id": aid, "note": "must rewatch"},
    )
    assert r.status_code == 201
    item = r.get_json()["item"]
    assert item["anime_id"] == aid
    assert item["note"] == "must rewatch"


def test_adding_duplicate_anime_is_idempotent(client, auth_headers, app):
    headers, _ = auth_headers
    c = _create(client, headers, name="Picks")
    aid = _make_anime(app)

    r1 = client.post(f"/api/collections/{c['id']}/items", headers=headers, json={"anime_id": aid})
    r2 = client.post(f"/api/collections/{c['id']}/items", headers=headers, json={"anime_id": aid})
    assert r1.status_code == 201
    assert r2.status_code == 200  # already exists


def test_remove_anime_from_collection(client, auth_headers, app):
    headers, _ = auth_headers
    c = _create(client, headers, name="Picks")
    aid = _make_anime(app)
    client.post(f"/api/collections/{c['id']}/items", headers=headers, json={"anime_id": aid})

    r = client.delete(f"/api/collections/{c['id']}/items/{aid}", headers=headers)
    assert r.status_code == 204
```

- [ ] **Step 2: Run to verify failure**

Run: `python -m pytest tests/test_collections.py -v`
Expected: new tests fail with 404.

- [ ] **Step 3: Append to `routes/collections.py`**

```python
from models import Anime, CollectionItem  # extend existing import line instead of adding a new one


@collections_bp.route("/<int:collection_id>/items", methods=["POST"])
@jwt_required()
def add_item(collection_id: int):
    user_id = int(get_jwt_identity())
    c = _owned_or_404(user_id, collection_id)
    data = request.get_json(silent=True) or {}
    anime_id = data.get("anime_id")
    if not isinstance(anime_id, int):
        return jsonify({"error": "`anime_id` must be an integer"}), 400
    if not Anime.query.get(anime_id):
        return jsonify({"error": "anime not found"}), 404

    existing = CollectionItem.query.filter_by(
        collection_id=c.id, anime_id=anime_id
    ).first()
    if existing:
        return jsonify({"item": existing.to_dict()}), 200

    item = CollectionItem(
        collection_id=c.id,
        anime_id=anime_id,
        note=(data.get("note") or "")[:500] or None,
    )
    db.session.add(item)
    db.session.commit()
    return jsonify({"item": item.to_dict()}), 201


@collections_bp.route("/<int:collection_id>/items/<int:anime_id>", methods=["DELETE"])
@jwt_required()
def remove_item(collection_id: int, anime_id: int):
    user_id = int(get_jwt_identity())
    c = _owned_or_404(user_id, collection_id)
    item = CollectionItem.query.filter_by(collection_id=c.id, anime_id=anime_id).first()
    if not item:
        return "", 204
    db.session.delete(item)
    db.session.commit()
    return "", 204
```

- [ ] **Step 4: Run tests**

Run: `python -m pytest tests/test_collections.py -v`
Expected: pass.

- [ ] **Step 5: Commit**

```bash
git add routes/collections.py tests/test_collections.py
git commit -m "Add collection item add and remove"
```

---

## Task 12: Collections public share

**Files:**
- Modify: `routes/collections.py`
- Modify: `tests/test_collections.py`

- [ ] **Step 1: Append failing tests**

```python
def test_toggle_public_generates_share_token(client, auth_headers):
    headers, _ = auth_headers
    c = _create(client, headers, name="Share Me")
    r = client.patch(f"/api/collections/{c['id']}", headers=headers, json={"is_public": True})
    assert r.status_code == 200
    body = r.get_json()["collection"]
    assert body["is_public"] is True
    assert body["share_token"]


def test_public_endpoint_returns_collection_without_auth(client, auth_headers, app):
    headers, _ = auth_headers
    c = _create(client, headers, name="Share Me")
    patched = client.patch(f"/api/collections/{c['id']}", headers=headers, json={"is_public": True})
    token = patched.get_json()["collection"]["share_token"]

    r = client.get(f"/api/collections/public/{token}")
    assert r.status_code == 200
    assert r.get_json()["collection"]["name"] == "Share Me"


def test_public_endpoint_404_when_private(client, auth_headers):
    headers, _ = auth_headers
    c = _create(client, headers, name="Private")
    r = client.get(f"/api/collections/public/never-generated")
    assert r.status_code == 404
```

- [ ] **Step 2: Run to verify failure**

Run: `python -m pytest tests/test_collections.py -v`
Expected: new tests fail.

- [ ] **Step 3: Extend `routes/collections.py` update handler and add public route**

Inside the existing `update_collection` function, **before** `db.session.commit()`, add:

```python
    if "is_public" in data:
        new_public = bool(data["is_public"])
        c.is_public = new_public
        if new_public and not c.share_token:
            from utils.tokens import generate_share_token
            # Ensure uniqueness (collision chance is negligible but cheap to check).
            while True:
                token = generate_share_token()
                if not Collection.query.filter_by(share_token=token).first():
                    c.share_token = token
                    break
        if not new_public:
            c.share_token = None
```

Then append to the file:

```python
@collections_bp.route("/public/<string:token>", methods=["GET"])
def get_public_collection(token: str):
    c = Collection.query.filter_by(share_token=token, is_public=True).first()
    if not c:
        return jsonify({"error": "not found"}), 404
    return jsonify({"collection": c.to_dict(include_items=True)})
```

- [ ] **Step 4: Run tests**

Run: `python -m pytest tests/test_collections.py -v`
Expected: pass.

- [ ] **Step 5: Commit**

```bash
git add routes/collections.py tests/test_collections.py
git commit -m "Add public share for collections"
```

---

## Task 13: Stats blueprint — dashboard aggregate

**Files:**
- Create: `routes/stats.py`
- Create: `tests/test_stats.py`
- Modify: `app.py`

- [ ] **Step 1: Write failing test**

Create `tests/test_stats.py`:

```python
"""Tests for /api/stats endpoints."""


def _seed_ratings(app, user_id):
    from models import db, Anime, Rating, FanGenreVote
    with app.app_context():
        a = Anime(mal_id=1, title_romaji="A", synopsis="", year=2020,
                  episodes=12, studio="Madhouse", cover_image_url="",
                  source="ORIGINAL", status="FINISHED", format="TV")
        b = Anime(mal_id=2, title_romaji="B", synopsis="", year=2023,
                  episodes=24, studio="MAPPA", cover_image_url="",
                  source="MANGA", status="FINISHED", format="TV")
        db.session.add_all([a, b])
        db.session.commit()
        db.session.add_all([
            Rating(user_id=user_id, anime_id=a.id, score=8),
            Rating(user_id=user_id, anime_id=b.id, score=9),
            FanGenreVote(user_id=user_id, anime_id=a.id, genre_name="Fantasy"),
            FanGenreVote(user_id=user_id, anime_id=b.id, genre_name="Fantasy"),
            FanGenreVote(user_id=user_id, anime_id=b.id, genre_name="Drama"),
        ])
        db.session.commit()


def test_stats_returns_aggregate_dashboard(client, auth_headers, app):
    headers, user = auth_headers
    _seed_ratings(app, user.id)

    r = client.get("/api/stats", headers=headers)
    assert r.status_code == 200
    body = r.get_json()

    assert body["totals"]["rated"] == 2
    assert body["totals"]["genre_votes"] == 3
    assert body["totals"]["average_score"] == 8.5

    assert {s["studio"] for s in body["top_studios"]} == {"Madhouse", "MAPPA"}
    assert body["estimated_hours_watched"] > 0

    years = {y["year"]: y["count"] for y in body["year_distribution"]}
    assert years == {2020: 1, 2023: 1}


def test_stats_requires_auth(client):
    r = client.get("/api/stats")
    assert r.status_code == 401
```

- [ ] **Step 2: Run to verify failure**

Run: `python -m pytest tests/test_stats.py -v`
Expected: 404 (blueprint not registered).

- [ ] **Step 3: Create `routes/stats.py`**

```python
"""Stats dashboard routes."""
from collections import Counter

from flask import Blueprint, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from sqlalchemy import func

from models import db, Anime, Rating, FanGenreVote, WatchlistEntry


stats_bp = Blueprint("stats", __name__)


DEFAULT_EPISODE_MINUTES = 24
COMPLETION_WEIGHTS = {
    "completed": 1.0,
    "watching": 0.5,
    "on_hold": 0.5,
    "dropped": 0.25,
    "plan_to_watch": 0.0,
}


@stats_bp.route("", methods=["GET"])
@jwt_required()
def dashboard():
    user_id = int(get_jwt_identity())

    ratings = (
        db.session.query(Rating, Anime)
        .join(Anime, Anime.id == Rating.anime_id)
        .filter(Rating.user_id == user_id)
        .all()
    )
    total_rated = len(ratings)
    avg_score = (
        round(sum(r.score for r, _ in ratings) / total_rated, 2)
        if total_rated else 0.0
    )

    total_genre_votes = FanGenreVote.query.filter_by(user_id=user_id).count()

    # Year distribution
    year_counter: Counter[int] = Counter()
    for _, anime in ratings:
        if anime.year:
            year_counter[int(anime.year)] += 1
    year_distribution = [
        {"year": y, "count": c} for y, c in sorted(year_counter.items())
    ]

    # Score distribution
    score_counter: Counter[int] = Counter(r.score for r, _ in ratings)
    score_distribution = [
        {"score": s, "count": score_counter.get(s, 0)} for s in range(1, 11)
    ]

    # Top studios
    studio_counter: Counter[str] = Counter()
    for _, anime in ratings:
        if anime.studio:
            studio_counter[anime.studio] += 1
    top_studios = [
        {"studio": name, "count": c}
        for name, c in studio_counter.most_common(10)
    ]

    # Top fan genres
    fan_rows = (
        db.session.query(FanGenreVote.genre_name, func.count(FanGenreVote.id))
        .filter(FanGenreVote.user_id == user_id)
        .group_by(FanGenreVote.genre_name)
        .order_by(func.count(FanGenreVote.id).desc())
        .limit(15)
        .all()
    )
    top_fan_tags = [{"name": n, "count": c} for n, c in fan_rows]

    # Hours watched estimate
    watchlist = {
        w.anime_id: w.status for w in
        WatchlistEntry.query.filter_by(user_id=user_id).all()
    }
    total_minutes = 0.0
    for _, anime in ratings:
        status = watchlist.get(anime.id, "completed")
        weight = COMPLETION_WEIGHTS.get(status, 1.0)
        eps = anime.episodes or 0
        total_minutes += eps * DEFAULT_EPISODE_MINUTES * weight
    hours = round(total_minutes / 60.0, 1)

    return jsonify({
        "totals": {
            "rated": total_rated,
            "genre_votes": total_genre_votes,
            "average_score": avg_score,
        },
        "year_distribution": year_distribution,
        "score_distribution": score_distribution,
        "top_studios": top_studios,
        "top_fan_tags": top_fan_tags,
        "estimated_hours_watched": hours,
    })
```

- [ ] **Step 4: Register blueprint in `app.py`**

```python
    from routes.stats import stats_bp
    app.register_blueprint(stats_bp, url_prefix="/api/stats")
```

- [ ] **Step 5: Run tests**

Run: `python -m pytest tests/test_stats.py -v`
Expected: pass.

- [ ] **Step 6: Commit**

```bash
git add routes/stats.py tests/test_stats.py app.py
git commit -m "Add stats dashboard endpoint"
```

---

## Task 14: Stats — genres and timeline

**Files:**
- Modify: `routes/stats.py`
- Modify: `tests/test_stats.py`

- [ ] **Step 1: Append failing tests**

Append to `tests/test_stats.py`:

```python
def test_stats_genres_breakdown(client, auth_headers, app):
    headers, user = auth_headers
    _seed_ratings(app, user.id)
    r = client.get("/api/stats/genres", headers=headers)
    assert r.status_code == 200
    body = r.get_json()
    fantasy = next(g for g in body["genres"] if g["name"] == "Fantasy")
    assert fantasy["count"] == 2
    assert fantasy["weighted_score"] > 0


def test_stats_timeline(client, auth_headers, app):
    headers, user = auth_headers
    _seed_ratings(app, user.id)
    r = client.get("/api/stats/timeline", headers=headers)
    assert r.status_code == 200
    body = r.get_json()
    assert {row["year"] for row in body["timeline"]} == {2020, 2023}
    for row in body["timeline"]:
        assert "count" in row
        assert "average_score" in row
```

- [ ] **Step 2: Run to verify failure**

Run: `python -m pytest tests/test_stats.py -v`
Expected: 404 on new endpoints.

- [ ] **Step 3: Append to `routes/stats.py`**

```python
@stats_bp.route("/genres", methods=["GET"])
@jwt_required()
def genres_breakdown():
    user_id = int(get_jwt_identity())
    rows = (
        db.session.query(
            FanGenreVote.genre_name,
            func.count(FanGenreVote.id),
            func.coalesce(func.avg(Rating.score), 0),
        )
        .outerjoin(
            Rating,
            (Rating.user_id == FanGenreVote.user_id)
            & (Rating.anime_id == FanGenreVote.anime_id),
        )
        .filter(FanGenreVote.user_id == user_id)
        .group_by(FanGenreVote.genre_name)
        .all()
    )
    genres = [
        {
            "name": name,
            "count": int(count),
            "weighted_score": round(float(avg) * int(count), 2),
            "avg_score": round(float(avg), 2),
        }
        for name, count, avg in rows
    ]
    genres.sort(key=lambda g: g["weighted_score"], reverse=True)
    return jsonify({"genres": genres})


@stats_bp.route("/timeline", methods=["GET"])
@jwt_required()
def timeline():
    user_id = int(get_jwt_identity())
    rows = (
        db.session.query(Anime.year, func.count(Rating.id), func.avg(Rating.score))
        .join(Rating, Rating.anime_id == Anime.id)
        .filter(Rating.user_id == user_id, Anime.year.isnot(None))
        .group_by(Anime.year)
        .order_by(Anime.year)
        .all()
    )
    out = [
        {"year": int(year), "count": int(count), "average_score": round(float(avg), 2)}
        for year, count, avg in rows
    ]
    return jsonify({"timeline": out})
```

- [ ] **Step 4: Run tests**

Run: `python -m pytest tests/test_stats.py -v`
Expected: pass.

- [ ] **Step 5: Commit**

```bash
git add routes/stats.py tests/test_stats.py
git commit -m "Add stats genres and timeline endpoints"
```

---

## Task 15: Activity blueprint

**Files:**
- Create: `routes/activity.py`
- Create: `tests/test_activity.py`
- Modify: `app.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_activity.py`:

```python
"""Tests for /api/activity endpoints."""
from datetime import datetime, timedelta


def _seed_activity(app, user_id):
    from models import db, Anime, Rating, FanGenreVote, WatchlistEntry
    with app.app_context():
        a = Anime(mal_id=1, title_romaji="Frieren", synopsis="", year=2023,
                  episodes=28, studio="Madhouse", cover_image_url="",
                  source="MANGA", status="FINISHED", format="TV")
        db.session.add(a)
        db.session.commit()
        r = Rating(user_id=user_id, anime_id=a.id, score=9, review_text="lovely")
        v = FanGenreVote(user_id=user_id, anime_id=a.id, genre_name="Tearjerker")
        w = WatchlistEntry(user_id=user_id, anime_id=a.id, status="completed")
        db.session.add_all([r, v, w])
        db.session.commit()


def test_activity_feed_returns_recent_actions(client, auth_headers, app):
    headers, user = auth_headers
    _seed_activity(app, user.id)

    r = client.get("/api/activity?limit=10", headers=headers)
    assert r.status_code == 200
    body = r.get_json()
    kinds = {item["type"] for item in body["items"]}
    assert {"rating", "genre_vote", "status"}.issubset(kinds)

    for item in body["items"]:
        assert "anime_id" in item
        assert "anime_title" in item
        assert "timestamp" in item


def test_activity_feed_respects_limit(client, auth_headers, app):
    headers, user = auth_headers
    _seed_activity(app, user.id)
    r = client.get("/api/activity?limit=1", headers=headers)
    assert r.status_code == 200
    assert len(r.get_json()["items"]) == 1


def test_activity_requires_auth(client):
    r = client.get("/api/activity")
    assert r.status_code == 401
```

- [ ] **Step 2: Run to verify failure**

Run: `python -m pytest tests/test_activity.py -v`
Expected: 404.

- [ ] **Step 3: Create `routes/activity.py`**

```python
"""Activity feed routes."""
from datetime import datetime
from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity

from models import db, Anime, Rating, FanGenreVote, WatchlistEntry


activity_bp = Blueprint("activity", __name__)


def _rating_event(r: Rating, anime: Anime):
    return {
        "type": "rating",
        "anime_id": anime.id,
        "anime_title": anime.title_english or anime.title_romaji,
        "cover": anime.cover_image_url,
        "timestamp": (r.updated_at or r.created_at).isoformat(),
        "meta": {"score": r.score, "has_review": bool(r.review_text)},
    }


def _genre_event(v: FanGenreVote, anime: Anime):
    return {
        "type": "genre_vote",
        "anime_id": anime.id,
        "anime_title": anime.title_english or anime.title_romaji,
        "cover": anime.cover_image_url,
        "timestamp": v.created_at.isoformat() if v.created_at else None,
        "meta": {"genre": v.genre_name},
    }


def _status_event(w: WatchlistEntry, anime: Anime):
    return {
        "type": "status",
        "anime_id": anime.id,
        "anime_title": anime.title_english or anime.title_romaji,
        "cover": anime.cover_image_url,
        "timestamp": (w.updated_at or w.created_at).isoformat() if (w.updated_at or w.created_at) else None,
        "meta": {"status": w.status, "episodes_watched": w.episodes_watched},
    }


def _fetch_events(user_id: int, before: datetime | None):
    out: list[dict] = []

    ratings = (
        db.session.query(Rating, Anime).join(Anime, Anime.id == Rating.anime_id)
        .filter(Rating.user_id == user_id).all()
    )
    out.extend(_rating_event(r, a) for r, a in ratings)

    votes = (
        db.session.query(FanGenreVote, Anime).join(Anime, Anime.id == FanGenreVote.anime_id)
        .filter(FanGenreVote.user_id == user_id).all()
    )
    out.extend(_genre_event(v, a) for v, a in votes)

    statuses = (
        db.session.query(WatchlistEntry, Anime).join(Anime, Anime.id == WatchlistEntry.anime_id)
        .filter(WatchlistEntry.user_id == user_id).all()
    )
    out.extend(_status_event(w, a) for w, a in statuses)

    out = [e for e in out if e["timestamp"]]
    out.sort(key=lambda e: e["timestamp"], reverse=True)
    if before:
        out = [e for e in out if e["timestamp"] < before.isoformat()]
    return out


@activity_bp.route("", methods=["GET"])
@jwt_required()
def feed():
    user_id = int(get_jwt_identity())
    try:
        limit = max(1, min(int(request.args.get("limit", 50)), 200))
    except ValueError:
        limit = 50
    before_raw = request.args.get("before")
    before = None
    if before_raw:
        try:
            before = datetime.fromisoformat(before_raw.replace("Z", "+00:00"))
        except ValueError:
            return jsonify({"error": "invalid `before` timestamp"}), 400

    events = _fetch_events(user_id, before)[:limit]
    return jsonify({"items": events})


@activity_bp.route("/on-this-day", methods=["GET"])
@jwt_required()
def on_this_day():
    user_id = int(get_jwt_identity())
    today = datetime.utcnow()
    events = _fetch_events(user_id, None)
    matches = []
    for e in events:
        try:
            ts = datetime.fromisoformat(e["timestamp"].replace("Z", "+00:00"))
        except ValueError:
            continue
        if ts.month == today.month and ts.day == today.day and ts.year < today.year:
            matches.append(e)
    return jsonify({"items": matches})
```

- [ ] **Step 4: Register blueprint in `app.py`**

```python
    from routes.activity import activity_bp
    app.register_blueprint(activity_bp, url_prefix="/api/activity")
```

- [ ] **Step 5: Run tests**

Run: `python -m pytest tests/test_activity.py -v`
Expected: pass.

- [ ] **Step 6: Commit**

```bash
git add routes/activity.py tests/test_activity.py app.py
git commit -m "Add activity feed and on-this-day endpoints"
```

---

## Task 16: Seasonal blueprint

**Files:**
- Create: `routes/seasonal.py`
- Create: `tests/test_seasonal.py`
- Modify: `app.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_seasonal.py`:

```python
"""Tests for /api/seasonal endpoints."""


def _seed_seasonal(app):
    from models import db, Anime
    with app.app_context():
        a = Anime(mal_id=101, title_romaji="Winter 2026 A", synopsis="", year=2026,
                  season="WINTER", episodes=12, studio="Studio", cover_image_url="",
                  source="ORIGINAL", status="RELEASING", format="TV")
        b = Anime(mal_id=102, title_romaji="Spring 2026 B", synopsis="", year=2026,
                  season="SPRING", episodes=12, studio="Studio", cover_image_url="",
                  source="ORIGINAL", status="NOT_YET_RELEASED", format="TV")
        db.session.add_all([a, b])
        db.session.commit()


def test_seasonal_returns_filtered_by_season_year(client, auth_headers, app):
    headers, _ = auth_headers
    _seed_seasonal(app)
    r = client.get("/api/seasonal?season=WINTER&year=2026", headers=headers)
    assert r.status_code == 200
    titles = {a["title_romaji"] for a in r.get_json()["anime"]}
    assert titles == {"Winter 2026 A"}


def test_seasonal_airing_now(client, auth_headers, app):
    headers, _ = auth_headers
    _seed_seasonal(app)
    r = client.get("/api/seasonal/airing-now", headers=headers)
    assert r.status_code == 200
    titles = {a["title_romaji"] for a in r.get_json()["anime"]}
    assert titles == {"Winter 2026 A"}


def test_seasonal_rejects_bad_season(client, auth_headers):
    headers, _ = auth_headers
    r = client.get("/api/seasonal?season=SUMMERTIME&year=2026", headers=headers)
    assert r.status_code == 400
```

Before running, confirm the `Anime` model has `season` and `status` columns. If `season` is missing, add it to `Anime` in `models.py` as `season = db.Column(db.String(16))` (nullable). This is a safe additive change.

- [ ] **Step 2: Run to verify failure**

Run: `python -m pytest tests/test_seasonal.py -v`
Expected: 404 (blueprint not registered) — plus a model error if `season` column was missing.

- [ ] **Step 3: Create `routes/seasonal.py`**

```python
"""Seasonal calendar routes."""
from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity

from models import Anime, WatchlistEntry


seasonal_bp = Blueprint("seasonal", __name__)

VALID_SEASONS = {"WINTER", "SPRING", "SUMMER", "FALL"}
AIRING_STATUSES = {"RELEASING", "CURRENTLY_AIRING"}


def _with_status_overlay(user_id: int, anime_list):
    owned = {
        w.anime_id: w for w in
        WatchlistEntry.query.filter(
            WatchlistEntry.user_id == user_id,
            WatchlistEntry.anime_id.in_([a.id for a in anime_list]),
        ).all()
    }
    out = []
    for a in anime_list:
        d = a.to_dict(include_community=False)
        w = owned.get(a.id)
        d["user_status"] = w.status if w else None
        d["is_favorite"] = bool(w and w.is_favorite)
        out.append(d)
    return out


@seasonal_bp.route("", methods=["GET"])
@jwt_required()
def seasonal():
    user_id = int(get_jwt_identity())
    season = (request.args.get("season") or "").upper()
    year_raw = request.args.get("year")
    if season not in VALID_SEASONS:
        return jsonify({"error": f"season must be one of {sorted(VALID_SEASONS)}"}), 400
    try:
        year = int(year_raw) if year_raw else None
    except ValueError:
        return jsonify({"error": "year must be an integer"}), 400
    if year is None:
        return jsonify({"error": "year is required"}), 400

    rows = Anime.query.filter_by(season=season, year=year).order_by(Anime.title_romaji).all()
    return jsonify({"anime": _with_status_overlay(user_id, rows)})


@seasonal_bp.route("/airing-now", methods=["GET"])
@jwt_required()
def airing_now():
    user_id = int(get_jwt_identity())
    rows = Anime.query.filter(Anime.status.in_(AIRING_STATUSES)).order_by(Anime.title_romaji).all()
    return jsonify({"anime": _with_status_overlay(user_id, rows)})
```

- [ ] **Step 4: Register blueprint in `app.py`**

```python
    from routes.seasonal import seasonal_bp
    app.register_blueprint(seasonal_bp, url_prefix="/api/seasonal")
```

- [ ] **Step 5: Run tests**

Run: `python -m pytest tests/test_seasonal.py -v`
Expected: pass.

- [ ] **Step 6: Commit**

```bash
git add routes/seasonal.py tests/test_seasonal.py app.py models.py
git commit -m "Add seasonal calendar endpoints"
```

---

## Task 17: Compare blueprint

**Files:**
- Create: `routes/compare.py`
- Create: `tests/test_compare.py`
- Modify: `app.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_compare.py`:

```python
"""Tests for /api/compare."""


def _seed_compare(app, user_id):
    from models import db, Anime, Rating, FanGenreVote
    with app.app_context():
        a = Anime(mal_id=1, title_romaji="A", synopsis="", year=2020,
                  episodes=12, studio="Madhouse", cover_image_url="",
                  source="MANGA", status="FINISHED", format="TV")
        b = Anime(mal_id=2, title_romaji="B", synopsis="", year=2023,
                  episodes=24, studio="MAPPA", cover_image_url="",
                  source="ORIGINAL", status="FINISHED", format="TV")
        db.session.add_all([a, b])
        db.session.commit()
        db.session.add_all([
            Rating(user_id=user_id, anime_id=a.id, score=8, review_text="solid"),
            Rating(user_id=user_id, anime_id=b.id, score=9, review_text="great"),
            FanGenreVote(user_id=user_id, anime_id=a.id, genre_name="Fantasy"),
            FanGenreVote(user_id=user_id, anime_id=b.id, genre_name="Fantasy"),
            FanGenreVote(user_id=user_id, anime_id=b.id, genre_name="Drama"),
        ])
        db.session.commit()
        return a.id, b.id


def test_compare_two_anime(client, auth_headers, app):
    headers, user = auth_headers
    aid, bid = _seed_compare(app, user.id)

    r = client.get(f"/api/compare?a={aid}&b={bid}", headers=headers)
    assert r.status_code == 200
    body = r.get_json()
    assert body["a"]["anime"]["id"] == aid
    assert body["b"]["anime"]["id"] == bid
    assert body["a"]["user"]["score"] == 8
    assert body["b"]["user"]["score"] == 9
    assert "Fantasy" in body["shared"]["fan_genres"]
    assert body["a"]["user"]["review_text"] == "solid"


def test_compare_requires_two_ids(client, auth_headers):
    headers, _ = auth_headers
    r = client.get("/api/compare?a=1", headers=headers)
    assert r.status_code == 400


def test_compare_404_when_anime_missing(client, auth_headers):
    headers, _ = auth_headers
    r = client.get("/api/compare?a=9999&b=10000", headers=headers)
    assert r.status_code == 404
```

- [ ] **Step 2: Run to verify failure**

Run: `python -m pytest tests/test_compare.py -v`
Expected: 404.

- [ ] **Step 3: Create `routes/compare.py`**

```python
"""Compare two anime side-by-side."""
from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity

from models import Anime, Rating, FanGenreVote


compare_bp = Blueprint("compare", __name__)


def _side_payload(user_id: int, anime: Anime):
    rating = Rating.query.filter_by(user_id=user_id, anime_id=anime.id).first()
    fan_votes = [v.genre_name for v in FanGenreVote.query.filter_by(user_id=user_id, anime_id=anime.id).all()]
    return {
        "anime": anime.to_dict(include_community=True),
        "user": {
            "score": rating.score if rating else None,
            "review_text": rating.review_text if rating else None,
            "fan_genres": fan_votes,
        },
    }


@compare_bp.route("", methods=["GET"])
@jwt_required()
def compare():
    user_id = int(get_jwt_identity())
    try:
        a_id = int(request.args.get("a", ""))
        b_id = int(request.args.get("b", ""))
    except ValueError:
        return jsonify({"error": "`a` and `b` must be integers"}), 400

    a = Anime.query.get(a_id)
    b = Anime.query.get(b_id)
    if not a or not b:
        return jsonify({"error": "anime not found"}), 404

    left = _side_payload(user_id, a)
    right = _side_payload(user_id, b)

    official_a = {g["name"] for g in left["anime"]["official_genres"]}
    official_b = {g["name"] for g in right["anime"]["official_genres"]}

    shared = {
        "official_genres": sorted(official_a & official_b),
        "fan_genres": sorted(set(left["user"]["fan_genres"]) & set(right["user"]["fan_genres"])),
        "studios": sorted({a.studio, b.studio} - {None})
                   if a.studio == b.studio and a.studio is not None else [],
    }
    unique = {
        "a_only_official_genres": sorted(official_a - official_b),
        "b_only_official_genres": sorted(official_b - official_a),
    }

    return jsonify({"a": left, "b": right, "shared": shared, "unique": unique})
```

- [ ] **Step 4: Register blueprint in `app.py`**

```python
    from routes.compare import compare_bp
    app.register_blueprint(compare_bp, url_prefix="/api/compare")
```

- [ ] **Step 5: Run tests**

Run: `python -m pytest tests/test_compare.py -v`
Expected: pass.

- [ ] **Step 6: Commit**

```bash
git add routes/compare.py tests/test_compare.py app.py
git commit -m "Add compare endpoint"
```

---

## Task 18: `.env.example` and full smoke

**Files:**
- Create: `.env.example`
- Run full test suite
- Manual smoke

- [ ] **Step 1: Create `.env.example`**

```
# =====================================================
# Bingery — environment template
# Copy to .env and fill in the values for your setup.
# =====================================================

# --- App ---
JWT_SECRET_KEY=change-me
DATABASE_URL=sqlite:///bingery.db    # in prod Render sets this to a Postgres URL

# --- AI provider switch (ollama | anthropic) ---
AI_PROVIDER=ollama

# --- Ollama (used when AI_PROVIDER=ollama) ---
OLLAMA_URL=http://localhost:11434
OLLAMA_MODEL=gemma4:31b

# --- Anthropic (used when AI_PROVIDER=anthropic) ---
ANTHROPIC_API_KEY=
ANTHROPIC_MODEL=claude-sonnet-4-6
```

- [ ] **Step 2: Run full test suite**

Run: `python -m pytest -v`
Expected: all tests pass.

- [ ] **Step 3: Manual smoke**

With `AI_PROVIDER=anthropic` and a valid API key, start the app and confirm:

```bash
python app.py
```

Then in another terminal:

```bash
curl -s http://localhost:5000/api/health
curl -s -X POST http://localhost:5000/api/chat/message -H "Content-Type: application/json" -d '{"message":"hi"}'
```

Expected: health returns OK; chat returns a text response.

Then repeat with `AI_PROVIDER=ollama` (Ollama daemon running with `gemma4:31b` pulled).

- [ ] **Step 4: Commit**

```bash
git add .env.example
git commit -m "Document environment variables for both AI providers"
```

---

## Self-Review Checklist

**Spec coverage:** Every spec §4 (AI provider) item is covered by Tasks 2–7. Every spec §5 (data model) item is covered by Task 8. Every spec §6 (API surface) new endpoint is covered by Tasks 9–17. `.env.example` (spec §3.3) covered by Task 18. Existing endpoints untouched (verified because no tasks modify their files).

**Type consistency:** `AIProvider.chat` signature is used identically in every call site (tasks 3, 4, 7). `ToolSchema`, `Message`, `AIResponse`, `ToolCall` names match across every task. `Collection.to_dict(include_items=False)` shape is consistent between tasks 8, 9, 10, 12.

**No placeholders:** Every code block is runnable. No "TBD", no "similar to earlier," no descriptions-without-code.

**Out of scope for this plan (captured in Plan 2 / 3):**
- Frontend work.
- `build.sh` / `render.yaml` updates (done in Plan 3 since it couples with frontend).
- New endpoint UIs.

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-04-17-plan-1-backend-foundation.md`.

**Two execution options:**

**1. Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, review between tasks, fast iteration.

**2. Inline Execution** — Execute tasks in this session using executing-plans, batch execution with checkpoints.

Which approach do you prefer, and should I proceed with Plan 2 (frontend) before starting execution or after Plan 1 ships?
