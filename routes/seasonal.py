"""Seasonal calendar routes."""
from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity

from models import db, Anime, WatchlistEntry


seasonal_bp = Blueprint("seasonal", __name__)

VALID_SEASONS = {"WINTER", "SPRING", "SUMMER", "FALL"}
AIRING_STATUSES = {"RELEASING", "CURRENTLY_AIRING"}


def _with_status_overlay(user_id: int, anime_list):
    owned = {
        w.anime_id: w for w in
        db.session.query(WatchlistEntry).filter(
            WatchlistEntry.user_id == user_id,
            WatchlistEntry.anime_id.in_([a.id for a in anime_list]),
        ).all()
    }
    out = []
    for a in anime_list:
        d = a.to_dict(include_community=False)
        w = owned.get(a.id)
        d["user_status"] = w.status if w else None
        d["is_favorite"] = bool(w and w.is_favorite)
        out.append(d)
    return out


@seasonal_bp.route("", methods=["GET"])
@jwt_required()
def seasonal():
    user_id = int(get_jwt_identity())
    season = (request.args.get("season") or "").upper()
    year_raw = request.args.get("year")
    if season not in VALID_SEASONS:
        return jsonify({"error": f"season must be one of {sorted(VALID_SEASONS)}"}), 400
    try:
        year = int(year_raw) if year_raw else None
    except ValueError:
        return jsonify({"error": "year must be an integer"}), 400
    if year is None:
        return jsonify({"error": "year is required"}), 400

    rows = (
        db.session.query(Anime)
        .filter_by(season=season, year=year)
        .order_by(Anime.title)
        .all()
    )
    return jsonify({"anime": _with_status_overlay(user_id, rows)})


@seasonal_bp.route("/airing-now", methods=["GET"])
@jwt_required()
def airing_now():
    user_id = int(get_jwt_identity())
    rows = (
        db.session.query(Anime)
        .filter(Anime.status.in_(AIRING_STATUSES))
        .order_by(Anime.title)
        .all()
    )
    return jsonify({"anime": _with_status_overlay(user_id, rows)})
