# Skater Season Filter & History Table Fixes — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add season filtering to the skater analytics page, fix competition history table alignment, and make the history table scrollable.

**Architecture:** Backend gets a `season` query param on 3 existing endpoints + 1 new seasons-discovery endpoint. Frontend adds a dropdown in the hero that controls all data queries via React Query key invalidation.

**Tech Stack:** Python/Litestar + SQLAlchemy (backend), React/TypeScript + Tailwind CSS + @tanstack/react-query v5 (frontend)

**Spec:** `docs/superpowers/specs/2026-03-23-skater-season-filter-design.md`

---

### Task 1: Backend — Add `season` param to `get_skater_scores`

**Files:**
- Modify: `backend/app/routes/skaters.py:92-124`

- [ ] **Step 1: Add `season` parameter and join**

Add `season: Optional[str] = None` param. Add `.join(Score.competition)` to the query. When `season` is provided, add `.where(Competition.season == season)`.

```python
@get("/{skater_id:int}/scores")
async def get_skater_scores(skater_id: int, session: AsyncSession, season: Optional[str] = None) -> list[dict]:
    skater = await session.get(Skater, skater_id)
    if not skater:
        raise NotFoundException(f"Skater {skater_id} not found")

    stmt = (
        select(Score)
        .where(Score.skater_id == skater_id)
        .join(Score.competition)
        .options(selectinload(Score.competition))
        .order_by(Score.id)
    )
    if season:
        stmt = stmt.where(Competition.season == season)

    result = await session.execute(stmt)
    scores = result.scalars().all()
    return [
        {
            "id": s.id,
            "competition_id": s.competition_id,
            "competition_name": s.competition.name if s.competition else None,
            "competition_date": s.competition.date.isoformat() if s.competition and s.competition.date else None,
            "segment": s.segment,
            "category": s.category,
            "starting_number": s.starting_number,
            "rank": s.rank,
            "total_score": s.total_score,
            "technical_score": s.technical_score,
            "component_score": s.component_score,
            "deductions": s.deductions,
            "components": s.components,
            "elements": s.elements,
            "event_date": s.event_date.isoformat() if s.event_date else None,
        }
        for s in scores
    ]
```

- [ ] **Step 2: Verify manually**

Run: `cd backend && PATH="/opt/homebrew/bin:$PATH" uv run python -c "from app.routes.skaters import get_skater_scores; print('OK')"`

- [ ] **Step 3: Commit**

```bash
git add backend/app/routes/skaters.py
git commit -m "feat: add season filter to skater scores endpoint"
```

---

### Task 2: Backend — Add `season` param to `get_skater_elements`

**Files:**
- Modify: `backend/app/routes/skaters.py:48-89`

- [ ] **Step 1: Add `season` parameter**

Add `season: Optional[str] = None` param. The query already joins on `Competition`. When `season` is provided, add `.where(Competition.season == season)`.

```python
@get("/{skater_id:int}/elements")
async def get_skater_elements(
    skater_id: int,
    session: AsyncSession,
    element_type: Optional[str] = None,
    season: Optional[str] = None,
) -> list[dict]:
    skater = await session.get(Skater, skater_id)
    if not skater:
        raise NotFoundException(f"Skater {skater_id} not found")

    stmt = (
        select(Score)
        .where(Score.skater_id == skater_id)
        .options(selectinload(Score.competition))
        .order_by(Competition.date)
        .join(Score.competition)
    )
    if season:
        stmt = stmt.where(Competition.season == season)

    result = await session.execute(stmt)
    scores = result.scalars().all()

    records = []
    for s in scores:
        if not s.elements:
            continue
        for element in s.elements:
            name = element.get("name", "")
            if element_type is not None and not name.lower().startswith(element_type.lower()):
                continue
            records.append({
                "score_id": s.id,
                "competition_id": s.competition_id,
                "competition_name": s.competition.name if s.competition else None,
                "competition_date": s.competition.date.isoformat() if s.competition and s.competition.date else None,
                "segment": s.segment,
                "category": s.category,
                "element_name": name,
                "base_value": element.get("base_value"),
                "goe": element.get("goe"),
                "judges": element.get("judge_goe") or element.get("judges"),
                "total": element.get("score") or element.get("total"),
                "markers": element.get("markers") or [],
            })
    return records
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/routes/skaters.py
git commit -m "feat: add season filter to skater elements endpoint"
```

---

### Task 3: Backend — Add `season` param to `get_skater_category_results`

**Files:**
- Modify: `backend/app/routes/skaters.py:127-155`

- [ ] **Step 1: Add `season` parameter**

The query already joins on `Competition`. Add `season: Optional[str] = None` and filter when provided.

```python
@get("/{skater_id:int}/category-results")
async def get_skater_category_results(skater_id: int, session: AsyncSession, season: Optional[str] = None) -> list[dict]:
    skater = await session.get(Skater, skater_id)
    if not skater:
        raise NotFoundException(f"Skater {skater_id} not found")

    stmt = (
        select(CategoryResult)
        .where(CategoryResult.skater_id == skater_id)
        .options(selectinload(CategoryResult.competition))
        .join(CategoryResult.competition)
        .order_by(Competition.date.desc())
    )
    if season:
        stmt = stmt.where(Competition.season == season)

    result = await session.execute(stmt)
    cat_results = result.scalars().all()
    return [
        {
            "id": cr.id,
            "competition_id": cr.competition_id,
            "competition_name": cr.competition.name if cr.competition else None,
            "competition_date": cr.competition.date.isoformat() if cr.competition and cr.competition.date else None,
            "category": cr.category,
            "overall_rank": cr.overall_rank,
            "combined_total": cr.combined_total,
            "segment_count": cr.segment_count,
            "sp_rank": cr.sp_rank,
            "fs_rank": cr.fs_rank,
        }
        for cr in cat_results
    ]
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/routes/skaters.py
git commit -m "feat: add season filter to skater category results endpoint"
```

---

### Task 4: Backend — Add `GET /api/skaters/:id/seasons` endpoint

**Files:**
- Modify: `backend/app/routes/skaters.py` (add new handler + register in router)

- [ ] **Step 1: Add the seasons endpoint**

Query distinct seasons from both `scores` and `category_results` tables via union, joined to `competitions`.

```python
# Update the existing import: from sqlalchemy import func, select
# to: from sqlalchemy import func, select, union_all

@get("/{skater_id:int}/seasons")
async def get_skater_seasons(skater_id: int, session: AsyncSession) -> list[str]:
    skater = await session.get(Skater, skater_id)
    if not skater:
        raise NotFoundException(f"Skater {skater_id} not found")

    # Union of competition_ids from both scores and category_results
    score_comp_ids = select(Score.competition_id).where(Score.skater_id == skater_id)
    cat_comp_ids = select(CategoryResult.competition_id).where(CategoryResult.skater_id == skater_id)
    all_comp_ids = union_all(score_comp_ids, cat_comp_ids).subquery()

    stmt = (
        select(Competition.season)
        .join(all_comp_ids, Competition.id == all_comp_ids.c.competition_id)
        .where(Competition.season.isnot(None))
        .distinct()
        .order_by(Competition.season.desc())
    )
    result = await session.execute(stmt)
    return [row[0] for row in result.all()]
```

- [ ] **Step 2: Register in router**

Update the `Router()` at the bottom of the file to include `get_skater_seasons`:

```python
router = Router(
    path="/api/skaters",
    route_handlers=[list_skaters, get_skater, get_skater_elements, get_skater_scores, get_skater_category_results, get_skater_seasons],
    dependencies={"session": Provide(get_session)},
)
```

- [ ] **Step 3: Verify import works**

Run: `cd backend && PATH="/opt/homebrew/bin:$PATH" uv run python -c "from app.routes.skaters import get_skater_seasons; print('OK')"`

- [ ] **Step 4: Commit**

```bash
git add backend/app/routes/skaters.py
git commit -m "feat: add skater seasons discovery endpoint"
```

---

### Task 5: Frontend — Update API client with season params

**Files:**
- Modify: `frontend/src/api/client.ts:445-458`

- [ ] **Step 1: Update `api.skaters` methods**

Add `season` param to `scores`, `categoryResults`, and update `elements` to use an options object. Add `seasons` method.

```typescript
  skaters: {
    list: (club?: string) => {
      const qs = club ? `?club=${encodeURIComponent(club)}` : "";
      return request<Skater[]>(`/skaters/${qs}`);
    },
    get: (id: number) => request<Skater>(`/skaters/${id}`),
    seasons: (id: number) => request<string[]>(`/skaters/${id}/seasons`),
    scores: (id: number, season?: string) => {
      const qs = new URLSearchParams();
      if (season) qs.set("season", season);
      const query = qs.toString() ? `?${qs}` : "";
      return request<Score[]>(`/skaters/${id}/scores${query}`);
    },
    categoryResults: (id: number, season?: string) => {
      const qs = new URLSearchParams();
      if (season) qs.set("season", season);
      const query = qs.toString() ? `?${qs}` : "";
      return request<CategoryResult[]>(`/skaters/${id}/category-results${query}`);
    },
    elements: (id: number, opts?: { elementType?: string; season?: string }) => {
      const qs = new URLSearchParams();
      if (opts?.elementType) qs.set("element_type", opts.elementType);
      if (opts?.season) qs.set("season", opts.season);
      const query = qs.toString() ? `?${qs}` : "";
      return request<Element[]>(`/skaters/${id}/elements${query}`);
    },
  },
```

- [ ] **Step 2: Update any callers of `api.skaters.elements` that pass `elementType`**

Search for existing calls. The current page passes no `elementType`, so no callers to update.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/api/client.ts
git commit -m "feat: add season params to skater API client methods"
```

---

### Task 6: Frontend — Add season dropdown and filtered queries

**Files:**
- Modify: `frontend/src/pages/SkaterAnalyticsPage.tsx`

- [ ] **Step 1: Add imports and state**

Add `keepPreviousData` import and season state:

```typescript
import { useQuery, keepPreviousData } from "@tanstack/react-query";

// Inside component, after skaterId:
const [selectedSeason, setSelectedSeason] = useState<string | null>(null);
```

- [ ] **Step 2: Add seasons query**

```typescript
const { data: seasons } = useQuery({
  queryKey: ["skater-seasons", skaterId],
  queryFn: () => api.skaters.seasons(skaterId),
});
```

- [ ] **Step 3: Update existing data queries to include season**

Update the three data queries to pass season and use `placeholderData`:

```typescript
const { data: scores, isLoading: loadingScores } = useQuery({
  queryKey: ["skater-scores", skaterId, selectedSeason],
  queryFn: () => api.skaters.scores(skaterId, selectedSeason ?? undefined),
  placeholderData: keepPreviousData,
});

const { data: elements, isLoading: loadingElements } = useQuery({
  queryKey: ["skater-elements", skaterId, selectedSeason],
  queryFn: () => api.skaters.elements(skaterId, { season: selectedSeason ?? undefined }),
  placeholderData: keepPreviousData,
});

const { data: categoryResults, isLoading: loadingCatResults } = useQuery({
  queryKey: ["skater-category-results", skaterId, selectedSeason],
  queryFn: () => api.skaters.categoryResults(skaterId, selectedSeason ?? undefined),
  placeholderData: keepPreviousData,
});
```

- [ ] **Step 4: Add season dropdown in the hero section**

Insert a season select inside the hero `<div>`, in the right area near the stat boxes. Place it before the `HeroStatBox` flex container:

```tsx
{/* In the hero section, inside the flex container with stat boxes */}
{/* Replace existing <div className="flex gap-3 shrink-0"> at line 432 with: */}
<div className="flex gap-3 shrink-0 items-center">
  {seasons && seasons.length > 0 && (
    <select
      value={selectedSeason ?? ""}
      onChange={(e) => setSelectedSeason(e.target.value || null)}
      className="bg-white/15 backdrop-blur-sm rounded-xl px-4 py-2.5 text-sm text-white font-bold font-headline appearance-none cursor-pointer focus:outline-none focus:ring-2 focus:ring-white/30"
    >
      <option value="" className="text-on-surface bg-surface">Toutes les saisons</option>
      {seasons.map((s) => (
        <option key={s} value={s} className="text-on-surface bg-surface">{s}</option>
      ))}
    </select>
  )}
  <HeroStatBox
    label="Meilleur score"
    value={bestTss != null ? bestTss.toFixed(2) : "—"}
  />
  <HeroStatBox
    label="Compétitions"
    value={String(historyRows.length)}
  />
</div>
```

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/SkaterAnalyticsPage.tsx
git commit -m "feat: add season filter dropdown to skater analytics page"
```

---

### Task 7: Frontend — Fix history table column alignment

**Files:**
- Modify: `frontend/src/pages/SkaterAnalyticsPage.tsx` (history table section, ~lines 614-756)

- [ ] **Step 1: Add invisible spacer for single-segment rows**

In the single-segment branch (the `else` of `isMultiSegment`), wrap the competition link in the same flex container used by multi-segment rows, but with an invisible spacer instead of the chevron:

Replace the single-segment `<td>` for competition name (lines 700-708):

```tsx
<td className="px-3 py-2 text-sm text-on-surface">
  <div className="flex items-center gap-1.5">
    <span className="material-symbols-outlined text-sm leading-none invisible">
      chevron_right
    </span>
    <Link
      to={`/competitions/${s.competition_id}`}
      className="text-primary hover:underline font-medium"
    >
      {s.competition_name ?? `#${s.competition_id}`}
    </Link>
  </div>
</td>
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/pages/SkaterAnalyticsPage.tsx
git commit -m "fix: align single-segment competition names with multi-segment rows"
```

---

### Task 8: Frontend — Make history table scrollable with sticky header

**Files:**
- Modify: `frontend/src/pages/SkaterAnalyticsPage.tsx` (history table wrapper, ~line 595)

- [ ] **Step 1: Update the overflow wrapper**

Change the existing `<div className="overflow-auto">` wrapping the table to:

```tsx
<div className="overflow-x-auto overflow-y-auto max-h-[400px]">
```

- [ ] **Step 2: Make thead sticky**

Update the `<thead>` element to add sticky positioning:

```tsx
<thead className="sticky top-0 z-10">
```

The existing `bg-surface-container-low` on the `<tr>` inside provides a solid background.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/pages/SkaterAnalyticsPage.tsx
git commit -m "feat: make competition history table scrollable with sticky header"
```

---

### Task 9: Smoke test

- [ ] **Step 1: Start backend and frontend**

```bash
cd backend && PATH="/opt/homebrew/bin:$PATH" uv run litestar run --reload &
cd frontend && PATH="/opt/homebrew/bin:$PATH" npm run dev &
```

- [ ] **Step 2: Verify in browser**

1. Navigate to a skater page
2. Verify season dropdown appears in hero (if competitions have seasons)
3. Select a specific season — all data should update
4. Select "Toutes les saisons" — back to full view
5. Check history table: single-segment and multi-segment names align
6. Check history table scrolls vertically when tall enough
7. Check sticky header stays visible while scrolling

- [ ] **Step 3: Final commit if any fixes needed**
