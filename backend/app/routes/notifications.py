from __future__ import annotations

from litestar import Router, get, patch, post, Request
from litestar.di import Provide
from litestar.exceptions import NotFoundException, PermissionDeniedException
from sqlalchemy import select, func, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.models.notification import Notification


def _notif_to_dict(n: Notification) -> dict:
    return {
        "id": n.id,
        "type": n.type,
        "title": n.title,
        "message": n.message,
        "link": n.link,
        "is_read": n.is_read,
        "created_at": n.created_at.isoformat() if n.created_at else None,
    }


@get("/")
async def list_notifications(
    request: Request,
    session: AsyncSession,
    unread: bool | None = None,
) -> list[dict]:
    state = request.scope.get("state", {})
    user_id = state.get("user_id")
    if not user_id:
        raise PermissionDeniedException("Not authenticated")

    stmt = (
        select(Notification)
        .where(Notification.user_id == user_id)
        .order_by(Notification.created_at.desc())
        .limit(50)
    )
    if unread is True:
        stmt = stmt.where(Notification.is_read == False)  # noqa: E712

    result = await session.execute(stmt)
    return [_notif_to_dict(n) for n in result.scalars().all()]


@get("/count")
async def unread_count(request: Request, session: AsyncSession) -> dict:
    state = request.scope.get("state", {})
    user_id = state.get("user_id")
    if not user_id:
        raise PermissionDeniedException("Not authenticated")

    stmt = (
        select(func.count())
        .select_from(Notification)
        .where(Notification.user_id == user_id, Notification.is_read == False)  # noqa: E712
    )
    result = await session.execute(stmt)
    count = result.scalar() or 0
    return {"count": count}


@patch("/{notification_id:int}/read")
async def mark_read(notification_id: int, request: Request, session: AsyncSession) -> dict:
    state = request.scope.get("state", {})
    user_id = state.get("user_id")
    if not user_id:
        raise PermissionDeniedException("Not authenticated")

    notif = await session.get(Notification, notification_id)
    if not notif:
        raise NotFoundException("Notification not found")
    if notif.user_id != user_id:
        raise PermissionDeniedException("Not your notification")

    notif.is_read = True
    await session.commit()
    return _notif_to_dict(notif)


@post("/read-all", status_code=200)
async def mark_all_read(request: Request, session: AsyncSession) -> dict:
    state = request.scope.get("state", {})
    user_id = state.get("user_id")
    if not user_id:
        raise PermissionDeniedException("Not authenticated")

    stmt = (
        update(Notification)
        .where(Notification.user_id == user_id, Notification.is_read == False)  # noqa: E712
        .values(is_read=True)
    )
    result = await session.execute(stmt)
    await session.commit()
    return {"marked": result.rowcount}


router = Router(
    path="/api/me/notifications",
    route_handlers=[list_notifications, unread_count, mark_read, mark_all_read],
    dependencies={"session": Provide(get_session)},
)
