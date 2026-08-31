# backend/app/services/french_ranking/cache_repository.py
"""Lecture/écriture SQL pures de `french_ranking_entries`.

Aucune logique réseau ni de traduction ici — `cache.py` orchestre.
"""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.french_ranking_entry import FrenchRankingEntry

from .types import FrenchRankingEntryRow


async def latest_fetch_at(session: AsyncSession) -> datetime | None:
    return (
        await session.execute(select(func.max(FrenchRankingEntry.fetched_at)))
    ).scalar_one_or_none()


async def replace_entries(
    session: AsyncSession, rows: list[FrenchRankingEntryRow], now: datetime
) -> None:
    """Remplace TOUTES les lignes (delete puis insert, pas de diff/hash).

    Le commit appartient à l'appelant.
    """
    await session.execute(delete(FrenchRankingEntry))
    for row in rows:
        session.add(
            FrenchRankingEntry(
                licence_number=row.licence_number,
                last_name=row.last_name,
                first_name=row.first_name,
                sex=row.sex,
                birth_date=date.fromisoformat(row.birth_date) if row.birth_date else None,
                club_name_raw=row.club_name_raw,
                has_competition_licence=row.has_competition_licence,
                filiere=row.filiere,
                ligue_code=row.ligue_code,
                fetched_at=now,
            )
        )
    await session.flush()


async def fetch_entries(session: AsyncSession) -> list[FrenchRankingEntryRow]:
    rows = (await session.execute(select(FrenchRankingEntry))).scalars().all()
    return [
        FrenchRankingEntryRow(
            licence_number=r.licence_number,
            last_name=r.last_name,
            first_name=r.first_name,
            sex=r.sex,
            birth_date=r.birth_date.isoformat() if r.birth_date else None,
            club_name_raw=r.club_name_raw,
            has_competition_licence=r.has_competition_licence,
            filiere=r.filiere,
            ligue_code=r.ligue_code,
        )
        for r in rows
    ]
