# backend/tests/test_skater_self_attach.py
"""Rattachement d'un patineur supplémentaire par un utilisateur déjà connecté.

Le formulaire public ne sert qu'une fois : ces tests couvrent le chemin suivi
par un parent dont un second enfant prend une licence en cours de saison.
"""

from datetime import datetime, timezone

import httpx
import pytest
from sqlalchemy import select

from app.models.account_request import AccountRequest
from app.models.app_settings import AppSettings
from app.models.skater import Skater
from app.models.user import User
from app.models.user_skater import UserSkater
from app.services.account_request import attach_skater

NOW = datetime(2026, 1, 15, tzinfo=timezone.utc)

CSV_TCP = (
    "Nom,Prénom,Licence,Club,Sexe,Naissance\n"
    "DUPONT,Léa,123456,TOULOUSE CLUB PATINAGE,F,5/3/2010\n"
    "MARTIN,Tom,789012,TOULOUSE CLUB PATINAGE,M,7/9/2012\n"
    "BERNARD,Zoé,555555,MONTPELLIER PATINAGE,F,1/1/2011\n"
)


def _csv_client(csv: str = CSV_TCP) -> httpx.AsyncClient:
    return httpx.AsyncClient(
        transport=httpx.MockTransport(lambda r: httpx.Response(200, text=csv))
    )


async def _seed_settings(db_session, **kw):
    settings = AppSettings(
        club_name="Toulouse Club Patinage",
        club_short="TCP",
        french_ranking_url="https://exemple.fr/a.csv",
        account_requests_enabled=True,
        **kw,
    )
    db_session.add(settings)
    await db_session.commit()
    return settings


async def _seed_parent(db_session) -> User:
    """Un compte skater déjà créé, lié à un premier enfant."""
    from app.auth.passwords import hash_password

    first_child = Skater(first_name="Léa", last_name="DUPONT", licence_number="123456")
    db_session.add(first_child)
    await db_session.flush()

    user = User(
        email="parent@exemple.fr",
        display_name="Marie DUPONT",
        role="skater",
        password_hash=hash_password("motdepasse1"),
    )
    db_session.add(user)
    await db_session.flush()
    db_session.add(UserSkater(user_id=user.id, skater_id=first_child.id))
    await db_session.commit()
    await db_session.refresh(user)
    return user


# --- Service ---------------------------------------------------------------


async def test_attach_lie_un_second_patineur_verifie(db_session):
    await _seed_settings(db_session)
    user = await _seed_parent(db_session)
    db_session.add(Skater(first_name="Tom", last_name="MARTIN"))
    await db_session.commit()

    result = await attach_skater(
        db_session, user, "789012", "2012-09-07", NOW, client=_csv_client()
    )

    assert result.status == "created"
    links = (
        (await db_session.execute(select(UserSkater).where(UserSkater.user_id == user.id)))
        .scalars()
        .all()
    )
    assert len(links) == 2


async def test_attach_cree_le_patineur_absent_du_club(db_session):
    await _seed_settings(db_session)
    user = await _seed_parent(db_session)

    result = await attach_skater(
        db_session, user, "789012", "2012-09-07", NOW, client=_csv_client()
    )

    assert result.status == "created"
    skater = (
        await db_session.execute(select(Skater).where(Skater.licence_number == "789012"))
    ).scalar_one()
    assert skater.first_name == "Tom"


async def test_attach_rejette_une_naissance_incorrecte(db_session):
    await _seed_settings(db_session)
    user = await _seed_parent(db_session)

    result = await attach_skater(
        db_session, user, "789012", "2000-01-01", NOW, client=_csv_client()
    )

    assert result.status == "rejected"
    links = (
        (await db_session.execute(select(UserSkater).where(UserSkater.user_id == user.id)))
        .scalars()
        .all()
    )
    assert len(links) == 1


async def test_attach_rejette_une_licence_inconnue(db_session):
    await _seed_settings(db_session)
    user = await _seed_parent(db_session)

    result = await attach_skater(
        db_session, user, "999999", "2012-09-07", NOW, client=_csv_client()
    )

    assert result.status == "rejected"


async def test_attach_rejette_un_patineur_hors_club(db_session):
    """Zoé BERNARD est licenciée à Montpellier : le compte ne doit pas la voir."""
    await _seed_settings(db_session)
    user = await _seed_parent(db_session)

    result = await attach_skater(
        db_session, user, "555555", "2011-01-01", NOW, client=_csv_client()
    )

    assert result.status == "rejected"


async def test_attach_met_en_attente_admin_si_ambigu(db_session):
    """Même nom de famille, prénom différent : lier serait un doublon fabriqué."""
    await _seed_settings(db_session)
    user = await _seed_parent(db_session)
    db_session.add(Skater(first_name="Thomas", last_name="MARTIN"))
    await db_session.commit()

    result = await attach_skater(
        db_session, user, "789012", "2012-09-07", NOW, client=_csv_client()
    )

    assert result.status == "pending_admin"
    links = (
        (await db_session.execute(select(UserSkater).where(UserSkater.user_id == user.id)))
        .scalars()
        .all()
    )
    assert len(links) == 1


async def test_attach_est_idempotent_si_deja_lie(db_session):
    await _seed_settings(db_session)
    user = await _seed_parent(db_session)

    result = await attach_skater(
        db_session, user, "123456", "2010-03-05", NOW, client=_csv_client()
    )

    assert result.status == "already_linked"
    links = (
        (await db_session.execute(select(UserSkater).where(UserSkater.user_id == user.id)))
        .scalars()
        .all()
    )
    assert len(links) == 1


async def test_attach_trace_la_demande_pour_audit(db_session):
    await _seed_settings(db_session)
    user = await _seed_parent(db_session)

    await attach_skater(db_session, user, "789012", "2012-09-07", NOW, client=_csv_client())

    rows = (await db_session.execute(select(AccountRequest))).scalars().all()
    assert len(rows) == 1
    assert rows[0].user_id == user.id
    assert rows[0].email == "parent@exemple.fr"


# --- Route -----------------------------------------------------------------


@pytest.fixture(autouse=True)
def _reset_limiter():
    from app.auth.rate_limit import skater_attach_limiter

    skater_attach_limiter._attempts.clear()
    yield
    skater_attach_limiter._attempts.clear()


def _auth(user) -> dict:
    from app.auth.tokens import create_access_token

    return {"Authorization": f"Bearer {create_access_token(user_id=user.id, role=user.role)}"}


async def test_route_refuse_un_anonyme(client, db_session):
    await _seed_settings(db_session)
    resp = await client.post(
        "/api/me/skaters/attach",
        json={"licence_number": "789012", "birth_date": "2012-09-07"},
    )
    assert resp.status_code == 401


async def test_route_refuse_un_reader(client, db_session, reader_token):
    """Seul un compte skater gère sa propre liste de patineurs."""
    await _seed_settings(db_session)
    resp = await client.post(
        "/api/me/skaters/attach",
        json={"licence_number": "789012", "birth_date": "2012-09-07"},
        headers={"Authorization": f"Bearer {reader_token}"},
    )
    assert resp.status_code == 403


async def test_route_valide_la_charge_utile(client, db_session):
    await _seed_settings(db_session)
    user = await _seed_parent(db_session)
    resp = await client.post(
        "/api/me/skaters/attach", json={"licence_number": ""}, headers=_auth(user)
    )
    assert resp.status_code == 400


async def test_route_rate_limite_les_tentatives(client, db_session, monkeypatch):
    """Sans plafond, un compte légitime pourrait énumérer les licences du club."""
    await _seed_settings(db_session)
    user = await _seed_parent(db_session)

    async def _fake(*a, **kw):
        from app.services.account_request import AttachResult

        return AttachResult(status="rejected", reason="licence_inconnue", skater=None)

    monkeypatch.setattr("app.routes.me.attach_skater", _fake)

    codes = []
    for _ in range(7):
        resp = await client.post(
            "/api/me/skaters/attach",
            json={"licence_number": "999999", "birth_date": "2012-09-07"},
            headers=_auth(user),
        )
        codes.append(resp.status_code)
    assert 429 in codes


# --- Validation admin d'un rattachement ------------------------------------


async def test_admin_approuve_un_rattachement_sur_compte_existant(
    client, db_session, admin_token
):
    """Une demande ambiguë issue d'un compte connecté doit lier au compte
    existant, pas tenter d'en créer un second sur la même adresse."""
    await _seed_settings(db_session)
    user = await _seed_parent(db_session)
    homonyme = Skater(first_name="Thomas", last_name="MARTIN")
    db_session.add(homonyme)
    await db_session.commit()
    await db_session.refresh(homonyme)

    result = await attach_skater(
        db_session, user, "789012", "2012-09-07", NOW, client=_csv_client()
    )
    assert result.status == "pending_admin"

    req = (await db_session.execute(select(AccountRequest))).scalars().first()
    resp = await client.post(
        f"/api/admin/account-requests/{req.id}/approve",
        json={"skater_ids": [homonyme.id]},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200

    links = (
        (await db_session.execute(select(UserSkater).where(UserSkater.user_id == user.id)))
        .scalars()
        .all()
    )
    assert len(links) == 2

    users = (
        (await db_session.execute(select(User).where(User.email == "parent@exemple.fr")))
        .scalars()
        .all()
    )
    assert len(users) == 1
