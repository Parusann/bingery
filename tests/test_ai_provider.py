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


@pytest.mark.skip(reason="provider class added in later task")
def test_factory_returns_anthropic_by_default(monkeypatch):
    monkeypatch.setenv("AI_PROVIDER", "anthropic")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "k")
    provider = get_provider()
    assert provider.__class__.__name__ == "AnthropicProvider"


@pytest.mark.skip(reason="provider class added in later task")
def test_factory_returns_ollama(monkeypatch):
    monkeypatch.setenv("AI_PROVIDER", "ollama")
    monkeypatch.setenv("OLLAMA_MODEL", "gemma4:31b")
    provider = get_provider()
    assert provider.__class__.__name__ == "OllamaProvider"


def test_factory_rejects_unknown_provider(monkeypatch):
    monkeypatch.setenv("AI_PROVIDER", "nonsense")
    with pytest.raises(ValueError, match="Unknown AI_PROVIDER"):
        get_provider()
