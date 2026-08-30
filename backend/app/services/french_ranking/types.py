"""Types du lecteur French Ranking. Portés depuis ligue-app-competitions."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class LicenceRow:
    """Une ligne brute du CSV French Ranking."""

    licence: str
    last: str
    first: str
    sex: str  # "F" | "M"
    birth: str
    club_name: str
    filiere_raw: str
    region_raw: str


@dataclass(frozen=True)
class FrenchRankingEntryRow:
    """Une entrée traduite, telle que stockée en cache et relue."""

    licence_number: str
    last_name: str
    first_name: str
    sex: str | None
    birth_date: str | None
    club_name_raw: str
    has_competition_licence: bool
    filiere: str | None
    ligue_code: str | None
