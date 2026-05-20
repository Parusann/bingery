# syntax=docker/dockerfile:1.6

# ── Stage 1: build the Vite frontend ───────────────────────────────────────
FROM node:20-slim AS frontend
WORKDIR /app/frontend

# Cache deps first
COPY frontend/package.json frontend/package-lock.json* ./
RUN --mount=type=cache,target=/root/.npm \
    npm ci --no-audit --no-fund

# Build
COPY frontend/ ./
ENV NODE_ENV=production
RUN npm run build

# ── Stage 2: Python runtime ────────────────────────────────────────────────
FROM python:3.13-slim AS runtime

# curl is used by the Docker HEALTHCHECK directive below.
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PORT=5000 \
    FLASK_ENV=production

WORKDIR /app

# Install Python deps first for layer caching
COPY requirements.txt ./
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install -r requirements.txt

# Copy backend
COPY app.py config.py models.py ./
COPY routes/ ./routes/
COPY utils/ ./utils/
COPY seed.py seed_demo_user.py seed_dub_schedule.py ./
COPY sync_anilist.py sync_dub_animeschedule.py sync_dub_crunchyroll.py ./
COPY migrate_watchlist.py ./

# Copy built frontend from stage 1 — app.py serves /frontend/dist if present.
COPY --from=frontend /app/frontend/dist ./frontend/dist

# Fly volume mount point. The DB lives here so it survives redeploys.
RUN mkdir -p /data
ENV DATABASE_URL=sqlite:////data/bingery.db

EXPOSE 5000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD curl -fsS http://localhost:5000/api/health || exit 1

# Gunicorn with 2 workers (256 MB Fly VMs handle this comfortably) and a
# generous timeout because chat requests can wait ~60 s on Ollama.
CMD ["gunicorn", "app:app", \
     "--bind", "0.0.0.0:5000", \
     "--workers", "2", \
     "--threads", "4", \
     "--timeout", "180", \
     "--access-logfile", "-", \
     "--error-logfile", "-"]
