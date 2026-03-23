from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required

anilist_bp = Blueprint("anilist", __name__, url_prefix="/api/anilist")


@anilist_bp.route("/search", methods=["GET"])
def search_anilist():
    """
    Search AniList for anime (without saving to DB).
    GET /api/anilist/search?q=frieren&page=1&per_page=10

    Use this for the AI-assisted logging feature — user types a title,
    we search AniList, they pick one, we auto-fill the details.
    """
    from utils.anilist import AniListClient

    query = request.args.get("q", "").strip()
    if not query:
        return jsonify({"error": "Query parameter 'q' is required."}), 400

    page = request.args.get("page", 1, type=int)
    per_page = min(request.args.get("per_page", 10, type=int), 25)

    try:
        client = AniListClient()
        result = client.search_anime(query, page=page, per_page=per_page)
        return jsonify({
            "results": result["results"],
            "page_info": result["page_info"],
        }), 200
    except Exception as e:
        return jsonify({"error": f"AniList search failed: {str(e)}"}), 502


@anilist_bp.route("/anime/<int:anilist_id>", methods=["GET"])
def get_anilist_anime(anilist_id):
    """
    Get full details for a single anime from AniList.
    GET /api/anilist/anime/154587
    """
    from utils.anilist import AniListClient

    try:
        client = AniListClient()
        anime = client.get_anime(anilist_id)
        return jsonify({"anime": anime}), 200
    except Exception as e:
        return jsonify({"error": f"AniList fetch failed: {str(e)}"}), 502


@anilist_bp.route("/sync", methods=["POST"])
@jwt_required()
def sync_from_anilist():
    """
    Sync anime from AniList to the local database.
    POST /api/anilist/sync
    Body: { "mode": "popular", "pages": 2 }
    Body: { "mode": "search", "query": "isekai", "pages": 1 }
    Body: { "mode": "seasonal", "season": "WINTER", "year": 2025, "pages": 1 }

    Modes: popular, top, trending, seasonal, search
    """
    from utils.anilist import sync_anime_from_anilist

    data = request.get_json() or {}
    mode = data.get("mode", "popular")
    pages = min(data.get("pages", 1), 10)  # cap at 10 pages

    if mode not in ("popular", "top", "trending", "seasonal", "search"):
        return jsonify({"error": "Invalid mode."}), 400

    try:
        total = sync_anime_from_anilist(
            current_app._get_current_object(),
            mode=mode,
            query=data.get("query", ""),
            pages=pages,
            season=data.get("season"),
            season_year=data.get("year"),
        )
        return jsonify({"synced": total, "mode": mode}), 200
    except Exception as e:
        return jsonify({"error": f"Sync failed: {str(e)}"}), 502


@anilist_bp.route("/trending", methods=["GET"])
def get_trending():
    """Get currently trending anime from AniList."""
    from utils.anilist import AniListClient

    per_page = min(request.args.get("per_page", 20, type=int), 50)
    try:
        client = AniListClient()
        result = client.get_trending(page=1, per_page=per_page)
        return jsonify({"results": result["results"]}), 200
    except Exception as e:
        return jsonify({"error": f"AniList fetch failed: {str(e)}"}), 502


@anilist_bp.route("/seasonal", methods=["GET"])
def get_seasonal():
    """
    Get anime for a specific season.
    GET /api/anilist/seasonal?year=2025&season=WINTER
    """
    from utils.anilist import AniListClient

    year = request.args.get("year", type=int)
    season = request.args.get("season", "").upper()

    if not year or season not in ("WINTER", "SPRING", "SUMMER", "FALL"):
        return jsonify({"error": "year (int) and season (WINTER/SPRING/SUMMER/FALL) required."}), 400

    per_page = min(request.args.get("per_page", 30, type=int), 50)
    try:
        client = AniListClient()
        result = client.get_seasonal(year, season, page=1, per_page=per_page)
        return jsonify({"results": result["results"]}), 200
    except Exception as e:
        return jsonify({"error": f"AniList fetch failed: {str(e)}"}), 502
