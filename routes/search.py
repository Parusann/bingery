from flask import Blueprint, request, jsonify
from models import db, Anime, Genre, anime_genres

search_bp = Blueprint("search", __name__, url_prefix="/api/search")


@search_bp.route("/autocomplete", methods=["GET"])
def autocomplete():
    """
    GET /api/search/autocomplete?q=ste&limit=8
    Fast, lightweight autocomplete for the search bar.
    Returns minimal data: id, title, image, year, score.
    """
    q = request.args.get("q", "").strip()
    if len(q) < 2:
        return jsonify({"results": []}), 200

    limit = min(request.args.get("limit", 8, type=int), 20)

    results = (
        Anime.query
        .filter(db.or_(
            Anime.title.ilike(f"%{q}%"),
            Anime.title_english.ilike(f"%{q}%"),
        ))
        .order_by(
            # Prioritize exact prefix matches
            db.case(
                (Anime.title_english.ilike(f"{q}%"), 0),
                (Anime.title.ilike(f"{q}%"), 1),
                else_=2,
            ),
            Anime.api_score.desc().nullslast(),
        )
        .limit(limit)
        .all()
    )

    return jsonify({
        "results": [{
            "id": a.id,
            "title": a.title,
            "title_english": a.title_english,
            "image_url": a.image_url,
            "year": a.year,
            "api_score": a.api_score,
            "episodes": a.episodes,
            "genres": [g.name for g in a.official_genres[:3]],
        } for a in results]
    }), 200


@search_bp.route("/full", methods=["GET"])
def full_search():
    """
    GET /api/search/full?q=mystery&genres=Horror,Thriller&year_min=2015&min_score=7&sort=score&page=1
    Advanced search with multiple filters.
    """
    q = request.args.get("q", "").strip()
    genres_param = request.args.get("genres", "").strip()
    year_min = request.args.get("year_min", type=int)
    year_max = request.args.get("year_max", type=int)
    min_score = request.args.get("min_score", type=float)
    status = request.args.get("status", "").strip()
    sort = request.args.get("sort", "score")
    page = request.args.get("page", 1, type=int)
    per_page = min(request.args.get("per_page", 24, type=int), 100)

    query = Anime.query

    if q:
        query = query.filter(db.or_(
            Anime.title.ilike(f"%{q}%"),
            Anime.title_english.ilike(f"%{q}%"),
            Anime.synopsis.ilike(f"%{q}%"),
        ))

    if genres_param:
        genre_names = [g.strip() for g in genres_param.split(",") if g.strip()]
        if genre_names:
            query = query.join(anime_genres).join(Genre).filter(Genre.name.in_(genre_names))

    if year_min:
        query = query.filter(Anime.year >= year_min)
    if year_max:
        query = query.filter(Anime.year <= year_max)
    if min_score:
        query = query.filter(Anime.api_score >= min_score)
    if status:
        query = query.filter(Anime.status == status)

    # Sorting
    if sort == "year":
        query = query.order_by(Anime.year.desc().nullslast())
    elif sort == "title":
        query = query.order_by(Anime.title.asc())
    elif sort == "newest":
        query = query.order_by(Anime.year.desc().nullslast(), Anime.api_score.desc().nullslast())
    else:
        query = query.order_by(Anime.api_score.desc().nullslast())

    paginated = query.distinct().paginate(page=page, per_page=per_page, error_out=False)

    return jsonify({
        "results": [a.to_dict(include_community=True) for a in paginated.items],
        "total": paginated.total,
        "page": paginated.page,
        "pages": paginated.pages,
    }), 200
