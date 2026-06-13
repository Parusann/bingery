# Bingery Deployment Plan — free / nearly-free, AI on your home PC

Goal: public, always-on web app for ~$0/year; chat requests routed through
your home computer's Ollama so you pay zero API costs.

## Recommended stack

| Piece | Host | Cost | Notes |
|---|---|---|---|
| Frontend (Vite build) | **Cloudflare Pages** | $0 | Unlimited bandwidth, GitHub CI, free TLS |
| Backend (Flask) | **Fly.io free tier** | $0 | 3 shared-cpu VMs (256 MB), 3 GB persistent volume |
| Database | **SQLite on Fly volume** | $0 | The current `bingery.db` (~200 MB) fits with headroom |
| Ollama tunnel | **Cloudflare Tunnel** (cloudflared) | $0 | Public hostname → home PC `localhost:11434` |
| Tunnel auth | **Cloudflare Access** | $0 (≤50 users) | Service-token gate so only your Fly app can hit Ollama |
| Domain | optional | $0–$12/yr | Skip = use `bingery.pages.dev` + `bingery.fly.dev`; with a domain Cloudflare Registrar is at-cost |

Total fixed cost: **$0** with default subdomains. ~$10/yr with a custom domain.

## Architecture

```
 user browser
     │
     ▼  (HTTPS, served by Cloudflare Pages)
 [ frontend: bingery.pages.dev ]
     │
     ▼  (fetch /api/* → Vite proxy in dev; absolute URL in prod)
 [ backend: bingery.fly.dev ]  ← Flask + SQLite on volume
     │
     ▼  (POST /api/generate, Bearer service token)
 [ cloudflared tunnel: ollama.yourdomain ]
     │
     ▼
 [ your home PC: localhost:11434 Ollama gemma4:e4b ]
```

When the home PC is **off**, the rest of the site stays up. The
`/api/chat/message` route degrades gracefully (returns "AI temporarily
offline" instead of 500ing).

## Why this combo

- Free, no credit card required to start.
- Web app stays public even when your PC reboots — only chat is gated.
- Cloudflare Tunnel is more reliable than ngrok (no expiring URLs, no rate
  limits) and lighter than VPN.
- SQLite on a Fly volume avoids the migration hassle of standing up
  Postgres for ~200 MB of mostly-read anime data.

## Pre-deploy code changes

1. **12-factor the config**. `app.py` should read every secret from `os.environ`:
   - `DATABASE_URL` (default to `sqlite:////data/bingery.db` in prod)
   - `JWT_SECRET_KEY`, `SECRET_KEY`
   - `OLLAMA_BASE_URL` (e.g. `https://ollama.yourdomain`)
   - `OLLAMA_MODEL` (`gemma4:e4b`)
   - `OLLAMA_CF_ACCESS_CLIENT_ID` / `OLLAMA_CF_ACCESS_CLIENT_SECRET` (Cloudflare
     Access service token; or `OLLAMA_EXTRA_HEADERS` as a JSON escape hatch)
   - `AI_PROVIDER` (`ollama` or `anthropic` as a fallback)
   - `EMAIL_PROVIDER=brevo`, `BREVO_API_KEY`, `EMAIL_FROM` (sign-up codes)
   - `ADMIN_SYNC_SECRET` (admin sync endpoints)
2. **Graceful Ollama-offline path**. In `utils/ai_provider.py`, catch
   ConnectionError + timeouts; return a structured `provider_unavailable`
   error that `chatbot.py` converts to a friendly 503 response.
3. **CORS**. Flask must allow the Cloudflare Pages origin
   (`https://bingery.pages.dev`). Add `flask-cors` with that one allowed
   origin.
4. **SPA serving** in prod. Build `frontend/` to `frontend/dist`,
   `app.py` already serves `frontend/dist/index.html` for unknown
   non-API paths. Verify before deploying.
5. **Dockerfile** at repo root: `python:3.13-slim`, copy code, install
   requirements, expose 5000, run `gunicorn 'app:app' --workers 2 --bind 0.0.0.0:5000`.
6. **`fly.toml`** with one volume mount (`/data`), env vars set via `fly secrets`.

## Deploy in order

1. **Backend → Fly.io**
   - `fly launch` (no Postgres, mount volume `/data`)
   - `fly secrets set JWT_SECRET_KEY=… SECRET_KEY=… CORS_ORIGINS=… OLLAMA_BASE_URL=… OLLAMA_CF_ACCESS_CLIENT_ID=… OLLAMA_CF_ACCESS_CLIENT_SECRET=… EMAIL_PROVIDER=brevo BREVO_API_KEY=… EMAIL_FROM=… ADMIN_SYNC_SECRET=…`
     (`FLASK_ENV=production` is set in `fly.toml`, so the email secrets are
     required — the app refuses to boot without them)
   - `fly deploy`
   - `fly ssh console` → copy `bingery.db` to `/data/bingery.db`
2. **Ollama tunnel → home PC**
   - Install `cloudflared` (winget install Cloudflare.cloudflared)
   - `cloudflared tunnel login` (auths against your Cloudflare account)
   - `cloudflared tunnel create bingery-ollama`
   - Create `~/.cloudflared/config.yml` pointing `ollama.yourdomain` →
     `http://localhost:11434`
   - `cloudflared tunnel route dns bingery-ollama ollama.yourdomain`
   - **Lock it down**: Cloudflare Zero Trust → Access → Application →
     `ollama.yourdomain` → policy requires a service token. Embed that
     token in the Fly secret so only your backend can hit it.
   - Install as Windows service: `cloudflared service install` →
     auto-starts on boot.
3. **Frontend → Cloudflare Pages**
   - Connect GitHub repo → branch `main`
   - Build command: `cd frontend && npm ci && npm run build`
   - Output dir: `frontend/dist`
   - Env var: `VITE_API_URL=https://bingery.fly.dev`
4. **DNS** (if using a custom domain)
   - Apex / `www` → Cloudflare Pages
   - `api` → Fly.io app (add custom hostname in Fly dashboard)
   - `ollama` → already routed by `cloudflared tunnel route dns`

## Trade-offs to know

- **Cold start on Fly free tier**: ~5–10 s on first request after the VM
  scales down. Fix later with `auto_stop_machines = false` (still free
  if you stay under the 3-VM limit).
- **Home PC reliability**: when it's off, chat returns the graceful
  503. Everything else (discover, schedule, for-you, collections,
  stats, compare) keeps working from the cloud.
- **No horizontal scaling** with SQLite-on-volume. Fine for a portfolio
  site; migrate to Neon Postgres ($0 free tier) only if traffic actually
  grows.

## Cheaper-still alternative (if you don't mind site going down with PC)

Run everything on your home PC behind a single Cloudflare Tunnel:

- `cloudflared` exposes Flask (port 5000) at `bingery.yourdomain`
- Flask serves the built frontend itself (no Cloudflare Pages)
- Ollama stays on `localhost:11434`, never exposed

Cost: $0. Site goes down whenever your PC sleeps or reboots. Acceptable
for a personal project; not great for showing recruiters.

## Things deferred

- OAuth / social login. Email + password with verification codes shipped
  (see `routes/auth.py` + `utils/email_provider.py`); social login would be
  the next add.
- `ANIMESCHEDULE_API_KEY` re-registration if you want real future-dub
  data instead of the synthetic 8-week lag.
- Production logging (Fly's built-in is fine to start; Sentry free tier
  is the next step).
- Rate limiting on `/api/chat/message`. Flask-Limiter + in-process
  storage is plenty for personal scale.
