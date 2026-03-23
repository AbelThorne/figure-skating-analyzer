# Skater Analytics: Season Filter & History Table Fixes

## Overview

Three improvements to the Skater Analytics page (`SkaterAnalyticsPage.tsx`):
1. Season filter to scope all data by season
2. History table column alignment fix for mixed single/multi-segment rows
3. Scrollable history table with sticky header

## 1. Season Filter

### Backend

Add an optional `season` query parameter to three endpoints:

- `GET /api/skaters/:id/scores?season=2025-2026`
- `GET /api/skaters/:id/elements?season=2025-2026`
- `GET /api/skaters/:id/category-results?season=2025-2026`

When `season` is provided, add `.where(Competition.season == season)` to the query. Note: the `get_skater_scores` endpoint currently uses `selectinload` but does not `.join(Competition)` — add the join so the where clause works.

Add a new lightweight endpoint to discover available seasons:

- `GET /api/skaters/:id/seasons` — returns `string[]` of distinct seasons

Query both `scores` and `category_results` tables to avoid missing seasons where only one type of record exists:

```sql
SELECT DISTINCT c.season
FROM (
    SELECT competition_id FROM scores WHERE skater_id = :id
    UNION
    SELECT competition_id FROM category_results WHERE skater_id = :id
) x
JOIN competitions c ON x.competition_id = c.id
WHERE c.season IS NOT NULL
ORDER BY c.season DESC
```

Register the new endpoint in the router's `route_handlers` list.

### API Client

Add optional `season?: string` parameter to:
- `api.skaters.scores(id, season?)`
- `api.skaters.elements(id, opts?: { elementType?, season? })` — use options object since both params are optional
- `api.skaters.categoryResults(id, season?)`

Add `api.skaters.seasons(id)` returning `Promise<string[]>`.

Use `URLSearchParams` for composing query strings (matching the existing pattern in `scores.list`).

### Frontend

**Loading strategy:** fetch seasons and all data queries in parallel on mount (with `season=null` meaning all). The seasons query populates the dropdown; the data queries show content immediately. When the user picks a season, the data queries refetch with the new season key.

**Default:** `selectedSeason: string | null` defaults to `null` (all seasons / "Toutes les saisons"). This shows the full picture by default.

**Dropdown placement:** in the hero section, right side, near the stat boxes. Styled as a small select with the same surface treatment as existing controls (`bg-white/15`, backdrop-blur, `text-white`).

**Label:** "Saison" with options "Toutes les saisons" (null) + each season from the endpoint.

**Empty state:** if the seasons endpoint returns an empty list, hide the dropdown entirely.

**Transition UX:** use React Query's `placeholderData: keepPreviousData` so stale data stays visible while new season data loads (no skeleton flash).

**Scope:** the filter affects everything on the page — hero stats, progression chart, KPI cards, history table, element detail panel, GOE chart, PCS radar.

## 2. History Table Alignment (Approach B)

### Problem

Single-segment competitions render directly as one row with all columns filled. Multi-segment competitions render a parent summary row (with chevron, name, date, category, overall rank, dashes for TES/PCS, combined total) then expandable segment sub-rows.

When both types appear in the same table, the visual weight and alignment differ — single-segment rows show competition name flush left while multi-segment rows indent after a chevron icon, creating misalignment.

### Fix

Always render the chevron/expand container for all rows. For single-segment rows, render an invisible placeholder of the same width as the chevron icon. This ensures competition names start at the same horizontal position regardless of row type.

Keep existing column styling for single-segment rows (TES/PCS in `text-on-surface`, total bold). The alignment fix is purely about the left-edge name position.

## 3. Scrollable History Table

Modify the existing `overflow-auto` wrapper div (line 595) to add vertical scroll constraints. Replace `overflow-auto` with `overflow-x-auto overflow-y-auto` and add `max-h-[400px]`.

Make the `<thead>` sticky:

```
<thead className="sticky top-0 z-10">
```

The `bg-surface-container-low` on the header row already provides a solid background so content won't show through.

## Files to Modify

| File | Changes |
|------|---------|
| `backend/app/routes/skaters.py` | Add `season` param to 3 endpoints + new `seasons` endpoint + register in router |
| `frontend/src/api/client.ts` | Add `season` params + `api.skaters.seasons()` |
| `frontend/src/pages/SkaterAnalyticsPage.tsx` | Season dropdown, filtered queries, table scroll, alignment fix |

## Out of Scope

- No changes to other pages
- No new backend models
- No database migrations
- No URL persistence for selected season (could add later)
- No backend tests (existing test patterns are minimal)
