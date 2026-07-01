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


def _ctx_user(n):
    from models import db, User

    u = User(email=f"{n}@x.com", username=n, password_hash="x")
    db.session.add(u)
    db.session.commit()
    return u


def test_context_includes_watchlist_groups_and_favorites(app):
    from models import db, Anime, WatchlistEntry
    from routes.chat_context import build_llm_context

    with app.app_context():
        u = _ctx_user("ctx5")
        a1, a2, a3 = Anime(title="Watching One"), Anime(title="Dropped One"), Anime(title="Fav One")
        db.session.add_all([a1, a2, a3])
        db.session.flush()
        db.session.add_all([
            WatchlistEntry(user_id=u.id, anime_id=a1.id, status="watching"),
            WatchlistEntry(user_id=u.id, anime_id=a2.id, status="dropped"),
            WatchlistEntry(user_id=u.id, anime_id=a3.id, status="completed", is_favorite=True),
        ])
        db.session.commit()
        out = build_llm_context(u.id, "hi", "recommend")
        assert "Watching One" in out["user"]["watchlist"]["watching"]
        assert "Dropped One" in out["user"]["watchlist"]["dropped"]
        assert "Fav One" in out["user"]["favorites"]


def test_context_includes_review_snippets_ordered_by_signal(app):
    from models import db, Anime, Rating
    from routes.chat_context import build_llm_context

    with app.app_context():
        u = _ctx_user("ctx6")
        titles = {}
        for name, score, review in [
            ("Loved Show", 10, "Peak fiction. " * 40),  # 560 chars, must truncate
            ("Meh Show", 6, "It was fine."),
            ("Hated Show", 1, "Dropped it hard."),
        ]:
            a = Anime(title=name)
            db.session.add(a)
            db.session.flush()
            db.session.add(Rating(user_id=u.id, anime_id=a.id, score=score, review=review))
            titles[name] = a.id
        db.session.commit()
        out = build_llm_context(u.id, "hi", "recommend")
        reviews = out["user"]["reviews"]
        # strongest signals (|score-5.5|) come first: 10 and 1 before 6
        assert {reviews[0]["title"], reviews[1]["title"]} == {"Loved Show", "Hated Show"}
        assert reviews[2]["title"] == "Meh Show"
        assert all(len(r["snippet"]) <= 280 for r in reviews)


def test_rate_mode_carries_full_signals_but_no_candidates(app):
    from models import db, Anime, WatchlistEntry
    from routes.chat_context import build_llm_context

    with app.app_context():
        u = _ctx_user("ctx7")
        a = Anime(title="Rated Context Show")
        db.session.add(a)
        db.session.flush()
        db.session.add(WatchlistEntry(user_id=u.id, anime_id=a.id, status="watching"))
        db.session.commit()
        out = build_llm_context(u.id, "how should I rate this", "rate")
        assert "candidates" not in out
        assert "Rated Context Show" in out["user"]["watchlist"]["watching"]
        assert "reviews" in out["user"]


def test_shrink_user_block_trims_watchlist_before_reviews():
    import json

    from routes.chat_context import _shrink_user_block

    block = {
        "watchlist": {"completed": [f"Bulk Show {i}" for i in range(200)]},
        "favorites": ["Fav Show"],
        "reviews": [{"title": "A", "score": 10, "snippet": "x" * 280}],
    }
    out = _shrink_user_block(block, budget=1200)
    assert len(json.dumps(out)) <= 1200
    assert out["reviews"], "reviews must be the last thing sacrificed"
    assert len(out["watchlist"]["completed"]) < 200
