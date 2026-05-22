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


def test_system_prompt_includes_grounding_rules():
    from routes.chatbot_tools import BINGERY_SYSTEM
    assert "GROUNDING RULES" in BINGERY_SYSTEM
    assert "PICK ONLY from the candidates" in BINGERY_SYSTEM or "PICK ONLY from `candidates`" in BINGERY_SYSTEM
    assert "single highest-value signal" in BINGERY_SYSTEM.lower() or "single strongest signal" in BINGERY_SYSTEM.lower()


@patch("routes.chatbot.get_provider")
def test_recommend_mode_filters_non_candidates(get_provider_mock, client, app, auth_headers):
    """In recommend mode, suggested_anime is restricted to the candidate set:
    titles the LLM bold-mentions that aren't in `candidates` get dropped silently.
    """
    from models import db, Anime, Rating
    headers, user = auth_headers
    with app.app_context():
        # Two anime: one already rated (excluded from candidates), one fresh
        rated = Anime(title="Already Rated", anilist_id=3001, api_score=8.0)
        candidate = Anime(title="Real Pick", anilist_id=3002, api_score=8.5)
        db.session.add_all([rated, candidate])
        db.session.commit()
        db.session.add(Rating(user_id=user.id, anime_id=rated.id, score=9))
        db.session.commit()
        rated_id = rated.id
        candidate_id = candidate.id

    get_provider_mock.return_value.chat.return_value = AIResponse(
        text="**Already Rated** — but you've seen this. **Real Pick** — fresh vibes."
    )

    resp = client.post(
        "/api/chat/message",
        json={"message": "recommend me something", "mode": "recommend"},
        headers=headers,
    )

    assert resp.status_code == 200
    body = resp.get_json()
    suggested_ids = {s["id"] for s in body["suggested_anime"]}
    # Already-rated anime is excluded from candidates by score_candidates,
    # so even though _resolve_title found it, the validation pass drops it.
    assert rated_id not in suggested_ids
    assert candidate_id in suggested_ids
