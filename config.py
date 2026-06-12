"""Flask application config.

All secrets read from environment variables. In production
(`FLASK_ENV=production`) the app refuses to boot with dev-default
secrets — that's the safety net before public deployment.
"""
import os
import sys
from datetime import timedelta

BASE_DIR = os.path.abspath(os.path.dirname(__file__))

# Sentinel defaults; production startup refuses to use these.
_DEV_SECRET_KEY = "bingery-dev-secret-key-change-in-production"
_DEV_JWT_SECRET = "bingery-jwt-secret-change-in-production"


def _split_origins(raw: str | None) -> list[str]:
    """Parse CORS_ORIGINS as comma-separated list. Empty/None → ['*']."""
    if not raw:
        return ["*"]
    parts = [p.strip() for p in raw.split(",") if p.strip()]
    return parts or ["*"]


def _is_production() -> bool:
    env = (os.environ.get("FLASK_ENV") or "").strip().lower()
    if env:
        return env in ("production", "prod")
    # Fail closed on Fly: FLY_APP_NAME is always set in the runtime, so a
    # dropped FLASK_ENV line can't silently disable the boot guards.
    return bool(os.environ.get("FLY_APP_NAME"))


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", _DEV_SECRET_KEY)

    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL", f"sqlite:///{os.path.join(BASE_DIR, 'bingery.db')}"
    )
    # Render/Heroku-style postgres:// → SQLAlchemy postgresql:// fixup.
    if SQLALCHEMY_DATABASE_URI and SQLALCHEMY_DATABASE_URI.startswith("postgres://"):
        SQLALCHEMY_DATABASE_URI = SQLALCHEMY_DATABASE_URI.replace(
            "postgres://", "postgresql://", 1
        )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    JWT_SECRET_KEY = os.environ.get("JWT_SECRET_KEY", _DEV_JWT_SECRET)
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(days=7)

    ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")

    # Email verification (sign-up codes). 'console' logs the code (dev);
    # 'brevo' sends via the Brevo HTTP API (production).
    EMAIL_PROVIDER = (os.environ.get("EMAIL_PROVIDER") or "console").strip().lower()
    BREVO_API_KEY = os.environ.get("BREVO_API_KEY", "")
    EMAIL_FROM = os.environ.get("EMAIL_FROM", "")

    # Frontend origins allowed to call /api/*. Comma-separated. Default '*'
    # is fine for local dev; production MUST set this to the Pages origin.
    CORS_ORIGINS = _split_origins(os.environ.get("CORS_ORIGINS"))

    # Production safety guards — refuse to start with dev secrets exposed.
    if _is_production():
        problems: list[str] = []
        if SECRET_KEY == _DEV_SECRET_KEY:
            problems.append("SECRET_KEY is unset (still the dev default)")
        if JWT_SECRET_KEY == _DEV_JWT_SECRET:
            problems.append("JWT_SECRET_KEY is unset (still the dev default)")
        if "*" in CORS_ORIGINS:
            problems.append(
                "CORS_ORIGINS is '*' — set it to your Cloudflare Pages origin"
            )
        if EMAIL_PROVIDER != "brevo":
            problems.append(
                "EMAIL_PROVIDER must be 'brevo' in production (console would "
                "log verification codes instead of emailing them)"
            )
        elif not BREVO_API_KEY or not EMAIL_FROM:
            problems.append(
                "BREVO_API_KEY and EMAIL_FROM must be set when EMAIL_PROVIDER=brevo"
            )
        if problems:
            sys.stderr.write(
                "FATAL: production safety checks failed:\n"
                + "\n".join(f"  - {p}" for p in problems)
                + "\nSet the corresponding env vars before deploying.\n"
            )
            raise SystemExit(2)
