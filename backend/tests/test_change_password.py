"""Tests for password change endpoint."""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.user import User


@pytest.mark.asyncio
async def test_change_password_success(client: AsyncClient, admin_user, admin_token: str, db_session: AsyncSession):
    user, old_password = admin_user
    resp = await client.post(
        "/api/auth/change-password",
        json={"current_password": old_password, "new_password": "newpass1234"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert data["user"]["email"] == user.email

    # Verify can login with new password
    login_resp = await client.post(
        "/api/auth/login",
        json={"email": user.email, "password": "newpass1234"},
    )
    assert login_resp.status_code == 200


@pytest.mark.asyncio
async def test_change_password_wrong_current(client: AsyncClient, admin_token: str):
    resp = await client.post(
        "/api/auth/change-password",
        json={"current_password": "wrongpassword", "new_password": "newpass1234"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_change_password_too_short(client: AsyncClient, admin_user, admin_token: str):
    _, old_password = admin_user
    resp = await client.post(
        "/api/auth/change-password",
        json={"current_password": old_password, "new_password": "short"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_change_password_clears_must_change_flag(client: AsyncClient, admin_user, admin_token: str, db_session: AsyncSession):
    user, old_password = admin_user
    # Set the flag
    user.must_change_password = True
    await db_session.commit()

    resp = await client.post(
        "/api/auth/change-password",
        json={"current_password": old_password, "new_password": "newpass1234"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["user"]["must_change_password"] is False

    # Verify in DB
    await db_session.refresh(user)
    assert user.must_change_password is False


@pytest.mark.asyncio
async def test_change_password_increments_token_version(client: AsyncClient, admin_user, admin_token: str, db_session: AsyncSession):
    user, old_password = admin_user
    old_version = user.token_version

    resp = await client.post(
        "/api/auth/change-password",
        json={"current_password": old_password, "new_password": "newpass1234"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200

    await db_session.refresh(user)
    assert user.token_version == old_version + 1


@pytest.mark.asyncio
async def test_change_password_oauth_only_user(client: AsyncClient, db_session: AsyncSession):
    from app.auth.tokens import create_access_token

    oauth_user = User(
        email="oauth@test.com",
        display_name="OAuth User",
        role="reader",
        password_hash=None,
        google_oauth_enabled=True,
    )
    db_session.add(oauth_user)
    await db_session.commit()
    await db_session.refresh(oauth_user)

    token = create_access_token(user_id=oauth_user.id, role=oauth_user.role)
    resp = await client.post(
        "/api/auth/change-password",
        json={"current_password": "anything", "new_password": "newpass1234"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 400
    assert "OAuth" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_change_password_unauthenticated(client: AsyncClient):
    resp = await client.post(
        "/api/auth/change-password",
        json={"current_password": "old", "new_password": "newpass1234"},
    )
    assert resp.status_code == 401
