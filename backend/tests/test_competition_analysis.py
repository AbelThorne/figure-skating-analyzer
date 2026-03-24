"""Tests for competition club analysis service."""

import pytest
import pytest_asyncio
from datetime import date
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.competition import Competition
from app.models.skater import Skater
from app.models.category_result import CategoryResult
from app.models.app_settings import AppSettings
from app.services.competition_analysis import (
    compute_club_challenge_points,
    compute_competition_club_analysis,
)


def test_single_skater_in_category():
    """1 skater: gets 1 base + 3 podium = 4."""
    result = compute_club_challenge_points(rank=1, total_in_category=1)
    assert result == {"base": 1, "podium": 3, "total": 4}


def test_two_skaters():
    """2 skaters: rank 1 gets 2+3=5, rank 2 gets 1+2=3."""
    r1 = compute_club_challenge_points(rank=1, total_in_category=2)
    assert r1 == {"base": 2, "podium": 3, "total": 5}
    r2 = compute_club_challenge_points(rank=2, total_in_category=2)
    assert r2 == {"base": 1, "podium": 2, "total": 3}


def test_four_skaters():
    """4 skaters: rank 1=7, rank 2=5, rank 3=3, rank 4=1."""
    assert compute_club_challenge_points(1, 4) == {"base": 4, "podium": 3, "total": 7}
    assert compute_club_challenge_points(2, 4) == {"base": 3, "podium": 2, "total": 5}
    assert compute_club_challenge_points(3, 4) == {"base": 2, "podium": 1, "total": 3}
    assert compute_club_challenge_points(4, 4) == {"base": 1, "podium": 0, "total": 1}


def test_ten_skaters_cap():
    """10 skaters: rank 1 gets 10+3=13, rank 10 gets 1."""
    assert compute_club_challenge_points(1, 10) == {"base": 10, "podium": 3, "total": 13}
    assert compute_club_challenge_points(10, 10) == {"base": 1, "podium": 0, "total": 1}


def test_eleven_skaters_capped_at_ten():
    """11 skaters: rank 1 still gets 10+3=13, ranks 10 and 11 both get 1."""
    assert compute_club_challenge_points(1, 11) == {"base": 10, "podium": 3, "total": 13}
    assert compute_club_challenge_points(10, 11) == {"base": 1, "podium": 0, "total": 1}
    assert compute_club_challenge_points(11, 11) == {"base": 1, "podium": 0, "total": 1}


def test_fifteen_skaters_beyond_tenth():
    """15 skaters: ranks 11-15 all get 1 base, 0 podium."""
    for rank in range(11, 16):
        assert compute_club_challenge_points(rank, 15) == {"base": 1, "podium": 0, "total": 1}


@pytest_asyncio.fixture
async def seed_club_analysis(db_session: AsyncSession):
    """Seed data for competition club analysis.

    Competition 'Comp A' with 2 categories:
    - 'R2 Minime Femme': 4 skaters (2 from TC, 2 from OC)
    - 'R1 Junior Homme': 2 skaters (1 from TC, 1 from OC)

    Prior competition 'Comp Prior' for PB detection.
    """
    settings = AppSettings(club_name="Test Club", club_short="TC", current_season="2025-2026")
    db_session.add(settings)

    comp_prior = Competition(name="Comp Prior", url="http://test/prior", date=date(2025, 9, 1), season="2025-2026")
    comp_a = Competition(name="Comp A", url="http://test/compa", date=date(2025, 11, 1), season="2025-2026")
    db_session.add_all([comp_prior, comp_a])
    await db_session.flush()

    s1 = Skater(first_name="Marie", last_name="Dupont", club="TC")
    s2 = Skater(first_name="Julie", last_name="Moreau", club="TC")
    s3 = Skater(first_name="Jean", last_name="Martin", club="TC")
    s4 = Skater(first_name="Other", last_name="One", club="OC")
    s5 = Skater(first_name="Other", last_name="Two", club="OC")
    s6 = Skater(first_name="Other", last_name="Three", club="OC")
    db_session.add_all([s1, s2, s3, s4, s5, s6])
    await db_session.flush()

    db_session.add(CategoryResult(
        competition_id=comp_prior.id, skater_id=s1.id,
        category="R2 Minime Femme", overall_rank=2, combined_total=28.0,
        segment_count=1, skating_level="R2", age_group="Minime", gender="Femme",
    ))

    for skater, rank, total in [
        (s1, 1, 35.0), (s4, 2, 32.0), (s2, 3, 30.0), (s5, 4, 25.0),
    ]:
        db_session.add(CategoryResult(
            competition_id=comp_a.id, skater_id=skater.id,
            category="R2 Minime Femme", overall_rank=rank, combined_total=total,
            segment_count=1, skating_level="R2", age_group="Minime", gender="Femme",
        ))

    for skater, rank, total in [
        (s6, 1, 60.0), (s3, 2, 55.0),
    ]:
        db_session.add(CategoryResult(
            competition_id=comp_a.id, skater_id=skater.id,
            category="R1 Junior Homme", overall_rank=rank, combined_total=total,
            segment_count=1, skating_level="R1", age_group="Junior", gender="Homme",
        ))

    await db_session.commit()
    return {"comp_a": comp_a, "comp_prior": comp_prior}


@pytest.mark.asyncio
async def test_competition_club_analysis(db_session: AsyncSession, seed_club_analysis):
    comp_a = seed_club_analysis["comp_a"]
    result = await compute_competition_club_analysis(db_session, comp_a.id, "TC")

    # KPIs
    assert result["kpis"]["skaters_entered"] == 3
    assert result["kpis"]["total_medals"] == 3  # Marie rank 1, Jean rank 2, Julie rank 3
    assert result["kpis"]["personal_bests"] == 1  # Only Marie
    assert result["kpis"]["categories_entered"] == 2
    assert result["kpis"]["categories_total"] == 2

    # Club challenge ranking
    ranking = result["club_challenge"]["ranking"]
    assert len(ranking) == 2
    tc_entry = next(e for e in ranking if e["is_my_club"])
    assert tc_entry["total_points"] == 13
    assert tc_entry["rank"] == 1
    oc_entry = next(e for e in ranking if not e["is_my_club"])
    assert oc_entry["total_points"] == 11
    assert oc_entry["rank"] == 2

    # Medals
    assert len(result["medals"]) == 3
    medal_names = {m["skater_name"] for m in result["medals"]}
    assert "Marie Dupont" in medal_names
    assert "Jean Martin" in medal_names
    assert "Julie Moreau" in medal_names

    # Results
    assert len(result["results"]) == 3
    marie_result = next(r for r in result["results"] if r["skater_name"] == "Marie Dupont")
    assert marie_result["is_pb"] is True
    assert marie_result["medal"] == 1
    julie_result = next(r for r in result["results"] if r["skater_name"] == "Julie Moreau")
    assert julie_result["is_pb"] is False
    assert julie_result["medal"] == 3
    jean_result = next(r for r in result["results"] if r["skater_name"] == "Jean Martin")
    assert jean_result["is_pb"] is False
    assert jean_result["medal"] == 2
