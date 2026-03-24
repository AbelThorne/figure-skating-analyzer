import pytest
from datetime import date
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.competition import Competition
from app.models.skater import Skater
from app.models.score import Score
from app.models.category_result import CategoryResult
from app.models.app_settings import AppSettings
from app.services.report_data import get_skater_report_data, get_club_report_data


async def _seed_skater_data(session: AsyncSession):
    skater = Skater(first_name="Alice", last_name="DUPONT", club="CSG Chambéry", nationality="FRA")
    session.add(skater)
    await session.flush()

    comp1 = Competition(name="CSNPA Automne", url="http://example.com/c1", date=date(2025, 10, 15), season="2025-2026")
    comp2 = Competition(name="Coupe Régionale", url="http://example.com/c2", date=date(2026, 1, 20), season="2025-2026")
    comp_other = Competition(name="Old Comp", url="http://example.com/c3", date=date(2024, 11, 1), season="2024-2025")
    session.add_all([comp1, comp2, comp_other])
    await session.flush()

    scores = [
        Score(competition_id=comp1.id, skater_id=skater.id, segment="Short Program",
              category="Novice Dames", total_score=30.0, technical_score=18.0,
              component_score=12.0, deductions=0.0, event_date=comp1.date, rank=2),
        Score(competition_id=comp1.id, skater_id=skater.id, segment="Free Skating",
              category="Novice Dames", total_score=55.0, technical_score=33.0,
              component_score=22.0, deductions=0.0, event_date=comp1.date, rank=1),
        Score(competition_id=comp2.id, skater_id=skater.id, segment="Short Program",
              category="Novice Dames", total_score=35.0, technical_score=20.0,
              component_score=15.0, deductions=0.0, event_date=comp2.date, rank=1),
        Score(competition_id=comp2.id, skater_id=skater.id, segment="Free Skating",
              category="Novice Dames", total_score=50.0, technical_score=30.0,
              component_score=20.0, deductions=0.0, event_date=comp2.date, rank=3),
        Score(competition_id=comp_other.id, skater_id=skater.id, segment="Short Program",
              category="Novice Dames", total_score=99.0, technical_score=60.0,
              component_score=39.0, deductions=0.0, event_date=comp_other.date, rank=1),
    ]
    session.add_all(scores)

    cr1 = CategoryResult(competition_id=comp1.id, skater_id=skater.id, category="Novice Dames",
                         overall_rank=1, combined_total=85.0, segment_count=2)
    cr2 = CategoryResult(competition_id=comp2.id, skater_id=skater.id, category="Novice Dames",
                         overall_rank=2, combined_total=85.0, segment_count=2)
    session.add_all([cr1, cr2])
    await session.commit()
    return skater


@pytest.mark.asyncio
async def test_skater_report_data(db_session: AsyncSession):
    skater = await _seed_skater_data(db_session)
    data = await get_skater_report_data(skater.id, "2025-2026", db_session)

    assert data.skater_name == "Alice DUPONT"
    assert data.season == "2025-2026"
    assert len(data.results) == 4
    assert "Short Program" in data.personal_bests
    assert data.personal_bests["Short Program"]["tss"] == 35.0
    assert "Free Skating" in data.personal_bests
    assert data.personal_bests["Free Skating"]["tss"] == 55.0
    assert data.element_summary is None


@pytest.mark.asyncio
async def test_skater_report_data_empty_season(db_session: AsyncSession):
    skater = await _seed_skater_data(db_session)
    data = await get_skater_report_data(skater.id, "2030-2031", db_session)
    assert len(data.results) == 0


async def _seed_club_data(session: AsyncSession):
    settings = AppSettings(club_name="CSG Chambéry", club_short="CSG", current_season="2025-2026")
    session.add(settings)

    s1 = Skater(first_name="Alice", last_name="DUPONT", club="CSG Chambéry")
    s2 = Skater(first_name="Bob", last_name="MARTIN", club="CSG Chambéry")
    s3 = Skater(first_name="Eve", last_name="OTHER", club="Autre Club")
    session.add_all([s1, s2, s3])
    await session.flush()

    comp1 = Competition(name="CSNPA Automne", url="http://example.com/c1", date=date(2025, 10, 15), season="2025-2026")
    comp2 = Competition(name="Coupe Régionale", url="http://example.com/c2", date=date(2026, 1, 20), season="2025-2026")
    session.add_all([comp1, comp2])
    await session.flush()

    session.add_all([
        Score(competition_id=comp1.id, skater_id=s1.id, segment="Short Program",
              category="Novice Dames", total_score=30.0, technical_score=18.0,
              component_score=12.0, deductions=0.0, event_date=comp1.date, rank=1),
        Score(competition_id=comp2.id, skater_id=s1.id, segment="Short Program",
              category="Novice Dames", total_score=38.0, technical_score=22.0,
              component_score=16.0, deductions=0.0, event_date=comp2.date, rank=1),
        Score(competition_id=comp1.id, skater_id=s2.id, segment="Short Program",
              category="Junior Messieurs", total_score=45.0, technical_score=28.0,
              component_score=17.0, deductions=0.0, event_date=comp1.date, rank=3),
        Score(competition_id=comp1.id, skater_id=s3.id, segment="Short Program",
              category="Novice Dames", total_score=99.0, technical_score=60.0,
              component_score=39.0, deductions=0.0, event_date=comp1.date, rank=1),
    ])

    session.add_all([
        CategoryResult(competition_id=comp1.id, skater_id=s1.id, category="Novice Dames",
                       overall_rank=1, combined_total=30.0, segment_count=1),
        CategoryResult(competition_id=comp2.id, skater_id=s1.id, category="Novice Dames",
                       overall_rank=1, combined_total=38.0, segment_count=1),
        CategoryResult(competition_id=comp1.id, skater_id=s2.id, category="Junior Messieurs",
                       overall_rank=3, combined_total=45.0, segment_count=1),
    ])
    await session.commit()
    return s1, s2


@pytest.mark.asyncio
async def test_club_report_data(db_session: AsyncSession):
    s1, s2 = await _seed_club_data(db_session)
    data = await get_club_report_data("2025-2026", db_session)

    assert data.club_name == "CSG Chambéry"
    assert data.season == "2025-2026"
    assert data.stats["active_skaters"] == 2
    assert data.stats["total_programs"] == 3

    assert len(data.skaters_summary) == 2
    names = [s["name"] for s in data.skaters_summary]
    assert "Alice DUPONT" in names
    assert "Bob MARTIN" in names
    assert "Eve OTHER" not in names

    assert len(data.medals) >= 2

    assert len(data.most_improved) >= 1
    assert data.most_improved[0]["name"] == "Alice DUPONT"
    assert data.most_improved[0]["delta"] == 8.0
