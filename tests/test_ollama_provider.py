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
