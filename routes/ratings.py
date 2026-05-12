from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from models import db, Anime, Rating, FanGenreVote, User, WatchlistEntry

ratings_bp = Blueprint("ratings", __name__, url_prefix="/api")


# ═══════════════════════════════════════════════════════════════════════════════
# RATINGS (1-10 score)
# ═══════════════════════════════════════════════════════════════════════════════

@ratings_bp.route("/anime/<int:anime_id>/rate", methods=["POST"])
@jwt_required()
def rate_anime(anime_id):
    """
    Rate an anime 1-10. Creates or updates the user's rating.
    Body: { "score": 8, "review": "optional text" }
    """
    user_id = int(get_jwt_identity())
    anime = db.session.get(Anime, anime_id)
    if not anime:
        return jsonify({"error": "Anime not found."}), 404

    data = request.get_json() or {}
    score = data.get("score")
    if not isinstance(score, int) or score < 1 or score > 10:
        return jsonify({"error": "Score must be an integer from 1 to 10."}), 400

    review = (data.get("review") or "")[:2000]

    # Upsert — update if already rated, otherwise create
    rating = db.session.query(Rating).filter_by(user_id=user_id, anime_id=anime_id).first()
    if rating:
        rating.score = score
        rating.review = review
    else:
        rating = Rating(
            user_id=user_id, anime_id=anime_id, score=score, review=review
        )
        db.session.add(rating)

    # Auto-set watchlist status to "completed" when rating
    wl = db.session.query(WatchlistEntry).filter_by(user_id=user_id, anime_id=anime_id).first()
    if not wl:
        wl = WatchlistEntry(user_id=user_id, anime_id=anime_id, status="completed")
        db.session.add(wl)
    elif wl.status == "plan_to_watch":
        wl.status = "completed"

    db.session.commit()

    return jsonify({
        "rating": rating.to_dict(),
        "community_score": anime.get_community_score(),
        "rating_count": anime.get_rating_count(),
    }), 200


@ratings_bp.route("/anime/<int:anime_id>/rate", methods=["DELETE"])
@jwt_required()
def delete_rating(anime_id):
    """Remove the user's rating for an anime."""
    user_id = int(get_jwt_identity())
    rating = db.session.query(Rating).filter_by(user_id=user_id, anime_id=anime_id).first()
    if not rating:
        return jsonify({"error": "No rating found to delete."}), 404

    db.session.delete(rating)
    db.session.commit()

    anime = db.session.get(Anime, anime_id)
    return jsonify({
        "message": "Rating deleted.",
        "community_score": anime.get_community_score(),
        "rating_count": anime.get_rating_count(),
    }), 200


# ═══════════════════════════════════════════════════════════════════════════════
# FAN GENRE VOTES
# ═══════════════════════════════════════════════════════════════════════════════

# All genre tags users can vote on. Includes standard, demographic, thematic,
# and niche categories so users can precisely classify anime.
ALLOWED_FAN_GENRES = [
    # ── Standard genres ───────────────────────────────────────────────────
    "Action", "Adventure", "Comedy", "Drama", "Fantasy", "Horror",
    "Mystery", "Romance", "Sci-Fi", "Slice of Life", "Supernatural",
    "Thriller", "Sports", "Music",
    # ── Demographic ───────────────────────────────────────────────────────
    "Shounen", "Shoujo", "Seinen", "Josei", "Kodomomuke",
    # ── Thematic / sub-genre ──────────────────────────────────────────────
    "Isekai", "Mecha", "Magical Girl", "Harem", "Reverse Harem",
    "Martial Arts", "Military", "Psychological", "Ecchi",
    "Gore", "Survival", "Post-Apocalyptic", "Cyberpunk",
    "Steampunk", "Historical", "Samurai", "Vampire",
    "Zombie", "Demons", "Dark Fantasy", "Mythology",
    "Reincarnation", "Time Travel", "Virtual Reality",
    "Game", "Cooking", "Medical", "Detective",
    # ── Tone / style ──────────────────────────────────────────────────────
    "Wholesome", "Feel-Good", "Tearjerker", "Mind-Bending",
    "Slow Burn", "Fast-Paced", "Episodic", "Satirical",
    "Coming of Age", "Tragic",
    # ── Setting ───────────────────────────────────────────────────────────
    "School", "Workplace", "Space", "Underworld", "Urban",
    "Rural", "Kingdom", "Tournament", "Dungeon",
]


@ratings_bp.route("/anime/<int:anime_id>/fan-genres", methods=["POST"])
@jwt_required()
def vote_fan_genres(anime_id):
    """
    Submit fan genre votes for an anime.
    Replaces all previous votes from this user for this anime.
    Body: { "genres": ["Shounen", "Isekai", "Action", "Dark Fantasy"] }
    """
    user_id = int(get_jwt_identity())
    anime = db.session.get(Anime, anime_id)
    if not anime:
        return jsonify({"error": "Anime not found."}), 404

    data = request.get_json() or {}
    genres = data.get("genres", [])

    if not isinstance(genres, list):
        return jsonify({"error": "genres must be a list of strings."}), 400
    if len(genres) > 15:
        return jsonify({"error": "You can select up to 15 genres per anime."}), 400

    # Validate genre tags
    invalid = [g for g in genres if g not in ALLOWED_FAN_GENRES]
    if invalid:
        return jsonify({
            "error": f"Invalid genre tags: {', '.join(invalid)}",
            "allowed": ALLOWED_FAN_GENRES,
        }), 400

    # Remove previous votes and replace with new ones
    db.session.query(FanGenreVote).filter_by(user_id=user_id, anime_id=anime_id).delete()

    for genre_tag in genres:
        vote = FanGenreVote(
            user_id=user_id, anime_id=anime_id, genre_tag=genre_tag
        )
        db.session.add(vote)

    db.session.commit()

    return jsonify({
        "user_genre_votes": genres,
        "fan_genres": anime.get_fan_genres(),
    }), 200


@ratings_bp.route("/anime/<int:anime_id>/fan-genres", methods=["GET"])
def get_fan_genres(anime_id):
    """Get aggregated fan genre data for an anime."""
    anime = db.session.get(Anime, anime_id)
    if not anime:
        return jsonify({"error": "Anime not found."}), 404

    return jsonify({"fan_genres": anime.get_fan_genres()}), 200


@ratings_bp.route("/fan-genres/allowed", methods=["GET"])
def get_allowed_fan_genres():
    """Return the full list of fan genre tags users can vote on, grouped."""
    grouped = {
        "standard": [g for g in ALLOWED_FAN_GENRES if g in [
            "Action", "Adventure", "Comedy", "Drama", "Fantasy", "Horror",
            "Mystery", "Romance", "Sci-Fi", "Slice of Life", "Supernatural",
            "Thriller", "Sports", "Music",
        ]],
        "demographic": [g for g in ALLOWED_FAN_GENRES if g in [
            "Shounen", "Shoujo", "Seinen", "Josei", "Kodomomuke",
        ]],
        "thematic": [g for g in ALLOWED_FAN_GENRES if g in [
            "Isekai", "Mecha", "Magical Girl", "Harem", "Reverse Harem",
            "Martial Arts", "Military", "Psychological", "Ecchi",
            "Gore", "Survival", "Post-Apocalyptic", "Cyberpunk",
            "Steampunk", "Historical", "Samurai", "Vampire",
            "Zombie", "Demons", "Dark Fantasy", "Mythology",
            "Reincarnation", "Time Travel", "Virtual Reality",
            "Game", "Cooking", "Medical", "Detective",
        ]],
        "tone": [g for g in ALLOWED_FAN_GENRES if g in [
            "Wholesome", "Feel-Good", "Tearjerker", "Mind-Bending",
            "Slow Burn", "Fast-Paced", "Episodic", "Satirical",
            "Coming of Age", "Tragic",
        ]],
        "setting": [g for g in ALLOWED_FAN_GENRES if g in [
            "School", "Workplace", "Space", "Underworld", "Urban",
            "Rural", "Kingdom", "Tournament", "Dungeon",
        ]],
    }
    return jsonify({"genres": grouped, "all": ALLOWED_FAN_GENRES}), 200


# ═══════════════════════════════════════════════════════════════════════════════
# COMBINED: Rate + Tag in one call (convenience endpoint)
# ═══════════════════════════════════════════════════════════════════════════════

@ratings_bp.route("/anime/<int:anime_id>/review", methods=["POST"])
@jwt_required()
def submit_full_review(anime_id):
    """
    Submit a rating AND fan genre votes in a single call.
    Body: { "score": 9, "review": "Masterpiece", "genres": ["Shounen", "Action"] }
    """
    user_id = int(get_jwt_identity())
    anime = db.session.get(Anime, anime_id)
    if not anime:
        return jsonify({"error": "Anime not found."}), 404

    data = request.get_json() or {}

    # ── Score ─────────────────────────────────────────────────────────────
    score = data.get("score")
    if not isinstance(score, int) or score < 1 or score > 10:
        return jsonify({"error": "Score must be an integer from 1 to 10."}), 400

    review_text = (data.get("review") or "")[:2000]

    rating = db.session.query(Rating).filter_by(user_id=user_id, anime_id=anime_id).first()
    if rating:
        rating.score = score
        rating.review = review_text
    else:
        rating = Rating(
            user_id=user_id, anime_id=anime_id, score=score, review=review_text
        )
        db.session.add(rating)

    # ── Fan genres ────────────────────────────────────────────────────────
    genres = data.get("genres", [])
    if isinstance(genres, list) and len(genres) <= 15:
        valid_genres = [g for g in genres if g in ALLOWED_FAN_GENRES]
        db.session.query(FanGenreVote).filter_by(user_id=user_id, anime_id=anime_id).delete()
        for genre_tag in valid_genres:
            db.session.add(
                FanGenreVote(user_id=user_id, anime_id=anime_id, genre_tag=genre_tag)
            )

    # ── Auto-watchlist ────────────────────────────────────────────────────
    wl = db.session.query(WatchlistEntry).filter_by(user_id=user_id, anime_id=anime_id).first()
    status_override = data.get("watch_status")
    if not wl:
        wl = WatchlistEntry(
            user_id=user_id, anime_id=anime_id,
            status=status_override if status_override in ("watching", "completed", "dropped", "on_hold") else "completed",
        )
        db.session.add(wl)
    elif status_override and status_override in ("watching", "completed", "dropped", "on_hold", "plan_to_watch"):
        wl.status = status_override
    elif wl.status == "plan_to_watch":
        wl.status = "completed"

    db.session.commit()

    return jsonify({
        "rating": rating.to_dict(),
        "user_genre_votes": genres,
        "community_score": anime.get_community_score(),
        "rating_count": anime.get_rating_count(),
        "fan_genres": anime.get_fan_genres(),
    }), 200


# ═══════════════════════════════════════════════════════════════════════════════
# USER'S WATCHLIST / HISTORY
# ═══════════════════════════════════════════════════════════════════════════════

@ratings_bp.route("/users/<int:user_id>/ratings", methods=["GET"])
def get_user_ratings(user_id):
    """Get all anime a user has rated, with their scores."""
    user = db.session.get(User, user_id)
    if not user:
        return jsonify({"error": "User not found."}), 404

    page = request.args.get("page", 1, type=int)
    per_page = min(request.args.get("per_page", 50, type=int), 100)

    paginated = (
        Rating.query
        .filter_by(user_id=user_id)
        .order_by(Rating.updated_at.desc())
        .paginate(page=page, per_page=per_page, error_out=False)
    )

    items = []
    for r in paginated.items:
        rd = r.to_dict()
        rd["anime"] = r.anime.to_dict(include_community=False)
        items.append(rd)

    return jsonify({
        "ratings": items,
        "total": paginated.total,
        "page": paginated.page,
        "pages": paginated.pages,
    }), 200


@ratings_bp.route("/me/ratings", methods=["GET"])
@jwt_required()
def get_my_ratings():
    """Shortcut: get the logged-in user's ratings."""
    user_id = int(get_jwt_identity())
    return get_user_ratings(user_id)
