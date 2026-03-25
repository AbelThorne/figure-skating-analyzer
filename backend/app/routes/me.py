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
