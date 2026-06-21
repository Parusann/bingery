"""Tests for the Crunchyroll RSS dub ingester (Plan 4 Task B2a)."""
from __future__ import annotations

from datetime import datetime, timezone

import pytest
import responses

from models import Anime, Episode, db
from utils.dub_sources.crunchyroll import (
    CR_RSS_URL,
    DUB_SOURCE,
    best_match,
    extract_episode_number,
    extract_show_title,
    fetch_feed,
    ingest_feed,
    parse_pub_date,
    parse_rss,
    token_set_ratio,
)


# ─── Fixtures ────────────────────────────────────────────────────────────────


RSS_FIXTURE = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>Crunchyroll Episodes</title>
    <link>https://www.crunchyroll.com</link>
    <description>Sample dub-release feed.</description>
    <item>
      <title>Attack on Titan Episode 12</title>
      <link>https://www.crunchyroll.com/aot-12</link>
      <pubDate>Mon, 11 May 2026 21:00:00 +0000</pubDate>
    </item>
    <item>
      <title>My Hero Academia Season 7 Episode 3</title>
      <link>https://www.crunchyroll.com/mha-s7-3</link>
      <pubDate>Tue, 12 May 2026 19:30:00 +0000</pubDate>
    </item>
    <item>
      <title>Demon Slayer Ep. 5</title>
      <link>https://www.crunchyroll.com/ds-5</link>
      <pubDate>Wed, 13 May 2026 18:00:00 +0000</pubDate>
    </item>
    <item>
      <title>Some Random Show With No Match Episode 1</title>
      <link>https://www.crunchyroll.com/random</link>
      <pubDate>Thu, 14 May 2026 12:00:00 +0000</pubDate>
    </item>
    <item>
      <title>News Announcement: Big Update</title>
      <link>https://www.crunchyroll.com/news</link>
      <pubDate>Thu, 14 May 2026 13:00:00 +0000</pubDate>
    </item>
  </channel>
</rss>
"""


def _seed_anime(app):
    """Insert three matchable anime + return their ids."""
    with app.app_context():
        rows = [
            Anime(
                anilist_id=1001,
                title="Attack on Titan",
                title_english="Attack on Titan",
                synopsis="",
                year=2013,
                episodes=25,
                studio="WIT",
                image_url="",
                source="MANGA",
                status="FINISHED",
            ),
            Anime(
                anilist_id=1002,
                title="Boku no Hero Academia",
                title_english="My Hero Academia",
                synopsis="",
                year=2016,
                episodes=13,
                studio="Bones",
                image_url="",
                source="MANGA",
                status="RELEASING",
            ),
            Anime(
                anilist_id=1003,
                title="Kimetsu no Yaiba",
                title_english="Demon Slayer",
                synopsis="",
                year=2019,
                episodes=26,
                studio="ufotable",
                image_url="",
                source="MANGA",
                status="RELEASING",
            ),
            Anime(
                anilist_id=1004,
                title="Boku no Hero Academia 7",
                title_english="My Hero Academia Season 7",
                synopsis="",
                year=2026,
                episodes=12,
                studio="Bones",
                image_url="",
                source="MANGA",
                status="RELEASING",
            ),
        ]
        db.session.add_all(rows)
        db.session.commit()
        return {r.anilist_id: r.id for r in rows}


# ─── Pure helpers ────────────────────────────────────────────────────────────


def test_parse_pub_date_rfc822_utc():
    dt = parse_pub_date("Mon, 11 May 2026 21:00:00 +0000")
    assert dt is not None
    assert dt.year == 2026 and dt.month == 5 and dt.day == 11
    assert dt.hour == 21 and dt.tzinfo == timezone.utc


def test_parse_pub_date_invalid():
    assert parse_pub_date("not-a-date") is None
    assert parse_pub_date("") is None


def test_extract_episode_number_word():
    assert extract_episode_number("Attack on Titan Episode 12") == 12


def test_extract_episode_number_abbreviation():
    assert extract_episode_number("Demon Slayer Ep. 5") == 5
    assert extract_episode_number("Show Ep 17") == 17


def test_extract_episode_number_missing():
    assert extract_episode_number("News Announcement: Big Update") is None


def test_extract_show_title_strips_episode_tail():
    assert extract_show_title("Attack on Titan Episode 12") == "Attack on Titan"
    assert extract_show_title("My Hero Academia Season 7 Episode 3") == "My Hero Academia Season 7"
    assert extract_show_title("Demon Slayer Ep. 5") == "Demon Slayer"


def test_token_set_ratio_identical_is_100():
    assert token_set_ratio("Attack on Titan", "Attack on Titan") == 100.0


def test_token_set_ratio_word_reorder_high():
    # Token-set is robust to word order.
    assert token_set_ratio("Attack on Titan", "Titan Attack on") >= 80.0


def test_token_set_ratio_no_overlap_low():
    assert token_set_ratio("Naruto", "Bleach") < 50.0


def test_token_set_ratio_empty_strings():
    assert token_set_ratio("", "anything") == 0.0
    assert token_set_ratio("anything", "") == 0.0


# ─── Parsing ─────────────────────────────────────────────────────────────────


def test_parse_rss_extracts_all_entries_with_dates():
    entries = parse_rss(RSS_FIXTURE)
    assert len(entries) == 5
    titles = [e.raw_title for e in entries]
    assert "Attack on Titan Episode 12" in titles
    assert "News Announcement: Big Update" in titles


def test_parse_rss_normalizes_show_and_episode():
    entries = parse_rss(RSS_FIXTURE)
    aot = next(e for e in entries if "Attack" in e.raw_title)
    assert aot.show_title == "Attack on Titan"
    assert aot.episode_number == 12
    news = next(e for e in entries if "News" in e.raw_title)
    assert news.episode_number is None


# ─── Matching ────────────────────────────────────────────────────────────────


def test_best_match_returns_correct_anime(app):
    ids = _seed_anime(app)
    with app.app_context():
        candidates = Anime.query.all()
        anime, score = best_match("Attack on Titan", candidates)
        assert anime is not None
        assert anime.id == ids[1001]
        assert score >= 80.0


def test_best_match_matches_english_title(app):
    ids = _seed_anime(app)
    with app.app_context():
        candidates = Anime.query.all()
        anime, score = best_match("Demon Slayer", candidates)
        assert anime is not None
        assert anime.id == ids[1003]
        assert score >= 80.0


def test_best_match_demotes_unknown_later_season():
    """A later-season feed with only the base row present scores below the
    accept threshold (safe failure: no wrong-season dub written)."""
    base = _Cand("Boku no Hero Academia", "My Hero Academia")
    _, score = best_match("My Hero Academia Season 7", [base])
    assert score < 80.0


def test_best_match_returns_low_score_for_unknown(app):
    _seed_anime(app)
    with app.app_context():
        candidates = Anime.query.all()
        _, score = best_match("Some Random Show With No Match", candidates)
        assert score < 80.0


# ─── Ingest end-to-end ───────────────────────────────────────────────────────


def test_ingest_feed_dry_run_does_not_write(app):
    _seed_anime(app)
    with app.app_context():
        before = Episode.query.count()
        summary = ingest_feed(RSS_FIXTURE, dry_run=True)
        after = Episode.query.count()
    assert after == before
    assert summary["dry_run"] is True
    assert summary["matched"] >= 3  # AoT, MHA, Demon Slayer
    assert summary["written"] == 0


def test_ingest_feed_writes_episodes_with_dub_source(app):
    ids = _seed_anime(app)
    with app.app_context():
        summary = ingest_feed(RSS_FIXTURE, dry_run=False)
        aot_ep = (
            Episode.query
            .filter_by(anime_id=ids[1001], episode_number=12)
            .first()
        )
        assert aot_ep is not None
        assert aot_ep.dub_source == DUB_SOURCE
        assert aot_ep.air_date_dub is not None
        assert aot_ep.air_date_dub.year == 2026
        assert aot_ep.air_date_dub.month == 5
        assert aot_ep.air_date_dub.day == 11
        # Season-aware: the "My Hero Academia Season 7" entry attaches to the
        # Season-7 row, NOT the base row.
        mha_s7_ep = (
            Episode.query
            .filter_by(anime_id=ids[1004], episode_number=3)
            .first()
        )
        assert mha_s7_ep is not None
        assert Episode.query.filter_by(anime_id=ids[1002]).first() is None
    assert summary["written"] >= 3


def test_ingest_feed_is_idempotent(app):
    _seed_anime(app)
    with app.app_context():
        first = ingest_feed(RSS_FIXTURE, dry_run=False)
        ep_count_after_first = Episode.query.count()
        second = ingest_feed(RSS_FIXTURE, dry_run=False)
        ep_count_after_second = Episode.query.count()
    assert ep_count_after_first == ep_count_after_second
    assert first["written"] == second["written"]


def test_ingest_feed_since_filters_older_entries(app):
    _seed_anime(app)
    since = datetime(2026, 5, 13, tzinfo=timezone.utc)
    with app.app_context():
        summary = ingest_feed(RSS_FIXTURE, dry_run=False, since=since)
        # AoT (May 11) + MHA (May 12) filtered out; Demon Slayer (May 13) kept.
        assert summary["parsed"] <= 3
        # Demon Slayer should still be present.
        ds = (
            Episode.query
            .filter(Episode.episode_number == 5, Episode.dub_source == DUB_SOURCE)
            .first()
        )
        assert ds is not None


def test_ingest_feed_skips_entries_with_no_episode_number(app):
    _seed_anime(app)
    with app.app_context():
        summary = ingest_feed(RSS_FIXTURE, dry_run=True)
    assert summary["skipped_no_episode_number"] >= 1


def test_ingest_feed_records_unmatched_titles(app):
    _seed_anime(app)
    with app.app_context():
        summary = ingest_feed(RSS_FIXTURE, dry_run=True)
    assert summary["unmatched"] >= 1
    assert any(
        "Random" in u["title"] for u in summary["unmatched_titles"]
    )


# ─── HTTP layer ──────────────────────────────────────────────────────────────


@responses.activate
def test_fetch_feed_get_with_user_agent():
    responses.add(
        responses.GET,
        CR_RSS_URL,
        body=RSS_FIXTURE,
        status=200,
        content_type="application/rss+xml",
    )
    xml = fetch_feed()
    assert "<rss" in xml
    assert "Attack on Titan" in xml
    assert len(responses.calls) == 1
    ua = responses.calls[0].request.headers.get("User-Agent", "")
    assert "bingery-dub-sync" in ua


@responses.activate
def test_fetch_feed_raises_on_5xx():
    responses.add(responses.GET, CR_RSS_URL, status=503)
    with pytest.raises(Exception):
        fetch_feed()


# ─── Season-aware matching ───────────────────────────────────────────────────


class _Cand:
    """Lightweight candidate with the fields best_match reads."""

    def __init__(self, title, title_english=None):
        self.title = title
        self.title_english = title_english


def test_parse_season_variants():
    from utils.dub_sources.crunchyroll import _parse_season

    assert _parse_season("My Hero Academia") == 1
    assert _parse_season("My Hero Academia Season 7") == 7
    assert _parse_season("My Hero Academia 3rd Season") == 3
    assert _parse_season("Show Part 2") == 2
    assert _parse_season("Show Cour 2") == 2
    assert _parse_season("Show S2") == 2
    assert _parse_season("Mob Psycho 100") == 1  # a bare number is not a season


def test_best_match_picks_correct_season_not_base():
    base = _Cand("My Hero Academia")
    s7 = _Cand("My Hero Academia Season 7")
    anime, _ = best_match("My Hero Academia Season 7", [base, s7])
    assert anime is s7


def test_best_match_no_season_picks_base():
    base = _Cand("My Hero Academia")
    s7 = _Cand("My Hero Academia Season 7")
    anime, _ = best_match("My Hero Academia", [base, s7])
    assert anime is base


def test_best_match_part_distinguishes_seasons():
    p1 = _Cand("Attack on Titan")
    p2 = _Cand("Attack on Titan Part 2")
    anime, _ = best_match("Attack on Titan Part 2", [p1, p2])
    assert anime is p2
