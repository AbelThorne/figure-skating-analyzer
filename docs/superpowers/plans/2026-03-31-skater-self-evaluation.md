# Skater Self-Evaluation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Allow skaters to log daily mood ratings, write self-evaluations with per-element ratings, and register their technical programs (SP/FS). Coaches see anonymous mood aggregates and shared evaluations.

**Architecture:** Three new SQLAlchemy models (`SkaterProgram`, `TrainingMood`, `SelfEvaluation`) added to `backend/app/models/`. A new route file `backend/app/routes/self_eval.py` handles all API endpoints under `/api/training/` (programs, moods, self-evaluations). Frontend adds types + API functions to `client.ts`, a `MoodInput` component, a `SelfEvalModal` component, a `ProgramEditor` component, a `TrainingJournal` section, and a `MoodAggregateWidget` for the coach view.

**Tech Stack:** Python/Litestar/SQLAlchemy (backend), React/TypeScript/TanStack Query/Tailwind (frontend), pytest-asyncio (tests)

---

## File Structure

### Backend — New Files

| File | Responsibility |
|------|---------------|
| `backend/app/models/skater_program.py` | `SkaterProgram` model — registered SP/FS element lists |
| `backend/app/models/training_mood.py` | `TrainingMood` model — daily 1-5 mood rating |
| `backend/app/models/self_evaluation.py` | `SelfEvaluation` model — daily eval with notes + element ratings |
| `backend/app/routes/self_eval.py` | All self-eval routes (programs, moods, self-evaluations, weekly-summary) |
| `backend/tests/test_self_eval.py` | Route + permission tests for all self-eval endpoints |

### Backend — Modified Files

| File | Change |
|------|--------|
| `backend/app/models/__init__.py` | Register 3 new models |
| `backend/app/main.py` | Register `self_eval_router` |
| `backend/app/routes/training.py` | Add shared self-evaluations to timeline |

### Frontend — New Files

| File | Responsibility |
|------|---------------|
| `frontend/src/components/MoodInput.tsx` | 5-emoji mood picker, one-tap save |
| `frontend/src/components/SelfEvalModal.tsx` | Modal form: date, mood, notes, element ratings, share toggle |
| `frontend/src/components/ProgramEditor.tsx` | SP/FS element list editor with add/remove |
| `frontend/src/components/TrainingJournal.tsx` | Mood timeline strip + past evaluations list |
| `frontend/src/components/MoodAggregateWidget.tsx` | Coach widget: average, distribution bar chart, trend |

### Frontend — Modified Files

| File | Change |
|------|--------|
| `frontend/src/api/client.ts` | Add types + API functions for programs, moods, self-evaluations |
| `frontend/src/pages/SkaterAnalyticsPage.tsx` | Add MoodInput, SelfEvalModal, ProgramEditor, TrainingJournal sections |
| `frontend/src/pages/TrainingPage.tsx` | Add MoodAggregateWidget for coach/admin |
| `frontend/src/pages/SkaterTrainingPage.tsx` | Show shared self-evaluations in timeline |

---

## Task 1: SkaterProgram Model

**Files:**
- Create: `backend/app/models/skater_program.py`
- Modify: `backend/app/models/__init__.py`

- [ ] **Step 1: Create the SkaterProgram model**

```python
# backend/app/models/skater_program.py
from datetime import datetime, timezone

from sqlalchemy import DateTime, Integer, JSON, String, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class SkaterProgram(Base):
    __tablename__ = "skater_programs"
    __table_args__ = (
        UniqueConstraint("skater_id", "segment", name="uq_program_skater_segment"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    skater_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("skaters.id", ondelete="CASCADE"), nullable=False
    )
    segment: Mapped[str] = mapped_column(String(4), nullable=False)  # "SP" or "FS"
    elements: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, onupdate=_utcnow)
```

- [ ] **Step 2: Register the model in `__init__.py`**

Add to `backend/app/models/__init__.py`:

```python
from app.models.skater_program import SkaterProgram
```

And add `"SkaterProgram"` to `__all__`.

- [ ] **Step 3: Verify model loads**

Run: `cd backend && PATH="/opt/homebrew/bin:$PATH" uv run python -c "from app.models.skater_program import SkaterProgram; print(SkaterProgram.__tablename__)"`

Expected: `skater_programs`

- [ ] **Step 4: Commit**

```bash
git add backend/app/models/skater_program.py backend/app/models/__init__.py
git commit -m "feat: add SkaterProgram model for registered SP/FS programs"
```

---

## Task 2: TrainingMood Model

**Files:**
- Create: `backend/app/models/training_mood.py`
- Modify: `backend/app/models/__init__.py`

- [ ] **Step 1: Create the TrainingMood model**

```python
# backend/app/models/training_mood.py
from datetime import date, datetime, timezone

from sqlalchemy import Date, DateTime, Integer, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class TrainingMood(Base):
    __tablename__ = "training_moods"
    __table_args__ = (
        UniqueConstraint("skater_id", "date", name="uq_mood_skater_date"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    skater_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("skaters.id", ondelete="CASCADE"), nullable=False
    )
    date: Mapped[date] = mapped_column(Date, nullable=False)
    rating: Mapped[int] = mapped_column(Integer, nullable=False)  # 1-5
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
```

- [ ] **Step 2: Register the model in `__init__.py`**

Add to `backend/app/models/__init__.py`:

```python
from app.models.training_mood import TrainingMood
```

And add `"TrainingMood"` to `__all__`.

- [ ] **Step 3: Commit**

```bash
git add backend/app/models/training_mood.py backend/app/models/__init__.py
git commit -m "feat: add TrainingMood model for daily mood ratings"
```

---

## Task 3: SelfEvaluation Model

**Files:**
- Create: `backend/app/models/self_evaluation.py`
- Modify: `backend/app/models/__init__.py`

- [ ] **Step 1: Create the SelfEvaluation model**

```python
# backend/app/models/self_evaluation.py
from datetime import date, datetime, timezone
from typing import Optional

from sqlalchemy import Boolean, Date, DateTime, Integer, JSON, Text, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class SelfEvaluation(Base):
    __tablename__ = "self_evaluations"
    __table_args__ = (
        UniqueConstraint("skater_id", "date", name="uq_self_eval_skater_date"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    skater_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("skaters.id", ondelete="CASCADE"), nullable=False
    )
    mood_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("training_moods.id", ondelete="SET NULL"), nullable=True
    )
    date: Mapped[date] = mapped_column(Date, nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    element_ratings: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    shared: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, onupdate=_utcnow)
```

- [ ] **Step 2: Register the model in `__init__.py`**

Add to `backend/app/models/__init__.py`:

```python
from app.models.self_evaluation import SelfEvaluation
```

And add `"SelfEvaluation"` to `__all__`.

- [ ] **Step 3: Commit**

```bash
git add backend/app/models/self_evaluation.py backend/app/models/__init__.py
git commit -m "feat: add SelfEvaluation model for skater self-assessments"
```

---

## Task 4: Self-Eval Routes — Programs

**Files:**
- Create: `backend/app/routes/self_eval.py`

- [ ] **Step 1: Create the route file with program endpoints**

```python
# backend/app/routes/self_eval.py
from __future__ import annotations

from datetime import date
from typing import Optional

from litestar import Router, get, post, put, delete, Request
from litestar.di import Provide
from litestar.exceptions import NotFoundException, PermissionDeniedException
from litestar.status_codes import HTTP_201_CREATED, HTTP_204_NO_CONTENT
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.models.skater_program import SkaterProgram
from app.models.training_mood import TrainingMood
from app.models.self_evaluation import SelfEvaluation
from app.models.user_skater import UserSkater


async def _check_skater_own_access(request: Request, skater_id: int, session: AsyncSession) -> None:
    """Skater role: verify they own this skater_id. Coach/admin: pass through."""
    state = request.scope.get("state", {})
    role = state.get("user_role")
    if role == "reader":
        raise PermissionDeniedException("No access to training data")
    if role == "skater":
        result = await session.execute(
            select(UserSkater).where(
                UserSkater.user_id == state["user_id"],
                UserSkater.skater_id == skater_id,
            )
        )
        if not result.scalar_one_or_none():
            raise PermissionDeniedException("You do not have access to this skater")


def _program_to_dict(p: SkaterProgram) -> dict:
    return {
        "id": p.id,
        "skater_id": p.skater_id,
        "segment": p.segment,
        "elements": p.elements,
        "created_at": p.created_at.isoformat() if p.created_at else None,
        "updated_at": p.updated_at.isoformat() if p.updated_at else None,
    }


def _mood_to_dict(m: TrainingMood) -> dict:
    return {
        "id": m.id,
        "skater_id": m.skater_id,
        "date": m.date.isoformat(),
        "rating": m.rating,
        "created_at": m.created_at.isoformat() if m.created_at else None,
    }


def _eval_to_dict(e: SelfEvaluation) -> dict:
    return {
        "id": e.id,
        "skater_id": e.skater_id,
        "mood_id": e.mood_id,
        "date": e.date.isoformat(),
        "notes": e.notes,
        "element_ratings": e.element_ratings,
        "shared": e.shared,
        "created_at": e.created_at.isoformat() if e.created_at else None,
        "updated_at": e.updated_at.isoformat() if e.updated_at else None,
    }


# ── Programs ─────────────────────────────────────────────────────────────────


@get("/programs")
async def list_programs(
    request: Request, session: AsyncSession, skater_id: int = 0,
) -> list[dict]:
    await _check_skater_own_access(request, skater_id, session)
    stmt = select(SkaterProgram).where(SkaterProgram.skater_id == skater_id)
    result = await session.execute(stmt)
    return [_program_to_dict(p) for p in result.scalars().all()]


@put("/programs")
async def upsert_program(request: Request, session: AsyncSession, data: dict) -> dict:
    skater_id = data["skater_id"]
    segment = data["segment"]
    await _check_skater_own_access(request, skater_id, session)

    if segment not in ("SP", "FS"):
        raise PermissionDeniedException("Segment must be SP or FS")

    existing = (await session.execute(
        select(SkaterProgram).where(
            SkaterProgram.skater_id == skater_id,
            SkaterProgram.segment == segment,
        )
    )).scalar_one_or_none()

    if existing:
        existing.elements = data["elements"]
        await session.commit()
        await session.refresh(existing)
        return _program_to_dict(existing)

    program = SkaterProgram(
        skater_id=skater_id,
        segment=segment,
        elements=data["elements"],
    )
    session.add(program)
    await session.commit()
    await session.refresh(program)
    return _program_to_dict(program)


@delete("/programs/{program_id:int}", status_code=HTTP_204_NO_CONTENT)
async def delete_program(program_id: int, request: Request, session: AsyncSession) -> None:
    program = await session.get(SkaterProgram, program_id)
    if not program:
        raise NotFoundException("Program not found")
    await _check_skater_own_access(request, program.skater_id, session)
    await session.delete(program)
    await session.commit()


# ── Moods ─────────────────────────────────────────────────────────────────


@get("/moods")
async def list_moods(
    request: Request,
    session: AsyncSession,
    skater_id: int = 0,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
) -> list[dict]:
    await _check_skater_own_access(request, skater_id, session)
    stmt = select(TrainingMood).where(
        TrainingMood.skater_id == skater_id
    ).order_by(TrainingMood.date.desc())
    if from_date:
        stmt = stmt.where(TrainingMood.date >= date.fromisoformat(from_date))
    if to_date:
        stmt = stmt.where(TrainingMood.date <= date.fromisoformat(to_date))
    result = await session.execute(stmt)
    return [_mood_to_dict(m) for m in result.scalars().all()]


@post("/moods", status_code=HTTP_201_CREATED)
async def create_mood(request: Request, session: AsyncSession, data: dict) -> dict:
    skater_id = data["skater_id"]
    await _check_skater_own_access(request, skater_id, session)

    state = request.scope.get("state", {})
    if state.get("user_role") not in ("skater",):
        raise PermissionDeniedException("Only skaters can create moods")

    mood_date = date.fromisoformat(data["date"]) if "date" in data else date.today()
    rating = data["rating"]
    if not (1 <= rating <= 5):
        raise PermissionDeniedException("Rating must be between 1 and 5")

    # Check uniqueness
    existing = (await session.execute(
        select(TrainingMood).where(
            TrainingMood.skater_id == skater_id,
            TrainingMood.date == mood_date,
        )
    )).scalar_one_or_none()
    if existing:
        from litestar.exceptions import ClientException
        raise ClientException(status_code=409, detail="Mood already exists for this date")

    mood = TrainingMood(skater_id=skater_id, date=mood_date, rating=rating)
    session.add(mood)
    await session.commit()
    await session.refresh(mood)
    return _mood_to_dict(mood)


@put("/moods/{mood_id:int}")
async def update_mood(mood_id: int, request: Request, session: AsyncSession, data: dict) -> dict:
    mood = await session.get(TrainingMood, mood_id)
    if not mood:
        raise NotFoundException("Mood not found")
    await _check_skater_own_access(request, mood.skater_id, session)

    state = request.scope.get("state", {})
    if state.get("user_role") not in ("skater",):
        raise PermissionDeniedException("Only skaters can update moods")

    rating = data["rating"]
    if not (1 <= rating <= 5):
        raise PermissionDeniedException("Rating must be between 1 and 5")

    mood.rating = rating
    await session.commit()
    await session.refresh(mood)
    return _mood_to_dict(mood)


@get("/moods/weekly-summary")
async def mood_weekly_summary(
    request: Request,
    session: AsyncSession,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
) -> dict:
    state = request.scope.get("state", {})
    role = state.get("user_role")
    if role not in ("coach", "admin"):
        raise PermissionDeniedException("Only coaches and admins can view mood summary")

    stmt = select(TrainingMood)
    if from_date:
        stmt = stmt.where(TrainingMood.date >= date.fromisoformat(from_date))
    if to_date:
        stmt = stmt.where(TrainingMood.date <= date.fromisoformat(to_date))
    result = await session.execute(stmt)
    moods = result.scalars().all()

    if not moods:
        return {"average": None, "count": 0, "distribution": [0, 0, 0, 0, 0]}

    ratings = [m.rating for m in moods]
    distribution = [0, 0, 0, 0, 0]
    for r in ratings:
        distribution[r - 1] += 1

    return {
        "average": round(sum(ratings) / len(ratings), 1),
        "count": len(ratings),
        "distribution": distribution,
    }


# ── Self-Evaluations ─────────────────────────────────────────────────────


@get("/self-evaluations")
async def list_self_evaluations(
    request: Request,
    session: AsyncSession,
    skater_id: int = 0,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
) -> list[dict]:
    state = request.scope.get("state", {})
    role = state.get("user_role")

    if role == "reader":
        raise PermissionDeniedException("No access to training data")

    stmt = select(SelfEvaluation).where(
        SelfEvaluation.skater_id == skater_id
    ).order_by(SelfEvaluation.date.desc())

    if role == "skater":
        await _check_skater_own_access(request, skater_id, session)
        # Skater sees all their own evaluations (private + shared)
    elif role in ("coach", "admin"):
        # Coach/admin sees only shared evaluations
        stmt = stmt.where(SelfEvaluation.shared == True)  # noqa: E712

    if from_date:
        stmt = stmt.where(SelfEvaluation.date >= date.fromisoformat(from_date))
    if to_date:
        stmt = stmt.where(SelfEvaluation.date <= date.fromisoformat(to_date))

    result = await session.execute(stmt)
    return [_eval_to_dict(e) for e in result.scalars().all()]


@post("/self-evaluations", status_code=HTTP_201_CREATED)
async def create_self_evaluation(request: Request, session: AsyncSession, data: dict) -> dict:
    skater_id = data["skater_id"]
    await _check_skater_own_access(request, skater_id, session)

    state = request.scope.get("state", {})
    if state.get("user_role") not in ("skater",):
        raise PermissionDeniedException("Only skaters can create self-evaluations")

    eval_date = date.fromisoformat(data["date"]) if "date" in data else date.today()

    # Check uniqueness
    existing = (await session.execute(
        select(SelfEvaluation).where(
            SelfEvaluation.skater_id == skater_id,
            SelfEvaluation.date == eval_date,
        )
    )).scalar_one_or_none()
    if existing:
        from litestar.exceptions import ClientException
        raise ClientException(status_code=409, detail="Self-evaluation already exists for this date")

    # Validate element_ratings if provided
    element_ratings = data.get("element_ratings")
    if element_ratings:
        for er in element_ratings:
            if not (1 <= er.get("rating", 0) <= 5):
                raise PermissionDeniedException("Element ratings must be between 1 and 5")

    # Link to same-day mood if exists
    mood_id = None
    mood = (await session.execute(
        select(TrainingMood).where(
            TrainingMood.skater_id == skater_id,
            TrainingMood.date == eval_date,
        )
    )).scalar_one_or_none()
    if mood:
        mood_id = mood.id

    evaluation = SelfEvaluation(
        skater_id=skater_id,
        mood_id=mood_id,
        date=eval_date,
        notes=data.get("notes"),
        element_ratings=element_ratings,
        shared=data.get("shared", False),
    )
    session.add(evaluation)
    await session.commit()
    await session.refresh(evaluation)
    return _eval_to_dict(evaluation)


@put("/self-evaluations/{eval_id:int}")
async def update_self_evaluation(
    eval_id: int, request: Request, session: AsyncSession, data: dict,
) -> dict:
    evaluation = await session.get(SelfEvaluation, eval_id)
    if not evaluation:
        raise NotFoundException("Self-evaluation not found")
    await _check_skater_own_access(request, evaluation.skater_id, session)

    state = request.scope.get("state", {})
    if state.get("user_role") not in ("skater",):
        raise PermissionDeniedException("Only skaters can update self-evaluations")

    for field in ("notes", "element_ratings", "shared"):
        if field in data:
            setattr(evaluation, field, data[field])

    await session.commit()
    await session.refresh(evaluation)
    return _eval_to_dict(evaluation)


@delete("/self-evaluations/{eval_id:int}", status_code=HTTP_204_NO_CONTENT)
async def delete_self_evaluation(
    eval_id: int, request: Request, session: AsyncSession,
) -> None:
    evaluation = await session.get(SelfEvaluation, eval_id)
    if not evaluation:
        raise NotFoundException("Self-evaluation not found")
    await _check_skater_own_access(request, evaluation.skater_id, session)

    state = request.scope.get("state", {})
    if state.get("user_role") not in ("skater",):
        raise PermissionDeniedException("Only skaters can delete self-evaluations")

    await session.delete(evaluation)
    await session.commit()


# ── Router ────────────────────────────────────────────────────────────────

router = Router(
    path="/api/training",
    route_handlers=[
        list_programs, upsert_program, delete_program,
        list_moods, create_mood, update_mood, mood_weekly_summary,
        list_self_evaluations, create_self_evaluation,
        update_self_evaluation, delete_self_evaluation,
    ],
    dependencies={"session": Provide(get_session)},
)
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/routes/self_eval.py
git commit -m "feat: add self-eval routes (programs, moods, self-evaluations)"
```

---

## Task 5: Register Self-Eval Router in Main

**Files:**
- Modify: `backend/app/main.py`

- [ ] **Step 1: Add import and register router**

Add after line 30 (`from app.routes.training import router as training_router`):

```python
from app.routes.self_eval import router as self_eval_router
```

Add `self_eval_router` to the `route_handlers` list in the `Litestar` constructor (after `training_router`).

- [ ] **Step 2: Commit**

```bash
git add backend/app/main.py
git commit -m "feat: register self-eval router in app"
```

---

## Task 6: Backend Tests — Programs

**Files:**
- Create: `backend/tests/test_self_eval.py`

- [ ] **Step 1: Write program CRUD tests**

```python
# backend/tests/test_self_eval.py
import pytest

from app.models.skater import Skater


@pytest.fixture
async def skater(db_session):
    """Create a standalone skater for self-eval tests."""
    s = Skater(first_name="Lea", last_name="Petit", club="TestClub")
    db_session.add(s)
    await db_session.commit()
    await db_session.refresh(s)
    return s


# ── Programs ─────────────────────────────────────────────────────────────────


async def test_upsert_program_skater(client, skater_token, skater_user_with_skater):
    _, _, skater = skater_user_with_skater
    resp = await client.put(
        "/api/training/programs",
        json={"skater_id": skater.id, "segment": "SP", "elements": ["2A", "3Lz", "CCoSp4"]},
        headers={"Authorization": f"Bearer {skater_token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["segment"] == "SP"
    assert data["elements"] == ["2A", "3Lz", "CCoSp4"]


async def test_upsert_program_updates_existing(client, skater_token, skater_user_with_skater):
    _, _, skater = skater_user_with_skater
    # Create
    await client.put(
        "/api/training/programs",
        json={"skater_id": skater.id, "segment": "SP", "elements": ["2A"]},
        headers={"Authorization": f"Bearer {skater_token}"},
    )
    # Update
    resp = await client.put(
        "/api/training/programs",
        json={"skater_id": skater.id, "segment": "SP", "elements": ["2A", "3F"]},
        headers={"Authorization": f"Bearer {skater_token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["elements"] == ["2A", "3F"]


async def test_list_programs(client, skater_token, skater_user_with_skater):
    _, _, skater = skater_user_with_skater
    await client.put(
        "/api/training/programs",
        json={"skater_id": skater.id, "segment": "SP", "elements": ["2A"]},
        headers={"Authorization": f"Bearer {skater_token}"},
    )
    resp = await client.get(
        f"/api/training/programs?skater_id={skater.id}",
        headers={"Authorization": f"Bearer {skater_token}"},
    )
    assert resp.status_code == 200
    assert len(resp.json()) == 1


async def test_delete_program(client, skater_token, skater_user_with_skater):
    _, _, skater = skater_user_with_skater
    create_resp = await client.put(
        "/api/training/programs",
        json={"skater_id": skater.id, "segment": "FS", "elements": ["3Lz"]},
        headers={"Authorization": f"Bearer {skater_token}"},
    )
    program_id = create_resp.json()["id"]
    resp = await client.delete(
        f"/api/training/programs/{program_id}",
        headers={"Authorization": f"Bearer {skater_token}"},
    )
    assert resp.status_code == 204


async def test_program_invalid_segment(client, skater_token, skater_user_with_skater):
    _, _, skater = skater_user_with_skater
    resp = await client.put(
        "/api/training/programs",
        json={"skater_id": skater.id, "segment": "XY", "elements": []},
        headers={"Authorization": f"Bearer {skater_token}"},
    )
    assert resp.status_code == 403


async def test_reader_no_access_programs(client, reader_token, skater_user_with_skater):
    _, _, skater = skater_user_with_skater
    resp = await client.get(
        f"/api/training/programs?skater_id={skater.id}",
        headers={"Authorization": f"Bearer {reader_token}"},
    )
    assert resp.status_code == 403


async def test_coach_can_read_programs(client, coach_token, skater_user_with_skater, skater_token):
    _, _, skater = skater_user_with_skater
    # Skater creates program
    await client.put(
        "/api/training/programs",
        json={"skater_id": skater.id, "segment": "SP", "elements": ["2A"]},
        headers={"Authorization": f"Bearer {skater_token}"},
    )
    # Coach reads
    resp = await client.get(
        f"/api/training/programs?skater_id={skater.id}",
        headers={"Authorization": f"Bearer {coach_token}"},
    )
    assert resp.status_code == 200
    assert len(resp.json()) == 1


# ── Moods ─────────────────────────────────────────────────────────────────


async def test_create_mood(client, skater_token, skater_user_with_skater):
    _, _, skater = skater_user_with_skater
    resp = await client.post(
        "/api/training/moods",
        json={"skater_id": skater.id, "date": "2026-03-31", "rating": 4},
        headers={"Authorization": f"Bearer {skater_token}"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["rating"] == 4
    assert data["date"] == "2026-03-31"


async def test_create_mood_duplicate_409(client, skater_token, skater_user_with_skater):
    _, _, skater = skater_user_with_skater
    await client.post(
        "/api/training/moods",
        json={"skater_id": skater.id, "date": "2026-03-30", "rating": 3},
        headers={"Authorization": f"Bearer {skater_token}"},
    )
    resp = await client.post(
        "/api/training/moods",
        json={"skater_id": skater.id, "date": "2026-03-30", "rating": 5},
        headers={"Authorization": f"Bearer {skater_token}"},
    )
    assert resp.status_code == 409


async def test_update_mood(client, skater_token, skater_user_with_skater):
    _, _, skater = skater_user_with_skater
    create_resp = await client.post(
        "/api/training/moods",
        json={"skater_id": skater.id, "date": "2026-03-29", "rating": 2},
        headers={"Authorization": f"Bearer {skater_token}"},
    )
    mood_id = create_resp.json()["id"]
    resp = await client.put(
        f"/api/training/moods/{mood_id}",
        json={"rating": 5},
        headers={"Authorization": f"Bearer {skater_token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["rating"] == 5


async def test_mood_rating_out_of_range(client, skater_token, skater_user_with_skater):
    _, _, skater = skater_user_with_skater
    resp = await client.post(
        "/api/training/moods",
        json={"skater_id": skater.id, "date": "2026-03-28", "rating": 6},
        headers={"Authorization": f"Bearer {skater_token}"},
    )
    assert resp.status_code == 403


async def test_list_moods(client, skater_token, skater_user_with_skater):
    _, _, skater = skater_user_with_skater
    await client.post(
        "/api/training/moods",
        json={"skater_id": skater.id, "date": "2026-03-25", "rating": 4},
        headers={"Authorization": f"Bearer {skater_token}"},
    )
    await client.post(
        "/api/training/moods",
        json={"skater_id": skater.id, "date": "2026-03-26", "rating": 3},
        headers={"Authorization": f"Bearer {skater_token}"},
    )
    resp = await client.get(
        f"/api/training/moods?skater_id={skater.id}",
        headers={"Authorization": f"Bearer {skater_token}"},
    )
    assert resp.status_code == 200
    assert len(resp.json()) == 2


async def test_coach_can_read_moods(client, coach_token, skater_token, skater_user_with_skater):
    _, _, skater = skater_user_with_skater
    await client.post(
        "/api/training/moods",
        json={"skater_id": skater.id, "date": "2026-03-24", "rating": 4},
        headers={"Authorization": f"Bearer {skater_token}"},
    )
    resp = await client.get(
        f"/api/training/moods?skater_id={skater.id}",
        headers={"Authorization": f"Bearer {coach_token}"},
    )
    assert resp.status_code == 200
    assert len(resp.json()) == 1


async def test_coach_cannot_create_mood(client, coach_token, skater_user_with_skater):
    _, _, skater = skater_user_with_skater
    resp = await client.post(
        "/api/training/moods",
        json={"skater_id": skater.id, "date": "2026-03-23", "rating": 3},
        headers={"Authorization": f"Bearer {coach_token}"},
    )
    assert resp.status_code == 403


async def test_reader_no_access_moods(client, reader_token, skater_user_with_skater):
    _, _, skater = skater_user_with_skater
    resp = await client.get(
        f"/api/training/moods?skater_id={skater.id}",
        headers={"Authorization": f"Bearer {reader_token}"},
    )
    assert resp.status_code == 403


async def test_weekly_summary(client, coach_token, skater_token, skater_user_with_skater):
    _, _, skater = skater_user_with_skater
    # Create some moods
    for day, rating in [("2026-03-24", 4), ("2026-03-25", 5), ("2026-03-26", 3)]:
        await client.post(
            "/api/training/moods",
            json={"skater_id": skater.id, "date": day, "rating": rating},
            headers={"Authorization": f"Bearer {skater_token}"},
        )
    resp = await client.get(
        "/api/training/moods/weekly-summary?from_date=2026-03-24&to_date=2026-03-26",
        headers={"Authorization": f"Bearer {coach_token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["average"] == 4.0
    assert data["count"] == 3
    assert data["distribution"] == [0, 0, 1, 1, 1]


async def test_weekly_summary_empty(client, coach_token):
    resp = await client.get(
        "/api/training/moods/weekly-summary?from_date=2099-01-01&to_date=2099-01-07",
        headers={"Authorization": f"Bearer {coach_token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["average"] is None
    assert data["count"] == 0


async def test_skater_cannot_view_weekly_summary(client, skater_token):
    resp = await client.get(
        "/api/training/moods/weekly-summary",
        headers={"Authorization": f"Bearer {skater_token}"},
    )
    assert resp.status_code == 403


# ── Self-Evaluations ─────────────────────────────────────────────────────


async def test_create_self_evaluation(client, skater_token, skater_user_with_skater):
    _, _, skater = skater_user_with_skater
    resp = await client.post(
        "/api/training/self-evaluations",
        json={
            "skater_id": skater.id,
            "date": "2026-03-31",
            "notes": "Good session",
            "element_ratings": [{"name": "3Lz", "rating": 4}],
            "shared": False,
        },
        headers={"Authorization": f"Bearer {skater_token}"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["notes"] == "Good session"
    assert data["shared"] is False
    assert data["element_ratings"] == [{"name": "3Lz", "rating": 4}]


async def test_create_self_evaluation_duplicate_409(client, skater_token, skater_user_with_skater):
    _, _, skater = skater_user_with_skater
    await client.post(
        "/api/training/self-evaluations",
        json={"skater_id": skater.id, "date": "2026-03-30", "notes": "First"},
        headers={"Authorization": f"Bearer {skater_token}"},
    )
    resp = await client.post(
        "/api/training/self-evaluations",
        json={"skater_id": skater.id, "date": "2026-03-30", "notes": "Second"},
        headers={"Authorization": f"Bearer {skater_token}"},
    )
    assert resp.status_code == 409


async def test_update_self_evaluation_toggle_shared(client, skater_token, skater_user_with_skater):
    _, _, skater = skater_user_with_skater
    create_resp = await client.post(
        "/api/training/self-evaluations",
        json={"skater_id": skater.id, "date": "2026-03-29", "notes": "Test", "shared": False},
        headers={"Authorization": f"Bearer {skater_token}"},
    )
    eval_id = create_resp.json()["id"]
    resp = await client.put(
        f"/api/training/self-evaluations/{eval_id}",
        json={"shared": True},
        headers={"Authorization": f"Bearer {skater_token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["shared"] is True


async def test_coach_sees_only_shared_evaluations(
    client, coach_token, skater_token, skater_user_with_skater,
):
    _, _, skater = skater_user_with_skater
    # Private eval
    await client.post(
        "/api/training/self-evaluations",
        json={"skater_id": skater.id, "date": "2026-03-27", "notes": "Private", "shared": False},
        headers={"Authorization": f"Bearer {skater_token}"},
    )
    # Shared eval
    await client.post(
        "/api/training/self-evaluations",
        json={"skater_id": skater.id, "date": "2026-03-28", "notes": "Shared", "shared": True},
        headers={"Authorization": f"Bearer {skater_token}"},
    )
    # Coach query
    resp = await client.get(
        f"/api/training/self-evaluations?skater_id={skater.id}",
        headers={"Authorization": f"Bearer {coach_token}"},
    )
    assert resp.status_code == 200
    evals = resp.json()
    assert len(evals) == 1
    assert evals[0]["notes"] == "Shared"


async def test_skater_sees_all_own_evaluations(client, skater_token, skater_user_with_skater):
    _, _, skater = skater_user_with_skater
    await client.post(
        "/api/training/self-evaluations",
        json={"skater_id": skater.id, "date": "2026-03-25", "notes": "Private", "shared": False},
        headers={"Authorization": f"Bearer {skater_token}"},
    )
    await client.post(
        "/api/training/self-evaluations",
        json={"skater_id": skater.id, "date": "2026-03-26", "notes": "Shared", "shared": True},
        headers={"Authorization": f"Bearer {skater_token}"},
    )
    resp = await client.get(
        f"/api/training/self-evaluations?skater_id={skater.id}",
        headers={"Authorization": f"Bearer {skater_token}"},
    )
    assert resp.status_code == 200
    assert len(resp.json()) == 2


async def test_delete_self_evaluation(client, skater_token, skater_user_with_skater):
    _, _, skater = skater_user_with_skater
    create_resp = await client.post(
        "/api/training/self-evaluations",
        json={"skater_id": skater.id, "date": "2026-03-24", "notes": "Delete me"},
        headers={"Authorization": f"Bearer {skater_token}"},
    )
    eval_id = create_resp.json()["id"]
    resp = await client.delete(
        f"/api/training/self-evaluations/{eval_id}",
        headers={"Authorization": f"Bearer {skater_token}"},
    )
    assert resp.status_code == 204


async def test_reader_no_access_self_evaluations(client, reader_token, skater_user_with_skater):
    _, _, skater = skater_user_with_skater
    resp = await client.get(
        f"/api/training/self-evaluations?skater_id={skater.id}",
        headers={"Authorization": f"Bearer {reader_token}"},
    )
    assert resp.status_code == 403


async def test_coach_cannot_create_self_evaluation(client, coach_token, skater_user_with_skater):
    _, _, skater = skater_user_with_skater
    resp = await client.post(
        "/api/training/self-evaluations",
        json={"skater_id": skater.id, "date": "2026-03-23", "notes": "Coach eval"},
        headers={"Authorization": f"Bearer {coach_token}"},
    )
    assert resp.status_code == 403


async def test_self_evaluation_links_mood(client, skater_token, skater_user_with_skater):
    _, _, skater = skater_user_with_skater
    # Create mood first
    mood_resp = await client.post(
        "/api/training/moods",
        json={"skater_id": skater.id, "date": "2026-03-22", "rating": 4},
        headers={"Authorization": f"Bearer {skater_token}"},
    )
    mood_id = mood_resp.json()["id"]
    # Create eval on same day
    eval_resp = await client.post(
        "/api/training/self-evaluations",
        json={"skater_id": skater.id, "date": "2026-03-22", "notes": "Linked"},
        headers={"Authorization": f"Bearer {skater_token}"},
    )
    assert eval_resp.status_code == 201
    assert eval_resp.json()["mood_id"] == mood_id
```

- [ ] **Step 2: Run tests to verify they fail (routes not yet registered)**

Run: `cd backend && PATH="/opt/homebrew/bin:$PATH" uv run pytest tests/test_self_eval.py -v --tb=short 2>&1 | head -60`

Expected: tests fail (models exist but router not yet registered in main.py)

- [ ] **Step 3: Commit test file**

```bash
git add backend/tests/test_self_eval.py
git commit -m "test: add comprehensive self-eval tests (programs, moods, evaluations)"
```

---

## Task 7: Run Tests Green

**Files:** None (all code already written in Tasks 1-5)

- [ ] **Step 1: Run the full self-eval test suite**

Run: `cd backend && PATH="/opt/homebrew/bin:$PATH" uv run pytest tests/test_self_eval.py -v`

Expected: All tests pass.

- [ ] **Step 2: Run full test suite to check for regressions**

Run: `cd backend && PATH="/opt/homebrew/bin:$PATH" uv run pytest -v`

Expected: All existing tests still pass.

- [ ] **Step 3: Fix any failures**

If there are route conflicts between `training.py` and `self_eval.py` (both mounted at `/api/training`), resolve by either:
- Merging the new handlers into `training.py` instead of a separate file, OR
- Using a sub-path like `/api/training/self` for the new router

The preferred approach: add the new handlers directly to the existing `training.py` router since they share the same path prefix and permission patterns.

- [ ] **Step 4: Commit any fixes**

```bash
git add -u
git commit -m "fix: resolve route conflicts and ensure all tests pass"
```

---

## Task 8: Add Shared Self-Evaluations to Timeline

**Files:**
- Modify: `backend/app/routes/training.py` (or wherever timeline handler lives)

- [ ] **Step 1: Add self-evaluation to timeline handler**

In the `get_timeline` handler in `training.py`, add after the incidents query block:

```python
from app.models.self_evaluation import SelfEvaluation

# Self-evaluations (shared only for coach/admin, all for skater own)
eval_stmt = select(SelfEvaluation).where(SelfEvaluation.skater_id == skater_id)
if role in ("coach", "admin"):
    eval_stmt = eval_stmt.where(SelfEvaluation.shared == True)  # noqa: E712
if from_date:
    eval_stmt = eval_stmt.where(SelfEvaluation.date >= date.fromisoformat(from_date))
if to_date:
    eval_stmt = eval_stmt.where(SelfEvaluation.date <= date.fromisoformat(to_date))
self_evals = (await session.execute(eval_stmt)).scalars().all()
```

And add to the timeline assembly:

```python
for e in self_evals:
    entry = {
        "id": e.id,
        "type": "self_evaluation",
        "skater_id": e.skater_id,
        "date": e.date.isoformat(),
        "notes": e.notes,
        "element_ratings": e.element_ratings,
        "shared": e.shared,
        "mood_id": e.mood_id,
        "sort_date": e.date.isoformat(),
        "created_at": e.created_at.isoformat() if e.created_at else None,
    }
    timeline.append(entry)
```

- [ ] **Step 2: Run tests**

Run: `cd backend && PATH="/opt/homebrew/bin:$PATH" uv run pytest tests/ -v`

Expected: All pass.

- [ ] **Step 3: Commit**

```bash
git add backend/app/routes/training.py
git commit -m "feat: include shared self-evaluations in training timeline"
```

---

## Task 9: Frontend API Types & Functions

**Files:**
- Modify: `frontend/src/api/client.ts`

- [ ] **Step 1: Add type definitions**

Add after the `UpdateChallengePayload` interface (around line 521):

```typescript
export interface SkaterProgram {
  id: number;
  skater_id: number;
  segment: "SP" | "FS";
  elements: string[];
  created_at: string | null;
  updated_at: string | null;
}

export interface UpsertProgramPayload {
  skater_id: number;
  segment: "SP" | "FS";
  elements: string[];
}

export interface TrainingMood {
  id: number;
  skater_id: number;
  date: string;
  rating: number;
  created_at: string | null;
}

export interface CreateMoodPayload {
  skater_id: number;
  date: string;
  rating: number;
}

export interface MoodWeeklySummary {
  average: number | null;
  count: number;
  distribution: number[];
}

export interface ElementRating {
  name: string;
  rating: number;
}

export interface SelfEvaluation {
  id: number;
  skater_id: number;
  mood_id: number | null;
  date: string;
  notes: string | null;
  element_ratings: ElementRating[] | null;
  shared: boolean;
  created_at: string | null;
  updated_at: string | null;
}

export interface CreateSelfEvaluationPayload {
  skater_id: number;
  date: string;
  notes?: string;
  element_ratings?: ElementRating[];
  shared?: boolean;
}

export interface UpdateSelfEvaluationPayload {
  notes?: string;
  element_ratings?: ElementRating[];
  shared?: boolean;
}
```

- [ ] **Step 2: Update TimelineEntry type**

Update the `TimelineEntry` type to include self-evaluations:

```typescript
export type TimelineEntry =
  | (WeeklyReview & { type: "review"; sort_date: string })
  | (TrainingIncident & { type: "incident"; sort_date: string })
  | (SelfEvaluation & { type: "self_evaluation"; sort_date: string });
```

- [ ] **Step 3: Add API functions**

Add inside the `training` object in the `api` namespace (after `challenges`):

```typescript
    programs: {
      list: (skater_id: number) =>
        request<SkaterProgram[]>(`/training/programs?skater_id=${skater_id}`),
      upsert: (data: UpsertProgramPayload) =>
        request<SkaterProgram>("/training/programs", {
          method: "PUT",
          body: JSON.stringify(data),
        }),
      delete: (id: number) =>
        request<void>(`/training/programs/${id}`, { method: "DELETE" }),
    },
    moods: {
      list: (params: { skater_id: number; from?: string; to?: string }) => {
        const qs = new URLSearchParams({ skater_id: String(params.skater_id) });
        if (params.from) qs.set("from_date", params.from);
        if (params.to) qs.set("to_date", params.to);
        return request<TrainingMood[]>(`/training/moods?${qs}`);
      },
      create: (data: CreateMoodPayload) =>
        request<TrainingMood>("/training/moods", {
          method: "POST",
          body: JSON.stringify(data),
        }),
      update: (id: number, data: { rating: number }) =>
        request<TrainingMood>(`/training/moods/${id}`, {
          method: "PUT",
          body: JSON.stringify(data),
        }),
      weeklySummary: (params?: { from?: string; to?: string }) => {
        const qs = new URLSearchParams();
        if (params?.from) qs.set("from_date", params.from);
        if (params?.to) qs.set("to_date", params.to);
        const query = qs.toString() ? `?${qs}` : "";
        return request<MoodWeeklySummary>(`/training/moods/weekly-summary${query}`);
      },
    },
    selfEvaluations: {
      list: (params: { skater_id: number; from?: string; to?: string }) => {
        const qs = new URLSearchParams({ skater_id: String(params.skater_id) });
        if (params.from) qs.set("from_date", params.from);
        if (params.to) qs.set("to_date", params.to);
        return request<SelfEvaluation[]>(`/training/self-evaluations?${qs}`);
      },
      create: (data: CreateSelfEvaluationPayload) =>
        request<SelfEvaluation>("/training/self-evaluations", {
          method: "POST",
          body: JSON.stringify(data),
        }),
      update: (id: number, data: UpdateSelfEvaluationPayload) =>
        request<SelfEvaluation>(`/training/self-evaluations/${id}`, {
          method: "PUT",
          body: JSON.stringify(data),
        }),
      delete: (id: number) =>
        request<void>(`/training/self-evaluations/${id}`, { method: "DELETE" }),
    },
```

- [ ] **Step 4: Commit**

```bash
git add frontend/src/api/client.ts
git commit -m "feat: add self-eval types and API functions to frontend client"
```

---

## Task 10: MoodInput Component

**Files:**
- Create: `frontend/src/components/MoodInput.tsx`

- [ ] **Step 1: Create the MoodInput component**

```tsx
// frontend/src/components/MoodInput.tsx
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, TrainingMood } from "../api/client";

const EMOJIS = [
  { value: 1, emoji: "\u{1F61E}" },  // disappointed
  { value: 2, emoji: "\u{1F615}" },  // confused
  { value: 3, emoji: "\u{1F610}" },  // neutral
  { value: 4, emoji: "\u{1F642}" },  // slightly smiling
  { value: 5, emoji: "\u{1F604}" },  // grinning
];

interface Props {
  skaterId: number;
  today: string; // ISO date string YYYY-MM-DD
}

export default function MoodInput({ skaterId, today }: Props) {
  const queryClient = useQueryClient();

  const { data: moods } = useQuery({
    queryKey: ["moods", skaterId, today],
    queryFn: () => api.training.moods.list({ skater_id: skaterId, from: today, to: today }),
  });

  const todayMood = moods?.[0] as TrainingMood | undefined;

  const createMutation = useMutation({
    mutationFn: (rating: number) =>
      api.training.moods.create({ skater_id: skaterId, date: today, rating }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["moods", skaterId] }),
  });

  const updateMutation = useMutation({
    mutationFn: (rating: number) =>
      api.training.moods.update(todayMood!.id, { rating }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["moods", skaterId] }),
  });

  const handleClick = (rating: number) => {
    if (todayMood) {
      updateMutation.mutate(rating);
    } else {
      createMutation.mutate(rating);
    }
  };

  return (
    <div className="bg-surface-container-lowest rounded-xl shadow-sm p-5">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-[10px] font-black uppercase tracking-widest text-on-surface-variant mb-2">
            Comment s'est passe l'entrainement ?
          </p>
          <div className="flex gap-3">
            {EMOJIS.map(({ value, emoji }) => (
              <button
                key={value}
                onClick={() => handleClick(value)}
                className={`text-[28px] transition-all cursor-pointer rounded-xl px-1.5 py-0.5 ${
                  todayMood?.rating === value
                    ? "bg-primary-container scale-110"
                    : "opacity-30 grayscale hover:opacity-60 hover:grayscale-0"
                }`}
              >
                {emoji}
              </button>
            ))}
          </div>
        </div>
        <p className="text-[10px] text-outline flex items-center gap-1">
          <span className="material-symbols-outlined text-sm">visibility</span>
          Visible par vos coachs
        </p>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/components/MoodInput.tsx
git commit -m "feat: add MoodInput emoji picker component"
```

---

## Task 11: ProgramEditor Component

**Files:**
- Create: `frontend/src/components/ProgramEditor.tsx`

- [ ] **Step 1: Create the ProgramEditor component**

```tsx
// frontend/src/components/ProgramEditor.tsx
import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api, SkaterProgram } from "../api/client";

interface Props {
  skaterId: number;
  readOnly?: boolean;
}

export default function ProgramEditor({ skaterId, readOnly = false }: Props) {
  const queryClient = useQueryClient();
  const [activeSegment, setActiveSegment] = useState<"SP" | "FS">("SP");
  const [newElement, setNewElement] = useState("");

  const { data: programs } = useQuery({
    queryKey: ["programs", skaterId],
    queryFn: () => api.training.programs.list(skaterId),
  });

  const activeProgram = programs?.find((p) => p.segment === activeSegment);

  const upsertMutation = useMutation({
    mutationFn: (elements: string[]) =>
      api.training.programs.upsert({ skater_id: skaterId, segment: activeSegment, elements }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["programs", skaterId] }),
  });

  const handleAdd = () => {
    const trimmed = newElement.trim();
    if (!trimmed) return;
    const current = activeProgram?.elements ?? [];
    upsertMutation.mutate([...current, trimmed]);
    setNewElement("");
  };

  const handleRemove = (index: number) => {
    const current = activeProgram?.elements ?? [];
    upsertMutation.mutate(current.filter((_, i) => i !== index));
  };

  const elements = activeProgram?.elements ?? [];

  return (
    <div className="bg-surface-container-lowest rounded-xl shadow-sm p-5">
      <p className="text-[10px] font-black uppercase tracking-widest text-on-surface-variant mb-3">
        Mon programme
      </p>
      <div className="flex gap-2 mb-3">
        {(["SP", "FS"] as const).map((seg) => (
          <button
            key={seg}
            onClick={() => setActiveSegment(seg)}
            className={`text-[10px] font-bold px-3 py-1 rounded-full uppercase transition-colors ${
              activeSegment === seg
                ? "bg-primary-container text-on-primary-container"
                : "bg-surface-container text-on-surface-variant"
            }`}
          >
            {seg === "SP" ? "PC" : "PL"}
          </button>
        ))}
      </div>
      <div className="space-y-1">
        {elements.map((el, i) => (
          <div key={i} className="flex items-center justify-between text-sm text-on-surface-variant">
            <span>{el}</span>
            {!readOnly && (
              <button onClick={() => handleRemove(i)} className="text-outline-variant hover:text-error text-xs">
                <span className="material-symbols-outlined text-sm">close</span>
              </button>
            )}
          </div>
        ))}
        {elements.length === 0 && (
          <p className="text-xs text-outline">Aucun element enregistre</p>
        )}
      </div>
      {!readOnly && (
        <div className="mt-2 flex items-center gap-2">
          <input
            type="text"
            value={newElement}
            onChange={(e) => setNewElement(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleAdd()}
            placeholder="Ex: 3Lz"
            className="bg-surface-container rounded-lg px-3 py-1.5 text-xs flex-1 outline-none focus:ring-1 focus:ring-primary"
          />
          <button onClick={handleAdd} className="text-primary text-xs font-semibold">
            + Ajouter
          </button>
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/components/ProgramEditor.tsx
git commit -m "feat: add ProgramEditor component for SP/FS element lists"
```

---

## Task 12: SelfEvalModal Component

**Files:**
- Create: `frontend/src/components/SelfEvalModal.tsx`

- [ ] **Step 1: Create the SelfEvalModal component**

```tsx
// frontend/src/components/SelfEvalModal.tsx
import { useState, useEffect } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, ElementRating, SelfEvaluation } from "../api/client";

const EMOJIS = [
  { value: 1, emoji: "\u{1F61E}" },
  { value: 2, emoji: "\u{1F615}" },
  { value: 3, emoji: "\u{1F610}" },
  { value: 4, emoji: "\u{1F642}" },
  { value: 5, emoji: "\u{1F604}" },
];

interface Props {
  skaterId: number;
  today: string;
  existingEval?: SelfEvaluation;
  onClose: () => void;
}

export default function SelfEvalModal({ skaterId, today, existingEval, onClose }: Props) {
  const queryClient = useQueryClient();
  const [evalDate, setEvalDate] = useState(existingEval?.date ?? today);
  const [moodRating, setMoodRating] = useState<number | null>(null);
  const [notes, setNotes] = useState(existingEval?.notes ?? "");
  const [elementRatings, setElementRatings] = useState<ElementRating[]>(
    existingEval?.element_ratings ?? []
  );
  const [shared, setShared] = useState(existingEval?.shared ?? false);
  const [newElement, setNewElement] = useState("");

  // Pre-fill elements from registered program
  const { data: programs } = useQuery({
    queryKey: ["programs", skaterId],
    queryFn: () => api.training.programs.list(skaterId),
  });

  useEffect(() => {
    if (!existingEval && programs && elementRatings.length === 0) {
      const allElements: ElementRating[] = [];
      for (const p of programs) {
        for (const el of p.elements) {
          if (!allElements.find((e) => e.name === el)) {
            allElements.push({ name: el, rating: 0 });
          }
        }
      }
      if (allElements.length > 0) setElementRatings(allElements);
    }
  }, [programs, existingEval, elementRatings.length]);

  // Pre-fill mood from today's mood
  const { data: moods } = useQuery({
    queryKey: ["moods", skaterId, evalDate],
    queryFn: () => api.training.moods.list({ skater_id: skaterId, from: evalDate, to: evalDate }),
  });

  useEffect(() => {
    if (moods?.[0]) setMoodRating(moods[0].rating);
  }, [moods]);

  const moodMutation = useMutation({
    mutationFn: (rating: number) => {
      if (moods?.[0]) return api.training.moods.update(moods[0].id, { rating });
      return api.training.moods.create({ skater_id: skaterId, date: evalDate, rating });
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["moods"] }),
  });

  const createMutation = useMutation({
    mutationFn: () =>
      api.training.selfEvaluations.create({
        skater_id: skaterId,
        date: evalDate,
        notes: notes || undefined,
        element_ratings: elementRatings.filter((e) => e.rating > 0),
        shared,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["selfEvaluations"] });
      queryClient.invalidateQueries({ queryKey: ["timeline"] });
      onClose();
    },
  });

  const updateMutation = useMutation({
    mutationFn: () =>
      api.training.selfEvaluations.update(existingEval!.id, {
        notes: notes || undefined,
        element_ratings: elementRatings.filter((e) => e.rating > 0),
        shared,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["selfEvaluations"] });
      queryClient.invalidateQueries({ queryKey: ["timeline"] });
      onClose();
    },
  });

  const handleSave = () => {
    if (moodRating) moodMutation.mutate(moodRating);
    if (existingEval) updateMutation.mutate();
    else createMutation.mutate();
  };

  const setRating = (index: number, rating: number) => {
    setElementRatings((prev) =>
      prev.map((e, i) => (i === index ? { ...e, rating } : e))
    );
  };

  const addElement = () => {
    const trimmed = newElement.trim();
    if (!trimmed || elementRatings.find((e) => e.name === trimmed)) return;
    setElementRatings((prev) => [...prev, { name: trimmed, rating: 0 }]);
    setNewElement("");
  };

  const removeElement = (index: number) => {
    setElementRatings((prev) => prev.filter((_, i) => i !== index));
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4" onClick={onClose}>
      <div className="absolute inset-0 bg-on-surface/30" />
      <div
        className="relative bg-surface-container-lowest rounded-2xl shadow-arctic p-6 w-full max-w-md max-h-[90vh] overflow-y-auto"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between mb-5">
          <h3 className="font-headline font-bold text-on-surface">Evaluer ma seance</h3>
          <button onClick={onClose} className="text-outline hover:text-on-surface">
            <span className="material-symbols-outlined">close</span>
          </button>
        </div>

        {/* Date */}
        <div className="mb-4">
          <label className="text-[10px] font-black uppercase tracking-widest text-on-surface-variant block mb-1.5">
            Date
          </label>
          <input
            type="date"
            value={evalDate}
            onChange={(e) => setEvalDate(e.target.value)}
            disabled={!!existingEval}
            className="bg-surface-container-low rounded-lg px-3 py-2.5 text-sm w-full outline-none"
          />
        </div>

        {/* Mood */}
        <div className="mb-4">
          <label className="text-[10px] font-black uppercase tracking-widest text-on-surface-variant block mb-1.5">
            Humeur
          </label>
          <div className="flex gap-2.5">
            {EMOJIS.map(({ value, emoji }) => (
              <button
                key={value}
                onClick={() => setMoodRating(value)}
                className={`text-2xl rounded-xl px-1 py-0.5 transition-all ${
                  moodRating === value
                    ? "bg-primary-container"
                    : "opacity-30 hover:opacity-60"
                }`}
              >
                {emoji}
              </button>
            ))}
          </div>
        </div>

        {/* Notes */}
        <div className="mb-4">
          <label className="text-[10px] font-black uppercase tracking-widest text-on-surface-variant block mb-1.5">
            Notes
          </label>
          <textarea
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            placeholder="Comment s'est passee la seance..."
            rows={3}
            className="bg-surface-container-low rounded-lg px-3 py-2.5 text-sm w-full outline-none resize-none"
          />
        </div>

        {/* Element Ratings */}
        <div className="mb-4">
          <label className="text-[10px] font-black uppercase tracking-widest text-on-surface-variant block mb-2">
            Elements techniques
          </label>
          <div className="space-y-2">
            {elementRatings.map((el, i) => (
              <div key={i} className="flex items-center justify-between py-1.5 border-b border-surface-container-low">
                <span className="text-sm font-semibold min-w-[70px]">{el.name}</span>
                <div className="flex gap-1">
                  {[1, 2, 3, 4, 5].map((v) => (
                    <button
                      key={v}
                      onClick={() => setRating(i, v)}
                      className={`w-7 h-7 rounded-full text-[11px] font-bold flex items-center justify-center transition-colors ${
                        v <= el.rating
                          ? "bg-primary text-on-primary"
                          : "bg-surface-container text-outline"
                      }`}
                    >
                      {v}
                    </button>
                  ))}
                </div>
                <button onClick={() => removeElement(i)} className="text-outline-variant hover:text-error ml-2">
                  <span className="material-symbols-outlined text-sm">close</span>
                </button>
              </div>
            ))}
          </div>
          <div className="mt-2 flex items-center gap-2">
            <input
              type="text"
              value={newElement}
              onChange={(e) => setNewElement(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && addElement()}
              placeholder="Ajouter un element"
              className="bg-surface-container rounded-lg px-3 py-1.5 text-xs flex-1 outline-none focus:ring-1 focus:ring-primary"
            />
            <button onClick={addElement} className="text-primary text-xs font-semibold">
              + Ajouter
            </button>
          </div>
        </div>

        {/* Share toggle */}
        <div className="flex items-center justify-between py-3 border-t border-surface-container-low">
          <div>
            <p className="text-sm font-semibold">Partager avec les coachs</p>
            <p className="text-[10px] text-outline">Votre evaluation sera visible par l'equipe</p>
          </div>
          <button
            onClick={() => setShared(!shared)}
            className={`w-10 h-[22px] rounded-full relative transition-colors ${
              shared ? "bg-primary" : "bg-surface-container"
            }`}
          >
            <div
              className={`w-[18px] h-[18px] bg-surface-container-lowest rounded-full absolute top-[2px] shadow-sm transition-transform ${
                shared ? "translate-x-[20px]" : "translate-x-[2px]"
              }`}
            />
          </button>
        </div>

        {/* Save */}
        <button
          onClick={handleSave}
          disabled={createMutation.isPending || updateMutation.isPending}
          className="w-full bg-primary text-on-primary rounded-lg py-3 text-sm font-bold mt-3 active:scale-95 transition-all disabled:opacity-50"
        >
          Enregistrer
        </button>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/components/SelfEvalModal.tsx
git commit -m "feat: add SelfEvalModal component for self-evaluation form"
```

---

## Task 13: TrainingJournal Component

**Files:**
- Create: `frontend/src/components/TrainingJournal.tsx`

- [ ] **Step 1: Create the TrainingJournal component**

```tsx
// frontend/src/components/TrainingJournal.tsx
import { useQuery } from "@tanstack/react-query";
import { api, TrainingMood, SelfEvaluation } from "../api/client";

const EMOJI_MAP: Record<number, string> = {
  1: "\u{1F61E}",
  2: "\u{1F615}",
  3: "\u{1F610}",
  4: "\u{1F642}",
  5: "\u{1F604}",
};

const DAY_NAMES = ["Dim", "Lun", "Mar", "Mer", "Jeu", "Ven", "Sam"];

interface Props {
  skaterId: number;
  weekStart: string; // ISO date of Monday
  weekEnd: string;   // ISO date of Sunday
}

export default function TrainingJournal({ skaterId, weekStart, weekEnd }: Props) {
  const { data: moods } = useQuery({
    queryKey: ["moods", skaterId, weekStart, weekEnd],
    queryFn: () => api.training.moods.list({ skater_id: skaterId, from: weekStart, to: weekEnd }),
  });

  const { data: evals } = useQuery({
    queryKey: ["selfEvaluations", skaterId, weekStart, weekEnd],
    queryFn: () =>
      api.training.selfEvaluations.list({ skater_id: skaterId, from: weekStart, to: weekEnd }),
  });

  // Build mood map by date
  const moodByDate: Record<string, TrainingMood> = {};
  moods?.forEach((m) => { moodByDate[m.date] = m; });

  // Generate week days
  const weekDays: string[] = [];
  const start = new Date(weekStart + "T00:00:00");
  for (let i = 0; i < 7; i++) {
    const d = new Date(start);
    d.setDate(d.getDate() + i);
    weekDays.push(d.toISOString().slice(0, 10));
  }

  const formatDate = (iso: string) =>
    new Date(iso + "T00:00:00").toLocaleDateString("fr-FR", {
      weekday: "long",
      day: "numeric",
      month: "long",
    });

  return (
    <div className="bg-surface-container-lowest rounded-xl shadow-sm p-5">
      <p className="text-[10px] font-black uppercase tracking-widest text-on-surface-variant mb-4">
        Journal
      </p>

      {/* Mood timeline strip */}
      <div className="flex gap-2 mb-5 overflow-x-auto pb-1">
        {weekDays.map((day) => {
          const mood = moodByDate[day];
          const dayOfWeek = DAY_NAMES[new Date(day + "T00:00:00").getDay()];
          return (
            <div key={day} className="text-center min-w-[44px]">
              <div className="text-[9px] text-outline mb-0.5">{dayOfWeek}</div>
              <div className={`text-xl ${mood ? "" : "opacity-20"}`}>
                {mood ? EMOJI_MAP[mood.rating] : "\u{1F636}"}
              </div>
            </div>
          );
        })}
      </div>

      {/* Past evaluations */}
      {evals && evals.length > 0 && (
        <div className="border-t border-surface-container-low pt-3 space-y-3">
          {evals.map((ev) => {
            const mood = moodByDate[ev.date];
            return (
              <div key={ev.id} className="flex items-start gap-3 pb-3 border-b border-surface-container-low last:border-b-0">
                <div className="text-xl">{mood ? EMOJI_MAP[mood.rating] : "\u{1F636}"}</div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-1">
                    <span className="text-xs font-bold text-on-surface capitalize">
                      {formatDate(ev.date)}
                    </span>
                    {ev.shared && (
                      <span className="bg-primary-container text-on-primary-container text-[9px] font-bold px-2 py-0.5 rounded-full">
                        Partage
                      </span>
                    )}
                  </div>
                  {ev.notes && (
                    <p className="text-xs text-on-surface-variant leading-relaxed mb-2">
                      {ev.notes}
                    </p>
                  )}
                  {ev.element_ratings && ev.element_ratings.length > 0 && (
                    <div className="flex gap-1.5 flex-wrap">
                      {ev.element_ratings.map((er, i) => (
                        <span
                          key={i}
                          className="bg-surface-container-low text-[10px] px-2 py-1 rounded-lg font-semibold"
                        >
                          {er.name}{" "}
                          <span className="text-primary">{er.rating}/5</span>
                        </span>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}

      {(!evals || evals.length === 0) && (
        <p className="text-xs text-outline text-center py-4">
          Aucune evaluation cette semaine
        </p>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/components/TrainingJournal.tsx
git commit -m "feat: add TrainingJournal component with mood strip and eval history"
```

---

## Task 14: MoodAggregateWidget Component

**Files:**
- Create: `frontend/src/components/MoodAggregateWidget.tsx`

- [ ] **Step 1: Create the MoodAggregateWidget component**

```tsx
// frontend/src/components/MoodAggregateWidget.tsx
import { useQuery } from "@tanstack/react-query";
import { api, MoodWeeklySummary } from "../api/client";

const EMOJI_MAP: Record<number, string> = {
  1: "\u{1F61E}",
  2: "\u{1F615}",
  3: "\u{1F610}",
  4: "\u{1F642}",
  5: "\u{1F604}",
};

function averageEmoji(avg: number): string {
  return EMOJI_MAP[Math.round(avg)] ?? "\u{1F610}";
}

interface Props {
  currentWeekStart: string;
  currentWeekEnd: string;
  previousWeekStart: string;
  previousWeekEnd: string;
}

export default function MoodAggregateWidget({
  currentWeekStart,
  currentWeekEnd,
  previousWeekStart,
  previousWeekEnd,
}: Props) {
  const { data: current } = useQuery({
    queryKey: ["moodSummary", currentWeekStart, currentWeekEnd],
    queryFn: () => api.training.moods.weeklySummary({ from: currentWeekStart, to: currentWeekEnd }),
  });

  const { data: previous } = useQuery({
    queryKey: ["moodSummary", previousWeekStart, previousWeekEnd],
    queryFn: () => api.training.moods.weeklySummary({ from: previousWeekStart, to: previousWeekEnd }),
  });

  if (!current) return null;

  const maxDist = Math.max(...(current.distribution ?? [1]));
  const trend =
    current.average != null && previous?.average != null
      ? +(current.average - previous.average).toFixed(1)
      : null;

  return (
    <div className="bg-surface-container-lowest rounded-xl shadow-sm p-5">
      <div className="flex items-center justify-between mb-4">
        <p className="text-[10px] font-black uppercase tracking-widest text-on-surface-variant">
          Humeur du groupe
        </p>
        <p className="text-[10px] text-outline">
          Semaine du{" "}
          {new Date(currentWeekStart + "T00:00:00").toLocaleDateString("fr-FR", {
            day: "numeric",
            month: "long",
          })}
        </p>
      </div>

      <div className="flex gap-5 items-start">
        {/* Big average */}
        <div className="text-center min-w-[80px]">
          <div className="text-[40px] mb-1">
            {current.average != null ? averageEmoji(current.average) : "\u{1F636}"}
          </div>
          <div className="font-headline text-[28px] font-extrabold text-on-surface">
            {current.average ?? "—"}
          </div>
          <div className="text-[10px] text-outline">sur 5</div>
        </div>

        {/* Distribution bar chart */}
        <div className="flex-1">
          <div className="flex items-end gap-2 h-[60px] mb-2">
            {current.distribution.map((count, i) => (
              <div key={i} className="flex-1 flex flex-col items-center">
                <div className="text-[9px] text-outline mb-0.5">{count}</div>
                <div
                  className={`w-full rounded-t ${i >= 3 ? "bg-primary" : "bg-primary-container"}`}
                  style={{ height: `${maxDist > 0 ? (count / maxDist) * 50 : 4}px`, minHeight: "4px" }}
                />
              </div>
            ))}
          </div>
          <div className="flex gap-2">
            {[1, 2, 3, 4, 5].map((v) => (
              <div key={v} className="flex-1 text-center text-sm">
                {EMOJI_MAP[v]}
              </div>
            ))}
          </div>
        </div>

        {/* Trend */}
        {trend !== null && (
          <div className="text-center min-w-[70px] pt-2">
            <p className="text-[10px] font-black uppercase tracking-wider text-on-surface-variant mb-1">
              Tendance
            </p>
            <div className="flex items-center justify-center gap-1">
              <span className={`text-lg ${trend >= 0 ? "text-primary" : "text-error"}`}>
                {trend >= 0 ? "\u25B2" : "\u25BC"}
              </span>
              <span className={`font-headline text-base font-bold ${trend >= 0 ? "text-primary" : "text-error"}`}>
                {trend >= 0 ? "+" : ""}{trend}
              </span>
            </div>
            <p className="text-[9px] text-outline">vs semaine prec.</p>
          </div>
        )}
      </div>

      <div className="mt-3 pt-2.5 border-t border-surface-container-low flex items-center gap-1.5">
        <span className="text-[10px] text-outline">{current.count} evaluations cette semaine</span>
        <span className="text-[10px] text-outline">·</span>
        <span className="text-[10px] text-outline">Donnees anonymes</span>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/components/MoodAggregateWidget.tsx
git commit -m "feat: add MoodAggregateWidget for coach group mood overview"
```

---

## Task 15: Integrate Components into SkaterAnalyticsPage

**Files:**
- Modify: `frontend/src/pages/SkaterAnalyticsPage.tsx`

- [ ] **Step 1: Add imports**

Add at the top of the file:

```typescript
import MoodInput from "../components/MoodInput";
import SelfEvalModal from "../components/SelfEvalModal";
import ProgramEditor from "../components/ProgramEditor";
import TrainingJournal from "../components/TrainingJournal";
```

- [ ] **Step 2: Add state and date helpers**

Inside the component function, add:

```typescript
const [showEvalModal, setShowEvalModal] = useState(false);
const today = new Date().toISOString().slice(0, 10);

// Week bounds for journal
const now = new Date();
const monday = new Date(now);
monday.setDate(now.getDate() - ((now.getDay() + 6) % 7));
const sunday = new Date(monday);
sunday.setDate(monday.getDate() + 6);
const weekStart = monday.toISOString().slice(0, 10);
const weekEnd = sunday.toISOString().slice(0, 10);
```

- [ ] **Step 3: Add self-eval blocks for skater role**

After the hero header section, add (guarded by `role === "skater"`):

```tsx
{role === "skater" && skaterId && (
  <>
    {/* Mood */}
    <MoodInput skaterId={skaterId} today={today} />

    {/* Eval + Program side by side */}
    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
      <div className="bg-surface-container-lowest rounded-xl shadow-sm p-5 text-center">
        <p className="text-[10px] font-black uppercase tracking-widest text-on-surface-variant mb-3">
          Evaluation d'aujourd'hui
        </p>
        <p className="text-3xl mb-2">{"\u{1F4DD}"}</p>
        <p className="text-sm text-on-surface-variant mb-3">
          Pas encore d'evaluation pour aujourd'hui
        </p>
        <button
          onClick={() => setShowEvalModal(true)}
          className="bg-primary text-on-primary rounded-lg px-5 py-2.5 text-xs font-bold active:scale-95 transition-all"
        >
          Evaluer ma seance
        </button>
      </div>
      <ProgramEditor skaterId={skaterId} />
    </div>

    {/* Journal */}
    <TrainingJournal skaterId={skaterId} weekStart={weekStart} weekEnd={weekEnd} />

    {/* Modal */}
    {showEvalModal && (
      <SelfEvalModal
        skaterId={skaterId}
        today={today}
        onClose={() => setShowEvalModal(false)}
      />
    )}
  </>
)}
```

Where `skaterId` is the numeric skater ID from the page params, and `role` is from `useAuth()`.

- [ ] **Step 4: Run frontend dev server to verify**

Run: `cd frontend && PATH="/opt/homebrew/bin:$PATH" npm run dev`

Open the skater analytics page logged in as a skater user. Verify the mood input, evaluation button, program editor, and journal sections appear.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/SkaterAnalyticsPage.tsx
git commit -m "feat: integrate self-eval components into skater analytics page"
```

---

## Task 16: Integrate MoodAggregateWidget into TrainingPage

**Files:**
- Modify: `frontend/src/pages/TrainingPage.tsx`

- [ ] **Step 1: Add import and widget**

Add import:

```typescript
import MoodAggregateWidget from "../components/MoodAggregateWidget";
```

Add week calculation and widget at the top of the page content (guarded by coach/admin role):

```tsx
const now = new Date();
const monday = new Date(now);
monday.setDate(now.getDate() - ((now.getDay() + 6) % 7));
const sunday = new Date(monday);
sunday.setDate(monday.getDate() + 6);
const prevMonday = new Date(monday);
prevMonday.setDate(monday.getDate() - 7);
const prevSunday = new Date(monday);
prevSunday.setDate(monday.getDate() - 1);

// At top of page content:
<MoodAggregateWidget
  currentWeekStart={monday.toISOString().slice(0, 10)}
  currentWeekEnd={sunday.toISOString().slice(0, 10)}
  previousWeekStart={prevMonday.toISOString().slice(0, 10)}
  previousWeekEnd={prevSunday.toISOString().slice(0, 10)}
/>
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/pages/TrainingPage.tsx
git commit -m "feat: add mood aggregate widget to coach training page"
```

---

## Task 17: Show Shared Self-Evaluations in SkaterTrainingPage

**Files:**
- Modify: `frontend/src/pages/SkaterTrainingPage.tsx`

- [ ] **Step 1: Update timeline rendering**

The timeline already fetches from `/api/training/timeline`, which now includes `self_evaluation` entries (from Task 8). Add a card renderer for the new type in the timeline section:

```tsx
{entry.type === "self_evaluation" && (
  <div className="bg-surface-container-low rounded-2xl p-5 space-y-2">
    <div className="flex items-center gap-2">
      <h4 className="font-headline font-bold text-on-surface text-sm">
        Auto-evaluation du{" "}
        {new Date(entry.date + "T00:00:00").toLocaleDateString("fr-FR", {
          day: "numeric",
          month: "long",
        })}
      </h4>
      {entry.shared && (
        <span className="bg-primary-container text-on-primary-container text-[9px] font-bold px-2 py-0.5 rounded-full">
          Partage
        </span>
      )}
    </div>
    {entry.notes && (
      <p className="text-sm text-on-surface-variant">{entry.notes}</p>
    )}
    {entry.element_ratings && entry.element_ratings.length > 0 && (
      <div className="flex gap-1.5 flex-wrap">
        {entry.element_ratings.map((er: { name: string; rating: number }, i: number) => (
          <span key={i} className="bg-surface-container text-[10px] px-2 py-1 rounded-lg font-semibold">
            {er.name} <span className="text-primary">{er.rating}/5</span>
          </span>
        ))}
      </div>
    )}
  </div>
)}
```

- [ ] **Step 2: Update the `TimelineEntry` import if needed**

Ensure `SelfEvaluation` is imported from `client.ts` and the `TimelineEntry` union type includes it.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/pages/SkaterTrainingPage.tsx
git commit -m "feat: render shared self-evaluations in skater training timeline"
```

---

## Task 18: Final Verification

- [ ] **Step 1: Run full backend test suite**

Run: `cd backend && PATH="/opt/homebrew/bin:$PATH" uv run pytest -v`

Expected: All tests pass, including the new `test_self_eval.py`.

- [ ] **Step 2: Run frontend type check**

Run: `cd frontend && PATH="/opt/homebrew/bin:$PATH" npx tsc --noEmit`

Expected: No type errors.

- [ ] **Step 3: Manual smoke test with Docker Compose**

Run: `docker compose up --build`

Test flow:
1. Log in as skater
2. Navigate to analytics page
3. Click mood emoji — verify it saves
4. Open "Evaluer ma seance" modal — fill in notes + ratings, save
5. Verify journal shows the evaluation
6. Log in as coach
7. Verify "Humeur du groupe" widget shows aggregate
8. Navigate to skater training page — verify shared evaluation appears in timeline

- [ ] **Step 4: Commit any final fixes**

```bash
git add -u
git commit -m "fix: final adjustments from smoke testing"
```
