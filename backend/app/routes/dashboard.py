from __future__ import annotations

from typing import Optional

from litestar import Request, Router, get
from litestar.di import Provide
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth.guards import reject_skater_role
from app.config import CLUB_NAME, CLUB_SHORT
from app.database import get_session
from app.models.competition import Competition
from app.models.score import Score
from app.models.skater import Skater
from app.models.category_result import CategoryResult


@get("/")
async def get_dashboard(
    request: Request,
    session: AsyncSession,
    season: Optional[str] = None,
) -> dict:
    reject_skater_role(request)
    club_name = CLUB_SHORT

    # Build a base subquery: scores joined with skaters (and competitions for season filter)
    # that belong to the club.

    # --- Helper: base statement selecting Score joined to Skater and Competition ---
    def _base_stmt():
        stmt = (
            select(Score)
            .join(Score.skater)
            .join(Score.competition)
        )
        if club_name != "":
            stmt = stmt.where(func.lower(Skater.club) == club_name.lower())
        if season is not None:
            stmt = stmt.where(Competition.season == season)
        return stmt

    # --- active_skaters ---
    active_skaters_stmt = (
        select(func.count(func.distinct(Score.skater_id)))
        .join(Score.skater)
        .join(Score.competition)
    )
    if club_name != "":
        active_skaters_stmt = active_skaters_stmt.where(
            func.lower(Skater.club) == club_name.lower()
        )
    if season is not None:
        active_skaters_stmt = active_skaters_stmt.where(Competition.season == season)

    active_skaters_result = await session.execute(active_skaters_stmt)
    active_skaters = active_skaters_result.scalar() or 0

    # --- competitions_tracked ---
    competitions_tracked_stmt = (
        select(func.count(func.distinct(Score.competition_id)))
        .join(Score.skater)
        .join(Score.competition)
    )
    if club_name != "":
        competitions_tracked_stmt = competitions_tracked_stmt.where(
            func.lower(Skater.club) == club_name.lower()
        )
    if season is not None:
        competitions_tracked_stmt = competitions_tracked_stmt.where(
            Competition.season == season
        )

    competitions_tracked_result = await session.execute(competitions_tracked_stmt)
    competitions_tracked = competitions_tracked_result.scalar() or 0

    # --- total_programs ---
    total_programs_stmt = (
        select(func.count(Score.id))
        .join(Score.skater)
        .join(Score.competition)
    )
    if club_name != "":
        total_programs_stmt = total_programs_stmt.where(
            func.lower(Skater.club) == club_name.lower()
        )
    if season is not None:
        total_programs_stmt = total_programs_stmt.where(Competition.season == season)

    total_programs_result = await session.execute(total_programs_stmt)
    total_programs = total_programs_result.scalar() or 0

    # --- medals (overall_rank <= 3, from category results) ---
    medals_stmt = (
        select(CategoryResult)
        .options(selectinload(CategoryResult.skater), selectinload(CategoryResult.competition))
        .join(CategoryResult.skater)
        .join(CategoryResult.competition)
        .where(CategoryResult.overall_rank <= 3)
        .order_by(CategoryResult.overall_rank)
    )
    if club_name != "":
        medals_stmt = medals_stmt.where(
            func.lower(Skater.club) == club_name.lower()
        )
    if season is not None:
        medals_stmt = medals_stmt.where(Competition.season == season)

    medals_result = await session.execute(medals_stmt)
    medal_rows = medals_result.scalars().all()
    medals = [
        {
            "skater_name": cr.skater.display_name if cr.skater else None,
            "rank": cr.overall_rank,
            "competition_name": cr.competition.name if cr.competition else None,
            "category": cr.category,
            "combined_total": cr.combined_total,
            "segment_count": cr.segment_count,
        }
        for cr in medal_rows
    ]

    # --- top_scores (up to 5, highest combined_total from category results) ---
    top_scores_stmt = (
        select(CategoryResult)
        .options(selectinload(CategoryResult.skater), selectinload(CategoryResult.competition))
        .join(CategoryResult.skater)
        .join(CategoryResult.competition)
        .where(CategoryResult.combined_total.isnot(None))
        .order_by(CategoryResult.combined_total.desc())
        .limit(5)
    )
    if club_name != "":
        top_scores_stmt = top_scores_stmt.where(
            func.lower(Skater.club) == club_name.lower()
        )
    if season is not None:
        top_scores_stmt = top_scores_stmt.where(Competition.season == season)

    top_scores_result = await session.execute(top_scores_stmt)
    top_score_rows = top_scores_result.scalars().all()
    top_scores = [
        {
            "skater_id": cr.skater_id,
            "skater_name": cr.skater.display_name if cr.skater else None,
            "tss": cr.combined_total,
            "competition_name": cr.competition.name if cr.competition else None,
            "competition_date": (
                cr.competition.date.isoformat()
                if cr.competition and cr.competition.date
                else None
            ),
            "category": cr.category,
        }
        for cr in top_score_rows
    ]

    # --- most_improved (up to 3) ---
    # Use category results (combined totals) ordered by competition date asc,
    # compute first/last combined total per skater.
    all_cat_stmt = (
        select(CategoryResult)
        .options(selectinload(CategoryResult.skater), selectinload(CategoryResult.competition))
        .join(CategoryResult.skater)
        .join(CategoryResult.competition)
        .where(CategoryResult.combined_total.isnot(None))
        .order_by(Competition.date.asc())
    )
    if club_name != "":
        all_cat_stmt = all_cat_stmt.where(
            func.lower(Skater.club) == club_name.lower()
        )
    if season is not None:
        all_cat_stmt = all_cat_stmt.where(Competition.season == season)

    all_cat_result = await session.execute(all_cat_stmt)
    all_cat_rows = all_cat_result.scalars().all()

    # Group by skater_id, track first and last combined total (chronological)
    skater_tss: dict[int, dict] = {}
    for cr in all_cat_rows:
        sid = cr.skater_id
        total = cr.combined_total
        if total is None:
            continue
        if sid not in skater_tss:
            skater_tss[sid] = {
                "skater_id": sid,
                "skater_name": cr.skater.display_name if cr.skater else None,
                "first_tss": total,
                "last_tss": total,
            }
        else:
            skater_tss[sid]["last_tss"] = total

    improved_list = []
    for sid, data in skater_tss.items():
        gain = data["last_tss"] - data["first_tss"]
        improved_list.append(
            {
                "skater_name": data["skater_name"],
                "skater_id": sid,
                "tss_gain": gain,
                "first_tss": data["first_tss"],
                "last_tss": data["last_tss"],
            }
        )

    improved_list.sort(key=lambda x: x["tss_gain"], reverse=True)
    most_improved = improved_list[:3]

    # --- recent_competitions (last 3 by date desc) ---
    recent_comp_stmt = (
        select(Competition)
        .join(Score, Score.competition_id == Competition.id)
        .join(Skater, Score.skater_id == Skater.id)
        .distinct()
        .order_by(Competition.date.desc())
        .limit(3)
    )
    if club_name != "":
        recent_comp_stmt = recent_comp_stmt.where(
            func.lower(Skater.club) == club_name.lower()
        )
    if season is not None:
        recent_comp_stmt = recent_comp_stmt.where(Competition.season == season)

    recent_comp_result = await session.execute(recent_comp_stmt)
    recent_comp_rows = recent_comp_result.scalars().all()
    recent_competitions = [
        {
            "id": c.id,
            "name": c.name,
            "date": c.date.isoformat() if c.date else None,
            "season": c.season,
            "discipline": c.discipline,
        }
        for c in recent_comp_rows
    ]

    return {
        "club_name": CLUB_NAME,
        "season": season,
        "active_skaters": active_skaters,
        "competitions_tracked": competitions_tracked,
        "total_programs": total_programs,
        "medals": medals,
        "top_scores": top_scores,
        "most_improved": most_improved,
        "recent_competitions": recent_competitions,
    }


router = Router(
    path="/api/dashboard",
    route_handlers=[get_dashboard],
    dependencies={"session": Provide(get_session)},
)
