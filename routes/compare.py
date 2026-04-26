"""Compare two anime side-by-side."""
from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity

from models import db, Anime, Rating, FanGenreVote


compare_bp = Blueprint("compare", __name__)


def _side_payload(user_id: int, anime: Anime):
    rating = (
        db.session.query(Rating)
        .filter_by(user_id=user_id, anime_id=anime.id)
        .first()
    )
    fan_votes = [
        v.genre_tag
        for v in db.session.query(FanGenreVote)
        .filter_by(user_id=user_id, anime_id=anime.id)
        .all()
    ]
    return {
        "anime": anime.to_dict(include_community=True),
        "user": {
            "score": rating.score if rating else None,
            "review": rating.review if rating else None,
            "fan_genres": fan_votes,
        },
    }


@compare_bp.route("", methods=["GET"])
@jwt_required()
def compare():
    """Compare two anime side-by-side with the caller's per-anime data.

    GET /api/compare?a=<anime_id>&b=<anime_id>
    -> 200 {"a": {...}, "b": {...}, "shared": {...}, "unique": {...}}
    -> 400 if `a` or `b` is missing or non-integer.
    -> 404 if either anime does not exist.
    """
    user_id = int(get_jwt_identity())
    try:
        a_id = int(request.args.get("a", ""))
        b_id = int(request.args.get("b", ""))
    except ValueError:
        return jsonify({"error": "both `a` and `b` are required and must be integers"}), 400

    a = db.session.get(Anime, a_id)
    b = db.session.get(Anime, b_id)
    if not a or not b:
        return jsonify({"error": "anime not found"}), 404

    left = _side_payload(user_id, a)
    right = _side_payload(user_id, b)

    official_a = {g["name"] for g in left["anime"]["official_genres"]}
    official_b = {g["name"] for g in right["anime"]["official_genres"]}

    shared = {
        "official_genres": sorted(official_a & official_b),
        "fan_genres": sorted(
            set(left["user"]["fan_genres"]) & set(right["user"]["fan_genres"])
        ),
        "studios": [a.studio]
        if a.studio == b.studio and a.studio is not None
        else [],
    }
    unique = {
        "a_only_official_genres": sorted(official_a - official_b),
        "b_only_official_genres": sorted(official_b - official_a),
    }

    return jsonify({"a": left, "b": right, "shared": shared, "unique": unique})
