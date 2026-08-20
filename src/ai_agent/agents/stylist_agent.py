"""Stylist Agent - 风格控制 Agent

负责：
1. 从 Qdrant 加载风格档案
2. 将风格约束注入到创作 prompt 中
3. 管理用户偏好
"""
from __future__ import annotations

import structlog

from ai_agent.llm.factory import get_llm
from ai_agent.rag.embeddings import generate_embedding
from ai_agent.rag.qdrant_client import qdrant_store
from ai_agent.rag import style_analyzer as style_analyzer_mod

def _get_style_analyzer():
    return style_analyzer_mod._get_style_analyzer()

logger = structlog.get_logger(__name__)


class StylistAgent:
    """风格控制 Agent"""

    def __init__(self) -> None:
        self._llm = get_llm(temperature=0.3)

    async def load_style_profile(
        self,
        user_id: str,
        style_name: str | None = None,
        genre_hint: str | None = None,
    ) -> dict | None:
        """加载风格档案

        Args:
            user_id: 用户 ID
            style_name: 风格档案名称（可选）
            genre_hint: 题材提示

        Returns:
            风格档案或 None
        """
        if not style_name:
            # 返回用户的默认风格档案
            profiles = qdrant_store.list_style_profiles(user_id)
            if profiles:
                return profiles[0]
            return None

        # 按名称搜索
        profiles = qdrant_store.list_style_profiles(user_id)
        for profile in profiles:
            if profile.get("name") == style_name:
                return profile

        return None

    async def find_similar_styles(
        self,
        text_sample: str,
        user_id: str,
        limit: int = 3,
    ) -> list[dict]:
        """查找相似风格

        Args:
            text_sample: 文本样本
            user_id: 用户 ID
            limit: 返回数量

        Returns:
            相似风格列表
        """
        try:
            vector = await generate_embedding(text_sample)
            return qdrant_store.search_similar_styles(vector, user_id, limit)
        except Exception as e:
            logger.error("stylist.find_similar.failed", error=str(e))
            return []

    async def create_style_profile(
        self,
        user_id: str,
        name: str,
        text_sample: str,
        genre_hint: str | None = None,
    ) -> dict:
        """创建新的风格档案

        Args:
            user_id: 用户 ID
            name: 风格档案名称
            text_sample: 小说文本样本
            genre_hint: 题材提示

        Returns:
            创建的风格档案
        """
        # 分析风格特征
        profile = await _get_style_analyzer().extract_full_profile(
            text=text_sample,
            user_id=user_id,
            name=name,
            genre_hint=genre_hint,
        )

        # 存储到 Qdrant
        qdrant_store.upsert_style_profile(
            user_id=user_id,
            profile_id=profile["profile_id"],
            name=name,
            vector=profile["vector"],
            payload={
                "embedding_text": profile["embedding_text"],
                "genre_tags": profile["genre_tags"],
                "characteristics": profile["characteristics"],
                "banned_words": profile["banned_words"],
                "sample_phrases": profile["sample_phrases"],
            },
        )

        logger.info("stylist.profile.created", user_id=user_id, profile_id=profile["profile_id"])
        return profile

    def apply_style_constraints(
        self,
        prompt: str,
        style_profile: dict,
    ) -> str:
        """将风格约束注入到 prompt

        Args:
            prompt: 原始 prompt
            style_profile: 风格档案

        Returns:
            注入风格约束后的 prompt
        """
        characteristics = style_profile.get("characteristics", {})
        banned_words = style_profile.get("banned_words", [])
        sample_phrases = style_profile.get("sample_phrases", [])

        style_guide = "\n\n## 风格约束\n"

        if characteristics:
            style_guide += "### 写作风格要求：\n"
            for key, value in characteristics.items():
                if value:
                    style_guide += f"- {key}: {value}\n"

        if banned_words:
            style_guide += f"\n### 避免使用的词汇：\n{'、'.join(banned_words)}\n"

        if sample_phrases:
            style_guide += f"\n### 典型表达示例：\n{'；'.join(sample_phrases)}\n"

        return prompt + style_guide

    async def list_user_styles(self, user_id: str) -> list[dict]:
        """列出用户所有风格档案

        Args:
            user_id: 用户 ID

        Returns:
            风格档案列表
        """
        return qdrant_store.list_style_profiles(user_id)


# === Global Instance (lazy) ===
_stylist_agent: StylistAgent | None = None


def _get_stylist_agent() -> StylistAgent:
    """Lazy accessor."""
    global _stylist_agent
    if _stylist_agent is None:
        _stylist_agent = StylistAgent()
    return _stylist_agent


class _LazyStylistAgent:
    """Proxy that defers StylistAgent creation until first method call."""

    def __getattr__(self, name: str):
        return getattr(_get_stylist_agent(), name)


stylist_agent = _LazyStylistAgent()
