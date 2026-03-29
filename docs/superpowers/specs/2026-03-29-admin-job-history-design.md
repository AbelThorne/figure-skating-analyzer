# Admin Job History Tab

## Overview

Add a "Tâches" tab to the admin settings page that displays a history of all import/reimport/enrich jobs from the last 7 days. Jobs are persisted to the database (replacing the current in-memory-only approach) so history survives server restarts.

## Backend: `Job` Model

New SQLAlchemy model persisted to SQLite:

| Column | Type | Notes |
|--------|------|-------|
| `id` | String(12) | PK, UUID hex[:12] (same format as current) |
| `type` | String | `import`, `reimport`, `enrich` |
| `trigger` | String | `manual`, `auto`, `bulk` |
| `competition_id` | Integer | FK to `competitions.id` |
| `status` | String | `queued`, `running`, `completed`, `failed`, `cancelled` |
| `result` | JSON | ImportResult or EnrichResult dict, nullable |
| `error` | Text | Error message if failed, nullable |
| `created_at` | DateTime | When submitted |
| `started_at` | DateTime | When execution began, nullable |
| `completed_at` | DateTime | When finished, nullable |

Relationships: `Job.competition` -> `Competition` (many-to-one), `Competition.jobs` back-ref.

The `cancelled` status is new — set when a queued job is cancelled from the admin UI.

The `trigger` field is set at creation time by the caller:
- `manual` — user clicked import/reimport/enrich on a competition
- `auto` — triggered by the auto-poll feature
- `bulk` — triggered from bulk import

## Backend: Job Queue Changes

`job_queue.py` keeps its in-memory queue for execution orchestration but persists to the DB:

- **`create_job(type, competition_id, trigger)`** — inserts a `Job` row with status `queued`, adds to in-memory queue, returns job dict.
- **Worker loop** — on pickup: sets `status=running`, `started_at`. On completion: sets `status=completed|failed`, `completed_at`, `result`/`error`.
- **`cancel_job(job_id)`** — new method. If the job is still in the in-memory queue (not yet running), removes it from the queue and sets `status=cancelled`, `completed_at` in DB. Returns error if job is already running or finished.
- **Startup cleanup** — deletes `Job` rows older than 7 days. Marks any `running` jobs left from a previous process as `failed` (server restarted mid-execution).
- **`list_jobs()` / `get_job()`** — read from DB instead of in-memory dict.

Processing remains single-threaded, one job at a time. Handler signature unchanged.

## Backend: API Endpoints

All in `routes/jobs.py`, protected by `auth_guard` + `require_admin`:

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/jobs/` | GET | List all jobs (newest first), includes `competition_name` via join |
| `/api/jobs/{job_id}` | GET | Single job with full result/error |
| `/api/jobs/{job_id}/cancel` | POST | Cancel a queued job. 400 if not cancellable. |

Response shape extends existing `JobInfo` with: `started_at`, `completed_at`, `competition_name`, `trigger`.

## Frontend: "Taches" Tab

New tab in `SettingsPage.tsx` labeled "Taches", after "Entrainement". Subtitle: "Historique des 7 derniers jours".

### Job List

Simple chronological list (newest first) with columns:

| Column | Content |
|--------|---------|
| Status icon | Spinner (running), clock (queued), checkmark (completed), X (failed), slash (cancelled) |
| Type + trigger | "Import - auto", "Reimport - manuel", "Enrichissement - lot" |
| Competition | Competition name, truncated with ellipsis |
| Started | Relative time ("il y a 3 min") or "En attente" if queued |
| Duration | From `started_at` to `completed_at`. End time as tooltip on hover. "-" if not started |
| Result summary | Short text from result (e.g. "5 scores importes"), truncated with ellipsis |
| Actions | `...` menu: "Voir les details" (always), "Annuler" (only for queued jobs) |

### Log Detail Modal

Triggered from "Voir les details" in the `...` menu:

- Job metadata: type, trigger, competition, status, timestamps (created, started, completed)
- Formatted result: import stats (events found, scores imported/skipped, category results) or enrich stats (PDFs downloaded, scores enriched, unmatched)
- Error block: if failed, error message in a red-tinted surface

### Polling

Uses TanStack Query with `refetchInterval: 5000` while the tab is active, so running/queued jobs update live.

## Testing

Backend tests (pytest, async, in-memory SQLite):

- `Job` model CRUD: create, read by ID, list ordered by created_at desc
- Cancel: successfully cancel queued job, reject cancel on running/completed/failed
- Cleanup: jobs older than 7 days deleted on startup, stale `running` jobs marked `failed`
- API auth: admin-only access, 403 for non-admin roles
- API responses: correct shape with `competition_name`, `trigger`, timestamps

No frontend tests (no test infrastructure in the project).
