from __future__ import annotations

from datetime import datetime, timezone

from litestar import Router, Response, get, post, Request
from litestar.di import Provide
from litestar.exceptions import NotFoundException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.guards import require_admin
from app.auth.passwords import hash_password
from app.database import get_session, engine, Base, _bootstrap
from app.models.account_request import AccountRequest
from app.models.app_settings import AppSettings
from app.models.skater import Skater
from app.models.user import User
from app.models.user_skater import UserSkater
from app.services.account_request import generate_temp_password
from app.services.email_service import get_smtp_config, send_email


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


@post("/recalculate-clubs")
async def recalculate_clubs(request: Request, session: AsyncSession) -> dict:
    """Update Skater.club to match the club from their most recent score."""
    require_admin(request)

    from sqlalchemy import select, func, update
    from app.models.skater import Skater
    from app.models.score import Score
    from app.models.competition import Competition

    # Single query: for each skater, get the club from the score with the latest competition date
    # Use a subquery with DISTINCT ON equivalent for SQLite (window function)
    latest_club_subq = (
        select(
            Score.skater_id,
            Score.club,
            func.row_number().over(
                partition_by=Score.skater_id,
                order_by=Competition.date.desc().nullslast(),
            ).label("rn"),
        )
        .join(Competition, Score.competition_id == Competition.id)
        .where(Score.club.isnot(None), Score.club != "")
        .subquery()
    )

    latest_clubs = (
        await session.execute(
            select(latest_club_subq.c.skater_id, latest_club_subq.c.club)
            .where(latest_club_subq.c.rn == 1)
        )
    ).all()

    updated = 0
    for skater_id, club in latest_clubs:
        result = await session.execute(
            update(Skater)
            .where(Skater.id == skater_id, Skater.club != club)
            .values(club=club)
        )
        updated += result.rowcount

    await session.commit()
    return {"status": "ok", "skaters_updated": updated}


@get("/account-requests")
async def list_account_requests(request: Request, session: AsyncSession) -> list[dict]:
    require_admin(request)
    rows = (
        (await session.execute(select(AccountRequest).order_by(AccountRequest.created_at.desc())))
        .scalars()
        .all()
    )
    return [
        {
            "id": r.id,
            "email": r.email,
            "display_name": r.display_name,
            "licence_numbers": r.licence_numbers,
            "status": r.status,
            "reject_reason": r.reject_reason,
            "created_at": r.created_at.isoformat() if r.created_at else None,
            "resolved_at": r.resolved_at.isoformat() if r.resolved_at else None,
            "user_id": r.user_id,
        }
        for r in rows
    ]


@post("/account-requests/{request_id:int}/approve")
async def approve_account_request(
    request_id: int, data: dict, request: Request, session: AsyncSession
) -> Response:
    """Résout une demande `pending_admin` en liant les patineurs choisis par l'admin."""
    require_admin(request)

    req = (
        await session.execute(select(AccountRequest).where(AccountRequest.id == request_id))
    ).scalar_one_or_none()
    if req is None:
        raise NotFoundException("Demande introuvable")
    if req.status != "pending_admin":
        return Response(
            content={"detail": "Cette demande a déjà été traitée."}, status_code=400
        )

    skater_ids = data.get("skater_ids") or []
    if not isinstance(skater_ids, list) or not skater_ids:
        return Response(
            content={"detail": "Au moins un patineur doit être sélectionné."},
            status_code=400,
        )

    existing = (
        await session.execute(select(User).where(User.email == req.email))
    ).scalar_one_or_none()
    if existing is not None:
        return Response(
            content={"detail": "Un compte existe déjà pour cette adresse."}, status_code=400
        )

    temp_password = generate_temp_password()
    user = User(
        email=req.email,
        display_name=req.display_name,
        role="skater",
        password_hash=hash_password(temp_password),
        must_change_password=True,
    )
    session.add(user)
    await session.flush()

    linked_names: list[str] = []
    for skater_id in skater_ids:
        skater = await session.get(Skater, skater_id)
        if skater is None:
            continue
        if skater.licence_number is None and req.licence_numbers:
            skater.licence_number = req.licence_numbers[0]
        session.add(UserSkater(user_id=user.id, skater_id=skater.id))
        linked_names.append(skater.display_name)

    req.status = "created"
    req.user_id = user.id
    req.resolved_at = datetime.now(timezone.utc)
    await session.commit()

    settings = (await session.execute(select(AppSettings).limit(1))).scalar_one_or_none()
    smtp = await get_smtp_config(session)
    if smtp:
        club_name = settings.club_name if settings else "SkateLab"
        await send_email(
            to=req.email,
            subject=f"Votre compte {club_name} est prêt",
            template_name="account_created.html",
            context={
                "club_name": club_name,
                "display_name": user.display_name,
                "email": req.email,
                "temp_password": temp_password,
                "skaters": linked_names,
                "failures": [],
            },
            smtp_config=smtp,
        )

    return Response(content={"detail": "Compte créé", "user_id": user.id}, status_code=200)


router = Router(
    path="/api/admin",
    route_handlers=[
        reset_database,
        recalculate_clubs,
        list_account_requests,
        approve_account_request,
    ],
    dependencies={"session": Provide(get_session)},
)
