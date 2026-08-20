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
    total_chapters: int = Field(
        default=3, ge=1, le=100, description="计划创作章节数"
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


# === 导出 Schema ===

class ExportRequest(BaseModel):
    """导出请求"""

    thread_id: str = Field(..., description="会话线程 ID")
    title: str = Field(default="未命名小说", description="小说标题")


class ExportResponse(BaseModel):
    """导出响应"""

    content: str = Field(..., description="导出的文本内容")
    byte_count: int = Field(..., description="内容字节数")


# === Session Schema ===

class SessionInfo(BaseModel):
    """会话信息"""

    thread_id: str
    user_id: str
    phase: str
    current_chapter: int
    total_chapters: int
    created_at: str | None = None


class SessionListResponse(BaseModel):
    """会话列表响应"""

    sessions: list[SessionInfo]


# === Outline Schema ===

class OutlineUpdate(BaseModel):
    """大纲更新请求"""

    outline: dict = Field(..., description="更新后的大纲结构")
    characters: dict | None = Field(default=None, description="更新后的角色设定")


class OutlineResponse(BaseModel):
    """大纲响应"""

    outline: dict
    characters: dict | None
    phase: str
