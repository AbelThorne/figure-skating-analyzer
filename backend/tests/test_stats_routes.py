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


@pytest_asyncio.fixture
async def seed_benchmark_data(db_session: AsyncSession):
    """Seed broader field data for benchmark computation."""
    settings = AppSettings(club_name="Test Club", club_short="TC", current_season="2025-2026")
    db_session.add(settings)

    comp = Competition(name="Big Comp", url="http://test/big", date=date(2025, 11, 1), season="2025-2026")
    db_session.add(comp)
    await db_session.flush()

    totals = [20.0, 25.0, 28.0, 30.0, 33.0, 35.0, 38.0, 40.0, 45.0, 50.0]
    for i, total in enumerate(totals):
        skater = Skater(first_name=f"Skater{i}", last_name=f"Test{i}", club=f"Club{i}")
        db_session.add(skater)
        await db_session.flush()
        db_session.add(CategoryResult(
            competition_id=comp.id, skater_id=skater.id,
            category="R2 Minime Femme", overall_rank=i + 1, combined_total=total,
            segment_count=1, skating_level="R2", age_group="Minime", gender="Femme",
        ))

    await db_session.commit()


@pytest.mark.asyncio
async def test_benchmarks(client: AsyncClient, admin_token: str, seed_benchmark_data):
    resp = await client.get(
        "/api/stats/benchmarks?skating_level=R2&age_group=Minime&gender=Femme",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["skating_level"] == "R2"
    assert data["age_group"] == "Minime"
    assert data["gender"] == "Femme"
    assert data["data_points"] == 10
    assert data["min"] == 20.0
    assert data["max"] == 50.0
    assert data["median"] == 34.0
    assert data["p25"] is not None
    assert data["p75"] is not None


@pytest.mark.asyncio
async def test_benchmarks_no_data(client: AsyncClient, admin_token: str, seed_benchmark_data):
    resp = await client.get(
        "/api/stats/benchmarks?skating_level=R1&age_group=Junior&gender=Homme",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["data_points"] == 0


@pytest_asyncio.fixture
async def seed_element_data(db_session: AsyncSession):
    """Seed scores with element data for mastery tests."""
    settings = AppSettings(club_name="Test Club", club_short="TC", current_season="2025-2026")
    db_session.add(settings)

    comp = Competition(name="Comp E", url="http://test/compe", date=date(2025, 11, 1), season="2025-2026")
    db_session.add(comp)
    await db_session.flush()

    skater = Skater(first_name="Marie", last_name="Dupont", club="TC")
    db_session.add(skater)
    await db_session.flush()

    score = Score(
        competition_id=comp.id, skater_id=skater.id,
        segment="FS", category="R2 Minime Femme",
        total_score=40.0, technical_score=22.0, component_score=18.0,
        skating_level="R2", age_group="Minime", gender="Femme",
        elements=[
            {"name": "2A", "base_value": 3.3, "goe": 0.5, "score": 3.8, "number": 1, "markers": [], "judge_goe": [1, 1, 0], "info_flag": None},
            {"name": "2Lz", "base_value": 2.1, "goe": -0.3, "score": 1.8, "number": 2, "markers": [], "judge_goe": [-1, -1, 0], "info_flag": None},
            {"name": "2T", "base_value": 1.3, "goe": 0.0, "score": 1.3, "number": 3, "markers": [], "judge_goe": [0, 0, 0], "info_flag": None},
            {"name": "CCoSp4", "base_value": 3.5, "goe": 1.0, "score": 4.5, "number": 4, "markers": [], "judge_goe": [2, 2, 2], "info_flag": None},
            {"name": "FSSp3", "base_value": 2.6, "goe": 0.5, "score": 3.1, "number": 5, "markers": [], "judge_goe": [1, 1, 1], "info_flag": None},
            {"name": "StSq3", "base_value": 3.3, "goe": 0.8, "score": 4.1, "number": 6, "markers": [], "judge_goe": [2, 1, 2], "info_flag": None},
        ],
    )
    db_session.add(score)
    await db_session.commit()


@pytest.mark.asyncio
async def test_element_mastery(client: AsyncClient, admin_token: str, seed_element_data):
    resp = await client.get(
        "/api/stats/element-mastery",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    data = resp.json()

    assert len(data["jumps"]) == 3
    jump_map = {j["jump_type"]: j for j in data["jumps"]}
    assert jump_map["2A"]["attempts"] == 1
    assert jump_map["2A"]["positive_goe_pct"] == 100.0
    assert jump_map["2Lz"]["negative_goe_pct"] == 100.0
    assert jump_map["2T"]["neutral_goe_pct"] == 100.0

    assert len(data["spins"]) == 2
    spin_map = {s["element_type"]: s for s in data["spins"]}
    assert spin_map["CCoSp"]["level_distribution"]["4"] == 1
    assert spin_map["FSSp"]["level_distribution"]["3"] == 1

    assert len(data["steps"]) == 1
    assert data["steps"][0]["element_type"] == "StSq"
    assert data["steps"][0]["level_distribution"]["3"] == 1
