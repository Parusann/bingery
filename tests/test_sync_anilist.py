"""Tests for sync_anilist.py — driven by a mocked AniListClient."""
from datetime import datetime, timezone

import pytest

from models import db, Anime, Episode, AniListSyncState, get_or_create_sync_state
from sync_anilist import run_sync, process_media_entry, main


# ─── Fixture helpers ─────────────────────────────────────────────────────────


def _airing_at(year, month, day, hour=14, minute=30):
    """Build an AniList-style epoch-seconds timestamp."""
    return int(
        datetime(year, month, day, hour, minute, tzinfo=timezone.utc).timestamp()
    )


def _media(anilist_id, title, episodes_schedule=None, next_airing=None):
    """Build a normalized media dict in the shape `fetch_catalog_page` returns."""
    return {
        "anilist_id": anilist_id,
        "mal_id": None,
        "title": title,
        "title_english": None,
        "title_japanese": None,
        "synopsis": f"Synopsis for {title}",
        "api_score": 7.5,
        "year": 2024,
        "season": "spring",
        "episodes": 12,
        "studio": "Studio S",
        "image_url": f"https://example.com/{anilist_id}.jpg",
        "banner_url": None,
        "status": "Currently Airing",
        "source": "Manga",
        "genres": ["Action"],
        "tags": [],
        "popularity": 100,
        "favourites": 50,
        "next_airing_episode": next_airing,
        "airing_schedule": episodes_schedule or [],
    }


class FakeClient:
    """A drop-in stand-in for AniListClient.fetch_catalog_page."""

    def __init__(self, pages):
        # pages: list of {"media": [...], "page_info": {...}} dicts
        self.pages = pages
        self.calls = []

    def fetch_catalog_page(self, page, per_page=50):
        self.calls.append({"page": page, "per_page": per_page})
        # 1-indexed pages: page=1 -> self.pages[0]
        if page < 1 or page > len(self.pages):
            return {
                "media": [],
                "page_info": {
                    "currentPage": page,
                    "lastPage": len(self.pages),
                    "hasNextPage": False,
                    "total": 0,
                    "perPage": per_page,
                },
            }
        return self.pages[page - 1]


class ExplodingClient:
    """A client that raises on fetch — simulates 502 / network error."""

    def __init__(self, message="502 Bad Gateway"):
        self.message = message

    def fetch_catalog_page(self, page, per_page=50):
        raise RuntimeError(self.message)


def _build_one_page(media_list, has_next=False, current=1, last=1):
    return {
        "media": media_list,
        "page_info": {
            "currentPage": current,
            "lastPage": last,
            "hasNextPage": has_next,
            "total": len(media_list),
            "perPage": 50,
        },
    }


# ─── Fresh sync ──────────────────────────────────────────────────────────────


def test_fresh_sync_persists_anime_and_episodes(app):
    with app.app_context():
        media = [
            _media(
                anilist_id=100 + i,
                title=f"Anime {i}",
                episodes_schedule=[
                    {"episode": 1, "airingAt": _airing_at(2024, 4, 5)},
                    {"episode": 2, "airingAt": _airing_at(2024, 4, 12)},
                ],
                next_airing={"episode": 3, "airingAt": _airing_at(2024, 4, 19)},
            )
            for i in range(5)
        ]
        client = FakeClient([_build_one_page(media, has_next=False)])

        summary = run_sync(client, start_page=1, sleep_seconds=0, log=lambda *_: None)

        assert summary["ok"] is True
        assert summary["pages_processed"] == 1
        assert summary["media_processed"] == 5

        anime_rows = Anime.query.order_by(Anime.anilist_id).all()
        assert len(anime_rows) == 5
        # Each anime should have 3 episodes (sched 1, 2 + next 3 — dedup'd by unique constraint)
        ep_count = Episode.query.count()
        assert ep_count == 5 * 3

        state = get_or_create_sync_state()
        assert state.last_page == 1
        assert state.status == "idle"


# ─── Resume ──────────────────────────────────────────────────────────────────


def test_resume_starts_at_last_page_plus_one(app):
    with app.app_context():
        state = get_or_create_sync_state()
        state.last_page = 2
        db.session.commit()

        # Build pages 3 + 4. The client only stores 2 entries, but the loop
        # starts at page 3, so the FakeClient is asked for pages 3 then 4.
        page3 = _build_one_page(
            [_media(300, "P3 A")], has_next=True, current=3, last=4
        )
        page4 = _build_one_page(
            [_media(400, "P4 A")], has_next=False, current=4, last=4
        )

        # FakeClient is 1-indexed against its array — pad with empty slots
        # for pages 1 + 2 so page 3 -> self.pages[2] and page 4 -> self.pages[3]
        client = FakeClient([
            _build_one_page([], has_next=True, current=1, last=4),
            _build_one_page([], has_next=True, current=2, last=4),
            page3,
            page4,
        ])

        start_page = state.last_page + 1
        summary = run_sync(
            client, start_page=start_page, sleep_seconds=0, log=lambda *_: None
        )

        assert summary["pages_processed"] == 2
        assert summary["media_processed"] == 2
        # The first call should be page 3, not page 1.
        assert client.calls[0]["page"] == 3
        assert client.calls[1]["page"] == 4


# ─── Idempotency ─────────────────────────────────────────────────────────────


def test_idempotent_double_run_produces_no_duplicates(app):
    with app.app_context():
        media = [
            _media(
                anilist_id=42,
                title="Same Anime",
                episodes_schedule=[
                    {"episode": 1, "airingAt": _airing_at(2024, 4, 5)},
                    {"episode": 2, "airingAt": _airing_at(2024, 4, 12)},
                ],
            )
        ]

        # First run.
        client1 = FakeClient([_build_one_page(media)])
        run_sync(client1, start_page=1, sleep_seconds=0, log=lambda *_: None)

        assert Anime.query.count() == 1
        assert Episode.query.count() == 2

        # Second run — last_page is now 1, so a --full restart would be page 1 again.
        client2 = FakeClient([_build_one_page(media)])
        run_sync(client2, start_page=1, sleep_seconds=0, log=lambda *_: None)

        assert Anime.query.count() == 1
        assert Episode.query.count() == 2


# ─── Upsert updates existing fields ─────────────────────────────────────────


def test_upsert_updates_anime_synopsis_on_rerun(app):
    with app.app_context():
        original = _media(anilist_id=7, title="Anime 7")
        client1 = FakeClient([_build_one_page([original])])
        run_sync(client1, start_page=1, sleep_seconds=0, log=lambda *_: None)

        a = Anime.query.filter_by(anilist_id=7).first()
        assert a is not None
        assert a.synopsis == "Synopsis for Anime 7"

        updated = _media(anilist_id=7, title="Anime 7 (updated)")
        updated["synopsis"] = "Brand new synopsis."
        client2 = FakeClient([_build_one_page([updated])])
        run_sync(client2, start_page=1, sleep_seconds=0, log=lambda *_: None)

        a2 = Anime.query.filter_by(anilist_id=7).first()
        assert a2.id == a.id  # same row
        assert a2.synopsis == "Brand new synopsis."
        assert a2.title == "Anime 7 (updated)"


# ─── Episode unique constraint ──────────────────────────────────────────────


def test_episode_unique_constraint_prevents_duplicates(app):
    with app.app_context():
        media = _media(
            anilist_id=99,
            title="Dup Test",
            episodes_schedule=[
                {"episode": 1, "airingAt": _airing_at(2024, 4, 5)},
            ],
            # nextAiringEpisode for the SAME episode 1 — should dedup.
            next_airing={"episode": 1, "airingAt": _airing_at(2024, 4, 5)},
        )
        client = FakeClient([_build_one_page([media])])
        run_sync(client, start_page=1, sleep_seconds=0, log=lambda *_: None)

        a = Anime.query.filter_by(anilist_id=99).first()
        eps = Episode.query.filter_by(anime_id=a.id).all()
        assert len(eps) == 1
        assert eps[0].episode_number == 1


# ─── Dry run ─────────────────────────────────────────────────────────────────


def test_dry_run_writes_nothing(app):
    with app.app_context():
        media = [
            _media(
                anilist_id=200,
                title="Dry Anime",
                episodes_schedule=[
                    {"episode": 1, "airingAt": _airing_at(2024, 4, 5)},
                ],
            )
        ]
        client = FakeClient([_build_one_page(media)])

        summary = run_sync(
            client,
            start_page=1,
            dry_run=True,
            sleep_seconds=0,
            log=lambda *_: None,
        )

        assert summary["ok"] is True
        assert summary["dry_run"] is True
        assert Anime.query.count() == 0
        assert Episode.query.count() == 0
        # last_page should not have advanced.
        state = get_or_create_sync_state()
        assert state.last_page == 0


# ─── Error path ──────────────────────────────────────────────────────────────


def test_error_path_records_status_and_message(app):
    with app.app_context():
        client = ExplodingClient("502 Bad Gateway")
        with pytest.raises(RuntimeError):
            run_sync(client, start_page=1, sleep_seconds=0, log=lambda *_: None)

        state = AniListSyncState.query.first()
        assert state is not None
        assert state.status == "error"
        assert state.error_message is not None
        assert "502" in state.error_message


# ─── CLI parses cleanly ──────────────────────────────────────────────────────


def test_cli_main_with_max_pages_zero_exits_cleanly(monkeypatch):
    # --max-pages=0 should short-circuit before touching the network or DB.
    rc = main(["--max-pages", "0"])
    assert rc == 0


def test_cli_main_invalid_since_returns_error_code():
    rc = main(["--since", "not-a-date"])
    assert rc == 2


# ─── process_media_entry directly ────────────────────────────────────────────


def test_process_media_entry_dry_run_returns_episode_count(app):
    with app.app_context():
        m = _media(
            anilist_id=1,
            title="X",
            episodes_schedule=[
                {"episode": 1, "airingAt": _airing_at(2024, 4, 5)},
                {"episode": 2, "airingAt": _airing_at(2024, 4, 12)},
            ],
            next_airing={"episode": 3, "airingAt": _airing_at(2024, 4, 19)},
        )
        summary = process_media_entry(m, dry_run=True)
        assert summary["dry_run"] is True
        assert summary["episodes_upserted"] == 3
        assert Anime.query.count() == 0
        assert Episode.query.count() == 0
