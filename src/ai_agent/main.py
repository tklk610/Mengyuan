"""NovelCraft FastAPI Application

PoC 版本的 FastAPI 应用
"""
from __future__ import annotations

import uuid
from contextlib import asynccontextmanager

import structlog
from fastapi import Depends, FastAPI, HTTPException, Security
from fastapi.security import HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from ai_agent.agents.novel_agent import novel_graph
from ai_agent.api.v1.router import router as v1_router
from ai_agent.auth.middleware import _bearer, verify_token
from ai_agent.config.settings import settings
from ai_agent.exception.handler import register_exception_handlers
from ai_agent.schemas.chat import (
    ChatRequest,
    ResumeRequest,
    SessionCreateResponse,
)

structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.add_log_level,
        structlog.processors.JSONRenderer(),
    ]
)
logger = structlog.get_logger(__name__)


# === Lifespan ===
@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    logger.info("app.startup", app_name=settings.app_name, env=settings.app_env)
    yield
    logger.info("app.shutdown")


# === App ===
app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 异常处理器
register_exception_handlers(app)

# API v1 router (auth: register / login)
app.include_router(v1_router)


# === In-Memory Session Store ===
# Key = f"{user_id}:{thread_id}" — 用户隔离
_sessions: dict[str, dict] = {}  # {(user_id, thread_id) -> session}


def _session_key(user_id: str, thread_id: str) -> str:
    return f"{user_id}:{thread_id}"


# === Authenticated Endpoints ===

@app.post("/api/session", response_model=SessionCreateResponse)
async def create_session(
    credentials: HTTPAuthorizationCredentials | None = Security(_bearer),
) -> SessionCreateResponse:
    """创建新的创作会话（需认证）"""
    if credentials is None or credentials.credentials is None:
        raise HTTPException(status_code=401, detail="Missing token")
    payload = verify_token(credentials.credentials)
    if payload is None:
        raise HTTPException(status_code=401, detail="Invalid token")
    user_id = payload.sub
    thread_id = str(uuid.uuid4())
    _sessions[_session_key(user_id, thread_id)] = {
        "user_id": user_id,
        "created": True,
    }
    logger.info("session.created", user_id=user_id, thread_id=thread_id)
    return SessionCreateResponse(user_id=user_id, thread_id=thread_id)


# === Endpoints ===

@app.get("/health")
async def health_check():
    """健康检查（无需认证）"""
    return {"status": "healthy", "app": settings.app_name}


@app.post("/api/chat")
async def chat(
    request: ChatRequest,
    credentials: HTTPAuthorizationCredentials | None = Security(_bearer),
) -> StreamingResponse:
    """SSE 流式聊天端点（需认证）

    认证：Bearer token 在 Authorization header，user_id 在请求体。
    Session 按 user_id 隔离（key = f"{user_id}:{thread_id}"）。
    """
    if credentials is not None:
        payload = verify_token(credentials.credentials)
        if payload is not None and payload.sub != request.user_id:
            raise HTTPException(status_code=403, detail="user_id does not match token")
    session_key = _session_key(request.user_id, request.thread_id)

    async def event_generator():
        """SSE 事件生成器"""
        config = {"configurable": {"thread_id": session_key, "user_id": request.user_id}}

        try:
            # 检查是否有中断需要恢复
            state = novel_graph.get_state(config)

            if state and state.next:
                # 有待处理的中断，跳过新输入
                yield {
                    "type": "status",
                    "data": {"agent": "system"},
                    "message": "等待上一个任务完成",
                }
                return

            # 构建初始状态
            initial_state = {
                "messages": [{"role": "user", "content": request.message}],
                "user_request": request.message,
                "genre": request.genre,
                "outline": None,
                "characters": None,
                "current_chapter": 1,
                "draft": None,
                "phase": "idle",
                "interrupt_type": None,
                "interrupt_options": None,
                "user_choice": None,
                "error": None,
            }

            # 流式执行 graph
            async for event in novel_graph.astream_events(
                initial_state, config=config, stream_mode="values"
            ):
                # 提取状态变化
                if isinstance(event, dict):
                    # 状态更新事件
                    if "outline" in event and event.get("outline"):
                        yield {
                            "type": "outline",
                            "data": event["outline"],
                            "message": "大纲已生成",
                        }

                    if "draft" in event and event.get("draft"):
                        # 流式输出草稿
                        draft = event["draft"]
                        for chunk in _chunk_text(draft, chunk_size=50):
                            yield {"type": "draft_delta", "data": chunk}

                    # 消息事件
                    messages = event.get("messages", [])
                    if messages:
                        latest = messages[-1]
                        if latest.get("role") == "assistant":
                            content = latest.get("content", "")
                            if content.startswith("📋"):
                                yield {"type": "status", "data": {"agent": "Narrator"}, "message": content}
                            elif content.startswith("✅"):
                                yield {"type": "complete", "data": {}, "message": content}

        except Exception as e:
            logger.error("chat.error", error=str(e), thread_id=request.thread_id)
            yield {"type": "error", "data": {}, "message": str(e)}

    return StreamingResponse(
        _sse_wrapper(event_generator()),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.post("/api/resume")
async def resume(
    request: ResumeRequest,
    credentials: HTTPAuthorizationCredentials | None = Security(_bearer),
) -> StreamingResponse:
    """恢复被中断的任务（需认证）

    认证：Bearer token 在 Authorization header，user_id 在请求体。
    Session 按 user_id 隔离。
    """
    if credentials is not None:
        payload = verify_token(credentials.credentials)
        if payload is not None and payload.sub != request.user_id:
            raise HTTPException(status_code=403, detail="user_id does not match token")

    session_key = _session_key(request.user_id, request.thread_id)
    config = {"configurable": {"thread_id": session_key, "user_id": request.user_id}}

    # 检查当前状态
    state = novel_graph.get_state(config)

    if not state or not state.next:
        raise HTTPException(status_code=400, detail="No pending interrupt to resume")

    try:
        # 通过 Command(resume=...) 恢复执行
        from langgraph.types import Command

        resume_value = {
            "choice": request.choice,
            "instruction": request.instruction,
        }

        async def event_generator():
            try:
                # stream_mode="updates" yields after each node completes.
                # Accept path: scribe_node replays, generates draft, interrupt resolves
                # with "accept", returns Command(goto=END). No more updates follow.
                # Rewrite/restart path: graph replays and re-enters scribe_node
                # for fresh LLM generation.
                async for update in novel_graph.astream(
                    Command(resume=resume_value),
                    config=config,
                    stream_mode="updates",
                ):
                    if isinstance(update, dict):
                        if "draft" in update and update.get("draft"):
                            draft = update["draft"]
                            for chunk in _chunk_text(draft, chunk_size=50):
                                yield {"type": "draft_delta", "data": chunk}
                        if "messages" in update:
                            msgs = update["messages"]
                            if msgs and isinstance(msgs, list):
                                latest = msgs[-1]
                                if isinstance(latest, dict) and latest.get("role") == "assistant":
                                    content = latest.get("content", "")
                                    if "✅" in content or "完成" in content:
                                        yield {"type": "complete", "data": {}, "message": content}

                # 显式检查最终状态——accept 路径的 graph 完成后不会额外
                # yield（Command(goto=END) 立即结束），所以在此补充 complete 事件
                final_state = novel_graph.get_state(config)
                if final_state is not None and final_state.next is None:
                    saved_phase = final_state.values.get("phase")
                    if saved_phase == "complete":
                        yield {"type": "complete", "data": {}, "message": "✅ 第1章已完成"}

            except Exception as e:
                logger.error("resume.error", error=str(e))
                yield {"type": "error", "data": {}, "message": str(e)}

        return StreamingResponse(
            _sse_wrapper(event_generator()),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    except Exception as e:
        logger.error("resume.error", error=str(e))
        raise HTTPException(status_code=500, detail=str(e)) from e


# === Helper Functions ===

async def _sse_wrapper(generator):
    """将字典事件转换为 SSE 格式"""
    async for event in generator:
        yield f"data: {event}\n\n"


def _chunk_text(text: str, chunk_size: int = 50) -> list[str]:
    """将文本分块"""
    words = text.split()
    chunks = []
    current_chunk = []

    for word in words:
        current_chunk.append(word)
        if len(current_chunk) >= chunk_size:
            chunks.append(" ".join(current_chunk))
            current_chunk = []

    if current_chunk:
        chunks.append(" ".join(current_chunk))

    return chunks
