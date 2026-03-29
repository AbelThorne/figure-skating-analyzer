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
