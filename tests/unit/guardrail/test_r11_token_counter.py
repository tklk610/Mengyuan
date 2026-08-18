"""Guardrail 4: R11 - record token usage across the full chain.

对应 .claude/Claude.md 红线 R11:
    全链路记录 token 用量（prompt / completion / total / 估算成本）。

本测试验证 check_r11_token_counter():
1. LLM 调用未包裹 TokenCounter.track() -> warning
2. 包裹了 TokenCounter.track() -> 通过
3. 非 LLM 方法调用（如自定义函数）不报
"""

from __future__ import annotations

import sys
from collections.abc import Callable
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[3] / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from check_red_lines import check_r11_token_counter  # noqa: E402


class TestR11TokenCounterGuardrail:
    """[Red line R11] record token usage across the full chain."""

    def test_llm_call_without_token_counter_should_be_rejected(
        self, tmp_py_file: Callable[[str, str], Path],
    ) -> None:
        """Sample 1: .ainvoke() but no TokenCounter.track in function -> warning."""
        p = tmp_py_file(
            "no_counter.py",
            (
                "from langchain_openai import ChatOpenAI\n"
                "\n"
                "async def summarize(text):\n"
                '    llm = ChatOpenAI(model="gpt-4o-mini", timeout=30)\n'
                '    resp = await llm.ainvoke(f"Summarize: {text}")\n'
                "    return resp.content\n"
            ),
        )
        violations = check_r11_token_counter([p])
        assert len(violations) >= 1
        v = violations[0]
        assert v.rule_id == "R11"
        assert v.severity == "warning"
        assert "TokenCounter" in v.message

    def test_llm_call_with_token_counter_should_pass(
        self, tmp_py_file: Callable[[str, str], Path],
    ) -> None:
        """Sample 2: correctly wrapped with TokenCounter.track() must pass."""
        p = tmp_py_file(
            "with_counter.py",
            (
                "from langchain_openai import ChatOpenAI\n"
                "from ai_agent.guardrail.token_counter import TokenCounter\n"
                "\n"
                "async def summarize(text, request_id):\n"
                '    llm = ChatOpenAI(model="gpt-4o-mini", timeout=30)\n'
                "    counter = TokenCounter()\n"
                '    with counter.track(request_id=request_id, model="gpt-4o-mini"):\n'
                '        resp = await llm.ainvoke(f"Summarize: {text}")\n'
                "    return resp.content\n"
            ),
        )
        violations = check_r11_token_counter([p])
        assert violations == []

    def test_non_llm_call_should_not_be_flagged(
        self, tmp_py_file: Callable[[str, str], Path],
    ) -> None:
        """Sample 3: plain function call (not .ainvoke/.invoke/.astream/.stream) ok."""
        p = tmp_py_file(
            "plain.py",
            (
                "def fetch_user(user_id):\n"
                "    return db.get(user_id)\n"
                "\n"
                "async def async_helper():\n"
                "    return await fetch_user('123')\n"
            ),
        )
        violations = check_r11_token_counter([p])
        assert violations == []

    @pytest.mark.parametrize("method", ["ainvoke", "invoke", "astream", "stream"])
    def test_all_llm_methods_are_tracked(
        self, tmp_py_file: Callable[[str, str], Path], method: str,
    ) -> None:
        """Sample 4: all 4 LLM invocation styles must be scanned."""
        p = tmp_py_file(
            "all_methods.py",
            (
                "async def f():\n"
                f"    resp = await llm.{method}(prompt)\n"
                "    return resp\n"
            ),
        )
        violations = check_r11_token_counter([p])
        assert len(violations) >= 1, (
            f"method {method}() should be flagged by R11"
        )
