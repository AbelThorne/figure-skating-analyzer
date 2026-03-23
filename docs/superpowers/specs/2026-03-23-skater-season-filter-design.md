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

Each endpoint already joins on `Competition`. When `season` is provided, add `.where(Competition.season == season)` to the query.

### API Client

Add optional `season?: string` parameter to:
- `api.skaters.scores(id, season?)`
- `api.skaters.elements(id, elementType?, season?)`
- `api.skaters.categoryResults(id, season?)`

### Frontend

**Season discovery:** derive available seasons from the scores data. Fetch scores without a season filter first to discover seasons, then use the selected season to filter all three queries.

Actually, simpler approach: add a new lightweight endpoint or derive seasons from the initial unfiltered scores fetch. Since scores already include `competition_date`, we can extract seasons client-side from the full scores list on first load. But this defeats the purpose of filtering.

Better approach: always fetch scores/elements/categoryResults with the season param. To populate the season dropdown, extract distinct seasons from the skater's competitions. Add a small endpoint:

- `GET /api/skaters/:id/seasons` — returns `string[]` of distinct seasons

This is a simple query: `SELECT DISTINCT c.season FROM scores s JOIN competitions c ON s.competition_id = c.id WHERE s.skater_id = :id AND c.season IS NOT NULL ORDER BY c.season DESC`.

**Dropdown placement:** in the hero section, right side, near the stat boxes. Styled as a small select with the same surface treatment as existing controls (bg-white/15, backdrop-blur, text-white).

**State:** `selectedSeason: string | null` (null = all seasons). The react-query keys include the season so data refetches on change.

**Scope:** the filter affects everything on the page — hero stats, progression chart, KPI cards, history table, element detail panel, GOE chart, PCS radar.

## 2. History Table Alignment (Approach B)

### Problem

Single-segment competitions render directly as one row with all columns filled. Multi-segment competitions render a parent summary row (with chevron, name, date, category, overall rank, dashes for TES/PCS, combined total) then expandable segment sub-rows.

When both types appear in the same table, the visual weight and alignment differ — single-segment rows show TES/PCS numbers where multi-segment parent rows show dashes, creating a jagged look.

### Fix

Make single-segment rows visually match multi-segment parent rows:

- Single-segment rows keep showing all data in one row (no expand/collapse needed)
- But style the row like a parent row: competition name without chevron indent (align left edge with multi-segment names by adding equivalent left padding to compensate for the missing chevron icon)
- TES and PCS columns: show values but in the same lighter `text-on-surface-variant` style
- Total column: bold, same as multi-segment parent total
- Rank column: use the same badge/number styling as multi-segment overall rank

The key alignment fix: multi-segment parent rows have a chevron icon + name with `gap-1.5`. Single-segment rows should add equivalent padding-left (~24px for the 16px icon + gap) so the competition name text starts at the same horizontal position. Actually, looking at the code, multi-segment rows use `flex items-center gap-1.5` with a material icon. Single-segment rows just have the link. So adding `pl-[26px]` (icon width 16px + gap 6px + original padding) to the single-segment name cell, or wrapping in the same flex container with an invisible spacer, would align them.

Simpler: always render the chevron container but for single-segment rows, use an invisible placeholder of the same width.

## 3. Scrollable History Table

Wrap the history table in a scrollable container:

```
max-h-[400px] overflow-y-auto
```

Make the `<thead>` sticky:

```
<thead className="sticky top-0 z-10">
```

The `bg-surface-container-low` on the header row already provides a solid background so content won't show through.

## Files to Modify

| File | Changes |
|------|---------|
| `backend/app/routes/skaters.py` | Add `season` param to 3 endpoints + new `seasons` endpoint |
| `frontend/src/api/client.ts` | Add `season` params + `api.skaters.seasons()` |
| `frontend/src/pages/SkaterAnalyticsPage.tsx` | Season dropdown, filtered queries, table scroll, alignment fix |

## Out of Scope

- No changes to other pages
- No new backend models
- No database migrations
