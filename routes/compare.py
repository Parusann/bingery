"""Compare two anime side-by-side, or two users' taste."""
from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity
from sqlalchemy import func

from models import db, Anime, Rating, FanGenreVote, User


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


# ─── Compare two users' taste ───────────────────────────────────────────────


def _user_summary(user: User):
    """Compact user reference for the compare-users response."""
    return {
        "id": user.id,
        "username": user.username,
        # User model has no `display_name` column today — return null so the
        # frontend contract is stable if/when it's added.
        "display_name": getattr(user, "display_name", None),
    }


def _genre_vote_counts(user_id: int):
    """Map of {genre_tag: votes_count} for a single user across all anime."""
    rows = (
        db.session.query(
            FanGenreVote.genre_tag,
            func.count(FanGenreVote.id).label("c"),
        )
        .filter(FanGenreVote.user_id == user_id)
        .group_by(FanGenreVote.genre_tag)
        .all()
    )
    return {row.genre_tag: int(row.c) for row in rows}


def _slice_sorted_top(items: dict, limit: int = 8):
    """Return [{"genre": g, "count": n}, ...] sorted desc by count, alpha tiebreak."""
    pairs = sorted(items.items(), key=lambda kv: (-kv[1], kv[0]))
    return [{"genre": g, "count": n} for g, n in pairs[:limit]]


@compare_bp.route("/users", methods=["GET"])
@jwt_required()
def compare_users():
    """Compare two users' taste (genre overlap + shared anime + score agreement).

    GET /api/compare/users?user_a=<username>&user_b=<username>
    -> 200 {"user_a": {...}, "user_b": {...}, "taste": {...}}
    -> 400 if `user_a` or `user_b` is missing.
    -> 404 if either user does not exist.

    Auth: any logged-in user. Caller does not need to be a or b.
    Self-compare (a == b) is allowed: shared sets are full, agreement is 1.0.
    """
    username_a = (request.args.get("user_a") or "").strip()
    username_b = (request.args.get("user_b") or "").strip()
    if not username_a or not username_b:
        return jsonify({"error": "both user_a and user_b are required"}), 400

    user_a = db.session.query(User).filter_by(username=username_a).first()
    user_b = db.session.query(User).filter_by(username=username_b).first()
    if user_a is None or user_b is None:
        return jsonify({"error": "user not found"}), 404

    # ── Genre slices ─────────────────────────────────────────────────────
    votes_a = _genre_vote_counts(user_a.id)
    votes_b = _genre_vote_counts(user_b.id)

    if user_a.id == user_b.id:
        # Self-compare: every genre is shared (count doubled — same vote on
        # both sides — matches the general "shared = a+b" rule), and there
        # are no "only A" / "only B" rows.
        shared_genres_map = {g: votes_a[g] * 2 for g in votes_a}
        only_a_map: dict = {}
        only_b_map: dict = {}
    else:
        shared_keys = set(votes_a) & set(votes_b)
        shared_genres_map = {g: votes_a[g] + votes_b[g] for g in shared_keys}
        only_a_map = {g: c for g, c in votes_a.items() if g not in votes_b}
        only_b_map = {g: c for g, c in votes_b.items() if g not in votes_a}

    shared_genres = _slice_sorted_top(shared_genres_map)
    only_a_genres = _slice_sorted_top(only_a_map)
    only_b_genres = _slice_sorted_top(only_b_map)

    # ── Shared rated anime + score agreement ─────────────────────────────
    ratings_a = (
        db.session.query(Rating).filter_by(user_id=user_a.id).all()
    )
    a_by_anime = {r.anime_id: r for r in ratings_a}

    if user_a.id == user_b.id:
        shared_pairs = [(r, r) for r in ratings_a]
    else:
        ratings_b = (
            db.session.query(Rating)
            .filter(
                Rating.user_id == user_b.id,
                Rating.anime_id.in_(list(a_by_anime.keys())) if a_by_anime else False,
            )
            .all()
        ) if a_by_anime else []
        shared_pairs = [
            (a_by_anime[rb.anime_id], rb) for rb in ratings_b
        ]

    if not shared_pairs:
        score_agreement = 0.0 if user_a.id != user_b.id else 1.0
    else:
        diffs = [abs(ra.score - rb.score) for ra, rb in shared_pairs]
        mean_diff = sum(diffs) / len(diffs)
        score_agreement = 1.0 - (mean_diff / 9.0)
    score_agreement = round(max(0.0, min(1.0, score_agreement)), 2)

    # Pick shared anime ordered by most recent updated_at across the pair,
    # capped at 24.
    if shared_pairs:
        pair_keys = []
        for ra, rb in shared_pairs:
            most_recent = ra.updated_at if ra.updated_at >= rb.updated_at else rb.updated_at
            pair_keys.append((ra.anime_id, most_recent))
        pair_keys.sort(key=lambda t: t[1], reverse=True)
        top_ids = [aid for aid, _ in pair_keys[:24]]
        anime_rows = (
            db.session.query(Anime).filter(Anime.id.in_(top_ids)).all()
        )
        by_id = {a.id: a for a in anime_rows}
        shared_anime = [
            by_id[aid].to_dict(include_community=False)
            for aid in top_ids
            if aid in by_id
        ]
    else:
        shared_anime = []

    return jsonify({
        "user_a": _user_summary(user_a),
        "user_b": _user_summary(user_b),
        "taste": {
            "shared_genres": shared_genres,
            "only_a_genres": only_a_genres,
            "only_b_genres": only_b_genres,
            "shared_anime": shared_anime,
            "score_agreement": score_agreement,
        },
    })
