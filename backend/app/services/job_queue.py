from __future__ import annotations

import asyncio
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Awaitable

from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.models.job import Job


class JobQueue:
    """Async job queue with DB persistence. Processes one job at a time."""

    def __init__(self) -> None:
        self._queue: asyncio.Queue[str] = asyncio.Queue()
        self._handler: Callable[[dict], Awaitable[Any]] | None = None
        self._worker_task: asyncio.Task | None = None
        self._session_factory: Callable | None = None
        self._owns_session = True  # True = create & commit/close sessions; False = use shared session

    def set_session_factory(self, factory: Callable, *, owns_session: bool = True) -> None:
        self._session_factory = factory
        self._owns_session = owns_session

    @asynccontextmanager
    async def _session_scope(self):
        if self._owns_session:
            # Production: factory is async_sessionmaker — create, commit, and close
            async with self._session_factory() as session:
                yield session
                await session.commit()
        else:
            # Tests: factory returns a shared session — flush but don't commit/close
            session = self._session_factory()
            yield session
            await session.flush()

    async def create_job(
        self, job_type: str, competition_id: int, trigger: str = "manual"
    ) -> dict:
        job_id = uuid.uuid4().hex[:12]
        now = datetime.now(timezone.utc)

        async with self._session_scope() as session:
            job = Job(
                id=job_id,
                type=job_type,
                trigger=trigger,
                competition_id=competition_id,
                status="queued",
                created_at=now,
            )
            session.add(job)

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
        }

    async def get_job(self, job_id: str) -> dict | None:
        async with self._session_scope() as session:
            stmt = (
                select(Job)
                .options(joinedload(Job.competition))
                .where(Job.id == job_id)
            )
            result = await session.execute(stmt)
            job = result.unique().scalar_one_or_none()
            if job is None:
                return None
            return self._job_to_dict(job)

    async def list_jobs(self) -> list[dict]:
        async with self._session_scope() as session:
            stmt = (
                select(Job)
                .options(joinedload(Job.competition))
                .order_by(Job.created_at.desc())
            )
            result = await session.execute(stmt)
            jobs = result.unique().scalars().all()
            return [self._job_to_dict(j) for j in jobs]

    async def cancel_job(self, job_id: str) -> bool:
        async with self._session_scope() as session:
            job = await session.get(Job, job_id)
            if job is None or job.status != "queued":
                return False
            job.status = "cancelled"
            job.completed_at = datetime.now(timezone.utc)

        # Remove from in-memory queue if present
        try:
            new_queue: asyncio.Queue[str] = asyncio.Queue()
            while not self._queue.empty():
                item = self._queue.get_nowait()
                if item != job_id:
                    new_queue.put_nowait(item)
                self._queue.task_done()
            self._queue = new_queue
        except asyncio.QueueEmpty:
            pass

        return True

    async def cleanup(self, days: int = 7) -> int:
        cutoff = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=days)
        deleted = 0

        async with self._session_scope() as session:
            # Mark stale running jobs as failed
            stmt = select(Job).where(Job.status == "running")
            result = await session.execute(stmt)
            for job in result.scalars().all():
                job.status = "failed"
                job.error = "Server restarted during execution"
                job.completed_at = datetime.now(timezone.utc)

            # Delete old completed/failed/cancelled jobs
            stmt = (
                delete(Job)
                .where(Job.created_at < cutoff)
                .where(Job.status.in_(["completed", "failed", "cancelled"]))
            )
            result = await session.execute(stmt)
            deleted = result.rowcount

        return deleted

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

            async with self._session_scope() as session:
                job = await session.get(Job, job_id)
                if not job or not self._handler or job.status != "queued":
                    self._queue.task_done()
                    continue

                # Mark as running
                job.status = "running"
                job.started_at = datetime.now(timezone.utc)

            # Build dict for handler
            job_dict = {
                "id": job_id,
                "type": job.type,
                "competition_id": job.competition_id,
                "status": "running",
            }

            try:
                result = await self._handler(job_dict)
                async with self._session_scope() as session:
                    job = await session.get(Job, job_id)
                    job.status = "completed"
                    job.result = result
                    job.completed_at = datetime.now(timezone.utc)
            except Exception as e:
                async with self._session_scope() as session:
                    job = await session.get(Job, job_id)
                    job.status = "failed"
                    job.error = str(e)
                    job.completed_at = datetime.now(timezone.utc)
            finally:
                self._queue.task_done()

    @staticmethod
    def _job_to_dict(job: Job) -> dict:
        return {
            "id": job.id,
            "type": job.type,
            "trigger": job.trigger,
            "competition_id": job.competition_id,
            "competition_name": job.competition.name if job.competition else None,
            "status": job.status,
            "result": job.result,
            "error": job.error,
            "created_at": job.created_at.isoformat() if job.created_at else None,
            "started_at": job.started_at.isoformat() if job.started_at else None,
            "completed_at": job.completed_at.isoformat() if job.completed_at else None,
        }


# Singleton instance
job_queue = JobQueue()
