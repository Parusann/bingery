"""Tests for AnthropicProvider."""
from unittest.mock import MagicMock, patch
import pytest

from utils.ai_provider import Message, ProviderUnavailableError, ToolCall, ToolSchema
from utils.ai_providers.anthropic_provider import AnthropicProvider


def test_assistant_tool_turn_becomes_tool_use_blocks():
    """The Anthropic API rejects a tool_result whose tool_use_id has no
    matching tool_use block in the preceding assistant turn, so the
    assistant turn must round-trip its tool calls as structured blocks."""
    msgs = [
        Message(role="user", content="hi"),
        Message(
            role="assistant",
            content="",
            tool_calls=[ToolCall(id="t1", name="search_db", arguments={"q": "x"})],
        ),
        Message(role="tool", tool_call_id="t1", tool_name="search_db", content="[]"),
    ]

    out = AnthropicProvider._to_anthropic_messages(msgs)

    assistant_blocks = out[1]["content"]
    assert {"type": "tool_use", "id": "t1", "name": "search_db", "input": {"q": "x"}} in assistant_blocks
    assert out[2]["role"] == "user"
    assert out[2]["content"][0]["type"] == "tool_result"
    assert out[2]["content"][0]["tool_use_id"] == "t1"


@patch("utils.ai_providers.anthropic_provider.anthropic.Anthropic")
def test_connection_error_maps_to_provider_unavailable(anthropic_cls):
    """Transient API failures must surface as ProviderUnavailableError so
    the chat route returns its friendly 503 instead of a 500."""
    import anthropic as anthropic_sdk
    import httpx

    client = anthropic_cls.return_value
    client.messages.create.side_effect = anthropic_sdk.APIConnectionError(
        request=httpx.Request("POST", "https://api.anthropic.com/v1/messages"),
    )

    provider = AnthropicProvider(api_key="k")
    with pytest.raises(ProviderUnavailableError):
        provider.chat([Message(role="user", content="hi")])


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
