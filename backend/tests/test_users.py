import pytest


@pytest.mark.asyncio
async def test_list_users_as_admin(client, admin_token):
    resp = await client.get(
        "/api/users/",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


@pytest.mark.asyncio
async def test_list_users_as_reader_forbidden(client, reader_token):
    resp = await client.get(
        "/api/users/",
        headers={"Authorization": f"Bearer {reader_token}"},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_create_user(client, admin_token):
    resp = await client.post(
        "/api/users/",
        json={
            "email": "newuser@test.com",
            "display_name": "New User",
            "role": "reader",
            "password": "password123",
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 201
    assert resp.json()["email"] == "newuser@test.com"


@pytest.mark.asyncio
async def test_update_user_role(client, admin_token, reader_user):
    user, _ = reader_user
    resp = await client.patch(
        f"/api/users/{user.id}",
        json={"role": "admin"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["role"] == "admin"


@pytest.mark.asyncio
async def test_delete_last_admin_prevented(client, admin_token, admin_user):
    user, _ = admin_user
    resp = await client.delete(
        f"/api/users/{user.id}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 400
