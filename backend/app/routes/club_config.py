from __future__ import annotations

from litestar import Router, get, patch, post, Request, Response
from litestar.datastructures import UploadFile
from litestar.di import Provide
from litestar.enums import RequestEncodingType
from litestar.exceptions import ClientException
from litestar.params import Body
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.guards import require_admin
from app.config import LOGOS_DIR, GOOGLE_CLIENT_ID
from app.database import get_session
from app.models.app_settings import AppSettings


@get("/")
async def get_config(session: AsyncSession) -> dict:
    result = await session.execute(select(AppSettings).limit(1))
    settings = result.scalar_one_or_none()

    if not settings:
        return {
            "setup_required": True,
            "google_client_id": GOOGLE_CLIENT_ID or None,
        }

    return {
        "setup_required": False,
        "club_name": settings.club_name,
        "club_short": settings.club_short,
        "logo_url": f"/api/logos/{settings.logo_path}" if settings.logo_path else "",
        "current_season": settings.current_season,
        "google_client_id": GOOGLE_CLIENT_ID or None,
    }


@patch("/")
async def update_config(
    data: dict, request: Request, session: AsyncSession
) -> Response:
    require_admin(request)

    result = await session.execute(select(AppSettings).limit(1))
    settings = result.scalar_one_or_none()
    if not settings:
        raise ClientException(detail="Run setup first", status_code=400)

    if "club_name" in data:
        settings.club_name = data["club_name"]
    if "club_short" in data:
        settings.club_short = data["club_short"]
    if "current_season" in data:
        settings.current_season = data["current_season"]

    await session.commit()
    await session.refresh(settings)

    return Response(
        content={
            "club_name": settings.club_name,
            "club_short": settings.club_short,
            "logo_url": f"/api/logos/{settings.logo_path}" if settings.logo_path else "",
            "current_season": settings.current_season,
        },
        status_code=200,
    )


@post("/logo")
async def upload_logo(
    request: Request,
    session: AsyncSession,
    data: UploadFile = Body(media_type=RequestEncodingType.MULTI_PART),
) -> dict:
    require_admin(request)

    result = await session.execute(select(AppSettings).limit(1))
    settings = result.scalar_one_or_none()
    if not settings:
        raise ClientException(detail="Run setup first", status_code=400)

    content = await data.read()
    filename = f"logo{_ext(data.filename or 'logo.png')}"
    path = LOGOS_DIR / filename
    path.write_bytes(content)

    settings.logo_path = filename
    await session.commit()

    return {"logo_url": f"/api/logos/{filename}"}


def _ext(name: str) -> str:
    return "." + name.rsplit(".", 1)[-1] if "." in name else ".png"


router = Router(
    path="/api/config",
    route_handlers=[get_config, update_config, upload_logo],
    dependencies={"session": Provide(get_session)},
)
