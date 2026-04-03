"""Team scoring calculation for France Clubs competitions.

Each skater's score is compared to a reference median for their category/division:
    points = 10 * (score / median)

Titular status (is_titular) is stored per score in DB. When NULL (not yet set),
auto-initialization assigns the first 6 skaters per division per club (by
starting_number) as titular and the rest as substitutes.
"""

from __future__ import annotations

import logging
import re
from collections import defaultdict

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.competition import Competition
from app.models.score import Score

logger = logging.getLogger(__name__)

# Default medians per reference category per division (season 2025-2026)
DEFAULT_MEDIANS: dict[str, dict[str, float]] = {
    "Poussins dames": {"D1": 21.15, "D2": 16.23, "D3": 16.23},
    "Poussins messieurs": {"D1": 19.65, "D2": 16.23, "D3": 16.23},
    "Benjamins dames": {"D1": 26.00, "D2": 19.10, "D3": 19.10},
    "Benjamins messieurs": {"D1": 28.93, "D2": 18.22, "D3": 18.22},
    "Minimes dames": {"D1": 40.03, "D2": 26.59, "D3": 20.10},
    "Minimes messieurs": {"D1": 45.26, "D2": 20.98, "D3": 20.51},
    "Novices dames": {"D1": 44.39, "D2": 36.41, "D3": 19.54},
    "Novices messieurs": {"D1": 47.89, "D2": 36.49, "D3": 17.98},
    "Juniors dames": {"D1": 60.07, "D2": 37.65, "D3": 19.28},
    "Juniors messieurs": {"D1": 75.43, "D2": 43.17, "D3": 17.70},
    "Seniors dames": {"D1": 83.16, "D2": 39.06, "D3": 19.28},
    "Seniors messieurs": {"D1": 118.08, "D2": 43.18, "D3": 17.70},
    "Couples novices": {"D1": 41.54},
    "Couples juniors": {"D1": 56.23},
    "Couples seniors": {"D1": 101.95},
}

# Map age_group (from category_parser) to the plural form used in median keys
_AGE_PLURAL: dict[str, str] = {
    "Poussin": "Poussins",
    "Benjamin": "Benjamins",
    "Minime": "Minimes",
    "Novice": "Novices",
    "Junior": "Juniors",
    "Senior": "Seniors",
}

# Pattern to extract division directly from category name (e.g., "Novice D2 Femme")
_DIVISION_PATTERN = re.compile(r"\b(D[123])\b", re.IGNORECASE)

# Pattern to detect couple/pair categories
_COUPLE_PATTERN = re.compile(r"\bCouples?\b", re.IGNORECASE)

# Max titular skaters per division per club
MAX_TITULAR_PER_DIVISION = 6
MAX_TITULAR_TOTAL = 18


def _extract_division(category: str | None) -> str | None:
    """Extract division (D1/D2/D3) from category name only."""
    if category:
        m = _DIVISION_PATTERN.search(category)
        if m:
            return m.group(1).upper()
    return None


def _build_median_key(category: str | None, age_group: str | None, gender: str | None) -> str | None:
    """Build the key used to look up the median value.

    For couples: "Couples novices", "Couples juniors", "Couples seniors"
    For individuals: "Novices dames", "Juniors messieurs", etc.
    """
    if category and _COUPLE_PATTERN.search(category):
        if age_group and age_group in _AGE_PLURAL:
            return f"Couples {_AGE_PLURAL[age_group].lower()}"
        return None

    if not age_group or age_group not in _AGE_PLURAL:
        return None

    plural = _AGE_PLURAL[age_group]
    if gender == "Femme":
        return f"{plural} dames"
    elif gender == "Homme":
        return f"{plural} messieurs"
    return None


async def auto_init_titular(session: AsyncSession, competition_id: int) -> None:
    """Auto-initialize is_titular for scores that have NULL is_titular.

    For each division, group scores by club and mark the first 6 (by
    starting_number, then rank) as titular, the rest as substitutes.
    """
    stmt = (
        select(Score)
        .where(Score.competition_id == competition_id, Score.is_titular.is_(None))
        .options(selectinload(Score.skater))
        .order_by(Score.category, Score.starting_number, Score.rank)
    )
    result = await session.execute(stmt)
    scores = result.scalars().all()

    if not scores:
        return

    # Group by (club, division)
    groups: dict[tuple[str, str], list[Score]] = defaultdict(list)
    for score in scores:
        division = _extract_division(score.category)
        if not division:
            continue
        club = score.skater.club if score.skater else None
        if not club:
            continue
        groups[(club, division)].append(score)

    for (_club, _div), group_scores in groups.items():
        # Sort by starting_number (None last), then rank (None last)
        group_scores.sort(key=lambda s: (
            s.starting_number if s.starting_number is not None else 9999,
            s.rank if s.rank is not None else 9999,
        ))
        for i, score in enumerate(group_scores):
            score.is_titular = i < MAX_TITULAR_PER_DIVISION

    # Scores not in any D1/D2/D3 category: mark as titular (they won't count
    # for team scoring anyway, but the field should not remain NULL)
    for score in scores:
        if score.is_titular is None:
            score.is_titular = True

    await session.flush()


def compute_team_scores(
    scores: list[Score],
    medians: dict[str, dict[str, float]],
) -> dict:
    """Compute team scores for a France Clubs competition.

    Returns a dict with:
        - clubs: list of {club, total_points, skater_count, skaters: [...]}
        - categories: list of {category, division, median, skaters: [...]}
        - unmapped: list of categories that couldn't be mapped to a median
    """
    skater_entries: list[dict] = []
    unmapped_categories: set[str] = set()

    for score in scores:
        if score.total_score is None:
            continue

        skater = score.skater
        if not skater:
            continue

        full_name = (
            f"{skater.first_name} {skater.last_name}".strip()
            if skater.first_name
            else skater.last_name or ""
        )
        club = skater.club or "\u2014"
        # is_titular=None treated as titular (shouldn't happen after auto-init)
        is_remplacant = score.is_titular is False

        # Determine division — only keep D1/D2/D3 categories
        division = _extract_division(score.category)
        if not division:
            continue

        # Determine median key and look up median value
        median_key = _build_median_key(score.category, score.age_group, score.gender)

        median_value: float | None = None
        if median_key and division:
            div_medians = medians.get(median_key, {})
            median_value = div_medians.get(division)

        if median_value is None and median_key:
            unmapped_categories.add(f"{score.category or '?'} ({median_key}/{division})")
        elif median_value is None:
            unmapped_categories.add(score.category or "?")

        points: float | None = None
        if median_value and median_value > 0:
            points = round(10.0 * score.total_score / median_value, 2)

        skater_entries.append({
            "score_id": score.id,
            "skater_id": skater.id,
            "skater_name": full_name,
            "club": club,
            "category": score.category,
            "division": division,
            "median_key": median_key,
            "median_value": median_value,
            "total_score": score.total_score,
            "points": points,
            "is_remplacant": is_remplacant,
            "is_titular": score.is_titular is not False,
            "rank": score.rank,
            "starting_number": score.starting_number,
        })

    # Aggregate by club
    club_map: dict[str, dict] = {}
    for entry in skater_entries:
        club_name = entry["club"]
        if club_name not in club_map:
            club_map[club_name] = {"club": club_name, "total_points": 0.0, "skater_count": 0, "skaters": []}

        club_map[club_name]["skaters"].append(entry)
        if not entry["is_remplacant"] and entry["points"] is not None:
            club_map[club_name]["total_points"] += entry["points"]
            club_map[club_name]["skater_count"] += 1

    # Sort clubs by total points descending
    clubs = sorted(club_map.values(), key=lambda c: c["total_points"], reverse=True)
    for i, club in enumerate(clubs, 1):
        club["rank"] = i
        club["total_points"] = round(club["total_points"], 2)
        # Sort skaters within club by category then points
        club["skaters"].sort(key=lambda s: (s["category"] or "", -(s["points"] or 0)))

    # Build category summary
    cat_map: dict[str, dict] = {}
    for entry in skater_entries:
        cat_key = entry["category"] or "?"
        if cat_key not in cat_map:
            cat_map[cat_key] = {
                "category": cat_key,
                "division": entry["division"],
                "median_key": entry["median_key"],
                "median_value": entry["median_value"],
                "skaters": [],
            }
        cat_map[cat_key]["skaters"].append(entry)

    categories = sorted(cat_map.values(), key=lambda c: c["category"])

    return {
        "clubs": clubs,
        "categories": categories,
        "unmapped": sorted(unmapped_categories),
    }


async def get_team_scores(session: AsyncSession, competition_id: int) -> dict | None:
    """Load competition scores and compute team scores.

    Returns None if competition is not france_clubs type.
    """
    comp = await session.get(Competition, competition_id)
    if not comp or comp.competition_type != "france_clubs":
        return None

    # Auto-initialize titular status for scores that don't have it yet
    await auto_init_titular(session, competition_id)

    # Get medians: competition-specific, or fall back to defaults from AppSettings
    medians = comp.team_medians
    if not medians:
        from app.models.app_settings import AppSettings
        result = await session.execute(select(AppSettings).limit(1))
        settings = result.scalar_one_or_none()
        medians = (settings.default_team_medians if settings else None) or DEFAULT_MEDIANS

    # Load all scores for this competition with skater info
    stmt = (
        select(Score)
        .where(Score.competition_id == competition_id)
        .options(selectinload(Score.skater))
        .order_by(Score.category, Score.rank)
    )
    result = await session.execute(stmt)
    scores = result.scalars().all()

    team_data = compute_team_scores(scores, medians)
    team_data["medians"] = medians
    team_data["medians_source"] = "competition" if comp.team_medians else "default"
    return team_data
