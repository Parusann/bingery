"""Seed-based anime similarity: pure scoring functions + catalog ranking.

Everything above `get_tag_index` is unit-testable without an app context —
no Flask or model imports in the math section. The design doc is
docs/superpowers/specs/2026-07-01-chat-similarity-revamp-design.md.
"""
from __future__ import annotations

import math

ERA_SIGMA_YEARS = 8.0

WEIGHTS = {
    "tags": 45,
    "genres": 20,
    "fan_genres": 10,
    "format": 10,
    "quality": 10,
    "era": 5,
}


def weighted_jaccard(a: dict[str, float], b: dict[str, float]) -> float:
    if not a or not b:
        return 0.0
    keys = set(a) | set(b)
    mx = sum(max(a.get(k, 0.0), b.get(k, 0.0)) for k in keys)
    if mx == 0:
        return 0.0
    return sum(min(a.get(k, 0.0), b.get(k, 0.0)) for k in keys) / mx


def jaccard(a: set, b: set) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def source_bucket(source: str | None) -> str:
    s = (source or "").lower()
    if "manga" in s:
        return "manga"
    if "novel" in s:
        return "novel"
    if s == "original":
        return "original"
    return "other"


def episode_bucket(episodes: int | None) -> str:
    if episodes is None:
        return "medium"
    if episodes <= 13:
        return "short"
    if episodes <= 26:
        return "medium"
    return "long"


def era_proximity(year_a: int | None, year_b: int | None) -> float:
    if year_a is None or year_b is None:
        return 0.5
    return math.exp(-((year_a - year_b) ** 2) / (2 * ERA_SIGMA_YEARS**2))
