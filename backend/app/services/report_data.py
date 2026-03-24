from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Optional

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.competition import Competition
from app.models.score import Score
from app.models.skater import Skater
from app.models.category_result import CategoryResult
from app.models.app_settings import AppSettings
from app.config import CLUB_NAME, CLUB_SHORT


@dataclass
class SkaterReportResult:
    competition_name: str
    competition_date: Optional[date]
    category: Optional[str]
    segment: str
    rank: Optional[int]
    tss: Optional[float]
    tes: Optional[float]
    pcs: Optional[float]
    deductions: Optional[float]


@dataclass
class ElementStats:
    name: str
    attempts: int
    avg_goe: float


@dataclass
class ElementSummary:
    most_attempted: list[ElementStats]
    best_goe: list[ElementStats]
    total_elements_tracked: int


@dataclass
class SkaterReportData:
    skater_name: str
    club: Optional[str]
    season: str
    generated_at: str
    personal_bests: dict[str, dict]
    results: list[SkaterReportResult]
    element_summary: Optional[ElementSummary]


async def get_skater_report_data(
    skater_id: int,
    season: str,
    session: AsyncSession,
) -> SkaterReportData:
    skater_row = await session.get(Skater, skater_id)
    skater_name = skater_row.display_name if skater_row else f"Patineur #{skater_id}"
    club = skater_row.club if skater_row else None

    stmt = (
        select(Score, Competition.name, Competition.date)
        .join(Competition, Score.competition_id == Competition.id)
        .where(Score.skater_id == skater_id, Competition.season == season)
        .order_by(Competition.date, Score.segment)
    )
    rows = (await session.execute(stmt)).all()

    results: list[SkaterReportResult] = []
    personal_bests: dict[str, dict] = {}

    for score, comp_name, comp_date in rows:
        results.append(SkaterReportResult(
            competition_name=comp_name,
            competition_date=comp_date,
            category=score.category,
            segment=score.segment,
            rank=score.rank,
            tss=score.total_score,
            tes=score.technical_score,
            pcs=score.component_score,
            deductions=score.deductions,
        ))
        tss = score.total_score or 0
        seg = score.segment
        if seg not in personal_bests or tss > personal_bests[seg]["tss"]:
            personal_bests[seg] = {
                "tss": score.total_score,
                "tes": score.technical_score,
                "pcs": score.component_score,
                "competition": comp_name,
                "date": comp_date,
            }

    element_summary = _compute_element_summary([score for score, _, _ in rows])

    return SkaterReportData(
        skater_name=skater_name,
        club=club,
        season=season,
        generated_at=datetime.now().strftime("%d/%m/%Y %H:%M"),
        personal_bests=personal_bests,
        results=results,
        element_summary=element_summary,
    )


def _compute_element_summary(scores: list[Score]) -> Optional[ElementSummary]:
    element_data: dict[str, list[float]] = {}
    for score in scores:
        if not score.elements:
            continue
        elements_list = score.elements if isinstance(score.elements, list) else score.elements.get("elements", [])
        for el in elements_list:
            name = el.get("name", "")
            goe = el.get("goe")
            if name and goe is not None:
                element_data.setdefault(name, []).append(float(goe))
    if not element_data:
        return None
    stats = [
        ElementStats(name=name, attempts=len(goes), avg_goe=round(sum(goes) / len(goes), 2))
        for name, goes in element_data.items()
    ]
    most_attempted = sorted(stats, key=lambda s: s.attempts, reverse=True)[:5]
    best_goe = sorted([s for s in stats if s.attempts >= 2], key=lambda s: s.avg_goe, reverse=True)[:5]
    return ElementSummary(most_attempted=most_attempted, best_goe=best_goe, total_elements_tracked=sum(s.attempts for s in stats))


@dataclass
class ClubReportData:
    club_name: str
    club_logo_path: Optional[str]
    season: str
    generated_at: str
    stats: dict
    skaters_summary: list[dict]
    medals: list[dict]
    most_improved: list[dict]


async def get_club_report_data(
    season: str,
    session: AsyncSession,
) -> ClubReportData:
    settings = (await session.execute(select(AppSettings))).scalar_one_or_none()
    club_name = CLUB_NAME or (settings.club_name if settings else "Club")
    club_short = CLUB_SHORT or club_name
    club_logo = settings.logo_path if settings else None

    club_skaters_stmt = select(Skater).where(func.lower(Skater.club) == club_short.lower())
    club_skaters = (await session.execute(club_skaters_stmt)).scalars().all()
    club_skater_ids = [s.id for s in club_skaters]

    if not club_skater_ids:
        return ClubReportData(
            club_name=club_name, club_logo_path=club_logo, season=season,
            generated_at=datetime.now().strftime("%d/%m/%Y %H:%M"),
            stats={"active_skaters": 0, "competitions_tracked": 0, "total_programs": 0, "total_podiums": 0},
            skaters_summary=[], medals=[], most_improved=[],
        )

    scores_stmt = (
        select(Score, Competition.name, Competition.date)
        .join(Competition, Score.competition_id == Competition.id)
        .where(Score.skater_id.in_(club_skater_ids), Competition.season == season)
        .order_by(Competition.date)
    )
    score_rows = (await session.execute(scores_stmt)).all()

    cr_stmt = (
        select(CategoryResult)
        .join(Competition, CategoryResult.competition_id == Competition.id)
        .options(selectinload(CategoryResult.competition), selectinload(CategoryResult.skater))
        .where(CategoryResult.skater_id.in_(club_skater_ids), Competition.season == season)
        .order_by(Competition.date)
    )
    cat_results = (await session.execute(cr_stmt)).scalars().all()

    active_ids = set()
    comp_ids = set()
    for score, comp_name, comp_date in score_rows:
        active_ids.add(score.skater_id)
        comp_ids.add(score.competition_id)

    medals_list = []
    podium_count = 0
    for cr in cat_results:
        if cr.overall_rank and cr.overall_rank <= 3:
            podium_count += 1
            medals_list.append({
                "skater_name": cr.skater.display_name,
                "competition_name": cr.competition.name,
                "competition_date": cr.competition.date,
                "category": cr.category,
                "rank": cr.overall_rank,
            })

    skater_map: dict[int, dict] = {}
    for score, comp_name, comp_date in score_rows:
        sid = score.skater_id
        if sid not in skater_map:
            sk = next(s for s in club_skaters if s.id == sid)
            skater_map[sid] = {
                "name": sk.display_name, "category": score.category, "comp_ids": set(),
                "best_tss": 0.0, "best_tes": 0.0, "best_pcs": 0.0,
                "first_tss": None, "first_date": None, "last_tss": None, "last_date": None,
            }
        entry = skater_map[sid]
        entry["comp_ids"].add(score.competition_id)
        entry["category"] = score.category
        tss = score.total_score or 0
        tes = score.technical_score or 0
        pcs = score.component_score or 0
        if tss > entry["best_tss"]: entry["best_tss"] = tss
        if tes > entry["best_tes"]: entry["best_tes"] = tes
        if pcs > entry["best_pcs"]: entry["best_pcs"] = pcs
        score_date = comp_date or score.event_date
        if entry["first_date"] is None or (score_date and score_date < entry["first_date"]):
            entry["first_date"] = score_date
            entry["first_tss"] = tss
        if entry["last_date"] is None or (score_date and score_date > entry["last_date"]):
            entry["last_date"] = score_date
            entry["last_tss"] = tss

    skaters_summary = sorted([
        {"name": v["name"], "category": v["category"], "competitions_entered": len(v["comp_ids"]),
         "best_tss": v["best_tss"], "best_tes": v["best_tes"], "best_pcs": v["best_pcs"]}
        for v in skater_map.values()
    ], key=lambda x: x["name"])

    improvements = []
    for v in skater_map.values():
        if v["first_tss"] is not None and v["last_tss"] is not None and v["first_date"] != v["last_date"]:
            delta = v["last_tss"] - v["first_tss"]
            improvements.append({"name": v["name"], "category": v["category"],
                                 "first_tss": v["first_tss"], "last_tss": v["last_tss"], "delta": round(delta, 2)})
    most_improved = sorted(improvements, key=lambda x: x["delta"], reverse=True)[:3]

    return ClubReportData(
        club_name=club_name, club_logo_path=club_logo, season=season,
        generated_at=datetime.now().strftime("%d/%m/%Y %H:%M"),
        stats={"active_skaters": len(active_ids), "competitions_tracked": len(comp_ids),
               "total_programs": len(score_rows), "total_podiums": podium_count},
        skaters_summary=skaters_summary, medals=medals_list, most_improved=most_improved,
    )
