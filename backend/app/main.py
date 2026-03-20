from contextlib import asynccontextmanager
from typing import AsyncGenerator

from litestar import Litestar
from litestar.config.cors import CORSConfig

from app.database import init_db
from app.routes.competitions import router as competitions_router
from app.routes.skaters import router as skaters_router
from app.routes.scores import router as scores_router
from app.routes.dashboard import router as dashboard_router


@asynccontextmanager
async def lifespan(_: Litestar) -> AsyncGenerator[None, None]:
    await init_db()
    yield


cors_config = CORSConfig(
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
)

app = Litestar(
    route_handlers=[competitions_router, skaters_router, scores_router, dashboard_router],
    cors_config=cors_config,
    lifespan=[lifespan],
)
