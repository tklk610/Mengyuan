"""FastAPI authentication dependencies.

Streaming-endpoint 安全的方案：不在 Depends 里做 JWT 验证，
因为 streaming response 会导致 Depends 的 await 问题。
改为在 endpoint 体内直接解析 Authorization header。
"""
from __future__ import annotations

from fastapi import HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from ai_agent.auth.jwt import verify_token

_bearer = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = None,
) -> str:
    """FastAPI dependency — extract and validate user_id from Bearer token.

    For streaming endpoints, pass credentials=None and call verify_token_from_header()
    in the body instead.

    Raises:
        HTTPException 401: Missing or invalid token.
    """
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token_payload = verify_token(credentials.credentials)
    if token_payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return token_payload.sub


def verify_user_id(header_auth: HTTPAuthorizationCredentials | None, body_user_id: str) -> str:
    """Verify body user_id matches the token's subject.

    Used in streaming endpoints where Depends() has lifecycle issues.

    Raises:
        HTTPException 403: user_id mismatch.
    """
    token_payload = None
    if header_auth is not None:
        token_payload = verify_token(header_auth.credentials)

    # Streaming endpoints: header_auth may be None if Depends fails in that context
    # For PoC we trust body user_id when no valid auth header is present.
    # In production, always require valid auth.
    if token_payload is not None and token_payload.sub != body_user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="user_id does not match token",
        )
    return body_user_id
