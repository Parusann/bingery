"""Stats dashboard routes."""
from collections import Counter

from flask import Blueprint, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from sqlalchemy import func

from models import db, Anime, Rating, FanGenreVote, WatchlistEntry


stats_bp = Blueprint("stats", __name__)


DEFAULT_EPISODE_MINUTES = 24
COMPLETION_WEIGHTS = {
    "completed": 1.0,
    "watching": 0.5,
    "on_hold": 0.5,
    "dropped": 0.25,
    "plan_to_watch": 0.0,
}


@stats_bp.route("", methods=["GET"])
@jwt_required()
def dashboard():
    user_id = int(get_jwt_identity())

    ratings = (
        db.session.query(Rating, Anime)
        .join(Anime, Anime.id == Rating.anime_id)
        .filter(Rating.user_id == user_id)
        .all()
    )
    total_rated = len(ratings)
    avg_score = (
        round(sum(r.score for r, _ in ratings) / total_rated, 2)
        if total_rated else 0.0
    )

    total_genre_votes = FanGenreVote.query.filter_by(user_id=user_id).count()

    # Year distribution
    year_counter: Counter[int] = Counter()
    for _, anime in ratings:
        if anime.year:
            year_counter[int(anime.year)] += 1
    year_distribution = [
        {"year": y, "count": c} for y, c in sorted(year_counter.items())
    ]

    # Score distribution
    score_counter: Counter[int] = Counter(r.score for r, _ in ratings)
    score_distribution = [
        {"score": s, "count": score_counter.get(s, 0)} for s in range(1, 11)
    ]

    # Top studios
    studio_counter: Counter[str] = Counter()
    for _, anime in ratings:
        if anime.studio:
            studio_counter[anime.studio] += 1
    top_studios = [
        {"studio": name, "count": c}
        for name, c in studio_counter.most_common(10)
    ]

    # Top fan genres
    fan_rows = (
        db.session.query(FanGenreVote.genre_tag, func.count(FanGenreVote.id))
        .filter(FanGenreVote.user_id == user_id)
        .group_by(FanGenreVote.genre_tag)
        .order_by(func.count(FanGenreVote.id).desc())
        .limit(15)
        .all()
    )
    top_fan_tags = [{"name": n, "count": c} for n, c in fan_rows]

    # Hours watched estimate
    watchlist = {
        w.anime_id: w.status for w in
        WatchlistEntry.query.filter_by(user_id=user_id).all()
    }
    total_minutes = 0.0
    for _, anime in ratings:
        status = watchlist.get(anime.id, "completed")
        weight = COMPLETION_WEIGHTS.get(status, 1.0)
        eps = anime.episodes or 0
        total_minutes += eps * DEFAULT_EPISODE_MINUTES * weight
    hours = round(total_minutes / 60.0, 1)

    return jsonify({
        "totals": {
            "rated": total_rated,
            "genre_votes": total_genre_votes,
            "average_score": avg_score,
        },
        "year_distribution": year_distribution,
        "score_distribution": score_distribution,
        "top_studios": top_studios,
        "top_fan_tags": top_fan_tags,
        "estimated_hours_watched": hours,
    })
