import pytest
from datetime import date

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


async def test_create_incident(client, coach_and_skater):
    coach, token, skater = coach_and_skater
    resp = await client.post(
        "/api/training/incidents",
        json={
            "skater_id": skater.id,
            "date": "2026-03-24",
            "incident_type": "injury",
            "description": "Douleur au genou",
            "visible_to_skater": False,
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["incident_type"] == "injury"
    assert data["visible_to_skater"] is False


async def test_update_incident(client, coach_and_skater):
    _, token, skater = coach_and_skater
    create_resp = await client.post(
        "/api/training/incidents",
        json={
            "skater_id": skater.id,
            "date": "2026-03-24",
            "incident_type": "behavior",
            "description": "Retard",
            "visible_to_skater": False,
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    incident_id = create_resp.json()["id"]
    resp = await client.put(
        f"/api/training/incidents/{incident_id}",
        json={"description": "Retard répété", "visible_to_skater": True},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["description"] == "Retard répété"
    assert resp.json()["visible_to_skater"] is True


async def test_delete_incident(client, coach_and_skater):
    _, token, skater = coach_and_skater
    create_resp = await client.post(
        "/api/training/incidents",
        json={
            "skater_id": skater.id,
            "date": "2026-03-24",
            "incident_type": "other",
            "description": "Test",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    incident_id = create_resp.json()["id"]
    resp = await client.delete(
        f"/api/training/incidents/{incident_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 204


async def test_skater_hidden_incident_not_visible(client, coach_and_skater, db_session):
    _, coach_token, skater = coach_and_skater

    # Create parent linked to skater
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

    # Create hidden incident
    await client.post(
        "/api/training/incidents",
        json={
            "skater_id": skater.id,
            "date": "2026-03-24",
            "incident_type": "injury",
            "description": "Chute",
            "visible_to_skater": False,
        },
        headers={"Authorization": f"Bearer {coach_token}"},
    )

    resp = await client.get(
        f"/api/training/incidents?skater_id={skater.id}",
        headers={"Authorization": f"Bearer {parent_token}"},
    )
    assert resp.status_code == 200
    assert len(resp.json()) == 0
