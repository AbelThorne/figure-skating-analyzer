# backend/tests/test_self_eval.py
import pytest

from app.models.skater import Skater


@pytest.fixture
async def skater(db_session):
    """Create a standalone skater for self-eval tests."""
    s = Skater(first_name="Lea", last_name="Petit", club="TestClub")
    db_session.add(s)
    await db_session.commit()
    await db_session.refresh(s)
    return s


# ── Programs ─────────────────────────────────────────────────────────────────


async def test_upsert_program_skater(client, skater_token, skater_user_with_skater):
    _, _, skater = skater_user_with_skater
    resp = await client.put(
        "/api/training/programs",
        json={"skater_id": skater.id, "segment": "SP", "elements": ["2A", "3Lz", "CCoSp4"]},
        headers={"Authorization": f"Bearer {skater_token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["segment"] == "SP"
    assert data["elements"] == ["2A", "3Lz", "CCoSp4"]


async def test_upsert_program_updates_existing(client, skater_token, skater_user_with_skater):
    _, _, skater = skater_user_with_skater
    await client.put(
        "/api/training/programs",
        json={"skater_id": skater.id, "segment": "SP", "elements": ["2A"]},
        headers={"Authorization": f"Bearer {skater_token}"},
    )
    resp = await client.put(
        "/api/training/programs",
        json={"skater_id": skater.id, "segment": "SP", "elements": ["2A", "3F"]},
        headers={"Authorization": f"Bearer {skater_token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["elements"] == ["2A", "3F"]


async def test_list_programs(client, skater_token, skater_user_with_skater):
    _, _, skater = skater_user_with_skater
    await client.put(
        "/api/training/programs",
        json={"skater_id": skater.id, "segment": "SP", "elements": ["2A"]},
        headers={"Authorization": f"Bearer {skater_token}"},
    )
    resp = await client.get(
        f"/api/training/programs?skater_id={skater.id}",
        headers={"Authorization": f"Bearer {skater_token}"},
    )
    assert resp.status_code == 200
    assert len(resp.json()) == 1


async def test_delete_program(client, skater_token, skater_user_with_skater):
    _, _, skater = skater_user_with_skater
    create_resp = await client.put(
        "/api/training/programs",
        json={"skater_id": skater.id, "segment": "FS", "elements": ["3Lz"]},
        headers={"Authorization": f"Bearer {skater_token}"},
    )
    program_id = create_resp.json()["id"]
    resp = await client.delete(
        f"/api/training/programs/{program_id}",
        headers={"Authorization": f"Bearer {skater_token}"},
    )
    assert resp.status_code == 204


async def test_program_invalid_segment(client, skater_token, skater_user_with_skater):
    _, _, skater = skater_user_with_skater
    resp = await client.put(
        "/api/training/programs",
        json={"skater_id": skater.id, "segment": "XY", "elements": []},
        headers={"Authorization": f"Bearer {skater_token}"},
    )
    assert resp.status_code == 403


async def test_reader_no_access_programs(client, reader_token, skater_user_with_skater):
    _, _, skater = skater_user_with_skater
    resp = await client.get(
        f"/api/training/programs?skater_id={skater.id}",
        headers={"Authorization": f"Bearer {reader_token}"},
    )
    assert resp.status_code == 403


async def test_coach_can_read_programs(client, coach_token, skater_user_with_skater, skater_token):
    _, _, skater = skater_user_with_skater
    await client.put(
        "/api/training/programs",
        json={"skater_id": skater.id, "segment": "SP", "elements": ["2A"]},
        headers={"Authorization": f"Bearer {skater_token}"},
    )
    resp = await client.get(
        f"/api/training/programs?skater_id={skater.id}",
        headers={"Authorization": f"Bearer {coach_token}"},
    )
    assert resp.status_code == 200
    assert len(resp.json()) == 1


# ── Moods ─────────────────────────────────────────────────────────────────


async def test_create_mood(client, skater_token, skater_user_with_skater):
    _, _, skater = skater_user_with_skater
    resp = await client.post(
        "/api/training/moods",
        json={"skater_id": skater.id, "date": "2026-03-31", "rating": 4},
        headers={"Authorization": f"Bearer {skater_token}"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["rating"] == 4
    assert data["date"] == "2026-03-31"


async def test_create_mood_duplicate_409(client, skater_token, skater_user_with_skater):
    _, _, skater = skater_user_with_skater
    await client.post(
        "/api/training/moods",
        json={"skater_id": skater.id, "date": "2026-03-30", "rating": 3},
        headers={"Authorization": f"Bearer {skater_token}"},
    )
    resp = await client.post(
        "/api/training/moods",
        json={"skater_id": skater.id, "date": "2026-03-30", "rating": 5},
        headers={"Authorization": f"Bearer {skater_token}"},
    )
    assert resp.status_code == 409


async def test_update_mood(client, skater_token, skater_user_with_skater):
    _, _, skater = skater_user_with_skater
    create_resp = await client.post(
        "/api/training/moods",
        json={"skater_id": skater.id, "date": "2026-03-29", "rating": 2},
        headers={"Authorization": f"Bearer {skater_token}"},
    )
    mood_id = create_resp.json()["id"]
    resp = await client.put(
        f"/api/training/moods/{mood_id}",
        json={"rating": 5},
        headers={"Authorization": f"Bearer {skater_token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["rating"] == 5


async def test_mood_rating_out_of_range(client, skater_token, skater_user_with_skater):
    _, _, skater = skater_user_with_skater
    resp = await client.post(
        "/api/training/moods",
        json={"skater_id": skater.id, "date": "2026-03-28", "rating": 6},
        headers={"Authorization": f"Bearer {skater_token}"},
    )
    assert resp.status_code == 403


async def test_list_moods(client, skater_token, skater_user_with_skater):
    _, _, skater = skater_user_with_skater
    await client.post(
        "/api/training/moods",
        json={"skater_id": skater.id, "date": "2026-03-25", "rating": 4},
        headers={"Authorization": f"Bearer {skater_token}"},
    )
    await client.post(
        "/api/training/moods",
        json={"skater_id": skater.id, "date": "2026-03-26", "rating": 3},
        headers={"Authorization": f"Bearer {skater_token}"},
    )
    resp = await client.get(
        f"/api/training/moods?skater_id={skater.id}",
        headers={"Authorization": f"Bearer {skater_token}"},
    )
    assert resp.status_code == 200
    assert len(resp.json()) == 2


async def test_coach_can_read_moods(client, coach_token, skater_token, skater_user_with_skater):
    _, _, skater = skater_user_with_skater
    await client.post(
        "/api/training/moods",
        json={"skater_id": skater.id, "date": "2026-03-24", "rating": 4},
        headers={"Authorization": f"Bearer {skater_token}"},
    )
    resp = await client.get(
        f"/api/training/moods?skater_id={skater.id}",
        headers={"Authorization": f"Bearer {coach_token}"},
    )
    assert resp.status_code == 200
    assert len(resp.json()) == 1


async def test_coach_cannot_create_mood(client, coach_token, skater_user_with_skater):
    _, _, skater = skater_user_with_skater
    resp = await client.post(
        "/api/training/moods",
        json={"skater_id": skater.id, "date": "2026-03-23", "rating": 3},
        headers={"Authorization": f"Bearer {coach_token}"},
    )
    assert resp.status_code == 403


async def test_reader_no_access_moods(client, reader_token, skater_user_with_skater):
    _, _, skater = skater_user_with_skater
    resp = await client.get(
        f"/api/training/moods?skater_id={skater.id}",
        headers={"Authorization": f"Bearer {reader_token}"},
    )
    assert resp.status_code == 403


async def test_weekly_summary(client, coach_token, skater_token, skater_user_with_skater):
    _, _, skater = skater_user_with_skater
    for day, rating in [("2026-03-24", 4), ("2026-03-25", 5), ("2026-03-26", 3)]:
        await client.post(
            "/api/training/moods",
            json={"skater_id": skater.id, "date": day, "rating": rating},
            headers={"Authorization": f"Bearer {skater_token}"},
        )
    resp = await client.get(
        "/api/training/moods/weekly-summary?from_date=2026-03-24&to_date=2026-03-26",
        headers={"Authorization": f"Bearer {coach_token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["average"] == 4.0
    assert data["count"] == 3
    assert data["distribution"] == [0, 0, 1, 1, 1]


async def test_weekly_summary_empty(client, coach_token):
    resp = await client.get(
        "/api/training/moods/weekly-summary?from_date=2099-01-01&to_date=2099-01-07",
        headers={"Authorization": f"Bearer {coach_token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["average"] is None
    assert data["count"] == 0


async def test_skater_cannot_view_weekly_summary(client, skater_token):
    resp = await client.get(
        "/api/training/moods/weekly-summary",
        headers={"Authorization": f"Bearer {skater_token}"},
    )
    assert resp.status_code == 403


# ── Self-Evaluations ─────────────────────────────────────────────────────


async def test_create_self_evaluation(client, skater_token, skater_user_with_skater):
    _, _, skater = skater_user_with_skater
    resp = await client.post(
        "/api/training/self-evaluations",
        json={
            "skater_id": skater.id,
            "date": "2026-03-31",
            "notes": "Good session",
            "element_ratings": [{"name": "3Lz", "rating": 4}],
            "shared": False,
        },
        headers={"Authorization": f"Bearer {skater_token}"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["notes"] == "Good session"
    assert data["shared"] is False
    assert data["element_ratings"] == [{"name": "3Lz", "rating": 4}]


async def test_create_self_evaluation_duplicate_409(client, skater_token, skater_user_with_skater):
    _, _, skater = skater_user_with_skater
    await client.post(
        "/api/training/self-evaluations",
        json={"skater_id": skater.id, "date": "2026-03-30", "notes": "First"},
        headers={"Authorization": f"Bearer {skater_token}"},
    )
    resp = await client.post(
        "/api/training/self-evaluations",
        json={"skater_id": skater.id, "date": "2026-03-30", "notes": "Second"},
        headers={"Authorization": f"Bearer {skater_token}"},
    )
    assert resp.status_code == 409


async def test_update_self_evaluation_toggle_shared(client, skater_token, skater_user_with_skater):
    _, _, skater = skater_user_with_skater
    create_resp = await client.post(
        "/api/training/self-evaluations",
        json={"skater_id": skater.id, "date": "2026-03-29", "notes": "Test", "shared": False},
        headers={"Authorization": f"Bearer {skater_token}"},
    )
    eval_id = create_resp.json()["id"]
    resp = await client.put(
        f"/api/training/self-evaluations/{eval_id}",
        json={"shared": True},
        headers={"Authorization": f"Bearer {skater_token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["shared"] is True


async def test_coach_sees_only_shared_evaluations(
    client, coach_token, skater_token, skater_user_with_skater,
):
    _, _, skater = skater_user_with_skater
    await client.post(
        "/api/training/self-evaluations",
        json={"skater_id": skater.id, "date": "2026-03-27", "notes": "Private", "shared": False},
        headers={"Authorization": f"Bearer {skater_token}"},
    )
    await client.post(
        "/api/training/self-evaluations",
        json={"skater_id": skater.id, "date": "2026-03-28", "notes": "Shared", "shared": True},
        headers={"Authorization": f"Bearer {skater_token}"},
    )
    resp = await client.get(
        f"/api/training/self-evaluations?skater_id={skater.id}",
        headers={"Authorization": f"Bearer {coach_token}"},
    )
    assert resp.status_code == 200
    evals = resp.json()
    assert len(evals) == 1
    assert evals[0]["notes"] == "Shared"


async def test_skater_sees_all_own_evaluations(client, skater_token, skater_user_with_skater):
    _, _, skater = skater_user_with_skater
    await client.post(
        "/api/training/self-evaluations",
        json={"skater_id": skater.id, "date": "2026-03-25", "notes": "Private", "shared": False},
        headers={"Authorization": f"Bearer {skater_token}"},
    )
    await client.post(
        "/api/training/self-evaluations",
        json={"skater_id": skater.id, "date": "2026-03-26", "notes": "Shared", "shared": True},
        headers={"Authorization": f"Bearer {skater_token}"},
    )
    resp = await client.get(
        f"/api/training/self-evaluations?skater_id={skater.id}",
        headers={"Authorization": f"Bearer {skater_token}"},
    )
    assert resp.status_code == 200
    assert len(resp.json()) == 2


async def test_delete_self_evaluation(client, skater_token, skater_user_with_skater):
    _, _, skater = skater_user_with_skater
    create_resp = await client.post(
        "/api/training/self-evaluations",
        json={"skater_id": skater.id, "date": "2026-03-24", "notes": "Delete me"},
        headers={"Authorization": f"Bearer {skater_token}"},
    )
    eval_id = create_resp.json()["id"]
    resp = await client.delete(
        f"/api/training/self-evaluations/{eval_id}",
        headers={"Authorization": f"Bearer {skater_token}"},
    )
    assert resp.status_code == 204


async def test_reader_no_access_self_evaluations(client, reader_token, skater_user_with_skater):
    _, _, skater = skater_user_with_skater
    resp = await client.get(
        f"/api/training/self-evaluations?skater_id={skater.id}",
        headers={"Authorization": f"Bearer {reader_token}"},
    )
    assert resp.status_code == 403


async def test_coach_cannot_create_self_evaluation(client, coach_token, skater_user_with_skater):
    _, _, skater = skater_user_with_skater
    resp = await client.post(
        "/api/training/self-evaluations",
        json={"skater_id": skater.id, "date": "2026-03-23", "notes": "Coach eval"},
        headers={"Authorization": f"Bearer {coach_token}"},
    )
    assert resp.status_code == 403


async def test_self_evaluation_links_mood(client, skater_token, skater_user_with_skater):
    _, _, skater = skater_user_with_skater
    mood_resp = await client.post(
        "/api/training/moods",
        json={"skater_id": skater.id, "date": "2026-03-22", "rating": 4},
        headers={"Authorization": f"Bearer {skater_token}"},
    )
    mood_id = mood_resp.json()["id"]
    eval_resp = await client.post(
        "/api/training/self-evaluations",
        json={"skater_id": skater.id, "date": "2026-03-22", "notes": "Linked"},
        headers={"Authorization": f"Bearer {skater_token}"},
    )
    assert eval_resp.status_code == 201
    assert eval_resp.json()["mood_id"] == mood_id
