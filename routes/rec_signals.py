"""Multi-signal candidate scoring for chat recommendations.

This module exposes pure functions for signal computation plus the public
entry points the chatbot and /recommend/for-me routes call:

* build_signal_profile(user_id)  -> dict
* score_candidates(user_id, profile, limit, include_nsfw) -> list[dict]
* get_signal_profile(user_id)    -> dict  (cached, lazy invalidation)

See docs/superpowers/specs/2026-05-21-chat-rec-engine-design.md.
"""

import math

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
