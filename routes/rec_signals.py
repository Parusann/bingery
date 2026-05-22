"""Multi-signal candidate scoring for chat recommendations.

This module exposes pure functions for signal computation plus the public
entry points the chatbot and /recommend/for-me routes call:

* build_signal_profile(user_id)  -> dict
* score_candidates(user_id, profile, limit, include_nsfw) -> list[dict]
* get_signal_profile(user_id)    -> dict  (cached, lazy invalidation)

See docs/superpowers/specs/2026-05-21-chat-rec-engine-design.md.
"""

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
