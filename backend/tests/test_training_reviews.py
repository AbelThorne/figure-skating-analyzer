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


@pytest.fixture
async def skater_parent(db_session, coach_and_skater):
    _, _, skater = coach_and_skater
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
    token = create_access_token(user_id=parent.id, role=parent.role)
    return parent, token


async def test_create_review(client, coach_and_skater):
    coach, token, skater = coach_and_skater
    resp = await client.post(
        "/api/training/reviews",
        json={
            "skater_id": skater.id,
            "week_start": "2026-03-23",
            "attendance": "3/4",
            "engagement": 4,
            "progression": 3,
            "attitude": 5,
            "strengths": "Bon travail",
            "improvements": "Pirouettes",
            "visible_to_skater": True,
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["skater_id"] == skater.id
    assert data["engagement"] == 4
    assert data["coach_id"] == coach.id


async def test_create_review_auto_monday(client, coach_and_skater):
    _, token, skater = coach_and_skater
    resp = await client.post(
        "/api/training/reviews",
        json={
            "skater_id": skater.id,
            "week_start": "2026-03-25",
            "attendance": "4/4",
            "engagement": 3,
            "progression": 3,
            "attitude": 3,
            "strengths": "",
            "improvements": "",
            "visible_to_skater": True,
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201
    assert resp.json()["week_start"] == "2026-03-23"


async def test_list_reviews(client, coach_and_skater):
    _, token, skater = coach_and_skater
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
    resp = await client.get(
        f"/api/training/reviews?skater_id={skater.id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert len(resp.json()) == 1


async def test_update_review(client, coach_and_skater):
    coach, token, skater = coach_and_skater
    create_resp = await client.post(
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
    review_id = create_resp.json()["id"]
    resp = await client.put(
        f"/api/training/reviews/{review_id}",
        json={"engagement": 5, "strengths": "Excellent travail"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["engagement"] == 5
    assert resp.json()["strengths"] == "Excellent travail"


async def test_delete_review(client, coach_and_skater):
    _, token, skater = coach_and_skater
    create_resp = await client.post(
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
    review_id = create_resp.json()["id"]
    resp = await client.delete(
        f"/api/training/reviews/{review_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 204


async def test_reader_cannot_create_review(client, coach_and_skater, reader_token):
    _, _, skater = coach_and_skater
    resp = await client.post(
        "/api/training/reviews",
        json={
            "skater_id": skater.id,
            "week_start": "2026-03-23",
            "attendance": "3/4",
            "engagement": 4,
            "progression": 3,
            "attitude": 5,
            "strengths": "",
            "improvements": "",
            "visible_to_skater": True,
        },
        headers={"Authorization": f"Bearer {reader_token}"},
    )
    assert resp.status_code == 403


async def test_skater_sees_visible_reviews(client, coach_and_skater, skater_parent):
    _, coach_token, skater = coach_and_skater
    parent, parent_token = skater_parent

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
        "/api/training/reviews",
        json={
            "skater_id": skater.id,
            "week_start": "2026-03-16",
            "attendance": "2/4",
            "engagement": 2,
            "progression": 2,
            "attitude": 2,
            "strengths": "",
            "improvements": "",
            "visible_to_skater": False,
        },
        headers={"Authorization": f"Bearer {coach_token}"},
    )

    resp = await client.get(
        f"/api/training/reviews?skater_id={skater.id}",
        headers={"Authorization": f"Bearer {parent_token}"},
    )
    assert resp.status_code == 200
    assert len(resp.json()) == 1
