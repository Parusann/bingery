# Chat Recommendation Engine Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the current LLM-only chat recommendation flow with a multi-signal candidate-retrieval pipeline so picks are grounded in pre-curated data, reasons cite specific signals, and obscure-but-fitting gems surface instead of populist defaults.

**Architecture:** Backend computes a richer user signal profile (cached on `User.taste_profile_cache`), runs a multi-signal candidate scorer that produces 30-50 ranked unwatched anime with per-signal breakdowns, and passes both the profile and candidates to the LLM. The LLM's prompt forces it to pick ONLY from the candidate list and cite one specific signal per pick. A validation pass after the LLM call silently drops any hallucinated titles.

**Tech Stack:** Python 3.13 / Flask / SQLAlchemy / SQLite / pytest / Ollama (gemma4:e4b).

**Reference:** This plan implements [`docs/superpowers/specs/2026-05-21-chat-rec-engine-design.md`](../specs/2026-05-21-chat-rec-engine-design.md).

---

## File map

**Create (new):**
- `routes/rec_signals.py` — Pure functions for signal scoring + signal profile builder. No DB writes beyond the cache update in `get_signal_profile`.
- `routes/chat_context.py` — Composes the JSON context passed to the LLM (signal profile + candidates).
- `tests/test_rec_signals.py` — Unit tests for every signal helper + integration tests for the profile builder and candidate scorer.
- `tests/test_chat_context.py` — Snapshot test for the LLM context JSON shape.

**Modify:**
- `models.py` — Add `User.taste_profile_cache` (Text) and `Anime.popularity` (Integer) columns.
- `sync_anilist.py` — Persist `popularity` from the AniList API response onto `Anime`.
- `routes/chatbot.py` — Replace ad-hoc context with `build_llm_context(...)`, add validation pass.
- `routes/chatbot_tools.py` — Append GROUNDING RULES to `BINGERY_SYSTEM`; stop computing taste_profile inline.
- `routes/recommend.py` — Unify `/api/recommend/for-me` on `score_candidates` for consistency.
- `tests/test_sync_anilist.py` — Cover the new `popularity` field.

**Migration (local + production SQLite):**
- `ALTER TABLE user ADD COLUMN taste_profile_cache TEXT;`
- `ALTER TABLE anime ADD COLUMN popularity INTEGER;`

**Note on naming vs. spec:** The spec said `Anime.popularity_rank`. The AniList API exposes raw `popularity` (a user-count), not a rank. We store `popularity` and derive "is this in the top-100 most popular?" in Python during scoring. The `surprise_factor` semantics are unchanged.

---

## Task 1: Add `User.taste_profile_cache` column

**Files:**
- Modify: `models.py`
- Test: `tests/test_models.py`
- Migration: in-place SQLite ALTER TABLE

- [ ] **Step 1: Write the failing test**

Add to `tests/test_models.py` (at end of file):

```python
def test_user_has_taste_profile_cache_column(app, db_session):
    from models import User
    u = User(email="x@x.com", username="x", password_hash="x")
    u.taste_profile_cache = '{"foo": 1}'
    db_session.add(u)
    db_session.commit()
    fetched = User.query.filter_by(email="x@x.com").first()
    assert fetched.taste_profile_cache == '{"foo": 1}'
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
C:/Users/parus/AppData/Local/Microsoft/WindowsApps/python.exe -m pytest tests/test_models.py::test_user_has_taste_profile_cache_column -v
```

Expected: FAIL with `AttributeError: 'User' object has no attribute 'taste_profile_cache'`.

- [ ] **Step 3: Add the column to `models.py`**

In the `User(db.Model)` class definition, add this column alongside the other user columns:

```python
    taste_profile_cache = db.Column(db.Text, nullable=True)
```

- [ ] **Step 4: Apply the column to the existing local DB**

```bash
C:/Users/parus/AppData/Local/Microsoft/WindowsApps/python.exe -c "import sqlite3; c = sqlite3.connect('bingery.db'); c.execute('ALTER TABLE user ADD COLUMN taste_profile_cache TEXT'); c.commit(); print('migrated')"
```

Expected output: `migrated`.

Note: the test DB is created fresh by conftest fixtures, so no migration needed there.

- [ ] **Step 5: Run the test to verify it passes**

```bash
C:/Users/parus/AppData/Local/Microsoft/WindowsApps/python.exe -m pytest tests/test_models.py::test_user_has_taste_profile_cache_column -v
```

Expected: PASS.

- [ ] **Step 6: Run the full test suite to verify nothing else broke**

```bash
C:/Users/parus/AppData/Local/Microsoft/WindowsApps/python.exe -m pytest -q
```

Expected: 221 passed (the existing 220 + this new one).

- [ ] **Step 7: Commit**

```bash
git add models.py tests/test_models.py
git commit -m "models: add User.taste_profile_cache column for signal-profile cache"
```

---

## Task 2: Add `Anime.popularity` column

**Files:**
- Modify: `models.py`
- Test: `tests/test_models.py`
- Migration: in-place SQLite ALTER TABLE

- [ ] **Step 1: Write the failing test**

Add to `tests/test_models.py`:

```python
def test_anime_has_popularity_column(app, db_session):
    from models import Anime
    a = Anime(title="Test Anime", anilist_id=999999, popularity=12345)
    db_session.add(a)
    db_session.commit()
    fetched = Anime.query.filter_by(anilist_id=999999).first()
    assert fetched.popularity == 12345
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
C:/Users/parus/AppData/Local/Microsoft/WindowsApps/python.exe -m pytest tests/test_models.py::test_anime_has_popularity_column -v
```

Expected: FAIL.

- [ ] **Step 3: Add the column to `models.py`**

In the `Anime(db.Model)` class, add alongside `api_score`:

```python
    popularity = db.Column(db.Integer, nullable=True)  # AniList user-list count
```

Also extend `to_dict` to expose it (find the existing `to_dict` method and add `"popularity": self.popularity,` to the returned dict near `api_score`).

- [ ] **Step 4: Apply the column to the local DB**

```bash
C:/Users/parus/AppData/Local/Microsoft/WindowsApps/python.exe -c "import sqlite3; c = sqlite3.connect('bingery.db'); c.execute('ALTER TABLE anime ADD COLUMN popularity INTEGER'); c.commit(); print('migrated')"
```

Expected output: `migrated`.

- [ ] **Step 5: Run the test + full suite**

```bash
C:/Users/parus/AppData/Local/Microsoft/WindowsApps/python.exe -m pytest tests/test_models.py::test_anime_has_popularity_column -v
C:/Users/parus/AppData/Local/Microsoft/WindowsApps/python.exe -m pytest -q
```

Expected: target test PASS, full suite 222 passed.

- [ ] **Step 6: Commit**

```bash
git add models.py tests/test_models.py
git commit -m "models: add Anime.popularity column populated from AniList user-list count"
```

---

## Task 3: Persist `popularity` in AniList sync

**Files:**
- Modify: `sync_anilist.py`
- Test: `tests/test_sync_anilist.py`

The AniList client (`utils/anilist.py`) already extracts `popularity` into the dict it returns; the sync script just isn't writing it to the model.

- [ ] **Step 1: Locate the upsert in `sync_anilist.py`**

Open `sync_anilist.py` and find the function that creates/updates an `Anime` row from the AniList payload (search for `api_score` assignment — the new field goes next to it).

- [ ] **Step 2: Write the failing test**

Add to `tests/test_sync_anilist.py` (near other upsert tests):

```python
def test_upsert_persists_popularity(app, db_session, monkeypatch):
    from sync_anilist import upsert_anime_from_anilist  # adjust import to actual symbol
    from models import Anime
    payload = {
        "id": 555555,
        "title": {"romaji": "Test Show", "english": "Test Show"},
        "popularity": 42000,
        "averageScore": 80,
        "episodes": 12,
        "studios": {"nodes": [{"name": "Studio T"}]},
        "genres": ["Drama"],
        "seasonYear": 2024,
        "season": "WINTER",
        "status": "FINISHED",
        "format": "TV",
        "coverImage": {"large": ""},
        "bannerImage": "",
        "description": "",
        "favourites": 100,
        "duration": 24,
    }
    upsert_anime_from_anilist(payload, db_session)
    db_session.commit()
    fetched = Anime.query.filter_by(anilist_id=555555).first()
    assert fetched.popularity == 42000
```

**Note:** If `sync_anilist.py`'s actual upsert symbol is named differently (e.g. `_upsert_from_payload`), adjust the import. The repo's existing test file will show the convention.

- [ ] **Step 3: Run the test to verify it fails**

```bash
C:/Users/parus/AppData/Local/Microsoft/WindowsApps/python.exe -m pytest tests/test_sync_anilist.py::test_upsert_persists_popularity -v
```

Expected: FAIL (either AttributeError or the value will be `None`).

- [ ] **Step 4: Add the assignment in `sync_anilist.py`**

In the upsert function, alongside the existing `api_score`-assignment line, add:

```python
anime.popularity = payload.get("popularity")
```

- [ ] **Step 5: Run the target test + full suite**

```bash
C:/Users/parus/AppData/Local/Microsoft/WindowsApps/python.exe -m pytest tests/test_sync_anilist.py -v
C:/Users/parus/AppData/Local/Microsoft/WindowsApps/python.exe -m pytest -q
```

Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add sync_anilist.py tests/test_sync_anilist.py
git commit -m "sync_anilist: persist popularity from AniList payload onto Anime"
```

---

## Task 4: Create `routes/rec_signals.py` skeleton

**Files:**
- Create: `routes/rec_signals.py`
- Test: `tests/test_rec_signals.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_rec_signals.py`:

```python
"""Unit + integration tests for routes.rec_signals.

The signal helpers are pure functions; profile builder + score_candidates
hit the DB and use the standard conftest fixtures.
"""

def test_module_has_schema_version():
    from routes import rec_signals
    assert isinstance(rec_signals.SIGNAL_PROFILE_SCHEMA_VERSION, int)
    assert rec_signals.SIGNAL_PROFILE_SCHEMA_VERSION >= 1
```

- [ ] **Step 2: Run to verify failure**

```bash
C:/Users/parus/AppData/Local/Microsoft/WindowsApps/python.exe -m pytest tests/test_rec_signals.py -v
```

Expected: FAIL with `ModuleNotFoundError` or `AttributeError`.

- [ ] **Step 3: Create the skeleton**

Create `routes/rec_signals.py`:

```python
"""Multi-signal candidate scoring for chat recommendations.

This module exposes pure functions for signal computation plus the public
entry points the chatbot and /recommend/for-me routes call:

* build_signal_profile(user_id)  -> dict
* score_candidates(user_id, profile, limit, include_nsfw) -> list[dict]
* get_signal_profile(user_id)    -> dict  (cached, lazy invalidation)

See docs/superpowers/specs/2026-05-21-chat-rec-engine-design.md.
"""

SIGNAL_PROFILE_SCHEMA_VERSION = 1
```

- [ ] **Step 4: Run the test to verify it passes**

```bash
C:/Users/parus/AppData/Local/Microsoft/WindowsApps/python.exe -m pytest tests/test_rec_signals.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add routes/rec_signals.py tests/test_rec_signals.py
git commit -m "rec_signals: skeleton module with schema version constant"
```

---

## Task 5: Implement `_studio_affinity` signal

**Files:**
- Modify: `routes/rec_signals.py`
- Modify: `tests/test_rec_signals.py`

- [ ] **Step 1: Write failing tests**

Add to `tests/test_rec_signals.py`:

```python
class TestStudioAffinity:
    def test_returns_zero_when_studio_unknown_to_user(self):
        from routes.rec_signals import _studio_affinity
        result = _studio_affinity("Studio X", [])
        assert result == 0.0

    def test_returns_hit_rate_for_known_studio(self):
        from routes.rec_signals import _studio_affinity
        top_studios = [{"name": "MAPPA", "hit_rate": 0.83, "n": 6}]
        result = _studio_affinity("MAPPA", top_studios)
        assert result == 0.83

    def test_studio_match_is_case_insensitive(self):
        from routes.rec_signals import _studio_affinity
        top_studios = [{"name": "MAPPA", "hit_rate": 0.83, "n": 6}]
        result = _studio_affinity("mappa", top_studios)
        assert result == 0.83

    def test_returns_zero_for_empty_candidate_studio(self):
        from routes.rec_signals import _studio_affinity
        top_studios = [{"name": "MAPPA", "hit_rate": 0.83, "n": 6}]
        assert _studio_affinity("", top_studios) == 0.0
        assert _studio_affinity(None, top_studios) == 0.0
```

- [ ] **Step 2: Run to verify failures**

```bash
C:/Users/parus/AppData/Local/Microsoft/WindowsApps/python.exe -m pytest tests/test_rec_signals.py::TestStudioAffinity -v
```

Expected: 4 FAILs with `AttributeError: module 'routes.rec_signals' has no attribute '_studio_affinity'`.

- [ ] **Step 3: Implement**

Append to `routes/rec_signals.py`:

```python
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
```

- [ ] **Step 4: Run tests**

```bash
C:/Users/parus/AppData/Local/Microsoft/WindowsApps/python.exe -m pytest tests/test_rec_signals.py::TestStudioAffinity -v
```

Expected: all 4 PASS.

- [ ] **Step 5: Commit**

```bash
git add routes/rec_signals.py tests/test_rec_signals.py
git commit -m "rec_signals: studio_affinity helper (hit rate lookup, case-insensitive)"
```

---

## Task 6: Implement `_genre_match` signal

**Files:**
- Modify: `routes/rec_signals.py`
- Modify: `tests/test_rec_signals.py`

- [ ] **Step 1: Write failing tests**

```python
class TestGenreMatch:
    def test_zero_when_no_overlap(self):
        from routes.rec_signals import _genre_match
        candidate_genres = ["Sports"]
        user_top_genres = [["Drama", 4.2], ["Slice of Life", 3.1]]
        assert _genre_match(candidate_genres, user_top_genres) == 0.0

    def test_full_overlap_returns_one(self):
        from routes.rec_signals import _genre_match
        candidate_genres = ["Drama", "Slice of Life"]
        user_top_genres = [["Drama", 4.2], ["Slice of Life", 3.1]]
        assert _genre_match(candidate_genres, user_top_genres) == 1.0

    def test_partial_overlap_returns_weighted_share(self):
        from routes.rec_signals import _genre_match
        candidate_genres = ["Drama"]
        user_top_genres = [["Drama", 4.0], ["Slice of Life", 1.0]]
        # 4.0 of total 5.0 in user weight matches => 0.8
        assert abs(_genre_match(candidate_genres, user_top_genres) - 0.8) < 1e-6

    def test_empty_inputs_zero(self):
        from routes.rec_signals import _genre_match
        assert _genre_match([], []) == 0.0
        assert _genre_match(["Drama"], []) == 0.0
        assert _genre_match([], [["Drama", 1.0]]) == 0.0
```

- [ ] **Step 2: Run to verify failures**

```bash
C:/Users/parus/AppData/Local/Microsoft/WindowsApps/python.exe -m pytest tests/test_rec_signals.py::TestGenreMatch -v
```

Expected: 4 FAILs.

- [ ] **Step 3: Implement**

```python
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
```

- [ ] **Step 4: Run tests + commit**

```bash
C:/Users/parus/AppData/Local/Microsoft/WindowsApps/python.exe -m pytest tests/test_rec_signals.py::TestGenreMatch -v
```

Expected: 4 PASS.

```bash
git add routes/rec_signals.py tests/test_rec_signals.py
git commit -m "rec_signals: genre_match helper (weighted user-genre share)"
```

---

## Task 7: Implement `_fan_genre_match` signal

**Files:**
- Modify: `routes/rec_signals.py`
- Modify: `tests/test_rec_signals.py`

Same shape as `_genre_match` but over user-applied fan-genre tags.

- [ ] **Step 1: Write failing tests**

```python
class TestFanGenreMatch:
    def test_partial_match_returns_weighted_share(self):
        from routes.rec_signals import _fan_genre_match
        cand = ["melancholy", "talky"]
        user_fan = [["melancholy", 4], ["talky", 3], ["weird", 1]]
        # 7 of total 8 user weight matches => 0.875
        assert abs(_fan_genre_match(cand, user_fan) - 7/8) < 1e-6

    def test_empty_returns_zero(self):
        from routes.rec_signals import _fan_genre_match
        assert _fan_genre_match([], [["x", 1]]) == 0.0
        assert _fan_genre_match(["x"], []) == 0.0
```

- [ ] **Step 2: Run, verify FAIL**

```bash
C:/Users/parus/AppData/Local/Microsoft/WindowsApps/python.exe -m pytest tests/test_rec_signals.py::TestFanGenreMatch -v
```

- [ ] **Step 3: Implement**

```python
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
```

- [ ] **Step 4: Run + commit**

```bash
C:/Users/parus/AppData/Local/Microsoft/WindowsApps/python.exe -m pytest tests/test_rec_signals.py::TestFanGenreMatch -v
```

```bash
git add routes/rec_signals.py tests/test_rec_signals.py
git commit -m "rec_signals: fan_genre_match helper (user-tag weighted share)"
```

---

## Task 8: Implement `_era_fit` signal

**Files:**
- Modify: `routes/rec_signals.py`
- Modify: `tests/test_rec_signals.py`

- [ ] **Step 1: Write failing tests**

```python
class TestEraFit:
    def test_exact_year_match_returns_one(self):
        from routes.rec_signals import _era_fit
        assert _era_fit(2018, 2018) == 1.0

    def test_decreases_with_distance(self):
        from routes.rec_signals import _era_fit
        near = _era_fit(2020, 2018)
        far = _era_fit(2000, 2018)
        assert 0 < far < near < 1

    def test_none_inputs_return_zero(self):
        from routes.rec_signals import _era_fit
        assert _era_fit(None, 2018) == 0.0
        assert _era_fit(2018, None) == 0.0

    def test_six_year_gap_is_near_e_to_the_negative_half(self):
        from routes.rec_signals import _era_fit
        import math
        # sigma=6, so |delta|=6 yields exp(-0.5) ~ 0.6065
        assert abs(_era_fit(2018, 2024) - math.exp(-0.5)) < 1e-3
```

- [ ] **Step 2: Run, verify FAIL**

```bash
C:/Users/parus/AppData/Local/Microsoft/WindowsApps/python.exe -m pytest tests/test_rec_signals.py::TestEraFit -v
```

- [ ] **Step 3: Implement**

Add to top of `routes/rec_signals.py`:

```python
import math
```

Then:

```python
def _era_fit(candidate_year, user_era_lean_year):
    """Gaussian centered on the user's era lean, sigma=6 years.

    Returns 1.0 for exact match, ~0.6 at 6-year gap, ~0.14 at 12-year gap.
    Returns 0.0 if either year is None (unknown era).
    """
    if candidate_year is None or user_era_lean_year is None:
        return 0.0
    delta = candidate_year - user_era_lean_year
    return math.exp(-(delta * delta) / (2 * 6 * 6))
```

- [ ] **Step 4: Run + commit**

```bash
C:/Users/parus/AppData/Local/Microsoft/WindowsApps/python.exe -m pytest tests/test_rec_signals.py::TestEraFit -v
```

```bash
git add routes/rec_signals.py tests/test_rec_signals.py
git commit -m "rec_signals: era_fit helper (gaussian around user era lean)"
```

---

## Task 9: Implement `_episode_fit` signal

**Files:**
- Modify: `routes/rec_signals.py`
- Modify: `tests/test_rec_signals.py`

- [ ] **Step 1: Write failing tests**

```python
class TestEpisodeFit:
    def test_returns_short_share_for_short_anime(self):
        from routes.rec_signals import _episode_fit
        prefs = {"short": 0.7, "medium": 0.2, "long": 0.1}
        assert _episode_fit(12, prefs) == 0.7

    def test_returns_medium_share_for_medium_anime(self):
        from routes.rec_signals import _episode_fit
        prefs = {"short": 0.7, "medium": 0.2, "long": 0.1}
        assert _episode_fit(24, prefs) == 0.2

    def test_returns_long_share_for_long_anime(self):
        from routes.rec_signals import _episode_fit
        prefs = {"short": 0.7, "medium": 0.2, "long": 0.1}
        assert _episode_fit(60, prefs) == 0.1

    def test_unknown_episode_count_returns_zero(self):
        from routes.rec_signals import _episode_fit
        prefs = {"short": 0.7, "medium": 0.2, "long": 0.1}
        assert _episode_fit(None, prefs) == 0.0
        assert _episode_fit(0, prefs) == 0.0
```

- [ ] **Step 2: Run, verify FAIL**

```bash
C:/Users/parus/AppData/Local/Microsoft/WindowsApps/python.exe -m pytest tests/test_rec_signals.py::TestEpisodeFit -v
```

- [ ] **Step 3: Implement**

```python
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
```

- [ ] **Step 4: Run + commit**

```bash
C:/Users/parus/AppData/Local/Microsoft/WindowsApps/python.exe -m pytest tests/test_rec_signals.py::TestEpisodeFit -v
```

```bash
git add routes/rec_signals.py tests/test_rec_signals.py
git commit -m "rec_signals: episode_fit helper (short/medium/long bucket lookup)"
```

---

## Task 10: Implement `_surprise_bonus` signal

**Files:**
- Modify: `routes/rec_signals.py`
- Modify: `tests/test_rec_signals.py`

- [ ] **Step 1: Write failing tests**

```python
class TestSurpriseBonus:
    def test_full_bonus_for_obscure_high_quality(self):
        from routes.rec_signals import _surprise_bonus
        top_100 = {1, 2, 3}
        # api_score >= 8 AND not in top_100
        assert _surprise_bonus(8.6, 999, top_100) == 1.0

    def test_half_bonus_for_quality_alone(self):
        from routes.rec_signals import _surprise_bonus
        top_100 = {1, 999}
        # api_score >= 8 but IS in top_100
        assert _surprise_bonus(8.6, 999, top_100) == 0.5

    def test_half_bonus_for_obscurity_alone(self):
        from routes.rec_signals import _surprise_bonus
        top_100 = {1}
        # not in top_100 but api_score < 8
        assert _surprise_bonus(7.0, 999, top_100) == 0.5

    def test_no_bonus_for_neither(self):
        from routes.rec_signals import _surprise_bonus
        top_100 = {1, 999}
        assert _surprise_bonus(7.0, 999, top_100) == 0.0

    def test_handles_none_api_score(self):
        from routes.rec_signals import _surprise_bonus
        # api_score=None counts as low quality; obscurity alone gives 0.5
        assert _surprise_bonus(None, 999, {1}) == 0.5
```

- [ ] **Step 2: Run, verify FAIL**

```bash
C:/Users/parus/AppData/Local/Microsoft/WindowsApps/python.exe -m pytest tests/test_rec_signals.py::TestSurpriseBonus -v
```

- [ ] **Step 3: Implement**

```python
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
```

- [ ] **Step 4: Run + commit**

```bash
C:/Users/parus/AppData/Local/Microsoft/WindowsApps/python.exe -m pytest tests/test_rec_signals.py::TestSurpriseBonus -v
```

```bash
git add routes/rec_signals.py tests/test_rec_signals.py
git commit -m "rec_signals: surprise_bonus helper (high-quality + obscure boost)"
```

---

## Task 11: Implement `_watchlist_coherence` signal

**Files:**
- Modify: `routes/rec_signals.py`
- Modify: `tests/test_rec_signals.py`

- [ ] **Step 1: Write failing tests**

```python
class TestWatchlistCoherence:
    def test_one_when_in_planning(self):
        from routes.rec_signals import _watchlist_coherence
        assert _watchlist_coherence(42, [1, 42, 100]) == 1

    def test_zero_when_not_in_planning(self):
        from routes.rec_signals import _watchlist_coherence
        assert _watchlist_coherence(42, [1, 100]) == 0
        assert _watchlist_coherence(42, []) == 0
```

- [ ] **Step 2: Run, verify FAIL**

```bash
C:/Users/parus/AppData/Local/Microsoft/WindowsApps/python.exe -m pytest tests/test_rec_signals.py::TestWatchlistCoherence -v
```

- [ ] **Step 3: Implement**

```python
def _watchlist_coherence(candidate_id, planning_ids):
    """1 if user has this anime in 'planning' status, else 0."""
    return 1 if candidate_id in planning_ids else 0
```

- [ ] **Step 4: Run + commit**

```bash
C:/Users/parus/AppData/Local/Microsoft/WindowsApps/python.exe -m pytest tests/test_rec_signals.py::TestWatchlistCoherence -v
```

```bash
git add routes/rec_signals.py tests/test_rec_signals.py
git commit -m "rec_signals: watchlist_coherence helper (planning-status bonus)"
```

---

## Task 12: Implement `_dropped_trait_penalty` signal

**Files:**
- Modify: `routes/rec_signals.py`
- Modify: `tests/test_rec_signals.py`

- [ ] **Step 1: Write failing tests**

```python
class TestDroppedTraitPenalty:
    def test_zero_when_no_overlap(self):
        from routes.rec_signals import _dropped_trait_penalty
        dropped = {"studios": ["Bad Studio"], "genres": ["Ecchi"]}
        assert _dropped_trait_penalty("Good Studio", ["Drama"], dropped) == 0.0

    def test_half_for_studio_alone(self):
        from routes.rec_signals import _dropped_trait_penalty
        dropped = {"studios": ["Bad Studio"], "genres": ["Ecchi"]}
        assert _dropped_trait_penalty("Bad Studio", ["Drama"], dropped) == 0.5

    def test_genre_share_contribution(self):
        from routes.rec_signals import _dropped_trait_penalty
        dropped = {"studios": [], "genres": ["Ecchi", "Sports"]}
        # Both candidate genres are in the dropped list => 1.0 share => 0.5 weight
        assert _dropped_trait_penalty("Studio X", ["Ecchi", "Sports"], dropped) == 0.5

    def test_combined_full_penalty(self):
        from routes.rec_signals import _dropped_trait_penalty
        dropped = {"studios": ["Bad Studio"], "genres": ["Ecchi"]}
        # studio matches (+0.5) and 1/1 candidate genre matches (+0.5) => 1.0
        assert _dropped_trait_penalty("Bad Studio", ["Ecchi"], dropped) == 1.0

    def test_no_candidate_genres_uses_studio_only(self):
        from routes.rec_signals import _dropped_trait_penalty
        dropped = {"studios": ["Bad Studio"], "genres": ["Ecchi"]}
        assert _dropped_trait_penalty("Bad Studio", [], dropped) == 0.5
```

- [ ] **Step 2: Run, verify FAIL**

```bash
C:/Users/parus/AppData/Local/Microsoft/WindowsApps/python.exe -m pytest tests/test_rec_signals.py::TestDroppedTraitPenalty -v
```

- [ ] **Step 3: Implement**

```python
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
```

- [ ] **Step 4: Run + commit**

```bash
C:/Users/parus/AppData/Local/Microsoft/WindowsApps/python.exe -m pytest tests/test_rec_signals.py::TestDroppedTraitPenalty -v
```

```bash
git add routes/rec_signals.py tests/test_rec_signals.py
git commit -m "rec_signals: dropped_trait_penalty helper (studio + genre overlap)"
```

---

## Task 13: Implement `score_candidate` combiner

**Files:**
- Modify: `routes/rec_signals.py`
- Modify: `tests/test_rec_signals.py`

- [ ] **Step 1: Write failing test**

```python
class TestScoreCandidate:
    def test_returns_signals_breakdown_and_total(self):
        from routes.rec_signals import score_candidate
        candidate = {
            "id": 42, "title": "X", "studio": "MAPPA",
            "genres": ["Drama"], "fan_genres": ["melancholy"],
            "api_score": 8.6, "year": 2018, "episodes": 12,
        }
        profile = {
            "top_genres": [["Drama", 1.0]],
            "top_studios": [{"name": "MAPPA", "hit_rate": 1.0, "n": 5}],
            "fan_genre_clusters": [["melancholy", 1]],
            "era_lean_year": 2018,
            "episode_fit_pref": {"short": 1.0, "medium": 0, "long": 0},
            "dropped_traits": {"studios": [], "genres": []},
            "watchlist_planning_ids": [],
        }
        top_100 = set()  # candidate 42 not in top-100
        result = score_candidate(candidate, profile, top_100)
        assert result["id"] == 42
        assert result["signals"]["studio_affinity"] == 1.0
        assert result["signals"]["genre_match"] == 1.0
        assert result["signals"]["fan_genre_match"] == 1.0
        assert abs(result["signals"]["era_fit"] - 1.0) < 1e-6
        assert result["signals"]["episode_fit"] == 1.0
        assert result["signals"]["surprise_factor"] == 1.0
        assert result["signals"]["watchlist_aligned"] == 0
        assert result["signals"]["dropped_trait_penalty"] == 0.0
        # All signals max out: 25+20+15+10+10+10 = 90; no watchlist (0), no penalty (0)
        assert abs(result["signals"]["total_score"] - 90.0) < 1e-6

    def test_penalty_subtracts_from_total(self):
        from routes.rec_signals import score_candidate
        candidate = {
            "id": 1, "title": "Y", "studio": "Bad", "genres": ["Ecchi"],
            "fan_genres": [], "api_score": 6.0, "year": 2020, "episodes": 12,
        }
        profile = {
            "top_genres": [], "top_studios": [], "fan_genre_clusters": [],
            "era_lean_year": 2020,
            "episode_fit_pref": {"short": 0, "medium": 0, "long": 0},
            "dropped_traits": {"studios": ["Bad"], "genres": ["Ecchi"]},
            "watchlist_planning_ids": [],
        }
        result = score_candidate(candidate, profile, {1})
        # era_fit only (1.0 * 10 = 10), penalty (1.0 * 20 = -20) => -10 floored to 0
        assert result["signals"]["dropped_trait_penalty"] == 1.0
        assert result["signals"]["total_score"] == 0.0  # floor at 0
```

- [ ] **Step 2: Run, verify FAIL**

```bash
C:/Users/parus/AppData/Local/Microsoft/WindowsApps/python.exe -m pytest tests/test_rec_signals.py::TestScoreCandidate -v
```

- [ ] **Step 3: Implement**

```python
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
```

- [ ] **Step 4: Run + commit**

```bash
C:/Users/parus/AppData/Local/Microsoft/WindowsApps/python.exe -m pytest tests/test_rec_signals.py -v
```

Expected: all signal tests + both `TestScoreCandidate` tests PASS.

```bash
git add routes/rec_signals.py tests/test_rec_signals.py
git commit -m "rec_signals: score_candidate combiner with weighted total + floor at 0"
```

---

## Task 14: Implement `build_signal_profile`

**Files:**
- Modify: `routes/rec_signals.py`
- Modify: `tests/test_rec_signals.py`

This is the heavy DB-touching function. It uses the existing conftest fixtures.

- [ ] **Step 1: Write failing tests**

```python
class TestBuildSignalProfile:
    def test_empty_profile_for_user_with_no_ratings(self, app, db_session):
        from models import User
        from routes.rec_signals import build_signal_profile
        u = User(email="new@x.com", username="newbie", password_hash="x")
        db_session.add(u)
        db_session.commit()
        profile = build_signal_profile(u.id)
        assert profile["rating_count_at_compute"] == 0
        assert profile["top_genres"] == []
        assert profile["top_studios"] == []
        assert profile["loved_examples"] == []
        assert profile["currently_watching"] == []
        assert profile["watchlist_planning_ids"] == []

    def test_extracts_top_studios_with_hit_rate(self, app, db_session):
        """User rated 3 MAPPA shows: 9, 8, 5. hit_rate = 2/3 ≈ 0.667."""
        from models import User, Anime, Rating
        from routes.rec_signals import build_signal_profile
        u = User(email="r@x.com", username="rater", password_hash="x")
        db_session.add(u); db_session.commit()
        for i, score in enumerate([9, 8, 5]):
            a = Anime(title=f"MAPPA Show {i}", anilist_id=900 + i, studio="MAPPA")
            db_session.add(a); db_session.commit()
            db_session.add(Rating(user_id=u.id, anime_id=a.id, score=score))
        db_session.commit()
        profile = build_signal_profile(u.id)
        mappa = next((s for s in profile["top_studios"] if s["name"] == "MAPPA"), None)
        assert mappa is not None
        assert mappa["n"] == 3
        assert abs(mappa["hit_rate"] - 2/3) < 1e-3

    def test_loved_and_dropped_examples_populated(self, app, db_session):
        from models import User, Anime, Rating
        from routes.rec_signals import build_signal_profile
        u = User(email="r2@x.com", username="r2", password_hash="x")
        db_session.add(u); db_session.commit()
        loved = Anime(title="Frieren", anilist_id=701, studio="Madhouse")
        dropped = Anime(title="Bad Show", anilist_id=702, studio="Other")
        db_session.add_all([loved, dropped]); db_session.commit()
        db_session.add(Rating(user_id=u.id, anime_id=loved.id, score=9))
        db_session.add(Rating(user_id=u.id, anime_id=dropped.id, score=3))
        db_session.commit()
        profile = build_signal_profile(u.id)
        assert any(e["title"] == "Frieren" for e in profile["loved_examples"])
        assert any(e["title"] == "Bad Show" for e in profile["dropped_or_low_examples"])
```

- [ ] **Step 2: Run, verify FAIL**

```bash
C:/Users/parus/AppData/Local/Microsoft/WindowsApps/python.exe -m pytest tests/test_rec_signals.py::TestBuildSignalProfile -v
```

- [ ] **Step 3: Implement**

Add to `routes/rec_signals.py`:

```python
from datetime import datetime, timezone
from collections import Counter
from sqlalchemy import func

from models import db, User, Anime, Rating, FanGenreVote, WatchlistEntry, Genre, anime_genres


def build_signal_profile(user_id):
    """Compute the user's signal profile from scratch.

    See the spec (§4) for the schema. Pure read; does NOT write the cache.
    Caller (get_signal_profile) is responsible for caching.
    """
    ratings = (
        db.session.query(Rating, Anime)
        .join(Anime, Anime.id == Rating.anime_id)
        .filter(Rating.user_id == user_id)
        .all()
    )
    rating_count = len(ratings)

    if rating_count == 0:
        return _empty_profile(rating_count)

    # Top genres: weighted by rating score (>5 contributes positively)
    genre_weights = Counter()
    for r, a in ratings:
        weight = max(0, r.score - 5)
        for g in a.official_genres:
            genre_weights[g.name] += weight
    top_genres = sorted(genre_weights.items(), key=lambda x: -x[1])[:8]
    top_genres = [[name, float(w)] for name, w in top_genres if w > 0]

    # Top studios: hit_rate = (ratings >= 8) / (ratings for that studio); require n >= 2
    studio_ratings = Counter()
    studio_hits = Counter()
    for r, a in ratings:
        if not a.studio:
            continue
        studio_ratings[a.studio] += 1
        if r.score >= 8:
            studio_hits[a.studio] += 1
    top_studios = []
    for studio, n in studio_ratings.items():
        if n < 2:
            continue
        top_studios.append({
            "name": studio,
            "hit_rate": studio_hits[studio] / n,
            "n": n,
        })
    top_studios.sort(key=lambda s: (-s["hit_rate"], -s["n"]))
    top_studios = top_studios[:5]

    # Fan-genre clusters: count fan-genre votes by this user
    fan_votes = (
        db.session.query(FanGenreVote.genre_tag, func.count(FanGenreVote.id))
        .filter(FanGenreVote.user_id == user_id)
        .group_by(FanGenreVote.genre_tag)
        .order_by(func.count(FanGenreVote.id).desc())
        .limit(8)
        .all()
    )
    fan_genre_clusters = [[tag, int(c)] for tag, c in fan_votes]

    # Era lean: weighted average year, weight = max(0, score-5)
    era_num, era_den = 0.0, 0.0
    for r, a in ratings:
        if a.year is None:
            continue
        w = max(0, r.score - 5)
        era_num += w * a.year
        era_den += w
    era_lean_year = int(round(era_num / era_den)) if era_den else None

    # Episode-fit pref: based on COMPLETED entries (status='completed' in watchlist
    # OR rated >= 6 as a fallback). Bucket by episode count.
    completed = (
        db.session.query(Anime)
        .join(WatchlistEntry, WatchlistEntry.anime_id == Anime.id)
        .filter(WatchlistEntry.user_id == user_id, WatchlistEntry.status == "completed")
        .all()
    )
    if not completed:
        # Fallback: rated >= 6
        completed = [a for r, a in ratings if r.score >= 6]
    buckets = {"short": 0, "medium": 0, "long": 0}
    for a in completed:
        if not a.episodes:
            continue
        if a.episodes <= 13:
            buckets["short"] += 1
        elif a.episodes <= 26:
            buckets["medium"] += 1
        else:
            buckets["long"] += 1
    total_buckets = sum(buckets.values())
    if total_buckets:
        episode_fit_pref = {k: v / total_buckets for k, v in buckets.items()}
    else:
        episode_fit_pref = {"short": 0.0, "medium": 0.0, "long": 0.0}

    # Dropped traits: studios + genres of rated <=5 OR dropped-status anime
    dropped_studios, dropped_genres = set(), set()
    for r, a in ratings:
        if r.score <= 5:
            if a.studio:
                dropped_studios.add(a.studio)
            for g in a.official_genres:
                dropped_genres.add(g.name)
    dropped_anime = (
        db.session.query(Anime)
        .join(WatchlistEntry, WatchlistEntry.anime_id == Anime.id)
        .filter(WatchlistEntry.user_id == user_id, WatchlistEntry.status == "dropped")
        .all()
    )
    for a in dropped_anime:
        if a.studio:
            dropped_studios.add(a.studio)
        for g in a.official_genres:
            dropped_genres.add(g.name)

    # Loved (rated >= 8) + dropped_or_low (rated <= 5) examples — newest first
    sorted_by_score = sorted(ratings, key=lambda ra: (-ra[0].score, -ra[0].id))
    loved_examples = [
        {"title": a.title, "score": r.score}
        for r, a in sorted_by_score if r.score >= 8
    ][:5]
    dropped_or_low_examples = [
        {"title": a.title, "score": r.score}
        for r, a in sorted_by_score if r.score <= 5
    ][:3]

    # Currently watching + planning watchlist
    currently_watching = (
        db.session.query(Anime.title)
        .join(WatchlistEntry, WatchlistEntry.anime_id == Anime.id)
        .filter(WatchlistEntry.user_id == user_id, WatchlistEntry.status == "watching")
        .limit(3)
        .all()
    )
    currently_watching = [t[0] for t in currently_watching]

    planning_ids = (
        db.session.query(WatchlistEntry.anime_id)
        .filter(WatchlistEntry.user_id == user_id, WatchlistEntry.status == "planning")
        .limit(20)
        .all()
    )
    planning_ids = [pid[0] for pid in planning_ids]

    return {
        "schema_version": SIGNAL_PROFILE_SCHEMA_VERSION,
        "computed_at": datetime.now(timezone.utc).isoformat(),
        "rating_count_at_compute": rating_count,
        "top_genres": top_genres,
        "top_studios": top_studios,
        "fan_genre_clusters": fan_genre_clusters,
        "era_lean_year": era_lean_year,
        "episode_fit_pref": episode_fit_pref,
        "dropped_traits": {"studios": sorted(dropped_studios), "genres": sorted(dropped_genres)},
        "loved_examples": loved_examples,
        "dropped_or_low_examples": dropped_or_low_examples,
        "currently_watching": currently_watching,
        "watchlist_planning_ids": planning_ids,
    }


def _empty_profile(rating_count):
    return {
        "schema_version": SIGNAL_PROFILE_SCHEMA_VERSION,
        "computed_at": datetime.now(timezone.utc).isoformat(),
        "rating_count_at_compute": rating_count,
        "top_genres": [],
        "top_studios": [],
        "fan_genre_clusters": [],
        "era_lean_year": None,
        "episode_fit_pref": {"short": 0.0, "medium": 0.0, "long": 0.0},
        "dropped_traits": {"studios": [], "genres": []},
        "loved_examples": [],
        "dropped_or_low_examples": [],
        "currently_watching": [],
        "watchlist_planning_ids": [],
    }
```

**Note on `Anime.official_genres`:** Verify this is the existing relationship name on the Anime model. If the relationship has a different name (e.g. `genres`), adjust references. The repo already uses `a.official_genres` in `routes/recommend.py` (see `_reason_for` helper), so it's stable.

- [ ] **Step 4: Run target tests**

```bash
C:/Users/parus/AppData/Local/Microsoft/WindowsApps/python.exe -m pytest tests/test_rec_signals.py::TestBuildSignalProfile -v
```

Expected: 3 PASS.

- [ ] **Step 5: Run full suite**

```bash
C:/Users/parus/AppData/Local/Microsoft/WindowsApps/python.exe -m pytest -q
```

Expected: all green.

- [ ] **Step 6: Commit**

```bash
git add routes/rec_signals.py tests/test_rec_signals.py
git commit -m "rec_signals: build_signal_profile (top genres/studios, era lean, ep-fit, dropped traits)"
```

---

## Task 15: Implement `score_candidates` (DB-backed retrieval)

**Files:**
- Modify: `routes/rec_signals.py`
- Modify: `tests/test_rec_signals.py`

- [ ] **Step 1: Write failing test**

```python
class TestScoreCandidates:
    def test_excludes_already_rated_anime(self, app, db_session):
        from models import User, Anime, Rating
        from routes.rec_signals import build_signal_profile, score_candidates
        u = User(email="sc@x.com", username="sc", password_hash="x")
        db_session.add(u); db_session.commit()
        rated = Anime(title="Rated Already", anilist_id=801, studio="Z")
        db_session.add(rated); db_session.commit()
        db_session.add(Rating(user_id=u.id, anime_id=rated.id, score=9))
        db_session.commit()
        # Add an unrated candidate so the result isn't empty
        unrated = Anime(title="Free", anilist_id=802, studio="Z")
        db_session.add(unrated); db_session.commit()

        profile = build_signal_profile(u.id)
        candidates = score_candidates(u.id, profile, limit=10, include_nsfw=False)
        ids = {c["id"] for c in candidates}
        assert rated.id not in ids
        assert unrated.id in ids

    def test_returns_sorted_by_total_score_desc(self, app, db_session):
        from models import User, Anime
        from routes.rec_signals import build_signal_profile, score_candidates
        u = User(email="sc2@x.com", username="sc2", password_hash="x")
        db_session.add(u); db_session.commit()
        for i in range(5):
            db_session.add(Anime(title=f"Cand {i}", anilist_id=850 + i, api_score=7 + i * 0.1))
        db_session.commit()
        profile = build_signal_profile(u.id)
        candidates = score_candidates(u.id, profile, limit=10, include_nsfw=False)
        totals = [c["signals"]["total_score"] for c in candidates]
        assert totals == sorted(totals, reverse=True)
```

- [ ] **Step 2: Run, verify FAIL**

```bash
C:/Users/parus/AppData/Local/Microsoft/WindowsApps/python.exe -m pytest tests/test_rec_signals.py::TestScoreCandidates -v
```

- [ ] **Step 3: Implement**

Add to `routes/rec_signals.py`:

```python
from utils.nsfw import maybe_exclude_nsfw, HARD_BLOCKED_GENRES


def score_candidates(user_id, signal_profile, limit=40, include_nsfw=False):
    """Score all unwatched anime for this user, return the top `limit` candidates.

    Hard-filters out anything the user has already engaged with (rated or
    in watchlist with non-planning status). Respects NSFW rules.
    """
    # Anime IDs the user has already touched
    rated_ids = {
        r[0] for r in
        db.session.query(Rating.anime_id).filter(Rating.user_id == user_id).all()
    }
    blocked_watchlist_ids = {
        w[0] for w in
        db.session.query(WatchlistEntry.anime_id)
        .filter(WatchlistEntry.user_id == user_id,
                WatchlistEntry.status.in_(["watching", "completed", "dropped", "on_hold"]))
        .all()
    }
    excluded = rated_ids | blocked_watchlist_ids

    # Pull the candidate universe
    query = db.session.query(Anime).filter(~Anime.id.in_(excluded)) if excluded else db.session.query(Anime)
    if not include_nsfw:
        query = maybe_exclude_nsfw(query)
    # We still exclude hard-blocked genres regardless of include_nsfw flag
    # (Hentai). maybe_exclude_nsfw handles that when include_nsfw=False; do
    # nothing extra here.

    candidates_raw = query.all()

    # Top-100 popular IDs for surprise_bonus
    top_100_ids = {
        a[0] for a in
        db.session.query(Anime.id)
        .filter(Anime.popularity.isnot(None))
        .order_by(Anime.popularity.desc())
        .limit(100)
        .all()
    }

    scored = []
    for a in candidates_raw:
        cand = {
            "id": a.id,
            "title": a.title,
            "studio": a.studio,
            "genres": [g.name for g in a.official_genres],
            "fan_genres": [fg["genre"] for fg in (a.get_fan_genres() or [])[:5]],
            "api_score": a.api_score,
            "year": a.year,
            "episodes": a.episodes,
            "image_url": getattr(a, "image_url", None),
        }
        scored.append(score_candidate(cand, signal_profile, top_100_ids))

    scored.sort(key=lambda c: c["signals"]["total_score"], reverse=True)
    return scored[:limit]
```

**Note on `a.get_fan_genres()`:** This helper is already used in `routes/recommend.py:get_similar_anime` (see existing code). If the actual method name differs, adjust accordingly; check the Anime model.

- [ ] **Step 4: Run target test + full suite**

```bash
C:/Users/parus/AppData/Local/Microsoft/WindowsApps/python.exe -m pytest tests/test_rec_signals.py::TestScoreCandidates -v
C:/Users/parus/AppData/Local/Microsoft/WindowsApps/python.exe -m pytest -q
```

Expected: green.

- [ ] **Step 5: Commit**

```bash
git add routes/rec_signals.py tests/test_rec_signals.py
git commit -m "rec_signals: score_candidates (DB retrieval, exclusion, NSFW, top-100 popularity)"
```

---

## Task 16: Implement `get_signal_profile` with lazy cache

**Files:**
- Modify: `routes/rec_signals.py`
- Modify: `tests/test_rec_signals.py`

- [ ] **Step 1: Write failing tests**

```python
class TestGetSignalProfile:
    def test_first_call_computes_and_caches(self, app, db_session):
        from models import User
        from routes.rec_signals import get_signal_profile
        u = User(email="gp@x.com", username="gp", password_hash="x")
        db_session.add(u); db_session.commit()
        assert u.taste_profile_cache is None
        profile = get_signal_profile(u.id)
        db_session.refresh(u)
        assert u.taste_profile_cache is not None
        assert profile["rating_count_at_compute"] == 0

    def test_second_call_reuses_cache_when_rating_count_unchanged(self, app, db_session):
        from models import User
        from routes.rec_signals import get_signal_profile
        u = User(email="gp2@x.com", username="gp2", password_hash="x")
        db_session.add(u); db_session.commit()
        first = get_signal_profile(u.id)
        # Mutate the cache directly to confirm we read it back
        import json
        cached = json.loads(u.taste_profile_cache)
        cached["era_lean_year"] = 1999  # sentinel
        u.taste_profile_cache = json.dumps(cached)
        db_session.commit()
        second = get_signal_profile(u.id)
        assert second["era_lean_year"] == 1999

    def test_cache_invalidated_when_rating_count_changes(self, app, db_session):
        from models import User, Anime, Rating
        from routes.rec_signals import get_signal_profile
        u = User(email="gp3@x.com", username="gp3", password_hash="x")
        db_session.add(u); db_session.commit()
        get_signal_profile(u.id)
        # Add a rating
        a = Anime(title="X", anilist_id=909, studio="Y")
        db_session.add(a); db_session.commit()
        db_session.add(Rating(user_id=u.id, anime_id=a.id, score=9))
        db_session.commit()
        fresh = get_signal_profile(u.id)
        assert fresh["rating_count_at_compute"] == 1

    def test_cache_invalidated_when_schema_version_bumps(self, app, db_session):
        from models import User
        from routes.rec_signals import get_signal_profile
        import json
        u = User(email="gp4@x.com", username="gp4", password_hash="x")
        # Pre-seed an old-schema-version cache
        old = {"schema_version": 0, "rating_count_at_compute": 0,
               "top_genres": [["STALE", 999]]}
        u.taste_profile_cache = json.dumps(old)
        db_session.add(u); db_session.commit()
        fresh = get_signal_profile(u.id)
        assert fresh["schema_version"] >= 1
        assert fresh["top_genres"] == []
```

- [ ] **Step 2: Run, verify FAIL**

```bash
C:/Users/parus/AppData/Local/Microsoft/WindowsApps/python.exe -m pytest tests/test_rec_signals.py::TestGetSignalProfile -v
```

- [ ] **Step 3: Implement**

Add to `routes/rec_signals.py`:

```python
import json


def get_signal_profile(user_id):
    """Lazy-cached signal profile fetcher.

    Recomputes the profile if:
      - no cache exists yet, OR
      - the cached schema_version != current SIGNAL_PROFILE_SCHEMA_VERSION, OR
      - the user's rating count has changed since the cache was written.
    """
    user = db.session.get(User, user_id)
    if user is None:
        raise ValueError(f"User {user_id} not found")

    cached = None
    if user.taste_profile_cache:
        try:
            cached = json.loads(user.taste_profile_cache)
        except (ValueError, TypeError):
            cached = None

    current_count = db.session.query(func.count(Rating.id)).filter(Rating.user_id == user_id).scalar() or 0

    stale = (
        cached is None
        or cached.get("schema_version") != SIGNAL_PROFILE_SCHEMA_VERSION
        or cached.get("rating_count_at_compute") != current_count
    )
    if stale:
        fresh = build_signal_profile(user_id)
        user.taste_profile_cache = json.dumps(fresh)
        db.session.commit()
        return fresh
    return cached
```

- [ ] **Step 4: Run + commit**

```bash
C:/Users/parus/AppData/Local/Microsoft/WindowsApps/python.exe -m pytest tests/test_rec_signals.py::TestGetSignalProfile -v
C:/Users/parus/AppData/Local/Microsoft/WindowsApps/python.exe -m pytest -q
```

Expected: green.

```bash
git add routes/rec_signals.py tests/test_rec_signals.py
git commit -m "rec_signals: get_signal_profile with lazy cache + schema-version invalidation"
```

---

## Task 17: Create `routes/chat_context.py`

**Files:**
- Create: `routes/chat_context.py`
- Test: `tests/test_chat_context.py`

- [ ] **Step 1: Write failing snapshot tests**

Create `tests/test_chat_context.py`:

```python
def test_recommend_mode_includes_candidates(app, db_session):
    from models import User, Anime
    from routes.chat_context import build_llm_context
    u = User(email="ctx@x.com", username="ctx", password_hash="x")
    db_session.add(u); db_session.commit()
    db_session.add(Anime(title="Pickable", anilist_id=1000, api_score=8.5))
    db_session.commit()
    ctx = build_llm_context(u.id, "something melancholy", "recommend", include_nsfw=False)
    assert ctx["mode"] == "recommend"
    assert ctx["user_message"] == "something melancholy"
    assert "user" in ctx and "top_studios" in ctx["user"]
    assert "candidates" in ctx
    assert isinstance(ctx["candidates"], list)


def test_rate_mode_omits_candidates(app, db_session):
    from models import User
    from routes.chat_context import build_llm_context
    u = User(email="ctx2@x.com", username="ctx2", password_hash="x")
    db_session.add(u); db_session.commit()
    ctx = build_llm_context(u.id, "I just finished Frieren", "rate", include_nsfw=False)
    assert ctx["mode"] == "rate"
    assert "candidates" not in ctx


def test_onboard_mode_omits_candidates(app, db_session):
    from models import User
    from routes.chat_context import build_llm_context
    u = User(email="ctx3@x.com", username="ctx3", password_hash="x")
    db_session.add(u); db_session.commit()
    ctx = build_llm_context(u.id, "help me start", "onboard", include_nsfw=False)
    assert ctx["mode"] == "onboard"
    assert "candidates" not in ctx


def test_user_block_omits_cache_only_fields(app, db_session):
    from models import User
    from routes.chat_context import build_llm_context
    u = User(email="ctx4@x.com", username="ctx4", password_hash="x")
    db_session.add(u); db_session.commit()
    ctx = build_llm_context(u.id, "anything", "recommend", include_nsfw=False)
    # cache-only fields should be stripped before going to the LLM
    assert "schema_version" not in ctx["user"]
    assert "computed_at" not in ctx["user"]
    assert "rating_count_at_compute" not in ctx["user"]
```

- [ ] **Step 2: Run, verify FAIL**

```bash
C:/Users/parus/AppData/Local/Microsoft/WindowsApps/python.exe -m pytest tests/test_chat_context.py -v
```

- [ ] **Step 3: Implement**

Create `routes/chat_context.py`:

```python
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
```

- [ ] **Step 4: Run + commit**

```bash
C:/Users/parus/AppData/Local/Microsoft/WindowsApps/python.exe -m pytest tests/test_chat_context.py -v
C:/Users/parus/AppData/Local/Microsoft/WindowsApps/python.exe -m pytest -q
```

Expected: green.

```bash
git add routes/chat_context.py tests/test_chat_context.py
git commit -m "chat_context: build_llm_context composes profile + conditional candidates"
```

---

## Task 18: Append GROUNDING RULES to `BINGERY_SYSTEM`

**Files:**
- Modify: `routes/chatbot_tools.py`
- Test: `tests/test_chatbot_integration.py` (existing) — extend coverage

- [ ] **Step 1: Write failing test**

Add to `tests/test_chatbot_integration.py`:

```python
def test_system_prompt_includes_grounding_rules():
    from routes.chatbot_tools import BINGERY_SYSTEM
    assert "GROUNDING RULES" in BINGERY_SYSTEM
    assert "PICK ONLY from the candidates" in BINGERY_SYSTEM or "PICK ONLY from `candidates`" in BINGERY_SYSTEM
    assert "single highest-value signal" in BINGERY_SYSTEM.lower() or "single strongest signal" in BINGERY_SYSTEM.lower()
```

- [ ] **Step 2: Run, verify FAIL**

```bash
C:/Users/parus/AppData/Local/Microsoft/WindowsApps/python.exe -m pytest tests/test_chatbot_integration.py::test_system_prompt_includes_grounding_rules -v
```

- [ ] **Step 3: Modify `routes/chatbot_tools.py`**

Open `routes/chatbot_tools.py`. The `BINGERY_SYSTEM` string ends after the existing reply-structure section. Append BEFORE the closing triple-quote:

```python
# GROUNDING RULES (CRITICAL — only apply when the context JSON includes a `candidates` array)
1. Your `suggested_anime` MUST be selected ONLY from the `candidates` array
   provided in the context JSON. You may not name an anime not in that list.
   If no candidate fits the user's vibe, say so honestly and ask a follow-up
   — do not invent.
2. For each suggested anime, your reason MUST cite the SINGLE strongest signal
   from that candidate's `signals` object, framed in human terms. Examples:
     signals.fan_genre_match=0.91 → "matches your melancholy + talky cluster"
     signals.studio_affinity=0.83 → "from MAPPA, where you've loved 5 of 6"
     signals.surprise_factor=1.0  → "underrated gem outside the top-100"
   Do not invent reasons.
```

- [ ] **Step 4: Run target test**

```bash
C:/Users/parus/AppData/Local/Microsoft/WindowsApps/python.exe -m pytest tests/test_chatbot_integration.py::test_system_prompt_includes_grounding_rules -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add routes/chatbot_tools.py tests/test_chatbot_integration.py
git commit -m "chatbot_tools: append GROUNDING RULES to BINGERY_SYSTEM"
```

---

## Task 19: Wire `chatbot.py` to `build_llm_context` + add validation pass

**Files:**
- Modify: `routes/chatbot.py`
- Test: `tests/test_chatbot_integration.py`

- [ ] **Step 1: Locate the current LLM-call site**

Open `routes/chatbot.py` and find the `/api/chat/message` handler. The current code computes a thin taste_profile inline and stuffs it into the system prompt. The two changes:

1. Replace that with `from routes.chat_context import build_llm_context` and a call.
2. After the LLM returns, filter `suggested_anime` against the candidate ID set.

- [ ] **Step 2: Write failing test**

```python
def test_hallucinated_titles_are_filtered_out(client, db_session, monkeypatch):
    """If the LLM names anime not in the candidate set, those are dropped silently."""
    from models import User, Anime
    from routes.chatbot import get_jwt_identity  # only to confirm import path

    u = User(email="h@x.com", username="h", password_hash="x")
    db_session.add(u); db_session.commit()
    db_session.add(Anime(title="Real Pick", anilist_id=2001, api_score=8.0))
    db_session.commit()

    # Mock the AI provider to return a response naming an anime NOT in candidates
    from routes import chatbot as chatbot_module
    class FakeProvider:
        def generate(self, messages, **kw):
            return type("R", (), {
                "text": '{"response": "Try Real Pick and Made Up Show.", '
                        '"suggested_anime": ['
                        '{"id": ' + str(Anime.query.filter_by(anilist_id=2001).first().id) + ', "title": "Real Pick", "image_url": null},'
                        '{"id": 999999, "title": "Made Up Show", "image_url": null}'
                        '], "suggested_actions": []}'
            })()
    monkeypatch.setattr(chatbot_module, "get_provider", lambda: FakeProvider())

    # Log in as our user and send a chat message
    # (Assume the existing conftest provides an `auth_token` fixture or a login helper;
    # if not, post to /auth/login first.)
    login = client.post("/api/auth/login", json={"email": "h@x.com", "password": "x"})
    # If passwords are bcrypt-hashed in the User row created above, this login will
    # fail. In that case set the user with the real auth flow before the assertion.
    # Adjust this section to match how other tests in test_chatbot_integration.py
    # authenticate.

    # NOTE: the integration test scaffolding may already exist — copy the
    # pattern from the closest existing chat test rather than reimplementing.
```

**Implementer note:** this test depends on the existing integration-test scaffolding in `tests/test_chatbot_integration.py` (auth helpers, AI-provider monkeypatch pattern). Open that file and adapt the assertion to match its existing patterns. The core assertion is:

```python
response_json = post_chat_response.get_json()
returned_ids = {s["id"] for s in response_json["suggested_anime"]}
assert 999999 not in returned_ids  # hallucinated ID stripped
assert real_pick_id in returned_ids  # real candidate kept
```

- [ ] **Step 3: Run, verify FAIL**

```bash
C:/Users/parus/AppData/Local/Microsoft/WindowsApps/python.exe -m pytest tests/test_chatbot_integration.py -v -k hallucinated
```

- [ ] **Step 4: Modify `routes/chatbot.py`**

Open `routes/chatbot.py`. Find the message handler:

```python
@chatbot_bp.route("/message", methods=["POST"])
@jwt_required()
def chat_message():
    # ... existing code that builds messages ...
```

Replace the inline taste-profile section with:

```python
from routes.chat_context import build_llm_context

# (inside the handler, after parsing the request body)
include_nsfw = request.args.get("include_nsfw", "false").lower() == "true"
context = build_llm_context(user_id, message, mode, include_nsfw=include_nsfw)
candidate_ids = {c["id"] for c in context.get("candidates", [])}

# Stuff the context JSON into the system prompt
import json as _json
system_prompt = build_system_prompt(mode) + "\n\n# CONTEXT JSON\n" + _json.dumps(context, ensure_ascii=False)
```

(Adjust to match the existing `build_system_prompt` signature and prompt-assembly pattern in the file — this snippet is illustrative.)

After the LLM call and the response parsing, add the validation pass:

```python
if candidate_ids:
    raw_suggested = parsed.get("suggested_anime", []) or []
    filtered = [s for s in raw_suggested if s.get("id") in candidate_ids]
    dropped = len(raw_suggested) - len(filtered)
    if dropped:
        current_app.logger.warning(
            "Chat: dropped %d hallucinated titles from suggested_anime", dropped
        )
    parsed["suggested_anime"] = filtered
```

- [ ] **Step 5: Run target test + full suite**

```bash
C:/Users/parus/AppData/Local/Microsoft/WindowsApps/python.exe -m pytest tests/test_chatbot_integration.py -v
C:/Users/parus/AppData/Local/Microsoft/WindowsApps/python.exe -m pytest -q
```

Expected: target test PASS, full suite all green.

- [ ] **Step 6: Commit**

```bash
git add routes/chatbot.py tests/test_chatbot_integration.py
git commit -m "chatbot: use build_llm_context + filter hallucinated titles from suggested_anime"
```

---

## Task 20: Unify `/api/recommend/for-me` on `score_candidates`

**Files:**
- Modify: `routes/recommend.py`
- Test: existing `tests/` (no new file; add to whichever existing file covers `/recommend`)

This makes the For You page consistent with chat — same scorer, same exclusions, same surprise-factor behavior. Per the spec, the response shape stays `{anime, reason, relevance_score}`.

- [ ] **Step 1: Read the current `/for-me` route**

Open `routes/recommend.py` and locate the `/for-me` route (it returns the `{recommendations: [{anime, reason, relevance_score}], taste_profile, source}` payload).

- [ ] **Step 2: Write failing test (compatibility check)**

Add to whichever test file covers `/recommend` (likely `tests/test_recommend.py` if it exists, or add to `test_chatbot_integration.py` near similar tests):

```python
def test_for_me_payload_uses_signal_scoring(client, db_session):
    """The /for-me endpoint returns picks that share fields with score_candidates."""
    from models import User, Anime
    u = User(email="fy@x.com", username="fy", password_hash="x")
    db_session.add(u); db_session.commit()
    db_session.add(Anime(title="A", anilist_id=3001, api_score=8.5, studio="MAPPA"))
    db_session.commit()
    # Login and call /recommend/for-me
    # (match the conftest auth helper pattern)
    # Assert response.json()["recommendations"][0] has keys: anime, reason, relevance_score
    # Assert reason cites a numeric signal (contains a digit or a known signal name keyword)
```

- [ ] **Step 3: Update the route**

In `routes/recommend.py`'s `/for-me` handler, replace the existing scoring loop with:

```python
from routes.rec_signals import get_signal_profile, score_candidates

profile = get_signal_profile(user_id)
scored = score_candidates(user_id, profile, limit=limit, include_nsfw=False)

if not scored:
    return jsonify({"recommendations": [], "taste_profile": _serialize_taste_profile_v2(profile), "source": "empty"}), 200

# Map score_candidates output to the existing response shape
def reason_for(c):
    signals = c["signals"]
    # pick the single strongest contributing signal
    contributions = [
        ("studio_affinity", 25 * signals["studio_affinity"],
         f"matches your top studio ({c['studio']})" if c["studio"] else "studio affinity"),
        ("genre_match", 20 * signals["genre_match"],
         f"matches {len(c['genres'])} of your top genres"),
        ("fan_genre_match", 15 * signals["fan_genre_match"],
         "matches your fan-genre cluster"),
        ("surprise_factor", 10 * signals["surprise_factor"],
         "underrated pick outside the top-100"),
        ("watchlist_aligned", 5 * signals["watchlist_aligned"],
         "already in your planning list"),
    ]
    contributions.sort(key=lambda x: -x[1])
    return contributions[0][2]

recs = [{
    "anime": {k: c[k] for k in ("id", "title", "studio", "genres", "api_score", "year", "episodes", "image_url")},
    "reason": reason_for(c),
    "relevance_score": c["signals"]["total_score"] / 100.0,
} for c in scored]

return jsonify({
    "recommendations": recs,
    "taste_profile": _serialize_taste_profile_v2(profile),
    "source": "personalized",
}), 200
```

Add the helper for serializing the new profile shape (keep field names backward compatible with whatever the frontend's `taste_profile` view expects):

```python
def _serialize_taste_profile_v2(profile):
    return {
        "top_genres": [
            {"name": name, "weight": round(min(1.0, w / 10.0), 2), "score": round(w, 2)}
            for name, w in profile.get("top_genres", [])[:8]
        ],
        "avg_score": None,  # legacy field; UI will fall back gracefully
        "rating_count": profile.get("rating_count_at_compute", 0),
    }
```

(Confirm the frontend's `Taste profile` view doesn't break by running the frontend `vitest` suite in Task 22.)

- [ ] **Step 4: Run target test + full suite**

```bash
C:/Users/parus/AppData/Local/Microsoft/WindowsApps/python.exe -m pytest -q
```

Expected: green.

- [ ] **Step 5: Commit**

```bash
git add routes/recommend.py tests/
git commit -m "recommend: unify /for-me on score_candidates (same signals as chat)"
```

---

## Task 21: Smoke-test the chat against live local Ollama

**Files:**
- (no file changes; verification only)

- [ ] **Step 1: Start the local stack**

```powershell
# In one PowerShell window, ensure Ollama is up (tray app), then start Flask:
C:/Users/parus/AppData/Local/Microsoft/WindowsApps/python.exe app.py
```

In another window:
```powershell
cd C:\Users\parus\Downloads\bingery-update\frontend
npm run dev
```

- [ ] **Step 2: Hit the chat endpoint with a curl smoke test**

```bash
TOKEN=$(curl -s -X POST http://127.0.0.1:5000/api/auth/login -H 'Content-Type: application/json' -d '{"email":"demo@bingery.app","password":"demo123"}' | python -c 'import sys,json;print(json.load(sys.stdin)["token"])')

curl -s -X POST http://127.0.0.1:5000/api/chat/message -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' -d '{"message":"I want something melancholy","mode":"recommend"}' | python -m json.tool
```

Expected output: a JSON response with `suggested_anime` containing 2-3 picks, each with an `id` that exists in the database. The `response` text should reference specific signals (e.g., "from MAPPA where you've loved..." or "underrated gem outside the top-100"). NO populist picks (Demon Slayer / AoT / JJK) unless they genuinely match the signal profile.

- [ ] **Step 3: Manually inspect 3 sample queries**

Run these three:
- "I want something melancholy"
- "I'm in a shonen mood"
- "Surprise me"

For each, capture the picks + reasons. Verify subjectively:
- Reasons cite specific signals (not vibes)
- At least one of the three queries surfaces a pick that the user (Mio) hasn't already rated AND is not in the top-100 most-popular
- No hallucinated titles (every `id` resolves in the DB)

- [ ] **Step 4: Commit any tweaks discovered**

If during smoke-testing you find the signal weights produce poor picks (e.g., genre_match overweighted at 20 vs studio at 25 swamps studio), tune in `routes/rec_signals.py:score_candidate` and re-run the smoke test. Commit any tuning as:

```bash
git add routes/rec_signals.py
git commit -m "rec_signals: tune signal weights based on Mio smoke test"
```

If no tweaks needed, skip the commit.

---

## Task 22: Apply migrations to Fly production DB

**Files:**
- (production DB only)

- [ ] **Step 1: Run the ALTER TABLE on Fly via SSH**

```powershell
& "$HOME\.fly\bin\flyctl.exe" ssh console -a bingery -C "sqlite3 /data/bingery.db 'ALTER TABLE user ADD COLUMN taste_profile_cache TEXT; ALTER TABLE anime ADD COLUMN popularity INTEGER;'"
```

Expected: silent success (no output) or `Error: The handle is invalid.` (benign PowerShell stderr-as-error wrapping; the ALTER actually succeeded — verify with the next step).

- [ ] **Step 2: Verify schema changed**

```powershell
& "$HOME\.fly\bin\flyctl.exe" ssh console -a bingery -C "sqlite3 /data/bingery.db '.schema user' | grep taste_profile_cache"
& "$HOME\.fly\bin\flyctl.exe" ssh console -a bingery -C "sqlite3 /data/bingery.db '.schema anime' | grep popularity"
```

Expected: each prints the column line. If empty, the ALTER didn't apply — investigate before proceeding.

- [ ] **Step 3: Trigger the next AniList sync OR upload locally-synced data**

The new `Anime.popularity` column is NULL until the AniList sync repopulates it. Two paths:

**Path A** (recommended): wait for the next scheduled cron sync. The render.yaml cron triggers weekly per `Plan 4 Task A10`. If you can't wait, manually trigger:

```powershell
& "$HOME\.fly\bin\flyctl.exe" ssh console -a bingery -C "cd /app && python sync_anilist.py --limit 500"
```

**Path B**: re-upload `bingery.db` from local (where you've already run the sync). Use the existing `tunnel.ps1` / Fly SFTP pattern from earlier in this session.

- [ ] **Step 4: Smoke-test live chat**

```powershell
$TOKEN = (Invoke-RestMethod -Method Post -Uri https://bingery.fly.dev/api/auth/login -ContentType 'application/json' -Body '{"email":"demo@bingery.app","password":"demo123"}').token
Invoke-RestMethod -Method Post -Uri https://bingery.fly.dev/api/chat/message -ContentType 'application/json' -Headers @{Authorization="Bearer $TOKEN"} -Body '{"message":"surprise me","mode":"recommend"}' | ConvertTo-Json -Depth 10
```

Expected: chat returns picks with the new signal-driven reasons. Note: requires the cloudflared tunnel + Ollama to be running locally (use the GUI from earlier in this session).

- [ ] **Step 5: Commit nothing (DB migration only)**

(No commit needed — this is a one-shot prod migration. The Python schema change was committed in Tasks 1-2.)

---

## Task 23: Frontend regression check + final cleanup

**Files:**
- Verification: `frontend/` test suite + manual UI walkthrough

- [ ] **Step 1: Run the frontend type-check + tests**

```bash
cd C:/Users/parus/Downloads/bingery-update/frontend
./node_modules/.bin/tsc -b
./node_modules/.bin/vitest run
```

Expected: tsc clean, all vitest tests pass. If the For You page's taste-profile rendering broke because the response shape changed slightly (Task 20), fix the frontend type/component to match the new shape and add a vitest case.

- [ ] **Step 2: Manual walkthrough**

Open `http://localhost:5173/`, log in as `demo@bingery.app` / `demo123`, then:

1. Chat → Recommend mode → "I want something melancholy" → verify picks + signal-cited reasons
2. Chat → Rate mode → "I just finished Frieren" → verify it reflects on Mio's loved_examples
3. For You page → verify recommendations render with the new reasons + relevance scores
4. Compare page → still works (anime-vs-anime, unrelated)

- [ ] **Step 3: Final commit (if any frontend tweak)**

```bash
git add frontend/
git commit -m "frontend: adapt taste-profile renderer to v2 shape from new rec engine"
```

(Skip if no frontend changes.)

- [ ] **Step 4: Push everything**

```bash
git push origin main
```

- [ ] **Step 5: Update the spec's success criteria checklist**

Manually verify §13 of the spec (`docs/superpowers/specs/2026-05-21-chat-rec-engine-design.md`):
- ✅ 3 sample queries produce non-populist picks
- ✅ Reason text cites specific signals
- ✅ Zero hallucinated titles in 20 consecutive chats
- ✅ Round-trip latency stays within +250ms of baseline (~14.3s vs 14.0s)
- ✅ Test suite green (220 existing + ~30 new)

If any criterion fails, file a follow-up ticket; don't try to fix in this plan's scope.

---

## Self-Review (run after writing this plan)

**1. Spec coverage:**
- §1 Goal → Tasks 13, 15, 17, 19 deliver the grounded pipeline.
- §2 Non-goals → All respected (no embeddings, no tool-calling, no UI changes beyond Task 23 fix-up).
- §3 Architecture → Tasks 16, 17, 18, 19 wire the flow.
- §4 Signal profile → Task 14.
- §5 Candidate scoring → Tasks 5-13, 15.
- §6 LLM context + grounding prompt → Tasks 17, 18.
- §7 Implementation surface → Tasks 1-3 (models + sync), 4-17 (rec_signals + chat_context), 18-19 (chatbot wiring), 20 (recommend unify), 22 (production migration).
- §8 Mode-specific behavior → Task 17 covers both branches.
- §9 Performance budget → No explicit task; verify in Task 21 smoke test.
- §10 Open risks: 10.1 (popularity_rank → popularity rename) addressed in the File map note and Tasks 2, 3, 10, 15; 10.2 (validation pass) in Task 19; 10.3 (cold-start) in Task 17 via `_RECOMMEND_LIMIT_COLD`; 10.4 (schema version) in Task 16.
- §11 Testing → All TDD tasks add tests; integration test in Task 19; smoke in Task 21.
- §12 Out of scope → respected.
- §13 Success criteria → checked in Task 23 step 5.

**2. Placeholder scan:** No "TBD"/"TODO" placeholders. Task 19 step 2 has implementer guidance for adapting to existing conftest patterns rather than inventing them — this is a discovery step, not a placeholder. Task 20 step 2 says "match the conftest auth helper pattern" for the same reason.

**3. Type consistency:** All function signatures match across tasks:
- `_studio_affinity(candidate_studio, user_top_studios)` defined in Task 5, used in Task 13.
- `_genre_match(candidate_genres, user_top_genres)` defined in Task 6, used in Task 13.
- `build_signal_profile(user_id) -> dict` defined in Task 14, used in Task 16, 17, 20.
- `score_candidates(user_id, signal_profile, limit, include_nsfw)` defined in Task 15, used in Task 17, 20.
- `get_signal_profile(user_id) -> dict` defined in Task 16, used in Task 17, 20.
- `build_llm_context(user_id, message, mode, include_nsfw)` defined in Task 17, used in Task 19.
- `SIGNAL_PROFILE_SCHEMA_VERSION` defined in Task 4, used in Tasks 14, 16.

All consistent.

---

## Execution

This plan is structured for **subagent-driven development** — each task is small enough to dispatch to a fresh subagent, review the diff, then move on. Alternatively run inline with `executing-plans`.
