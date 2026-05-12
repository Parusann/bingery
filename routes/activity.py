"""Activity feed routes."""
from datetime import datetime, timezone
from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity

from models import db, Anime, Rating, FanGenreVote, WatchlistEntry

activity_bp = Blueprint("activity", __name__)


def _rating_event(r: Rating, anime: Anime):
    dt = r.updated_at or r.created_at
    return dt, {
        "type": "rating",
        "anime_id": anime.id,
        "anime_title": anime.title_english or anime.title,
        "cover": anime.image_url,
        "timestamp": dt.isoformat() if dt else None,
        "meta": {"score": r.score, "has_review": bool(r.review)},
    }


def _genre_event(v: FanGenreVote, anime: Anime):
    dt = v.created_at
    return dt, {
        "type": "genre_vote",
        "anime_id": anime.id,
        "anime_title": anime.title_english or anime.title,
        "cover": anime.image_url,
        "timestamp": dt.isoformat() if dt else None,
        "meta": {"genre": v.genre_tag},
    }


def _status_event(w: WatchlistEntry, anime: Anime):
    dt = w.updated_at or w.created_at
    return dt, {
        "type": "status",
        "anime_id": anime.id,
        "anime_title": anime.title_english or anime.title,
        "cover": anime.image_url,
        "timestamp": dt.isoformat() if dt else None,
        "meta": {"status": w.status, "episodes_watched": w.episodes_watched},
    }


def _fetch_events(user_id: int, before):
    """Return list of (datetime, event_dict) pairs, newest first, optionally filtered by `before`.

    `before` must be a tz-naive UTC datetime (callers normalize user input).
    Sort uses (dt, type) for deterministic ordering when timestamps tie.
    """
    pairs: list = []

    ratings = (
        db.session.query(Rating, Anime)
        .join(Anime, Anime.id == Rating.anime_id)
        .filter(Rating.user_id == user_id)
        .all()
    )
    pairs.extend(_rating_event(r, a) for r, a in ratings)

    votes = (
        db.session.query(FanGenreVote, Anime)
        .join(Anime, Anime.id == FanGenreVote.anime_id)
        .filter(FanGenreVote.user_id == user_id)
        .all()
    )
    pairs.extend(_genre_event(v, a) for v, a in votes)

    statuses = (
        db.session.query(WatchlistEntry, Anime)
        .join(Anime, Anime.id == WatchlistEntry.anime_id)
        .filter(WatchlistEntry.user_id == user_id)
        .all()
    )
    pairs.extend(_status_event(w, a) for w, a in statuses)

    pairs = [(dt, e) for dt, e in pairs if dt is not None]
    # Descending by datetime; tiebreak ascending by type for stable order.
    pairs.sort(key=lambda p: (p[0], p[1]["type"]), reverse=True)
    if before is not None:
        pairs = [(dt, e) for dt, e in pairs if dt < before]
    return pairs


def _naive_utc_now() -> datetime:
    """Tz-naive UTC now — matches SQLAlchemy DateTime column storage."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _parse_before(raw: str) -> datetime:
    """Parse a user-supplied ISO-8601 timestamp into tz-naive UTC.

    Accepts both tz-aware (e.g. `2026-04-24T00:00:00Z`) and tz-naive forms.
    Raises `ValueError` on invalid input.
    """
    dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    if dt.tzinfo is not None:
        dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt


@activity_bp.route("", methods=["GET"])
@jwt_required()
def feed():
    user_id = int(get_jwt_identity())
    try:
        limit = max(1, min(int(request.args.get("limit", 50)), 200))
    except (ValueError, TypeError):
        limit = 50
    before_raw = request.args.get("before")
    before = None
    if before_raw:
        try:
            before = _parse_before(before_raw)
        except ValueError:
            return jsonify({"error": "invalid `before` timestamp"}), 400

    pairs = _fetch_events(user_id, before)[:limit]
    return jsonify({"items": [e for _dt, e in pairs]})


@activity_bp.route("/on-this-day", methods=["GET"])
@jwt_required()
def on_this_day():
    user_id = int(get_jwt_identity())
    today = _naive_utc_now()
    pairs = _fetch_events(user_id, None)
    matches = [
        e
        for dt, e in pairs
        if dt.month == today.month
        and dt.day == today.day
        and dt.year < today.year
    ]
    return jsonify({"items": matches})
