from __future__ import annotations

from typing import Optional

from litestar import Router, get
from litestar.di import Provide
from litestar.exceptions import NotFoundException
from litestar.params import Parameter
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_session
from app.models.score import Score


@get("/")
async def list_scores(
    session: AsyncSession,
    competition_id: Optional[int] = None,
    skater_id: Optional[int] = None,
    segment: Optional[str] = None,
) -> list[dict]:
    stmt = (
        select(Score)
        .options(selectinload(Score.competition), selectinload(Score.skater))
        .order_by(Score.competition_id, Score.segment, Score.rank)
    )
    if competition_id is not None:
        stmt = stmt.where(Score.competition_id == competition_id)
    if skater_id is not None:
        stmt = stmt.where(Score.skater_id == skater_id)
    if segment is not None:
        stmt = stmt.where(Score.segment == segment.upper())

    result = await session.execute(stmt)
    scores = result.scalars().all()
    return [_score_to_dict(s) for s in scores]


def _score_to_dict(s: Score) -> dict:
    return {
        "id": s.id,
        "competition_id": s.competition_id,
        "competition_name": s.competition.name if s.competition else None,
        "competition_date": s.competition.date.isoformat() if s.competition and s.competition.date else None,
        "skater_id": s.skater_id,
        "skater_name": s.skater.name if s.skater else None,
        "skater_nationality": s.skater.nationality if s.skater else None,
        "skater_club": s.skater.club if s.skater else None,
        "segment": s.segment,
        "category": s.category,
        "starting_number": s.starting_number,
        "rank": s.rank,
        "total_score": s.total_score,
        "technical_score": s.technical_score,
        "component_score": s.component_score,
        "deductions": s.deductions,
        "components": s.components,
        "elements": s.elements,
    }


@get("/{score_id:int}/elements")
async def get_score_elements(score_id: int, session: AsyncSession) -> list[dict]:
    score = await session.get(Score, score_id)
    if not score:
        raise NotFoundException(f"Score {score_id} not found")
    return score.elements or []


router = Router(
    path="/api/scores",
    route_handlers=[list_scores, get_score_elements],
    dependencies={"session": Provide(get_session)},
)
