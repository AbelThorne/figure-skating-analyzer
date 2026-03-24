# Competition Club Analysis Page — Design Spec

## Overview

A new page under the "Club" navigation that analyses the club's performance at a specific competition. It includes a club challenge ranking (computed from a point system), medal summary, personal bests, category coverage, and a detailed results table.

The page lives as a second tab ("Compétition") alongside the existing season-level analytics ("Saison") under `/club`.

## Navigation & Routing

- Rename current `/stats` route to `/club`
- `/club` redirects to `/club/saison`
- `/club/saison` — existing StatsPage content (progression, comparison, element mastery)
- `/club/competition` — new ClubCompetitionPage
- Tab bar at top of both pages: **Saison** | **Compétition**
- "Club" nav entry in sidebar points to `/club`

## Page Layout (top to bottom)

### 1. Tab Bar
Two tabs: "Saison" (links to `/club/saison`) and "Compétition" (links to `/club/competition`). Active tab has primary-colored underline.

### 2. Filter Row
- **Season dropdown** — prefilter, lists all seasons from DB
- **Competition dropdown** — filtered to competitions where the club had at least one skater in the selected season

### 3. KPI Hero Row
Four metric cards in a horizontal grid:

| KPI | Description |
|-----|-------------|
| Patineurs engagés | Count of club skaters in this competition |
| Médailles | Count of rank 1-3 finishes by club skaters |
| Records personnels | Count of skaters who beat their prior best score |
| Catégories couvertes | `N / M` — categories with club skaters / total categories |

### 4. Two-Column Section
- **Left (3fr): Club Challenge Ranking** — table of all clubs ranked by total points. Columns: #, Club, Points, Podium (tiebreaker). Own club row highlighted. Header includes a "Voir le détail par catégorie ›" link that opens a modal.
- **Right (2fr): Podiums du club** — list of club skaters who finished rank 1-3, with medal icon, name, category, and score. Gold/silver/bronze background tints.

### 5. Detailed Results Table
All club skaters in this competition. Columns: Patineur, Catégorie, Rang (x / n), Score, icons (medal + PB star). Sorted by category then rank. Dimmed rows for non-podium results.

### 6. Category Breakdown Modal
Triggered by "Voir le détail par catégorie" link on the Club Challenge panel. Modal contains:
- Accordion of categories (expandable/collapsible)
- Each category header shows: category name, skater count, club points subtotal
- Expanded view: table with columns Rang, Patineur, Base, Podium, Total (per the scoring formula)

## Club Challenge Scoring Algorithm

For N skaters in a category (N = total skaters in the category across all clubs):

1. **Base points**: Skater at rank `i` (1-indexed) receives `max(min(N - i + 1, 10), 1)` points
   - Rank 1 gets `min(N, 10)`, rank 2 gets `min(N-1, 10)`, etc.
   - All skaters beyond 10th place receive 1 point
2. **Podium bonus**: Rank 1 gets +3, rank 2 gets +2, rank 3 gets +1
3. **Club total**: Sum of all base + podium points across all categories
4. **Tiebreaker**: If two clubs have the same total points, the club with more podium points ranks higher

### Examples

| Skaters | Rank 1 | Rank 2 | Rank 3 | Rank 4 | Rank 10 | Rank 11+ |
|---------|--------|--------|--------|--------|---------|----------|
| 1 | 1+3=4 | — | — | — | — | — |
| 2 | 2+3=5 | 1+2=3 | — | — | — | — |
| 3 | 3+3=6 | 2+2=4 | 1+1=2 | — | — | — |
| 4 | 4+3=7 | 3+2=5 | 2+1=3 | 1 | — | — |
| 9 | 9+3=12 | 8+2=10 | 7+1=8 | 6 | — | — |
| 10 | 10+3=13 | 9+2=11 | 8+1=9 | 7 | 1 | — |
| 11 | 10+3=13 | 9+2=11 | 8+1=9 | 7 | 1 | 1 |

## API Design

### Endpoint

```
GET /api/stats/competition-club-analysis?competition_id={id}&club={club_name}
```

- `competition_id` (required) — competition to analyze
- `club` (optional) — defaults to configured `CLUB_SHORT`

### Response Shape

```typescript
interface CompetitionClubAnalysis {
  competition: { id: number; name: string; date: string; season: string };
  club_name: string;

  kpis: {
    skaters_entered: number;
    total_medals: number;
    personal_bests: number;
    categories_entered: number;
    categories_total: number;
  };

  club_challenge: {
    ranking: ClubChallengeEntry[];
    category_breakdown: CategoryBreakdown[];
  };

  medals: MedalEntry[];
  personal_bests_list: PBEntry[];
  categories: CategoryCoverageEntry[];
  results: ClubSkaterResult[];
}

interface ClubChallengeEntry {
  club: string;
  total_points: number;
  podium_points: number;
  rank: number;
  is_my_club: boolean;
}

interface CategoryBreakdown {
  category: string;
  clubs: { club: string; points: number; podium_points: number }[];
  club_skaters: {
    skater_name: string;
    rank: number;
    base_points: number;
    podium_points: number;
    total_points: number;
  }[];
}

interface MedalEntry {
  skater_id: number;
  skater_name: string;
  category: string;
  rank: 1 | 2 | 3;
  combined_total: number;
}

interface PBEntry {
  skater_id: number;
  skater_name: string;
  category: string;
  current_score: number;
  previous_best: number;
  improvement: number;
}

interface CategoryCoverageEntry {
  category: string;
  club_skaters: number;
  total_skaters: number;
}

interface ClubSkaterResult {
  skater_id: number;
  skater_name: string;
  category: string;
  overall_rank: number | null;
  total_skaters: number;
  combined_total: number | null;
  is_pb: boolean;
  medal: 1 | 2 | 3 | null;
}
```

### Competition List Filtering

Add optional `club` query parameter to `GET /api/competitions/`:
- When provided, filter to competitions where at least one `CategoryResult` has a skater whose `club` matches (case-insensitive)
- Used by the frontend competition dropdown

## Backend Implementation

### New file: `backend/app/services/competition_analysis.py`

Service class computing the full analysis:

1. **Load data** — single query joining `CategoryResult` → `Skater` for the competition
2. **Club challenge** — group by (category, club), rank within category, apply point formula, aggregate
3. **PB detection** — for each club skater, query their best `combined_total` from prior competitions (same category, earlier date). Flag as PB if current > previous best or if first competition
4. **Medals** — filter category results where `overall_rank <= 3` and skater belongs to club
5. **Category coverage** — group by category, count club vs total
6. **Detailed results** — all club skater results enriched with PB and medal flags

### Route: `backend/app/routes/stats.py`

Add endpoint handler that calls the service and returns the response.

## Frontend Implementation

### New file: `frontend/src/pages/ClubCompetitionPage.tsx`

- Uses `useQuery` to fetch competition club analysis
- Season/competition dropdowns with dependent filtering
- KPI cards, club challenge table, medals list, results table
- Category breakdown modal (reuse existing modal pattern from `ScoreCardModal`)

### Modified files:
- `App.tsx` — add `/club`, `/club/saison`, `/club/competition` routes, redirect `/stats` to `/club/saison`
- `Layout.tsx` or nav component — update "Club" nav to point to `/club`
- `frontend/src/api/client.ts` — add types and API function for the new endpoint

## Design System Compliance

- Tailwind CSS only, no component libraries
- All UI text in French
- Surface color layering (no borders for sectioning)
- Fonts: Manrope (headlines), Inter (body), Material Symbols Outlined (icons)
- Numeric scores use `font-mono`
- Colors: `on-surface` for text, `primary` for actions/highlights, `error` for failures
- Own club row uses a lighter primary tint background
- Medal backgrounds: gold `#fff8e1`, silver `#f5f5f5`, bronze `#fdf0ef`
