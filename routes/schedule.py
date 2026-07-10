"""Schedule API — weekly episode windows and per-anime episode lists.

This blueprint owns `/api/schedule/week` (the /schedule page's Sunday-anchored
timeline) and `/api/anime/<id>/episodes` (the AnimeDetail "next episode"
widget). Both endpoints are JWT-protected and registered under
`url_prefix="/api"` so the schedule feature stays self-contained.

Both surfaces share one notion of an *estimated* dub date: a dub air date is
estimated exactly when its `Episode.dub_source` is the synthetic projection
tag (`SYNTHETIC_TAG`). `/week` exposes it as the per-row `estimated` flag and
`/episodes` as `dub_estimated`, so the timeline and the detail page label the
same date the same way.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from flask import Blueprint, jsonify, request
from flask_jwt_extended import get_jwt_identity, jwt_required

from models import db, Anime, Episode, WatchlistEntry
from utils.nsfw import maybe_exclude_nsfw
from utils.schedule_window import window_rows_query
from seed_dub_schedule import SYNTHETIC_TAG


schedule_bp = Blueprint("schedule", __name__)


# ─── Helpers ────────────────────────────────────────────────────────────────


def _as_iso_z(dt: datetime | None) -> str | None:
    """Return an ISO-8601 UTC timestamp using a trailing Z for null-safety."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def _anime_display_title(anime: Anime) -> str:
    """Prefer English title, fall back to romaji `title`."""
    return anime.title_english or anime.title


def _anime_summary(anime: Anime) -> dict:
    return {
        "id": anime.id,
        "title": _anime_display_title(anime),
        "image_url": anime.image_url,
    }


def _episode_air_date(dt: datetime | None) -> datetime | None:
    """Normalise an Episode air datetime to a UTC datetime (assume naive=UTC)."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _dub_is_estimated(episode: Episode) -> bool:
    """True when the dub air date is the synthetic projection, not a real source."""
    return (episode.dub_source or "") == SYNTHETIC_TAG


def _episode_payload(episode: Episode) -> dict:
    """Serialize an Episode with sub/dub air dates and dub provenance.

    `dub_source` is the raw provenance string; `dub_estimated` is True only for
    the synthetic projection (sub + lag). This lets the detail page flag an
    estimated dub date exactly the way the /schedule/week timeline does.
    """
    return {
        "id": episode.id,
        "episode_number": episode.episode_number,
        "air_date_sub": _as_iso_z(episode.air_date_sub),
        "air_date_dub": _as_iso_z(episode.air_date_dub),
        "dub_source": episode.dub_source,
        "dub_estimated": _dub_is_estimated(episode),
    }


def _watchlisted_anime_ids(user_id) -> set[int]:
    """Return the set of anime IDs the user has any WatchlistEntry for.

    `user_id` arrives as a string from `get_jwt_identity()` (we sign tokens
    with `identity=str(user.id)`); WatchlistEntry.user_id is an Integer column,
    so we cast before binding to avoid a silent empty result.
    """
    rows = (
        db.session.query(WatchlistEntry.anime_id)
        .filter_by(user_id=int(user_id))
        .all()
    )
    return {r[0] for r in rows}


# ─── Endpoint: GET /api/anime/<id>/episodes ────────────────────────────────


@schedule_bp.route("/anime/<int:anime_id>/episodes", methods=["GET"])
@jwt_required()
def anime_episodes(anime_id: int):
    """Return every Episode for an anime plus next_sub and next_dub."""
    anime = db.session.get(Anime, anime_id)
    if not anime:
        return jsonify({"error": "anime not found"}), 404

    episodes_q = (
        db.session.query(Episode)
        .filter(Episode.anime_id == anime_id)
        .order_by(Episode.episode_number.asc())
    )
    # Same episode-count bound the week view applies: rows numbered past the
    # catalog's own finale are ghosts (season splits, stale schedules) and
    # must not feed the "next episode" widget.
    if anime.episodes and anime.episodes > 0:
        from sqlalchemy import or_

        episodes_q = episodes_q.filter(
            or_(
                Episode.episode_number.is_(None),
                Episode.episode_number <= anime.episodes,
            )
        )
    episodes = episodes_q.all()

    episode_dicts = [_episode_payload(e) for e in episodes]

    now_utc = datetime.now(timezone.utc)

    def _next(field_name: str) -> dict | None:
        candidates = []
        for e in episodes:
            raw = getattr(e, field_name)
            air = _episode_air_date(raw)
            if air is None or air < now_utc:
                continue
            candidates.append((air, e))
        if not candidates:
            return None
        candidates.sort(key=lambda pair: pair[0])
        _, ep = candidates[0]
        return _episode_payload(ep)

    return (
        jsonify(
            {
                "episodes": episode_dicts,
                "next_sub": _next("air_date_sub"),
                "next_dub": _next("air_date_dub"),
            }
        ),
        200,
    )


# ─── Endpoint: GET /api/schedule/week ──────────────────────────────────────


def _parse_week_anchor(raw: str | None) -> datetime | None:
    """Parse a ?week=YYYY-MM-DD param into a UTC midnight datetime.

    Returns None on missing/invalid input; caller is expected to 400.
    """
    if not raw:
        return None
    try:
        dt = datetime.strptime(raw, "%Y-%m-%d")
    except ValueError:
        return None
    return dt.replace(tzinfo=timezone.utc)


def _iso_date(dt: datetime) -> str:
    """YYYY-MM-DD from a UTC datetime."""
    return dt.strftime("%Y-%m-%d")


@schedule_bp.route("/schedule/week", methods=["GET"])
@jwt_required()
def schedule_week():
    """Return a single week (Sunday-anchored, 7 days) of episodes.

    Query params:
        week  — ISO YYYY-MM-DD, required. Sunday of the visible week (UTC).
        lang  — "sub" | "dub" | "both", default "both".
        mine  — "0" | "1", default "0". When "1", only episodes from
                anime the requesting user has a WatchlistEntry for.
    """
    week_start = _parse_week_anchor(request.args.get("week"))
    if week_start is None:
        return jsonify({"error": "week parameter required (YYYY-MM-DD)"}), 400

    lang = (request.args.get("lang") or "both").lower()
    if lang not in ("sub", "dub", "both"):
        return jsonify({"error": "lang must be one of sub/dub/both"}), 400

    mine = (request.args.get("mine") or "0").strip().lower() in ("1", "true", "yes", "on")

    user_id = get_jwt_identity()
    watchlist_ids = _watchlisted_anime_ids(user_id)

    tz_name = (request.args.get("tz") or "").strip()
    try:
        view_tz = ZoneInfo(tz_name) if tz_name else timezone.utc
    except (ZoneInfoNotFoundError, ValueError):
        view_tz = timezone.utc

    week_end = week_start + timedelta(days=7)
    # Query a ±1 day margin so episodes that shift days under tz conversion
    # aren't dropped by the UTC window; precise bucketing is by local date below.
    start_naive = (week_start - timedelta(days=1)).replace(tzinfo=None)
    end_naive = (week_end + timedelta(days=1)).replace(tzinfo=None)

    # Bucket builder seeded with empty days so the response is always 7 long.
    buckets: dict[str, list[dict]] = {}
    for i in range(7):
        bucket_date = week_start + timedelta(days=i)
        buckets[_iso_date(bucket_date)] = []

    def _collect(field, kind: str) -> None:
        rows = (
            maybe_exclude_nsfw(
                window_rows_query(field, start_naive, end_naive)
            )
            .all()
        )
        for episode, anime in rows:
            if mine and anime.id not in watchlist_ids:
                continue
            raw = getattr(episode, field.key)
            air_at = _episode_air_date(raw)
            if air_at is None:
                continue
            bucket_key = air_at.astimezone(view_tz).date().isoformat()
            if bucket_key not in buckets:
                continue
            buckets[bucket_key].append({
                "id": episode.id,
                "anime_id": anime.id,
                "anime": _anime_summary(anime),
                "episode_number": episode.episode_number,
                "air_time_utc": _as_iso_z(air_at),
                "type": kind,
                "estimated": (kind == "dub" and _dub_is_estimated(episode)),
                "on_watchlist": anime.id in watchlist_ids,
                "_sort_air": air_at,
                "_sort_title": (anime.title or "").lower(),
            })

    if lang in ("sub", "both"):
        _collect(Episode.air_date_sub, "sub")
    if lang in ("dub", "both"):
        _collect(Episode.air_date_dub, "dub")

    days_payload = []
    for i in range(7):
        date_key = _iso_date(week_start + timedelta(days=i))
        episodes = buckets[date_key]
        episodes.sort(key=lambda e: (e["_sort_air"], e["_sort_title"]))
        for e in episodes:
            e.pop("_sort_air", None)
            e.pop("_sort_title", None)
        days_payload.append({"date": date_key, "episodes": episodes})

    return jsonify({
        "week_start": _iso_date(week_start),
        "days": days_payload,
    }), 200
