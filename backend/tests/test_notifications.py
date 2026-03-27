"""Tests for the notification system (in-app + email preferences)."""
import pytest
from app.models.notification import Notification
from app.models.skater import Skater
from app.models.user_skater import UserSkater
from app.models.weekly_review import WeeklyReview
from app.models.incident import Incident
from datetime import date, datetime, timezone


@pytest.mark.asyncio
async def test_unread_count_empty(client, admin_token):
    res = await client.get(
        "/api/me/notifications/count",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert res.status_code == 200
    assert res.json()["count"] == 0


@pytest.mark.asyncio
async def test_list_notifications_empty(client, admin_token):
    res = await client.get(
        "/api/me/notifications/",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert res.status_code == 200
    assert res.json() == []


@pytest.mark.asyncio
async def test_create_review_creates_notification(
    client, db_session, coach_token, skater_user_with_skater
):
    """When a coach creates a visible review, the linked skater user gets a notification."""
    user, _, skater = skater_user_with_skater

    res = await client.post(
        "/api/training/reviews",
        json={
            "skater_id": skater.id,
            "week_start": "2026-03-23",
            "engagement": 4,
            "progression": 3,
            "attitude": 5,
            "strengths": "Bon travail",
            "improvements": "Sauts",
            "visible_to_skater": True,
        },
        headers={"Authorization": f"Bearer {coach_token}"},
    )
    assert res.status_code == 201

    from sqlalchemy import select
    result = await db_session.execute(
        select(Notification).where(Notification.user_id == user.id)
    )
    notifs = result.scalars().all()
    assert len(notifs) == 1
    assert notifs[0].type == "review"
    assert "Alice Dupont" in notifs[0].title
    assert notifs[0].is_read is False


@pytest.mark.asyncio
async def test_create_review_no_notification_when_not_visible(
    client, db_session, coach_token, skater_user_with_skater
):
    user, _, skater = skater_user_with_skater

    res = await client.post(
        "/api/training/reviews",
        json={
            "skater_id": skater.id,
            "week_start": "2026-03-23",
            "engagement": 4,
            "progression": 3,
            "attitude": 5,
            "visible_to_skater": False,
        },
        headers={"Authorization": f"Bearer {coach_token}"},
    )
    assert res.status_code == 201

    from sqlalchemy import select
    result = await db_session.execute(
        select(Notification).where(Notification.user_id == user.id)
    )
    assert len(result.scalars().all()) == 0


@pytest.mark.asyncio
async def test_create_incident_creates_notification(
    client, db_session, coach_token, skater_user_with_skater
):
    user, _, skater = skater_user_with_skater

    res = await client.post(
        "/api/training/incidents",
        json={
            "skater_id": skater.id,
            "date": "2026-03-25",
            "incident_type": "injury",
            "description": "Cheville tordue",
            "visible_to_skater": True,
        },
        headers={"Authorization": f"Bearer {coach_token}"},
    )
    assert res.status_code == 201

    from sqlalchemy import select
    result = await db_session.execute(
        select(Notification).where(Notification.user_id == user.id)
    )
    notifs = result.scalars().all()
    assert len(notifs) == 1
    assert notifs[0].type == "incident"
    assert "Alice Dupont" in notifs[0].title


@pytest.mark.asyncio
async def test_mark_read(client, db_session, admin_user, admin_token):
    user, _ = admin_user
    notif = Notification(
        user_id=user.id,
        type="review",
        title="Test",
        message="Test message",
        link="/test",
    )
    db_session.add(notif)
    await db_session.commit()
    await db_session.refresh(notif)

    res = await client.patch(
        f"/api/me/notifications/{notif.id}/read",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert res.status_code == 200
    assert res.json()["is_read"] is True


@pytest.mark.asyncio
async def test_mark_all_read(client, db_session, admin_user, admin_token):
    user, _ = admin_user
    for i in range(3):
        db_session.add(Notification(
            user_id=user.id, type="review", title=f"Test {i}", message="", link="/test"
        ))
    await db_session.commit()

    res = await client.post(
        "/api/me/notifications/read-all",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert res.status_code == 200
    assert res.json()["marked"] == 3

    res = await client.get(
        "/api/me/notifications/count",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert res.json()["count"] == 0


@pytest.mark.asyncio
async def test_update_preferences(client, admin_token):
    res = await client.patch(
        "/api/me/preferences",
        json={"email_notifications": False},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert res.status_code == 200
    assert res.json()["email_notifications"] is False

    res = await client.patch(
        "/api/me/preferences",
        json={"email_notifications": True},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert res.json()["email_notifications"] is True
