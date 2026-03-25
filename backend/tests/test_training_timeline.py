import pytest

from app.auth.tokens import create_access_token
from app.auth.passwords import hash_password
from app.models.user import User
from app.models.skater import Skater
from app.models.user_skater import UserSkater


@pytest.fixture
async def coach_and_skater(db_session):
    coach = User(
        email="coach@test.com",
        password_hash=hash_password("coachpass1"),
        display_name="Test Coach",
        role="coach",
    )
    db_session.add(coach)
    skater = Skater(first_name="Alice", last_name="Dupont", club="TestClub")
    db_session.add(skater)
    await db_session.commit()
    await db_session.refresh(coach)
    await db_session.refresh(skater)
    token = create_access_token(user_id=coach.id, role=coach.role)
    return coach, token, skater


async def test_timeline_merges_reviews_and_incidents(client, coach_and_skater):
    _, token, skater = coach_and_skater

    # Create a review
    await client.post(
        "/api/training/reviews",
        json={
            "skater_id": skater.id,
            "week_start": "2026-03-23",
            "attendance": "3/4",
            "engagement": 4,
            "progression": 3,
            "attitude": 5,
            "strengths": "Bon",
            "improvements": "Mieux",
            "visible_to_skater": True,
        },
        headers={"Authorization": f"Bearer {token}"},
    )

    # Create an incident
    await client.post(
        "/api/training/incidents",
        json={
            "skater_id": skater.id,
            "date": "2026-03-25",
            "incident_type": "injury",
            "description": "Chute",
            "visible_to_skater": True,
        },
        headers={"Authorization": f"Bearer {token}"},
    )

    resp = await client.get(
        f"/api/training/timeline?skater_id={skater.id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2
    # Most recent first
    assert data[0]["type"] == "incident"
    assert data[1]["type"] == "review"


async def test_timeline_skater_sees_only_visible(client, coach_and_skater, db_session):
    _, coach_token, skater = coach_and_skater

    parent = User(
        email="parent@test.com",
        password_hash=hash_password("parentpass1"),
        display_name="Parent",
        role="skater",
    )
    db_session.add(parent)
    await db_session.flush()
    link = UserSkater(user_id=parent.id, skater_id=skater.id)
    db_session.add(link)
    await db_session.commit()
    await db_session.refresh(parent)
    parent_token = create_access_token(user_id=parent.id, role=parent.role)

    # Visible review + hidden incident
    await client.post(
        "/api/training/reviews",
        json={
            "skater_id": skater.id,
            "week_start": "2026-03-23",
            "attendance": "3/4",
            "engagement": 4,
            "progression": 3,
            "attitude": 5,
            "strengths": "Bon",
            "improvements": "Mieux",
            "visible_to_skater": True,
        },
        headers={"Authorization": f"Bearer {coach_token}"},
    )
    await client.post(
        "/api/training/incidents",
        json={
            "skater_id": skater.id,
            "date": "2026-03-25",
            "incident_type": "injury",
            "description": "Chute",
            "visible_to_skater": False,
        },
        headers={"Authorization": f"Bearer {coach_token}"},
    )

    resp = await client.get(
        f"/api/training/timeline?skater_id={skater.id}",
        headers={"Authorization": f"Bearer {parent_token}"},
    )
    assert resp.status_code == 200
    assert len(resp.json()) == 1
    assert resp.json()[0]["type"] == "review"
