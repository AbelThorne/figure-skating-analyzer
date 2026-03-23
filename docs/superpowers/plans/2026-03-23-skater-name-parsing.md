# Skater Name Parsing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Split the single `name` field on Skater into `first_name` + `last_name` using uppercase-word detection, fixing name inversion, deduplication, and sorting across all competition formats.

**Architecture:** A pure-function `parse_skater_name(raw)` detects uppercase words as family name and the rest as given name, regardless of word order. The Skater model gains `first_name`/`last_name` columns; the old `name` column is removed. All API endpoints and frontend types are updated. Since the DB uses `create_all` (no Alembic), we wipe and re-import after the schema change.

**Tech Stack:** Python 3.13, SQLAlchemy (async), Litestar, React/TypeScript

---

## File Structure

| File | Action | Responsibility |
|------|--------|----------------|
| `backend/app/services/name_parser.py` | Create | `parse_skater_name()` pure function |
| `backend/tests/test_name_parser.py` | Create | Unit tests for name parsing |
| `backend/app/models/skater.py` | Modify | Add `first_name`, `last_name`; remove `name`; add unique constraint |
| `backend/app/services/import_service.py` | Modify | Use `parse_skater_name`, match on `(first_name, last_name)` |
| `backend/app/services/site_scraper.py` | Modify | Parse names in `_parse_seg_row` and `_parse_cat_row` |
| `backend/app/routes/skaters.py` | Modify | Sort by `last_name`; return `first_name`/`last_name` in API |
| `backend/app/routes/scores.py` | Modify | Return `first_name`/`last_name` instead of `name` |
| `backend/app/routes/dashboard.py` | Modify | Build `skater_name` from `first_name`/`last_name` |
| `frontend/src/api/client.ts` | Modify | Update `Skater` interface |
| `frontend/src/pages/SkaterBrowserPage.tsx` | Modify | Display/search using `first_name`/`last_name` |
| `frontend/src/pages/SkaterAnalyticsPage.tsx` | Modify | Display name from new fields |

---

### Task 1: Name parser — pure function with tests (TDD)

**Files:**
- Create: `backend/app/services/name_parser.py`
- Create: `backend/tests/test_name_parser.py`

The core heuristic: words that are fully uppercase (allowing hyphens, apostrophes, spaces between uppercase words) form the family name. Everything else is the given name. Works for both `Firstname LASTNAME` and `LASTNAME Firstname` orderings.

Edge cases to handle:
- `O'SHEA` — apostrophe inside uppercase word → family name
- `PANNEAU-THIERY` — hyphenated → family name
- `SIAO HIM FA Adam` — multi-word family name
- `GUTMANN Lara Naki` — multi-word first name
- `Fanny Sofia LIISANANTTI` — multi-word first name, family last
- `GIOTOPOULOS MOORE Hektor` — multi-word family name (all-caps words)
- Single-word names or all-lowercase — fallback: treat entire string as last name

- [ ] **Step 1: Write failing tests**

```python
# backend/tests/test_name_parser.py
import pytest
from app.services.name_parser import parse_skater_name


@pytest.mark.parametrize(
    "raw, expected_first, expected_last",
    [
        # FS Manager format: Firstname LASTNAME
        ("Fanny Sofia LIISANANTTI", "Fanny Sofia", "LIISANANTTI"),
        ("Lilou MORLON", "Lilou", "MORLON"),
        ("Emma WARIN", "Emma", "WARIN"),
        ("Lola PANNEAU-THIERY", "Lola", "PANNEAU-THIERY"),
        # ISU OWG 2026 format: LASTNAME Firstname
        ("MALININ Ilia", "Ilia", "MALININ"),
        ("KAGIYAMA Yuma", "Yuma", "KAGIYAMA"),
        ("SIAO HIM FA Adam", "Adam", "SIAO HIM FA"),
        ("GUTMANN Lara Naki", "Lara Naki", "GUTMANN"),
        ("O'SHEA Danny", "Danny", "O'SHEA"),
        ("GIOTOPOULOS MOORE Hektor", "Hektor", "GIOTOPOULOS MOORE"),
        # ISU Worlds 2025 format: Firstname LASTNAME (same as FS Manager)
        ("Adam SIAO HIM FA", "Adam", "SIAO HIM FA"),
        ("Kevin AYMOZ", "Kevin", "AYMOZ"),
        # Edge cases
        ("STELLATO-DUDEK Deanna", "Deanna", "STELLATO-DUDEK"),
        ("Mathys BUE-HUBERT", "Mathys", "BUE-HUBERT"),
    ],
)
def test_parse_skater_name(raw, expected_first, expected_last):
    first, last = parse_skater_name(raw)
    assert first == expected_first
    assert last == expected_last


def test_parse_single_uppercase_word():
    """A single uppercase word → last name only."""
    first, last = parse_skater_name("MALININ")
    assert first == ""
    assert last == "MALININ"


def test_parse_all_lowercase_fallback():
    """No uppercase words → entire string is last name."""
    first, last = parse_skater_name("unknown name")
    assert first == ""
    assert last == "unknown name"


def test_parse_empty_string():
    first, last = parse_skater_name("")
    assert first == ""
    assert last == ""


def test_parse_extra_whitespace():
    first, last = parse_skater_name("  Fanny   LIISANANTTI  ")
    assert first == "Fanny"
    assert last == "LIISANANTTI"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && PATH="/opt/homebrew/bin:$PATH" uv run pytest tests/test_name_parser.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.services.name_parser'`

- [ ] **Step 3: Implement the name parser**

```python
# backend/app/services/name_parser.py
"""Parse skater names into (first_name, last_name) using uppercase detection.

Competition result pages use two orderings:
  - "Firstname LASTNAME"    (FS Manager, ISU Worlds 2025)
  - "LASTNAME Firstname"    (ISU OWG 2026)

The reliable signal: family-name words are fully UPPERCASE (allowing
hyphens and apostrophes within a word). Given-name words use mixed case.
"""

from __future__ import annotations

import re


def _is_uppercase_word(word: str) -> bool:
    """Check if a word is an uppercase family-name word.

    Allows hyphens and apostrophes: O'SHEA, PANNEAU-THIERY.
    Must contain at least one letter.
    """
    letters = re.sub(r"['\-]", "", word)
    return len(letters) > 0 and letters == letters.upper() and letters.isalpha()


def parse_skater_name(raw: str) -> tuple[str, str]:
    """Parse a raw skater name into (first_name, last_name).

    Returns:
        A tuple of (first_name, last_name). first_name may be empty
        if only a family name is present.
    """
    raw = " ".join(raw.split())  # normalize whitespace
    if not raw:
        return ("", "")

    words = raw.split()

    # Classify each word as uppercase (family) or not (given)
    upper_indices = [i for i, w in enumerate(words) if _is_uppercase_word(w)]

    if not upper_indices:
        # No uppercase words — treat entire string as last name
        return ("", raw)

    # Uppercase words must be contiguous to form the family name.
    # Find the contiguous block of uppercase words.
    # (handles "SIAO HIM FA Adam" and "Adam SIAO HIM FA" and
    #  "GIOTOPOULOS MOORE Hektor")
    first_upper = upper_indices[0]
    last_upper = upper_indices[-1]

    # Check contiguity — all indices between first and last must be uppercase
    family_words = words[first_upper : last_upper + 1]
    given_words = words[:first_upper] + words[last_upper + 1 :]

    last_name = " ".join(family_words)
    first_name = " ".join(given_words)

    return (first_name, last_name)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && PATH="/opt/homebrew/bin:$PATH" uv run pytest tests/test_name_parser.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/name_parser.py backend/tests/test_name_parser.py
git commit -m "feat: add skater name parser with uppercase family-name detection"
```

---

### Task 2: Update Skater model — add `first_name`/`last_name`, remove `name`

**Files:**
- Modify: `backend/app/models/skater.py`

Since we use `create_all` without Alembic, this is a schema replacement — the DB will be recreated on next init.

- [ ] **Step 1: Update the Skater model**

Replace the contents of `backend/app/models/skater.py`:

```python
from typing import Optional

from sqlalchemy import String, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Skater(Base):
    __tablename__ = "skaters"
    __table_args__ = (
        UniqueConstraint("first_name", "last_name", name="uq_skater_name"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    first_name: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    last_name: Mapped[str] = mapped_column(String(255), nullable=False)
    nationality: Mapped[Optional[str]] = mapped_column(String(3), nullable=True)
    club: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    birth_year: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    scores: Mapped[list["Score"]] = relationship(  # noqa: F821
        "Score", back_populates="skater"
    )
    category_results: Mapped[list["CategoryResult"]] = relationship(  # noqa: F821
        "CategoryResult", back_populates="skater"
    )

    @property
    def display_name(self) -> str:
        """Formatted display name: 'Firstname LASTNAME'."""
        if self.first_name:
            return f"{self.first_name} {self.last_name}"
        return self.last_name
```

- [ ] **Step 2: Run existing tests to check what breaks**

Run: `cd backend && PATH="/opt/homebrew/bin:$PATH" uv run pytest -x --tb=short 2>&1 | head -50`
Expected: Failures in tests referencing `Skater.name` or `s.name`

- [ ] **Step 3: Commit**

```bash
git add backend/app/models/skater.py
git commit -m "refactor: split Skater.name into first_name + last_name columns"
```

---

### Task 3: Update import service — parse names and match on `(first_name, last_name)`

**Files:**
- Modify: `backend/app/services/import_service.py`

- [ ] **Step 1: Update `_get_or_create_skater` and callers**

In `backend/app/services/import_service.py`, apply these changes:

Add import at top:
```python
from app.services.name_parser import parse_skater_name
```

Replace `_get_or_create_skater`:
```python
async def _get_or_create_skater(
    session: AsyncSession,
    raw_name: str,
    nationality: str | None,
    club: str | None,
) -> Skater:
    first_name, last_name = parse_skater_name(raw_name)
    stmt = select(Skater).where(
        Skater.first_name == first_name,
        Skater.last_name == last_name,
    )
    skater = (await session.execute(stmt)).scalar_one_or_none()
    if not skater:
        skater = Skater(
            first_name=first_name,
            last_name=last_name,
            nationality=nationality,
            club=club,
        )
        session.add(skater)
        await session.flush()
    else:
        if not skater.nationality and nationality:
            skater.nationality = nationality
        if not skater.club and club:
            skater.club = club
    return skater
```

The callers (`run_import` loop) already pass `r.name` / `cr.name` as the first positional arg — the parameter name change from `name` to `raw_name` is internal only, no caller changes needed.

- [ ] **Step 2: Update enrichment skater matching**

In `run_enrich`, the PDF protocol uses its own name format (regex `_SKATER_HEADER_RE` in parser.py). The matching currently does `Skater.name == skater_name`. Update to parse the PDF name too:

Replace the skater lookup block in `run_enrich` (around line 186-195):

```python
                pdf_first, pdf_last = parse_skater_name(skater_name)
                stmt = (
                    select(Score)
                    .join(Skater)
                    .where(
                        Score.competition_id == comp.id,
                        Skater.first_name == pdf_first,
                        Skater.last_name == pdf_last,
                    )
                )
```

- [ ] **Step 3: Commit**

```bash
git add backend/app/services/import_service.py
git commit -m "refactor: use parse_skater_name in import service for dedup and matching"
```

---

### Task 4: Update scraper data classes — add `first_name`/`last_name` to ScrapedResult

**Files:**
- Modify: `backend/app/services/site_scraper.py`

The scraper currently stores the raw name string in `ScrapedResult.name` and `ScrapedCategoryResult.name`. These raw names flow into `_get_or_create_skater`, which now parses them. No changes needed to the scraper data classes — the parsing happens in the import service.

However, we need to update `normalize_name()` (used for fuzzy matching) and remove references to `Skater.name` anywhere in this file.

- [ ] **Step 1: Verify no direct `Skater.name` references in site_scraper.py**

The file doesn't import or reference the Skater model — it only defines data classes and scraping logic. No changes needed here.

- [ ] **Step 2: Commit (skip if no changes)**

No commit needed for this task — it was a verification step.

---

### Task 5: Update API routes — skaters endpoint

**Files:**
- Modify: `backend/app/routes/skaters.py`

- [ ] **Step 1: Update `list_skaters` sorting and `_skater_to_dict`**

Replace the sorting logic (line 25) and the dict builder:

```python
@get("/")
async def list_skaters(session: AsyncSession, club: Optional[str] = None) -> list[dict]:
    stmt = select(Skater)
    if club:
        stmt = stmt.where(func.lower(Skater.club) == club.lower())
    result = await session.execute(stmt)
    skaters = sorted(result.scalars(), key=lambda s: (s.last_name.upper(), s.first_name.upper()))
    return [_skater_to_dict(s) for s in skaters]
```

Update `_skater_to_dict`:

```python
def _skater_to_dict(s: Skater) -> dict:
    return {
        "id": s.id,
        "first_name": s.first_name,
        "last_name": s.last_name,
        "nationality": s.nationality,
        "club": s.club,
        "birth_year": s.birth_year,
    }
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/routes/skaters.py
git commit -m "refactor: update skaters API to return first_name/last_name, sort by last_name"
```

---

### Task 6: Update API routes — scores and dashboard

**Files:**
- Modify: `backend/app/routes/scores.py`
- Modify: `backend/app/routes/dashboard.py`

- [ ] **Step 1: Update scores.py**

In `_score_to_dict` and `_category_result_to_dict`, replace `"skater_name": s.skater.name` with:

```python
"skater_first_name": s.skater.first_name if s.skater else None,
"skater_last_name": s.skater.last_name if s.skater else None,
```

Same pattern in `_category_result_to_dict` (replace `cr.skater.name`).

- [ ] **Step 2: Update dashboard.py**

In all places that build `"skater_name"` from `cr.skater.name`, replace with:

```python
"skater_name": cr.skater.display_name if cr.skater else None,
```

This uses the `display_name` property added to the model, which formats as "Firstname LASTNAME".

The dashboard returns `skater_name` as a display string (not structured), which is fine for the cards/lists.

- [ ] **Step 3: Commit**

```bash
git add backend/app/routes/scores.py backend/app/routes/dashboard.py
git commit -m "refactor: update scores and dashboard routes for first_name/last_name"
```

---

### Task 7: Update frontend types and display

**Files:**
- Modify: `frontend/src/api/client.ts`
- Modify: `frontend/src/pages/SkaterBrowserPage.tsx`
- Modify: `frontend/src/pages/SkaterAnalyticsPage.tsx`
- Modify: `frontend/src/pages/CompetitionPage.tsx`
- Modify: `frontend/src/pages/StatsPage.tsx`

- [ ] **Step 1: Update TypeScript types**

In `frontend/src/api/client.ts`, update the `Skater` interface:

```typescript
export interface Skater {
  id: number;
  first_name: string;
  last_name: string;
  nationality: string | null;
  club: string | null;
  birth_year: number | null;
}
```

Update score-related interfaces that have `skater_name` — in the `Score`-like type that has `skater_name`, replace with `skater_first_name` and `skater_last_name`. Dashboard types keep `skater_name` (it's a display string).

- [ ] **Step 2: Update SkaterBrowserPage.tsx**

Replace `s.name` references:
- Search filter: `s.first_name.toLowerCase().includes(...) || s.last_name.toLowerCase().includes(...)`
- Avatar initial: `s.last_name.charAt(0).toUpperCase()`
- Display: `{s.first_name} {s.last_name}` (with last name in uppercase via the API)

- [ ] **Step 3: Update SkaterAnalyticsPage.tsx**

Replace `skater?.name` references:
- `skaterName` prop: `\`${skater?.first_name ?? ""} ${skater?.last_name ?? ""}\``
- Avatar initial: `skater?.last_name?.[0]?.toUpperCase()`
- Display name: `{skater?.first_name} {skater?.last_name}`

- [ ] **Step 4: Update CompetitionPage.tsx**

Replace `cr.skater_name` and `s.skater_name` with formatted versions:
- `{s.skater_first_name} {s.skater_last_name}`
- Same for category result rows

- [ ] **Step 5: Update StatsPage.tsx**

Replace `s.name` with `{s.first_name} {s.last_name}`.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/api/client.ts frontend/src/pages/SkaterBrowserPage.tsx frontend/src/pages/SkaterAnalyticsPage.tsx frontend/src/pages/CompetitionPage.tsx frontend/src/pages/StatsPage.tsx
git commit -m "refactor: update frontend for first_name/last_name skater fields"
```

---

### Task 8: Add flag emoji utility and display flags next to skater names

**Files:**
- Create: `frontend/src/utils/countryFlags.ts`
- Modify: `frontend/src/pages/SkaterBrowserPage.tsx`
- Modify: `frontend/src/pages/SkaterAnalyticsPage.tsx`

The site stores nationality as alpha-3 codes (e.g. "FRA"). Unicode flag emojis use alpha-2 codes. We need a mapping table (alpha-3 → alpha-2) and a converter function.

- [ ] **Step 1: Create country flag utility**

```typescript
// frontend/src/utils/countryFlags.ts

// Alpha-3 → Alpha-2 mapping for countries appearing in figure skating
const ALPHA3_TO_ALPHA2: Record<string, string> = {
  AUS: "AU", AUT: "AT", AZE: "AZ", BEL: "BE", BLR: "BY",
  BRA: "BR", CAN: "CA", CHN: "CN", CRO: "HR", CZE: "CZ",
  DEN: "DK", ESP: "ES", EST: "EE", FIN: "FI", FRA: "FR",
  GBR: "GB", GEO: "GE", GER: "DE", GRE: "GR", HUN: "HU",
  IND: "IN", ISR: "IL", ITA: "IT", JPN: "JP", KAZ: "KZ",
  KOR: "KR", LAT: "LV", LTU: "LT", MEX: "MX", NED: "NL",
  NOR: "NO", PHI: "PH", POL: "PL", POR: "PT", ROU: "RO",
  RSA: "ZA", RUS: "RU", SLO: "SI", SUI: "CH", SVK: "SK",
  SWE: "SE", THA: "TH", TPE: "TW", TUR: "TR", UKR: "UA",
  USA: "US", UZB: "UZ",
};

/**
 * Convert an alpha-3 country code to a flag emoji.
 * Returns the flag emoji or null if the code is unknown.
 */
export function countryFlag(alpha3: string | null | undefined): string | null {
  if (!alpha3) return null;
  const alpha2 = ALPHA3_TO_ALPHA2[alpha3.toUpperCase()];
  if (!alpha2) return null;
  // Regional indicator symbols: 🇦 = U+1F1E6, offset from 'A' (0x41)
  return String.fromCodePoint(
    0x1f1e6 + alpha2.charCodeAt(0) - 0x41,
    0x1f1e6 + alpha2.charCodeAt(1) - 0x41,
  );
}
```

- [ ] **Step 2: Display flag in SkaterBrowserPage**

Import the utility and show the flag emoji next to the nationality code or the skater name in the browser table.

- [ ] **Step 3: Display flag in SkaterAnalyticsPage**

Show the flag emoji next to the skater name in the hero section.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/utils/countryFlags.ts frontend/src/pages/SkaterBrowserPage.tsx frontend/src/pages/SkaterAnalyticsPage.tsx
git commit -m "feat: add flag emoji display for skater nationality"
```

---

### Task 9: Run full test suite and verify (renumbered)

**Files:** None (verification only)

- [ ] **Step 1: Run backend tests**

Run: `cd backend && PATH="/opt/homebrew/bin:$PATH" uv run pytest -v 2>&1 | tail -30`
Expected: All pass (some existing tests may need `first_name`/`last_name` updates)

- [ ] **Step 2: Fix any remaining test failures**

Tests in `test_fs_manager_scraper.py` and `test_integration.py` may reference `Skater.name` — update them to use `first_name`/`last_name`.

- [ ] **Step 3: Run frontend type check**

Run: `cd frontend && PATH="/opt/homebrew/bin:$PATH" npx tsc --noEmit 2>&1 | head -30`
Expected: No type errors

- [ ] **Step 4: Commit any fixes**

```bash
git add -u
git commit -m "fix: update remaining tests and types for name split"
```

---

### Task 10: Wipe DB and re-import test competitions

**Files:** None (manual verification)

Since the schema changed (no Alembic), the DB needs to be recreated:

- [ ] **Step 1: Delete the DB file**

```bash
rm backend/skatelab.db
```

- [ ] **Step 2: Start the backend to recreate schema**

Run: `cd backend && PATH="/opt/homebrew/bin:$PATH" uv run python -m app.main &`
Wait for startup, then import the test competitions via the API.

- [ ] **Step 3: Import test competitions and verify names**

Import the 4 bootstrap competitions and verify that:
- Names are split correctly (e.g. first_name="Fanny Sofia", last_name="LIISANANTTI")
- No duplicates for the same skater across competitions
- Sorting by last_name works correctly in the API response
- The frontend displays names properly
