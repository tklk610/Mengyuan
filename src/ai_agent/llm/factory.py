"""LLM Factory - 统一 LLM 调用入口

遵循编码规范 §3.1:
- 禁止直接散落 ChatOpenAI().invoke()
- 必须通过工厂获取
- 自动注入 timeout / retry / token 计数
"""
from __future__ import annotations

import time
from typing import Literal

from langchain_anthropic import ChatAnthropic
from langchain_core.language_models import BaseChatModel
from langchain_openai import ChatOpenAI
from typing_extensions import TypedDict

from ai_agent.config.settings import settings
from ai_agent.exception.exceptions import LLMTimeoutError


class LLMResponse(TypedDict):
    """LLM 响应结构"""

    content: str
    usage: dict


def get_llm(
    provider: Literal["minimax", "openai", "anthropic"] | None = None,
    model: str | None = None,
    temperature: float | None = None,
    max_tokens: int | None = None,
    timeout: int | None = None,
) -> BaseChatModel:
    """获取 LLM 实例的工厂方法

    Args:
        provider: LLM 提供商，默认使用配置中的默认提供商
        model: 模型名称，默认使用配置中的默认模型
        temperature: 温度参数
        max_tokens: 最大 token 数
        timeout: 超时秒数

    Returns:
        BaseChatModel 实例
    """
    provider = provider or settings.llm_provider
    temperature = temperature or settings.llm_temperature
    max_tokens = max_tokens or settings.llm_max_tokens
    timeout = timeout or settings.llm_timeout_seconds

    if provider == "openai":
        return ChatOpenAI(
            model=model or settings.openai_model,
            temperature=temperature,
            max_tokens=max_tokens,  # type: ignore[call-arg]
            timeout=timeout,
            api_key=settings.openai_api_key or None,  # type: ignore[arg-type]
        )
    elif provider == "anthropic":
        return ChatAnthropic(
            model=model or settings.anthropic_model,
            temperature=temperature,
            max_tokens=max_tokens,  # type: ignore[call-arg]
            timeout=timeout,
            api_key=settings.anthropic_api_key or None,  # type: ignore[arg-type]
        )
    elif provider == "minimax":
        # MiniMax 使用 OpenAI 兼容 API
        return ChatOpenAI(
            model=model or settings.minimax_model,
            temperature=temperature,
            max_tokens=max_tokens,  # type: ignore[call-arg]
            timeout=timeout,
            api_key=settings.minimax_api_key or None,  # type: ignore[arg-type]
            base_url="https://api.minimax.chat/v1",
        )
    else:
        raise ValueError(f"Unsupported LLM provider: {provider}")


async def ainvoke_with_timeout(
    llm: BaseChatModel, prompt: str, timeout: int = 120
) -> LLMResponse:
    """带超时控制的 LLM 调用

    Args:
        llm: LLM 实例
        prompt: 输入提示
        timeout: 超时秒数

    Returns:
        LLMResponse with content and usage

    Raises:
        LLMTimeoutError: 调用超时
    """
    start_time = time.perf_counter()

    try:
        import asyncio

        result = await asyncio.wait_for(
            llm.ainvoke(prompt),
            timeout=timeout,
        )

        latency_ms = round((time.perf_counter() - start_time) * 1000, 2)

        return LLMResponse(
            content=str(result.content) if hasattr(result, "content") else str(result),
            usage={
                "prompt_tokens": result.usage.prompt_tokens
                if hasattr(result, "usage") and hasattr(result.usage, "prompt_tokens")
                else 0,
                "completion_tokens": result.usage.completion_tokens
                if hasattr(result, "usage") and hasattr(result.usage, "completion_tokens")
                else 0,
                "total_tokens": result.usage.total_tokens
                if hasattr(result, "usage") and hasattr(result.usage, "total_tokens")
                else 0,
                "latency_ms": latency_ms,
            },
        )

    except TimeoutError as e:
        raise LLMTimeoutError(
            model=getattr(llm, "model", "unknown"), timeout=timeout
        ) from e
