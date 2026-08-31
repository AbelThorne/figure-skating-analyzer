# backend/tests/test_account_request_service.py
from app.models.app_settings import AppSettings
from app.models.skater import Skater
from app.models.skater_alias import SkaterAlias
from app.services.account_request import (
    fold,
    generate_temp_password,
    is_club_member,
    resolve_skater,
    verify_licence,
)
from app.services.french_ranking.types import FrenchRankingEntryRow

from datetime import datetime, timezone

import httpx
from sqlalchemy import select

from app.models.account_request import AccountRequest
from app.models.user import User
from app.models.user_skater import UserSkater
from app.services.account_request import process_request


def _entry(**kw) -> FrenchRankingEntryRow:
    base = dict(
        licence_number="123456",
        last_name="DUPONT",
        first_name="Léa",
        sex="F",
        birth_date="2010-03-05",
        club_name_raw="TOULOUSE CLUB PATINAGE",
        has_competition_licence=True,
        filiere=None,
        ligue_code="OCC",
    )
    base.update(kw)
    return FrenchRankingEntryRow(**base)


def _settings(**kw) -> AppSettings:
    base = dict(club_name="Toulouse Club Patinage", club_short="TCP")
    base.update(kw)
    return AppSettings(**base)


def test_fold_supprime_accents_casse_et_ponctuation():
    assert fold("Léa") == "lea"
    assert fold("TOULOUSE CLUB PATINAGE") == "toulouse club patinage"
    assert fold("Saint-Gaudens") == "saint gaudens"


def test_verify_licence_accepte_licence_et_naissance_correctes():
    entry, reason = verify_licence([_entry()], "123456", "2010-03-05")
    assert entry is not None
    assert reason is None


def test_verify_licence_rejette_une_licence_inconnue():
    entry, reason = verify_licence([_entry()], "999999", "2010-03-05")
    assert entry is None
    assert reason == "licence_inconnue"


def test_verify_licence_rejette_une_naissance_incorrecte():
    entry, reason = verify_licence([_entry()], "123456", "2011-01-01")
    assert entry is None
    assert reason == "naissance_incorrecte"


def test_verify_licence_rejette_si_naissance_absente_du_referentiel():
    entry, reason = verify_licence([_entry(birth_date=None)], "123456", "2010-03-05")
    assert entry is None
    assert reason == "naissance_incorrecte"


def test_is_club_member_compare_au_nom_complet_du_club():
    assert is_club_member(_entry(), _settings()) is True


def test_is_club_member_compare_au_sigle():
    assert is_club_member(_entry(club_name_raw="TCP"), _settings()) is True


def test_is_club_member_accepte_une_graphie_configuree():
    settings = _settings(french_ranking_club_names=["CLUB PATINAGE TOULOUSAIN"])
    assert is_club_member(_entry(club_name_raw="Club Patinage Toulousain"), settings) is True


def test_is_club_member_refuse_un_autre_club():
    assert is_club_member(_entry(club_name_raw="MONTPELLIER PATINAGE"), _settings()) is False


def test_is_club_member_ignore_le_prefixe_nl():
    assert is_club_member(_entry(club_name_raw="NL - TOULOUSE CLUB PATINAGE"), _settings()) is True


async def test_resolve_skater_exact_par_licence(db_session):
    db_session.add(Skater(first_name="Autre", last_name="NOM", licence_number="123456"))
    await db_session.commit()

    skater, mode = await resolve_skater(db_session, _entry())
    assert mode == "exact"
    assert skater.licence_number == "123456"


async def test_resolve_skater_exact_par_nom_folde(db_session):
    db_session.add(Skater(first_name="LEA", last_name="dupont"))
    await db_session.commit()

    skater, mode = await resolve_skater(db_session, _entry())
    assert mode == "exact"
    assert skater.last_name == "dupont"


async def test_resolve_skater_exact_par_alias(db_session):
    target = Skater(first_name="Léa", last_name="DUPONT-MARTIN")
    db_session.add(target)
    await db_session.flush()
    db_session.add(SkaterAlias(first_name="Léa", last_name="DUPONT", skater_id=target.id))
    await db_session.commit()

    skater, mode = await resolve_skater(db_session, _entry())
    assert mode == "exact"
    assert skater.id == target.id


async def test_resolve_skater_ambigu_si_nom_approchant(db_session):
    db_session.add(Skater(first_name="Léa", last_name="DUPOND"))
    await db_session.commit()

    skater, mode = await resolve_skater(db_session, _entry())
    assert mode == "ambiguous"
    assert skater is not None


async def test_resolve_skater_absent_si_aucun_patineur(db_session):
    skater, mode = await resolve_skater(db_session, _entry())
    assert mode == "absent"
    assert skater is None


def test_generate_temp_password_est_assez_long_et_aleatoire():
    a, b = generate_temp_password(), generate_temp_password()
    assert len(a) >= 12
    assert a != b


NOW = datetime(2026, 8, 30, 12, 0, 0, tzinfo=timezone.utc)

CSV_TCP = (
    "Nom,Prénom,Licence,Club,Sexe,Naissance\n"
    "DUPONT,Léa,123456,TOULOUSE CLUB PATINAGE,F,5/3/2010\n"
    "MARTIN,Tom,789012,TOULOUSE CLUB PATINAGE,M,7/9/2012\n"
    "BERNARD,Zoé,555555,MONTPELLIER PATINAGE,F,1/1/2011\n"
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


def _csv_client(csv: str = CSV_TCP) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(lambda r: httpx.Response(200, text=csv)))


async def test_process_request_cree_le_compte_et_lie_le_patineur(db_session):
    await _seed_settings(db_session)
    db_session.add(Skater(first_name="Léa", last_name="DUPONT"))
    await db_session.commit()

    req = await process_request(
        db_session,
        "parent@exemple.fr",
        "Marie DUPONT",
        [{"licence_number": "123456", "birth_date": "2010-03-05"}],
        NOW,
        client=_csv_client(),
    )

    assert req.status == "created"
    user = (
        await db_session.execute(select(User).where(User.email == "parent@exemple.fr"))
    ).scalar_one()
    assert user.role == "skater"
    assert user.must_change_password is True
    assert user.password_hash is not None

    links = (
        await db_session.execute(select(UserSkater).where(UserSkater.user_id == user.id))
    ).scalars().all()
    assert len(links) == 1


async def test_process_request_pose_la_licence_sur_le_patineur(db_session):
    await _seed_settings(db_session)
    db_session.add(Skater(first_name="Léa", last_name="DUPONT"))
    await db_session.commit()

    await process_request(
        db_session,
        "parent@exemple.fr",
        "Marie DUPONT",
        [{"licence_number": "123456", "birth_date": "2010-03-05"}],
        NOW,
        client=_csv_client(),
    )

    skater = (
        await db_session.execute(select(Skater).where(Skater.last_name == "DUPONT"))
    ).scalar_one()
    assert skater.licence_number == "123456"


async def test_process_request_cree_le_patineur_absent(db_session):
    await _seed_settings(db_session)

    req = await process_request(
        db_session,
        "parent@exemple.fr",
        "Marie DUPONT",
        [{"licence_number": "123456", "birth_date": "2010-03-05"}],
        NOW,
        client=_csv_client(),
    )

    assert req.status == "created"
    skater = (
        await db_session.execute(select(Skater).where(Skater.licence_number == "123456"))
    ).scalar_one()
    assert skater.first_name == "Léa"
    assert skater.manual_create is True


async def test_process_request_rejette_un_autre_club(db_session):
    await _seed_settings(db_session)

    req = await process_request(
        db_session,
        "curieux@exemple.fr",
        "Curieux",
        [{"licence_number": "555555", "birth_date": "2011-01-01"}],
        NOW,
        client=_csv_client(),
    )

    assert req.status == "rejected"
    assert (
        await db_session.execute(select(User).where(User.email == "curieux@exemple.fr"))
    ).scalar_one_or_none() is None


async def test_process_request_rejette_une_naissance_incorrecte(db_session):
    await _seed_settings(db_session)

    req = await process_request(
        db_session,
        "curieux@exemple.fr",
        "Curieux",
        [{"licence_number": "123456", "birth_date": "1999-01-01"}],
        NOW,
        client=_csv_client(),
    )

    assert req.status == "rejected"


async def test_process_request_partiellement_valide_cree_le_compte(db_session):
    await _seed_settings(db_session)

    req = await process_request(
        db_session,
        "parent@exemple.fr",
        "Marie DUPONT",
        [
            {"licence_number": "123456", "birth_date": "2010-03-05"},
            {"licence_number": "999999", "birth_date": "2010-01-01"},
        ],
        NOW,
        client=_csv_client(),
    )

    assert req.status == "created"
    assert "999999" in (req.reject_reason or "")
    user = (
        await db_session.execute(select(User).where(User.email == "parent@exemple.fr"))
    ).scalar_one()
    links = (
        await db_session.execute(select(UserSkater).where(UserSkater.user_id == user.id))
    ).scalars().all()
    assert len(links) == 1


async def test_process_request_met_en_attente_si_ambigu(db_session):
    await _seed_settings(db_session)
    db_session.add(Skater(first_name="Léa", last_name="DUPOND"))
    await db_session.commit()

    req = await process_request(
        db_session,
        "parent@exemple.fr",
        "Marie DUPONT",
        [{"licence_number": "123456", "birth_date": "2010-03-05"}],
        NOW,
        client=_csv_client(),
    )

    assert req.status == "pending_admin"
    assert (
        await db_session.execute(select(User).where(User.email == "parent@exemple.fr"))
    ).scalar_one_or_none() is None


async def test_process_request_ne_duplique_pas_un_email_existant(db_session):
    await _seed_settings(db_session)
    db_session.add(
        User(email="parent@exemple.fr", display_name="Déjà là", role="reader", password_hash="x")
    )
    await db_session.commit()

    req = await process_request(
        db_session,
        "parent@exemple.fr",
        "Marie DUPONT",
        [{"licence_number": "123456", "birth_date": "2010-03-05"}],
        NOW,
        client=_csv_client(),
    )

    assert req.status == "rejected"
    users = (
        await db_session.execute(select(User).where(User.email == "parent@exemple.fr"))
    ).scalars().all()
    assert len(users) == 1
