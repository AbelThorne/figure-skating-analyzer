# Phase 3 — Authentication, User Management & Deployment

## Overview

Add full authentication, role-based access control, and Docker-based deployment to the Figure Skating Analyzer. Every route (frontend and API) requires authentication. Two roles govern access: **admin** (full control) and **reader** (read-only).

> **Note:** This spec supersedes the lightweight `ADMIN_TOKEN` bearer approach described in the original roadmap (Phase 3.2). A full user management system with roles was chosen because the app needs per-user Google OAuth, role-based UI, and user management — a single shared token cannot support these requirements. The roadmap should be updated to reflect this.

---

## 1. Authentication

### 1.1 JWT Token Strategy

- **Access token:** short-lived (~15 min), sent as `Authorization: Bearer <token>` header
- **Refresh token:** long-lived (~7 days), stored in httpOnly cookie
  - Cookie attributes: `HttpOnly`, `SameSite=Lax`, `Path=/api/auth/refresh`
  - `Secure=true` in production; controlled by `SECURE_COOKIES` env var (default: `true`, set to `false` for local HTTP dev)
  - CSRF mitigated by `SameSite=Lax` + requiring `Content-Type: application/json` header on the refresh endpoint
- **Refresh token revocation:** Users table includes a `token_version` integer (default: 0). The version is embedded in the refresh JWT payload. On logout or user deactivation, `token_version` is incremented, invalidating all existing refresh tokens for that user.
- **JWT signing:** symmetric key from `SECRET_KEY` env var, HS256 algorithm
- **Library:** `PyJWT` + `bcrypt` (via `passlib[bcrypt]`)

### 1.2 Password Login

- `POST /api/auth/login` — accepts `{email, password}`, returns `{access_token, user}` + sets refresh cookie
- `POST /api/auth/refresh` — reads refresh cookie, validates `token_version` against DB, returns new `{access_token}`
- `POST /api/auth/logout` — clears refresh cookie + increments user's `token_version`
- **Password rules:** minimum 8 characters
- **Rate limiting:** max 5 login attempts per email per minute (429 Too Many Requests). Implemented via in-memory counter (acceptable for single-instance deployment).

### 1.3 Google OAuth

- Frontend uses Google Sign-In JavaScript SDK (`@react-oauth/google`)
- User clicks "Se connecter avec Google" → Google returns an ID token
- `POST /api/auth/google` — backend receives the Google ID token, verifies it with Google's public keys (`google-auth` library), extracts email
- Email matching logic (in order):
  1. User with this email exists in DB → set `google_oauth_enabled = true` if not already, issue JWT with their role
  2. Email domain matches an entry in the allowed-domains table → auto-create a **reader** account with `google_oauth_enabled = true`, issue JWT
  3. Neither → reject with 403
- Returns same `{access_token, user}` + refresh cookie response as password login
- **Env var:** `GOOGLE_CLIENT_ID` (required for OAuth, optional overall — if unset, Google button hidden)

### 1.4 Litestar Auth Guard

- A `before_request` guard on all `/api/` routes (except `/api/auth/*`, `GET /api/config`, and `GET /api/health`)
- Extracts JWT from `Authorization` header, validates signature and expiry
- Checks `is_active` on the user record on every request (DB lookup; acceptable for single-instance app with small user count). If `is_active = false` → 401.
- Injects `current_user` (with `id`, `email`, `role`) into request state
- Returns 401 if token missing/invalid/expired
- **Role guard decorator:** `@require_role("admin")` for admin-only endpoints

---

## 2. User Model & Management

### 2.1 User Model

Table `users`:

| Column | Type | Notes |
|--------|------|-------|
| `id` | UUID | Primary key |
| `email` | String(255) | Unique, required |
| `password_hash` | String(255) | Nullable (null for Google-only users) |
| `display_name` | String(255) | Required |
| `role` | Enum(`admin`, `reader`) | Default: `reader` |
| `google_oauth_enabled` | Boolean | Default: false |
| `is_active` | Boolean | Default: true |
| `token_version` | Integer | Default: 0, incremented on logout/deactivation |
| `created_at` | DateTime | Auto |
| `updated_at` | DateTime | Auto |

### 2.2 Allowed Domains

Table `allowed_domains`:

| Column | Type | Notes |
|--------|------|-------|
| `id` | UUID | Primary key |
| `domain` | String(255) | Unique (e.g. `club-toulouse.fr`) |
| `created_by` | UUID FK → users | |
| `created_at` | DateTime | Auto |

### 2.3 First-Run Bootstrap

On application startup:

1. Check if users table is empty
2. If empty and `ADMIN_EMAIL` + `ADMIN_PASSWORD` env vars are set → create admin account
3. If empty and no env vars → `GET /api/config` returns `{setup_required: true}` → frontend shows `/setup` page where the first visitor creates the initial admin account
4. `/setup` route and `POST /api/auth/setup` endpoint are only accessible when user table is empty (guard enforced)

**`POST /api/auth/setup` payload:**
```json
{
  "email": "admin@example.com",
  "password": "...",         // min 8 chars
  "display_name": "Coach",
  "club_name": "My Club",
  "club_short": "MC"
}
```
Creates the admin user and app settings in a single atomic transaction. On success, returns `{access_token, user}` + sets refresh cookie (user is logged in immediately, no separate login step).

### 2.4 Admin Endpoints

All require `admin` role:

- `GET /api/users` — list all users (id, email, display_name, role, is_active, google_oauth_enabled)
- `POST /api/users` — create user `{email, display_name, role, password?}`
- `PATCH /api/users/{id}` — update role, display_name, is_active
- `DELETE /api/users/{id}` — delete user (prevent deleting last admin)
- `GET /api/domains` — list allowed domains
- `POST /api/domains` — add domain `{domain}`
- `DELETE /api/domains/{id}` — remove domain

---

## 3. Club Configuration (Admin Settings)

### 3.1 Settings Model

Move club config from env vars to a single-row DB table `app_settings`:

| Column | Type | Notes |
|--------|------|-------|
| `id` | Integer | Always 1 (single row) |
| `club_name` | String(255) | Required |
| `club_short` | String(50) | Required |
| `logo_path` | String(255) | Nullable, relative path in data dir |
| `current_season` | String(20) | e.g. `2025-2026` |

On first run, seed from `CLUB_NAME` / `CLUB_SHORT` env vars if set.

### 3.2 Config Endpoints

- `GET /api/config` — returns `{club_name, club_short, logo_url, current_season, setup_required}`. This is the only endpoint accessible without auth (needed to show club branding on the login page and detect first-run).
- `PATCH /api/config` — admin-only. Update club name, short, season.
- `POST /api/config/logo` — admin-only. Multipart upload. Stores image in `data/logos/`, updates `logo_path`. Returns new `logo_url`.
- Logo served as a static file by the backend (Litestar static files config for `data/logos/`).

---

## 4. Frontend Auth

### 4.1 Auth Context

- `AuthProvider` React context wrapping the app
- Holds: `user` (email, role, display_name), `accessToken`, `login()`, `loginWithGoogle()`, `logout()`
- On mount: attempt silent refresh via `POST /api/auth/refresh` (cookie-based). If fails → user is unauthenticated.
- All `fetch` calls in `api/client.ts` attach `Authorization: Bearer <token>` header
- 401 responses trigger silent refresh attempt; if that fails → redirect to `/login`
- **Refresh mutex:** concurrent 401s coalesce into a single refresh request (shared promise pattern) to avoid redundant refresh calls

### 4.2 Pages

- **`/login`** — email/password form + "Se connecter avec Google" button (hidden if `GOOGLE_CLIENT_ID` not configured). Club logo + name displayed from `/api/config`. Follows Kinetic Lens design system.
- **`/setup`** — first-run only. Form: admin email, password, display name, club name, club short. Creates admin + app settings in one step.
- **`/settings`** — admin-only. Tabs or sections:
  - **Club:** name, short name, logo upload with preview
  - **Utilisateurs:** table of users with add/edit/delete actions
  - **Domaines autorisés:** list with add/delete

### 4.3 Route Protection

- All routes wrapped in `AuthProvider` → if unauthenticated, redirect to `/login`
- `/setup` only accessible when `setup_required: true`
- `/settings` only accessible for `admin` role (redirect readers to `/`)
- Admin-only UI elements (import button, delete competition, etc.) conditionally rendered based on `user.role`
- Backend enforces all role checks independently — frontend hiding is UX only

---

## 5. Docker & Deployment

### 5.1 Backend Image (`Dockerfile.backend`)

- Base: `python:3.12-slim`
- Install `uv`, copy `pyproject.toml` + `uv.lock`, install deps
- Copy `backend/app/`
- Entrypoint: `uvicorn app.main:app --host 0.0.0.0 --port 8000`
- Volume mount point: `/data` (SQLite DB, PDFs, logos)
- Health check: `GET /api/health` (unauthenticated, returns 200)

### 5.2 Frontend Image (`Dockerfile.frontend`)

- Stage 1: `node:20-alpine`, `npm install` + `npm run build`
- Stage 2: `nginx:alpine`, copy built files + nginx config
- Nginx config: serve static files, proxy `/api/*` to `backend:8000`
- Build arg: `VITE_GOOGLE_CLIENT_ID` (baked into the JS bundle)

### 5.3 Docker Compose (`docker-compose.yml`)

```yaml
services:
  backend:
    build:
      context: .
      dockerfile: Dockerfile.backend
    volumes:
      - app-data:/data
    env_file: .env
    ports:
      - "8000:8000"
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/api/health"]
      interval: 30s
      timeout: 5s
      retries: 3

  frontend:
    build:
      context: .
      dockerfile: Dockerfile.frontend
      args:
        VITE_GOOGLE_CLIENT_ID: ${GOOGLE_CLIENT_ID:-}
    ports:
      - "80:80"
    depends_on:
      - backend

volumes:
  app-data:
```

**Local dev:** `docker compose up` — frontend on `localhost:80`, backend on `localhost:8000`.

**GCP:** Same compose on a VM. GCP load balancer terminates TLS, forwards HTTP to the VM.

### 5.4 Environment Variables (`.env.example`)

| Variable | Required | Default | Purpose |
|----------|----------|---------|---------|
| `SECRET_KEY` | Yes | — | JWT signing key |
| `DATABASE_URL` | No | `sqlite+aiosqlite:///data/skating.db` | DB connection string |
| `ADMIN_EMAIL` | No | — | First-run admin bootstrap |
| `ADMIN_PASSWORD` | No | — | First-run admin bootstrap |
| `CLUB_NAME` | No | — | First-run club name seed |
| `CLUB_SHORT` | No | — | First-run club short seed |
| `GOOGLE_CLIENT_ID` | No | — | Google OAuth (hidden if unset) |
| `PDF_DIR` | No | `/data/pdfs` | PDF storage path |
| `ALLOWED_ORIGINS` | No | `http://localhost:5173` | CORS origins (only needed for local dev; in Docker, nginx proxies API calls same-origin) |
| `SECURE_COOKIES` | No | `true` | Set to `false` for local HTTP dev |

### 5.5 CI/CD — GitHub Actions

Two workflows, one per image, triggered on push to `main` and on tag creation.

**`ci-backend.yml`:**
- Trigger: push to `main` with changes in `backend/**`, or any tag `v*`
- Auth: Workload Identity Federation to GCP (no service account keys)
- Steps: checkout → authenticate to Artifact Registry → build & push `europe-west9-docker.pkg.dev/skating-analyzer/skating-analyzer/backend`
- **Tag on push to main:** short commit SHA (e.g. `backend:abc1234`)
- **Tag on git tag:** the tag name (e.g. `backend:v1.2.0`)

**`ci-frontend.yml`:**
- Trigger: push to `main` with changes in `frontend/**`, or any tag `v*`
- Same auth and registry
- Image: `europe-west9-docker.pkg.dev/skating-analyzer/skating-analyzer/frontend`
- Same tagging strategy

**GCP prerequisites (manual, documented in `.env.example` or README):**
- Artifact Registry repository `skating-analyzer` in `europe-west9`
- Workload Identity Federation pool + provider configured for GitHub Actions
- Service account with `roles/artifactregistry.writer` bound to the WIF provider

### 5.6 Database Abstraction

- `DATABASE_URL` env var drives the SQLAlchemy engine
- Default: SQLite. Switchable to PostgreSQL by changing the URL to `postgresql+asyncpg://...`
- Avoid SQLite-specific SQL in all queries (use SQLAlchemy ORM exclusively)
- Alembic migrations recommended when adding the user/settings tables (new dependency)

---

## 6. Backend Dependencies (New)

Add to `pyproject.toml`:

- `PyJWT>=2.8` — JWT encoding/decoding
- `passlib[bcrypt]>=1.7` — password hashing
- `google-auth>=2.0` — Google ID token verification
- `python-multipart>=0.0.9` — already present, needed for logo upload
- `alembic>=1.13` — database migrations

---

## 7. Verification

1. **First run (no users):** Start app → frontend redirects to `/setup` → create admin → redirected to dashboard
2. **First run (env vars):** Set `ADMIN_EMAIL` + `ADMIN_PASSWORD` → start app → login page shown → admin can log in
3. **Password login:** Admin logs in with email/password → gets access to all features
4. **Google OAuth:** Admin adds allowed domain → user with matching email signs in with Google → auto-created as reader
5. **Role enforcement:** Reader cannot access `/settings`, cannot see import/delete buttons, gets 403 on admin API calls
6. **Token refresh:** Access token expires → frontend silently refreshes → no interruption
7. **Club settings:** Admin uploads logo, changes club name → reflected across the app
8. **User management:** Admin creates/edits/disables users → changes take effect immediately
9. **Docker local:** `docker compose up` → app accessible on `localhost:80`, data persists across restarts
10. **Docker GCP:** Deploy on VM behind LB → app accessible via HTTPS domain
11. **CI push:** Push to `main` with backend changes → GitHub Actions builds and pushes `backend:<sha>` to Artifact Registry
12. **CI tag:** Create git tag `v1.0.0` → both images tagged `v1.0.0` in Artifact Registry
