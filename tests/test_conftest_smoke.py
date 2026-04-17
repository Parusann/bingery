"""Smoke test that the shared fixtures actually run end-to-end."""


def test_auth_headers_fixture_works(auth_headers):
    headers, user = auth_headers
    assert user.username == "tester"
    assert user.email == "tester@example.com"
    assert headers["Authorization"].startswith("Bearer ")
    assert user.id is not None
