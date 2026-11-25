"""Serve the built app and its real API against disposable browser-test data."""

import logging
import os
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))


def main():
    if not (ROOT / "frontend/dist/index.html").is_file():
        raise SystemExit("Build the frontend with npm run build before running browser tests.")

    logging.getLogger("werkzeug").setLevel(logging.WARNING)
    with TemporaryDirectory(prefix="bingery-e2e-") as temp:
        os.environ.update(
            DATABASE_URL=f"sqlite:///{Path(temp).as_posix()}/browser.db",
            FLASK_ENV="testing",
            BREVO_API_KEY="", ANTHROPIC_API_KEY="", OLLAMA_API_KEY="",
            ADMIN_SYNC_SECRET="", ANIMESCHEDULE_API_KEY="", MAL_CLIENT_ID="",
            EMAIL_PROVIDER="console",
            SIGNUP_OPEN="0",
            SECRET_KEY=os.urandom(32).hex(),
            JWT_SECRET_KEY=os.urandom(32).hex(),
        )
        with patch("dotenv.load_dotenv", return_value=False):
            from app import app
        from models import Anime, Waitlist, db

        # A split-deployment build might point at a remote API. Keep every
        # browser request that can change account data inside this fixture.
        @app.after_request
        def restrict_connections(response):
            response.headers["Content-Security-Policy"] = "connect-src 'self'"
            return response

        with app.app_context():
            db.session.add_all([
                Anime(title="Spirited Away", year=2001, api_score=9, studio="Studio Ghibli",
                      synopsis="A young girl finds herself in a world of spirits."),
                Anime(title="Castle in the Sky", year=1986, api_score=8),
                Waitlist(email="viewer@example.test", status="approved", invite_code="browse-invite"),
            ])
            db.session.commit()

        # Capture the console provider's simulated delivery so Playwright can
        # enter the actual one-time code through the verification form.
        mail_log = Path(os.environ["BINGERY_E2E_MAIL"])
        handler = logging.FileHandler(mail_log, mode="x", encoding="utf-8")
        logger = logging.getLogger("utils.email_provider")
        logger.setLevel(logging.INFO)
        logger.addHandler(handler)
        try:
            app.run(host="127.0.0.1", port=int(os.environ["BINGERY_E2E_PORT"]), use_reloader=False)
        finally:
            logger.removeHandler(handler)
            handler.close()
            mail_log.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
