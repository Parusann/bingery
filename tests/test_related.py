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


def test_normalize_relation_node_carries_is_adult():
    out = AniListClient._normalize_relation_node(
        {"id": 1, "title": {"romaji": "X"}, "isAdult": True}
    )
    assert out["is_adult"] is True
    out = AniListClient._normalize_relation_node({"id": 2, "title": {"romaji": "Y"}})
    assert out["is_adult"] is False


def test_429_responses_are_retried_boundedly(monkeypatch):
    """A persistent 429 must give up after a couple of retries instead of
    recursing forever inside a web worker."""
    client = AniListClient()
    monkeypatch.setattr(client, "_rate_limit", lambda: None)
    monkeypatch.setattr("utils.anilist.time.sleep", lambda s: None)
    calls = {"n": 0}

    class _Resp429:
        status_code = 429
        headers = {"Retry-After": "0"}

        def raise_for_status(self):
            pass

        def json(self):
            return {}

    def fake_post(url, json=None, timeout=None):
        calls["n"] += 1
        return _Resp429()

    monkeypatch.setattr(client.session, "post", fake_post)

    with pytest.raises(Exception):
        client._execute("query { x }")
    assert calls["n"] <= 4


def test_relations_cache_is_bounded(monkeypatch):
    import utils.anilist as al

    al._RELATIONS_CACHE.clear()
    monkeypatch.setattr(al, "RELATIONS_CACHE_MAX", 2)
    client = AniListClient()

    def fake_execute(q, v=None):
        return {
            "Media": {
                "id": v["id"],
                "type": "ANIME",
                "title": {"romaji": "X"},
                "relations": {"edges": []},
            }
        }

    monkeypatch.setattr(client, "_execute", fake_execute)
    for i in (1, 2, 3):
        client.get_anime_relations(i)
    assert len(al._RELATIONS_CACHE) <= 2
    al._RELATIONS_CACHE.clear()


def test_related_endpoint_filters_hard_blocked_entries(client, app, monkeypatch):
    """The franchise strip must apply the hard-block NSFW policy: locally
    Hentai-tagged entries and AniList isAdult nodes never render."""
    from models import db, Anime, Genre

    with app.app_context():
        base = Anime(title="Base Show", anilist_id=500, api_score=8.0)
        bad = Anime(title="Naughty Spinoff", anilist_id=501, api_score=8.0)
        g = Genre(name="Hentai", category="standard")
        bad.official_genres.append(g)
        db.session.add_all([base, bad])
        db.session.commit()
        base_id = base.id

    fake_nodes = {
        500: {"title": "Base Show", "format": "TV", "year": 2020, "month": 1,
              "day": 1, "release_date": "2020-01-01", "image_url": None},
        501: {"title": "Naughty Spinoff", "format": "OVA", "year": 2021, "month": 1,
              "day": 1, "release_date": "2021-01-01", "image_url": None},
        502: {"title": "Remote Adult", "format": "OVA", "year": 2022, "month": 1,
              "day": 1, "release_date": None, "image_url": None, "is_adult": True},
    }
    monkeypatch.setattr("utils.anilist.assemble_franchise", lambda aid, fetch: fake_nodes)

    r = client.get(f"/api/anime/{base_id}/related")
    assert r.status_code == 200
    titles = [x["title"] for x in r.get_json()["related"]]
    assert "Base Show" in titles
    assert "Naughty Spinoff" not in titles  # locally hard-blocked
    assert "Remote Adult" not in titles     # AniList isAdult flag


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
