"""
Migration: Add WatchlistEntry table and auto-create watchlist entries
from existing ratings.

Run: python migrate_watchlist.py
"""
from app import create_app
from models import db, Rating, WatchlistEntry

def migrate():
    app = create_app()
    with app.app_context():
        # Create only new tables (won't drop existing ones)
        db.create_all()

        # Check if we already migrated
        existing = WatchlistEntry.query.first()
        if existing:
            print("  Watchlist table already has data — skipping migration.")
            return

        # Create watchlist entries from existing ratings
        ratings = Rating.query.all()
        count = 0
        for r in ratings:
            existing_entry = WatchlistEntry.query.filter_by(
                user_id=r.user_id, anime_id=r.anime_id
            ).first()
            if not existing_entry:
                entry = WatchlistEntry(
                    user_id=r.user_id,
                    anime_id=r.anime_id,
                    status="completed",
                )
                db.session.add(entry)
                count += 1

        db.session.commit()
        print(f"\n  Migration complete!")
        print(f"  Created {count} watchlist entries from existing ratings.")
        print(f"  Total watchlist entries: {WatchlistEntry.query.count()}")


if __name__ == "__main__":
    print("\n  Running watchlist migration...")
    migrate()
    print()
