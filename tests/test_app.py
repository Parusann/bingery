"""Tests for app-level routing: the SPA catch-all must not swallow
unknown /api/* requests into a 200 index.html response."""


def test_unknown_api_route_returns_json_404(client):
    r = client.get("/api/this-route-does-not-exist")
    assert r.status_code == 404
    assert r.get_json() is not None
    assert "error" in r.get_json()


def test_unknown_api_post_route_returns_404_not_index(client):
    r = client.post("/api/nope", json={})
    assert r.status_code in (404, 405)
    # Must be JSON, never the SPA shell.
    assert r.get_json() is not None


def test_frontend_deep_link_and_missing_asset_are_distinct(tmp_path, monkeypatch):
    import app as app_module

    monkeypatch.setattr(app_module, "_static_root", lambda: str(tmp_path))
    client = app_module.create_app().test_client()
    assert client.get("/discover").status_code == 503
    assert client.get("/api/health").status_code == 200

    (tmp_path / "index.html").write_text("<title>Bingery</title>")
    assets = tmp_path / "assets"
    assets.mkdir()
    (assets / "app.js").write_text("export default 42;")
    assert client.get("/anime/42").get_data(as_text=True) == "<title>Bingery</title>"
    assert client.get("/assets/app.js").get_data(as_text=True) == "export default 42;"
    assert client.get("/assets/stale.js").status_code == 404
    assert client.get("/icon.png").status_code == 404
    assert client.get("/api").status_code == 404 and client.get("/api").is_json
