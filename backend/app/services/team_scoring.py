"""Team scoring calculation for France Clubs competitions.

Each skater's score is compared to a reference median for their category/division:
    points = 10 * (score / median)

Titular status (is_titular) is stored per score in DB. When NULL (not yet set),
auto-initialization assigns the first 6 skaters per division per club (by
starting_number) as titular and the rest as substitutes.

Division rankings rank clubs within each division (D1, D2, D3) by total points.

Challenge scoring converts each division rank into challenge points via a lookup
table (CSNPA Book Chapter 4, Section E.3). The challenge total is the sum across
all divisions. Tiebreaker: best D1 rank, then D2, then D3.
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


def _normalize_couple_club(club: str | None, is_couple: bool) -> str | None:
    """For couple/pair entries, take only the first club if two are listed.

    France Clubs rules require both partners to compete for the same club.
    Some scraped sources concatenate both clubs as "Club A / Club B"; this
    function normalises that to just the first club name.
    """
    if is_couple and club and " / " in club:
        return club.split(" / ", 1)[0].strip() or None
    return club

# Max titular skaters per division per club
MAX_TITULAR_PER_DIVISION = 6
MAX_TITULAR_PER_CATEGORY = 2
MAX_SUBSTITUTES_PER_DIVISION = 6
MAX_TITULAR_TOTAL = 18

# Challenge points tables (CSNPA Book Ch.4 E.3)
# Key = division, value = list where index 0 = 1st place points, etc.
CHALLENGE_POINTS: dict[str, list[int]] = {
    "D1": [35, 32, 29, 26, 23, 20, 19, 18, 17, 16, 15, 14, 13, 12, 11, 10, 9, 8, 7, 6],
    "D2": [30, 28, 26, 24, 22, 20, 19, 18, 17, 16, 15, 14, 13, 12, 11, 10, 9, 8, 7, 6],
    "D3": [25, 24, 23, 22, 21, 20, 19, 18, 17, 16, 15, 14, 13, 12, 11, 10, 9, 8, 7, 6],
}


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

    For each division per club, assigns titulaires respecting:
    - Max 6 titulaires per division per club
    - Max 2 titulaires per category per club (within a division)
    Scores are sorted by starting_number then rank (best first).
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
        skater = score.skater
        is_couple = skater and not skater.first_name and " / " in (skater.last_name or "")
        raw_club = score.club or (skater.club if skater else None)
        club = _normalize_couple_club(raw_club, bool(is_couple))
        if not club:
            continue
        groups[(club, division)].append(score)

    for (_club, _div), group_scores in groups.items():
        # Sort by starting_number (None last), then rank (None last)
        group_scores.sort(key=lambda s: (
            s.starting_number if s.starting_number is not None else 9999,
            s.rank if s.rank is not None else 9999,
        ))
        titular_count = 0
        cat_titular_count: dict[str, int] = defaultdict(int)
        for score in group_scores:
            cat = score.category or ""
            if titular_count < MAX_TITULAR_PER_DIVISION and cat_titular_count[cat] < MAX_TITULAR_PER_CATEGORY:
                score.is_titular = True
                titular_count += 1
                cat_titular_count[cat] += 1
            else:
                score.is_titular = False

    # Scores not in any D1/D2/D3 category: mark as titular (they won't count
    # for team scoring anyway, but the field should not remain NULL)
    for score in scores:
        if score.is_titular is None:
            score.is_titular = True

    await session.flush()


def _validate_teams(skater_entries: list[dict]) -> list[dict]:
    """Validate team composition rules (CSNPA Book Ch.4 D.1).

    Returns a list of violation dicts:
        {club, division, category (optional), rule, message}
    """
    violations: list[dict] = []

    # Group titular entries by (club, division)
    div_groups: dict[tuple[str, str], list[dict]] = defaultdict(list)
    # Group all entries (titular + sub) by (club, division) for sub count
    div_all: dict[tuple[str, str], list[dict]] = defaultdict(list)

    for entry in skater_entries:
        club = entry["club"]
        div = entry["division"]
        if not div:
            continue
        div_all[(club, div)].append(entry)
        if entry["is_titular"]:
            div_groups[(club, div)].append(entry)

    for (club, div), titular_entries in div_groups.items():
        # Rule: max 6 titular per division per club
        if len(titular_entries) > MAX_TITULAR_PER_DIVISION:
            violations.append({
                "club": club,
                "division": div,
                "category": None,
                "rule": "max_titular_per_division",
                "message": f"Max {MAX_TITULAR_PER_DIVISION} titulaires par division ({len(titular_entries)} trouves)",
            })

        # Rule: max 2 titular per category per club
        cat_counts: dict[str, int] = defaultdict(int)
        for e in titular_entries:
            cat_counts[e["category"] or "?"] += 1
        for cat, count in cat_counts.items():
            if count > MAX_TITULAR_PER_CATEGORY:
                violations.append({
                    "club": club,
                    "division": div,
                    "category": cat,
                    "rule": "max_titular_per_category",
                    "message": f"Max {MAX_TITULAR_PER_CATEGORY} titulaires par categorie ({count} trouves)",
                })

    # Rule: max 6 substitutes per division per club
    for (club, div), all_entries in div_all.items():
        sub_count = sum(1 for e in all_entries if e["is_remplacant"])
        if sub_count > MAX_SUBSTITUTES_PER_DIVISION:
            violations.append({
                "club": club,
                "division": div,
                "category": None,
                "rule": "max_substitutes_per_division",
                "message": f"Max {MAX_SUBSTITUTES_PER_DIVISION} remplacants par division ({sub_count} trouves)",
            })

    return violations


def compute_team_scores(
    scores: list[Score],
    medians: dict[str, dict[str, float]],
) -> dict:
    """Compute team scores for a France Clubs competition.

    Returns a dict with:
        - clubs: list of {club, total_points, skater_count, skaters: [...]}
        - division_rankings: dict of division -> ranked club list
        - challenge: list of challenge scoring entries
        - categories: list of {category, division, median, skaters: [...]}
        - violations: list of rule violations
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
        is_couple = not skater.first_name and " / " in (skater.last_name or "")
        club = _normalize_couple_club(score.club or skater.club or None, is_couple) or "\u2014"
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

    # --- Division rankings ---
    # Group entries by (division, club) and sum titular points
    div_club_points: dict[str, dict[str, dict]] = {}  # div -> club -> {points, count, skaters}
    for entry in skater_entries:
        div = entry["division"]
        if not div:
            continue
        club_name = entry["club"]
        if div not in div_club_points:
            div_club_points[div] = {}
        if club_name not in div_club_points[div]:
            div_club_points[div][club_name] = {"total_points": 0.0, "skater_count": 0, "skaters": []}
        bucket = div_club_points[div][club_name]
        bucket["skaters"].append(entry)
        if not entry["is_remplacant"] and entry["points"] is not None:
            bucket["total_points"] += entry["points"]
            bucket["skater_count"] += 1

    division_rankings: dict[str, list[dict]] = {}
    for div in sorted(div_club_points.keys()):
        div_clubs = []
        for club_name, bucket in div_club_points[div].items():
            div_clubs.append({
                "club": club_name,
                "total_points": round(bucket["total_points"], 2),
                "skater_count": bucket["skater_count"],
                "skaters": sorted(bucket["skaters"], key=lambda s: (s["category"] or "", -(s["points"] or 0))),
            })
        # Sort by total points desc, tiebreaker: more skaters first
        div_clubs.sort(key=lambda c: (-c["total_points"], -c["skater_count"]))
        for i, dc in enumerate(div_clubs, 1):
            dc["rank"] = i
        division_rankings[div] = div_clubs

    # --- Challenge scoring ---
    # For each club, look up their rank in each division and convert to challenge points
    challenge_map: dict[str, dict] = {}
    for div, div_clubs in division_rankings.items():
        points_table = CHALLENGE_POINTS.get(div, [])
        for dc in div_clubs:
            club_name = dc["club"]
            if club_name not in challenge_map:
                challenge_map[club_name] = {
                    "club": club_name,
                    "challenge_points": 0,
                    "division_ranks": {},
                    "division_points": {},
                }
            rank = dc["rank"]
            cp = points_table[rank - 1] if rank <= len(points_table) else max(points_table[-1] - (rank - len(points_table)), 1) if points_table else 0
            challenge_map[club_name]["division_ranks"][div] = rank
            challenge_map[club_name]["division_points"][div] = cp
            challenge_map[club_name]["challenge_points"] += cp

    # Sort by challenge points desc, tiebreaker: best D1 rank, then D2, then D3
    challenge = sorted(
        challenge_map.values(),
        key=lambda c: (
            -c["challenge_points"],
            c["division_ranks"].get("D1", 999),
            c["division_ranks"].get("D2", 999),
            c["division_ranks"].get("D3", 999),
        ),
    )
    for i, ch in enumerate(challenge, 1):
        ch["rank"] = i

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

    # --- Validate team composition ---
    violations = _validate_teams(skater_entries)

    return {
        "clubs": clubs,
        "division_rankings": division_rankings,
        "challenge": challenge,
        "categories": categories,
        "violations": violations,
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

    # Add last import timestamp from most recent completed job
    from app.models.job import Job
    job_stmt = (
        select(Job.completed_at)
        .where(Job.competition_id == competition_id)
        .where(Job.status == "completed")
        .order_by(Job.completed_at.desc())
        .limit(1)
    )
    job_result = await session.execute(job_stmt)
    last_completed = job_result.scalar_one_or_none()
    team_data["last_import_at"] = (last_completed.isoformat() + "Z") if last_completed else None

    return team_data
