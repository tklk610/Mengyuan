"""JWT token creation and verification."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from jose import JWTError, jwt
from pydantic import BaseModel

from ai_agent.config.settings import settings


class TokenPayload(BaseModel):
    """Decoded JWT payload."""

    sub: str  # user_id
    exp: datetime


ALGORITHM = "HS256"


def create_access_token(user_id: str, expires_delta: timedelta | None = None) -> str:
    """Create a signed JWT access token.

    Args:
        user_id: The subject claim (user identifier).
        expires_delta: Optional TTL. Defaults to 24 hours.

    Returns:
        Encoded JWT string.
    """
    if expires_delta is None:
        expires_delta = timedelta(hours=24)

    expire = datetime.now(UTC) + expires_delta
    payload: dict[str, Any] = {
        "sub": user_id,
        "exp": expire,
        "iat": datetime.now(UTC),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=ALGORITHM)


def verify_token(token: str) -> TokenPayload | None:
    """Verify and decode a JWT token.

    Args:
        token: Encoded JWT string.

    Returns:
        TokenPayload if valid, None if expired or invalid.
    """
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[ALGORITHM])
        return TokenPayload(**payload)
    except JWTError:
        return None
