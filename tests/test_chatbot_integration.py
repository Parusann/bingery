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
            mal_id=1, title="Frieren", synopsis="x", year=2023,
            episodes=28, studio="Madhouse", image_url="", source="ORIGINAL",
            status="FINISHED",
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
