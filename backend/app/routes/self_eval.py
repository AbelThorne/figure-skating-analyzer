# backend/app/routes/self_eval.py
from __future__ import annotations

from datetime import date
from typing import Optional

from litestar import Router, get, post, put, delete, Request
from litestar.di import Provide
from litestar.exceptions import NotFoundException, PermissionDeniedException
from litestar.status_codes import HTTP_201_CREATED, HTTP_204_NO_CONTENT
from sqlalchemy import select
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
    elif role in ("coach", "admin"):
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

    element_ratings = data.get("element_ratings")
    if element_ratings:
        for er in element_ratings:
            if not (1 <= er.get("rating", 0) <= 5):
                raise PermissionDeniedException("Element ratings must be between 1 and 5")

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


# ── Exported handler list (merged into training router) ───────────────────

self_eval_handlers = [
    list_programs, upsert_program, delete_program,
    list_moods, create_mood, update_mood, mood_weekly_summary,
    list_self_evaluations, create_self_evaluation,
    update_self_evaluation, delete_self_evaluation,
]
