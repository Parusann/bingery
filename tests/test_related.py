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
