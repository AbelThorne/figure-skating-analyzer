"""Parse raw FFSG category strings into structured fields."""

import logging
import re

logger = logging.getLogger(__name__)

_LEVEL_RULES: list[tuple[re.Pattern, str]] = [
    (re.compile(r"\bAdulte\s+Acier\b", re.IGNORECASE), "Adulte Acier"),
    (re.compile(r"\bAdulte\s+Bronze\b", re.IGNORECASE), "Adulte Bronze"),
    (re.compile(r"\bAdulte\s+Argent\b", re.IGNORECASE), "Adulte Argent"),
    (re.compile(r"\bAdulte\s+Or\b", re.IGNORECASE), "Adulte Or"),
    (re.compile(r"\bAdulte\s+Master\b", re.IGNORECASE), "Adulte Master"),
    (re.compile(r"\bR3\s+A\b", re.IGNORECASE), "R3 A"),
    (re.compile(r"\bR3\s+B\b", re.IGNORECASE), "R3 B"),
    (re.compile(r"\bR3\s+C\b", re.IGNORECASE), "R3 C"),
    (re.compile(r"\b(?:National|D1)\b", re.IGNORECASE), "National"),
    (re.compile(r"\b(?:F[eé]d[eé]ral[e]?|D2)\b", re.IGNORECASE), "Fédéral"),
    (re.compile(r"\b(?:R1|D3)\b", re.IGNORECASE), "R1"),
    (re.compile(r"\bR2\b", re.IGNORECASE), "R2"),
]

_AGE_RULES: list[tuple[re.Pattern, str]] = [
    (re.compile(r"\b(?:Jun-Sen|Junior-Senior)\b", re.IGNORECASE), "Junior-Senior"),
    (re.compile(r"\b(?:Min-Nov|Minime-Novice)\b", re.IGNORECASE), "Minime-Novice"),
    (re.compile(r"\bBabies\b", re.IGNORECASE), "Babies"),
    (re.compile(r"\bPoussin\b", re.IGNORECASE), "Poussin"),
    (re.compile(r"\bBenjamin\b", re.IGNORECASE), "Benjamin"),
    (re.compile(r"\bMinime\b", re.IGNORECASE), "Minime"),
    (re.compile(r"\bNovice\b", re.IGNORECASE), "Novice"),
    (re.compile(r"\bJunior\b", re.IGNORECASE), "Junior"),
    (re.compile(r"\bSenior\b", re.IGNORECASE), "Senior"),
]

_GENDER_PATTERN = re.compile(r"\b(Femme|Homme)\b", re.IGNORECASE)
_SERIE_PATTERN = re.compile(r"\bSerie\s+\d+\b", re.IGNORECASE)


def parse_category(raw: str | None) -> dict:
    """Parse a raw category string into structured fields.

    Returns {"skating_level": ..., "age_group": ..., "gender": ...}
    with None for any field that cannot be determined.
    """
    if not raw:
        return {"skating_level": None, "age_group": None, "gender": None}

    skating_level = None
    for pattern, level in _LEVEL_RULES:
        if pattern.search(raw):
            skating_level = level
            break

    if skating_level is None and raw.strip():
        logger.warning("Could not determine skating level from category: %r", raw)

    if skating_level and skating_level.startswith("Adulte"):
        age_group = "Adulte"
    else:
        cleaned = _SERIE_PATTERN.sub("", raw)
        age_group = None
        for pattern, group in _AGE_RULES:
            if pattern.search(cleaned):
                age_group = group
                break

    gender_match = _GENDER_PATTERN.search(raw)
    gender = gender_match.group(1).capitalize() if gender_match else None

    return {
        "skating_level": skating_level,
        "age_group": age_group,
        "gender": gender,
    }
