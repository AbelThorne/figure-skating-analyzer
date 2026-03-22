import pytest


@pytest.mark.asyncio
async def test_get_config_no_auth_required(client, db_session):
    """GET /api/config must work without authentication."""
    resp = await client.get("/api/config/")
    assert resp.status_code == 200
    data = resp.json()
    assert "setup_required" in data


@pytest.mark.asyncio
async def test_setup_required_when_no_settings(client, db_session):
    resp = await client.get("/api/config/")
    assert resp.json()["setup_required"] is True


@pytest.mark.asyncio
async def test_config_returns_settings(client, db_session):
    from app.models.app_settings import AppSettings

    settings = AppSettings(
        club_name="Test Club", club_short="TC", current_season="2025-2026"
    )
    db_session.add(settings)
    await db_session.commit()

    resp = await client.get("/api/config/")
    data = resp.json()
    assert data["setup_required"] is False
    assert data["club_name"] == "Test Club"
    assert data["club_short"] == "TC"


@pytest.mark.asyncio
async def test_patch_config_admin_only(client, reader_token, db_session):
    from app.models.app_settings import AppSettings

    settings = AppSettings(club_name="X", club_short="X", current_season="2025-2026")
    db_session.add(settings)
    await db_session.commit()

    resp = await client.patch(
        "/api/config/",
        json={"club_name": "New Name"},
        headers={"Authorization": f"Bearer {reader_token}"},
    )
    assert resp.status_code == 403
