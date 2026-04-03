"""Tests for team scoring calculation and API routes."""

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.competition import Competition
from app.models.skater import Skater
from app.models.score import Score
from app.models.app_settings import AppSettings
from app.services.team_scoring import compute_team_scores, auto_init_titular, DEFAULT_MEDIANS, CHALLENGE_POINTS


# --- Unit tests for compute_team_scores ---


def _make_score_stub(
    score_id, skater_id, first_name, last_name, club, nationality,
    category, total_score, rank, skating_level=None, age_group=None, gender=None,
    is_titular=True, starting_number=None,
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
            self.is_titular = is_titular
            self.starting_number = starting_number
            self.club = club

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


def test_remplacant_excluded_by_is_titular():
    """Skaters with is_titular=False are remplacants and excluded from total."""
    medians = {"Novices dames": {"D1": 40.0}}
    scores = [
        _make_score_stub(
            1, 1, "Alice", "DUPONT", "Club A", "FRA",
            "Novice D1 Femme", 40.0, 1,
            skating_level="National", age_group="Novice", gender="Femme",
            is_titular=True,
        ),
        _make_score_stub(
            2, 2, "Marie", "MARTIN", "Club A", "FRA",
            "Novice D1 Femme", 80.0, 2,
            skating_level="National", age_group="Novice", gender="Femme",
            is_titular=False,  # substitute
        ),
    ]
    result = compute_team_scores(scores, medians)

    club_a = next(c for c in result["clubs"] if c["club"] == "Club A")
    # Only Alice's points count (10.0), Marie is remplacant
    assert club_a["total_points"] == 10.0
    assert club_a["skater_count"] == 1

    # Marie should be flagged as remplacant in entries
    marie = next(s for s in club_a["skaters"] if s["skater_name"] == "Marie MARTIN")
    assert marie["is_remplacant"] is True
    assert marie["is_titular"] is False


def test_is_titular_none_treated_as_titular():
    """Scores with is_titular=None are treated as titular (backward compat)."""
    medians = {"Novices dames": {"D1": 40.0}}
    scores = [
        _make_score_stub(
            1, 1, "Alice", "DUPONT", "Club A", "FRA",
            "Novice D1 Femme", 40.0, 1,
            skating_level="National", age_group="Novice", gender="Femme",
            is_titular=None,
        ),
    ]
    result = compute_team_scores(scores, medians)

    club_a = result["clubs"][0]
    assert club_a["total_points"] == 10.0
    assert club_a["skater_count"] == 1
    alice = club_a["skaters"][0]
    assert alice["is_remplacant"] is False


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


def test_entries_include_is_titular_and_starting_number():
    """Skater entries include is_titular and starting_number fields."""
    medians = {"Novices dames": {"D1": 40.0}}
    scores = [
        _make_score_stub(
            1, 1, "Alice", "DUPONT", "Club A", "FRA",
            "Novice D1 Femme", 40.0, 1,
            skating_level="National", age_group="Novice", gender="Femme",
            is_titular=True, starting_number=3,
        ),
    ]
    result = compute_team_scores(scores, medians)
    entry = result["clubs"][0]["skaters"][0]
    assert entry["is_titular"] is True
    assert entry["starting_number"] == 3


def test_no_violations_when_valid():
    """No violations when team composition is valid."""
    medians = {"Novices dames": {"D1": 40.0}}
    scores = [
        _make_score_stub(1, 1, "A1", "A", "Club A", "FRA",
            "Novice D1 Femme", 40.0, 1, age_group="Novice", gender="Femme"),
        _make_score_stub(2, 2, "A2", "A", "Club A", "FRA",
            "Novice D1 Femme", 35.0, 2, age_group="Novice", gender="Femme"),
    ]
    result = compute_team_scores(scores, medians)
    assert result["violations"] == []


def test_violation_max_2_per_category():
    """Violation when >2 titular in same category for same club."""
    medians = {"Novices dames": {"D1": 40.0}}
    scores = [
        _make_score_stub(1, 1, "A1", "A", "Club A", "FRA",
            "Novice D1 Femme", 40.0, 1, age_group="Novice", gender="Femme", is_titular=True),
        _make_score_stub(2, 2, "A2", "A", "Club A", "FRA",
            "Novice D1 Femme", 35.0, 2, age_group="Novice", gender="Femme", is_titular=True),
        _make_score_stub(3, 3, "A3", "A", "Club A", "FRA",
            "Novice D1 Femme", 30.0, 3, age_group="Novice", gender="Femme", is_titular=True),
    ]
    result = compute_team_scores(scores, medians)
    cat_violations = [v for v in result["violations"] if v["rule"] == "max_titular_per_category"]
    assert len(cat_violations) == 1
    assert cat_violations[0]["club"] == "Club A"
    assert cat_violations[0]["division"] == "D1"
    assert cat_violations[0]["category"] == "Novice D1 Femme"


def test_violation_max_6_per_division():
    """Violation when >6 titular in same division for same club."""
    medians = {
        "Novices dames": {"D1": 40.0},
        "Juniors dames": {"D1": 50.0},
        "Minimes dames": {"D1": 30.0},
        "Benjamins dames": {"D1": 20.0},
    }
    # 7 titulaires across 4 categories in D1 — all valid per category (max 2 each)
    # but exceeds 6 per division
    scores = [
        _make_score_stub(1, 1, "A1", "A", "Club A", "FRA",
            "Novice D1 Femme", 40.0, 1, age_group="Novice", gender="Femme", is_titular=True),
        _make_score_stub(2, 2, "A2", "A", "Club A", "FRA",
            "Novice D1 Femme", 38.0, 2, age_group="Novice", gender="Femme", is_titular=True),
        _make_score_stub(3, 3, "A3", "A", "Club A", "FRA",
            "Junior D1 Femme", 50.0, 1, age_group="Junior", gender="Femme", is_titular=True),
        _make_score_stub(4, 4, "A4", "A", "Club A", "FRA",
            "Junior D1 Femme", 48.0, 2, age_group="Junior", gender="Femme", is_titular=True),
        _make_score_stub(5, 5, "A5", "A", "Club A", "FRA",
            "Minime D1 Femme", 30.0, 1, age_group="Minime", gender="Femme", is_titular=True),
        _make_score_stub(6, 6, "A6", "A", "Club A", "FRA",
            "Minime D1 Femme", 28.0, 2, age_group="Minime", gender="Femme", is_titular=True),
        _make_score_stub(7, 7, "A7", "A", "Club A", "FRA",
            "Benjamin D1 Femme", 20.0, 1, age_group="Benjamin", gender="Femme", is_titular=True),
    ]
    result = compute_team_scores(scores, medians)
    div_violations = [v for v in result["violations"] if v["rule"] == "max_titular_per_division"]
    assert len(div_violations) == 1
    assert div_violations[0]["division"] == "D1"


def test_division_rankings():
    """Clubs are ranked per division separately."""
    medians = {
        "Novices dames": {"D1": 40.0, "D2": 30.0},
        "Juniors messieurs": {"D1": 50.0},
    }
    scores = [
        # Club A: D1 Novice + D1 Junior
        _make_score_stub(1, 1, "Alice", "DUPONT", "Club A", "FRA",
            "Novice D1 Femme", 40.0, 1, age_group="Novice", gender="Femme"),
        _make_score_stub(2, 2, "Bob", "DUPONT", "Club A", "FRA",
            "Junior D1 Homme", 60.0, 1, age_group="Junior", gender="Homme"),
        # Club B: D1 Novice only
        _make_score_stub(3, 3, "Marie", "MARTIN", "Club B", "FRA",
            "Novice D1 Femme", 80.0, 2, age_group="Novice", gender="Femme"),
        # Club C: D2 only
        _make_score_stub(4, 4, "Paul", "PETIT", "Club C", "FRA",
            "Novice D2 Femme", 30.0, 1, age_group="Novice", gender="Femme"),
    ]
    result = compute_team_scores(scores, medians)

    assert "division_rankings" in result
    assert "D1" in result["division_rankings"]
    assert "D2" in result["division_rankings"]

    d1 = result["division_rankings"]["D1"]
    # Club A: 10*(40/40) + 10*(60/50) = 22.0
    # Club B: 10*(80/40) = 20.0
    assert d1[0]["club"] == "Club A"
    assert d1[0]["total_points"] == 22.0
    assert d1[0]["rank"] == 1
    assert d1[1]["club"] == "Club B"
    assert d1[1]["rank"] == 2

    d2 = result["division_rankings"]["D2"]
    assert len(d2) == 1
    assert d2[0]["club"] == "Club C"
    assert d2[0]["rank"] == 1


def test_challenge_scoring():
    """Challenge points based on division ranks using CSNPA table."""
    medians = {
        "Novices dames": {"D1": 40.0, "D2": 30.0, "D3": 20.0},
    }
    scores = [
        # Club A: present in D1 (rank 1), D2 (rank 1), D3 (rank 1)
        _make_score_stub(1, 1, "A1", "A", "Club A", "FRA",
            "Novice D1 Femme", 40.0, 1, age_group="Novice", gender="Femme"),
        _make_score_stub(2, 2, "A2", "A", "Club A", "FRA",
            "Novice D2 Femme", 30.0, 1, age_group="Novice", gender="Femme"),
        _make_score_stub(3, 3, "A3", "A", "Club A", "FRA",
            "Novice D3 Femme", 20.0, 1, age_group="Novice", gender="Femme"),
        # Club B: present in D1 (rank 2) only
        _make_score_stub(4, 4, "B1", "B", "Club B", "FRA",
            "Novice D1 Femme", 20.0, 2, age_group="Novice", gender="Femme"),
    ]
    result = compute_team_scores(scores, medians)

    assert "challenge" in result
    challenge = result["challenge"]

    club_a = next(c for c in challenge if c["club"] == "Club A")
    club_b = next(c for c in challenge if c["club"] == "Club B")

    # Club A: D1 rank 1 (35pts) + D2 rank 1 (30pts) + D3 rank 1 (25pts) = 90
    assert club_a["challenge_points"] == 90
    assert club_a["division_ranks"] == {"D1": 1, "D2": 1, "D3": 1}
    assert club_a["rank"] == 1

    # Club B: D1 rank 2 (32pts) = 32
    assert club_b["challenge_points"] == 32
    assert club_b["division_ranks"] == {"D1": 2}
    assert club_b["rank"] == 2


def test_challenge_tiebreaker():
    """Challenge tiebreaker: best D1, then D2, then D3."""
    medians = {
        "Novices dames": {"D1": 40.0, "D2": 30.0},
    }
    scores = [
        # Club A: D1 rank 1 (35pts), D2 rank 2 (28pts) = 63
        _make_score_stub(1, 1, "A1", "A", "Club A", "FRA",
            "Novice D1 Femme", 80.0, 1, age_group="Novice", gender="Femme"),
        _make_score_stub(2, 2, "A2", "A", "Club A", "FRA",
            "Novice D2 Femme", 10.0, 2, age_group="Novice", gender="Femme"),
        # Club B: D1 rank 2 (32pts), D2 rank 1 (30pts) = 62
        _make_score_stub(3, 3, "B1", "B", "Club B", "FRA",
            "Novice D1 Femme", 40.0, 2, age_group="Novice", gender="Femme"),
        _make_score_stub(4, 4, "B2", "B", "Club B", "FRA",
            "Novice D2 Femme", 60.0, 1, age_group="Novice", gender="Femme"),
    ]
    result = compute_team_scores(scores, medians)
    challenge = result["challenge"]

    # Club A has more challenge points (63 vs 62)
    assert challenge[0]["club"] == "Club A"
    assert challenge[0]["challenge_points"] == 63
    assert challenge[1]["club"] == "Club B"
    assert challenge[1]["challenge_points"] == 62


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
        starting_number=1,
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
        starting_number=2,
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
    assert "division_rankings" in data
    assert "challenge" in data
    assert len(data["clubs"]) == 2
    # Both skaters are in D1 so division_rankings should have D1
    assert "D1" in data["division_rankings"]
    assert len(data["division_rankings"]["D1"]) == 2
    # Challenge should have 2 clubs
    assert len(data["challenge"]) == 2
    assert data["challenge"][0]["challenge_points"] > 0


async def test_team_scores_auto_init_titular(client, admin_token, france_clubs_setup, db_session):
    """Team scores endpoint auto-initializes is_titular when NULL."""
    comp = france_clubs_setup
    # Scores should have is_titular=None initially
    resp = await client.get(
        f"/api/competitions/{comp.id}/team-scores",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    # Both skaters should be titular (< 6 per club per division)
    for club in data["clubs"]:
        for s in club["skaters"]:
            assert s["is_titular"] is True


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


async def test_toggle_titular_status(client, admin_token, france_clubs_setup, db_session):
    """Admin can toggle is_titular on a score."""
    comp = france_clubs_setup

    # First load team scores to trigger auto-init
    resp = await client.get(
        f"/api/competitions/{comp.id}/team-scores",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    score_id = resp.json()["clubs"][0]["skaters"][0]["score_id"]

    # Toggle to substitute
    resp = await client.put(
        f"/api/competitions/{comp.id}/team-titular/{score_id}",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"is_titular": False},
    )
    assert resp.status_code == 200
    assert resp.json()["is_titular"] is False

    # Verify it's reflected in team scores
    resp = await client.get(
        f"/api/competitions/{comp.id}/team-scores",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    toggled = None
    for club in resp.json()["clubs"]:
        for s in club["skaters"]:
            if s["score_id"] == score_id:
                toggled = s
                break
    assert toggled is not None
    assert toggled["is_remplacant"] is True
    assert toggled["is_titular"] is False


async def test_reset_titular(client, admin_token, france_clubs_setup, db_session):
    """Admin can reset all titular statuses to auto-init defaults."""
    comp = france_clubs_setup

    # First load to auto-init, then toggle one
    resp = await client.get(
        f"/api/competitions/{comp.id}/team-scores",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    score_id = resp.json()["clubs"][0]["skaters"][0]["score_id"]

    await client.put(
        f"/api/competitions/{comp.id}/team-titular/{score_id}",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"is_titular": False},
    )

    # Reset
    resp = await client.put(
        f"/api/competitions/{comp.id}/team-titular-reset",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["reset"] is True

    # All should be titular again (only 2 skaters, < 6 per div/club)
    resp = await client.get(
        f"/api/competitions/{comp.id}/team-scores",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    for club in resp.json()["clubs"]:
        for s in club["skaters"]:
            assert s["is_titular"] is True


async def test_reader_cannot_toggle_titular(client, reader_token, france_clubs_setup):
    """Non-admin users cannot toggle titular status."""
    comp = france_clubs_setup
    resp = await client.put(
        f"/api/competitions/{comp.id}/team-titular/1",
        headers={"Authorization": f"Bearer {reader_token}"},
        json={"is_titular": False},
    )
    assert resp.status_code == 403


async def test_auto_init_limits_6_per_division_per_club(db_session: AsyncSession):
    """Auto-init marks up to 6 per division per club as titular, respecting max 2 per category."""
    settings = AppSettings(club_name="Test Club", club_short="TC", current_season="2025-2026")
    db_session.add(settings)

    comp = Competition(
        name="FC Limit Test",
        url="https://example.com/fc-limit",
        competition_type="france_clubs",
    )
    db_session.add(comp)
    await db_session.flush()

    # Create 8 skaters in same club/division across 4 categories (2 each)
    # This ensures max 2 per category is respected while filling 6 titulaires
    categories = ["Novice D1 Femme", "Novice D1 Femme",
                   "Junior D1 Femme", "Junior D1 Femme",
                   "Minime D1 Femme", "Minime D1 Femme",
                   "Benjamin D1 Femme", "Benjamin D1 Femme"]
    skaters = []
    for i in range(8):
        sk = Skater(first_name=f"Skater{i}", last_name=f"LAST{i}", club="Club A", nationality="FRA")
        db_session.add(sk)
        skaters.append(sk)
    await db_session.flush()

    for i, sk in enumerate(skaters):
        score = Score(
            competition_id=comp.id,
            skater_id=sk.id,
            segment="FS",
            category=categories[i],
            total_score=30.0 + i,
            rank=i + 1,
            skating_level="National",
            age_group="Novice",
            gender="Femme",
            starting_number=i + 1,
        )
        db_session.add(score)
    await db_session.flush()

    await auto_init_titular(db_session, comp.id)

    from sqlalchemy import select as sa_select
    stmt = sa_select(Score).where(Score.competition_id == comp.id).order_by(Score.starting_number)
    result = await db_session.execute(stmt)
    scores = result.scalars().all()

    titular_count = sum(1 for s in scores if s.is_titular is True)
    sub_count = sum(1 for s in scores if s.is_titular is False)
    assert titular_count == 6
    assert sub_count == 2


async def test_auto_init_respects_max_2_per_category(db_session: AsyncSession):
    """Auto-init marks at most 2 titular per category per club, even if division has room."""
    settings = AppSettings(club_name="Test Club", club_short="TC", current_season="2025-2026")
    db_session.add(settings)

    comp = Competition(
        name="FC Cat Limit Test",
        url="https://example.com/fc-cat-limit",
        competition_type="france_clubs",
    )
    db_session.add(comp)
    await db_session.flush()

    # 4 skaters all in same category — only 2 can be titular
    skaters = []
    for i in range(4):
        sk = Skater(first_name=f"Skater{i}", last_name=f"LAST{i}", club="Club A", nationality="FRA")
        db_session.add(sk)
        skaters.append(sk)
    await db_session.flush()

    for i, sk in enumerate(skaters):
        score = Score(
            competition_id=comp.id,
            skater_id=sk.id,
            segment="FS",
            category="Novice D1 Femme",
            total_score=30.0 + i,
            rank=i + 1,
            skating_level="National",
            age_group="Novice",
            gender="Femme",
            starting_number=i + 1,
        )
        db_session.add(score)
    await db_session.flush()

    await auto_init_titular(db_session, comp.id)

    from sqlalchemy import select as sa_select
    stmt = sa_select(Score).where(Score.competition_id == comp.id).order_by(Score.starting_number)
    result = await db_session.execute(stmt)
    scores = result.scalars().all()

    titular_count = sum(1 for s in scores if s.is_titular is True)
    sub_count = sum(1 for s in scores if s.is_titular is False)
    assert titular_count == 2
    assert sub_count == 2
