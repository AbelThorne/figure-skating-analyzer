"""Tests for team scoring calculation and API routes."""

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.competition import Competition
from app.models.skater import Skater
from app.models.score import Score
from app.models.app_settings import AppSettings
from app.services.team_scoring import compute_team_scores, DEFAULT_MEDIANS


# --- Unit tests for compute_team_scores ---


def _make_score_stub(
    score_id, skater_id, first_name, last_name, club, nationality,
    category, total_score, rank, skating_level=None, age_group=None, gender=None,
):
    """Create a mock Score-like object for testing."""

    class FakeSkater:
        def __init__(self):
            self.id = skater_id
            self.first_name = first_name
            self.last_name = last_name
            self.club = club
            self.nationality = nationality

    class FakeScore:
        def __init__(self):
            self.id = score_id
            self.skater_id = skater_id
            self.skater = FakeSkater()
            self.category = category
            self.total_score = total_score
            self.rank = rank
            self.skating_level = skating_level
            self.age_group = age_group
            self.gender = gender

    return FakeScore()


def test_basic_team_score_calculation():
    """Test that points = 10 * (score / median)."""
    medians = {"Novices dames": {"D1": 40.0}}
    scores = [
        _make_score_stub(
            1, 1, "Alice", "DUPONT", "Club A", "FRA",
            "Novice D1 Femme", 40.0, 1,
            skating_level="National", age_group="Novice", gender="Femme",
        ),
        _make_score_stub(
            2, 2, "Marie", "MARTIN", "Club B", "FRA",
            "Novice D1 Femme", 20.0, 2,
            skating_level="National", age_group="Novice", gender="Femme",
        ),
    ]
    result = compute_team_scores(scores, medians)

    assert len(result["clubs"]) == 2
    club_a = next(c for c in result["clubs"] if c["club"] == "Club A")
    club_b = next(c for c in result["clubs"] if c["club"] == "Club B")

    assert club_a["total_points"] == 10.0  # 10 * (40/40)
    assert club_b["total_points"] == 5.0   # 10 * (20/40)
    assert club_a["rank"] == 1
    assert club_b["rank"] == 2


def test_remplacant_excluded_by_nationality():
    """Skaters with empty nationality are remplaçants and excluded from total."""
    medians = {"Novices dames": {"D1": 40.0}}
    scores = [
        _make_score_stub(
            1, 1, "Alice", "DUPONT", "Club A", "FRA",
            "Novice D1 Femme", 40.0, 1,
            skating_level="National", age_group="Novice", gender="Femme",
        ),
        _make_score_stub(
            2, 2, "Marie", "MARTIN", "Club A", None,  # empty nationality = remplaçant
            "Novice D1 Femme", 80.0, 2,
            skating_level="National", age_group="Novice", gender="Femme",
        ),
    ]
    result = compute_team_scores(scores, medians)

    club_a = next(c for c in result["clubs"] if c["club"] == "Club A")
    # Only Alice's points count (10.0), Marie is remplaçant
    assert club_a["total_points"] == 10.0
    assert club_a["skater_count"] == 1


def test_remplacant_excluded_by_name():
    """Skaters with REMPL in name are excluded from total."""
    medians = {"Novices dames": {"D1": 40.0}}
    scores = [
        _make_score_stub(
            1, 1, "Alice", "DUPONT", "Club A", "FRA",
            "Novice D1 Femme", 40.0, 1,
            skating_level="National", age_group="Novice", gender="Femme",
        ),
        _make_score_stub(
            2, 2, "Marie REMPL", "MARTIN", "Club A", "FRA",
            "Novice D1 Femme", 80.0, 2,
            skating_level="National", age_group="Novice", gender="Femme",
        ),
    ]
    result = compute_team_scores(scores, medians)

    club_a = next(c for c in result["clubs"] if c["club"] == "Club A")
    assert club_a["total_points"] == 10.0
    assert club_a["skater_count"] == 1


def test_division_from_category_name():
    """Division extracted from D1/D2/D3 in category name."""
    medians = {"Juniors dames": {"D2": 30.0}}
    scores = [
        _make_score_stub(
            1, 1, "Alice", "DUPONT", "Club A", "FRA",
            "Junior D2 Femme", 30.0, 1,
            skating_level=None, age_group="Junior", gender="Femme",
        ),
    ]
    result = compute_team_scores(scores, medians)

    club_a = result["clubs"][0]
    assert club_a["total_points"] == 10.0  # 10 * (30/30)


def test_division_from_skating_level_excluded():
    """Categories without explicit D1/D2/D3 in name are excluded (individual categories)."""
    medians = {"Minimes messieurs": {"D2": 20.0}}
    scores = [
        _make_score_stub(
            1, 1, "Pierre", "DURAND", "Club A", "FRA",
            "Minime Fédéral Homme", 40.0, 1,
            skating_level="Fédéral", age_group="Minime", gender="Homme",
        ),
    ]
    result = compute_team_scores(scores, medians)

    # No clubs — individual categories (without D1/D2/D3 in name) are skipped
    assert len(result["clubs"]) == 0


def test_unmapped_category():
    """Categories without matching median are reported as unmapped."""
    medians = {}  # No medians at all
    scores = [
        _make_score_stub(
            1, 1, "Alice", "DUPONT", "Club A", "FRA",
            "Novice D1 Femme", 40.0, 1,
            skating_level="National", age_group="Novice", gender="Femme",
        ),
    ]
    result = compute_team_scores(scores, medians)
    assert len(result["unmapped"]) > 0


def test_multiple_clubs_ranking():
    """Clubs are ranked by total points descending."""
    medians = {"Novices dames": {"D1": 40.0}, "Juniors messieurs": {"D1": 50.0}}
    scores = [
        _make_score_stub(
            1, 1, "Alice", "DUPONT", "Club A", "FRA",
            "Novice D1 Femme", 40.0, 1,
            skating_level="National", age_group="Novice", gender="Femme",
        ),
        _make_score_stub(
            2, 2, "Bob", "DUPONT", "Club A", "FRA",
            "Junior D1 Homme", 60.0, 1,
            skating_level="National", age_group="Junior", gender="Homme",
        ),
        _make_score_stub(
            3, 3, "Marie", "MARTIN", "Club B", "FRA",
            "Novice D1 Femme", 80.0, 2,
            skating_level="National", age_group="Novice", gender="Femme",
        ),
    ]
    result = compute_team_scores(scores, medians)

    # Club A: 10*(40/40) + 10*(60/50) = 10 + 12 = 22
    # Club B: 10*(80/40) = 20
    assert result["clubs"][0]["club"] == "Club A"
    assert result["clubs"][0]["total_points"] == 22.0
    assert result["clubs"][1]["club"] == "Club B"
    assert result["clubs"][1]["total_points"] == 20.0


def test_couples_category():
    """Couple categories use 'Couples novices' etc. as median key."""
    medians = {"Couples novices": {"D1": 41.54}}
    scores = [
        _make_score_stub(
            1, 1, "", "Alice DUPONT / Bob DUPONT", "Club A", "FRA",
            "Couples Novice D1", 41.54, 1,
            skating_level="National", age_group="Novice", gender=None,
        ),
    ]
    result = compute_team_scores(scores, medians)
    assert result["clubs"][0]["total_points"] == 10.0


# --- API integration tests ---


@pytest_asyncio.fixture
async def france_clubs_setup(db_session: AsyncSession):
    """Create a france_clubs competition with scores for testing."""
    settings = AppSettings(club_name="Test Club", club_short="TC", current_season="2025-2026")
    db_session.add(settings)

    comp = Competition(
        name="France Clubs Test",
        url="https://example.com/fc",
        competition_type="france_clubs",
    )
    db_session.add(comp)
    await db_session.flush()

    skater1 = Skater(first_name="Alice", last_name="DUPONT", club="Club A", nationality="FRA")
    skater2 = Skater(first_name="Marie", last_name="MARTIN", club="Club B", nationality="FRA")
    db_session.add_all([skater1, skater2])
    await db_session.flush()

    score1 = Score(
        competition_id=comp.id,
        skater_id=skater1.id,
        segment="FS",
        category="Novice D1 Femme",
        total_score=44.39,
        rank=1,
        skating_level="National",
        age_group="Novice",
        gender="Femme",
    )
    score2 = Score(
        competition_id=comp.id,
        skater_id=skater2.id,
        segment="FS",
        category="Novice D1 Femme",
        total_score=30.0,
        rank=2,
        skating_level="National",
        age_group="Novice",
        gender="Femme",
    )
    db_session.add_all([score1, score2])
    await db_session.commit()

    return comp


async def test_team_scores_api(client, admin_token, france_clubs_setup):
    """Test GET /api/competitions/{id}/team-scores."""
    comp = france_clubs_setup
    resp = await client.get(
        f"/api/competitions/{comp.id}/team-scores",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "clubs" in data
    assert "categories" in data
    assert "medians" in data
    assert len(data["clubs"]) == 2


async def test_team_scores_not_france_clubs(client, admin_token, db_session):
    """Non france_clubs competitions return 404."""
    comp = Competition(
        name="Regular Comp",
        url="https://example.com/regular",
        competition_type="cr",
    )
    db_session.add(comp)
    await db_session.commit()

    resp = await client.get(
        f"/api/competitions/{comp.id}/team-scores",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 404


async def test_update_competition_medians(client, admin_token, france_clubs_setup):
    """Admin can update competition-specific medians."""
    comp = france_clubs_setup
    custom_medians = {"Novices dames": {"D1": 50.0}}

    resp = await client.put(
        f"/api/competitions/{comp.id}/team-medians",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"medians": custom_medians},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["source"] == "competition"
    assert data["medians"]["Novices dames"]["D1"] == 50.0


async def test_get_competition_medians_default(client, admin_token, france_clubs_setup):
    """When no competition medians set, returns default medians."""
    comp = france_clubs_setup
    resp = await client.get(
        f"/api/competitions/{comp.id}/team-medians",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["source"] == "default"


async def test_default_medians_api(client, admin_token, france_clubs_setup):
    """Admin can get and update default medians."""
    resp = await client.get(
        "/api/competitions/default-team-medians",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "medians" in data

    custom = {"Novices dames": {"D1": 99.0}}
    resp = await client.put(
        "/api/competitions/default-team-medians",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"medians": custom},
    )
    assert resp.status_code == 200
    assert resp.json()["medians"]["Novices dames"]["D1"] == 99.0


async def test_reader_cannot_update_medians(client, reader_token, france_clubs_setup):
    """Non-admin users cannot update medians."""
    comp = france_clubs_setup
    resp = await client.put(
        f"/api/competitions/{comp.id}/team-medians",
        headers={"Authorization": f"Bearer {reader_token}"},
        json={"medians": {}},
    )
    assert resp.status_code == 403
