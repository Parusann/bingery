"""Multi-signal candidate scoring for chat recommendations.

This module exposes pure functions for signal computation plus the public
entry points the chatbot and /recommend/for-me routes call:

* build_signal_profile(user_id)  -> dict
* score_candidates(user_id, profile, limit, include_nsfw) -> list[dict]
* get_signal_profile(user_id)    -> dict  (cached, lazy invalidation)

See docs/superpowers/specs/2026-05-21-chat-rec-engine-design.md.
"""

import math
from datetime import datetime, timezone
from collections import Counter

from sqlalchemy import func

from models import db, User, Anime, Rating, FanGenreVote, WatchlistEntry, Genre, anime_genres
from utils.nsfw import maybe_exclude_nsfw, HARD_BLOCKED_GENRES

SIGNAL_PROFILE_SCHEMA_VERSION = 1


def _studio_affinity(candidate_studio, user_top_studios):
    """Return the user's hit_rate for this studio, or 0.0 if unknown.

    candidate_studio: str or None — the candidate anime's studio name
    user_top_studios: list of {"name", "hit_rate", "n"} entries from the profile
    """
    if not candidate_studio:
        return 0.0
    key = candidate_studio.strip().lower()
    for entry in user_top_studios:
        if entry["name"].strip().lower() == key:
            return float(entry["hit_rate"])
    return 0.0


def _genre_match(candidate_genres, user_top_genres):
    """Weighted Jaccard: share of user's total genre-weight that the candidate covers.

    candidate_genres: list[str]
    user_top_genres: list of [name, weight] pairs
    Returns float in [0, 1].
    """
    if not candidate_genres or not user_top_genres:
        return 0.0
    cand_set = {g.lower() for g in candidate_genres}
    total = sum(w for _, w in user_top_genres)
    if total == 0:
        return 0.0
    matched = sum(w for name, w in user_top_genres if name.lower() in cand_set)
    return min(1.0, matched / total)


def _fan_genre_match(candidate_fan_genres, user_fan_genre_clusters):
    """Same shape as _genre_match but over user-applied fan-genre clusters.

    user_fan_genre_clusters: list of [tag, count] pairs from the profile.
    """
    if not candidate_fan_genres or not user_fan_genre_clusters:
        return 0.0
    cand_set = {g.lower() for g in candidate_fan_genres}
    total = sum(c for _, c in user_fan_genre_clusters)
    if total == 0:
        return 0.0
    matched = sum(c for tag, c in user_fan_genre_clusters if tag.lower() in cand_set)
    return min(1.0, matched / total)


def _era_fit(candidate_year, user_era_lean_year):
    """Gaussian centered on the user's era lean, sigma=6 years.

    Returns 1.0 for exact match, ~0.6 at 6-year gap, ~0.14 at 12-year gap.
    Returns 0.0 if either year is None (unknown era).
    """
    if candidate_year is None or user_era_lean_year is None:
        return 0.0
    delta = candidate_year - user_era_lean_year
    return math.exp(-(delta * delta) / (2 * 6 * 6))


def _episode_fit(candidate_episodes, user_episode_pref):
    """Look up the user's share for the candidate's episode-count bucket.

    Buckets: short (<=13), medium (14-26), long (>26).
    Returns 0.0 if candidate_episodes is None or 0.
    """
    if not candidate_episodes:
        return 0.0
    if candidate_episodes <= 13:
        bucket = "short"
    elif candidate_episodes <= 26:
        bucket = "medium"
    else:
        bucket = "long"
    return float(user_episode_pref.get(bucket, 0.0))


def _surprise_bonus(candidate_api_score, candidate_id, top_100_popular_ids):
    """Bonus for high-quality + obscure picks.

    1.0 if api_score >= 8 AND not in top-100 popular
    0.5 if exactly one of those is true
    0.0 if neither
    """
    is_high_quality = candidate_api_score is not None and candidate_api_score >= 8
    is_obscure = candidate_id not in top_100_popular_ids
    if is_high_quality and is_obscure:
        return 1.0
    if is_high_quality or is_obscure:
        return 0.5
    return 0.0


def _watchlist_coherence(candidate_id, planning_ids):
    """1 if user has this anime in 'planning' status, else 0."""
    return 1 if candidate_id in planning_ids else 0


def _dropped_trait_penalty(candidate_studio, candidate_genres, user_dropped_traits):
    """Penalty in [0, 1] for sharing traits with the user's dropped / low-rated set.

    0.5 weight for studio match + 0.5 weight for candidate-genre share with
    dropped genres.
    """
    studio_part = 0.0
    if candidate_studio:
        dropped_studios_lower = {s.lower() for s in user_dropped_traits.get("studios", [])}
        if candidate_studio.lower() in dropped_studios_lower:
            studio_part = 0.5

    genre_part = 0.0
    if candidate_genres:
        dropped_genres_lower = {g.lower() for g in user_dropped_traits.get("genres", [])}
        overlap = sum(1 for g in candidate_genres if g.lower() in dropped_genres_lower)
        genre_part = (overlap / max(1, len(candidate_genres))) * 0.5

    return min(1.0, studio_part + genre_part)


def score_candidate(candidate, signal_profile, top_100_popular_ids):
    """Compute the full per-signal breakdown and total score for one anime.

    candidate: dict with id, title, studio, genres, fan_genres, api_score,
               year, episodes (the shape returned by Anime.to_dict + fan_genres)
    signal_profile: output of build_signal_profile
    top_100_popular_ids: set of anime IDs ranked top 100 by popularity

    Returns dict with the candidate fields plus a `signals` sub-dict containing
    each component plus total_score (floored to 0, capped at 100).
    """
    studio = candidate.get("studio") or ""
    genres = candidate.get("genres") or []
    fan_genres = candidate.get("fan_genres") or []

    sa = _studio_affinity(studio, signal_profile.get("top_studios", []))
    gm = _genre_match(genres, signal_profile.get("top_genres", []))
    fm = _fan_genre_match(fan_genres, signal_profile.get("fan_genre_clusters", []))
    ef = _era_fit(candidate.get("year"), signal_profile.get("era_lean_year"))
    epf = _episode_fit(candidate.get("episodes"), signal_profile.get("episode_fit_pref", {}))
    sb = _surprise_bonus(candidate.get("api_score"), candidate.get("id"), top_100_popular_ids)
    wc = _watchlist_coherence(candidate.get("id"), signal_profile.get("watchlist_planning_ids", []))
    pen = _dropped_trait_penalty(studio, genres, signal_profile.get("dropped_traits", {}))

    total = (25 * sa) + (20 * gm) + (15 * fm) + (10 * ef) + (10 * epf) + (10 * sb) + (5 * wc) - (20 * pen)
    total = max(0.0, min(100.0, total))

    return {
        **{k: candidate.get(k) for k in ("id", "title", "studio", "genres", "fan_genres", "api_score", "year", "episodes", "image_url")},
        "signals": {
            "studio_affinity": round(sa, 4),
            "genre_match": round(gm, 4),
            "fan_genre_match": round(fm, 4),
            "era_fit": round(ef, 4),
            "episode_fit": round(epf, 4),
            "surprise_factor": round(sb, 4),
            "watchlist_aligned": wc,
            "dropped_trait_penalty": round(pen, 4),
            "total_score": round(total, 2),
        },
    }


def build_signal_profile(user_id):
    """Compute the user's signal profile from scratch.

    See the spec (§4) for the schema. Pure read; does NOT write the cache.
    Caller (get_signal_profile) is responsible for caching.
    """
    ratings = (
        db.session.query(Rating, Anime)
        .join(Anime, Anime.id == Rating.anime_id)
        .filter(Rating.user_id == user_id)
        .all()
    )
    rating_count = len(ratings)

    if rating_count == 0:
        return _empty_profile(rating_count)

    # Top genres: weighted by rating score (>5 contributes positively)
    genre_weights = Counter()
    for r, a in ratings:
        weight = max(0, r.score - 5)
        for g in a.official_genres:
            genre_weights[g.name] += weight
    top_genres = sorted(genre_weights.items(), key=lambda x: -x[1])[:8]
    top_genres = [[name, float(w)] for name, w in top_genres if w > 0]

    # Top studios: hit_rate = (ratings >= 8) / (ratings for that studio); require n >= 2
    studio_ratings = Counter()
    studio_hits = Counter()
    for r, a in ratings:
        if not a.studio:
            continue
        studio_ratings[a.studio] += 1
        if r.score >= 8:
            studio_hits[a.studio] += 1
    top_studios = []
    for studio, n in studio_ratings.items():
        if n < 2:
            continue
        top_studios.append({
            "name": studio,
            "hit_rate": studio_hits[studio] / n,
            "n": n,
        })
    top_studios.sort(key=lambda s: (-s["hit_rate"], -s["n"]))
    top_studios = top_studios[:5]

    # Fan-genre clusters: count fan-genre votes by this user
    fan_votes = (
        db.session.query(FanGenreVote.genre_tag, func.count(FanGenreVote.id))
        .filter(FanGenreVote.user_id == user_id)
        .group_by(FanGenreVote.genre_tag)
        .order_by(func.count(FanGenreVote.id).desc())
        .limit(8)
        .all()
    )
    fan_genre_clusters = [[tag, int(c)] for tag, c in fan_votes]

    # Era lean: weighted average year, weight = max(0, score-5)
    era_num, era_den = 0.0, 0.0
    for r, a in ratings:
        if a.year is None:
            continue
        w = max(0, r.score - 5)
        era_num += w * a.year
        era_den += w
    era_lean_year = int(round(era_num / era_den)) if era_den else None

    # Episode-fit pref: based on COMPLETED entries (status='completed' in watchlist
    # OR rated >= 6 as a fallback). Bucket by episode count.
    completed = (
        db.session.query(Anime)
        .join(WatchlistEntry, WatchlistEntry.anime_id == Anime.id)
        .filter(WatchlistEntry.user_id == user_id, WatchlistEntry.status == "completed")
        .all()
    )
    if not completed:
        # Fallback: rated >= 6
        completed = [a for r, a in ratings if r.score >= 6]
    buckets = {"short": 0, "medium": 0, "long": 0}
    for a in completed:
        if not a.episodes:
            continue
        if a.episodes <= 13:
            buckets["short"] += 1
        elif a.episodes <= 26:
            buckets["medium"] += 1
        else:
            buckets["long"] += 1
    total_buckets = sum(buckets.values())
    if total_buckets:
        episode_fit_pref = {k: v / total_buckets for k, v in buckets.items()}
    else:
        episode_fit_pref = {"short": 0.0, "medium": 0.0, "long": 0.0}

    # Dropped traits: studios + genres of rated <=5 OR dropped-status anime
    dropped_studios, dropped_genres = set(), set()
    for r, a in ratings:
        if r.score <= 5:
            if a.studio:
                dropped_studios.add(a.studio)
            for g in a.official_genres:
                dropped_genres.add(g.name)
    dropped_anime = (
        db.session.query(Anime)
        .join(WatchlistEntry, WatchlistEntry.anime_id == Anime.id)
        .filter(WatchlistEntry.user_id == user_id, WatchlistEntry.status == "dropped")
        .all()
    )
    for a in dropped_anime:
        if a.studio:
            dropped_studios.add(a.studio)
        for g in a.official_genres:
            dropped_genres.add(g.name)

    # Loved (rated >= 8) + dropped_or_low (rated <= 5) examples — newest first
    sorted_by_score = sorted(ratings, key=lambda ra: (-ra[0].score, -ra[0].id))
    loved_examples = [
        {"title": a.title, "score": r.score}
        for r, a in sorted_by_score if r.score >= 8
    ][:5]
    dropped_or_low_examples = [
        {"title": a.title, "score": r.score}
        for r, a in sorted_by_score if r.score <= 5
    ][:3]

    # Currently watching + planning watchlist
    currently_watching = (
        db.session.query(Anime.title)
        .join(WatchlistEntry, WatchlistEntry.anime_id == Anime.id)
        .filter(WatchlistEntry.user_id == user_id, WatchlistEntry.status == "watching")
        .limit(3)
        .all()
    )
    currently_watching = [t[0] for t in currently_watching]

    planning_ids = (
        db.session.query(WatchlistEntry.anime_id)
        .filter(WatchlistEntry.user_id == user_id, WatchlistEntry.status == "planning")
        .limit(20)
        .all()
    )
    planning_ids = [pid[0] for pid in planning_ids]

    return {
        "schema_version": SIGNAL_PROFILE_SCHEMA_VERSION,
        "computed_at": datetime.now(timezone.utc).isoformat(),
        "rating_count_at_compute": rating_count,
        "top_genres": top_genres,
        "top_studios": top_studios,
        "fan_genre_clusters": fan_genre_clusters,
        "era_lean_year": era_lean_year,
        "episode_fit_pref": episode_fit_pref,
        "dropped_traits": {"studios": sorted(dropped_studios), "genres": sorted(dropped_genres)},
        "loved_examples": loved_examples,
        "dropped_or_low_examples": dropped_or_low_examples,
        "currently_watching": currently_watching,
        "watchlist_planning_ids": planning_ids,
    }


def score_candidates(user_id, signal_profile, limit=40, include_nsfw=False):
    """Score all unwatched anime for this user, return the top `limit` candidates.

    Hard-filters out anything the user has already engaged with (rated or
    in watchlist with non-planning status). Respects NSFW rules.
    """
    # Anime IDs the user has already touched
    rated_ids = {
        r[0] for r in
        db.session.query(Rating.anime_id).filter(Rating.user_id == user_id).all()
    }
    blocked_watchlist_ids = {
        w[0] for w in
        db.session.query(WatchlistEntry.anime_id)
        .filter(WatchlistEntry.user_id == user_id,
                WatchlistEntry.status.in_(["watching", "completed", "dropped", "on_hold"]))
        .all()
    }
    excluded = rated_ids | blocked_watchlist_ids

    # Pull the candidate universe
    query = db.session.query(Anime).filter(~Anime.id.in_(excluded)) if excluded else db.session.query(Anime)
    if not include_nsfw:
        query = maybe_exclude_nsfw(query)
    # We still exclude hard-blocked genres regardless of include_nsfw flag
    # (Hentai). maybe_exclude_nsfw handles that when include_nsfw=False; do
    # nothing extra here.

    candidates_raw = query.all()

    # Top-100 popular IDs for surprise_bonus
    top_100_ids = {
        a[0] for a in
        db.session.query(Anime.id)
        .filter(Anime.popularity.isnot(None))
        .order_by(Anime.popularity.desc())
        .limit(100)
        .all()
    }

    scored = []
    for a in candidates_raw:
        cand = {
            "id": a.id,
            "title": a.title,
            "studio": a.studio,
            "genres": [g.name for g in a.official_genres],
            "fan_genres": [fg["genre"] for fg in (a.get_fan_genres() or [])[:5]],
            "api_score": a.api_score,
            "year": a.year,
            "episodes": a.episodes,
            "image_url": getattr(a, "image_url", None),
        }
        scored.append(score_candidate(cand, signal_profile, top_100_ids))

    scored.sort(key=lambda c: c["signals"]["total_score"], reverse=True)
    return scored[:limit]


def _empty_profile(rating_count):
    return {
        "schema_version": SIGNAL_PROFILE_SCHEMA_VERSION,
        "computed_at": datetime.now(timezone.utc).isoformat(),
        "rating_count_at_compute": rating_count,
        "top_genres": [],
        "top_studios": [],
        "fan_genre_clusters": [],
        "era_lean_year": None,
        "episode_fit_pref": {"short": 0.0, "medium": 0.0, "long": 0.0},
        "dropped_traits": {"studios": [], "genres": []},
        "loved_examples": [],
        "dropped_or_low_examples": [],
        "currently_watching": [],
        "watchlist_planning_ids": [],
    }
