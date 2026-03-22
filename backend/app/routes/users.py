from __future__ import annotations

from litestar import Router, get, post, patch, delete, Request, Response
from litestar.di import Provide
from litestar.exceptions import NotFoundException
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.guards import require_admin
from app.auth.passwords import hash_password
from app.database import get_session


@get("/")
async def list_users(request: Request, session: AsyncSession) -> list[dict]:
    require_admin(request)
    from app.models.user import User

    result = await session.execute(select(User).order_by(User.created_at))
    users = result.scalars().all()
    return [
        {
            "id": u.id,
            "email": u.email,
            "display_name": u.display_name,
            "role": u.role,
            "is_active": u.is_active,
            "google_oauth_enabled": u.google_oauth_enabled,
        }
        for u in users
    ]


@post("/")
async def create_user(data: dict, request: Request, session: AsyncSession) -> Response:
    require_admin(request)
    from app.models.user import User

    email = data.get("email", "").strip().lower()
    display_name = data.get("display_name", "").strip()
    role = data.get("role", "reader")
    password = data.get("password")

    if not email or not display_name:
        return Response(content={"detail": "email and display_name required"}, status_code=400)

    user = User(
        email=email,
        display_name=display_name,
        role=role,
        password_hash=hash_password(password) if password else None,
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)

    return Response(
        content={
            "id": user.id,
            "email": user.email,
            "display_name": user.display_name,
            "role": user.role,
            "is_active": user.is_active,
            "google_oauth_enabled": user.google_oauth_enabled,
        },
        status_code=201,
    )


@patch("/{user_id:str}")
async def update_user(
    user_id: str, data: dict, request: Request, session: AsyncSession
) -> dict:
    require_admin(request)
    from app.models.user import User

    result = await session.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise NotFoundException("User not found")

    if "role" in data:
        user.role = data["role"]
    if "display_name" in data:
        user.display_name = data["display_name"]
    if "is_active" in data:
        user.is_active = data["is_active"]
        if not data["is_active"]:
            user.token_version += 1

    await session.commit()
    await session.refresh(user)

    return {
        "id": user.id,
        "email": user.email,
        "display_name": user.display_name,
        "role": user.role,
        "is_active": user.is_active,
        "google_oauth_enabled": user.google_oauth_enabled,
    }


@delete("/{user_id:str}", status_code=200)
async def delete_user(
    user_id: str, request: Request, session: AsyncSession
) -> Response:
    require_admin(request)
    from app.models.user import User

    result = await session.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise NotFoundException("User not found")

    if user.role == "admin":
        count_result = await session.execute(
            select(func.count()).select_from(User).where(
                User.role == "admin", User.id != user_id
            )
        )
        if count_result.scalar() == 0:
            return Response(
                content={"detail": "Cannot delete the last admin user"},
                status_code=400,
            )

    await session.delete(user)
    await session.commit()
    return Response(content=None, status_code=204)


router = Router(
    path="/api/users",
    route_handlers=[list_users, create_user, update_user, delete_user],
    dependencies={"session": Provide(get_session)},
)
