"""Activity feed routes."""
from datetime import datetime
from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity

from models import db, Anime, Rating, FanGenreVote, WatchlistEntry

activity_bp = Blueprint("activity", __name__)


def _rating_event(r: Rating, anime: Anime):
    return {
        "type": "rating",
        "anime_id": anime.id,
        "anime_title": anime.title_english or anime.title,
        "cover": anime.image_url,
        "timestamp": (r.updated_at or r.created_at).isoformat()
        if (r.updated_at or r.created_at)
        else None,
        "meta": {"score": r.score, "has_review": bool(r.review)},
    }


def _genre_event(v: FanGenreVote, anime: Anime):
    return {
        "type": "genre_vote",
        "anime_id": anime.id,
        "anime_title": anime.title_english or anime.title,
        "cover": anime.image_url,
        "timestamp": v.created_at.isoformat() if v.created_at else None,
        "meta": {"genre": v.genre_tag},
    }


def _status_event(w: WatchlistEntry, anime: Anime):
    return {
        "type": "status",
        "anime_id": anime.id,
        "anime_title": anime.title_english or anime.title,
        "cover": anime.image_url,
        "timestamp": (w.updated_at or w.created_at).isoformat()
        if (w.updated_at or w.created_at)
        else None,
        "meta": {"status": w.status, "episodes_watched": w.episodes_watched},
    }


def _fetch_events(user_id: int, before):
    out: list[dict] = []

    ratings = (
        db.session.query(Rating, Anime)
        .join(Anime, Anime.id == Rating.anime_id)
        .filter(Rating.user_id == user_id)
        .all()
    )
    out.extend(_rating_event(r, a) for r, a in ratings)

    votes = (
        db.session.query(FanGenreVote, Anime)
        .join(Anime, Anime.id == FanGenreVote.anime_id)
        .filter(FanGenreVote.user_id == user_id)
        .all()
    )
    out.extend(_genre_event(v, a) for v, a in votes)

    statuses = (
        db.session.query(WatchlistEntry, Anime)
        .join(Anime, Anime.id == WatchlistEntry.anime_id)
        .filter(WatchlistEntry.user_id == user_id)
        .all()
    )
    out.extend(_status_event(w, a) for w, a in statuses)

    out = [e for e in out if e["timestamp"]]
    out.sort(key=lambda e: e["timestamp"], reverse=True)
    if before:
        out = [e for e in out if e["timestamp"] < before.isoformat()]
    return out


@activity_bp.route("", methods=["GET"])
@jwt_required()
def feed():
    user_id = int(get_jwt_identity())
    try:
        limit = max(1, min(int(request.args.get("limit", 50)), 200))
    except ValueError:
        limit = 50
    before_raw = request.args.get("before")
    before = None
    if before_raw:
        try:
            before = datetime.fromisoformat(before_raw.replace("Z", "+00:00"))
        except ValueError:
            return jsonify({"error": "invalid `before` timestamp"}), 400

    events = _fetch_events(user_id, before)[:limit]
    return jsonify({"items": events})


@activity_bp.route("/on-this-day", methods=["GET"])
@jwt_required()
def on_this_day():
    user_id = int(get_jwt_identity())
    today = datetime.utcnow()
    events = _fetch_events(user_id, None)
    matches = []
    for e in events:
        try:
            ts = datetime.fromisoformat(e["timestamp"].replace("Z", "+00:00"))
        except ValueError:
            continue
        if ts.month == today.month and ts.day == today.day and ts.year < today.year:
            matches.append(e)
    return jsonify({"items": matches})
