from __future__ import annotations

from litestar import Request
from litestar.exceptions import NotAuthorizedException, PermissionDeniedException
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.tokens import decode_token

# Paths that skip JWT auth entirely
_PUBLIC_PREFIXES = ("/api/auth/", "/api/health")
# Exact paths (with or without trailing slash) that are public
_PUBLIC_EXACT = ("/api/config", "/api/config/")


async def auth_guard(request: Request) -> None:
    """Litestar before_request hook: validate JWT on non-public routes."""
    path: str = request.scope["path"]
    if any(path.startswith(p) for p in _PUBLIC_PREFIXES) or path in _PUBLIC_EXACT:
        return
    auth_header = request.headers.get("authorization", "")
    if not auth_header.startswith("Bearer "):
        raise NotAuthorizedException("Missing or invalid Authorization header")
    token = auth_header[7:]
    try:
        payload = decode_token(token)
    except Exception:
        raise NotAuthorizedException("Invalid or expired token")
    if payload.get("type") != "access":
        raise NotAuthorizedException("Invalid token type")
    # Store user info in request state for downstream handlers
    request.scope["state"] = {
        **request.scope.get("state", {}),
        "user_id": payload["sub"],
        "user_role": payload["role"],
    }


def require_admin(request: Request) -> None:
    """Reusable helper to check admin role. Raises 403 if not admin."""
    if request.scope.get("state", {}).get("user_role") != "admin":
        raise PermissionDeniedException("Admin role required")


def reject_skater_role(request: Request) -> None:
    """Block access for skater role. Raises 403."""
    if request.scope.get("state", {}).get("user_role") == "skater":
        raise PermissionDeniedException("Skater role cannot access this resource")


def require_coach_or_admin(request: Request) -> None:
    """Allow only coach and admin roles. Raises 403 otherwise."""
    role = request.scope.get("state", {}).get("user_role")
    if role not in ("coach", "admin"):
        raise PermissionDeniedException("Coach or admin role required")


async def require_skater_access(request: Request, skater_id: int, session: AsyncSession) -> None:
    """For skater role, verify the user has access to this specific skater."""
    state = request.scope.get("state", {})
    if state.get("user_role") != "skater":
        return  # admin and reader pass through

    from app.models.user_skater import UserSkater
    from sqlalchemy import select

    result = await session.execute(
        select(UserSkater).where(
            UserSkater.user_id == state["user_id"],
            UserSkater.skater_id == skater_id,
        )
    )
    if not result.scalar_one_or_none():
        raise PermissionDeniedException("You do not have access to this skater")
