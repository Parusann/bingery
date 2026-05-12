from datetime import datetime, timezone
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

# ─── Association table: official genres ↔ anime ─────────────────────────────

anime_genres = db.Table(
    "anime_genres",
    db.Column("anime_id", db.Integer, db.ForeignKey("anime.id"), primary_key=True),
    db.Column("genre_id", db.Integer, db.ForeignKey("genre.id"), primary_key=True),
)


# ─── Genre (official, from API sources like MAL / AniList) ──────────────────

class Genre(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(60), unique=True, nullable=False)
    # 'standard' = MAL/AniList genre, 'demographic' = shounen/seinen/etc,
    # 'theme' = isekai/mecha/etc, 'setting' = school/space/etc
    category = db.Column(db.String(30), nullable=False, default="standard")

    def to_dict(self):
        return {"id": self.id, "name": self.name, "category": self.category}


# ─── User ────────────────────────────────────────────────────────────────────

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(128), nullable=False)
    avatar_url = db.Column(db.String(300), default=None)
    bio = db.Column(db.String(500), default="")
    created_at = db.Column(
        db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc)
    )

    # Relationships
    ratings = db.relationship("Rating", backref="user", lazy="dynamic")
    fan_genre_votes = db.relationship("FanGenreVote", backref="user", lazy="dynamic")

    def to_dict(self, include_stats=False):
        data = {
            "id": self.id,
            "username": self.username,
            "email": self.email,
            "avatar_url": self.avatar_url,
            "bio": self.bio,
            "created_at": self.created_at.isoformat(),
        }
        if include_stats:
            data["total_ratings"] = self.ratings.count()
            data["total_genre_votes"] = self.fan_genre_votes.count()
            data["average_score"] = (
                db.session.query(db.func.avg(Rating.score))
                .filter(Rating.user_id == self.id)
                .scalar()
            )
            if data["average_score"]:
                data["average_score"] = round(float(data["average_score"]), 1)
        return data


# ─── Anime ───────────────────────────────────────────────────────────────────

class Anime(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    mal_id = db.Column(db.Integer, unique=True, nullable=True, index=True)
    anilist_id = db.Column(db.Integer, unique=True, nullable=True, index=True)
    title = db.Column(db.String(300), nullable=False, index=True)
    title_english = db.Column(db.String(300), nullable=True)
    title_japanese = db.Column(db.String(300), nullable=True)
    synopsis = db.Column(db.Text, default="")
    api_score = db.Column(db.Float, nullable=True)  # score from MAL/AniList
    year = db.Column(db.Integer, nullable=True)
    season = db.Column(db.String(20), nullable=True)  # spring, summer, fall, winter
    episodes = db.Column(db.Integer, nullable=True)
    studio = db.Column(db.String(200), nullable=True)
    image_url = db.Column(db.String(500), nullable=True)
    banner_url = db.Column(db.String(500), nullable=True)
    status = db.Column(db.String(50), default="Unknown")  # Airing, Completed, Upcoming
    source = db.Column(db.String(50), nullable=True)  # Manga, Light Novel, Original, etc
    created_at = db.Column(
        db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    updated_at = db.Column(
        db.DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    official_genres = db.relationship("Genre", secondary=anime_genres, backref="anime_list")
    ratings = db.relationship("Rating", backref="anime", lazy="dynamic")
    fan_genre_votes = db.relationship("FanGenreVote", backref="anime", lazy="dynamic")

    def get_community_score(self):
        """Average score from Bingery users (1-10 scale)."""
        avg = (
            db.session.query(db.func.avg(Rating.score))
            .filter(Rating.anime_id == self.id)
            .scalar()
        )
        return round(float(avg), 1) if avg else None

    def get_rating_count(self):
        return self.ratings.count()

    def get_fan_genres(self):
        """
        Returns aggregated fan genre votes:
        [{"genre": "Isekai", "votes": 42, "percentage": 78.5}, ...]
        Sorted by vote count descending.
        """
        results = (
            db.session.query(
                FanGenreVote.genre_tag,
                db.func.count(FanGenreVote.id).label("vote_count"),
            )
            .filter(FanGenreVote.anime_id == self.id)
            .group_by(FanGenreVote.genre_tag)
            .order_by(db.func.count(FanGenreVote.id).desc())
            .all()
        )

        total_raters = (
            db.session.query(db.func.count(db.distinct(FanGenreVote.user_id)))
            .filter(FanGenreVote.anime_id == self.id)
            .scalar()
        ) or 1

        return [
            {
                "genre": row.genre_tag,
                "votes": row.vote_count,
                "percentage": round((row.vote_count / total_raters) * 100, 1),
            }
            for row in results
        ]

    def to_dict(self, include_community=True):
        data = {
            "id": self.id,
            "mal_id": self.mal_id,
            "anilist_id": self.anilist_id,
            "title": self.title,
            "title_english": self.title_english,
            "title_japanese": self.title_japanese,
            "synopsis": self.synopsis,
            "api_score": self.api_score,
            "year": self.year,
            "season": self.season,
            "episodes": self.episodes,
            "studio": self.studio,
            "image_url": self.image_url,
            "banner_url": self.banner_url,
            "status": self.status,
            "source": self.source,
            "official_genres": [g.to_dict() for g in self.official_genres],
        }
        if include_community:
            data["community_score"] = self.get_community_score()
            data["rating_count"] = self.get_rating_count()
            data["fan_genres"] = self.get_fan_genres()
        return data


# ─── Rating (1-10 score from a user for an anime) ───────────────────────────

class Rating(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    anime_id = db.Column(
        db.Integer, db.ForeignKey("anime.id"), nullable=False, index=True
    )
    score = db.Column(db.Integer, nullable=False)  # 1-10
    review = db.Column(db.Text, nullable=True)  # optional short review
    created_at = db.Column(
        db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    updated_at = db.Column(
        db.DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    __table_args__ = (
        db.UniqueConstraint("user_id", "anime_id", name="unique_user_anime_rating"),
        db.CheckConstraint("score >= 1 AND score <= 10", name="valid_score_range"),
    )

    def to_dict(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "anime_id": self.anime_id,
            "score": self.score,
            "review": self.review,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }


# ─── Fan Genre Vote ─────────────────────────────────────────────────────────
#
# Each row = one user saying "I think this anime is [genre_tag]".
# A user can vote multiple genres per anime, but only once per genre per anime.

class FanGenreVote(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    anime_id = db.Column(
        db.Integer, db.ForeignKey("anime.id"), nullable=False, index=True
    )
    genre_tag = db.Column(db.String(60), nullable=False, index=True)
    created_at = db.Column(
        db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc)
    )

    __table_args__ = (
        db.UniqueConstraint(
            "user_id", "anime_id", "genre_tag", name="unique_user_anime_genre_vote"
        ),
    )

    def to_dict(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "anime_id": self.anime_id,
            "genre_tag": self.genre_tag,
            "created_at": self.created_at.isoformat(),
        }


# ─── Watchlist Entry (watch status tracking) ────────────────────────────────
#
# Tracks a user's relationship with an anime independent of rating.
# Statuses: watching, completed, plan_to_watch, dropped, on_hold
# A user can have a watchlist entry without a rating (e.g. Plan to Watch)
# and a rating automatically sets status to "completed" if not already set.

WATCH_STATUSES = ["watching", "completed", "plan_to_watch", "dropped", "on_hold"]

class WatchlistEntry(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    anime_id = db.Column(
        db.Integer, db.ForeignKey("anime.id"), nullable=False, index=True
    )
    status = db.Column(db.String(20), nullable=False, default="plan_to_watch")
    episodes_watched = db.Column(db.Integer, default=0)
    is_favorite = db.Column(db.Boolean, default=False)
    notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(
        db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    updated_at = db.Column(
        db.DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    user = db.relationship("User", backref=db.backref("watchlist_entries", lazy="dynamic"))
    anime = db.relationship("Anime", backref=db.backref("watchlist_entries", lazy="dynamic"))

    __table_args__ = (
        db.UniqueConstraint("user_id", "anime_id", name="unique_user_anime_watchlist"),
    )

    def to_dict(self, include_anime=False):
        data = {
            "id": self.id,
            "user_id": self.user_id,
            "anime_id": self.anime_id,
            "status": self.status,
            "episodes_watched": self.episodes_watched,
            "is_favorite": self.is_favorite,
            "notes": self.notes,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }
        if include_anime:
            data["anime"] = self.anime.to_dict(include_community=False)
            # Include user's rating if it exists
            rating = db.session.query(Rating).filter_by(
                user_id=self.user_id, anime_id=self.anime_id
            ).first()
            data["score"] = rating.score if rating else None
        return data


class Collection(db.Model):
    __tablename__ = "collections"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    name = db.Column(db.String(80), nullable=False)
    description = db.Column(db.String(500))
    color = db.Column(db.String(16), default="amber")
    icon = db.Column(db.String(32), default="bookmark")
    is_public = db.Column(db.Boolean, default=False, nullable=False)
    share_token = db.Column(db.String(32), unique=True, nullable=True)
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())
    updated_at = db.Column(
        db.DateTime,
        default=db.func.current_timestamp(),
        onupdate=db.func.current_timestamp(),
    )

    user = db.relationship("User", backref=db.backref("collections", lazy="dynamic"))
    items = db.relationship(
        "CollectionItem",
        backref="collection",
        cascade="all, delete-orphan",
        lazy="dynamic",
    )

    def to_dict(self, include_items: bool = False, public: bool = False):
        d = {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "color": self.color,
            "icon": self.icon,
            "is_public": self.is_public,
            "items_count": self.items.count(),
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
        if not public:
            d["user_id"] = self.user_id
            d["share_token"] = self.share_token
        if include_items:
            d["items"] = [i.to_dict() for i in self.items]
        return d


class CollectionItem(db.Model):
    __tablename__ = "collection_items"
    __table_args__ = (
        db.UniqueConstraint("collection_id", "anime_id", name="uq_collection_anime"),
    )

    id = db.Column(db.Integer, primary_key=True)
    collection_id = db.Column(db.Integer, db.ForeignKey("collections.id"), nullable=False)
    anime_id = db.Column(db.Integer, db.ForeignKey("anime.id"), nullable=False)
    note = db.Column(db.String(500))
    added_at = db.Column(db.DateTime, default=db.func.current_timestamp())

    anime = db.relationship("Anime")

    def to_dict(self):
        return {
            "id": self.id,
            "collection_id": self.collection_id,
            "anime_id": self.anime_id,
            "note": self.note,
            "added_at": self.added_at.isoformat() if self.added_at else None,
            "anime": self.anime.to_dict(include_community=False) if self.anime else None,
        }
