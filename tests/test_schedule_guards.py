"""Per-track ghost guards on /api/schedule/week.

The week view must not serve:
  * future-dated sub episodes of shows whose sub track is finished/cancelled
    (the "completed-anime leak" — stale rows for shows that stopped airing),
  * synthetic dub projections for finished shows with no real dub evidence
    (fabrications for possibly-never-dubbed titles),
  * episodes numbered beyond the catalog's own episode count (they cannot
    exist on any track).

It MUST still serve:
  * past episodes of finished shows (this week's history),
  * real-source dub dates of finished shows (ongoing dub of a finished sub),
  * synthetic trailing estimates for finished shows that DO have real dub
    evidence (labeled estimates, the seeder's contract),
  * future episodes of airing/upcoming shows.
"""

from datetime import datetime, timedelta, timezone

import pytest

from models import db, Anime, Episode
from seed_dub_schedule import SYNTHETIC_TAG

NOW = datetime.now(timezone.utc)
FUTURE = (NOW + timedelta(hours=1)).replace(tzinfo=None)
PAST = (NOW - timedelta(hours=1)).replace(tzinfo=None)


def _week_param(ts: datetime) -> str:
    """Sunday (UTC) of the week containing naive-UTC timestamp ts."""
    sunday = ts - timedelta(days=(ts.weekday() + 1) % 7)
    return sunday.strftime("%Y-%m-%d")


def _mk(title, status, *, episodes=None):
    anime = Anime(title=title, status=status, episodes=episodes)
    db.session.add(anime)
    db.session.flush()
    return anime


def _ep(anime, number, *, sub=None, dub=None, dub_source=None):
    e = Episode(anime_id=anime.id, episode_number=number,
                air_date_sub=sub, air_date_dub=dub, dub_source=dub_source)
    db.session.add(e)
    return e


def _served_titles(client, auth_headers, ts, lang):
    headers, _user = auth_headers
    resp = client.get(
        f"/api/schedule/week?week={_week_param(ts)}&lang={lang}",
        headers=headers,
    )
    assert resp.status_code == 200
    return {
        ep["anime"]["title"]
        for day in resp.get_json()["days"]
        for ep in day["episodes"]
    }


@pytest.fixture
def guard_data(app):
    with app.app_context():
        # sub-track cases
        _ep(_mk("Ghost Finished Sub", "Finished Airing"), 13, sub=FUTURE)
        _ep(_mk("Ghost Cancelled Sub", "Cancelled"), 3, sub=FUTURE)
        _ep(_mk("History Finished Sub", "Finished Airing"), 12, sub=PAST)
        _ep(_mk("Live Airing Sub", "Currently Airing"), 5, sub=FUTURE)
        _ep(_mk("Premiere Upcoming Sub", "Upcoming"), 1, sub=FUTURE)

        # episode-count bound (both tracks)
        over = _mk("Overrun Show", "Currently Airing", episodes=39)
        _ep(over, 47, sub=FUTURE, dub=FUTURE, dub_source=SYNTHETIC_TAG)
        _ep(over, 39, sub=FUTURE)

        # dub-track cases
        _ep(_mk("Ghost Synthetic Dub", "Finished Airing"), 4,
            dub=FUTURE, dub_source=SYNTHETIC_TAG)

        evidenced = _mk("Trailing Estimated Dub", "Finished Airing")
        _ep(evidenced, 1, dub=PAST - timedelta(days=30),
            dub_source="crunchyroll_rss")  # real evidence
        _ep(evidenced, 9, dub=FUTURE, dub_source=SYNTHETIC_TAG)

        _ep(_mk("Real Dub Of Finished Sub", "Finished Airing"), 7,
            dub=FUTURE, dub_source="crunchyroll_rss")

        _ep(_mk("Synthetic Dub Of Airing Show", "Currently Airing"), 6,
            dub=FUTURE, dub_source=SYNTHETIC_TAG)
        db.session.commit()


def test_sub_track_ghost_guards(client, auth_headers, guard_data):
    titles = _served_titles(client, auth_headers, FUTURE, "sub")
    assert "Ghost Finished Sub" not in titles
    assert "Ghost Cancelled Sub" not in titles
    assert "Live Airing Sub" in titles
    assert "Premiere Upcoming Sub" in titles


def test_past_episodes_of_finished_shows_stay(client, auth_headers, guard_data):
    titles = _served_titles(client, auth_headers, PAST, "sub")
    assert "History Finished Sub" in titles


def test_episode_count_bound_on_both_tracks(client, auth_headers, guard_data):
    sub_titles = _served_titles(client, auth_headers, FUTURE, "sub")
    dub_titles = _served_titles(client, auth_headers, FUTURE, "dub")
    # ep 47 of a 39-episode show is gone from both tracks; ep 39 survives.
    assert "Overrun Show" in sub_titles       # ep 39 (== count) still served
    assert "Overrun Show" not in dub_titles   # only ep 47 had a dub date


def test_dub_track_guards(client, auth_headers, guard_data):
    titles = _served_titles(client, auth_headers, FUTURE, "dub")
    # fabricated projection for a finished show with no dub evidence: gone
    assert "Ghost Synthetic Dub" not in titles
    # ongoing dubs of finished subs keep working, real or evidenced-estimate
    assert "Real Dub Of Finished Sub" in titles
    assert "Trailing Estimated Dub" in titles
    assert "Synthetic Dub Of Airing Show" in titles


def test_estimated_flag_survives_guards(client, auth_headers, guard_data):
    headers, _user = auth_headers
    resp = client.get(
        f"/api/schedule/week?week={_week_param(FUTURE)}&lang=dub",
        headers=headers,
    )
    rows = {
        ep["anime"]["title"]: ep
        for day in resp.get_json()["days"]
        for ep in day["episodes"]
    }
    assert rows["Trailing Estimated Dub"]["estimated"] is True
    assert rows["Real Dub Of Finished Sub"]["estimated"] is False
