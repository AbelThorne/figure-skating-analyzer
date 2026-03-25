# Skater Role Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a `skater` role that restricts users to viewing only their linked skater(s), with full backend guards and a dedicated frontend experience.

**Architecture:** New `user_skaters` association table links users to skaters. Backend guards enforce per-skater access for the `skater` role and block access to all other endpoints. Frontend conditionally renders a minimal sidebar and redirects unauthorized routes.

**Tech Stack:** Python/Litestar + SQLAlchemy (backend), React/TypeScript (frontend), SQLite (DB)

**Spec:** `docs/superpowers/specs/2026-03-24-skater-role-design.md`

---

### Task 1: Data Model — `user_skaters` table + enum extension

**Files:**
- Modify: `backend/app/models/user.py:25-27`
- Create: `backend/app/models/user_skater.py`
- Modify: `backend/app/models/__init__.py`
- Modify: `backend/app/database.py:40-49` (add migration for new column type)
- Test: `backend/tests/test_users.py`

- [ ] **Step 1: Write test for skater user creation with linked skaters**

In `backend/tests/test_users.py`, add:

```python
@pytest.mark.asyncio
async def test_create_skater_user_with_linked_skaters(db_session):
    """Verify user_skaters association works at model level."""
    from app.models.user import User
    from app.models.skater import Skater
    from app.models.user_skater import UserSkater
    from sqlalchemy import select

    skater = Skater(first_name="Alice", last_name="Dupont", club="TestClub")
    db_session.add(skater)
    await db_session.flush()

    user = User(
        email="parent@test.com",
        display_name="Parent",
        role="skater",
        password_hash="fakehash",
    )
    db_session.add(user)
    await db_session.flush()

    link = UserSkater(user_id=user.id, skater_id=skater.id)
    db_session.add(link)
    await db_session.commit()

    result = await db_session.execute(
        select(UserSkater).where(UserSkater.user_id == user.id)
    )
    links = result.scalars().all()
    assert len(links) == 1
    assert links[0].skater_id == skater.id
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && PATH="/opt/homebrew/bin:$PATH" uv run pytest tests/test_users.py::test_create_skater_user_with_linked_skaters -v`
Expected: FAIL — `user_skater` module not found

- [ ] **Step 3: Create `user_skater.py` model**

Create `backend/app/models/user_skater.py`:

```python
from sqlalchemy import String, Integer, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class UserSkater(Base):
    __tablename__ = "user_skaters"
    __table_args__ = (
        UniqueConstraint("user_id", "skater_id", name="uq_user_skater"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    skater_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("skaters.id", ondelete="CASCADE"), nullable=False
    )
```

- [ ] **Step 4: Update user model enum**

In `backend/app/models/user.py:25-27`, change the SAEnum:

```python
    role: Mapped[str] = mapped_column(
        SAEnum("admin", "reader", "skater", name="user_role"), nullable=False, default="reader"
    )
```

- [ ] **Step 5: Register model in `__init__.py`**

In `backend/app/models/__init__.py`, add:

```python
from app.models.user_skater import UserSkater
```

And add `"UserSkater"` to `__all__`.

- [ ] **Step 6: Run test to verify it passes**

Run: `cd backend && PATH="/opt/homebrew/bin:$PATH" uv run pytest tests/test_users.py::test_create_skater_user_with_linked_skaters -v`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add backend/app/models/user_skater.py backend/app/models/user.py backend/app/models/__init__.py backend/tests/test_users.py
git commit -m "feat: add user_skaters table and skater role enum value"
```

---

### Task 2: Backend Guards — `reject_skater_role` + `require_skater_access`

**Files:**
- Modify: `backend/app/auth/guards.py`
- Test: `backend/tests/test_skater_access.py`

- [ ] **Step 1: Write tests for skater guards**

Create `backend/tests/test_skater_access.py`:

```python
import pytest

from app.models.user import User
from app.models.skater import Skater
from app.models.user_skater import UserSkater
from app.auth.passwords import hash_password


@pytest.fixture
async def skater_setup(db_session):
    """Create a skater user linked to one skater, plus an unlinked skater."""
    skater1 = Skater(first_name="Alice", last_name="Dupont", club="TestClub")
    skater2 = Skater(first_name="Bob", last_name="Martin", club="TestClub")
    db_session.add_all([skater1, skater2])
    await db_session.flush()

    password = "skaterpass1"
    user = User(
        email="skater@test.com",
        password_hash=hash_password(password),
        display_name="Skater Parent",
        role="skater",
    )
    db_session.add(user)
    await db_session.flush()

    link = UserSkater(user_id=user.id, skater_id=skater1.id)
    db_session.add(link)
    await db_session.commit()
    await db_session.refresh(skater1)
    await db_session.refresh(skater2)
    await db_session.refresh(user)

    from app.auth.tokens import create_access_token
    token = create_access_token(user_id=user.id, role=user.role)

    return {
        "user": user,
        "token": token,
        "linked_skater": skater1,
        "unlinked_skater": skater2,
    }


@pytest.mark.asyncio
async def test_skater_can_access_linked_skater(client, skater_setup):
    resp = await client.get(
        f"/api/skaters/{skater_setup['linked_skater'].id}",
        headers={"Authorization": f"Bearer {skater_setup['token']}"},
    )
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_skater_cannot_access_unlinked_skater(client, skater_setup):
    resp = await client.get(
        f"/api/skaters/{skater_setup['unlinked_skater'].id}",
        headers={"Authorization": f"Bearer {skater_setup['token']}"},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_skater_cannot_access_dashboard(client, skater_setup):
    resp = await client.get(
        "/api/dashboard/",
        headers={"Authorization": f"Bearer {skater_setup['token']}"},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_skater_cannot_list_all_skaters(client, skater_setup):
    resp = await client.get(
        "/api/skaters/",
        headers={"Authorization": f"Bearer {skater_setup['token']}"},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_skater_cannot_access_competitions(client, skater_setup):
    resp = await client.get(
        "/api/competitions/",
        headers={"Authorization": f"Bearer {skater_setup['token']}"},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_admin_can_still_access_all_skaters(client, admin_token):
    resp = await client.get(
        "/api/skaters/",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_reader_can_still_access_all_skaters(client, reader_token):
    resp = await client.get(
        "/api/skaters/",
        headers={"Authorization": f"Bearer {reader_token}"},
    )
    assert resp.status_code == 200
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && PATH="/opt/homebrew/bin:$PATH" uv run pytest tests/test_skater_access.py -v`
Expected: FAIL — guards not yet implemented

- [ ] **Step 3: Add `skater_user` and `skater_token` fixtures to conftest**

In `backend/tests/conftest.py`, add after the `reader_token` fixture:

```python
@pytest_asyncio.fixture
async def skater_user_with_skater(db_session: AsyncSession):
    """Create a skater user linked to a test skater."""
    from app.models.user import User
    from app.models.skater import Skater
    from app.models.user_skater import UserSkater

    skater = Skater(first_name="Alice", last_name="Dupont", club="TestClub")
    db_session.add(skater)
    await db_session.flush()

    password = "skaterpass1"
    user = User(
        email="skater@test.com",
        password_hash=hash_password(password),
        display_name="Skater Parent",
        role="skater",
    )
    db_session.add(user)
    await db_session.flush()

    link = UserSkater(user_id=user.id, skater_id=skater.id)
    db_session.add(link)
    await db_session.commit()
    await db_session.refresh(user)
    await db_session.refresh(skater)
    return user, password, skater


@pytest_asyncio.fixture
async def skater_token(skater_user_with_skater) -> str:
    """Return a valid access token for the skater user."""
    from app.auth.tokens import create_access_token

    user, _, _ = skater_user_with_skater
    return create_access_token(user_id=user.id, role=user.role)
```

- [ ] **Step 4: Implement guards in `guards.py`**

Add to `backend/app/auth/guards.py`:

```python
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


def reject_skater_role(request: Request) -> None:
    """Block access for skater role. Raises 403."""
    if request.scope.get("state", {}).get("user_role") == "skater":
        raise PermissionDeniedException("Skater role cannot access this resource")


async def require_skater_access(request: Request, skater_id: int, session: AsyncSession) -> None:
    """For skater role, verify the user has access to this specific skater."""
    state = request.scope.get("state", {})
    if state.get("user_role") != "skater":
        return  # admin and reader pass through

    from app.models.user_skater import UserSkater

    result = await session.execute(
        select(UserSkater).where(
            UserSkater.user_id == state["user_id"],
            UserSkater.skater_id == skater_id,
        )
    )
    if not result.scalar_one_or_none():
        raise PermissionDeniedException("You do not have access to this skater")
```

- [ ] **Step 5: Add `reject_skater_role` to restricted routes**

In `backend/app/routes/skaters.py`, modify `list_skaters` (line 20-27):

```python
from app.auth.guards import reject_skater_role, require_skater_access

@get("/")
async def list_skaters(request: Request, session: AsyncSession, club: Optional[str] = None) -> list[dict]:
    reject_skater_role(request)
    # ... rest unchanged
```

Add `Request` import and `require_skater_access` call to each per-skater endpoint. For `get_skater`:

```python
@get("/{skater_id:int}")
async def get_skater(skater_id: int, request: Request, session: AsyncSession) -> dict:
    await require_skater_access(request, skater_id, session)
    # ... rest unchanged
```

Do the same for `get_skater_elements`, `get_skater_scores`, `get_skater_category_results`, `get_skater_seasons`.

In `backend/app/routes/dashboard.py`, add to the `get_dashboard` function:

```python
from app.auth.guards import reject_skater_role

@get("/")
async def get_dashboard(request: Request, session: AsyncSession, season: Optional[str] = None) -> dict:
    reject_skater_role(request)
    # ... rest unchanged
```

Add `Request` import and `reject_skater_role(request)` as the first line of every GET handler in:
- `backend/app/routes/competitions.py` — `list_competitions`, `get_competition`, `get_competition_skaters`
- `backend/app/routes/stats.py` — all GET handlers
- `backend/app/routes/club_config.py` — `get_config` GET handler (club configuration data)
- `backend/app/routes/reports.py` — `club_report_pdf` only (skater PDF stays accessible)

In `backend/app/routes/reports.py`, add `require_skater_access` to `skater_report_pdf`:

```python
from app.auth.guards import reject_skater_role, require_skater_access

@get("/skater/{skater_id:int}/pdf")
async def skater_report_pdf(skater_id: int, season: str, request: Request, session: AsyncSession) -> Response:
    await require_skater_access(request, skater_id, session)
    # ... rest unchanged

@get("/club/pdf")
async def club_report_pdf(season: str, request: Request, session: AsyncSession) -> Response:
    reject_skater_role(request)
    # ... rest unchanged
```

- [ ] **Step 6: Refactor tests to use proper fixture pattern**

Update `backend/tests/test_skater_access.py` to use `skater_user_with_skater` and `skater_token` from conftest, plus separate fixtures for unlinked skater setup. Simplify tests to use `client`, `skater_token`, `admin_token`, `reader_token` fixtures.

- [ ] **Step 7: Run tests to verify they pass**

Run: `cd backend && PATH="/opt/homebrew/bin:$PATH" uv run pytest tests/test_skater_access.py -v`
Expected: ALL PASS

- [ ] **Step 8: Run full test suite**

Run: `cd backend && PATH="/opt/homebrew/bin:$PATH" uv run pytest -v`
Expected: ALL PASS (no regressions)

- [ ] **Step 9: Commit**

```bash
git add backend/app/auth/guards.py backend/app/routes/skaters.py backend/app/routes/dashboard.py backend/app/routes/competitions.py backend/app/routes/stats.py backend/app/routes/club_config.py backend/app/routes/reports.py backend/tests/test_skater_access.py backend/tests/conftest.py
git commit -m "feat: add skater role guards — reject_skater_role + require_skater_access"
```

---

### Task 3: Backend — `GET /api/me/skaters` endpoint

**Files:**
- Create: `backend/app/routes/me.py`
- Modify: `backend/app/main.py:24,68`
- Test: `backend/tests/test_skater_access.py`

- [ ] **Step 1: Write tests**

Add to `backend/tests/test_skater_access.py`:

```python
@pytest.mark.asyncio
async def test_me_skaters_returns_linked_skaters(client, skater_token, skater_user_with_skater):
    resp = await client.get(
        "/api/me/skaters",
        headers={"Authorization": f"Bearer {skater_token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["first_name"] == "Alice"
    assert data[0]["last_name"] == "Dupont"


@pytest.mark.asyncio
async def test_me_skaters_returns_empty_for_admin(client, admin_token):
    resp = await client.get(
        "/api/me/skaters",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    assert resp.json() == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && PATH="/opt/homebrew/bin:$PATH" uv run pytest tests/test_skater_access.py::test_me_skaters_returns_linked_skaters -v`
Expected: FAIL — 404

- [ ] **Step 3: Create `me.py` route**

Create `backend/app/routes/me.py`:

```python
from __future__ import annotations

from litestar import Router, get, Request
from litestar.di import Provide
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.models.user_skater import UserSkater
from app.models.skater import Skater


@get("/skaters")
async def my_skaters(request: Request, session: AsyncSession) -> list[dict]:
    """Return skaters linked to the current user. Empty list for non-skater roles."""
    state = request.scope.get("state", {})
    if state.get("user_role") != "skater":
        return []

    user_id = state["user_id"]
    stmt = (
        select(Skater)
        .join(UserSkater, UserSkater.skater_id == Skater.id)
        .where(UserSkater.user_id == user_id)
        .order_by(Skater.first_name)
    )
    result = await session.execute(stmt)
    skaters = result.scalars().all()
    return [
        {
            "id": s.id,
            "first_name": s.first_name,
            "last_name": s.last_name,
            "club": s.club,
        }
        for s in skaters
    ]


router = Router(
    path="/api/me",
    route_handlers=[my_skaters],
    dependencies={"session": Provide(get_session)},
)
```

- [ ] **Step 4: Register route in `main.py`**

In `backend/app/main.py`, add import and register:

```python
from app.routes.me import router as me_router
```

Add `me_router` to the `route_handlers` list.

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd backend && PATH="/opt/homebrew/bin:$PATH" uv run pytest tests/test_skater_access.py::test_me_skaters_returns_linked_skaters tests/test_skater_access.py::test_me_skaters_returns_empty_for_admin -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add backend/app/routes/me.py backend/app/main.py backend/tests/test_skater_access.py
git commit -m "feat: add GET /api/me/skaters endpoint"
```

---

### Task 4: Backend — User CRUD with `skater_ids`

**Files:**
- Modify: `backend/app/routes/users.py`
- Modify: `backend/app/routes/skaters.py:20-27` (search parameter)
- Test: `backend/tests/test_users.py`

- [ ] **Step 1: Write tests**

Add to `backend/tests/test_users.py`:

```python
@pytest.mark.asyncio
async def test_create_skater_user_with_skater_ids(client, admin_token, db_session):
    from app.models.skater import Skater

    skater = Skater(first_name="Luna", last_name="Star", club="TestClub")
    db_session.add(skater)
    await db_session.commit()
    await db_session.refresh(skater)

    resp = await client.post(
        "/api/users/",
        json={
            "email": "parent@test.com",
            "display_name": "Parent Luna",
            "role": "skater",
            "password": "password123",
            "skater_ids": [skater.id],
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 201
    assert resp.json()["role"] == "skater"
    assert resp.json()["skater_ids"] == [skater.id]


@pytest.mark.asyncio
async def test_list_users_includes_skater_ids(client, admin_token, db_session):
    from app.models.skater import Skater
    from app.models.user import User
    from app.models.user_skater import UserSkater
    from app.auth.passwords import hash_password

    skater = Skater(first_name="Max", last_name="Power", club="TestClub")
    db_session.add(skater)
    await db_session.flush()
    user = User(email="skateparent@test.com", display_name="SP", role="skater", password_hash=hash_password("pass12345"))
    db_session.add(user)
    await db_session.flush()
    db_session.add(UserSkater(user_id=user.id, skater_id=skater.id))
    await db_session.commit()

    resp = await client.get(
        "/api/users/",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    skater_user = next(u for u in resp.json() if u["email"] == "skateparent@test.com")
    assert skater_user["skater_ids"] == [skater.id]


@pytest.mark.asyncio
async def test_update_role_from_skater_clears_links(client, admin_token, db_session):
    from app.models.skater import Skater
    from app.models.user import User
    from app.models.user_skater import UserSkater
    from app.auth.passwords import hash_password
    from sqlalchemy import select

    skater = Skater(first_name="Zoe", last_name="Clear", club="TestClub")
    db_session.add(skater)
    await db_session.flush()
    user = User(email="toclear@test.com", display_name="TC", role="skater", password_hash=hash_password("pass12345"))
    db_session.add(user)
    await db_session.flush()
    db_session.add(UserSkater(user_id=user.id, skater_id=skater.id))
    await db_session.commit()

    resp = await client.patch(
        f"/api/users/{user.id}",
        json={"role": "reader"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["role"] == "reader"

    result = await db_session.execute(
        select(UserSkater).where(UserSkater.user_id == user.id)
    )
    assert result.scalars().all() == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && PATH="/opt/homebrew/bin:$PATH" uv run pytest tests/test_users.py::test_create_skater_user_with_skater_ids tests/test_users.py::test_list_users_includes_skater_ids tests/test_users.py::test_update_role_from_skater_clears_links -v`
Expected: FAIL

- [ ] **Step 3: Implement `skater_ids` in user routes**

Modify `backend/app/routes/users.py`:

In `list_users`: add `skater_ids` to each user response by loading `UserSkater` records:

```python
from app.models.user_skater import UserSkater

@get("/")
async def list_users(request: Request, session: AsyncSession) -> list[dict]:
    require_admin(request)
    from app.models.user import User

    result = await session.execute(select(User).order_by(User.created_at))
    users = result.scalars().all()

    # Load all user_skater links in one query
    us_result = await session.execute(select(UserSkater))
    all_links = us_result.scalars().all()
    links_by_user: dict[str, list[int]] = {}
    for link in all_links:
        links_by_user.setdefault(link.user_id, []).append(link.skater_id)

    return [
        {
            "id": u.id,
            "email": u.email,
            "display_name": u.display_name,
            "role": u.role,
            "is_active": u.is_active,
            "google_oauth_enabled": u.google_oauth_enabled,
            "skater_ids": links_by_user.get(u.id, []),
        }
        for u in users
    ]
```

In `create_user`: after commit, handle `skater_ids`:

```python
async def _sync_skater_links(session: AsyncSession, user_id: str, skater_ids: list[int]) -> None:
    """Replace all user_skater links for a user."""
    from app.models.user_skater import UserSkater

    # Delete existing links
    existing = await session.execute(
        select(UserSkater).where(UserSkater.user_id == user_id)
    )
    for link in existing.scalars().all():
        await session.delete(link)

    # Add new links
    for sid in skater_ids:
        session.add(UserSkater(user_id=user_id, skater_id=sid))
```

Call it in `create_user` after `session.refresh(user)`:

```python
    skater_ids = data.get("skater_ids", [])
    if role == "skater" and skater_ids:
        await _sync_skater_links(session, user.id, skater_ids)
        await session.commit()
```

Add `skater_ids` to the create response. Similarly for `update_user`: if role changes away from `skater`, clear links. If role is `skater` and `skater_ids` provided, sync them.

In `update_user`:

```python
    old_role = user.role
    # ... existing role/field updates ...

    # Handle skater_ids
    if "skater_ids" in data and user.role == "skater":
        await _sync_skater_links(session, user.id, data["skater_ids"])
    elif old_role == "skater" and user.role != "skater":
        await _sync_skater_links(session, user.id, [])

    await session.commit()
    await session.refresh(user)
```

Add `skater_ids` to update response.

- [ ] **Step 4: Add search filter to `list_skaters`**

In `backend/app/routes/skaters.py`, modify `list_skaters` to accept a `search` query parameter:

```python
@get("/")
async def list_skaters(request: Request, session: AsyncSession, club: Optional[str] = None, search: Optional[str] = None) -> list[dict]:
    reject_skater_role(request)
    stmt = select(Skater)
    if club:
        stmt = stmt.where(func.lower(Skater.club) == club.lower())
    if search:
        pattern = f"%{search}%"
        stmt = stmt.where(
            (Skater.first_name.ilike(pattern)) | (Skater.last_name.ilike(pattern))
        )
    result = await session.execute(stmt)
    skaters = sorted(result.scalars(), key=lambda s: (s.last_name.upper(), s.first_name.upper()))
    return [_skater_to_dict(s) for s in skaters]
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd backend && PATH="/opt/homebrew/bin:$PATH" uv run pytest tests/test_users.py -v`
Expected: ALL PASS

- [ ] **Step 6: Run full test suite**

Run: `cd backend && PATH="/opt/homebrew/bin:$PATH" uv run pytest -v`
Expected: ALL PASS

- [ ] **Step 7: Commit**

```bash
git add backend/app/routes/users.py backend/app/routes/skaters.py backend/tests/test_users.py
git commit -m "feat: user CRUD handles skater_ids, skater search filter"
```

---

### Task 5: Frontend — Types + API client

**Files:**
- Modify: `frontend/src/api/client.ts:306-327`

- [ ] **Step 1: Update `AuthUser` type**

In `frontend/src/api/client.ts:310`, change:

```typescript
role: "admin" | "reader" | "skater";
```

- [ ] **Step 2: Update `UserRecord` type**

In `frontend/src/api/client.ts:324`, change:

```typescript
role: "admin" | "reader" | "skater";
```

Add `skater_ids` field:

```typescript
export interface UserRecord {
  id: string;
  email: string;
  display_name: string;
  role: "admin" | "reader" | "skater";
  is_active: boolean;
  google_oauth_enabled: boolean;
  skater_ids: number[];
}
```

- [ ] **Step 3: Add `MySkater` type and `me.skaters` API function**

Add after `UserRecord`:

```typescript
export interface MySkater {
  id: number;
  first_name: string;
  last_name: string;
  club: string;
}
```

In the `api` object, add a `me` namespace:

```typescript
me: {
  skaters: (): Promise<MySkater[]> => get("/api/me/skaters"),
},
```

- [ ] **Step 4: Add skater search function**

Ensure the existing `skaters.list` function (or equivalent) supports a `search` parameter. If it doesn't exist, add:

```typescript
skaters: {
  list: (params?: { club?: string; search?: string }): Promise<SkaterRecord[]> =>
    get("/api/skaters", params),
  // ... existing methods
},
```

- [ ] **Step 5: Commit**

```bash
git add frontend/src/api/client.ts
git commit -m "feat: add skater role to frontend types + me/skaters API"
```

---

### Task 6: Frontend — Skater routing + sidebar

**Files:**
- Modify: `frontend/src/App.tsx`
- Create: `frontend/src/pages/MySkatersPage.tsx`

- [ ] **Step 1: Create `MySkatersPage.tsx`**

Create `frontend/src/pages/MySkatersPage.tsx`:

```tsx
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { api } from "../api/client";

export default function MySkatersPage() {
  const { data: skaters, isLoading } = useQuery({
    queryKey: ["me", "skaters"],
    queryFn: api.me.skaters,
  });

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-20">
        <span className="material-symbols-outlined animate-spin text-primary text-3xl">
          progress_activity
        </span>
      </div>
    );
  }

  if (!skaters || skaters.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-20 gap-4">
        <span className="material-symbols-outlined text-on-surface-variant text-5xl">
          person_off
        </span>
        <p className="text-on-surface-variant text-sm">
          Aucun patineur associé à votre compte. Contactez l'administrateur.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {skaters.map((s) => (
          <Link
            key={s.id}
            to={`/patineurs/${s.id}/analyse`}
            className="bg-surface-container rounded-xl p-5 hover:bg-surface-container-high transition-colors group"
          >
            <div className="flex items-center gap-3">
              <span className="material-symbols-outlined text-primary text-2xl">
                ice_skating
              </span>
              <div>
                <p className="font-headline font-bold text-on-surface group-hover:text-primary transition-colors">
                  {s.first_name} {s.last_name}
                </p>
                {s.club && (
                  <p className="text-xs text-on-surface-variant mt-0.5">{s.club}</p>
                )}
              </div>
            </div>
          </Link>
        ))}
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Update `App.tsx` — Skater sidebar + routing**

In `frontend/src/App.tsx`, add import:

```typescript
import MySkatersPage from "./pages/MySkatersPage";
```

Replace the `navLinks` constant and the sidebar `<nav>` section with role-conditional rendering. In `AuthenticatedLayout`:

After the existing `navLinks.map(...)` block (lines 100-116), wrap it with a condition:

```tsx
{user?.role !== "skater" && (
  <nav className="flex-1 py-2">
    {navLinks.map(({ to, label, icon, end }) => (
      // ... existing NavLink code
    ))}
  </nav>
)}
{user?.role === "skater" && (
  <SkaterNav closeSidebar={closeSidebar} />
)}
```

Create a `SkaterNav` component inside `App.tsx` (before `AuthenticatedLayout`):

```tsx
function SkaterNav({ closeSidebar }: { closeSidebar: () => void }) {
  const { data: skaters } = useQuery({
    queryKey: ["me", "skaters"],
    queryFn: api.me.skaters,
  });

  const label = skaters && skaters.length === 1 ? "MON PATINEUR" : "MES PATINEURS";
  const to = skaters && skaters.length === 1
    ? `/patineurs/${skaters[0].id}/analyse`
    : "/mes-patineurs";

  return (
    <nav className="flex-1 py-2">
      <NavLink
        to={to}
        onClick={closeSidebar}
        className={({ isActive }) =>
          isActive
            ? "bg-white text-primary shadow-sm rounded-xl mx-2 my-0.5 px-4 py-3 font-bold flex items-center gap-3"
            : "text-on-surface-variant hover:bg-surface-container rounded-xl mx-2 my-0.5 px-4 py-3 flex items-center gap-3 transition-colors"
        }
      >
        <span className="material-symbols-outlined text-xl">ice_skating</span>
        <span className="text-[11px] font-bold uppercase tracking-wider">{label}</span>
      </NavLink>
    </nav>
  );
}
```

In the `<Routes>` section, add the new route:

```tsx
<Route path="/mes-patineurs" element={<MySkatersPage />} />
```

- [ ] **Step 3: Add skater role redirect logic**

In `App.tsx`, add a `SkaterRedirect` component that redirects unauthorized routes:

```tsx
function SkaterRedirect() {
  const { data: skaters, isLoading } = useQuery({
    queryKey: ["me", "skaters"],
    queryFn: api.me.skaters,
  });

  if (isLoading) return null;

  const target = skaters && skaters.length === 1
    ? `/patineurs/${skaters[0].id}/analyse`
    : "/mes-patineurs";

  return <Navigate to={target} replace />;
}
```

Wrap the main routes so that for `skater` role, only allowed routes are rendered:

```tsx
{user?.role === "skater" ? (
  <Routes>
    <Route path="/patineurs/:id/analyse" element={<SkaterAnalyticsPage />} />
    <Route path="/mes-patineurs" element={<MySkatersPage />} />
    <Route path="/profil" element={<ProfilePage />} />
    <Route path="*" element={<SkaterRedirect />} />
  </Routes>
) : (
  <Routes>
    {/* ... existing routes */}
  </Routes>
)}
```

- [ ] **Step 4: Update `getPageTitle` for new routes**

Add to `getPageTitle`:

```typescript
if (pathname === "/mes-patineurs") return "Mes patineurs";
```

- [ ] **Step 5: Verify the app compiles**

Run: `cd frontend && PATH="/opt/homebrew/bin:$PATH" npx tsc --noEmit`
Expected: No errors

- [ ] **Step 6: Commit**

```bash
git add frontend/src/App.tsx frontend/src/pages/MySkatersPage.tsx
git commit -m "feat: skater role routing, sidebar, and MySkatersPage"
```

---

### Task 7: Frontend — Conditional competition links in SkaterAnalyticsPage

**Files:**
- Modify: `frontend/src/pages/SkaterAnalyticsPage.tsx:779-785,860-865`

- [ ] **Step 1: Make competition names conditional on role**

In `frontend/src/pages/SkaterAnalyticsPage.tsx`, import `useAuth`:

```typescript
import { useAuth } from "../auth/AuthContext";
```

At the top of the component, get the user:

```typescript
const { user } = useAuth();
```

At line ~779 (collapsed row competition link), replace the `<Link>` with:

```tsx
{user?.role === "skater" ? (
  <span className="font-medium text-on-surface">
    {row.competitionName ?? `#${row.competitionId}`}
  </span>
) : (
  <Link
    to={`/competitions/${row.competitionId}`}
    className="text-primary hover:underline font-medium"
    onClick={(e) => e.stopPropagation()}
  >
    {row.competitionName ?? `#${row.competitionId}`}
  </Link>
)}
```

At line ~860 (table cell), do the same replacement:

```tsx
<td className="px-3 py-2 text-sm text-on-surface">
  {user?.role === "skater" ? (
    <span className="font-medium">
      {s.competition_name ?? `#${s.competition_id}`}
    </span>
  ) : (
    <Link
      to={`/competitions/${s.competition_id}`}
      className="text-primary hover:underline font-medium"
    >
      {s.competition_name ?? `#${s.competition_id}`}
    </Link>
  )}
</td>
```

- [ ] **Step 2: Verify compilation**

Run: `cd frontend && PATH="/opt/homebrew/bin:$PATH" npx tsc --noEmit`
Expected: No errors

- [ ] **Step 3: Commit**

```bash
git add frontend/src/pages/SkaterAnalyticsPage.tsx
git commit -m "feat: disable competition links for skater role"
```

---

### Task 8: Frontend — Admin skater assignment in SettingsPage

**Files:**
- Modify: `frontend/src/pages/SettingsPage.tsx`

- [ ] **Step 1: Add skater autocomplete to user creation form**

In `frontend/src/pages/SettingsPage.tsx`:

Add to the `newUser` state (line 59-65):

```typescript
const [newUser, setNewUser] = useState({
  email: "",
  display_name: "",
  role: "reader",
  password: "",
  must_change_password: false,
  skater_ids: [] as number[],
});
```

Add a `<option value="skater">Patineur</option>` after the admin option (line 331).

After the role select (line 332), add conditionally:

```tsx
{newUser.role === "skater" && (
  <SkaterPicker
    selectedIds={newUser.skater_ids}
    onChange={(ids) => setNewUser((u) => ({ ...u, skater_ids: ids }))}
  />
)}
```

Create a `SkaterPicker` component (can be defined above `SettingsPage` or extracted to its own file). It should:
- Have a text input for searching
- Call `GET /api/skaters?search=...` with debounce
- Show results as clickable items
- Display selected skaters as removable chips

```tsx
function SkaterPicker({
  selectedIds,
  onChange,
}: {
  selectedIds: number[];
  onChange: (ids: number[]) => void;
}) {
  const [search, setSearch] = useState("");
  const [debouncedSearch, setDebouncedSearch] = useState("");

  useEffect(() => {
    const timer = setTimeout(() => setDebouncedSearch(search), 300);
    return () => clearTimeout(timer);
  }, [search]);

  const { data: results } = useQuery({
    queryKey: ["skaters", "search", debouncedSearch],
    queryFn: () => api.skaters.list({ search: debouncedSearch }),
    enabled: debouncedSearch.length >= 2,
  });

  const { data: allSkaters } = useQuery({
    queryKey: ["skaters", "all"],
    queryFn: () => api.skaters.list(),
  });

  const selectedSkaters = allSkaters?.filter((s) => selectedIds.includes(s.id)) ?? [];

  return (
    <div className="space-y-2">
      <label className="text-xs font-bold text-on-surface-variant uppercase tracking-wider">
        Patineurs associés
      </label>
      {/* Selected chips */}
      {selectedSkaters.length > 0 && (
        <div className="flex flex-wrap gap-1">
          {selectedSkaters.map((s) => (
            <span
              key={s.id}
              className="inline-flex items-center gap-1 bg-primary/10 text-primary text-xs px-2 py-1 rounded-full"
            >
              {s.first_name} {s.last_name}
              <button
                type="button"
                onClick={() => onChange(selectedIds.filter((id) => id !== s.id))}
                className="hover:text-error"
              >
                <span className="material-symbols-outlined text-sm">close</span>
              </button>
            </span>
          ))}
        </div>
      )}
      {/* Search input */}
      <input
        placeholder="Rechercher un patineur..."
        value={search}
        onChange={(e) => setSearch(e.target.value)}
        className={inputCls}
      />
      {/* Results dropdown */}
      {results && results.length > 0 && search.length >= 2 && (
        <div className="bg-surface-container rounded-lg shadow-md max-h-40 overflow-y-auto">
          {results
            .filter((s) => !selectedIds.includes(s.id))
            .map((s) => (
              <button
                key={s.id}
                type="button"
                onClick={() => {
                  onChange([...selectedIds, s.id]);
                  setSearch("");
                }}
                className="w-full text-left px-3 py-2 text-sm hover:bg-surface-container-high transition-colors"
              >
                {s.first_name} {s.last_name}
                {s.club && (
                  <span className="text-on-surface-variant ml-2 text-xs">({s.club})</span>
                )}
              </button>
            ))}
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Reset `skater_ids` when clearing the form**

In the `createUser` mutation's `onSuccess` (line 72):

```typescript
setNewUser({ email: "", display_name: "", role: "reader", password: "", must_change_password: false, skater_ids: [] });
```

- [ ] **Step 3: Pass `skater_ids` to the API call**

Ensure the `api.users.create` function passes `skater_ids` through. Check `frontend/src/api/client.ts` — the create function should already pass the full object body. If it does `POST /api/users` with the newUser object, `skater_ids` will be included automatically.

- [ ] **Step 4: Add role badge for skater in user list**

Find the role badge rendering in SettingsPage (search for `"admin"` and `"Administrateur"` or `"Lecteur"` in the user list). Add a case for `"skater"`:

```tsx
{u.role === "skater" && (
  <span className="text-[10px] px-2 py-0.5 rounded-full bg-blue-100 text-blue-700 font-bold">
    Patineur
  </span>
)}
```

- [ ] **Step 5: Verify compilation**

Run: `cd frontend && PATH="/opt/homebrew/bin:$PATH" npx tsc --noEmit`
Expected: No errors

- [ ] **Step 6: Commit**

```bash
git add frontend/src/pages/SettingsPage.tsx
git commit -m "feat: admin UI for skater role with skater picker"
```

---

### Task 9: Integration testing + cleanup

**Files:**
- All modified files

- [ ] **Step 1: Run full backend test suite**

Run: `cd backend && PATH="/opt/homebrew/bin:$PATH" uv run pytest -v`
Expected: ALL PASS

- [ ] **Step 2: Run frontend type check**

Run: `cd frontend && PATH="/opt/homebrew/bin:$PATH" npx tsc --noEmit`
Expected: No errors

- [ ] **Step 3: Manual smoke test checklist**

Start both servers and verify:

1. Login as admin → all pages accessible, Settings shows skater option in role dropdown
2. Create a skater user with linked patineur → verify user appears in list with "Patineur" badge
3. Login as skater user → redirected to skater page, sidebar shows only "Mon patineur"
4. Verify competition names are text-only (not links) on skater analytics page
5. Try navigating to `/competitions` → redirected back
6. Login as reader → verify everything still works as before

- [ ] **Step 4: Final commit if any fixes needed**

```bash
git add -A && git commit -m "fix: integration fixes for skater role"
```
