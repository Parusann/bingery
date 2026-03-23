#!/usr/bin/env bash
set -o errexit

pip install -r requirements.txt

# Create tables and seed initial data
python -c "from app import create_app; app = create_app(); app.app_context().push(); from models import db; db.create_all(); print('Tables created.')"
python seed.py
python -m utils.anilist --mode popular --pages 2
