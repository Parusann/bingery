# Related Franchise Strip Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** On the anime detail page, show the whole franchise (seasons, movies, OVAs, specials) as a wrapping poster strip ordered by release date, with the current title highlighted, placed under the Community fan genres section.

**Architecture:** Relations aren't stored locally, so we fetch them live from AniList at view time. A new `GET /api/anime/<id>/related` endpoint runs a bounded breadth-first traversal across AniList franchise relations (cached per-title), maps each related title back to our catalog by `anilist_id`, injects the current title, sorts by release date, and returns a flat list. The frontend renders it as a wrapping grid of poster cards under the fan-genre section, mirroring the existing `/similar` → `useSimilar` → strip pattern.

**Tech Stack:** Flask + SQLAlchemy (backend), AniList GraphQL API, pytest (tests); React + TypeScript + React Query + Tailwind (frontend).

**Spec:** `docs/superpowers/specs/2026-06-01-related-franchise-strip-design.md`

---

## File Structure

**Backend**
- `utils/anilist.py` (modify) — add `RELATIONS_QUERY`, refactor `_request` to delegate to a fragment-free `_execute`, add `_normalize_relations`, `get_anime_relations` (with TTL cache), and the module-level `assemble_franchise` BFS + its constants.
- `routes/anime.py` (modify) — add `GET /<int:anime_id>/related`.
- `tests/test_related.py` (create) — unit tests for `assemble_franchise` + `_normalize_relations` + the fragment-bypass, and route integration tests.

**Frontend**
- `frontend/src/types/api.ts` (modify) — add `RelatedEntry`, `RelatedResponse`.
- `frontend/src/lib/api.ts` (modify) — add `getRelated`.
- `frontend/src/hooks/useAnimeDetail.ts` (modify) — add `useRelated`.
- `frontend/src/features/details/RelatedStrip.tsx` (create) — the wrapping poster strip.
- `frontend/src/features/details/AnimeDetailPage.tsx` (modify) — wire + place the section.

**Key interfaces (defined once, used across tasks)**

`AniListClient.get_anime_relations(anilist_id: int) -> dict` returns:
```python
{
  "self":  {"anilist_id": int, "title": str, "format": str|None,
            "year": int|None, "month": int|None, "day": int|None,
            "release_date": str|None, "image_url": str|None, "type": "ANIME"},
  "edges": [{"relation_type": str, "node": <same shape as "self">}, ...],
}
```

`assemble_franchise(start_id, fetch_relations, max_nodes=25, max_depth=5) -> dict[int, node]`
where `node` is the "self"/"node" shape above, keyed by `anilist_id`.

---

## Task 1: Create feature branch

**Files:** none (git only)

You have been working directly on `main`. Isolate this feature on a branch.

- [ ] **Step 1: Create and switch to the branch**

Run:
```bash
git checkout -b feat/related-franchise-strip
```
Expected: `Switched to a new branch 'feat/related-franchise-strip'`

(If the team prefers to work on `main`, skip this task — but a branch is recommended.)

---

## Task 2: AniList client — fragment-free `_execute` + relations query/normalizer

**Files:**
- Modify: `utils/anilist.py` (`_request` at ~195-216; add constants near the other query constants ~26-117; add methods on `AniListClient`)
- Test: `tests/test_related.py`

The existing `_request` appends `ANIME_FRAGMENT` to *every* query. The relations query must NOT carry that fragment (it would either force fragment bloat onto relation nodes or trigger GraphQL's "unused fragment" error). We extract a fragment-free `_execute` core, keep `_request` behavior identical, and add a self-contained relations query + normalizer.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_related.py` with:

```python
"""Tests for the related-franchise feature (AniList client + endpoint)."""
import pytest

from utils.anilist import AniListClient


class _FakeResponse:
    def __init__(self, payload):
        self._payload = payload
        self.status_code = 200
        self.headers = {}

    def raise_for_status(self):
        pass

    def json(self):
        return self._payload


def test_request_appends_fragment_but_execute_does_not(monkeypatch):
    """_request must carry ANIME_FRAGMENT; _execute must send the raw query."""
    sent = {}
    client = AniListClient()

    def fake_post(url, json=None, timeout=None):
        sent["query"] = json["query"]
        return _FakeResponse({"data": {"ok": True}})

    monkeypatch.setattr(client.session, "post", fake_post)
    monkeypatch.setattr(client, "_rate_limit", lambda: None)

    client._request("query Q { a }")
    assert "fragment AnimeFields" in sent["query"]

    client._execute("query R { b }")
    assert "fragment AnimeFields" not in sent["query"]


def test_normalize_relations_shapes_self_and_edges():
    client = AniListClient()
    media = {
        "id": 100,
        "type": "ANIME",
        "title": {"romaji": "Shingeki no Kyojin", "english": "Attack on Titan"},
        "format": "TV",
        "seasonYear": 2013,
        "startDate": {"year": 2013, "month": 4, "day": 7},
        "coverImage": {"large": "L.jpg", "medium": "M.jpg"},
        "relations": {
            "edges": [
                {
                    "relationType": "SEQUEL",
                    "node": {
                        "id": 200, "type": "ANIME",
                        "title": {"romaji": "S2", "english": None},
                        "format": "TV", "seasonYear": 2017,
                        "startDate": {"year": 2017, "month": 4, "day": 1},
                        "coverImage": {"large": "L2.jpg", "medium": None},
                    },
                },
            ]
        },
    }
    out = client._normalize_relations(media)

    assert out["self"]["anilist_id"] == 100
    assert out["self"]["title"] == "Attack on Titan"   # english preferred
    assert out["self"]["format"] == "TV"
    assert out["self"]["release_date"] == "2013-04-07"
    assert out["self"]["year"] == 2013
    assert out["self"]["image_url"] == "L.jpg"
    assert out["self"]["type"] == "ANIME"

    assert len(out["edges"]) == 1
    edge = out["edges"][0]
    assert edge["relation_type"] == "SEQUEL"
    assert edge["node"]["anilist_id"] == 200
    assert edge["node"]["title"] == "S2"               # romaji fallback
    assert edge["node"]["release_date"] == "2017-04-01"


def test_normalize_relations_handles_missing_dates_and_format():
    client = AniListClient()
    media = {
        "id": 5, "type": "ANIME",
        "title": {"romaji": "OVA", "english": None},
        "format": None, "seasonYear": None,
        "startDate": {"year": None, "month": None, "day": None},
        "coverImage": {"large": None, "medium": None},
        "relations": {"edges": []},
    }
    out = client._normalize_relations(media)
    assert out["self"]["format"] is None
    assert out["self"]["release_date"] is None
    assert out["self"]["year"] is None
    assert out["self"]["image_url"] is None
    assert out["edges"] == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_related.py -v`
Expected: FAIL — `AttributeError: 'AniListClient' object has no attribute '_execute'` (and `_normalize_relations`).

- [ ] **Step 3: Add the relations query constant**

In `utils/anilist.py`, after the `DETAIL_QUERY` block (before `ANIME_FRAGMENT` at ~line 66), add:

```python
# Self-contained relations query — deliberately does NOT use ...AnimeFields,
# so it is sent via _execute() (no fragment append) and keeps the shared
# catalog-sync payload unchanged. Relation nodes carry the fields the
# franchise strip needs: format, dates, cover art, and media type.
RELATIONS_QUERY = """
query ($id: Int) {
  Media(id: $id, type: ANIME) {
    id
    type
    title { romaji english }
    format
    seasonYear
    startDate { year month day }
    coverImage { large medium }
    relations {
      edges {
        relationType
        node {
          id
          type
          title { romaji english }
          format
          seasonYear
          startDate { year month day }
          coverImage { large medium }
        }
      }
    }
  }
}
"""

# AniList MediaFormat -> display label for the franchise strip.
FORMAT_LABELS = {
    "TV": "TV",
    "TV_SHORT": "TV Short",
    "MOVIE": "Movie",
    "SPECIAL": "Special",
    "OVA": "OVA",
    "ONA": "ONA",
    "MUSIC": "Music",
}
```

- [ ] **Step 4: Refactor `_request` to delegate to `_execute`**

Replace the existing `_request` method (currently ~lines 195-216) with:

```python
    def _request(self, query: str, variables: Optional[dict] = None) -> dict:
        # Existing callers rely on the shared AnimeFields fragment being appended.
        return self._execute(query + ANIME_FRAGMENT, variables)

    def _execute(self, full_query: str, variables: Optional[dict] = None) -> dict:
        """Send an already-complete GraphQL document (no fragment appended)."""
        self._rate_limit()
        payload = {"query": full_query}
        if variables:
            payload["variables"] = variables

        response = self.session.post(ANILIST_API, json=payload, timeout=15)

        if response.status_code == 429:
            retry_after = int(response.headers.get("Retry-After", 60))
            print(f"  Rate limited. Waiting {retry_after}s...")
            time.sleep(retry_after)
            return self._execute(full_query, variables)

        response.raise_for_status()
        data = response.json()

        if "errors" in data:
            raise Exception(f"AniList API error: {data['errors']}")

        return data["data"]
```

- [ ] **Step 5: Add the relations normalizer**

Add this method to `AniListClient` (place it right after `_execute`):

```python
    @staticmethod
    def _normalize_relation_node(node: dict) -> dict:
        start = node.get("startDate") or {}
        year, month, day = start.get("year"), start.get("month"), start.get("day")
        release_date = None
        if year and month and day:
            release_date = f"{year:04d}-{month:02d}-{day:02d}"
        title = node.get("title") or {}
        cover = node.get("coverImage") or {}
        return {
            "anilist_id": node.get("id"),
            "title": title.get("english") or title.get("romaji") or "Unknown",
            "format": FORMAT_LABELS.get(node.get("format")),
            "year": year or node.get("seasonYear"),
            "month": month,
            "day": day,
            "release_date": release_date,
            "image_url": cover.get("large") or cover.get("medium"),
            "type": node.get("type"),
        }

    def _normalize_relations(self, media: dict) -> dict:
        """Shape a RELATIONS_QUERY Media object into {self, edges}."""
        edges = []
        for edge in (media.get("relations") or {}).get("edges", []):
            edges.append({
                "relation_type": edge.get("relationType"),
                "node": self._normalize_relation_node(edge.get("node") or {}),
            })
        return {"self": self._normalize_relation_node(media), "edges": edges}
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `pytest tests/test_related.py -v`
Expected: PASS (3 tests).

- [ ] **Step 7: Commit**

```bash
git add utils/anilist.py tests/test_related.py
git commit -m "feat(anilist): add fragment-free relations query and normalizer"
```

---

## Task 3: AniList client — `get_anime_relations` with TTL cache

**Files:**
- Modify: `utils/anilist.py` (add module-level cache near the top constants; add method on `AniListClient`)
- Test: `tests/test_related.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_related.py`:

```python
def test_get_anime_relations_caches_by_id(monkeypatch):
    import utils.anilist as anilist_mod

    anilist_mod._RELATIONS_CACHE.clear()
    calls = {"n": 0}
    client = AniListClient()

    def fake_execute(query, variables=None):
        calls["n"] += 1
        return {"Media": {
            "id": variables["id"], "type": "ANIME",
            "title": {"romaji": "X", "english": None},
            "format": "TV", "seasonYear": 2020,
            "startDate": {"year": 2020, "month": 1, "day": 1},
            "coverImage": {"large": "x.jpg", "medium": None},
            "relations": {"edges": []},
        }}

    monkeypatch.setattr(client, "_execute", fake_execute)

    first = client.get_anime_relations(42)
    second = client.get_anime_relations(42)
    assert first["self"]["anilist_id"] == 42
    assert calls["n"] == 1          # second call served from cache
    assert second == first
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_related.py::test_get_anime_relations_caches_by_id -v`
Expected: FAIL — `AttributeError: module 'utils.anilist' has no attribute '_RELATIONS_CACHE'`.

- [ ] **Step 3: Add the cache + method**

In `utils/anilist.py`, near the top constants (after `RATE_LIMIT_DELAY` at ~line 29), add:

```python
# Per-title relations cache (anilist_id -> (fetched_at, normalized_dict)).
# AniList relations change rarely; the app runs a single gunicorn worker so
# this in-process cache is effectively global.
_RELATIONS_CACHE: dict = {}
RELATIONS_CACHE_TTL = 60 * 60 * 24  # 24 hours
```

Add this method to `AniListClient` (after `_normalize_relations`):

```python
    def get_anime_relations(self, anilist_id: int) -> dict:
        """Fetch + normalize one title's relations, cached for RELATIONS_CACHE_TTL."""
        now = time.time()
        cached = _RELATIONS_CACHE.get(anilist_id)
        if cached and now - cached[0] < RELATIONS_CACHE_TTL:
            return cached[1]
        data = self._execute(RELATIONS_QUERY, {"id": anilist_id})
        result = self._normalize_relations(data["Media"])
        _RELATIONS_CACHE[anilist_id] = (now, result)
        return result
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_related.py::test_get_anime_relations_caches_by_id -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add utils/anilist.py tests/test_related.py
git commit -m "feat(anilist): add cached get_anime_relations"
```

---

## Task 4: `assemble_franchise` bounded BFS

**Files:**
- Modify: `utils/anilist.py` (module-level function + constants, after `AniListClient`)
- Test: `tests/test_related.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_related.py`:

```python
from utils.anilist import assemble_franchise


def _node(aid, rel_type=None, type_="ANIME"):
    n = {"anilist_id": aid, "title": f"T{aid}", "format": "TV",
         "year": 2000 + aid, "month": 1, "day": 1,
         "release_date": f"{2000 + aid:04d}-01-01", "image_url": None, "type": type_}
    return ({"relation_type": rel_type, "node": n} if rel_type else n)


def _graph_fetch(graph):
    """graph: {id: {"self": node, "edges": [edge,...]}} -> fetch callable."""
    def fetch(aid):
        return graph[aid]
    return fetch


def test_assembles_full_chain_across_multiple_hops():
    # 100 <-prequel- 200 -sequel-> 300 -sequel-> 400  ; start mid-chain at 200
    graph = {
        100: {"self": _node(100), "edges": [_node(200, "SEQUEL")]},
        200: {"self": _node(200), "edges": [_node(100, "PREQUEL"), _node(300, "SEQUEL")]},
        300: {"self": _node(300), "edges": [_node(200, "PREQUEL"), _node(400, "SEQUEL")]},
        400: {"self": _node(400), "edges": [_node(300, "PREQUEL")]},
    }
    out = assemble_franchise(200, _graph_fetch(graph))
    assert set(out.keys()) == {100, 200, 300, 400}   # not just one hop


def test_filters_non_franchise_relation_types_and_non_anime():
    graph = {
        1: {"self": _node(1), "edges": [
            _node(2, "SEQUEL"),
            _node(3, "ADAPTATION"),          # excluded relation type
            _node(4, "CHARACTER"),           # excluded relation type
            _node(5, "SEQUEL", type_="MANGA"),  # excluded media type
        ]},
        2: {"self": _node(2), "edges": [_node(1, "PREQUEL")]},
    }
    out = assemble_franchise(1, _graph_fetch(graph))
    assert set(out.keys()) == {1, 2}


def test_respects_max_nodes_cap():
    graph = {i: {"self": _node(i), "edges": [_node(i + 1, "SEQUEL")]} for i in range(1, 50)}
    graph[49] = {"self": _node(49), "edges": []}
    out = assemble_franchise(1, _graph_fetch(graph), max_nodes=3)
    assert len(out) <= 4   # 3 fetched selves + at most one un-fetched stub


def test_handles_cycles_without_infinite_loop():
    graph = {
        1: {"self": _node(1), "edges": [_node(2, "SEQUEL")]},
        2: {"self": _node(2), "edges": [_node(1, "PREQUEL")]},
    }
    out = assemble_franchise(1, _graph_fetch(graph))
    assert set(out.keys()) == {1, 2}


def test_skips_fetch_errors():
    def fetch(aid):
        if aid == 2:
            raise RuntimeError("AniList down")
        return {
            1: {"self": _node(1), "edges": [_node(2, "SEQUEL"), _node(3, "SEQUEL")]},
            3: {"self": _node(3), "edges": [_node(1, "PREQUEL")]},
        }[aid]
    out = assemble_franchise(1, fetch)
    assert 1 in out and 3 in out      # error on node 2 doesn't abort traversal
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_related.py -k assemble -v`
Expected: FAIL — `ImportError: cannot import name 'assemble_franchise'`.

- [ ] **Step 3: Implement `assemble_franchise`**

In `utils/anilist.py`, add at module level after the `AniListClient` class:

```python
# Relation types that belong to the same franchise "chain". Excludes
# ADAPTATION (source manga/novel), SPIN_OFF, SUMMARY (recaps), CHARACTER,
# COMPILATION, CONTAINS, OTHER, SOURCE. Single source of truth — easy to tune.
FRANCHISE_RELATION_TYPES = {"PREQUEL", "SEQUEL", "PARENT", "SIDE_STORY", "ALTERNATIVE"}
FRANCHISE_MAX_NODES = 25
FRANCHISE_MAX_DEPTH = 5


def assemble_franchise(start_id, fetch_relations,
                       max_nodes=FRANCHISE_MAX_NODES, max_depth=FRANCHISE_MAX_DEPTH):
    """Breadth-first traversal across franchise relations.

    AniList only returns direct (one-hop) relations, so we walk the graph to
    gather the whole connected franchise. `fetch_relations(anilist_id)` must
    return {"self": node, "edges": [{"relation_type", "node"}, ...]} (see
    AniListClient.get_anime_relations). Returns {anilist_id: node_dict}.
    Bounded by max_nodes (AniList calls) and max_depth (chain length).
    """
    from collections import deque

    nodes = {}
    queue = deque([(start_id, 0)])
    enqueued = {start_id}
    queries = 0

    while queue and queries < max_nodes:
        current_id, depth = queue.popleft()
        try:
            data = fetch_relations(current_id)
        except Exception:
            continue
        queries += 1
        nodes[current_id] = data["self"]          # authoritative self data
        if depth >= max_depth:
            continue
        for edge in data["edges"]:
            node = edge["node"]
            if node.get("type") != "ANIME":
                continue
            if edge["relation_type"] not in FRANCHISE_RELATION_TYPES:
                continue
            nid = node["anilist_id"]
            nodes.setdefault(nid, node)           # stub display data if unseen
            if nid not in enqueued:
                enqueued.add(nid)
                queue.append((nid, depth + 1))

    return nodes
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_related.py -k assemble -v`
Expected: PASS (5 tests).

- [ ] **Step 5: Commit**

```bash
git add utils/anilist.py tests/test_related.py
git commit -m "feat(anilist): add bounded franchise BFS traversal"
```

---

## Task 5: `GET /api/anime/<id>/related` endpoint

**Files:**
- Modify: `routes/anime.py` (add route after `get_anime` at ~line 94)
- Test: `tests/test_related.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_related.py`:

```python
def _seed_anime(app, anilist_id, title, year=2000, image="local.jpg"):
    from models import db, Anime
    with app.app_context():
        a = Anime(anilist_id=anilist_id, title=title, year=year, image_url=image)
        db.session.add(a)
        db.session.commit()
        return a.id


# Synthetic franchise: 100 (S1) <-> 200 (S2, current) <-> 300 (S3, NOT in catalog)
_ROUTE_GRAPH = {
    100: {"self": _node(100), "edges": [_node(200, "SEQUEL")]},
    200: {"self": _node(200), "edges": [_node(100, "PREQUEL"), _node(300, "SEQUEL")]},
    300: {"self": _node(300), "edges": [_node(200, "PREQUEL")]},
}


def _patch_relations(monkeypatch):
    monkeypatch.setattr(
        "utils.anilist.AniListClient.get_anime_relations",
        lambda self, aid: _ROUTE_GRAPH[aid],
    )


def test_related_endpoint_sorted_with_current_and_catalog_mapping(client, app, monkeypatch):
    _patch_relations(monkeypatch)
    _seed_anime(app, anilist_id=100, title="Season 1", year=2100)
    current_id = _seed_anime(app, anilist_id=200, title="Season 2", year=2101)
    # anilist_id 300 deliberately NOT seeded -> should appear with id=None

    r = client.get(f"/api/anime/{current_id}/related")
    assert r.status_code == 200
    related = r.get_json()["related"]

    ids = [e["anilist_id"] for e in related]
    assert ids == [100, 200, 300]                       # ascending release date

    by_aid = {e["anilist_id"]: e for e in related}
    assert by_aid[200]["is_current"] is True
    assert by_aid[100]["is_current"] is False
    assert by_aid[100]["id"] is not None                # in catalog -> linkable
    assert by_aid[300]["id"] is None                    # not in catalog
    assert by_aid[200]["title"] == "Season 2"           # local title used
    assert by_aid[100]["format"] == "TV"                # label present


def test_related_returns_empty_without_anilist_id(client, app, monkeypatch):
    _patch_relations(monkeypatch)
    from models import db, Anime
    with app.app_context():
        a = Anime(anilist_id=None, title="Standalone", year=2000)
        db.session.add(a)
        db.session.commit()
        aid = a.id
    r = client.get(f"/api/anime/{aid}/related")
    assert r.status_code == 200
    assert r.get_json()["related"] == []


def test_related_returns_empty_on_anilist_error(client, app, monkeypatch):
    def boom(self, aid):
        raise RuntimeError("AniList down")
    monkeypatch.setattr("utils.anilist.AniListClient.get_anime_relations", boom)
    cur = _seed_anime(app, anilist_id=200, title="Season 2")
    r = client.get(f"/api/anime/{cur}/related")
    assert r.status_code == 200
    assert r.get_json()["related"] == []


def test_related_404_for_missing_anime(client):
    r = client.get("/api/anime/999999/related")
    assert r.status_code == 404
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_related.py -k "related_endpoint or related_returns or related_404" -v`
Expected: FAIL — the endpoint tests get Flask's 404 (route not registered) instead of 200 + JSON. (`test_related_404_for_missing_anime` may already pass, since an unknown id 404s either way.)

- [ ] **Step 3: Implement the endpoint**

In `routes/anime.py`, add after the `get_anime` function (after line ~94, before the `/ratings` route):

```python
@anime_bp.route("/<int:anime_id>/related", methods=["GET"])
def get_related(anime_id):
    """Same-franchise entries (seasons/movies/specials) in release order.

    Relations aren't stored locally, so they're fetched live from AniList and
    mapped back to our catalog by anilist_id. On any AniList failure we return
    an empty list (200) so the detail page is never broken by an upstream error.
    """
    anime = db.session.get(Anime, anime_id)
    if not anime:
        return jsonify({"error": "Anime not found."}), 404
    if not anime.anilist_id:
        return jsonify({"related": []}), 200

    from utils.anilist import AniListClient, assemble_franchise

    try:
        client = AniListClient()
        nodes = assemble_franchise(anime.anilist_id, client.get_anime_relations)
    except Exception:
        return jsonify({"related": []}), 200

    # Map AniList ids -> local catalog rows in one query.
    local = {
        a.anilist_id: a
        for a in Anime.query.filter(Anime.anilist_id.in_(list(nodes.keys()))).all()
    }

    items = []
    for aid, node in nodes.items():
        a = local.get(aid)
        year, month, day = node.get("year"), node.get("month"), node.get("day")
        sort_key = (
            year if year is not None else 9999,
            month if month is not None else 99,
            day if day is not None else 99,
            (node.get("title") or "").lower(),
        )
        items.append((sort_key, {
            "anilist_id": aid,
            "id": a.id if a else None,
            "title": (a.title_english or a.title) if a else node.get("title"),
            "format": node.get("format"),
            "release_date": node.get("release_date"),
            "year": year,
            "image_url": (a.image_url if (a and a.image_url) else node.get("image_url")),
            "is_current": aid == anime.anilist_id,
        }))

    items.sort(key=lambda x: x[0])
    return jsonify({"related": [payload for _, payload in items]}), 200
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_related.py -v`
Expected: PASS (all tests in the file).

- [ ] **Step 5: Commit**

```bash
git add routes/anime.py tests/test_related.py
git commit -m "feat(anime): add /anime/<id>/related franchise endpoint"
```

---

## Task 6: Frontend types — `RelatedEntry` + `RelatedResponse`

**Files:**
- Modify: `frontend/src/types/api.ts` (after `SimilarResponse` at ~line 35)

- [ ] **Step 1: Add the types**

In `frontend/src/types/api.ts`, immediately after the `SimilarResponse` interface (line 33-35), add:

```ts
export interface RelatedEntry {
  anilist_id: number;
  id: number | null;          // local Bingery id, or null if not in catalog
  title: string;
  format: string | null;      // "TV" | "Movie" | "OVA" | "Special" | ...
  release_date: string | null; // ISO date if fully known, else null
  year: number | null;
  image_url: string | null;
  is_current: boolean;
}

export interface RelatedResponse {
  related: RelatedEntry[];
}
```

- [ ] **Step 2: Verify it type-checks**

Run: `& 'C:\Users\parus\Downloads\bingery-update\frontend\node_modules\.bin\tsc.cmd' -b 'C:\Users\parus\Downloads\bingery-update\frontend'`
Expected: exit 0 (no errors).

- [ ] **Step 3: Commit**

```bash
git add frontend/src/types/api.ts
git commit -m "feat(types): add RelatedEntry and RelatedResponse"
```

---

## Task 7: Frontend API client + hook

**Files:**
- Modify: `frontend/src/lib/api.ts` (type import at ~line 11; method near `getSimilar` at ~line 128)
- Modify: `frontend/src/hooks/useAnimeDetail.ts` (after `useSimilar` at ~line 18)

- [ ] **Step 1: Import the response type**

In `frontend/src/lib/api.ts`, find the type import that includes `SimilarResponse,` (~line 11) and add `RelatedResponse,` directly beneath it. Example result:
```ts
  SimilarResponse,
  RelatedResponse,
```

- [ ] **Step 2: Add the `getRelated` method**

In `frontend/src/lib/api.ts`, directly after the `getSimilar` line (~line 128):
```ts
  getSimilar: (id: number) => request<SimilarResponse>(`/anime/${id}/similar`),
  getRelated: (id: number) => request<RelatedResponse>(`/anime/${id}/related`),
```

- [ ] **Step 3: Add the `useRelated` hook**

In `frontend/src/hooks/useAnimeDetail.ts`, after the `useSimilar` function (line 12-18), add:
```ts
export function useRelated(id: number | undefined) {
  return useQuery({
    queryKey: ["anime-related", id],
    queryFn: () => api.getRelated(id!),
    enabled: !!id,
  });
}
```

- [ ] **Step 4: Verify it type-checks**

Run: `& 'C:\Users\parus\Downloads\bingery-update\frontend\node_modules\.bin\tsc.cmd' -b 'C:\Users\parus\Downloads\bingery-update\frontend'`
Expected: exit 0.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/lib/api.ts frontend/src/hooks/useAnimeDetail.ts
git commit -m "feat(api): add getRelated client method and useRelated hook"
```

---

## Task 8: `RelatedStrip` component

**Files:**
- Create: `frontend/src/features/details/RelatedStrip.tsx`

- [ ] **Step 1: Create the component**

Create `frontend/src/features/details/RelatedStrip.tsx`:

```tsx
import { Link } from "react-router-dom";
import { cn } from "@/lib/cn";
import type { RelatedEntry } from "@/types/api";

function releaseLabel(e: RelatedEntry): string {
  if (e.release_date) {
    const d = new Date(e.release_date);
    if (!Number.isNaN(d.getTime())) {
      return d.toLocaleDateString(undefined, { year: "numeric", month: "short" });
    }
  }
  return e.year ? String(e.year) : "TBA";
}

export function RelatedStrip({ related }: { related: RelatedEntry[] }) {
  // Nothing meaningful to show for a standalone title (just itself).
  if (related.length <= 1) return null;

  return (
    <section className="mt-10">
      <h2 className="font-display text-2xl mb-4">Watch the rest in order!</h2>
      <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6 gap-4">
        {related.map((e) => {
          const inner = (
            <>
              <div className="relative aspect-[2/3] bg-black/40 overflow-hidden">
                {e.image_url ? (
                  <img
                    src={e.image_url}
                    alt={e.title}
                    loading="lazy"
                    className="w-full h-full object-cover"
                  />
                ) : (
                  <div className="w-full h-full flex items-center justify-center text-text-dim text-xs">
                    No image
                  </div>
                )}
                {e.format ? (
                  <span className="absolute top-2 left-2 px-2 py-0.5 rounded-md bg-black/70 backdrop-blur-md text-[11px] font-medium text-text">
                    {e.format}
                  </span>
                ) : null}
                {e.is_current ? (
                  <span className="absolute top-2 right-2 px-2 py-0.5 rounded-md bg-amber text-black text-[11px] font-semibold">
                    Current
                  </span>
                ) : null}
              </div>
              <div className="p-3">
                <h3 className="text-sm font-semibold line-clamp-2 mb-1">{e.title}</h3>
                <p className="text-xs text-text-muted tabular-nums">{releaseLabel(e)}</p>
              </div>
            </>
          );

          const cardClass = cn(
            "block rounded-lg overflow-hidden border bg-surface transition-colors",
            e.is_current
              ? "border-amber ring-2 ring-amber/50"
              : "border-border hover:border-border-strong"
          );

          // Current title and non-catalog entries are not links.
          if (e.id != null && !e.is_current) {
            return (
              <Link key={e.anilist_id} to={`/anime/${e.id}`} className={cardClass}>
                {inner}
              </Link>
            );
          }
          return (
            <div
              key={e.anilist_id}
              className={cn(cardClass, e.id == null && "opacity-90")}
            >
              {inner}
            </div>
          );
        })}
      </div>
    </section>
  );
}
```

- [ ] **Step 2: Verify it type-checks**

Run: `& 'C:\Users\parus\Downloads\bingery-update\frontend\node_modules\.bin\tsc.cmd' -b 'C:\Users\parus\Downloads\bingery-update\frontend'`
Expected: exit 0.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/features/details/RelatedStrip.tsx
git commit -m "feat(details): add RelatedStrip franchise poster grid"
```

---

## Task 9: Wire the strip into the detail page

**Files:**
- Modify: `frontend/src/features/details/AnimeDetailPage.tsx`

- [ ] **Step 1: Add imports**

In `frontend/src/features/details/AnimeDetailPage.tsx`:
- Change line 4 from:
  ```ts
  import { useAnimeDetail, useSimilar } from "@/hooks/useAnimeDetail";
  ```
  to:
  ```ts
  import { useAnimeDetail, useSimilar, useRelated } from "@/hooks/useAnimeDetail";
  ```
- After line 13 (`import { SimilarStrip } from "./SimilarStrip";`) add:
  ```ts
  import { RelatedStrip } from "./RelatedStrip";
  ```

- [ ] **Step 2: Call the hook**

After line 20 (`const similar = useSimilar(numericId);`) add:
```ts
  const related = useRelated(numericId);
```

- [ ] **Step 3: Render the section under the fan-genre grid**

The fan-genre `<section>` lives in the 2-column grid that closes with `</div>` on line 70, and `<SimilarStrip ... />` is on line 71. Insert the strip between them so it spans full width directly beneath the fan-genre area:

Change:
```tsx
      </div>
      <SimilarStrip similar={similar.data?.similar ?? []} />
    </article>
```
to:
```tsx
      </div>
      <RelatedStrip related={related.data?.related ?? []} />
      <SimilarStrip similar={similar.data?.similar ?? []} />
    </article>
```

- [ ] **Step 4: Verify it type-checks**

Run: `& 'C:\Users\parus\Downloads\bingery-update\frontend\node_modules\.bin\tsc.cmd' -b 'C:\Users\parus\Downloads\bingery-update\frontend'`
Expected: exit 0.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/features/details/AnimeDetailPage.tsx
git commit -m "feat(details): show franchise strip under fan genres"
```

---

## Task 10: Full verification

**Files:** none (verification only)

- [ ] **Step 1: Run the full backend test suite**

Run: `pytest -q`
Expected: all tests pass (existing + new `tests/test_related.py`). No regressions from the `_request`/`_execute` refactor.

- [ ] **Step 2: Frontend type-check**

Run: `& 'C:\Users\parus\Downloads\bingery-update\frontend\node_modules\.bin\tsc.cmd' -b 'C:\Users\parus\Downloads\bingery-update\frontend'`
Expected: exit 0.

- [ ] **Step 3: Manual smoke test**

Start the backend and frontend locally (per the project's dev recipe). Open a multi-entry franchise detail page (e.g. search "Attack on Titan", open Season 1). Confirm:
- A "Watch the rest in order!" section appears under Community fan genres.
- Cards are ordered oldest→newest, show poster + title + format badge + date.
- The current title shows the "Current" badge + accent ring and is not clickable.
- Other in-catalog cards navigate to their detail page on click; the section re-renders for the new title.
- Open a standalone title (e.g. a one-off movie) and confirm the section is absent.

- [ ] **Step 4: Final review**

Run: `git log --oneline feat/related-franchise-strip` and confirm the commit sequence is clean. Leave the branch ready for the user to decide on merge/PR/deploy (do not merge or deploy without the user's go-ahead).

---

## Notes & gotchas

- **Latency:** cold-cache traversal of a large franchise makes sequential AniList calls (`RATE_LIMIT_DELAY = 0.7s` each, capped at `FRANCHISE_MAX_NODES = 25`). The strip loads via its own React Query, so the page renders immediately and the strip fills in. Per-title results are cached for 24h.
- **`_request` refactor:** behavior is preserved exactly — `_request` now delegates to `_execute(query + ANIME_FRAGMENT, ...)`. Run the full suite (Task 10) to confirm no AniList-dependent path regressed.
- **No DB migration:** this feature adds no columns or tables; it reads existing `Anime.anilist_id` only.
- **Tuning:** to include spin-offs/recaps later, edit `FRANCHISE_RELATION_TYPES`. To change traversal breadth, edit `FRANCHISE_MAX_NODES` / `FRANCHISE_MAX_DEPTH`.
