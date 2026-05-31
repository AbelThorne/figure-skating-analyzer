# Club on Score — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Store club per score (not just per skater) so that skaters who change clubs appear correctly for each club across competitions, while preserving `Skater.club` as a manually-editable "current club" field.

**Architecture:** Add a `club` column to `Score` and `CategoryResult`. During import, populate it from scraped data. Update `Skater.club` to the most recent score's club (unless the skater was manually edited). Dashboard and team scoring read club from Score/CategoryResult instead of Skater. `Skater.club` remains the fallback for skaters with no scores (manual creates, training-only).

**Tech Stack:** Python/Litestar, SQLAlchemy async, SQLite, React/TypeScript

---

### Task 1: Add `club` column to Score model + migration

**Files:**
- Modify: `backend/app/models/score.py:1-43`
- Modify: `backend/app/database.py:42-69` (migration list)

- [ ] **Step 1: Add club field to Score model**

In `backend/app/models/score.py`, add after the `is_titular` field (line 35):

```python
club: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
```

- [ ] **Step 2: Add migration entry for scores.club**

In `backend/app/database.py`, add to the `_MIGRATIONS` list (after the `is_titular` entry at line 68):

```python
("scores", "club", "VARCHAR(255)"),
```

- [ ] **Step 3: Commit**

```bash
git add backend/app/models/score.py backend/app/database.py
git commit -m "feat: add club column to Score model"
```

---

### Task 2: Add `club` column to CategoryResult model

**Files:**
- Modify: `backend/app/models/category_result.py` — add club field
- Modify: `backend/app/database.py:42-69` (migration list)

- [ ] **Step 1: Add club field to CategoryResult model**

In `backend/app/models/category_result.py`, add a club field (same pattern as Score):

```python
club: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
```

- [ ] **Step 2: Add migration entry for category_results.club**

In `backend/app/database.py`, add to the `_MIGRATIONS` list:

```python
("category_results", "club", "VARCHAR(255)"),
```

- [ ] **Step 3: Commit**

```bash
git add backend/app/models/category_result.py backend/app/database.py
git commit -m "feat: add club column to CategoryResult model"
```

---

### Task 3: Backfill existing data — copy Skater.club to Score.club and CategoryResult.club

**Files:**
- Modify: `backend/app/database.py` — add backfill function called from `init_db()`

- [ ] **Step 1: Write backfill migration**

Add a new async function in `backend/app/database.py` after `_migrate_add_columns`:

```python
async def _backfill_score_club(conn) -> None:
    """One-time backfill: copy skater.club to scores/category_results where club is NULL."""
    await conn.execute(text("""
        UPDATE scores SET club = (
            SELECT skaters.club FROM skaters WHERE skaters.id = scores.skater_id
        ) WHERE scores.club IS NULL
    """))
    await conn.execute(text("""
        UPDATE category_results SET club = (
            SELECT skaters.club FROM skaters WHERE skaters.id = category_results.skater_id
        ) WHERE category_results.club IS NULL
    """))
    logger.info("Backfilled score/category_result club from skater.club")
```

- [ ] **Step 2: Call backfill from init_db()**

In `init_db()`, add after the `_migrate_add_columns` call (line 32):

```python
await conn.run_sync(lambda c: None)  # not needed, just call after migrations
```

Actually, call it inside the `async with engine.begin() as conn:` block, after `_migrate_add_columns(conn)`:

```python
await _backfill_score_club(conn)
```

- [ ] **Step 3: Commit**

```bash
git add backend/app/database.py
git commit -m "feat: backfill Score.club and CategoryResult.club from Skater.club"
```

---

### Task 4: Update import service to store club on Score and CategoryResult

**Files:**
- Modify: `backend/app/services/import_service.py:140-200`

- [ ] **Step 1: Set club on Score during import**

In `import_service.py`, in the loop that creates scores (around line 158), after the skater is retrieved and the Score object is created, set `club` on the score. Find where the Score is constructed (look for `Score(` in the import function) and add `club=r.club`:

In the score creation section (around line 158-175), the code calls `_get_or_create_skater` with `r.club`. After the Score is created/found, set:

```python
score.club = r.club
```

Similarly for CategoryResult creation (around line 195), set:

```python
cat_result.club = cr.club
```

- [ ] **Step 2: Update Skater.club logic — always update to latest**

In `_get_or_create_skater` (line 79-80), change from:

```python
if not skater.club and club:
    skater.club = club
```

to:

```python
if club:
    skater.club = club
```

This ensures `Skater.club` always reflects the most recently imported club. Manual edits are preserved until the next import with a different club, which is the desired behavior (the competition data is authoritative).

- [ ] **Step 3: Commit**

```bash
git add backend/app/services/import_service.py
git commit -m "feat: store club on Score/CategoryResult during import, update Skater.club to latest"
```

---

### Task 5: Write tests for import club behavior

**Files:**
- Create: `backend/tests/test_import_club.py`

- [ ] **Step 1: Write test — club stored on Score during import**

```python
"""Tests for club storage on Score and Skater.club update behavior."""

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.competition import Competition
from app.models.skater import Skater
from app.models.score import Score
from app.services.import_service import _get_or_create_skater


@pytest.mark.asyncio
async def test_get_or_create_skater_updates_club(db_session: AsyncSession):
    """When a skater already exists, their club should be updated to the new value."""
    skater = Skater(first_name="Alice", last_name="DUPONT", club="Old Club")
    db_session.add(skater)
    await db_session.flush()

    result = await _get_or_create_skater(db_session, "Alice DUPONT", "FRA", "New Club")
    assert result.id == skater.id
    assert result.club == "New Club"


@pytest.mark.asyncio
async def test_get_or_create_skater_keeps_club_when_none(db_session: AsyncSession):
    """When import has no club info, keep existing club."""
    skater = Skater(first_name="Alice", last_name="DUPONT", club="Existing Club")
    db_session.add(skater)
    await db_session.flush()

    result = await _get_or_create_skater(db_session, "Alice DUPONT", "FRA", None)
    assert result.club == "Existing Club"


@pytest.mark.asyncio
async def test_get_or_create_skater_sets_club_on_new(db_session: AsyncSession):
    """New skater gets club from import."""
    result = await _get_or_create_skater(db_session, "Bob MARTIN", "FRA", "My Club")
    assert result.club == "My Club"
```

- [ ] **Step 2: Run tests to verify they pass**

Run: `cd backend && uv run pytest tests/test_import_club.py -v`
Expected: 3 PASSED

- [ ] **Step 3: Commit**

```bash
git add backend/tests/test_import_club.py
git commit -m "test: add tests for club storage on import"
```

---

### Task 6: Update Score serialization — use Score.club instead of Skater.club

**Files:**
- Modify: `backend/app/routes/scores.py:43-53` (`_score_to_dict`)
- Modify: `backend/app/routes/scores.py:120-125` (`_cat_result_to_dict`)

- [ ] **Step 1: Update _score_to_dict to use Score.club**

In `backend/app/routes/scores.py`, line 53, change:

```python
"skater_club": s.skater.club if s.skater else None,
```

to:

```python
"skater_club": s.club or (s.skater.club if s.skater else None),
```

This uses Score.club first, falling back to Skater.club for old data that wasn't backfilled.

- [ ] **Step 2: Update _cat_result_to_dict similarly**

Line 125, change:

```python
"skater_club": cr.skater.club if cr.skater else None,
```

to:

```python
"skater_club": cr.club or (cr.skater.club if cr.skater else None),
```

- [ ] **Step 3: Commit**

```bash
git add backend/app/routes/scores.py
git commit -m "feat: read club from Score/CategoryResult instead of Skater"
```

---

### Task 7: Update dashboard to filter by Score.club

**Files:**
- Modify: `backend/app/routes/dashboard.py`

The dashboard currently filters skaters by `Skater.club`. We need to change it so a skater is included if they have `Skater.club` matching OR if they have any Score with `Score.club` matching. This way, a manually-added skater with the right club shows up, AND a skater who transferred shows up via their scores.

- [ ] **Step 1: Update dashboard club filter logic**

The current pattern (repeated ~8 times) is:

```python
if club_name != "":
    stmt = stmt.where(func.lower(Skater.club) == club_name.lower())
```

For queries that join on Score (most dashboard queries), change to:

```python
if club_name != "":
    stmt = stmt.where(
        or_(
            func.lower(Skater.club) == club_name.lower(),
            func.lower(Score.club) == club_name.lower(),
        )
    )
```

For queries that only use Skater (like active_skaters count), use a subquery:

```python
if club_name != "":
    stmt = stmt.where(
        or_(
            func.lower(Skater.club) == club_name.lower(),
            Skater.id.in_(
                select(Score.skater_id).where(func.lower(Score.club) == club_name.lower())
            ),
        )
    )
```

Add `from sqlalchemy import or_` to the imports if not already present.

Go through each dashboard endpoint and apply the appropriate pattern based on whether Score is already joined in the query.

- [ ] **Step 2: Commit**

```bash
git add backend/app/routes/dashboard.py
git commit -m "feat: dashboard filters by Score.club OR Skater.club"
```

---

### Task 8: Update team scoring to use Score.club

**Files:**
- Modify: `backend/app/services/team_scoring.py:139,262`

- [ ] **Step 1: Update auto_init_titular**

In `team_scoring.py` line 139, change:

```python
club = score.skater.club if score.skater else None
```

to:

```python
club = score.club or (score.skater.club if score.skater else None)
```

- [ ] **Step 2: Update compute_team_scores**

Line 262, change:

```python
club = skater.club or "\u2014"
```

to:

```python
club = score.club or skater.club or "\u2014"
```

(The variable `score` is available — it's the loop variable from `for score in scores:` at line 249.)

- [ ] **Step 3: Update test stubs**

In `backend/tests/test_team_scoring.py`, update `_make_score_stub` (line 17-46) to include `club` on FakeScore:

```python
class FakeScore:
    def __init__(self):
        self.id = score_id
        self.skater_id = skater_id
        self.skater = FakeSkater()
        self.category = category
        self.total_score = total_score
        self.rank = rank
        self.skating_level = skating_level
        self.age_group = age_group
        self.gender = gender
        self.is_titular = is_titular
        self.starting_number = starting_number
        self.club = club  # Add this line
```

- [ ] **Step 4: Run existing team scoring tests**

Run: `cd backend && uv run pytest tests/test_team_scoring.py -v`
Expected: All existing tests PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/team_scoring.py backend/tests/test_team_scoring.py
git commit -m "feat: team scoring uses Score.club instead of Skater.club"
```

---

### Task 9: Update competition analysis to use Score.club / CategoryResult.club

**Files:**
- Modify: `backend/app/services/competition_analysis.py:69`

- [ ] **Step 1: Update club lookup in competition analysis**

Line 69, change:

```python
skater_club = (cr.skater.club or "").upper()
```

to:

```python
skater_club = (cr.club or cr.skater.club or "").upper()
```

- [ ] **Step 2: Run competition analysis tests**

Run: `cd backend && uv run pytest tests/test_competition_analysis.py -v`
Expected: All PASS

- [ ] **Step 3: Commit**

```bash
git add backend/app/services/competition_analysis.py
git commit -m "feat: competition analysis uses CategoryResult.club"
```

---

### Task 10: Update report data to use Score.club

**Files:**
- Modify: `backend/app/services/report_data.py:156`

- [ ] **Step 1: Update club report skater query**

In `report_data.py`, the club report currently filters skaters by `Skater.club` (line 156):

```python
select(Skater).where(func.lower(Skater.club) == club_short.lower())
```

Change to include skaters who have scores with the matching club:

```python
select(Skater).where(
    or_(
        func.lower(Skater.club) == club_short.lower(),
        Skater.id.in_(
            select(Score.skater_id).where(func.lower(Score.club) == club_short.lower())
        ),
    )
)
```

Add the necessary imports (`from sqlalchemy import or_`, and `from app.models.score import Score`).

- [ ] **Step 2: Commit**

```bash
git add backend/app/services/report_data.py
git commit -m "feat: club report includes skaters by Score.club"
```

---

### Task 11: Update skater routes — list filter by Score.club too

**Files:**
- Modify: `backend/app/routes/skaters.py:28`

- [ ] **Step 1: Update skater list club filter**

The current filter (line 28):

```python
stmt.where(func.lower(Skater.club) == club.lower())
```

Change to:

```python
stmt.where(
    or_(
        func.lower(Skater.club) == club.lower(),
        Skater.id.in_(
            select(Score.skater_id).where(func.lower(Score.club) == club.lower())
        ),
    )
)
```

Add imports: `from sqlalchemy import or_` and `from app.models.score import Score`.

- [ ] **Step 2: Commit**

```bash
git add backend/app/routes/skaters.py
git commit -m "feat: skater list filter includes Score.club match"
```

---

### Task 12: Update database.py merge logic

**Files:**
- Modify: `backend/app/database.py:225-226`

- [ ] **Step 1: Update pair skater merge to propagate club on scores**

In `_merge_pair_skaters()`, the current code (lines 225-226) propagates club from old to new skater:

```python
if not new.club and old.club:
    new.club = old.club
```

This is fine to keep as-is — it handles `Skater.club`. But we should also note that scores already have their own club from import, so no additional change is needed for score-level club during merges.

No code change needed here. Move on.

---

### Task 13: Run full test suite

**Files:** None (verification only)

- [ ] **Step 1: Run all tests**

Run: `cd backend && uv run pytest -v`
Expected: All tests PASS

- [ ] **Step 2: Fix any failures**

If any tests fail due to the new `club` field, update them to account for `Score.club` / `CategoryResult.club`.

- [ ] **Step 3: Final commit if fixes were needed**

```bash
git add -A
git commit -m "fix: update tests for Score.club changes"
```
