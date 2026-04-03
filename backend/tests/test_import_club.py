"""Tests for club storage on Score and Skater.club update behavior."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.skater import Skater
from app.services.import_service import _get_or_create_skater


@pytest.mark.asyncio
async def test_get_or_create_skater_updates_club(db_session: AsyncSession):
    """When a skater already exists, their club should be updated to the new value."""
    skater = Skater(first_name="Alice", last_name="DUPONT", club="Old Club")
    db_session.add(skater)
    await db_session.flush()

    result = await _get_or_create_skater(db_session, "Alice DUPONT", "FRA", "New Club")
    assert result.id == skater.id
    assert result.club == "New Club"


@pytest.mark.asyncio
async def test_get_or_create_skater_keeps_club_when_none(db_session: AsyncSession):
    """When import has no club info, keep existing club."""
    skater = Skater(first_name="Alice", last_name="DUPONT", club="Existing Club")
    db_session.add(skater)
    await db_session.flush()

    result = await _get_or_create_skater(db_session, "Alice DUPONT", "FRA", None)
    assert result.club == "Existing Club"


@pytest.mark.asyncio
async def test_get_or_create_skater_sets_club_on_new(db_session: AsyncSession):
    """New skater gets club from import."""
    result = await _get_or_create_skater(db_session, "Bob MARTIN", "FRA", "My Club")
    assert result.club == "My Club"
