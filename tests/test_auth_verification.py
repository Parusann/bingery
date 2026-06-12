"""Tests for the email-verification sign-up flow (pending_signup + endpoints)."""
from datetime import datetime, timedelta

from models import db, PendingSignup, User


REGISTER_BODY = {
    "username": "newbie",
    "email": "new@example.com",
    "password": "password123",
}


def _register(client, **overrides):
    return client.post("/api/auth/register", json={**REGISTER_BODY, **overrides})


def test_pending_signup_model_defaults(app):
    row = PendingSignup(
        email="new@example.com",
        username="newbie",
        password_hash="x" * 60,
        code_hash="y" * 60,
        code_expires_at=datetime(2026, 1, 1, 0, 10),
        last_sent_at=datetime(2026, 1, 1, 0, 0),
        created_at=datetime(2026, 1, 1, 0, 0),
    )
    db.session.add(row)
    db.session.commit()

    fetched = db.session.query(PendingSignup).filter_by(email="new@example.com").one()
    assert fetched.attempts_remaining == 5
    assert fetched.resend_count == 0
    assert fetched.display_name is None


def test_register_creates_pending_not_user(client, sent_codes):
    r = _register(client)
    assert r.status_code == 202
    body = r.get_json()
    assert body == {"verification_required": True, "email": "new@example.com"}

    assert db.session.query(User).filter_by(email="new@example.com").first() is None
    pending = db.session.query(PendingSignup).filter_by(email="new@example.com").one()
    assert pending.username == "newbie"
    assert pending.attempts_remaining == 5

    assert len(sent_codes) == 1
    to_email, code = sent_codes[0]
    assert to_email == "new@example.com"
    assert len(code) == 6 and code.isdigit()
    # The code is stored hashed, never in plaintext.
    assert code not in pending.code_hash


def test_register_validation_errors_join_into_string(client, sent_codes):
    r = client.post("/api/auth/register", json={"username": "ab"})
    assert r.status_code == 400
    err = r.get_json()["error"]
    # One string, like every other error body in the API — not a list.
    assert isinstance(err, str)
    assert "Username must be at least 3 characters." in err
    assert "A valid email is required." in err
    assert "Password must be at least 6 characters." in err
    assert sent_codes == []


def test_register_verified_email_conflicts(client, sent_codes, auth_headers):
    # auth_headers creates a real user tester@example.com
    r = _register(client, email="tester@example.com", username="someoneelse")
    assert r.status_code == 409
    assert r.get_json() == {"error": "Email already registered."}


def test_register_taken_username_conflicts(client, sent_codes, auth_headers):
    r = _register(client, username="tester")
    assert r.status_code == 409
    assert r.get_json() == {"error": "Username already taken."}


def test_reregister_overwrites_pending(client, sent_codes, monkeypatch):
    import routes.auth as auth_module

    _register(client)

    # Past the send cooldown, a re-register fully overwrites: new code sent.
    real_now = auth_module._utcnow()
    monkeypatch.setattr(auth_module, "_utcnow", lambda: real_now + timedelta(seconds=61))
    r = _register(client, username="newname", password="otherpass1")
    assert r.status_code == 202

    rows = db.session.query(PendingSignup).filter_by(email="new@example.com").all()
    assert len(rows) == 1
    assert rows[0].username == "newname"
    assert len(sent_codes) == 2
    assert sent_codes[0][1] not in rows[0].code_hash  # plaintext never stored


def test_reregister_within_cooldown_updates_identity_without_send(client, sent_codes):
    _register(client)
    old_code = _code_for(sent_codes)

    r = _register(client, username="newname", password="otherpass1")
    assert r.status_code == 202
    assert len(sent_codes) == 1  # no second email inside the cooldown

    pending = db.session.query(PendingSignup).filter_by(email="new@example.com").one()
    assert pending.username == "newname"

    # The originally emailed code still verifies, and the LATEST password wins.
    assert _verify(client, old_code).status_code == 201
    login = client.post(
        "/api/auth/login",
        json={"email": "new@example.com", "password": "otherpass1"},
    )
    assert login.status_code == 200


def test_register_email_failure_returns_503(client, monkeypatch):
    from utils.email_provider import EmailSendError

    class _Boom:
        def send_verification_code(self, to_email, code):
            raise EmailSendError("brevo down")

    monkeypatch.setattr("routes.auth.get_email_provider", lambda: _Boom())
    r = _register(client)
    assert r.status_code == 503
    assert "verification email" in r.get_json()["error"]
    # Pending row is kept so a retry can resend.
    assert db.session.query(PendingSignup).filter_by(email="new@example.com").count() == 1


def test_register_collision_adopts_winner_code_and_latest_identity(client, sent_codes, monkeypatch):
    """Simultaneous registrations for one email: the loser's commit hits the
    unique constraint. It must answer 202 and apply the latest identity to
    the winner's row, keeping the winner's already-emailed code valid."""
    import routes.auth as auth_module
    from sqlalchemy.exc import IntegrityError

    real_commit = db.session.commit
    state = {"raced": False}

    def racing_commit():
        if state["raced"]:
            return real_commit()
        state["raced"] = True
        # Simulate the concurrent winner: discard the loser's INSERT, commit
        # the winner's row in its place, then fail like the DB would.
        db.session.rollback()
        now = auth_module._utcnow()
        winner = PendingSignup(
            email="new@example.com",
            username="winner",
            password_hash="w" * 60,
            code_hash=auth_module.bcrypt.generate_password_hash("111222").decode("utf-8"),
            code_expires_at=now + auth_module.CODE_TTL,
            last_sent_at=now,
            created_at=now,
        )
        db.session.add(winner)
        real_commit()
        raise IntegrityError(
            "INSERT INTO pending_signup", {},
            Exception("UNIQUE constraint failed: pending_signup.email"),
        )

    monkeypatch.setattr(db.session, "commit", racing_commit)

    r = _register(client)
    assert r.status_code == 202
    assert r.get_json() == {"verification_required": True, "email": "new@example.com"}

    rows = db.session.query(PendingSignup).filter_by(email="new@example.com").all()
    assert len(rows) == 1
    assert rows[0].username == "newbie"  # latest identity applied

    # The winner's emailed code still verifies, with the latest credentials.
    assert _verify(client, "111222").status_code == 201
    login = client.post(
        "/api/auth/login",
        json={"email": "new@example.com", "password": "password123"},
    )
    assert login.status_code == 200


def test_register_purges_stale_pendings(client, sent_codes, monkeypatch):
    import routes.auth as auth_module

    _register(client, email="old@example.com", username="oldtimer")

    real_now = auth_module._utcnow()
    monkeypatch.setattr(
        auth_module, "_utcnow", lambda: real_now + timedelta(hours=25)
    )
    _register(client)  # new@example.com — triggers the lazy purge

    assert db.session.query(PendingSignup).filter_by(email="old@example.com").count() == 0
    assert db.session.query(PendingSignup).filter_by(email="new@example.com").count() == 1


def _code_for(sent_codes, email="new@example.com"):
    return [c for (to, c) in sent_codes if to == email][-1]


def _verify(client, code, email="new@example.com"):
    return client.post("/api/auth/verify", json={"email": email, "code": code})


UNIFORM = {"error": "Invalid or expired code."}


def test_verify_happy_path_creates_user_and_token(client, sent_codes):
    _register(client)
    r = _verify(client, _code_for(sent_codes))
    assert r.status_code == 201
    body = r.get_json()
    assert body["user"]["username"] == "newbie"
    assert body["user"]["email"] == "new@example.com"

    # Pending row consumed; real user exists; token works.
    assert db.session.query(PendingSignup).count() == 0
    assert db.session.query(User).filter_by(email="new@example.com").count() == 1
    me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {body['token']}"})
    assert me.status_code == 200

    # And the password from registration works for login.
    login = client.post(
        "/api/auth/login",
        json={"email": "new@example.com", "password": "password123"},
    )
    assert login.status_code == 200


def test_verify_wrong_code_decrements_attempts(client, sent_codes):
    _register(client)
    right = _code_for(sent_codes)
    wrong = "000000" if right != "000000" else "000001"

    r = _verify(client, wrong)
    assert r.status_code == 400
    assert r.get_json() == UNIFORM
    pending = db.session.query(PendingSignup).one()
    assert pending.attempts_remaining == 4

    # The right code still works while attempts remain.
    assert _verify(client, right).status_code == 201


def test_concurrent_wrong_attempts_do_not_lose_decrements(client, sent_codes, monkeypatch):
    """Two wrong-code requests racing: each must burn one attempt even when
    the second SELECTed before the first committed (lost-update guard)."""
    import routes.auth as auth_module

    _register(client)
    right = _code_for(sent_codes)
    wrong = "000000" if right != "000000" else "000001"

    real_check = auth_module.bcrypt.check_password_hash

    def racing_check(pw_hash, pw):
        # A concurrent wrong attempt lands between this request's SELECT and
        # its decrement: a SQL-side decrement the ORM snapshot doesn't see.
        db.session.query(PendingSignup).filter_by(email="new@example.com").update(
            {PendingSignup.attempts_remaining: PendingSignup.attempts_remaining - 1},
            synchronize_session=False,
        )
        return real_check(pw_hash, pw)

    monkeypatch.setattr(auth_module.bcrypt, "check_password_hash", racing_check)

    r = _verify(client, wrong)
    assert r.status_code == 400
    pending = db.session.query(PendingSignup).one()
    assert pending.attempts_remaining == 3  # 5 - concurrent(1) - this request(1)


def test_verify_attempts_exhaustion_blocks_even_correct_code(client, sent_codes):
    _register(client)
    right = _code_for(sent_codes)
    wrong = "000000" if right != "000000" else "000001"

    for _ in range(5):
        assert _verify(client, wrong).status_code == 400
    # Correct code is now dead too — must resend.
    r = _verify(client, right)
    assert r.status_code == 400
    assert r.get_json() == UNIFORM
    assert db.session.query(User).count() == 0


def test_verify_expired_code(client, sent_codes, monkeypatch):
    import routes.auth as auth_module

    _register(client)
    right = _code_for(sent_codes)
    real_now = auth_module._utcnow()
    monkeypatch.setattr(auth_module, "_utcnow", lambda: real_now + timedelta(minutes=11))

    r = _verify(client, right)
    assert r.status_code == 400
    assert r.get_json() == UNIFORM


def test_verify_unknown_email_uniform(client):
    r = _verify(client, "123456", email="nobody@example.com")
    assert r.status_code == 400
    assert r.get_json() == UNIFORM


def test_verify_unknown_email_burns_dummy_bcrypt_check(client, monkeypatch):
    """Anti-timing-oracle: the unknown-email path must cost one bcrypt check
    like the wrong-code path, so response timing doesn't reveal whether a
    pending signup exists for the email."""
    import routes.auth as auth_module

    calls = []
    real = auth_module.bcrypt.check_password_hash
    monkeypatch.setattr(
        auth_module.bcrypt,
        "check_password_hash",
        lambda pw_hash, pw: (calls.append(pw_hash), real(pw_hash, pw))[1],
    )
    r = _verify(client, "123456", email="nobody@example.com")
    assert r.status_code == 400
    assert r.get_json() == UNIFORM
    assert len(calls) == 1


def test_verify_username_race_returns_409(client, sent_codes, app):
    """Someone claims the username between register and verify."""
    from flask_bcrypt import Bcrypt

    _register(client)
    other = User(
        username="newbie",
        email="other@example.com",
        password_hash=Bcrypt(app).generate_password_hash("pw123456").decode("utf-8"),
    )
    db.session.add(other)
    db.session.commit()

    r = _verify(client, _code_for(sent_codes))
    assert r.status_code == 409
    assert r.get_json() == {"error": "Username already taken."}


def _resend(client, email="new@example.com"):
    return client.post("/api/auth/resend", json={"email": email})


def test_resend_within_cooldown_is_silent_noop(client, sent_codes):
    _register(client)
    r = _resend(client)
    assert r.status_code == 200
    assert r.get_json() == {"ok": True}
    assert len(sent_codes) == 1  # nothing new sent


def test_resend_after_cooldown_issues_new_code(client, sent_codes, monkeypatch):
    import routes.auth as auth_module

    _register(client)
    old_code = _code_for(sent_codes)
    # burn two attempts so we can see the reset
    wrong = "000000" if old_code != "000000" else "000001"
    _verify(client, wrong)

    real_now = auth_module._utcnow()
    monkeypatch.setattr(auth_module, "_utcnow", lambda: real_now + timedelta(seconds=61))

    assert _resend(client).status_code == 200
    assert len(sent_codes) == 2
    new_code = _code_for(sent_codes)

    pending = db.session.query(PendingSignup).one()
    assert pending.attempts_remaining == 5
    assert pending.resend_count == 1

    # Old code dead, new code works.
    assert _verify(client, old_code).status_code == 400 or old_code == new_code
    assert _verify(client, new_code).status_code == 201


def test_resend_cap_at_five(client, sent_codes, monkeypatch):
    import routes.auth as auth_module

    _register(client)
    real_now = auth_module._utcnow()
    for i in range(1, 8):
        monkeypatch.setattr(
            auth_module, "_utcnow",
            lambda offset=i: real_now + timedelta(seconds=61 * offset),
        )
        assert _resend(client).status_code == 200

    pending = db.session.query(PendingSignup).one()
    assert pending.resend_count == 5
    assert len(sent_codes) == 1 + 5  # initial + 5 resends, then capped


def test_resend_unknown_email_uniform_200(client, sent_codes):
    r = _resend(client, email="nobody@example.com")
    assert r.status_code == 200
    assert r.get_json() == {"ok": True}
    assert sent_codes == []


def test_resend_unknown_email_burns_dummy_hash(client, monkeypatch):
    """Anti-timing-oracle: the no-pending path must do the same bcrypt work
    as a real resend (the outbound email's latency stays unavoidable)."""
    import routes.auth as auth_module

    calls = []
    real = auth_module.bcrypt.generate_password_hash
    monkeypatch.setattr(
        auth_module.bcrypt,
        "generate_password_hash",
        lambda pw: (calls.append(pw), real(pw))[1],
    )
    r = _resend(client, email="nobody@example.com")
    assert r.status_code == 200
    assert r.get_json() == {"ok": True}
    assert len(calls) == 1


def test_resend_cooldown_noop_burns_dummy_hash(client, sent_codes, monkeypatch):
    """The silent cooldown no-op must cost the same bcrypt work as the
    no-pending path, so the two stay indistinguishable by timing."""
    import routes.auth as auth_module

    _register(client)

    calls = []
    real = auth_module.bcrypt.generate_password_hash
    monkeypatch.setattr(
        auth_module.bcrypt,
        "generate_password_hash",
        lambda pw: (calls.append(pw), real(pw))[1],
    )
    r = _resend(client)  # within the 60s cooldown → silent no-op
    assert r.status_code == 200
    assert len(calls) == 1
    assert len(sent_codes) == 1  # still no new email


def test_resend_send_failure_keeps_old_code_valid(client, sent_codes, monkeypatch):
    import routes.auth as auth_module
    from utils.email_provider import EmailSendError

    _register(client)
    old_code = _code_for(sent_codes)

    real_now = auth_module._utcnow()
    monkeypatch.setattr(auth_module, "_utcnow", lambda: real_now + timedelta(seconds=61))

    class _Boom:
        def send_verification_code(self, to_email, code):
            raise EmailSendError("down")

    monkeypatch.setattr("routes.auth.get_email_provider", lambda: _Boom())
    r = _resend(client)
    assert r.status_code == 200
    assert r.get_json() == {"ok": True}

    # Rollback undid all state changes: no budget burned, no cooldown started.
    pending = db.session.query(PendingSignup).one()
    assert pending.resend_count == 0
    assert pending.attempts_remaining == 5

    # The original code still verifies (clock is +61s, well inside the 10-min TTL).
    assert _verify(client, old_code).status_code == 201
