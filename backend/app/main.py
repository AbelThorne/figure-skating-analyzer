from contextlib import asynccontextmanager
from typing import AsyncGenerator

from litestar import Litestar, get
from litestar.config.cors import CORSConfig
from litestar.static_files import StaticFilesConfig

from app.config import ALLOWED_ORIGINS, LOGOS_DIR
from app.database import init_db
from app.auth.guards import auth_guard
from app.routes.auth import router as auth_router
from app.routes.competitions import router as competitions_router
from app.routes.skaters import router as skaters_router
from app.routes.scores import router as scores_router
from app.routes.dashboard import router as dashboard_router
from app.routes.club_config import router as config_router
from app.routes.users import router as users_router
from app.routes.domains import router as domains_router


@asynccontextmanager
async def lifespan(_: Litestar) -> AsyncGenerator[None, None]:
    await init_db()
    yield


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
    ],
    cors_config=cors_config,
    lifespan=[lifespan],
    before_request=auth_guard,
    static_files_config=[
        StaticFilesConfig(
            directories=[str(LOGOS_DIR)],
            path="/api/logos",
        ),
    ],
)
