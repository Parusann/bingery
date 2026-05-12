#!/usr/bin/env bash
set -euo pipefail

python -m pip install --upgrade pip
pip install -r requirements.txt

pushd frontend > /dev/null
npm ci
npm run build
popd > /dev/null

python seed.py || true
