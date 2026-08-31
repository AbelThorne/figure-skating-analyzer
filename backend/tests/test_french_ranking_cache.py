# backend/tests/test_french_ranking_cache.py
from datetime import datetime, timedelta, timezone

import httpx

from app.services.french_ranking.cache import ensure_fresh_cache, find_by_licence
from app.services.french_ranking.cache_repository import fetch_entries, replace_entries
from app.services.french_ranking.types import FrenchRankingEntryRow

CSV = "Nom,Prénom,Licence,Club,Sexe,Naissance\nDUPONT,Léa,123456,TOULOUSE CLUB PATINAGE,F,5/3/2010"

NOW = datetime(2026, 8, 30, 12, 0, 0, tzinfo=timezone.utc)


def _client(handler) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


async def test_remplit_le_cache_quand_il_est_vide(db_session):
    client = _client(lambda req: httpx.Response(200, text=CSV))
    entries = await ensure_fresh_cache(db_session, "https://exemple.fr/a.csv", NOW, client=client)
    assert len(entries) == 1
    assert entries[0].licence_number == "123456"
    assert entries[0].birth_date == "2010-03-05"


async def test_ne_refetch_pas_avant_expiration_du_ttl(db_session):
    calls = []

    def handler(req):
        calls.append(req)
        return httpx.Response(200, text=CSV)

    client = _client(handler)
    await ensure_fresh_cache(db_session, "https://exemple.fr/a.csv", NOW, client=client)
    await ensure_fresh_cache(
        db_session, "https://exemple.fr/a.csv", NOW + timedelta(minutes=30), client=client
    )
    assert len(calls) == 1


async def test_refetch_apres_expiration_du_ttl(db_session):
    calls = []

    def handler(req):
        calls.append(req)
        return httpx.Response(200, text=CSV)

    client = _client(handler)
    await ensure_fresh_cache(db_session, "https://exemple.fr/a.csv", NOW, client=client)
    await ensure_fresh_cache(
        db_session, "https://exemple.fr/a.csv", NOW + timedelta(hours=2), client=client
    )
    assert len(calls) == 2


async def test_sert_le_cache_perime_si_le_reseau_echoue(db_session):
    ok = _client(lambda req: httpx.Response(200, text=CSV))
    await ensure_fresh_cache(db_session, "https://exemple.fr/a.csv", NOW, client=ok)

    def boom(req):
        raise httpx.ConnectError("réseau indisponible")

    entries = await ensure_fresh_cache(
        db_session, "https://exemple.fr/a.csv", NOW + timedelta(hours=2), client=_client(boom)
    )
    assert len(entries) == 1  # l'ancien cache est servi, aucune exception


async def test_renvoie_une_liste_vide_sans_url_ni_cache(db_session):
    assert await ensure_fresh_cache(db_session, None, NOW) == []


async def test_remplace_entierement_les_entrees(db_session):
    row = FrenchRankingEntryRow(
        licence_number="999",
        last_name="ANCIEN",
        first_name="X",
        sex=None,
        birth_date=None,
        club_name_raw="AUTRE",
        has_competition_licence=True,
        filiere=None,
        ligue_code=None,
    )
    await replace_entries(db_session, [row], NOW)
    await db_session.commit()

    client = _client(lambda req: httpx.Response(200, text=CSV))
    await ensure_fresh_cache(
        db_session, "https://exemple.fr/a.csv", NOW + timedelta(hours=2), client=client
    )
    entries = await fetch_entries(db_session)
    assert [e.licence_number for e in entries] == ["123456"]


async def test_find_by_licence_ignore_les_espaces():
    row = FrenchRankingEntryRow(
        licence_number="123456",
        last_name="DUPONT",
        first_name="Léa",
        sex="F",
        birth_date="2010-03-05",
        club_name_raw="TOULOUSE",
        has_competition_licence=True,
        filiere=None,
        ligue_code=None,
    )
    assert find_by_licence([row], "  123456 ") is row
    assert find_by_licence([row], "000") is None
