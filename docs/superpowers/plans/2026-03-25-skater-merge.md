# Skater Merge Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Allow admins to merge duplicate skaters (same person, different name spellings) and prevent re-imports from recreating them.

**Architecture:** New `SkaterAlias` model maps old names to merged skaters. A merge endpoint reassigns all FK references then deletes sources. The import pipeline checks aliases before creating new skaters.

**Tech Stack:** Python/Litestar, SQLAlchemy async, React/TypeScript, TanStack Query

**Spec:** `docs/superpowers/specs/2026-03-25-skater-merge-design.md`

---

### Task 1: SkaterAlias Model

**Files:**
- Create: `backend/app/models/skater_alias.py`
- Modify: `backend/app/models/__init__.py`

- [ ] **Step 1: Create the SkaterAlias model**

Create `backend/app/models/skater_alias.py`:

```python
from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class SkaterAlias(Base):
    __tablename__ = "skater_aliases"
    __table_args__ = (
        UniqueConstraint("first_name", "last_name", name="uq_skater_alias_name"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    first_name: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    last_name: Mapped[str] = mapped_column(String(255), nullable=False)
    skater_id: Mapped[int] = mapped_column(
        ForeignKey("skaters.id", ondelete="CASCADE"), nullable=False
    )
```

- [ ] **Step 2: Register in models __init__.py**

Add to `backend/app/models/__init__.py`:

```python
from app.models.skater_alias import SkaterAlias
```

And add `"SkaterAlias"` to the `__all__` list.

- [ ] **Step 3: Verify the table is created in tests**

Run: `cd backend && PATH="/opt/homebrew/bin:$PATH" uv run pytest tests/test_integration.py -v -x --timeout=30`
Expected: PASS (the test fixture creates all tables via `Base.metadata.create_all`)

- [ ] **Step 4: Commit**

```bash
git add backend/app/models/skater_alias.py backend/app/models/__init__.py
git commit -m "feat: add SkaterAlias model"
```

---

### Task 2: Merge Endpoint — Tests

**Files:**
- Create: `backend/tests/test_skater_merge.py`

- [ ] **Step 1: Write test for basic merge**

Create `backend/tests/test_skater_merge.py`:

```python
import pytest
from app.models.skater import Skater
from app.models.score import Score
from app.models.category_result import CategoryResult
from app.models.competition import Competition
from app.models.user_skater import UserSkater
from app.models.skater_alias import SkaterAlias


@pytest.mark.asyncio
async def test_merge_skaters_basic(client, db_session, admin_token):
    """Merge reassigns scores, category results, creates alias, deletes source."""
    comp = Competition(name="Test Comp", url="http://example.com")
    db_session.add(comp)
    target = Skater(first_name="Alice", last_name="MARTIN", club="ClubA")
    source = Skater(first_name="Alice", last_name="DUPONT", nationality="FRA")
    db_session.add_all([target, source])
    await db_session.flush()

    score = Score(
        competition_id=comp.id, skater_id=source.id,
        segment="FS", category="Novice Dames", total_score=50.0,
    )
    cat_result = CategoryResult(
        competition_id=comp.id, skater_id=source.id,
        category="Novice Dames", overall_rank=1,
    )
    db_session.add_all([score, cat_result])
    await db_session.commit()

    resp = await client.post(
        "/api/skaters/merge",
        json={"target_id": target.id, "source_ids": [source.id]},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["merged"] == 1
    assert data["aliases_created"] == 1

    # Score reassigned
    await db_session.refresh(score)
    assert score.skater_id == target.id

    # Category result reassigned
    await db_session.refresh(cat_result)
    assert cat_result.skater_id == target.id

    # Source deleted
    assert await db_session.get(Skater, source.id) is None

    # Alias created
    from sqlalchemy import select
    alias = (await db_session.execute(
        select(SkaterAlias).where(SkaterAlias.last_name == "DUPONT")
    )).scalar_one()
    assert alias.skater_id == target.id

    # Metadata filled (target had no nationality, source had FRA)
    await db_session.refresh(target)
    assert target.nationality == "FRA"
    # Target's existing club preserved
    assert target.club == "ClubA"
```

- [ ] **Step 2: Write test for merge with duplicate score conflict**

Append to `backend/tests/test_skater_merge.py`:

```python
@pytest.mark.asyncio
async def test_merge_skaters_duplicate_score(client, db_session, admin_token):
    """When both target and source have a score for the same comp/cat/seg, source's is deleted."""
    comp = Competition(name="Comp", url="http://example.com/2")
    db_session.add(comp)
    target = Skater(first_name="Bob", last_name="TARGET")
    source = Skater(first_name="Bob", last_name="SOURCE")
    db_session.add_all([target, source])
    await db_session.flush()

    target_score = Score(
        competition_id=comp.id, skater_id=target.id,
        segment="SP", category="Junior Messieurs", total_score=60.0,
    )
    source_score = Score(
        competition_id=comp.id, skater_id=source.id,
        segment="SP", category="Junior Messieurs", total_score=55.0,
    )
    target_cr = CategoryResult(
        competition_id=comp.id, skater_id=target.id,
        category="Junior Messieurs", overall_rank=1,
    )
    source_cr = CategoryResult(
        competition_id=comp.id, skater_id=source.id,
        category="Junior Messieurs", overall_rank=2,
    )
    db_session.add_all([target_score, source_score, target_cr, source_cr])
    await db_session.commit()

    resp = await client.post(
        "/api/skaters/merge",
        json={"target_id": target.id, "source_ids": [source.id]},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200

    # Target's score preserved, source's deleted
    await db_session.refresh(target_score)
    assert target_score.total_score == 60.0
    assert await db_session.get(Score, source_score.id) is None

    # Target's category result preserved, source's deleted
    await db_session.refresh(target_cr)
    assert target_cr.overall_rank == 1
    assert await db_session.get(CategoryResult, source_cr.id) is None
```

- [ ] **Step 3: Write test for merge with UserSkater reassignment**

Append to `backend/tests/test_skater_merge.py`:

```python
@pytest.mark.asyncio
async def test_merge_skaters_user_skater_links(client, db_session, admin_token):
    """UserSkater links are reassigned; duplicates are deleted."""
    from app.models.user import User
    from app.auth.passwords import hash_password

    target = Skater(first_name="Claire", last_name="TARGET")
    source = Skater(first_name="Claire", last_name="SOURCE")
    db_session.add_all([target, source])
    await db_session.flush()

    user = User(
        email="parent@test.com", password_hash=hash_password("pass"),
        display_name="Parent", role="skater",
    )
    db_session.add(user)
    await db_session.flush()

    # User linked to both target and source
    link1 = UserSkater(user_id=user.id, skater_id=target.id)
    link2 = UserSkater(user_id=user.id, skater_id=source.id)
    db_session.add_all([link1, link2])
    await db_session.commit()

    resp = await client.post(
        "/api/skaters/merge",
        json={"target_id": target.id, "source_ids": [source.id]},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200

    # Source link deleted (was duplicate), target link preserved
    from sqlalchemy import select
    links = (await db_session.execute(
        select(UserSkater).where(UserSkater.user_id == user.id)
    )).scalars().all()
    assert len(links) == 1
    assert links[0].skater_id == target.id
```

- [ ] **Step 4: Write test for validation errors**

Append to `backend/tests/test_skater_merge.py`:

```python
@pytest.mark.asyncio
async def test_merge_skaters_validation(client, db_session, admin_token):
    """Validation: target must exist, source must not contain target, reader cannot merge."""
    target = Skater(first_name="D", last_name="TARGET")
    db_session.add(target)
    await db_session.commit()

    # source_ids contains target_id
    resp = await client.post(
        "/api/skaters/merge",
        json={"target_id": target.id, "source_ids": [target.id]},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 400

    # target does not exist
    resp = await client.post(
        "/api/skaters/merge",
        json={"target_id": 99999, "source_ids": [target.id]},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 404

    # empty source_ids
    resp = await client.post(
        "/api/skaters/merge",
        json={"target_id": target.id, "source_ids": []},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_merge_skaters_reader_forbidden(client, db_session, reader_token):
    """Non-admin users cannot merge."""
    resp = await client.post(
        "/api/skaters/merge",
        json={"target_id": 1, "source_ids": [2]},
        headers={"Authorization": f"Bearer {reader_token}"},
    )
    assert resp.status_code == 403
```

- [ ] **Step 5: Run tests to verify they fail**

Run: `cd backend && PATH="/opt/homebrew/bin:$PATH" uv run pytest tests/test_skater_merge.py -v -x`
Expected: FAIL (endpoint does not exist yet)

- [ ] **Step 6: Commit test file**

```bash
git add backend/tests/test_skater_merge.py
git commit -m "test: add skater merge endpoint tests (red)"
```

---

### Task 3: Merge Endpoint — Implementation

**Files:**
- Modify: `backend/app/routes/skaters.py`

- [ ] **Step 1: Add the merge endpoint**

Update the existing imports in `backend/app/routes/skaters.py`:

- Line 5: add `post` to the litestar import: `from litestar import Request, Router, get, post`
- Line 7: add `ClientException` to the exceptions import: `from litestar.exceptions import ClientException, NotFoundException`

Then add these new imports:

```python
from app.auth.guards import require_admin
from app.models.user_skater import UserSkater
from app.models.skater_alias import SkaterAlias
```

Then add the merge route handler before the `router` definition:

```python
@post("/merge")
async def merge_skaters(request: Request, session: AsyncSession, data: dict) -> dict:
    require_admin(request)

    target_id = data.get("target_id")
    source_ids = data.get("source_ids", [])

    if not source_ids:
        raise ClientException(detail="source_ids must not be empty", status_code=400)
    if target_id in source_ids:
        raise ClientException(detail="target_id must not be in source_ids", status_code=400)

    target = await session.get(Skater, target_id)
    if not target:
        raise NotFoundException(detail=f"Target skater {target_id} not found")

    sources = []
    for sid in source_ids:
        s = await session.get(Skater, sid)
        if not s:
            raise NotFoundException(detail=f"Source skater {sid} not found")
        sources.append(s)

    aliases_created = 0
    for source in sources:
        # 1. Reassign scores (delete on conflict)
        source_scores = (await session.execute(
            select(Score).where(Score.skater_id == source.id)
        )).scalars().all()
        for score in source_scores:
            existing = (await session.execute(
                select(Score).where(
                    Score.skater_id == target.id,
                    Score.competition_id == score.competition_id,
                    Score.category == score.category,
                    Score.segment == score.segment,
                )
            )).scalar_one_or_none()
            if existing:
                await session.delete(score)
            else:
                score.skater_id = target.id

        # 2. Reassign category results (delete on conflict)
        source_crs = (await session.execute(
            select(CategoryResult).where(CategoryResult.skater_id == source.id)
        )).scalars().all()
        for cr in source_crs:
            existing = (await session.execute(
                select(CategoryResult).where(
                    CategoryResult.skater_id == target.id,
                    CategoryResult.competition_id == cr.competition_id,
                    CategoryResult.category == cr.category,
                )
            )).scalar_one_or_none()
            if existing:
                await session.delete(cr)
            else:
                cr.skater_id = target.id

        # 3. Reassign user_skater links (delete on conflict)
        source_links = (await session.execute(
            select(UserSkater).where(UserSkater.skater_id == source.id)
        )).scalars().all()
        for link in source_links:
            existing = (await session.execute(
                select(UserSkater).where(
                    UserSkater.user_id == link.user_id,
                    UserSkater.skater_id == target.id,
                )
            )).scalar_one_or_none()
            if existing:
                await session.delete(link)
            else:
                link.skater_id = target.id

        # 4. Flush before deleting source (no CASCADE on Score/CategoryResult FKs)
        await session.flush()

        # 5. Fill blank metadata
        if not target.nationality and source.nationality:
            target.nationality = source.nationality
        if not target.club and source.club:
            target.club = source.club
        if not target.birth_year and source.birth_year:
            target.birth_year = source.birth_year

        # 6. Create alias
        existing_alias = (await session.execute(
            select(SkaterAlias).where(
                SkaterAlias.first_name == source.first_name,
                SkaterAlias.last_name == source.last_name,
            )
        )).scalar_one_or_none()
        if existing_alias and existing_alias.skater_id != target.id:
            raise ClientException(
                detail=f"Alias conflict: {source.first_name} {source.last_name} is already an alias for skater {existing_alias.skater_id}",
                status_code=400,
            )
        if not existing_alias:
            session.add(SkaterAlias(
                first_name=source.first_name,
                last_name=source.last_name,
                skater_id=target.id,
            ))
            aliases_created += 1

        # 7. Delete source
        await session.delete(source)

    await session.commit()
    return {"merged": len(sources), "aliases_created": aliases_created}
```

- [ ] **Step 2: Register merge_skaters in the router**

In the `router` definition at the bottom of `skaters.py`, add `merge_skaters` to `route_handlers`:

```python
router = Router(
    path="/api/skaters",
    route_handlers=[list_skaters, get_skater, get_skater_elements, get_skater_scores, get_skater_category_results, get_skater_seasons, merge_skaters],
    dependencies={"session": Provide(get_session)},
)
```

- [ ] **Step 3: Run merge tests**

Run: `cd backend && PATH="/opt/homebrew/bin:$PATH" uv run pytest tests/test_skater_merge.py -v -x`
Expected: ALL PASS

- [ ] **Step 4: Run full test suite**

Run: `cd backend && PATH="/opt/homebrew/bin:$PATH" uv run pytest -v --timeout=30`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/routes/skaters.py
git commit -m "feat: add POST /api/skaters/merge endpoint"
```

---

### Task 4: Alias Lookup in Import Pipeline

**Files:**
- Modify: `backend/app/services/import_service.py`
- Create test in: `backend/tests/test_skater_merge.py` (append)

- [ ] **Step 1: Write failing test for alias resolution during import**

Append to `backend/tests/test_skater_merge.py`:

```python
@pytest.mark.asyncio
async def test_get_or_create_skater_uses_alias(db_session):
    """_get_or_create_skater should resolve aliases instead of creating new skaters."""
    from app.services.import_service import _get_or_create_skater

    # Create target skater and alias
    target = Skater(first_name="Emma", last_name="MARTIN")
    db_session.add(target)
    await db_session.flush()

    alias = SkaterAlias(first_name="Emma", last_name="DUPONT", skater_id=target.id)
    db_session.add(alias)
    await db_session.commit()

    # Lookup with the aliased name should return the target
    result = await _get_or_create_skater(db_session, "Emma DUPONT", None, None)
    assert result.id == target.id
    assert result.last_name == "MARTIN"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && PATH="/opt/homebrew/bin:$PATH" uv run pytest tests/test_skater_merge.py::test_get_or_create_skater_uses_alias -v -x`
Expected: FAIL (creates a new skater instead of resolving alias)

- [ ] **Step 3: Add alias lookup to _get_or_create_skater**

In `backend/app/services/import_service.py`, add the import at the top:

```python
from app.models.skater_alias import SkaterAlias
```

Then in `_get_or_create_skater`, insert the alias check block after the pairs migration block (after the `if not skater and first_name == "" and " / " in last_name:` block ends at line 54) and before the `if not skater:` block that creates a new skater (line 56):

```python
    # Check aliases (from merged skaters)
    if not skater:
        alias_stmt = select(SkaterAlias).where(
            SkaterAlias.first_name == first_name,
            SkaterAlias.last_name == last_name,
        )
        alias = (await session.execute(alias_stmt)).scalar_one_or_none()
        if alias:
            skater = await session.get(Skater, alias.skater_id)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && PATH="/opt/homebrew/bin:$PATH" uv run pytest tests/test_skater_merge.py::test_get_or_create_skater_uses_alias -v -x`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/import_service.py backend/tests/test_skater_merge.py
git commit -m "feat: resolve skater aliases during import"
```

---

### Task 5: Orphan Cleanup Guard

**Files:**
- Modify: `backend/app/services/import_service.py`

- [ ] **Step 1: Extract orphan query as a reusable function and update it**

In `backend/app/services/import_service.py`, add a helper function (before `run_import`) and update the orphan cleanup block to use it:

Add near the top-level (after imports):

```python
def _orphan_skater_query():
    """Query for skaters with no scores, no category results, and no aliases."""
    from sqlalchemy import exists
    return select(Skater).where(
        ~exists(select(Score.id).where(Score.skater_id == Skater.id)),
        ~exists(select(CategoryResult.id).where(CategoryResult.skater_id == Skater.id)),
        ~exists(select(SkaterAlias.id).where(SkaterAlias.skater_id == Skater.id)),
    )
```

Then replace the existing orphan block in `run_import` (around line 204-209):

Replace:
```python
    from sqlalchemy import exists
    orphan_stmt = select(Skater).where(
        ~exists(select(Score.id).where(Score.skater_id == Skater.id)),
        ~exists(select(CategoryResult.id).where(CategoryResult.skater_id == Skater.id)),
    )
```

With:
```python
    orphan_stmt = _orphan_skater_query()
```

- [ ] **Step 2: Write test for orphan cleanup with alias target**

Append to `backend/tests/test_skater_merge.py`:

```python
@pytest.mark.asyncio
async def test_orphan_cleanup_preserves_alias_targets(db_session):
    """Skaters that are alias targets should not be deleted as orphans."""
    from app.services.import_service import _orphan_skater_query

    # Create a skater with no scores but with an alias pointing to it
    target = Skater(first_name="Zoe", last_name="TARGET", club="Club")
    db_session.add(target)
    await db_session.flush()

    alias = SkaterAlias(first_name="Zoe", last_name="OLD-NAME", skater_id=target.id)
    db_session.add(alias)
    await db_session.commit()

    target_id = target.id

    # Use the actual production orphan query
    orphans = (await db_session.execute(_orphan_skater_query())).scalars().all()

    # Target should NOT be in orphans because it has an alias
    orphan_ids = [o.id for o in orphans]
    assert target_id not in orphan_ids
```

- [ ] **Step 3: Run the test**

Run: `cd backend && PATH="/opt/homebrew/bin:$PATH" uv run pytest tests/test_skater_merge.py::test_orphan_cleanup_preserves_alias_targets -v -x`
Expected: PASS

- [ ] **Step 4: Run full test suite**

Run: `cd backend && PATH="/opt/homebrew/bin:$PATH" uv run pytest -v --timeout=30`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/import_service.py backend/tests/test_skater_merge.py
git commit -m "fix: exclude alias targets from orphan cleanup"
```

---

### Task 6: Frontend — API Client Addition

**Files:**
- Modify: `frontend/src/api/client.ts`

- [ ] **Step 1: Add merge method to skaters API**

In `frontend/src/api/client.ts`, in the `skaters` object (around line 634), add `merge` after the existing `elements` method:

```typescript
    merge: (targetId: number, sourceIds: number[]) =>
      request<{ merged: number; aliases_created: number }>("/skaters/merge", {
        method: "POST",
        body: JSON.stringify({ target_id: targetId, source_ids: sourceIds }),
      }),
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/api/client.ts
git commit -m "feat: add skaters.merge API client method"
```

---

### Task 7: Frontend — Merge UI in Settings Page

**Files:**
- Modify: `frontend/src/pages/SettingsPage.tsx`

- [ ] **Step 1: Add merge state and mutation**

In `frontend/src/pages/SettingsPage.tsx`, add merge state variables after the existing state declarations (around line 253, after the database reset state):

```typescript
  // --- Skater merge ---
  const [mergeSearch, setMergeSearch] = useState("");
  const [debouncedMergeSearch, setDebouncedMergeSearch] = useState("");
  const [mergeSelected, setMergeSelected] = useState<Skater[]>([]);
  const [mergeTargetId, setMergeTargetId] = useState<number | null>(null);
  const [showMergeConfirm, setShowMergeConfirm] = useState(false);
  const [mergeSuccess, setMergeSuccess] = useState("");

  useEffect(() => {
    const timer = setTimeout(() => setDebouncedMergeSearch(mergeSearch), 300);
    return () => clearTimeout(timer);
  }, [mergeSearch]);

  const { data: mergeResults } = useQuery({
    queryKey: ["skaters", "merge-search", debouncedMergeSearch],
    queryFn: () => api.skaters.list({ search: debouncedMergeSearch }),
    enabled: debouncedMergeSearch.length >= 2,
  });

  const mergeMutation = useMutation({
    mutationFn: () => {
      const sourceIds = mergeSelected
        .filter((s) => s.id !== mergeTargetId)
        .map((s) => s.id);
      return api.skaters.merge(mergeTargetId!, sourceIds);
    },
    onSuccess: (data) => {
      qc.invalidateQueries({ queryKey: ["skaters"] });
      setMergeSelected([]);
      setMergeTargetId(null);
      setShowMergeConfirm(false);
      setMergeSuccess(`${data.merged} patineur(s) fusionné(s)`);
      setTimeout(() => setMergeSuccess(""), 3000);
    },
  });
```

Add the `Skater` type import at the top of the file — update the existing import:

```typescript
import { api, type UserRecord, type ImportResult, type Skater } from "../api/client";
```

- [ ] **Step 2: Add merge UI section**

In the JSX, add a new `<section>` block **before** the "Danger zone" section (before line 814 `{/* Danger zone */}`):

```tsx
      {/* Skater merge */}
      <section className="bg-surface-container-lowest rounded-2xl p-6 shadow-arctic">
        <h2 className="font-headline font-bold text-on-surface text-lg mb-2">
          Fusionner des patineurs
        </h2>
        <p className="text-on-surface-variant text-xs mb-4">
          Regroupez les scores de patineurs en doublon (nom différent, même personne).
        </p>

        {mergeSuccess && (
          <div className="mb-4 px-4 py-2 bg-primary/10 text-primary text-sm rounded-xl font-medium">
            {mergeSuccess}
          </div>
        )}

        {/* Search */}
        <div className="relative max-w-sm">
          <span className="material-symbols-outlined absolute left-3 top-1/2 -translate-y-1/2 text-on-surface-variant text-[18px] pointer-events-none">
            search
          </span>
          <input
            placeholder="Rechercher un patineur…"
            value={mergeSearch}
            onChange={(e) => setMergeSearch(e.target.value)}
            className="w-full bg-surface-container-high rounded-full py-2 pl-10 pr-4 text-sm font-body text-on-surface focus:outline-none focus:ring-2 focus:ring-primary"
          />
        </div>

        {/* Search results */}
        {mergeResults && mergeSearch.length >= 2 && (
          <div className="mt-2 bg-surface-container rounded-lg shadow-md max-h-40 overflow-y-auto max-w-sm">
            {mergeResults
              .filter((s) => !mergeSelected.some((sel) => sel.id === s.id))
              .map((s) => (
                <button
                  key={s.id}
                  type="button"
                  onClick={() => {
                    const updated = [...mergeSelected, s];
                    setMergeSelected(updated);
                    if (!mergeTargetId) setMergeTargetId(s.id);
                    setMergeSearch("");
                  }}
                  className="w-full text-left px-3 py-2 text-sm hover:bg-surface-container-high transition-colors"
                >
                  {s.first_name} {s.last_name}
                  {s.club && (
                    <span className="text-on-surface-variant ml-2 text-xs">({s.club})</span>
                  )}
                </button>
              ))}
            {mergeResults.filter((s) => !mergeSelected.some((sel) => sel.id === s.id)).length === 0 && (
              <p className="px-3 py-2 text-xs text-on-surface-variant">Aucun résultat</p>
            )}
          </div>
        )}

        {/* Selected skaters */}
        {mergeSelected.length > 0 && (
          <div className="mt-4 space-y-2">
            <label className="text-xs font-bold text-on-surface-variant uppercase tracking-wider">
              Patineurs sélectionnés — choisissez le patineur principal
            </label>
            {mergeSelected.map((s) => (
              <div
                key={s.id}
                className="flex items-center gap-3 p-2 bg-surface-container-low rounded-xl"
              >
                <input
                  type="radio"
                  name="merge-target"
                  checked={mergeTargetId === s.id}
                  onChange={() => setMergeTargetId(s.id)}
                  className="accent-primary"
                />
                <span className="text-sm text-on-surface font-medium">
                  {s.first_name} {s.last_name}
                </span>
                {s.club && (
                  <span className="text-xs text-on-surface-variant">({s.club})</span>
                )}
                <button
                  type="button"
                  onClick={() => {
                    const updated = mergeSelected.filter((sel) => sel.id !== s.id);
                    setMergeSelected(updated);
                    if (mergeTargetId === s.id) {
                      setMergeTargetId(updated[0]?.id ?? null);
                    }
                  }}
                  className="ml-auto text-on-surface-variant hover:text-error"
                >
                  <span className="material-symbols-outlined text-sm">close</span>
                </button>
              </div>
            ))}

            {mergeSelected.length >= 2 && (
              <div className="mt-3">
                {showMergeConfirm ? (
                  <div className="p-3 bg-surface-container rounded-xl space-y-3">
                    <p className="text-sm text-on-surface">
                      Fusionner {mergeSelected.length} patineurs en{" "}
                      <strong>
                        {mergeSelected.find((s) => s.id === mergeTargetId)?.first_name}{" "}
                        {mergeSelected.find((s) => s.id === mergeTargetId)?.last_name}
                      </strong>{" "}
                      ? Les scores seront regroupés.
                    </p>
                    <div className="flex gap-2">
                      <button
                        onClick={() => mergeMutation.mutate()}
                        disabled={mergeMutation.isPending}
                        className="px-4 py-2 bg-primary text-on-primary rounded-xl text-sm font-bold hover:bg-primary/90 transition-colors disabled:opacity-50"
                      >
                        {mergeMutation.isPending ? "Fusion..." : "Confirmer"}
                      </button>
                      <button
                        onClick={() => setShowMergeConfirm(false)}
                        className="px-4 py-2 text-on-surface-variant text-sm"
                      >
                        Annuler
                      </button>
                    </div>
                    {mergeMutation.isError && (
                      <p className="text-error text-xs">{String(mergeMutation.error)}</p>
                    )}
                  </div>
                ) : (
                  <button
                    onClick={() => setShowMergeConfirm(true)}
                    className="px-4 py-2 bg-primary text-on-primary rounded-xl text-sm font-bold hover:bg-primary/90 transition-colors flex items-center gap-2"
                  >
                    <span className="material-symbols-outlined text-sm">merge</span>
                    Fusionner
                  </button>
                )}
              </div>
            )}
          </div>
        )}
      </section>
```

- [ ] **Step 3: Verify frontend builds**

Run: `cd frontend && PATH="/opt/homebrew/bin:$PATH" npm run build`
Expected: Build succeeds with no errors

- [ ] **Step 4: Commit**

```bash
git add frontend/src/pages/SettingsPage.tsx
git commit -m "feat: add skater merge UI to settings page"
```

---

### Task 8: Final Verification

- [ ] **Step 1: Run full backend test suite**

Run: `cd backend && PATH="/opt/homebrew/bin:$PATH" uv run pytest -v --timeout=30`
Expected: ALL PASS

- [ ] **Step 2: Run frontend build**

Run: `cd frontend && PATH="/opt/homebrew/bin:$PATH" npm run build`
Expected: Build succeeds

- [ ] **Step 3: Verify Docker build**

Run: `docker compose build`
Expected: Builds successfully
