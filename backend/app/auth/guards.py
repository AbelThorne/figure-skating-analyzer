from __future__ import annotations

from litestar import Request
from litestar.exceptions import NotAuthorizedException, PermissionDeniedException

from app.auth.tokens import decode_token

# Paths that skip JWT auth entirely
_PUBLIC_PREFIXES = ("/api/auth/", "/api/config", "/api/health")


async def auth_guard(request: Request) -> None:
    """Litestar before_request hook: validate JWT on non-public routes."""
    path: str = request.scope["path"]
    if any(path.startswith(p) for p in _PUBLIC_PREFIXES):
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
