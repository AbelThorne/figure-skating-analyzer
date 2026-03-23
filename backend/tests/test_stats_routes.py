import pytest
import pytest_asyncio
from datetime import date
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.competition import Competition
from app.models.skater import Skater
from app.models.category_result import CategoryResult
from app.models.score import Score
from app.models.app_settings import AppSettings


@pytest_asyncio.fixture
async def seed_data(db_session: AsyncSession):
    """Seed competitions, skaters, and category results for stats tests."""
    settings = AppSettings(club_name="Test Club", club_short="TC", current_season="2025-2026")
    db_session.add(settings)

    comp1 = Competition(name="Comp 1", url="http://test/comp1", date=date(2025, 10, 15), season="2025-2026")
    comp2 = Competition(name="Comp 2", url="http://test/comp2", date=date(2025, 12, 1), season="2025-2026")
    comp3 = Competition(name="Comp 3", url="http://test/comp3", date=date(2026, 2, 10), season="2025-2026")
    db_session.add_all([comp1, comp2, comp3])
    await db_session.flush()

    skater1 = Skater(first_name="Marie", last_name="Dupont", club="TC")
    skater2 = Skater(first_name="Jean", last_name="Martin", club="TC")
    skater3 = Skater(first_name="Other", last_name="Club", club="OC")
    db_session.add_all([skater1, skater2, skater3])
    await db_session.flush()

    # Marie: 3 results, improving (R2 Minime)
    for comp, total in [(comp1, 30.0), (comp2, 35.0), (comp3, 40.0)]:
        db_session.add(CategoryResult(
            competition_id=comp.id, skater_id=skater1.id,
            category="R2 Minime Femme", overall_rank=1, combined_total=total,
            segment_count=1, skating_level="R2", age_group="Minime", gender="Femme",
        ))

    # Jean: 2 results, declining (R1 Junior)
    for comp, total in [(comp1, 50.0), (comp3, 45.0)]:
        db_session.add(CategoryResult(
            competition_id=comp.id, skater_id=skater2.id,
            category="R1 Junior Homme", overall_rank=2, combined_total=total,
            segment_count=1, skating_level="R1", age_group="Junior", gender="Homme",
        ))

    # Other club skater: should not appear with club filter
    db_session.add(CategoryResult(
        competition_id=comp1.id, skater_id=skater3.id,
        category="R2 Minime Femme", overall_rank=3, combined_total=25.0,
        segment_count=1, skating_level="R2", age_group="Minime", gender="Femme",
    ))

    await db_session.commit()
    return {"skater1": skater1, "skater2": skater2, "skater3": skater3}


@pytest.mark.asyncio
async def test_progression_ranking_default(client: AsyncClient, admin_token: str, seed_data):
    resp = await client.get(
        "/api/stats/progression-ranking",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    # Marie (gain=10) should be first, Jean (gain=-5) second
    assert len(data) == 2
    assert data[0]["skater_name"] == "Marie Dupont"
    assert data[0]["tss_gain"] == 10.0
    assert data[0]["first_tss"] == 30.0
    assert data[0]["last_tss"] == 40.0
    assert data[0]["competitions_count"] == 3
    assert len(data[0]["sparkline"]) == 3
    assert data[1]["skater_name"] == "Jean Martin"
    assert data[1]["tss_gain"] == -5.0


@pytest.mark.asyncio
async def test_progression_ranking_filter_level(client: AsyncClient, admin_token: str, seed_data):
    resp = await client.get(
        "/api/stats/progression-ranking?skating_level=R2",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["skater_name"] == "Marie Dupont"


@pytest.mark.asyncio
async def test_progression_ranking_filter_gender(client: AsyncClient, admin_token: str, seed_data):
    resp = await client.get(
        "/api/stats/progression-ranking?gender=Homme",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["skater_name"] == "Jean Martin"
