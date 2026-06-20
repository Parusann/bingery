"""Tests for sync_anilist.py — driven by a mocked AniListClient.

The real sync chunks by `seasonYear` to sidestep AniList's deep-page-offset
cap at 5000 (and the absence of `id_greater` on Media). The mock simulates
that API: each call gets `(season_year, page)` and returns a slice of media
with hasNextPage flag.
"""
from datetime import datetime, timezone

import pytest

from models import db, Anime, Episode, AniListSyncState, get_or_create_sync_state
from sync_anilist import run_sync, process_media_entry, main


# ─── Fixture helpers ─────────────────────────────────────────────────────────


def _airing_at(year, month, day, hour=14, minute=30):
    return int(
        datetime(year, month, day, hour, minute, tzinfo=timezone.utc).timestamp()
    )


def _media(anilist_id, title, year=2024, episodes_schedule=None, next_airing=None):
    return {
        "anilist_id": anilist_id,
        "mal_id": None,
        "title": title,
        "title_english": None,
        "title_japanese": None,
        "synopsis": f"Synopsis for {title}",
        "api_score": 7.5,
        "year": year,
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
    """Year-chunked stand-in for AniListClient.fetch_catalog_page.

    Holds media grouped by year. Returns up to `per_page` items per call,
    paginated within the requested year.
    """

    def __init__(self, media_by_year, per_page_default=50):
        # media_by_year: dict[int, list[media]]
        self.media_by_year = {y: list(items) for y, items in media_by_year.items()}
        self.calls = []

    def fetch_catalog_page(self, season_year, page=1, per_page=50):
        self.calls.append(
            {"season_year": season_year, "page": page, "per_page": per_page}
        )
        year_media = self.media_by_year.get(season_year, [])
        start = (page - 1) * per_page
        end = start + per_page
        batch = year_media[start:end]
        has_next = end < len(year_media)
        return {
            "media": batch,
            "page_info": {
                "currentPage": page,
                "lastPage": max(1, -(-len(year_media) // per_page)),
                "hasNextPage": has_next,
                "perPage": per_page,
            },
        }


class ExplodingClient:
    def __init__(self, message="502 Bad Gateway"):
        self.message = message

    def fetch_catalog_page(self, season_year, page=1, per_page=50):
        raise RuntimeError(self.message)


# ─── Fresh sync ──────────────────────────────────────────────────────────────


def test_fresh_sync_persists_anime_and_episodes(app):
    with app.app_context():
        media = [
            _media(
                anilist_id=100 + i,
                title=f"Anime {i}",
                year=2024,
                episodes_schedule=[
                    {"episode": 1, "airingAt": _airing_at(2024, 4, 5)},
                    {"episode": 2, "airingAt": _airing_at(2024, 4, 12)},
                ],
                next_airing={"episode": 3, "airingAt": _airing_at(2024, 4, 19)},
            )
            for i in range(5)
        ]
        client = FakeClient({2024: media})

        summary = run_sync(
            client,
            start_year=2024,
            end_year=2024,
            sleep_seconds=0,
            log=lambda *_: None,
        )

        assert summary["ok"] is True
        assert summary["pages_processed"] == 1
        assert summary["media_processed"] == 5

        anime_rows = Anime.query.order_by(Anime.anilist_id).all()
        assert len(anime_rows) == 5
        assert Episode.query.count() == 5 * 3

        state = get_or_create_sync_state()
        assert state.last_page == 2024  # last completed year
        assert state.status == "idle"


# ─── Pagination within a single year ─────────────────────────────────────────


def test_year_with_multiple_pages_paginates_correctly(app):
    """120 anime in one year → 3 pages at per_page=50."""
    with app.app_context():
        media = [
            _media(anilist_id=1000 + i, title=f"A{i}", year=2023)
            for i in range(120)
        ]
        client = FakeClient({2023: media})

        summary = run_sync(
            client,
            start_year=2023,
            end_year=2023,
            sleep_seconds=0,
            log=lambda *_: None,
        )

        assert summary["media_processed"] == 120
        assert summary["pages_processed"] == 3  # 50 + 50 + 20
        # Pages requested are 1, 2, 3 of seasonYear=2023.
        assert [c["page"] for c in client.calls] == [1, 2, 3]
        assert all(c["season_year"] == 2023 for c in client.calls)


# ─── Iterating across multiple years ─────────────────────────────────────────


def test_iterates_across_years(app):
    with app.app_context():
        client = FakeClient(
            {
                2022: [_media(anilist_id=2200, title="22A", year=2022)],
                2023: [_media(anilist_id=2300, title="23A", year=2023)],
                2024: [_media(anilist_id=2400, title="24A", year=2024)],
            }
        )

        summary = run_sync(
            client,
            start_year=2022,
            end_year=2024,
            sleep_seconds=0,
            log=lambda *_: None,
        )

        assert summary["media_processed"] == 3
        assert summary["pages_processed"] == 3  # one page per year
        years_called = [c["season_year"] for c in client.calls]
        assert years_called == [2022, 2023, 2024]
        state = get_or_create_sync_state()
        assert state.last_page == 2024


# ─── Resume from last_year + 1 ───────────────────────────────────────────────


def test_resume_starts_at_year_after_last_completed(app):
    """If state.last_page=2022 (last completed year), resume starts at 2023."""
    with app.app_context():
        # Caller computes start_year = state.last_page + 1 in main(); here we
        # exercise run_sync directly with the resolved year.
        client = FakeClient(
            {
                2023: [_media(anilist_id=2300, title="23A", year=2023)],
                2024: [_media(anilist_id=2400, title="24A", year=2024)],
            }
        )

        summary = run_sync(
            client,
            start_year=2023,
            end_year=2024,
            sleep_seconds=0,
            log=lambda *_: None,
        )

        assert summary["media_processed"] == 2
        years_called = [c["season_year"] for c in client.calls]
        # First call should be 2023, not 2022.
        assert 2022 not in years_called
        assert years_called == [2023, 2024]


# ─── Idempotency ─────────────────────────────────────────────────────────────


def test_idempotent_double_run_produces_no_duplicates(app):
    with app.app_context():
        media = [
            _media(
                anilist_id=42,
                title="Same Anime",
                year=2024,
                episodes_schedule=[
                    {"episode": 1, "airingAt": _airing_at(2024, 4, 5)},
                    {"episode": 2, "airingAt": _airing_at(2024, 4, 12)},
                ],
            )
        ]

        client1 = FakeClient({2024: media})
        run_sync(
            client1, start_year=2024, end_year=2024,
            sleep_seconds=0, log=lambda *_: None,
        )
        assert Anime.query.count() == 1
        assert Episode.query.count() == 2

        client2 = FakeClient({2024: media})
        run_sync(
            client2, start_year=2024, end_year=2024,
            sleep_seconds=0, log=lambda *_: None,
        )
        assert Anime.query.count() == 1
        assert Episode.query.count() == 2


# ─── Upsert updates existing fields ─────────────────────────────────────────


def test_upsert_updates_anime_synopsis_on_rerun(app):
    with app.app_context():
        original = _media(anilist_id=7, title="Anime 7", year=2024)
        client1 = FakeClient({2024: [original]})
        run_sync(
            client1, start_year=2024, end_year=2024,
            sleep_seconds=0, log=lambda *_: None,
        )

        a = Anime.query.filter_by(anilist_id=7).first()
        assert a is not None
        assert a.synopsis == "Synopsis for Anime 7"

        updated = _media(anilist_id=7, title="Anime 7 (updated)", year=2024)
        updated["synopsis"] = "Brand new synopsis."
        client2 = FakeClient({2024: [updated]})
        run_sync(
            client2, start_year=2024, end_year=2024,
            sleep_seconds=0, log=lambda *_: None,
        )

        a2 = Anime.query.filter_by(anilist_id=7).first()
        assert a2.id == a.id
        assert a2.synopsis == "Brand new synopsis."
        assert a2.title == "Anime 7 (updated)"


# ─── Episode unique constraint ──────────────────────────────────────────────


def test_episode_unique_constraint_prevents_duplicates(app):
    with app.app_context():
        media = _media(
            anilist_id=99,
            title="Dup Test",
            year=2024,
            episodes_schedule=[{"episode": 1, "airingAt": _airing_at(2024, 4, 5)}],
            next_airing={"episode": 1, "airingAt": _airing_at(2024, 4, 5)},
        )
        client = FakeClient({2024: [media]})
        run_sync(
            client, start_year=2024, end_year=2024,
            sleep_seconds=0, log=lambda *_: None,
        )

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
                year=2024,
                episodes_schedule=[{"episode": 1, "airingAt": _airing_at(2024, 4, 5)}],
            )
        ]
        client = FakeClient({2024: media})

        summary = run_sync(
            client,
            start_year=2024,
            end_year=2024,
            dry_run=True,
            sleep_seconds=0,
            log=lambda *_: None,
        )

        assert summary["ok"] is True
        assert summary["dry_run"] is True
        assert Anime.query.count() == 0
        assert Episode.query.count() == 0
        state = get_or_create_sync_state()
        assert state.last_page == 0


# ─── Error path ──────────────────────────────────────────────────────────────


def test_error_path_records_status_and_message(app):
    with app.app_context():
        client = ExplodingClient("502 Bad Gateway")
        with pytest.raises(RuntimeError):
            run_sync(
                client, start_year=2024, end_year=2024,
                sleep_seconds=0, log=lambda *_: None,
            )

        state = AniListSyncState.query.first()
        assert state is not None
        assert state.status == "error"
        assert state.error_message is not None
        assert "502" in state.error_message


# ─── CLI parses cleanly ──────────────────────────────────────────────────────


def test_cli_main_with_max_pages_zero_exits_cleanly(monkeypatch):
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
            year=2024,
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


# ─── Orphan-catcher (format-based pagination) ────────────────────────────────


class FakeFormatClient:
    """Stand-in for AniListClient.fetch_catalog_page_by_format."""

    def __init__(self, media_by_format, per_page_default=50):
        self.media_by_format = {
            f: list(items) for f, items in media_by_format.items()
        }
        self.calls = []

    def fetch_catalog_page_by_format(self, media_format, page=1, per_page=50):
        self.calls.append(
            {"format": media_format, "page": page, "per_page": per_page}
        )
        items = self.media_by_format.get(media_format, [])
        start = (page - 1) * per_page
        end = start + per_page
        batch = items[start:end]
        has_next = end < len(items)
        return {
            "media": batch,
            "page_info": {
                "currentPage": page,
                "lastPage": max(1, -(-len(items) // per_page)),
                "hasNextPage": has_next,
                "perPage": per_page,
            },
        }


def test_run_format_sync_upserts_media(app):
    from sync_anilist import run_format_sync

    with app.app_context():
        media = [
            _media(anilist_id=9000 + i, title=f"Special {i}", year=2010)
            for i in range(3)
        ]
        client = FakeFormatClient({"SPECIAL": media})
        summary = run_format_sync(
            client, media_format="SPECIAL", sleep_seconds=0
        )
        assert summary["ok"] is True
        assert summary["format"] == "SPECIAL"
        assert summary["pages_processed"] == 1
        assert summary["media_processed"] == 3
        assert Anime.query.count() == 3
        # FakeFormatClient was called exactly once because hasNextPage=False.
        assert len(client.calls) == 1
        assert client.calls[0]["format"] == "SPECIAL"


def test_run_format_sync_paginates_multiple_pages(app):
    from sync_anilist import run_format_sync

    with app.app_context():
        # 60 entries → 2 pages at perPage=50.
        media = [
            _media(anilist_id=9100 + i, title=f"OVA {i}", year=2010)
            for i in range(60)
        ]
        client = FakeFormatClient({"OVA": media})
        summary = run_format_sync(client, media_format="OVA", sleep_seconds=0)
        assert summary["pages_processed"] == 2
        assert summary["media_processed"] == 60
        assert Anime.query.count() == 60
        assert [c["page"] for c in client.calls] == [1, 2]


def test_run_format_sync_max_pages_cap(app):
    from sync_anilist import run_format_sync

    with app.app_context():
        media = [
            _media(anilist_id=9200 + i, title=f"ONA {i}", year=2010)
            for i in range(200)
        ]
        client = FakeFormatClient({"ONA": media})
        summary = run_format_sync(
            client, media_format="ONA", max_pages=2, sleep_seconds=0
        )
        assert summary["pages_processed"] == 2
        # Only 100 of 200 written.
        assert Anime.query.count() == 100


def test_run_format_sync_dry_run_does_not_write(app):
    from sync_anilist import run_format_sync

    with app.app_context():
        media = [
            _media(anilist_id=9300 + i, title=f"Music {i}", year=2010)
            for i in range(5)
        ]
        client = FakeFormatClient({"MUSIC": media})
        summary = run_format_sync(
            client, media_format="MUSIC", dry_run=True, sleep_seconds=0
        )
        assert summary["dry_run"] is True
        assert summary["media_processed"] == 5
        assert Anime.query.count() == 0


def test_run_format_sync_idempotent_on_rerun(app):
    from sync_anilist import run_format_sync

    with app.app_context():
        media = [
            _media(anilist_id=9400 + i, title=f"TVShort {i}", year=2010)
            for i in range(4)
        ]
        client = FakeFormatClient({"TV_SHORT": media})

        first = run_format_sync(
            client, media_format="TV_SHORT", sleep_seconds=0
        )
        count_after_first = Anime.query.count()
        # Reset the call log and re-run; idempotent upserts should not
        # produce duplicate rows.
        client.calls.clear()
        second = run_format_sync(
            client, media_format="TV_SHORT", sleep_seconds=0
        )
        assert first["media_processed"] == second["media_processed"]
        assert Anime.query.count() == count_after_first


def test_upsert_persists_popularity(app):
    """Verify that popularity from AniList payload is persisted to Anime.popularity.

    Tests both create and update branches:
    - CREATE: First call with popularity=42000 creates new Anime record.
    - UPDATE: Second call with same anilist_id but popularity=99999 updates existing record.
    """
    from utils.anilist import sync_anime_to_db
    from models import Anime

    with app.app_context():
        payload = {
            "anilist_id": 555555,
            "mal_id": None,
            "title": "Test Show",
            "title_english": None,
            "title_japanese": None,
            "synopsis": "Test synopsis",
            "popularity": 42000,
            "api_score": 80,
            "year": 2024,
            "season": "winter",
            "episodes": 12,
            "studio": "Studio T",
            "image_url": "https://example.com/image.jpg",
            "banner_url": None,
            "status": "FINISHED",
            "source": "Original",
            "genres": ["Drama"],
        }
        # CREATE BRANCH: First call inserts new record.
        anime = sync_anime_to_db(payload)
        db.session.flush()

        # Refetch to ensure it was persisted
        fetched = Anime.query.filter_by(anilist_id=555555).first()
        assert fetched is not None
        assert fetched.popularity == 42000

        # UPDATE BRANCH: Second call with same anilist_id, new popularity value.
        payload["popularity"] = 99999
        sync_anime_to_db(payload)
        db.session.flush()

        # Refetch again to verify update persisted
        fetched_again = Anime.query.filter_by(anilist_id=555555).first()
        assert fetched_again is not None
        assert fetched_again.popularity == 99999


def test_normalize_null_average_score_stays_none():
    """AniList returns null averageScore for unrated titles; storing 0.0
    would overwrite real scores on re-sync (the upsert skips None)."""
    from utils.anilist import AniListClient

    client = AniListClient()
    out = client._normalize_anime({"id": 1, "idMal": None, "title": {"romaji": "X"}})
    assert out["api_score"] is None


class _IdClient:
    """Stand-in for AniListClient exposing get_anime(id) from a dict."""

    def __init__(self, by_id):
        self.by_id = by_id
        self.calls = []

    def get_anime(self, anilist_id):
        self.calls.append(anilist_id)
        return self.by_id.get(anilist_id)


def test_sync_ids_backfills_specific_titles(app):
    from sync_anilist import sync_ids
    from models import Anime

    with app.app_context():
        client = _IdClient(
            {137667: _media(anilist_id=137667, title="Lord of Mysteries", year=2025)}
        )
        summary = sync_ids(client, [137667])
        assert summary["synced"] == 1
        assert summary["failed"] == 0
        assert Anime.query.filter_by(anilist_id=137667).count() == 1
        assert client.calls == [137667]

        summary2 = sync_ids(client, [137667])
        assert summary2["synced"] == 1
        assert Anime.query.filter_by(anilist_id=137667).count() == 1


def test_sync_ids_skips_unknown_without_crashing(app):
    from sync_anilist import sync_ids
    from models import Anime

    with app.app_context():
        client = _IdClient({})
        summary = sync_ids(client, [999999])
        assert summary["synced"] == 0
        assert summary["failed"] == 1
        assert Anime.query.filter_by(anilist_id=999999).count() == 0


def test_sync_ids_dry_run_writes_nothing(app):
    from sync_anilist import sync_ids
    from models import Anime

    with app.app_context():
        client = _IdClient({7: _media(anilist_id=7, title="Dry Run Show", year=2024)})
        summary = sync_ids(client, [7], dry_run=True)
        assert summary["synced"] == 1
        assert Anime.query.filter_by(anilist_id=7).count() == 0


def test_orphan_catcher_reaches_seasonyear_null_ona():
    """Guard the coverage fix: the orphan-catcher must keep covering ONA, and
    its query must NOT filter by seasonYear (that's what hides donghua)."""
    from sync_anilist import ORPHAN_FORMATS
    from utils.anilist import CATALOG_QUERY_BY_FORMAT

    assert "ONA" in ORPHAN_FORMATS
    assert "seasonYear" not in CATALOG_QUERY_BY_FORMAT
