from __future__ import annotations

from litestar import Router, post, Request
from litestar.di import Provide

from app.auth.guards import require_admin
from app.database import get_session, engine, Base, _bootstrap


@post("/reset-database")
async def reset_database(request: Request) -> dict:
    """Drop all data tables and re-create them. Admin only."""
    require_admin(request)

    import app.models  # noqa: F401 — ensure all models registered

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    await _bootstrap()

    return {"status": "ok", "message": "Database reset successfully"}


router = Router(
    path="/api/admin",
    route_handlers=[reset_database],
    dependencies={"session": Provide(get_session)},
)
