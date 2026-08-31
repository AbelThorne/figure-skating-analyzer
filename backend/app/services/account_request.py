# backend/app/services/account_request.py
"""Logique métier de la demande de création de compte.

Isolée des routes pour être testable sans HTTP. Trois responsabilités :
vérifier une licence contre le French Ranking, décider si le patineur appartient
au club de l'instance, et résoudre le `Skater` local correspondant.
"""

from __future__ import annotations

import logging
import re
import secrets
import string
import unicodedata
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.passwords import hash_password
from app.models.account_request import AccountRequest
from app.models.app_settings import AppSettings
from app.models.skater import Skater
from app.models.skater_alias import SkaterAlias
from app.models.user import User
from app.models.user_skater import UserSkater
from app.services.email_service import get_smtp_config, send_email
from app.services.french_ranking.cache import ensure_fresh_cache, find_by_licence
from app.services.french_ranking.parser import NL_PREFIX
from app.services.french_ranking.types import FrenchRankingEntryRow

_PUNCT_RE = re.compile(r"[^a-z0-9]+")

logger = logging.getLogger(__name__)

_REJECT_LABELS = {
    "licence_inconnue": "licence introuvable dans le classement national",
    "naissance_incorrecte": "date de naissance ne correspondant pas",
    "hors_club": "patineur non licencié dans ce club",
}


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


async def process_request(
    session: AsyncSession,
    email: str,
    display_name: str,
    licences: list[dict],
    now: datetime,
    *,
    client=None,
) -> AccountRequest:
    """Traite une demande de bout en bout.

    Ne lève jamais pour un motif métier : l'issue est portée par
    `AccountRequest.status`. L'appelant renvoie TOUJOURS la même réponse HTTP.
    """
    email = email.strip().lower()
    request_row = AccountRequest(
        email=email,
        display_name=display_name.strip(),
        licence_numbers=[l.get("licence_number", "") for l in licences],
        status="rejected",
    )
    session.add(request_row)

    settings = (await session.execute(select(AppSettings).limit(1))).scalar_one_or_none()
    smtp = await get_smtp_config(session)
    club_name = settings.club_name if settings else "SkateLab"

    # Email déjà utilisé : ne pas dupliquer, ne pas révéler l'existence du compte.
    existing = (
        await session.execute(select(User).where(User.email == email))
    ).scalar_one_or_none()
    if existing is not None:
        request_row.reject_reason = "email_deja_utilise"
        request_row.resolved_at = now
        await session.commit()
        if smtp:
            await send_email(
                to=email,
                subject=f"Votre compte {club_name}",
                template_name="account_already_exists.html",
                context={"club_name": club_name, "display_name": existing.display_name},
                smtp_config=smtp,
            )
        return request_row

    entries = await ensure_fresh_cache(
        session, settings.french_ranking_url if settings else None, now, client=client
    )

    resolved: list[tuple[FrenchRankingEntryRow, Skater | None, str]] = []
    failures: list[str] = []

    for item in licences:
        licence_number = str(item.get("licence_number", "")).strip()
        birth_date = str(item.get("birth_date", "")).strip()

        entry, reason = verify_licence(entries, licence_number, birth_date)
        if entry is None:
            failures.append(f"{licence_number} ({_REJECT_LABELS.get(reason, reason)})")
            continue
        if settings is None or not is_club_member(entry, settings):
            failures.append(f"{licence_number} ({_REJECT_LABELS['hors_club']})")
            continue

        skater, mode = await resolve_skater(session, entry)
        resolved.append((entry, skater, mode))

    request_row.reject_reason = ", ".join(failures) or None

    if not resolved:
        request_row.resolved_at = now
        await session.commit()
        if smtp:
            await send_email(
                to=email,
                subject=f"Votre demande de compte {club_name}",
                template_name="account_request_rejected.html",
                context={"club_name": club_name, "failures": failures},
                smtp_config=smtp,
            )
        await _notify_admins(session, request_row, club_name, smtp)
        return request_row

    # Un seul cas ambigu suffit à demander une validation admin : créer le
    # patineur fabriquerait un doublon.
    if any(mode == "ambiguous" for _, _, mode in resolved):
        request_row.status = "pending_admin"
        await session.commit()
        await _notify_admins(session, request_row, club_name, smtp)
        return request_row

    temp_password = generate_temp_password()
    user = User(
        email=email,
        display_name=display_name.strip(),
        role="skater",
        password_hash=hash_password(temp_password),
        must_change_password=True,
    )
    session.add(user)
    await session.flush()

    linked_names: list[str] = []
    for entry, skater, mode in resolved:
        if skater is None:
            skater = Skater(
                first_name=entry.first_name,
                last_name=entry.last_name,
                club=entry.club_name_raw,
                birth_year=int(entry.birth_date[:4]) if entry.birth_date else None,
                licence_number=entry.licence_number,
                manual_create=True,
            )
            session.add(skater)
            await session.flush()
        elif skater.licence_number is None:
            skater.licence_number = entry.licence_number

        session.add(UserSkater(user_id=user.id, skater_id=skater.id))
        linked_names.append(f"{entry.first_name} {entry.last_name}")

    request_row.status = "created"
    request_row.user_id = user.id
    request_row.resolved_at = now
    await session.commit()

    if smtp:
        await send_email(
            to=email,
            subject=f"Votre compte {club_name} est prêt",
            template_name="account_created.html",
            context={
                "club_name": club_name,
                "display_name": user.display_name,
                "email": email,
                "temp_password": temp_password,
                "skaters": linked_names,
                "failures": failures,
            },
            smtp_config=smtp,
        )
    await _notify_admins(session, request_row, club_name, smtp)
    return request_row


async def _notify_admins(
    session: AsyncSession, request_row: AccountRequest, club_name: str, smtp: dict | None
) -> None:
    """Notifie les admins de toute demande — c'est le filet qui rend un
    rattachement anormal visible et révocable."""
    admins = (
        (await session.execute(select(User).where(User.role == "admin", User.is_active)))
        .scalars()
        .all()
    )
    for admin in admins:
        if not admin.email_notifications or not smtp:
            continue
        try:
            await send_email(
                to=admin.email,
                subject=f"[{club_name}] Demande de compte — {request_row.status}",
                template_name="account_request_admin.html",
                context={
                    "club_name": club_name,
                    "email": request_row.email,
                    "display_name": request_row.display_name,
                    "licences": request_row.licence_numbers,
                    "status": request_row.status,
                    "reject_reason": request_row.reject_reason,
                },
                smtp_config=smtp,
            )
        except Exception:
            logger.exception("Échec notification admin pour la demande %s", request_row.id)
