"""Competition club analysis service."""

from collections import defaultdict

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.category_result import CategoryResult
from app.models.competition import Competition


def compute_club_challenge_points(rank: int, total_in_category: int) -> dict:
    """Compute club challenge points for a skater at a given rank.

    Base points: max(1, min(11 - rank, total - rank + 1))
    - Counts backwards from last place (total - rank + 1)
    - Capped by rank position (11 - rank gives max 10 for rank 1, max 1 for rank 10+)
    - Minimum 1 point for participation

    Podium bonus: rank 1 -> +3, rank 2 -> +2, rank 3 -> +1.
    """
    base = max(1, min(11 - rank, total_in_category - rank + 1))
    podium = {1: 3, 2: 2, 3: 1}.get(rank, 0)
    return {"base": base, "podium": podium, "total": base + podium}


async def compute_competition_club_analysis(
    session: AsyncSession,
    competition_id: int,
    club: str,
) -> dict:
    """Compute full club analysis for a given competition."""
    comp_result = await session.execute(
        select(Competition).where(Competition.id == competition_id)
    )
    competition = comp_result.scalar_one()

    stmt = (
        select(CategoryResult)
        .where(CategoryResult.competition_id == competition_id)
        .options(selectinload(CategoryResult.skater))
        .join(CategoryResult.skater)
    )
    result = await session.execute(stmt)
    all_results = result.scalars().all()

    by_category: dict[str, list[CategoryResult]] = defaultdict(list)
    for cr in all_results:
        by_category[cr.category].append(cr)

    for cat_results in by_category.values():
        cat_results.sort(key=lambda cr: cr.overall_rank or 999)

    club_upper = club.upper()

    # Club Challenge
    club_points: dict[str, dict] = defaultdict(lambda: {"total": 0, "podium": 0})
    category_breakdown = []

    for category, cat_results in sorted(by_category.items()):
        n = len(cat_results)
        cat_clubs: dict[str, dict] = defaultdict(lambda: {"points": 0, "podium_points": 0})
        club_skaters_detail = []

        for cr in cat_results:
            if cr.overall_rank is None:
                continue
            skater_club = (cr.club or cr.skater.club or "").upper()
            pts = compute_club_challenge_points(cr.overall_rank, n)
            cat_clubs[skater_club]["points"] += pts["total"]
            cat_clubs[skater_club]["podium_points"] += pts["podium"]
            club_points[skater_club]["total"] += pts["total"]
            club_points[skater_club]["podium"] += pts["podium"]

            if skater_club == club_upper:
                club_skaters_detail.append({
                    "skater_name": f"{cr.skater.first_name} {cr.skater.last_name}",
                    "rank": cr.overall_rank,
                    "base_points": pts["base"],
                    "podium_points": pts["podium"],
                    "total_points": pts["total"],
                })

        category_breakdown.append({
            "category": category,
            "clubs": [
                {"club": c, "points": v["points"], "podium_points": v["podium_points"]}
                for c, v in sorted(cat_clubs.items())
            ],
            "club_skaters": club_skaters_detail,
        })

    ranking = []
    for c, pts in club_points.items():
        ranking.append({
            "club": c,
            "total_points": pts["total"],
            "podium_points": pts["podium"],
            "is_my_club": c == club_upper,
        })
    ranking.sort(key=lambda x: (-x["total_points"], -x["podium_points"]))
    for i, entry in enumerate(ranking):
        entry["rank"] = i + 1

    club_results = [cr for cr in all_results if (cr.skater.club or "").upper() == club_upper]
    club_skater_ids = {cr.skater_id for cr in club_results}

    # PB detection
    pb_skater_ids: set[int] = set()
    for cr in club_results:
        prior_stmt = (
            select(func.max(CategoryResult.combined_total))
            .join(CategoryResult.competition)
            .where(
                CategoryResult.skater_id == cr.skater_id,
                CategoryResult.category == cr.category,
                CategoryResult.competition_id != competition_id,
                Competition.date < competition.date,
                CategoryResult.combined_total.isnot(None),
            )
        )
        prior_result = await session.execute(prior_stmt)
        prev_best = prior_result.scalar()
        if prev_best is not None and cr.combined_total is not None and cr.combined_total > prev_best:
            pb_skater_ids.add(cr.skater_id)

    # Medals
    medals = []
    for cr in club_results:
        if cr.overall_rank and cr.overall_rank <= 3:
            medals.append({
                "skater_id": cr.skater_id,
                "skater_name": f"{cr.skater.first_name} {cr.skater.last_name}",
                "category": cr.category,
                "rank": cr.overall_rank,
                "combined_total": cr.combined_total,
            })
    medals.sort(key=lambda m: (m["rank"], m["category"]))

    # Category coverage
    categories = []
    for category, cat_results in sorted(by_category.items()):
        club_count = sum(1 for cr in cat_results if (cr.skater.club or "").upper() == club_upper)
        categories.append({
            "category": category,
            "club_skaters": club_count,
            "total_skaters": len(cat_results),
        })

    # Detailed results
    results = []
    for cr in club_results:
        total_in_cat = len(by_category.get(cr.category, []))
        results.append({
            "skater_id": cr.skater_id,
            "skater_name": f"{cr.skater.first_name} {cr.skater.last_name}",
            "category": cr.category,
            "overall_rank": cr.overall_rank,
            "total_skaters": total_in_cat,
            "combined_total": cr.combined_total,
            "is_pb": cr.skater_id in pb_skater_ids,
            "medal": cr.overall_rank if cr.overall_rank and cr.overall_rank <= 3 else None,
        })
    results.sort(key=lambda r: (r["category"], r["overall_rank"] or 999))

    kpis = {
        "skaters_entered": len(club_skater_ids),
        "total_medals": len(medals),
        "personal_bests": len(pb_skater_ids),
        "categories_entered": sum(1 for c in categories if c["club_skaters"] > 0),
        "categories_total": len(by_category),
    }

    return {
        "competition": {
            "id": competition.id,
            "name": competition.name,
            "date": competition.date.isoformat() if competition.date else None,
            "season": competition.season,
        },
        "club_name": club,
        "kpis": kpis,
        "club_challenge": {"ranking": ranking, "category_breakdown": category_breakdown},
        "medals": medals,
        "categories": categories,
        "results": results,
    }
