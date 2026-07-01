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
