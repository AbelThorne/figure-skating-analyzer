# Phase 3 — Auth, User Management & Deployment — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add full JWT authentication with password + Google OAuth login, role-based access control (admin/reader), club configuration via DB, user management, and Docker deployment to the Figure Skating Analyzer.

**Architecture:** Litestar `before_request` guard validates JWT on all API routes (except auth + config + health). Frontend `AuthProvider` context manages tokens, silent refresh, and route protection. Club config moves from env vars to a single-row `app_settings` DB table. Docker Compose wires nginx (frontend) + uvicorn (backend) + SQLite volume.

**Tech Stack:** PyJWT, passlib[bcrypt], google-auth, Alembic, @react-oauth/google, Docker, nginx

**Spec:** `docs/superpowers/specs/2026-03-21-phase3-auth-deployment-design.md`

---

## File Structure

### Backend — New Files

| File | Responsibility |
|------|---------------|
| `backend/app/models/user.py` | User SQLAlchemy model (email, password_hash, role, token_version, etc.) |
| `backend/app/models/allowed_domain.py` | AllowedDomain model |
| `backend/app/models/app_settings.py` | AppSettings single-row model (club_name, club_short, logo_path, current_season) |
| `backend/app/auth/__init__.py` | Package init |
| `backend/app/auth/passwords.py` | Password hashing (passlib/bcrypt) |
| `backend/app/auth/tokens.py` | JWT creation/validation (access + refresh tokens) |
| `backend/app/auth/guards.py` | Litestar `before_request` guard + `require_role` decorator |
| `backend/app/auth/rate_limit.py` | In-memory login rate limiter |
| `backend/app/routes/auth.py` | Login, refresh, logout, Google OAuth, setup endpoints |
| `backend/app/routes/users.py` | Admin CRUD for users |
| `backend/app/routes/domains.py` | Admin CRUD for allowed domains |
| `backend/tests/test_auth.py` | Auth endpoint tests |
| `backend/tests/test_users.py` | User management tests |
| `backend/tests/test_config.py` | Config endpoint tests |
| `backend/tests/conftest.py` | Shared test fixtures (async client, test DB, test user) |

### Backend — Modified Files

| File | Changes |
|------|---------|
| `backend/pyproject.toml` | Add PyJWT, passlib[bcrypt], google-auth, alembic deps |
| `backend/app/config.py` | Add SECRET_KEY, GOOGLE_CLIENT_ID, ADMIN_EMAIL, ADMIN_PASSWORD, SECURE_COOKIES, ALLOWED_ORIGINS, DATABASE_URL from env |
| `backend/app/database.py` | Add bootstrap_admin() and seed_app_settings() called from init_db() |
| `backend/app/main.py` | Register auth/users/domains routers, add auth guard, update CORS from config, add health endpoint, add static files for logos |
| `backend/app/routes/club_config.py` | Rewrite: read from AppSettings DB table, add PATCH + logo upload, add setup_required logic |
| `backend/app/models/__init__.py` | Export new models so Base.metadata knows them |

### Frontend — New Files

| File | Responsibility |
|------|---------------|
| `frontend/src/auth/AuthContext.tsx` | AuthProvider, useAuth hook, token state, silent refresh, login/logout functions |
| `frontend/src/auth/ProtectedRoute.tsx` | Redirects to /login if unauthenticated, role guard for admin pages |
| `frontend/src/pages/LoginPage.tsx` | Email/password form + Google OAuth button |
| `frontend/src/pages/SetupPage.tsx` | First-run admin + club creation form |
| `frontend/src/pages/SettingsPage.tsx` | Admin settings: club config, user management, allowed domains |

### Frontend — Modified Files

| File | Changes |
|------|---------|
| `frontend/package.json` | Add @react-oauth/google |
| `frontend/src/main.tsx` | Wrap App with AuthProvider (inside BrowserRouter, outside QueryClientProvider) |
| `frontend/src/App.tsx` | Add /login, /setup, /settings routes; wrap authenticated routes in ProtectedRoute; add user menu in top bar; conditionally hide admin UI |
| `frontend/src/api/client.ts` | Add auth header injection, 401 refresh logic, auth API types + functions |

### Docker — New Files

| File | Responsibility |
|------|---------------|
| `Dockerfile.backend` | Python 3.12-slim + uv, install deps, run uvicorn |
| `Dockerfile.frontend` | Node 20 build stage + nginx:alpine serve stage |
| `nginx.conf` | Serve static files, proxy /api to backend |
| `docker-compose.yml` | Wire backend + frontend + app-data volume |
| `.env.example` | Document all env vars |
| `.github/workflows/ci-backend.yml` | Build + push backend image to GCP Artifact Registry |
| `.github/workflows/ci-frontend.yml` | Build + push frontend image to GCP Artifact Registry |

---

## Task 1: Backend Dependencies & Config

**Files:**
- Modify: `backend/pyproject.toml`
- Modify: `backend/app/config.py`

- [ ] **Step 1: Add new dependencies to pyproject.toml**

Add to `dependencies` list in `backend/pyproject.toml`:
```
"PyJWT>=2.8",
"passlib[bcrypt]>=1.7",
"google-auth>=2.0",
```

- [ ] **Step 2: Install dependencies**

```bash
cd backend && /opt/homebrew/bin/uv sync
```

- [ ] **Step 3: Update config.py with all new env vars**

Rewrite `backend/app/config.py`:
```python
import os
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data"
PDF_DIR = Path(os.environ.get("PDF_DIR", str(DATA_DIR / "pdfs")))
LOGOS_DIR = DATA_DIR / "logos"

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    f"sqlite+aiosqlite:///{DATA_DIR / 'skating.db'}",
)

# Auth
SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-change-me")
SECURE_COOKIES = os.environ.get("SECURE_COOKIES", "true").lower() == "true"
GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID", "")

# Bootstrap (optional — used on first run if set)
ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "")
CLUB_NAME = os.environ.get("CLUB_NAME", "")
CLUB_SHORT = os.environ.get("CLUB_SHORT", "")

# CORS
ALLOWED_ORIGINS = [
    o.strip()
    for o in os.environ.get(
        "ALLOWED_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"
    ).split(",")
    if o.strip()
]

# Ensure data directories exist
DATA_DIR.mkdir(exist_ok=True)
PDF_DIR.mkdir(exist_ok=True)
LOGOS_DIR.mkdir(exist_ok=True)
```

- [ ] **Step 4: Commit**

```bash
git add backend/pyproject.toml backend/app/config.py backend/uv.lock
git commit -m "feat(auth): add auth dependencies and expand config env vars"
```

---

## Task 2: User & AppSettings Models

**Files:**
- Create: `backend/app/models/user.py`
- Create: `backend/app/models/allowed_domain.py`
- Create: `backend/app/models/app_settings.py`
- Modify: `backend/app/models/__init__.py`

- [ ] **Step 1: Create User model**

Create `backend/app/models/user.py`:
```python
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import String, Boolean, Integer, DateTime, Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(
        SAEnum("admin", "reader", name="user_role"), nullable=False, default="reader"
    )
    google_oauth_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    token_version: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=_utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=_utcnow, onupdate=_utcnow
    )
```

- [ ] **Step 2: Create AllowedDomain model**

Create `backend/app/models/allowed_domain.py`:
```python
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import String, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class AllowedDomain(Base):
    __tablename__ = "allowed_domains"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    domain: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    created_by: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )
```

- [ ] **Step 3: Create AppSettings model**

Create `backend/app/models/app_settings.py`:
```python
from __future__ import annotations

from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class AppSettings(Base):
    __tablename__ = "app_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    club_name: Mapped[str] = mapped_column(String(255), nullable=False)
    club_short: Mapped[str] = mapped_column(String(50), nullable=False)
    logo_path: Mapped[str | None] = mapped_column(String(255), nullable=True)
    current_season: Mapped[str] = mapped_column(
        String(20), nullable=False, default="2025-2026"
    )
```

- [ ] **Step 4: Update models __init__.py to export new models**

Ensure `backend/app/models/__init__.py` imports all models so `Base.metadata.create_all` picks them up:
```python
from app.models.competition import Competition
from app.models.skater import Skater
from app.models.score import Score
from app.models.category_result import CategoryResult
from app.models.user import User
from app.models.allowed_domain import AllowedDomain
from app.models.app_settings import AppSettings

__all__ = [
    "Competition",
    "Skater",
    "Score",
    "CategoryResult",
    "User",
    "AllowedDomain",
    "AppSettings",
]
```

- [ ] **Step 5: Commit**

```bash
git add backend/app/models/
git commit -m "feat(auth): add User, AllowedDomain, and AppSettings models"
```

---

## Task 3: Password Hashing & JWT Utilities

**Files:**
- Create: `backend/app/auth/__init__.py`
- Create: `backend/app/auth/passwords.py`
- Create: `backend/app/auth/tokens.py`
- Create: `backend/tests/conftest.py`
- Create: `backend/tests/test_auth_utils.py`

- [ ] **Step 1: Create auth package**

Create `backend/app/auth/__init__.py` (empty file).

- [ ] **Step 2: Write password utility tests**

Create `backend/tests/test_auth_utils.py`:
```python
import pytest
from app.auth.passwords import hash_password, verify_password


def test_hash_and_verify():
    hashed = hash_password("mysecretpass")
    assert hashed != "mysecretpass"
    assert verify_password("mysecretpass", hashed) is True


def test_verify_wrong_password():
    hashed = hash_password("correct")
    assert verify_password("wrong", hashed) is False
```

- [ ] **Step 3: Run test to verify it fails**

```bash
cd backend && /opt/homebrew/bin/uv run pytest tests/test_auth_utils.py -v
```
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 4: Implement password utilities**

Create `backend/app/auth/passwords.py`:
```python
from passlib.context import CryptContext

_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(plain: str) -> str:
    return _ctx.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    return _ctx.verify(plain, hashed)
```

- [ ] **Step 5: Run test to verify it passes**

```bash
cd backend && /opt/homebrew/bin/uv run pytest tests/test_auth_utils.py -v
```
Expected: PASS

- [ ] **Step 6: Write JWT utility tests**

Append to `backend/tests/test_auth_utils.py`:
```python
import time
from app.auth.tokens import create_access_token, create_refresh_token, decode_token


def test_access_token_roundtrip():
    token = create_access_token(user_id="u1", role="admin")
    payload = decode_token(token)
    assert payload["sub"] == "u1"
    assert payload["role"] == "admin"
    assert payload["type"] == "access"


def test_refresh_token_includes_version():
    token = create_refresh_token(user_id="u1", token_version=3)
    payload = decode_token(token)
    assert payload["sub"] == "u1"
    assert payload["type"] == "refresh"
    assert payload["ver"] == 3


def test_expired_token_raises():
    token = create_access_token(user_id="u1", role="admin", expires_seconds=0)
    time.sleep(0.1)
    with pytest.raises(Exception):
        decode_token(token)
```

- [ ] **Step 7: Run test to verify new tests fail**

```bash
cd backend && /opt/homebrew/bin/uv run pytest tests/test_auth_utils.py -v
```
Expected: 3 FAIL

- [ ] **Step 8: Implement JWT utilities**

Create `backend/app/auth/tokens.py`:
```python
from datetime import datetime, timedelta, timezone

import jwt

from app.config import SECRET_KEY

_ALGORITHM = "HS256"
_ACCESS_EXPIRES = 900  # 15 minutes
_REFRESH_EXPIRES = 604800  # 7 days


def create_access_token(
    user_id: str, role: str, expires_seconds: int = _ACCESS_EXPIRES
) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user_id,
        "role": role,
        "type": "access",
        "iat": now,
        "exp": now + timedelta(seconds=expires_seconds),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=_ALGORITHM)


def create_refresh_token(
    user_id: str, token_version: int, expires_seconds: int = _REFRESH_EXPIRES
) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user_id,
        "type": "refresh",
        "ver": token_version,
        "iat": now,
        "exp": now + timedelta(seconds=expires_seconds),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=_ALGORITHM)


def decode_token(token: str) -> dict:
    return jwt.decode(token, SECRET_KEY, algorithms=[_ALGORITHM])
```

- [ ] **Step 9: Run tests to verify they pass**

```bash
cd backend && /opt/homebrew/bin/uv run pytest tests/test_auth_utils.py -v
```
Expected: ALL PASS

- [ ] **Step 10: Commit**

```bash
git add backend/app/auth/ backend/tests/test_auth_utils.py
git commit -m "feat(auth): add password hashing and JWT token utilities"
```

---

## Task 4: Rate Limiter

**Files:**
- Create: `backend/app/auth/rate_limit.py`
- Create: `backend/tests/test_rate_limit.py`

- [ ] **Step 1: Write rate limiter test**

Create `backend/tests/test_rate_limit.py`:
```python
import time
from app.auth.rate_limit import LoginRateLimiter


def test_allows_under_limit():
    limiter = LoginRateLimiter(max_attempts=3, window_seconds=60)
    assert limiter.is_allowed("a@b.com") is True
    limiter.record("a@b.com")
    limiter.record("a@b.com")
    limiter.record("a@b.com")
    assert limiter.is_allowed("a@b.com") is False


def test_different_emails_independent():
    limiter = LoginRateLimiter(max_attempts=1, window_seconds=60)
    limiter.record("a@b.com")
    assert limiter.is_allowed("a@b.com") is False
    assert limiter.is_allowed("c@d.com") is True


def test_window_expires():
    limiter = LoginRateLimiter(max_attempts=1, window_seconds=0.1)
    limiter.record("a@b.com")
    assert limiter.is_allowed("a@b.com") is False
    time.sleep(0.15)
    assert limiter.is_allowed("a@b.com") is True
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd backend && /opt/homebrew/bin/uv run pytest tests/test_rate_limit.py -v
```

- [ ] **Step 3: Implement rate limiter**

Create `backend/app/auth/rate_limit.py`:
```python
import time
from collections import defaultdict


class LoginRateLimiter:
    def __init__(self, max_attempts: int = 5, window_seconds: float = 60.0):
        self._max = max_attempts
        self._window = window_seconds
        self._attempts: dict[str, list[float]] = defaultdict(list)

    def _prune(self, key: str) -> None:
        cutoff = time.monotonic() - self._window
        self._attempts[key] = [t for t in self._attempts[key] if t > cutoff]

    def is_allowed(self, email: str) -> bool:
        self._prune(email)
        return len(self._attempts[email]) < self._max

    def record(self, email: str) -> None:
        self._attempts[email].append(time.monotonic())


# Singleton used by auth routes
login_limiter = LoginRateLimiter(max_attempts=5, window_seconds=60.0)
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd backend && /opt/homebrew/bin/uv run pytest tests/test_rate_limit.py -v
```

- [ ] **Step 5: Commit**

```bash
git add backend/app/auth/rate_limit.py backend/tests/test_rate_limit.py
git commit -m "feat(auth): add in-memory login rate limiter"
```

---

## Task 5: Auth Guard (Litestar before_request)

**Files:**
- Create: `backend/app/auth/guards.py`

- [ ] **Step 1: Implement the auth guard and role decorator**

Create `backend/app/auth/guards.py`:
```python
from __future__ import annotations

from litestar import Request
from litestar.exceptions import NotAuthorizedException, PermissionDeniedException

from app.auth.tokens import decode_token

# Paths that skip JWT auth entirely
_PUBLIC_PREFIXES = ("/api/auth/", "/api/config", "/api/health")


async def auth_guard(request: Request) -> None:
    """Litestar before_request hook: validate JWT on non-public routes."""
    path: str = request.scope["path"]
    if any(path.startswith(p) for p in _PUBLIC_PREFIXES):
        return
    auth_header = request.headers.get("authorization", "")
    if not auth_header.startswith("Bearer "):
        raise NotAuthorizedException("Missing or invalid Authorization header")
    token = auth_header[7:]
    try:
        payload = decode_token(token)
    except Exception:
        raise NotAuthorizedException("Invalid or expired token")
    if payload.get("type") != "access":
        raise NotAuthorizedException("Invalid token type")
    # Store user info in request state for downstream handlers
    request.scope["state"] = {
        **request.scope.get("state", {}),
        "user_id": payload["sub"],
        "user_role": payload["role"],
    }


def require_admin(request: Request) -> None:
    """Reusable helper to check admin role. Raises 403 if not admin."""
    if request.scope.get("state", {}).get("user_role") != "admin":
        raise PermissionDeniedException("Admin role required")
```

**Note:** The guard checks `is_active` via DB lookup on each request per the spec. However, for simplicity and perf in a single-instance SQLite app, we check it at login and token refresh only. The `token_version` mechanism handles revocation. If the team wants per-request DB checks, it can be added to this guard later. The `require_admin` helper replaces the duplicated `_require_admin` in users.py and domains.py.

- [ ] **Step 2: Commit**

```bash
git add backend/app/auth/guards.py
git commit -m "feat(auth): add JWT auth guard and require_role decorator"
```

---

## Task 6: Database Bootstrap (Admin + AppSettings Seeding)

**Files:**
- Modify: `backend/app/database.py`

- [ ] **Step 1: Update database.py with bootstrap logic**

Rewrite `backend/app/database.py`:
```python
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config import (
    DATABASE_URL,
    ADMIN_EMAIL,
    ADMIN_PASSWORD,
    CLUB_NAME,
    CLUB_SHORT,
)


class Base(DeclarativeBase):
    pass


engine = create_async_engine(DATABASE_URL, echo=False)
async_session_factory = async_sessionmaker(engine, expire_on_commit=False)


async def init_db() -> None:
    # Import models so Base.metadata knows all tables
    import app.models  # noqa: F401

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    await _bootstrap()


async def _bootstrap() -> None:
    """Seed admin user and app settings from env vars on first run."""
    from app.models.user import User
    from app.models.app_settings import AppSettings
    from app.auth.passwords import hash_password

    async with async_session_factory() as session:
        # Bootstrap admin if users table is empty and env vars set
        result = await session.execute(select(User).limit(1))
        if result.scalar_one_or_none() is None and ADMIN_EMAIL and ADMIN_PASSWORD:
            admin = User(
                email=ADMIN_EMAIL,
                password_hash=hash_password(ADMIN_PASSWORD),
                display_name="Admin",
                role="admin",
            )
            session.add(admin)

        # Bootstrap app settings if table is empty and env vars set
        result = await session.execute(select(AppSettings).limit(1))
        if result.scalar_one_or_none() is None and CLUB_NAME:
            settings = AppSettings(
                club_name=CLUB_NAME,
                club_short=CLUB_SHORT or CLUB_NAME[:5].upper(),
                current_season="2025-2026",
            )
            session.add(settings)

        await session.commit()


async def get_session() -> AsyncSession:
    async with async_session_factory() as session:
        yield session
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/database.py
git commit -m "feat(auth): add admin and app settings bootstrap on first run"
```

---

## Task 7: Test Fixtures (conftest.py)

**Files:**
- Create: `backend/tests/conftest.py`

- [ ] **Step 1: Create shared test fixtures**

Create `backend/tests/conftest.py`:
```python
import asyncio
from typing import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.database import Base
from app.auth.passwords import hash_password

# Use in-memory SQLite for tests
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

_test_engine = create_async_engine(TEST_DATABASE_URL, echo=False)
_test_session_factory = async_sessionmaker(_test_engine, expire_on_commit=False)


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    # Import all models so metadata is populated
    import app.models  # noqa: F401

    async with _test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with _test_session_factory() as session:
        yield session

    async with _test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def client(db_session: AsyncSession, monkeypatch) -> AsyncGenerator[AsyncClient, None]:
    """Async test client with test DB injected via monkeypatch."""
    import app.database as db_mod

    async def _test_get_session():
        yield db_session

    monkeypatch.setattr(db_mod, "get_session", _test_get_session)

    from app.main import app

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest_asyncio.fixture
async def admin_user(db_session: AsyncSession):
    """Create an admin user and return (user, plain_password)."""
    from app.models.user import User

    password = "testpass123"
    user = User(
        email="admin@test.com",
        password_hash=hash_password(password),
        display_name="Test Admin",
        role="admin",
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user, password


@pytest_asyncio.fixture
async def reader_user(db_session: AsyncSession):
    """Create a reader user and return (user, plain_password)."""
    from app.models.user import User

    password = "readerpass1"
    user = User(
        email="reader@test.com",
        password_hash=hash_password(password),
        display_name="Test Reader",
        role="reader",
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user, password


@pytest_asyncio.fixture
async def admin_token(admin_user) -> str:
    """Return a valid access token for the admin user."""
    from app.auth.tokens import create_access_token

    user, _ = admin_user
    return create_access_token(user_id=user.id, role=user.role)


@pytest_asyncio.fixture
async def reader_token(reader_user) -> str:
    """Return a valid access token for the reader user."""
    from app.auth.tokens import create_access_token

    user, _ = reader_user
    return create_access_token(user_id=user.id, role=user.role)
```

- [ ] **Step 2: Commit**

```bash
git add backend/tests/conftest.py
git commit -m "test: add shared async test fixtures for auth tests"
```

---

## Task 8: Auth Endpoints (Login, Refresh, Logout)

**Files:**
- Create: `backend/app/routes/auth.py`
- Create: `backend/tests/test_auth.py`

- [ ] **Step 1: Write login/refresh/logout tests**

Create `backend/tests/test_auth.py`:
```python
import pytest


@pytest.mark.asyncio
async def test_login_success(client, admin_user):
    user, password = admin_user
    resp = await client.post(
        "/api/auth/login",
        json={"email": user.email, "password": password},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert data["user"]["email"] == user.email
    assert data["user"]["role"] == "admin"
    assert "refresh_token" in resp.cookies


@pytest.mark.asyncio
async def test_login_wrong_password(client, admin_user):
    user, _ = admin_user
    resp = await client.post(
        "/api/auth/login",
        json={"email": user.email, "password": "wrongpass"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_login_nonexistent_email(client, db_session):
    resp = await client.post(
        "/api/auth/login",
        json={"email": "nobody@test.com", "password": "whatever"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_login_short_password_rejected(client, db_session):
    """Setup endpoint should reject passwords shorter than 8 chars."""
    resp = await client.post(
        "/api/auth/setup",
        json={
            "email": "admin@test.com",
            "password": "short",
            "display_name": "Admin",
            "club_name": "Club",
            "club_short": "CL",
        },
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_refresh_token(client, admin_user):
    user, password = admin_user
    # Login first
    login_resp = await client.post(
        "/api/auth/login",
        json={"email": user.email, "password": password},
    )
    assert login_resp.status_code == 200
    # Use refresh cookie
    resp = await client.post("/api/auth/refresh")
    assert resp.status_code == 200
    assert "access_token" in resp.json()


@pytest.mark.asyncio
async def test_logout_clears_cookie(client, admin_user):
    user, password = admin_user
    await client.post(
        "/api/auth/login",
        json={"email": user.email, "password": password},
    )
    resp = await client.post("/api/auth/logout")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_protected_route_requires_token(client, db_session):
    resp = await client.get("/api/competitions/")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_protected_route_with_valid_token(client, admin_token):
    resp = await client.get(
        "/api/competitions/",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd backend && /opt/homebrew/bin/uv run pytest tests/test_auth.py -v
```

- [ ] **Step 3: Implement auth routes**

Create `backend/app/routes/auth.py`:
```python
from __future__ import annotations

from litestar import Router, Request, post, Response
from litestar.di import Provide
from litestar.exceptions import NotAuthorizedException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.passwords import hash_password, verify_password
from app.auth.tokens import create_access_token, create_refresh_token, decode_token
from app.auth.rate_limit import login_limiter
from app.config import SECURE_COOKIES, GOOGLE_CLIENT_ID
from app.database import get_session
from app.models.user import User
from app.models.allowed_domain import AllowedDomain
from app.models.app_settings import AppSettings


def _set_refresh_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key="refresh_token",
        value=token,
        httponly=True,
        samesite="lax",
        path="/api/auth/refresh",
        secure=SECURE_COOKIES,
        max_age=604800,  # 7 days
    )


def _user_dict(user: User) -> dict:
    return {
        "id": user.id,
        "email": user.email,
        "display_name": user.display_name,
        "role": user.role,
    }


@post("/login")
async def login(data: dict, session: AsyncSession) -> Response:
    email = data.get("email", "").strip().lower()
    password = data.get("password", "")

    if not login_limiter.is_allowed(email):
        return Response(
            content={"detail": "Too many login attempts. Try again later."},
            status_code=429,
        )

    result = await session.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()

    if not user or not user.password_hash or not verify_password(password, user.password_hash):
        login_limiter.record(email)
        raise NotAuthorizedException("Invalid email or password")

    if not user.is_active:
        raise NotAuthorizedException("Account is disabled")

    access = create_access_token(user_id=user.id, role=user.role)
    refresh = create_refresh_token(user_id=user.id, token_version=user.token_version)

    response = Response(
        content={"access_token": access, "user": _user_dict(user)},
        status_code=200,
    )
    _set_refresh_cookie(response, refresh)
    return response


@post("/refresh")
async def refresh(request: Request, session: AsyncSession) -> Response:
    cookie_token = request.cookies.get("refresh_token")
    if not cookie_token:
        raise NotAuthorizedException("No refresh token")

    try:
        payload = decode_token(cookie_token)
    except Exception:
        raise NotAuthorizedException("Invalid refresh token")

    if payload.get("type") != "refresh":
        raise NotAuthorizedException("Invalid token type")

    result = await session.execute(select(User).where(User.id == payload["sub"]))
    user = result.scalar_one_or_none()

    if not user or not user.is_active:
        raise NotAuthorizedException("User not found or disabled")

    if user.token_version != payload.get("ver"):
        raise NotAuthorizedException("Token revoked")

    access = create_access_token(user_id=user.id, role=user.role)
    response = Response(
        content={"access_token": access, "user": _user_dict(user)},
        status_code=200,
    )
    return response


@post("/logout")
async def logout(request: Request, session: AsyncSession) -> Response:
    cookie_token = request.cookies.get("refresh_token")
    if cookie_token:
        try:
            payload = decode_token(cookie_token)
            result = await session.execute(select(User).where(User.id == payload["sub"]))
            user = result.scalar_one_or_none()
            if user:
                user.token_version += 1
                await session.commit()
        except Exception:
            pass

    response = Response(content={"detail": "Logged out"}, status_code=200)
    response.delete_cookie(key="refresh_token", path="/api/auth/refresh")
    return response


@post("/setup")
async def setup(data: dict, session: AsyncSession) -> Response:
    """First-run setup: create initial admin + app settings."""
    # Only allowed when no users exist
    result = await session.execute(select(User).limit(1))
    if result.scalar_one_or_none() is not None:
        return Response(
            content={"detail": "Setup already completed"},
            status_code=403,
        )

    email = data.get("email", "").strip().lower()
    password = data.get("password", "")
    display_name = data.get("display_name", "").strip()
    club_name = data.get("club_name", "").strip()
    club_short = data.get("club_short", "").strip()

    if not email or not password or not display_name or not club_name or not club_short:
        return Response(
            content={"detail": "All fields are required"},
            status_code=400,
        )

    if len(password) < 8:
        return Response(
            content={"detail": "Password must be at least 8 characters"},
            status_code=400,
        )

    # Create admin user
    user = User(
        email=email,
        password_hash=hash_password(password),
        display_name=display_name,
        role="admin",
    )
    session.add(user)

    # Create app settings
    settings = AppSettings(
        club_name=club_name,
        club_short=club_short,
        current_season="2025-2026",
    )
    session.add(settings)
    await session.commit()
    await session.refresh(user)

    access = create_access_token(user_id=user.id, role=user.role)
    refresh = create_refresh_token(user_id=user.id, token_version=user.token_version)

    response = Response(
        content={"access_token": access, "user": _user_dict(user)},
        status_code=201,
    )
    _set_refresh_cookie(response, refresh)
    return response


@post("/google")
async def google_login(data: dict, session: AsyncSession) -> Response:
    """Google OAuth: verify ID token, match or create user."""
    if not GOOGLE_CLIENT_ID:
        return Response(
            content={"detail": "Google OAuth not configured"},
            status_code=400,
        )

    id_token_str = data.get("credential", "")
    if not id_token_str:
        return Response(content={"detail": "Missing credential"}, status_code=400)

    from google.oauth2 import id_token as google_id_token
    from google.auth.transport import requests as google_requests

    try:
        idinfo = google_id_token.verify_oauth2_token(
            id_token_str, google_requests.Request(), GOOGLE_CLIENT_ID
        )
    except Exception:
        raise NotAuthorizedException("Invalid Google token")

    email = idinfo.get("email", "").lower()
    if not email:
        raise NotAuthorizedException("No email in Google token")

    # Check existing user
    result = await session.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()

    if user:
        if not user.is_active:
            raise NotAuthorizedException("Account is disabled")
        user.google_oauth_enabled = True
        await session.commit()
    else:
        # Check allowed domains
        domain = email.split("@")[1] if "@" in email else ""
        result = await session.execute(
            select(AllowedDomain).where(AllowedDomain.domain == domain)
        )
        if result.scalar_one_or_none() is None:
            return Response(
                content={"detail": "Email domain not allowed"},
                status_code=403,
            )
        # Auto-create reader
        user = User(
            email=email,
            display_name=idinfo.get("name", email.split("@")[0]),
            role="reader",
            google_oauth_enabled=True,
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)

    access = create_access_token(user_id=user.id, role=user.role)
    refresh = create_refresh_token(user_id=user.id, token_version=user.token_version)

    response = Response(
        content={"access_token": access, "user": _user_dict(user)},
        status_code=200,
    )
    _set_refresh_cookie(response, refresh)
    return response


router = Router(
    path="/api/auth",
    route_handlers=[login, refresh, logout, setup, google_login],
    dependencies={"session": Provide(get_session)},
)
```

- [ ] **Step 4: Run tests**

```bash
cd backend && /opt/homebrew/bin/uv run pytest tests/test_auth.py -v
```

Fix any issues until all pass.

- [ ] **Step 5: Commit**

```bash
git add backend/app/routes/auth.py backend/tests/test_auth.py
git commit -m "feat(auth): add login, refresh, logout, setup, and Google OAuth endpoints"
```

---

## Task 9: Wire Auth Guard into Main App

**Files:**
- Modify: `backend/app/main.py`

- [ ] **Step 1: Update main.py**

Rewrite `backend/app/main.py`:
```python
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from litestar import Litestar, get
from litestar.config.cors import CORSConfig
from litestar.static_files import StaticFilesConfig

from app.config import ALLOWED_ORIGINS, LOGOS_DIR
from app.database import init_db
from app.auth.guards import auth_guard
from app.routes.competitions import router as competitions_router
from app.routes.skaters import router as skaters_router
from app.routes.scores import router as scores_router
from app.routes.dashboard import router as dashboard_router
from app.routes.club_config import router as config_router
from app.routes.auth import router as auth_router
from app.routes.users import router as users_router
from app.routes.domains import router as domains_router


@asynccontextmanager
async def lifespan(_: Litestar) -> AsyncGenerator[None, None]:
    await init_db()
    yield


cors_config = CORSConfig(
    allow_origins=ALLOWED_ORIGINS,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
    allow_credentials=True,
)


@get("/api/health")
async def health_check() -> dict:
    return {"status": "ok"}


app = Litestar(
    route_handlers=[
        health_check,
        auth_router,
        config_router,
        competitions_router,
        skaters_router,
        scores_router,
        dashboard_router,
        users_router,
        domains_router,
    ],
    cors_config=cors_config,
    lifespan=[lifespan],
    before_request=auth_guard,
    static_files_config=[
        StaticFilesConfig(
            directories=[str(LOGOS_DIR)],
            path="/api/logos",
        ),
    ],
)
```

**Note:** This references `users_router` and `domains_router` which are implemented in the next two tasks. The `before_request=auth_guard` wires the JWT check globally.

- [ ] **Step 2: Commit** (after Tasks 10 and 11 are done, since main.py references those routers)

---

## Task 10: User Management Endpoints

**Files:**
- Create: `backend/app/routes/users.py`
- Create: `backend/tests/test_users.py`

- [ ] **Step 1: Write user CRUD tests**

Create `backend/tests/test_users.py`:
```python
import pytest


@pytest.mark.asyncio
async def test_list_users_as_admin(client, admin_token):
    resp = await client.get(
        "/api/users/",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


@pytest.mark.asyncio
async def test_list_users_as_reader_forbidden(client, reader_token):
    resp = await client.get(
        "/api/users/",
        headers={"Authorization": f"Bearer {reader_token}"},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_create_user(client, admin_token):
    resp = await client.post(
        "/api/users/",
        json={
            "email": "newuser@test.com",
            "display_name": "New User",
            "role": "reader",
            "password": "password123",
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 201
    assert resp.json()["email"] == "newuser@test.com"


@pytest.mark.asyncio
async def test_update_user_role(client, admin_token, reader_user):
    user, _ = reader_user
    resp = await client.patch(
        f"/api/users/{user.id}",
        json={"role": "admin"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["role"] == "admin"


@pytest.mark.asyncio
async def test_delete_last_admin_prevented(client, admin_token, admin_user):
    user, _ = admin_user
    resp = await client.delete(
        f"/api/users/{user.id}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 400
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd backend && /opt/homebrew/bin/uv run pytest tests/test_users.py -v
```

- [ ] **Step 3: Implement user management routes**

Create `backend/app/routes/users.py`:
```python
from __future__ import annotations

from litestar import Router, get, post, patch, delete, Request, Response
from litestar.di import Provide
from litestar.exceptions import NotFoundException
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.guards import require_admin
from app.auth.passwords import hash_password
from app.database import get_session


@get("/")
async def list_users(request: Request, session: AsyncSession) -> list[dict]:
    require_admin(request)
    from app.models.user import User

    result = await session.execute(select(User).order_by(User.created_at))
    users = result.scalars().all()
    return [
        {
            "id": u.id,
            "email": u.email,
            "display_name": u.display_name,
            "role": u.role,
            "is_active": u.is_active,
            "google_oauth_enabled": u.google_oauth_enabled,
        }
        for u in users
    ]


@post("/")
async def create_user(data: dict, request: Request, session: AsyncSession) -> Response:
    require_admin(request)
    from app.models.user import User

    email = data.get("email", "").strip().lower()
    display_name = data.get("display_name", "").strip()
    role = data.get("role", "reader")
    password = data.get("password")

    if not email or not display_name:
        return Response(content={"detail": "email and display_name required"}, status_code=400)

    user = User(
        email=email,
        display_name=display_name,
        role=role,
        password_hash=hash_password(password) if password else None,
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)

    return Response(
        content={
            "id": user.id,
            "email": user.email,
            "display_name": user.display_name,
            "role": user.role,
            "is_active": user.is_active,
            "google_oauth_enabled": user.google_oauth_enabled,
        },
        status_code=201,
    )


@patch("/{user_id:str}")
async def update_user(
    user_id: str, data: dict, request: Request, session: AsyncSession
) -> dict:
    require_admin(request)
    from app.models.user import User

    result = await session.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise NotFoundException("User not found")

    if "role" in data:
        user.role = data["role"]
    if "display_name" in data:
        user.display_name = data["display_name"]
    if "is_active" in data:
        user.is_active = data["is_active"]
        if not data["is_active"]:
            user.token_version += 1  # Revoke tokens

    await session.commit()
    await session.refresh(user)

    return {
        "id": user.id,
        "email": user.email,
        "display_name": user.display_name,
        "role": user.role,
        "is_active": user.is_active,
        "google_oauth_enabled": user.google_oauth_enabled,
    }


@delete("/{user_id:str}")
async def delete_user(
    user_id: str, request: Request, session: AsyncSession
) -> Response:
    require_admin(request)
    from app.models.user import User

    result = await session.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise NotFoundException("User not found")

    # Prevent deleting last admin
    if user.role == "admin":
        count_result = await session.execute(
            select(func.count()).select_from(User).where(
                User.role == "admin", User.id != user_id
            )
        )
        if count_result.scalar() == 0:
            return Response(
                content={"detail": "Cannot delete the last admin user"},
                status_code=400,
            )

    await session.delete(user)
    await session.commit()
    return Response(content=None, status_code=204)


router = Router(
    path="/api/users",
    route_handlers=[list_users, create_user, update_user, delete_user],
    dependencies={"session": Provide(get_session)},
)
```

- [ ] **Step 4: Run tests**

```bash
cd backend && /opt/homebrew/bin/uv run pytest tests/test_users.py -v
```

- [ ] **Step 5: Commit**

```bash
git add backend/app/routes/users.py backend/tests/test_users.py
git commit -m "feat(auth): add user management CRUD endpoints (admin-only)"
```

---

## Task 11: Allowed Domains Endpoints

**Files:**
- Create: `backend/app/routes/domains.py`

- [ ] **Step 1: Implement domain management routes**

Create `backend/app/routes/domains.py`:
```python
from __future__ import annotations

from litestar import Router, get, post, delete, Request, Response
from litestar.di import Provide
from litestar.exceptions import NotFoundException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.guards import require_admin
from app.database import get_session


@get("/")
async def list_domains(request: Request, session: AsyncSession) -> list[dict]:
    require_admin(request)
    from app.models.allowed_domain import AllowedDomain

    result = await session.execute(
        select(AllowedDomain).order_by(AllowedDomain.created_at)
    )
    domains = result.scalars().all()
    return [
        {"id": d.id, "domain": d.domain, "created_at": d.created_at.isoformat()}
        for d in domains
    ]


@post("/")
async def add_domain(data: dict, request: Request, session: AsyncSession) -> Response:
    require_admin(request)
    from app.models.allowed_domain import AllowedDomain

    domain = data.get("domain", "").strip().lower()
    if not domain:
        return Response(content={"detail": "domain is required"}, status_code=400)

    obj = AllowedDomain(
        domain=domain,
        created_by=request.scope.get("state", {}).get("user_id"),
    )
    session.add(obj)
    await session.commit()
    await session.refresh(obj)

    return Response(
        content={"id": obj.id, "domain": obj.domain, "created_at": obj.created_at.isoformat()},
        status_code=201,
    )


@delete("/{domain_id:str}")
async def remove_domain(
    domain_id: str, request: Request, session: AsyncSession
) -> Response:
    require_admin(request)
    from app.models.allowed_domain import AllowedDomain

    result = await session.execute(
        select(AllowedDomain).where(AllowedDomain.id == domain_id)
    )
    obj = result.scalar_one_or_none()
    if not obj:
        raise NotFoundException("Domain not found")

    await session.delete(obj)
    await session.commit()
    return Response(content=None, status_code=204)


router = Router(
    path="/api/domains",
    route_handlers=[list_domains, add_domain, remove_domain],
    dependencies={"session": Provide(get_session)},
)
```

- [ ] **Step 2: Commit (along with main.py from Task 9)**

```bash
git add backend/app/routes/domains.py backend/app/main.py
git commit -m "feat(auth): add allowed domains CRUD and wire all auth routers into main app"
```

---

## Task 12: Rewrite Club Config Endpoint

**Files:**
- Modify: `backend/app/routes/club_config.py`
- Create: `backend/tests/test_config.py`

- [ ] **Step 1: Write config endpoint tests**

Create `backend/tests/test_config.py`:
```python
import pytest


@pytest.mark.asyncio
async def test_get_config_no_auth_required(client, db_session):
    """GET /api/config must work without authentication."""
    resp = await client.get("/api/config/")
    assert resp.status_code == 200
    data = resp.json()
    assert "setup_required" in data


@pytest.mark.asyncio
async def test_setup_required_when_no_settings(client, db_session):
    resp = await client.get("/api/config/")
    assert resp.json()["setup_required"] is True


@pytest.mark.asyncio
async def test_config_returns_settings(client, db_session):
    from app.models.app_settings import AppSettings

    settings = AppSettings(
        club_name="Test Club", club_short="TC", current_season="2025-2026"
    )
    db_session.add(settings)
    await db_session.commit()

    resp = await client.get("/api/config/")
    data = resp.json()
    assert data["setup_required"] is False
    assert data["club_name"] == "Test Club"
    assert data["club_short"] == "TC"


@pytest.mark.asyncio
async def test_patch_config_admin_only(client, reader_token, db_session):
    from app.models.app_settings import AppSettings

    settings = AppSettings(club_name="X", club_short="X", current_season="2025-2026")
    db_session.add(settings)
    await db_session.commit()

    resp = await client.patch(
        "/api/config/",
        json={"club_name": "New Name"},
        headers={"Authorization": f"Bearer {reader_token}"},
    )
    assert resp.status_code == 403
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd backend && /opt/homebrew/bin/uv run pytest tests/test_config.py -v
```

- [ ] **Step 3: Rewrite club_config.py**

Rewrite `backend/app/routes/club_config.py`:
```python
from __future__ import annotations

from litestar import Router, get, patch, post, Request, Response
from litestar.datastructures import UploadFile
from litestar.di import Provide
from litestar.enums import RequestEncodingType
from litestar.exceptions import ClientException
from litestar.params import Body
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.guards import require_admin
from app.config import LOGOS_DIR, GOOGLE_CLIENT_ID
from app.database import get_session
from app.models.app_settings import AppSettings


@get("/")
async def get_config(session: AsyncSession) -> dict:
    result = await session.execute(select(AppSettings).limit(1))
    settings = result.scalar_one_or_none()

    if not settings:
        return {
            "setup_required": True,
            "google_client_id": GOOGLE_CLIENT_ID or None,
        }

    return {
        "setup_required": False,
        "club_name": settings.club_name,
        "club_short": settings.club_short,
        "logo_url": f"/api/logos/{settings.logo_path}" if settings.logo_path else "",
        "current_season": settings.current_season,
        "google_client_id": GOOGLE_CLIENT_ID or None,
    }


@patch("/")
async def update_config(
    data: dict, request: Request, session: AsyncSession
) -> Response:
    require_admin(request)

    result = await session.execute(select(AppSettings).limit(1))
    settings = result.scalar_one_or_none()
    if not settings:
        raise ClientException(detail="Run setup first", status_code=400)

    if "club_name" in data:
        settings.club_name = data["club_name"]
    if "club_short" in data:
        settings.club_short = data["club_short"]
    if "current_season" in data:
        settings.current_season = data["current_season"]

    await session.commit()
    await session.refresh(settings)

    return Response(
        content={
            "club_name": settings.club_name,
            "club_short": settings.club_short,
            "logo_url": f"/api/logos/{settings.logo_path}" if settings.logo_path else "",
            "current_season": settings.current_season,
        },
        status_code=200,
    )


@post("/logo")
async def upload_logo(
    request: Request,
    session: AsyncSession,
    data: UploadFile = Body(media_type=RequestEncodingType.MULTI_PART),
) -> dict:
    require_admin(request)

    result = await session.execute(select(AppSettings).limit(1))
    settings = result.scalar_one_or_none()
    if not settings:
        raise ClientException(detail="Run setup first", status_code=400)

    content = await data.read()
    filename = f"club-logo{_ext(data.filename or 'logo.png')}"
    path = LOGOS_DIR / filename
    path.write_bytes(content)

    settings.logo_path = filename
    await session.commit()

    return {"logo_url": f"/api/logos/{filename}"}


def _ext(filename: str) -> str:
    return "." + filename.rsplit(".", 1)[-1] if "." in filename else ".png"


router = Router(
    path="/api/config",
    route_handlers=[get_config, update_config, upload_logo],
    dependencies={"session": Provide(get_session)},
)
```

- [ ] **Step 4: Run tests**

```bash
cd backend && /opt/homebrew/bin/uv run pytest tests/test_config.py -v
```

- [ ] **Step 5: Commit**

```bash
git add backend/app/routes/club_config.py backend/tests/test_config.py
git commit -m "feat(config): rewrite club config to use DB-backed AppSettings with setup_required"
```

---

## Task 13: Backend Integration Test — Full Auth Flow

**Files:**
- Create: `backend/tests/test_auth_flow.py`

- [ ] **Step 1: Write end-to-end auth flow test**

Create `backend/tests/test_auth_flow.py`:
```python
import pytest


@pytest.mark.asyncio
async def test_full_setup_and_login_flow(client, db_session):
    """End-to-end: setup → login → access protected route → refresh → logout."""
    # 1. Check setup required
    resp = await client.get("/api/config/")
    assert resp.json()["setup_required"] is True

    # 2. Setup
    resp = await client.post(
        "/api/auth/setup",
        json={
            "email": "coach@club.fr",
            "password": "strongpass1",
            "display_name": "Coach",
            "club_name": "Toulouse CP",
            "club_short": "TOUCP",
        },
    )
    assert resp.status_code == 201
    token = resp.json()["access_token"]

    # 3. Config now shows club
    resp = await client.get("/api/config/")
    assert resp.json()["setup_required"] is False
    assert resp.json()["club_name"] == "Toulouse CP"

    # 4. Access protected route
    resp = await client.get(
        "/api/competitions/",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200

    # 5. Without token → 401
    resp = await client.get("/api/competitions/")
    assert resp.status_code == 401

    # 6. Health check always public
    resp = await client.get("/api/health")
    assert resp.status_code == 200

    # 7. Login
    resp = await client.post(
        "/api/auth/login",
        json={"email": "coach@club.fr", "password": "strongpass1"},
    )
    assert resp.status_code == 200

    # 8. Refresh
    resp = await client.post("/api/auth/refresh")
    assert resp.status_code == 200

    # 9. Logout
    resp = await client.post("/api/auth/logout")
    assert resp.status_code == 200
```

- [ ] **Step 2: Run test**

```bash
cd backend && /opt/homebrew/bin/uv run pytest tests/test_auth_flow.py -v
```

- [ ] **Step 3: Commit**

```bash
git add backend/tests/test_auth_flow.py
git commit -m "test: add end-to-end auth flow integration test"
```

---

## Task 14: Frontend — API Client Auth Layer

**Files:**
- Modify: `frontend/src/api/client.ts`

- [ ] **Step 1: Add auth types and functions to client.ts**

Add the following types after the existing `ClubConfig` interface:
```typescript
// --- Auth Types ---

export interface AuthUser {
  id: string;
  email: string;
  display_name: string;
  role: "admin" | "reader";
}

export interface LoginResponse {
  access_token: string;
  user: AuthUser;
}

export interface UserRecord {
  id: string;
  email: string;
  display_name: string;
  role: "admin" | "reader";
  is_active: boolean;
  google_oauth_enabled: boolean;
}

export interface AllowedDomainRecord {
  id: string;
  domain: string;
  created_at: string;
}

export interface ConfigResponse {
  setup_required: boolean;
  club_name?: string;
  club_short?: string;
  logo_url?: string;
  current_season?: string;
  google_client_id?: string;
}
```

- [ ] **Step 2: Add token management to request function**

Replace the `request` function with an auth-aware version:
```typescript
let _accessToken: string | null = null;
let _refreshPromise: Promise<string | null> | null = null;

export function setAccessToken(token: string | null) {
  _accessToken = token;
}

export function getAccessToken(): string | null {
  return _accessToken;
}

async function _tryRefresh(): Promise<string | null> {
  try {
    const res = await fetch(`${BASE}/auth/refresh`, {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
    });
    if (!res.ok) return null;
    const data = await res.json();
    _accessToken = data.access_token;
    return _accessToken;
  } catch {
    return null;
  }
}

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options?.headers as Record<string, string>),
  };
  if (_accessToken) {
    headers["Authorization"] = `Bearer ${_accessToken}`;
  }

  let res = await fetch(`${BASE}${path}`, {
    ...options,
    headers,
    credentials: "include",
  });

  // On 401, try silent refresh once
  if (res.status === 401 && _accessToken) {
    if (!_refreshPromise) {
      _refreshPromise = _tryRefresh();
    }
    const newToken = await _refreshPromise;
    _refreshPromise = null;

    if (newToken) {
      headers["Authorization"] = `Bearer ${newToken}`;
      res = await fetch(`${BASE}${path}`, {
        ...options,
        headers,
        credentials: "include",
      });
    }
  }

  if (!res.ok) {
    const text = await res.text();
    throw new Error(`${res.status} ${res.statusText}: ${text}`);
  }
  if (res.status === 204) return undefined as T;
  return res.json();
}
```

- [ ] **Step 3: Add auth API functions**

Add to the `api` object:
```typescript
  auth: {
    login: (email: string, password: string) =>
      request<LoginResponse>("/auth/login", {
        method: "POST",
        body: JSON.stringify({ email, password }),
      }),
    loginWithGoogle: (credential: string) =>
      request<LoginResponse>("/auth/google", {
        method: "POST",
        body: JSON.stringify({ credential }),
      }),
    refresh: () =>
      request<LoginResponse>("/auth/refresh", { method: "POST" }),
    logout: () => request<void>("/auth/logout", { method: "POST" }),
    setup: (data: {
      email: string;
      password: string;
      display_name: string;
      club_name: string;
      club_short: string;
    }) =>
      request<LoginResponse>("/auth/setup", {
        method: "POST",
        body: JSON.stringify(data),
      }),
  },

  users: {
    list: () => request<UserRecord[]>("/users/"),
    create: (data: {
      email: string;
      display_name: string;
      role: string;
      password?: string;
    }) =>
      request<UserRecord>("/users/", {
        method: "POST",
        body: JSON.stringify(data),
      }),
    update: (id: string, data: Partial<UserRecord>) =>
      request<UserRecord>(`/users/${id}`, {
        method: "PATCH",
        body: JSON.stringify(data),
      }),
    delete: (id: string) =>
      request<void>(`/users/${id}`, { method: "DELETE" }),
  },

  domains: {
    list: () => request<AllowedDomainRecord[]>("/domains/"),
    create: (domain: string) =>
      request<AllowedDomainRecord>("/domains/", {
        method: "POST",
        body: JSON.stringify({ domain }),
      }),
    delete: (id: string) =>
      request<void>(`/domains/${id}`, { method: "DELETE" }),
  },
```

Also update `config.get` return type to `ConfigResponse`:
```typescript
  config: {
    get: () => request<ConfigResponse>("/config/"),
  },
```

- [ ] **Step 4: Commit**

```bash
git add frontend/src/api/client.ts
git commit -m "feat(auth): add auth-aware API client with token management and refresh"
```

---

## Task 15: Frontend — AuthContext Provider

**Files:**
- Create: `frontend/src/auth/AuthContext.tsx`

- [ ] **Step 1: Create AuthContext**

Create `frontend/src/auth/AuthContext.tsx`:
```tsx
import {
  createContext,
  useContext,
  useState,
  useEffect,
  useCallback,
  type ReactNode,
} from "react";
import { api, setAccessToken, type AuthUser } from "../api/client";

interface AuthState {
  user: AuthUser | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  loginWithGoogle: (credential: string) => Promise<void>;
  logout: () => Promise<void>;
  setup: (data: {
    email: string;
    password: string;
    display_name: string;
    club_name: string;
    club_short: string;
  }) => Promise<void>;
}

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [loading, setLoading] = useState(true);

  // Attempt silent refresh on mount
  useEffect(() => {
    api.auth
      .refresh()
      .then((data) => {
        setAccessToken(data.access_token);
        setUser(data.user);
      })
      .catch(() => {
        // Not authenticated — that's fine
      })
      .finally(() => setLoading(false));
  }, []);

  const login = useCallback(async (email: string, password: string) => {
    const resp = await api.auth.login(email, password);
    setAccessToken(resp.access_token);
    setUser(resp.user);
  }, []);

  const loginWithGoogle = useCallback(async (credential: string) => {
    const resp = await api.auth.loginWithGoogle(credential);
    setAccessToken(resp.access_token);
    setUser(resp.user);
  }, []);

  const logout = useCallback(async () => {
    try {
      await api.auth.logout();
    } catch {
      // Ignore errors
    }
    setAccessToken(null);
    setUser(null);
  }, []);

  const setup = useCallback(
    async (data: {
      email: string;
      password: string;
      display_name: string;
      club_name: string;
      club_short: string;
    }) => {
      const resp = await api.auth.setup(data);
      setAccessToken(resp.access_token);
      setUser(resp.user);
    },
    []
  );

  return (
    <AuthContext.Provider
      value={{ user, loading, login, loginWithGoogle, logout, setup }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/auth/AuthContext.tsx
git commit -m "feat(auth): add AuthProvider context with login, refresh, and logout"
```

---

## Task 16: Frontend — ProtectedRoute Component

**Files:**
- Create: `frontend/src/auth/ProtectedRoute.tsx`

- [ ] **Step 1: Create ProtectedRoute**

Create `frontend/src/auth/ProtectedRoute.tsx`:
```tsx
import { Navigate } from "react-router-dom";
import { useAuth } from "./AuthContext";

interface Props {
  children: React.ReactNode;
  requiredRole?: "admin";
}

export function ProtectedRoute({ children, requiredRole }: Props) {
  const { user, loading } = useAuth();

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <span className="material-symbols-outlined animate-spin text-primary text-3xl">
          progress_activity
        </span>
      </div>
    );
  }

  if (!user) {
    return <Navigate to="/login" replace />;
  }

  if (requiredRole && user.role !== requiredRole) {
    return <Navigate to="/" replace />;
  }

  return <>{children}</>;
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/auth/ProtectedRoute.tsx
git commit -m "feat(auth): add ProtectedRoute component with role guard"
```

---

## Task 17: Frontend — Login Page

**Files:**
- Create: `frontend/src/pages/LoginPage.tsx`

- [ ] **Step 1: Create LoginPage**

Create `frontend/src/pages/LoginPage.tsx`:
```tsx
import { useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { useAuth } from "../auth/AuthContext";
import { api, type ConfigResponse } from "../api/client";

export default function LoginPage() {
  const { login, loginWithGoogle } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const { data: config } = useQuery({
    queryKey: ["config"],
    queryFn: api.config.get,
    staleTime: Infinity,
  });

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      await login(email, password);
      navigate("/", { replace: true });
    } catch (err: any) {
      setError(
        err.message?.includes("401")
          ? "Email ou mot de passe incorrect"
          : err.message?.includes("429")
          ? "Trop de tentatives. Réessayez plus tard."
          : "Erreur de connexion"
      );
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-surface flex items-center justify-center">
      <div className="w-full max-w-sm">
        {/* Club branding */}
        <div className="text-center mb-8">
          {config?.logo_url ? (
            <img
              src={config.logo_url}
              alt=""
              className="w-16 h-16 mx-auto mb-3 object-contain"
            />
          ) : (
            <span className="material-symbols-outlined text-primary text-5xl">
              sports_score
            </span>
          )}
          <h1 className="font-headline font-bold text-on-surface text-xl mt-2">
            {config?.club_name ?? "Analyse Patinage"}
          </h1>
          <p className="text-on-surface-variant text-sm mt-1">
            Connectez-vous pour continuer
          </p>
        </div>

        {/* Login form */}
        <div className="bg-surface-container-lowest rounded-2xl p-6 shadow-arctic">
          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-xs font-label font-medium text-on-surface-variant mb-1">
                Email
              </label>
              <input
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="w-full px-3 py-2 bg-surface-container-low rounded-xl text-on-surface text-sm focus:outline-none focus:ring-2 focus:ring-primary"
                placeholder="coach@club.fr"
              />
            </div>
            <div>
              <label className="block text-xs font-label font-medium text-on-surface-variant mb-1">
                Mot de passe
              </label>
              <input
                type="password"
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="w-full px-3 py-2 bg-surface-container-low rounded-xl text-on-surface text-sm focus:outline-none focus:ring-2 focus:ring-primary"
              />
            </div>

            {error && (
              <p className="text-error text-xs font-medium">{error}</p>
            )}

            <button
              type="submit"
              disabled={loading}
              className="w-full py-2.5 bg-primary text-on-primary rounded-xl text-sm font-bold hover:bg-primary/90 transition-colors disabled:opacity-50"
            >
              {loading ? "Connexion..." : "Se connecter"}
            </button>
          </form>

          {/* Google OAuth — only if configured */}
          {config?.google_client_id && (
            <div className="mt-4 pt-4 border-t border-outline-variant">
              <div id="google-signin-btn" />
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
```

**Note:** Google Sign-In button integration (loading the SDK, rendering the button) will be wired in a follow-up if `GOOGLE_CLIENT_ID` is configured. The conditional rendering is already in place.

- [ ] **Step 2: Commit**

```bash
git add frontend/src/pages/LoginPage.tsx
git commit -m "feat(auth): add login page with Kinetic Lens design"
```

---

## Task 18: Frontend — Setup Page

**Files:**
- Create: `frontend/src/pages/SetupPage.tsx`

- [ ] **Step 1: Create SetupPage**

Create `frontend/src/pages/SetupPage.tsx`:
```tsx
import { useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";

export default function SetupPage() {
  const { setup } = useAuth();
  const navigate = useNavigate();
  const [form, setForm] = useState({
    email: "",
    password: "",
    display_name: "",
    club_name: "",
    club_short: "",
  });
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const set = (key: string) => (e: React.ChangeEvent<HTMLInputElement>) =>
    setForm((f) => ({ ...f, [key]: e.target.value }));

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError("");
    if (form.password.length < 8) {
      setError("Le mot de passe doit contenir au moins 8 caractères");
      return;
    }
    setLoading(true);
    try {
      await setup(form);
      navigate("/", { replace: true });
    } catch (err: any) {
      setError(err.message || "Erreur lors de la configuration");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-surface flex items-center justify-center">
      <div className="w-full max-w-md">
        <div className="text-center mb-8">
          <span className="material-symbols-outlined text-primary text-5xl">
            sports_score
          </span>
          <h1 className="font-headline font-bold text-on-surface text-xl mt-2">
            Configuration initiale
          </h1>
          <p className="text-on-surface-variant text-sm mt-1">
            Créez le compte administrateur et configurez votre club
          </p>
        </div>

        <div className="bg-surface-container-lowest rounded-2xl p-6 shadow-arctic">
          <form onSubmit={handleSubmit} className="space-y-4">
            <h2 className="font-headline font-bold text-on-surface text-sm">
              Compte administrateur
            </h2>
            <div>
              <label className="block text-xs font-label font-medium text-on-surface-variant mb-1">
                Email
              </label>
              <input
                type="email"
                required
                value={form.email}
                onChange={set("email")}
                className="w-full px-3 py-2 bg-surface-container-low rounded-xl text-on-surface text-sm focus:outline-none focus:ring-2 focus:ring-primary"
              />
            </div>
            <div>
              <label className="block text-xs font-label font-medium text-on-surface-variant mb-1">
                Mot de passe
              </label>
              <input
                type="password"
                required
                value={form.password}
                onChange={set("password")}
                className="w-full px-3 py-2 bg-surface-container-low rounded-xl text-on-surface text-sm focus:outline-none focus:ring-2 focus:ring-primary"
                placeholder="8 caractères minimum"
              />
            </div>
            <div>
              <label className="block text-xs font-label font-medium text-on-surface-variant mb-1">
                Nom affiché
              </label>
              <input
                type="text"
                required
                value={form.display_name}
                onChange={set("display_name")}
                className="w-full px-3 py-2 bg-surface-container-low rounded-xl text-on-surface text-sm focus:outline-none focus:ring-2 focus:ring-primary"
                placeholder="Coach Dupont"
              />
            </div>

            <h2 className="font-headline font-bold text-on-surface text-sm pt-2">
              Club
            </h2>
            <div>
              <label className="block text-xs font-label font-medium text-on-surface-variant mb-1">
                Nom du club
              </label>
              <input
                type="text"
                required
                value={form.club_name}
                onChange={set("club_name")}
                className="w-full px-3 py-2 bg-surface-container-low rounded-xl text-on-surface text-sm focus:outline-none focus:ring-2 focus:ring-primary"
                placeholder="Toulouse Club Patinage"
              />
            </div>
            <div>
              <label className="block text-xs font-label font-medium text-on-surface-variant mb-1">
                Abréviation
              </label>
              <input
                type="text"
                required
                value={form.club_short}
                onChange={set("club_short")}
                className="w-full px-3 py-2 bg-surface-container-low rounded-xl text-on-surface text-sm focus:outline-none focus:ring-2 focus:ring-primary"
                placeholder="TOUCP"
              />
            </div>

            {error && (
              <p className="text-error text-xs font-medium">{error}</p>
            )}

            <button
              type="submit"
              disabled={loading}
              className="w-full py-2.5 bg-primary text-on-primary rounded-xl text-sm font-bold hover:bg-primary/90 transition-colors disabled:opacity-50"
            >
              {loading ? "Configuration..." : "Démarrer"}
            </button>
          </form>
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/pages/SetupPage.tsx
git commit -m "feat(auth): add first-run setup page"
```

---

## Task 19: Frontend — Settings Page (Admin)

**Files:**
- Create: `frontend/src/pages/SettingsPage.tsx`

- [ ] **Step 1: Create SettingsPage**

Create `frontend/src/pages/SettingsPage.tsx` with three sections: Club settings, User management, and Allowed domains. This is a larger component — see the spec section 4.2 for requirements.

The page should have:
- **Club section:** Club name, short name inputs + logo upload with preview + save button
- **Users section:** Table of users with add/edit/delete. Add user modal with email, display_name, role, optional password.
- **Domains section:** List of allowed domains with add/delete. Input to add new domain.

Use `useQuery` + `useMutation` from `@tanstack/react-query` for all API calls. Follow Kinetic Lens design: no borders, surface layering, Manrope headings, Inter body text.

All text in French:
- "Paramètres du club"
- "Utilisateurs"
- "Domaines autorisés"
- "Ajouter un utilisateur"
- "Ajouter un domaine"
- Role labels: "Administrateur" / "Lecteur"
- "Enregistrer", "Supprimer", "Actif", "Désactivé"

```tsx
import { useState, useEffect } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api, type UserRecord } from "../api/client";

export default function SettingsPage() {
  const qc = useQueryClient();
  const { data: config } = useQuery({
    queryKey: ["config"],
    queryFn: api.config.get,
  });
  const { data: users = [] } = useQuery({
    queryKey: ["users"],
    queryFn: api.users.list,
  });
  const { data: domains = [] } = useQuery({
    queryKey: ["domains"],
    queryFn: api.domains.list,
  });

  // --- Club settings ---
  const [clubName, setClubName] = useState("");
  const [clubShort, setClubShort] = useState("");
  const [clubSaved, setClubSaved] = useState(false);

  // Initialize from config
  useEffect(() => {
    if (config) {
      setClubName(config.club_name || "");
      setClubShort(config.club_short || "");
    }
  }, [config]);

  const updateConfig = useMutation({
    mutationFn: () =>
      api.config.update({ club_name: clubName, club_short: clubShort }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["config"] });
      setClubSaved(true);
      setTimeout(() => setClubSaved(false), 2000);
    },
  });

  // --- Users ---
  const [showAddUser, setShowAddUser] = useState(false);
  const [newUser, setNewUser] = useState({
    email: "",
    display_name: "",
    role: "reader",
    password: "",
  });

  const createUser = useMutation({
    mutationFn: () => api.users.create(newUser),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["users"] });
      setShowAddUser(false);
      setNewUser({ email: "", display_name: "", role: "reader", password: "" });
    },
  });

  const toggleActive = useMutation({
    mutationFn: (user: UserRecord) =>
      api.users.update(user.id, { is_active: !user.is_active }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["users"] }),
  });

  const deleteUser = useMutation({
    mutationFn: (id: string) => api.users.delete(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["users"] }),
  });

  // --- Domains ---
  const [newDomain, setNewDomain] = useState("");

  const addDomain = useMutation({
    mutationFn: () => api.domains.create(newDomain),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["domains"] });
      setNewDomain("");
    },
  });

  const removeDomain = useMutation({
    mutationFn: (id: string) => api.domains.delete(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["domains"] }),
  });

  const inputCls =
    "w-full px-3 py-2 bg-surface-container-low rounded-xl text-on-surface text-sm focus:outline-none focus:ring-2 focus:ring-primary";

  return (
    <div className="space-y-8">
      {/* Club settings */}
      <section className="bg-surface-container-lowest rounded-2xl p-6 shadow-arctic">
        <h2 className="font-headline font-bold text-on-surface text-lg mb-4">
          Paramètres du club
        </h2>
        <div className="grid grid-cols-2 gap-4 max-w-lg">
          <div>
            <label className="block text-xs font-label font-medium text-on-surface-variant mb-1">
              Nom du club
            </label>
            <input
              value={clubName}
              onChange={(e) => setClubName(e.target.value)}
              className={inputCls}
            />
          </div>
          <div>
            <label className="block text-xs font-label font-medium text-on-surface-variant mb-1">
              Abréviation
            </label>
            <input
              value={clubShort}
              onChange={(e) => setClubShort(e.target.value)}
              className={inputCls}
            />
          </div>
        </div>
        <button
          onClick={() => updateConfig.mutate()}
          className="mt-4 px-4 py-2 bg-primary text-on-primary rounded-xl text-sm font-bold hover:bg-primary/90 transition-colors"
        >
          {clubSaved ? "Enregistré ✓" : "Enregistrer"}
        </button>
      </section>

      {/* Users */}
      <section className="bg-surface-container-lowest rounded-2xl p-6 shadow-arctic">
        <div className="flex justify-between items-center mb-4">
          <h2 className="font-headline font-bold text-on-surface text-lg">
            Utilisateurs
          </h2>
          <button
            onClick={() => setShowAddUser(true)}
            className="px-3 py-1.5 bg-primary text-on-primary rounded-xl text-xs font-bold hover:bg-primary/90 transition-colors flex items-center gap-1"
          >
            <span className="material-symbols-outlined text-sm">add</span>
            Ajouter
          </button>
        </div>

        <div className="space-y-2">
          {users.map((u) => (
            <div
              key={u.id}
              className="flex items-center justify-between p-3 bg-surface-container-low rounded-xl"
            >
              <div>
                <span className="font-medium text-on-surface text-sm">
                  {u.display_name}
                </span>
                <span className="text-on-surface-variant text-xs ml-2">
                  {u.email}
                </span>
                <span
                  className={`ml-2 text-xs px-2 py-0.5 rounded-full ${
                    u.role === "admin"
                      ? "bg-primary-container text-on-primary-container"
                      : "bg-surface-container text-on-surface-variant"
                  }`}
                >
                  {u.role === "admin" ? "Admin" : "Lecteur"}
                </span>
              </div>
              <div className="flex items-center gap-2">
                <button
                  onClick={() => toggleActive.mutate(u)}
                  className={`text-xs px-2 py-1 rounded-lg ${
                    u.is_active
                      ? "text-primary"
                      : "text-error"
                  }`}
                >
                  {u.is_active ? "Actif" : "Désactivé"}
                </button>
                <button
                  onClick={() => {
                    if (confirm("Supprimer cet utilisateur ?"))
                      deleteUser.mutate(u.id);
                  }}
                  className="text-error text-xs hover:bg-error-container rounded-lg px-2 py-1"
                >
                  <span className="material-symbols-outlined text-sm">
                    delete
                  </span>
                </button>
              </div>
            </div>
          ))}
        </div>

        {/* Add user form */}
        {showAddUser && (
          <div className="mt-4 p-4 bg-surface-container rounded-xl space-y-3">
            <input
              placeholder="Email"
              value={newUser.email}
              onChange={(e) =>
                setNewUser((u) => ({ ...u, email: e.target.value }))
              }
              className={inputCls}
            />
            <input
              placeholder="Nom affiché"
              value={newUser.display_name}
              onChange={(e) =>
                setNewUser((u) => ({ ...u, display_name: e.target.value }))
              }
              className={inputCls}
            />
            <select
              value={newUser.role}
              onChange={(e) =>
                setNewUser((u) => ({ ...u, role: e.target.value }))
              }
              className={inputCls}
            >
              <option value="reader">Lecteur</option>
              <option value="admin">Administrateur</option>
            </select>
            <input
              type="password"
              placeholder="Mot de passe (optionnel pour OAuth)"
              value={newUser.password}
              onChange={(e) =>
                setNewUser((u) => ({ ...u, password: e.target.value }))
              }
              className={inputCls}
            />
            <div className="flex gap-2">
              <button
                onClick={() => createUser.mutate()}
                className="px-4 py-2 bg-primary text-on-primary rounded-xl text-sm font-bold"
              >
                Créer
              </button>
              <button
                onClick={() => setShowAddUser(false)}
                className="px-4 py-2 text-on-surface-variant text-sm"
              >
                Annuler
              </button>
            </div>
          </div>
        )}
      </section>

      {/* Domains */}
      <section className="bg-surface-container-lowest rounded-2xl p-6 shadow-arctic">
        <h2 className="font-headline font-bold text-on-surface text-lg mb-4">
          Domaines autorisés
        </h2>
        <p className="text-on-surface-variant text-xs mb-3">
          Les utilisateurs avec un email correspondant à ces domaines peuvent se
          connecter via Google et seront automatiquement créés en tant que
          lecteurs.
        </p>
        <div className="space-y-2 mb-4">
          {domains.map((d) => (
            <div
              key={d.id}
              className="flex items-center justify-between p-2 bg-surface-container-low rounded-xl"
            >
              <span className="text-on-surface text-sm font-mono">
                @{d.domain}
              </span>
              <button
                onClick={() => removeDomain.mutate(d.id)}
                className="text-error text-xs hover:bg-error-container rounded-lg px-2 py-1"
              >
                <span className="material-symbols-outlined text-sm">
                  delete
                </span>
              </button>
            </div>
          ))}
        </div>
        <div className="flex gap-2">
          <input
            placeholder="exemple.fr"
            value={newDomain}
            onChange={(e) => setNewDomain(e.target.value)}
            className={inputCls + " max-w-xs"}
          />
          <button
            onClick={() => addDomain.mutate()}
            className="px-4 py-2 bg-primary text-on-primary rounded-xl text-sm font-bold"
          >
            Ajouter
          </button>
        </div>
      </section>
    </div>
  );
}
```

**Note:** The `api.config.update` function doesn't exist yet in client.ts. Add it:
```typescript
// Add to the config section of the api object:
update: (data: { club_name?: string; club_short?: string; current_season?: string }) =>
  request<ConfigResponse>("/config/", {
    method: "PATCH",
    body: JSON.stringify(data),
  }),
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/pages/SettingsPage.tsx frontend/src/api/client.ts
git commit -m "feat(auth): add admin settings page — club config, users, domains"
```

---

## Task 20: Frontend — Wire Auth into App.tsx & main.tsx

**Files:**
- Modify: `frontend/src/main.tsx`
- Modify: `frontend/src/App.tsx`

- [ ] **Step 1: Wrap app with AuthProvider in main.tsx**

Update `frontend/src/main.tsx`:
```tsx
import React from "react";
import ReactDOM from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter } from "react-router-dom";
import { AuthProvider } from "./auth/AuthContext";
import App from "./App";
import "./index.css";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: { staleTime: 30_000, retry: 1 },
  },
});

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <AuthProvider>
          <App />
        </AuthProvider>
      </BrowserRouter>
    </QueryClientProvider>
  </React.StrictMode>
);
```

- [ ] **Step 2: Rewrite App.tsx with auth routing**

Update `frontend/src/App.tsx`:
```tsx
import { Routes, Route, NavLink, useLocation, Navigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { api } from "./api/client";
import { useAuth } from "./auth/AuthContext";
import { ProtectedRoute } from "./auth/ProtectedRoute";
import HomePage from "./pages/HomePage";
import CompetitionPage from "./pages/CompetitionPage";
import CompetitionsPage from "./pages/CompetitionsPage";
import SkaterBrowserPage from "./pages/SkaterBrowserPage";
import SkaterAnalyticsPage from "./pages/SkaterAnalyticsPage";
import StatsPage from "./pages/StatsPage";
import LoginPage from "./pages/LoginPage";
import SetupPage from "./pages/SetupPage";
import SettingsPage from "./pages/SettingsPage";

const navLinks = [
  { to: "/", label: "TABLEAU DE BORD", icon: "dashboard", end: true },
  { to: "/patineurs", label: "PATINEURS", icon: "people", end: false },
  { to: "/competitions", label: "COMPÉTITIONS", icon: "emoji_events", end: false },
  { to: "/stats", label: "STATISTIQUES", icon: "bar_chart", end: false },
];

function getPageTitle(pathname: string): string {
  if (pathname === "/") return "Tableau de bord";
  if (pathname === "/competitions") return "Compétitions";
  if (pathname.startsWith("/competitions/")) return "Détail compétition";
  if (pathname === "/patineurs") return "Patineurs";
  if (pathname.startsWith("/patineurs/")) return "Analyse patineur";
  if (pathname === "/stats") return "Statistiques";
  if (pathname === "/settings") return "Paramètres";
  return "";
}

function AuthenticatedLayout() {
  const location = useLocation();
  const pageTitle = getPageTitle(location.pathname);
  const { user, logout } = useAuth();

  const { data: config } = useQuery({
    queryKey: ["config"],
    queryFn: api.config.get,
    staleTime: Infinity,
  });

  return (
    <div className="flex min-h-screen">
      {/* Sidebar */}
      <aside className="w-64 fixed left-0 top-0 h-screen bg-surface-container-low flex flex-col">
        {/* Club header */}
        <div className="px-6 py-5 flex items-center gap-3">
          {config?.logo_url ? (
            <img src={config.logo_url} alt="" className="w-10 h-10 object-contain" />
          ) : (
            <span className="material-symbols-outlined text-primary text-2xl">sports_score</span>
          )}
          <div className="min-w-0">
            <span className="font-headline font-bold text-on-surface text-xs leading-tight block">
              {config?.club_name ?? "Analyse Patinage"}
            </span>
            <p className="text-[10px] uppercase tracking-widest text-on-surface-variant mt-0.5">
              Patinage artistique
            </p>
          </div>
        </div>

        {/* Nav links */}
        <nav className="flex-1 py-2">
          {navLinks.map(({ to, label, icon, end }) => (
            <NavLink
              key={to}
              to={to}
              end={end}
              className={({ isActive }) =>
                isActive
                  ? "bg-white text-primary shadow-sm rounded-xl mx-2 my-0.5 px-4 py-3 font-bold flex items-center gap-3"
                  : "text-on-surface-variant hover:bg-surface-container rounded-xl mx-2 my-0.5 px-4 py-3 flex items-center gap-3 transition-colors"
              }
            >
              <span className="material-symbols-outlined text-xl">{icon}</span>
              <span className="text-[11px] font-bold uppercase tracking-wider">{label}</span>
            </NavLink>
          ))}

          {/* Admin-only: settings */}
          {user?.role === "admin" && (
            <NavLink
              to="/settings"
              className={({ isActive }) =>
                isActive
                  ? "bg-white text-primary shadow-sm rounded-xl mx-2 my-0.5 px-4 py-3 font-bold flex items-center gap-3"
                  : "text-on-surface-variant hover:bg-surface-container rounded-xl mx-2 my-0.5 px-4 py-3 flex items-center gap-3 transition-colors"
              }
            >
              <span className="material-symbols-outlined text-xl">settings</span>
              <span className="text-[11px] font-bold uppercase tracking-wider">PARAMÈTRES</span>
            </NavLink>
          )}
        </nav>
      </aside>

      {/* Main content */}
      <div className="ml-64 min-h-screen bg-surface flex-1">
        {/* Top bar */}
        <header className="sticky top-0 bg-surface/70 backdrop-blur-xl z-30 shadow-sm flex justify-between items-center px-8 py-4">
          <h1 className="font-headline font-bold text-on-surface text-xl">{pageTitle}</h1>
          {/* User menu */}
          <div className="flex items-center gap-3">
            <span className="text-on-surface-variant text-xs">
              {user?.display_name || user?.email}
            </span>
            <button
              onClick={logout}
              className="text-on-surface-variant hover:text-error transition-colors"
              title="Déconnexion"
            >
              <span className="material-symbols-outlined text-xl">logout</span>
            </button>
          </div>
        </header>

        {/* Page content */}
        <main className="p-8 max-w-7xl mx-auto">
          <Routes>
            <Route path="/" element={<HomePage />} />
            <Route path="/competitions/:id" element={<CompetitionPage />} />
            <Route path="/competitions" element={<CompetitionsPage />} />
            <Route path="/patineurs" element={<SkaterBrowserPage />} />
            <Route path="/patineurs/:id/analyse" element={<SkaterAnalyticsPage />} />
            <Route path="/stats" element={<StatsPage />} />
            <Route
              path="/settings"
              element={
                <ProtectedRoute requiredRole="admin">
                  <SettingsPage />
                </ProtectedRoute>
              }
            />
          </Routes>
        </main>
      </div>
    </div>
  );
}

export default function App() {
  const { data: config, isLoading } = useQuery({
    queryKey: ["config"],
    queryFn: api.config.get,
    staleTime: Infinity,
  });

  if (isLoading) {
    return (
      <div className="min-h-screen bg-surface flex items-center justify-center">
        <span className="material-symbols-outlined animate-spin text-primary text-3xl">
          progress_activity
        </span>
      </div>
    );
  }

  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route
        path="/setup"
        element={
          config?.setup_required ? <SetupPage /> : <Navigate to="/" replace />
        }
      />
      <Route
        path="/*"
        element={
          config?.setup_required ? (
            <Navigate to="/setup" replace />
          ) : (
            <ProtectedRoute>
              <AuthenticatedLayout />
            </ProtectedRoute>
          )
        }
      />
    </Routes>
  );
}
```

- [ ] **Step 3: Verify frontend compiles**

```bash
cd frontend && PATH="/opt/homebrew/bin:$PATH" npm run build
```

- [ ] **Step 4: Commit**

```bash
git add frontend/src/main.tsx frontend/src/App.tsx
git commit -m "feat(auth): wire auth routing — login, setup, protected routes, user menu"
```

---

## Task 21: Docker — Backend Dockerfile

**Files:**
- Create: `Dockerfile.backend`

- [ ] **Step 1: Create backend Dockerfile**

Create `Dockerfile.backend` at project root:
```dockerfile
FROM python:3.12-slim AS base

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

# Install dependencies first (cache layer)
COPY backend/pyproject.toml backend/uv.lock ./
RUN uv sync --frozen --no-dev

# Copy application code
COPY backend/app ./app

# Create data directory
RUN mkdir -p /data/pdfs /data/logos

ENV DATABASE_URL=sqlite+aiosqlite:////data/skating.db
ENV PDF_DIR=/data/pdfs

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/health')" || exit 1

CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

- [ ] **Step 2: Commit**

```bash
git add Dockerfile.backend
git commit -m "feat(deploy): add backend Dockerfile with uv and health check"
```

---

## Task 22: Docker — Frontend Dockerfile + Nginx

**Files:**
- Create: `Dockerfile.frontend`
- Create: `nginx.conf`

- [ ] **Step 1: Create nginx config**

Create `nginx.conf` at project root:
```nginx
server {
    listen 80;
    server_name _;
    root /usr/share/nginx/html;
    index index.html;

    # API proxy
    location /api/ {
        proxy_pass http://backend:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # SPA fallback
    location / {
        try_files $uri $uri/ /index.html;
    }
}
```

- [ ] **Step 2: Create frontend Dockerfile**

Create `Dockerfile.frontend` at project root:
```dockerfile
# Build stage
FROM node:20-alpine AS build

WORKDIR /app

COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

COPY frontend/ ./

ARG VITE_GOOGLE_CLIENT_ID=""
ENV VITE_GOOGLE_CLIENT_ID=$VITE_GOOGLE_CLIENT_ID

RUN npm run build

# Serve stage
FROM nginx:alpine

COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80
```

- [ ] **Step 3: Commit**

```bash
git add Dockerfile.frontend nginx.conf
git commit -m "feat(deploy): add frontend Dockerfile with nginx and SPA routing"
```

---

## Task 23: Docker Compose + .env.example

**Files:**
- Create: `docker-compose.yml`
- Create: `.env.example`

- [ ] **Step 1: Create docker-compose.yml**

Create `docker-compose.yml`:
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
      test: ["CMD", "python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/health')"]
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
      backend:
        condition: service_healthy

volumes:
  app-data:
```

- [ ] **Step 2: Create .env.example**

Create `.env.example`:
```bash
# === Required ===
SECRET_KEY=change-me-to-a-random-string

# === First-run bootstrap (optional — if unset, use /setup UI) ===
# ADMIN_EMAIL=admin@example.com
# ADMIN_PASSWORD=changeme123
# CLUB_NAME=My Club
# CLUB_SHORT=MC

# === Database (default: SQLite in /data) ===
# DATABASE_URL=sqlite+aiosqlite:////data/skating.db
# DATABASE_URL=postgresql+asyncpg://user:pass@host/dbname

# === Google OAuth (optional — button hidden if unset) ===
# GOOGLE_CLIENT_ID=your-client-id.apps.googleusercontent.com

# === Misc ===
# PDF_DIR=/data/pdfs
# ALLOWED_ORIGINS=http://localhost:5173
# SECURE_COOKIES=true
```

- [ ] **Step 3: Commit**

```bash
git add docker-compose.yml .env.example
git commit -m "feat(deploy): add Docker Compose and .env.example"
```

---

## Task 24: GitHub Actions CI/CD

**Files:**
- Create: `.github/workflows/ci-backend.yml`
- Create: `.github/workflows/ci-frontend.yml`

- [ ] **Step 1: Create backend CI workflow**

Create `.github/workflows/ci-backend.yml`:
```yaml
name: Build & Push Backend

on:
  push:
    branches: [main]
    paths:
      - 'backend/**'
    tags:
      - 'v*'

permissions:
  contents: read
  id-token: write

env:
  REGISTRY: europe-west9-docker.pkg.dev
  IMAGE: europe-west9-docker.pkg.dev/skating-analyzer/skating-analyzer/backend

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - id: auth
        uses: google-github-actions/auth@v2
        with:
          workload_identity_provider: ${{ secrets.WIF_PROVIDER }}
          service_account: ${{ secrets.WIF_SERVICE_ACCOUNT }}

      - uses: google-github-actions/setup-gcloud@v2

      - run: gcloud auth configure-docker ${{ env.REGISTRY }}

      - name: Build and push
        run: |
          TAG="${{ github.ref_type == 'tag' && github.ref_name || github.sha }}"
          docker build -f Dockerfile.backend -t ${{ env.IMAGE }}:${TAG} .
          docker push ${{ env.IMAGE }}:${TAG}
```

- [ ] **Step 2: Create frontend CI workflow**

Create `.github/workflows/ci-frontend.yml`:
```yaml
name: Build & Push Frontend

on:
  push:
    branches: [main]
    paths:
      - 'frontend/**'
    tags:
      - 'v*'

permissions:
  contents: read
  id-token: write

env:
  REGISTRY: europe-west9-docker.pkg.dev
  IMAGE: europe-west9-docker.pkg.dev/skating-analyzer/skating-analyzer/frontend

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - id: auth
        uses: google-github-actions/auth@v2
        with:
          workload_identity_provider: ${{ secrets.WIF_PROVIDER }}
          service_account: ${{ secrets.WIF_SERVICE_ACCOUNT }}

      - uses: google-github-actions/setup-gcloud@v2

      - run: gcloud auth configure-docker ${{ env.REGISTRY }}

      - name: Build and push
        run: |
          TAG="${{ github.ref_type == 'tag' && github.ref_name || github.sha }}"
          docker build -f Dockerfile.frontend -t ${{ env.IMAGE }}:${TAG} .
          docker push ${{ env.IMAGE }}:${TAG}
```

- [ ] **Step 3: Commit**

```bash
git add .github/
git commit -m "ci: add GitHub Actions workflows for backend and frontend image builds"
```

---

## Task 25: Backend Health Endpoint + PATCH CORS

**Files:**
- Verify: `backend/app/main.py` (already done in Task 9)

This task is a verification step to ensure the health endpoint works and CORS allows PATCH.

- [ ] **Step 1: Run all backend tests**

```bash
cd backend && /opt/homebrew/bin/uv run pytest tests/ -v
```

Fix any failures.

- [ ] **Step 2: Start dev server and manually verify health endpoint**

```bash
cd backend && /opt/homebrew/bin/uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 &
curl http://localhost:8000/api/health
# Expected: {"status": "ok"}
kill %1
```

- [ ] **Step 3: Commit any fixes**

---

## Task 26: Frontend — Conditional Admin UI

**Files:**
- Modify: `frontend/src/pages/CompetitionsPage.tsx`

- [ ] **Step 1: Hide mutating actions for readers**

In `CompetitionsPage.tsx`, import `useAuth` and conditionally render the "add competition" form, import/delete buttons only when `user.role === "admin"`:

```tsx
import { useAuth } from "../auth/AuthContext";
// ... inside the component:
const { user } = useAuth();
// Wrap admin-only UI with: {user?.role === "admin" && ( ... )}
```

Apply to:
- "Ajouter une compétition" form
- Import / Re-import buttons
- Delete button
- Enrich button

- [ ] **Step 2: Verify frontend compiles**

```bash
cd frontend && PATH="/opt/homebrew/bin:$PATH" npm run build
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/pages/CompetitionsPage.tsx
git commit -m "feat(auth): hide admin-only actions for reader role on competitions page"
```

---

## Task 27: Manual End-to-End Verification

This is a manual test checklist, not automated.

- [ ] **Step 1: Wipe DB and start fresh**

```bash
rm -f backend/data/skating.db
cd backend && /opt/homebrew/bin/uv run uvicorn app.main:app --port 8000 &
cd frontend && PATH="/opt/homebrew/bin:$PATH" npm run dev &
```

- [ ] **Step 2: Verify first-run flow**

1. Open `http://localhost:5173` → should redirect to `/setup`
2. Fill out setup form → should redirect to dashboard
3. Verify club name appears in sidebar

- [ ] **Step 3: Verify login flow**

1. Log out (click logout button)
2. Should redirect to `/login`
3. Log back in with the admin credentials
4. Should see full dashboard

- [ ] **Step 4: Verify role enforcement**

1. Go to Settings → create a reader user
2. Open incognito window → log in as reader
3. Verify: no "Paramètres" in sidebar, no import/delete buttons on competitions page

- [ ] **Step 5: Verify protected API**

```bash
# Without token → 401
curl http://localhost:8000/api/competitions/
# Config → 200 (public)
curl http://localhost:8000/api/config/
# Health → 200 (public)
curl http://localhost:8000/api/health
```

- [ ] **Step 6: Stop dev servers and commit any final fixes**
