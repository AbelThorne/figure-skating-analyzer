from __future__ import annotations

from litestar import Router, get, post, delete, Request, Response
from litestar.di import Provide
from litestar.exceptions import NotFoundException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.guards import require_admin
from app.database import get_session


@get("/")
async def list_domains(request: Request, session: AsyncSession) -> list[dict]:
    require_admin(request)
    from app.models.allowed_domain import AllowedDomain

    result = await session.execute(
        select(AllowedDomain).order_by(AllowedDomain.created_at)
    )
    domains = result.scalars().all()
    return [
        {"id": d.id, "domain": d.domain, "created_at": d.created_at.isoformat()}
        for d in domains
    ]


@post("/")
async def add_domain(data: dict, request: Request, session: AsyncSession) -> Response:
    require_admin(request)
    from app.models.allowed_domain import AllowedDomain

    domain = data.get("domain", "").strip().lower()
    if not domain:
        return Response(content={"detail": "domain is required"}, status_code=400)

    obj = AllowedDomain(
        domain=domain,
        created_by=request.scope.get("state", {}).get("user_id"),
    )
    session.add(obj)
    await session.commit()
    await session.refresh(obj)

    return Response(
        content={"id": obj.id, "domain": obj.domain, "created_at": obj.created_at.isoformat()},
        status_code=201,
    )


@delete("/{domain_id:str}", status_code=200)
async def remove_domain(
    domain_id: str, request: Request, session: AsyncSession
) -> Response:
    require_admin(request)
    from app.models.allowed_domain import AllowedDomain

    result = await session.execute(
        select(AllowedDomain).where(AllowedDomain.id == domain_id)
    )
    obj = result.scalar_one_or_none()
    if not obj:
        raise NotFoundException("Domain not found")

    await session.delete(obj)
    await session.commit()
    return Response(content=None, status_code=204)


router = Router(
    path="/api/domains",
    route_handlers=[list_domains, add_domain, remove_domain],
    dependencies={"session": Provide(get_session)},
)
