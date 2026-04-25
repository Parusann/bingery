"""
Bingery Recommendation Engine.

Generates personalized anime recommendations based on:
- User's ratings and fan genre votes (taste profile)
- Similar users' preferences (collaborative filtering)
- Genre/tag affinity scoring
"""

from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from sqlalchemy import func, desc
from models import db, Anime, Rating, FanGenreVote, Genre, anime_genres, User

recommend_bp = Blueprint("recommend", __name__, url_prefix="/api/recommend")


def build_taste_profile(user_id):
    """
    Build a user's taste profile from their ratings and fan genre votes.
    Returns: {
        "top_genres": [("Action", 4.2), ("Mystery", 3.8), ...],
        "avg_score": 7.8,
        "total_rated": 12,
        "preferred_years": (2015, 2024),
        "genre_scores": {"Action": 4.2, ...},
        "rated_ids": [1, 2, 3, ...]
    }
    """
    ratings = db.session.query(Rating).filter_by(user_id=user_id).all()
    if not ratings:
        return None

    rated_ids = [r.anime_id for r in ratings]
    scores = {r.anime_id: r.score for r in ratings}
    avg_score = sum(scores.values()) / len(scores)

    # Genre affinity: for each genre the user voted on, weight by score
    genre_weights = {}
    genre_counts = {}
    votes = db.session.query(FanGenreVote).filter_by(user_id=user_id).all()
    for v in votes:
        score = scores.get(v.anime_id, avg_score)
        genre_weights[v.genre_tag] = genre_weights.get(v.genre_tag, 0) + score
        genre_counts[v.genre_tag] = genre_counts.get(v.genre_tag, 0) + 1

    # Also factor in official genres of highly rated anime
    for r in ratings:
        if r.score >= 7:
            anime = db.session.get(Anime, r.anime_id)
            if anime:
                for g in anime.official_genres:
                    weight = r.score * 0.5  # lower weight than explicit votes
                    genre_weights[g.name] = genre_weights.get(g.name, 0) + weight
                    genre_counts[g.name] = genre_counts.get(g.name, 0) + 1

    # Normalize: average score per genre
    genre_scores = {}
    for g in genre_weights:
        genre_scores[g] = round(genre_weights[g] / genre_counts[g], 2)

    top_genres = sorted(genre_scores.items(), key=lambda x: x[1], reverse=True)

    # Year preference
    years = []
    for r in ratings:
        anime = db.session.get(Anime, r.anime_id)
        if anime and anime.year:
            years.append(anime.year)
    preferred_years = (min(years), max(years)) if years else (2000, 2025)

    return {
        "top_genres": top_genres[:15],
        "avg_score": round(avg_score, 1),
        "total_rated": len(ratings),
        "preferred_years": preferred_years,
        "genre_scores": genre_scores,
        "rated_ids": rated_ids,
    }


def score_anime_for_user(anime, taste_profile):
    """Score an anime's relevance to a user's taste (0-100)."""
    if not taste_profile:
        return anime.api_score * 10 if anime.api_score else 50

    score = 0
    genre_scores = taste_profile["genre_scores"]

    # Genre match (up to 50 points)
    genre_matches = 0
    genre_value = 0
    for g in anime.official_genres:
        if g.name in genre_scores:
            genre_matches += 1
            genre_value += genre_scores[g.name]
    if genre_matches > 0:
        score += min(50, (genre_value / genre_matches) * 5)

    # Community/API score bonus (up to 25 points)
    community = anime.get_community_score()
    api = anime.api_score or 0
    best_score = max(community or 0, api)
    score += best_score * 2.5

    # Fan genre overlap — bonus if the community tagged it with user's fav genres
    fan_genres = anime.get_fan_genres()
    fan_genre_names = {fg["genre"] for fg in fan_genres}
    top_user_genres = {g[0] for g in taste_profile["top_genres"][:5]}
    overlap = fan_genre_names & top_user_genres
    score += len(overlap) * 3

    # Year recency bonus (slight)
    if anime.year and anime.year >= 2018:
        score += 2

    return min(100, round(score, 1))


@recommend_bp.route("/for-me", methods=["GET"])
@jwt_required()
def get_recommendations():
    """
    GET /api/recommend/for-me?limit=20
    Personalized recommendations based on taste profile.
    """
    user_id = int(get_jwt_identity())
    limit = min(request.args.get("limit", 20, type=int), 50)

    profile = build_taste_profile(user_id)
    if not profile:
        # New user — return popular anime
        popular = (
            Anime.query
            .filter(Anime.api_score.isnot(None))
            .order_by(Anime.api_score.desc())
            .limit(limit)
            .all()
        )
        return jsonify({
            "recommendations": [a.to_dict() for a in popular],
            "taste_profile": None,
            "reason": "popular",
        }), 200

    # Get all anime the user hasn't rated
    rated_ids = set(profile["rated_ids"])
    candidates = db.session.query(Anime).filter(~Anime.id.in_(rated_ids)).all()

    # Score each candidate
    scored = []
    for anime in candidates:
        s = score_anime_for_user(anime, profile)
        scored.append((anime, s))

    scored.sort(key=lambda x: x[1], reverse=True)
    top = scored[:limit]

    recs = []
    for anime, relevance in top:
        d = anime.to_dict(include_community=True)
        d["relevance_score"] = relevance
        recs.append(d)

    return jsonify({
        "recommendations": recs,
        "taste_profile": {
            "top_genres": profile["top_genres"][:8],
            "avg_score": profile["avg_score"],
            "total_rated": profile["total_rated"],
        },
        "reason": "personalized",
    }), 200


@recommend_bp.route("/taste-profile", methods=["GET"])
@jwt_required()
def get_taste_profile():
    """Full taste profile for the current user."""
    user_id = int(get_jwt_identity())
    profile = build_taste_profile(user_id)
    if not profile:
        return jsonify({"profile": None}), 200
    return jsonify({"profile": profile}), 200


@recommend_bp.route("/similar/<int:anime_id>", methods=["GET"])
def get_similar_anime(anime_id):
    """
    GET /api/recommend/similar/3?limit=8
    Find anime similar to a given anime (by genre overlap).
    """
    anime = db.session.get(Anime, anime_id)
    if not anime:
        return jsonify({"error": "Anime not found."}), 404

    limit = min(request.args.get("limit", 8, type=int), 20)
    genre_names = {g.name for g in anime.official_genres}
    fan_genres = {fg["genre"] for fg in anime.get_fan_genres()[:5]}
    all_tags = genre_names | fan_genres

    candidates = db.session.query(Anime).filter(Anime.id != anime_id).all()
    scored = []
    for c in candidates:
        c_genres = {g.name for g in c.official_genres}
        c_fan = {fg["genre"] for fg in c.get_fan_genres()[:5]}
        c_tags = c_genres | c_fan
        overlap = len(all_tags & c_tags)
        if overlap > 0:
            score = overlap * 10 + (c.api_score or 0)
            scored.append((c, score))

    scored.sort(key=lambda x: x[1], reverse=True)

    return jsonify({
        "similar": [s[0].to_dict() for s in scored[:limit]],
        "based_on": anime.to_dict(include_community=False),
    }), 200


@recommend_bp.route("/onboarding", methods=["GET"])
def get_onboarding_anime():
    """
    GET /api/recommend/onboarding
    Returns a curated set of diverse popular anime for new users to rate
    during onboarding, spanning different genres.
    """
    # Pick top-rated from each major genre
    target_genres = ["Action", "Comedy", "Drama", "Fantasy", "Horror",
                     "Mystery", "Romance", "Sci-Fi", "Slice of Life", "Thriller"]
    picks = []
    seen_ids = set()

    for genre_name in target_genres:
        anime = (
            Anime.query
            .join(anime_genres).join(Genre)
            .filter(Genre.name == genre_name)
            .filter(Anime.api_score.isnot(None))
            .filter(~Anime.id.in_(seen_ids))
            .order_by(Anime.api_score.desc())
            .first()
        )
        if anime:
            picks.append(anime.to_dict(include_community=False))
            seen_ids.add(anime.id)

    return jsonify({"anime": picks}), 200
