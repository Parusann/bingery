"""Tests for routes.chat_context.build_llm_context."""


def test_recommend_mode_includes_candidates(app):
    from models import db, User, Anime
    from routes.chat_context import build_llm_context
    u = User(email="ctx@x.com", username="ctx", password_hash="x")
    db.session.add(u); db.session.commit()
    db.session.add(Anime(title="Pickable", anilist_id=1000, api_score=8.5))
    db.session.commit()
    ctx = build_llm_context(u.id, "something melancholy", "recommend", include_nsfw=False)
    assert ctx["mode"] == "recommend"
    assert ctx["user_message"] == "something melancholy"
    assert "user" in ctx and "top_studios" in ctx["user"]
    assert "candidates" in ctx
    assert isinstance(ctx["candidates"], list)


def test_rate_mode_omits_candidates(app):
    from models import db, User
    from routes.chat_context import build_llm_context
    u = User(email="ctx2@x.com", username="ctx2", password_hash="x")
    db.session.add(u); db.session.commit()
    ctx = build_llm_context(u.id, "I just finished Frieren", "rate", include_nsfw=False)
    assert ctx["mode"] == "rate"
    assert "candidates" not in ctx


def test_onboard_mode_omits_candidates(app):
    from models import db, User
    from routes.chat_context import build_llm_context
    u = User(email="ctx3@x.com", username="ctx3", password_hash="x")
    db.session.add(u); db.session.commit()
    ctx = build_llm_context(u.id, "help me start", "onboard", include_nsfw=False)
    assert ctx["mode"] == "onboard"
    assert "candidates" not in ctx


def test_user_block_omits_cache_only_fields(app):
    from models import db, User
    from routes.chat_context import build_llm_context
    u = User(email="ctx4@x.com", username="ctx4", password_hash="x")
    db.session.add(u); db.session.commit()
    ctx = build_llm_context(u.id, "anything", "recommend", include_nsfw=False)
    # cache-only fields should be stripped before going to the LLM
    assert "schema_version" not in ctx["user"]
    assert "computed_at" not in ctx["user"]
    assert "rating_count_at_compute" not in ctx["user"]
