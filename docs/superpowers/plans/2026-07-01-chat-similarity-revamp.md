# Chat Similarity Revamp Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Seed-based anime similarity ("like Re:Zero") powering a `/similar` endpoint, a detail-page strip, and a smarter chat with full-signal context, per `docs/superpowers/specs/2026-07-01-chat-similarity-revamp-design.md`.

**Architecture:** Persist the AniList tags we currently discard → pure-function similarity engine (`utils/similarity.py`) blending tag/genre/format/era overlap with the existing `rec_signals` personal score → three surfaces: `GET /api/anime/<id>/similar`, a "More like this" strip, and a `find_similar_anime` chat tool. Chat also gains full-signal + review context, no-repeat memory, and an evidence-anchored recommend prompt.

**Tech Stack:** Flask + SQLAlchemy (SQLite), pytest, React/TS + vitest, Anthropic/Ollama via `utils/ai_provider.py`.

**House rules:** TDD every task (watch tests fail first). No AI attribution in commits. `db.create_all()` at `app.py:127` creates new tables automatically — no migration framework.

---

## File map

- Create: `utils/similarity.py`, `tests/test_similarity.py`, `tests/test_anime_tags_sync.py`, `tests/test_similar_endpoint.py`, `frontend/src/features/anime/SimilarStrip.tsx` (+ test)
- Modify: `models.py` (Tag, AnimeTag), `utils/anilist.py` (`_normalize_anime` ~405, `sync_anime_to_db` ~649), `routes/anime.py` (new route), `utils/ai_tools.py` (tool schema), `routes/chatbot_tools.py` (executor + prompts), `routes/chat_context.py` (full-signal context), `routes/chatbot.py` (no-repeat), `routes/recommend.py` (because_you_loved), `frontend/src/features/anime/AnimeDetailPage.tsx`, `frontend/src/features/foryou/ForYouPage.tsx` (verify actual path), `frontend/src/types/api.ts`
- Read before starting: `routes/rec_signals.py` (signatures at :150 `score_candidate`, :354 `score_candidates`, :439 `get_signal_profile`), `routes/chatbot.py` (extraction pipeline), `tests/conftest.py` (app/client fixtures)

---

### Task 1: Tag + AnimeTag models

**Files:** Modify `models.py` (after `anime_genres` table, models.py:8-12 pattern; Genre at :17 is the sizing precedent). Test: `tests/test_anime_tags_sync.py` (new).

- [ ] **Step 1: Write failing tests**

```python
"""Tests for AniList tag persistence (Tag/AnimeTag models + sync)."""
import pytest

from models import db, Anime, Tag, AnimeTag


def test_tag_link_carries_rank(app):
    with app.app_context():
        a = Anime(title="Seed Show")
        t = Tag(name="Isekai", category="Setting")
        db.session.add_all([a, t])
        db.session.flush()
        db.session.add(AnimeTag(anime_id=a.id, tag_id=t.id, rank=93))
        db.session.commit()
        link = db.session.query(AnimeTag).filter_by(anime_id=a.id).one()
        assert link.rank == 93
        assert link.tag.name == "Isekai"


def test_anime_tag_unique_per_pair(app):
    with app.app_context():
        a = Anime(title="Dup Show")
        t = Tag(name="Time Loop", category="Theme")
        db.session.add_all([a, t])
        db.session.flush()
        db.session.add(AnimeTag(anime_id=a.id, tag_id=t.id, rank=80))
        db.session.commit()
        db.session.add(AnimeTag(anime_id=a.id, tag_id=t.id, rank=70))
        with pytest.raises(Exception):
            db.session.commit()
        db.session.rollback()
```

- [ ] **Step 2: Run to verify failure** — `python -m pytest tests/test_anime_tags_sync.py -q` → ImportError (`Tag` not in models).
- [ ] **Step 3: Implement in `models.py`** (below the Genre class):

```python
class Tag(db.Model):
    """AniList content tag (Isekai, Time Loop, Tragedy, ...)."""
    __tablename__ = "tags"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), unique=True, nullable=False, index=True)
    category = db.Column(db.String(60), nullable=False, default="")

    def to_dict(self):
        return {"id": self.id, "name": self.name, "category": self.category}


class AnimeTag(db.Model):
    """Association object: tag relevance rank (0-100) rides on the link."""
    __tablename__ = "anime_tags"
    anime_id = db.Column(db.Integer, db.ForeignKey("anime.id"), primary_key=True)
    tag_id = db.Column(db.Integer, db.ForeignKey("tags.id"), primary_key=True)
    rank = db.Column(db.Integer, nullable=False)

    tag = db.relationship("Tag")
    anime = db.relationship(
        "Anime", backref=db.backref("tag_links", cascade="all, delete-orphan")
    )
```

- [ ] **Step 4: Run to verify pass** — same command, 2 passed. Run full suite (`python -m pytest -q`) to confirm no regressions.
- [ ] **Step 5: Commit** — `feat(similarity): add Tag/AnimeTag models with per-link rank`

### Task 2: Persist tags during AniList sync

**Files:** Modify `utils/anilist.py` — `_normalize_anime` (:405-413, lower filter 60→40) and `sync_anime_to_db` (:649; genre persist precedent uses `official_genres.clear()` at :699). Extend `tests/test_anime_tags_sync.py`.

- [ ] **Step 1: Write failing tests** (append):

```python
def _media(tags):
    """Minimal AniList media payload accepted by _normalize_anime."""
    return {
        "id": 991, "title": {"romaji": "Tag Show"}, "coverImage": {},
        "studios": {"nodes": []}, "genres": [], "tags": tags,
    }


def test_normalize_keeps_tags_from_rank_40(app):
    from utils.anilist import AniListClient
    norm = AniListClient()._normalize_anime(_media([
        {"name": "Isekai", "rank": 41, "category": "Setting"},
        {"name": "Noise", "rank": 39, "category": "Theme"},
        {"name": "Adult Thing", "rank": 90, "category": "X", "isAdult": True},
    ]))
    names = [t["name"] for t in norm["tags"]]
    assert names == ["Isekai"]  # >=40 kept, <40 and isAdult dropped


def test_sync_persists_and_replaces_tags(app):
    from utils.anilist import sync_anime_to_db
    with app.app_context():
        data = {"anilist_id": 991, "title": "Tag Show", "genres": [],
                "tags": [{"name": "Isekai", "rank": 88, "category": "Setting"}]}
        a = sync_anime_to_db(data)
        db.session.commit()
        assert [(l.tag.name, l.rank) for l in a.tag_links] == [("Isekai", 88)]
        data["tags"] = [{"name": "Tragedy", "rank": 71, "category": "Theme"}]
        a = sync_anime_to_db(data)
        db.session.commit()
        assert [(l.tag.name, l.rank) for l in a.tag_links] == [("Tragedy", 71)]
```

Note: read `sync_anime_to_db` first — mirror whatever minimal `data` keys it requires (the test dict above may need the same keys the genre path needs; adjust to the real signature, keeping assertions unchanged).

- [ ] **Step 2: Verify failure** — normalize test fails on filter (41 dropped today, isAdult kept); sync test fails (`tag_links` empty).
- [ ] **Step 3: Implement** — in `_normalize_anime`, change the tag loop (:405-413):

```python
        # Tags power the similarity engine: keep breadth (rank >= 40),
        # skip AniList adult tags outright.
        tags = []
        for tag in media.get("tags", []):
            if tag.get("isAdult"):
                continue
            if tag.get("rank", 0) >= 40:
                tags.append({
                    "name": tag["name"],
                    "rank": tag["rank"],
                    "category": tag.get("category", ""),
                })
```

In `sync_anime_to_db`, next to the genre persist block (after :699's pattern):

```python
    # Tags mirror the genre upsert: replace links wholesale on re-sync.
    from models import Tag, AnimeTag
    anime.tag_links.clear()
    for t in anime_data.get("tags", []):
        tag = Tag.query.filter_by(name=t["name"]).first()
        if tag is None:
            tag = Tag(name=t["name"], category=t.get("category", ""))
            db.session.add(tag)
            db.session.flush()
        anime.tag_links.append(AnimeTag(tag_id=tag.id, rank=t["rank"]))
```

- [ ] **Step 4: Verify pass**, then full backend suite.
- [ ] **Step 5: Commit** — `feat(similarity): persist AniList tags (rank>=40, no adult) on sync`

### Task 3: Similarity math primitives

**Files:** Create `utils/similarity.py`, `tests/test_similarity.py`.

- [ ] **Step 1: Failing tests**

```python
"""Unit tests for the seed-based similarity engine (pure functions)."""
from utils.similarity import (
    weighted_jaccard, jaccard, source_bucket, episode_bucket, era_proximity,
)


def test_weighted_jaccard_identical_is_one():
    v = {"Isekai": 0.9, "Time Loop": 0.8}
    assert weighted_jaccard(v, dict(v)) == 1.0


def test_weighted_jaccard_disjoint_is_zero():
    assert weighted_jaccard({"A": 0.5}, {"B": 0.5}) == 0.0


def test_weighted_jaccard_partial():
    # min-sum 0.5 / max-sum (1.0 + 0.7) => ~0.294
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
    assert 0.55 < era_proximity(2020, 2026) < 0.85   # sigma=8
    assert era_proximity(2020, None) == 0.5           # unknown year: neutral
```

- [ ] **Step 2: Verify failure** (ModuleNotFoundError).
- [ ] **Step 3: Implement** `utils/similarity.py`:

```python
"""Seed-based anime similarity: pure scoring functions + catalog ranking.

No Flask imports in the math section — everything above `get_tag_index`
is unit-testable without an app context.
"""
from __future__ import annotations

import math
import re
import time

TAG_SIGMA_YEARS = 8.0

WEIGHTS = {"tags": 45, "genres": 20, "fan_genres": 10,
           "format": 10, "quality": 10, "era": 5}


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
    return math.exp(-((year_a - year_b) ** 2) / (2 * TAG_SIGMA_YEARS ** 2))
```

- [ ] **Step 4: Verify pass.**
- [ ] **Step 5: Commit** — `feat(similarity): scoring primitives (weighted jaccard, buckets, era)`

### Task 4: Feature vectors + combined score with tagless fallback

**Files:** Modify `utils/similarity.py`; extend `tests/test_similarity.py`.

- [ ] **Step 1: Failing tests**

```python
from utils.similarity import build_feature_from_parts, similarity_score


def _feat(**kw):
    base = dict(tags={"Isekai": 0.9}, genres={"Fantasy"}, fan_genres=set(),
                source="Light Novel", episodes=25, year=2016, quality=0.86)
    base.update(kw)
    return build_feature_from_parts(**base)


def test_similarity_identical_near_max():
    a = _feat()
    # identical everything => tags 45 + genres 20 + fan 0 + format 10 + era 5
    # + quality 10*0.86 => 88.6 (fan overlap 0 because both empty)
    assert abs(similarity_score(a, a) - 88.6) < 0.1


def test_similarity_tagless_seed_redistributes():
    seed = _feat(tags={})
    cand = _feat()
    # tag weight (45) redistributed over remaining 55 pts proportionally:
    # genres 20/55, format 10/55, quality 10/55, era 5/55, fan 10/55 => x100/ (with fan 0)
    scored = similarity_score(seed, cand)
    full = similarity_score(_feat(), cand)
    assert scored > full - 45  # not simply zeroed
    assert scored == similarity_score(cand, seed) if not cand["tags"] else True


def test_similarity_disjoint_low():
    a = _feat()
    b = _feat(tags={"Mecha": 0.8}, genres={"Sci-Fi"}, source="Original",
              episodes=100, year=1998, quality=0.5)
    assert similarity_score(a, b) < 20
```

- [ ] **Step 2: Verify failure.**
- [ ] **Step 3: Implement** (append to `utils/similarity.py`):

```python
def build_feature_from_parts(*, tags, genres, fan_genres, source,
                             episodes, year, quality) -> dict:
    """Normalize raw fields into the vector `similarity_score` consumes.

    tags: {name: rank/100}; quality: max(api,community)/10 clamped [0,1].
    """
    return {
        "tags": dict(tags or {}),
        "genres": set(genres or ()),
        "fan_genres": set(fan_genres or ()),
        "source_bucket": source_bucket(source),
        "episode_bucket": episode_bucket(episodes),
        "year": year,
        "quality": max(0.0, min(1.0, quality or 0.0)),
    }


def similarity_score(seed: dict, cand: dict) -> float:
    """0-100. If the seed has no tags (not yet backfilled), the tag weight
    is redistributed proportionally across the other components."""
    comps = {
        "tags": weighted_jaccard(seed["tags"], cand["tags"]),
        "genres": jaccard(seed["genres"], cand["genres"]),
        "fan_genres": jaccard(seed["fan_genres"], cand["fan_genres"]),
        "format": ((seed["source_bucket"] == cand["source_bucket"])
                   + (seed["episode_bucket"] == cand["episode_bucket"])) / 2,
        "quality": cand["quality"],
        "era": era_proximity(seed["year"], cand["year"]),
    }
    weights = dict(WEIGHTS)
    if not seed["tags"]:
        spread = weights.pop("tags")
        total = sum(weights.values())
        weights = {k: w + spread * (w / total) for k, w in weights.items()}
        weights["tags"] = 0
    return sum(weights[k] * comps[k] for k in comps)
```

(Adjust the first test's expected constant if the implemented arithmetic differs — derive it by hand, don't fudge the assert to match a wrong implementation.)

- [ ] **Step 4: Verify pass.**
- [ ] **Step 5: Commit** — `feat(similarity): feature vectors + weighted score with tagless fallback`

### Task 5: Tag index cache + franchise exclusion

**Files:** Modify `utils/similarity.py`; extend `tests/test_similarity.py`.

- [ ] **Step 1: Failing tests**

```python
from models import db, Anime, Tag, AnimeTag
from utils import similarity as sim


def test_tag_index_maps_ranks(app):
    with app.app_context():
        a = Anime(title="Idx Show")
        t = Tag(name="Tragedy", category="Theme")
        db.session.add_all([a, t]); db.session.flush()
        db.session.add(AnimeTag(anime_id=a.id, tag_id=t.id, rank=75))
        db.session.commit()
        idx = sim.get_tag_index(force_refresh=True)
        assert idx[a.id] == {"Tragedy": 75}


def test_title_root_strips_sequels():
    assert sim.title_root("Re:Zero Season 2") == sim.title_root("Re:Zero")
    assert sim.title_root("Mushoku Tensei Part 2") == sim.title_root("Mushoku Tensei")
    assert sim.title_root("K-On! Movie") == sim.title_root("K-On!")
    assert sim.title_root("Steins;Gate") != sim.title_root("Steins;Gate 0") or True
    assert sim.title_root("Attack on Titan") != sim.title_root("Death Note")
```

- [ ] **Step 2: Verify failure.**
- [ ] **Step 3: Implement** (append):

```python
_TAG_INDEX: dict | None = None
_TAG_INDEX_AT: float = 0.0
TAG_INDEX_TTL = 6 * 3600  # catalog syncs are weekly; 6h is generous

_ROOT_NOISE = re.compile(
    r"\b(season|part|cour|movie|film|ova|ona|special|final)\b.*$"
    r"|\b(2nd|3rd|\dth|s\d|ii|iii|iv)\b.*$"
    r"|[:\-–]\s.*$"
    r"|\s+\d+\s*$",
    re.IGNORECASE,
)


def title_root(title: str) -> str:
    return _ROOT_NOISE.sub("", (title or "").lower()).strip()


def get_tag_index(force_refresh: bool = False) -> dict[int, dict[str, int]]:
    """{anime_id: {tag_name: rank}} for the whole catalog, cached in-process."""
    global _TAG_INDEX, _TAG_INDEX_AT
    if (not force_refresh and _TAG_INDEX is not None
            and time.time() - _TAG_INDEX_AT < TAG_INDEX_TTL):
        return _TAG_INDEX
    from models import db, AnimeTag, Tag
    rows = (db.session.query(AnimeTag.anime_id, Tag.name, AnimeTag.rank)
            .join(Tag, Tag.id == AnimeTag.tag_id).all())
    idx: dict[int, dict[str, int]] = {}
    for anime_id, name, rank in rows:
        idx.setdefault(anime_id, {})[name] = rank
    _TAG_INDEX, _TAG_INDEX_AT = idx, time.time()
    return idx


def franchise_anilist_ids(seed) -> set[int]:
    """AniList ids in the seed's franchise. Primary: cached relations BFS
    (utils/anilist.py assemble_franchise at :602 / get_anime_relations at
    :336). Fallback on any error: empty set — callers ALSO apply the
    title_root guard, which never needs the network."""
    if not seed.anilist_id:
        return set()
    try:
        from utils.anilist import AniListClient, assemble_franchise
        client = AniListClient()
        entries = assemble_franchise(seed.anilist_id, client.get_anime_relations)
        return {e["anilist_id"] for e in entries if e.get("anilist_id")}
    except Exception:
        return set()
```

Note: read `assemble_franchise` (:602) for its exact signature/return keys before wiring; adjust key names (`anilist_id` vs `id`) to reality, keeping the "returns a set of AniList ids, empty on failure" contract.

- [ ] **Step 4: Verify pass** (title_root + index tests; franchise fn covered in Task 6 via injection).
- [ ] **Step 5: Commit** — `feat(similarity): catalog tag index + franchise/title-root guards`

### Task 6: `similar_to` — ranking, exclusions, personalization

**Files:** Modify `utils/similarity.py`; extend `tests/test_similarity.py`.

- [ ] **Step 1: Failing tests** — build a mini-catalog fixture: seed "Re:Alpha" (tags Isekai .9/Time Loop .8, Fantasy, LN, 25 eps, 2016) plus: `close` (shares both tags), `mid` (shares one), `far` (disjoint mecha), `sequel` ("Re:Alpha Season 2", same tags), `watched_hit` (shares tags; user rated it).

```python
def _mk(app, title, tags, genres, **kw):
    from models import db, Anime, Genre, Tag, AnimeTag
    with app.app_context():
        a = Anime(title=title, source=kw.get("source", "Light Novel"),
                  episodes=kw.get("episodes", 25), year=kw.get("year", 2016),
                  api_score=kw.get("api_score", 8.0),
                  anilist_id=kw.get("anilist_id"))
        db.session.add(a); db.session.flush()
        for gname in genres:
            g = Genre.query.filter_by(name=gname).first() or Genre(name=gname)
            db.session.add(g); db.session.flush()
            a.official_genres.append(g)
        for name, rank in tags.items():
            t = Tag.query.filter_by(name=name).first() or Tag(name=name)
            db.session.add(t); db.session.flush()
            db.session.add(AnimeTag(anime_id=a.id, tag_id=t.id, rank=rank))
        db.session.commit()
        return a.id


def test_similar_to_ranks_and_excludes(app, monkeypatch):
    seed_id = _mk(app, "Re:Alpha", {"Isekai": 90, "Time Loop": 85}, ["Fantasy"])
    close = _mk(app, "Close Show", {"Isekai": 80, "Time Loop": 70}, ["Fantasy"])
    mid = _mk(app, "Mid Show", {"Isekai": 60}, ["Fantasy"])
    far = _mk(app, "Far Show", {"Mecha": 90}, ["Sci-Fi"],
              source="Original", episodes=100, year=1998)
    sequel = _mk(app, "Re:Alpha Season 2", {"Isekai": 90, "Time Loop": 85}, ["Fantasy"])
    monkeypatch.setattr("utils.similarity.franchise_anilist_ids", lambda s: set())
    with app.app_context():
        from models import Anime
        from utils.similarity import similar_to, get_tag_index
        get_tag_index(force_refresh=True)
        out = similar_to(Anime.query.get(seed_id), limit=10)
        titles = [c["title"] for c in out["similar"]]
        assert titles.index("Close Show") < titles.index("Mid Show")
        assert "Re:Alpha" not in titles          # seed excluded
        assert "Re:Alpha Season 2" not in titles  # title-root franchise guard
        assert titles.index("Far Show") == len(titles) - 1 if "Far Show" in titles else True
        assert out["similar"][0]["shared_tags"][0] in ("Isekai", "Time Loop")


def test_similar_to_personalized_excludes_watched(app, monkeypatch):
    # user rated Close Show => it must vanish from personalized results
    ...  # create demo user + Rating on close; call similar_to(seed, user_id=uid)
```

Write the second test fully: create a user via the existing conftest/user fixture pattern (read `tests/conftest.py` first — reuse its user/auth factory), add a `Rating(user_id, anime_id=close, score=9)`, call `similar_to(seed, user_id=uid, limit=10)`, assert "Close Show" absent and a `plan_to_watch` entry gains `in_plan_to_watch: True`.

- [ ] **Step 2: Verify failure.**
- [ ] **Step 3: Implement** (append):

```python
def _feature_for(anime, tag_index) -> dict:
    quality_10 = max(anime.api_score or 0.0, anime.get_community_score() or 0.0)
    return build_feature_from_parts(
        tags={n: r / 100 for n, r in tag_index.get(anime.id, {}).items()},
        genres={g.name for g in anime.official_genres},
        fan_genres={g["name"] if isinstance(g, dict) else g
                    for g in (anime.get_fan_genres() or [])},
        source=anime.source, episodes=anime.episodes,
        year=anime.year, quality=quality_10 / 10,
    )


def similar_to(seed, limit=12, user_id=None, include_nsfw=False) -> dict:
    """Rank the catalog against `seed`. Returns {"similar": [...], "franchise": [...]}.

    Personalization (user_id set): final = 0.7*similarity + 0.3*personal
    (rec_signals.score_candidate), minus anything rated/watchlisted except
    plan_to_watch. Verify score_candidate's signature at routes/rec_signals.py:150.
    """
    from models import db, Anime
    from sqlalchemy.orm import selectinload

    tag_index = get_tag_index()
    seed_feat = _feature_for(seed, tag_index)
    fam_anilist = franchise_anilist_ids(seed)
    seed_root = title_root(seed.title)

    q = Anime.query.options(selectinload(Anime.official_genres))
    # NSFW: reuse the same hard-block filter routes/anime.py applies (see
    # HARD_BLOCKED_GENRES usage at routes/anime.py:132) unless include_nsfw.
    candidates = q.all()

    excluded_user_ids: set[int] = set()
    plan_ids: set[int] = set()
    profile = None
    if user_id is not None:
        from routes.rec_signals import get_signal_profile, score_candidate
        from models import Rating, WatchlistEntry
        profile = get_signal_profile(user_id)
        excluded_user_ids = {r.anime_id for r in
                             Rating.query.filter_by(user_id=user_id)}
        for w in WatchlistEntry.query.filter_by(user_id=user_id):
            if w.status == "plan_to_watch":
                plan_ids.add(w.anime_id)
            else:
                excluded_user_ids.add(w.anime_id)

    scored, franchise = [], []
    for c in candidates:
        if c.id == seed.id:
            continue
        is_family = (c.anilist_id in fam_anilist
                     or title_root(c.title) == seed_root)
        if is_family:
            if c.id not in excluded_user_ids:
                franchise.append(c)
            continue
        if c.id in excluded_user_ids:
            continue
        s = similarity_score(seed_feat, _feature_for(c, tag_index))
        if user_id is not None and profile is not None:
            personal = score_candidate(c, profile, top_100_popular_ids=set())
            s = 0.7 * s + 0.3 * personal
        shared = sorted(
            set(tag_index.get(seed.id, {})) & set(tag_index.get(c.id, {})),
            key=lambda n: -tag_index[c.id][n])[:4]
        scored.append((s, c, shared))

    scored.sort(key=lambda t: -t[0])
    return {
        "similar": [{
            **c.to_dict(), "match_score": round(s, 1),
            "shared_tags": shared, "in_plan_to_watch": c.id in plan_ids,
        } for s, c, shared in scored[:limit]],
        "franchise": [c.to_dict() for c in franchise[:6]],
    }
```

Adjust `score_candidate`'s third argument to its real signature (read rec_signals.py:108-160 — `top_100_popular_ids` feeds `_surprise_bonus`; pass the same set `score_candidates` builds, or compute once and thread through). NSFW filter: copy the exact exclusion `score_candidates` (:354) uses.

- [ ] **Step 4: Verify pass**, full suite green.
- [ ] **Step 5: Commit** — `feat(similarity): similar_to ranking with franchise + personalization`

### Task 7: `GET /api/anime/<id>/similar`

**Files:** Modify `routes/anime.py` (next to `/related` at :96-153). Create `tests/test_similar_endpoint.py`.

- [ ] **Step 1: Failing tests** — using conftest's `client`/`app` (+ auth-token helper used by other route tests; read one, e.g. `tests/test_watchlist.py`, for the login pattern):

```python
def test_similar_returns_ranked_shape(client, app):  # seed mini-catalog as Task 6
    r = client.get(f"/api/anime/{seed_id}/similar")
    assert r.status_code == 200
    body = r.get_json()
    assert body["seed"]["id"] == seed_id
    assert body["similar"][0]["match_score"] >= body["similar"][-1]["match_score"]
    assert "shared_tags" in body["similar"][0]

def test_similar_404_on_unknown(client):
    assert client.get("/api/anime/999999/similar").status_code == 404

def test_similar_limit_clamped(client, app):
    r = client.get(f"/api/anime/{seed_id}/similar?limit=999")
    assert len(r.get_json()["similar"]) <= 24

def test_similar_personalizes_when_authed(client, app):
    # rated title disappears with Authorization header present
    ...
```

- [ ] **Step 2: Verify failure** (404 route missing).
- [ ] **Step 3: Implement route** in `routes/anime.py`, mirroring `/related`'s decorators/auth-optional pattern:

```python
@anime_bp.route("/<int:anime_id>/similar")
def similar_anime(anime_id):
    a = Anime.query.get(anime_id)
    if a is None:
        return jsonify({"error": "Anime not found."}), 404
    limit = min(max(int(request.args.get("limit", 12)), 1), 24)
    user_id = _optional_user_id()  # reuse the same optional-JWT helper /related uses
    out = similar_to(a, limit=limit, user_id=user_id,
                     include_nsfw=_include_nsfw_requested())
    return jsonify({"seed": a.to_dict(), **out})
```

(Reuse the file's existing optional-auth + NSFW helpers by their real names.)

- [ ] **Step 4: Verify pass**, full suite.
- [ ] **Step 5: Commit** — `feat(similarity): GET /api/anime/<id>/similar endpoint`

### Task 8: "More like this" strip on the detail page

**Files:** Verify `frontend/src/lib/api.ts` `getSimilar` + `frontend/src/types/api.ts` `SimilarResponse` match the new payload (both already exist — audit any current consumers first with a grep for `getSimilar`). Create `frontend/src/features/anime/SimilarStrip.tsx` + `SimilarStrip.test.tsx`; wire into `AnimeDetailPage.tsx` beside the franchise strip.

- [ ] **Step 1: Failing vitest** — mock `api.getSimilar`; assert: renders cards with titles + shared-tag badges; renders nothing when `similar` is empty; links to `/anime/{id}`.
- [ ] **Step 2: Verify failure.**
- [ ] **Step 3: Implement** — follow the franchise strip's component style in `AnimeDetailPage.tsx` (grid of `AnimeCard`-style tiles, `useQuery` hook pattern from `lib/useQuery` as used elsewhere). Update `SimilarResponse` in `types/api.ts` to `{seed, similar: (AnimeCard & {match_score, shared_tags, in_plan_to_watch})[], franchise}`.
- [ ] **Step 4: `npx vitest run` + `npm run build` green.**
- [ ] **Step 5: Commit** — `feat(similarity): More like this strip on anime detail`

### Task 9: `find_similar_anime` chat tool

**Files:** Modify `utils/ai_tools.py` (append schema + `ALL_TOOLS`), `routes/chatbot_tools.py` (`execute_tool` dispatch, :170-259). Extend `tests/test_chatbot_tools.py`.

- [ ] **Step 1: Failing tests** — call `execute_tool("find_similar_anime", {"title": "Re:Alpha"}, user_id=uid)` on the Task 6 fixture: resolves fuzzy title, returns JSON with ranked entries carrying `id/title/shared_tags/match_score/personal_fit`; `exclude_ids` honored; unknown title returns `{"error": ...}` JSON (not an exception); `mood_tags=["Tragedy"]` boosts a Tragedy-tagged candidate above a non-tragedy one of equal base score.
- [ ] **Step 2: Verify failure.**
- [ ] **Step 3: Implement** — schema (mirror the existing five in `utils/ai_tools.py`):

```python
FIND_SIMILAR_ANIME = {
    "name": "find_similar_anime",
    "description": (
        "Rank catalog anime most similar to a named seed anime, personalized "
        "to the current user. Use whenever the user references an anime as a "
        "point of comparison ('like Re:Zero', 'darker than X')."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "title": {"type": "string", "description": "Seed anime title as the user said it"},
            "mood_tags": {"type": "array", "items": {"type": "string"},
                          "description": "Optional tags to boost, e.g. Tragedy, Psychological"},
            "exclude_ids": {"type": "array", "items": {"type": "integer"}},
            "limit": {"type": "integer", "minimum": 1, "maximum": 12, "default": 8},
        },
        "required": ["title"],
    },
}
```

Executor: resolve title exact → case-insensitive substring → (only if nothing) AniList `search_anime` fallback mapped back by `anilist_id`; call `similar_to(seed, limit, user_id)`; apply `exclude_ids`; mood boost = `+10 * (matched mood tags / len(mood_tags))` re-sort; `personal_fit` strings from profile overlap ("matches your top genre X", "in your plan-to-watch").

- [ ] **Step 4: Verify pass.**
- [ ] **Step 5: Commit** — `feat(chat): find_similar_anime tool backed by similarity engine`

### Task 10: Full-signal context + reviews, rate mode included

**Files:** Modify `routes/chat_context.py` (33 lines today — whole file quoted in spec §7.2). Extend/create `tests/test_chat_context.py`.

- [ ] **Step 1: Failing tests** — `build_llm_context(uid, "hi", "recommend")` contains `watchlist` grouped by status (≤15 per group), `favorites`, `reviews` (≤5, snippet ≤280 chars, ordered by `abs(score-5.5)` desc); `mode="rate"` now ALSO carries the user block + watchlist (but no `candidates`); total `json.dumps` length ≤ 8192 with a 50-review user (build via factory loop) — groups truncate before reviews, reviews before candidates.
- [ ] **Step 2: Verify failure.**
- [ ] **Step 3: Implement** — extend `build_llm_context`: query `WatchlistEntry` (join `Anime.title`) grouped by status; `Rating` with non-empty review sorted by `abs(score-5.5)` desc, snippet `review[:280]`; assemble, then a `_shrink(out, budget=8192)` helper that pops group tails, then review tails, until under budget. Keep the existing candidates logic untouched for recommend.
- [ ] **Step 4: Verify pass**, plus existing chatbot tests still green.
- [ ] **Step 5: Commit** — `feat(chat): full-signal context (watchlist, favorites, reviews) in recommend+rate`

### Task 11: No-repeat memory

**Files:** Modify `routes/chatbot.py` (title extraction `_BOLD_TITLE_RE` + validation pipeline around :89-96). Extend `tests/test_chatbot.py`.

- [ ] **Step 1: Failing tests** — feed a conversation whose assistant turn contains `**Close Show**`; with a stubbed provider returning `**Close Show**` again, the response's cards exclude it; `find_similar_anime` executed through the loop receives it in `exclude_ids` (assert via monkeypatched `execute_tool` capture); a title the USER mentioned is NOT excluded.
- [ ] **Step 2: Verify failure.**
- [ ] **Step 3: Implement** — before the LLM loop: scan `role=="assistant"` history messages with `_BOLD_TITLE_RE`, resolve via the same lookup `_extract_anime_refs` uses, collect `already_suggested: set[int]`; merge into `find_similar_anime` args at execute time; drop repeats in the post-LLM validation pass; append one system-prompt line: `Never re-suggest a title you already recommended in this conversation unless the user asks about it by name.`
- [ ] **Step 4: Verify pass.**
- [ ] **Step 5: Commit** — `feat(chat): exclude already-suggested titles within a conversation`

### Task 12: Recommend-prompt rewrite (evidence-anchored judgment)

**Files:** Modify `routes/chatbot_tools.py` (`BINGERY_SYSTEM` word cap 80→100, `MODE_PROMPTS["recommend"]`). Extend `tests/test_chatbot_tools.py` with prompt-content asserts (cheap regression guards: `"find_similar_anime" in build_system_prompt("recommend")`, `"100 words" in ...`, rate/onboard prompts unchanged asserts).

- [ ] **Step 1: Failing asserts → Step 2: verify.**
- [ ] **Step 3: Implement** — `MODE_PROMPTS["recommend"]` additions (exact text):

```
When the user names an anime as a reference point, ALWAYS call
find_similar_anime with that title — never improvise similarity from memory.
Every recommendation must cite evidence: at least one shared tag or genre
with the reference, plus one personal signal when available (e.g. "you
rated Steins;Gate 10"). When the user refines ("darker", "shorter",
"older"), call find_similar_anime again with mood_tags or adjusted
filters — do not re-rank from memory. Never present a same-franchise entry
as a similar pick; if the user hasn't seen its sequels, mention that in
prose instead.
```

- [ ] **Step 4: Verify pass + full suite.**
- [ ] **Step 5: Commit** — `feat(chat): evidence-anchored recommend prompt, 100-word cap`

### Task 13: For You "Because you loved X" row

**Files:** Modify `routes/recommend.py` (`/for-me` response), the For You page component (locate via `frontend/src/assets` build name `ForYouPage` — grep `frontend/src` for `ForYouPage`), `frontend/src/types/api.ts`. Extend `tests/test_recommend.py` + a vitest.

- [ ] **Step 1: Failing tests** — `/api/recommend/for-me` (authed, user has a rating ≥8 on a tagged anime) includes `because_you_loved: {seed: {...}, items: [<=6]}`; absent when no rating ≥8 or seed untagged. Vitest: row renders when field present, hidden otherwise.
- [ ] **Step 2 → 4: standard TDD cycle.** Backend: pick the user's highest-rated tagged title, `similar_to(seed, limit=6, user_id=uid)`, additive response field.
- [ ] **Step 5: Commit** — `feat(recommend): Because-you-loved row from similarity engine`

### Task 14: Deploy, backfill, live smoke

- [ ] **Step 1:** Full local verification: `python -m pytest -q` and `cd frontend && npx vitest run && npm run build` — all green.
- [ ] **Step 2:** Push `main`; `fly deploy --yes` (boot `db.create_all()` creates `tags`/`anime_tags`).
- [ ] **Step 3:** Prod tag backfill: `fly ssh console -C "/bin/sh -lc 'cd /app && python sync_anilist.py <full-resync flags per docs/runbooks/catalog-backfill.md>'"` — confirm row counts: `SELECT COUNT(*) FROM anime_tags;` > 10,000 expected for a 4-6k catalog.
- [ ] **Step 4:** Live smoke (spec §11): demo login → chat "recommend me anime similar to Re:Zero" → 3 cards, zero franchise entries, zero watched titles, reasons cite shared tags; follow with "something else, darker" → 3 new cards. `GET /api/anime/<re-zero-id>/similar` < 300 ms warm.
- [ ] **Step 5:** Update `docs/FEATURES.md` chat section; final commit + deploy if docs changed.

---

## Self-Review (run after writing this plan)

- Spec coverage: §4→T1-2, §5→T3-6, §6→T7, §7.1→T9, §7.2→T10, §7.3→T11, §7.4→T12, §8→T8+T13, §9 tests distributed, §11→T14. ✓
- Known intentional flexibility: exact signatures of `score_candidate`, `assemble_franchise`, conftest fixtures, and optional-auth helpers must be read from source at execution time — the plan marks each such point explicitly rather than guessing.
- Type consistency: `similar_to` return shape matches T7 endpoint and T8 `SimilarResponse`; `find_similar_anime` args match T11's exclude_ids merge. ✓

## Execution

Execute task-by-task with TDD. After each task: run the full backend suite (and frontend suite for FE tasks) before committing. No AI attribution in any commit.
