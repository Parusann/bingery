"""Activity feed routes."""
from datetime import datetime, timezone
from math import ceil

from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity

from models import (
    db,
    Anime,
    DubReport,
    Episode,
    Rating,
    FanGenreVote,
    WatchlistEntry,
    Collection,
    CollectionItem,
)

activity_bp = Blueprint("activity", __name__)


# Stable per-kind code used to synthesize a globally unique event id.
# id = KIND_CODE[kind] * 10**12 + model_pk
KIND_CODE = {
    "rating": 1,
    "watch_status": 2,
    "genre_vote": 3,
    "favorite": 4,
    "collection_item": 5,
    "collection_create": 6,
    "dub_report": 7,
}

_ID_OFFSET = 10**12


def _synth_id(kind: str, pk: int) -> int:
    return KIND_CODE[kind] * _ID_OFFSET + int(pk)


def _anime_payload(anime):
    if anime is None:
        return None
    return {
        "id": anime.id,
        "title": anime.title_english or anime.title,
        "image_url": anime.image_url,
    }


def _rating_event(r: Rating, anime: Anime):
    dt = r.updated_at or r.created_at
    return dt, {
        "id": _synth_id("rating", r.id),
        "kind": "rating",
        "created_at": dt.isoformat() if dt else None,
        "anime": _anime_payload(anime),
        "meta": {"score": r.score, "has_review": bool(r.review)},
    }


def _genre_event(v: FanGenreVote, anime: Anime):
    dt = v.created_at
    return dt, {
        "id": _synth_id("genre_vote", v.id),
        "kind": "genre_vote",
        "created_at": dt.isoformat() if dt else None,
        "anime": _anime_payload(anime),
        "meta": {"genre": v.genre_tag},
    }


def _watch_status_event(w: WatchlistEntry, anime: Anime):
    dt = w.updated_at or w.created_at
    return dt, {
        "id": _synth_id("watch_status", w.id),
        "kind": "watch_status",
        "created_at": dt.isoformat() if dt else None,
        "anime": _anime_payload(anime),
        "meta": {
            "status": w.status,
            "episodes_watched": w.episodes_watched or 0,
        },
    }


def _favorite_event(w: WatchlistEntry, anime: Anime):
    dt = w.updated_at or w.created_at
    return dt, {
        "id": _synth_id("favorite", w.id),
        "kind": "favorite",
        "created_at": dt.isoformat() if dt else None,
        "anime": _anime_payload(anime),
        "meta": {},
    }


def _collection_item_event(ci: CollectionItem, anime: Anime, col: Collection):
    dt = ci.added_at
    return dt, {
        "id": _synth_id("collection_item", ci.id),
        "kind": "collection_item",
        "created_at": dt.isoformat() if dt else None,
        "anime": _anime_payload(anime),
        "meta": {
            "collection_id": col.id,
            "collection_title": col.name,
        },
    }


def _collection_create_event(col: Collection):
    dt = col.created_at
    return dt, {
        "id": _synth_id("collection_create", col.id),
        "kind": "collection_create",
        "created_at": dt.isoformat() if dt else None,
        "anime": None,
        "meta": {"title": col.name},
    }


def _dub_report_event(r: DubReport, episode: Episode, anime: Anime):
    dt = r.created_at
    return dt, {
        "id": _synth_id("dub_report", r.id),
        "kind": "dub_report",
        "created_at": dt.isoformat() if dt else None,
        "anime": _anime_payload(anime),
        "meta": {
            "episode_number": episode.episode_number,
            "air_date": r.air_date.isoformat() if r.air_date else None,
            "status": r.status,
            "note": r.note,
        },
    }


def _fetch_events(user_id: int, before):
    """Return list of (datetime, event_dict) pairs, newest first.

    `before` must be tz-naive UTC datetime or None.
    Sort: descending datetime, tiebreak ascending kind for stability.
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

    watchlist_rows = (
        db.session.query(WatchlistEntry, Anime)
        .join(Anime, Anime.id == WatchlistEntry.anime_id)
        .filter(WatchlistEntry.user_id == user_id)
        .all()
    )
    for w, a in watchlist_rows:
        pairs.append(_watch_status_event(w, a))
        if w.is_favorite:
            pairs.append(_favorite_event(w, a))

    collection_items = (
        db.session.query(CollectionItem, Anime, Collection)
        .join(Collection, Collection.id == CollectionItem.collection_id)
        .join(Anime, Anime.id == CollectionItem.anime_id)
        .filter(Collection.user_id == user_id)
        .all()
    )
    pairs.extend(_collection_item_event(ci, a, c) for ci, a, c in collection_items)

    collections = (
        db.session.query(Collection)
        .filter(Collection.user_id == user_id)
        .all()
    )
    pairs.extend(_collection_create_event(c) for c in collections)

    dub_reports = (
        db.session.query(DubReport, Episode, Anime)
        .join(Episode, Episode.id == DubReport.episode_id)
        .join(Anime, Anime.id == Episode.anime_id)
        .filter(DubReport.submitted_by == user_id)
        .all()
    )
    pairs.extend(_dub_report_event(r, ep, a) for r, ep, a in dub_reports)

    pairs = [(dt, e) for dt, e in pairs if dt is not None]
    # Stable two-pass sort: ascending kind first (tiebreak), then descending dt.
    # Python's sort is stable so the kind order is preserved for equal datetimes.
    pairs.sort(key=lambda p: p[1]["kind"])
    pairs.sort(key=lambda p: p[0], reverse=True)
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

    try:
        page = int(request.args.get("page", 1))
        if page < 1:
            page = 1
    except (ValueError, TypeError):
        page = 1

    before_raw = request.args.get("before")
    before = None
    if before_raw:
        try:
            before = _parse_before(before_raw)
        except ValueError:
            return jsonify({"error": "invalid `before` timestamp"}), 400

    pairs = _fetch_events(user_id, before)
    total = len(pairs)
    pages = max(1, ceil(total / limit)) if total else 1

    start = (page - 1) * limit
    end = start + limit
    sliced = pairs[start:end]

    return jsonify(
        {
            "events": [e for _dt, e in sliced],
            "page": page,
            "pages": pages,
        }
    )


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
