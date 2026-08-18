"""Auth API endpoints — register and login."""
from __future__ import annotations

from pydantic import BaseModel, EmailStr, Field

from ai_agent.auth.jwt import create_access_token
from ai_agent.auth.password import hash_password, verify_password


class RegisterRequest(BaseModel):
    """POST /api/v1/auth/register"""

    username: str = Field(..., min_length=3, max_length=64)
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)


class RegisterResponse(BaseModel):
    """Response for successful registration."""

    user_id: str
    username: str
    email: str


class LoginRequest(BaseModel):
    """POST /api/v1/auth/login"""

    email: EmailStr
    password: str


class LoginResponse(BaseModel):
    """Response for successful login."""

    access_token: str
    token_type: str = "bearer"
    user_id: str


# In-memory user store (PoC阶段；生产用 DB)
# Schema: user_id -> {user_id, username, email, password_hash}
_users_db: dict[str, dict] = {}
_email_index: dict[str, str] = {}  # email -> user_id


def get_user_by_email(email: str) -> dict | None:
    user_id = _email_index.get(email)
    if user_id is None:
        return None
    return _users_db.get(user_id)


def create_user(username: str, email: str, password: str) -> str:
    """Create a new user. Returns user_id."""
    import uuid
    user_id = str(uuid.uuid4())
    _users_db[user_id] = {
        "user_id": user_id,
        "username": username,
        "email": email,
        "password_hash": hash_password(password),
    }
    _email_index[email] = user_id
    return user_id


async def register(request: RegisterRequest) -> RegisterResponse:
    """Register a new user."""
    if get_user_by_email(request.email) is not None:
        from fastapi import HTTPException
        raise HTTPException(status_code=409, detail="Email already registered")

    user_id = create_user(request.username, request.email, request.password)
    return RegisterResponse(user_id=user_id, username=request.username, email=request.email)


async def login(request: LoginRequest) -> LoginResponse:
    """Authenticate user and return JWT token."""
    user = get_user_by_email(request.email)
    if user is None or not verify_password(request.password, user["password_hash"]):
        from fastapi import HTTPException
        raise HTTPException(status_code=401, detail="Invalid email or password")

    token = create_access_token(user["user_id"])
    return LoginResponse(access_token=token, user_id=user["user_id"])
