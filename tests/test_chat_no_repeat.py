"""No-repeat memory + rate-mode context injection for /api/chat/message."""
from unittest.mock import patch

from utils.ai_provider import AIResponse, ToolCall


@patch("routes.chatbot.get_provider")
def test_no_repeat_drops_already_suggested_cards(get_provider_mock, client, app):
    from models import db, Anime

    with app.app_context():
        db.session.add(Anime(title="Repeat Show", api_score=8.0))
        db.session.commit()
    get_provider_mock.return_value.chat.return_value = AIResponse(
        text="Try **Repeat Show** again!"
    )
    r = client.post(
        "/api/chat/message",
        json={
            "message": "something else please",
            "conversation": [
                {"role": "user", "content": "recommend me something"},
                {"role": "assistant", "content": "You should watch **Repeat Show**."},
            ],
        },
    )
    assert r.status_code == 200
    body = r.get_json()
    assert all(c["title"] != "Repeat Show" for c in body["suggested_anime"])


@patch("routes.chatbot.get_provider")
def test_repeat_allowed_when_user_asks_by_name(get_provider_mock, client, app):
    from models import db, Anime

    with app.app_context():
        db.session.add(Anime(title="Named Show", api_score=8.0))
        db.session.commit()
    get_provider_mock.return_value.chat.return_value = AIResponse(
        text="**Named Show** is a great pick."
    )
    r = client.post(
        "/api/chat/message",
        json={
            "message": "tell me more about Named Show",
            "conversation": [
                {"role": "assistant", "content": "Watch **Named Show**."},
            ],
        },
    )
    titles = [c["title"] for c in r.get_json()["suggested_anime"]]
    assert "Named Show" in titles


@patch("routes.chatbot.execute_tool")
@patch("routes.chatbot.get_provider")
def test_no_repeat_feeds_exclude_ids_to_find_similar(
    get_provider_mock, execute_tool_mock, client, app
):
    from models import db, Anime

    with app.app_context():
        a = Anime(title="Repeat Show Two", api_score=8.0)
        db.session.add(a)
        db.session.commit()
        repeat_id = a.id

    execute_tool_mock.return_value = "{}"
    get_provider_mock.return_value.chat.side_effect = [
        AIResponse(
            tool_calls=[
                ToolCall(id="t1", name="find_similar_anime", arguments={"title": "X"})
            ]
        ),
        AIResponse(text="Here you go."),
    ]
    r = client.post(
        "/api/chat/message",
        json={
            "message": "more like X",
            "conversation": [
                {"role": "assistant", "content": "Watch **Repeat Show Two**."},
            ],
        },
    )
    assert r.status_code == 200
    call = execute_tool_mock.call_args
    passed_input = call.args[1] if len(call.args) > 1 else call.kwargs["tool_input"]
    assert repeat_id in passed_input.get("exclude_ids", [])


@patch("routes.chatbot.execute_tool")
@patch("routes.chatbot.get_provider")
def test_find_similar_results_pass_grounding_validation(
    get_provider_mock, execute_tool_mock, client, app, auth_headers
):
    """In grounded recommend mode, titles surfaced by find_similar_anime
    must survive the candidate validation pass — they are engine-grounded
    even when outside the static candidates list."""
    import json as _json

    from models import db, Anime, Rating

    headers, user = auth_headers
    with app.app_context():
        # One rating => warm profile (limit 40); flood the candidate list
        # so Tool Pick can't make the static top-40.
        rated = Anime(title="Warmup Show", api_score=8.0)
        db.session.add(rated)
        db.session.flush()
        db.session.add(Rating(user_id=user.id, anime_id=rated.id, score=8))
        for i in range(44):
            db.session.add(Anime(title=f"Filler {i}", api_score=9.0))
        tool_pick = Anime(title="Tool Pick", api_score=None)
        db.session.add(tool_pick)
        db.session.commit()
        tool_pick_id = tool_pick.id

    execute_tool_mock.return_value = _json.dumps(
        {"seed": {"id": 1, "title": "X"}, "results": [{"id": tool_pick_id, "title": "Tool Pick"}]}
    )
    get_provider_mock.return_value.chat.side_effect = [
        AIResponse(
            tool_calls=[
                ToolCall(id="t1", name="find_similar_anime", arguments={"title": "X"})
            ]
        ),
        AIResponse(text="Try **Tool Pick**!"),
    ]
    r = client.post(
        "/api/chat/message",
        json={"message": "something like X", "conversation": [], "mode": "recommend"},
        headers=headers,
    )
    assert r.status_code == 200
    titles = [c["title"] for c in r.get_json()["suggested_anime"]]
    assert "Tool Pick" in titles


@patch("routes.chatbot.execute_tool")
@patch("routes.chatbot.get_provider")
def test_similar_seed_surfaces_as_seed_anime_card(
    get_provider_mock, execute_tool_mock, client, app
):
    """'Something like Charlotte' must return the seed's own card in a
    dedicated seed_anime field — and never duplicate it into the
    suggestion cards even if the LLM bolds it."""
    import json as _json

    from models import db, Anime

    with app.app_context():
        seed = Anime(title="Charlotte", year=2015, image_url="http://img/x.jpg",
                     api_score=7.8)
        pick = Anime(title="Plastic Memories", year=2015, api_score=7.9)
        db.session.add_all([seed, pick])
        db.session.commit()
        seed_id, pick_id = seed.id, pick.id

    execute_tool_mock.return_value = _json.dumps({
        "seed": {"id": seed_id, "title": "Charlotte"},
        "results": [{"id": pick_id, "title": "Plastic Memories"}],
    })
    get_provider_mock.return_value.chat.side_effect = [
        AIResponse(tool_calls=[
            ToolCall(id="t1", name="find_similar_anime",
                     arguments={"title": "Charlotte"})
        ]),
        AIResponse(text="**Charlotte** fans should try **Plastic Memories**."),
    ]
    r = client.post(
        "/api/chat/message",
        json={"message": "recommend me something like Charlotte",
              "conversation": []},
    )
    assert r.status_code == 200
    body = r.get_json()
    assert body["seed_anime"]["id"] == seed_id
    assert body["seed_anime"]["title"] == "Charlotte"
    assert body["seed_anime"]["image_url"] == "http://img/x.jpg"
    titles = [c["title"] for c in body["suggested_anime"]]
    assert "Plastic Memories" in titles
    assert "Charlotte" not in titles  # seed never doubles as a suggestion


@patch("routes.chatbot.get_provider")
def test_no_seed_anime_without_similarity_lookup(get_provider_mock, client):
    get_provider_mock.return_value.chat.return_value = AIResponse(
        text="Tell me more about what you like!"
    )
    r = client.post(
        "/api/chat/message",
        json={"message": "hi", "conversation": []},
    )
    assert r.status_code == 200
    assert r.get_json()["seed_anime"] is None


@patch("routes.chatbot.get_provider")
def test_legacy_modes_normalized_to_recommend(
    get_provider_mock, client, auth_headers
):
    """rate/onboard modes were removed; a legacy client sending them gets
    the full grounded recommend experience (context + candidates)."""
    headers, _user = auth_headers
    get_provider_mock.return_value.chat.return_value = AIResponse(
        text="Here's a pick."
    )
    r = client.post(
        "/api/chat/message",
        json={"message": "help me pick something", "mode": "rate"},
        headers=headers,
    )
    assert r.status_code == 200
    system_arg = get_provider_mock.return_value.chat.call_args.kwargs.get("system") or ""
    assert "CONTEXT JSON" in system_arg
    assert '"candidates"' in system_arg  # everything is recommend now
