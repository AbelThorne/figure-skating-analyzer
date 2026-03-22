import pytest


@pytest.mark.asyncio
async def test_full_setup_and_auth_flow(client, db_session):
    """Integration test: setup → login → access protected route → logout → blocked."""

    # 1. Config should show setup_required
    resp = await client.get("/api/config/")
    assert resp.status_code == 200
    assert resp.json()["setup_required"] is True

    # 2. Setup first admin
    resp = await client.post(
        "/api/auth/setup",
        json={
            "email": "admin@integration.test",
            "password": "integration123",
            "display_name": "Integration Admin",
            "club_name": "Test Club",
            "club_short": "TC",
        },
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["user"]["role"] == "admin"
    access_token = data["access_token"]

    # 3. Config should no longer require setup
    resp = await client.get("/api/config/")
    assert resp.json()["setup_required"] is False
    assert resp.json()["club_name"] == "Test Club"

    # 4. Access protected route with token
    resp = await client.get(
        "/api/competitions/",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert resp.status_code == 200

    # 5. Access protected route without token -> 401
    resp = await client.get("/api/competitions/")
    assert resp.status_code == 401

    # 6. Setup should fail (already completed)
    resp = await client.post(
        "/api/auth/setup",
        json={
            "email": "another@test.com",
            "password": "password123",
            "display_name": "Another",
            "club_name": "Other",
            "club_short": "OT",
        },
    )
    assert resp.status_code == 403

    # 7. Create a reader user
    resp = await client.post(
        "/api/users/",
        json={
            "email": "reader@integration.test",
            "display_name": "Reader",
            "role": "reader",
            "password": "readerpass1",
        },
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert resp.status_code == 201

    # 8. Login as reader
    resp = await client.post(
        "/api/auth/login",
        json={"email": "reader@integration.test", "password": "readerpass1"},
    )
    assert resp.status_code == 200
    reader_token = resp.json()["access_token"]

    # 9. Reader cannot access admin endpoints
    resp = await client.get(
        "/api/users/",
        headers={"Authorization": f"Bearer {reader_token}"},
    )
    assert resp.status_code == 403

    # 10. Reader can access competitions
    resp = await client.get(
        "/api/competitions/",
        headers={"Authorization": f"Bearer {reader_token}"},
    )
    assert resp.status_code == 200

    # 11. Health endpoint is public
    resp = await client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}
