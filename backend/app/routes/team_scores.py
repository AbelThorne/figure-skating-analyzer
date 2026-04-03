from __future__ import annotations

from litestar import Router, get, put, Request
from litestar.di import Provide
from litestar.exceptions import NotFoundException, ClientException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.guards import require_admin
from app.database import get_session
from app.models.app_settings import AppSettings
from app.models.competition import Competition
from app.services.team_scoring import get_team_scores, DEFAULT_MEDIANS


@get("/{competition_id:int}/team-scores")
async def get_competition_team_scores(
    competition_id: int, session: AsyncSession
) -> dict:
    result = await get_team_scores(session, competition_id)
    if result is None:
        raise NotFoundException("Compétition introuvable ou pas de type France Clubs")
    return result


@get("/{competition_id:int}/team-medians")
async def get_competition_medians(
    competition_id: int, session: AsyncSession
) -> dict:
    comp = await session.get(Competition, competition_id)
    if not comp:
        raise NotFoundException("Compétition introuvable")

    if comp.team_medians:
        return {"medians": comp.team_medians, "source": "competition"}

    result = await session.execute(select(AppSettings).limit(1))
    settings = result.scalar_one_or_none()
    medians = (settings.default_team_medians if settings else None) or DEFAULT_MEDIANS
    return {"medians": medians, "source": "default"}


@put("/{competition_id:int}/team-medians")
async def update_competition_medians(
    data: dict, competition_id: int, request: Request, session: AsyncSession
) -> dict:
    require_admin(request)
    comp = await session.get(Competition, competition_id)
    if not comp:
        raise NotFoundException("Compétition introuvable")

    medians = data.get("medians")
    if not isinstance(medians, dict):
        raise ClientException(detail="Format de médianes invalide", status_code=400)

    comp.team_medians = medians
    await session.commit()
    return {"medians": comp.team_medians, "source": "competition"}


@get("/default-team-medians")
async def get_default_medians(request: Request, session: AsyncSession) -> dict:
    require_admin(request)
    result = await session.execute(select(AppSettings).limit(1))
    settings = result.scalar_one_or_none()
    medians = (settings.default_team_medians if settings else None) or DEFAULT_MEDIANS
    return {"medians": medians}


@put("/default-team-medians")
async def update_default_medians(
    data: dict, request: Request, session: AsyncSession
) -> dict:
    require_admin(request)

    result = await session.execute(select(AppSettings).limit(1))
    settings = result.scalar_one_or_none()
    if not settings:
        raise ClientException(detail="Configuration non initialisée", status_code=400)

    medians = data.get("medians")
    if not isinstance(medians, dict):
        raise ClientException(detail="Format de médianes invalide", status_code=400)

    settings.default_team_medians = medians
    await session.commit()
    return {"medians": settings.default_team_medians}


router = Router(
    path="/api/competitions",
    route_handlers=[
        get_competition_team_scores,
        get_competition_medians,
        update_competition_medians,
        get_default_medians,
        update_default_medians,
    ],
    dependencies={"session": Provide(get_session)},
)
