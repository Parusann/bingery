"""Shared pytest fixtures for Bingery backend tests."""
import os
import pytest

# Ensure tests do not pick up developer env vars.
os.environ.setdefault("AI_PROVIDER", "anthropic")
os.environ.setdefault("ANTHROPIC_API_KEY", "test-key")
os.environ.setdefault("JWT_SECRET_KEY", "test-jwt-secret")
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")


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
        password=bcrypt.generate_password_hash("password").decode("utf-8"),
    )
    db.session.add(user)
    db.session.commit()

    with app.app_context():
        token = create_access_token(identity=str(user.id))

    return {"Authorization": f"Bearer {token}"}, user
