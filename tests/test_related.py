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
