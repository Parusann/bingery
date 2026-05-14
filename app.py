"""
Bingery — Flask API + Frontend Server
Run locally:  python app.py
Production:   gunicorn app:app
Seed:         python seed.py
"""

import os
from flask import Flask, jsonify, send_from_directory, request as flask_request
from flask_cors import CORS
from flask_jwt_extended import JWTManager

from config import Config
from models import db


# Serve the new Vite-built frontend from frontend/dist/. If that directory is
# missing (dev before build or CI stage 1) fall back to the legacy static/
# bundle so the server still returns usable HTML.
def _static_root() -> str:
    frontend = os.path.join(os.path.abspath(os.path.dirname(__file__)), "frontend", "dist")
    if os.path.isdir(frontend) and os.path.exists(os.path.join(frontend, "index.html")):
        return frontend
    return os.path.join(os.path.abspath(os.path.dirname(__file__)), "static")


def create_app(config_class=Config):
    root = _static_root()
    app = Flask(__name__, static_folder=root, static_url_path="")
    app.config.from_object(config_class)

    # ── Extensions ────────────────────────────────────────────────────────
    db.init_app(app)
    CORS(app, resources={r"/api/*": {"origins": "*"}})
    JWTManager(app)

    # ── Blueprints ────────────────────────────────────────────────────────
    from routes.auth import auth_bp, bcrypt as auth_bcrypt
    from routes.anime import anime_bp
    from routes.ratings import ratings_bp
    from routes.anilist import anilist_bp
    from routes.chatbot import chatbot_bp
    from routes.recommend import recommend_bp
    from routes.watchlist import watchlist_bp
    from routes.search import search_bp
    from routes.collections import collections_bp
    from routes.stats import stats_bp
    from routes.activity import activity_bp
    from routes.seasonal import seasonal_bp
    from routes.compare import compare_bp
    from routes.schedule import schedule_bp

    auth_bcrypt.init_app(app)
    app.register_blueprint(auth_bp)
    app.register_blueprint(anime_bp)
    app.register_blueprint(ratings_bp)
    app.register_blueprint(anilist_bp)
    app.register_blueprint(chatbot_bp)
    app.register_blueprint(recommend_bp)
    app.register_blueprint(watchlist_bp)
    app.register_blueprint(search_bp)
    app.register_blueprint(collections_bp, url_prefix="/api/collections")
    app.register_blueprint(stats_bp, url_prefix="/api/stats")
    app.register_blueprint(activity_bp, url_prefix="/api/activity")
    app.register_blueprint(seasonal_bp, url_prefix="/api/seasonal")
    app.register_blueprint(compare_bp, url_prefix="/api/compare")
    app.register_blueprint(schedule_bp, url_prefix="/api")

    # ── Health check ──────────────────────────────────────────────────────
    @app.route("/api/health", methods=["GET"])
    def health():
        return jsonify({"status": "ok", "service": "bingery-api"}), 200

    # ── Serve frontend (SPA with fallback) ────────────────────────────────
    @app.route("/", defaults={"path": ""})
    @app.route("/<path:path>")
    def spa(path: str):
        # API routes are handled above; anything else serves the SPA index.
        full = os.path.join(app.static_folder, path)
        if path and os.path.exists(full) and os.path.isfile(full):
            return send_from_directory(app.static_folder, path)
        return send_from_directory(app.static_folder, "index.html")

    # ── Error handlers ────────────────────────────────────────────────────
    @app.errorhandler(404)
    def not_found(e):
        if flask_request.path.startswith("/api/"):
            return jsonify({"error": "Not found."}), 404
        return send_from_directory(app.static_folder, "index.html")

    @app.errorhandler(500)
    def server_error(e):
        return jsonify({"error": "Internal server error."}), 500

    # Create tables on first run
    with app.app_context():
        db.create_all()

    return app


# Create app instance for gunicorn (must be module-level)
app = create_app()

if __name__ == "__main__":
    print("\n  Bingery running at http://localhost:5000")
    print("  Frontend:  http://localhost:5000/")
    print("  API:       http://localhost:5000/api/health")
    print()
    app.run(debug=True, port=5000)
