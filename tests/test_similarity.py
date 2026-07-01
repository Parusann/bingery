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


def _feat(**kw):
    from utils.similarity import build_feature_from_parts

    base = dict(
        tags={"Isekai": 0.9},
        genres={"Fantasy"},
        fan_genres=set(),
        source="Light Novel",
        episodes=25,
        year=2016,
        quality=0.86,
    )
    base.update(kw)
    return build_feature_from_parts(**base)


def test_similarity_identical_near_max():
    from utils.similarity import similarity_score

    a = _feat()
    # tags 45 + genres 20 + fan 0 (both empty) + format 10 + quality 8.6 + era 5
    assert abs(similarity_score(a, a) - 88.6) < 0.01


def test_similarity_tagless_seed_redistributes():
    from utils.similarity import similarity_score

    scored = similarity_score(_feat(tags={}), _feat())
    # tag weight (45) spreads proportionally over the other 55 points:
    # genres 36.36 + format 18.18 + quality 15.64 + era 9.09 + fan 0
    assert abs(scored - 79.2727) < 0.01


def test_similarity_disjoint_low():
    from utils.similarity import similarity_score

    a = _feat()
    b = _feat(
        tags={"Mecha": 0.8},
        genres={"Sci-Fi"},
        source="Original",
        episodes=100,
        year=1998,
        quality=0.5,
    )
    assert similarity_score(a, b) < 20
