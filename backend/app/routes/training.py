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

    review_stmt = select(WeeklyReview).where(WeeklyReview.skater_id == skater_id)
    if role == "skater":
        review_stmt = review_stmt.where(WeeklyReview.visible_to_skater == True)  # noqa: E712
    if from_date:
        review_stmt = review_stmt.where(WeeklyReview.week_start >= date.fromisoformat(from_date))
    if to_date:
        review_stmt = review_stmt.where(WeeklyReview.week_start <= date.fromisoformat(to_date))
    reviews = (await session.execute(review_stmt)).scalars().all()

    incident_stmt = select(Incident).where(Incident.skater_id == skater_id)
    if role == "skater":
        incident_stmt = incident_stmt.where(Incident.visible_to_skater == True)  # noqa: E712
    if from_date:
        incident_stmt = incident_stmt.where(Incident.date >= date.fromisoformat(from_date))
    if to_date:
        incident_stmt = incident_stmt.where(Incident.date <= date.fromisoformat(to_date))
    incidents = (await session.execute(incident_stmt)).scalars().all()

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
