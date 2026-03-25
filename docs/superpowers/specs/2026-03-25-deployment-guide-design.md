# Deployment Guide — Design Spec

## Context

The figure-skating-analyzer app needs a deployment guide targeting club managers with varying technical levels. The app uses Docker Compose with a Python/Litestar backend (SQLite) and a React SPA frontend (Nginx).

## Goals

- Enable non-technical club managers to deploy via PaaS (Render/Railway)
- Provide a VPS option for technically capable users
- Include helper scripts to minimize manual configuration
- All documentation in French

## Deliverables

1. `docs/deployment-guide.md` — complete guide in French
2. `render.yaml` — Render Blueprint for near-one-click deploy
3. `deploy.sh` — VPS installation script

## Architecture

### Option 1: Render (recommended)

- **Web Service** for the backend (Dockerfile.backend)
- **Static Site** for the frontend (npm build, no Nginx needed)
- **Persistent Disk** mounted at `/data` for SQLite DB + PDFs
- `render.yaml` Blueprint enables one-click setup
- Free tier limitations: 15-min sleep, 1 GB disk, ~30s cold start

### Option 2: Railway

- Uses `docker-compose.yml` directly (Railway native support)
- Persistent volume for `/data`
- No free tier (~5$/month), but no cold starts
- Minimal config — Railway auto-detects docker-compose

### Option 3: VPS + Docker Compose

- Any VPS provider (OVH, Hetzner, DigitalOcean, ~4-5 EUR/month)
- `deploy.sh` script handles: Docker install, repo clone, interactive `.env` setup, `docker compose up`
- HTTPS via Caddy reverse proxy (auto Let's Encrypt)
- Maintenance section: backups, updates, logs

## Guide Structure

1. **Introduction** — comparison table, decision helper
2. **Common prerequisites** — GitHub repo, Google OAuth (optional)
3. **Option 1: Render** — step-by-step with screenshots guidance
4. **Option 2: Railway** — step-by-step
5. **Option 3: VPS** — script-assisted setup
6. **Environment variables reference** — non-technical explanations
7. **Custom domain setup** — buy domain, DNS config, per-platform instructions
8. **Troubleshooting** — common issues and fixes

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `SECRET_KEY` | Yes | Random string for JWT signing |
| `ADMIN_EMAIL` | No | Bootstrap admin account (or use /setup UI) |
| `ADMIN_PASSWORD` | No | Bootstrap admin password |
| `CLUB_NAME` | No | Club display name |
| `CLUB_SHORT` | No | Club abbreviation |
| `DATABASE_URL` | No | Defaults to SQLite at /data/skating.db |
| `GOOGLE_CLIENT_ID` | No | For Google OAuth (button hidden if unset) |
| `ALLOWED_ORIGINS` | No | CORS origins (auto-configured per platform) |
| `SECURE_COOKIES` | No | Defaults to true |

## deploy.sh Behavior

1. Check OS (Debian/Ubuntu required for auto-install)
2. Install Docker + Docker Compose if missing
3. Clone repo from GitHub
4. Generate random `SECRET_KEY`
5. Interactive prompts: club name, admin email, admin password
6. Write `.env` file
7. Run `docker compose up -d --build`
8. Print access URL

## render.yaml Blueprint

Defines two services:
- `backend`: Web Service, Docker, env vars with `generateValue` for SECRET_KEY, disk at `/data`
- `frontend`: Static Site, build command + publish directory, env group reference

## Caddy Integration (VPS option)

A `docker-compose.prod.yml` override that adds a Caddy service:
- Reverse proxies port 80/443 to the frontend container
- Auto-provisions Let's Encrypt certificates
- Requires only setting the domain name

## Out of Scope

- PostgreSQL migration guide (mentioned as possible but not detailed)
- CI/CD pipelines
- Monitoring/alerting setup
- Multi-instance / high-availability
