"""Parsing du French Ranking (classement national FFSG, export CSV public).

Porté depuis ligue-app-competitions (`app/licence/french_ranking.py`).
Code pur : aucune I/O, aucune dépendance DB — directement testable.
"""

from __future__ import annotations

import re

from .types import LicenceRow

NL_PREFIX = "NL - "

_BIRTH_RE = re.compile(r"^(\d{1,2})/(\d{1,2})/(\d{4})$")
_DIGITS_RE = re.compile(r"^\d+$")

# Alias acceptés par champ logique : la graphie dérive d'une saison à l'autre
# (« Filière » en 2026-2027, « Catégorie » en 2025-2026).
_ALIASES: dict[str, list[str]] = {
    "nom": ["Nom"],
    "prenom": ["Prénom"],
    "licence": ["Licence"],
    "club": ["Club"],
    "sexe": ["Sexe"],
    "naissance": ["Naissance"],
    "filiere": ["Filière", "Filiere", "Catégorie", "Categorie"],
    "region": ["Région", "Region"],
}


def split_csv_line(line: str) -> list[str]:
    """Parse CSV « simple » : champs éventuellement entre guillemets, virgules
    protégées à l'intérieur des guillemets."""
    out: list[str] = []
    cur = ""
    in_q = False
    for c in line:
        if c == '"':
            in_q = not in_q
            continue
        if c == "," and not in_q:
            out.append(cur)
            cur = ""
            continue
        cur += c
    out.append(cur)
    return out


def normalize_birth(fr: str) -> str:
    """« 5/3/2010 » -> « 2010-03-05 ». Chaîne vide si le format ne correspond pas."""
    m = _BIRTH_RE.match(fr)
    if not m:
        return ""
    d, mo, y = m.group(1), m.group(2), m.group(3)
    return f"{y}-{mo.zfill(2)}-{d.zfill(2)}"


def parse_french_ranking(csv: str) -> list[LicenceRow]:
    """Résout les colonnes par alias d'en-tête. Nom/Prénom/Licence obligatoires."""
    lines = re.split(r"\r?\n", csv)
    if not lines:
        return []
    header = [h.strip() for h in split_csv_line(lines[0])]

    def col(field: str) -> int:
        for alias in _ALIASES[field]:
            if alias in header:
                return header.index(alias)
        return -1

    i_nom, i_pre, i_lic = col("nom"), col("prenom"), col("licence")
    i_club, i_sex, i_nai = col("club"), col("sexe"), col("naissance")
    i_fil, i_reg = col("filiere"), col("region")
    if i_nom < 0 or i_pre < 0 or i_lic < 0:
        raise ValueError("French Ranking: en-tête Nom/Prénom/Licence introuvable")

    def cell(row: list[str], idx: int) -> str:
        return (row[idx] if 0 <= idx < len(row) else "").strip()

    rows: list[LicenceRow] = []
    for line in lines[1:]:
        c = split_csv_line(line)
        if len(c) <= i_lic:
            continue
        licence = cell(c, i_lic)
        if not _DIGITS_RE.match(licence):
            continue
        sex_raw = cell(c, i_sex).upper()
        sex = "M" if sex_raw.startswith("H") or sex_raw.startswith("M") else "F"
        rows.append(
            LicenceRow(
                licence=licence,
                last=cell(c, i_nom),
                first=cell(c, i_pre),
                sex=sex,
                birth=normalize_birth(cell(c, i_nai)),
                club_name=cell(c, i_club),
                filiere_raw=cell(c, i_fil),
                region_raw=cell(c, i_reg),
            )
        )
    return rows
