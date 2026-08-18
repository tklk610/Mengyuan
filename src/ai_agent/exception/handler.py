"""NovelCraft Exception Handler

统一异常处理，返回三段式结构 {code, message, data}
"""
from __future__ import annotations

import structlog
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from ai_agent.exception.exceptions import (
    AgentBudgetExhaustedError,
    BusinessError,
    NovelCraftError,
)

logger = structlog.get_logger(__name__)


def register_exception_handlers(app: FastAPI) -> None:
    """注册全局异常处理器"""

    @app.exception_handler(NovelCraftError)
    async def novel_craft_exception_handler(
        request: Request, exc: NovelCraftError
    ) -> JSONResponse:
        """处理所有 NovelCraft 自定义异常"""
        logger.warning(
            "novelcraft.exception",
            code=exc.code,
            message=exc.message,
            path=request.url.path,
        )
        return JSONResponse(
            status_code=400 if isinstance(exc, BusinessError) else 500,
            content={
                "code": exc.code,
                "message": exc.message,
                "data": None,
            },
        )

    @app.exception_handler(AgentBudgetExhaustedError)
    async def budget_exhausted_handler(
        request: Request, exc: AgentBudgetExhaustedError
    ) -> JSONResponse:
        """配额耗尽返回 429"""
        return JSONResponse(
            status_code=429,
            content={
                "code": exc.code,
                "message": exc.message,
                "data": {"retry_after": "tomorrow"},
            },
            headers={"Retry-After": "86400"},
        )

    @app.exception_handler(Exception)
    async def generic_exception_handler(
        request: Request, exc: Exception
    ) -> JSONResponse:
        """兜底异常处理，禁止泄露原始异常"""
        logger.error(
            "unexpected.exception",
            exc_type=type(exc).__name__,
            path=request.url.path,
        )
        return JSONResponse(
            status_code=500,
            content={
                "code": "INTERNAL_ERROR",
                "message": "An unexpected error occurred",
                "data": None,
            },
        )
