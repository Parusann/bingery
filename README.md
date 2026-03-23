# Bingery Backend

Flask API server for the Bingery anime catalog and recommendation platform.

---

## Quick Start

```bash
# 1. Install dependencies
cd bingery-backend
pip install -r requirements.txt

# 2. Seed the database with sample data
python seed.py

# 3. Run the server
python app.py
```

The API will be running at `http://localhost:5000`.

**Demo login:** `demo@bingery.app` / `demo123`

---

## Database Schema

### Users
| Column        | Type     | Notes                        |
|---------------|----------|------------------------------|
| id            | Integer  | Primary key                  |
| username      | String   | Unique, min 3 chars          |
| email         | String   | Unique                       |
| password_hash | String   | Bcrypt hashed                |
| avatar_url    | String   | Optional                     |
| bio           | String   | Max 500 chars                |
| created_at    | DateTime | Auto-set                     |

### Anime
| Column         | Type    | Notes                                |
|----------------|---------|--------------------------------------|
| id             | Integer | Primary key                          |
| mal_id         | Integer | MyAnimeList ID (unique)              |
| anilist_id     | Integer | AniList ID (unique)                  |
| title          | String  | Japanese/romaji title                |
| title_english  | String  | English title                        |
| title_japanese | String  | Japanese title                       |
| synopsis       | Text    | Description                          |
| api_score      | Float   | Score from MAL/AniList               |
| year           | Integer | Release year                         |
| season         | String  | spring/summer/fall/winter            |
| episodes       | Integer | Episode count                        |
| studio         | String  | Animation studio                     |
| image_url      | String  | Cover image                          |
| status         | String  | Airing / Finished Airing / Upcoming  |
| source         | String  | Manga / Light Novel / Original / etc |

### Ratings (1–10 Score)
| Column   | Type    | Notes                                 |
|----------|---------|---------------------------------------|
| id       | Integer | Primary key                           |
| user_id  | Integer | FK → Users                            |
| anime_id | Integer | FK → Anime                            |
| score    | Integer | 1–10 (enforced by CHECK constraint)   |
| review   | Text    | Optional review text (max 2000 chars) |

Unique constraint on `(user_id, anime_id)` — one rating per user per anime.

### Fan Genre Votes
| Column    | Type    | Notes                           |
|-----------|---------|---------------------------------|
| id        | Integer | Primary key                     |
| user_id   | Integer | FK → Users                      |
| anime_id  | Integer | FK → Anime                      |
| genre_tag | String  | The genre the user voted for    |

Unique constraint on `(user_id, anime_id, genre_tag)` — one vote per genre per user per anime.
Users can submit up to 15 genre tags per anime.

### Genres (Official API Genres)
| Column   | Type   | Notes                                            |
|----------|--------|--------------------------------------------------|
| id       | Integer| Primary key                                      |
| name     | String | Genre name (unique)                              |
| category | String | standard / demographic / theme                   |

Linked to Anime via `anime_genres` association table (many-to-many).

---

## API Endpoints

### Authentication

| Method | Endpoint             | Auth | Description          |
|--------|----------------------|------|----------------------|
| POST   | `/api/auth/register` | No   | Create account       |
| POST   | `/api/auth/login`    | No   | Login, get JWT token |
| GET    | `/api/auth/me`       | Yes  | Get your profile     |
| PATCH  | `/api/auth/me`       | Yes  | Update your profile  |

### Anime

| Method | Endpoint                     | Auth | Description                      |
|--------|------------------------------|------|----------------------------------|
| GET    | `/api/anime`                 | No   | List/search anime (paginated)    |
| GET    | `/api/anime/<id>`            | Opt  | Full anime detail                |
| GET    | `/api/anime/<id>/ratings`    | No   | All user ratings for this anime  |
| GET    | `/api/anime/genres`          | No   | Official genres (grouped)        |
| GET    | `/api/anime/top`             | No   | Top rated by community           |

### Ratings & Fan Genres

| Method | Endpoint                       | Auth | Description                              |
|--------|--------------------------------|------|------------------------------------------|
| POST   | `/api/anime/<id>/rate`         | Yes  | Rate 1–10 (create/update)                |
| DELETE | `/api/anime/<id>/rate`         | Yes  | Remove your rating                       |
| POST   | `/api/anime/<id>/fan-genres`   | Yes  | Submit fan genre votes                   |
| GET    | `/api/anime/<id>/fan-genres`   | No   | Get aggregated fan genre data            |

### AniList Integration

| Method | Endpoint                       | Auth | Description                              |
|--------|--------------------------------|------|------------------------------------------|
| GET    | `/api/anilist/search?q=`       | No   | Search AniList (no DB save)              |
| GET    | `/api/anilist/anime/<id>`      | No   | Get anime details from AniList           |
| GET    | `/api/anilist/trending`        | No   | Currently trending anime                 |
| GET    | `/api/anilist/seasonal`        | No   | Seasonal anime (?year=&season=)          |
| POST   | `/api/anilist/sync`            | Yes  | Sync AniList anime to local DB           |
| POST   | `/api/anime/<id>/review`       | Yes  | Combined: rate + fan genres in one call  |
| GET    | `/api/fan-genres/allowed`      | No   | All allowed fan genre tags (grouped)     |

### User Data

| Method | Endpoint                    | Auth | Description              |
|--------|-----------------------------|------|--------------------------|
| GET    | `/api/me/ratings`           | Yes  | Your rated anime         |
| GET    | `/api/users/<id>/ratings`   | No   | A user's rated anime     |

---

## Fan Genre System

Users can tag anime with genres they think apply. These accumulate across all users and display as **Fan Genre Categories** on each anime's profile, showing:

- **Genre name** — e.g., "Isekai", "Shounen", "Mind-Bending"
- **Vote count** — how many users tagged this genre
- **Percentage** — proportion of raters who picked this genre

### Available Fan Genres (59 total)

**Standard:** Action, Adventure, Comedy, Drama, Fantasy, Horror, Mystery, Romance, Sci-Fi, Slice of Life, Supernatural, Thriller, Sports, Music

**Demographic:** Shounen, Shoujo, Seinen, Josei, Kodomomuke

**Thematic:** Isekai, Mecha, Magical Girl, Harem, Reverse Harem, Martial Arts, Military, Psychological, Ecchi, Gore, Survival, Post-Apocalyptic, Cyberpunk, Steampunk, Historical, Samurai, Vampire, Zombie, Demons, Dark Fantasy, Mythology, Reincarnation, Time Travel, Virtual Reality, Game, Cooking, Medical, Detective

**Tone/Style:** Wholesome, Feel-Good, Tearjerker, Mind-Bending, Slow Burn, Fast-Paced, Episodic, Satirical, Coming of Age, Tragic

**Setting:** School, Workplace, Space, Underworld, Urban, Rural, Kingdom, Tournament, Dungeon

---

## Example API Calls

### Register
```bash
curl -X POST http://localhost:5000/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{"username":"newuser","email":"user@example.com","password":"mypassword"}'
```

### Login
```bash
curl -X POST http://localhost:5000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"demo@bingery.app","password":"demo123"}'
```

### Rate + Tag an anime
```bash
curl -X POST http://localhost:5000/api/anime/1/review \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -d '{
    "score": 9,
    "review": "Absolutely brilliant cat-and-mouse thriller",
    "genres": ["Mystery", "Thriller", "Shounen", "Psychological", "Mind-Bending"]
  }'
```

### Browse anime
```bash
curl "http://localhost:5000/api/anime?search=death&genre=Mystery&sort=api_score&order=desc"
```

### Get fan genre data
```bash
curl http://localhost:5000/api/anime/1/fan-genres
```

Response:
```json
{
  "fan_genres": [
    { "genre": "Mystery", "votes": 3, "percentage": 100.0 },
    { "genre": "Thriller", "votes": 3, "percentage": 100.0 },
    { "genre": "Shounen", "votes": 3, "percentage": 100.0 },
    { "genre": "Mind-Bending", "votes": 2, "percentage": 66.7 },
    { "genre": "Psychological", "votes": 2, "percentage": 66.7 }
  ]
}
```
