"""Compose the JSON context passed to the LLM for chat.

Pulls a (cached) signal profile, strips cache-only fields, and conditionally
attaches the candidates array for recommend mode.
"""

from routes.rec_signals import get_signal_profile, score_candidates


_CACHE_ONLY_FIELDS = ("schema_version", "computed_at", "rating_count_at_compute")
_RECOMMEND_LIMIT = 40
_RECOMMEND_LIMIT_COLD = 80


def build_llm_context(user_id, message, mode, include_nsfw=False):
    """Return the JSON dict to embed in the LLM system prompt.

    mode: 'recommend' | 'rate' | 'onboard'
    """
    profile = get_signal_profile(user_id)
    user_block = {k: v for k, v in profile.items() if k not in _CACHE_ONLY_FIELDS}

    out = {
        "mode": mode,
        "user_message": message,
        "user": user_block,
    }

    if mode == "recommend":
        limit = _RECOMMEND_LIMIT_COLD if profile["rating_count_at_compute"] == 0 else _RECOMMEND_LIMIT
        out["candidates"] = score_candidates(user_id, profile, limit=limit, include_nsfw=include_nsfw)

    return out
