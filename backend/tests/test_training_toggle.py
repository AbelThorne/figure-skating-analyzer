"""Tests for training_enabled toggle in AppSettings / config API."""
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession


@pytest.mark.asyncio
async def test_config_returns_training_enabled_default_false(client: AsyncClient, db_session: AsyncSession):
    """GET /api/config should return training_enabled=False by default."""
    from app.models.app_settings import AppSettings

    settings = AppSettings(club_name="Test Club", club_short="TC", current_season="2025-2026")
    db_session.add(settings)
    await db_session.commit()

    res = await client.get("/api/config/")
    assert res.status_code == 200
    data = res.json()
    assert "training_enabled" in data
    assert data["training_enabled"] is False


@pytest.mark.asyncio
async def test_admin_can_enable_training(client: AsyncClient, admin_token: str, db_session: AsyncSession):
    """PATCH /api/config with training_enabled=true should persist."""
    from app.models.app_settings import AppSettings

    settings = AppSettings(club_name="Test Club", club_short="TC", current_season="2025-2026")
    db_session.add(settings)
    await db_session.commit()

    res = await client.patch(
        "/api/config/",
        json={"training_enabled": True},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert res.status_code == 200
    assert res.json()["training_enabled"] is True

    # Verify GET returns updated value
    res = await client.get("/api/config/")
    assert res.json()["training_enabled"] is True


@pytest.mark.asyncio
async def test_admin_can_disable_training(client: AsyncClient, admin_token: str, db_session: AsyncSession):
    """Enable then disable training module."""
    from app.models.app_settings import AppSettings

    settings = AppSettings(club_name="Test Club", club_short="TC", current_season="2025-2026")
    db_session.add(settings)
    await db_session.commit()

    await client.patch(
        "/api/config/",
        json={"training_enabled": True},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    res = await client.patch(
        "/api/config/",
        json={"training_enabled": False},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert res.status_code == 200
    assert res.json()["training_enabled"] is False


@pytest.mark.asyncio
async def test_reader_cannot_toggle_training(client: AsyncClient, reader_token: str, db_session: AsyncSession):
    """Non-admin should be rejected."""
    from app.models.app_settings import AppSettings

    settings = AppSettings(club_name="Test Club", club_short="TC", current_season="2025-2026")
    db_session.add(settings)
    await db_session.commit()

    res = await client.patch(
        "/api/config/",
        json={"training_enabled": True},
        headers={"Authorization": f"Bearer {reader_token}"},
    )
    assert res.status_code == 403
