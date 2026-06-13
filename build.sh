#!/usr/bin/env bash
set -euo pipefail

python -m pip install --upgrade pip
pip install -r requirements.txt

pushd frontend > /dev/null
npm ci
npm run build
popd > /dev/null

# NOTE: do NOT run seed.py here — it calls db.drop_all() and would wipe the
# database on every deploy. Tables are created on app boot (db.create_all()).
# For a one-time initial seed run `python seed.py --force` manually against
# the target database.
