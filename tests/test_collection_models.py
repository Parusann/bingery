"""Tests for Collection and CollectionItem models."""
import pytest

from models import db, User, Anime, Collection, CollectionItem


def _make_user_and_anime(app):
    with app.app_context():
        user = User(username="u", email="u@e.com", password_hash="pw")
        a1 = Anime(mal_id=1, title="A", synopsis="", year=2020, episodes=12,
                   studio="S", image_url="", source="ORIGINAL",
                   status="FINISHED")
        a2 = Anime(mal_id=2, title="B", synopsis="", year=2021, episodes=24,
                   studio="S", image_url="", source="ORIGINAL",
                   status="FINISHED")
        db.session.add_all([user, a1, a2])
        db.session.commit()
        return user.id, a1.id, a2.id


def test_create_collection_with_items(app):
    uid, aid1, aid2 = _make_user_and_anime(app)
    with app.app_context():
        c = Collection(user_id=uid, name="Cozy Rewatches", color="amber", icon="flame")
        db.session.add(c)
        db.session.commit()

        db.session.add(CollectionItem(collection_id=c.id, anime_id=aid1))
        db.session.add(CollectionItem(collection_id=c.id, anime_id=aid2))
        db.session.commit()

        items = CollectionItem.query.filter_by(collection_id=c.id).all()
        assert len(items) == 2


def test_collection_item_unique_constraint(app):
    uid, aid1, _ = _make_user_and_anime(app)
    with app.app_context():
        c = Collection(user_id=uid, name="x")
        db.session.add(c)
        db.session.commit()
        db.session.add(CollectionItem(collection_id=c.id, anime_id=aid1))
        db.session.commit()

        with pytest.raises(Exception):
            db.session.add(CollectionItem(collection_id=c.id, anime_id=aid1))
            db.session.commit()
        db.session.rollback()


def test_collection_to_dict_includes_items_count(app):
    uid, aid1, _ = _make_user_and_anime(app)
    with app.app_context():
        c = Collection(user_id=uid, name="x", color="violet", icon="star", description="d")
        db.session.add(c)
        db.session.commit()
        db.session.add(CollectionItem(collection_id=c.id, anime_id=aid1))
        db.session.commit()
        d = c.to_dict()
        assert d["name"] == "x"
        assert d["color"] == "violet"
        assert d["icon"] == "star"
        assert d["items_count"] == 1
        assert d["is_public"] is False
        assert d["share_token"] is None
