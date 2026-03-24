from contextlib import asynccontextmanager
from typing import AsyncGenerator

from litestar import Litestar, get
from litestar.config.cors import CORSConfig
from litestar.static_files import StaticFilesConfig

from app.config import ALLOWED_ORIGINS, LOGOS_DIR, PDF_DIR
from app.database import init_db, async_session_factory
from app.auth.guards import auth_guard
from app.services.job_queue import job_queue
from app.services.import_service import run_import, run_enrich
from app.routes.auth import router as auth_router
from app.routes.competitions import router as competitions_router
from app.routes.jobs import router as jobs_router
from app.routes.skaters import router as skaters_router
from app.routes.scores import router as scores_router
from app.routes.dashboard import router as dashboard_router
from app.routes.club_config import router as config_router
from app.routes.users import router as users_router
from app.routes.domains import router as domains_router
from app.routes.admin import router as admin_router
from app.routes.stats import router as stats_router


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


cors_config = CORSConfig(
    allow_origins=ALLOWED_ORIGINS,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
    allow_credentials=True,
)


@get("/api/health")
async def health_check() -> dict:
    return {"status": "ok"}


app = Litestar(
    route_handlers=[
        health_check,
        auth_router,
        config_router,
        competitions_router,
        skaters_router,
        scores_router,
        dashboard_router,
        users_router,
        domains_router,
        jobs_router,
        admin_router,
        stats_router,
    ],
    cors_config=cors_config,
    lifespan=[lifespan],
    before_request=auth_guard,
    static_files_config=[
        StaticFilesConfig(
            directories=[str(LOGOS_DIR)],
            path="/api/logos",
        ),
        StaticFilesConfig(
            directories=[str(PDF_DIR)],
            path="/api/pdfs",
        ),
    ],
)
