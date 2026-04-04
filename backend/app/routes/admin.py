from __future__ import annotations

from litestar import Router, post, Request
from litestar.di import Provide
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.guards import require_admin
from app.database import get_session, engine, Base, _bootstrap


@post("/reset-database")
async def reset_database(request: Request) -> dict:
    """Drop all data tables and re-create them. Admin only."""
    require_admin(request)

    import app.models  # noqa: F401 — ensure all models registered

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    await _bootstrap()

    return {"status": "ok", "message": "Database reset successfully"}


@post("/recalculate-clubs")
async def recalculate_clubs(request: Request, session: AsyncSession) -> dict:
    """Update Skater.club to match the club from their most recent score."""
    require_admin(request)

    from sqlalchemy import select, func
    from app.models.skater import Skater
    from app.models.score import Score
    from app.models.competition import Competition

    # For each skater, find the club from the score with the most recent competition date
    skaters = (await session.execute(select(Skater))).scalars().all()
    updated = 0

    for skater in skaters:
        # Get the club from the most recent competition
        stmt = (
            select(Score.club)
            .join(Competition, Score.competition_id == Competition.id)
            .where(Score.skater_id == skater.id, Score.club.isnot(None), Score.club != "")
            .order_by(Competition.date.desc().nullslast())
            .limit(1)
        )
        latest_club = (await session.execute(stmt)).scalar_one_or_none()
        if latest_club and latest_club != skater.club:
            skater.club = latest_club
            updated += 1

    await session.commit()
    return {"status": "ok", "skaters_updated": updated}


router = Router(
    path="/api/admin",
    route_handlers=[reset_database, recalculate_clubs],
    dependencies={"session": Provide(get_session)},
)
