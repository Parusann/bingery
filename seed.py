"""
Seed the database with initial genres, anime, and demo user data.
Run:  python seed.py
"""

from app import create_app
from models import db, Genre, Anime, User, Rating, FanGenreVote, anime_genres
from flask_bcrypt import Bcrypt

bcrypt = Bcrypt()

# ═══════════════════════════════════════════════════════════════════════════════
# GENRES  (official — what you'd get from MAL / AniList APIs)
# ═══════════════════════════════════════════════════════════════════════════════

GENRES = [
    # Standard
    ("Action", "standard"), ("Adventure", "standard"), ("Comedy", "standard"),
    ("Drama", "standard"), ("Fantasy", "standard"), ("Horror", "standard"),
    ("Mystery", "standard"), ("Romance", "standard"), ("Sci-Fi", "standard"),
    ("Slice of Life", "standard"), ("Supernatural", "standard"),
    ("Thriller", "standard"), ("Sports", "standard"), ("Music", "standard"),
    # Demographic
    ("Shounen", "demographic"), ("Shoujo", "demographic"),
    ("Seinen", "demographic"), ("Josei", "demographic"),
    # Thematic
    ("Isekai", "theme"), ("Mecha", "theme"), ("Magical Girl", "theme"),
    ("Martial Arts", "theme"), ("Military", "theme"),
    ("Psychological", "theme"), ("Historical", "theme"),
    ("Vampire", "theme"), ("Demons", "theme"),
    ("Harem", "theme"), ("Game", "theme"),
]

# ═══════════════════════════════════════════════════════════════════════════════
# ANIME
# ═══════════════════════════════════════════════════════════════════════════════

ANIME = [
    {
        "mal_id": 1535, "title": "Death Note",
        "title_english": "Death Note",
        "synopsis": "A high school student discovers a supernatural notebook that grants its user the power to kill anyone whose name and face they know. With this newfound ability, he decides to create a utopia by eliminating criminals, but a legendary detective begins pursuing him.",
        "api_score": 8.62, "year": 2006, "episodes": 37,
        "studio": "Madhouse",
        "image_url": "https://cdn.myanimelist.net/images/anime/9/9453l.jpg",
        "status": "Finished Airing", "source": "Manga",
        "genres": ["Mystery", "Supernatural", "Thriller", "Shounen"],
    },
    {
        "mal_id": 16498, "title": "Shingeki no Kyojin",
        "title_english": "Attack on Titan",
        "synopsis": "Centuries ago, humanity was slaughtered to near extinction by monstrous humanoid creatures called Titans. Survivors sealed themselves behind enormous walls. When a colossal Titan breaches the outer wall, young Eren Yeager vows to eradicate every Titan.",
        "api_score": 8.54, "year": 2013, "episodes": 87,
        "studio": "Wit Studio / MAPPA",
        "image_url": "https://cdn.myanimelist.net/images/anime/10/47347l.jpg",
        "status": "Finished Airing", "source": "Manga",
        "genres": ["Action", "Drama", "Fantasy", "Mystery", "Shounen"],
    },
    {
        "mal_id": 9253, "title": "Steins;Gate",
        "title_english": "Steins;Gate",
        "synopsis": "Self-proclaimed mad scientist Rintaro Okabe and his friends accidentally discover a method of time travel using a modified microwave. Their experiments attract the attention of a powerful organization and lead to devastating consequences.",
        "api_score": 9.07, "year": 2011, "episodes": 24,
        "studio": "White Fox",
        "image_url": "https://cdn.myanimelist.net/images/anime/5/73199l.jpg",
        "status": "Finished Airing", "source": "Visual Novel",
        "genres": ["Sci-Fi", "Thriller", "Drama"],
    },
    {
        "mal_id": 5114, "title": "Fullmetal Alchemist: Brotherhood",
        "title_english": "Fullmetal Alchemist: Brotherhood",
        "synopsis": "After a failed alchemical experiment costs them dearly, brothers Edward and Alphonse Elric embark on a journey to find the Philosopher's Stone to restore their bodies. They uncover a vast conspiracy that threatens the entire nation.",
        "api_score": 9.10, "year": 2009, "episodes": 64,
        "studio": "Bones",
        "image_url": "https://cdn.myanimelist.net/images/anime/1208/94745l.jpg",
        "status": "Finished Airing", "source": "Manga",
        "genres": ["Action", "Adventure", "Drama", "Fantasy", "Shounen"],
    },
    {
        "mal_id": 40748, "title": "Jujutsu Kaisen",
        "title_english": "Jujutsu Kaisen",
        "synopsis": "Yuji Itadori, an unnaturally fit high school student, joins a secret organization of sorcerers to kill a powerful Curse after he swallows a cursed talisman — a finger belonging to the demon Sukuna.",
        "api_score": 8.67, "year": 2020, "episodes": 24,
        "studio": "MAPPA",
        "image_url": "https://cdn.myanimelist.net/images/anime/1171/109222l.jpg",
        "status": "Finished Airing", "source": "Manga",
        "genres": ["Action", "Fantasy", "Supernatural", "Shounen"],
    },
    {
        "mal_id": 37521, "title": "Vinland Saga",
        "title_english": "Vinland Saga",
        "synopsis": "Young Thorfinn grows up on tales of a mythical land far west, a place called Vinland. When his father is murdered, Thorfinn swears revenge and joins the mercenary band led by his father's killer, seeking a duel.",
        "api_score": 8.72, "year": 2019, "episodes": 24,
        "studio": "Wit Studio",
        "image_url": "https://cdn.myanimelist.net/images/anime/1500/103005l.jpg",
        "status": "Finished Airing", "source": "Manga",
        "genres": ["Action", "Adventure", "Drama", "Historical", "Seinen"],
    },
    {
        "mal_id": 19, "title": "Monster",
        "title_english": "Monster",
        "synopsis": "Dr. Kenzo Tenma, a brilliant neurosurgeon, makes a controversial decision to save a young boy's life over the city mayor's. Years later, that boy grows into a cold and calculating serial killer, and Tenma must hunt him down.",
        "api_score": 8.86, "year": 2004, "episodes": 74,
        "studio": "Madhouse",
        "image_url": "https://cdn.myanimelist.net/images/anime/10/18793l.jpg",
        "status": "Finished Airing", "source": "Manga",
        "genres": ["Drama", "Horror", "Mystery", "Psychological", "Thriller", "Seinen"],
    },
    {
        "mal_id": 32182, "title": "Mob Psycho 100",
        "title_english": "Mob Psycho 100",
        "synopsis": "Shigeo 'Mob' Kageyama is an average middle school boy but also the most powerful psychic. To keep his growing powers under control, he suppresses his emotions, working as an assistant to a con-man spirit medium.",
        "api_score": 8.47, "year": 2016, "episodes": 12,
        "studio": "Bones",
        "image_url": "https://cdn.myanimelist.net/images/anime/8/80356l.jpg",
        "status": "Finished Airing", "source": "Web Manga",
        "genres": ["Action", "Comedy", "Supernatural", "Shounen"],
    },
    {
        "mal_id": 34599, "title": "Made in Abyss",
        "title_english": "Made in Abyss",
        "synopsis": "In the town surrounding the Abyss — a vast, unexplored chasm — orphan Riko discovers a humanoid robot. Together they descend into the Abyss's treacherous layers in search of Riko's mother, facing horrors beyond imagination.",
        "api_score": 8.67, "year": 2017, "episodes": 13,
        "studio": "Kinema Citrus",
        "image_url": "https://cdn.myanimelist.net/images/anime/6/86733l.jpg",
        "status": "Finished Airing", "source": "Web Manga",
        "genres": ["Adventure", "Drama", "Fantasy", "Mystery", "Sci-Fi"],
    },
    {
        "mal_id": 50265, "title": "Spy x Family",
        "title_english": "Spy x Family",
        "synopsis": "A spy who must build a fake family for a mission unknowingly adopts a telepath as his daughter and marries an assassin. Each member hides their true identity while trying to fulfill their own secret objectives.",
        "api_score": 8.50, "year": 2022, "episodes": 12,
        "studio": "Wit Studio / CloverWorks",
        "image_url": "https://cdn.myanimelist.net/images/anime/1441/122795l.jpg",
        "status": "Finished Airing", "source": "Manga",
        "genres": ["Action", "Comedy", "Slice of Life", "Shounen"],
    },
    {
        "mal_id": 44511, "title": "Chainsaw Man",
        "title_english": "Chainsaw Man",
        "synopsis": "Denji is a teenage boy living with a Chainsaw Devil named Pochita. After being betrayed and killed, Pochita merges with him, granting him the ability to transform into a being with chainsaws. He joins a government agency to hunt devils.",
        "api_score": 8.49, "year": 2022, "episodes": 12,
        "studio": "MAPPA",
        "image_url": "https://cdn.myanimelist.net/images/anime/1806/126216l.jpg",
        "status": "Finished Airing", "source": "Manga",
        "genres": ["Action", "Fantasy", "Horror", "Shounen"],
    },
    {
        "mal_id": 1, "title": "Cowboy Bebop",
        "title_english": "Cowboy Bebop",
        "synopsis": "In the year 2071, a ragtag crew of bounty hunters — Spike, Jet, Faye, Ed, and the corgi Ein — travel across the solar system in their spaceship Bebop, chasing criminals and confronting their pasts.",
        "api_score": 8.75, "year": 1998, "episodes": 26,
        "studio": "Sunrise",
        "image_url": "https://cdn.myanimelist.net/images/anime/4/19644l.jpg",
        "status": "Finished Airing", "source": "Original",
        "genres": ["Action", "Drama", "Sci-Fi"],
    },
    {
        "mal_id": 11061, "title": "Hunter x Hunter (2011)",
        "title_english": "Hunter x Hunter",
        "synopsis": "Gon Freecss discovers that his absent father is a legendary Hunter. He sets out to become a Hunter himself, making friends and facing deadly challenges along the way in a world of extraordinary abilities.",
        "api_score": 9.04, "year": 2011, "episodes": 148,
        "studio": "Madhouse",
        "image_url": "https://cdn.myanimelist.net/images/anime/1337/99013l.jpg",
        "status": "Finished Airing", "source": "Manga",
        "genres": ["Action", "Adventure", "Fantasy", "Shounen"],
    },
    {
        "mal_id": 21, "title": "One Punch Man",
        "title_english": "One Punch Man",
        "synopsis": "Saitama is a hero who can defeat any opponent with a single punch. Bored by the lack of challenge, he searches for a worthy adversary while dealing with the politics of the Hero Association.",
        "api_score": 8.50, "year": 2015, "episodes": 12,
        "studio": "Madhouse",
        "image_url": "https://cdn.myanimelist.net/images/anime/12/76049l.jpg",
        "status": "Finished Airing", "source": "Web Manga",
        "genres": ["Action", "Comedy", "Supernatural", "Seinen"],
    },
    {
        "mal_id": 30276, "title": "One Punch Man Season 2",
        "title_english": None,
        "synopsis": "Continuation of Saitama's heroic adventures.",
        "api_score": 7.43, "year": 2019, "episodes": 12,
        "studio": "J.C.Staff",
        "image_url": "https://cdn.myanimelist.net/images/anime/1247/120745l.jpg",
        "status": "Finished Airing", "source": "Web Manga",
        "genres": ["Action", "Comedy", "Supernatural", "Seinen"],
    },
    {
        "mal_id": 38000, "title": "Kimetsu no Yaiba",
        "title_english": "Demon Slayer: Kimetsu no Yaiba",
        "synopsis": "After his family is slaughtered by demons and his sister Nezuko is turned into one, Tanjiro Kamado sets out to find a cure for her and avenge his family by becoming a demon slayer.",
        "api_score": 8.45, "year": 2019, "episodes": 26,
        "studio": "ufotable",
        "image_url": "https://cdn.myanimelist.net/images/anime/1286/99889l.jpg",
        "status": "Finished Airing", "source": "Manga",
        "genres": ["Action", "Fantasy", "Supernatural", "Shounen"],
    },
    {
        "mal_id": 20583, "title": "Haikyuu!!",
        "title_english": "Haikyu!!",
        "synopsis": "Inspired by a legendary volleyball player, short but athletic Shoyo Hinata joins his high school volleyball team and forms an unlikely partnership with a genius setter to compete at the national level.",
        "api_score": 8.44, "year": 2014, "episodes": 25,
        "studio": "Production I.G",
        "image_url": "https://cdn.myanimelist.net/images/anime/7/76014l.jpg",
        "status": "Finished Airing", "source": "Manga",
        "genres": ["Comedy", "Drama", "Sports", "Shounen"],
    },
    {
        "mal_id": 49387, "title": "Oshi no Ko",
        "title_english": "Oshi no Ko",
        "synopsis": "A doctor who is a fan of a pop idol is reincarnated as her son after both of their untimely deaths. Now inside the entertainment industry, he uncovers its dark secrets while protecting his twin sister.",
        "api_score": 8.36, "year": 2023, "episodes": 11,
        "studio": "Doga Kobo",
        "image_url": "https://cdn.myanimelist.net/images/anime/1812/134736l.jpg",
        "status": "Finished Airing", "source": "Manga",
        "genres": ["Drama", "Mystery", "Supernatural", "Seinen"],
    },
    {
        "mal_id": 52991, "title": "Sousou no Frieren",
        "title_english": "Frieren: Beyond Journey's End",
        "synopsis": "After the hero's party defeats the Demon King, the elven mage Frieren realizes that her long lifespan means she experienced their decade-long quest as a brief moment. She embarks on a new journey to understand human emotions.",
        "api_score": 9.30, "year": 2023, "episodes": 28,
        "studio": "Madhouse",
        "image_url": "https://cdn.myanimelist.net/images/anime/1015/138006l.jpg",
        "status": "Finished Airing", "source": "Manga",
        "genres": ["Adventure", "Drama", "Fantasy", "Shounen"],
    },
    {
        "mal_id": 47917, "title": "Bocchi the Rock!",
        "title_english": "Bocchi the Rock!",
        "synopsis": "Hitori 'Bocchi' Gotoh is an extremely shy girl who dreams of being in a band. When she's recruited by a desperate drummer, she must overcome her crippling social anxiety to perform on stage.",
        "api_score": 8.82, "year": 2022, "episodes": 12,
        "studio": "CloverWorks",
        "image_url": "https://cdn.myanimelist.net/images/anime/1448/127956l.jpg",
        "status": "Finished Airing", "source": "4-koma Manga",
        "genres": ["Comedy", "Music", "Slice of Life"],
    },
]

# ═══════════════════════════════════════════════════════════════════════════════
# DEMO USERS & RATINGS
# ═══════════════════════════════════════════════════════════════════════════════

DEMO_USERS = [
    {"username": "demo", "email": "demo@bingery.app", "password": "demo123"},
    {"username": "animeking", "email": "king@bingery.app", "password": "demo123"},
    {"username": "sakura_fan", "email": "sakura@bingery.app", "password": "demo123"},
]

# (user_index, anime_mal_id, score, fan_genres)
DEMO_RATINGS = [
    (0, 1535, 9, ["Mystery", "Thriller", "Shounen", "Mind-Bending", "Psychological"]),
    (0, 16498, 9, ["Action", "Shounen", "Dark Fantasy", "Survival"]),
    (0, 9253, 10, ["Sci-Fi", "Thriller", "Time Travel", "Slow Burn", "Mind-Bending"]),
    (0, 5114, 10, ["Action", "Adventure", "Shounen", "Fantasy"]),
    (0, 40748, 8, ["Action", "Supernatural", "Shounen", "Gore"]),
    (1, 1535, 10, ["Mystery", "Thriller", "Shounen", "Psychological", "Mind-Bending"]),
    (1, 5114, 9, ["Action", "Adventure", "Shounen", "Fantasy"]),
    (1, 11061, 10, ["Action", "Adventure", "Shounen", "Tournament"]),
    (1, 19, 9, ["Thriller", "Mystery", "Seinen", "Psychological", "Slow Burn"]),
    (1, 44511, 8, ["Action", "Horror", "Shounen", "Gore", "Demons"]),
    (1, 52991, 10, ["Adventure", "Fantasy", "Shounen", "Wholesome", "Slow Burn"]),
    (2, 50265, 9, ["Comedy", "Action", "Shounen", "Wholesome", "Feel-Good"]),
    (2, 47917, 10, ["Comedy", "Music", "Slice of Life", "Wholesome", "Coming of Age"]),
    (2, 38000, 8, ["Action", "Supernatural", "Shounen", "Demons", "Fantasy"]),
    (2, 34599, 9, ["Adventure", "Fantasy", "Horror", "Mystery", "Dark Fantasy"]),
    (2, 49387, 8, ["Drama", "Mystery", "Seinen", "Psychological"]),
]


def seed():
    app = create_app()
    with app.app_context():
        print("Dropping all tables...")
        db.drop_all()
        print("Creating all tables...")
        db.create_all()

        # ── Genres ────────────────────────────────────────────────────────
        print("Seeding genres...")
        genre_map = {}
        for name, cat in GENRES:
            g = Genre(name=name, category=cat)
            db.session.add(g)
            genre_map[name] = g
        db.session.flush()

        # ── Anime ─────────────────────────────────────────────────────────
        print("Seeding anime...")
        anime_map = {}  # mal_id -> Anime
        for a_data in ANIME:
            a = Anime(
                mal_id=a_data["mal_id"],
                title=a_data["title"],
                title_english=a_data.get("title_english"),
                synopsis=a_data["synopsis"],
                api_score=a_data["api_score"],
                year=a_data["year"],
                episodes=a_data["episodes"],
                studio=a_data["studio"],
                image_url=a_data["image_url"],
                status=a_data["status"],
                source=a_data.get("source"),
            )
            # Attach official genres
            for gname in a_data["genres"]:
                if gname in genre_map:
                    a.official_genres.append(genre_map[gname])
            db.session.add(a)
            anime_map[a_data["mal_id"]] = a
        db.session.flush()

        # ── Users ─────────────────────────────────────────────────────────
        print("Seeding demo users...")
        users = []
        for u_data in DEMO_USERS:
            u = User(
                username=u_data["username"],
                email=u_data["email"],
                password_hash=bcrypt.generate_password_hash(u_data["password"]).decode("utf-8"),
            )
            db.session.add(u)
            users.append(u)
        db.session.flush()

        # ── Ratings & Fan Genre Votes ─────────────────────────────────────
        print("Seeding ratings and fan genre votes...")
        for user_idx, mal_id, score, fan_genres in DEMO_RATINGS:
            anime = anime_map.get(mal_id)
            if not anime:
                continue
            user = users[user_idx]

            r = Rating(user_id=user.id, anime_id=anime.id, score=score)
            db.session.add(r)

            for genre_tag in fan_genres:
                v = FanGenreVote(
                    user_id=user.id, anime_id=anime.id, genre_tag=genre_tag
                )
                db.session.add(v)

        db.session.commit()

        # ── Summary ───────────────────────────────────────────────────────
        print(f"\n{'═' * 50}")
        print(f"  Seeded successfully!")
        print(f"  Genres:     {Genre.query.count()}")
        print(f"  Anime:      {Anime.query.count()}")
        print(f"  Users:      {User.query.count()}")
        print(f"  Ratings:    {Rating.query.count()}")
        print(f"  Fan Votes:  {FanGenreVote.query.count()}")
        print(f"{'═' * 50}")
        print(f"\n  Demo login:  demo@bingery.app / demo123")
        print(f"  DB file:     bingery.db\n")


if __name__ == "__main__":
    seed()
