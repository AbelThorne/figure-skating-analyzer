import pytest
from app.auth.tokens import create_access_token


@pytest.fixture
async def coach_user(db_session):
    from app.models.user import User
    from app.auth.passwords import hash_password

    user = User(
        email="coach@test.com",
        password_hash=hash_password("coachpass1"),
        display_name="Test Coach",
        role="coach",
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user, "coachpass1"


@pytest.fixture
async def coach_token(coach_user) -> str:
    user, _ = coach_user
    return create_access_token(user_id=user.id, role=user.role)


async def test_coach_role_created(coach_user):
    user, _ = coach_user
    assert user.role == "coach"


async def test_coach_can_login(client, coach_user):
    _, password = coach_user
    resp = await client.post("/api/auth/login", json={
        "email": "coach@test.com",
        "password": password,
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["user"]["role"] == "coach"
