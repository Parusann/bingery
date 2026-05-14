"""Schedule API — upcoming episode windows and per-anime episode lists.

This blueprint owns both `/api/schedule/upcoming` (used by the /schedule page
to render a multi-day timeline) and `/api/anime/<id>/episodes` (used by the
AnimeDetail "next episode" widget). Both endpoints are JWT-protected.

Pattern A from Plan 4 Task A3 — both routes live in this one blueprint
registered at `url_prefix="/api"` so the schedule feature stays self-contained.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required

from models import db, Anime, Episode


schedule_bp = Blueprint("schedule", __name__)


# ─── Helpers ────────────────────────────────────────────────────────────────


def _parse_days(raw: str | None) -> int:
    """Parse and clamp the `days` query param.

    Per spec: default 7, clamp to [1, 30]. Invalid/non-numeric values fall back
    to the default of 7 rather than 400-ing.
    """
    if raw is None or raw == "":
        return 7
    try:
        n = int(raw)
    except (TypeError, ValueError):
        return 7
    if n < 1:
        return 1
    if n > 30:
        return 30
    return n


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


# ─── Endpoint 1: GET /api/schedule/upcoming ────────────────────────────────


@schedule_bp.route("/schedule/upcoming", methods=["GET"])
@jwt_required()
def upcoming():
    """Return the upcoming episode airing schedule grouped by UTC date.

    Query params:
        days  — int in [1, 30], default 7 (clamped, never errors)
        kind  — "sub" | "dub" | "both", default "sub" (400s on garbage)
    """
    days = _parse_days(request.args.get("days"))

    kind = (request.args.get("kind") or "sub").strip().lower()
    if kind not in ("sub", "dub", "both"):
        return jsonify({"error": "kind must be one of sub/dub/both"}), 400

    # Window: today (UTC) 00:00 inclusive through today + days (UTC) 00:00 exclusive.
    now_utc = datetime.now(timezone.utc)
    start = now_utc.replace(hour=0, minute=0, second=0, microsecond=0)
    end = start + timedelta(days=days)

    # Pull candidate episodes for each requested kind. SQLAlchemy compares
    # naive datetimes column-side; our column values are stored naive-UTC,
    # so we strip tzinfo before binding.
    start_naive = start.replace(tzinfo=None)
    end_naive = end.replace(tzinfo=None)

    entries: list[tuple[str, datetime, Episode, Anime]] = []

    def _collect(field, label: str) -> None:
        rows = (
            db.session.query(Episode, Anime)
            .join(Anime, Anime.id == Episode.anime_id)
            .filter(field >= start_naive)
            .filter(field < end_naive)
            .all()
        )
        for episode, anime in rows:
            raw = getattr(episode, field.key)
            air_at = _episode_air_date(raw)
            if air_at is None:
                continue
            entries.append((label, air_at, episode, anime))

    if kind in ("sub", "both"):
        _collect(Episode.air_date_sub, "sub")
    if kind in ("dub", "both"):
        _collect(Episode.air_date_dub, "dub")

    # Bucket by UTC date.
    buckets: dict[str, list[dict]] = {}
    for label, air_at, episode, anime in entries:
        date_key = air_at.date().isoformat()
        buckets.setdefault(date_key, []).append(
            {
                "id": episode.id,
                "episode_number": episode.episode_number,
                "air_at": _as_iso_z(air_at),
                "anime": _anime_summary(anime),
                "kind": label,
                # transient sort keys; stripped below
                "_sort_air": air_at,
                "_sort_title": _anime_display_title(anime) or "",
            }
        )

    # Build day list, including empty days, ordered by date ascending.
    days_payload: list[dict] = []
    for i in range(days):
        date_key = (start + timedelta(days=i)).date().isoformat()
        episodes = buckets.get(date_key, [])
        episodes.sort(key=lambda e: (e["_sort_air"], e["_sort_title"]))
        for e in episodes:
            e.pop("_sort_air", None)
            e.pop("_sort_title", None)
        days_payload.append({"date": date_key, "episodes": episodes})

    return jsonify({"days": days_payload}), 200


# ─── Endpoint 2: GET /api/anime/<id>/episodes ──────────────────────────────


@schedule_bp.route("/anime/<int:anime_id>/episodes", methods=["GET"])
@jwt_required()
def anime_episodes(anime_id: int):
    """Return every Episode for an anime plus next_sub and next_dub."""
    anime = db.session.get(Anime, anime_id)
    if not anime:
        return jsonify({"error": "anime not found"}), 404

    episodes = (
        db.session.query(Episode)
        .filter(Episode.anime_id == anime_id)
        .order_by(Episode.episode_number.asc())
        .all()
    )

    episode_dicts = [
        {
            "id": e.id,
            "episode_number": e.episode_number,
            "air_date_sub": _as_iso_z(e.air_date_sub),
            "air_date_dub": _as_iso_z(e.air_date_dub),
        }
        for e in episodes
    ]

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
        return {
            "id": ep.id,
            "episode_number": ep.episode_number,
            "air_date_sub": _as_iso_z(ep.air_date_sub),
            "air_date_dub": _as_iso_z(ep.air_date_dub),
        }

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
