from __future__ import annotations

from litestar import Router, get

from app.config import CLUB_NAME, CLUB_SHORT


@get("/")
async def get_club_config() -> dict:
    return {
        "club_name": CLUB_NAME,
        "club_short": CLUB_SHORT,
        "logo_url": "/club-logo.png",
    }


router = Router(
    path="/api/config",
    route_handlers=[get_club_config],
)
