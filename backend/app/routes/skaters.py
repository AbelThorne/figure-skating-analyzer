from __future__ import annotations

from typing import Optional

from litestar import Router, get
from litestar.di import Provide
from litestar.exceptions import NotFoundException
from sqlalchemy import func, select, union_all
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_session
from app.models.skater import Skater
from app.models.score import Score
from app.models.competition import Competition
from app.models.category_result import CategoryResult


@get("/")
async def list_skaters(session: AsyncSession, club: Optional[str] = None) -> list[dict]:
    stmt = select(Skater)
    if club:
        stmt = stmt.where(func.lower(Skater.club) == club.lower())
    result = await session.execute(stmt)
    skaters = sorted(result.scalars(), key=lambda s: (s.last_name.upper(), s.first_name.upper()))
    return [_skater_to_dict(s) for s in skaters]


@get("/{skater_id:int}")
async def get_skater(skater_id: int, session: AsyncSession) -> dict:
    skater = await session.get(Skater, skater_id)
    if not skater:
        raise NotFoundException(f"Skater {skater_id} not found")
    return _skater_to_dict(skater)


def _skater_to_dict(s: Skater) -> dict:
    return {
        "id": s.id,
        "first_name": s.first_name,
        "last_name": s.last_name,
        "nationality": s.nationality,
        "club": s.club,
        "birth_year": s.birth_year,
    }


@get("/{skater_id:int}/elements")
async def get_skater_elements(
    skater_id: int,
    session: AsyncSession,
    element_type: Optional[str] = None,
    season: Optional[str] = None,
) -> list[dict]:
    skater = await session.get(Skater, skater_id)
    if not skater:
        raise NotFoundException(f"Skater {skater_id} not found")

    stmt = (
        select(Score)
        .where(Score.skater_id == skater_id)
        .options(selectinload(Score.competition))
        .order_by(Competition.date)
        .join(Score.competition)
    )
    if season:
        stmt = stmt.where(Competition.season == season)

    result = await session.execute(stmt)
    scores = result.scalars().all()

    records = []
    for s in scores:
        if not s.elements:
            continue
        for element in s.elements:
            name = element.get("name", "")
            if element_type is not None and not name.lower().startswith(element_type.lower()):
                continue
            records.append({
                "score_id": s.id,
                "competition_id": s.competition_id,
                "competition_name": s.competition.name if s.competition else None,
                "competition_date": s.competition.date.isoformat() if s.competition and s.competition.date else None,
                "segment": s.segment,
                "category": s.category,
                "element_name": name,
                "base_value": element.get("base_value"),
                "goe": element.get("goe"),
                "judges": element.get("judge_goe") or element.get("judges"),
                "total": element.get("score") or element.get("total"),
                "markers": element.get("markers") or [],
            })
    return records


@get("/{skater_id:int}/scores")
async def get_skater_scores(skater_id: int, session: AsyncSession, season: Optional[str] = None) -> list[dict]:
    skater = await session.get(Skater, skater_id)
    if not skater:
        raise NotFoundException(f"Skater {skater_id} not found")

    stmt = (
        select(Score)
        .where(Score.skater_id == skater_id)
        .join(Score.competition)
        .options(selectinload(Score.competition))
        .order_by(Score.id)
    )
    if season:
        stmt = stmt.where(Competition.season == season)

    result = await session.execute(stmt)
    scores = result.scalars().all()
    return [
        {
            "id": s.id,
            "competition_id": s.competition_id,
            "competition_name": s.competition.name if s.competition else None,
            "competition_date": s.competition.date.isoformat() if s.competition and s.competition.date else None,
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
            "skating_level": s.skating_level,
            "age_group": s.age_group,
            "gender": s.gender,
            "event_date": s.event_date.isoformat() if s.event_date else None,
        }
        for s in scores
    ]


@get("/{skater_id:int}/category-results")
async def get_skater_category_results(skater_id: int, session: AsyncSession, season: Optional[str] = None) -> list[dict]:
    skater = await session.get(Skater, skater_id)
    if not skater:
        raise NotFoundException(f"Skater {skater_id} not found")

    stmt = (
        select(CategoryResult)
        .where(CategoryResult.skater_id == skater_id)
        .options(selectinload(CategoryResult.competition))
        .join(CategoryResult.competition)
        .order_by(Competition.date.desc())
    )
    if season:
        stmt = stmt.where(Competition.season == season)

    result = await session.execute(stmt)
    cat_results = result.scalars().all()
    return [
        {
            "id": cr.id,
            "competition_id": cr.competition_id,
            "competition_name": cr.competition.name if cr.competition else None,
            "competition_date": cr.competition.date.isoformat() if cr.competition and cr.competition.date else None,
            "category": cr.category,
            "overall_rank": cr.overall_rank,
            "combined_total": cr.combined_total,
            "segment_count": cr.segment_count,
            "sp_rank": cr.sp_rank,
            "fs_rank": cr.fs_rank,
            "skating_level": cr.skating_level,
            "age_group": cr.age_group,
            "gender": cr.gender,
        }
        for cr in cat_results
    ]


@get("/{skater_id:int}/seasons")
async def get_skater_seasons(skater_id: int, session: AsyncSession) -> list[str]:
    skater = await session.get(Skater, skater_id)
    if not skater:
        raise NotFoundException(f"Skater {skater_id} not found")

    score_comp_ids = select(Score.competition_id).where(Score.skater_id == skater_id)
    cat_comp_ids = select(CategoryResult.competition_id).where(CategoryResult.skater_id == skater_id)
    all_comp_ids = union_all(score_comp_ids, cat_comp_ids).subquery()

    stmt = (
        select(Competition.season)
        .join(all_comp_ids, Competition.id == all_comp_ids.c.competition_id)
        .where(Competition.season.isnot(None))
        .distinct()
        .order_by(Competition.season.desc())
    )
    result = await session.execute(stmt)
    return [row[0] for row in result.all()]


router = Router(
    path="/api/skaters",
    route_handlers=[list_skaters, get_skater, get_skater_elements, get_skater_scores, get_skater_category_results, get_skater_seasons],
    dependencies={"session": Provide(get_session)},
)
