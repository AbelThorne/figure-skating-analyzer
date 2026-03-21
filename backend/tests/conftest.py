import asyncio
from typing import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.database import Base
from app.auth.passwords import hash_password

# Use in-memory SQLite for tests
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

_test_engine = create_async_engine(TEST_DATABASE_URL, echo=False)
_test_session_factory = async_sessionmaker(_test_engine, expire_on_commit=False)


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    # Import all models so metadata is populated
    import app.models  # noqa: F401

    async with _test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with _test_session_factory() as session:
        yield session

    async with _test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def client(db_session: AsyncSession, monkeypatch) -> AsyncGenerator[AsyncClient, None]:
    """Async test client with test DB injected via monkeypatch."""
    import app.database as db_mod

    async def _test_get_session():
        yield db_session

    monkeypatch.setattr(db_mod, "get_session", _test_get_session)

    from app.main import app

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest_asyncio.fixture
async def admin_user(db_session: AsyncSession):
    """Create an admin user and return (user, plain_password)."""
    from app.models.user import User

    password = "testpass123"
    user = User(
        email="admin@test.com",
        password_hash=hash_password(password),
        display_name="Test Admin",
        role="admin",
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user, password


@pytest_asyncio.fixture
async def reader_user(db_session: AsyncSession):
    """Create a reader user and return (user, plain_password)."""
    from app.models.user import User

    password = "readerpass1"
    user = User(
        email="reader@test.com",
        password_hash=hash_password(password),
        display_name="Test Reader",
        role="reader",
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user, password


@pytest_asyncio.fixture
async def admin_token(admin_user) -> str:
    """Return a valid access token for the admin user."""
    from app.auth.tokens import create_access_token

    user, _ = admin_user
    return create_access_token(user_id=user.id, role=user.role)


@pytest_asyncio.fixture
async def reader_token(reader_user) -> str:
    """Return a valid access token for the reader user."""
    from app.auth.tokens import create_access_token

    user, _ = reader_user
    return create_access_token(user_id=user.id, role=user.role)
