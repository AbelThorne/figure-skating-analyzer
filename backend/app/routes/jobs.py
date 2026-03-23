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
