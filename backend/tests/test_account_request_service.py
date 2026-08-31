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
