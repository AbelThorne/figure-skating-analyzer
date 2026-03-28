import pytest
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.competition import Competition


@pytest.mark.asyncio
async def test_polling_auto_disable_after_week(db_session: AsyncSession):
    """Competitions with date_end > 7 days ago should have polling disabled."""
    comp = Competition(
        name="Old Event",
        url="https://example.com/old-event/index.htm",
        date=date(2026, 3, 1),
        date_end=date(2026, 3, 2),
        polling_enabled=True,
        polling_activated_at=datetime(2026, 3, 1, tzinfo=timezone.utc),
    )
    db_session.add(comp)
    await db_session.commit()
    await db_session.refresh(comp)

    from app.main import _should_disable_polling
    assert _should_disable_polling(comp, today=date(2026, 3, 15)) is True
    assert _should_disable_polling(comp, today=date(2026, 3, 8)) is False
    assert _should_disable_polling(comp, today=date(2026, 3, 9)) is False
    assert _should_disable_polling(comp, today=date(2026, 3, 10)) is True


@pytest.mark.asyncio
async def test_polling_not_disabled_without_date_end(db_session: AsyncSession):
    """Competitions without date_end should keep polling active."""
    comp = Competition(
        name="No End Date",
        url="https://example.com/no-end/index.htm",
        polling_enabled=True,
        polling_activated_at=datetime(2026, 3, 1, tzinfo=timezone.utc),
    )
    db_session.add(comp)
    await db_session.commit()
    await db_session.refresh(comp)

    from app.main import _should_disable_polling
    assert _should_disable_polling(comp, today=date(2026, 12, 31)) is False
