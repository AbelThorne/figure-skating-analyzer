import logging

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

logger = logging.getLogger(__name__)

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
        await _migrate_add_columns(conn)

    await _backfill_categories()
    await _bootstrap()


async def _migrate_add_columns(conn) -> None:
    """Add columns that may be missing in existing SQLite databases."""
    _MIGRATIONS = [
        ("competitions", "rink", "VARCHAR(255)"),
        ("scores", "skating_level", "VARCHAR(20)"),
        ("scores", "age_group", "VARCHAR(30)"),
        ("scores", "gender", "VARCHAR(10)"),
        ("category_results", "skating_level", "VARCHAR(20)"),
        ("category_results", "age_group", "VARCHAR(30)"),
        ("category_results", "gender", "VARCHAR(10)"),
    ]
    for table, column, col_type in _MIGRATIONS:
        try:
            await conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}"))
            logger.info("Added column %s.%s", table, column)
        except Exception:
            pass  # Column already exists


async def _backfill_categories() -> None:
    """Parse category field for existing rows that lack structured fields."""
    from app.models.score import Score
    from app.models.category_result import CategoryResult
    from app.services.category_parser import parse_category

    async with async_session_factory() as session:
        result = await session.execute(
            select(Score).where(Score.skating_level.is_(None), Score.category.isnot(None))
        )
        scores = result.scalars().all()
        for score in scores:
            parsed = parse_category(score.category)
            score.skating_level = parsed["skating_level"]
            score.age_group = parsed["age_group"]
            score.gender = parsed["gender"]

        result = await session.execute(
            select(CategoryResult).where(
                CategoryResult.skating_level.is_(None), CategoryResult.category.isnot(None)
            )
        )
        cat_results = result.scalars().all()
        for cr in cat_results:
            parsed = parse_category(cr.category)
            cr.skating_level = parsed["skating_level"]
            cr.age_group = parsed["age_group"]
            cr.gender = parsed["gender"]

        if scores or cat_results:
            await session.commit()
            logger.info("Backfilled categories: %d scores, %d category_results", len(scores), len(cat_results))


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
