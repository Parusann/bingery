from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity, verify_jwt_in_request
from sqlalchemy import func
from models import db, Anime, Genre, Rating, FanGenreVote, anime_genres, WatchlistEntry

anime_bp = Blueprint("anime", __name__, url_prefix="/api/anime")


@anime_bp.route("", methods=["GET"])
def list_anime():
    """
    GET /api/anime?page=1&per_page=20&search=&genre=Action&sort=api_score&order=desc
    Returns paginated anime list with community data.
    """
    page = request.args.get("page", 1, type=int)
    per_page = min(request.args.get("per_page", 20, type=int), 100)
    search = request.args.get("search", "").strip()
    genre_filter = request.args.get("genre", "").strip()
    sort_by = request.args.get("sort", "api_score")
    order = request.args.get("order", "desc")

    query = Anime.query

    # Search by title
    if search:
        query = query.filter(
            db.or_(
                Anime.title.ilike(f"%{search}%"),
                Anime.title_english.ilike(f"%{search}%"),
            )
        )

    # Filter by official genre
    if genre_filter:
        query = query.join(anime_genres).join(Genre).filter(Genre.name == genre_filter)

    # Sorting
    sort_column = {
        "api_score": Anime.api_score,
        "year": Anime.year,
        "title": Anime.title,
        "episodes": Anime.episodes,
    }.get(sort_by, Anime.api_score)

    if sort_column is not None:
        query = query.order_by(
            sort_column.desc().nullslast() if order == "desc" else sort_column.asc().nullsfirst()
        )

    paginated = query.paginate(page=page, per_page=per_page, error_out=False)

    return jsonify({
        "anime": [a.to_dict() for a in paginated.items],
        "total": paginated.total,
        "page": paginated.page,
        "pages": paginated.pages,
        "per_page": per_page,
    }), 200


@anime_bp.route("/<int:anime_id>", methods=["GET"])
def get_anime(anime_id):
    """Full anime detail with community scores and fan genres."""
    anime = Anime.query.get(anime_id)
    if not anime:
        return jsonify({"error": "Anime not found."}), 404

    data = anime.to_dict(include_community=True)

    # If user is logged in, include their personal rating & genre votes
    try:
        verify_jwt_in_request(optional=True)
        uid = get_jwt_identity()
        if uid:
            uid = int(uid)
            rating = Rating.query.filter_by(user_id=uid, anime_id=anime_id).first()
            data["user_rating"] = rating.to_dict() if rating else None

            votes = FanGenreVote.query.filter_by(user_id=uid, anime_id=anime_id).all()
            data["user_genre_votes"] = [v.genre_tag for v in votes]

            wl = WatchlistEntry.query.filter_by(user_id=uid, anime_id=anime_id).first()
            data["user_watch_status"] = wl.to_dict() if wl else None
    except Exception:
        data["user_rating"] = None
        data["user_genre_votes"] = []
        data["user_watch_status"] = None

    return jsonify({"anime": data}), 200


@anime_bp.route("/<int:anime_id>/ratings", methods=["GET"])
def get_anime_ratings(anime_id):
    """All ratings for an anime, with pagination."""
    anime = Anime.query.get(anime_id)
    if not anime:
        return jsonify({"error": "Anime not found."}), 404

    page = request.args.get("page", 1, type=int)
    per_page = min(request.args.get("per_page", 20, type=int), 100)

    paginated = (
        Rating.query
        .filter_by(anime_id=anime_id)
        .order_by(Rating.updated_at.desc())
        .paginate(page=page, per_page=per_page, error_out=False)
    )

    ratings = []
    for r in paginated.items:
        rd = r.to_dict()
        rd["username"] = r.user.username
        ratings.append(rd)

    return jsonify({
        "ratings": ratings,
        "total": paginated.total,
        "page": paginated.page,
        "pages": paginated.pages,
        "community_score": anime.get_community_score(),
        "rating_count": anime.get_rating_count(),
    }), 200


@anime_bp.route("/genres", methods=["GET"])
def list_genres():
    """All available genres, grouped by category."""
    genres = Genre.query.order_by(Genre.category, Genre.name).all()
    grouped = {}
    for g in genres:
        grouped.setdefault(g.category, []).append(g.to_dict())
    return jsonify({"genres": grouped, "all": [g.to_dict() for g in genres]}), 200


@anime_bp.route("/top", methods=["GET"])
def top_anime():
    """Top-rated anime by community score."""
    limit = min(request.args.get("limit", 10, type=int), 50)

    subq = (
        db.session.query(
            Rating.anime_id,
            func.avg(Rating.score).label("avg_score"),
            func.count(Rating.id).label("num_ratings"),
        )
        .group_by(Rating.anime_id)
        .having(func.count(Rating.id) >= 1)
        .subquery()
    )

    results = (
        db.session.query(Anime, subq.c.avg_score, subq.c.num_ratings)
        .join(subq, Anime.id == subq.c.anime_id)
        .order_by(subq.c.avg_score.desc())
        .limit(limit)
        .all()
    )

    top = []
    for anime, avg_score, num_ratings in results:
        d = anime.to_dict(include_community=False)
        d["community_score"] = round(float(avg_score), 1)
        d["rating_count"] = num_ratings
        top.append(d)

    return jsonify({"top_anime": top}), 200
