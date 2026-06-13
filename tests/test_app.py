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
