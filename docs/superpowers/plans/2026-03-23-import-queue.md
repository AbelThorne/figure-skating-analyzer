# Import Queue Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Serialize all import/enrich operations through an in-memory asyncio job queue so they execute one at a time, preventing SQLite write conflicts and enabling proper multi-job tracking in the UI.

**Architecture:** A singleton `JobQueue` service with an asyncio worker processes jobs sequentially. Existing import/enrich endpoints return immediately with a job ID. A new `/api/jobs/` router exposes job status. The frontend polls job status and tracks multiple concurrent jobs per competition.

**Tech Stack:** Python asyncio (Queue), Litestar routes, React (useState + useEffect polling), existing SQLAlchemy async sessions.

---

## File Structure

| Action | File | Responsibility |
|--------|------|----------------|
| Create | `backend/app/services/job_queue.py` | Singleton job queue, worker loop, job state |
| Create | `backend/app/services/import_service.py` | Extracted import/enrich logic (pure functions) |
| Create | `backend/app/routes/jobs.py` | `GET /api/jobs/`, `GET /api/jobs/{id}` |
| Create | `backend/tests/test_job_queue.py` | Unit tests for job queue |
| Modify | `backend/app/routes/competitions.py` | Submit to queue instead of inline execution |
| Modify | `backend/app/main.py` | Register jobs router, start queue worker in lifespan |
| Modify | `frontend/src/api/client.ts` | Add `JobInfo` type, `api.jobs`, update return types |
| Modify | `frontend/src/pages/CompetitionsPage.tsx` | Multi-job tracking, polling, queue-aware buttons |

---

### Task 1: Create the JobQueue service

**Files:**
- Create: `backend/app/services/job_queue.py`
- Create: `backend/tests/test_job_queue.py`

- [ ] **Step 1: Write failing test for job creation and status tracking**

```python
# backend/tests/test_job_queue.py
import pytest
from app.services.job_queue import JobQueue


def test_create_job():
    q = JobQueue()
    job = q.create_job("import", competition_id=1)
    assert job["id"] is not None
    assert job["type"] == "import"
    assert job["competition_id"] == 1
    assert job["status"] == "queued"
    assert job["result"] is None
    assert job["error"] is None


def test_get_job():
    q = JobQueue()
    job = q.create_job("enrich", competition_id=2)
    fetched = q.get_job(job["id"])
    assert fetched is not None
    assert fetched["id"] == job["id"]


def test_get_job_not_found():
    q = JobQueue()
    assert q.get_job("nonexistent") is None


def test_list_jobs():
    q = JobQueue()
    q.create_job("import", competition_id=1)
    q.create_job("enrich", competition_id=2)
    jobs = q.list_jobs()
    assert len(jobs) == 2
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/julien/projects/figure-skating-analyzer && PATH="/opt/homebrew/bin:$PATH" uv run pytest backend/tests/test_job_queue.py -v`
Expected: FAIL — module not found

- [ ] **Step 3: Implement JobQueue**

```python
# backend/app/services/job_queue.py
from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timezone
from typing import Any, Callable, Awaitable


class JobQueue:
    """In-memory async job queue. Processes one job at a time."""

    def __init__(self) -> None:
        self._queue: asyncio.Queue[str] = asyncio.Queue()
        self._jobs: dict[str, dict[str, Any]] = {}
        self._handler: Callable[[dict], Awaitable[Any]] | None = None
        self._worker_task: asyncio.Task | None = None

    def create_job(self, job_type: str, competition_id: int) -> dict:
        job_id = uuid.uuid4().hex[:12]
        job = {
            "id": job_id,
            "type": job_type,
            "competition_id": competition_id,
            "status": "queued",
            "result": None,
            "error": None,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        self._jobs[job_id] = job
        self._queue.put_nowait(job_id)
        self._trim_old_jobs()
        return job

    def get_job(self, job_id: str) -> dict | None:
        return self._jobs.get(job_id)

    def list_jobs(self) -> list[dict]:
        return list(self._jobs.values())

    def set_handler(self, handler: Callable[[dict], Awaitable[Any]]) -> None:
        self._handler = handler

    async def start_worker(self) -> None:
        self._worker_task = asyncio.create_task(self._run_worker())

    async def stop_worker(self) -> None:
        if self._worker_task:
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass

    async def _run_worker(self) -> None:
        while True:
            job_id = await self._queue.get()
            job = self._jobs.get(job_id)
            if not job or not self._handler:
                self._queue.task_done()
                continue
            job["status"] = "running"
            try:
                result = await self._handler(job)
                job["status"] = "completed"
                job["result"] = result
            except Exception as e:
                job["status"] = "failed"
                job["error"] = str(e)
            finally:
                self._queue.task_done()

    def _trim_old_jobs(self, keep: int = 50) -> None:
        if len(self._jobs) <= keep:
            return
        finished = [
            (k, v) for k, v in self._jobs.items()
            if v["status"] in ("completed", "failed")
        ]
        finished.sort(key=lambda x: x[1]["created_at"])
        to_remove = len(self._jobs) - keep
        for k, _ in finished[:to_remove]:
            del self._jobs[k]


# Singleton instance
job_queue = JobQueue()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/julien/projects/figure-skating-analyzer && PATH="/opt/homebrew/bin:$PATH" uv run pytest backend/tests/test_job_queue.py -v`
Expected: 4 PASS

- [ ] **Step 5: Write async worker test**

Add to `backend/tests/test_job_queue.py`:

```python
@pytest.mark.asyncio
async def test_worker_processes_job():
    q = JobQueue()
    results = []

    async def handler(job):
        results.append(job["id"])
        return {"scores_imported": 5}

    q.set_handler(handler)
    job = q.create_job("import", competition_id=1)
    await q.start_worker()

    # Wait for processing
    await asyncio.wait_for(q._queue.join(), timeout=2.0)
    await q.stop_worker()

    assert job["status"] == "completed"
    assert job["result"] == {"scores_imported": 5}
    assert len(results) == 1


@pytest.mark.asyncio
async def test_worker_handles_failure():
    q = JobQueue()

    async def handler(job):
        raise ValueError("scrape failed")

    q.set_handler(handler)
    job = q.create_job("import", competition_id=1)
    await q.start_worker()

    await asyncio.wait_for(q._queue.join(), timeout=2.0)
    await q.stop_worker()

    assert job["status"] == "failed"
    assert "scrape failed" in job["error"]


@pytest.mark.asyncio
async def test_worker_sequential_processing():
    q = JobQueue()
    order = []

    async def handler(job):
        order.append(job["competition_id"])
        await asyncio.sleep(0.01)
        return {}

    q.set_handler(handler)
    q.create_job("import", competition_id=1)
    q.create_job("enrich", competition_id=2)
    q.create_job("import", competition_id=3)
    await q.start_worker()

    await asyncio.wait_for(q._queue.join(), timeout=5.0)
    await q.stop_worker()

    assert order == [1, 2, 3]
```

- [ ] **Step 6: Run all queue tests**

Run: `cd /Users/julien/projects/figure-skating-analyzer && PATH="/opt/homebrew/bin:$PATH" uv run pytest backend/tests/test_job_queue.py -v`
Expected: 7 PASS

- [ ] **Step 7: Commit**

```bash
git add backend/app/services/job_queue.py backend/tests/test_job_queue.py
git commit -m "feat: add in-memory asyncio job queue for serialized imports"
```

---

### Task 2: Extract import/enrich logic into service functions

**Files:**
- Create: `backend/app/services/import_service.py`

- [ ] **Step 1: Extract import logic from route handler**

Create `backend/app/services/import_service.py` with the import and enrich logic extracted from `competitions.py`. These functions take an `AsyncSession` and `competition_id`, do all the work, and return the result dict.

```python
# backend/app/services/import_service.py
from __future__ import annotations

from datetime import date as date_type

from sqlalchemy import select, delete as sa_delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.competition import Competition
from app.models.skater import Skater
from app.models.score import Score
from app.models.category_result import CategoryResult
from app.services.scraper_factory import get_scraper
from app.services.downloader import download_pdfs, url_to_slug
from app.services.parser import parse_elements, extract_segment_code


async def _get_or_create_skater(
    session: AsyncSession,
    name: str,
    nationality: str | None,
    club: str | None,
) -> Skater:
    stmt = select(Skater).where(Skater.name == name)
    skater = (await session.execute(stmt)).scalar_one_or_none()
    if not skater:
        skater = Skater(name=name, nationality=nationality, club=club)
        session.add(skater)
        await session.flush()
    else:
        if not skater.nationality and nationality:
            skater.nationality = nationality
        if not skater.club and club:
            skater.club = club
    return skater


async def run_import(session: AsyncSession, competition_id: int, force: bool = False) -> dict:
    """Import competition results. Returns the import result dict."""
    comp = await session.get(Competition, competition_id)
    if not comp:
        raise ValueError(f"Competition {competition_id} not found")

    if force:
        await session.execute(
            sa_delete(Score).where(Score.competition_id == competition_id)
        )
        await session.execute(
            sa_delete(CategoryResult).where(CategoryResult.competition_id == competition_id)
        )
        await session.flush()

    scraper = get_scraper(comp.url)
    events, results, cat_results, comp_info = await scraper.scrape(comp.url)

    if comp_info.name and (comp.name == comp.url or not comp.name or comp.name == "index.htm"):
        comp.name = comp_info.name
    if comp_info.date and not comp.date:
        comp.date = date_type.fromisoformat(comp_info.date)

    imported = 0
    skipped = 0
    cat_imported = 0
    cat_skipped = 0
    errors = []

    for r in results:
        try:
            skater = await _get_or_create_skater(session, r.name, r.nationality, r.club)
            existing = await session.execute(
                select(Score).where(
                    Score.competition_id == comp.id,
                    Score.skater_id == skater.id,
                    Score.category == r.category,
                    Score.segment == r.segment,
                )
            )
            if existing.scalar_one_or_none():
                skipped += 1
                continue
            score = Score(
                competition_id=comp.id,
                skater_id=skater.id,
                segment=r.segment or "UNKNOWN",
                category=r.category,
                rank=r.rank,
                total_score=r.total_score,
                technical_score=r.technical_score,
                component_score=r.component_score,
                components=r.components,
                deductions=r.deductions,
                starting_number=r.starting_number,
                event_date=date_type.fromisoformat(r.event_date) if r.event_date else None,
            )
            session.add(score)
            imported += 1
        except Exception as e:
            errors.append({"skater": r.name, "error": str(e)})

    for cr in cat_results:
        try:
            skater = await _get_or_create_skater(session, cr.name, cr.nationality, cr.club)
            existing = await session.execute(
                select(CategoryResult).where(
                    CategoryResult.competition_id == comp.id,
                    CategoryResult.skater_id == skater.id,
                    CategoryResult.category == cr.category,
                )
            )
            if existing.scalar_one_or_none():
                cat_skipped += 1
                continue
            cat_result = CategoryResult(
                competition_id=comp.id,
                skater_id=skater.id,
                category=cr.category or "UNKNOWN",
                overall_rank=cr.overall_rank,
                combined_total=cr.combined_total,
                segment_count=cr.segment_count,
                sp_rank=cr.sp_rank,
                fs_rank=cr.fs_rank,
            )
            session.add(cat_result)
            cat_imported += 1
        except Exception as e:
            errors.append({"skater": cr.name, "error": str(e)})

    status = "success" if not errors else "partial"
    import_log = {
        "status": status,
        "events_found": len(events),
        "scores_imported": imported,
        "scores_skipped": skipped,
        "category_results_imported": cat_imported,
        "category_results_skipped": cat_skipped,
        "errors": errors,
    }
    comp.last_import_log = import_log
    await session.commit()

    return {
        "competition_id": competition_id,
        **import_log,
    }


async def run_enrich(session: AsyncSession, competition_id: int, force: bool = False) -> dict:
    """Enrich scores with PDF element details. Returns the enrich result dict."""
    comp = await session.get(Competition, competition_id)
    if not comp:
        raise ValueError(f"Competition {competition_id} not found")

    scraper = get_scraper(comp.url)
    events, _, _, _ = await scraper.scrape(comp.url)
    pdf_urls = [e.pdf_url for e in events if e.pdf_url]

    if not pdf_urls:
        return {"competition_id": competition_id, "pdfs_downloaded": 0, "scores_enriched": 0, "errors": []}

    slug = url_to_slug(comp.url)
    pdf_paths = await download_pdfs(pdf_urls, slug)

    enriched = 0
    unmatched = []
    errors = []

    for pdf_path in pdf_paths:
        try:
            parsed = parse_elements(pdf_path)
            for entry in parsed:
                skater_name = entry["skater_name"]
                elements = entry["elements"]
                seg_code = extract_segment_code(entry.get("category_segment"))
                stmt = (
                    select(Score)
                    .join(Skater)
                    .where(
                        Score.competition_id == comp.id,
                        Skater.name == skater_name,
                    )
                )
                if seg_code:
                    stmt = stmt.where(Score.segment == seg_code)
                result = await session.execute(stmt)
                scores = result.scalars().all()
                if scores:
                    for score in scores:
                        if not score.elements or force:
                            score.elements = elements
                            score.pdf_path = str(pdf_path)
                            enriched += 1
                else:
                    unmatched.append(skater_name)
        except Exception as e:
            errors.append({"file": str(pdf_path), "error": str(e)})

    await session.commit()
    return {
        "competition_id": competition_id,
        "pdfs_downloaded": len(pdf_paths),
        "scores_enriched": enriched,
        "unmatched": unmatched,
        "errors": errors,
    }
```

- [ ] **Step 2: Verify existing tests still pass**

Run: `cd /Users/julien/projects/figure-skating-analyzer && PATH="/opt/homebrew/bin:$PATH" uv run pytest backend/tests/ -v --timeout=30`
Expected: all existing tests pass (new service is not yet wired up)

- [ ] **Step 3: Commit**

```bash
git add backend/app/services/import_service.py
git commit -m "refactor: extract import/enrich logic into import_service module"
```

---

### Task 3: Wire up JobQueue to import_service and update competition routes

**Files:**
- Modify: `backend/app/main.py`
- Modify: `backend/app/routes/competitions.py`
- Create: `backend/app/routes/jobs.py`

- [ ] **Step 1: Create jobs router**

```python
# backend/app/routes/jobs.py
from __future__ import annotations

from litestar import Router, get
from litestar.exceptions import NotFoundException

from app.services.job_queue import job_queue


@get("/")
async def list_jobs() -> list[dict]:
    return job_queue.list_jobs()


@get("/{job_id:str}")
async def get_job(job_id: str) -> dict:
    job = job_queue.get_job(job_id)
    if not job:
        raise NotFoundException(f"Job {job_id} not found")
    return job


router = Router(
    path="/api/jobs",
    route_handlers=[list_jobs, get_job],
)
```

- [ ] **Step 2: Create the job handler and wire into lifespan**

Update `backend/app/main.py` to start/stop the queue worker and register the job handler:

Add imports at top:
```python
from app.services.job_queue import job_queue
from app.services.import_service import run_import, run_enrich
from app.database import async_session_factory
from app.routes.jobs import router as jobs_router
```

Replace the lifespan function:
```python
@asynccontextmanager
async def lifespan(_: Litestar) -> AsyncGenerator[None, None]:
    await init_db()

    async def _handle_job(job: dict) -> dict:
        async with async_session_factory() as session:
            if job["type"] == "import":
                return await run_import(session, job["competition_id"], force=False)
            elif job["type"] == "reimport":
                return await run_import(session, job["competition_id"], force=True)
            elif job["type"] == "enrich":
                return await run_enrich(session, job["competition_id"], force=False)
            else:
                raise ValueError(f"Unknown job type: {job['type']}")

    job_queue.set_handler(_handle_job)
    await job_queue.start_worker()
    try:
        yield
    finally:
        await job_queue.stop_worker()
```

Add `jobs_router` to the route_handlers list in the `Litestar(...)` constructor.

- [ ] **Step 3: Update competition import/enrich endpoints to submit jobs**

In `backend/app/routes/competitions.py`:

Replace the `import_competition` handler:
```python
@post("/{competition_id:int}/import")
async def import_competition(competition_id: int, session: AsyncSession) -> dict:
    comp = await session.get(Competition, competition_id)
    if not comp:
        raise NotFoundException(f"Competition {competition_id} not found")
    from app.services.job_queue import job_queue
    return job_queue.create_job("import", competition_id)
```

Replace the `enrich_competition` handler:
```python
@post("/{competition_id:int}/enrich")
async def enrich_competition(competition_id: int, session: AsyncSession) -> dict:
    comp = await session.get(Competition, competition_id)
    if not comp:
        raise NotFoundException(f"Competition {competition_id} not found")
    from app.services.job_queue import job_queue
    return job_queue.create_job("enrich", competition_id)
```

Add a reimport endpoint (currently reimport is import with `?force=true`, keep that working):
```python
@post("/{competition_id:int}/reimport")
async def reimport_competition(competition_id: int, session: AsyncSession) -> dict:
    comp = await session.get(Competition, competition_id)
    if not comp:
        raise NotFoundException(f"Competition {competition_id} not found")
    from app.services.job_queue import job_queue
    return job_queue.create_job("reimport", competition_id)
```

Also keep the old `?force=true` query param working on the import endpoint by checking for it:
```python
@post("/{competition_id:int}/import")
async def import_competition(competition_id: int, session: AsyncSession, force: bool = False) -> dict:
    comp = await session.get(Competition, competition_id)
    if not comp:
        raise NotFoundException(f"Competition {competition_id} not found")
    from app.services.job_queue import job_queue
    job_type = "reimport" if force else "import"
    return job_queue.create_job(job_type, competition_id)
```

Remove the old inline import/enrich logic and the `_get_or_create_skater` helper from `competitions.py` (it now lives in `import_service.py`). Keep `import_competition`, `enrich_competition`, `get_import_status`, `bulk_import`, and the CRUD handlers.

Update `bulk_import` to submit jobs:
```python
@post("/bulk-import")
async def bulk_import(data: dict, session: AsyncSession) -> dict:
    from app.services.job_queue import job_queue

    urls: list[str] = data.get("urls", [])
    enrich: bool = data.get("enrich", False)
    season: str = data.get("season", "")
    discipline: str = data.get("discipline", "")

    job_ids = []
    for url in urls:
        # Get or create competition
        existing = await session.execute(
            select(Competition).where(Competition.url == url)
        )
        comp = existing.scalar_one_or_none()
        if not comp:
            comp = Competition(
                name=url, url=url,
                season=season or None, discipline=discipline or None,
            )
            session.add(comp)
            await session.flush()
            await session.refresh(comp)

        job = job_queue.create_job("import", comp.id)
        job_ids.append(job["id"])

        if enrich:
            enrich_job = job_queue.create_job("enrich", comp.id)
            job_ids.append(enrich_job["id"])

    await session.commit()
    return {"job_ids": job_ids, "total": len(job_ids)}
```

Remove unused imports from `competitions.py` (`sa_delete`, `Score`, `CategoryResult`, `Skater`, `get_scraper`, `download_pdfs`, `url_to_slug`, `parse_elements`, `extract_segment_code`, `date_type`).

Add `reimport_competition` to the `route_handlers` list in the router.

- [ ] **Step 4: Verify the app starts and existing tests pass**

Run: `cd /Users/julien/projects/figure-skating-analyzer && PATH="/opt/homebrew/bin:$PATH" uv run pytest backend/tests/ -v --timeout=30`

- [ ] **Step 5: Commit**

```bash
git add backend/app/routes/jobs.py backend/app/routes/competitions.py backend/app/main.py
git commit -m "feat: wire job queue into import/enrich endpoints"
```

---

### Task 4: Update frontend API client

**Files:**
- Modify: `frontend/src/api/client.ts`

- [ ] **Step 1: Add JobInfo type and api.jobs namespace**

Add after the `BulkImportResult` interface:
```typescript
export interface JobInfo {
  id: string;
  type: "import" | "reimport" | "enrich";
  competition_id: number;
  status: "queued" | "running" | "completed" | "failed";
  result: ImportResult | EnrichResult | null;
  error: string | null;
  created_at: string;
}
```

Update the `api.competitions.import` and `api.competitions.enrich` return types from `ImportResult`/`EnrichResult` to `JobInfo`:
```typescript
import: (id: number) =>
  request<JobInfo>(`/competitions/${id}/import`, { method: "POST" }),
reimport: (id: number) =>
  request<JobInfo>(`/competitions/${id}/import?force=true`, { method: "POST" }),
enrich: (id: number) =>
  request<JobInfo>(`/competitions/${id}/enrich`, { method: "POST" }),
```

Add `jobs` namespace:
```typescript
jobs: {
  list: () => request<JobInfo[]>("/jobs/"),
  get: (id: string) => request<JobInfo>(`/jobs/${id}`),
},
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/api/client.ts
git commit -m "feat: add JobInfo type and jobs API to frontend client"
```

---

### Task 5: Update CompetitionsPage for job queue UI

**Files:**
- Modify: `frontend/src/pages/CompetitionsPage.tsx`

- [ ] **Step 1: Replace single-id tracking with job map and polling**

Rewrite the state and mutation logic in `CompetitionsPage.tsx`:

Replace state variables:
```typescript
// Remove these:
// const [importingId, setImportingId] = useState<number | null>(null);
// const [enrichingId, setEnrichingId] = useState<number | null>(null);

// Add these:
const [activeJobs, setActiveJobs] = useState<Record<string, JobInfo>>({});
// Maps competition_id → list of active job IDs for that competition
const competitionJobs: Record<number, string[]> = {};
for (const [jobId, job] of Object.entries(activeJobs)) {
  if (job.status === "queued" || job.status === "running") {
    if (!competitionJobs[job.competition_id]) {
      competitionJobs[job.competition_id] = [];
    }
    competitionJobs[job.competition_id].push(jobId);
  }
}
```

Add import for `JobInfo` and `useEffect` / `useRef`:
```typescript
import { useState, useEffect, useRef } from "react";
import { api, Competition, CreateCompetitionPayload, ImportResult, EnrichResult, JobInfo } from "../api/client";
```

Add polling effect:
```typescript
const pollIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

useEffect(() => {
  const activeJobIds = Object.entries(activeJobs)
    .filter(([, j]) => j.status === "queued" || j.status === "running")
    .map(([id]) => id);

  if (activeJobIds.length === 0) {
    if (pollIntervalRef.current) {
      clearInterval(pollIntervalRef.current);
      pollIntervalRef.current = null;
    }
    return;
  }

  if (pollIntervalRef.current) return; // already polling

  pollIntervalRef.current = setInterval(async () => {
    const updates: Record<string, JobInfo> = {};
    let anyChanged = false;
    for (const jobId of activeJobIds) {
      try {
        const job = await api.jobs.get(jobId);
        updates[jobId] = job;
        if (job.status !== activeJobs[jobId]?.status) {
          anyChanged = true;
        }
        if (job.status === "completed" || job.status === "failed") {
          anyChanged = true;
          // Refresh competition list when a job finishes
          qc.invalidateQueries({ queryKey: ["competitions"] });
          qc.invalidateQueries({ queryKey: ["scores"] });
          // Show result
          if (job.status === "completed" && job.result) {
            if (job.type === "enrich") {
              setEnrichResults((prev) => ({
                ...prev,
                [job.competition_id]: job.result as EnrichResult,
              }));
              setDismissedEnrich((prev) => {
                const next = new Set(prev);
                next.delete(job.competition_id);
                return next;
              });
            } else {
              setImportResults((prev) => ({
                ...prev,
                [job.competition_id]: job.result as ImportResult,
              }));
              setDismissedResults((prev) => {
                const next = new Set(prev);
                next.delete(job.competition_id);
                return next;
              });
            }
          }
        }
      } catch {
        // Job may have been cleaned up
        updates[jobId] = { ...activeJobs[jobId], status: "failed", error: "Lost contact with job" };
        anyChanged = true;
      }
    }
    if (anyChanged) {
      setActiveJobs((prev) => ({ ...prev, ...updates }));
    }
  }, 2000);

  return () => {
    if (pollIntervalRef.current) {
      clearInterval(pollIntervalRef.current);
      pollIntervalRef.current = null;
    }
  };
}, [activeJobs]);
```

- [ ] **Step 2: Update mutations to track jobs instead of single IDs**

Replace the import/reimport/enrich mutations:
```typescript
const importMutation = useMutation({
  mutationFn: (id: number) => api.competitions.import(id),
  onSuccess: (job: JobInfo) => {
    setActiveJobs((prev) => ({ ...prev, [job.id]: job }));
  },
});

const reimportMutation = useMutation({
  mutationFn: (id: number) => api.competitions.reimport(id),
  onSuccess: (job: JobInfo) => {
    setActiveJobs((prev) => ({ ...prev, [job.id]: job }));
  },
});

const enrichMutation = useMutation({
  mutationFn: (id: number) => api.competitions.enrich(id),
  onSuccess: (job: JobInfo) => {
    setActiveJobs((prev) => ({ ...prev, [job.id]: job }));
  },
});
```

- [ ] **Step 3: Update button rendering for queue-aware states**

In the competition row rendering, replace the button disabled/label logic.

For each competition, derive status:
```typescript
const compJobs = competitionJobs[c.id] || [];
const hasActiveJob = compJobs.length > 0;
const activeJobTypes = compJobs.map((jid) => activeJobs[jid]?.type);
const isImporting = activeJobTypes.includes("import") || activeJobTypes.includes("reimport");
const isEnriching = activeJobTypes.includes("enrich");

// For queued state detection
const importJobStatus = compJobs
  .map((jid) => activeJobs[jid])
  .find((j) => j?.type === "import" || j?.type === "reimport")?.status;
const enrichJobStatus = compJobs
  .map((jid) => activeJobs[jid])
  .find((j) => j?.type === "enrich")?.status;
```

Update import button label:
```typescript
{importJobStatus === "queued"
  ? "En file d'attente"
  : importJobStatus === "running"
    ? "Importation..."
    : "Importer"}
```

Update enrich button label:
```typescript
{enrichJobStatus === "queued"
  ? "En file d'attente"
  : enrichJobStatus === "running"
    ? "Enrichissement..."
    : "Enrichir PDF"}
```

Disable import/reimport buttons when that competition already has an import job active. Disable enrich button when that competition already has an enrich job active. Do NOT globally disable — other competitions' buttons stay enabled (they just queue).

- [ ] **Step 4: Verify the app compiles**

Run: `cd /Users/julien/projects/figure-skating-analyzer/frontend && PATH="/opt/homebrew/bin:$PATH" npx tsc --noEmit`

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/CompetitionsPage.tsx
git commit -m "feat: queue-aware competition import UI with polling and multi-job tracking"
```

---

### Task 6: Integration test and cleanup

- [ ] **Step 1: Run full test suite**

Run: `cd /Users/julien/projects/figure-skating-analyzer && PATH="/opt/homebrew/bin:$PATH" uv run pytest backend/tests/ -v --timeout=30`

- [ ] **Step 2: Fix any broken tests**

The existing `test_integration.py` likely calls import/enrich endpoints and expects the old response shape. Update those tests to expect `{id, type, competition_id, status: "queued", ...}` instead of `{competition_id, status: "success", ...}`.

- [ ] **Step 3: Verify frontend builds**

Run: `cd /Users/julien/projects/figure-skating-analyzer/frontend && PATH="/opt/homebrew/bin:$PATH" npm run build`

- [ ] **Step 4: Final commit**

```bash
git add -A
git commit -m "test: update integration tests for job queue responses"
```
