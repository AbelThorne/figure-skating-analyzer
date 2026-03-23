# Club Analytics Page Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the redundant Statistiques tab with a club-level analytics page featuring progression ranking, side-by-side comparison with benchmarks, and element mastery tracking.

**Architecture:** Backend adds a category parser, element classifier, and three new endpoints under `/api/stats/`. Frontend replaces `StatsPage.tsx` with a new `ClubPage.tsx` containing three sections. New columns on `Score` and `CategoryResult` are populated during import via the category parser.

**Tech Stack:** Python/Litestar + SQLAlchemy (backend), React/TypeScript + Recharts + Tailwind CSS (frontend), pytest + pytest-asyncio (tests)

**Spec:** `docs/superpowers/specs/2026-03-23-club-analytics-page.md`

---

## File Map

### Backend — New files
| File | Responsibility |
|------|---------------|
| `backend/app/services/category_parser.py` | Pure function to parse raw category string into `skating_level`, `age_group`, `gender` |
| `backend/app/services/element_classifier.py` | Classify element codes as jump/spin/step, extract jump type and level |
| `backend/app/routes/stats.py` | Three endpoints: progression-ranking, benchmarks, element-mastery |
| `backend/tests/test_category_parser.py` | Unit tests for category parser |
| `backend/tests/test_element_classifier.py` | Unit tests for element classifier |
| `backend/tests/test_stats_routes.py` | Integration tests for the three stats endpoints |

### Backend — Modified files
| File | Change |
|------|--------|
| `backend/app/models/score.py` | Add `skating_level`, `age_group`, `gender` columns |
| `backend/app/models/category_result.py` | Add `skating_level`, `age_group`, `gender` columns |
| `backend/app/database.py` | Add migration entries for the 6 new columns |
| `backend/app/services/import_service.py` | Call `parse_category()` when creating Score/CategoryResult rows |
| `backend/app/main.py` | Register `stats_router` |

### Frontend — New files
| File | Responsibility |
|------|---------------|
| `frontend/src/utils/elementClassifier.ts` | Shared element classification utilities (extracted from SkaterAnalyticsPage) |

### Frontend — Modified files
| File | Change |
|------|--------|
| `frontend/src/api/client.ts` | Add new fields to types, add `api.stats` namespace |
| `frontend/src/pages/StatsPage.tsx` | Full rewrite → `ClubPage.tsx` content (keep same file to avoid routing changes) |
| `frontend/src/pages/SkaterAnalyticsPage.tsx` | Import element classification from shared utility |
| `frontend/src/App.tsx` | Rename tab label and page title |

---

## Task 1: Category Parser

**Files:**
- Create: `backend/app/services/category_parser.py`
- Create: `backend/tests/test_category_parser.py`

- [ ] **Step 1: Write failing tests for category parser**

Create `backend/tests/test_category_parser.py`:

```python
import pytest
from app.services.category_parser import parse_category


class TestParseLevel:
    def test_national(self):
        assert parse_category("National Novice Femme")["skating_level"] == "National"

    def test_d1_maps_to_national(self):
        assert parse_category("D1 Junior Homme")["skating_level"] == "National"

    def test_federal(self):
        assert parse_category("Fédéral Senior Femme")["skating_level"] == "Fédéral"

    def test_federale_accent_variant(self):
        assert parse_category("Fédérale Junior Femme")["skating_level"] == "Fédéral"

    def test_d2_maps_to_federal(self):
        assert parse_category("D2 Novice Homme")["skating_level"] == "Fédéral"

    def test_r1(self):
        assert parse_category("R1 Minime Femme")["skating_level"] == "R1"

    def test_d3_maps_to_r1(self):
        assert parse_category("D3 Benjamin Homme")["skating_level"] == "R1"

    def test_r2(self):
        assert parse_category("R2 Novice Femme")["skating_level"] == "R2"

    def test_r3_a(self):
        assert parse_category("R3 A Jun-Sen Serie 1 Femme")["skating_level"] == "R3 A"

    def test_r3_b(self):
        assert parse_category("R3 B Poussin Serie 1 Femme")["skating_level"] == "R3 B"

    def test_r3_c(self):
        assert parse_category("R3 C Babies Homme")["skating_level"] == "R3 C"

    def test_adulte_bronze(self):
        assert parse_category("Adulte Bronze Femme")["skating_level"] == "Adulte Bronze"

    def test_adulte_argent(self):
        assert parse_category("Adulte Argent Homme")["skating_level"] == "Adulte Argent"

    def test_adulte_or(self):
        assert parse_category("Adulte Or Femme")["skating_level"] == "Adulte Or"

    def test_no_level_returns_none(self):
        assert parse_category("Novice Femme")["skating_level"] is None


class TestParseAgeGroup:
    def test_babies(self):
        assert parse_category("R3 C Babies Femme")["age_group"] == "Babies"

    def test_poussin(self):
        assert parse_category("R3 B Poussin Serie 1 Femme")["age_group"] == "Poussin"

    def test_benjamin(self):
        assert parse_category("National Benjamin Femme")["age_group"] == "Benjamin"

    def test_minime(self):
        assert parse_category("R1 Minime Homme")["age_group"] == "Minime"

    def test_novice(self):
        assert parse_category("R2 Novice Femme")["age_group"] == "Novice"

    def test_junior(self):
        assert parse_category("Fédéral Junior Femme")["age_group"] == "Junior"

    def test_senior(self):
        assert parse_category("Fédéral Senior Homme")["age_group"] == "Senior"

    def test_junior_senior_compound(self):
        assert parse_category("R1 Junior-Senior Femme")["age_group"] == "Junior-Senior"

    def test_jun_sen_abbreviation(self):
        assert parse_category("R3 A Jun-Sen Serie 1 Femme")["age_group"] == "Junior-Senior"

    def test_min_nov_abbreviation(self):
        assert parse_category("R3 A Min-Nov Serie 1 Femme")["age_group"] == "Minime-Novice"

    def test_adulte_age_group(self):
        assert parse_category("Adulte Bronze Femme")["age_group"] == "Adulte"

    def test_adulte_or_age_group(self):
        assert parse_category("Adulte Or Homme")["age_group"] == "Adulte"


class TestParseGender:
    def test_femme(self):
        assert parse_category("R2 Minime Femme")["gender"] == "Femme"

    def test_homme(self):
        assert parse_category("R1 Minime Homme")["gender"] == "Homme"

    def test_no_gender(self):
        assert parse_category("R2 Minime")["gender"] is None


class TestEdgeCases:
    def test_full_compound_r3(self):
        result = parse_category("R3 A Min-Nov Serie 1 Femme")
        assert result == {
            "skating_level": "R3 A",
            "age_group": "Minime-Novice",
            "gender": "Femme",
        }

    def test_serie_stripped(self):
        result = parse_category("R3 B Benjamin Serie 1 Femme")
        assert result["age_group"] == "Benjamin"

    def test_empty_string(self):
        result = parse_category("")
        assert result == {"skating_level": None, "age_group": None, "gender": None}

    def test_none_input(self):
        result = parse_category(None)
        assert result == {"skating_level": None, "age_group": None, "gender": None}

    def test_case_insensitive(self):
        result = parse_category("national novice femme")
        assert result["skating_level"] == "National"
        assert result["age_group"] == "Novice"
        assert result["gender"] == "Femme"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && PATH="/opt/homebrew/bin:$PATH" uv run pytest tests/test_category_parser.py -v`
Expected: FAIL (module not found)

- [ ] **Step 3: Implement category parser**

Create `backend/app/services/category_parser.py`:

```python
"""Parse raw FFSG category strings into structured fields."""

import logging
import re
import unicodedata

logger = logging.getLogger(__name__)

# Level tokens checked in order. Multi-word tokens first to avoid partial matches.
_LEVEL_RULES: list[tuple[re.Pattern, str]] = [
    (re.compile(r"\bAdulte\s+Bronze\b", re.IGNORECASE), "Adulte Bronze"),
    (re.compile(r"\bAdulte\s+Argent\b", re.IGNORECASE), "Adulte Argent"),
    (re.compile(r"\bAdulte\s+Or\b", re.IGNORECASE), "Adulte Or"),
    (re.compile(r"\bR3\s+A\b", re.IGNORECASE), "R3 A"),
    (re.compile(r"\bR3\s+B\b", re.IGNORECASE), "R3 B"),
    (re.compile(r"\bR3\s+C\b", re.IGNORECASE), "R3 C"),
    (re.compile(r"\b(?:National|D1)\b", re.IGNORECASE), "National"),
    (re.compile(r"\b(?:F[eé]d[eé]ral[e]?|D2)\b", re.IGNORECASE), "Fédéral"),
    (re.compile(r"\b(?:R1|D3)\b", re.IGNORECASE), "R1"),
    (re.compile(r"\bR2\b", re.IGNORECASE), "R2"),
]

# Age group tokens. Compound groups first to avoid partial matches.
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

    # For Adulte levels, age_group is always "Adulte"
    if skating_level and skating_level.startswith("Adulte"):
        age_group = "Adulte"
    else:
        # Strip "Serie X" before matching age group
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && PATH="/opt/homebrew/bin:$PATH" uv run pytest tests/test_category_parser.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/category_parser.py backend/tests/test_category_parser.py
git commit -m "feat: add category parser for FFSG category strings"
```

---

## Task 2: Element Classifier

**Files:**
- Create: `backend/app/services/element_classifier.py`
- Create: `backend/tests/test_element_classifier.py`
- Create: `frontend/src/utils/elementClassifier.ts`
- Modify: `frontend/src/pages/SkaterAnalyticsPage.tsx` (import from shared utility)

- [ ] **Step 1: Write failing tests for element classifier**

Create `backend/tests/test_element_classifier.py`:

```python
import pytest
from app.services.element_classifier import classify_element, extract_jump_type, extract_level


class TestClassifyElement:
    # Jumps
    def test_single_axel(self):
        assert classify_element("1A") == "jump"

    def test_double_toe(self):
        assert classify_element("2T") == "jump"

    def test_double_salchow(self):
        assert classify_element("2S") == "jump"

    def test_double_loop(self):
        assert classify_element("2Lo") == "jump"

    def test_double_flip(self):
        assert classify_element("2F") == "jump"

    def test_double_lutz(self):
        assert classify_element("2Lz") == "jump"

    def test_triple_toe(self):
        assert classify_element("3T") == "jump"

    def test_triple_axel(self):
        assert classify_element("3A") == "jump"

    # Spins
    def test_combo_spin(self):
        assert classify_element("CCoSp4") == "spin"

    def test_flying_combo_spin(self):
        assert classify_element("FCSp3") == "spin"

    def test_flying_sit_spin(self):
        assert classify_element("FSSp4") == "spin"

    def test_camel_spin_no_level(self):
        assert classify_element("CCSp") == "spin"

    def test_layback_spin(self):
        assert classify_element("LSp4") == "spin"

    # Steps
    def test_step_sequence(self):
        assert classify_element("StSq3") == "step"

    def test_choreo_sequence(self):
        assert classify_element("ChSq1") == "step"

    # Not a false positive
    def test_spin_not_jump(self):
        assert classify_element("FCSp3") != "jump"

    def test_step_not_jump(self):
        assert classify_element("StSq3") != "jump"

    # Unknown
    def test_unknown_element(self):
        assert classify_element("BoDs3") is None


class TestExtractJumpType:
    def test_double_axel(self):
        assert extract_jump_type("2A") == "2A"

    def test_triple_toe(self):
        assert extract_jump_type("3T") == "3T"

    def test_single_loop(self):
        assert extract_jump_type("1Lo") == "1Lo"

    def test_quad_salchow(self):
        assert extract_jump_type("4S") == "4S"

    def test_non_jump_returns_none(self):
        assert extract_jump_type("CCoSp4") is None


class TestExtractLevel:
    def test_level_4(self):
        assert extract_level("CCoSp4") == 4

    def test_level_3(self):
        assert extract_level("StSq3") == 3

    def test_level_1(self):
        assert extract_level("ChSq1") == 1

    def test_no_level(self):
        assert extract_level("CCSp") == 0

    def test_b_suffix(self):
        assert extract_level("CCoSpB") == 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && PATH="/opt/homebrew/bin:$PATH" uv run pytest tests/test_element_classifier.py -v`
Expected: FAIL (module not found)

- [ ] **Step 3: Implement Python element classifier**

Create `backend/app/services/element_classifier.py`:

```python
"""Classify ISU element codes into jump, spin, or step categories."""

import re

# Jump: starts with optional rotation count (1-4) followed by jump type code
_JUMP_PATTERN = re.compile(r"^([1-4]?)(A|T|S|Lo|Lz|F)\b")

# Spin: contains "Sp" followed by optional level digit or B, near end
_SPIN_PATTERN = re.compile(r"Sp[B0-4]?$")

# Step/choreo sequence
_STEP_PATTERN = re.compile(r"^(StSq|ChSq)")

# Level extraction: digit at end of code
_LEVEL_PATTERN = re.compile(r"(\d)$")


def classify_element(name: str) -> str | None:
    """Classify an element code as 'jump', 'spin', 'step', or None."""
    if _JUMP_PATTERN.match(name):
        return "jump"
    if _SPIN_PATTERN.search(name):
        return "spin"
    if _STEP_PATTERN.match(name):
        return "step"
    return None


def extract_jump_type(name: str) -> str | None:
    """Extract the jump type with rotation count, e.g. '2A', '3Lz'.

    Returns None if not a jump element.
    """
    m = _JUMP_PATTERN.match(name)
    if not m:
        return None
    rotation = m.group(1) or "1"
    jump_code = m.group(2)
    return f"{rotation}{jump_code}"


def extract_level(name: str) -> int:
    """Extract the level number from an element code.

    Returns 0 if no level or B suffix.
    """
    m = _LEVEL_PATTERN.search(name)
    if m:
        return int(m.group(1))
    return 0
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && PATH="/opt/homebrew/bin:$PATH" uv run pytest tests/test_element_classifier.py -v`
Expected: All PASS

- [ ] **Step 5: Create shared frontend element classifier**

Create `frontend/src/utils/elementClassifier.ts`:

```typescript
// Jump: starts with optional rotation count (1-4) followed by jump type
const JUMP_PATTERN = /^([1-4]?)(A|T|S|Lo|Lz|F)\b/;

// Spin: contains "Sp" near end with optional level
const SPIN_PATTERN = /Sp[B0-4]?$/;

// Step/choreo sequence
const STEP_PATTERN = /^(StSq|ChSq)/;

const LEVEL_PATTERN = /(\d)$/;

export type ElementType = "jump" | "spin" | "step";

export function classifyElement(name: string): ElementType | null {
  if (JUMP_PATTERN.test(name)) return "jump";
  if (SPIN_PATTERN.test(name)) return "spin";
  if (STEP_PATTERN.test(name)) return "step";
  return null;
}

export function isJumpElement(name: string): boolean {
  return JUMP_PATTERN.test(name);
}

export function isSpinElement(name: string): boolean {
  return SPIN_PATTERN.test(name);
}

export function isStepElement(name: string): boolean {
  return STEP_PATTERN.test(name);
}

export function extractJumpType(name: string): string | null {
  const m = name.match(JUMP_PATTERN);
  if (!m) return null;
  const rotation = m[1] || "1";
  return `${rotation}${m[2]}`;
}

export function elementLevel(name: string): number {
  const m = name.match(LEVEL_PATTERN);
  if (m) return parseInt(m[1], 10);
  if (/B$/i.test(name)) return 0;
  return 0;
}
```

- [ ] **Step 6: Update SkaterAnalyticsPage to use shared utility**

In `frontend/src/pages/SkaterAnalyticsPage.tsx`:
- Replace the inline `JUMP_PATTERN`, `isJumpElement`, `isSpinElement`, `isStepElement`, `elementLevel` functions (lines 23-38) with imports from `../utils/elementClassifier`.
- Remove the old inline definitions.

Replace:
```typescript
// ─── Jump detection ───────────────────────────────────────────────────────────
const JUMP_PATTERN = /\d*(A|T|S|F|Lo|Lz|q)\b/i;
function isJumpElement(name: string) {
  return JUMP_PATTERN.test(name);
}

// ─── Spin detection ───────────────────────────────────────────────────────────
function isSpinElement(name: string) {
  return /Sp/i.test(name);
}
/** Extract spin/step level: digit at end = that digit, B suffix = 0.5, otherwise 0 */
function elementLevel(name: string): number {
  const digitMatch = name.match(/(\d)$/);
  if (digitMatch) return parseInt(digitMatch[1], 10);
  if (/B$/i.test(name)) return 0.5;
  return 0;
}

// ─── Step / choreo detection ──────────────────────────────────────────────────
function isStepElement(name: string) {
  return /St|ChSq/i.test(name);
}
```

With:
```typescript
import { isJumpElement, isSpinElement, isStepElement, elementLevel } from "../utils/elementClassifier";
```

Note: `elementLevel` returns `0` for "B" suffix in the new version (was `0.5`). This is intentional — "B" means "Base level" which is effectively level 0 in the ISU system.

- [ ] **Step 7: Commit**

```bash
git add backend/app/services/element_classifier.py backend/tests/test_element_classifier.py \
  frontend/src/utils/elementClassifier.ts frontend/src/pages/SkaterAnalyticsPage.tsx
git commit -m "feat: add element classifier (Python + TypeScript shared utility)"
```

---

## Task 3: Database Schema — New Columns + Migration

**Files:**
- Modify: `backend/app/models/score.py`
- Modify: `backend/app/models/category_result.py`
- Modify: `backend/app/database.py`

- [ ] **Step 1: Add columns to Score model**

In `backend/app/models/score.py`, add after the `raw_data` field (line 31):

```python
    skating_level: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    age_group: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    gender: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
```

- [ ] **Step 2: Add columns to CategoryResult model**

In `backend/app/models/category_result.py`, add after the `fs_rank` field (line 37):

```python
    skating_level: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    age_group: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    gender: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
```

- [ ] **Step 3: Add migration entries**

In `backend/app/database.py`, add to the `_MIGRATIONS` list inside `_migrate_add_columns`:

```python
    _MIGRATIONS = [
        ("competitions", "rink", "VARCHAR(255)"),
        ("scores", "skating_level", "VARCHAR(20)"),
        ("scores", "age_group", "VARCHAR(30)"),
        ("scores", "gender", "VARCHAR(10)"),
        ("category_results", "skating_level", "VARCHAR(20)"),
        ("category_results", "age_group", "VARCHAR(30)"),
        ("category_results", "gender", "VARCHAR(10)"),
    ]
```

- [ ] **Step 4: Verify models work with existing tests**

Run: `cd backend && PATH="/opt/homebrew/bin:$PATH" uv run pytest tests/ -v --timeout=30`
Expected: All existing tests still pass (new columns are nullable so they don't break anything)

- [ ] **Step 5: Commit**

```bash
git add backend/app/models/score.py backend/app/models/category_result.py backend/app/database.py
git commit -m "feat: add skating_level, age_group, gender columns to Score and CategoryResult"
```

---

## Task 4: Import Service Integration + Backfill

**Files:**
- Modify: `backend/app/services/import_service.py`
- Modify: `backend/app/database.py` (backfill routine)

- [ ] **Step 1: Integrate category parser into import service**

In `backend/app/services/import_service.py`, add import at the top:

```python
from app.services.category_parser import parse_category
```

Then, where `Score` is created (around line 111-126), after creating the `score` object, add:

```python
            parsed = parse_category(r.category)
            score.skating_level = parsed["skating_level"]
            score.age_group = parsed["age_group"]
            score.gender = parsed["gender"]
```

Similarly, where `CategoryResult` is created (around line 143-152), after creating the `cat_result` object:

```python
            parsed = parse_category(cr.category)
            cat_result.skating_level = parsed["skating_level"]
            cat_result.age_group = parsed["age_group"]
            cat_result.gender = parsed["gender"]
```

- [ ] **Step 2: Add backfill routine to database.py**

In `backend/app/database.py`, add a `_backfill_categories` function and call it from `init_db()` after migrations:

```python
async def _backfill_categories() -> None:
    """Parse category field for existing rows that lack structured fields."""
    from app.models.score import Score
    from app.models.category_result import CategoryResult
    from app.services.category_parser import parse_category

    async with async_session_factory() as session:
        # Backfill scores
        result = await session.execute(
            select(Score).where(Score.skating_level.is_(None), Score.category.isnot(None))
        )
        scores = result.scalars().all()
        for score in scores:
            parsed = parse_category(score.category)
            score.skating_level = parsed["skating_level"]
            score.age_group = parsed["age_group"]
            score.gender = parsed["gender"]

        # Backfill category results
        result = await session.execute(
            select(CategoryResult).where(
                CategoryResult.skating_level.is_(None), CategoryResult.category.isnot(None)
            )
        )
        cat_results = result.scalars().all()
        for cr in cat_results:
            parsed = parse_category(cr.category)
            cr.skating_level = parsed["skating_level"]
            cr.age_group = parsed["age_group"]
            cr.gender = parsed["gender"]

        if scores or cat_results:
            await session.commit()
            logger.info("Backfilled categories: %d scores, %d category_results", len(scores), len(cat_results))
```

In `init_db()`, add after the `_migrate_add_columns` call (after line 32):

```python
    await _backfill_categories()
```

- [ ] **Step 3: Commit**

```bash
git add backend/app/services/import_service.py backend/app/database.py
git commit -m "feat: integrate category parser into import + add backfill routine"
```

---

## Task 5: Stats Routes — Progression Ranking

**Files:**
- Create: `backend/app/routes/stats.py`
- Create: `backend/tests/test_stats_routes.py`
- Modify: `backend/app/main.py`

- [ ] **Step 1: Write failing test for progression-ranking endpoint**

Create `backend/tests/test_stats_routes.py`:

```python
import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.competition import Competition
from app.models.skater import Skater
from app.models.category_result import CategoryResult
from app.models.score import Score
from app.models.app_settings import AppSettings


@pytest_asyncio.fixture
async def seed_data(db_session: AsyncSession):
    """Seed competitions, skaters, and category results for stats tests."""
    settings = AppSettings(club_name="Test Club", club_short="TC", current_season="2025-2026")
    db_session.add(settings)

    comp1 = Competition(name="Comp 1", url="http://test/comp1", date="2025-10-15", season="2025-2026")
    comp2 = Competition(name="Comp 2", url="http://test/comp2", date="2025-12-01", season="2025-2026")
    comp3 = Competition(name="Comp 3", url="http://test/comp3", date="2026-02-10", season="2025-2026")
    db_session.add_all([comp1, comp2, comp3])
    await db_session.flush()

    skater1 = Skater(first_name="Marie", last_name="Dupont", club="TC")
    skater2 = Skater(first_name="Jean", last_name="Martin", club="TC")
    skater3 = Skater(first_name="Other", last_name="Club", club="OC")
    db_session.add_all([skater1, skater2, skater3])
    await db_session.flush()

    # Marie: 3 results, improving (R2 Minime)
    for comp, total in [(comp1, 30.0), (comp2, 35.0), (comp3, 40.0)]:
        db_session.add(CategoryResult(
            competition_id=comp.id, skater_id=skater1.id,
            category="R2 Minime Femme", overall_rank=1, combined_total=total,
            segment_count=1, skating_level="R2", age_group="Minime", gender="Femme",
        ))

    # Jean: 2 results, declining (R1 Junior)
    for comp, total in [(comp1, 50.0), (comp3, 45.0)]:
        db_session.add(CategoryResult(
            competition_id=comp.id, skater_id=skater2.id,
            category="R1 Junior Homme", overall_rank=2, combined_total=total,
            segment_count=1, skating_level="R1", age_group="Junior", gender="Homme",
        ))

    # Other club skater: should not appear with club filter
    db_session.add(CategoryResult(
        competition_id=comp1.id, skater_id=skater3.id,
        category="R2 Minime Femme", overall_rank=3, combined_total=25.0,
        segment_count=1, skating_level="R2", age_group="Minime", gender="Femme",
    ))

    await db_session.commit()
    return {"skater1": skater1, "skater2": skater2, "skater3": skater3}


@pytest.mark.asyncio
async def test_progression_ranking_default(client: AsyncClient, admin_token: str, seed_data):
    resp = await client.get(
        "/api/stats/progression-ranking",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    # Marie (gain=10) should be first, Jean (gain=-5) second
    assert len(data) == 2
    assert data[0]["skater_name"] == "Marie Dupont"
    assert data[0]["tss_gain"] == 10.0
    assert data[0]["first_tss"] == 30.0
    assert data[0]["last_tss"] == 40.0
    assert data[0]["competitions_count"] == 3
    assert len(data[0]["sparkline"]) == 3
    assert data[1]["skater_name"] == "Jean Martin"
    assert data[1]["tss_gain"] == -5.0


@pytest.mark.asyncio
async def test_progression_ranking_filter_level(client: AsyncClient, admin_token: str, seed_data):
    resp = await client.get(
        "/api/stats/progression-ranking?skating_level=R2",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["skater_name"] == "Marie Dupont"


@pytest.mark.asyncio
async def test_progression_ranking_filter_gender(client: AsyncClient, admin_token: str, seed_data):
    resp = await client.get(
        "/api/stats/progression-ranking?gender=Homme",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["skater_name"] == "Jean Martin"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && PATH="/opt/homebrew/bin:$PATH" uv run pytest tests/test_stats_routes.py -v`
Expected: FAIL (route not found / 404)

- [ ] **Step 3: Implement stats router with progression-ranking endpoint**

Create `backend/app/routes/stats.py`:

```python
"""Club-level statistics endpoints."""

from typing import Optional

from litestar import Router, get
from litestar.di import Provide
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_session
from app.models.app_settings import AppSettings
from app.models.category_result import CategoryResult
from app.models.competition import Competition
from app.models.skater import Skater


async def _get_club_short(session: AsyncSession, club: Optional[str]) -> Optional[str]:
    """Resolve club_short from parameter or app settings."""
    if club:
        return club
    result = await session.execute(select(AppSettings).limit(1))
    settings = result.scalar_one_or_none()
    return settings.club_short if settings else None


@get("/progression-ranking")
async def progression_ranking(
    session: AsyncSession,
    season: Optional[str] = None,
    club: Optional[str] = None,
    skating_level: Optional[str] = None,
    age_group: Optional[str] = None,
    gender: Optional[str] = None,
) -> list[dict]:
    club_short = await _get_club_short(session, club)

    # If no season specified, get current from settings
    if not season:
        result = await session.execute(select(AppSettings).limit(1))
        settings = result.scalar_one_or_none()
        season = settings.current_season if settings else None

    stmt = (
        select(CategoryResult)
        .join(CategoryResult.competition)
        .join(CategoryResult.skater)
        .options(selectinload(CategoryResult.skater), selectinload(CategoryResult.competition))
        .where(CategoryResult.combined_total.isnot(None))
        .order_by(Competition.date.asc())
    )

    if season:
        stmt = stmt.where(Competition.season == season)
    if club_short:
        stmt = stmt.where(func.upper(Skater.club) == club_short.upper())
    if skating_level:
        stmt = stmt.where(CategoryResult.skating_level == skating_level)
    if age_group:
        stmt = stmt.where(CategoryResult.age_group == age_group)
    if gender:
        stmt = stmt.where(CategoryResult.gender == gender)

    result = await session.execute(stmt)
    rows = result.scalars().all()

    # Group by skater + skating_level + age_group
    from collections import defaultdict
    groups: dict[tuple, list] = defaultdict(list)
    for cr in rows:
        key = (cr.skater_id, cr.skating_level, cr.age_group)
        groups[key].append(cr)

    ranking = []
    for (skater_id, level, age), entries in groups.items():
        if len(entries) < 2:
            continue
        first = entries[0]
        last = entries[-1]
        skater = first.skater
        ranking.append({
            "skater_id": skater_id,
            "skater_name": f"{skater.first_name} {skater.last_name}",
            "skating_level": level,
            "age_group": age,
            "gender": first.gender,
            "first_tss": first.combined_total,
            "last_tss": last.combined_total,
            "tss_gain": round(last.combined_total - first.combined_total, 2),
            "competitions_count": len(entries),
            "sparkline": [
                {
                    "date": e.competition.date if e.competition else None,
                    "value": e.combined_total,
                }
                for e in entries
            ],
        })

    # Sort by tss_gain desc, then last_tss desc
    ranking.sort(key=lambda x: (-x["tss_gain"], -x["last_tss"]))
    return ranking


router = Router(
    path="/api/stats",
    route_handlers=[progression_ranking],
    dependencies={"session": Provide(get_session)},
)
```

- [ ] **Step 4: Register stats router in main.py**

In `backend/app/main.py`, add import:

```python
from app.routes.stats import router as stats_router
```

And add `stats_router` to the `route_handlers` list.

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd backend && PATH="/opt/homebrew/bin:$PATH" uv run pytest tests/test_stats_routes.py -v`
Expected: All PASS

- [ ] **Step 6: Commit**

```bash
git add backend/app/routes/stats.py backend/tests/test_stats_routes.py backend/app/main.py
git commit -m "feat: add progression-ranking stats endpoint"
```

---

## Task 6: Stats Routes — Benchmarks Endpoint

**Files:**
- Modify: `backend/app/routes/stats.py`
- Modify: `backend/tests/test_stats_routes.py`

- [ ] **Step 1: Write failing test for benchmarks endpoint**

Add to `backend/tests/test_stats_routes.py`:

```python
@pytest_asyncio.fixture
async def seed_benchmark_data(db_session: AsyncSession):
    """Seed broader field data for benchmark computation."""
    settings = AppSettings(club_name="Test Club", club_short="TC", current_season="2025-2026")
    db_session.add(settings)

    comp = Competition(name="Big Comp", url="http://test/big", date="2025-11-01", season="2025-2026")
    db_session.add(comp)
    await db_session.flush()

    # Create 10 skaters with R2 Minime Femme results
    totals = [20.0, 25.0, 28.0, 30.0, 33.0, 35.0, 38.0, 40.0, 45.0, 50.0]
    for i, total in enumerate(totals):
        skater = Skater(first_name=f"Skater{i}", last_name=f"Test{i}", club=f"Club{i}")
        db_session.add(skater)
        await db_session.flush()
        db_session.add(CategoryResult(
            competition_id=comp.id, skater_id=skater.id,
            category="R2 Minime Femme", overall_rank=i + 1, combined_total=total,
            segment_count=1, skating_level="R2", age_group="Minime", gender="Femme",
        ))

    await db_session.commit()


@pytest.mark.asyncio
async def test_benchmarks(client: AsyncClient, admin_token: str, seed_benchmark_data):
    resp = await client.get(
        "/api/stats/benchmarks?skating_level=R2&age_group=Minime&gender=Femme",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["skating_level"] == "R2"
    assert data["age_group"] == "Minime"
    assert data["gender"] == "Femme"
    assert data["data_points"] == 10
    assert data["min"] == 20.0
    assert data["max"] == 50.0
    # Median of [20,25,28,30,33,35,38,40,45,50] = (33+35)/2 = 34.0
    assert data["median"] == 34.0
    assert data["p25"] is not None
    assert data["p75"] is not None


@pytest.mark.asyncio
async def test_benchmarks_insufficient_data(client: AsyncClient, admin_token: str, seed_benchmark_data):
    resp = await client.get(
        "/api/stats/benchmarks?skating_level=R1&age_group=Junior&gender=Homme",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["data_points"] == 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && PATH="/opt/homebrew/bin:$PATH" uv run pytest tests/test_stats_routes.py::test_benchmarks -v`
Expected: FAIL (404)

- [ ] **Step 3: Implement benchmarks endpoint**

Add to `backend/app/routes/stats.py`:

```python
import statistics


@get("/benchmarks")
async def benchmarks(
    session: AsyncSession,
    skating_level: str,
    age_group: str,
    gender: str,
    season: Optional[str] = None,
) -> dict:
    stmt = (
        select(CategoryResult.combined_total)
        .join(CategoryResult.competition)
        .where(
            CategoryResult.combined_total.isnot(None),
            CategoryResult.skating_level == skating_level,
            CategoryResult.age_group == age_group,
            CategoryResult.gender == gender,
        )
    )
    if season:
        stmt = stmt.where(Competition.season == season)

    result = await session.execute(stmt)
    totals = sorted([row[0] for row in result.all()])

    if not totals:
        return {
            "skating_level": skating_level,
            "age_group": age_group,
            "gender": gender,
            "data_points": 0,
            "min": None,
            "max": None,
            "median": None,
            "p25": None,
            "p75": None,
        }

    n = len(totals)
    return {
        "skating_level": skating_level,
        "age_group": age_group,
        "gender": gender,
        "data_points": n,
        "min": totals[0],
        "max": totals[-1],
        "median": round(statistics.median(totals), 2),
        "p25": round(statistics.quantiles(totals, n=4)[0], 2) if n >= 2 else totals[0],
        "p75": round(statistics.quantiles(totals, n=4)[2], 2) if n >= 2 else totals[-1],
    }
```

Add `benchmarks` to `route_handlers` in the router.

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && PATH="/opt/homebrew/bin:$PATH" uv run pytest tests/test_stats_routes.py -v -k benchmark`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/routes/stats.py backend/tests/test_stats_routes.py
git commit -m "feat: add benchmarks stats endpoint"
```

---

## Task 7: Stats Routes — Element Mastery Endpoint

**Files:**
- Modify: `backend/app/routes/stats.py`
- Modify: `backend/tests/test_stats_routes.py`

- [ ] **Step 1: Write failing test for element-mastery endpoint**

Add to `backend/tests/test_stats_routes.py`:

```python
@pytest_asyncio.fixture
async def seed_element_data(db_session: AsyncSession):
    """Seed scores with element data for mastery tests."""
    settings = AppSettings(club_name="Test Club", club_short="TC", current_season="2025-2026")
    db_session.add(settings)

    comp = Competition(name="Comp E", url="http://test/compe", date="2025-11-01", season="2025-2026")
    db_session.add(comp)
    await db_session.flush()

    skater = Skater(first_name="Marie", last_name="Dupont", club="TC")
    db_session.add(skater)
    await db_session.flush()

    score = Score(
        competition_id=comp.id, skater_id=skater.id,
        segment="FS", category="R2 Minime Femme",
        total_score=40.0, technical_score=22.0, component_score=18.0,
        skating_level="R2", age_group="Minime", gender="Femme",
        elements=[
            {"name": "2A", "base_value": 3.3, "goe": 0.5, "score": 3.8, "number": 1, "markers": [], "judge_goe": [1, 1, 0], "info_flag": None},
            {"name": "2Lz", "base_value": 2.1, "goe": -0.3, "score": 1.8, "number": 2, "markers": [], "judge_goe": [-1, -1, 0], "info_flag": None},
            {"name": "2T", "base_value": 1.3, "goe": 0.0, "score": 1.3, "number": 3, "markers": [], "judge_goe": [0, 0, 0], "info_flag": None},
            {"name": "CCoSp4", "base_value": 3.5, "goe": 1.0, "score": 4.5, "number": 4, "markers": [], "judge_goe": [2, 2, 2], "info_flag": None},
            {"name": "FSSp3", "base_value": 2.6, "goe": 0.5, "score": 3.1, "number": 5, "markers": [], "judge_goe": [1, 1, 1], "info_flag": None},
            {"name": "StSq3", "base_value": 3.3, "goe": 0.8, "score": 4.1, "number": 6, "markers": [], "judge_goe": [2, 1, 2], "info_flag": None},
        ],
    )
    db_session.add(score)
    await db_session.commit()


@pytest.mark.asyncio
async def test_element_mastery(client: AsyncClient, admin_token: str, seed_element_data):
    resp = await client.get(
        "/api/stats/element-mastery",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    data = resp.json()

    # Jumps
    assert len(data["jumps"]) == 3
    jump_map = {j["jump_type"]: j for j in data["jumps"]}
    assert jump_map["2A"]["attempts"] == 1
    assert jump_map["2A"]["positive_goe_pct"] == 100.0
    assert jump_map["2Lz"]["negative_goe_pct"] == 100.0
    assert jump_map["2T"]["neutral_goe_pct"] == 100.0

    # Spins
    assert len(data["spins"]) == 2
    spin_map = {s["element_type"]: s for s in data["spins"]}
    assert spin_map["CCoSp"]["level_distribution"]["4"] == 1
    assert spin_map["FSSp"]["level_distribution"]["3"] == 1

    # Steps
    assert len(data["steps"]) == 1
    assert data["steps"][0]["element_type"] == "StSq"
    assert data["steps"][0]["level_distribution"]["3"] == 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && PATH="/opt/homebrew/bin:$PATH" uv run pytest tests/test_stats_routes.py::test_element_mastery -v`
Expected: FAIL (404)

- [ ] **Step 3: Implement element-mastery endpoint**

Add to `backend/app/routes/stats.py`:

```python
from app.models.score import Score
from app.services.element_classifier import classify_element, extract_jump_type, extract_level


@get("/element-mastery")
async def element_mastery(
    session: AsyncSession,
    season: Optional[str] = None,
    club: Optional[str] = None,
    skating_level: Optional[str] = None,
    age_group: Optional[str] = None,
    gender: Optional[str] = None,
) -> dict:
    club_short = await _get_club_short(session, club)

    if not season:
        result = await session.execute(select(AppSettings).limit(1))
        settings = result.scalar_one_or_none()
        season = settings.current_season if settings else None

    stmt = (
        select(Score)
        .join(Score.competition)
        .join(Score.skater)
        .where(Score.elements.isnot(None))
    )

    if season:
        stmt = stmt.where(Competition.season == season)
    if club_short:
        stmt = stmt.where(func.upper(Skater.club) == club_short.upper())
    if skating_level:
        stmt = stmt.where(Score.skating_level == skating_level)
    if age_group:
        stmt = stmt.where(Score.age_group == age_group)
    if gender:
        stmt = stmt.where(Score.gender == gender)

    result = await session.execute(stmt)
    scores = result.scalars().all()

    # Aggregate elements
    from collections import defaultdict

    jump_stats: dict[str, dict] = defaultdict(lambda: {"attempts": 0, "positive": 0, "negative": 0, "neutral": 0, "goe_sum": 0.0})
    spin_stats: dict[str, dict] = defaultdict(lambda: {"attempts": 0, "levels": defaultdict(int), "goe_sum": 0.0})
    step_stats: dict[str, dict] = defaultdict(lambda: {"attempts": 0, "levels": defaultdict(int), "goe_sum": 0.0})

    for score in scores:
        if not score.elements:
            continue
        for el in score.elements:
            name = el.get("name", "")
            goe = el.get("goe", 0) or 0
            el_type = classify_element(name)

            if el_type == "jump":
                jt = extract_jump_type(name)
                if jt:
                    jump_stats[jt]["attempts"] += 1
                    jump_stats[jt]["goe_sum"] += goe
                    if goe > 0:
                        jump_stats[jt]["positive"] += 1
                    elif goe < 0:
                        jump_stats[jt]["negative"] += 1
                    else:
                        jump_stats[jt]["neutral"] += 1

            elif el_type == "spin":
                # Strip level digit for grouping: "CCoSp4" -> "CCoSp"
                base = name.rstrip("0123456789B")
                level = extract_level(name)
                spin_stats[base]["attempts"] += 1
                spin_stats[base]["levels"][str(level)] += 1
                spin_stats[base]["goe_sum"] += goe

            elif el_type == "step":
                base = name.rstrip("0123456789B")
                level = extract_level(name)
                step_stats[base]["attempts"] += 1
                step_stats[base]["levels"][str(level)] += 1
                step_stats[base]["goe_sum"] += goe

    # Format response
    # Sort jumps by difficulty order
    jump_order = ["1A", "1T", "1S", "1Lo", "1F", "1Lz", "2T", "2S", "2Lo", "2F", "2Lz", "2A", "3T", "3S", "3Lo", "3F", "3Lz", "3A", "4T", "4S", "4Lo", "4F", "4Lz", "4A"]
    jump_order_map = {j: i for i, j in enumerate(jump_order)}

    jumps = []
    for jt, stats in sorted(jump_stats.items(), key=lambda x: jump_order_map.get(x[0], 99)):
        n = stats["attempts"]
        jumps.append({
            "jump_type": jt,
            "attempts": n,
            "positive_goe_pct": round(stats["positive"] / n * 100, 1),
            "negative_goe_pct": round(stats["negative"] / n * 100, 1),
            "neutral_goe_pct": round(stats["neutral"] / n * 100, 1),
            "avg_goe": round(stats["goe_sum"] / n, 2),
        })

    def _format_level_stats(stats_dict):
        result = []
        for base, stats in sorted(stats_dict.items()):
            n = stats["attempts"]
            level_dist = {str(i): stats["levels"].get(str(i), 0) for i in range(5)}
            result.append({
                "element_type": base,
                "attempts": n,
                "level_distribution": level_dist,
                "avg_goe": round(stats["goe_sum"] / n, 2),
            })
        return result

    return {
        "jumps": jumps,
        "spins": _format_level_stats(spin_stats),
        "steps": _format_level_stats(step_stats),
    }
```

Add `element_mastery` to `route_handlers` in the router.

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && PATH="/opt/homebrew/bin:$PATH" uv run pytest tests/test_stats_routes.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/routes/stats.py backend/tests/test_stats_routes.py
git commit -m "feat: add element-mastery stats endpoint"
```

---

## Task 8: Frontend API Client Updates

**Files:**
- Modify: `frontend/src/api/client.ts`

- [ ] **Step 1: Add new fields to existing types**

In `frontend/src/api/client.ts`, add to the `Score` interface (after `elements: ScoreElement[] | null;`):

```typescript
  skating_level: string | null;
  age_group: string | null;
  gender: string | null;
```

Add to `CategoryResult` interface (after `fs_rank: number | null;`):

```typescript
  skating_level: string | null;
  age_group: string | null;
  gender: string | null;
```

- [ ] **Step 2: Add new response types**

Add before the `api` object:

```typescript
export interface ProgressionRankingEntry {
  skater_id: number;
  skater_name: string;
  skating_level: string | null;
  age_group: string | null;
  gender: string | null;
  first_tss: number;
  last_tss: number;
  tss_gain: number;
  competitions_count: number;
  sparkline: { date: string | null; value: number }[];
}

export interface BenchmarkData {
  skating_level: string;
  age_group: string;
  gender: string;
  data_points: number;
  min: number | null;
  max: number | null;
  median: number | null;
  p25: number | null;
  p75: number | null;
}

export interface JumpMastery {
  jump_type: string;
  attempts: number;
  positive_goe_pct: number;
  negative_goe_pct: number;
  neutral_goe_pct: number;
  avg_goe: number;
}

export interface LevelMastery {
  element_type: string;
  attempts: number;
  level_distribution: Record<string, number>;
  avg_goe: number;
}

export interface ElementMasteryData {
  jumps: JumpMastery[];
  spins: LevelMastery[];
  steps: LevelMastery[];
}
```

- [ ] **Step 3: Add api.stats namespace**

Add inside the `api` object, after the `dashboard` namespace:

```typescript
  stats: {
    progressionRanking: (params?: {
      season?: string;
      club?: string;
      skating_level?: string;
      age_group?: string;
      gender?: string;
    }) => {
      const qs = new URLSearchParams();
      if (params?.season) qs.set("season", params.season);
      if (params?.club) qs.set("club", params.club);
      if (params?.skating_level) qs.set("skating_level", params.skating_level);
      if (params?.age_group) qs.set("age_group", params.age_group);
      if (params?.gender) qs.set("gender", params.gender);
      const query = qs.toString() ? `?${qs}` : "";
      return request<ProgressionRankingEntry[]>(`/stats/progression-ranking${query}`);
    },
    benchmarks: (params: {
      skating_level: string;
      age_group: string;
      gender: string;
      season?: string;
    }) => {
      const qs = new URLSearchParams({
        skating_level: params.skating_level,
        age_group: params.age_group,
        gender: params.gender,
      });
      if (params.season) qs.set("season", params.season);
      return request<BenchmarkData>(`/stats/benchmarks?${qs}`);
    },
    elementMastery: (params?: {
      season?: string;
      club?: string;
      skating_level?: string;
      age_group?: string;
      gender?: string;
    }) => {
      const qs = new URLSearchParams();
      if (params?.season) qs.set("season", params.season);
      if (params?.club) qs.set("club", params.club);
      if (params?.skating_level) qs.set("skating_level", params.skating_level);
      if (params?.age_group) qs.set("age_group", params.age_group);
      if (params?.gender) qs.set("gender", params.gender);
      const query = qs.toString() ? `?${qs}` : "";
      return request<ElementMasteryData>(`/stats/element-mastery${query}`);
    },
  },
```

- [ ] **Step 4: Commit**

```bash
git add frontend/src/api/client.ts
git commit -m "feat: add stats API types and client functions"
```

---

## Task 9: Frontend — Club Page (Progression Ranking Section)

**Files:**
- Modify: `frontend/src/pages/StatsPage.tsx` (full rewrite)
- Modify: `frontend/src/App.tsx`

- [ ] **Step 1: Update App.tsx navigation**

In `frontend/src/App.tsx`:
- Change the nav label from `"STATISTIQUES"` to `"CLUB"`
- Change the page title mapping from `"Statistiques"` to `"Club"`

- [ ] **Step 2: Rewrite StatsPage.tsx — page shell with shared filters and progression ranking**

Replace the entire content of `frontend/src/pages/StatsPage.tsx`. The component structure:

```tsx
import { useState, useMemo } from "react";
import { Link } from "react-router-dom";
import { useQuery, keepPreviousData } from "@tanstack/react-query";
import { api, ProgressionRankingEntry } from "../api/client";

// ─── Sparkline component ─────────────────────────────────────────────────────
function Sparkline({ data }: { data: { value: number }[] }) {
  if (data.length < 2) return null;
  const values = data.map((d) => d.value);
  const min = Math.min(...values);
  const max = Math.max(...values);
  const range = max - min || 1;
  const w = 80, h = 24;
  const points = values
    .map((v, i) => `${(i / (values.length - 1)) * w},${h - ((v - min) / range) * h}`)
    .join(" ");
  return (
    <svg width={w} height={h} className="inline-block">
      <polyline points={points} fill="none" stroke="#2e6385" strokeWidth="1.5" />
    </svg>
  );
}

// ─── Sort helper ──────────────────────────────────────────────────────────────
type SortKey = "tss_gain" | "last_tss" | "skater_name" | "competitions_count";

export default function StatsPage() {
  // ── Shared filter state ────────────────────────────────────────────────────
  const [selectedSeason, setSelectedSeason] = useState<string | null>(null);
  const [selectedLevel, setSelectedLevel] = useState<string | null>(null);
  const [selectedAgeGroup, setSelectedAgeGroup] = useState<string | null>(null);
  const [selectedGender, setSelectedGender] = useState<string | null>(null);
  const [sortKey, setSortKey] = useState<SortKey>("tss_gain");
  const [sortAsc, setSortAsc] = useState(false);

  const { data: config } = useQuery({
    queryKey: ["config"],
    queryFn: api.config.get,
    staleTime: Infinity,
  });

  const season = selectedSeason ?? config?.current_season ?? undefined;

  // ── Progression ranking ────────────────────────────────────────────────────
  const { data: ranking = [], isLoading: loadingRanking } = useQuery({
    queryKey: ["progression-ranking", season, selectedLevel, selectedAgeGroup, selectedGender],
    queryFn: () =>
      api.stats.progressionRanking({
        season,
        skating_level: selectedLevel ?? undefined,
        age_group: selectedAgeGroup ?? undefined,
        gender: selectedGender ?? undefined,
      }),
    placeholderData: keepPreviousData,
  });

  // ── Derive filter options from ranking data ────────────────────────────────
  const filterOptions = useMemo(() => {
    const levels = new Set<string>();
    const ages = new Set<string>();
    const genders = new Set<string>();
    for (const r of ranking) {
      if (r.skating_level) levels.add(r.skating_level);
      if (r.age_group) ages.add(r.age_group);
      if (r.gender) genders.add(r.gender);
    }
    return {
      levels: [...levels].sort(),
      ageGroups: [...ages].sort(),
      genders: [...genders].sort(),
    };
  }, [ranking]);

  // ── Sorted ranking ─────────────────────────────────────────────────────────
  const sortedRanking = useMemo(() => {
    const sorted = [...ranking].sort((a, b) => {
      let cmp = 0;
      if (sortKey === "skater_name") cmp = a.skater_name.localeCompare(b.skater_name);
      else cmp = (a[sortKey] ?? 0) - (b[sortKey] ?? 0);
      if (cmp === 0) cmp = (b.last_tss ?? 0) - (a.last_tss ?? 0); // tie-break
      return sortAsc ? cmp : -cmp;
    });
    return sorted;
  }, [ranking, sortKey, sortAsc]);

  function toggleSort(key: SortKey) {
    if (sortKey === key) setSortAsc(!sortAsc);
    else { setSortKey(key); setSortAsc(false); }
  }

  const sortIcon = (key: SortKey) =>
    sortKey === key ? (sortAsc ? "arrow_upward" : "arrow_downward") : "";

  return (
    <div className="p-6 space-y-6 font-body">
      {/* Page header */}
      <div>
        <h1 className="font-headline text-2xl font-bold text-on-surface">Vue club</h1>
        <p className="text-sm text-on-surface-variant mt-1">
          Analyse collective des patineurs du club
        </p>
      </div>

      {/* Shared filters */}
      <div className="flex flex-wrap gap-3">
        {config?.current_season && (
          <select
            className="bg-surface-container-high rounded-lg px-3 py-2 text-sm text-on-surface focus:outline-none focus:ring-2 focus:ring-primary"
            value={selectedSeason ?? ""}
            onChange={(e) => setSelectedSeason(e.target.value || null)}
          >
            <option value="">Saison en cours</option>
            {/* Season options would ideally come from an endpoint; for now use current */}
          </select>
        )}
        <select
          className="bg-surface-container-high rounded-lg px-3 py-2 text-sm text-on-surface focus:outline-none focus:ring-2 focus:ring-primary"
          value={selectedLevel ?? ""}
          onChange={(e) => setSelectedLevel(e.target.value || null)}
        >
          <option value="">Tous les niveaux</option>
          {filterOptions.levels.map((l) => (
            <option key={l} value={l}>{l}</option>
          ))}
        </select>
        <select
          className="bg-surface-container-high rounded-lg px-3 py-2 text-sm text-on-surface focus:outline-none focus:ring-2 focus:ring-primary"
          value={selectedAgeGroup ?? ""}
          onChange={(e) => setSelectedAgeGroup(e.target.value || null)}
        >
          <option value="">Toutes les catégories</option>
          {filterOptions.ageGroups.map((a) => (
            <option key={a} value={a}>{a}</option>
          ))}
        </select>
        <select
          className="bg-surface-container-high rounded-lg px-3 py-2 text-sm text-on-surface focus:outline-none focus:ring-2 focus:ring-primary"
          value={selectedGender ?? ""}
          onChange={(e) => setSelectedGender(e.target.value || null)}
        >
          <option value="">Tous</option>
          {filterOptions.genders.map((g) => (
            <option key={g} value={g}>{g}</option>
          ))}
        </select>
      </div>

      {/* ── PROGRESSION SECTION ── */}
      <div className="bg-surface-container-lowest rounded-xl shadow-sm p-6">
        <h2 className="text-base font-extrabold font-headline text-on-surface mb-4">
          Progression
        </h2>
        {loadingRanking ? (
          <div className="animate-pulse bg-surface-container-low rounded-xl h-40" />
        ) : sortedRanking.length === 0 ? (
          <p className="text-on-surface-variant text-sm">
            {selectedLevel || selectedAgeGroup || selectedGender
              ? "Aucun résultat pour les filtres sélectionnés."
              : "Aucun patineur n'a participé à au moins 2 compétitions cette saison."}
          </p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[700px] border-collapse">
              <thead>
                <tr className="bg-surface-container-low">
                  {[
                    { key: "skater_name" as SortKey, label: "Patineur", left: true },
                    { key: null, label: "Niveau / Catégorie", left: false },
                    { key: null, label: "Premier", left: false },
                    { key: null, label: "Dernier", left: false },
                    { key: "tss_gain" as SortKey, label: "Δ", left: false },
                    { key: null, label: "Tendance", left: false },
                    { key: "competitions_count" as SortKey, label: "Comp.", left: false },
                  ].map((col, i) => (
                    <th
                      key={col.label}
                      className={`text-[10px] font-black uppercase tracking-widest text-on-surface-variant px-3 py-2.5 ${
                        col.left ? "text-left" : "text-right"
                      } ${i === 0 ? "rounded-tl-xl" : ""} ${i === 6 ? "rounded-tr-xl" : ""} ${
                        col.key ? "cursor-pointer select-none hover:text-on-surface" : ""
                      }`}
                      onClick={col.key ? () => toggleSort(col.key!) : undefined}
                    >
                      {col.label}
                      {col.key && sortIcon(col.key) && (
                        <span className="material-symbols-outlined text-[12px] ml-0.5 align-middle">
                          {sortIcon(col.key)}
                        </span>
                      )}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {sortedRanking.map((entry, idx) => (
                  <tr
                    key={`${entry.skater_id}-${entry.skating_level}`}
                    className={idx % 2 === 0 ? "bg-surface-container-lowest" : "bg-surface-container-low/30"}
                  >
                    <td className="px-3 py-2 text-sm">
                      <Link
                        to={`/patineurs/${entry.skater_id}`}
                        className="text-primary hover:underline font-medium"
                      >
                        {entry.skater_name}
                      </Link>
                    </td>
                    <td className="px-3 py-2 text-right">
                      <span className="inline-block bg-primary-container/30 text-on-surface-variant text-[10px] font-bold px-2 py-0.5 rounded-full">
                        {[entry.skating_level, entry.age_group].filter(Boolean).join(" · ")}
                      </span>
                    </td>
                    <td className="px-3 py-2 text-right font-mono text-sm text-on-surface-variant">
                      {entry.first_tss.toFixed(2)}
                    </td>
                    <td className="px-3 py-2 text-right font-mono text-sm text-on-surface">
                      {entry.last_tss.toFixed(2)}
                    </td>
                    <td className={`px-3 py-2 text-right font-mono text-sm font-bold ${
                      entry.tss_gain > 0 ? "text-green-700" : entry.tss_gain < 0 ? "text-error" : "text-on-surface-variant"
                    }`}>
                      {entry.tss_gain > 0 ? "+" : ""}{entry.tss_gain.toFixed(2)}
                    </td>
                    <td className="px-3 py-2 text-right">
                      <Sparkline data={entry.sparkline} />
                    </td>
                    <td className="px-3 py-2 text-right font-mono text-sm text-on-surface-variant">
                      {entry.competitions_count}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* ── COMPARISON SECTION (Task 10) ── */}
      {/* Placeholder — will be added in Task 10 */}

      {/* ── ELEMENT MASTERY SECTION (Task 11) ── */}
      {/* Placeholder — will be added in Task 11 */}
    </div>
  );
}
```

- [ ] **Step 3: Verify the page renders**

Run: `cd frontend && PATH="/opt/homebrew/bin:$PATH" npm run build`
Expected: Build succeeds with no TypeScript errors

- [ ] **Step 4: Commit**

```bash
git add frontend/src/pages/StatsPage.tsx frontend/src/App.tsx
git commit -m "feat: replace Statistiques page with Club page (progression ranking)"
```

---

## Task 10: Frontend — Comparison Section with Benchmarks

**Files:**
- Modify: `frontend/src/pages/StatsPage.tsx`

- [ ] **Step 1: Add comparison section**

Add below the progression ranking section in `StatsPage.tsx`.

New imports needed at the top of the file:

```tsx
import {
  ComposedChart, Line, XAxis, YAxis, CartesianGrid, Tooltip,
  Legend, ResponsiveContainer, ReferenceArea, ReferenceLine,
} from "recharts";
import { api, ProgressionRankingEntry, Skater, CategoryResult, BenchmarkData } from "../api/client";
```

New state and queries to add inside the component (after the progression ranking section state):

```tsx
  // ── Comparison section state ───────────────────────────────────────────────
  const [selectedSkaterIds, setSelectedSkaterIds] = useState<number[]>([]);
  const [levelOverride, setLevelOverride] = useState<string | null>(null);

  const { data: skaters = [] } = useQuery({
    queryKey: ["skaters", config?.club_short],
    queryFn: () => api.skaters.list(config?.club_short),
    enabled: !!config?.club_short,
  });

  const SKATER_COLORS = ["#2e6385", "#7cb9e8", "#e8a87c"];

  // Fetch category results for each selected skater
  const skaterResults = selectedSkaterIds.map((id, i) => {
    // eslint-disable-next-line react-hooks/rules-of-hooks
    const { data } = useQuery({
      queryKey: ["skater-category-results", id, season],
      queryFn: () => api.skaters.categoryResults(id, season),
      enabled: id != null,
    });
    return { id, color: SKATER_COLORS[i], results: data ?? [] };
  });

  // Determine benchmark params from first selected skater's results
  const firstSkaterResult = skaterResults[0]?.results[0];
  const benchmarkLevel = levelOverride ?? firstSkaterResult?.skating_level ?? null;
  const benchmarkAgeGroup = firstSkaterResult?.age_group ?? null;
  const benchmarkGender = firstSkaterResult?.gender ?? null;

  const { data: benchmark } = useQuery({
    queryKey: ["benchmarks", benchmarkLevel, benchmarkAgeGroup, benchmarkGender, season],
    queryFn: () =>
      api.stats.benchmarks({
        skating_level: benchmarkLevel!,
        age_group: benchmarkAgeGroup!,
        gender: benchmarkGender!,
        season,
      }),
    enabled: !!benchmarkLevel && !!benchmarkAgeGroup && !!benchmarkGender,
  });

  // Build chart data: merge all skaters' results onto a common date axis
  const comparisonData = useMemo(() => {
    const dateMap = new Map<string, Record<string, number | null>>();
    for (const { id, results } of skaterResults) {
      for (const r of results) {
        if (!r.competition_date || r.combined_total == null) continue;
        const date = r.competition_date.slice(0, 10);
        if (!dateMap.has(date)) dateMap.set(date, {});
        dateMap.get(date)![`skater_${id}`] = r.combined_total;
      }
    }
    return [...dateMap.entries()]
      .sort(([a], [b]) => a.localeCompare(b))
      .map(([date, values]) => ({ date, ...values }));
  }, [skaterResults]);

  function toggleSkater(id: number) {
    setSelectedSkaterIds((prev) => {
      if (prev.includes(id)) return prev.filter((x) => x !== id);
      if (prev.length >= 3) return prev;
      return [...prev, id];
    });
  }
```

The JSX for the comparison section (replace the `{/* Placeholder — will be added in Task 10 */}` comment):

```tsx
      {/* ── COMPARISON SECTION ── */}
      <div className="bg-surface-container-lowest rounded-xl shadow-sm p-6">
        <h2 className="text-base font-extrabold font-headline text-on-surface mb-4">
          Comparaison
        </h2>

        {/* Skater selector as pills */}
        <div className="flex flex-wrap gap-2 mb-4">
          {skaters.map((s: Skater) => {
            const selected = selectedSkaterIds.includes(s.id);
            const idx = selectedSkaterIds.indexOf(s.id);
            return (
              <button
                key={s.id}
                onClick={() => toggleSkater(s.id)}
                className={`px-3 py-1.5 rounded-full text-xs font-bold transition-colors ${
                  selected
                    ? "text-white"
                    : "bg-surface-container-high text-on-surface-variant hover:bg-surface-container"
                }`}
                style={selected ? { backgroundColor: SKATER_COLORS[idx] } : {}}
                disabled={!selected && selectedSkaterIds.length >= 3}
              >
                {s.first_name} {s.last_name}
              </button>
            );
          })}
        </div>

        {/* Level override */}
        {selectedSkaterIds.length > 0 && (
          <div className="flex items-center gap-3 mb-4">
            <span className="text-xs text-on-surface-variant">Comparer au niveau :</span>
            <select
              className="bg-surface-container-high rounded-lg px-3 py-1.5 text-xs text-on-surface focus:outline-none focus:ring-2 focus:ring-primary"
              value={levelOverride ?? ""}
              onChange={(e) => setLevelOverride(e.target.value || null)}
            >
              <option value="">
                {benchmarkLevel ?? "Auto"}
              </option>
              {filterOptions.levels.map((l) => (
                <option key={l} value={l}>{l}</option>
              ))}
            </select>
            {benchmark && benchmark.data_points > 0 && benchmark.data_points < 3 && (
              <span className="text-xs text-on-surface-variant italic">
                Données insuffisantes pour le benchmark
              </span>
            )}
          </div>
        )}

        {selectedSkaterIds.length === 0 ? (
          <div className="flex items-center justify-center h-[260px] text-on-surface-variant text-sm">
            Sélectionnez des patineurs pour comparer leur progression.
          </div>
        ) : (
          <ResponsiveContainer width="100%" height={300}>
            <ComposedChart data={comparisonData} margin={{ top: 4, right: 8, left: -16, bottom: 4 }}>
              <CartesianGrid vertical={false} stroke="#e0e3e5" />
              <XAxis
                dataKey="date"
                tick={{ fontSize: 10, fontFamily: "Inter, sans-serif", fill: "#41484d" }}
                axisLine={false}
                tickLine={false}
              />
              <YAxis
                tick={{ fontSize: 10, fontFamily: "monospace", fill: "#41484d" }}
                axisLine={false}
                tickLine={false}
                domain={["auto", "auto"]}
              />
              <Tooltip
                contentStyle={{
                  fontSize: 11, fontFamily: "Inter, sans-serif",
                  borderRadius: 12, border: "none",
                  boxShadow: "0 1px 4px rgba(0,0,0,0.12)",
                }}
              />
              <Legend wrapperStyle={{ fontSize: 11 }} />

              {/* Benchmark bands */}
              {benchmark && benchmark.data_points >= 3 && benchmark.min != null && benchmark.max != null && (
                <>
                  <ReferenceArea
                    y1={benchmark.min} y2={benchmark.max}
                    fill="#2e6385" fillOpacity={0.04}
                    label={{ value: "", position: "right" }}
                  />
                  <ReferenceArea
                    y1={benchmark.p25!} y2={benchmark.p75!}
                    fill="#2e6385" fillOpacity={0.08}
                  />
                  <ReferenceLine
                    y={benchmark.median!}
                    stroke="#2e6385" strokeDasharray="4 4" strokeOpacity={0.5}
                    label={{ value: "Médiane", position: "right", fontSize: 9, fill: "#41484d" }}
                  />
                </>
              )}

              {/* Skater lines */}
              {skaterResults.map(({ id, color }) => {
                const skater = skaters.find((s: Skater) => s.id === id);
                return (
                  <Line
                    key={id}
                    type="monotone"
                    dataKey={`skater_${id}`}
                    name={skater ? `${skater.first_name} ${skater.last_name}` : `#${id}`}
                    stroke={color}
                    strokeWidth={2}
                    dot={{ r: 3, fill: color, stroke: "#fff", strokeWidth: 1.5 }}
                    connectNulls={false}
                  />
                );
              })}
            </ComposedChart>
          </ResponsiveContainer>
        )}
      </div>
```

**Note on hooks in loops**: The `skaterResults` map uses `useQuery` inside a `.map()`. This works because `selectedSkaterIds` length is bounded (max 3) and the array is stable. However, if the linter complains, refactor to 3 separate `useQuery` calls with `enabled` guards. The implementing agent should handle this.

- [ ] **Step 2: Verify build**

Run: `cd frontend && PATH="/opt/homebrew/bin:$PATH" npm run build`
Expected: Build succeeds

- [ ] **Step 3: Commit**

```bash
git add frontend/src/pages/StatsPage.tsx
git commit -m "feat: add comparison section with benchmark bands to Club page"
```

---

## Task 11: Frontend — Element Mastery Section

**Files:**
- Modify: `frontend/src/pages/StatsPage.tsx`

- [ ] **Step 1: Add element mastery section**

Add below the comparison section in `StatsPage.tsx`.

New imports to add (merge with existing):

```tsx
import { BarChart, Bar, Cell } from "recharts";
```

New query inside the component:

```tsx
  // ── Element mastery ────────────────────────────────────────────────────────
  const { data: mastery, isLoading: loadingMastery } = useQuery({
    queryKey: ["element-mastery", season, selectedLevel, selectedAgeGroup, selectedGender],
    queryFn: () =>
      api.stats.elementMastery({
        season,
        skating_level: selectedLevel ?? undefined,
        age_group: selectedAgeGroup ?? undefined,
        gender: selectedGender ?? undefined,
      }),
    placeholderData: keepPreviousData,
  });

  const hasElements = mastery && (mastery.jumps.length > 0 || mastery.spins.length > 0 || mastery.steps.length > 0);
```

Replace the `{/* Placeholder — will be added in Task 11 */}` comment with:

```tsx
      {/* ── ELEMENT MASTERY SECTION ── */}
      <div className="bg-surface-container-lowest rounded-xl shadow-sm p-6">
        <h2 className="text-base font-extrabold font-headline text-on-surface mb-4">
          Maîtrise des éléments
        </h2>

        {loadingMastery ? (
          <div className="animate-pulse bg-surface-container-low rounded-xl h-60" />
        ) : !hasElements ? (
          /* "Enrichir avec les PDF" prompt */
          <div className="bg-surface-container-lowest rounded-xl shadow-sm p-5 border-l-4 border-tertiary">
            <div className="flex items-start gap-3">
              <span className="material-symbols-outlined text-tertiary text-2xl mt-0.5">
                picture_as_pdf
              </span>
              <div>
                <p className="font-bold font-headline text-on-surface">
                  Enrichir avec les PDF
                </p>
                <p className="text-xs text-on-surface-variant mt-1">
                  {mastery && mastery.jumps.length === 0 && (selectedLevel || selectedAgeGroup || selectedGender)
                    ? "Aucun élément trouvé pour les filtres sélectionnés."
                    : "Importez les PDFs pour voir l'analyse d'éléments détaillée."}
                </p>
              </div>
            </div>
          </div>
        ) : (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Jump success rates */}
            <div>
              <h3 className="text-[10px] font-black uppercase tracking-widest text-on-surface-variant mb-3">
                Taux de réussite des sauts
              </h3>
              <ResponsiveContainer width="100%" height={Math.max(200, mastery!.jumps.length * 32)}>
                <BarChart
                  data={mastery!.jumps}
                  layout="vertical"
                  margin={{ top: 0, right: 40, left: 0, bottom: 0 }}
                >
                  <CartesianGrid horizontal={false} stroke="#e0e3e5" />
                  <XAxis type="number" domain={[0, 100]} tick={{ fontSize: 10 }} axisLine={false} tickLine={false} />
                  <YAxis
                    type="category" dataKey="jump_type" width={40}
                    tick={{ fontSize: 11, fontFamily: "monospace", fill: "#191c1e" }}
                    axisLine={false} tickLine={false}
                  />
                  <Tooltip
                    formatter={(value: number, name: string) => [`${value.toFixed(1)}%`, name]}
                    contentStyle={{ fontSize: 11, borderRadius: 12, border: "none", boxShadow: "0 1px 4px rgba(0,0,0,0.12)" }}
                  />
                  <Bar dataKey="positive_goe_pct" name="GOE +" stackId="goe" fill="#4caf50" />
                  <Bar dataKey="neutral_goe_pct" name="GOE 0" stackId="goe" fill="#ffc107" />
                  <Bar dataKey="negative_goe_pct" name="GOE −" stackId="goe" fill="#f44336" />
                </BarChart>
              </ResponsiveContainer>
            </div>

            {/* Spin/step level distribution */}
            <div>
              <h3 className="text-[10px] font-black uppercase tracking-widest text-on-surface-variant mb-3">
                Niveaux pirouettes et pas
              </h3>
              {(() => {
                const LEVEL_COLORS = ["#e0e0e0", "#b0bec5", "#78909c", "#455a64", "#263238"];
                const combined = [...(mastery!.spins ?? []), ...(mastery!.steps ?? [])];
                const chartData = combined.map((el) => ({
                  name: el.element_type,
                  ...Object.fromEntries(
                    Object.entries(el.level_distribution).map(([k, v]) => [`level_${k}`, v])
                  ),
                  avg_goe: el.avg_goe,
                  attempts: el.attempts,
                }));
                return (
                  <ResponsiveContainer width="100%" height={Math.max(200, chartData.length * 32)}>
                    <BarChart
                      data={chartData}
                      layout="vertical"
                      margin={{ top: 0, right: 40, left: 0, bottom: 0 }}
                    >
                      <CartesianGrid horizontal={false} stroke="#e0e3e5" />
                      <XAxis type="number" tick={{ fontSize: 10 }} axisLine={false} tickLine={false} />
                      <YAxis
                        type="category" dataKey="name" width={60}
                        tick={{ fontSize: 11, fontFamily: "monospace", fill: "#191c1e" }}
                        axisLine={false} tickLine={false}
                      />
                      <Tooltip
                        contentStyle={{ fontSize: 11, borderRadius: 12, border: "none", boxShadow: "0 1px 4px rgba(0,0,0,0.12)" }}
                      />
                      {[0, 1, 2, 3, 4].map((level) => (
                        <Bar
                          key={level}
                          dataKey={`level_${level}`}
                          name={`Niveau ${level}`}
                          stackId="levels"
                          fill={LEVEL_COLORS[level]}
                        />
                      ))}
                    </BarChart>
                  </ResponsiveContainer>
                );
              })()}
            </div>
          </div>
        )}
      </div>
```

- [ ] **Step 2: Verify build**

Run: `cd frontend && PATH="/opt/homebrew/bin:$PATH" npm run build`
Expected: Build succeeds

- [ ] **Step 3: Commit**

```bash
git add frontend/src/pages/StatsPage.tsx
git commit -m "feat: add element mastery section to Club page"
```

---

## Task 12: Run All Backend Tests

**Files:** None (verification only)

- [ ] **Step 1: Run full backend test suite**

Run: `cd backend && PATH="/opt/homebrew/bin:$PATH" uv run pytest -v`
Expected: All tests pass

- [ ] **Step 2: Fix any failures**

If any tests fail, fix the issues and re-run.

- [ ] **Step 3: Final frontend build check**

Run: `cd frontend && PATH="/opt/homebrew/bin:$PATH" npm run build`
Expected: Build succeeds

- [ ] **Step 4: Final commit if any fixes were needed**

```bash
git add -A
git commit -m "fix: resolve test/build issues from integration"
```
