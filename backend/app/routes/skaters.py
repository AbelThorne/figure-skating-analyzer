from __future__ import annotations

from litestar import Router, get
from litestar.di import Provide
from litestar.exceptions import NotFoundException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_session
from app.models.skater import Skater
from app.models.score import Score
from app.models.competition import Competition


@get("/")
async def list_skaters(session: AsyncSession) -> list[dict]:
    result = await session.execute(select(Skater).order_by(Skater.name))
    return [
        {"id": s.id, "name": s.name, "nationality": s.nationality}
        for s in result.scalars()
    ]


@get("/{skater_id:int}")
async def get_skater(skater_id: int, session: AsyncSession) -> dict:
    skater = await session.get(Skater, skater_id)
    if not skater:
        raise NotFoundException(f"Skater {skater_id} not found")
    return {"id": skater.id, "name": skater.name, "nationality": skater.nationality}


@get("/{skater_id:int}/scores")
async def get_skater_scores(skater_id: int, session: AsyncSession) -> list[dict]:
    skater = await session.get(Skater, skater_id)
    if not skater:
        raise NotFoundException(f"Skater {skater_id} not found")

    result = await session.execute(
        select(Score)
        .where(Score.skater_id == skater_id)
        .options(selectinload(Score.competition))
        .order_by(Score.id)
    )
    scores = result.scalars().all()
    return [
        {
            "id": s.id,
            "competition_id": s.competition_id,
            "competition_name": s.competition.name if s.competition else None,
            "competition_date": s.competition.date.isoformat() if s.competition and s.competition.date else None,
            "segment": s.segment,
            "rank": s.rank,
            "total_score": s.total_score,
            "technical_score": s.technical_score,
            "component_score": s.component_score,
            "deductions": s.deductions,
        }
        for s in scores
    ]


router = Router(
    path="/api/skaters",
    route_handlers=[list_skaters, get_skater, get_skater_scores],
    dependencies={"session": Provide(get_session)},
)
