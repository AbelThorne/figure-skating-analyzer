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


@pytest.mark.asyncio
async def test_create_skater_user_with_linked_skaters(db_session):
    """Verify user_skaters association works at model level."""
    from app.models.user import User
    from app.models.skater import Skater
    from app.models.user_skater import UserSkater
    from sqlalchemy import select

    skater = Skater(first_name="Alice", last_name="Dupont", club="TestClub")
    db_session.add(skater)
    await db_session.flush()

    user = User(
        email="parent@test.com",
        display_name="Parent",
        role="skater",
        password_hash="fakehash",
    )
    db_session.add(user)
    await db_session.flush()

    link = UserSkater(user_id=user.id, skater_id=skater.id)
    db_session.add(link)
    await db_session.commit()

    result = await db_session.execute(
        select(UserSkater).where(UserSkater.user_id == user.id)
    )
    links = result.scalars().all()
    assert len(links) == 1
    assert links[0].skater_id == skater.id
