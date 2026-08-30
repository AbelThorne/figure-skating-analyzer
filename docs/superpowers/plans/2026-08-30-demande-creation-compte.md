# Demande de création de compte — Plan d'implémentation

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Permettre à un parent ou un patineur de demander un compte en fournissant les numéros de licence des patineurs à rattacher, vérifiés contre le French Ranking ; création automatique du compte en rôle `skater` avec mot de passe temporaire envoyé par email.

**Architecture:** Portage local du lecteur French Ranking (parsing CSV pur + cache SQLite TTL 1h) depuis `../ligue-app-competitions`. Un module métier `account_request.py` isolé des routes orchestre vérification licence → appartenance au club → résolution du patineur (exact / ambigu / absent) → création du compte. Endpoint public à réponse neutre, notification admin systématique.

**Tech Stack:** Litestar, SQLAlchemy 2 async, SQLite (aiosqlite), httpx, Jinja2, aiosmtplib, pytest/pytest-asyncio, React + TypeScript + Vite + TanStack Query + Tailwind.

**Spec:** `docs/superpowers/specs/2026-08-30-demande-creation-compte-design.md`

## Global Constraints

- **Tout le texte utilisateur (UI + emails) en français.**
- Design system Kinetic Lens : Tailwind seul, aucune bibliothèque de composants ; pas de bordures pour le sectionnement (superposition de surfaces) ; `font-mono` pour les valeurs numériques. Couleurs : `on-surface` `#191c1e`, `primary` `#2e6385`, `error` `#ba1a1a`.
- `npm` et `uv` ne sont pas dans le PATH : préfixer par `PATH="/opt/homebrew/bin:$PATH"`.
- Tests backend : `cd backend && uv run pytest`. `asyncio_mode = "auto"` — les tests async n'ont pas besoin de décorateur.
- Nouvelles colonnes sur tables existantes : ajouter au `_MIGRATIONS` de `backend/app/database.py:41` (`ALTER TABLE ... ADD COLUMN`, échec silencieux si déjà présente). Les **nouvelles tables** sont créées par `Base.metadata.create_all` — il suffit d'importer le modèle.
- Réponse HTTP du endpoint public **toujours identique** (`202`), quel que soit le résultat : pas d'oracle d'énumération de licences.
- Commits fréquents, un par tâche minimum. Messages en français, préfixe conventionnel (`feat:`, `test:`, `fix:`).

---

## Structure des fichiers

**Créés — backend**

| Fichier | Responsabilité |
|---|---|
| `backend/app/services/french_ranking/__init__.py` | Exports du paquet |
| `backend/app/services/french_ranking/parser.py` | Parsing CSV pur (aucune I/O) |
| `backend/app/services/french_ranking/url.py` | Normalisation d'URL Google Sheets |
| `backend/app/services/french_ranking/types.py` | Dataclasses `LicenceRow`, `FrenchRankingEntryRow` |
| `backend/app/services/french_ranking/cache_repository.py` | SQL pur sur `french_ranking_entries` |
| `backend/app/services/french_ranking/cache.py` | Rafraîchissement TTL 1h, ne lève jamais |
| `backend/app/models/french_ranking_entry.py` | Modèle du cache |
| `backend/app/models/account_request.py` | Modèle de la demande |
| `backend/app/services/account_request.py` | Logique métier (vérif, club, résolution, orchestration) |
| `backend/app/templates/emails/account_created.html` | Email compte créé |
| `backend/app/templates/emails/account_request_rejected.html` | Email demande rejetée |
| `backend/app/templates/emails/account_already_exists.html` | Email compte déjà existant |

**Créés — frontend**

| Fichier | Responsabilité |
|---|---|
| `frontend/src/pages/RequestAccountPage.tsx` | Formulaire public de demande |

**Modifiés**

| Fichier | Modification |
|---|---|
| `backend/app/models/skater.py` | + `licence_number` |
| `backend/app/models/app_settings.py` | + `french_ranking_url`, `account_requests_enabled`, `french_ranking_club_names` |
| `backend/app/database.py:41` | + 4 entrées `_MIGRATIONS` |
| `backend/app/routes/auth.py` | + `request_account`, expiration du mot de passe temporaire dans `login` |
| `backend/app/routes/admin.py` | + liste et approbation des demandes |
| `backend/app/routes/club_config.py` | + `account-requests-enabled` (public) |
| `backend/app/main.py` | Import des nouveaux modèles |
| `frontend/src/api/client.ts` | + types et appels |
| `frontend/src/App.tsx` | + route `/request-account` |
| `frontend/src/pages/LoginPage.tsx` | + lien conditionnel |
| `frontend/src/pages/SettingsPage.tsx` | + réglages French Ranking + onglet demandes |

**Tests créés**

`backend/tests/test_french_ranking_parser.py`, `test_french_ranking_url.py`, `test_french_ranking_cache.py`, `test_account_request_service.py`, `test_account_request_routes.py`.

---

### Task 1: Parsing CSV du French Ranking

Code pur, sans I/O ni DB. Portage 1:1 depuis `../ligue-app-competitions/backend/app/licence/french_ranking.py`.

**Files:**
- Create: `backend/app/services/french_ranking/__init__.py`
- Create: `backend/app/services/french_ranking/types.py`
- Create: `backend/app/services/french_ranking/parser.py`
- Test: `backend/tests/test_french_ranking_parser.py`

**Interfaces:**
- Consumes: rien.
- Produces: `LicenceRow` (dataclass frozen : `licence: str`, `last: str`, `first: str`, `sex: str`, `birth: str`, `club_name: str`, `filiere_raw: str`, `region_raw: str`) ; `split_csv_line(line: str) -> list[str]` ; `normalize_birth(fr: str) -> str` ; `parse_french_ranking(csv: str) -> list[LicenceRow]` ; constante `NL_PREFIX = "NL - "`.

- [ ] **Step 1: Écrire les tests qui échouent**

```python
# backend/tests/test_french_ranking_parser.py
import pytest

from app.services.french_ranking.parser import (
    NL_PREFIX,
    normalize_birth,
    parse_french_ranking,
    split_csv_line,
)


def test_split_csv_line_protege_les_virgules_entre_guillemets():
    assert split_csv_line('a,"b,c",d') == ["a", "b,c", "d"]


def test_normalize_birth_convertit_le_format_francais():
    assert normalize_birth("5/3/2010") == "2010-03-05"
    assert normalize_birth("") == ""
    assert normalize_birth("n/a") == ""


def test_parse_accepte_l_alias_filiere():
    csv = "Nom,Prénom,Licence,Club,Sexe,Naissance,Filière,Région\nDUPONT,Léa,123456,TOULOUSE,F,5/3/2010,Nationale,OCC"
    rows = parse_french_ranking(csv)
    assert len(rows) == 1
    assert rows[0].licence == "123456"
    assert rows[0].last == "DUPONT"
    assert rows[0].first == "Léa"
    assert rows[0].birth == "2010-03-05"
    assert rows[0].filiere_raw == "Nationale"


def test_parse_accepte_l_alias_categorie_ancienne_saison():
    csv = "Nom,Prénom,Licence,Club,Sexe,Naissance,Catégorie,Region\nDUPONT,Léa,123456,TOULOUSE,F,5/3/2010,Nationale,OCC"
    rows = parse_french_ranking(csv)
    assert rows[0].filiere_raw == "Nationale"


def test_parse_ignore_les_lignes_sans_licence_numerique():
    csv = "Nom,Prénom,Licence\nDUPONT,Léa,ABC\nMARTIN,Tom,7890"
    rows = parse_french_ranking(csv)
    assert [r.licence for r in rows] == ["7890"]


def test_parse_normalise_le_sexe():
    csv = "Nom,Prénom,Licence,Sexe\nA,B,1,Homme\nC,D,2,Dame"
    rows = parse_french_ranking(csv)
    assert [r.sex for r in rows] == ["M", "F"]


def test_parse_leve_si_entete_obligatoire_absent():
    with pytest.raises(ValueError):
        parse_french_ranking("Foo,Bar\n1,2")


def test_nl_prefix_marque_les_sans_licence_competition():
    csv = f"Nom,Prénom,Licence,Club\nA,B,1,{NL_PREFIX}TOULOUSE"
    rows = parse_french_ranking(csv)
    assert rows[0].club_name.startswith(NL_PREFIX)
```

- [ ] **Step 2: Lancer les tests pour vérifier l'échec**

Run: `cd backend && PATH="/opt/homebrew/bin:$PATH" uv run pytest tests/test_french_ranking_parser.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.services.french_ranking'`

- [ ] **Step 3: Écrire `types.py`**

```python
# backend/app/services/french_ranking/types.py
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
```

- [ ] **Step 4: Écrire `parser.py`**

```python
# backend/app/services/french_ranking/parser.py
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
```

- [ ] **Step 5: Écrire `__init__.py`**

```python
# backend/app/services/french_ranking/__init__.py
"""Lecteur du French Ranking (classement national FFSG)."""
```

- [ ] **Step 6: Lancer les tests pour vérifier le succès**

Run: `cd backend && PATH="/opt/homebrew/bin:$PATH" uv run pytest tests/test_french_ranking_parser.py -v`
Expected: PASS — 8 tests

- [ ] **Step 7: Commit**

```bash
git add backend/app/services/french_ranking/ backend/tests/test_french_ranking_parser.py
git commit -m "feat(french-ranking): parsing CSV du classement national"
```

---

### Task 2: Normalisation d'URL Google Sheets

**Files:**
- Create: `backend/app/services/french_ranking/url.py`
- Test: `backend/tests/test_french_ranking_url.py`

**Interfaces:**
- Consumes: rien.
- Produces: `normalize_french_ranking_url(raw_url: str) -> str`.

- [ ] **Step 1: Écrire les tests qui échouent**

```python
# backend/tests/test_french_ranking_url.py
from app.services.french_ranking.url import normalize_french_ranking_url


def test_reecrit_pubhtml_en_export_csv():
    assert (
        normalize_french_ranking_url("https://docs.google.com/spreadsheets/d/e/ABC/pubhtml")
        == "https://docs.google.com/spreadsheets/d/e/ABC/pub?output=csv"
    )


def test_preserve_le_gid_en_query_string():
    assert (
        normalize_french_ranking_url("https://docs.google.com/spreadsheets/d/e/ABC/pubhtml?gid=42")
        == "https://docs.google.com/spreadsheets/d/e/ABC/pub?output=csv&gid=42"
    )


def test_preserve_le_gid_en_fragment():
    assert (
        normalize_french_ranking_url("https://docs.google.com/spreadsheets/d/e/ABC/pubhtml#gid=42")
        == "https://docs.google.com/spreadsheets/d/e/ABC/pub?output=csv&gid=42"
    )


def test_laisse_inchangee_une_url_deja_au_format_export():
    url = "https://docs.google.com/spreadsheets/d/e/ABC/pub?output=csv&gid=7"
    assert normalize_french_ranking_url(url) == url


def test_laisse_inchangee_une_source_non_google():
    assert normalize_french_ranking_url("https://exemple.fr/ranking.csv") == "https://exemple.fr/ranking.csv"


def test_supprime_les_espaces_autour():
    assert normalize_french_ranking_url("  https://exemple.fr/a.csv  ") == "https://exemple.fr/a.csv"
```

- [ ] **Step 2: Lancer les tests pour vérifier l'échec**

Run: `cd backend && PATH="/opt/homebrew/bin:$PATH" uv run pytest tests/test_french_ranking_url.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.services.french_ranking.url'`

- [ ] **Step 3: Écrire `url.py`**

```python
# backend/app/services/french_ranking/url.py
"""Normalisation d'URL French Ranking.

Un admin colle le lien de partage Google Sheets (« pubhtml »), qui ne renvoie
qu'une coquille JS sans données. L'export exploitable est `pub?output=csv`.

Le `gid` doit être préservé : sans lui, l'export ne renvoie silencieusement que
le PREMIER onglet du classeur (un classeur French Ranking a un onglet par
catégorie/sexe).
"""

from __future__ import annotations

import re

_GID_RE = re.compile(r"[?&#]gid=(-?\d+)")


def normalize_french_ranking_url(raw_url: str) -> str:
    """Réécrit `.../pubhtml[?...]` en `.../pub?output=csv[&gid=N]`.

    Laisse inchangée toute autre URL (déjà au format export, ou source non-Google).
    """
    url = raw_url.strip()
    if "/pubhtml" in url:
        base = url.split("/pubhtml", 1)[0]
        match = _GID_RE.search(url)
        if match:
            return f"{base}/pub?output=csv&gid={match.group(1)}"
        return f"{base}/pub?output=csv"
    return url
```

- [ ] **Step 4: Lancer les tests pour vérifier le succès**

Run: `cd backend && PATH="/opt/homebrew/bin:$PATH" uv run pytest tests/test_french_ranking_url.py -v`
Expected: PASS — 6 tests

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/french_ranking/url.py backend/tests/test_french_ranking_url.py
git commit -m "feat(french-ranking): normalisation d'URL Google Sheets"
```

---

### Task 3: Modèles et migrations

Nouvelles tables (`french_ranking_entries`, `account_requests`) et nouvelles colonnes (`skaters.licence_number`, 3 sur `app_settings`).

**Files:**
- Create: `backend/app/models/french_ranking_entry.py`
- Create: `backend/app/models/account_request.py`
- Modify: `backend/app/models/skater.py`
- Modify: `backend/app/models/app_settings.py`
- Modify: `backend/app/database.py:41` (liste `_MIGRATIONS`)
- Test: `backend/tests/test_account_request_models.py`

**Interfaces:**
- Consumes: rien.
- Produces: `FrenchRankingEntry` (colonnes `id`, `licence_number`, `last_name`, `first_name`, `sex`, `birth_date`, `club_name_raw`, `has_competition_licence`, `filiere`, `ligue_code`, `fetched_at`) ; `AccountRequest` (`id`, `email`, `display_name`, `licence_numbers` JSON, `status`, `reject_reason`, `created_at`, `resolved_at`, `user_id`) ; `Skater.licence_number` ; `AppSettings.french_ranking_url`, `.account_requests_enabled`, `.french_ranking_club_names`.

- [ ] **Step 1: Écrire le test qui échoue**

```python
# backend/tests/test_account_request_models.py
from datetime import datetime, timezone

from sqlalchemy import select

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
```

- [ ] **Step 2: Lancer le test pour vérifier l'échec**

Run: `cd backend && PATH="/opt/homebrew/bin:$PATH" uv run pytest tests/test_account_request_models.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.models.account_request'`

- [ ] **Step 3: Écrire `french_ranking_entry.py`**

```python
# backend/app/models/french_ranking_entry.py
"""Cache local du French Ranking : une ligne = un patineur, remplacé en bloc à
chaque rafraîchissement (pas de diff/hash).

Contrairement au projet ligue, pas de dimension saison : une instance SkateLab
n'a qu'une saison courante (`app_settings.current_season`).
"""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class FrenchRankingEntry(Base):
    __tablename__ = "french_ranking_entries"
    __table_args__ = (Index("ix_french_ranking_entries_licence", "licence_number"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    licence_number: Mapped[str] = mapped_column(String(50), nullable=False)
    last_name: Mapped[str] = mapped_column(String(255), nullable=False)
    first_name: Mapped[str] = mapped_column(String(255), nullable=False)
    sex: Mapped[str | None] = mapped_column(String(1), nullable=True)
    birth_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    club_name_raw: Mapped[str] = mapped_column(String(255), nullable=False)
    has_competition_licence: Mapped[bool] = mapped_column(Boolean, nullable=False)
    filiere: Mapped[str | None] = mapped_column(String(100), nullable=True)
    ligue_code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    fetched_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
```

- [ ] **Step 4: Écrire `account_request.py`**

```python
# backend/app/models/account_request.py
"""Trace d'une demande de création de compte : audit et notification admin.

`status` : created | pending_admin | rejected | expired
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import JSON, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class AccountRequest(Base):
    __tablename__ = "account_requests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    licence_numbers: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="created")
    reject_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, nullable=False)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, default=None)
    user_id: Mapped[str | None] = mapped_column(String(36), nullable=True, default=None)
```

- [ ] **Step 5: Ajouter `licence_number` à `Skater`**

Dans `backend/app/models/skater.py`, après la ligne `manual_create` :

```python
    licence_number: Mapped[Optional[str]] = mapped_column(
        String(50), nullable=True, unique=True
    )
```

- [ ] **Step 6: Ajouter les colonnes à `AppSettings`**

Dans `backend/app/models/app_settings.py`, après `default_team_medians` :

```python
    french_ranking_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    account_requests_enabled: Mapped[bool] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    french_ranking_club_names: Mapped[list | None] = mapped_column(JSON, nullable=True)
```

- [ ] **Step 7: Ajouter les migrations de colonnes**

Dans `backend/app/database.py`, ajouter à la fin de la liste `_MIGRATIONS` (ligne 41) :

```python
        ("skaters", "licence_number", "VARCHAR(50)"),
        ("app_settings", "french_ranking_url", "VARCHAR(500)"),
        ("app_settings", "account_requests_enabled", "INTEGER DEFAULT 0"),
        ("app_settings", "french_ranking_club_names", "JSON"),
```

- [ ] **Step 8: Importer les nouveaux modèles**

Vérifier que `backend/app/main.py` (ou `database.py`) importe les nouveaux modèles pour que `Base.metadata.create_all` crée les tables. Chercher où les autres modèles sont importés :

Run: `cd backend && grep -rn "from app.models" app/main.py app/database.py | head`

Ajouter au même endroit :

```python
from app.models.account_request import AccountRequest  # noqa: F401
from app.models.french_ranking_entry import FrenchRankingEntry  # noqa: F401
```

- [ ] **Step 9: Lancer les tests pour vérifier le succès**

Run: `cd backend && PATH="/opt/homebrew/bin:$PATH" uv run pytest tests/test_account_request_models.py -v`
Expected: PASS — 4 tests

- [ ] **Step 10: Vérifier l'absence de régression**

Run: `cd backend && PATH="/opt/homebrew/bin:$PATH" uv run pytest -q`
Expected: tous les tests passent.

- [ ] **Step 11: Commit**

```bash
git add backend/app/models/ backend/app/database.py backend/app/main.py backend/tests/test_account_request_models.py
git commit -m "feat(models): cache French Ranking, demandes de compte, licence patineur"
```

---

### Task 4: Cache French Ranking (TTL, tolérance aux pannes)

**Files:**
- Create: `backend/app/services/french_ranking/cache_repository.py`
- Create: `backend/app/services/french_ranking/cache.py`
- Test: `backend/tests/test_french_ranking_cache.py`

**Interfaces:**
- Consumes: `LicenceRow`, `FrenchRankingEntryRow`, `parse_french_ranking` (Task 1) ; `normalize_french_ranking_url` (Task 2) ; `FrenchRankingEntry` (Task 3).
- Produces: `latest_fetch_at(session) -> datetime | None` ; `replace_entries(session, rows: list[FrenchRankingEntryRow], now: datetime) -> None` ; `fetch_entries(session) -> list[FrenchRankingEntryRow]` ; `ensure_fresh_cache(session, url: str | None, now: datetime, *, client: httpx.AsyncClient | None = None) -> list[FrenchRankingEntryRow]` ; `find_by_licence(entries, licence_number) -> FrenchRankingEntryRow | None`.

**Comportement clé :** `ensure_fresh_cache` **ne lève jamais**. Toute erreur réseau ou de parsing sert le cache existant tel quel, même périmé.

- [ ] **Step 1: Écrire les tests qui échouent**

```python
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
```

- [ ] **Step 2: Lancer les tests pour vérifier l'échec**

Run: `cd backend && PATH="/opt/homebrew/bin:$PATH" uv run pytest tests/test_french_ranking_cache.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.services.french_ranking.cache'`

- [ ] **Step 3: Écrire `cache_repository.py`**

```python
# backend/app/services/french_ranking/cache_repository.py
"""Lecture/écriture SQL pures de `french_ranking_entries`.

Aucune logique réseau ni de traduction ici — `cache.py` orchestre.
"""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.french_ranking_entry import FrenchRankingEntry

from .types import FrenchRankingEntryRow


async def latest_fetch_at(session: AsyncSession) -> datetime | None:
    return (
        await session.execute(select(func.max(FrenchRankingEntry.fetched_at)))
    ).scalar_one_or_none()


async def replace_entries(
    session: AsyncSession, rows: list[FrenchRankingEntryRow], now: datetime
) -> None:
    """Remplace TOUTES les lignes (delete puis insert, pas de diff/hash).

    Le commit appartient à l'appelant.
    """
    await session.execute(delete(FrenchRankingEntry))
    for row in rows:
        session.add(
            FrenchRankingEntry(
                licence_number=row.licence_number,
                last_name=row.last_name,
                first_name=row.first_name,
                sex=row.sex,
                birth_date=date.fromisoformat(row.birth_date) if row.birth_date else None,
                club_name_raw=row.club_name_raw,
                has_competition_licence=row.has_competition_licence,
                filiere=row.filiere,
                ligue_code=row.ligue_code,
                fetched_at=now,
            )
        )
    await session.flush()


async def fetch_entries(session: AsyncSession) -> list[FrenchRankingEntryRow]:
    rows = (await session.execute(select(FrenchRankingEntry))).scalars().all()
    return [
        FrenchRankingEntryRow(
            licence_number=r.licence_number,
            last_name=r.last_name,
            first_name=r.first_name,
            sex=r.sex,
            birth_date=r.birth_date.isoformat() if r.birth_date else None,
            club_name_raw=r.club_name_raw,
            has_competition_licence=r.has_competition_licence,
            filiere=r.filiere,
            ligue_code=r.ligue_code,
        )
        for r in rows
    ]
```

- [ ] **Step 4: Écrire `cache.py`**

```python
# backend/app/services/french_ranking/cache.py
"""Rafraîchissement paresseux (TTL 1h) du cache local French Ranking.

Ne lève JAMAIS : toute erreur réseau/parsing sert le cache existant tel quel
(même périmé) ; aucun cache -> liste vide. Le formulaire public de demande de
compte en dépend — une panne Google ne doit pas renvoyer une 500.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from .cache_repository import fetch_entries, latest_fetch_at, replace_entries
from .parser import NL_PREFIX, parse_french_ranking
from .types import FrenchRankingEntryRow, LicenceRow
from .url import normalize_french_ranking_url

logger = logging.getLogger(__name__)

_TTL = timedelta(hours=1)


def _translate(row: LicenceRow) -> FrenchRankingEntryRow:
    return FrenchRankingEntryRow(
        licence_number=row.licence,
        last_name=row.last,
        first_name=row.first,
        sex=row.sex if row.sex in ("F", "M") else None,
        birth_date=row.birth or None,
        club_name_raw=row.club_name,
        has_competition_licence=not row.club_name.startswith(NL_PREFIX),
        filiere=row.filiere_raw or None,
        ligue_code=row.region_raw or None,
    )


async def _fetch_and_parse(
    url: str, *, client: httpx.AsyncClient | None = None
) -> list[LicenceRow] | None:
    """Renvoie None en cas d'échec (l'appelant sert alors le cache existant)."""
    try:
        fetch_url = normalize_french_ranking_url(url)
        owns_client = client is None
        c = client if client is not None else httpx.AsyncClient()
        try:
            response = await c.get(fetch_url, follow_redirects=True, timeout=15.0)
            response.raise_for_status()
            return parse_french_ranking(response.text)
        finally:
            if owns_client:
                await c.aclose()
    except Exception:
        logger.warning("Échec rafraîchissement cache French Ranking (%s)", url, exc_info=True)
        return None


async def ensure_fresh_cache(
    session: AsyncSession,
    url: str | None,
    now: datetime,
    *,
    client: httpx.AsyncClient | None = None,
) -> list[FrenchRankingEntryRow]:
    if url:
        last = await latest_fetch_at(session)
        stale = last is None or (now - _as_aware(last)) >= _TTL
        if stale:
            parsed = await _fetch_and_parse(url, client=client)
            if parsed is not None:
                await replace_entries(session, [_translate(r) for r in parsed], now)
                await session.commit()
    return await fetch_entries(session)


def _as_aware(value: datetime) -> datetime:
    """SQLite relit les DATETIME sans tzinfo : on les rattache à UTC."""
    from datetime import timezone

    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def find_by_licence(
    entries: list[FrenchRankingEntryRow], licence_number: str
) -> FrenchRankingEntryRow | None:
    n = licence_number.strip()
    return next((e for e in entries if e.licence_number == n), None)
```

- [ ] **Step 5: Lancer les tests pour vérifier le succès**

Run: `cd backend && PATH="/opt/homebrew/bin:$PATH" uv run pytest tests/test_french_ranking_cache.py -v`
Expected: PASS — 7 tests

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/french_ranking/ backend/tests/test_french_ranking_cache.py
git commit -m "feat(french-ranking): cache TTL 1h tolérant aux pannes réseau"
```

---

### Task 5: Logique métier de la demande

Le cœur : vérification licence + date de naissance, appartenance au club, résolution du patineur en trois modes.

**Files:**
- Create: `backend/app/services/account_request.py`
- Test: `backend/tests/test_account_request_service.py`

**Interfaces:**
- Consumes: `FrenchRankingEntryRow`, `find_by_licence` (Task 4) ; `Skater`, `SkaterAlias`, `AppSettings` (Task 3).
- Produces:
  - `fold(value: str) -> str` — minuscules, diacritiques et ponctuation supprimés.
  - `verify_licence(entries, licence_number: str, birth_date: str) -> tuple[FrenchRankingEntryRow | None, str | None]` — `(entrée, None)` si valide, `(None, motif)` sinon. Motifs : `"licence_inconnue"`, `"naissance_incorrecte"`.
  - `is_club_member(entry, settings) -> bool`.
  - `resolve_skater(session, entry) -> tuple[Skater | None, str]` — `mode` ∈ `"exact"`, `"ambiguous"`, `"absent"`.
  - `generate_temp_password() -> str`.

- [ ] **Step 1: Écrire les tests qui échouent**

```python
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
```

- [ ] **Step 2: Lancer les tests pour vérifier l'échec**

Run: `cd backend && PATH="/opt/homebrew/bin:$PATH" uv run pytest tests/test_account_request_service.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.services.account_request'`

- [ ] **Step 3: Écrire `account_request.py`**

```python
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
from app.services.french_ranking.parser import NL_PREFIX
from app.services.french_ranking.cache import find_by_licence
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
```

- [ ] **Step 4: Lancer les tests pour vérifier le succès**

Run: `cd backend && PATH="/opt/homebrew/bin:$PATH" uv run pytest tests/test_account_request_service.py -v`
Expected: PASS — 16 tests

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/account_request.py backend/tests/test_account_request_service.py
git commit -m "feat(compte): vérification licence, appartenance club, résolution patineur"
```

---

### Task 6: Orchestration et emails

Assemble : traitement d'une demande complète, création du compte, envoi des emails, notification admin.

**Files:**
- Modify: `backend/app/services/account_request.py`
- Create: `backend/app/templates/emails/account_created.html`
- Create: `backend/app/templates/emails/account_request_rejected.html`
- Create: `backend/app/templates/emails/account_already_exists.html`
- Test: `backend/tests/test_account_request_service.py` (ajout)

**Interfaces:**
- Consumes: tout Task 5 ; `send_email`, `get_smtp_config` (`app/services/email_service.py`) ; `AccountRequest` (Task 3) ; `User`, `UserSkater`.
- Produces: `process_request(session, email: str, display_name: str, licences: list[dict], now: datetime, *, client=None) -> AccountRequest` — `licences` est une liste de `{"licence_number": str, "birth_date": str}`.

- [ ] **Step 1: Écrire les tests qui échouent**

Ajouter à `backend/tests/test_account_request_service.py` :

```python
from datetime import datetime, timezone

import httpx
from sqlalchemy import select

from app.models.account_request import AccountRequest
from app.models.user import User
from app.models.user_skater import UserSkater
from app.services.account_request import process_request

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
```

- [ ] **Step 2: Lancer les tests pour vérifier l'échec**

Run: `cd backend && PATH="/opt/homebrew/bin:$PATH" uv run pytest tests/test_account_request_service.py -v -k process_request`
Expected: FAIL — `ImportError: cannot import name 'process_request'`

- [ ] **Step 3: Ajouter `process_request` à `account_request.py`**

Ajouter les imports en tête du fichier :

```python
import logging
from datetime import datetime

from app.auth.passwords import hash_password
from app.models.account_request import AccountRequest
from app.models.user import User
from app.models.user_skater import UserSkater
from app.services.email_service import get_smtp_config, send_email
from app.services.french_ranking.cache import ensure_fresh_cache

logger = logging.getLogger(__name__)

_REJECT_LABELS = {
    "licence_inconnue": "licence introuvable dans le classement national",
    "naissance_incorrecte": "date de naissance ne correspondant pas",
    "hors_club": "patineur non licencié dans ce club",
}
```

Puis la fonction, en fin de fichier :

```python
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
```

- [ ] **Step 4: Écrire les templates d'email**

`backend/app/templates/emails/account_created.html` :

```html
{% extends "base_email.html" %}
{% block content %}
<h2 style="font-family: Manrope, sans-serif; font-size: 18px; margin: 0 0 16px;">Votre compte est prêt</h2>
<p>Bonjour {{ display_name }},</p>
<p>Votre compte {{ club_name }} a été créé. Vous pouvez suivre les résultats de :</p>
<ul>
  {% for skater in skaters %}<li>{{ skater }}</li>{% endfor %}
</ul>
<p><strong>Identifiant :</strong> {{ email }}<br>
<strong>Mot de passe temporaire :</strong> <code style="font-family: monospace; background: #f1f1f1; padding: 2px 6px; border-radius: 4px;">{{ temp_password }}</code></p>
<p>Ce mot de passe est valable <strong>7 jours</strong> et devra être changé à votre première connexion.</p>
{% if failures %}
<p style="color: #ba1a1a;"><strong>Licences non rattachées :</strong></p>
<ul style="color: #ba1a1a;">
  {% for failure in failures %}<li>{{ failure }}</li>{% endfor %}
</ul>
<p>Vous pouvez refaire une demande pour ces patineurs après avoir vérifié les informations saisies.</p>
{% endif %}
{% endblock %}
```

`backend/app/templates/emails/account_request_rejected.html` :

```html
{% extends "base_email.html" %}
{% block content %}
<h2 style="font-family: Manrope, sans-serif; font-size: 18px; margin: 0 0 16px;">Demande de compte</h2>
<p>Bonjour,</p>
<p>Votre demande de compte {{ club_name }} n'a pas pu aboutir : aucune des licences fournies n'a pu être rattachée à un patineur du club.</p>
<p>Vérifiez le numéro de licence et la date de naissance saisis, puis refaites une demande. Si le problème persiste, contactez le club.</p>
{% endblock %}
```

`backend/app/templates/emails/account_already_exists.html` :

```html
{% extends "base_email.html" %}
{% block content %}
<h2 style="font-family: Manrope, sans-serif; font-size: 18px; margin: 0 0 16px;">Vous avez déjà un compte</h2>
<p>Bonjour {{ display_name }},</p>
<p>Une demande de création de compte {{ club_name }} vient d'être faite avec cette adresse email, mais un compte existe déjà.</p>
<p>Utilisez la page de connexion habituelle. Si vous avez oublié votre mot de passe, contactez le club.</p>
{% endblock %}
```

`backend/app/templates/emails/account_request_admin.html` :

```html
{% extends "base_email.html" %}
{% block content %}
<h2 style="font-family: Manrope, sans-serif; font-size: 18px; margin: 0 0 16px;">Demande de compte — {{ status }}</h2>
<p><strong>Demandeur :</strong> {{ display_name }} ({{ email }})</p>
<p><strong>Licences :</strong> {{ licences | join(", ") }}</p>
{% if reject_reason %}<p><strong>Motifs :</strong> {{ reject_reason }}</p>{% endif %}
{% if status == "pending_admin" %}
<p>Cette demande attend une validation manuelle : un patineur approchant existe déjà, une création automatique risquerait de créer un doublon.</p>
{% endif %}
{% endblock %}
```

- [ ] **Step 5: Lancer les tests pour vérifier le succès**

Run: `cd backend && PATH="/opt/homebrew/bin:$PATH" uv run pytest tests/test_account_request_service.py -v`
Expected: PASS — 24 tests

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/account_request.py backend/app/templates/emails/ backend/tests/test_account_request_service.py
git commit -m "feat(compte): orchestration de la demande et emails"
```

---

### Task 7: Endpoint public et expiration du mot de passe temporaire

**Files:**
- Modify: `backend/app/routes/auth.py`
- Modify: `backend/app/auth/rate_limit.py`
- Test: `backend/tests/test_account_request_routes.py`

**Interfaces:**
- Consumes: `process_request` (Task 6) ; `login_limiter` existant.
- Produces: `POST /api/auth/request-account` (réponse `202` neutre) ; `account_request_limiter` ; refus de connexion sur mot de passe temporaire périmé.

**Contrainte :** la réponse est **identique** dans tous les cas — succès, licence inconnue, mauvais club, email existant.

- [ ] **Step 1: Écrire les tests qui échouent**

```python
# backend/tests/test_account_request_routes.py
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from app.models.app_settings import AppSettings
from app.models.account_request import AccountRequest
from app.models.user import User

NEUTRAL = {"detail": "Si les informations fournies sont valides, vous recevrez un email."}


@pytest.fixture(autouse=True)
def _reset_limiter():
    from app.auth.rate_limit import account_request_limiter

    account_request_limiter._attempts.clear()
    yield
    account_request_limiter._attempts.clear()


async def _seed(db_session):
    db_session.add(
        AppSettings(
            club_name="Toulouse Club Patinage",
            club_short="TCP",
            french_ranking_url=None,
            account_requests_enabled=True,
        )
    )
    await db_session.commit()


async def test_reponse_neutre_quand_la_licence_est_inconnue(client, db_session):
    await _seed(db_session)
    resp = await client.post(
        "/api/auth/request-account",
        json={
            "email": "parent@exemple.fr",
            "display_name": "Marie DUPONT",
            "licences": [{"licence_number": "999999", "birth_date": "2010-01-01"}],
        },
    )
    assert resp.status_code == 202
    assert resp.json() == NEUTRAL


async def test_la_demande_est_tracee(client, db_session):
    await _seed(db_session)
    await client.post(
        "/api/auth/request-account",
        json={
            "email": "parent@exemple.fr",
            "display_name": "Marie DUPONT",
            "licences": [{"licence_number": "999999", "birth_date": "2010-01-01"}],
        },
    )
    rows = (await db_session.execute(select(AccountRequest))).scalars().all()
    assert len(rows) == 1
    assert rows[0].email == "parent@exemple.fr"


async def test_refuse_une_charge_utile_invalide(client, db_session):
    await _seed(db_session)
    resp = await client.post(
        "/api/auth/request-account",
        json={"email": "", "display_name": "", "licences": []},
    )
    assert resp.status_code == 400


async def test_refuse_si_la_fonctionnalite_est_desactivee(client, db_session):
    db_session.add(
        AppSettings(club_name="TCP", club_short="TCP", account_requests_enabled=False)
    )
    await db_session.commit()

    resp = await client.post(
        "/api/auth/request-account",
        json={
            "email": "parent@exemple.fr",
            "display_name": "Marie",
            "licences": [{"licence_number": "1", "birth_date": "2010-01-01"}],
        },
    )
    assert resp.status_code == 403


async def test_limite_le_nombre_de_demandes(client, db_session):
    await _seed(db_session)
    payload = {
        "email": "spam@exemple.fr",
        "display_name": "Spam",
        "licences": [{"licence_number": "1", "birth_date": "2010-01-01"}],
    }
    for _ in range(3):
        await client.post("/api/auth/request-account", json=payload)
    resp = await client.post("/api/auth/request-account", json=payload)
    assert resp.status_code == 429


async def test_login_refuse_un_mot_de_passe_temporaire_perime(client, db_session):
    from app.auth.passwords import hash_password

    user = User(
        email="perime@exemple.fr",
        display_name="Périmé",
        role="skater",
        password_hash=hash_password("Temporaire123"),
        must_change_password=True,
    )
    db_session.add(user)
    await db_session.flush()
    db_session.add(
        AccountRequest(
            email="perime@exemple.fr",
            display_name="Périmé",
            licence_numbers=["1"],
            status="created",
            user_id=user.id,
            created_at=datetime.now(timezone.utc) - timedelta(days=8),
        )
    )
    await db_session.commit()

    resp = await client.post(
        "/api/auth/login", json={"email": "perime@exemple.fr", "password": "Temporaire123"}
    )
    assert resp.status_code == 401

    row = (
        await db_session.execute(
            select(AccountRequest).where(AccountRequest.email == "perime@exemple.fr")
        )
    ).scalar_one()
    assert row.status == "expired"


async def test_login_accepte_un_mot_de_passe_temporaire_recent(client, db_session):
    from app.auth.passwords import hash_password

    user = User(
        email="frais@exemple.fr",
        display_name="Frais",
        role="skater",
        password_hash=hash_password("Temporaire123"),
        must_change_password=True,
    )
    db_session.add(user)
    await db_session.flush()
    db_session.add(
        AccountRequest(
            email="frais@exemple.fr",
            display_name="Frais",
            licence_numbers=["1"],
            status="created",
            user_id=user.id,
            created_at=datetime.now(timezone.utc) - timedelta(days=2),
        )
    )
    await db_session.commit()

    resp = await client.post(
        "/api/auth/login", json={"email": "frais@exemple.fr", "password": "Temporaire123"}
    )
    assert resp.status_code == 200
```

- [ ] **Step 2: Lancer les tests pour vérifier l'échec**

Run: `cd backend && PATH="/opt/homebrew/bin:$PATH" uv run pytest tests/test_account_request_routes.py -v`
Expected: FAIL — `ImportError: cannot import name 'account_request_limiter'`

- [ ] **Step 3: Ajouter le limiteur**

À la fin de `backend/app/auth/rate_limit.py` :

```python
# Formulaire public de demande de compte : plus strict que le login, il est
# ouvert à tous et permettrait sinon d'énumérer les licences du club.
account_request_limiter = LoginRateLimiter(max_attempts=3, window_seconds=3600.0)
```

- [ ] **Step 4: Ajouter le endpoint dans `auth.py`**

Imports à ajouter en tête de `backend/app/routes/auth.py` :

```python
from datetime import timedelta

from app.auth.rate_limit import account_request_limiter
from app.models.account_request import AccountRequest
from app.services.account_request import process_request

_NEUTRAL_RESPONSE = {
    "detail": "Si les informations fournies sont valides, vous recevrez un email."
}
_TEMP_PASSWORD_TTL = timedelta(days=7)
```

Le handler, avant la déclaration du `router` :

```python
@post("/request-account")
async def request_account(data: dict, request: Request, session: AsyncSession) -> Response:
    """Demande publique de création de compte.

    La réponse est TOUJOURS identique (202) quel que soit le résultat : sans
    cela, le endpoint permettrait d'énumérer les licences du club.
    """
    settings = (await session.execute(select(AppSettings).limit(1))).scalar_one_or_none()
    if settings is None or not settings.account_requests_enabled:
        return Response(
            content={"detail": "Les demandes de compte ne sont pas activées."},
            status_code=403,
        )

    email = str(data.get("email", "")).strip().lower()
    display_name = str(data.get("display_name", "")).strip()
    licences = data.get("licences") or []

    if not email or not display_name or not isinstance(licences, list) or not licences:
        return Response(
            content={"detail": "Email, nom et au moins une licence sont requis."},
            status_code=400,
        )

    client_ip = request.client.host if request.client else "inconnu"
    for key in (email, client_ip):
        if not account_request_limiter.is_allowed(key):
            return Response(
                content={"detail": "Trop de demandes. Réessayez plus tard."},
                status_code=429,
            )
    for key in (email, client_ip):
        account_request_limiter.record(key)

    try:
        await process_request(
            session, email, display_name, licences, datetime.now(timezone.utc)
        )
    except Exception:
        import logging

        logging.getLogger(__name__).exception("Échec du traitement d'une demande de compte")

    return Response(content=_NEUTRAL_RESPONSE, status_code=202)
```

Enregistrer le handler dans le `Router` en fin de fichier :

```python
router = Router(
    path="/api/auth",
    route_handlers=[
        login,
        refresh,
        logout,
        setup,
        google_login,
        change_password,
        request_account,
    ],
    dependencies={"session": Provide(get_session)},
)
```

- [ ] **Step 5: Ajouter l'expiration dans `login`**

Dans le handler `login` de `backend/app/routes/auth.py`, juste après le contrôle `if not user.is_active:` :

```python
    # Mot de passe temporaire périmé : la demande devient caduque (évalué à la
    # connexion, pas de tâche planifiée).
    if user.must_change_password:
        pending = (
            await session.execute(
                select(AccountRequest)
                .where(AccountRequest.user_id == user.id, AccountRequest.status == "created")
                .order_by(AccountRequest.created_at.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        if pending is not None:
            created = pending.created_at
            if created.tzinfo is None:
                created = created.replace(tzinfo=timezone.utc)
            if datetime.now(timezone.utc) - created > _TEMP_PASSWORD_TTL:
                pending.status = "expired"
                await session.commit()
                raise NotAuthorizedException("Temporary password has expired")
```

- [ ] **Step 6: Lancer les tests pour vérifier le succès**

Run: `cd backend && PATH="/opt/homebrew/bin:$PATH" uv run pytest tests/test_account_request_routes.py -v`
Expected: PASS — 7 tests

- [ ] **Step 7: Vérifier l'absence de régression sur l'auth**

Run: `cd backend && PATH="/opt/homebrew/bin:$PATH" uv run pytest tests/ -q`
Expected: tous les tests passent.

- [ ] **Step 8: Commit**

```bash
git add backend/app/routes/auth.py backend/app/auth/rate_limit.py backend/tests/test_account_request_routes.py
git commit -m "feat(compte): endpoint public de demande + expiration du mot de passe temporaire"
```

---

### Task 8: Endpoints admin et exposition du réglage

**Files:**
- Modify: `backend/app/routes/admin.py`
- Modify: `backend/app/routes/club_config.py`
- Test: `backend/tests/test_account_request_routes.py` (ajout)

**Interfaces:**
- Consumes: `AccountRequest` (Task 3) ; `resolve_skater`, `generate_temp_password` (Task 5) ; `require_admin`.
- Produces: `GET /api/admin/account-requests` ; `POST /api/admin/account-requests/{request_id}/approve` (payload `{"skater_ids": [int]}`) ; `GET /api/club-config/account-requests-enabled`.

- [ ] **Step 1: Écrire les tests qui échouent**

Ajouter à `backend/tests/test_account_request_routes.py` :

```python
async def test_liste_admin_des_demandes(client, db_session, admin_token):
    await _seed(db_session)
    db_session.add(
        AccountRequest(
            email="parent@exemple.fr",
            display_name="Marie",
            licence_numbers=["123456"],
            status="pending_admin",
        )
    )
    await db_session.commit()

    resp = await client.get(
        "/api/admin/account-requests", headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    assert body[0]["status"] == "pending_admin"


async def test_liste_admin_refusee_aux_non_admins(client, db_session, reader_token):
    await _seed(db_session)
    resp = await client.get(
        "/api/admin/account-requests", headers={"Authorization": f"Bearer {reader_token}"}
    )
    assert resp.status_code in (401, 403)


async def test_approbation_cree_le_compte_et_les_liens(client, db_session, admin_token):
    from app.models.skater import Skater
    from app.models.user_skater import UserSkater

    await _seed(db_session)
    skater = Skater(first_name="Léa", last_name="DUPOND")
    db_session.add(skater)
    await db_session.flush()
    req = AccountRequest(
        email="parent@exemple.fr",
        display_name="Marie DUPONT",
        licence_numbers=["123456"],
        status="pending_admin",
    )
    db_session.add(req)
    await db_session.commit()

    resp = await client.post(
        f"/api/admin/account-requests/{req.id}/approve",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"skater_ids": [skater.id]},
    )
    assert resp.status_code == 200

    user = (
        await db_session.execute(select(User).where(User.email == "parent@exemple.fr"))
    ).scalar_one()
    assert user.role == "skater"
    assert user.must_change_password is True

    links = (
        await db_session.execute(select(UserSkater).where(UserSkater.user_id == user.id))
    ).scalars().all()
    assert len(links) == 1


async def test_approbation_refuse_une_demande_deja_resolue(client, db_session, admin_token):
    await _seed(db_session)
    req = AccountRequest(
        email="parent@exemple.fr",
        display_name="Marie",
        licence_numbers=["1"],
        status="created",
    )
    db_session.add(req)
    await db_session.commit()

    resp = await client.post(
        f"/api/admin/account-requests/{req.id}/approve",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"skater_ids": []},
    )
    assert resp.status_code == 400


async def test_le_front_sait_si_le_formulaire_est_actif(client, db_session):
    await _seed(db_session)
    resp = await client.get("/api/club-config/account-requests-enabled")
    assert resp.status_code == 200
    assert resp.json() == {"enabled": True}
```

- [ ] **Step 2: Lancer les tests pour vérifier l'échec**

Run: `cd backend && PATH="/opt/homebrew/bin:$PATH" uv run pytest tests/test_account_request_routes.py -v -k "admin or front"`
Expected: FAIL — 404 sur les nouvelles routes.

- [ ] **Step 3: Ajouter les handlers admin**

Dans `backend/app/routes/admin.py`, aligner les imports sur ceux déjà présents puis ajouter :

```python
@get("/account-requests")
async def list_account_requests(request: Request, session: AsyncSession) -> list[dict]:
    require_admin(request)
    from app.models.account_request import AccountRequest

    rows = (
        (await session.execute(select(AccountRequest).order_by(AccountRequest.created_at.desc())))
        .scalars()
        .all()
    )
    return [
        {
            "id": r.id,
            "email": r.email,
            "display_name": r.display_name,
            "licence_numbers": r.licence_numbers,
            "status": r.status,
            "reject_reason": r.reject_reason,
            "created_at": r.created_at.isoformat() if r.created_at else None,
            "resolved_at": r.resolved_at.isoformat() if r.resolved_at else None,
            "user_id": r.user_id,
        }
        for r in rows
    ]


@post("/account-requests/{request_id:int}/approve")
async def approve_account_request(
    request_id: int, data: dict, request: Request, session: AsyncSession
) -> Response:
    """Résout une demande `pending_admin` en liant les patineurs choisis par l'admin."""
    require_admin(request)
    from datetime import datetime, timezone

    from app.auth.passwords import hash_password
    from app.models.account_request import AccountRequest
    from app.models.app_settings import AppSettings
    from app.models.skater import Skater
    from app.models.user import User
    from app.models.user_skater import UserSkater
    from app.services.account_request import generate_temp_password
    from app.services.email_service import get_smtp_config, send_email

    req = (
        await session.execute(select(AccountRequest).where(AccountRequest.id == request_id))
    ).scalar_one_or_none()
    if req is None:
        raise NotFoundException("Demande introuvable")
    if req.status != "pending_admin":
        return Response(
            content={"detail": "Cette demande a déjà été traitée."}, status_code=400
        )

    skater_ids = data.get("skater_ids") or []
    if not isinstance(skater_ids, list) or not skater_ids:
        return Response(
            content={"detail": "Au moins un patineur doit être sélectionné."},
            status_code=400,
        )

    existing = (
        await session.execute(select(User).where(User.email == req.email))
    ).scalar_one_or_none()
    if existing is not None:
        return Response(
            content={"detail": "Un compte existe déjà pour cette adresse."}, status_code=400
        )

    temp_password = generate_temp_password()
    user = User(
        email=req.email,
        display_name=req.display_name,
        role="skater",
        password_hash=hash_password(temp_password),
        must_change_password=True,
    )
    session.add(user)
    await session.flush()

    linked_names: list[str] = []
    for skater_id in skater_ids:
        skater = await session.get(Skater, skater_id)
        if skater is None:
            continue
        if skater.licence_number is None and req.licence_numbers:
            skater.licence_number = req.licence_numbers[0]
        session.add(UserSkater(user_id=user.id, skater_id=skater.id))
        linked_names.append(skater.display_name)

    req.status = "created"
    req.user_id = user.id
    req.resolved_at = datetime.now(timezone.utc)
    await session.commit()

    settings = (await session.execute(select(AppSettings).limit(1))).scalar_one_or_none()
    smtp = await get_smtp_config(session)
    if smtp:
        club_name = settings.club_name if settings else "SkateLab"
        await send_email(
            to=req.email,
            subject=f"Votre compte {club_name} est prêt",
            template_name="account_created.html",
            context={
                "club_name": club_name,
                "display_name": user.display_name,
                "email": req.email,
                "temp_password": temp_password,
                "skaters": linked_names,
                "failures": [],
            },
            smtp_config=smtp,
        )

    return Response(content={"detail": "Compte créé", "user_id": user.id}, status_code=200)
```

Enregistrer les deux handlers dans le `Router` d'`admin.py` (ajouter `list_account_requests` et `approve_account_request` à `route_handlers`).

- [ ] **Step 4: Ajouter le endpoint public de configuration**

Dans `backend/app/routes/club_config.py`, ajouter le handler et l'enregistrer dans le `Router` :

```python
@get("/account-requests-enabled")
async def account_requests_enabled(session: AsyncSession) -> dict:
    """Public : dit au front s'il doit afficher le lien de demande de compte."""
    from app.models.app_settings import AppSettings

    settings = (await session.execute(select(AppSettings).limit(1))).scalar_one_or_none()
    return {"enabled": bool(settings and settings.account_requests_enabled)}
```

Vérifier que ce chemin est bien accessible sans authentification. Si `club_config.py` est protégé par le `auth_guard` global, exempter explicitement ce chemin dans `backend/app/auth/guards.py` (chercher la liste des chemins publics : `grep -n "public\|exempt\|/api/auth" backend/app/auth/guards.py`).

- [ ] **Step 5: Lancer les tests pour vérifier le succès**

Run: `cd backend && PATH="/opt/homebrew/bin:$PATH" uv run pytest tests/test_account_request_routes.py -v`
Expected: PASS — 12 tests

- [ ] **Step 6: Commit**

```bash
git add backend/app/routes/admin.py backend/app/routes/club_config.py backend/app/auth/guards.py backend/tests/test_account_request_routes.py
git commit -m "feat(compte): endpoints admin de gestion des demandes"
```

---

### Task 9: Formulaire public côté frontend

**Files:**
- Create: `frontend/src/pages/RequestAccountPage.tsx`
- Modify: `frontend/src/api/client.ts`
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/pages/LoginPage.tsx`

**Interfaces:**
- Consumes: `POST /api/auth/request-account`, `GET /api/club-config/account-requests-enabled` (Tasks 7-8).
- Produces: types `AccountRequestLicence`, `AccountRequestPayload` ; fonctions `requestAccount`, `getAccountRequestsEnabled` ; route `/request-account`.

- [ ] **Step 1: Ajouter les types et appels API**

Dans `frontend/src/api/client.ts`, suivre le style des fonctions voisines :

```typescript
export interface AccountRequestLicence {
  licence_number: string;
  birth_date: string;
}

export interface AccountRequestPayload {
  email: string;
  display_name: string;
  licences: AccountRequestLicence[];
}

export async function requestAccount(payload: AccountRequestPayload): Promise<{ detail: string }> {
  const res = await fetch("/api/auth/request-account", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  const body = await res.json().catch(() => ({ detail: "" }));
  if (!res.ok) throw new Error(body.detail || "Échec de la demande");
  return body;
}

export async function getAccountRequestsEnabled(): Promise<{ enabled: boolean }> {
  const res = await fetch("/api/club-config/account-requests-enabled");
  if (!res.ok) return { enabled: false };
  return res.json();
}
```

- [ ] **Step 2: Écrire `RequestAccountPage.tsx`**

```tsx
import { useState } from "react";
import { Link } from "react-router-dom";
import { useMutation } from "@tanstack/react-query";

import { requestAccount, type AccountRequestLicence } from "../api/client";

export default function RequestAccountPage() {
  const [email, setEmail] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [licences, setLicences] = useState<AccountRequestLicence[]>([
    { licence_number: "", birth_date: "" },
  ]);
  const [submitted, setSubmitted] = useState(false);

  const mutation = useMutation({
    mutationFn: requestAccount,
    onSuccess: () => setSubmitted(true),
  });

  const updateLicence = (index: number, patch: Partial<AccountRequestLicence>) =>
    setLicences((prev) => prev.map((l, i) => (i === index ? { ...l, ...patch } : l)));

  const canSubmit =
    email.trim() !== "" &&
    displayName.trim() !== "" &&
    licences.every((l) => l.licence_number.trim() !== "" && l.birth_date !== "");

  if (submitted) {
    return (
      <div className="min-h-screen bg-surface flex items-center justify-center p-6">
        <div className="bg-surface-container rounded-2xl p-8 max-w-md w-full">
          <h1 className="font-headline text-xl text-on-surface mb-3">Demande envoyée</h1>
          <p className="text-on-surface-variant text-sm mb-6">
            Si les informations fournies sont valides, vous recevrez un email contenant vos
            identifiants de connexion.
          </p>
          <Link to="/login" className="text-primary text-sm font-medium">
            Retour à la connexion
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-surface flex items-center justify-center p-6">
      <form
        className="bg-surface-container rounded-2xl p-8 max-w-md w-full"
        onSubmit={(e) => {
          e.preventDefault();
          mutation.mutate({ email, display_name: displayName, licences });
        }}
      >
        <h1 className="font-headline text-xl text-on-surface mb-2">Demander un compte</h1>
        <p className="text-on-surface-variant text-sm mb-6">
          Renseignez le numéro de licence et la date de naissance de chaque patineur que vous
          souhaitez suivre.
        </p>

        <label className="block text-sm text-on-surface-variant mb-1">Votre email</label>
        <input
          type="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          className="w-full bg-surface rounded-lg px-3 py-2 mb-4 text-on-surface"
          required
        />

        <label className="block text-sm text-on-surface-variant mb-1">Votre nom</label>
        <input
          type="text"
          value={displayName}
          onChange={(e) => setDisplayName(e.target.value)}
          className="w-full bg-surface rounded-lg px-3 py-2 mb-4 text-on-surface"
          required
        />

        {licences.map((licence, index) => (
          <div key={index} className="bg-surface rounded-lg p-3 mb-3">
            <label className="block text-sm text-on-surface-variant mb-1">
              Numéro de licence
            </label>
            <input
              type="text"
              inputMode="numeric"
              value={licence.licence_number}
              onChange={(e) => updateLicence(index, { licence_number: e.target.value })}
              className="w-full bg-surface-container rounded-lg px-3 py-2 mb-2 font-mono text-on-surface"
              required
            />
            <label className="block text-sm text-on-surface-variant mb-1">
              Date de naissance
            </label>
            <input
              type="date"
              value={licence.birth_date}
              onChange={(e) => updateLicence(index, { birth_date: e.target.value })}
              className="w-full bg-surface-container rounded-lg px-3 py-2 text-on-surface"
              required
            />
            {licences.length > 1 && (
              <button
                type="button"
                onClick={() => setLicences((prev) => prev.filter((_, i) => i !== index))}
                className="text-error text-sm mt-2"
              >
                Retirer
              </button>
            )}
          </div>
        ))}

        <button
          type="button"
          onClick={() =>
            setLicences((prev) => [...prev, { licence_number: "", birth_date: "" }])
          }
          className="text-primary text-sm font-medium mb-6"
        >
          + Ajouter un patineur
        </button>

        {mutation.isError && (
          <p className="text-error text-sm mb-4">{(mutation.error as Error).message}</p>
        )}

        <button
          type="submit"
          disabled={!canSubmit || mutation.isPending}
          className="w-full bg-primary text-on-primary rounded-lg py-2.5 font-medium disabled:opacity-50"
        >
          {mutation.isPending ? "Envoi..." : "Envoyer la demande"}
        </button>

        <Link to="/login" className="block text-center text-primary text-sm mt-4">
          Retour à la connexion
        </Link>
      </form>
    </div>
  );
}
```

- [ ] **Step 3: Déclarer la route**

Dans `frontend/src/App.tsx`, ajouter l'import et la route, à côté de celle de `/login` (route publique, hors `ProtectedRoute`) :

```tsx
import RequestAccountPage from "./pages/RequestAccountPage";
```

```tsx
<Route path="/request-account" element={<RequestAccountPage />} />
```

- [ ] **Step 4: Ajouter le lien conditionnel sur `LoginPage`**

Dans `frontend/src/pages/LoginPage.tsx` :

```tsx
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";

import { getAccountRequestsEnabled } from "../api/client";
```

```tsx
  const { data: accountRequests } = useQuery({
    queryKey: ["account-requests-enabled"],
    queryFn: getAccountRequestsEnabled,
  });
```

Puis, sous le bouton de connexion :

```tsx
  {accountRequests?.enabled && (
    <Link to="/request-account" className="block text-center text-primary text-sm mt-4">
      Demander un compte
    </Link>
  )}
```

- [ ] **Step 5: Vérifier la compilation**

Run: `cd frontend && PATH="/opt/homebrew/bin:$PATH" npm run build`
Expected: build réussi, aucune erreur TypeScript.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/pages/RequestAccountPage.tsx frontend/src/api/client.ts frontend/src/App.tsx frontend/src/pages/LoginPage.tsx
git commit -m "feat(compte): formulaire public de demande de compte"
```

---

### Task 10: Réglages et gestion des demandes dans SettingsPage

**Files:**
- Modify: `frontend/src/pages/SettingsPage.tsx`
- Modify: `frontend/src/api/client.ts`
- Modify: `backend/app/routes/club_config.py` (persistance des réglages)

**Interfaces:**
- Consumes: `GET /api/admin/account-requests`, `POST /api/admin/account-requests/{id}/approve` (Task 8).
- Produces: types `AccountRequest` ; fonctions `listAccountRequests`, `approveAccountRequest`, `updateFrenchRankingSettings`.

- [ ] **Step 1: Ajouter la persistance des réglages côté backend**

Repérer dans `backend/app/routes/club_config.py` le handler qui met à jour `AppSettings` (`grep -n "patch\|put\|update" backend/app/routes/club_config.py`) et y traiter les trois nouveaux champs, en suivant le style existant :

```python
    if "french_ranking_url" in data:
        settings.french_ranking_url = (data["french_ranking_url"] or "").strip() or None
    if "account_requests_enabled" in data:
        settings.account_requests_enabled = bool(data["account_requests_enabled"])
    if "french_ranking_club_names" in data:
        names = data["french_ranking_club_names"] or []
        settings.french_ranking_club_names = [str(n).strip() for n in names if str(n).strip()]
```

Vérifier que le handler existant renvoie aussi ces champs en lecture.

- [ ] **Step 2: Ajouter les appels API frontend**

Dans `frontend/src/api/client.ts` :

```typescript
export interface AccountRequest {
  id: number;
  email: string;
  display_name: string;
  licence_numbers: string[];
  status: "created" | "pending_admin" | "rejected" | "expired";
  reject_reason: string | null;
  created_at: string | null;
  resolved_at: string | null;
  user_id: string | null;
}

export async function listAccountRequests(): Promise<AccountRequest[]> {
  return apiGet("/api/admin/account-requests");
}

export async function approveAccountRequest(
  id: number,
  skaterIds: number[],
): Promise<{ detail: string; user_id: string }> {
  return apiPost(`/api/admin/account-requests/${id}/approve`, { skater_ids: skaterIds });
}
```

Adapter `apiGet`/`apiPost` aux helpers réellement présents dans le fichier (vérifier les noms avant d'écrire).

- [ ] **Step 3: Ajouter la carte de réglages French Ranking**

Dans `frontend/src/pages/SettingsPage.tsx`, à côté de la carte SMTP existante, ajouter une carte « Demandes de compte » avec : un champ URL French Ranking, une case à cocher d'activation, et un champ texte pour les graphies de club (une par ligne, converties en tableau). Réutiliser le style et le pattern de mutation de la carte SMTP voisine.

- [ ] **Step 4: Ajouter la liste des demandes en attente**

Toujours dans `SettingsPage.tsx`, ajouter une section listant les demandes (`listAccountRequests`), avec pour chaque demande en `pending_admin` un sélecteur de patineur et un bouton « Approuver » appelant `approveAccountRequest`. Les autres statuts sont affichés en lecture seule, avec leur motif.

- [ ] **Step 5: Vérifier la compilation**

Run: `cd frontend && PATH="/opt/homebrew/bin:$PATH" npm run build`
Expected: build réussi.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/pages/SettingsPage.tsx frontend/src/api/client.ts backend/app/routes/club_config.py
git commit -m "feat(compte): réglages French Ranking et gestion des demandes"
```

---

### Task 11: Vérification finale et documentation

**Files:**
- Modify: `CLAUDE.md`

- [ ] **Step 1: Lancer toute la suite backend**

Run: `cd backend && PATH="/opt/homebrew/bin:$PATH" uv run pytest -v`
Expected: tous les tests passent, aucun échec ni erreur.

- [ ] **Step 2: Lancer le build frontend**

Run: `cd frontend && PATH="/opt/homebrew/bin:$PATH" npm run build`
Expected: build réussi.

- [ ] **Step 3: Vérifier le parcours de bout en bout**

Démarrer la pile (`make dev-backend` et `make dev-frontend`), puis :

1. Dans les paramètres, renseigner une URL French Ranking et activer les demandes.
2. Vérifier que le lien « Demander un compte » apparaît sur `/login`.
3. Soumettre une demande avec une licence valide du club et la bonne date de naissance.
4. Vérifier que le compte est créé, que le patineur est lié, et que `skaters.licence_number` est renseigné :

```bash
docker compose exec backend sqlite3 /app/data/skatelab.db \
  "SELECT email, role, must_change_password FROM users ORDER BY created_at DESC LIMIT 1;"
```

(Adapter le chemin de la base au montage réel — le vérifier avec `docker compose exec backend ls /app/data`.)

5. Se connecter avec le mot de passe temporaire et vérifier que le changement de mot de passe est imposé.

- [ ] **Step 4: Documenter dans CLAUDE.md**

Dans la section « Architecture » / backend de `CLAUDE.md`, ajouter après la ligne décrivant le pipeline d'import :

```markdown
- **Demande de compte**: formulaire public (`/request-account`) → `services/account_request.py` vérifie la licence contre le cache French Ranking (`services/french_ranking/`, TTL 1h, portage depuis `ligue-app-competitions`) → compte `skater` créé automatiquement + mot de passe temporaire (7 j) par email. Réponse HTTP toujours neutre (pas d'oracle d'énumération). Cas ambigus routés vers validation admin.
```

Ajouter `AccountRequest` et `FrenchRankingEntry` à la liste des **Models**.

- [ ] **Step 5: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: documente la demande de création de compte"
```
