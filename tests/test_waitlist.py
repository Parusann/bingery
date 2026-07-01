"""Tests for the public waitlist endpoint."""
import pytest

from models import db, Waitlist


class _Recorder:
    """Capture sends instead of emailing."""

    def __init__(self):
        self.confirmations: list[str] = []
        self.owner_alerts: list[str] = []

    def send_waitlist_confirmation(self, to_email):
        self.confirmations.append(to_email)

    def send_waitlist_owner_alert(self, signup_email):
        self.owner_alerts.append(signup_email)


@pytest.fixture
def waitlist_recorder(monkeypatch):
    """The waitlist route imports get_email_provider at module level, so
    patch it there."""
    recorder = _Recorder()
    monkeypatch.setattr("routes.waitlist.get_email_provider", lambda: recorder)
    return recorder


@pytest.fixture
def sent_waitlist(waitlist_recorder):
    return waitlist_recorder.confirmations


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


def test_join_waitlist_sends_owner_alert(client, waitlist_recorder):
    r = client.post("/api/waitlist", json={"email": "New@Example.com"})
    assert r.status_code == 200, r.get_json()
    assert waitlist_recorder.owner_alerts == ["new@example.com"]


def test_join_waitlist_duplicate_sends_no_owner_alert(client, waitlist_recorder):
    client.post("/api/waitlist", json={"email": "dupe@example.com"})
    waitlist_recorder.owner_alerts.clear()
    r = client.post("/api/waitlist", json={"email": "dupe@example.com"})
    assert r.get_json()["status"] == "already"
    assert waitlist_recorder.owner_alerts == []


def test_join_waitlist_survives_owner_alert_failure(client, app, waitlist_recorder):
    def boom(signup_email):
        raise RuntimeError("owner alert failed")

    waitlist_recorder.send_waitlist_owner_alert = boom
    r = client.post("/api/waitlist", json={"email": "ok@example.com"})
    assert r.status_code == 200
    assert r.get_json()["status"] == "added"
    assert waitlist_recorder.confirmations == ["ok@example.com"]
    with app.app_context():
        assert (
            db.session.query(Waitlist).filter_by(email="ok@example.com").count() == 1
        )


def test_join_waitlist_survives_provider_construction_failure(
    client, app, monkeypatch
):
    """A misconfigured EMAIL_PROVIDER raises in the factory itself; the
    recorded signup must still answer 200, not 500."""

    def boom():
        raise ValueError("Unknown EMAIL_PROVIDER: 'brvo'")

    monkeypatch.setattr("routes.waitlist.get_email_provider", boom)
    r = client.post("/api/waitlist", json={"email": "cfg@example.com"})
    assert r.status_code == 200
    assert r.get_json()["status"] == "added"
    with app.app_context():
        assert (
            db.session.query(Waitlist).filter_by(email="cfg@example.com").count() == 1
        )


def test_join_waitlist_owner_alert_sent_even_if_confirmation_fails(
    client, waitlist_recorder
):
    def boom(to_email):
        raise RuntimeError("confirmation failed")

    waitlist_recorder.send_waitlist_confirmation = boom
    r = client.post("/api/waitlist", json={"email": "ok2@example.com"})
    assert r.status_code == 200
    assert waitlist_recorder.owner_alerts == ["ok2@example.com"]
