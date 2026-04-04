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

    from sqlalchemy import select, func, update
    from app.models.skater import Skater
    from app.models.score import Score
    from app.models.competition import Competition

    # Single query: for each skater, get the club from the score with the latest competition date
    # Use a subquery with DISTINCT ON equivalent for SQLite (window function)
    latest_club_subq = (
        select(
            Score.skater_id,
            Score.club,
            func.row_number().over(
                partition_by=Score.skater_id,
                order_by=Competition.date.desc().nullslast(),
            ).label("rn"),
        )
        .join(Competition, Score.competition_id == Competition.id)
        .where(Score.club.isnot(None), Score.club != "")
        .subquery()
    )

    latest_clubs = (
        await session.execute(
            select(latest_club_subq.c.skater_id, latest_club_subq.c.club)
            .where(latest_club_subq.c.rn == 1)
        )
    ).all()

    updated = 0
    for skater_id, club in latest_clubs:
        result = await session.execute(
            update(Skater)
            .where(Skater.id == skater_id, Skater.club != club)
            .values(club=club)
        )
        updated += result.rowcount

    await session.commit()
    return {"status": "ok", "skaters_updated": updated}


router = Router(
    path="/api/admin",
    route_handlers=[reset_database, recalculate_clubs],
    dependencies={"session": Provide(get_session)},
)
