"""风格特征分析与提取

使用 LLM 分析小说文本，提取风格特征
"""
from __future__ import annotations

import json
import uuid
from typing import Any

import structlog

from ai_agent.llm.factory import ainvoke_with_timeout, get_llm
from ai_agent.exception.exceptions import ToolExecutionError

logger = structlog.get_logger(__name__)


# === Prompt Templates ===

STYLE_ANALYSIS_PROMPT = """你是一位专业的小说风格分析师。请分析以下小说文本，提取其风格特征。

分析要点：
1. 句式结构（短句/长句/复合句比例）
2. 描写密度（环境描写/心理描写/动作描写比例）
3. 对话风格（口语化/书面化/古风化）
4. 叙事视角（第一人称/第三人称/全知视角）
5. 节奏类型（快节奏/中等/慢热）
6. 文风特点（简洁华丽/古典/现代/网络等）
7. 题材特征（修仙/仙侠/奇幻/现实等）

请提取1000-2000字左右的小说片段进行分析。"

小说片段：
{text_slice}

请以 JSON 格式输出分析结果：
{{
    "sentence_structure": "句式特点描述",
    "description_density": "描写密度评价",
    "dialogue_style": "对话风格描述",
    "narrative_pov": "叙事视角",
    "pacing": "节奏类型",
    "tone": "文风/语调",
    "genre_tags": ["题材标签1", "标签2"],
    "banned_words": ["避免使用的词汇"],
    "sample_phrases": ["典型表达示例1", "示例2"]
}}"""


EMBEDDING_PROMPT = """请分析以下小说片段的写作风格，生成一个简洁的风格描述（50字以内），用于向量检索匹配。

小说片段：
{text_slice}

风格描述："""


# === Style Analyzer ===

class StyleAnalyzer:
    """小说风格分析器"""

    def __init__(self) -> None:
        self._llm = get_llm(temperature=0.3)

    async def analyze_text(self, text: str, genre_hint: str | None = None) -> dict[str, Any]:
        """分析文本风格特征

        Args:
            text: 小说文本（全文或长片段）
            genre_hint: 题材提示（可选）

        Returns:
            风格特征字典
        """
        # 取前 2000 字进行分析
        text_slice = text[:2000]
        if genre_hint:
            prompt = STYLE_ANALYSIS_PROMPT.replace(
                "请提取1000-2000字左右的小说片段进行分析。",
                f"题材提示：{genre_hint}\n\n请提取1000-2000字左右的小说片段进行分析。"
            )

        prompt = STYLE_ANALYSIS_PROMPT.format(text_slice=text_slice)

        try:
            response = await ainvoke_with_timeout(self._llm, prompt, timeout=120)
            content = response["content"]

            # 解析 JSON
            json_str = content
            if "```json" in content:
                json_str = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                json_str = content.split("```")[1].split("```")[0]

            style_features = json.loads(json_str.strip())
            logger.info("style_analyzer.complete", features=list(style_features.keys()))
            return style_features

        except json.JSONDecodeError as e:
            logger.error("style_analyzer.parse.failed", error=str(e))
            raise ToolExecutionError("style_analyzer", f"Failed to parse style features: {e}") from e
        except Exception as e:
            logger.error("style_analyzer.failed", error=str(e))
            raise ToolExecutionError("style_analyzer", str(e)) from e

    async def generate_embedding_text(self, text: str) -> str:
        """生成用于向量检索的风格描述文本

        Args:
            text: 小说文本

        Returns:
            风格描述文本（短句，用于生成向量）
        """
        text_slice = text[:1000]
        prompt = EMBEDDING_PROMPT.format(text_slice=text_slice)

        try:
            response = await ainvoke_with_timeout(self._llm, prompt, timeout=60)
            content = response["content"].strip()
            logger.info("style_analyzer.embedding_text.generated", length=len(content))
            return content
        except Exception as e:
            logger.error("style_analyzer.embedding_text.failed", error=str(e))
            raise ToolExecutionError("style_analyzer", str(e)) from e

    async def extract_full_profile(
        self,
        text: str,
        user_id: str,
        name: str,
        genre_hint: str | None = None,
    ) -> dict[str, Any]:
        """提取完整的风格档案

        Args:
            text: 小说文本
            user_id: 用户 ID
            name: 风格档案名称
            genre_hint: 题材提示

        Returns:
            完整的风格档案（包含向量）
        """
        from ai_agent.rag.embeddings import generate_embedding

        profile_id = str(uuid.uuid4())

        # 并行分析风格特征和生成嵌入文本
        import asyncio
        style_task = self.analyze_text(text, genre_hint)
        embedding_text_task = self.generate_embedding_text(text)

        style_features, embedding_text = await asyncio.gather(
            style_task, embedding_text_task
        )

        # 生成向量
        vector = await generate_embedding(embedding_text)

        return {
            "profile_id": profile_id,
            "user_id": user_id,
            "name": name,
            "vector": vector,
            "embedding_text": embedding_text,
            "genre_tags": style_features.get("genre_tags", []),
            "characteristics": {
                "sentence_structure": style_features.get("sentence_structure", ""),
                "description_density": style_features.get("description_density", ""),
                "dialogue_style": style_features.get("dialogue_style", ""),
                "narrative_pov": style_features.get("narrative_pov", ""),
                "pacing": style_features.get("pacing", ""),
                "tone": style_features.get("tone", ""),
            },
            "banned_words": style_features.get("banned_words", []),
            "sample_phrases": style_features.get("sample_phrases", []),
        }


# === Global Instance (lazy) ===
_style_analyzer: StyleAnalyzer | None = None
_style_analyzer_initialized = False


def _get_style_analyzer() -> StyleAnalyzer:
    """Lazy accessor to avoid LLM init at import time."""
    global _style_analyzer, _style_analyzer_initialized
    if not _style_analyzer_initialized:
        _style_analyzer = StyleAnalyzer()
        _style_analyzer_initialized = True
    return _style_analyzer


def __getattr__(name: str):
    """Lazy proxy: forward attribute access to the actual analyzer."""
    if name == "style_analyzer":
        return _get_style_analyzer()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
