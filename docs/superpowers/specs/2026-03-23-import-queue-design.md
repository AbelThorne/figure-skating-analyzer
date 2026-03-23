# Import Queue Design

## Problem

Import and enrich operations are synchronous HTTP endpoints that block for seconds/minutes. Triggering multiple operations concurrently causes SQLite write conflicts and the frontend only tracks one "busy" state at a time, leading to broken UX.

## Solution

A single in-memory asyncio job queue that serializes all import/enrich operations. Jobs are submitted via existing endpoints (which now return immediately) and tracked via polling.

## Backend

### Job Queue (`backend/app/services/job_queue.py`)

- Singleton `JobQueue` with an `asyncio.Queue` and a background worker task
- Worker processes one job at a time, calling the same import/enrich logic
- Jobs stored in a dict: `job_id → JobInfo`
- `JobInfo` dataclass: `id`, `type` (import|reimport|enrich), `competition_id`, `status` (queued|running|completed|failed), `result`, `error`, `created_at`
- Old completed/failed jobs cleaned up after a threshold (e.g. keep last 50)

### Endpoint changes

**Modified endpoints** (return immediately with job info):
- `POST /competitions/{id}/import` → returns `{job_id, status: "queued", competition_id}`
- `POST /competitions/{id}/enrich` → returns `{job_id, status: "queued", competition_id}`

**New endpoints**:
- `GET /jobs/` → list all jobs (active + recent)
- `GET /jobs/{job_id}` → get single job status + result

**Removed/unchanged**:
- `GET /competitions/{id}/import-status` — keep as-is, still reads `last_import_log`
- `POST /competitions/bulk-import` — refactor to submit multiple jobs to the queue

### Import logic refactor

Extract the actual import/enrich logic from the route handlers into standalone async functions in a service module, so both the queue worker and (if needed) direct calls can use them. These functions receive an `AsyncSession` and do the work.

## Frontend

### State changes in `CompetitionsPage.tsx`

Replace:
- `importingId: number | null` → `jobs: Record<string, JobInfo>` (jobId → status)
- `enrichingId: number | null` → same map

Add:
- `competitionJobs: Record<number, string[]>` — maps competitionId to active jobIds

### Polling

After submitting a job, start polling `GET /jobs/{job_id}` every 2 seconds until `completed` or `failed`. On completion, show result inline (existing notification UI). Stop polling.

### Button states

For each competition row:
- If competition has any active job (queued/running): show status text on the relevant button, disable that button
- Other competitions' buttons remain enabled (clicking queues a new job)
- Show "En file d'attente" for queued jobs, "Importation..." / "Enrichissement..." for running jobs

### API client additions

```typescript
interface JobInfo {
  id: string;
  type: "import" | "reimport" | "enrich";
  competition_id: number;
  status: "queued" | "running" | "completed" | "failed";
  result: ImportResult | EnrichResult | null;
  error: string | null;
  created_at: string;
}

api.jobs = {
  list: () => request<JobInfo[]>("/jobs/"),
  get: (id: string) => request<JobInfo>("/jobs/" + id),
};
```

The existing `api.competitions.import()` / `api.competitions.enrich()` return type changes from `ImportResult`/`EnrichResult` to `JobInfo`.

## Bulk import

`POST /competitions/bulk-import` submits each URL as a separate job to the queue and returns the list of job IDs. The frontend can then poll each one individually (or poll `GET /jobs/` to see all).
