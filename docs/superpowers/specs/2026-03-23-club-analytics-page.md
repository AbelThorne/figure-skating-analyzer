# Club Analytics Page — Design Spec

**Date**: 2026-03-23
**Replaces**: The current "Statistiques" tab (`StatsPage.tsx`), which duplicates functionality already present in the skater detail page.

## Overview

Repurpose the "Statistiques" tab into a **club-level analytics page** with three sections:

1. **Progression ranking** — which skaters improved the most this season
2. **Side-by-side comparison** — overlay 2-3 skaters' score curves with benchmark bands
3. **Element mastery tracker** — club-wide jump success rates and spin/step level distributions

The tab is renamed from "STATISTIQUES" to "CLUB" (route stays `/stats`).

## Foundation: Category Parsing

### Problem

The `category` field on `Score` and `CategoryResult` is a raw compound string like `"R2 Minime Femme"` or `"R3 A Min-Nov Serie 1 Femme"`. Benchmarking and filtering require structured access to level, age group, and gender.

### New Fields

Add to both `Score` and `CategoryResult` models:

| Field | Type | Examples |
|-------|------|---------|
| `skating_level` | `VARCHAR(20)`, nullable | `National`, `Fédéral`, `R1`, `R2`, `R3 A`, `R3 B`, `R3 C`, `Adulte Bronze`, `Adulte Argent`, `Adulte Or`, `International` |
| `age_group` | `VARCHAR(30)`, nullable | `Babies`, `Poussin`, `Benjamin`, `Minime`, `Novice`, `Junior`, `Senior`, `Junior-Senior`, `Minime-Novice` |
| `gender` | `VARCHAR(10)`, nullable | `Femme`, `Homme` |

### Parser

New module `backend/app/services/category_parser.py` with a pure function:

```python
def parse_category(raw: str) -> dict:
    """Parse a raw category string into structured fields.

    Returns {"skating_level": ..., "age_group": ..., "gender": ...}
    with None for any field that cannot be determined.
    """
```

Rules:
- **Level tokens** (checked in order, first match wins):
  - `National` or `D1` → `National`
  - `Fédéral` or `Fédérale` or `D2` → `Fédéral`
  - `R1` or `D3` → `R1`
  - `R2` → `R2`
  - `R3 A` → `R3 A`
  - `R3 B` → `R3 B`
  - `R3 C` → `R3 C`
  - `Adulte Bronze` → `Adulte Bronze` (age_group set to `Adulte`)
  - `Adulte Argent` → `Adulte Argent` (age_group set to `Adulte`)
  - `Adulte Or` → `Adulte Or` (age_group set to `Adulte`)
  - If no level token found → `None` (logged as a warning for debugging; likely International but could be a typo)
- **Age group tokens** (after stripping `Serie X`):
  - For `Adulte` levels → `Adulte`
  - `Jun-Sen` or `Junior-Senior` → `Junior-Senior`
  - `Min-Nov` or `Minime-Novice` → `Minime-Novice`
  - `Babies` → `Babies`
  - `Poussin` → `Poussin`
  - `Benjamin` → `Benjamin`
  - `Minime` → `Minime`
  - `Novice` → `Novice`
  - `Junior` → `Junior`
  - `Senior` → `Senior`
- **Gender**: `Femme` or `Homme` (last token typically)
- Case-insensitive matching, accent-insensitive for `Fédéral`/`Fédérale`

### Integration

- Called during import (in the scraper service, after creating Score/CategoryResult rows) to populate the new fields.
- SQLite migration: add columns via the existing `_migrate_add_columns` mechanism.
- Backfill command or startup routine to parse existing rows where the new fields are NULL.

## Section 1: Progression Ranking

### Purpose

Show which club skaters improved the most over a season, as a sortable leaderboard.

### Backend

**Endpoint**: `GET /api/stats/progression-ranking`

Query params:
- `season` (optional, defaults to current season)
- `club` (optional, defaults to configured club — uses `club_short` from `AppSettings`)
- `skating_level` (optional, filter)
- `age_group` (optional, filter)
- `gender` (optional, filter)

Logic (progression ranking):
- For each skater with 2+ `CategoryResult` rows in the season (matching filters), compute:
  - First and last `combined_total` (ordered by competition date)
  - Delta (gain/loss)
  - All scores as a sparkline array with dates
- Progression is computed **within the same `skating_level + age_group`** combination. If a skater changed level mid-season, they appear with their most recent level and the delta is computed from their first result at that level.
- Return sorted by `tss_gain` descending

Response:
```json
[
  {
    "skater_id": 1,
    "skater_name": "Marie Dupont",
    "skating_level": "R2",
    "age_group": "Minime",
    "gender": "Femme",
    "first_tss": 32.5,
    "last_tss": 41.2,
    "tss_gain": 8.7,
    "competitions_count": 4,
    "sparkline": [
      { "date": "2025-10-15", "value": 32.5 },
      { "date": "2025-11-20", "value": 35.1 },
      { "date": "2026-01-18", "value": 38.0 },
      { "date": "2026-03-02", "value": 41.2 }
    ]
  }
]
```

### UI

- Table with columns: Skater (link to detail), Level/Age pill, First score, Last score, Delta (colored green/red), Sparkline (tiny inline line chart), Competitions count
- Sorted by delta descending by default, secondary sort by `last_tss` descending. All skaters shown (including negative progression). Column headers clickable to re-sort.

### Empty/edge states

- No skaters with 2+ results: show "Aucun patineur n'a participé à au moins 2 compétitions cette saison."
- Filters produce zero results: show "Aucun résultat pour les filtres sélectionnés."

## Section 2: Side-by-Side Comparison with Benchmarks

### Purpose

Overlay 2-3 skaters' score progression curves on one chart, with a benchmark band showing where they stand relative to the field at their level + age group.

### Backend

**Endpoint**: `GET /api/stats/benchmarks`

Query params:
- `skating_level` (required)
- `age_group` (required)
- `gender` (required)
- `season` (optional)

Logic:
- Gather all `CategoryResult.combined_total` values matching the level + age group + gender (and season if provided)
- Compute min, max, median, p25, p75

Response:
```json
{
  "skating_level": "R2",
  "age_group": "Minime",
  "gender": "Femme",
  "data_points": 45,
  "min": 18.5,
  "max": 52.3,
  "median": 34.1,
  "p25": 26.4,
  "p75": 41.8
}
```

**Skater score data**: The frontend fetches each selected skater's score progression using the existing `api.skaters.categoryResults(id, season)` endpoint — no new batch endpoint needed (max 3 calls).

### UI

- **Skater multi-select** (max 3): filtered to club skaters by default, toggle to show all. Each skater gets a distinct color.
- **Chart** (Recharts `ComposedChart`):
  - Benchmark rendered as **flat horizontal bands** spanning the full chart width (the benchmark is an aggregate across all competitions, not per-date)
  - `ReferenceArea` for p25–p75 (primary shaded band)
  - Lighter `ReferenceArea` for min–max (outer band)
  - Dashed `ReferenceLine` for median
  - `Line` per selected skater (distinct colors, labeled in legend)
  - X-axis: competition dates, Y-axis: combined total
  - Tooltip showing skater values at a given date point, plus the benchmark range
- **Level override dropdown**: optional, to answer "how would my R2 skater compare against R1 field?"
- Benchmark adapts to the first selected skater's `skating_level + age_group + gender`. If skaters span different categories, a note explains which benchmark is shown.

### Empty/edge states

- No skaters selected: show placeholder message "Sélectionnez des patineurs pour comparer leur progression."
- Selected skater has no data in the season: omit from chart, show a small note
- Benchmark has < 3 data points: hide the benchmark bands, show note "Données insuffisantes pour le benchmark"

## Section 3: Element Mastery Tracker

### Purpose

Club-wide view of element execution quality: jump success rates and spin/step level distributions.

### Backend

**Endpoint**: `GET /api/stats/element-mastery`

Query params:
- `club` (optional, defaults to configured club — uses `club_short` from `AppSettings`)
- `season` (optional)
- `skating_level` (optional, filter)
- `age_group` (optional, filter)
- `gender` (optional, filter)

Logic:
- Gather all elements from scores belonging to club skaters (matching filters)
- Classify each element (jump, spin, step) — the detection logic currently lives client-side only (`SkaterAnalyticsPage.tsx` lines 23-43). It must be ported to Python in a new `backend/app/services/element_classifier.py` module. The frontend logic should also be extracted into a shared utility (`frontend/src/utils/elementClassifier.ts`) to avoid drift.
- **Important**: The current frontend regexes have issues that must be fixed during the port:
  - Jump pattern `/\d*(A|T|S|F|Lo|Lz|q)\b/i` is too broad (matches `FCSp`, `StSq`) and includes `q` which is a marker not a jump. Use `^[1-4]?(A|T|S|Lo|Lz|F)\b` anchored to start.
  - Spin pattern `/Sp/i` should be tightened to `/Sp\d?$/` to match codes like `CCoSp4`, `FSSp3`.
  - Step pattern `/St|ChSq/i` should be `^(StSq|ChSq)` to avoid partial matches.
- For jumps: group by jump type, compute attempt count, positive/neutral/negative GOE percentages, avg GOE
- For spins: group by element type, compute level distribution and avg GOE
- For steps: same as spins

Response:
```json
{
  "jumps": [
    {
      "jump_type": "2A",
      "attempts": 24,
      "positive_goe_pct": 58.3,
      "negative_goe_pct": 25.0,
      "neutral_goe_pct": 16.7,
      "avg_goe": 0.42
    }
  ],
  "spins": [
    {
      "element_type": "CCoSp",
      "attempts": 32,
      "level_distribution": { "0": 2, "1": 5, "2": 12, "3": 10, "4": 3 },
      "avg_goe": 1.15
    }
  ],
  "steps": [
    {
      "element_type": "StSq",
      "attempts": 28,
      "level_distribution": { "0": 1, "1": 8, "2": 14, "3": 5, "4": 0 },
      "avg_goe": 0.72
    }
  ]
}
```

### UI

Two cards (side by side on desktop, stacked on mobile):

**Jump success rates**:
- Horizontal bar chart grouped by jump type (sorted by difficulty: 1A, 2T, 2S, 2Lo, 2F, 2Lz, 2A, 3T, ...)
- Each bar segmented: green (positive GOE), yellow (neutral), red (negative)
- Attempt count label on each bar

**Spin/step level distribution**:
- Stacked bar chart: each bar = element type, segments = levels 0-4
- Color gradient from light (level 0) to saturated (level 4)
- Average GOE shown as a secondary annotation

### Empty/edge states

- No enriched data at all: show the "Enrichir avec les PDF" prompt (same as skater detail page)
- Filters produce zero elements: show "Aucun élément trouvé pour les filtres sélectionnés."

## Page Layout

```
+---------------------------------------------+
| Vue club                                     |
| Analyse collective des patineurs du club     |
|                                              |
| [Season v] [Level v] [Age group v] [Gender v] |
+---------------------------------------------+
| PROGRESSION                                  |
| +------------------------------------------+|
| | Leaderboard table with sparklines         ||
| +------------------------------------------+|
+---------------------------------------------+
| COMPARAISON                                  |
| +------------------------------------------+|
| | [Skater multi-select]  [Level override]   ||
| | Overlay chart with benchmark bands        ||
| +------------------------------------------+|
+---------------------------------------------+
| MAITRISE DES ELEMENTS                        |
| +-------------------+ +--------------------+|
| | Jump success bars  | | Spin/step levels   ||
| +-------------------+ +--------------------+|
+---------------------------------------------+
```

**Shared filters** at the top (season, skating level, age group, gender) apply to all three sections. The comparison section has its own additional skater multi-select and level override.

## Navigation

- Tab label: `CLUB` (was `STATISTIQUES`)
- Icon: `bar_chart` (unchanged)
- Route: `/stats` (unchanged)
- Page title in `App.tsx`: update from `"Statistiques"` to `"Club"`

## Design System

Follows Kinetic Lens:
- Surface color layering for section separation (no borders)
- Fonts: Manrope (section headings), Inter (body), monospace (numeric scores)
- All UI text in French
- Colors: `primary` (#2e6385) for primary data series, secondary palette for additional skater lines
- Chart styling consistent with existing Recharts usage in the app

## Adulte Categories

`Adulte Bronze`, `Adulte Argent`, and `Adulte Or` are treated as their own track. They appear in level/age filters alongside competitive levels but are kept separate — no cross-comparison between Adulte and competitive categories in benchmarks.

## TypeScript Types

Add `skating_level`, `age_group`, and `gender` to the `Score` and `CategoryResult` interfaces in `frontend/src/api/client.ts`. Add new API functions for the three new endpoints under an `api.stats` namespace.

## Data Dependencies

- Element mastery requires enriched data (PDF import). Show the same "Enrichir avec les PDF" prompt when no element data is available.
- Progression ranking and comparison work with basic import data (no PDF needed).
- All sections degrade gracefully when data is insufficient (empty state messages in French).
