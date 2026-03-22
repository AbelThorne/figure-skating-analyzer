import pytest


@pytest.mark.asyncio
async def test_login_success(client, admin_user):
    user, password = admin_user
    resp = await client.post(
        "/api/auth/login",
        json={"email": user.email, "password": password},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert data["user"]["email"] == user.email
    assert data["user"]["role"] == "admin"
    assert "refresh_token" in resp.cookies


@pytest.mark.asyncio
async def test_login_wrong_password(client, admin_user):
    user, _ = admin_user
    resp = await client.post(
        "/api/auth/login",
        json={"email": user.email, "password": "wrongpass"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_login_nonexistent_email(client, db_session):
    resp = await client.post(
        "/api/auth/login",
        json={"email": "nobody@test.com", "password": "whatever"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_login_short_password_rejected(client, db_session):
    """Setup endpoint should reject passwords shorter than 8 chars."""
    resp = await client.post(
        "/api/auth/setup",
        json={
            "email": "admin@test.com",
            "password": "short",
            "display_name": "Admin",
            "club_name": "Club",
            "club_short": "CL",
        },
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_refresh_token(client, admin_user):
    user, password = admin_user
    login_resp = await client.post(
        "/api/auth/login",
        json={"email": user.email, "password": password},
    )
    assert login_resp.status_code == 200
    # Extract refresh cookie and send it explicitly
    refresh_cookie = login_resp.cookies.get("refresh_token")
    assert refresh_cookie is not None
    client.cookies.set("refresh_token", refresh_cookie)
    resp = await client.post("/api/auth/refresh")
    assert resp.status_code == 200
    assert "access_token" in resp.json()


@pytest.mark.asyncio
async def test_logout_clears_cookie(client, admin_user):
    user, password = admin_user
    await client.post(
        "/api/auth/login",
        json={"email": user.email, "password": password},
    )
    resp = await client.post("/api/auth/logout")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_protected_route_requires_token(client, db_session):
    resp = await client.get("/api/competitions/")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_protected_route_with_valid_token(client, admin_token):
    resp = await client.get(
        "/api/competitions/",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
