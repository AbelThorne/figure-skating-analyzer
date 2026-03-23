"""Club-level statistics endpoints."""

from collections import defaultdict
from typing import Optional

from litestar import Router, get
from litestar.di import Provide
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_session
from app.models.app_settings import AppSettings
from app.models.category_result import CategoryResult
from app.models.competition import Competition
from app.models.skater import Skater


async def _get_club_short(session: AsyncSession, club: Optional[str]) -> Optional[str]:
    if club:
        return club
    result = await session.execute(select(AppSettings).limit(1))
    settings = result.scalar_one_or_none()
    return settings.club_short if settings else None


async def _get_current_season(session: AsyncSession) -> Optional[str]:
    result = await session.execute(select(AppSettings).limit(1))
    settings = result.scalar_one_or_none()
    return settings.current_season if settings else None


@get("/progression-ranking")
async def progression_ranking(
    session: AsyncSession,
    season: Optional[str] = None,
    club: Optional[str] = None,
    skating_level: Optional[str] = None,
    age_group: Optional[str] = None,
    gender: Optional[str] = None,
) -> list[dict]:
    club_short = await _get_club_short(session, club)
    if not season:
        season = await _get_current_season(session)

    stmt = (
        select(CategoryResult)
        .join(CategoryResult.competition)
        .join(CategoryResult.skater)
        .options(selectinload(CategoryResult.skater), selectinload(CategoryResult.competition))
        .where(CategoryResult.combined_total.isnot(None))
        .order_by(Competition.date.asc())
    )

    if season:
        stmt = stmt.where(Competition.season == season)
    if club_short:
        stmt = stmt.where(func.upper(Skater.club) == club_short.upper())
    if skating_level:
        stmt = stmt.where(CategoryResult.skating_level == skating_level)
    if age_group:
        stmt = stmt.where(CategoryResult.age_group == age_group)
    if gender:
        stmt = stmt.where(CategoryResult.gender == gender)

    result = await session.execute(stmt)
    rows = result.scalars().all()

    groups: dict[tuple, list] = defaultdict(list)
    for cr in rows:
        key = (cr.skater_id, cr.skating_level, cr.age_group)
        groups[key].append(cr)

    ranking = []
    for (skater_id, level, age), entries in groups.items():
        if len(entries) < 2:
            continue
        first = entries[0]
        last = entries[-1]
        skater = first.skater
        ranking.append({
            "skater_id": skater_id,
            "skater_name": f"{skater.first_name} {skater.last_name}",
            "skating_level": level,
            "age_group": age,
            "gender": first.gender,
            "first_tss": first.combined_total,
            "last_tss": last.combined_total,
            "tss_gain": round(last.combined_total - first.combined_total, 2),
            "competitions_count": len(entries),
            "sparkline": [
                {
                    "date": e.competition.date if e.competition else None,
                    "value": e.combined_total,
                }
                for e in entries
            ],
        })

    ranking.sort(key=lambda x: (-x["tss_gain"], -x["last_tss"]))
    return ranking


router = Router(
    path="/api/stats",
    route_handlers=[progression_ranking],
    dependencies={"session": Provide(get_session)},
)
