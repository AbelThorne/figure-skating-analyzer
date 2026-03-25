# Training Tracking Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add coach-driven training tracking with weekly reviews, incident reporting, and longitudinal progress visualization.

**Architecture:** Two new SQLAlchemy models (WeeklyReview, Incident) with a new `coach` role. Backend routes under `/api/training/`. Frontend adds a training tracking section for coaches and an "Entraînement" tab for skaters. Email notifications are excluded from this plan (separable phase).

**Tech Stack:** Python/Litestar/SQLAlchemy (backend), React/TypeScript/Recharts (frontend), pytest-asyncio (tests)

---

### Task 1: Add `coach` role to User model and auth guards

**Files:**
- Modify: `backend/app/models/user.py:25-27` (add "coach" to enum)
- Modify: `backend/app/auth/guards.py` (add `require_coach_or_admin` guard)
- Modify: `backend/app/database.py:41-56` (add migration for existing DBs)
- Test: `backend/tests/test_training_auth.py`

- [ ] **Step 1: Write failing tests for coach role auth**

Create `backend/tests/test_training_auth.py`:

```python
import pytest
from app.auth.tokens import create_access_token


@pytest.fixture
async def coach_user(db_session):
    from app.models.user import User
    from app.auth.passwords import hash_password

    user = User(
        email="coach@test.com",
        password_hash=hash_password("coachpass1"),
        display_name="Test Coach",
        role="coach",
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user, "coachpass1"


@pytest.fixture
async def coach_token(coach_user) -> str:
    user, _ = coach_user
    return create_access_token(user_id=user.id, role=user.role)


async def test_coach_role_created(coach_user):
    user, _ = coach_user
    assert user.role == "coach"


async def test_coach_can_login(client, coach_user):
    _, password = coach_user
    resp = await client.post("/api/auth/login", json={
        "email": "coach@test.com",
        "password": password,
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["user"]["role"] == "coach"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && uv run pytest tests/test_training_auth.py -v`
Expected: FAIL — "coach" is not a valid enum value

- [ ] **Step 3: Add "coach" to User role enum**

In `backend/app/models/user.py`, change line 26:
```python
    role: Mapped[str] = mapped_column(
        SAEnum("admin", "reader", "skater", "coach", name="user_role"), nullable=False, default="reader"
    )
```

- [ ] **Step 4: Add `require_coach_or_admin` guard**

In `backend/app/auth/guards.py`, add after the `reject_skater_role` function:

```python
def require_coach_or_admin(request: Request) -> None:
    """Allow only coach and admin roles. Raises 403 otherwise."""
    role = request.scope.get("state", {}).get("user_role")
    if role not in ("coach", "admin"):
        raise PermissionDeniedException("Coach or admin role required")
```

- [ ] **Step 5: Add `email_notifications` column to User model (for future email phase)**

In `backend/app/models/user.py`, add after the `must_change_password` field:
```python
    email_notifications: Mapped[bool] = mapped_column(Boolean, default=True)
```

This column is defined in the spec's data model. The email notification feature itself is deferred, but the column should exist so the follow-up plan doesn't need to alter the model.

- [ ] **Step 6: Update auth type in frontend API client**

In `frontend/src/api/client.ts`, update the `AuthUser` interface role type (line 311):
```typescript
  role: "admin" | "reader" | "skater" | "coach";
```

And the `UserRecord` interface role type (line 324):
```typescript
  role: "admin" | "reader" | "skater" | "coach";
```

- [ ] **Step 7: Run tests to verify they pass**

Run: `cd backend && uv run pytest tests/test_training_auth.py -v`
Expected: PASS

- [ ] **Step 8: Commit**

```bash
git add backend/app/models/user.py backend/app/auth/guards.py backend/tests/test_training_auth.py frontend/src/api/client.ts
git commit -m "feat: add coach role, email_notifications column, and require_coach_or_admin guard"
```

---

### Task 2: Create WeeklyReview and Incident models

**Files:**
- Create: `backend/app/models/weekly_review.py`
- Create: `backend/app/models/incident.py`
- Modify: `backend/app/models/__init__.py` (register new models)
- Test: `backend/tests/test_training_models.py`

- [ ] **Step 1: Write failing test for WeeklyReview model**

Create `backend/tests/test_training_models.py`:

```python
import pytest
from datetime import date


async def test_create_weekly_review(db_session):
    from app.models.skater import Skater
    from app.models.user import User
    from app.models.weekly_review import WeeklyReview
    from app.auth.passwords import hash_password

    skater = Skater(first_name="Alice", last_name="Dupont", club="TestClub")
    db_session.add(skater)
    coach = User(
        email="coach@test.com",
        password_hash=hash_password("pass"),
        display_name="Coach",
        role="coach",
    )
    db_session.add(coach)
    await db_session.flush()

    review = WeeklyReview(
        skater_id=skater.id,
        coach_id=coach.id,
        week_start=date(2026, 3, 23),  # a Monday
        attendance="3/4",
        engagement=4,
        progression=3,
        attitude=5,
        strengths="Bon travail sur les sauts",
        improvements="Travailler les pirouettes",
        visible_to_skater=True,
    )
    db_session.add(review)
    await db_session.commit()
    await db_session.refresh(review)

    assert review.id is not None
    assert review.week_start == date(2026, 3, 23)
    assert review.engagement == 4
    assert review.visible_to_skater is True


async def test_weekly_review_unique_constraint(db_session):
    from app.models.skater import Skater
    from app.models.user import User
    from app.models.weekly_review import WeeklyReview
    from app.auth.passwords import hash_password
    from sqlalchemy.exc import IntegrityError

    skater = Skater(first_name="Bob", last_name="Martin", club="TestClub")
    db_session.add(skater)
    coach = User(
        email="coach2@test.com",
        password_hash=hash_password("pass"),
        display_name="Coach2",
        role="coach",
    )
    db_session.add(coach)
    await db_session.flush()

    review1 = WeeklyReview(
        skater_id=skater.id, coach_id=coach.id, week_start=date(2026, 3, 23),
        attendance="4/4", engagement=3, progression=3, attitude=3,
        strengths="", improvements="", visible_to_skater=True,
    )
    db_session.add(review1)
    await db_session.commit()

    review2 = WeeklyReview(
        skater_id=skater.id, coach_id=coach.id, week_start=date(2026, 3, 23),
        attendance="3/4", engagement=4, progression=4, attitude=4,
        strengths="", improvements="", visible_to_skater=True,
    )
    db_session.add(review2)
    with pytest.raises(IntegrityError):
        await db_session.commit()


async def test_create_incident(db_session):
    from app.models.skater import Skater
    from app.models.user import User
    from app.models.incident import Incident
    from app.auth.passwords import hash_password

    skater = Skater(first_name="Claire", last_name="Duval", club="TestClub")
    db_session.add(skater)
    coach = User(
        email="coach3@test.com",
        password_hash=hash_password("pass"),
        display_name="Coach3",
        role="coach",
    )
    db_session.add(coach)
    await db_session.flush()

    incident = Incident(
        skater_id=skater.id,
        coach_id=coach.id,
        date=date(2026, 3, 24),
        incident_type="injury",
        description="Chute sur un axel, douleur au genou",
        visible_to_skater=False,
    )
    db_session.add(incident)
    await db_session.commit()
    await db_session.refresh(incident)

    assert incident.id is not None
    assert incident.incident_type == "injury"
    assert incident.visible_to_skater is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && uv run pytest tests/test_training_models.py -v`
Expected: FAIL — modules not found

- [ ] **Step 3: Create WeeklyReview model**

Create `backend/app/models/weekly_review.py`:

```python
from datetime import date, datetime, timezone

from sqlalchemy import Date, DateTime, Integer, String, Text, Boolean, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class WeeklyReview(Base):
    __tablename__ = "weekly_reviews"
    __table_args__ = (
        UniqueConstraint("skater_id", "week_start", name="uq_review_skater_week"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    skater_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("skaters.id", ondelete="CASCADE"), nullable=False
    )
    coach_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    week_start: Mapped[date] = mapped_column(Date, nullable=False)
    attendance: Mapped[str] = mapped_column(String(20), nullable=False, default="")
    engagement: Mapped[int] = mapped_column(Integer, nullable=False)
    progression: Mapped[int] = mapped_column(Integer, nullable=False)
    attitude: Mapped[int] = mapped_column(Integer, nullable=False)
    strengths: Mapped[str] = mapped_column(Text, nullable=False, default="")
    improvements: Mapped[str] = mapped_column(Text, nullable=False, default="")
    visible_to_skater: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, onupdate=_utcnow)
```

- [ ] **Step 4: Create Incident model**

Create `backend/app/models/incident.py`:

```python
from datetime import date, datetime, timezone

from sqlalchemy import Date, DateTime, Integer, String, Text, Boolean, ForeignKey, Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Incident(Base):
    __tablename__ = "incidents"

    id: Mapped[int] = mapped_column(primary_key=True)
    skater_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("skaters.id", ondelete="CASCADE"), nullable=False
    )
    coach_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    date: Mapped[date] = mapped_column(Date, nullable=False)
    incident_type: Mapped[str] = mapped_column(
        SAEnum("injury", "behavior", "other", name="incident_type_enum"), nullable=False
    )
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    visible_to_skater: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, onupdate=_utcnow)
```

- [ ] **Step 5: Register models in `__init__.py`**

In `backend/app/models/__init__.py`, add:

```python
from app.models.weekly_review import WeeklyReview
from app.models.incident import Incident
```

And add `"WeeklyReview"` and `"Incident"` to the `__all__` list.

- [ ] **Step 6: Run tests to verify they pass**

Run: `cd backend && uv run pytest tests/test_training_models.py -v`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add backend/app/models/weekly_review.py backend/app/models/incident.py backend/app/models/__init__.py backend/tests/test_training_models.py
git commit -m "feat: add WeeklyReview and Incident models"
```

---

### Task 3: Backend routes for weekly reviews

**Files:**
- Create: `backend/app/routes/training.py`
- Modify: `backend/app/main.py` (register router)
- Test: `backend/tests/test_training_reviews.py`

- [ ] **Step 1: Write failing tests for review CRUD**

Create `backend/tests/test_training_reviews.py`:

```python
import pytest
from datetime import date

from app.auth.tokens import create_access_token
from app.auth.passwords import hash_password
from app.models.user import User
from app.models.skater import Skater
from app.models.user_skater import UserSkater


@pytest.fixture
async def coach_and_skater(db_session):
    """Create a coach, a skater, and return (coach, coach_token, skater)."""
    coach = User(
        email="coach@test.com",
        password_hash=hash_password("coachpass1"),
        display_name="Test Coach",
        role="coach",
    )
    db_session.add(coach)
    skater = Skater(first_name="Alice", last_name="Dupont", club="TestClub")
    db_session.add(skater)
    await db_session.commit()
    await db_session.refresh(coach)
    await db_session.refresh(skater)
    token = create_access_token(user_id=coach.id, role=coach.role)
    return coach, token, skater


@pytest.fixture
async def skater_parent(db_session, coach_and_skater):
    """Create a skater-role user linked to the skater."""
    _, _, skater = coach_and_skater
    parent = User(
        email="parent@test.com",
        password_hash=hash_password("parentpass1"),
        display_name="Parent",
        role="skater",
    )
    db_session.add(parent)
    await db_session.flush()
    link = UserSkater(user_id=parent.id, skater_id=skater.id)
    db_session.add(link)
    await db_session.commit()
    await db_session.refresh(parent)
    token = create_access_token(user_id=parent.id, role=parent.role)
    return parent, token


async def test_create_review(client, coach_and_skater):
    coach, token, skater = coach_and_skater
    resp = await client.post(
        "/api/training/reviews",
        json={
            "skater_id": skater.id,
            "week_start": "2026-03-23",
            "attendance": "3/4",
            "engagement": 4,
            "progression": 3,
            "attitude": 5,
            "strengths": "Bon travail",
            "improvements": "Pirouettes",
            "visible_to_skater": True,
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["skater_id"] == skater.id
    assert data["engagement"] == 4
    assert data["coach_id"] == coach.id


async def test_create_review_auto_monday(client, coach_and_skater):
    """week_start should be snapped to the Monday of the given date's week."""
    _, token, skater = coach_and_skater
    resp = await client.post(
        "/api/training/reviews",
        json={
            "skater_id": skater.id,
            "week_start": "2026-03-25",  # Wednesday
            "attendance": "4/4",
            "engagement": 3,
            "progression": 3,
            "attitude": 3,
            "strengths": "",
            "improvements": "",
            "visible_to_skater": True,
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201
    assert resp.json()["week_start"] == "2026-03-23"  # Snapped to Monday


async def test_list_reviews(client, coach_and_skater):
    _, token, skater = coach_and_skater
    # Create a review first
    await client.post(
        "/api/training/reviews",
        json={
            "skater_id": skater.id,
            "week_start": "2026-03-23",
            "attendance": "3/4",
            "engagement": 4,
            "progression": 3,
            "attitude": 5,
            "strengths": "Bon",
            "improvements": "Mieux",
            "visible_to_skater": True,
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    resp = await client.get(
        f"/api/training/reviews?skater_id={skater.id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert len(resp.json()) == 1


async def test_update_review(client, coach_and_skater):
    coach, token, skater = coach_and_skater
    create_resp = await client.post(
        "/api/training/reviews",
        json={
            "skater_id": skater.id,
            "week_start": "2026-03-23",
            "attendance": "3/4",
            "engagement": 4,
            "progression": 3,
            "attitude": 5,
            "strengths": "Bon",
            "improvements": "Mieux",
            "visible_to_skater": True,
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    review_id = create_resp.json()["id"]
    resp = await client.put(
        f"/api/training/reviews/{review_id}",
        json={"engagement": 5, "strengths": "Excellent travail"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["engagement"] == 5
    assert resp.json()["strengths"] == "Excellent travail"


async def test_delete_review(client, coach_and_skater):
    _, token, skater = coach_and_skater
    create_resp = await client.post(
        "/api/training/reviews",
        json={
            "skater_id": skater.id,
            "week_start": "2026-03-23",
            "attendance": "3/4",
            "engagement": 4,
            "progression": 3,
            "attitude": 5,
            "strengths": "Bon",
            "improvements": "Mieux",
            "visible_to_skater": True,
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    review_id = create_resp.json()["id"]
    resp = await client.delete(
        f"/api/training/reviews/{review_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 204


async def test_reader_cannot_create_review(client, coach_and_skater, reader_token):
    _, _, skater = coach_and_skater
    resp = await client.post(
        "/api/training/reviews",
        json={
            "skater_id": skater.id,
            "week_start": "2026-03-23",
            "attendance": "3/4",
            "engagement": 4,
            "progression": 3,
            "attitude": 5,
            "strengths": "",
            "improvements": "",
            "visible_to_skater": True,
        },
        headers={"Authorization": f"Bearer {reader_token}"},
    )
    assert resp.status_code == 403


async def test_skater_sees_visible_reviews(client, coach_and_skater, skater_parent):
    _, coach_token, skater = coach_and_skater
    parent, parent_token = skater_parent

    # Create visible review
    await client.post(
        "/api/training/reviews",
        json={
            "skater_id": skater.id,
            "week_start": "2026-03-23",
            "attendance": "3/4",
            "engagement": 4,
            "progression": 3,
            "attitude": 5,
            "strengths": "Bon",
            "improvements": "Mieux",
            "visible_to_skater": True,
        },
        headers={"Authorization": f"Bearer {coach_token}"},
    )
    # Create hidden review
    await client.post(
        "/api/training/reviews",
        json={
            "skater_id": skater.id,
            "week_start": "2026-03-16",
            "attendance": "2/4",
            "engagement": 2,
            "progression": 2,
            "attitude": 2,
            "strengths": "",
            "improvements": "",
            "visible_to_skater": False,
        },
        headers={"Authorization": f"Bearer {coach_token}"},
    )

    resp = await client.get(
        f"/api/training/reviews?skater_id={skater.id}",
        headers={"Authorization": f"Bearer {parent_token}"},
    )
    assert resp.status_code == 200
    assert len(resp.json()) == 1  # Only the visible one
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && uv run pytest tests/test_training_reviews.py -v`
Expected: FAIL — route not found

- [ ] **Step 3: Create training routes file**

Create `backend/app/routes/training.py`:

```python
from __future__ import annotations

from datetime import date, timedelta
from typing import Optional

from litestar import Router, get, post, put, delete, Request
from litestar.di import Provide
from litestar.exceptions import NotFoundException, PermissionDeniedException
from litestar.status_codes import HTTP_201_CREATED, HTTP_204_NO_CONTENT
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.guards import require_coach_or_admin
from app.database import get_session
from app.models.weekly_review import WeeklyReview
from app.models.incident import Incident
from app.models.user_skater import UserSkater


def _snap_to_monday(d: date) -> date:
    """Return the Monday of the week containing `d`."""
    return d - timedelta(days=d.weekday())


def _review_to_dict(r: WeeklyReview) -> dict:
    return {
        "id": r.id,
        "skater_id": r.skater_id,
        "coach_id": r.coach_id,
        "week_start": r.week_start.isoformat(),
        "attendance": r.attendance,
        "engagement": r.engagement,
        "progression": r.progression,
        "attitude": r.attitude,
        "strengths": r.strengths,
        "improvements": r.improvements,
        "visible_to_skater": r.visible_to_skater,
        "created_at": r.created_at.isoformat() if r.created_at else None,
        "updated_at": r.updated_at.isoformat() if r.updated_at else None,
    }


def _incident_to_dict(i: Incident) -> dict:
    return {
        "id": i.id,
        "skater_id": i.skater_id,
        "coach_id": i.coach_id,
        "date": i.date.isoformat(),
        "incident_type": i.incident_type,
        "description": i.description,
        "visible_to_skater": i.visible_to_skater,
        "created_at": i.created_at.isoformat() if i.created_at else None,
        "updated_at": i.updated_at.isoformat() if i.updated_at else None,
    }


async def _check_skater_read_access(request: Request, skater_id: int, session: AsyncSession) -> None:
    """For skater role, verify user has access to this skater via UserSkater."""
    state = request.scope.get("state", {})
    if state.get("user_role") == "skater":
        result = await session.execute(
            select(UserSkater).where(
                UserSkater.user_id == state["user_id"],
                UserSkater.skater_id == skater_id,
            )
        )
        if not result.scalar_one_or_none():
            raise PermissionDeniedException("You do not have access to this skater")


# --- Weekly Reviews ---


@get("/reviews")
async def list_reviews(
    request: Request,
    session: AsyncSession,
    skater_id: Optional[int] = None,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
) -> list[dict]:
    state = request.scope.get("state", {})
    role = state.get("user_role")

    if role not in ("coach", "admin", "skater"):
        raise PermissionDeniedException("Access denied")

    stmt = select(WeeklyReview).order_by(WeeklyReview.week_start.desc())

    if skater_id is not None:
        if role == "skater":
            await _check_skater_read_access(request, skater_id, session)
        stmt = stmt.where(WeeklyReview.skater_id == skater_id)

    if role == "skater":
        stmt = stmt.where(WeeklyReview.visible_to_skater == True)  # noqa: E712
        # Also filter to only linked skaters if no skater_id specified
        if skater_id is None:
            user_id = state["user_id"]
            linked = select(UserSkater.skater_id).where(UserSkater.user_id == user_id)
            stmt = stmt.where(WeeklyReview.skater_id.in_(linked))

    if from_date:
        stmt = stmt.where(WeeklyReview.week_start >= date.fromisoformat(from_date))
    if to_date:
        stmt = stmt.where(WeeklyReview.week_start <= date.fromisoformat(to_date))

    result = await session.execute(stmt)
    return [_review_to_dict(r) for r in result.scalars().all()]


@get("/reviews/{review_id:int}")
async def get_review(review_id: int, request: Request, session: AsyncSession) -> dict:
    state = request.scope.get("state", {})
    role = state.get("user_role")

    review = await session.get(WeeklyReview, review_id)
    if not review:
        raise NotFoundException("Review not found")

    if role == "skater":
        await _check_skater_read_access(request, review.skater_id, session)
        if not review.visible_to_skater:
            raise NotFoundException("Review not found")
    elif role not in ("coach", "admin"):
        raise PermissionDeniedException("Access denied")

    return _review_to_dict(review)


@post("/reviews", status_code=HTTP_201_CREATED)
async def create_review(request: Request, session: AsyncSession, data: dict) -> dict:
    require_coach_or_admin(request)
    state = request.scope.get("state", {})

    week_start = _snap_to_monday(date.fromisoformat(data["week_start"]))

    review = WeeklyReview(
        skater_id=data["skater_id"],
        coach_id=state["user_id"],
        week_start=week_start,
        attendance=data.get("attendance", ""),
        engagement=data["engagement"],
        progression=data["progression"],
        attitude=data["attitude"],
        strengths=data.get("strengths", ""),
        improvements=data.get("improvements", ""),
        visible_to_skater=data.get("visible_to_skater", True),
    )
    session.add(review)
    await session.commit()
    await session.refresh(review)
    return _review_to_dict(review)


@put("/reviews/{review_id:int}")
async def update_review(review_id: int, request: Request, session: AsyncSession, data: dict) -> dict:
    state = request.scope.get("state", {})
    role = state.get("user_role")

    if role not in ("coach", "admin"):
        raise PermissionDeniedException("Access denied")

    review = await session.get(WeeklyReview, review_id)
    if not review:
        raise NotFoundException("Review not found")

    for field in ("attendance", "engagement", "progression", "attitude", "strengths", "improvements", "visible_to_skater"):
        if field in data:
            setattr(review, field, data[field])

    # Per spec: any coach can edit any review, coach_id updates to current editor
    review.coach_id = state["user_id"]

    await session.commit()
    await session.refresh(review)
    return _review_to_dict(review)


@delete("/reviews/{review_id:int}", status_code=HTTP_204_NO_CONTENT)
async def delete_review(review_id: int, request: Request, session: AsyncSession) -> None:
    state = request.scope.get("state", {})
    role = state.get("user_role")

    if role not in ("coach", "admin"):
        raise PermissionDeniedException("Access denied")

    review = await session.get(WeeklyReview, review_id)
    if not review:
        raise NotFoundException("Review not found")

    if role == "coach" and review.coach_id != state["user_id"]:
        raise PermissionDeniedException("You can only delete your own reviews")

    await session.delete(review)
    await session.commit()


# --- Incidents ---


@get("/incidents")
async def list_incidents(
    request: Request,
    session: AsyncSession,
    skater_id: Optional[int] = None,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
) -> list[dict]:
    state = request.scope.get("state", {})
    role = state.get("user_role")

    if role not in ("coach", "admin", "skater"):
        raise PermissionDeniedException("Access denied")

    stmt = select(Incident).order_by(Incident.date.desc())

    if skater_id is not None:
        if role == "skater":
            await _check_skater_read_access(request, skater_id, session)
        stmt = stmt.where(Incident.skater_id == skater_id)

    if role == "skater":
        stmt = stmt.where(Incident.visible_to_skater == True)  # noqa: E712
        if skater_id is None:
            user_id = state["user_id"]
            linked = select(UserSkater.skater_id).where(UserSkater.user_id == user_id)
            stmt = stmt.where(Incident.skater_id.in_(linked))

    if from_date:
        stmt = stmt.where(Incident.date >= date.fromisoformat(from_date))
    if to_date:
        stmt = stmt.where(Incident.date <= date.fromisoformat(to_date))

    result = await session.execute(stmt)
    return [_incident_to_dict(i) for i in result.scalars().all()]


@get("/incidents/{incident_id:int}")
async def get_incident(incident_id: int, request: Request, session: AsyncSession) -> dict:
    state = request.scope.get("state", {})
    role = state.get("user_role")

    incident = await session.get(Incident, incident_id)
    if not incident:
        raise NotFoundException("Incident not found")

    if role == "skater":
        await _check_skater_read_access(request, incident.skater_id, session)
        if not incident.visible_to_skater:
            raise NotFoundException("Incident not found")
    elif role not in ("coach", "admin"):
        raise PermissionDeniedException("Access denied")

    return _incident_to_dict(incident)


@post("/incidents", status_code=HTTP_201_CREATED)
async def create_incident(request: Request, session: AsyncSession, data: dict) -> dict:
    require_coach_or_admin(request)
    state = request.scope.get("state", {})

    incident = Incident(
        skater_id=data["skater_id"],
        coach_id=state["user_id"],
        date=date.fromisoformat(data["date"]),
        incident_type=data["incident_type"],
        description=data.get("description", ""),
        visible_to_skater=data.get("visible_to_skater", False),
    )
    session.add(incident)
    await session.commit()
    await session.refresh(incident)
    return _incident_to_dict(incident)


@put("/incidents/{incident_id:int}")
async def update_incident(incident_id: int, request: Request, session: AsyncSession, data: dict) -> dict:
    state = request.scope.get("state", {})
    role = state.get("user_role")

    if role not in ("coach", "admin"):
        raise PermissionDeniedException("Access denied")

    incident = await session.get(Incident, incident_id)
    if not incident:
        raise NotFoundException("Incident not found")

    if role == "coach" and incident.coach_id != state["user_id"]:
        raise PermissionDeniedException("You can only edit your own incidents")

    for field in ("date", "incident_type", "description", "visible_to_skater"):
        if field in data:
            value = data[field]
            if field == "date":
                value = date.fromisoformat(value)
            setattr(incident, field, value)

    await session.commit()
    await session.refresh(incident)
    return _incident_to_dict(incident)


@delete("/incidents/{incident_id:int}", status_code=HTTP_204_NO_CONTENT)
async def delete_incident(incident_id: int, request: Request, session: AsyncSession) -> None:
    state = request.scope.get("state", {})
    role = state.get("user_role")

    if role not in ("coach", "admin"):
        raise PermissionDeniedException("Access denied")

    incident = await session.get(Incident, incident_id)
    if not incident:
        raise NotFoundException("Incident not found")

    if role == "coach" and incident.coach_id != state["user_id"]:
        raise PermissionDeniedException("You can only delete your own incidents")

    await session.delete(incident)
    await session.commit()


# --- Timeline ---


@get("/timeline")
async def get_timeline(
    request: Request,
    session: AsyncSession,
    skater_id: int = 0,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
) -> list[dict]:
    state = request.scope.get("state", {})
    role = state.get("user_role")

    if role not in ("coach", "admin", "skater"):
        raise PermissionDeniedException("Access denied")

    if role == "skater":
        await _check_skater_read_access(request, skater_id, session)

    # Fetch reviews
    review_stmt = select(WeeklyReview).where(WeeklyReview.skater_id == skater_id)
    if role == "skater":
        review_stmt = review_stmt.where(WeeklyReview.visible_to_skater == True)  # noqa: E712
    if from_date:
        review_stmt = review_stmt.where(WeeklyReview.week_start >= date.fromisoformat(from_date))
    if to_date:
        review_stmt = review_stmt.where(WeeklyReview.week_start <= date.fromisoformat(to_date))
    reviews = (await session.execute(review_stmt)).scalars().all()

    # Fetch incidents
    incident_stmt = select(Incident).where(Incident.skater_id == skater_id)
    if role == "skater":
        incident_stmt = incident_stmt.where(Incident.visible_to_skater == True)  # noqa: E712
    if from_date:
        incident_stmt = incident_stmt.where(Incident.date >= date.fromisoformat(from_date))
    if to_date:
        incident_stmt = incident_stmt.where(Incident.date <= date.fromisoformat(to_date))
    incidents = (await session.execute(incident_stmt)).scalars().all()

    # Merge into timeline
    timeline = []
    for r in reviews:
        entry = _review_to_dict(r)
        entry["type"] = "review"
        entry["sort_date"] = r.week_start.isoformat()
        timeline.append(entry)
    for i in incidents:
        entry = _incident_to_dict(i)
        entry["type"] = "incident"
        entry["sort_date"] = i.date.isoformat()
        timeline.append(entry)

    timeline.sort(key=lambda x: x["sort_date"], reverse=True)
    return timeline


router = Router(
    path="/api/training",
    route_handlers=[
        list_reviews, get_review, create_review, update_review, delete_review,
        list_incidents, get_incident, create_incident, update_incident, delete_incident,
        get_timeline,
    ],
    dependencies={"session": Provide(get_session)},
)
```

- [ ] **Step 4: Register training router in main.py**

In `backend/app/main.py`, add import:
```python
from app.routes.training import router as training_router
```

Add `training_router` to the `route_handlers` list in the `Litestar()` call.

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd backend && uv run pytest tests/test_training_reviews.py -v`
Expected: PASS

- [ ] **Step 6: Run all existing tests to verify no regression**

Run: `cd backend && uv run pytest -v`
Expected: All tests PASS

- [ ] **Step 7: Commit**

```bash
git add backend/app/routes/training.py backend/app/main.py backend/tests/test_training_reviews.py
git commit -m "feat: add training review and incident CRUD routes with timeline"
```

---

### Task 4: Backend tests for incidents and timeline

**Files:**
- Test: `backend/tests/test_training_incidents.py`
- Test: `backend/tests/test_training_timeline.py`

- [ ] **Step 1: Write incident tests**

Create `backend/tests/test_training_incidents.py`:

```python
import pytest
from datetime import date

from app.auth.tokens import create_access_token
from app.auth.passwords import hash_password
from app.models.user import User
from app.models.skater import Skater
from app.models.user_skater import UserSkater


@pytest.fixture
async def coach_and_skater(db_session):
    coach = User(
        email="coach@test.com",
        password_hash=hash_password("coachpass1"),
        display_name="Test Coach",
        role="coach",
    )
    db_session.add(coach)
    skater = Skater(first_name="Alice", last_name="Dupont", club="TestClub")
    db_session.add(skater)
    await db_session.commit()
    await db_session.refresh(coach)
    await db_session.refresh(skater)
    token = create_access_token(user_id=coach.id, role=coach.role)
    return coach, token, skater


async def test_create_incident(client, coach_and_skater):
    coach, token, skater = coach_and_skater
    resp = await client.post(
        "/api/training/incidents",
        json={
            "skater_id": skater.id,
            "date": "2026-03-24",
            "incident_type": "injury",
            "description": "Douleur au genou",
            "visible_to_skater": False,
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["incident_type"] == "injury"
    assert data["visible_to_skater"] is False


async def test_update_incident(client, coach_and_skater):
    _, token, skater = coach_and_skater
    create_resp = await client.post(
        "/api/training/incidents",
        json={
            "skater_id": skater.id,
            "date": "2026-03-24",
            "incident_type": "behavior",
            "description": "Retard",
            "visible_to_skater": False,
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    incident_id = create_resp.json()["id"]
    resp = await client.put(
        f"/api/training/incidents/{incident_id}",
        json={"description": "Retard répété", "visible_to_skater": True},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["description"] == "Retard répété"
    assert resp.json()["visible_to_skater"] is True


async def test_delete_incident(client, coach_and_skater):
    _, token, skater = coach_and_skater
    create_resp = await client.post(
        "/api/training/incidents",
        json={
            "skater_id": skater.id,
            "date": "2026-03-24",
            "incident_type": "other",
            "description": "Test",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    incident_id = create_resp.json()["id"]
    resp = await client.delete(
        f"/api/training/incidents/{incident_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 204


async def test_skater_hidden_incident_not_visible(client, coach_and_skater, db_session):
    _, coach_token, skater = coach_and_skater

    # Create parent linked to skater
    parent = User(
        email="parent@test.com",
        password_hash=hash_password("parentpass1"),
        display_name="Parent",
        role="skater",
    )
    db_session.add(parent)
    await db_session.flush()
    link = UserSkater(user_id=parent.id, skater_id=skater.id)
    db_session.add(link)
    await db_session.commit()
    await db_session.refresh(parent)
    parent_token = create_access_token(user_id=parent.id, role=parent.role)

    # Create hidden incident
    await client.post(
        "/api/training/incidents",
        json={
            "skater_id": skater.id,
            "date": "2026-03-24",
            "incident_type": "injury",
            "description": "Chute",
            "visible_to_skater": False,
        },
        headers={"Authorization": f"Bearer {coach_token}"},
    )

    resp = await client.get(
        f"/api/training/incidents?skater_id={skater.id}",
        headers={"Authorization": f"Bearer {parent_token}"},
    )
    assert resp.status_code == 200
    assert len(resp.json()) == 0
```

- [ ] **Step 2: Write timeline tests**

Create `backend/tests/test_training_timeline.py`:

```python
import pytest

from app.auth.tokens import create_access_token
from app.auth.passwords import hash_password
from app.models.user import User
from app.models.skater import Skater
from app.models.user_skater import UserSkater


@pytest.fixture
async def coach_and_skater(db_session):
    coach = User(
        email="coach@test.com",
        password_hash=hash_password("coachpass1"),
        display_name="Test Coach",
        role="coach",
    )
    db_session.add(coach)
    skater = Skater(first_name="Alice", last_name="Dupont", club="TestClub")
    db_session.add(skater)
    await db_session.commit()
    await db_session.refresh(coach)
    await db_session.refresh(skater)
    token = create_access_token(user_id=coach.id, role=coach.role)
    return coach, token, skater


async def test_timeline_merges_reviews_and_incidents(client, coach_and_skater):
    _, token, skater = coach_and_skater

    # Create a review
    await client.post(
        "/api/training/reviews",
        json={
            "skater_id": skater.id,
            "week_start": "2026-03-23",
            "attendance": "3/4",
            "engagement": 4,
            "progression": 3,
            "attitude": 5,
            "strengths": "Bon",
            "improvements": "Mieux",
            "visible_to_skater": True,
        },
        headers={"Authorization": f"Bearer {token}"},
    )

    # Create an incident
    await client.post(
        "/api/training/incidents",
        json={
            "skater_id": skater.id,
            "date": "2026-03-25",
            "incident_type": "injury",
            "description": "Chute",
            "visible_to_skater": True,
        },
        headers={"Authorization": f"Bearer {token}"},
    )

    resp = await client.get(
        f"/api/training/timeline?skater_id={skater.id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2
    # Most recent first
    assert data[0]["type"] == "incident"
    assert data[1]["type"] == "review"


async def test_timeline_skater_sees_only_visible(client, coach_and_skater, db_session):
    _, coach_token, skater = coach_and_skater

    parent = User(
        email="parent@test.com",
        password_hash=hash_password("parentpass1"),
        display_name="Parent",
        role="skater",
    )
    db_session.add(parent)
    await db_session.flush()
    link = UserSkater(user_id=parent.id, skater_id=skater.id)
    db_session.add(link)
    await db_session.commit()
    await db_session.refresh(parent)
    parent_token = create_access_token(user_id=parent.id, role=parent.role)

    # Visible review + hidden incident
    await client.post(
        "/api/training/reviews",
        json={
            "skater_id": skater.id,
            "week_start": "2026-03-23",
            "attendance": "3/4",
            "engagement": 4,
            "progression": 3,
            "attitude": 5,
            "strengths": "Bon",
            "improvements": "Mieux",
            "visible_to_skater": True,
        },
        headers={"Authorization": f"Bearer {coach_token}"},
    )
    await client.post(
        "/api/training/incidents",
        json={
            "skater_id": skater.id,
            "date": "2026-03-25",
            "incident_type": "injury",
            "description": "Chute",
            "visible_to_skater": False,
        },
        headers={"Authorization": f"Bearer {coach_token}"},
    )

    resp = await client.get(
        f"/api/training/timeline?skater_id={skater.id}",
        headers={"Authorization": f"Bearer {parent_token}"},
    )
    assert resp.status_code == 200
    assert len(resp.json()) == 1
    assert resp.json()[0]["type"] == "review"
```

- [ ] **Step 3: Run all training tests**

Run: `cd backend && uv run pytest tests/test_training_incidents.py tests/test_training_timeline.py -v`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add backend/tests/test_training_incidents.py backend/tests/test_training_timeline.py
git commit -m "test: add incident and timeline endpoint tests"
```

---

### Task 5: Add coach fixture to conftest.py

**Files:**
- Modify: `backend/tests/conftest.py` (add coach_user and coach_token fixtures)

- [ ] **Step 1: Add coach fixtures to conftest**

In `backend/tests/conftest.py`, add after the `reader_user` fixture:

```python
@pytest_asyncio.fixture
async def coach_user(db_session: AsyncSession):
    """Create a coach user and return (user, plain_password)."""
    from app.models.user import User

    password = "coachpass1"
    user = User(
        email="coach@test.com",
        password_hash=hash_password(password),
        display_name="Test Coach",
        role="coach",
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user, password


@pytest_asyncio.fixture
async def coach_token(coach_user) -> str:
    """Return a valid access token for the coach user."""
    from app.auth.tokens import create_access_token

    user, _ = coach_user
    return create_access_token(user_id=user.id, role=user.role)
```

- [ ] **Step 2: Run all tests to verify no regression**

Run: `cd backend && uv run pytest -v`
Expected: All PASS

- [ ] **Step 3: Commit**

```bash
git add backend/tests/conftest.py
git commit -m "test: add coach_user and coach_token fixtures to conftest"
```

---

### Task 6: Frontend API client — training types and functions

**Files:**
- Modify: `frontend/src/api/client.ts` (add types and API functions)

- [ ] **Step 1: Add training TypeScript types**

In `frontend/src/api/client.ts`, add after the `BenchmarkData` interface (around line 390):

```typescript
// --- Training Tracking Types ---

export interface WeeklyReview {
  id: number;
  skater_id: number;
  coach_id: string;
  week_start: string;
  attendance: string;
  engagement: number;
  progression: number;
  attitude: number;
  strengths: string;
  improvements: string;
  visible_to_skater: boolean;
  created_at: string | null;
  updated_at: string | null;
}

export interface CreateReviewPayload {
  skater_id: number;
  week_start: string;
  attendance: string;
  engagement: number;
  progression: number;
  attitude: number;
  strengths: string;
  improvements: string;
  visible_to_skater: boolean;
}

export interface UpdateReviewPayload {
  attendance?: string;
  engagement?: number;
  progression?: number;
  attitude?: number;
  strengths?: string;
  improvements?: string;
  visible_to_skater?: boolean;
}

export interface TrainingIncident {
  id: number;
  skater_id: number;
  coach_id: string;
  date: string;
  incident_type: "injury" | "behavior" | "other";
  description: string;
  visible_to_skater: boolean;
  created_at: string | null;
  updated_at: string | null;
}

export interface CreateIncidentPayload {
  skater_id: number;
  date: string;
  incident_type: "injury" | "behavior" | "other";
  description: string;
  visible_to_skater: boolean;
}

export interface UpdateIncidentPayload {
  date?: string;
  incident_type?: "injury" | "behavior" | "other";
  description?: string;
  visible_to_skater?: boolean;
}

export type TimelineEntry = (WeeklyReview & { type: "review"; sort_date: string }) | (TrainingIncident & { type: "incident"; sort_date: string });
```

- [ ] **Step 2: Add training API functions**

In `frontend/src/api/client.ts`, add inside the `api` object (after the `stats` section):

```typescript
  training: {
    reviews: {
      list: (params?: { skater_id?: number; from?: string; to?: string }) => {
        const qs = new URLSearchParams();
        if (params?.skater_id !== undefined) qs.set("skater_id", String(params.skater_id));
        if (params?.from) qs.set("from_date", params.from);
        if (params?.to) qs.set("to_date", params.to);
        const query = qs.toString() ? `?${qs}` : "";
        return request<WeeklyReview[]>(`/training/reviews${query}`);
      },
      get: (id: number) => request<WeeklyReview>(`/training/reviews/${id}`),
      create: (data: CreateReviewPayload) =>
        request<WeeklyReview>("/training/reviews", {
          method: "POST",
          body: JSON.stringify(data),
        }),
      update: (id: number, data: UpdateReviewPayload) =>
        request<WeeklyReview>(`/training/reviews/${id}`, {
          method: "PUT",
          body: JSON.stringify(data),
        }),
      delete: (id: number) =>
        request<void>(`/training/reviews/${id}`, { method: "DELETE" }),
    },
    incidents: {
      list: (params?: { skater_id?: number; from?: string; to?: string }) => {
        const qs = new URLSearchParams();
        if (params?.skater_id !== undefined) qs.set("skater_id", String(params.skater_id));
        if (params?.from) qs.set("from_date", params.from);
        if (params?.to) qs.set("to_date", params.to);
        const query = qs.toString() ? `?${qs}` : "";
        return request<TrainingIncident[]>(`/training/incidents${query}`);
      },
      get: (id: number) => request<TrainingIncident>(`/training/incidents/${id}`),
      create: (data: CreateIncidentPayload) =>
        request<TrainingIncident>("/training/incidents", {
          method: "POST",
          body: JSON.stringify(data),
        }),
      update: (id: number, data: UpdateIncidentPayload) =>
        request<TrainingIncident>(`/training/incidents/${id}`, {
          method: "PUT",
          body: JSON.stringify(data),
        }),
      delete: (id: number) =>
        request<void>(`/training/incidents/${id}`, { method: "DELETE" }),
    },
    timeline: (params: { skater_id: number; from?: string; to?: string }) => {
      const qs = new URLSearchParams({ skater_id: String(params.skater_id) });
      if (params.from) qs.set("from_date", params.from);
      if (params.to) qs.set("to_date", params.to);
      return request<TimelineEntry[]>(`/training/timeline?${qs}`);
    },
  },
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/api/client.ts
git commit -m "feat: add training tracking types and API functions to frontend client"
```

---

### Task 7: Frontend — Training skater list page (coach view)

**Files:**
- Create: `frontend/src/pages/TrainingPage.tsx`
- Modify: `frontend/src/App.tsx` (add route and nav link for coach)

- [ ] **Step 1: Create TrainingPage component**

Create `frontend/src/pages/TrainingPage.tsx`:

```tsx
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { api, Skater, WeeklyReview } from "../api/client";

function SkaterCard({ skater, lastReview }: { skater: Skater; lastReview?: WeeklyReview }) {
  const avgScore = lastReview
    ? ((lastReview.engagement + lastReview.progression + lastReview.attitude) / 3).toFixed(1)
    : null;

  return (
    <Link
      to={`/entrainement/patineurs/${skater.id}`}
      className="bg-surface-container-low rounded-2xl p-5 hover:bg-surface-container transition-colors"
    >
      <div className="flex items-center justify-between">
        <div>
          <h3 className="font-headline font-bold text-on-surface">
            {skater.first_name} {skater.last_name}
          </h3>
          {skater.club && (
            <p className="text-xs text-on-surface-variant mt-0.5">{skater.club}</p>
          )}
        </div>
        {avgScore && (
          <div className="text-right">
            <span className="font-mono text-lg font-bold text-primary">{avgScore}</span>
            <p className="text-[10px] text-on-surface-variant uppercase">Moy.</p>
          </div>
        )}
      </div>
      {lastReview && (
        <p className="text-xs text-on-surface-variant mt-2">
          Dernier retour : semaine du {new Date(lastReview.week_start).toLocaleDateString("fr-FR")}
        </p>
      )}
    </Link>
  );
}

export default function TrainingPage() {
  const { data: skaters, isLoading: skatersLoading } = useQuery({
    queryKey: ["skaters"],
    queryFn: () => api.skaters.list(),
  });

  const { data: reviews } = useQuery({
    queryKey: ["training", "reviews", "latest"],
    queryFn: () => api.training.reviews.list(),
  });

  if (skatersLoading) {
    return (
      <div className="flex items-center justify-center py-20">
        <span className="material-symbols-outlined animate-spin text-primary text-3xl">
          progress_activity
        </span>
      </div>
    );
  }

  // Build map of latest review per skater
  const latestReview: Record<number, WeeklyReview> = {};
  if (reviews) {
    for (const r of reviews) {
      if (!latestReview[r.skater_id] || r.week_start > latestReview[r.skater_id].week_start) {
        latestReview[r.skater_id] = r;
      }
    }
  }

  return (
    <div className="space-y-6">
      <p className="text-on-surface-variant text-sm">
        {skaters?.length ?? 0} patineur{(skaters?.length ?? 0) > 1 ? "s" : ""}
      </p>
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {skaters?.map((s) => (
          <SkaterCard key={s.id} skater={s} lastReview={latestReview[s.id]} />
        ))}
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Add route and nav for coach/admin in App.tsx**

In `frontend/src/App.tsx`:

1. Add import: `import TrainingPage from "./pages/TrainingPage";`

2. Add nav link object to the `navLinks` array:
```typescript
{ to: "/entrainement", label: "ENTRAÎNEMENT", icon: "fitness_center", end: false },
```

3. Add route inside the non-skater routes block (after the `/club` routes):
```tsx
<Route path="/entrainement" element={<TrainingPage />} />
```

4. Add to `getPageTitle`:
```typescript
if (pathname === "/entrainement") return "Suivi entraînement";
if (pathname.startsWith("/entrainement/")) return "Suivi entraînement";
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/pages/TrainingPage.tsx frontend/src/App.tsx
git commit -m "feat: add training skater list page with coach navigation"
```

---

### Task 8: Frontend — Skater training detail page with tabs

**Files:**
- Create: `frontend/src/pages/SkaterTrainingPage.tsx`
- Modify: `frontend/src/App.tsx` (add route)

- [ ] **Step 1: Create SkaterTrainingPage**

Create `frontend/src/pages/SkaterTrainingPage.tsx`:

```tsx
import { useState } from "react";
import { useParams } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api, Skater, WeeklyReview, TrainingIncident } from "../api/client";

const TABS = [
  { key: "reviews", label: "Retours", icon: "rate_review" },
  { key: "incidents", label: "Incidents", icon: "warning" },
  { key: "evolution", label: "Évolution", icon: "trending_up" },
] as const;

type Tab = typeof TABS[number]["key"];

function RatingDots({ value, max = 5 }: { value: number; max?: number }) {
  return (
    <div className="flex gap-0.5">
      {Array.from({ length: max }, (_, i) => (
        <div
          key={i}
          className={`w-2.5 h-2.5 rounded-full ${
            i < value ? "bg-primary" : "bg-surface-container"
          }`}
        />
      ))}
    </div>
  );
}

function ReviewCard({ review }: { review: WeeklyReview }) {
  const weekDate = new Date(review.week_start).toLocaleDateString("fr-FR", {
    day: "numeric",
    month: "long",
    year: "numeric",
  });

  return (
    <div className="bg-surface-container-low rounded-2xl p-5 space-y-3">
      <div className="flex items-center justify-between">
        <h4 className="font-headline font-bold text-on-surface text-sm">
          Semaine du {weekDate}
        </h4>
        <div className="flex items-center gap-2">
          {!review.visible_to_skater && (
            <span className="material-symbols-outlined text-on-surface-variant text-sm" title="Non visible par le patineur">
              visibility_off
            </span>
          )}
          <span className="font-mono text-xs text-on-surface-variant">{review.attendance}</span>
        </div>
      </div>
      <div className="grid grid-cols-3 gap-4">
        <div>
          <p className="text-[10px] uppercase tracking-wider text-on-surface-variant mb-1">Engagement</p>
          <RatingDots value={review.engagement} />
        </div>
        <div>
          <p className="text-[10px] uppercase tracking-wider text-on-surface-variant mb-1">Progression</p>
          <RatingDots value={review.progression} />
        </div>
        <div>
          <p className="text-[10px] uppercase tracking-wider text-on-surface-variant mb-1">Attitude</p>
          <RatingDots value={review.attitude} />
        </div>
      </div>
      {review.strengths && (
        <div>
          <p className="text-[10px] uppercase tracking-wider text-on-surface-variant mb-0.5">Points forts</p>
          <p className="text-sm text-on-surface">{review.strengths}</p>
        </div>
      )}
      {review.improvements && (
        <div>
          <p className="text-[10px] uppercase tracking-wider text-on-surface-variant mb-0.5">Axes d'amélioration</p>
          <p className="text-sm text-on-surface">{review.improvements}</p>
        </div>
      )}
    </div>
  );
}

const INCIDENT_TYPE_LABELS: Record<string, { label: string; color: string; icon: string }> = {
  injury: { label: "Blessure", color: "text-error", icon: "healing" },
  behavior: { label: "Comportement", color: "text-orange-600", icon: "report" },
  other: { label: "Autre", color: "text-on-surface-variant", icon: "info" },
};

function IncidentCard({ incident }: { incident: TrainingIncident }) {
  const meta = INCIDENT_TYPE_LABELS[incident.incident_type] ?? INCIDENT_TYPE_LABELS.other;
  return (
    <div className="bg-surface-container-low rounded-2xl p-5 space-y-2">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className={`material-symbols-outlined text-lg ${meta.color}`}>{meta.icon}</span>
          <span className={`text-sm font-bold ${meta.color}`}>{meta.label}</span>
        </div>
        <div className="flex items-center gap-2">
          {!incident.visible_to_skater && (
            <span className="material-symbols-outlined text-on-surface-variant text-sm" title="Non visible par le patineur">
              visibility_off
            </span>
          )}
          <span className="text-xs text-on-surface-variant">
            {new Date(incident.date).toLocaleDateString("fr-FR")}
          </span>
        </div>
      </div>
      <p className="text-sm text-on-surface">{incident.description}</p>
    </div>
  );
}

export default function SkaterTrainingPage() {
  const { id } = useParams<{ id: string }>();
  const skaterId = Number(id);
  const [activeTab, setActiveTab] = useState<Tab>("reviews");

  const { data: skater } = useQuery({
    queryKey: ["skater", skaterId],
    queryFn: () => api.skaters.get(skaterId),
  });

  const { data: reviews } = useQuery({
    queryKey: ["training", "reviews", skaterId],
    queryFn: () => api.training.reviews.list({ skater_id: skaterId }),
  });

  const { data: incidents } = useQuery({
    queryKey: ["training", "incidents", skaterId],
    queryFn: () => api.training.incidents.list({ skater_id: skaterId }),
  });

  if (!skater) {
    return (
      <div className="flex items-center justify-center py-20">
        <span className="material-symbols-outlined animate-spin text-primary text-3xl">
          progress_activity
        </span>
      </div>
    );
  }

  // Averages over last 4 weeks
  const recentReviews = (reviews ?? []).slice(0, 4);
  const avg = (field: "engagement" | "progression" | "attitude") =>
    recentReviews.length
      ? (recentReviews.reduce((s, r) => s + r[field], 0) / recentReviews.length).toFixed(1)
      : "—";

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="font-headline font-bold text-on-surface text-xl">
            {skater.first_name} {skater.last_name}
          </h2>
          {skater.club && (
            <p className="text-sm text-on-surface-variant">{skater.club}</p>
          )}
        </div>
        <div className="flex gap-4">
          {(["engagement", "progression", "attitude"] as const).map((field) => (
            <div key={field} className="text-center">
              <span className="font-mono text-lg font-bold text-primary">{avg(field)}</span>
              <p className="text-[10px] uppercase tracking-wider text-on-surface-variant capitalize">
                {field}
              </p>
            </div>
          ))}
        </div>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 bg-surface-container rounded-xl p-1">
        {TABS.map((tab) => (
          <button
            key={tab.key}
            onClick={() => setActiveTab(tab.key)}
            className={`flex-1 flex items-center justify-center gap-2 py-2.5 rounded-lg text-xs font-bold uppercase tracking-wider transition-colors ${
              activeTab === tab.key
                ? "bg-white text-primary shadow-sm"
                : "text-on-surface-variant hover:text-on-surface"
            }`}
          >
            <span className="material-symbols-outlined text-lg">{tab.icon}</span>
            {tab.label}
          </button>
        ))}
      </div>

      {/* Tab content */}
      {activeTab === "reviews" && (
        <div className="space-y-3">
          {(reviews ?? []).length === 0 ? (
            <p className="text-sm text-on-surface-variant text-center py-10">Aucun retour pour le moment</p>
          ) : (
            reviews?.map((r) => <ReviewCard key={r.id} review={r} />)
          )}
        </div>
      )}

      {activeTab === "incidents" && (
        <div className="space-y-3">
          {(incidents ?? []).length === 0 ? (
            <p className="text-sm text-on-surface-variant text-center py-10">Aucun incident signalé</p>
          ) : (
            incidents?.map((i) => <IncidentCard key={i.id} incident={i} />)
          )}
        </div>
      )}

      {activeTab === "evolution" && (
        <div className="text-sm text-on-surface-variant text-center py-10">
          Les graphiques d'évolution seront ajoutés dans la prochaine tâche.
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Add route in App.tsx**

Add import: `import SkaterTrainingPage from "./pages/SkaterTrainingPage";`

Add route (in non-skater routes, after the `/entrainement` route):
```tsx
<Route path="/entrainement/patineurs/:id" element={<SkaterTrainingPage />} />
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/pages/SkaterTrainingPage.tsx frontend/src/App.tsx
git commit -m "feat: add skater training detail page with reviews and incidents tabs"
```

---

### Task 9: Frontend — Review and incident create/edit forms

**Files:**
- Modify: `frontend/src/pages/SkaterTrainingPage.tsx` (add modals for creating and editing reviews and incidents)

- [ ] **Step 1: Add ReviewFormModal component (supports create and edit)**

In `frontend/src/pages/SkaterTrainingPage.tsx`, add before the `export default`:

```tsx
function ReviewFormModal({
  skaterId,
  existing,
  onClose,
}: {
  skaterId: number;
  existing?: WeeklyReview;
  onClose: () => void;
}) {
  const queryClient = useQueryClient();
  const [form, setForm] = useState({
    week_start: existing?.week_start ?? new Date().toISOString().split("T")[0],
    attendance: existing?.attendance ?? "",
    engagement: existing?.engagement ?? 3,
    progression: existing?.progression ?? 3,
    attitude: existing?.attitude ?? 3,
    strengths: existing?.strengths ?? "",
    improvements: existing?.improvements ?? "",
    visible_to_skater: existing?.visible_to_skater ?? true,
  });

  const mutation = useMutation({
    mutationFn: () =>
      existing
        ? api.training.reviews.update(existing.id, form)
        : api.training.reviews.create({ ...form, skater_id: skaterId }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["training", "reviews"] });
      onClose();
    },
  });

  function RatingSelect({ value, onChange, label }: { value: number; onChange: (v: number) => void; label: string }) {
    return (
      <div>
        <label className="text-[10px] uppercase tracking-wider text-on-surface-variant block mb-1">{label}</label>
        <div className="flex gap-1">
          {[1, 2, 3, 4, 5].map((n) => (
            <button
              key={n}
              type="button"
              onClick={() => onChange(n)}
              className={`w-8 h-8 rounded-lg font-mono text-sm font-bold transition-colors ${
                n <= value
                  ? "bg-primary text-white"
                  : "bg-surface-container text-on-surface-variant hover:bg-surface-container-high"
              }`}
            >
              {n}
            </button>
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="fixed inset-0 bg-scrim/50 z-50 flex items-center justify-center p-4" onClick={onClose}>
      <div
        className="bg-surface rounded-3xl p-6 w-full max-w-lg max-h-[90vh] overflow-y-auto space-y-4"
        onClick={(e) => e.stopPropagation()}
      >
        <h3 className="font-headline font-bold text-on-surface text-lg">
          {existing ? "Modifier le retour" : "Nouveau retour"}
        </h3>

        <div>
          <label className="text-[10px] uppercase tracking-wider text-on-surface-variant block mb-1">Semaine du</label>
          <input
            type="date"
            value={form.week_start}
            onChange={(e) => setForm({ ...form, week_start: e.target.value })}
            className="w-full bg-surface-container rounded-xl px-4 py-2.5 text-sm text-on-surface outline-none focus:ring-2 focus:ring-primary"
          />
        </div>

        <div>
          <label className="text-[10px] uppercase tracking-wider text-on-surface-variant block mb-1">Assiduité</label>
          <input
            type="text"
            placeholder="ex: 3/4"
            value={form.attendance}
            onChange={(e) => setForm({ ...form, attendance: e.target.value })}
            className="w-full bg-surface-container rounded-xl px-4 py-2.5 text-sm text-on-surface outline-none focus:ring-2 focus:ring-primary"
          />
        </div>

        <div className="grid grid-cols-3 gap-4">
          <RatingSelect label="Engagement" value={form.engagement} onChange={(v) => setForm({ ...form, engagement: v })} />
          <RatingSelect label="Progression" value={form.progression} onChange={(v) => setForm({ ...form, progression: v })} />
          <RatingSelect label="Attitude" value={form.attitude} onChange={(v) => setForm({ ...form, attitude: v })} />
        </div>

        <div>
          <label className="text-[10px] uppercase tracking-wider text-on-surface-variant block mb-1">Points forts</label>
          <textarea
            value={form.strengths}
            onChange={(e) => setForm({ ...form, strengths: e.target.value })}
            rows={3}
            className="w-full bg-surface-container rounded-xl px-4 py-2.5 text-sm text-on-surface outline-none focus:ring-2 focus:ring-primary resize-none"
          />
        </div>

        <div>
          <label className="text-[10px] uppercase tracking-wider text-on-surface-variant block mb-1">Axes d'amélioration</label>
          <textarea
            value={form.improvements}
            onChange={(e) => setForm({ ...form, improvements: e.target.value })}
            rows={3}
            className="w-full bg-surface-container rounded-xl px-4 py-2.5 text-sm text-on-surface outline-none focus:ring-2 focus:ring-primary resize-none"
          />
        </div>

        <label className="flex items-center gap-2 cursor-pointer">
          <input
            type="checkbox"
            checked={form.visible_to_skater}
            onChange={(e) => setForm({ ...form, visible_to_skater: e.target.checked })}
            className="accent-primary"
          />
          <span className="text-sm text-on-surface">Visible par le patineur/parent</span>
        </label>

        <div className="flex gap-3 pt-2">
          <button onClick={onClose} className="flex-1 py-2.5 rounded-xl text-sm font-bold text-on-surface-variant hover:bg-surface-container transition-colors">
            Annuler
          </button>
          <button
            onClick={() => mutation.mutate()}
            disabled={mutation.isPending}
            className="flex-1 py-2.5 rounded-xl text-sm font-bold bg-primary text-white hover:bg-primary/90 transition-colors disabled:opacity-50"
          >
            {mutation.isPending ? "Enregistrement..." : "Enregistrer"}
          </button>
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Add IncidentFormModal component**

In the same file, add after `ReviewFormModal`:

```tsx
function IncidentFormModal({
  skaterId,
  existing,
  onClose,
}: {
  skaterId: number;
  existing?: TrainingIncident;
  onClose: () => void;
}) {
  const queryClient = useQueryClient();
  const [form, setForm] = useState({
    date: existing?.date ?? new Date().toISOString().split("T")[0],
    incident_type: (existing?.incident_type ?? "other") as "injury" | "behavior" | "other",
    description: existing?.description ?? "",
    visible_to_skater: existing?.visible_to_skater ?? false,
  });

  const mutation = useMutation({
    mutationFn: () =>
      existing
        ? api.training.incidents.update(existing.id, form)
        : api.training.incidents.create({ ...form, skater_id: skaterId }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["training", "incidents"] });
      onClose();
    },
  });

  return (
    <div className="fixed inset-0 bg-scrim/50 z-50 flex items-center justify-center p-4" onClick={onClose}>
      <div
        className="bg-surface rounded-3xl p-6 w-full max-w-lg space-y-4"
        onClick={(e) => e.stopPropagation()}
      >
        <h3 className="font-headline font-bold text-on-surface text-lg">
          {existing ? "Modifier l'incident" : "Signaler un incident"}
        </h3>

        <div>
          <label className="text-[10px] uppercase tracking-wider text-on-surface-variant block mb-1">Date</label>
          <input
            type="date"
            value={form.date}
            onChange={(e) => setForm({ ...form, date: e.target.value })}
            className="w-full bg-surface-container rounded-xl px-4 py-2.5 text-sm text-on-surface outline-none focus:ring-2 focus:ring-primary"
          />
        </div>

        <div>
          <label className="text-[10px] uppercase tracking-wider text-on-surface-variant block mb-1">Type</label>
          <select
            value={form.incident_type}
            onChange={(e) => setForm({ ...form, incident_type: e.target.value as "injury" | "behavior" | "other" })}
            className="w-full bg-surface-container rounded-xl px-4 py-2.5 text-sm text-on-surface outline-none focus:ring-2 focus:ring-primary"
          >
            <option value="injury">Blessure</option>
            <option value="behavior">Comportement</option>
            <option value="other">Autre</option>
          </select>
        </div>

        <div>
          <label className="text-[10px] uppercase tracking-wider text-on-surface-variant block mb-1">Description</label>
          <textarea
            value={form.description}
            onChange={(e) => setForm({ ...form, description: e.target.value })}
            rows={4}
            className="w-full bg-surface-container rounded-xl px-4 py-2.5 text-sm text-on-surface outline-none focus:ring-2 focus:ring-primary resize-none"
          />
        </div>

        <label className="flex items-center gap-2 cursor-pointer">
          <input
            type="checkbox"
            checked={form.visible_to_skater}
            onChange={(e) => setForm({ ...form, visible_to_skater: e.target.checked })}
            className="accent-primary"
          />
          <span className="text-sm text-on-surface">Visible par le patineur/parent</span>
        </label>

        <div className="flex gap-3 pt-2">
          <button onClick={onClose} className="flex-1 py-2.5 rounded-xl text-sm font-bold text-on-surface-variant hover:bg-surface-container transition-colors">
            Annuler
          </button>
          <button
            onClick={() => mutation.mutate()}
            disabled={mutation.isPending}
            className="flex-1 py-2.5 rounded-xl text-sm font-bold bg-primary text-white hover:bg-primary/90 transition-colors disabled:opacity-50"
          >
            {mutation.isPending ? "Enregistrement..." : "Enregistrer"}
          </button>
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 3: Wire modals into SkaterTrainingPage (create + edit)**

In `SkaterTrainingPage`, add state and buttons:

1. Add state at top of component:
```tsx
const [editingReview, setEditingReview] = useState<WeeklyReview | undefined>();
const [showReviewForm, setShowReviewForm] = useState(false);
const [editingIncident, setEditingIncident] = useState<TrainingIncident | undefined>();
const [showIncidentForm, setShowIncidentForm] = useState(false);
```

2. Add "Nouveau retour" button in the reviews tab content (before the review list):
```tsx
<div className="flex justify-end">
  <button
    onClick={() => { setEditingReview(undefined); setShowReviewForm(true); }}
    className="flex items-center gap-2 bg-primary text-white px-4 py-2 rounded-xl text-sm font-bold hover:bg-primary/90 transition-colors"
  >
    <span className="material-symbols-outlined text-lg">add</span>
    Nouveau retour
  </button>
</div>
```

3. Add an edit button on each `ReviewCard` that triggers:
```tsx
onClick={() => { setEditingReview(review); setShowReviewForm(true); }}
```

4. Same pattern for incidents tab with "Nouvel incident" button and edit button on each `IncidentCard`.

5. Add modals at end of component (before closing `</div>`):
```tsx
{showReviewForm && <ReviewFormModal skaterId={skaterId} existing={editingReview} onClose={() => setShowReviewForm(false)} />}
{showIncidentForm && <IncidentFormModal skaterId={skaterId} existing={editingIncident} onClose={() => setShowIncidentForm(false)} />}
```

- [ ] **Step 4: Commit**

```bash
git add frontend/src/pages/SkaterTrainingPage.tsx
git commit -m "feat: add review and incident creation modals"
```

---

### Task 10: Frontend — Evolution charts (longitudinal view)

**Files:**
- Create: `frontend/src/components/TrainingEvolutionChart.tsx`
- Modify: `frontend/src/pages/SkaterTrainingPage.tsx` (wire chart into evolution tab)

- [ ] **Step 1: Create TrainingEvolutionChart component**

Create `frontend/src/components/TrainingEvolutionChart.tsx`:

```tsx
import {
  LineChart, Line, XAxis, YAxis, Tooltip, Legend, ResponsiveContainer,
  ReferenceDot,
} from "recharts";
import { WeeklyReview, TrainingIncident } from "../api/client";

const INCIDENT_COLORS: Record<string, string> = {
  injury: "#ba1a1a",
  behavior: "#ea580c",
  other: "#6b7280",
};

const INCIDENT_LABELS: Record<string, string> = {
  injury: "Blessure",
  behavior: "Comportement",
  other: "Autre",
};

interface Props {
  reviews: WeeklyReview[];
  incidents: TrainingIncident[];
}

export default function TrainingEvolutionChart({ reviews, incidents }: Props) {
  // Sort reviews by date ascending
  const sorted = [...reviews].sort((a, b) => a.week_start.localeCompare(b.week_start));

  const data = sorted.map((r) => ({
    week: new Date(r.week_start).toLocaleDateString("fr-FR", { day: "2-digit", month: "short" }),
    week_start: r.week_start,
    engagement: r.engagement,
    progression: r.progression,
    attitude: r.attitude,
    attendance: r.attendance,
  }));

  // Map incidents to their nearest week for overlay
  const incidentMarkers = incidents.map((i) => {
    const closest = sorted.reduce((prev, curr) =>
      Math.abs(new Date(curr.week_start).getTime() - new Date(i.date).getTime()) <
      Math.abs(new Date(prev.week_start).getTime() - new Date(i.date).getTime())
        ? curr
        : prev
    , sorted[0]);
    return {
      week: closest
        ? new Date(closest.week_start).toLocaleDateString("fr-FR", { day: "2-digit", month: "short" })
        : "",
      incident: i,
    };
  });

  if (data.length === 0) {
    return (
      <p className="text-sm text-on-surface-variant text-center py-10">
        Pas encore assez de données pour afficher l'évolution.
      </p>
    );
  }

  return (
    <div className="space-y-6">
      {/* Main chart */}
      <div>
        <h4 className="font-headline font-bold text-on-surface text-sm mb-3">Évolution des notes</h4>
        <ResponsiveContainer width="100%" height={280}>
          <LineChart data={data}>
            <XAxis dataKey="week" tick={{ fontSize: 11 }} />
            <YAxis domain={[0, 5]} ticks={[1, 2, 3, 4, 5]} tick={{ fontSize: 11 }} />
            <Tooltip
              contentStyle={{ borderRadius: "12px", border: "none", boxShadow: "0 4px 12px rgba(0,0,0,0.1)" }}
            />
            <Legend wrapperStyle={{ fontSize: "12px" }} />
            <Line type="monotone" dataKey="engagement" name="Engagement" stroke="#2e6385" strokeWidth={2} dot={{ r: 3 }} />
            <Line type="monotone" dataKey="progression" name="Progression" stroke="#059669" strokeWidth={2} dot={{ r: 3 }} />
            <Line type="monotone" dataKey="attitude" name="Attitude" stroke="#7c3aed" strokeWidth={2} dot={{ r: 3 }} />
            {/* Incident markers */}
            {incidentMarkers.map((m, idx) => (
              <ReferenceDot
                key={idx}
                x={m.week}
                y={0.3}
                r={6}
                fill={INCIDENT_COLORS[m.incident.incident_type] ?? "#6b7280"}
                stroke="white"
                strokeWidth={2}
              />
            ))}
          </LineChart>
        </ResponsiveContainer>
      </div>

      {/* Attendance row */}
      <div>
        <h4 className="font-headline font-bold text-on-surface text-sm mb-2">Assiduité</h4>
        <div className="flex gap-2 flex-wrap">
          {data.map((d, i) => (
            <div key={i} className="bg-surface-container-low rounded-xl px-3 py-2 text-center min-w-[60px]">
              <span className="font-mono text-sm font-bold text-on-surface">{d.attendance || "—"}</span>
              <p className="text-[9px] text-on-surface-variant mt-0.5">{d.week}</p>
            </div>
          ))}
        </div>
      </div>

      {/* Incident legend */}
      {incidents.length > 0 && (
        <div>
          <h4 className="font-headline font-bold text-on-surface text-sm mb-2">Incidents</h4>
          <div className="space-y-1">
            {incidents.map((i) => (
              <div key={i.id} className="flex items-center gap-2 text-sm">
                <div
                  className="w-3 h-3 rounded-full"
                  style={{ backgroundColor: INCIDENT_COLORS[i.incident_type] }}
                />
                <span className="text-on-surface-variant">
                  {new Date(i.date).toLocaleDateString("fr-FR")} —{" "}
                  {INCIDENT_LABELS[i.incident_type]}: {i.description}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Wire chart into SkaterTrainingPage evolution tab**

In `frontend/src/pages/SkaterTrainingPage.tsx`:

1. Add import: `import TrainingEvolutionChart from "../components/TrainingEvolutionChart";`

2. Replace the evolution tab placeholder with:
```tsx
{activeTab === "evolution" && (
  <TrainingEvolutionChart
    reviews={reviews ?? []}
    incidents={incidents ?? []}
  />
)}
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/TrainingEvolutionChart.tsx frontend/src/pages/SkaterTrainingPage.tsx
git commit -m "feat: add longitudinal evolution chart with incident markers"
```

---

### Task 11: Frontend — Coach navigation and skater training tab

**Files:**
- Modify: `frontend/src/App.tsx` (coach-specific nav, skater "Entraînement" tab)

- [ ] **Step 1: Add coach navigation**

In `frontend/src/App.tsx`, update the nav rendering logic. Currently the sidebar shows `navLinks` for non-skater roles. Update to show training-focused nav for coach:

```tsx
{user?.role === "skater" ? (
  <SkaterNav closeSidebar={closeSidebar} />
) : user?.role === "coach" ? (
  <nav className="flex-1 py-2">
    {[
      { to: "/entrainement", label: "ENTRAÎNEMENT", icon: "fitness_center", end: true },
      { to: "/patineurs", label: "PATINEURS", icon: "people", end: false },
      { to: "/competitions", label: "COMPÉTITIONS", icon: "emoji_events", end: false },
    ].map(({ to, label, icon, end }) => (
      <NavLink
        key={to}
        to={to}
        end={end}
        onClick={closeSidebar}
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
  </nav>
) : (
  <nav className="flex-1 py-2">
    {navLinks.map(/* ... existing code ... */)}
  </nav>
)}
```

- [ ] **Step 2: Add coach routes**

In the routes section, add coach-specific routes. The coach role should share the admin/reader routes for competitions (read-only) plus training routes:

```tsx
{user?.role === "coach" ? (
  <>
    <Route path="/entrainement" element={<TrainingPage />} />
    <Route path="/entrainement/patineurs/:id" element={<SkaterTrainingPage />} />
    <Route path="/patineurs" element={<SkaterBrowserPage />} />
    <Route path="/patineurs/:id/analyse" element={<SkaterAnalyticsPage />} />
    <Route path="/competitions" element={<CompetitionsPage />} />
    <Route path="/competitions/:id" element={<CompetitionPage />} />
    <Route path="/profil" element={<ProfilePage />} />
    <Route path="*" element={<Navigate to="/entrainement" replace />} />
  </>
) : user?.role === "skater" ? (
  /* existing skater routes */
) : (
  /* existing admin/reader routes */
)}
```

For admin, also add the training routes (admin can access everything):

Add to the admin/reader route block:
```tsx
<Route path="/entrainement" element={<TrainingPage />} />
<Route path="/entrainement/patineurs/:id" element={<SkaterTrainingPage />} />
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/App.tsx
git commit -m "feat: add coach-specific navigation and routing"
```

---

### Task 12: Frontend — Skater role training tab

**Files:**
- Modify: `frontend/src/pages/SkaterAnalyticsPage.tsx` (add "Entraînement" tab for skater role)
- Modify: `frontend/src/App.tsx` (add training route for skater role)

- [ ] **Step 1: Add training tab to skater analytics page**

In `frontend/src/pages/SkaterAnalyticsPage.tsx`, add an "Entraînement" tab visible when `user.role === "skater"`. This tab shows:
- A timeline of visible reviews and incidents (using the `/api/training/timeline` endpoint)
- A `TrainingEvolutionChart` component (reused from Task 10) filtered to visible data only

The tab should be added to the existing tab bar in the skater analytics page. Use the same `TimelineEntry` type from the API client. Render `ReviewCard` and `IncidentCard` components (extracted or imported from `SkaterTrainingPage.tsx` — if they are not already extracted, extract them to `frontend/src/components/TrainingCards.tsx` for reuse).

- [ ] **Step 2: Add skater training route**

In `frontend/src/App.tsx`, in the skater routes block, add the training route so skaters can navigate to their patineurs' training data. The `SkaterAnalyticsPage` already handles this via the new tab, so no new page is needed.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/pages/SkaterAnalyticsPage.tsx frontend/src/App.tsx
git commit -m "feat: add training tab for skater role on analytics page"
```

---

### Task 13: Run full test suite and verify

**Files:** None (verification only)

- [ ] **Step 1: Run all backend tests**

Run: `cd backend && uv run pytest -v`
Expected: All tests PASS

- [ ] **Step 2: Verify frontend builds**

Run: `cd frontend && PATH="/opt/homebrew/bin:$PATH" npm run build`
Expected: Build succeeds with no TypeScript errors

- [ ] **Step 3: Final commit if any fixes needed**

If fixes were needed, commit them:
```bash
git commit -m "fix: resolve issues found during final verification"
```
