# Figure Skating Analyzer — Product Roadmap & Implementation Plan

## Context

This is a full-stack tool (Python/Litestar backend + React/TypeScript/Vite frontend) for importing, storing, and analyzing figure skating competition results. It is used by **coaches and clubs** to track skater performance across competitions. The primary discipline is **singles (Men/Women)**.

The app is **scoped to a single club**: all analytics, reports, and the skater browser are filtered to show only skaters belonging to the configured club. The club name is a required configuration parameter (`CLUB_NAME`) — stored in `backend/.env` / environment variable. If not set, the app prompts the user to configure it on first launch (via a setup screen in the frontend).

Data is sourced from:
- FS Manager HTML pages (already working)
- Swiss Timing sites (future)
- ISU Challenger/Grand Prix results (future)

The #1 priority is **better analytics & charts** — specifically element-level GOE trends, PCS component breakdown, judge panel analysis, and element difficulty tracking.

## Design System

All frontend work **must follow** the "Kinetic Lens" design system defined in:
**`docs/superpowers/specs/2026-03-20-frontend-design.md`**

Key constraints for every agent working on the frontend:
- **UI framework: Tailwind CSS only** — no Ant Design, MUI, or shadcn
- **No borders for sectioning** — use surface color layering instead
- **Fonts: Manrope** (headlines) + **Inter** (body/labels) + **Material Symbols Outlined** (icons)
- **Colors: strict token map** — never use raw hex values outside the defined palette
- **Charts: Recharts** with custom colors from the token map (`#2e6385` primary, `#a5d8ff` secondary)
- All numeric scores use `font-mono`; all text uses `on-surface` (#191c1e), never pure black

---

## Current State (What's Built)

- ✅ Competition CRUD (add by URL, delete)
- ✅ HTML-first import from FS Manager SEG pages (scrapes TSS, TES, PCS, component scores, deductions)
- ✅ Optional PDF enrichment (element-by-element details, base value, GOE, judge scores)
- ✅ Competition page with score table + TES/PCS bar chart
- ✅ Skater stats page with line chart (TSS/TES/PCS over time)
- ✅ Skater DB with name/club/nationality
- ✅ Club dashboard (HomePage) with KPI cards, medals, top scores, most improved, recent competitions
- ✅ Element data API + Skater analytics page (GOE charts, PCS radar, element difficulty, judge panel)
- ✅ Club skater browser with category filters and search
- ✅ Import status & error feedback (inline results, partial success, ErrorDetailModal)
- ✅ Pluggable scraper architecture (BaseScraper, FSManagerScraper, scraper factory)
- ✅ Re-import & merge support with force option
- ✅ Docker Compose deployment (backend + frontend + SQLite volume)
- ✅ Authentication (JWT + Google OAuth, user management, role-based guards)
- ✅ Club configuration & first-run setup (AppSettings, SetupPage, SettingsPage)
- ✅ Competition metadata enrichment (season/discipline/city/country auto-detection)
- ✅ Bulk import via YAML lots (SettingsPage)
- ✅ Season detection & filtering (auto-detect on import, `/competitions/seasons` endpoint)

---

## Phase 1 — Analytics & Dashboard ✅ COMPLETE

### 1.0 Club Dashboard (Home Page)

Replace the current plain competition list with a rich club dashboard that gives coaches an at-a-glance view of the season.

**Backend:**
- `GET /api/dashboard?season=2025-2026` — returns aggregated stats for the configured club:
  - `active_skaters`: count of club skaters with at least one score this season
  - `competitions_tracked`: count of competitions with club skater results
  - `total_programs`: total number of scored programs (SP + FS) by club skaters this season
  - `medals`: list of podium finishes `{skater_name, rank, competition, segment, category}`
  - `top_scores`: top 5 TSS scores by club skaters this season `{skater_name, tss, competition, segment}`
  - `most_improved`: up to 3 skaters with biggest TSS gain (first vs last result) this season
  - `recent_competitions`: last 3 competitions with club results, with date and result summary

**Frontend — `frontend/src/pages/HomePage.tsx` (rewrite):**
- Season selector at the top (defaults to current season)
- **Stats row**: 3–4 KPI cards — Active Skaters, Competitions, Programs Scored, Podiums
- **Medals & podiums**: compact list grouped by category
- **Top scores**: small table of best TSS performances
- **Most improved**: 3-card row showing skater name + TSS delta
- **Recent competitions**: list with links to competition detail pages
- **"Export Season Report" button**: triggers `GET /api/reports/club/pdf?season=…` download (reuses Phase 4.2 report)
- Competition management (add/delete) moved to a separate `/competitions` admin page

**Files to modify/create:**
- `frontend/src/pages/HomePage.tsx` — full rewrite as dashboard
- `frontend/src/pages/CompetitionsPage.tsx` — new page for competition list + add/delete
- `backend/app/routes/dashboard.py` — new `GET /api/dashboard` endpoint
- `frontend/src/App.tsx` — update routes (`/` → dashboard, `/competitions` → admin list)
- `frontend/src/api/client.ts` — add dashboard query types

**Verification:**
1. Load `/` — confirm KPI cards show correct counts for the configured club
2. Medals list shows only club skater podiums
3. "Export Season Report" button downloads a PDF
4. Changing season selector updates all dashboard data
5. Competition management accessible at `/competitions`

---

**Goal:** Surface the rich element data already captured in PDFs (`elements` JSON field) through charts and tables coaches actually care about. All analytics default to club skaters — the same `CLUB_NAME` filter applies everywhere.

### 1.1 Backend: Element Data API

Expose element-level data cleanly.

**Files to modify:**
- `backend/app/routes/scores.py` — add endpoints:
  - `GET /api/scores/{id}/elements` — return elements list for a score
  - `GET /api/skaters/{id}/elements?element_type=3A` — return element history across competitions for a skater, optionally filtered by element type (e.g. `3A`, `4T`, `CSSp4`)
- `backend/app/models/score.py` — ensure `elements` JSON field is fully typed/documented

**Element structure** (from PDF enrichment):
```json
{
  "name": "3Lz+3T",
  "base_value": 11.11,
  "goe": 1.43,
  "judges": [-1, 2, 2, 2, 2, 2, 1, 2, 2],
  "total": 12.54
}
```

### 1.2 Frontend: Skater Element Analytics Page

Add a new page `/skaters/:id/analytics` (or tab on skater page).

**Components to build:**
- `ElementGOEChart` — bar chart showing GOE per element over time (x: competition date, y: GOE, grouped by element type)
- `ElementTable` — table showing all elements from a selected program: name, base value, GOE, judge breakdown
- `PCSRadarChart` — radar/spider chart showing the 5 PCS components (CO, PR, SK, PE, IN) for a given performance, overlaid across competitions
- `ElementDifficultyChart` — track base value evolution over time (are skaters upgrading content?)
- `JudgePanel` — for a selected score, show the 9 judges' GOE distribution per element (heatmap or small grid)

**Files to create:**
- `frontend/src/pages/SkaterAnalyticsPage.tsx`
- `frontend/src/components/ElementGOEChart.tsx`
- `frontend/src/components/PCSRadarChart.tsx`
- `frontend/src/components/ElementDifficultyChart.tsx`
- `frontend/src/components/JudgePanel.tsx`

**Files to modify:**
- `frontend/src/App.tsx` — add route `/skaters/:id/analytics`
- `frontend/src/api/client.ts` — add element query functions and types
- `frontend/src/pages/CompetitionPage.tsx` — link skater names to their analytics page

### 1.3 Skater Navigation: Club Skater Browser

**Goal:** Let coaches browse and access analytics for their club's skaters. By default, all skater views are scoped to the configured club (`CLUB_NAME`). Other skaters (from other clubs, seen in imported competitions) are accessible but not surfaced by default.

**Backend changes:**
- `GET /api/skaters?club=<CLUB_NAME>` — default filter; returns only club skaters unless `club` param is explicitly overridden
- `GET /api/skaters/{id}/elements` — already club-agnostic (skater-level), but reached only via club skater links

**Frontend changes:**
- New page `frontend/src/pages/SkaterBrowserPage.tsx` — lists the club's skaters by default (name, category, competitions this season)
- Optional "Show all clubs" toggle for coaches who want to look up a competitor's skater
- Route `/skaters` in nav

**Verification:** Navigate to `/skaters` — only club skaters shown by default. Toggle shows all. Click a skater → analytics page.

---

## Phase 2 — Import Robustness & Multi-Source Support ✅ COMPLETE

**Goal:** Make imports more reliable and extensible for Swiss Timing and ISU formats.

### 2.1 Import Status & Error Feedback

Currently, import failures are silent or minimal. Add:

**Backend:**
- `GET /api/competitions/{id}/import-status` — return last import result: `{status, events_found, events_imported, errors: [{event, message}]}`
- Store import log per competition (add `last_import_log` JSON field to Competition model)

**Frontend:**
- Show import results inline on HomePage after clicking Import
- Display partial success: "Imported 8/10 events. 2 failed: [Novice Ladies SP — parsing error]"

### 2.2 Scraper Architecture: Pluggable Sources

Refactor scraping layer to support multiple site formats.

**Backend refactor:**
- `backend/app/services/scrapers/base.py` — abstract `BaseScraper` with `parse_index()` / `parse_seg_page()` interface
- `backend/app/services/scrapers/fs_manager.py` — move existing `FSManagerScraper` here
- `backend/app/services/scrapers/swiss_timing.py` — stub (implement when URLs provided)
- `backend/app/services/scrapers/isu.py` — stub
- `backend/app/services/scraper_factory.py` — detect site type from URL pattern, return correct scraper

**Files to modify:**
- `backend/app/routes/competitions.py` — use scraper factory instead of hardcoded `FSManagerScraper`

### 2.3 Re-import & Merge Strategy

Allow coaches to re-import a competition after adding new events or correcting data.

- Import endpoint already idempotent (unique constraint on competition+skater+category+segment)
- Add `force=true` query param to delete existing scores for that competition before re-importing
- Add "Re-import" button in UI (same as Import, but warn about data replacement)

---

## Phase 3 — Self-Hosted Deployment & Club Management ✅ COMPLETE

**Goal:** Make the app runnable by a club on a shared server with minimal ops overhead.

### 3.1 Docker Compose Setup

- `Dockerfile.backend` — Python/uv container running Litestar on port 8000
- `Dockerfile.frontend` — Node build stage + nginx serving static files
- `docker-compose.yml` — wire up backend + frontend + SQLite volume mount
- `.env.example` — configurable `DB_PATH`, `PDF_DIR`, `ALLOWED_ORIGINS`

### 3.2 Basic Auth / Access Control (lightweight)

For a single-club deployment, a simple approach:
- Environment variable `ADMIN_TOKEN` — all mutating API calls (import, delete) require `Authorization: Bearer <token>` header
- Read-only routes (GET) remain public
- Frontend stores token in localStorage after coach enters it on first visit

### 3.3 Club Configuration & First-Run Setup

The app is scoped to a specific club. Club identity is central to filtering skaters and generating reports.

**Backend:**
- `CLUB_NAME` environment variable (required) — stored in `.env`, added to `backend/app/config.py`
- `GET /api/config` — returns `{club_name, season_current}` so the frontend can display it and check if setup is complete
- If `CLUB_NAME` is not set, the endpoint returns `{setup_required: true}`

**Frontend:**
- On app load, fetch `/api/config`. If `setup_required: true`, redirect to `/setup`
- `frontend/src/pages/SetupPage.tsx` — simple form: enter club name, save (writes to backend `.env` or triggers a `POST /api/config` endpoint)
- Club name displayed in the app header/nav as branding
- All skater queries default-filter to `club=CLUB_NAME` (coaches only see their own skaters in analytics and reports)

**Files to create/modify:**
- `backend/app/config.py` — add `CLUB_NAME` setting
- `backend/app/routes/config.py` — new `GET /api/config` (and optional `POST /api/config` for setup)
- `frontend/src/pages/SetupPage.tsx` — first-run setup screen
- `frontend/src/App.tsx` — gate app routes behind config check

### 3.4 Competition Metadata Enrichment

Allow coaches to annotate competitions:
- Add `notes` field to Competition model
- Add `season` auto-detection from date (already partially exists)
- Add `discipline` field (Singles Men / Singles Women / etc.) — useful for filtering analytics

---

## Phase 4 — Season & Club Reports (PDF Export)

**Goal:** Generate printable PDF reports for individual skaters and for the club as an end-of-year recap.

### 4.1 Skater Season Report

A per-skater, per-season PDF report containing:
- **Personal bests**: Best TSS, TES, PCS achieved this season (SP and FS separately)
- **Competition results table**: All competitions entered this season — date, competition name, segment, rank, TSS, TES, PCS
- **Score progression charts**: Line charts showing TSS/TES/PCS across the season (rendered as images embedded in PDF)
- **Element analysis summary**: GOE trends per element type, most consistent elements, best total element score

**Backend:**
- `GET /api/reports/skater/{id}?season=2025-2026` — returns structured JSON for the report
- `GET /api/reports/skater/{id}/pdf?season=2025-2026` — generates and streams a PDF file
- Use `reportlab` or `weasyprint` (render HTML→PDF) to generate the PDF server-side
- Charts rendered via `matplotlib` (server-side, embedded as PNG in PDF) or via frontend screenshot approach

**Frontend:**
- "Export Season Report" button on the Skater Analytics page
- Season selector (dropdown of available seasons for that skater)
- Triggers download of the generated PDF

### 4.2 Club End-of-Year Report

A club-wide PDF report containing:
- **Cover**: Club name, season, date generated
- **Activity stats**: Total skaters tracked, total competitions, total programs analyzed
- **All skaters summary table**: Skater name, category, competitions entered, best TSS, best TES, best PCS
- **Medals & podiums**: List of 1st/2nd/3rd place finishes — skater, competition, segment, category
- **Score progression highlights**: Most improved skaters (biggest TSS gain start→end of season), top performers per category

**Backend:**
- `GET /api/reports/club?season=2025-2026` — returns structured JSON
- `GET /api/reports/club/pdf?season=2025-2026` — generates and streams club PDF report

**Frontend:**
- "Export Club Report" button on HomePage or a new Reports page
- Season selector
- Triggers PDF download

### 4.3 Season Detection ✅ COMPLETE

- ✅ Auto-detect season from competition date (Jul–Jun cycle) — implemented in `competition_metadata.py`
- ✅ Competition model `season` field populated on import
- ✅ `GET /api/competitions/seasons` endpoint returns all seasons
- ✅ `GET /api/skaters/{id}/seasons` returns per-skater seasons
- ✅ Frontend season selectors on StatsPage, ClubCompetitionPage, SkaterAnalyticsPage

---

## Implementation Order

| Phase | Step | Status | Effort |
|-------|------|--------|--------|
| 1 | Club dashboard (home page rewrite + API) | ✅ Done | Medium |
| 1 | Element data API endpoints | ✅ Done | Small |
| 1 | Skater analytics page + GOE/PCS charts | ✅ Done | Medium |
| 1 | Club browser navigation | ✅ Done | Small |
| 2 | Import status & error feedback | ✅ Done | Small |
| 2 | Scraper factory architecture | ✅ Done | Medium |
| 2 | Re-import UI | ✅ Done | Small |
| 3 | Club config & first-run setup screen | ✅ Done | Small |
| 3 | Docker Compose deployment | ✅ Done | Small |
| 3 | Auth (JWT + Google OAuth + user mgmt) | ✅ Done | Medium |
| 3 | Competition metadata enrichment | ✅ Done | Small |
| 4 | Season detection & filtering | ✅ Done | Small |
| 4 | Skater & club report JSON APIs | ⏳ TODO | Medium |
| 4 | PDF generation (reportlab/weasyprint) | ⏳ TODO | Medium |
| 4 | Export buttons in frontend | ⏳ TODO | Small |

---

## Verification Strategy (per phase)

**Phase 1:**
1. Import a competition with PDF enrichment to populate `elements` JSON
2. Navigate to `/skaters/:id/analytics`
3. Confirm GOE chart shows per-element values across competitions
4. Confirm PCS radar chart shows 5 component scores
5. Browse `/skaters` — confirm clubs are listed with skater drill-down

**Phase 2:**
1. Import a competition — check import status response includes event-level results
2. Introduce a bad event URL — verify partial success is reported clearly
3. Add a second scraper stub — verify factory routes by URL pattern

**Phase 3:**
1. Start app without `CLUB_NAME` set — verify frontend redirects to `/setup`
2. Enter club name on setup screen — verify it persists and app loads normally
3. Confirm club name appears in nav header
4. Confirm skater browser and analytics default-filter to the configured club
5. Run `docker compose up` — verify app is accessible on configured port
6. Attempt import without token — verify 401
7. Attempt GET without token — verify 200

**Phase 4:**
1. Import 3+ competitions for a skater across a full season
2. Call `GET /api/reports/skater/{id}/pdf?season=2025-2026` — verify PDF downloads
3. Check PDF contains: personal bests table, results table, progression charts, element summary
4. Call `GET /api/reports/club/pdf?season=2025-2026` — verify club PDF downloads
5. Check PDF contains: activity stats, skaters table, medals list, most improved section

---

## Key Files Reference

| File | Purpose |
|------|---------|
| `backend/app/services/site_scraper.py` | FS Manager HTML scraper (Phase 2: split into scrapers/) |
| `backend/app/routes/competitions.py` | Import/enrich endpoints |
| `backend/app/routes/scores.py` | Score queries (Phase 1: add element endpoints) |
| `backend/app/routes/config.py` | Club config endpoint (Phase 3) |
| `backend/app/config.py` | App config incl. `CLUB_NAME` (Phase 3) |
| `frontend/src/pages/SetupPage.tsx` | First-run club setup screen (Phase 3) |
| `backend/app/models/score.py` | Score model with `elements` JSON field |
| `frontend/src/pages/CompetitionPage.tsx` | Competition detail (add skater links) |
| `frontend/src/pages/StatsPage.tsx` | Skater stats (refactor into analytics page) |
| `frontend/src/pages/HomePage.tsx` | Rewrite as club dashboard (Phase 1.0) |
| `frontend/src/pages/CompetitionsPage.tsx` | New competition admin page (Phase 1.0) |
| `backend/app/routes/dashboard.py` | Dashboard aggregation endpoint (Phase 1.0) |
| `frontend/src/api/client.ts` | API client types (Phase 1: add element types) |
