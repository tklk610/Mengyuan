"""NovelCraft Agent State Schema

LangGraph State 定义，用于多 Agent 协作时的共享状态
遵循编码规范 - 完整类型注解
"""
from __future__ import annotations

import operator
from typing import Annotated, Literal, NotRequired, TypedDict


class NovelState(TypedDict):
    """NovelCraft Agent 共享状态"""

    # === 对话历史 ===
    messages: Annotated[list[dict], operator.add]
    """对话消息历史"""

    # === 用户输入 ===
    user_request: str
    """用户原始需求"""
    genre: str
    """小说题材"""

    # === 创作内容 ===
    outline: dict | None
    """结构化大纲（Narrator 生成）"""
    characters: dict | None
    """角色设定"""
    current_chapter: int
    """当前章节号"""
    total_chapters: int
    """计划总章节数"""
    draft: str | None
    """当前草稿（Scribe 生成）"""
    completed_chapters: list[dict]
    """已完成章节列表 [{chapter: int, title: str, draft: str, word_count: int}]"""

    # === 控制信号 ===
    phase: NotRequired[Literal[
        "idle", "planning", "writing", "waiting_approval", "complete"
    ]]
    """当前阶段"""
    interrupt_type: NotRequired[str | None]
    """中断类型"""
    interrupt_options: NotRequired[list[str] | None]
    """中断选项（供重入时恢复）"""
    user_choice: NotRequired[str | None]
    """用户选择"""
    interrupt_value: NotRequired[dict | None]
    """中断值（draft/choice 等，供重入时恢复）"""

    # === 错误处理 ===
    error: str | None
    """错误信息"""
