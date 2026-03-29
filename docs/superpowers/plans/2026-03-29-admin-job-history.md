# Admin Job History Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a persistent job history with an admin "Tâches" tab showing import/reimport/enrich jobs from the last 7 days, with detail modal and cancel support.

**Architecture:** Replace in-memory job storage with a `Job` SQLAlchemy model. The in-memory asyncio queue still drives execution, but all state is persisted to SQLite. The frontend gets a new tab in SettingsPage that polls `/api/jobs/` and renders a job list with a detail modal and `...` action menu.

**Tech Stack:** Python/Litestar/SQLAlchemy (backend), React/TypeScript/TanStack Query (frontend), Tailwind CSS

---

### Task 1: Create `Job` SQLAlchemy Model

**Files:**
- Create: `backend/app/models/job.py`
- Modify: `backend/app/models/__init__.py`

- [ ] **Step 1: Create the Job model**

```python
# backend/app/models/job.py
from datetime import datetime
from typing import Optional

from sqlalchemy import String, Text, JSON, DateTime, Integer, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[str] = mapped_column(String(12), primary_key=True)
    type: Mapped[str] = mapped_column(String(20), nullable=False)
    trigger: Mapped[str] = mapped_column(String(10), nullable=False, default="manual")
    competition_id: Mapped[int] = mapped_column(Integer, ForeignKey("competitions.id"), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="queued")
    result: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    competition: Mapped["Competition"] = relationship("Competition", back_populates="jobs")  # noqa: F821
```

- [ ] **Step 2: Register the model in `__init__.py`**

Add to `backend/app/models/__init__.py`:

```python
from app.models.job import Job
```

And add `"Job"` to the `__all__` list.

- [ ] **Step 3: Add `jobs` relationship to Competition model**

In `backend/app/models/competition.py`, add after the `category_results` relationship:

```python
    jobs: Mapped[list["Job"]] = relationship(  # noqa: F821
        "Job", back_populates="competition", cascade="all, delete-orphan"
    )
```

- [ ] **Step 4: Commit**

```bash
git add backend/app/models/job.py backend/app/models/__init__.py backend/app/models/competition.py
git commit -m "feat: add Job SQLAlchemy model for persistent job history"
```

---

### Task 2: Rewrite `job_queue.py` to Persist to DB

**Files:**
- Modify: `backend/app/services/job_queue.py`

- [ ] **Step 1: Write tests for DB-backed job queue**

Create `backend/tests/test_job_queue_db.py`:

```python
import asyncio
from datetime import datetime, timezone, timedelta

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.job import Job
from app.models.competition import Competition
from app.services.job_queue import JobQueue


@pytest_asyncio.fixture
async def competition(db_session: AsyncSession):
    comp = Competition(name="Test Comp", url="http://example.com/test")
    db_session.add(comp)
    await db_session.commit()
    await db_session.refresh(comp)
    return comp


@pytest_asyncio.fixture
async def queue(db_session: AsyncSession):
    q = JobQueue()
    q.set_session_factory(lambda: db_session)
    return q


async def test_create_job_persists(queue, competition, db_session):
    job = await queue.create_job("import", competition.id, trigger="manual")
    assert job["id"] is not None
    assert job["status"] == "queued"
    assert job["trigger"] == "manual"

    row = await db_session.get(Job, job["id"])
    assert row is not None
    assert row.status == "queued"
    assert row.trigger == "manual"


async def test_list_jobs_from_db(queue, competition, db_session):
    await queue.create_job("import", competition.id)
    await queue.create_job("enrich", competition.id)

    jobs = await queue.list_jobs()
    assert len(jobs) == 2
    # Newest first
    assert jobs[0]["created_at"] >= jobs[1]["created_at"]


async def test_get_job_from_db(queue, competition, db_session):
    job = await queue.create_job("import", competition.id)
    fetched = await queue.get_job(job["id"])
    assert fetched is not None
    assert fetched["id"] == job["id"]
    assert fetched["competition_name"] == "Test Comp"


async def test_get_job_not_found(queue):
    result = await queue.get_job("nonexistent")
    assert result is None


async def test_cancel_queued_job(queue, competition, db_session):
    job = await queue.create_job("import", competition.id)
    result = await queue.cancel_job(job["id"])
    assert result is True

    row = await db_session.get(Job, job["id"])
    assert row.status == "cancelled"
    assert row.completed_at is not None


async def test_cancel_running_job_fails(queue, competition, db_session):
    job = await queue.create_job("import", competition.id)
    row = await db_session.get(Job, job["id"])
    row.status = "running"
    await db_session.commit()

    result = await queue.cancel_job(job["id"])
    assert result is False


async def test_cancel_nonexistent_job_fails(queue):
    result = await queue.cancel_job("nope")
    assert result is False


async def test_cleanup_old_jobs(queue, competition, db_session):
    old_job = Job(
        id="old123456789",
        type="import",
        trigger="manual",
        competition_id=competition.id,
        status="completed",
        created_at=datetime.now(timezone.utc) - timedelta(days=10),
        completed_at=datetime.now(timezone.utc) - timedelta(days=10),
    )
    recent_job = Job(
        id="new123456789",
        type="import",
        trigger="manual",
        competition_id=competition.id,
        status="completed",
        created_at=datetime.now(timezone.utc) - timedelta(days=1),
        completed_at=datetime.now(timezone.utc) - timedelta(days=1),
    )
    db_session.add_all([old_job, recent_job])
    await db_session.commit()

    await queue.cleanup(days=7)

    assert await db_session.get(Job, "old123456789") is None
    assert await db_session.get(Job, "new123456789") is not None


async def test_cleanup_marks_stale_running_as_failed(queue, competition, db_session):
    stale = Job(
        id="stale1234567",
        type="import",
        trigger="manual",
        competition_id=competition.id,
        status="running",
        created_at=datetime.now(timezone.utc) - timedelta(hours=1),
        started_at=datetime.now(timezone.utc) - timedelta(hours=1),
    )
    db_session.add(stale)
    await db_session.commit()

    await queue.cleanup(days=7)

    await db_session.refresh(stale)
    assert stale.status == "failed"
    assert stale.error == "Server restarted during execution"
    assert stale.completed_at is not None


@pytest.mark.asyncio
async def test_worker_processes_and_persists(queue, competition, db_session):
    async def handler(job):
        return {"scores_imported": 5}

    queue.set_handler(handler)
    job = await queue.create_job("import", competition.id)
    await queue.start_worker()
    await asyncio.wait_for(queue._queue.join(), timeout=2.0)
    await queue.stop_worker()

    row = await db_session.get(Job, job["id"])
    assert row.status == "completed"
    assert row.result == {"scores_imported": 5}
    assert row.started_at is not None
    assert row.completed_at is not None


@pytest.mark.asyncio
async def test_worker_handles_failure_and_persists(queue, competition, db_session):
    async def handler(job):
        raise ValueError("scrape failed")

    queue.set_handler(handler)
    job = await queue.create_job("import", competition.id)
    await queue.start_worker()
    await asyncio.wait_for(queue._queue.join(), timeout=2.0)
    await queue.stop_worker()

    row = await db_session.get(Job, job["id"])
    assert row.status == "failed"
    assert "scrape failed" in row.error
    assert row.completed_at is not None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && uv run pytest tests/test_job_queue_db.py -v`
Expected: FAIL (methods don't exist yet)

- [ ] **Step 3: Rewrite `job_queue.py` with DB persistence**

Replace `backend/app/services/job_queue.py` with:

```python
from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timezone, timedelta
from typing import Any, Callable, Awaitable

from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload


class JobQueue:
    """Async job queue with SQLite persistence. Processes one job at a time."""

    def __init__(self) -> None:
        self._queue: asyncio.Queue[str] = asyncio.Queue()
        self._handler: Callable[[dict], Awaitable[Any]] | None = None
        self._worker_task: asyncio.Task | None = None
        self._session_factory: Callable[[], AsyncSession] | None = None

    def set_session_factory(self, factory: Callable) -> None:
        self._session_factory = factory

    def _get_session(self) -> AsyncSession:
        if self._session_factory is None:
            raise RuntimeError("Session factory not set on JobQueue")
        return self._session_factory()

    async def create_job(
        self, job_type: str, competition_id: int, trigger: str = "manual"
    ) -> dict:
        from app.models.job import Job

        job_id = uuid.uuid4().hex[:12]
        now = datetime.now(timezone.utc)

        job = Job(
            id=job_id,
            type=job_type,
            trigger=trigger,
            competition_id=competition_id,
            status="queued",
            created_at=now,
        )

        session = self._get_session()
        # Check if session is a context manager (factory) or direct session (test)
        if hasattr(session, "__aenter__"):
            async with session as s:
                s.add(job)
                await s.commit()
        else:
            session.add(job)
            await session.commit()

        self._queue.put_nowait(job_id)

        return {
            "id": job_id,
            "type": job_type,
            "trigger": trigger,
            "competition_id": competition_id,
            "status": "queued",
            "result": None,
            "error": None,
            "created_at": now.isoformat(),
            "started_at": None,
            "completed_at": None,
        }

    async def get_job(self, job_id: str) -> dict | None:
        from app.models.job import Job

        session = self._get_session()
        if hasattr(session, "__aenter__"):
            async with session as s:
                stmt = select(Job).options(joinedload(Job.competition)).where(Job.id == job_id)
                row = (await s.execute(stmt)).scalar_one_or_none()
        else:
            stmt = select(Job).options(joinedload(Job.competition)).where(Job.id == job_id)
            row = (await session.execute(stmt)).scalar_one_or_none()

        if not row:
            return None
        return self._row_to_dict(row)

    async def list_jobs(self) -> list[dict]:
        from app.models.job import Job

        stmt = (
            select(Job)
            .options(joinedload(Job.competition))
            .order_by(Job.created_at.desc())
        )

        session = self._get_session()
        if hasattr(session, "__aenter__"):
            async with session as s:
                rows = (await s.execute(stmt)).scalars().all()
        else:
            rows = (await session.execute(stmt)).scalars().all()

        return [self._row_to_dict(r) for r in rows]

    async def cancel_job(self, job_id: str) -> bool:
        from app.models.job import Job

        session = self._get_session()
        if hasattr(session, "__aenter__"):
            async with session as s:
                row = await s.get(Job, job_id)
                if not row or row.status != "queued":
                    return False
                row.status = "cancelled"
                row.completed_at = datetime.now(timezone.utc)
                await s.commit()
        else:
            row = await session.get(Job, job_id)
            if not row or row.status != "queued":
                return False
            row.status = "cancelled"
            row.completed_at = datetime.now(timezone.utc)
            await session.commit()

        # Remove from in-memory queue
        new_queue: asyncio.Queue[str] = asyncio.Queue()
        while not self._queue.empty():
            try:
                item = self._queue.get_nowait()
                if item != job_id:
                    new_queue.put_nowait(item)
                self._queue.task_done()
            except asyncio.QueueEmpty:
                break
        self._queue = new_queue

        return True

    async def cleanup(self, days: int = 7) -> None:
        from app.models.job import Job

        cutoff = datetime.now(timezone.utc) - timedelta(days=days)

        session = self._get_session()
        if hasattr(session, "__aenter__"):
            async with session as s:
                # Delete old jobs
                await s.execute(delete(Job).where(Job.created_at < cutoff))
                # Mark stale running jobs as failed
                stmt = select(Job).where(Job.status == "running")
                stale = (await s.execute(stmt)).scalars().all()
                for job in stale:
                    job.status = "failed"
                    job.error = "Server restarted during execution"
                    job.completed_at = datetime.now(timezone.utc)
                await s.commit()
        else:
            await session.execute(delete(Job).where(Job.created_at < cutoff))
            stmt = select(Job).where(Job.status == "running")
            stale = (await session.execute(stmt)).scalars().all()
            for job in stale:
                job.status = "failed"
                job.error = "Server restarted during execution"
                job.completed_at = datetime.now(timezone.utc)
            await session.commit()

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
        from app.models.job import Job

        while True:
            job_id = await self._queue.get()

            # Check if cancelled while in queue
            session = self._get_session()
            if hasattr(session, "__aenter__"):
                async with session as s:
                    row = await s.get(Job, job_id)
            else:
                row = await session.get(Job, job_id)

            if not row or row.status == "cancelled" or not self._handler:
                self._queue.task_done()
                continue

            now = datetime.now(timezone.utc)

            # Mark as running
            if hasattr(session, "__aenter__"):
                async with self._get_session() as s:
                    row = await s.get(Job, job_id)
                    row.status = "running"
                    row.started_at = now
                    await s.commit()
            else:
                row.status = "running"
                row.started_at = now
                await session.commit()

            job_dict = {
                "id": job_id,
                "type": row.type,
                "competition_id": row.competition_id,
            }

            try:
                result = await self._handler(job_dict)
                completed_at = datetime.now(timezone.utc)
                if hasattr(self._get_session(), "__aenter__"):
                    async with self._get_session() as s:
                        row = await s.get(Job, job_id)
                        row.status = "completed"
                        row.result = result
                        row.completed_at = completed_at
                        await s.commit()
                else:
                    await session.refresh(row)
                    row.status = "completed"
                    row.result = result
                    row.completed_at = completed_at
                    await session.commit()
            except Exception as e:
                completed_at = datetime.now(timezone.utc)
                if hasattr(self._get_session(), "__aenter__"):
                    async with self._get_session() as s:
                        row = await s.get(Job, job_id)
                        row.status = "failed"
                        row.error = str(e)
                        row.completed_at = completed_at
                        await s.commit()
                else:
                    await session.refresh(row)
                    row.status = "failed"
                    row.error = str(e)
                    row.completed_at = completed_at
                    await session.commit()
            finally:
                self._queue.task_done()

    @staticmethod
    def _row_to_dict(row) -> dict:
        return {
            "id": row.id,
            "type": row.type,
            "trigger": row.trigger,
            "competition_id": row.competition_id,
            "competition_name": row.competition.name if row.competition else None,
            "status": row.status,
            "result": row.result,
            "error": row.error,
            "created_at": row.created_at.isoformat() if row.created_at else None,
            "started_at": row.started_at.isoformat() if row.started_at else None,
            "completed_at": row.completed_at.isoformat() if row.completed_at else None,
        }


# Singleton instance
job_queue = JobQueue()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && uv run pytest tests/test_job_queue_db.py -v`
Expected: All PASS

- [ ] **Step 5: Delete old test file**

Delete `backend/tests/test_job_queue.py` (tests the old in-memory-only implementation).

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/job_queue.py backend/tests/test_job_queue_db.py
git rm backend/tests/test_job_queue.py
git commit -m "feat: rewrite job queue with DB persistence, cleanup, and cancel"
```

---

### Task 3: Update Callers to Pass `trigger` and Use Async `create_job`

**Files:**
- Modify: `backend/app/main.py`
- Modify: `backend/app/routes/competitions.py`

- [ ] **Step 1: Update `main.py` lifespan to set session factory, run cleanup, and pass trigger**

In `backend/app/main.py`, update the `lifespan` function:

After `await init_db()`, add:
```python
    job_queue.set_session_factory(async_session_factory)
    await job_queue.cleanup(days=7)
```

Update `_handle_job` — no changes needed (it receives a dict with `type` and `competition_id`).

In `_polling_loop`, update the two `create_job` calls to be async and pass `trigger="auto"`:
```python
                    await job_queue.create_job("import", comp.id, trigger="auto")
                    await job_queue.create_job("enrich", comp.id, trigger="auto")
```

- [ ] **Step 2: Update `routes/competitions.py` to use async create_job with trigger**

In `import_competition` (line ~134):
```python
    return await job_queue.create_job(job_type, competition_id, trigger="manual")
```

In `enrich_competition` (line ~155):
```python
    return await job_queue.create_job("enrich", competition_id, trigger="manual")
```

In `bulk_import` (line ~247-251):
```python
        job = await job_queue.create_job("import", comp.id, trigger="bulk")
        job_ids.append(job["id"])

        if enrich:
            enrich_job = await job_queue.create_job("enrich", comp.id, trigger="bulk")
            job_ids.append(enrich_job["id"])
```

- [ ] **Step 3: Run full test suite**

Run: `cd backend && uv run pytest -v`
Expected: All PASS

- [ ] **Step 4: Commit**

```bash
git add backend/app/main.py backend/app/routes/competitions.py
git commit -m "feat: update job callers for async create_job with trigger parameter"
```

---

### Task 4: Update Job API Routes

**Files:**
- Modify: `backend/app/routes/jobs.py`
- Create: `backend/tests/test_jobs_api.py`

- [ ] **Step 1: Write API tests**

Create `backend/tests/test_jobs_api.py`:

```python
import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.competition import Competition
from app.models.job import Job
from datetime import datetime, timezone


@pytest_asyncio.fixture
async def competition(db_session: AsyncSession):
    comp = Competition(name="API Test Comp", url="http://example.com/api-test")
    db_session.add(comp)
    await db_session.commit()
    await db_session.refresh(comp)
    return comp


@pytest_asyncio.fixture
async def sample_job(db_session: AsyncSession, competition):
    job = Job(
        id="testjob12345",
        type="import",
        trigger="manual",
        competition_id=competition.id,
        status="queued",
        created_at=datetime.now(timezone.utc),
    )
    db_session.add(job)
    await db_session.commit()
    return job


async def test_list_jobs_requires_admin(client, reader_token):
    resp = await client.get("/api/jobs/", headers={"Authorization": f"Bearer {reader_token}"})
    assert resp.status_code == 403


async def test_list_jobs_as_admin(client, admin_token, sample_job):
    resp = await client.get("/api/jobs/", headers={"Authorization": f"Bearer {admin_token}"})
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 1
    assert data[0]["id"] == "testjob12345"
    assert data[0]["competition_name"] == "API Test Comp"
    assert data[0]["trigger"] == "manual"


async def test_get_job_as_admin(client, admin_token, sample_job):
    resp = await client.get("/api/jobs/testjob12345", headers={"Authorization": f"Bearer {admin_token}"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == "testjob12345"
    assert data["competition_name"] == "API Test Comp"


async def test_get_job_not_found(client, admin_token):
    resp = await client.get("/api/jobs/nonexistent", headers={"Authorization": f"Bearer {admin_token}"})
    assert resp.status_code == 404


async def test_cancel_queued_job(client, admin_token, sample_job, db_session):
    resp = await client.post("/api/jobs/testjob12345/cancel", headers={"Authorization": f"Bearer {admin_token}"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "cancelled"


async def test_cancel_non_queued_job_fails(client, admin_token, sample_job, db_session):
    sample_job.status = "completed"
    await db_session.commit()

    resp = await client.post("/api/jobs/testjob12345/cancel", headers={"Authorization": f"Bearer {admin_token}"})
    assert resp.status_code == 400


async def test_cancel_requires_admin(client, reader_token, sample_job):
    resp = await client.post("/api/jobs/testjob12345/cancel", headers={"Authorization": f"Bearer {reader_token}"})
    assert resp.status_code == 403
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && uv run pytest tests/test_jobs_api.py -v`
Expected: FAIL

- [ ] **Step 3: Rewrite `routes/jobs.py`**

Replace `backend/app/routes/jobs.py`:

```python
from __future__ import annotations

from litestar import Router, get, post, Request
from litestar.exceptions import NotFoundException
from litestar.status_codes import HTTP_400_BAD_REQUEST
from litestar.response import Response

from app.auth.guards import require_admin
from app.services.job_queue import job_queue


@get("/")
async def list_jobs(request: Request) -> list[dict]:
    require_admin(request)
    return await job_queue.list_jobs()


@get("/{job_id:str}")
async def get_job(request: Request, job_id: str) -> dict:
    require_admin(request)
    job = await job_queue.get_job(job_id)
    if not job:
        raise NotFoundException(f"Job {job_id} not found")
    return job


@post("/{job_id:str}/cancel")
async def cancel_job(request: Request, job_id: str) -> Response:
    require_admin(request)
    success = await job_queue.cancel_job(job_id)
    if not success:
        return Response(
            content={"detail": "Job cannot be cancelled (not queued or not found)"},
            status_code=HTTP_400_BAD_REQUEST,
        )
    job = await job_queue.get_job(job_id)
    return Response(content=job, status_code=200)


router = Router(
    path="/api/jobs",
    route_handlers=[list_jobs, get_job, cancel_job],
)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && uv run pytest tests/test_jobs_api.py -v`
Expected: All PASS

- [ ] **Step 5: Run full test suite**

Run: `cd backend && uv run pytest -v`
Expected: All PASS

- [ ] **Step 6: Commit**

```bash
git add backend/app/routes/jobs.py backend/tests/test_jobs_api.py
git commit -m "feat: add admin-only job API with cancel endpoint"
```

---

### Task 5: Update Frontend API Types and Client

**Files:**
- Modify: `frontend/src/api/client.ts`

- [ ] **Step 1: Update `JobInfo` interface**

In `frontend/src/api/client.ts`, replace the `JobInfo` interface (around line 397):

```typescript
export interface JobInfo {
  id: string;
  type: "import" | "reimport" | "enrich";
  trigger: "manual" | "auto" | "bulk";
  competition_id: number;
  competition_name: string | null;
  status: "queued" | "running" | "completed" | "failed" | "cancelled";
  result: ImportResult | EnrichResult | null;
  error: string | null;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
}
```

- [ ] **Step 2: Add cancel API method**

In the `jobs` section of the api object (around line 791), add cancel:

```typescript
  jobs: {
    list: () => request<JobInfo[]>("/jobs/"),
    get: (id: string) => request<JobInfo>(`/jobs/${id}`),
    cancel: (id: string) => request<JobInfo>(`/jobs/${id}/cancel`, { method: "POST" }),
  },
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/api/client.ts
git commit -m "feat: update JobInfo type and add cancel API method"
```

---

### Task 6: Update JobContext for New Status

**Files:**
- Modify: `frontend/src/contexts/JobContext.tsx`

- [ ] **Step 1: Update status checks to include `cancelled`**

In `JobContext.tsx`, the polling logic filters on `"queued" | "running"` which is correct — cancelled jobs won't be polled. But the recovery logic on mount (line ~82) only tracks `queued`/`running` jobs, which is also correct.

No functional changes needed in JobContext — the `cancelled` status is terminal like `completed`/`failed`, and the existing filtering logic already handles it correctly (it only polls `queued` and `running` jobs).

However, the `trackBulkJobs` function creates placeholder JobInfo objects without the new fields. Update the placeholder in `trackBulkJobs` (around line 102):

```typescript
      newJobs[jid] = {
        id: jid,
        type: "import",
        trigger: "bulk",
        competition_id: 0,
        competition_name: null,
        status: "queued",
        result: null,
        error: null,
        created_at: "",
        started_at: null,
        completed_at: null,
      };
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/contexts/JobContext.tsx
git commit -m "fix: update JobContext placeholder to include new JobInfo fields"
```

---

### Task 7: Create Admin Job History Tab Component

**Files:**
- Create: `frontend/src/components/AdminJobsTab.tsx`

- [ ] **Step 1: Create the AdminJobsTab component**

Create `frontend/src/components/AdminJobsTab.tsx`:

```tsx
import { useState, useRef, useEffect } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api, type JobInfo, type ImportResult, type EnrichResult } from "../api/client";

function formatRelativeTime(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  const sec = Math.floor(diff / 1000);
  const min = Math.floor(sec / 60);
  const hr = Math.floor(min / 60);
  const day = Math.floor(hr / 24);
  if (sec < 60) return "à l'instant";
  if (min < 60) return `il y a ${min} min`;
  if (hr < 24) return `il y a ${hr} h`;
  return `il y a ${day} j`;
}

function formatFullDate(iso: string): string {
  return new Date(iso).toLocaleString("fr-FR", {
    dateStyle: "long",
    timeStyle: "short",
  });
}

function formatDuration(startedAt: string, completedAt: string): string {
  const ms = new Date(completedAt).getTime() - new Date(startedAt).getTime();
  const sec = Math.floor(ms / 1000);
  if (sec < 60) return `${sec}s`;
  const min = Math.floor(sec / 60);
  const rem = sec % 60;
  return `${min}m ${rem}s`;
}

const STATUS_ICONS: Record<string, { icon: string; className: string }> = {
  running: { icon: "progress_activity", className: "text-primary animate-spin" },
  queued: { icon: "schedule", className: "text-on-surface-variant" },
  completed: { icon: "check_circle", className: "text-green-600" },
  failed: { icon: "cancel", className: "text-error" },
  cancelled: { icon: "block", className: "text-on-surface-variant" },
};

const TYPE_LABELS: Record<string, string> = {
  import: "Import",
  reimport: "Réimport",
  enrich: "Enrichissement",
};

const TRIGGER_LABELS: Record<string, string> = {
  manual: "manuel",
  auto: "auto",
  bulk: "lot",
};

function resultSummary(job: JobInfo): string {
  if (!job.result) return "";
  if (job.type === "enrich") {
    const r = job.result as EnrichResult;
    return `${r.scores_enriched} score(s) enrichi(s)`;
  }
  const r = job.result as ImportResult;
  return `${r.scores_imported} score(s) importé(s)`;
}

function JobDetailModal({
  job,
  onClose,
}: {
  job: JobInfo;
  onClose: () => void;
}) {
  const overlayRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handleKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", handleKey);
    return () => document.removeEventListener("keydown", handleKey);
  }, [onClose]);

  const r = job.result;
  const isImport = job.type === "import" || job.type === "reimport";
  const isEnrich = job.type === "enrich";
  const importResult = isImport ? (r as ImportResult | null) : null;
  const enrichResult = isEnrich ? (r as EnrichResult | null) : null;

  return (
    <div
      ref={overlayRef}
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40"
      onClick={(e) => {
        if (e.target === overlayRef.current) onClose();
      }}
    >
      <div className="bg-surface-container-lowest rounded-2xl shadow-xl w-full max-w-lg mx-4 max-h-[80vh] overflow-y-auto">
        <div className="p-6 space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="font-headline font-bold text-on-surface text-lg">
              Détails de la tâche
            </h3>
            <button
              onClick={onClose}
              className="text-on-surface-variant hover:text-on-surface"
            >
              <span className="material-symbols-outlined">close</span>
            </button>
          </div>

          {/* Metadata */}
          <div className="grid grid-cols-2 gap-3 text-sm">
            <div>
              <span className="text-on-surface-variant">Type</span>
              <p className="text-on-surface font-medium">
                {TYPE_LABELS[job.type] ?? job.type}
                <span className="ml-1 text-on-surface-variant text-xs">
                  ({TRIGGER_LABELS[job.trigger] ?? job.trigger})
                </span>
              </p>
            </div>
            <div>
              <span className="text-on-surface-variant">Statut</span>
              <p className="text-on-surface font-medium flex items-center gap-1">
                <span
                  className={`material-symbols-outlined text-base ${STATUS_ICONS[job.status]?.className}`}
                >
                  {STATUS_ICONS[job.status]?.icon}
                </span>
                {job.status}
              </p>
            </div>
            <div>
              <span className="text-on-surface-variant">Compétition</span>
              <p className="text-on-surface font-medium">{job.competition_name ?? `#${job.competition_id}`}</p>
            </div>
            <div>
              <span className="text-on-surface-variant">Créé le</span>
              <p className="text-on-surface font-medium">{formatFullDate(job.created_at)}</p>
            </div>
            {job.started_at && (
              <div>
                <span className="text-on-surface-variant">Démarré le</span>
                <p className="text-on-surface font-medium">{formatFullDate(job.started_at)}</p>
              </div>
            )}
            {job.completed_at && (
              <div>
                <span className="text-on-surface-variant">Terminé le</span>
                <p className="text-on-surface font-medium">{formatFullDate(job.completed_at)}</p>
              </div>
            )}
          </div>

          {/* Import result */}
          {importResult && (
            <div className="bg-surface-container-low rounded-xl p-4 space-y-2">
              <h4 className="text-sm font-semibold text-on-surface">Résultat</h4>
              <div className="grid grid-cols-2 gap-2 text-sm">
                <div>
                  <span className="text-on-surface-variant">Épreuves trouvées</span>
                  <p className="font-mono text-on-surface">{importResult.events_found}</p>
                </div>
                <div>
                  <span className="text-on-surface-variant">Scores importés</span>
                  <p className="font-mono text-on-surface">{importResult.scores_imported}</p>
                </div>
                <div>
                  <span className="text-on-surface-variant">Scores ignorés</span>
                  <p className="font-mono text-on-surface">{importResult.scores_skipped}</p>
                </div>
                <div>
                  <span className="text-on-surface-variant">Classements</span>
                  <p className="font-mono text-on-surface">{importResult.category_results_imported}</p>
                </div>
              </div>
              {importResult.errors.length > 0 && (
                <div className="mt-2">
                  <p className="text-xs font-semibold text-error mb-1">Erreurs ({importResult.errors.length})</p>
                  <ul className="text-xs text-error/80 space-y-0.5">
                    {importResult.errors.map((e, i) => (
                      <li key={i}>{e.skater}: {e.error}</li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          )}

          {/* Enrich result */}
          {enrichResult && (
            <div className="bg-surface-container-low rounded-xl p-4 space-y-2">
              <h4 className="text-sm font-semibold text-on-surface">Résultat</h4>
              <div className="grid grid-cols-2 gap-2 text-sm">
                <div>
                  <span className="text-on-surface-variant">PDFs téléchargés</span>
                  <p className="font-mono text-on-surface">{enrichResult.pdfs_downloaded}</p>
                </div>
                <div>
                  <span className="text-on-surface-variant">Scores enrichis</span>
                  <p className="font-mono text-on-surface">{enrichResult.scores_enriched}</p>
                </div>
              </div>
              {enrichResult.unmatched.length > 0 && (
                <div className="mt-2">
                  <p className="text-xs font-semibold text-amber-600 mb-1">
                    Non appariés ({enrichResult.unmatched.length})
                  </p>
                  <ul className="text-xs text-on-surface-variant space-y-0.5">
                    {enrichResult.unmatched.map((u, i) => (
                      <li key={i}>{u}</li>
                    ))}
                  </ul>
                </div>
              )}
              {enrichResult.errors.length > 0 && (
                <div className="mt-2">
                  <p className="text-xs font-semibold text-error mb-1">Erreurs ({enrichResult.errors.length})</p>
                  <ul className="text-xs text-error/80 space-y-0.5">
                    {enrichResult.errors.map((e, i) => (
                      <li key={i}>{e.file}: {e.error}</li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          )}

          {/* Error */}
          {job.error && !job.result && (
            <div className="bg-error/10 rounded-xl p-4">
              <h4 className="text-sm font-semibold text-error mb-1">Erreur</h4>
              <p className="text-sm text-error/90 whitespace-pre-wrap">{job.error}</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function ActionMenu({
  job,
  onViewDetails,
  onCancel,
}: {
  job: JobInfo;
  onViewDetails: () => void;
  onCancel: () => void;
}) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handleClick = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, []);

  return (
    <div ref={ref} className="relative">
      <button
        onClick={() => setOpen(!open)}
        className="p-1 rounded-lg hover:bg-surface-container-high text-on-surface-variant hover:text-on-surface transition-colors"
      >
        <span className="material-symbols-outlined text-xl">more_vert</span>
      </button>
      {open && (
        <div className="absolute right-0 top-8 z-10 bg-surface-container-lowest rounded-xl shadow-lg py-1 min-w-[160px]">
          <button
            onClick={() => {
              onViewDetails();
              setOpen(false);
            }}
            className="w-full text-left px-4 py-2 text-sm text-on-surface hover:bg-surface-container-low flex items-center gap-2"
          >
            <span className="material-symbols-outlined text-base">visibility</span>
            Voir les détails
          </button>
          {job.status === "queued" && (
            <button
              onClick={() => {
                onCancel();
                setOpen(false);
              }}
              className="w-full text-left px-4 py-2 text-sm text-error hover:bg-surface-container-low flex items-center gap-2"
            >
              <span className="material-symbols-outlined text-base">cancel</span>
              Annuler
            </button>
          )}
        </div>
      )}
    </div>
  );
}

export default function AdminJobsTab() {
  const qc = useQueryClient();
  const [detailJob, setDetailJob] = useState<JobInfo | null>(null);

  const { data: jobs, isLoading } = useQuery({
    queryKey: ["admin-jobs"],
    queryFn: () => api.jobs.list(),
    refetchInterval: 5000,
  });

  const cancelMutation = useMutation({
    mutationFn: (id: string) => api.jobs.cancel(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["admin-jobs"] });
    },
  });

  if (isLoading) {
    return (
      <div className="flex justify-center py-12">
        <span className="material-symbols-outlined animate-spin text-primary text-3xl">
          progress_activity
        </span>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div>
        <h2 className="font-headline font-bold text-on-surface text-lg">Tâches</h2>
        <p className="text-sm text-on-surface-variant">
          Historique des 7 derniers jours
        </p>
      </div>

      {!jobs || jobs.length === 0 ? (
        <div className="bg-surface-container-lowest rounded-2xl p-8 text-center">
          <span className="material-symbols-outlined text-4xl text-on-surface-variant mb-2">
            task
          </span>
          <p className="text-on-surface-variant text-sm">Aucune tâche récente</p>
        </div>
      ) : (
        <div className="bg-surface-container-lowest rounded-2xl shadow-arctic overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-xs font-semibold text-on-surface-variant uppercase tracking-wider">
                <th className="px-4 py-3 w-10"></th>
                <th className="px-4 py-3">Type</th>
                <th className="px-4 py-3">Compétition</th>
                <th className="px-4 py-3">Début</th>
                <th className="px-4 py-3">Durée</th>
                <th className="px-4 py-3">Résultat</th>
                <th className="px-4 py-3 w-10"></th>
              </tr>
            </thead>
            <tbody className="divide-y divide-surface-container-high">
              {jobs.map((job) => {
                const si = STATUS_ICONS[job.status] ?? STATUS_ICONS.queued;
                return (
                  <tr key={job.id} className="hover:bg-surface-container-low/50 transition-colors">
                    <td className="px-4 py-3">
                      <span className={`material-symbols-outlined text-lg ${si.className}`}>
                        {si.icon}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-on-surface">
                      <span className="font-medium">{TYPE_LABELS[job.type] ?? job.type}</span>
                      <span className="ml-1.5 text-xs text-on-surface-variant">
                        {TRIGGER_LABELS[job.trigger] ?? job.trigger}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-on-surface max-w-[200px] truncate">
                      {job.competition_name ?? `#${job.competition_id}`}
                    </td>
                    <td className="px-4 py-3 text-on-surface-variant whitespace-nowrap">
                      {job.started_at ? formatRelativeTime(job.started_at) : "En attente"}
                    </td>
                    <td
                      className="px-4 py-3 font-mono text-on-surface-variant whitespace-nowrap"
                      title={job.completed_at ? formatFullDate(job.completed_at) : undefined}
                    >
                      {job.started_at && job.completed_at
                        ? formatDuration(job.started_at, job.completed_at)
                        : job.started_at
                          ? "..."
                          : "—"}
                    </td>
                    <td className="px-4 py-3 text-on-surface-variant max-w-[180px] truncate">
                      {job.error
                        ? <span className="text-error">{job.error}</span>
                        : resultSummary(job)}
                    </td>
                    <td className="px-4 py-3">
                      <ActionMenu
                        job={job}
                        onViewDetails={() => setDetailJob(job)}
                        onCancel={() => cancelMutation.mutate(job.id)}
                      />
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {detailJob && (
        <JobDetailModal job={detailJob} onClose={() => setDetailJob(null)} />
      )}
    </div>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/components/AdminJobsTab.tsx
git commit -m "feat: add AdminJobsTab component with job list, detail modal, and cancel"
```

---

### Task 8: Wire Tab into SettingsPage

**Files:**
- Modify: `frontend/src/pages/SettingsPage.tsx`

- [ ] **Step 1: Add import for AdminJobsTab**

At the top of `SettingsPage.tsx`, add:

```typescript
import AdminJobsTab from "../components/AdminJobsTab";
```

- [ ] **Step 2: Update activeTab type**

Change the `useState` (around line 286):

```typescript
const [activeTab, setActiveTab] = useState<"general" | "users" | "training" | "jobs">("general");
```

- [ ] **Step 3: Add the tab button**

After the "Entraînement" button closing `)}` (around line 483), add before the closing `</div>`:

```tsx
        <button
          onClick={() => setActiveTab("jobs")}
          className={`px-5 py-2 text-sm font-semibold transition-colors border-b-2 ${
            activeTab === "jobs"
              ? "text-primary border-primary"
              : "text-on-surface-variant border-transparent hover:text-on-surface"
          }`}
        >
          Tâches
        </button>
```

- [ ] **Step 4: Add the tab content**

After the training tab content block (after the last `{activeTab === "training" && (...)}`), add:

```tsx
      {activeTab === "jobs" && <AdminJobsTab />}
```

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/SettingsPage.tsx
git commit -m "feat: wire AdminJobsTab into SettingsPage as 'Tâches' tab"
```

---

### Task 9: Run Full Test Suite and Manual Verification

- [ ] **Step 1: Run backend tests**

Run: `cd backend && uv run pytest -v`
Expected: All PASS

- [ ] **Step 2: Start dev servers and verify**

Run: `make dev-backend` and `make dev-frontend`

Manual checks:
1. Navigate to Administration page
2. See "Tâches" tab
3. Click it — should show "Aucune tâche récente" or existing job history
4. Trigger an import from the Competitions page
5. Switch to Tâches tab — see the job appear with status updates
6. Click `...` → "Voir les détails" — modal opens with job metadata and result
7. Submit multiple imports, cancel a queued one via `...` → "Annuler"

- [ ] **Step 3: Commit any fixes if needed**
