from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config import (
    DATABASE_URL,
    ADMIN_EMAIL,
    ADMIN_PASSWORD,
    CLUB_NAME,
    CLUB_SHORT,
)


class Base(DeclarativeBase):
    pass


engine = create_async_engine(DATABASE_URL, echo=False)
async_session_factory = async_sessionmaker(engine, expire_on_commit=False)


async def init_db() -> None:
    # Import models so Base.metadata knows all tables
    import app.models  # noqa: F401

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    await _bootstrap()


async def _bootstrap() -> None:
    """Seed admin user and app settings from env vars on first run."""
    from app.models.user import User
    from app.models.app_settings import AppSettings
    from app.auth.passwords import hash_password

    async with async_session_factory() as session:
        # Bootstrap admin if users table is empty and env vars set
        result = await session.execute(select(User).limit(1))
        if result.scalar_one_or_none() is None and ADMIN_EMAIL and ADMIN_PASSWORD:
            admin = User(
                email=ADMIN_EMAIL,
                password_hash=hash_password(ADMIN_PASSWORD),
                display_name="Admin",
                role="admin",
            )
            session.add(admin)

        # Bootstrap app settings if table is empty and env vars set
        result = await session.execute(select(AppSettings).limit(1))
        if result.scalar_one_or_none() is None and CLUB_NAME:
            settings = AppSettings(
                club_name=CLUB_NAME,
                club_short=CLUB_SHORT or CLUB_NAME[:5].upper(),
                current_season="2025-2026",
            )
            session.add(settings)

        await session.commit()


async def get_session() -> AsyncSession:
    async with async_session_factory() as session:
        yield session
