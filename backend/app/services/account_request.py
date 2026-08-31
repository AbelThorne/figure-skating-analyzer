# backend/app/services/account_request.py
"""Logique métier de la demande de création de compte.

Isolée des routes pour être testable sans HTTP. Trois responsabilités :
vérifier une licence contre le French Ranking, décider si le patineur appartient
au club de l'instance, et résoudre le `Skater` local correspondant.
"""

from __future__ import annotations

import re
import secrets
import string
import unicodedata

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.app_settings import AppSettings
from app.models.skater import Skater
from app.models.skater_alias import SkaterAlias
from app.services.french_ranking.cache import find_by_licence
from app.services.french_ranking.parser import NL_PREFIX
from app.services.french_ranking.types import FrenchRankingEntryRow

_PUNCT_RE = re.compile(r"[^a-z0-9]+")


def fold(value: str) -> str:
    """« Léa » -> « lea », « Saint-Gaudens » -> « saint gaudens ».

    Minuscules, diacritiques supprimés, ponctuation réduite à des espaces.
    """
    decomposed = unicodedata.normalize("NFKD", value)
    stripped = "".join(c for c in decomposed if not unicodedata.combining(c)).lower()
    return _PUNCT_RE.sub(" ", stripped).strip()


def verify_licence(
    entries: list[FrenchRankingEntryRow], licence_number: str, birth_date: str
) -> tuple[FrenchRankingEntryRow | None, str | None]:
    """Vérifie qu'une licence existe ET que la date de naissance correspond.

    La licence seule ne prouve rien (elle est publiée dans les résultats) : la
    date de naissance est la preuve d'appartenance minimale exigée.
    """
    entry = find_by_licence(entries, licence_number)
    if entry is None:
        return None, "licence_inconnue"
    if not entry.birth_date or entry.birth_date != birth_date.strip():
        return None, "naissance_incorrecte"
    return entry, None


def is_club_member(entry: FrenchRankingEntryRow, settings: AppSettings) -> bool:
    """Le `club_name_raw` national est une chaîne libre : comparaison foldée
    contre le nom du club, son sigle, et les graphies configurées."""
    raw = entry.club_name_raw
    if raw.startswith(NL_PREFIX):
        raw = raw[len(NL_PREFIX) :]
    candidate = fold(raw)

    accepted = [settings.club_name, settings.club_short]
    accepted.extend(settings.french_ranking_club_names or [])
    return any(candidate == fold(name) for name in accepted if name)


async def resolve_skater(
    session: AsyncSession, entry: FrenchRankingEntryRow
) -> tuple[Skater | None, str]:
    """Résout le `Skater` local correspondant à une entrée French Ranking.

    Renvoie `(skater, mode)` :
      - `exact`     : match sûr (licence, nom foldé, ou alias) -> on lie
      - `ambiguous` : match approchant -> validation admin (ne PAS créer, ce
                      serait fabriquer un doublon)
      - `absent`    : aucun candidat -> création automatique
    """
    by_licence = (
        await session.execute(
            select(Skater).where(Skater.licence_number == entry.licence_number)
        )
    ).scalar_one_or_none()
    if by_licence is not None:
        return by_licence, "exact"

    target_first, target_last = fold(entry.first_name), fold(entry.last_name)

    skaters = (await session.execute(select(Skater))).scalars().all()
    for skater in skaters:
        if fold(skater.first_name) == target_first and fold(skater.last_name) == target_last:
            return skater, "exact"

    aliases = (await session.execute(select(SkaterAlias))).scalars().all()
    for alias in aliases:
        if fold(alias.first_name) == target_first and fold(alias.last_name) == target_last:
            return await session.get(Skater, alias.skater_id), "exact"

    # Match approchant : même nom de famille OU même prénom, mais pas les deux.
    for skater in skaters:
        same_last = fold(skater.last_name) == target_last
        same_first = fold(skater.first_name) == target_first
        if same_last or same_first:
            return skater, "ambiguous"

    return None, "absent"


def generate_temp_password(length: int = 14) -> str:
    """Mot de passe temporaire lisible (pas de caractères ambigus)."""
    alphabet = (string.ascii_letters + string.digits).translate(
        str.maketrans("", "", "lI1O0")
    )
    return "".join(secrets.choice(alphabet) for _ in range(length))
