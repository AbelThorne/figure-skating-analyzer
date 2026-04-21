# Programme Builder Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an ephemeral program builder tool that lets coaches construct figure skating programs, see base values and GOE ranges in real time, apply ISU markers, and get automatic category suggestions.

**Architecture:** Two static JSON data files served by simple GET endpoints (no DB model). All calculation and validation logic runs client-side in React. A new `/programme` page with responsive two-column layout (program table + category panel).

**Tech Stack:** Litestar (backend, serving JSON), React + TypeScript + Tailwind CSS (frontend), TanStack Query (data fetching), Material Symbols Outlined (icons).

**Spec:** `docs/superpowers/specs/2026-04-21-program-builder-design.md`

**Reference PDFs (project root):**
- `2707-ISU-SOV-SinglesPairs-2025-26-25-05-01-1747377995-9986.pdf` — SOV base values + GOE tables
- `CNSPA Book 2025-2026 - 20251210.pdf` — Category rules, program requirements
- `TP-Handbook-Pair-Skating-2025-26-25July-1754657063-3208.pdf` — Marker effects, combo/sequence rules
- `reglement PA Occitanie 2025 2026.pdf` — Occitanie Exhibition/Duo rules

---

## File Structure

### Files to create

```
backend/app/
  data/
    sov_2025_2026.json                    # All SOV base values + GOE from ISU Comm 2707
    program_rules_2025_2026.json          # Category rules from CNSPA Book + Occitanie
  routes/
    program_builder.py                    # GET /api/sov, GET /api/program-rules

backend/tests/
  test_program_builder.py                 # Auth + response tests

frontend/src/
  pages/
    ProgramBuilderPage.tsx                # Main page with two-column layout
  components/
    program-builder/
      ElementPicker.tsx                   # Searchable dropdown grouped by type
      ModifierDropdown.tsx                # Marker selector per element/jump
      GoeTooltip.tsx                      # Hover tooltip showing GOE -5…-1 or +1…+5
      ProgramTable.tsx                    # Element list with BV/Min/Max + actions
      CompetitionLoader.tsx               # Load program from existing score
      CategoryPanel.tsx                   # Category suggestion + validation + summary
  hooks/
    useSovData.ts                         # TanStack Query wrapper for SOV
    useProgramRules.ts                    # TanStack Query wrapper for rules
    useProgramBuilder.ts                  # Central state + calculation logic
  utils/
    sov-calculator.ts                     # BV computation, code composition, GOE lookup
    program-validator.ts                  # Validate program against category rules
    category-matcher.ts                   # Match program to best category
```

### Files to modify

```
backend/app/main.py                       # Register program_builder router
frontend/src/api/client.ts                # Add types + api.programBuilder namespace
frontend/src/App.tsx                      # Add nav item + route for /programme
```

---

## Task 1: Backend — SOV Data File

**Files:**
- Create: `backend/app/data/sov_2025_2026.json`

This task creates the complete SOV data file by digitizing all entries from the ISU Communication 2707 PDF. The file contains every element's base value and GOE values (-5 through +5, excluding 0).

- [ ] **Step 1: Create the data directory**

```bash
mkdir -p backend/app/data
```

- [ ] **Step 2: Read the SOV PDF and create the JSON file**

Read pages 1-12 of `2707-ISU-SOV-SinglesPairs-2025-26-25-05-01-1747377995-9986.pdf` in the project root. Extract ALL elements from every table.

Create `backend/app/data/sov_2025_2026.json` with this exact structure:

```json
{
  "season": "2025-2026",
  "elements": {
    "<code>": {
      "category": "single" | "pair",
      "type": "jump" | "spin" | "step" | "choreo" | "lift" | "throw" | "twist" | "death_spiral" | "pair_spin" | "pivot",
      "base_value": <number>,
      "goe": [<-5>, <-4>, <-3>, <-2>, <-1>, <+1>, <+2>, <+3>, <+4>, <+5>]
    }
  }
}
```

**Rules for extraction:**
- The `goe` array has exactly 10 values in order: [-5, -4, -3, -2, -1, +1, +2, +3, +4, +5]
- `category` is `"single"` for singles elements, `"pair"` for pair-specific elements (lifts, throws, twists, death spirals, pair spins, pivot)
- Elements with marker suffixes (`<`, `e`, `e<`) are separate entries with their own base values and GOE values
- Spins with `V` suffix (e.g., `CCoSp3V`) are separate entries
- The `<<` (downgrade) marker does NOT have SOV entries — it's handled by code transformation at runtime

**Element types to extract (all from singles tables):**

| Type | Codes to extract | Notes |
|------|-----------------|-------|
| `jump` | 1T through 4A (and 5T-5Lz if present). Plus variants: `<` suffix for all, `e` suffix for F/Lz only, `e<` for F/Lz only | 1Eu (Euler) is a jump |
| `spin` | USp, LSp, CSp, SSp (levels B,1,2,3,4). CUSp, CLSp, CCSp, CSSp (levels B,1,2,3,4). FUSp, FLSp, FCSp, FSSp (levels B,1,2,3,4). FCUSp, FCLSp, FCCSp, FCSSp (levels B,1,2,3,4). CoSp, CCoSp, FCoSp, FCCoSp (levels B,1,2,3,4). Plus `V` suffix variants for each | Level B = no number suffix |
| `step` | StSqB, StSq1, StSq2, StSq3, StSq4 | |
| `choreo` | ChSq1 | |

**Pair element types to extract (from pairs tables):**

| Type | Codes | Notes |
|------|-------|-------|
| `lift` | All pair lift codes with levels (e.g., 1Li1, 1LiB, etc. through 5RLi4) | |
| `throw` | 1TTh through 4LzTh, plus variants with `<`, `e`, `e<` | |
| `twist` | 1Tw through 4Tw with levels B-4, plus `<` variants | |
| `death_spiral` | BoDsB through FoDs4 (Bo=Back outside, Bi=Back inside, Fo=Front outside, Fi=Front inside, levels B-4) | |
| `pair_spin` | PSpB through PSp4, PCoSpB through PCoSp4 | |
| `pivot` | PiF (levels if applicable) | |

**Example entries (for reference — extract actual values from PDF):**

```json
{
  "1T": { "category": "single", "type": "jump", "base_value": 0.40, "goe": [-0.20, -0.16, -0.12, -0.08, -0.04, 0.04, 0.08, 0.12, 0.16, 0.20] },
  "1T<": { "category": "single", "type": "jump", "base_value": 0.32, "goe": [-0.16, -0.13, -0.10, -0.06, -0.03, 0.03, 0.06, 0.10, 0.13, 0.16] },
  "3Lz": { "category": "single", "type": "jump", "base_value": 5.90, "goe": [-2.95, -2.36, -1.77, -1.18, -0.59, 0.59, 1.18, 1.77, 2.36, 2.95] },
  "3Lze": { "category": "single", "type": "jump", "base_value": 4.72, "goe": [-2.36, -1.89, -1.42, -0.94, -0.47, 0.47, 0.94, 1.42, 1.89, 2.36] },
  "3Lz<": { "category": "single", "type": "jump", "base_value": 4.72, "goe": [-2.36, -1.89, -1.42, -0.94, -0.47, 0.47, 0.94, 1.42, 1.89, 2.36] },
  "3Lze<": { "category": "single", "type": "jump", "base_value": 3.78, "goe": [-1.89, -1.51, -1.13, -0.76, -0.38, 0.38, 0.76, 1.13, 1.51, 1.89] },
  "1Eu": { "category": "single", "type": "jump", "base_value": 0.50, "goe": [-0.25, -0.20, -0.15, -0.10, -0.05, 0.05, 0.10, 0.15, 0.20, 0.25] },
  "FSSp4": { "category": "single", "type": "spin", "base_value": 3.00, "goe": [-1.50, -1.20, -0.90, -0.60, -0.30, 0.30, 0.60, 0.90, 1.20, 1.50] },
  "CCoSp3V": { "category": "single", "type": "spin", "base_value": 2.25, "goe": [-1.13, -0.90, -0.68, -0.45, -0.23, 0.23, 0.45, 0.68, 0.90, 1.13] },
  "StSq3": { "category": "single", "type": "step", "base_value": 3.30, "goe": [-1.65, -1.32, -0.99, -0.66, -0.33, 0.33, 0.66, 0.99, 1.32, 1.65] },
  "ChSq1": { "category": "single", "type": "choreo", "base_value": 3.00, "goe": [-2.50, -2.00, -1.50, -1.00, -0.50, 0.50, 1.00, 1.50, 2.00, 2.50] }
}
```

Write the complete file with ALL entries from the PDF. Verify the total entry count is reasonable (expect 300-500 entries across all element types).

- [ ] **Step 3: Validate the JSON is well-formed**

```bash
cd /Users/julien/projects/figure-skating-analyzer && python3 -c "
import json
with open('backend/app/data/sov_2025_2026.json') as f:
    data = json.load(f)
print(f'Season: {data[\"season\"]}')
print(f'Total elements: {len(data[\"elements\"])}')
types = {}
for code, el in data['elements'].items():
    t = el['type']
    types[t] = types.get(t, 0) + 1
    assert len(el['goe']) == 10, f'{code} has {len(el[\"goe\"])} GOE values, expected 10'
    assert el['category'] in ('single', 'pair'), f'{code} has invalid category {el[\"category\"]}'
for t, count in sorted(types.items()):
    print(f'  {t}: {count}')
print('All validations passed!')
"
```

Expected: no assertion errors, reasonable counts per type.

- [ ] **Step 4: Commit**

```bash
git add backend/app/data/sov_2025_2026.json
git commit -m "feat: add ISU SOV 2025-2026 data file for program builder"
```

---

## Task 2: Backend — Program Rules Data File

**Files:**
- Create: `backend/app/data/program_rules_2025_2026.json`

Create the category rules file by reading the CNSPA Book and Occitanie rules PDFs.

- [ ] **Step 1: Read reference documents**

Read these PDF pages to extract all category rules:
- `CNSPA Book 2025-2026 - 20251210.pdf` — pages 24-39 (programme requirements per category), pages 68-78 (Adulte categories)
- `reglement PA Occitanie 2025 2026.pdf` — pages 1-3 (Exhibition and Duo rules)

- [ ] **Step 2: Create the program rules JSON file**

Create `backend/app/data/program_rules_2025_2026.json` following this structure. Extract the actual values from the PDFs read above.

```json
{
  "season": "2025-2026",
  "categories": {
    "<category_name>": {
      "label": "<display name>",
      "segments": {
        "PC": {
          "label": "Programme Court",
          "duration": "<duration string>",
          "total_elements": <number>,
          "max_jump_elements": <number>,
          "max_spins": <number>,
          "max_steps": <number>,
          "max_choreo": <number>,
          "max_jump_level": <number | null>,
          "max_spin_level": <number | null>,
          "triples_allowed": <boolean>,
          "quads_allowed": <boolean>,
          "axel_required": <boolean>,
          "combo_allowed": <boolean>,
          "max_combo_jumps": <number>,
          "component_factor_m": <number>,
          "component_factor_f": <number>,
          "bonus_second_half": <boolean>
        },
        "PL": {
          "label": "Programme Libre",
          "duration": "<duration string>",
          "max_jump_elements": <number>,
          "max_spins": <number>,
          "max_steps": <number>,
          "max_choreo": <number>,
          "max_jump_level": <number | null>,
          "max_spin_level": <number | null>,
          "triples_allowed": <boolean>,
          "quads_allowed": <boolean>,
          "max_combos": <number>,
          "max_sequences": <number>,
          "max_combo_with_3_jumps": <number>,
          "component_factor_m": <number>,
          "component_factor_f": <number>,
          "bonus_second_half": <boolean>
        }
      }
    }
  }
}
```

**Categories to include** (from CNSPA Book + Occitanie rules):

| Category | Source | Key constraints |
|----------|--------|-----------------|
| ISU Senior | CNSPA Book | PC (7 elements) + PL (max 7 jumps, 3 combos, quads allowed) |
| ISU Junior | CNSPA Book | PC (7 elements) + PL (max 7 jumps, 3 combos, max triple) |
| ISU Advanced Novice | CNSPA Book | PC (6 elements, max triple) + PL (max 6 jumps, max triple) |
| ISU Intermediate Novice | CNSPA Book | PL only (max 5 jumps, max double) |
| ISU Basic Novice | CNSPA Book | PL only (max 5 jumps, max double) |
| Régional 3 - Niveau C | CNSPA Book | PL only (2 jumps from 1S/1T/1Lo, no combos, 1 spin USp only) |
| Régional 3 - Niveau B | CNSPA Book | PL only (2 jumps from 1S/1T/1Lo, no combos, 2 spins) |
| Régional 3 - Niveau A | CNSPA Book | PL only (4 jumps from singles, 2 combos, 2 spins) |
| Adulte Master Élite | CNSPA Book | PL (full program, triples allowed) |
| Adulte Or | CNSPA Book | PL (limited jumps, max double) |
| Adulte Argent | CNSPA Book | PL (limited jumps, max single axel) |
| Adulte Bronze | CNSPA Book | PL (limited jumps, max single) |
| Occitanie Exhibition | Occitanie PDF | PL (1 jump, 2 spins, 1 step, level max 1) |
| Occitanie Duo | Occitanie PDF | PL (2 jumps, 2 spins, 1 step, level max 1, duo element) |

For fields not applicable to a segment, omit them (the frontend handles missing fields as "no constraint").

- [ ] **Step 3: Validate the JSON**

```bash
cd /Users/julien/projects/figure-skating-analyzer && python3 -c "
import json
with open('backend/app/data/program_rules_2025_2026.json') as f:
    data = json.load(f)
print(f'Season: {data[\"season\"]}')
cats = data['categories']
print(f'Categories: {len(cats)}')
for name, cat in cats.items():
    segs = list(cat['segments'].keys())
    print(f'  {name}: segments={segs}')
print('Valid JSON!')
"
```

- [ ] **Step 4: Commit**

```bash
git add backend/app/data/program_rules_2025_2026.json
git commit -m "feat: add program rules 2025-2026 data file for category matching"
```

---

## Task 3: Backend — API Route + Tests (TDD)

**Files:**
- Create: `backend/tests/test_program_builder.py`
- Create: `backend/app/routes/program_builder.py`
- Modify: `backend/app/main.py`

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_program_builder.py`:

```python
import pytest
from app.auth.tokens import create_access_token


@pytest.fixture
async def coach_user(db_session):
    from app.models.user import User
    from app.auth.passwords import hash_password

    user = User(
        email="coach@test.com",
        password_hash=hash_password("coachpass1"),
        display_name="Test Coach",
        role="coach",
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest.fixture
async def coach_token(coach_user) -> str:
    return create_access_token(user_id=coach_user.id, role=coach_user.role)


@pytest.fixture
async def admin_user(db_session):
    from app.models.user import User
    from app.auth.passwords import hash_password

    user = User(
        email="admin@test.com",
        password_hash=hash_password("adminpass1"),
        display_name="Test Admin",
        role="admin",
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest.fixture
async def admin_token(admin_user) -> str:
    return create_access_token(user_id=admin_user.id, role=admin_user.role)


@pytest.fixture
async def reader_user(db_session):
    from app.models.user import User
    from app.auth.passwords import hash_password

    user = User(
        email="reader@test.com",
        password_hash=hash_password("readerpass1"),
        display_name="Test Reader",
        role="reader",
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest.fixture
async def reader_token(reader_user) -> str:
    return create_access_token(user_id=reader_user.id, role=reader_user.role)


@pytest.fixture
async def skater_user(db_session):
    from app.models.user import User
    from app.auth.passwords import hash_password

    user = User(
        email="skater@test.com",
        password_hash=hash_password("skaterpass1"),
        display_name="Test Skater",
        role="skater",
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest.fixture
async def skater_token(skater_user) -> str:
    return create_access_token(user_id=skater_user.id, role=skater_user.role)


# ── GET /api/program-builder/sov ─────────────────────────────────────────


async def test_get_sov_as_coach(client, coach_token):
    resp = await client.get(
        "/api/program-builder/sov",
        headers={"Authorization": f"Bearer {coach_token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["season"] == "2025-2026"
    assert "elements" in data
    assert "3Lz" in data["elements"]
    el = data["elements"]["3Lz"]
    assert el["type"] == "jump"
    assert el["category"] == "single"
    assert isinstance(el["base_value"], (int, float))
    assert len(el["goe"]) == 10


async def test_get_sov_as_admin(client, admin_token):
    resp = await client.get(
        "/api/program-builder/sov",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    assert "elements" in resp.json()


async def test_get_sov_rejected_for_reader(client, reader_token):
    resp = await client.get(
        "/api/program-builder/sov",
        headers={"Authorization": f"Bearer {reader_token}"},
    )
    assert resp.status_code == 403


async def test_get_sov_rejected_for_skater(client, skater_token):
    resp = await client.get(
        "/api/program-builder/sov",
        headers={"Authorization": f"Bearer {skater_token}"},
    )
    assert resp.status_code == 403


async def test_get_sov_rejected_unauthenticated(client):
    resp = await client.get("/api/program-builder/sov")
    assert resp.status_code == 401


# ── GET /api/program-builder/rules ───────────────────────────────────────


async def test_get_rules_as_coach(client, coach_token):
    resp = await client.get(
        "/api/program-builder/rules",
        headers={"Authorization": f"Bearer {coach_token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["season"] == "2025-2026"
    assert "categories" in data
    assert len(data["categories"]) >= 10


async def test_get_rules_as_admin(client, admin_token):
    resp = await client.get(
        "/api/program-builder/rules",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    assert "categories" in resp.json()


async def test_get_rules_rejected_for_reader(client, reader_token):
    resp = await client.get(
        "/api/program-builder/rules",
        headers={"Authorization": f"Bearer {reader_token}"},
    )
    assert resp.status_code == 403


async def test_get_rules_rejected_for_skater(client, skater_token):
    resp = await client.get(
        "/api/program-builder/rules",
        headers={"Authorization": f"Bearer {skater_token}"},
    )
    assert resp.status_code == 403
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /Users/julien/projects/figure-skating-analyzer/backend && PATH="/opt/homebrew/bin:$PATH" uv run pytest tests/test_program_builder.py -v
```

Expected: FAIL (route not found, 404 errors).

- [ ] **Step 3: Create the route handler**

Create `backend/app/routes/program_builder.py`:

```python
from __future__ import annotations

import json
from pathlib import Path

from litestar import Router, get, Request

from app.auth.guards import require_coach_or_admin
from app.database import get_session
from litestar.di import Provide

_DATA_DIR = Path(__file__).resolve().parent.parent / "data"

_sov_cache: dict | None = None
_rules_cache: dict | None = None


def _load_sov() -> dict:
    global _sov_cache
    if _sov_cache is None:
        with open(_DATA_DIR / "sov_2025_2026.json") as f:
            _sov_cache = json.load(f)
    return _sov_cache


def _load_rules() -> dict:
    global _rules_cache
    if _rules_cache is None:
        with open(_DATA_DIR / "program_rules_2025_2026.json") as f:
            _rules_cache = json.load(f)
    return _rules_cache


@get("/sov")
async def get_sov(request: Request) -> dict:
    require_coach_or_admin(request)
    return _load_sov()


@get("/rules")
async def get_rules(request: Request) -> dict:
    require_coach_or_admin(request)
    return _load_rules()


router = Router(
    path="/api/program-builder",
    route_handlers=[get_sov, get_rules],
)
```

- [ ] **Step 4: Register the router in main.py**

In `backend/app/main.py`, add the import and register the router.

Add this import after the existing route imports (after `from app.routes.team_scores import router as team_scores_router`):

```python
from app.routes.program_builder import router as program_builder_router
```

Add `program_builder_router` to the `route_handlers` list in the `Litestar()` constructor, after `team_scores_router`.

- [ ] **Step 5: Run tests to verify they pass**

```bash
cd /Users/julien/projects/figure-skating-analyzer/backend && PATH="/opt/homebrew/bin:$PATH" uv run pytest tests/test_program_builder.py -v
```

Expected: all 9 tests PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/app/routes/program_builder.py backend/tests/test_program_builder.py backend/app/main.py
git commit -m "feat: add program builder API endpoints (GET /api/program-builder/sov, /rules)"
```

---

## Task 4: Frontend — API Types and Data Hooks

**Files:**
- Modify: `frontend/src/api/client.ts`
- Create: `frontend/src/hooks/useSovData.ts`
- Create: `frontend/src/hooks/useProgramRules.ts`

- [ ] **Step 1: Add types to client.ts**

In `frontend/src/api/client.ts`, add these type definitions after the existing `TimelineEntry` interface (before the `export const api = {` line):

```typescript
// ── Program Builder types ───────────────────────────────────────────────

export interface SovElement {
  category: "single" | "pair";
  type: "jump" | "spin" | "step" | "choreo" | "lift" | "throw" | "twist" | "death_spiral" | "pair_spin" | "pivot";
  base_value: number;
  goe: number[]; // 10 values: [-5, -4, -3, -2, -1, +1, +2, +3, +4, +5]
}

export interface SovData {
  season: string;
  elements: Record<string, SovElement>;
}

export interface ProgramRuleSegment {
  label?: string;
  duration?: string;
  total_elements?: number;
  max_jump_elements?: number;
  max_spins?: number;
  max_steps?: number;
  max_choreo?: number;
  max_jump_level?: number | null;
  max_spin_level?: number | null;
  max_step_level?: number | null;
  triples_allowed?: boolean;
  quads_allowed?: boolean;
  combo_allowed?: boolean;
  max_combos?: number;
  max_combo_jumps?: number;
  max_sequences?: number;
  max_combo_with_3_jumps?: number;
  allowed_jumps?: string[];
  allowed_spin_types?: string[];
  bonus_second_half?: boolean;
  component_factor?: number;
  component_factor_m?: number;
  component_factor_f?: number;
  has_duo_element?: boolean;
  notes?: string;
}

export interface ProgramRuleCategory {
  label: string;
  segments: Record<string, ProgramRuleSegment>;
}

export interface ProgramRulesData {
  season: string;
  categories: Record<string, ProgramRuleCategory>;
}
```

- [ ] **Step 2: Add api.programBuilder namespace**

In `frontend/src/api/client.ts`, add this namespace inside the `api` object, after the `training` namespace (before the closing `};`):

```typescript
  programBuilder: {
    sov: () => request<SovData>("/program-builder/sov"),
    rules: () => request<ProgramRulesData>("/program-builder/rules"),
  },
```

- [ ] **Step 3: Create useSovData hook**

Create `frontend/src/hooks/useSovData.ts`:

```typescript
import { useQuery } from "@tanstack/react-query";
import { api, SovData } from "../api/client";

export function useSovData() {
  return useQuery<SovData>({
    queryKey: ["program-builder", "sov"],
    queryFn: api.programBuilder.sov,
    staleTime: Infinity,
  });
}
```

- [ ] **Step 4: Create useProgramRules hook**

Create `frontend/src/hooks/useProgramRules.ts`:

```typescript
import { useQuery } from "@tanstack/react-query";
import { api, ProgramRulesData } from "../api/client";

export function useProgramRules() {
  return useQuery<ProgramRulesData>({
    queryKey: ["program-builder", "rules"],
    queryFn: api.programBuilder.rules,
    staleTime: Infinity,
  });
}
```

- [ ] **Step 5: Commit**

```bash
git add frontend/src/api/client.ts frontend/src/hooks/useSovData.ts frontend/src/hooks/useProgramRules.ts
git commit -m "feat: add program builder API types and data hooks"
```

---

## Task 5: Frontend — SOV Calculator Utility

**Files:**
- Create: `frontend/src/utils/sov-calculator.ts`

This utility handles all base value and GOE calculations: composing element codes from markers, looking up BV in the SOV, applying multiplicators (`x`, `+REP`, `*`), and computing min/max scores.

- [ ] **Step 1: Create the SOV calculator**

Create `frontend/src/utils/sov-calculator.ts`:

```typescript
import type { SovData, SovElement } from "../api/client";

/** Markers that require a dedicated SOV entry (suffixed to the code). */
const SOV_SUFFIX_MARKERS = ["e", "<"] as const;

/** Jump rotation number extracted from code (e.g., "3" from "3Lz"). */
function getJumpRotation(code: string): number | null {
  const m = code.match(/^(\d)/);
  return m ? parseInt(m[1], 10) : null;
}

/** Downgrade a jump code by reducing rotation by 1 (e.g., "3Lz" → "2Lz", "2A" → "1A"). */
function downgradeCode(code: string): string | null {
  const rotation = getJumpRotation(code);
  if (rotation == null || rotation <= 1) return null;
  return code.replace(/^\d/, String(rotation - 1));
}

/**
 * Compose the SOV lookup code from a base element code and its active markers.
 *
 * - Markers `e` and `<` add suffixes to the code (order: `e` then `<`).
 * - Marker `<<` transforms the code to rotation-1 (then any `e` suffix is applied).
 * - Marker `V` adds `V` suffix (spins only — e.g., CCoSp3 → CCoSp3V).
 * - Markers `q`, `!`, `*`, `x`, `+REP` do NOT affect the SOV lookup code.
 *
 * Returns null if the composed code doesn't exist in the SOV (e.g., downgrading a 1T).
 */
export function composeSovCode(baseCode: string, markers: string[]): string | null {
  const hasDowngrade = markers.includes("<<");
  const hasEdge = markers.includes("e");
  const hasUnderRotation = markers.includes("<");
  const hasV = markers.includes("V");

  let code = baseCode;

  if (hasDowngrade) {
    const downgraded = downgradeCode(code);
    if (!downgraded) return null;
    code = downgraded;
  }

  // Build suffix: V for spins, edge then under-rotation for jumps
  if (hasV) code += "V";
  if (hasEdge) code += "e";
  if (hasUnderRotation && !hasDowngrade) code += "<";

  return code;
}

/**
 * Look up a SOV element by its composed code.
 */
export function lookupSov(sov: SovData, code: string): SovElement | null {
  return sov.elements[code] ?? null;
}

/**
 * Calculate the effective base value for a single element (not a combo).
 *
 * @param sov - The SOV data
 * @param baseCode - The original element code (e.g., "3Lz")
 * @param markers - Active markers on this element
 * @returns The computed BV, or 0 if the element is nullified or not found
 */
export function calculateElementBV(
  sov: SovData,
  baseCode: string,
  markers: string[],
): number {
  // * marker = nullified, BV is 0
  if (markers.includes("*")) return 0;

  const sovCode = composeSovCode(baseCode, markers);
  if (!sovCode) return 0;

  const element = lookupSov(sov, sovCode);
  if (!element) return 0;

  let bv = element.base_value;

  // Apply multiplicators
  if (markers.includes("x")) bv *= 1.10;
  if (markers.includes("+REP")) bv *= 0.70;

  return Math.round(bv * 100) / 100;
}

/**
 * Get the GOE array for an element after marker application.
 * Returns the GOE values from the SOV entry matching the composed code.
 */
export function getElementGoe(
  sov: SovData,
  baseCode: string,
  markers: string[],
): number[] | null {
  if (markers.includes("*")) return null;

  const sovCode = composeSovCode(baseCode, markers);
  if (!sovCode) return null;

  const element = lookupSov(sov, sovCode);
  return element?.goe ?? null;
}

/**
 * A single jump within a combo/sequence, with its own code and markers.
 */
export interface ComboJump {
  code: string;
  markers: string[];
}

/**
 * Calculate base value for a combo/sequence.
 * Sum of individual jump BVs (after per-jump markers), then apply combo-level multiplicators.
 *
 * @param comboMarkers - Markers that apply to the combo as a whole (x, +REP)
 */
export function calculateComboBV(
  sov: SovData,
  jumps: ComboJump[],
  comboMarkers: string[],
): number {
  if (comboMarkers.includes("*")) return 0;

  let totalBV = 0;
  for (const jump of jumps) {
    // Per-jump markers affect individual BV (but not x/+REP which are combo-level)
    const jumpMarkersForBV = jump.markers.filter(m => !["x", "+REP"].includes(m));
    const bv = calculateElementBV(sov, jump.code, jumpMarkersForBV);
    totalBV += bv;
  }

  // Apply combo-level multiplicators
  if (comboMarkers.includes("x")) totalBV *= 1.10;
  if (comboMarkers.includes("+REP")) totalBV *= 0.70;

  return Math.round(totalBV * 100) / 100;
}

/**
 * Calculate min score (BV + GOE at -5) for a single element.
 */
export function calculateElementMin(
  sov: SovData,
  baseCode: string,
  markers: string[],
): number {
  const bv = calculateElementBV(sov, baseCode, markers);
  const goe = getElementGoe(sov, baseCode, markers);
  if (!goe) return bv;
  return Math.round((bv + goe[0]) * 100) / 100; // goe[0] = GOE at -5
}

/**
 * Calculate max score (BV + GOE at +5) for a single element.
 */
export function calculateElementMax(
  sov: SovData,
  baseCode: string,
  markers: string[],
): number {
  const bv = calculateElementBV(sov, baseCode, markers);
  const goe = getElementGoe(sov, baseCode, markers);
  if (!goe) return bv;
  return Math.round((bv + goe[9]) * 100) / 100; // goe[9] = GOE at +5
}

/**
 * Get full GOE breakdown for hover tooltips.
 * Returns array of { level, value } for either negative (-5 to -1) or positive (+1 to +5).
 */
export function getGoeBreakdown(
  sov: SovData,
  baseCode: string,
  markers: string[],
  side: "negative" | "positive",
): { level: number; value: number }[] | null {
  const goe = getElementGoe(sov, baseCode, markers);
  if (!goe) return null;

  const bv = calculateElementBV(sov, baseCode, markers);

  if (side === "negative") {
    return [
      { level: -5, value: Math.round((bv + goe[0]) * 100) / 100 },
      { level: -4, value: Math.round((bv + goe[1]) * 100) / 100 },
      { level: -3, value: Math.round((bv + goe[2]) * 100) / 100 },
      { level: -2, value: Math.round((bv + goe[3]) * 100) / 100 },
      { level: -1, value: Math.round((bv + goe[4]) * 100) / 100 },
    ];
  }

  return [
    { level: +1, value: Math.round((bv + goe[5]) * 100) / 100 },
    { level: +2, value: Math.round((bv + goe[6]) * 100) / 100 },
    { level: +3, value: Math.round((bv + goe[7]) * 100) / 100 },
    { level: +4, value: Math.round((bv + goe[8]) * 100) / 100 },
    { level: +5, value: Math.round((bv + goe[9]) * 100) / 100 },
  ];
}

/**
 * Check if an element code represents a jump (for combo/modifier logic).
 */
export function isJump(sov: SovData, code: string): boolean {
  const el = sov.elements[code];
  return el?.type === "jump";
}

/**
 * Check if an element code is a Flip or Lutz (for edge marker compatibility).
 */
export function isFlipOrLutz(code: string): boolean {
  return /\d[FL](?:lz|$)/i.test(code) || code.endsWith("F") || code.endsWith("Lz");
}

/**
 * Check if an element code is an Axel type.
 */
export function isAxel(code: string): boolean {
  return /\dA$/.test(code) || code === "1Eu";
}

/**
 * Get the available base element codes (without marker variants) from SOV,
 * optionally filtered by category.
 */
export function getBaseElements(
  sov: SovData,
  includePairs: boolean,
): Record<string, string[]> {
  const groups: Record<string, string[]> = {};

  for (const [code, el] of Object.entries(sov.elements)) {
    // Skip marker variants (codes containing <, e suffix, V suffix for spins)
    if (code.includes("<") || /e$/.test(code) || /V$/.test(code)) continue;
    // Skip pair elements if not included
    if (!includePairs && el.category === "pair") continue;

    const type = el.type;
    if (!groups[type]) groups[type] = [];
    groups[type].push(code);
  }

  // Sort each group
  for (const codes of Object.values(groups)) {
    codes.sort((a, b) => {
      const aRot = parseInt(a) || 0;
      const bRot = parseInt(b) || 0;
      if (aRot !== bRot) return aRot - bRot;
      return a.localeCompare(b);
    });
  }

  return groups;
}
```

- [ ] **Step 2: Verify TypeScript compiles**

```bash
cd /Users/julien/projects/figure-skating-analyzer/frontend && PATH="/opt/homebrew/bin:$PATH" npx tsc --noEmit --pretty 2>&1 | head -30
```

Expected: no errors in `sov-calculator.ts`.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/utils/sov-calculator.ts
git commit -m "feat: add SOV calculator utility for BV/GOE computation"
```

---

## Task 6: Frontend — Program Validator Utility

**Files:**
- Create: `frontend/src/utils/program-validator.ts`

- [ ] **Step 1: Create the program validator**

Create `frontend/src/utils/program-validator.ts`:

```typescript
import type { ProgramRuleSegment } from "../api/client";

/**
 * A program element as stored in the builder state.
 */
export interface ProgramElement {
  id: string; // unique ID for React keys
  baseCode: string; // original code without markers (e.g., "3Lz")
  type: "jump" | "spin" | "step" | "choreo" | "lift" | "throw" | "twist" | "death_spiral" | "pair_spin" | "pivot";
  markers: string[]; // active markers on this element
  // For combos: array of jumps with individual markers
  comboJumps?: { code: string; markers: string[] }[];
  bv: number;
  min: number;
  max: number;
}

export interface ValidationResult {
  rule: string;
  label: string;
  status: "ok" | "warning" | "error";
  detail: string;
}

/**
 * Extract the jump rotation from a code (e.g., 3 from "3Lz").
 */
function jumpRotation(code: string): number {
  const m = code.match(/^(\d)/);
  return m ? parseInt(m[1], 10) : 0;
}

/**
 * Check if a jump code is a triple (rotation 3).
 */
function isTriple(code: string): boolean {
  return jumpRotation(code) === 3;
}

/**
 * Check if a jump code is a quad (rotation 4+).
 */
function isQuad(code: string): boolean {
  return jumpRotation(code) >= 4;
}

/**
 * Validate a program against a specific category segment's rules.
 * Returns a list of validation results (pass, warning, or violation).
 */
export function validateProgram(
  elements: ProgramElement[],
  rules: ProgramRuleSegment,
): ValidationResult[] {
  const results: ValidationResult[] = [];

  // Count elements by type
  const jumpElements = elements.filter(e => e.type === "jump");
  const spinElements = elements.filter(e => e.type === "spin" || e.type === "pair_spin");
  const stepElements = elements.filter(e => e.type === "step");
  const choreoElements = elements.filter(e => e.type === "choreo");
  const combos = elements.filter(e => e.comboJumps && e.comboJumps.length > 1);

  // Collect all individual jumps (including from combos)
  const allJumpCodes: string[] = [];
  for (const el of jumpElements) {
    if (el.comboJumps && el.comboJumps.length > 1) {
      for (const j of el.comboJumps) allJumpCodes.push(j.code);
    } else {
      allJumpCodes.push(el.baseCode);
    }
  }

  // Max jump elements
  if (rules.max_jump_elements != null) {
    const count = jumpElements.length;
    const max = rules.max_jump_elements;
    results.push({
      rule: "max_jump_elements",
      label: "Éléments sauts",
      status: count > max ? "error" : "ok",
      detail: `${count}/${max}`,
    });
  }

  // Max spins
  if (rules.max_spins != null) {
    const count = spinElements.length;
    const max = rules.max_spins;
    results.push({
      rule: "max_spins",
      label: "Pirouettes",
      status: count > max ? "error" : "ok",
      detail: `${count}/${max}`,
    });
  }

  // Max steps
  if (rules.max_steps != null) {
    const count = stepElements.length;
    const max = rules.max_steps;
    results.push({
      rule: "max_steps",
      label: "Pas",
      status: count > max ? "error" : "ok",
      detail: `${count}/${max}`,
    });
  }

  // Max choreo
  if (rules.max_choreo != null) {
    const count = choreoElements.length;
    const max = rules.max_choreo;
    results.push({
      rule: "max_choreo",
      label: "Chorégraphique",
      status: count > max ? "error" : "ok",
      detail: `${count}/${max}`,
    });
  }

  // Triples allowed
  if (rules.triples_allowed === false) {
    const hasTriple = allJumpCodes.some(isTriple);
    results.push({
      rule: "triples_allowed",
      label: "Triples",
      status: hasTriple ? "error" : "ok",
      detail: hasTriple ? "Triples présents — interdit" : "Aucun triple",
    });
  }

  // Quads allowed
  if (rules.quads_allowed === false) {
    const hasQuad = allJumpCodes.some(isQuad);
    results.push({
      rule: "quads_allowed",
      label: "Quadruples",
      status: hasQuad ? "error" : "ok",
      detail: hasQuad ? "Quadruples présents — interdit" : "Aucun quadruple",
    });
  }

  // Max jump level (rotation)
  if (rules.max_jump_level != null) {
    const maxRot = Math.max(0, ...allJumpCodes.map(jumpRotation));
    const allowed = rules.max_jump_level;
    results.push({
      rule: "max_jump_level",
      label: "Niveau max sauts",
      status: maxRot > allowed ? "error" : "ok",
      detail: maxRot > allowed
        ? `Rotation ${maxRot} — max autorisé : ${allowed}`
        : `Max ${maxRot}/${allowed}`,
    });
  }

  // Max spin level
  if (rules.max_spin_level != null) {
    const spinLevels = spinElements.map(e => {
      const m = e.baseCode.match(/(\d)V?$/);
      return m ? parseInt(m[1], 10) : 0;
    });
    const maxLevel = Math.max(0, ...spinLevels);
    const allowed = rules.max_spin_level;
    results.push({
      rule: "max_spin_level",
      label: "Niveau max pirouettes",
      status: maxLevel > allowed ? "error" : "ok",
      detail: `Niveau ${maxLevel}/${allowed}`,
    });
  }

  // Allowed jumps (for Régional 3)
  if (rules.allowed_jumps) {
    const forbidden = allJumpCodes.filter(c => !rules.allowed_jumps!.includes(c));
    results.push({
      rule: "allowed_jumps",
      label: "Sauts autorisés",
      status: forbidden.length > 0 ? "error" : "ok",
      detail: forbidden.length > 0
        ? `Non autorisés : ${forbidden.join(", ")}`
        : `Tous autorisés (${rules.allowed_jumps.join(", ")})`,
    });
  }

  // Allowed spin types (for Régional 3)
  if (rules.allowed_spin_types) {
    const spinBaseCodes = spinElements.map(e => e.baseCode.replace(/[BV\d]+$/, ""));
    const forbidden = spinBaseCodes.filter(c => !rules.allowed_spin_types!.includes(c));
    results.push({
      rule: "allowed_spin_types",
      label: "Types pirouettes",
      status: forbidden.length > 0 ? "error" : "ok",
      detail: forbidden.length > 0
        ? `Non autorisés : ${forbidden.join(", ")}`
        : "Tous autorisés",
    });
  }

  // Combo rules
  if (rules.combo_allowed === false && combos.length > 0) {
    results.push({
      rule: "combo_allowed",
      label: "Combinaisons",
      status: "error",
      detail: "Combinaisons interdites pour cette catégorie",
    });
  } else if (rules.max_combos != null) {
    results.push({
      rule: "max_combos",
      label: "Combinaisons",
      status: combos.length > rules.max_combos ? "error" : "ok",
      detail: `${combos.length}/${rules.max_combos}`,
    });
  }

  // Axel required (for PC)
  if (rules.axel_required) {
    const hasAxel = allJumpCodes.some(c => /\dA$/.test(c));
    results.push({
      rule: "axel_required",
      label: "Axel requis",
      status: hasAxel ? "ok" : "warning",
      detail: hasAxel ? "Axel présent" : "Pas d'Axel (requis en PC)",
    });
  }

  // Total elements
  if (rules.total_elements != null) {
    const total = elements.length;
    const max = rules.total_elements;
    results.push({
      rule: "total_elements",
      label: "Total éléments",
      status: total > max ? "error" : "ok",
      detail: `${total}/${max}`,
    });
  }

  return results;
}

/**
 * Count violations (error status) in validation results.
 */
export function countViolations(results: ValidationResult[]): number {
  return results.filter(r => r.status === "error").length;
}
```

- [ ] **Step 2: Verify TypeScript compiles**

```bash
cd /Users/julien/projects/figure-skating-analyzer/frontend && PATH="/opt/homebrew/bin:$PATH" npx tsc --noEmit --pretty 2>&1 | head -30
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/utils/program-validator.ts
git commit -m "feat: add program validator utility for structural rule checking"
```

---

## Task 7: Frontend — Category Matcher Utility

**Files:**
- Create: `frontend/src/utils/category-matcher.ts`

- [ ] **Step 1: Create the category matcher**

Create `frontend/src/utils/category-matcher.ts`:

```typescript
import type { ProgramRulesData } from "../api/client";
import type { ProgramElement, ValidationResult } from "./program-validator";
import { validateProgram, countViolations } from "./program-validator";

export interface CategoryMatch {
  categoryName: string;
  categoryLabel: string;
  segmentKey: string;
  segmentLabel: string;
  violations: number;
  results: ValidationResult[];
}

/**
 * Match a program against all categories and segments, returning them sorted
 * by number of violations (ascending). Categories with 0 violations are "compatible".
 */
export function matchCategories(
  elements: ProgramElement[],
  rulesData: ProgramRulesData,
): CategoryMatch[] {
  const matches: CategoryMatch[] = [];

  for (const [catName, cat] of Object.entries(rulesData.categories)) {
    for (const [segKey, seg] of Object.entries(cat.segments)) {
      const results = validateProgram(elements, seg);
      matches.push({
        categoryName: catName,
        categoryLabel: cat.label,
        segmentKey: segKey,
        segmentLabel: seg.label ?? segKey,
        violations: countViolations(results),
        results,
      });
    }
  }

  // Sort: compatible first (0 violations), then by violations ascending
  // Among compatible categories, sort by restrictiveness (more rules = more restrictive)
  matches.sort((a, b) => {
    if (a.violations !== b.violations) return a.violations - b.violations;
    // More validation results = more restrictive = show first
    return b.results.length - a.results.length;
  });

  return matches;
}

/**
 * Get the best matching category (fewest violations, most restrictive among ties).
 */
export function getBestMatch(matches: CategoryMatch[]): CategoryMatch | null {
  return matches.length > 0 ? matches[0] : null;
}

/**
 * Get all compatible categories (0 violations).
 */
export function getCompatibleCategories(matches: CategoryMatch[]): CategoryMatch[] {
  return matches.filter(m => m.violations === 0);
}
```

- [ ] **Step 2: Verify TypeScript compiles**

```bash
cd /Users/julien/projects/figure-skating-analyzer/frontend && PATH="/opt/homebrew/bin:$PATH" npx tsc --noEmit --pretty 2>&1 | head -30
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/utils/category-matcher.ts
git commit -m "feat: add category matcher utility for automatic category suggestion"
```

---

## Task 8: Frontend — ElementPicker Component

**Files:**
- Create: `frontend/src/components/program-builder/ElementPicker.tsx`

This component is a searchable dropdown grouped by element type. Used both for adding new elements and for inline editing (popover replacement).

- [ ] **Step 1: Create the ElementPicker component**

Create `frontend/src/components/program-builder/ElementPicker.tsx`:

```typescript
import { useState, useRef, useEffect } from "react";
import type { SovData } from "../../api/client";
import { getBaseElements } from "../../utils/sov-calculator";

const TYPE_LABELS: Record<string, string> = {
  jump: "Sauts",
  spin: "Pirouettes",
  step: "Pas",
  choreo: "Chorégraphique",
  lift: "Portés",
  throw: "Jetés",
  twist: "Twist lifts",
  death_spiral: "Spirales de la mort",
  pair_spin: "Pirouettes couple",
  pivot: "Pivot",
};

const TYPE_ORDER = [
  "jump", "spin", "step", "choreo",
  "lift", "throw", "twist", "death_spiral", "pair_spin", "pivot",
];

interface Props {
  sov: SovData;
  includePairs: boolean;
  onSelect: (code: string) => void;
  /** If true, only show jumps (for combo add). */
  jumpsOnly?: boolean;
  /** Placeholder text. */
  placeholder?: string;
}

export default function ElementPicker({
  sov,
  includePairs,
  onSelect,
  jumpsOnly = false,
  placeholder = "Rechercher un élément...",
}: Props) {
  const [search, setSearch] = useState("");
  const [isOpen, setIsOpen] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  const allGroups = getBaseElements(sov, includePairs);

  // Filter groups by search and jumpsOnly
  const filteredGroups: Record<string, string[]> = {};
  const searchLower = search.toLowerCase();

  for (const type of TYPE_ORDER) {
    if (jumpsOnly && type !== "jump") continue;
    const codes = allGroups[type];
    if (!codes) continue;

    const filtered = codes.filter(code =>
      code.toLowerCase().includes(searchLower),
    );
    if (filtered.length > 0) {
      filteredGroups[type] = filtered;
    }
  }

  // Close on outside click
  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setIsOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, []);

  function handleSelect(code: string) {
    onSelect(code);
    setSearch("");
    setIsOpen(false);
  }

  return (
    <div ref={containerRef} className="relative">
      <input
        ref={inputRef}
        type="text"
        value={search}
        placeholder={placeholder}
        onChange={e => {
          setSearch(e.target.value);
          setIsOpen(true);
        }}
        onFocus={() => setIsOpen(true)}
        className="w-full px-3 py-2 rounded-lg bg-surface-container-low text-on-surface text-sm placeholder:text-on-surface-variant/50 focus:outline-none focus:ring-2 focus:ring-primary/30"
      />

      {isOpen && Object.keys(filteredGroups).length > 0 && (
        <div className="absolute z-50 mt-1 w-full max-h-64 overflow-y-auto rounded-xl bg-surface-container-lowest shadow-lg border border-outline-variant/20">
          {Object.entries(filteredGroups).map(([type, codes]) => (
            <div key={type}>
              <div className="px-3 py-1.5 text-[10px] font-black uppercase tracking-widest text-on-surface-variant bg-surface-container-low/50 sticky top-0">
                {TYPE_LABELS[type] ?? type}
              </div>
              {codes.map(code => (
                <button
                  key={code}
                  onClick={() => handleSelect(code)}
                  className="w-full text-left px-3 py-1.5 text-sm font-mono hover:bg-surface-container transition-colors"
                >
                  {code}
                  <span className="ml-2 text-xs text-on-surface-variant">
                    {sov.elements[code]?.base_value.toFixed(2)}
                  </span>
                </button>
              ))}
            </div>
          ))}
        </div>
      )}

      {isOpen && Object.keys(filteredGroups).length === 0 && search && (
        <div className="absolute z-50 mt-1 w-full rounded-xl bg-surface-container-lowest shadow-lg border border-outline-variant/20 p-3 text-sm text-on-surface-variant">
          Aucun élément trouvé
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Verify TypeScript compiles**

```bash
cd /Users/julien/projects/figure-skating-analyzer/frontend && PATH="/opt/homebrew/bin:$PATH" npx tsc --noEmit --pretty 2>&1 | head -30
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/program-builder/ElementPicker.tsx
git commit -m "feat: add ElementPicker component with searchable grouped dropdown"
```

---

## Task 9: Frontend — ModifierDropdown and GoeTooltip Components

**Files:**
- Create: `frontend/src/components/program-builder/ModifierDropdown.tsx`
- Create: `frontend/src/components/program-builder/GoeTooltip.tsx`

- [ ] **Step 1: Create the ModifierDropdown component**

Create `frontend/src/components/program-builder/ModifierDropdown.tsx`:

```typescript
import { isFlipOrLutz } from "../../utils/sov-calculator";

/** Marker definitions with labels, exclusion groups, and compatibility. */
interface MarkerDef {
  value: string;
  label: string;
  group?: string; // Markers in the same group are mutually exclusive
  flipLutzOnly?: boolean;
}

const JUMP_MARKERS: MarkerDef[] = [
  { value: "q", label: "q", group: "rotation" },
  { value: "<", label: "<", group: "rotation" },
  { value: "<<", label: "<<", group: "rotation" },
  { value: "e", label: "e", group: "edge", flipLutzOnly: true },
  { value: "!", label: "!", group: "edge", flipLutzOnly: true },
  { value: "*", label: "*" },
  { value: "x", label: "x" },
  { value: "+REP", label: "+REP" },
];

const SPIN_MARKERS: MarkerDef[] = [
  { value: "V", label: "V" },
  { value: "*", label: "*" },
];

const GENERIC_MARKERS: MarkerDef[] = [
  { value: "*", label: "*" },
];

interface Props {
  elementCode: string;
  elementType: string;
  activeMarkers: string[];
  onChange: (markers: string[]) => void;
}

export default function ModifierDropdown({
  elementCode,
  elementType,
  activeMarkers,
  onChange,
}: Props) {
  const isFL = isFlipOrLutz(elementCode);

  // Get available markers based on element type
  let availableMarkers: MarkerDef[];
  if (elementType === "jump") {
    availableMarkers = JUMP_MARKERS.filter(m => !m.flipLutzOnly || isFL);
  } else if (elementType === "spin" || elementType === "pair_spin") {
    availableMarkers = SPIN_MARKERS;
  } else {
    availableMarkers = GENERIC_MARKERS;
  }

  function toggleMarker(marker: string) {
    if (marker === "*") {
      // * is exclusive with everything
      if (activeMarkers.includes("*")) {
        onChange([]);
      } else {
        onChange(["*"]);
      }
      return;
    }

    // If * is active, remove it first
    let current = activeMarkers.filter(m => m !== "*");

    if (current.includes(marker)) {
      // Remove the marker
      onChange(current.filter(m => m !== marker));
      return;
    }

    // Find the marker definition to check group exclusivity
    const def = availableMarkers.find(m => m.value === marker);
    if (def?.group) {
      // Remove other markers in the same group
      const sameGroup = availableMarkers
        .filter(m => m.group === def.group && m.value !== marker)
        .map(m => m.value);
      current = current.filter(m => !sameGroup.includes(m));
    }

    onChange([...current, marker]);
  }

  if (availableMarkers.length === 0) return null;

  return (
    <div className="flex gap-0.5 flex-wrap">
      {availableMarkers.map(marker => {
        const isActive = activeMarkers.includes(marker.value);
        return (
          <button
            key={marker.value}
            onClick={() => toggleMarker(marker.value)}
            title={marker.label}
            className={`px-1.5 py-0.5 text-[10px] font-mono font-bold rounded transition-colors ${
              isActive
                ? "bg-primary/10 text-primary ring-1 ring-primary/30"
                : "bg-surface-container-low text-on-surface-variant hover:bg-surface-container"
            }`}
          >
            {marker.label}
          </button>
        );
      })}
    </div>
  );
}
```

- [ ] **Step 2: Create the GoeTooltip component**

Create `frontend/src/components/program-builder/GoeTooltip.tsx`:

```typescript
import { useState, useRef } from "react";
import type { SovData } from "../../api/client";
import { getGoeBreakdown } from "../../utils/sov-calculator";

interface Props {
  sov: SovData;
  baseCode: string;
  markers: string[];
  side: "negative" | "positive";
  value: number;
  children: React.ReactNode;
}

export default function GoeTooltip({
  sov,
  baseCode,
  markers,
  side,
  value,
  children,
}: Props) {
  const [visible, setVisible] = useState(false);
  const timeoutRef = useRef<ReturnType<typeof setTimeout>>();

  const breakdown = getGoeBreakdown(sov, baseCode, markers, side);

  function handleMouseEnter() {
    timeoutRef.current = setTimeout(() => setVisible(true), 300);
  }

  function handleMouseLeave() {
    if (timeoutRef.current) clearTimeout(timeoutRef.current);
    setVisible(false);
  }

  return (
    <div
      className="relative inline-block"
      onMouseEnter={handleMouseEnter}
      onMouseLeave={handleMouseLeave}
    >
      {children}

      {visible && breakdown && (
        <div className="absolute z-50 bottom-full mb-1 left-1/2 -translate-x-1/2 bg-surface-container-lowest rounded-lg shadow-lg border border-outline-variant/20 p-2 whitespace-nowrap">
          <table className="text-[10px] font-mono">
            <tbody>
              {breakdown.map(({ level, value: goeValue }) => (
                <tr key={level}>
                  <td className={`pr-2 font-bold ${
                    side === "negative" ? "text-[#ba1a1a]" : "text-primary"
                  }`}>
                    {level > 0 ? `+${level}` : level}
                  </td>
                  <td className="text-right text-on-surface">
                    {goeValue.toFixed(2)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 3: Verify TypeScript compiles**

```bash
cd /Users/julien/projects/figure-skating-analyzer/frontend && PATH="/opt/homebrew/bin:$PATH" npx tsc --noEmit --pretty 2>&1 | head -30
```

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/program-builder/ModifierDropdown.tsx frontend/src/components/program-builder/GoeTooltip.tsx
git commit -m "feat: add ModifierDropdown and GoeTooltip components"
```

---

## Task 10: Frontend — ProgramTable Component

**Files:**
- Create: `frontend/src/components/program-builder/ProgramTable.tsx`

The main table displaying all program elements with BV, Min, Max, modifiers, and actions. Supports inline editing (click element name to replace) and combo building.

- [ ] **Step 1: Create the ProgramTable component**

Create `frontend/src/components/program-builder/ProgramTable.tsx`:

```typescript
import { useState, useRef, useEffect } from "react";
import type { SovData } from "../../api/client";
import type { ProgramElement } from "../../utils/program-validator";
import ModifierDropdown from "./ModifierDropdown";
import GoeTooltip from "./GoeTooltip";
import ElementPicker from "./ElementPicker";

// Marker styles matching ScoreCardModal exactly
const MARKER_STYLE: Record<string, { color: string; label: string }> = {
  "*":    { color: "text-[#ba1a1a]", label: "Annulé" },
  "<<":   { color: "text-[#ba1a1a]", label: "Déclassé" },
  "<":    { color: "text-[#e65100]", label: "Sous-rotation" },
  "q":    { color: "text-[#e65100]", label: "Quart court" },
  "e":    { color: "text-[#e65100]", label: "Carre incorrecte" },
  "!":    { color: "text-[#b45309]", label: "Carre incertaine" },
  "x":    { color: "text-primary",   label: "Bonus 2e moitié" },
  "+REP": { color: "text-primary",   label: "Répétition" },
  "V":    { color: "text-[#e65100]", label: "Valeur réduite" },
};

/** Render markers as superscripts matching ScoreCardModal style. */
function MarkerSuperscripts({ markers }: { markers: string[] }) {
  const display = markers.filter(m => !["x", "+REP"].includes(m));
  if (display.length === 0) return null;
  return (
    <>
      {display.map((m, i) => {
        const style = MARKER_STYLE[m] ?? { color: "text-on-surface-variant", label: m };
        return (
          <span
            key={i}
            className={`font-mono text-[9px] font-bold ${style.color} align-super ml-[1px]`}
            title={style.label}
          >
            {m}
          </span>
        );
      })}
    </>
  );
}

/** Render element name with markers, handling combos with per-jump markers. */
function ElementDisplay({ element }: { element: ProgramElement }) {
  if (element.comboJumps && element.comboJumps.length > 1) {
    return (
      <span className="font-mono font-semibold">
        {element.comboJumps.map((jump, i) => (
          <span key={i}>
            {i > 0 && <span className="text-on-surface-variant">+</span>}
            <span>{jump.code}</span>
            <MarkerSuperscripts markers={jump.markers} />
          </span>
        ))}
        {/* Show combo-level markers (x, +REP) at end */}
        <MarkerSuperscripts markers={element.markers.filter(m => ["x", "+REP"].includes(m))} />
      </span>
    );
  }

  return (
    <span className="font-mono font-semibold">
      {element.baseCode}
      <MarkerSuperscripts markers={element.markers} />
    </span>
  );
}

interface Props {
  sov: SovData;
  elements: ProgramElement[];
  includePairs: boolean;
  onUpdateMarkers: (elementId: string, markers: string[]) => void;
  onUpdateComboJumpMarkers: (elementId: string, jumpIndex: number, markers: string[]) => void;
  onAddComboJump: (elementId: string, jumpCode: string) => void;
  onReplaceElement: (elementId: string, newCode: string) => void;
  onDeleteElement: (elementId: string) => void;
}

export default function ProgramTable({
  sov,
  elements,
  includePairs,
  onUpdateMarkers,
  onUpdateComboJumpMarkers,
  onAddComboJump,
  onReplaceElement,
  onDeleteElement,
}: Props) {
  const [editingId, setEditingId] = useState<string | null>(null);
  const popoverRef = useRef<HTMLDivElement>(null);

  // Close popover on outside click or Escape
  useEffect(() => {
    if (!editingId) return;

    function handleClick(e: MouseEvent) {
      if (popoverRef.current && !popoverRef.current.contains(e.target as Node)) {
        setEditingId(null);
      }
    }
    function handleKey(e: KeyboardEvent) {
      if (e.key === "Escape") setEditingId(null);
    }

    document.addEventListener("mousedown", handleClick);
    document.addEventListener("keydown", handleKey);
    return () => {
      document.removeEventListener("mousedown", handleClick);
      document.removeEventListener("keydown", handleKey);
    };
  }, [editingId]);

  // Totals
  const totalBV = elements.reduce((s, e) => s + e.bv, 0);
  const totalMin = elements.reduce((s, e) => s + e.min, 0);
  const totalMax = elements.reduce((s, e) => s + e.max, 0);

  return (
    <div className="overflow-x-auto rounded-xl">
      <table className="w-full border-collapse text-xs">
        <thead>
          <tr className="bg-surface-container-low">
            <th className="text-left font-black uppercase tracking-widest text-on-surface-variant px-3 py-2 rounded-tl-xl w-8">#</th>
            <th className="text-left font-black uppercase tracking-widest text-on-surface-variant px-3 py-2">Élément</th>
            <th className="text-left font-black uppercase tracking-widest text-on-surface-variant px-3 py-2">Mod.</th>
            <th className="text-right font-black uppercase tracking-widest text-on-surface-variant px-3 py-2">BV</th>
            <th className="text-right font-black uppercase tracking-widest text-on-surface-variant px-3 py-2">Min</th>
            <th className="text-right font-black uppercase tracking-widest text-on-surface-variant px-3 py-2">Max</th>
            <th className="text-center font-black uppercase tracking-widest text-on-surface-variant px-3 py-2 rounded-tr-xl w-20"></th>
          </tr>
        </thead>
        <tbody>
          {elements.map((el, i) => {
            const isCombo = el.comboJumps && el.comboJumps.length > 1;
            const canAddCombo = el.type === "jump" && (!el.comboJumps || el.comboJumps.length < 3);
            const rowBg = i % 2 === 0 ? "bg-surface-container-lowest" : "bg-surface-container-low/30";

            return (
              <tr key={el.id} className={rowBg}>
                <td className="px-3 py-2 text-on-surface-variant">{i + 1}</td>

                {/* Element name — click to edit */}
                <td className="px-3 py-2 relative">
                  <button
                    onClick={() => setEditingId(editingId === el.id ? null : el.id)}
                    className="hover:bg-surface-container px-1 -mx-1 rounded transition-colors cursor-pointer"
                    title="Cliquer pour remplacer"
                  >
                    <ElementDisplay element={el} />
                  </button>

                  {/* Inline edit popover */}
                  {editingId === el.id && (
                    <div
                      ref={popoverRef}
                      className="absolute z-50 top-full left-0 mt-1 w-64 bg-surface-container-lowest rounded-xl shadow-lg border border-outline-variant/20 p-2"
                    >
                      <ElementPicker
                        sov={sov}
                        includePairs={includePairs}
                        onSelect={(code) => {
                          onReplaceElement(el.id, code);
                          setEditingId(null);
                        }}
                        placeholder="Remplacer par..."
                      />
                    </div>
                  )}
                </td>

                {/* Modifiers */}
                <td className="px-3 py-2">
                  {isCombo ? (
                    <div className="flex flex-col gap-1">
                      {el.comboJumps!.map((jump, ji) => (
                        <div key={ji} className="flex items-center gap-1">
                          <span className="text-[9px] text-on-surface-variant font-mono w-8 shrink-0">{jump.code}</span>
                          <ModifierDropdown
                            elementCode={jump.code}
                            elementType="jump"
                            activeMarkers={jump.markers}
                            onChange={(markers) => onUpdateComboJumpMarkers(el.id, ji, markers)}
                          />
                        </div>
                      ))}
                    </div>
                  ) : (
                    <ModifierDropdown
                      elementCode={el.baseCode}
                      elementType={el.type}
                      activeMarkers={el.markers}
                      onChange={(markers) => onUpdateMarkers(el.id, markers)}
                    />
                  )}
                </td>

                {/* BV */}
                <td className="px-3 py-2 text-right font-mono font-bold text-on-surface">
                  {el.bv.toFixed(2)}
                </td>

                {/* Min with GOE tooltip */}
                <td className="px-3 py-2 text-right">
                  <GoeTooltip
                    sov={sov}
                    baseCode={el.baseCode}
                    markers={el.markers}
                    side="negative"
                    value={el.min}
                  >
                    <span className="font-mono text-[#ba1a1a] cursor-default">
                      {el.min.toFixed(2)}
                    </span>
                  </GoeTooltip>
                </td>

                {/* Max with GOE tooltip */}
                <td className="px-3 py-2 text-right">
                  <GoeTooltip
                    sov={sov}
                    baseCode={el.baseCode}
                    markers={el.markers}
                    side="positive"
                    value={el.max}
                  >
                    <span className="font-mono text-primary cursor-default">
                      {el.max.toFixed(2)}
                    </span>
                  </GoeTooltip>
                </td>

                {/* Actions */}
                <td className="px-3 py-2 text-center">
                  <div className="flex items-center justify-center gap-1">
                    {canAddCombo && (
                      <AddComboButton
                        sov={sov}
                        includePairs={includePairs}
                        elementId={el.id}
                        currentJumps={el.comboJumps?.length ?? 1}
                        onAdd={onAddComboJump}
                      />
                    )}
                    <button
                      onClick={() => onDeleteElement(el.id)}
                      className="text-on-surface-variant hover:text-error transition-colors p-0.5"
                      title="Supprimer"
                    >
                      <span className="material-symbols-outlined text-base">delete</span>
                    </button>
                  </div>
                </td>
              </tr>
            );
          })}

          {/* Total row */}
          {elements.length > 0 && (
            <tr className="bg-surface-container-low border-t border-outline-variant/30">
              <td colSpan={3} className="px-3 py-2 font-black uppercase tracking-widest text-on-surface-variant text-[10px]">
                Total
              </td>
              <td className="px-3 py-2 text-right font-mono font-bold text-on-surface">
                {totalBV.toFixed(2)}
              </td>
              <td className="px-3 py-2 text-right font-mono font-bold text-[#ba1a1a]">
                {totalMin.toFixed(2)}
              </td>
              <td className="px-3 py-2 text-right font-mono font-bold text-primary">
                {totalMax.toFixed(2)}
              </td>
              <td />
            </tr>
          )}

          {/* Empty state */}
          {elements.length === 0 && (
            <tr>
              <td colSpan={7} className="px-3 py-8 text-center text-on-surface-variant text-sm">
                Aucun élément. Utilisez le sélecteur ci-dessus pour ajouter des éléments.
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  );
}

/** Small inline button to add a jump to a combo. Opens a filtered jump picker. */
function AddComboButton({
  sov,
  includePairs,
  elementId,
  currentJumps,
  onAdd,
}: {
  sov: SovData;
  includePairs: boolean;
  elementId: string;
  currentJumps: number;
  onAdd: (elementId: string, jumpCode: string) => void;
}) {
  const [isOpen, setIsOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!isOpen) return;
    function handleClick(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setIsOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, [isOpen]);

  return (
    <div className="relative" ref={ref}>
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="text-on-surface-variant hover:text-primary transition-colors p-0.5"
        title={`Ajouter un saut (${currentJumps}/3)`}
      >
        <span className="material-symbols-outlined text-base">add</span>
      </button>

      {isOpen && (
        <div className="absolute z-50 top-full right-0 mt-1 w-48 bg-surface-container-lowest rounded-xl shadow-lg border border-outline-variant/20 p-2">
          <ElementPicker
            sov={sov}
            includePairs={includePairs}
            onSelect={(code) => {
              onAdd(elementId, code);
              setIsOpen(false);
            }}
            jumpsOnly
            placeholder="Ajouter un saut..."
          />
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Verify TypeScript compiles**

```bash
cd /Users/julien/projects/figure-skating-analyzer/frontend && PATH="/opt/homebrew/bin:$PATH" npx tsc --noEmit --pretty 2>&1 | head -30
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/program-builder/ProgramTable.tsx
git commit -m "feat: add ProgramTable component with inline editing and combo support"
```

---

## Task 11: Frontend — CompetitionLoader Component

**Files:**
- Create: `frontend/src/components/program-builder/CompetitionLoader.tsx`

Allows loading a real program from an existing skater's score in a competition.

- [ ] **Step 1: Create the CompetitionLoader component**

Create `frontend/src/components/program-builder/CompetitionLoader.tsx`:

```typescript
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api, Score } from "../../api/client";

interface Props {
  onLoad: (elements: { code: string; markers: string[] }[]) => void;
}

export default function CompetitionLoader({ onLoad }: Props) {
  const [showAll, setShowAll] = useState(false);
  const [selectedSkaterId, setSelectedSkaterId] = useState<number | null>(null);
  const [selectedScoreId, setSelectedScoreId] = useState<number | null>(null);

  // Fetch skaters (club only by default, all if toggled)
  const { data: skaters } = useQuery({
    queryKey: ["skaters", showAll ? "all" : "club"],
    queryFn: () => api.skaters.list(showAll ? {} : { club: "__my_club__" }),
  });

  // Fetch scores for selected skater
  const { data: scores } = useQuery({
    queryKey: ["skater-scores", selectedSkaterId],
    queryFn: () => api.skaters.scores(selectedSkaterId!),
    enabled: selectedSkaterId != null,
  });

  // Group scores by competition for display
  const scoreOptions = (scores ?? [])
    .filter(s => s.elements && s.elements.length > 0)
    .sort((a, b) => {
      const dateA = a.competition_date ?? "";
      const dateB = b.competition_date ?? "";
      return dateB.localeCompare(dateA);
    });

  function handleLoad() {
    if (!selectedScoreId || !scores) return;
    const score = scores.find(s => s.id === selectedScoreId);
    if (!score?.elements) return;

    const elements = score.elements.map(el => ({
      code: el.name,
      markers: (el.markers ?? []).filter(m => m !== "+" && m !== "F"),
    }));
    onLoad(elements);
  }

  return (
    <div className="flex flex-wrap items-end gap-3 p-4 bg-surface-container-low/50 rounded-xl">
      <div className="flex-1 min-w-[160px]">
        <label className="block text-[10px] font-black uppercase tracking-widest text-on-surface-variant mb-1">
          Patineur
        </label>
        <select
          value={selectedSkaterId ?? ""}
          onChange={e => {
            setSelectedSkaterId(e.target.value ? Number(e.target.value) : null);
            setSelectedScoreId(null);
          }}
          className="w-full px-3 py-2 rounded-lg bg-surface-container-lowest text-on-surface text-sm focus:outline-none focus:ring-2 focus:ring-primary/30"
        >
          <option value="">Sélectionner...</option>
          {(skaters ?? []).map(s => (
            <option key={s.id} value={s.id}>
              {s.last_name} {s.first_name}
            </option>
          ))}
        </select>
      </div>

      <div className="flex-1 min-w-[200px]">
        <label className="block text-[10px] font-black uppercase tracking-widest text-on-surface-variant mb-1">
          Score
        </label>
        <select
          value={selectedScoreId ?? ""}
          onChange={e => setSelectedScoreId(e.target.value ? Number(e.target.value) : null)}
          disabled={!selectedSkaterId}
          className="w-full px-3 py-2 rounded-lg bg-surface-container-lowest text-on-surface text-sm focus:outline-none focus:ring-2 focus:ring-primary/30 disabled:opacity-50"
        >
          <option value="">Sélectionner...</option>
          {scoreOptions.map(s => (
            <option key={s.id} value={s.id}>
              {s.competition_name} — {s.segment?.toUpperCase()} {s.category ? `(${s.category})` : ""}
              {s.competition_date ? ` · ${s.competition_date.slice(0, 10)}` : ""}
            </option>
          ))}
        </select>
      </div>

      <label className="flex items-center gap-1.5 text-xs text-on-surface-variant cursor-pointer shrink-0">
        <input
          type="checkbox"
          checked={showAll}
          onChange={e => {
            setShowAll(e.target.checked);
            setSelectedSkaterId(null);
            setSelectedScoreId(null);
          }}
          className="rounded"
        />
        Tous les patineurs
      </label>

      <button
        onClick={handleLoad}
        disabled={!selectedScoreId}
        className="px-4 py-2 bg-primary text-white rounded-lg text-sm font-bold hover:bg-primary/90 transition-colors disabled:opacity-50 disabled:cursor-not-allowed shrink-0"
      >
        Charger
      </button>
    </div>
  );
}
```

- [ ] **Step 2: Verify TypeScript compiles**

```bash
cd /Users/julien/projects/figure-skating-analyzer/frontend && PATH="/opt/homebrew/bin:$PATH" npx tsc --noEmit --pretty 2>&1 | head -30
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/program-builder/CompetitionLoader.tsx
git commit -m "feat: add CompetitionLoader component for loading programs from scores"
```

---

## Task 12: Frontend — CategoryPanel Component

**Files:**
- Create: `frontend/src/components/program-builder/CategoryPanel.tsx`

The right-side panel showing category suggestion, validation checklist, and program summary.

- [ ] **Step 1: Create the CategoryPanel component**

Create `frontend/src/components/program-builder/CategoryPanel.tsx`:

```typescript
import type { ProgramRulesData } from "../../api/client";
import type { ProgramElement } from "../../utils/program-validator";
import type { CategoryMatch } from "../../utils/category-matcher";
import { matchCategories, getCompatibleCategories, getBestMatch } from "../../utils/category-matcher";

interface Props {
  elements: ProgramElement[];
  rulesData: ProgramRulesData | undefined;
}

export default function CategoryPanel({ elements, rulesData }: Props) {
  if (!rulesData || elements.length === 0) {
    return (
      <div className="space-y-6">
        <SummarySection elements={elements} />
        <div className="text-sm text-on-surface-variant">
          Ajoutez des éléments pour voir la catégorie suggérée.
        </div>
      </div>
    );
  }

  const matches = matchCategories(elements, rulesData);
  const compatible = getCompatibleCategories(matches);
  const best = getBestMatch(matches);

  return (
    <div className="space-y-6">
      {/* Category suggestion */}
      <div>
        <h3 className="text-[10px] font-black uppercase tracking-widest text-on-surface-variant mb-3">
          Catégorie détectée
        </h3>
        {compatible.length > 0 ? (
          <div className="space-y-2">
            {compatible.map((m, i) => (
              <div
                key={`${m.categoryName}-${m.segmentKey}`}
                className={`px-3 py-2 rounded-lg ${
                  i === 0
                    ? "bg-primary/10 border border-primary/20"
                    : "bg-surface-container-low"
                }`}
              >
                <span className={`text-sm font-bold ${i === 0 ? "text-primary" : "text-on-surface"}`}>
                  {m.categoryLabel}
                </span>
                <span className="text-xs text-on-surface-variant ml-2">
                  — {m.segmentLabel}
                </span>
              </div>
            ))}
          </div>
        ) : best ? (
          <div className="px-3 py-2 rounded-lg bg-error/5 border border-error/20">
            <span className="text-sm font-bold text-on-surface">
              {best.categoryLabel}
            </span>
            <span className="text-xs text-on-surface-variant ml-2">
              — {best.segmentLabel}
            </span>
            <span className="text-xs text-error ml-2">
              ({best.violations} violation{best.violations > 1 ? "s" : ""})
            </span>
          </div>
        ) : null}
      </div>

      {/* Validation checklist */}
      {best && (
        <div>
          <h3 className="text-[10px] font-black uppercase tracking-widest text-on-surface-variant mb-3">
            Validation — {best.categoryLabel} ({best.segmentLabel})
          </h3>
          <div className="space-y-1.5">
            {best.results.map((r, i) => (
              <div key={i} className="flex items-start gap-2 text-xs">
                <span className="shrink-0 mt-0.5">
                  {r.status === "ok" && (
                    <span className="material-symbols-outlined text-sm text-green-600">check_circle</span>
                  )}
                  {r.status === "warning" && (
                    <span className="material-symbols-outlined text-sm text-orange-500">warning</span>
                  )}
                  {r.status === "error" && (
                    <span className="material-symbols-outlined text-sm text-error">cancel</span>
                  )}
                </span>
                <div>
                  <span className="font-medium text-on-surface">{r.label}</span>
                  <span className="text-on-surface-variant ml-1.5">{r.detail}</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Summary */}
      <SummarySection elements={elements} />
    </div>
  );
}

function SummarySection({ elements }: { elements: ProgramElement[] }) {
  const jumps = elements.filter(e => e.type === "jump");
  const spins = elements.filter(e => e.type === "spin" || e.type === "pair_spin");
  const steps = elements.filter(e => e.type === "step");
  const choreo = elements.filter(e => e.type === "choreo");
  const combos = elements.filter(e => e.comboJumps && e.comboJumps.length > 1);
  const secondHalf = elements.filter(e => e.markers.includes("x"));

  return (
    <div>
      <h3 className="text-[10px] font-black uppercase tracking-widest text-on-surface-variant mb-3">
        Résumé
      </h3>
      <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-xs">
        <CountRow label="Sauts" count={jumps.length} />
        <CountRow label="Pirouettes" count={spins.length} />
        <CountRow label="Pas" count={steps.length} />
        <CountRow label="Chorégraphique" count={choreo.length} />
        <CountRow label="Combinaisons" count={combos.length} />
        <CountRow label="2e moitié (x)" count={secondHalf.length} />
      </div>
    </div>
  );
}

function CountRow({ label, count }: { label: string; count: number }) {
  return (
    <div className="flex justify-between py-0.5">
      <span className="text-on-surface-variant">{label}</span>
      <span className="font-mono font-bold text-on-surface">{count}</span>
    </div>
  );
}
```

- [ ] **Step 2: Verify TypeScript compiles**

```bash
cd /Users/julien/projects/figure-skating-analyzer/frontend && PATH="/opt/homebrew/bin:$PATH" npx tsc --noEmit --pretty 2>&1 | head -30
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/program-builder/CategoryPanel.tsx
git commit -m "feat: add CategoryPanel component with auto-detection and validation"
```

---

## Task 13: Frontend — useProgramBuilder Hook

**Files:**
- Create: `frontend/src/hooks/useProgramBuilder.ts`

Central state management hook that ties everything together: element list, marker updates, BV/min/max recalculation, combo management, element replacement, and element deletion.

- [ ] **Step 1: Create the useProgramBuilder hook**

Create `frontend/src/hooks/useProgramBuilder.ts`:

```typescript
import { useState, useCallback, useMemo } from "react";
import type { SovData } from "../api/client";
import type { ProgramElement } from "../utils/program-validator";
import {
  calculateElementBV,
  calculateElementMin,
  calculateElementMax,
  calculateComboBV,
  isJump,
} from "../utils/sov-calculator";

let _nextId = 1;
function genId(): string {
  return `el-${_nextId++}`;
}

/**
 * Recalculate BV, min, and max for a program element.
 */
function recalcElement(sov: SovData, el: ProgramElement): ProgramElement {
  if (el.comboJumps && el.comboJumps.length > 1) {
    // Combo: sum of individual jump BVs + combo-level modifiers
    const comboMarkers = el.markers.filter(m => ["x", "+REP", "*"].includes(m));
    const bv = calculateComboBV(sov, el.comboJumps, comboMarkers);

    // Min/Max: sum of per-jump min/max with combo modifiers
    let minTotal = 0;
    let maxTotal = 0;
    for (const jump of el.comboJumps) {
      const jumpMarkers = jump.markers.filter(m => !["x", "+REP"].includes(m));
      minTotal += calculateElementMin(sov, jump.code, jumpMarkers);
      maxTotal += calculateElementMax(sov, jump.code, jumpMarkers);
    }
    if (comboMarkers.includes("*")) {
      minTotal = 0;
      maxTotal = 0;
    } else {
      if (comboMarkers.includes("x")) { minTotal *= 1.10; maxTotal *= 1.10; }
      if (comboMarkers.includes("+REP")) { minTotal *= 0.70; maxTotal *= 0.70; }
    }

    return {
      ...el,
      bv,
      min: Math.round(minTotal * 100) / 100,
      max: Math.round(maxTotal * 100) / 100,
    };
  }

  return {
    ...el,
    bv: calculateElementBV(sov, el.baseCode, el.markers),
    min: calculateElementMin(sov, el.baseCode, el.markers),
    max: calculateElementMax(sov, el.baseCode, el.markers),
  };
}

export function useProgramBuilder(sov: SovData | undefined) {
  const [elements, setElements] = useState<ProgramElement[]>([]);

  /** Add an element to the program. */
  const addElement = useCallback((code: string) => {
    if (!sov) return;
    const sovEl = sov.elements[code];
    if (!sovEl) return;

    const el: ProgramElement = {
      id: genId(),
      baseCode: code,
      type: sovEl.type,
      markers: [],
      bv: sovEl.base_value,
      min: sovEl.base_value + (sovEl.goe[0] ?? 0),
      max: sovEl.base_value + (sovEl.goe[9] ?? 0),
    };

    // If it's a jump, initialize comboJumps with single entry
    if (sovEl.type === "jump") {
      el.comboJumps = [{ code, markers: [] }];
    }

    setElements(prev => [...prev, el]);
  }, [sov]);

  /** Update markers on a non-combo element (or combo-level markers). */
  const updateMarkers = useCallback((elementId: string, markers: string[]) => {
    if (!sov) return;
    setElements(prev =>
      prev.map(el => {
        if (el.id !== elementId) return el;
        return recalcElement(sov, { ...el, markers });
      }),
    );
  }, [sov]);

  /** Update markers on a specific jump within a combo. */
  const updateComboJumpMarkers = useCallback((elementId: string, jumpIndex: number, markers: string[]) => {
    if (!sov) return;
    setElements(prev =>
      prev.map(el => {
        if (el.id !== elementId || !el.comboJumps) return el;
        const newJumps = el.comboJumps.map((j, i) =>
          i === jumpIndex ? { ...j, markers } : j,
        );
        return recalcElement(sov, { ...el, comboJumps: newJumps });
      }),
    );
  }, [sov]);

  /** Add a jump to an existing element to form a combo. */
  const addComboJump = useCallback((elementId: string, jumpCode: string) => {
    if (!sov) return;
    setElements(prev =>
      prev.map(el => {
        if (el.id !== elementId) return el;
        const currentJumps = el.comboJumps ?? [{ code: el.baseCode, markers: [] }];
        if (currentJumps.length >= 3) return el;

        // Euler only allowed in position 2 of a 3-jump combo
        if (jumpCode === "1Eu" && currentJumps.length !== 1) return el;

        const newJumps = [...currentJumps, { code: jumpCode, markers: [] }];
        const newBaseCode = newJumps.map(j => j.code).join("+");
        return recalcElement(sov, { ...el, baseCode: newBaseCode, comboJumps: newJumps });
      }),
    );
  }, [sov]);

  /** Replace an element with a new one (inline edit). Resets markers and breaks combos. */
  const replaceElement = useCallback((elementId: string, newCode: string) => {
    if (!sov) return;
    const sovEl = sov.elements[newCode];
    if (!sovEl) return;

    setElements(prev =>
      prev.map(el => {
        if (el.id !== elementId) return el;
        const newEl: ProgramElement = {
          ...el,
          baseCode: newCode,
          type: sovEl.type,
          markers: [],
          comboJumps: sovEl.type === "jump" ? [{ code: newCode, markers: [] }] : undefined,
          bv: 0,
          min: 0,
          max: 0,
        };
        return recalcElement(sov, newEl);
      }),
    );
  }, [sov]);

  /** Delete an element from the program. */
  const deleteElement = useCallback((elementId: string) => {
    setElements(prev => prev.filter(el => el.id !== elementId));
  }, []);

  /** Load a program from a score's elements. Replaces the current program. */
  const loadFromScore = useCallback((scoreElements: { code: string; markers: string[] }[]) => {
    if (!sov) return;
    const newElements: ProgramElement[] = [];

    for (const { code, markers } of scoreElements) {
      const parts = code.split("+");
      const firstPart = parts[0];
      const sovEl = sov.elements[firstPart];
      if (!sovEl) continue;

      const el: ProgramElement = {
        id: genId(),
        baseCode: code,
        type: sovEl.type,
        markers: markers.filter(m => ["x", "+REP"].includes(m)),
        bv: 0,
        min: 0,
        max: 0,
      };

      if (parts.length > 1 && sovEl.type === "jump") {
        // Combo element
        el.comboJumps = parts.map((p, i) => ({
          code: p,
          markers: [], // Score markers are positional; simplified for now
        }));
      } else if (sovEl.type === "jump") {
        el.comboJumps = [{ code: firstPart, markers: markers.filter(m => !["x", "+REP"].includes(m)) }];
      }

      newElements.push(recalcElement(sov, el));
    }

    setElements(newElements);
  }, [sov]);

  /** Clear all elements. */
  const clearProgram = useCallback(() => {
    setElements([]);
  }, []);

  return {
    elements,
    addElement,
    updateMarkers,
    updateComboJumpMarkers,
    addComboJump,
    replaceElement,
    deleteElement,
    loadFromScore,
    clearProgram,
  };
}
```

- [ ] **Step 2: Verify TypeScript compiles**

```bash
cd /Users/julien/projects/figure-skating-analyzer/frontend && PATH="/opt/homebrew/bin:$PATH" npx tsc --noEmit --pretty 2>&1 | head -30
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/hooks/useProgramBuilder.ts
git commit -m "feat: add useProgramBuilder hook for central program state management"
```

---

## Task 14: Frontend — ProgramBuilderPage + Navigation Integration

**Files:**
- Create: `frontend/src/pages/ProgramBuilderPage.tsx`
- Modify: `frontend/src/App.tsx`

- [ ] **Step 1: Create the ProgramBuilderPage**

Create `frontend/src/pages/ProgramBuilderPage.tsx`:

```typescript
import { useState } from "react";
import { useSovData } from "../hooks/useSovData";
import { useProgramRules } from "../hooks/useProgramRules";
import { useProgramBuilder } from "../hooks/useProgramBuilder";
import ElementPicker from "../components/program-builder/ElementPicker";
import ProgramTable from "../components/program-builder/ProgramTable";
import CompetitionLoader from "../components/program-builder/CompetitionLoader";
import CategoryPanel from "../components/program-builder/CategoryPanel";

export default function ProgramBuilderPage() {
  const { data: sov, isLoading: sovLoading } = useSovData();
  const { data: rules, isLoading: rulesLoading } = useProgramRules();
  const [includePairs, setIncludePairs] = useState(false);

  const {
    elements,
    addElement,
    updateMarkers,
    updateComboJumpMarkers,
    addComboJump,
    replaceElement,
    deleteElement,
    loadFromScore,
    clearProgram,
  } = useProgramBuilder(sov);

  if (sovLoading || rulesLoading) {
    return (
      <div className="flex items-center justify-center min-h-[40vh]">
        <span className="material-symbols-outlined animate-spin text-primary text-3xl">
          progress_activity
        </span>
      </div>
    );
  }

  if (!sov) {
    return (
      <div className="text-center text-on-surface-variant py-12">
        Erreur de chargement des données SOV.
      </div>
    );
  }

  return (
    <div className="flex flex-col lg:flex-row gap-6">
      {/* Left column — main content */}
      <div className="flex-1 min-w-0 space-y-6">
        {/* Competition loader */}
        <CompetitionLoader onLoad={loadFromScore} />

        {/* Element picker + controls */}
        <div className="flex flex-wrap items-end gap-3">
          <div className="flex-1 min-w-[200px]">
            <ElementPicker
              sov={sov}
              includePairs={includePairs}
              onSelect={addElement}
              placeholder="Ajouter un élément..."
            />
          </div>

          <label className="flex items-center gap-1.5 text-xs text-on-surface-variant cursor-pointer shrink-0">
            <input
              type="checkbox"
              checked={includePairs}
              onChange={e => setIncludePairs(e.target.checked)}
              className="rounded"
            />
            Éléments couples
          </label>

          {elements.length > 0 && (
            <button
              onClick={clearProgram}
              className="text-xs text-on-surface-variant hover:text-error transition-colors shrink-0"
            >
              Tout effacer
            </button>
          )}
        </div>

        {/* Program table */}
        <ProgramTable
          sov={sov}
          elements={elements}
          includePairs={includePairs}
          onUpdateMarkers={updateMarkers}
          onUpdateComboJumpMarkers={updateComboJumpMarkers}
          onAddComboJump={addComboJump}
          onReplaceElement={replaceElement}
          onDeleteElement={deleteElement}
        />
      </div>

      {/* Right column — category panel (stacks below on mobile) */}
      <div className="lg:w-80 shrink-0">
        <div className="lg:sticky lg:top-20">
          <CategoryPanel elements={elements} rulesData={rules} />
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Add navigation item and route in App.tsx**

In `frontend/src/App.tsx`:

**a) Add the import** at the top with the other page imports (after the `TrainingPage` import):

```typescript
import ProgramBuilderPage from "./pages/ProgramBuilderPage";
```

**b) Add the nav item for coach role.** In the coach nav section (around line 180), add the "PROGRAMME" item after "CLUB" and before "ENTRAÎNEMENT":

Find this array in the coach nav:
```typescript
{[
  { to: "/", label: "TABLEAU DE BORD", icon: "dashboard", end: true },
  ...(config?.training_enabled ? [{ to: "/entrainement", label: "ENTRAÎNEMENT", icon: "fitness_center", end: true }] : []),
  { to: "/patineurs", label: "PATINEURS", icon: "people", end: false },
  { to: "/competitions", label: "COMPÉTITIONS", icon: "emoji_events", end: false },
  { to: "/club", label: "CLUB", icon: "bar_chart", end: false },
]}
```

Replace with:
```typescript
{[
  { to: "/", label: "TABLEAU DE BORD", icon: "dashboard", end: true },
  ...(config?.training_enabled ? [{ to: "/entrainement", label: "ENTRAÎNEMENT", icon: "fitness_center", end: true }] : []),
  { to: "/patineurs", label: "PATINEURS", icon: "people", end: false },
  { to: "/competitions", label: "COMPÉTITIONS", icon: "emoji_events", end: false },
  { to: "/club", label: "CLUB", icon: "bar_chart", end: false },
  { to: "/programme", label: "PROGRAMME", icon: "sports_score", end: true },
]}
```

**c) Add the nav item for admin/default role.** In the default nav (around line 206), add "PROGRAMME" to `navLinksBase` — but only for non-reader roles. The simplest approach: add the link conditionally after `navLinksBase`:

Find:
```typescript
{[...navLinksBase, ...(config?.training_enabled && user?.role !== "reader" ? [trainingNavLink] : [])].map(
```

Replace with:
```typescript
{[...navLinksBase, ...(user?.role !== "reader" ? [{ to: "/programme", label: "PROGRAMME", icon: "sports_score", end: true }] : []), ...(config?.training_enabled && user?.role !== "reader" ? [trainingNavLink] : [])].map(
```

**d) Add the route for coach role.** In the coach routes section (around line 337), add the route after the `/club` route:

```typescript
<Route path="/programme" element={<ProgramBuilderPage />} />
```

**e) Add the route for admin/default role.** In the default routes section (around line 350), add the route after the `/club` routes:

```typescript
<Route path="/programme" element={<ProgramBuilderPage />} />
```

**f) Add the page title.** In the `getPageTitle` function, add:

```typescript
if (pathname === "/programme") return "Programme";
```

- [ ] **Step 3: Verify TypeScript compiles**

```bash
cd /Users/julien/projects/figure-skating-analyzer/frontend && PATH="/opt/homebrew/bin:$PATH" npx tsc --noEmit --pretty 2>&1 | head -30
```

- [ ] **Step 4: Start dev servers and test in browser**

```bash
cd /Users/julien/projects/figure-skating-analyzer && make dev-backend &
cd /Users/julien/projects/figure-skating-analyzer && make dev-frontend &
```

Open `http://localhost:5173/programme` (logged in as coach/admin). Test:
1. Element picker search and add
2. Modifier toggle and BV recalculation
3. Combo building with "+" button
4. Min/Max GOE hover tooltips
5. Category suggestion updates as elements are added
6. Inline editing by clicking element name
7. Element deletion via trash icon
8. Competition loader (select skater → score → load)
9. "Éléments couples" toggle
10. Responsive layout (resize to < lg breakpoint)
11. "Tout effacer" button

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/ProgramBuilderPage.tsx frontend/src/App.tsx
git commit -m "feat: add Programme page with navigation and routing"
```

---

## Task 15: Final — Run All Tests and Polish

**Files:**
- Potentially any file from above for fixes

- [ ] **Step 1: Run backend tests**

```bash
cd /Users/julien/projects/figure-skating-analyzer/backend && PATH="/opt/homebrew/bin:$PATH" uv run pytest -v
```

Expected: all tests pass including the new `test_program_builder.py`.

- [ ] **Step 2: Run frontend type check**

```bash
cd /Users/julien/projects/figure-skating-analyzer/frontend && PATH="/opt/homebrew/bin:$PATH" npx tsc --noEmit --pretty
```

Expected: no type errors.

- [ ] **Step 3: Fix any issues found**

If tests fail or TypeScript has errors, fix them and re-run.

- [ ] **Step 4: Final commit if needed**

```bash
git add -A
git commit -m "fix: resolve issues found during final test pass"
```
