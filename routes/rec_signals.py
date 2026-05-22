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
