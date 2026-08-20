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


# === 风格档案 Schema ===

class StyleProfileBase(BaseModel):
    """风格档案基础"""

    name: str = Field(..., description="风格档案名称")
    genre_hint: str | None = Field(default=None, description="题材提示")


class StyleProfileCreate(StyleProfileBase):
    """创建风格档案请求"""

    text_sample: str = Field(..., description="小说文本样本（1000-2000字）")


class StyleProfileResponse(StyleProfileBase):
    """风格档案响应"""

    profile_id: str
    genre_tags: list[str]
    characteristics: dict
    banned_words: list[str]
    sample_phrases: list[str]


class StyleSearchRequest(BaseModel):
    """风格搜索请求"""

    text_sample: str = Field(..., description="文本样本用于匹配相似风格")


class StyleSearchResponse(BaseModel):
    """风格搜索响应"""

    styles: list[dict]


# === 用户偏好 Schema ===

class UserPreferenceBase(BaseModel):
    """用户偏好基础"""

    narrative_pov: str | None = Field(default="第三人称", description="叙事视角")
    target_word_count: int = Field(default=3000, description="每章目标字数")
    ending_preference: str | None = Field(default="HE", description="结局倾向 (HE/BE/NE/开放)")
    pacing_preference: str | None = Field(default="中等", description="节奏偏好")
    avoid_elements: list[str] = Field(default_factory=list, description="避免的元素")
    preferred_tones: list[str] = Field(default_factory=list, description="偏好语调")


class UserPreferenceUpdate(UserPreferenceBase):
    """更新用户偏好请求"""


class UserPreferenceResponse(UserPreferenceBase):
    """用户偏好响应"""

    user_id: str
