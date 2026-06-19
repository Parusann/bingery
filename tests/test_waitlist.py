"""Tests for the public waitlist endpoint."""
import pytest

from models import db, Waitlist


@pytest.fixture
def sent_waitlist(monkeypatch):
    """Capture confirmation sends instead of emailing. The waitlist route
    imports get_email_provider at module level, so patch it there."""
    sent: list[str] = []

    class _Recorder:
        def send_waitlist_confirmation(self, to_email):
            sent.append(to_email)

    monkeypatch.setattr("routes.waitlist.get_email_provider", lambda: _Recorder())
    return sent


def test_join_waitlist_adds_and_sends(client, app, sent_waitlist):
    r = client.post("/api/waitlist", json={"email": "New@Example.com"})
    assert r.status_code == 200, r.get_json()
    assert r.get_json()["status"] == "added"
    assert sent_waitlist == ["new@example.com"]  # normalized lowercase
    with app.app_context():
        assert (
            db.session.query(Waitlist).filter_by(email="new@example.com").count() == 1
        )


def test_join_waitlist_duplicate_reports_already(client, app, sent_waitlist):
    client.post("/api/waitlist", json={"email": "dupe@example.com"})
    sent_waitlist.clear()
    r = client.post("/api/waitlist", json={"email": "dupe@example.com"})
    assert r.status_code == 200
    assert r.get_json()["status"] == "already"
    assert sent_waitlist == []  # no second email
    with app.app_context():
        assert (
            db.session.query(Waitlist).filter_by(email="dupe@example.com").count() == 1
        )


def test_join_waitlist_rejects_invalid_email(client, sent_waitlist):
    r = client.post("/api/waitlist", json={"email": "not-an-email"})
    assert r.status_code == 400
    assert sent_waitlist == []


def test_join_waitlist_rejects_non_string_email(client, sent_waitlist):
    r = client.post("/api/waitlist", json={"email": 123})
    assert r.status_code == 400
