"""Club-level statistics endpoints."""

import statistics
from collections import defaultdict
from typing import Optional

from litestar import Request, Router, get
from litestar.di import Provide
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth.guards import reject_skater_role
from app.database import get_session
from app.models.app_settings import AppSettings
from app.models.category_result import CategoryResult
from app.models.competition import Competition
from app.models.score import Score
from app.models.skater import Skater
from app.services.element_classifier import classify_element, extract_jump_type, extract_level
from app.services.competition_analysis import compute_competition_club_analysis


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
    request: Request,
    session: AsyncSession,
    season: Optional[str] = None,
    club: Optional[str] = None,
    skating_level: Optional[str] = None,
    age_group: Optional[str] = None,
    gender: Optional[str] = None,
) -> list[dict]:
    reject_skater_role(request)
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
            "tss_gain": round(last.combined_total - first.combined_total, 2) if len(entries) >= 2 else 0.0,
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


@get("/benchmarks")
async def benchmarks(
    request: Request,
    session: AsyncSession,
    skating_level: str,
    age_group: str,
    gender: str,
    season: Optional[str] = None,
) -> dict:
    reject_skater_role(request)
    stmt = (
        select(CategoryResult.combined_total)
        .join(CategoryResult.competition)
        .where(
            CategoryResult.combined_total.isnot(None),
            CategoryResult.skating_level == skating_level,
            CategoryResult.age_group == age_group,
            CategoryResult.gender == gender,
        )
    )
    if season:
        stmt = stmt.where(Competition.season == season)

    result = await session.execute(stmt)
    totals = sorted([row[0] for row in result.all()])

    if not totals:
        return {
            "skating_level": skating_level,
            "age_group": age_group,
            "gender": gender,
            "data_points": 0,
            "min": None, "max": None, "median": None, "p25": None, "p75": None,
        }

    n = len(totals)
    return {
        "skating_level": skating_level,
        "age_group": age_group,
        "gender": gender,
        "data_points": n,
        "min": totals[0],
        "max": totals[-1],
        "median": round(statistics.median(totals), 2),
        "p25": round(statistics.quantiles(totals, n=4)[0], 2) if n >= 2 else totals[0],
        "p75": round(statistics.quantiles(totals, n=4)[2], 2) if n >= 2 else totals[-1],
    }


@get("/element-mastery")
async def element_mastery(
    request: Request,
    session: AsyncSession,
    season: Optional[str] = None,
    club: Optional[str] = None,
    skating_level: Optional[str] = None,
    age_group: Optional[str] = None,
    gender: Optional[str] = None,
) -> dict:
    reject_skater_role(request)
    club_short = await _get_club_short(session, club)
    if not season:
        season = await _get_current_season(session)

    stmt = (
        select(Score)
        .join(Score.competition)
        .join(Score.skater)
        .where(Score.elements.isnot(None))
    )
    if season:
        stmt = stmt.where(Competition.season == season)
    if club_short:
        stmt = stmt.where(func.upper(Skater.club) == club_short.upper())
    if skating_level:
        stmt = stmt.where(Score.skating_level == skating_level)
    if age_group:
        stmt = stmt.where(Score.age_group == age_group)
    if gender:
        stmt = stmt.where(Score.gender == gender)

    result = await session.execute(stmt)
    scores = result.scalars().all()

    jump_stats: dict[str, dict] = defaultdict(lambda: {"attempts": 0, "positive": 0, "negative": 0, "neutral": 0, "goe_sum": 0.0})
    spin_stats: dict[str, dict] = defaultdict(lambda: {"attempts": 0, "levels": defaultdict(int), "goe_sum": 0.0})
    step_stats: dict[str, dict] = defaultdict(lambda: {"attempts": 0, "levels": defaultdict(int), "goe_sum": 0.0})

    for score in scores:
        if not score.elements:
            continue
        for el in score.elements:
            name = el.get("name", "")
            goe = el.get("goe", 0) or 0
            el_type = classify_element(name)

            if el_type == "jump":
                jt = extract_jump_type(name)
                if jt:
                    jump_stats[jt]["attempts"] += 1
                    jump_stats[jt]["goe_sum"] += goe
                    if goe > 0:
                        jump_stats[jt]["positive"] += 1
                    elif goe < 0:
                        jump_stats[jt]["negative"] += 1
                    else:
                        jump_stats[jt]["neutral"] += 1
            elif el_type == "spin":
                base = name.rstrip("0123456789B")
                level = extract_level(name)
                spin_stats[base]["attempts"] += 1
                spin_stats[base]["levels"][str(level)] += 1
                spin_stats[base]["goe_sum"] += goe
            elif el_type == "step":
                base = name.rstrip("0123456789B")
                level = extract_level(name)
                step_stats[base]["attempts"] += 1
                step_stats[base]["levels"][str(level)] += 1
                step_stats[base]["goe_sum"] += goe

    jump_order = ["1A", "1T", "1S", "1Lo", "1F", "1Lz", "2T", "2S", "2Lo", "2F", "2Lz", "2A", "3T", "3S", "3Lo", "3F", "3Lz", "3A", "4T", "4S", "4Lo", "4F", "4Lz", "4A"]
    jump_order_map = {j: i for i, j in enumerate(jump_order)}

    jumps = []
    for jt, stats in sorted(jump_stats.items(), key=lambda x: jump_order_map.get(x[0], 99)):
        n = stats["attempts"]
        jumps.append({
            "jump_type": jt,
            "attempts": n,
            "positive_goe_pct": round(stats["positive"] / n * 100, 1),
            "negative_goe_pct": round(stats["negative"] / n * 100, 1),
            "neutral_goe_pct": round(stats["neutral"] / n * 100, 1),
            "avg_goe": round(stats["goe_sum"] / n, 2),
        })

    def _format_level_stats(stats_dict):
        items = []
        for base, stats in sorted(stats_dict.items()):
            n = stats["attempts"]
            level_dist = {str(i): stats["levels"].get(str(i), 0) for i in range(5)}
            items.append({
                "element_type": base,
                "attempts": n,
                "level_distribution": level_dist,
                "avg_goe": round(stats["goe_sum"] / n, 2),
            })
        return items

    return {
        "jumps": jumps,
        "spins": _format_level_stats(spin_stats),
        "steps": _format_level_stats(step_stats),
    }


@get("/competition-club-analysis")
async def competition_club_analysis(
    request: Request,
    session: AsyncSession,
    competition_id: int,
    club: Optional[str] = None,
) -> dict:
    reject_skater_role(request)
    club_short = await _get_club_short(session, club)
    if not club_short:
        return {"error": "No club configured"}
    return await compute_competition_club_analysis(session, competition_id, club_short)


router = Router(
    path="/api/stats",
    route_handlers=[progression_ranking, benchmarks, element_mastery, competition_club_analysis],
    dependencies={"session": Provide(get_session)},
)
