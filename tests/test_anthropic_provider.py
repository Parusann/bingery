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
