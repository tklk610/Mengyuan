"""NovelCraft API Schemas

Pydantic DTO 定义，遵循编码规范
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


# === 请求 Schema ===
class ChatRequest(BaseModel):
    """聊天请求（需认证）"""

    user_id: str = Field(..., description="用户 ID（从 JWT token 解析）")
    thread_id: str = Field(..., description="会话线程 ID")
    message: str = Field(..., description="用户消息")
    genre: Literal["仙侠", "修仙", "奇幻", "悬疑", "言情", "科幻"] = Field(
        default="仙侠", description="小说题材"
    )


class ResumeRequest(BaseModel):
    """中断恢复请求（需认证）"""

    user_id: str = Field(..., description="用户 ID（从 JWT token 解析）")
    thread_id: str = Field(..., description="会话线程 ID")
    choice: Literal["accept", "rewrite", "restart"] = Field(
        ..., description="用户选择"
    )
    instruction: str | None = Field(
        default=None, description="修改指令（当 choice=rewrite 时）"
    )


# === 响应 Schema ===
class SessionCreateResponse(BaseModel):
    """创建会话响应"""

    user_id: str = Field(..., description="用户 ID")
    thread_id: str = Field(..., description="会话线程 ID")
    status: str = Field(default="created")


class SSEEvent(BaseModel):
    """SSE 事件"""

    type: Literal["status", "outline", "draft_delta", "interrupt", "complete", "error"]
    data: dict | str | None = Field(default=None)
    message: str | None = Field(default=None)


# === 状态 Schema ===
class OutlineSchema(BaseModel):
    """大纲结构"""

    title: str
    genre: str
    outline: dict
    characters: dict | None = None


class DraftSchema(BaseModel):
    """草稿结构"""

    chapter_number: int
    content: str
    word_count: int
