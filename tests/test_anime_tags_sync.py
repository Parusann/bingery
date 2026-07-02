"""Tests for AniList tag persistence (Tag/AnimeTag models + sync)."""
import pytest

from models import db, Anime, Tag, AnimeTag


def test_tag_link_carries_rank(app):
    with app.app_context():
        a = Anime(title="Seed Show")
        t = Tag(name="Isekai", category="Setting")
        db.session.add_all([a, t])
        db.session.flush()
        db.session.add(AnimeTag(anime_id=a.id, tag_id=t.id, rank=93))
        db.session.commit()
        link = db.session.query(AnimeTag).filter_by(anime_id=a.id).one()
        assert link.rank == 93
        assert link.tag.name == "Isekai"


def _media(tags):
    """Minimal AniList media payload accepted by _normalize_anime."""
    return {
        "id": 991,
        "title": {"romaji": "Tag Show"},
        "coverImage": {},
        "studios": {"nodes": []},
        "genres": [],
        "tags": tags,
    }


def test_normalize_keeps_tags_from_rank_40(app):
    from utils.anilist import AniListClient

    norm = AniListClient()._normalize_anime(_media([
        {"name": "Isekai", "rank": 41, "category": "Setting"},
        {"name": "Noise", "rank": 39, "category": "Theme"},
        {"name": "Adult Thing", "rank": 90, "category": "X", "isAdult": True},
    ]))
    names = [t["name"] for t in norm["tags"]]
    assert names == ["Isekai"]  # >=40 kept, <40 and isAdult dropped


def test_sync_persists_and_replaces_tags(app):
    from utils.anilist import sync_anime_to_db

    with app.app_context():
        data = {
            "anilist_id": 991, "title": "Tag Show", "genres": [],
            "tags": [{"name": "Isekai", "rank": 88, "category": "Setting"}],
        }
        a = sync_anime_to_db(data)
        db.session.commit()
        assert [(l.tag.name, l.rank) for l in a.tag_links] == [("Isekai", 88)]

        data["tags"] = [{"name": "Tragedy", "rank": 71, "category": "Theme"}]
        a = sync_anime_to_db(data)
        db.session.commit()
        assert [(l.tag.name, l.rank) for l in a.tag_links] == [("Tragedy", 71)]


def test_sync_survives_duplicate_mal_id(app):
    """AniList occasionally maps two entries to one MAL id. The sync must
    skip the conflicting mal_id (keeping the original owner) instead of
    dying on the unique constraint — this aborted a prod resync."""
    from utils.anilist import sync_anime_to_db

    with app.app_context():
        holder = sync_anime_to_db(
            {"anilist_id": 111, "mal_id": 555, "title": "Holder", "genres": [], "tags": []}
        )
        db.session.commit()

        thief = sync_anime_to_db(
            {"anilist_id": 222, "mal_id": 555, "title": "Thief", "genres": [], "tags": []}
        )
        db.session.commit()  # must not raise
        assert thief.mal_id is None
        assert holder.mal_id == 555

        # Re-syncing the same conflicting payload on the now-existing row
        # (the exact prod crash path: UPDATE with a taken mal_id).
        thief2 = sync_anime_to_db(
            {"anilist_id": 222, "mal_id": 555, "title": "Thief", "genres": [], "tags": []}
        )
        db.session.commit()
        assert thief2.mal_id is None

        # The legitimate owner keeps updating its own mal_id fine.
        holder2 = sync_anime_to_db(
            {"anilist_id": 111, "mal_id": 555, "title": "Holder", "genres": [], "tags": []}
        )
        db.session.commit()
        assert holder2.mal_id == 555


def test_anime_tag_unique_per_pair(app):
    with app.app_context():
        a = Anime(title="Dup Show")
        t = Tag(name="Time Loop", category="Theme")
        db.session.add_all([a, t])
        db.session.flush()
        db.session.add(AnimeTag(anime_id=a.id, tag_id=t.id, rank=80))
        db.session.commit()
        db.session.add(AnimeTag(anime_id=a.id, tag_id=t.id, rank=70))
        with pytest.raises(Exception):
            db.session.commit()
        db.session.rollback()
