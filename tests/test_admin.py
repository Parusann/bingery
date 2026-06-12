"""Tests for the admin sync endpoint's secret check."""


def test_wrong_secret_rejected_via_constant_time_compare(client, monkeypatch):
    """The secret comparison must go through hmac.compare_digest so the
    check is not a timing oracle on the shared secret."""
    monkeypatch.setenv("ADMIN_SYNC_SECRET", "s3cret")
    import routes.admin as admin_module

    calls = []
    real = admin_module.hmac.compare_digest
    monkeypatch.setattr(
        admin_module.hmac,
        "compare_digest",
        lambda a, b: (calls.append(1), real(a, b))[1],
    )

    r = client.post("/api/admin/sync-dub-sources", headers={"X-Admin-Secret": "wrong"})
    assert r.status_code == 401
    assert calls


def test_missing_secret_header_rejected(client, monkeypatch):
    monkeypatch.setenv("ADMIN_SYNC_SECRET", "s3cret")
    r = client.post("/api/admin/sync-dub-sources")
    assert r.status_code == 401


def test_unconfigured_secret_rejects_with_503(client, monkeypatch):
    monkeypatch.delenv("ADMIN_SYNC_SECRET", raising=False)
    r = client.post("/api/admin/sync-dub-sources", headers={"X-Admin-Secret": "x"})
    assert r.status_code == 503
