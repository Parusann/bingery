"""Multi-signal candidate scoring for chat recommendations.

This module exposes pure functions for signal computation plus the public
entry points the chatbot and /recommend/for-me routes call:

* build_signal_profile(user_id)  -> dict
* score_candidates(user_id, profile, limit, include_nsfw) -> list[dict]
* get_signal_profile(user_id)    -> dict  (cached, lazy invalidation)

See docs/superpowers/specs/2026-05-21-chat-rec-engine-design.md.
"""

SIGNAL_PROFILE_SCHEMA_VERSION = 1
