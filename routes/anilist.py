import hmac
import os

from flask import Blueprint, request, jsonify, current_app

anilist_bp = Blueprint("anilist", __name__, url_prefix="/api/anilist")


def _require_admin_secret():
    """Catalog mutation is admin-only: header X-Admin-Secret must match
    ADMIN_SYNC_SECRET (same scheme as routes/admin.py). Returns an error
    response tuple, or None when authorized."""
    expected = os.environ.get("ADMIN_SYNC_SECRET")
    if not expected:
        return jsonify({"error": "Sync is not enabled on this server."}), 503
    provided = request.headers.get("X-Admin-Secret") or ""
    if not hmac.compare_digest(provided, expected):
        return jsonify({"error": "Unauthorized."}), 401
    return None


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
    except Exception:
        current_app.logger.exception("AniList search failed")
        return jsonify({"error": "AniList search failed."}), 502


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
    except Exception:
        current_app.logger.exception("AniList fetch failed")
        return jsonify({"error": "AniList fetch failed."}), 502


@anilist_bp.route("/sync", methods=["POST"])
def sync_from_anilist():
    """
    Sync anime from AniList to the local database. Admin-only: requires
    the X-Admin-Secret header (it mutates the shared catalog and burns
    AniList rate budget).
    POST /api/anilist/sync
    Body: { "mode": "popular", "pages": 2 }
    Body: { "mode": "search", "query": "isekai", "pages": 1 }
    Body: { "mode": "seasonal", "season": "WINTER", "year": 2025, "pages": 1 }

    Modes: popular, top, trending, seasonal, search
    """
    from utils.anilist import sync_anime_from_anilist

    denied = _require_admin_secret()
    if denied is not None:
        return denied

    data = request.get_json(silent=True) or {}
    mode = data.get("mode", "popular")

    if mode not in ("popular", "top", "trending", "seasonal", "search"):
        return jsonify({"error": "Invalid mode."}), 400
    try:
        pages = int(data.get("pages", 1))
    except (TypeError, ValueError):
        return jsonify({"error": "'pages' must be an integer."}), 400
    pages = max(1, min(pages, 10))  # cap at 10 pages
    if mode == "seasonal" and (not data.get("season") or not data.get("year")):
        return jsonify({"error": "'season' and 'year' are required for seasonal mode."}), 400

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
    except Exception:
        current_app.logger.exception("AniList sync failed")
        return jsonify({"error": "Sync failed."}), 502


@anilist_bp.route("/trending", methods=["GET"])
def get_trending():
    """Get currently trending anime from AniList."""
    from utils.anilist import AniListClient

    per_page = max(1, min(request.args.get("per_page", 20, type=int) or 20, 50))
    try:
        client = AniListClient()
        result = client.get_trending(page=1, per_page=per_page)
        return jsonify({"results": result["results"]}), 200
    except Exception:
        current_app.logger.exception("AniList trending fetch failed")
        return jsonify({"error": "AniList fetch failed."}), 502


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

    per_page = max(1, min(request.args.get("per_page", 30, type=int) or 30, 50))
    try:
        client = AniListClient()
        result = client.get_seasonal(year, season, page=1, per_page=per_page)
        return jsonify({"results": result["results"]}), 200
    except Exception:
        current_app.logger.exception("AniList seasonal fetch failed")
        return jsonify({"error": "AniList fetch failed."}), 502
