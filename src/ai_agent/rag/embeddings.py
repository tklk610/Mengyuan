"""文本嵌入向量生成

使用 OpenAI 或兼容 API 生成文本嵌入向量
"""
from __future__ import annotations

from typing import Literal

import structlog
from langchain_openai import OpenAIEmbeddings

from ai_agent.config.settings import settings

logger = structlog.get_logger(__name__)


def get_embedding_model(
    provider: Literal["openai", "minimax"] | None = None,
) -> OpenAIEmbeddings:
    """获取嵌入模型

    Args:
        provider: 提供商，默认使用配置中的默认提供商

    Returns:
        OpenAIEmbeddings 实例
    """
    provider = provider or "openai"

    if provider == "minimax":
        return OpenAIEmbeddings(
            model="embo-01",
            api_key=settings.minimax_api_key,
            base_url="https://api.minimax.chat/v1",
        )
    else:
        return OpenAIEmbeddings(
            model="text-embedding-3-small",
            api_key=settings.openai_api_key or None,
        )


async def generate_embedding(text: str) -> list[float]:
    """生成文本的嵌入向量

    Args:
        text: 输入文本

    Returns:
        嵌入向量（1536 维）
    """
    try:
        embeddings = get_embedding_model()
        vector = await embeddings.aembed_query(text)
        logger.info("embedding.generated", text_length=len(text), vector_dim=len(vector))
        return vector
    except Exception as e:
        logger.error("embedding.failed", error=str(e))
        raise
