"""Tests for /api/anilist routes — sync authz, validation, error hygiene."""


def test_sync_requires_admin_secret_not_just_jwt(client, auth_headers, monkeypatch):
    """Catalog mutation must be admin-gated; a regular login is not enough."""
    headers, _user = auth_headers
    monkeypatch.setenv("ADMIN_SYNC_SECRET", "s3cret")
    monkeypatch.setattr("utils.anilist.sync_anime_from_anilist", lambda *a, **k: 0)
    r = client.post("/api/anilist/sync", json={"mode": "popular"}, headers=headers)
    assert r.status_code == 401


def test_sync_accepts_admin_secret(client, monkeypatch):
    monkeypatch.setenv("ADMIN_SYNC_SECRET", "s3cret")
    monkeypatch.setattr("utils.anilist.sync_anime_from_anilist", lambda *a, **k: 7)
    r = client.post(
        "/api/anilist/sync",
        json={"mode": "popular"},
        headers={"X-Admin-Secret": "s3cret"},
    )
    assert r.status_code == 200
    assert r.get_json()["synced"] == 7


def test_sync_rejects_non_numeric_pages_with_400(client, monkeypatch):
    monkeypatch.setenv("ADMIN_SYNC_SECRET", "s3cret")
    monkeypatch.setattr("utils.anilist.sync_anime_from_anilist", lambda *a, **k: 0)
    r = client.post(
        "/api/anilist/sync",
        json={"mode": "popular", "pages": "abc"},
        headers={"X-Admin-Secret": "s3cret"},
    )
    assert r.status_code == 400


def test_sync_seasonal_requires_season_and_year(client, monkeypatch):
    monkeypatch.setenv("ADMIN_SYNC_SECRET", "s3cret")
    monkeypatch.setattr("utils.anilist.sync_anime_from_anilist", lambda *a, **k: 0)
    r = client.post(
        "/api/anilist/sync",
        json={"mode": "seasonal"},
        headers={"X-Admin-Secret": "s3cret"},
    )
    assert r.status_code == 400


def test_search_errors_do_not_leak_exception_text(client, monkeypatch):
    class _Boom:
        def search_anime(self, *a, **k):
            raise Exception("SECRET-INTERNAL-DETAIL")

    monkeypatch.setattr("utils.anilist.AniListClient", lambda: _Boom())
    r = client.get("/api/anilist/search?q=test")
    assert r.status_code == 502
    assert "SECRET-INTERNAL-DETAIL" not in r.get_data(as_text=True)
