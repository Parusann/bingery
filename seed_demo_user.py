"""
seed_demo_user.py — Populate a curated demo user without wiping the database.

Safe to re-run: deletes the demo user's existing rows first, then re-creates
them. Designed to work against the live AniList-synced catalog, so anime are
looked up by title substring and missing entries are skipped rather than fatal.

Demo login:  demo@bingery.app / demo123
Run:         python seed_demo_user.py
"""

from __future__ import annotations

from datetime import datetime, timezone

from flask_bcrypt import Bcrypt
from sqlalchemy import or_

from app import create_app
from models import (
    Anime,
    Collection,
    CollectionItem,
    FanGenreVote,
    Rating,
    User,
    WatchlistEntry,
    db,
)

bcrypt = Bcrypt()


DEMO_USER = {
    "username": "demo",
    "email": "demo@bingery.app",
    "password": "demo123",
    "display_name": "Mio",
    "bio": (
        "Living for the next slow-burn masterpiece. Madhouse stan, "
        "Wit Studio enthusiast, and forever yelling about Steins;Gate at parties."
    ),
}


# (title_query, score 1-10, fan_genres, watch_status, is_favorite)
RATINGS: list[tuple[str, int, list[str], str, bool]] = [
    # ── All-time greats ────────────────────────────────────────────────
    ("Frieren",                          10, ["Adventure", "Fantasy", "Wholesome", "Slow Burn", "Tearjerker"], "completed", True),
    ("Steins;Gate",                      10, ["Sci-Fi", "Thriller", "Time Travel", "Mind-Bending", "Slow Burn"], "completed", True),
    ("Fullmetal Alchemist: Brotherhood", 10, ["Action", "Adventure", "Tragedy", "Shounen", "Tearjerker"], "completed", True),
    ("Hunter x Hunter",                  10, ["Action", "Adventure", "Tournament", "Shounen"], "completed", True),
    ("Monster",                           9, ["Psychological", "Thriller", "Mystery", "Slow Burn", "Seinen"], "completed", True),
    ("Cowboy Bebop",                      9, ["Action", "Sci-Fi", "Jazz", "Stylish"], "completed", True),
    ("Vinland Saga",                      9, ["Action", "Historical", "Drama", "Seinen", "Tragedy"], "completed", True),
    # ── Solid ──────────────────────────────────────────────────────────
    ("Attack on Titan",                   9, ["Action", "Dark Fantasy", "Tragedy", "Survival"], "completed", False),
    ("Made in Abyss",                     9, ["Adventure", "Dark Fantasy", "Horror"], "completed", False),
    ("Mob Psycho 100",                    8, ["Action", "Comedy", "Supernatural", "Coming of Age"], "completed", False),
    ("Bocchi the Rock",                   9, ["Music", "Comedy", "Slice of Life", "Wholesome"], "completed", False),
    ("Haikyu",                            9, ["Sports", "Drama", "Coming of Age", "Tournament"], "completed", False),
    ("Spy x Family",                      8, ["Comedy", "Action", "Wholesome"], "completed", False),
    ("Jujutsu Kaisen",                    8, ["Action", "Supernatural", "Shounen"], "completed", False),
    ("Death Note",                        8, ["Mystery", "Thriller", "Psychological"], "completed", False),
    # ── Mid / mixed ────────────────────────────────────────────────────
    ("Oshi no Ko",                        7, ["Drama", "Mystery", "Seinen"], "completed", False),
    ("Chainsaw Man",                      7, ["Action", "Horror", "Shounen"], "completed", False),
    ("Demon Slayer",                      7, ["Action", "Supernatural", "Shounen"], "completed", False),
    ("One Punch Man",                     8, ["Action", "Comedy", "Parody"], "completed", False),
    ("One Punch Man 2",                   5, ["Action", "Comedy"], "completed", False),
]


# Watchlist-only entries (no rating) — fallback gracefully if missing.
# (title_query, status, is_favorite)
WATCH_ONLY: list[tuple[str, str, bool]] = [
    # Plan to watch — bucket list
    ("Mushishi",                      "plan_to_watch", False),
    ("Ping Pong the Animation",       "plan_to_watch", False),
    ("Texhnolyze",                    "plan_to_watch", False),
    ("Sousou no Frieren 2nd Season",  "plan_to_watch", False),
    ("One Punch Man 3",               "plan_to_watch", False),
    # On hold — too dense to push through right now
    ("Legend of the Galactic Heroes", "on_hold",       False),
    # Dropped — tried, bounced off
    ("Sword Art Online",              "dropped",       False),
]


COLLECTIONS: list[dict] = [
    {
        "name": "All-Time S Tier",
        "description": "The seven I will defend with my entire soul. Slow burns, character work, peak storytelling.",
        "color": "violet",
        "icon": "trophy",
        "is_public": True,
        "anime_titles": [
            "Frieren",
            "Steins;Gate",
            "Fullmetal Alchemist: Brotherhood",
            "Hunter x Hunter",
            "Monster",
            "Cowboy Bebop",
            "Vinland Saga",
        ],
    },
    {
        "name": "Comfy Wholesome Vibes",
        "description": "For when real life is heavy and I need a hug in TV form.",
        "color": "amber",
        "icon": "heart",
        "is_public": True,
        "anime_titles": [
            "Bocchi the Rock",
            "Spy x Family",
            "Frieren",
            "Mob Psycho 100",
            "Haikyu",
        ],
    },
    {
        "name": "Mind-Benders",
        "description": "Plots that fold reality. Take notes, rewatch twice.",
        "color": "indigo",
        "icon": "sparkles",
        "is_public": False,
        "anime_titles": [
            "Steins;Gate",
            "Death Note",
            "Monster",
            "Made in Abyss",
            "Oshi no Ko",
        ],
    },
    {
        "name": "Currently Pinned",
        "description": "Active rotation right now.",
        "color": "rose",
        "icon": "bookmark",
        "is_public": False,
        "anime_titles": [
            "Frieren",
            "Jujutsu Kaisen",
            "Chainsaw Man",
            "Bocchi the Rock",
        ],
    },
]


def find_anime(title_query: str):
    """Exact title match first; fall back to fuzzy substring across title/title_english."""
    exact = (
        Anime.query
        .filter(or_(Anime.title == title_query, Anime.title_english == title_query))
        .first()
    )
    if exact:
        return exact
    return (
        Anime.query
        .filter(or_(
            Anime.title.ilike(f"%{title_query}%"),
            Anime.title_english.ilike(f"%{title_query}%"),
        ))
        .order_by(Anime.api_score.desc().nullslast())
        .first()
    )


def wipe_demo_data(user: User) -> None:
    Rating.query.filter_by(user_id=user.id).delete(synchronize_session=False)
    FanGenreVote.query.filter_by(user_id=user.id).delete(synchronize_session=False)
    WatchlistEntry.query.filter_by(user_id=user.id).delete(synchronize_session=False)
    for c in list(user.collections):
        db.session.delete(c)
    db.session.flush()


def get_or_create_demo_user() -> User:
    user = User.query.filter_by(email=DEMO_USER["email"]).first()
    pw_hash = bcrypt.generate_password_hash(DEMO_USER["password"]).decode("utf-8")
    if user:
        wipe_demo_data(user)
        user.username = DEMO_USER["username"]
        user.display_name = DEMO_USER["display_name"]
        user.bio = DEMO_USER["bio"]
        user.password_hash = pw_hash
    else:
        user = User(
            username=DEMO_USER["username"],
            email=DEMO_USER["email"],
            password_hash=pw_hash,
            display_name=DEMO_USER["display_name"],
            bio=DEMO_USER["bio"],
        )
        db.session.add(user)
        db.session.flush()
    return user


def seed_demo() -> None:
    app = create_app()
    with app.app_context():
        user = get_or_create_demo_user()
        skipped: list[str] = []

        for title_q, score, fan_genres, status, is_fav in RATINGS:
            anime = find_anime(title_q)
            if anime is None:
                skipped.append(title_q)
                continue

            db.session.add(Rating(user_id=user.id, anime_id=anime.id, score=score))

            for tag in fan_genres:
                db.session.add(FanGenreVote(
                    user_id=user.id, anime_id=anime.id, genre_tag=tag,
                ))

            episodes_watched = (
                anime.episodes if status == "completed" and anime.episodes else 0
            )
            db.session.add(WatchlistEntry(
                user_id=user.id,
                anime_id=anime.id,
                status=status,
                episodes_watched=episodes_watched,
                is_favorite=is_fav,
            ))

        for title_q, status, is_fav in WATCH_ONLY:
            anime = find_anime(title_q)
            if anime is None:
                skipped.append(title_q)
                continue
            if status == "on_hold" and anime.episodes:
                eps = min(20, anime.episodes // 3)
            elif status == "dropped" and anime.episodes:
                eps = min(3, anime.episodes)
            else:
                eps = 0
            db.session.add(WatchlistEntry(
                user_id=user.id,
                anime_id=anime.id,
                status=status,
                episodes_watched=eps,
                is_favorite=is_fav,
            ))

        for c_data in COLLECTIONS:
            coll = Collection(
                user_id=user.id,
                name=c_data["name"],
                description=c_data["description"],
                color=c_data["color"],
                icon=c_data["icon"],
                is_public=c_data["is_public"],
            )
            db.session.add(coll)
            db.session.flush()

            seen: set[int] = set()
            for title_q in c_data["anime_titles"]:
                anime = find_anime(title_q)
                if anime is None:
                    skipped.append(f"[{coll.name}] {title_q}")
                    continue
                if anime.id in seen:
                    continue
                seen.add(anime.id)
                db.session.add(CollectionItem(
                    collection_id=coll.id,
                    anime_id=anime.id,
                ))

        db.session.commit()

        user_id = user.id
        rating_count = Rating.query.filter_by(user_id=user_id).count()
        watch_count = WatchlistEntry.query.filter_by(user_id=user_id).count()
        vote_count = FanGenreVote.query.filter_by(user_id=user_id).count()
        coll_count = Collection.query.filter_by(user_id=user_id).count()
        item_count = (
            db.session.query(db.func.count(CollectionItem.id))
            .join(Collection)
            .filter(Collection.user_id == user_id)
            .scalar()
        )

        bar = "=" * 56
        print(f"\n{bar}")
        print("  Demo user ready")
        print(f"  Login:        {DEMO_USER['email']} / {DEMO_USER['password']}")
        print(f"  Display:      {user.display_name} (@{user.username})")
        print(f"  Ratings:      {rating_count}")
        print(f"  Genre votes:  {vote_count}")
        print(f"  Watchlist:    {watch_count}")
        print(f"  Collections:  {coll_count}  ({item_count} items)")
        if skipped:
            print(f"  Skipped:      {len(skipped)} not found in DB:")
            for t in skipped:
                print(f"                  - {t}")
        print(f"{bar}\n")


if __name__ == "__main__":
    seed_demo()
