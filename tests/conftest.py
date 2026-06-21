"""Shared pytest fixtures for Bingery backend tests."""
import os
import pytest

# Ensure tests do not pick up developer env vars.
os.environ.setdefault("AI_PROVIDER", "anthropic")
os.environ.setdefault("ANTHROPIC_API_KEY", "test-key")
os.environ.setdefault("JWT_SECRET_KEY", "test-jwt-secret")
# Force the test database UNCONDITIONALLY. setdefault would leave a real
# DATABASE_URL from the developer's shell in place, and the per-test
# config override below is a no-op (the engine is already bound at
# create_app() time) — so without this, db.drop_all() in the teardown
# could wipe a real database.
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
# Signups are open in tests unless a test explicitly sets this.
os.environ.pop("SIGNUP_INVITE_CODE", None)


@pytest.fixture
def app():
    from app import create_app
    from models import db

    flask_app = create_app()
    flask_app.config.update(
        TESTING=True,
        SQLALCHEMY_DATABASE_URI="sqlite:///:memory:",
        JWT_SECRET_KEY="test-jwt-secret",
    )

    with flask_app.app_context():
        # Hard safety net: never create/drop tables against a non-memory DB
        # (the bound engine, not just config, is what drop_all() uses).
        bound_uri = str(db.engine.url)
        assert ":memory:" in bound_uri, (
            f"refusing to run tests against non-memory database: {bound_uri}"
        )
        db.create_all()
        yield flask_app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def auth_headers(app):
    """Return headers with a JWT for a fresh test user."""
    from flask_jwt_extended import create_access_token
    from flask_bcrypt import Bcrypt
    from models import db, User

    bcrypt = Bcrypt(app)
    user = User(
        username="tester",
        email="tester@example.com",
        password_hash=bcrypt.generate_password_hash("password").decode("utf-8"),
    )
    db.session.add(user)
    db.session.commit()

    with app.app_context():
        token = create_access_token(identity=str(user.id))

    return {"Authorization": f"Bearer {token}"}, user


@pytest.fixture
def sent_codes(monkeypatch):
    """Capture (to_email, code) instead of sending real email.

    routes/auth.py imports get_email_provider at module level, so patch the
    name in that namespace.
    """
    sent: list[tuple[str, str]] = []

    class _Recorder:
        def send_verification_code(self, to_email, code):
            sent.append((to_email, code))

    monkeypatch.setattr("routes.auth.get_email_provider", lambda: _Recorder())
    return sent
