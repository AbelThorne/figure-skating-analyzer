from datetime import datetime, timedelta, timezone

import jwt

from app.config import SECRET_KEY

_ALGORITHM = "HS256"
_ACCESS_EXPIRES = 900  # 15 minutes
_REFRESH_EXPIRES = 604800  # 7 days


def create_access_token(
    user_id: str, role: str, expires_seconds: int = _ACCESS_EXPIRES
) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user_id,
        "role": role,
        "type": "access",
        "iat": now,
        "exp": now + timedelta(seconds=expires_seconds),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=_ALGORITHM)


def create_refresh_token(
    user_id: str, token_version: int, expires_seconds: int = _REFRESH_EXPIRES
) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user_id,
        "type": "refresh",
        "ver": token_version,
        "iat": now,
        "exp": now + timedelta(seconds=expires_seconds),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=_ALGORITHM)


def decode_token(token: str) -> dict:
    return jwt.decode(token, SECRET_KEY, algorithms=[_ALGORITHM])
