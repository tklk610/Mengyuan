"""API v1 router — aggregates all v1 endpoint modules."""
from __future__ import annotations

from fastapi import APIRouter

from ai_agent.api.v1 import auth

router = APIRouter(prefix="/api/v1")

router.add_api_route("/auth/register", auth.register, methods=["POST"], response_model=auth.RegisterResponse)
router.add_api_route("/auth/login", auth.login, methods=["POST"], response_model=auth.LoginResponse)
