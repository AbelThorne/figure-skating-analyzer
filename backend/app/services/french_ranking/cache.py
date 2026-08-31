# backend/app/services/french_ranking/cache.py
"""Rafraîchissement paresseux (TTL 1h) du cache local French Ranking.

Ne lève JAMAIS : toute erreur réseau/parsing sert le cache existant tel quel
(même périmé) ; aucun cache -> liste vide. Le formulaire public de demande de
compte en dépend — une panne Google ne doit pas renvoyer une 500.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from .cache_repository import fetch_entries, latest_fetch_at, replace_entries
from .parser import NL_PREFIX, parse_french_ranking
from .types import FrenchRankingEntryRow, LicenceRow
from .url import normalize_french_ranking_url

logger = logging.getLogger(__name__)

_TTL = timedelta(hours=1)


def _translate(row: LicenceRow) -> FrenchRankingEntryRow:
    return FrenchRankingEntryRow(
        licence_number=row.licence,
        last_name=row.last,
        first_name=row.first,
        sex=row.sex if row.sex in ("F", "M") else None,
        birth_date=row.birth or None,
        club_name_raw=row.club_name,
        has_competition_licence=not row.club_name.startswith(NL_PREFIX),
        filiere=row.filiere_raw or None,
        ligue_code=row.region_raw or None,
    )


def _as_aware(value: datetime) -> datetime:
    """SQLite relit les DATETIME sans tzinfo : on les rattache à UTC."""
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


async def _fetch_and_parse(
    url: str, *, client: httpx.AsyncClient | None = None
) -> list[LicenceRow] | None:
    """Renvoie None en cas d'échec (l'appelant sert alors le cache existant)."""
    try:
        fetch_url = normalize_french_ranking_url(url)
        owns_client = client is None
        c = client if client is not None else httpx.AsyncClient()
        try:
            response = await c.get(fetch_url, follow_redirects=True, timeout=15.0)
            response.raise_for_status()
            return parse_french_ranking(response.text)
        finally:
            if owns_client:
                await c.aclose()
    except Exception:
        logger.warning("Échec rafraîchissement cache French Ranking (%s)", url, exc_info=True)
        return None


async def ensure_fresh_cache(
    session: AsyncSession,
    url: str | None,
    now: datetime,
    *,
    client: httpx.AsyncClient | None = None,
) -> list[FrenchRankingEntryRow]:
    if url:
        last = await latest_fetch_at(session)
        stale = last is None or (now - _as_aware(last)) >= _TTL
        if stale:
            parsed = await _fetch_and_parse(url, client=client)
            if parsed is not None:
                await replace_entries(session, [_translate(r) for r in parsed], now)
                await session.commit()
    return await fetch_entries(session)


def find_by_licence(
    entries: list[FrenchRankingEntryRow], licence_number: str
) -> FrenchRankingEntryRow | None:
    n = licence_number.strip()
    return next((e for e in entries if e.licence_number == n), None)
