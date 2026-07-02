"""Unit tests for the seed-based similarity engine (pure functions)."""
import pytest

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
    # tags 55 + genres 15 + fan 0 (both empty) + format 10 + quality 8.6 + era 5
    assert abs(similarity_score(a, a) - 93.6) < 0.01


def test_similarity_tagless_seed_redistributes():
    from utils.similarity import similarity_score

    scored = similarity_score(_feat(tags={}), _feat())
    # tag weight (55) spreads proportionally over the other 45 points:
    # genres 33.33 + format 22.22 + quality 19.11 + era 11.11 + fan 0
    assert abs(scored - 85.7778) < 0.01


def test_seed_coverage_is_asymmetric():
    """A candidate with many EXTRA tags must not be penalized — what
    matters is how much of the seed's DNA it covers."""
    from utils.similarity import seed_coverage

    seed = {"Time Loop": 0.9, "Isekai": 0.8}
    broad = {"Time Loop": 0.9, "Isekai": 0.8, "Comedy": 0.9, "Mecha": 0.8, "Idol": 0.7}
    assert seed_coverage(seed, broad) == 1.0

    # half-strength on one tag, nothing on the other
    got = seed_coverage(seed, {"Time Loop": 0.45})
    assert abs(got - 0.45 / (0.9 + 0.8)) < 1e-9

    assert seed_coverage({}, broad) == 0.0


def test_seed_coverage_idf_downweights_ubiquitous_tags():
    """'Male Protagonist' (on half the catalog) must matter far less than
    'Time Loop' (rare). This is why prod shared_tags looked like junk."""
    from utils.similarity import seed_coverage

    seed = {"Male Protagonist": 0.9, "Time Loop": 0.9}
    idf = {"Male Protagonist": 0.05, "Time Loop": 2.0}
    only_junk = seed_coverage(seed, {"Male Protagonist": 0.9}, idf)
    only_rare = seed_coverage(seed, {"Time Loop": 0.9}, idf)
    assert only_rare > only_junk * 10


def test_seed_coverage_falls_back_when_all_idf_zero():
    """If every seed tag is catalog-universal (idf 0 everywhere), fall back
    to unweighted coverage instead of scoring all candidates 0."""
    from utils.similarity import seed_coverage

    seed = {"Isekai": 0.9}
    idf = {"Isekai": 0.0}
    assert abs(seed_coverage(seed, {"Isekai": 0.75}, idf) - 0.75 / 0.9) < 1e-9


def test_tag_idf_from_catalog(app):
    from models import db, Anime, Tag, AnimeTag
    from utils import similarity as sim

    with app.app_context():
        common = Tag(name="Everywhere")
        rare = Tag(name="Rare Gem")
        db.session.add_all([common, rare])
        db.session.flush()
        for i in range(4):
            a = Anime(title=f"IDF Show {i}")
            db.session.add(a)
            db.session.flush()
            db.session.add(AnimeTag(anime_id=a.id, tag_id=common.id, rank=80))
            if i == 0:
                db.session.add(AnimeTag(anime_id=a.id, tag_id=rare.id, rank=80))
        db.session.commit()
        sim.get_tag_index(force_refresh=True)
        idf = sim.get_tag_idf()
        assert idf["Everywhere"] == 0.0  # on every tagged anime => no signal
        assert idf["Rare Gem"] > 1.0


@pytest.fixture(autouse=True)
def _fresh_tag_index():
    """The tag index caches in-process; reset between tests so one test's
    catalog never leaks into another's."""
    from utils import similarity

    similarity._TAG_INDEX = None
    similarity._TAG_IDF = None
    similarity._TAG_INDEX_AT = 0.0
    yield


def test_tag_index_maps_ranks(app):
    from models import db, Anime, Tag, AnimeTag
    from utils import similarity as sim

    with app.app_context():
        a = Anime(title="Idx Show")
        t = Tag(name="Tragedy", category="Theme")
        db.session.add_all([a, t])
        db.session.flush()
        db.session.add(AnimeTag(anime_id=a.id, tag_id=t.id, rank=75))
        db.session.commit()
        idx = sim.get_tag_index(force_refresh=True)
        assert idx[a.id] == {"Tragedy": 75}


def test_title_root_strips_sequels():
    from utils.similarity import title_root

    assert title_root("Re:Zero Season 2") == title_root("Re:Zero")
    assert title_root("Mushoku Tensei Part 2") == title_root("Mushoku Tensei")
    assert title_root("K-On! Movie") == title_root("K-On!")
    assert title_root("Overlord II") == title_root("Overlord")
    # Plural forms leaked Re:Zero OVAs into prod /similar results.
    assert title_root("Re:Zero kara Hajimeru Isekai Seikatsu OVAs") == title_root(
        "Re:Zero kara Hajimeru Isekai Seikatsu"
    )
    assert title_root("Kaguya-sama Specials") == title_root("Kaguya-sama")
    assert title_root("Attack on Titan") != title_root("Death Note")


def test_title_root_never_empty():
    from utils.similarity import title_root

    # 'Final' is a noise word but must not reduce a title to nothing,
    # or every 'Final ...' title would franchise-match every other.
    assert title_root("Final Fantasy") != ""
    assert title_root("Final Fantasy") != title_root("Final Approach")


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


def _mk(app, title, tags, genres, **kw):
    """Create a catalog anime with tags/genres for similar_to tests."""
    from models import db, Anime, Genre, Tag, AnimeTag

    with app.app_context():
        a = Anime(
            title=title,
            source=kw.get("source", "Light Novel"),
            episodes=kw.get("episodes", 25),
            year=kw.get("year", 2016),
            api_score=kw.get("api_score", 8.0),
            anilist_id=kw.get("anilist_id"),
        )
        db.session.add(a)
        db.session.flush()
        for gname in genres:
            g = Genre.query.filter_by(name=gname).first()
            if not g:
                g = Genre(name=gname)
                db.session.add(g)
                db.session.flush()
            a.official_genres.append(g)
        for name, rank in tags.items():
            t = Tag.query.filter_by(name=name).first()
            if not t:
                t = Tag(name=name)
                db.session.add(t)
                db.session.flush()
            db.session.add(AnimeTag(anime_id=a.id, tag_id=t.id, rank=rank))
        db.session.commit()
        return a.id


def test_similar_to_ranks_and_excludes(app, monkeypatch):
    from models import Anime
    from utils.similarity import similar_to

    seed_id = _mk(app, "Re:Alpha", {"Isekai": 90, "Time Loop": 85}, ["Fantasy"])
    _mk(app, "Close Show", {"Isekai": 80, "Time Loop": 70}, ["Fantasy"])
    _mk(app, "Mid Show", {"Isekai": 60}, ["Fantasy"])
    _mk(app, "Far Show", {"Mecha": 90}, ["Sci-Fi"],
        source="Original", episodes=100, year=1998)
    _mk(app, "Re:Alpha Season 2", {"Isekai": 90, "Time Loop": 85}, ["Fantasy"])
    monkeypatch.setattr("utils.similarity.franchise_anilist_ids", lambda *a, **k: set())

    with app.app_context():
        out = similar_to(Anime.query.get(seed_id), limit=10)
        titles = [c["title"] for c in out["similar"]]
        assert titles.index("Close Show") < titles.index("Mid Show")
        assert "Re:Alpha" not in titles  # seed excluded
        assert "Re:Alpha Season 2" not in titles  # title-root franchise guard
        assert titles[-1] == "Far Show"
        assert set(out["similar"][0]["shared_tags"]) == {"Isekai", "Time Loop"}
        assert out["similar"][0]["match_score"] > out["similar"][-1]["match_score"]
        fam_titles = [c["title"] for c in out["franchise"]]
        assert fam_titles == ["Re:Alpha Season 2"]


def test_franchise_lookup_cache_only_never_constructs_client(monkeypatch):
    import time as _time

    from utils import anilist as al
    from utils import similarity as sim

    constructed = []

    class Spy:
        def __init__(self):
            constructed.append(1)

        def get_anime_relations(self, anilist_id):
            return {"self": {"anilist_id": anilist_id}, "edges": []}

    monkeypatch.setattr("utils.anilist.AniListClient", Spy)

    class Seed:
        anilist_id = 21355

    # Nothing cached: cache-only mode returns empty and never touches the client.
    monkeypatch.setattr(al, "_RELATIONS_CACHE", {})
    assert sim.franchise_anilist_ids(Seed(), allow_network=False) == set()
    assert not constructed

    # Cached relations (e.g. warmed by /related) are used without network.
    al._RELATIONS_CACHE[21355] = (
        _time.time(),
        {
            "self": {"anilist_id": 21355},
            "edges": [
                {
                    "relation_type": "SEQUEL",
                    "node": {"anilist_id": 108632, "type": "ANIME"},
                }
            ],
        },
    )
    ids = sim.franchise_anilist_ids(Seed(), allow_network=False)
    assert {21355, 108632} <= ids
    assert not constructed


def test_similar_to_query_count_is_bounded(app, monkeypatch):
    """similar_to must not fire per-candidate queries (community score,
    fan genres) — on the real 4-6k catalog that N+1 was a prod 502."""
    from sqlalchemy import event

    from models import db, Anime
    from utils.similarity import similar_to

    seed_id = _mk(app, "Perf Seed", {"Isekai": 90}, ["Fantasy"])
    for i in range(30):
        _mk(app, f"Perf Cand {i}", {"Isekai": 50 + i}, ["Fantasy"])
    monkeypatch.setattr("utils.similarity.franchise_anilist_ids", lambda *a, **k: set())

    with app.app_context():
        seed = Anime.query.get(seed_id)
        queries: list[str] = []

        def _count(conn, cursor, statement, parameters, context, executemany):
            queries.append(statement)

        engine = db.session.get_bind()
        event.listen(engine, "before_cursor_execute", _count)
        try:
            similar_to(seed, limit=10)
        finally:
            event.remove(engine, "before_cursor_execute", _count)
        assert len(queries) < 15, f"{len(queries)} queries — N+1 regression"


def test_similar_to_personalized_excludes_watched_and_flags_plan(app, monkeypatch):
    from models import db, Anime, Rating, User, WatchlistEntry
    from utils.similarity import similar_to

    seed_id = _mk(app, "Re:Beta", {"Isekai": 90, "Time Loop": 85}, ["Fantasy"])
    close_id = _mk(app, "Close Beta", {"Isekai": 80, "Time Loop": 70}, ["Fantasy"])
    plan_id = _mk(app, "Planned Beta", {"Isekai": 70}, ["Fantasy"])
    monkeypatch.setattr("utils.similarity.franchise_anilist_ids", lambda *a, **k: set())

    with app.app_context():
        u = User(username="simfan", email="simfan@example.com", password_hash="x")
        db.session.add(u)
        db.session.flush()
        db.session.add(Rating(user_id=u.id, anime_id=close_id, score=9))
        db.session.add(
            WatchlistEntry(user_id=u.id, anime_id=plan_id, status="plan_to_watch")
        )
        db.session.commit()

        out = similar_to(Anime.query.get(seed_id), limit=10, user_id=u.id)
        titles = [c["title"] for c in out["similar"]]
        assert "Close Beta" not in titles  # rated => excluded
        planned = next(c for c in out["similar"] if c["title"] == "Planned Beta")
        assert planned["in_plan_to_watch"] is True
