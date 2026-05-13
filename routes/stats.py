"""Stats dashboard routes."""
from collections import Counter
from datetime import date, datetime, timedelta, timezone

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

    total_genre_votes = (
        db.session.query(FanGenreVote)
        .filter_by(user_id=user_id)
        .count()
    )

    # Year distribution
    year_counter: Counter[int] = Counter()
    for _, anime in ratings:
        if anime.year:
            year_counter[anime.year] += 1
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

    # Hours watched estimate — derived from the watchlist, not ratings.
    # A rating doesn't imply viewing; watchlist status does.
    # For `watching` with a tracked episode count, use that directly;
    # otherwise weight total episodes by completion fraction.
    entries = (
        db.session.query(WatchlistEntry, Anime)
        .join(Anime, Anime.id == WatchlistEntry.anime_id)
        .filter(WatchlistEntry.user_id == user_id)
        .all()
    )
    total_minutes = 0.0
    for w, anime in entries:
        eps_total = anime.episodes or 0
        if w.status == "watching" and (w.episodes_watched or 0) > 0:
            minutes = w.episodes_watched * DEFAULT_EPISODE_MINUTES
        else:
            weight = COMPLETION_WEIGHTS.get(w.status, 0.0)
            minutes = eps_total * DEFAULT_EPISODE_MINUTES * weight
        total_minutes += minutes
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


@stats_bp.route("/genres", methods=["GET"])
@jwt_required()
def genres_breakdown():
    user_id = int(get_jwt_identity())
    # Unrated votes contribute 0 to the average (instead of being skipped),
    # so weighted_score = avg * count is not inflated when the user has
    # voted on anime they have not rated.
    rows = (
        db.session.query(
            FanGenreVote.genre_tag,
            func.count(FanGenreVote.id),
            func.coalesce(func.avg(func.coalesce(Rating.score, 0)), 0),
        )
        .outerjoin(
            Rating,
            (Rating.user_id == FanGenreVote.user_id)
            & (Rating.anime_id == FanGenreVote.anime_id),
        )
        .filter(FanGenreVote.user_id == user_id)
        .group_by(FanGenreVote.genre_tag)
        .all()
    )
    genres = [
        {
            "name": name,
            "count": int(count),
            "weighted_score": round(float(avg) * int(count), 2),
            "avg_score": round(float(avg), 2),
        }
        for name, count, avg in rows
    ]
    # Sort by weighted_score descending; tiebreak on name ascending for determinism.
    genres.sort(key=lambda g: (-g["weighted_score"], g["name"]))
    return jsonify({"genres": genres})


@stats_bp.route("/timeline", methods=["GET"])
@jwt_required()
def timeline():
    user_id = int(get_jwt_identity())
    rows = (
        db.session.query(Anime.year, func.count(Rating.id), func.avg(Rating.score))
        .join(Rating, Rating.anime_id == Anime.id)
        .filter(Rating.user_id == user_id, Anime.year.isnot(None))
        .group_by(Anime.year)
        .order_by(Anime.year)
        .all()
    )
    out = [
        {"year": int(year), "count": int(count), "average_score": round(float(avg), 2)}
        for year, count, avg in rows
    ]
    return jsonify({"timeline": out})


def _to_utc_date(value):
    """Return the UTC calendar date for a datetime. Naive datetimes are
    treated as UTC (DB columns use ``datetime.now(timezone.utc)``)."""
    if value is None:
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.date()
        return value.astimezone(timezone.utc).date()
    return value


def _activity_dates_for_user(user_id):
    """Return a Counter[date -> int] of per-day activity events for a user.

    "Activity" is any Rating.created_at, FanGenreVote.created_at, or
    WatchlistEntry.updated_at, bucketed by UTC date.
    """
    counter: Counter = Counter()

    rating_times = (
        db.session.query(Rating.created_at)
        .filter(Rating.user_id == user_id)
        .all()
    )
    for (ts,) in rating_times:
        d = _to_utc_date(ts)
        if d is not None:
            counter[d] += 1

    vote_times = (
        db.session.query(FanGenreVote.created_at)
        .filter(FanGenreVote.user_id == user_id)
        .all()
    )
    for (ts,) in vote_times:
        d = _to_utc_date(ts)
        if d is not None:
            counter[d] += 1

    entry_times = (
        db.session.query(WatchlistEntry.updated_at)
        .filter(WatchlistEntry.user_id == user_id)
        .all()
    )
    for (ts,) in entry_times:
        d = _to_utc_date(ts)
        if d is not None:
            counter[d] += 1

    return counter


@stats_bp.route("/overview", methods=["GET"])
@jwt_required()
def overview():
    user_id = int(get_jwt_identity())

    # Totals: rated, watched, favorites
    total_rated = (
        db.session.query(func.count(Rating.id))
        .filter(Rating.user_id == user_id)
        .scalar()
    ) or 0

    total_watched = (
        db.session.query(func.count(WatchlistEntry.id))
        .filter(
            WatchlistEntry.user_id == user_id,
            WatchlistEntry.status.in_(("completed", "watching")),
        )
        .scalar()
    ) or 0

    favorite_count = (
        db.session.query(func.count(WatchlistEntry.id))
        .filter(
            WatchlistEntry.user_id == user_id,
            WatchlistEntry.is_favorite.is_(True),
        )
        .scalar()
    ) or 0

    # Average rating (null when no ratings)
    avg_raw = (
        db.session.query(func.avg(Rating.score))
        .filter(Rating.user_id == user_id)
        .scalar()
    )
    avg_rating = round(float(avg_raw), 2) if avg_raw is not None else None

    # Hours watched — same formula as /stats dashboard
    entries = (
        db.session.query(WatchlistEntry, Anime)
        .join(Anime, Anime.id == WatchlistEntry.anime_id)
        .filter(WatchlistEntry.user_id == user_id)
        .all()
    )
    total_minutes = 0.0
    for w, anime in entries:
        eps_total = anime.episodes or 0
        if w.status == "watching" and (w.episodes_watched or 0) > 0:
            minutes = w.episodes_watched * DEFAULT_EPISODE_MINUTES
        else:
            weight = COMPLETION_WEIGHTS.get(w.status, 0.0)
            minutes = eps_total * DEFAULT_EPISODE_MINUTES * weight
        total_minutes += minutes
    hours_watched = round(total_minutes / 60.0, 1)

    # Rating distribution: always 10 buckets, score 1..10
    score_rows = (
        db.session.query(Rating.score, func.count(Rating.id))
        .filter(Rating.user_id == user_id)
        .group_by(Rating.score)
        .all()
    )
    score_counter = {int(s): int(c) for s, c in score_rows}
    rating_distribution = [
        {"score": s, "count": score_counter.get(s, 0)} for s in range(1, 11)
    ]

    # Top genres: from FanGenreVote, up to 8, sorted by count desc, tie-break by genre asc
    genre_rows = (
        db.session.query(FanGenreVote.genre_tag, func.count(FanGenreVote.id))
        .filter(FanGenreVote.user_id == user_id)
        .group_by(FanGenreVote.genre_tag)
        .all()
    )
    genre_pairs = [(name, int(count)) for name, count in genre_rows]
    genre_pairs.sort(key=lambda x: (-x[1], x[0]))
    top_genres = [{"genre": name, "count": count} for name, count in genre_pairs[:8]]
    top_genre = top_genres[0]["genre"] if top_genres else None

    # Streak: consecutive days of activity ending today (UTC)
    activity = _activity_dates_for_user(user_id)
    today = datetime.now(timezone.utc).date()
    streak_days = 0
    cursor = today
    while activity.get(cursor, 0) > 0:
        streak_days += 1
        cursor = cursor - timedelta(days=1)

    return jsonify({
        "overview": {
            "total_rated": int(total_rated),
            "total_watched": int(total_watched),
            "hours_watched": hours_watched,
            "favorite_count": int(favorite_count),
            "avg_rating": avg_rating,
            "top_genre": top_genre,
            "streak_days": streak_days,
        },
        "rating_distribution": rating_distribution,
        "top_genres": top_genres,
    })


@stats_bp.route("/heatmap", methods=["GET"])
@jwt_required()
def heatmap():
    user_id = int(get_jwt_identity())

    today = datetime.now(timezone.utc).date()
    window_start = today - timedelta(days=364)  # 365-day inclusive window

    activity = _activity_dates_for_user(user_id)
    in_window = {
        d: c for d, c in activity.items() if window_start <= d <= today and c > 0
    }

    cells = [
        {"date": d.isoformat(), "count": c}
        for d, c in sorted(in_window.items(), key=lambda kv: kv[0])
    ]
    max_count = max(in_window.values()) if in_window else 0

    return jsonify({
        "heatmap": {
            "cells": cells,
            "max": int(max_count),
        }
    })
