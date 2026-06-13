from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload
from models import db, Anime, Rating, FanGenreVote, WatchlistEntry, WATCH_STATUSES


def _parse_episodes(value):
    """Coerce episodes_watched to a non-negative int; None if invalid."""
    if isinstance(value, bool):
        return None
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return None

watchlist_bp = Blueprint("watchlist", __name__, url_prefix="/api/watchlist")


@watchlist_bp.route("", methods=["GET"])
@jwt_required()
def get_watchlist():
    """
    GET /api/watchlist?status=watching&sort=updated&page=1&per_page=50
    Get the user's full watchlist, optionally filtered by status.
    """
    user_id = int(get_jwt_identity())
    status_filter = request.args.get("status", "").strip()
    sort = request.args.get("sort", "updated")
    page = request.args.get("page", 1, type=int)
    per_page = min(request.args.get("per_page", 50, type=int), 100)

    query = db.session.query(WatchlistEntry).filter_by(user_id=user_id)

    if status_filter and status_filter in WATCH_STATUSES:
        query = query.filter_by(status=status_filter)

    if sort == "title":
        query = query.join(Anime).order_by(Anime.title.asc())
    elif sort == "score":
        query = query.join(Anime).order_by(
            Anime.api_score.desc().nullslast(), WatchlistEntry.updated_at.desc()
        )
    else:
        query = query.order_by(WatchlistEntry.updated_at.desc())

    # Eager-load the anime + its genres so building each entry doesn't fire
    # a query per row for them.
    query = query.options(
        selectinload(WatchlistEntry.anime).selectinload(Anime.official_genres)
    )

    paginated = query.paginate(page=page, per_page=per_page, error_out=False)
    items = paginated.items

    # Batch the per-entry rating + fan-genre lookups that to_dict(include_anime)
    # would otherwise issue one-by-one (the N+1). Page anime_ids are bounded by
    # per_page (<=100), safe for SQLite's IN(...) variable limit.
    anime_ids = [e.anime_id for e in items]
    score_by_anime = {}
    votes_by_anime = {}
    if anime_ids:
        score_by_anime = dict(
            db.session.query(Rating.anime_id, Rating.score).filter(
                Rating.user_id == user_id, Rating.anime_id.in_(anime_ids)
            )
        )
        for aid, tag in db.session.query(
            FanGenreVote.anime_id, FanGenreVote.genre_tag
        ).filter(
            FanGenreVote.user_id == user_id, FanGenreVote.anime_id.in_(anime_ids)
        ):
            votes_by_anime.setdefault(aid, []).append(tag)

    entries = []
    for e in items:
        d = e.to_dict(include_anime=False)
        d["anime"] = e.anime.to_dict(include_community=False)
        d["score"] = score_by_anime.get(e.anime_id)
        d["genres"] = votes_by_anime.get(e.anime_id, [])
        entries.append(d)

    return jsonify({
        "entries": entries,
        "total": paginated.total,
        "page": paginated.page,
        "pages": paginated.pages,
    }), 200


@watchlist_bp.route("/stats", methods=["GET"])
@jwt_required()
def get_watchlist_stats():
    """GET /api/watchlist/stats — Count per status."""
    user_id = int(get_jwt_identity())
    counts = {}
    for status in WATCH_STATUSES:
        counts[status] = db.session.query(WatchlistEntry).filter_by(
            user_id=user_id, status=status
        ).count()
    counts["total"] = sum(counts.values())
    counts["favorites"] = db.session.query(WatchlistEntry).filter_by(
        user_id=user_id, is_favorite=True
    ).count()
    return jsonify({"stats": counts}), 200


@watchlist_bp.route("/anime/<int:anime_id>", methods=["POST"])
@jwt_required()
def set_watch_status(anime_id):
    """
    POST /api/watchlist/anime/5
    Body: { "status": "watching", "episodes_watched": 12, "is_favorite": false }
    Creates or updates a watchlist entry.
    """
    user_id = int(get_jwt_identity())
    anime = db.session.get(Anime, anime_id)
    if not anime:
        return jsonify({"error": "Anime not found."}), 404

    data = request.get_json() or {}
    status = data.get("status", "plan_to_watch")
    if status not in WATCH_STATUSES:
        return jsonify({"error": f"Invalid status. Must be one of: {', '.join(WATCH_STATUSES)}"}), 400

    episodes = None
    if "episodes_watched" in data:
        episodes = _parse_episodes(data["episodes_watched"])
        if episodes is None:
            return jsonify({"error": "'episodes_watched' must be a non-negative integer."}), 400

    def _apply(entry):
        entry.status = status
        if episodes is not None:
            entry.episodes_watched = episodes
        if "is_favorite" in data:
            entry.is_favorite = bool(data["is_favorite"])
        if "notes" in data:
            entry.notes = (data["notes"] or "")[:1000]

    entry = db.session.query(WatchlistEntry).filter_by(user_id=user_id, anime_id=anime_id).first()
    if entry:
        _apply(entry)
    else:
        entry = WatchlistEntry(
            user_id=user_id,
            anime_id=anime_id,
            status=status,
            episodes_watched=episodes or 0,
            is_favorite=bool(data.get("is_favorite", False)),
            notes=(data.get("notes") or "")[:1000],
        )
        db.session.add(entry)

    try:
        db.session.commit()
    except IntegrityError:
        # Concurrent first-write for this (user, anime): adopt the winner's
        # row and apply this request's fields — latest write wins.
        db.session.rollback()
        entry = db.session.query(WatchlistEntry).filter_by(user_id=user_id, anime_id=anime_id).first()
        if entry is None:
            return jsonify({"error": "Concurrent update — please retry."}), 409
        _apply(entry)
        db.session.commit()
    return jsonify({"entry": entry.to_dict(include_anime=True)}), 200


@watchlist_bp.route("/anime/<int:anime_id>", methods=["GET"])
@jwt_required()
def get_watch_status(anime_id):
    """Get the user's watchlist entry for a specific anime."""
    user_id = int(get_jwt_identity())
    entry = db.session.query(WatchlistEntry).filter_by(user_id=user_id, anime_id=anime_id).first()
    if not entry:
        return jsonify({"entry": None}), 200
    return jsonify({"entry": entry.to_dict()}), 200


@watchlist_bp.route("/anime/<int:anime_id>", methods=["DELETE"])
@jwt_required()
def remove_from_watchlist(anime_id):
    """Remove an anime from the user's watchlist."""
    user_id = int(get_jwt_identity())
    entry = db.session.query(WatchlistEntry).filter_by(user_id=user_id, anime_id=anime_id).first()
    if not entry:
        return jsonify({"error": "Not in your watchlist."}), 404
    db.session.delete(entry)
    db.session.commit()
    return jsonify({"message": "Removed from watchlist."}), 200


@watchlist_bp.route("/anime/<int:anime_id>/favorite", methods=["POST"])
@jwt_required()
def toggle_favorite(anime_id):
    """Toggle favorite status. Creates a watchlist entry if needed."""
    user_id = int(get_jwt_identity())
    anime = db.session.get(Anime, anime_id)
    if not anime:
        return jsonify({"error": "Anime not found."}), 404

    entry = db.session.query(WatchlistEntry).filter_by(user_id=user_id, anime_id=anime_id).first()
    if entry:
        entry.is_favorite = not entry.is_favorite
    else:
        entry = WatchlistEntry(
            user_id=user_id, anime_id=anime_id,
            status="plan_to_watch", is_favorite=True,
        )
        db.session.add(entry)

    db.session.commit()
    return jsonify({"entry": entry.to_dict(), "is_favorite": entry.is_favorite}), 200


@watchlist_bp.route("/bulk", methods=["POST"])
@jwt_required()
def bulk_add():
    """
    POST /api/watchlist/bulk
    Body: { "anime_ids": [1, 2, 3], "status": "plan_to_watch" }
    Add multiple anime at once (for onboarding/import).
    """
    user_id = int(get_jwt_identity())
    data = request.get_json(silent=True) or {}
    anime_ids = data.get("anime_ids", [])
    status = data.get("status", "plan_to_watch")

    if status not in WATCH_STATUSES:
        return jsonify({"error": "Invalid status."}), 400
    if not isinstance(anime_ids, list) or not all(
        isinstance(a, int) and not isinstance(a, bool) for a in anime_ids
    ):
        return jsonify({"error": "'anime_ids' must be a list of integers."}), 400

    ids = anime_ids[:100]  # cap at 100
    valid_ids = {x for (x,) in db.session.query(Anime.id).filter(Anime.id.in_(ids))}
    already = {
        x for (x,) in db.session.query(WatchlistEntry.anime_id).filter(
            WatchlistEntry.user_id == user_id, WatchlistEntry.anime_id.in_(ids)
        )
    }

    added = 0
    for aid in ids:
        if aid in valid_ids and aid not in already:
            db.session.add(WatchlistEntry(user_id=user_id, anime_id=aid, status=status))
            already.add(aid)  # also dedupes repeats within the payload
            added += 1

    db.session.commit()
    return jsonify({"added": added, "status": status}), 200
