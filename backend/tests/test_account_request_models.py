from datetime import datetime, timezone

import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import create_async_engine

from app.database import _migrate_add_columns
from app.models.account_request import AccountRequest
from app.models.app_settings import AppSettings
from app.models.french_ranking_entry import FrenchRankingEntry
from app.models.skater import Skater


async def test_skater_porte_un_numero_de_licence(db_session):
    skater = Skater(first_name="Léa", last_name="DUPONT", licence_number="123456")
    db_session.add(skater)
    await db_session.commit()

    found = (
        await db_session.execute(select(Skater).where(Skater.licence_number == "123456"))
    ).scalar_one()
    assert found.first_name == "Léa"


async def test_app_settings_porte_la_config_french_ranking(db_session):
    settings = AppSettings(
        club_name="Toulouse Club Patinage",
        club_short="TCP",
        french_ranking_url="https://exemple.fr/a.csv",
        account_requests_enabled=True,
        french_ranking_club_names=["TOULOUSE CLUB PATINAGE"],
    )
    db_session.add(settings)
    await db_session.commit()

    found = (await db_session.execute(select(AppSettings))).scalar_one()
    assert found.account_requests_enabled is True
    assert found.french_ranking_club_names == ["TOULOUSE CLUB PATINAGE"]


async def test_french_ranking_entry_persiste_une_entree(db_session):
    entry = FrenchRankingEntry(
        licence_number="123456",
        last_name="DUPONT",
        first_name="Léa",
        sex="F",
        birth_date=None,
        club_name_raw="TOULOUSE CLUB PATINAGE",
        has_competition_licence=True,
        filiere=None,
        ligue_code="OCC",
        fetched_at=datetime.now(timezone.utc),
    )
    db_session.add(entry)
    await db_session.commit()

    found = (await db_session.execute(select(FrenchRankingEntry))).scalar_one()
    assert found.licence_number == "123456"


async def test_account_request_persiste_une_demande(db_session):
    req = AccountRequest(
        email="parent@exemple.fr",
        display_name="Marie DUPONT",
        licence_numbers=["123456", "789012"],
        status="created",
    )
    db_session.add(req)
    await db_session.commit()

    found = (await db_session.execute(select(AccountRequest))).scalar_one()
    assert found.licence_numbers == ["123456", "789012"]
    assert found.status == "created"
    assert found.resolved_at is None


async def test_migration_impose_unicite_licence_sur_base_deja_existante():
    """Simule une base pré-existante (skaters sans licence_number, donc sans
    contrainte unique dessus) et vérifie que `_migrate_add_columns` fait
    converger la contrainte d'unicité avec ce qu'obtient une base neuve via
    `Base.metadata.create_all`.
    """
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    try:
        async with engine.begin() as conn:
            # Schéma "pré-migration" : skaters existe déjà, mais sans la
            # colonne licence_number (donc sans contrainte unique dessus).
            await conn.execute(
                text(
                    "CREATE TABLE skaters ("
                    "id INTEGER PRIMARY KEY, "
                    "first_name VARCHAR(255) NOT NULL DEFAULT '', "
                    "last_name VARCHAR(255) NOT NULL"
                    ")"
                )
            )
            await _migrate_add_columns(conn)

        async with engine.begin() as conn:
            # Deux patineurs sans licence : ne doivent pas entrer en conflit
            # (SQLite traite les NULL comme distincts dans un index unique).
            await conn.execute(
                text(
                    "INSERT INTO skaters (first_name, last_name, licence_number) "
                    "VALUES ('Alice', 'MARTIN', NULL)"
                )
            )
            await conn.execute(
                text(
                    "INSERT INTO skaters (first_name, last_name, licence_number) "
                    "VALUES ('Bob', 'DURAND', NULL)"
                )
            )

            # Une licence, puis une deuxième identique : doit échouer.
            await conn.execute(
                text(
                    "INSERT INTO skaters (first_name, last_name, licence_number) "
                    "VALUES ('Léa', 'DUPONT', '999999')"
                )
            )
            with pytest.raises(IntegrityError):
                await conn.execute(
                    text(
                        "INSERT INTO skaters (first_name, last_name, licence_number) "
                        "VALUES ('Autre', 'PERSONNE', '999999')"
                    )
                )
    finally:
        await engine.dispose()
