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
