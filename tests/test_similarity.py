"""Unit tests for the seed-based similarity engine (pure functions)."""
from utils.similarity import (
    weighted_jaccard,
    jaccard,
    source_bucket,
    episode_bucket,
    era_proximity,
)


def test_weighted_jaccard_identical_is_one():
    v = {"Isekai": 0.9, "Time Loop": 0.8}
    assert weighted_jaccard(v, dict(v)) == 1.0


def test_weighted_jaccard_disjoint_is_zero():
    assert weighted_jaccard({"A": 0.5}, {"B": 0.5}) == 0.0


def test_weighted_jaccard_partial():
    # min-sum 0.5 / max-sum (1.0 + 0.7)
    got = weighted_jaccard({"A": 1.0}, {"A": 0.5, "B": 0.7})
    assert abs(got - 0.5 / 1.7) < 1e-9


def test_weighted_jaccard_empty_inputs():
    assert weighted_jaccard({}, {"A": 1.0}) == 0.0
    assert weighted_jaccard({}, {}) == 0.0


def test_jaccard_sets():
    assert jaccard({"a", "b"}, {"b", "c"}) == 1 / 3
    assert jaccard(set(), set()) == 0.0


def test_source_bucket():
    assert source_bucket("Manga") == "manga"
    assert source_bucket("Light Novel") == "novel"
    assert source_bucket("Web Novel") == "novel"
    assert source_bucket("Original") == "original"
    assert source_bucket("Video Game") == "other"
    assert source_bucket(None) == "other"


def test_episode_bucket():
    assert episode_bucket(12) == "short"
    assert episode_bucket(24) == "medium"
    assert episode_bucket(51) == "long"
    assert episode_bucket(None) == "medium"


def test_era_proximity():
    assert era_proximity(2020, 2020) == 1.0
    assert 0.55 < era_proximity(2020, 2026) < 0.85  # sigma=8
    assert era_proximity(2020, None) == 0.5  # unknown year: neutral
