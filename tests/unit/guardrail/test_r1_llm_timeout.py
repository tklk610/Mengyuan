"""Guardrail 1: R1 - LLM calls must have explicit timeout.

对应 .claude/Claude.md 红线 R1:
    所有 LLM 调用必须显式 timeout（默认 30s，可配置）。

本测试验证 scripts/check_red_lines.py 中的 check_r1_llm_timeout() 在以下场景正确：
1. ChatOpenAI() 不带 timeout -> 报 error
2. ChatOpenAI(timeout=30) -> 通过
3. ChatAnthropic() / AzureChatOpenAI() 等多 provider 都被覆盖
4. 普通函数（非 LLM 类）调用不被误报
"""

from __future__ import annotations

import sys
from collections.abc import Callable
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[3] / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from check_red_lines import check_r1_llm_timeout  # noqa: E402


class TestR1LLMTimeoutGuardrail:
    """[Red line R1] LLM calls must have explicit timeout."""

    def test_chatopenai_without_timeout_should_be_rejected(
        self, tmp_py_file: Callable[[str, str], Path],
    ) -> None:
        """Sample 1: ChatOpenAI() without timeout must be flagged."""
        p = tmp_py_file(
            "no_timeout.py",
            (
                'from langchain_openai import ChatOpenAI\n'
                'llm = ChatOpenAI(model="gpt-4o-mini")\n'
            ),
        )
        violations = check_r1_llm_timeout([p])
        assert len(violations) == 1
        assert violations[0].rule_id == "R1"
        assert violations[0].severity == "error"
        assert "timeout" in violations[0].message

    def test_chatopenai_with_timeout_should_pass(
        self, tmp_py_file: Callable[[str, str], Path],
    ) -> None:
        """Sample 2: explicit timeout=30 must pass."""
        p = tmp_py_file(
            "with_timeout.py",
            (
                'from langchain_openai import ChatOpenAI\n'
                'llm = ChatOpenAI(model="gpt-4o-mini", timeout=30)\n'
            ),
        )
        violations = check_r1_llm_timeout([p])
        assert violations == []

    def test_anthropic_provider_requires_timeout(
        self, tmp_py_file: Callable[[str, str], Path],
    ) -> None:
        """Sample 3a: ChatAnthropic without timeout must be flagged."""
        p = tmp_py_file("anthropic.py", "llm = ChatAnthropic()\n")
        violations = check_r1_llm_timeout([p])
        assert len(violations) >= 1

    def test_azure_provider_requires_timeout(
        self, tmp_py_file: Callable[[str, str], Path],
    ) -> None:
        """Sample 3b: AzureChatOpenAI without timeout must be flagged."""
        p = tmp_py_file("azure.py", "llm = AzureChatOpenAI()\n")
        violations = check_r1_llm_timeout([p])
        assert len(violations) >= 1

    def test_zhipuai_provider_requires_timeout(
        self, tmp_py_file: Callable[[str, str], Path],
    ) -> None:
        """Sample 3c: ChatZhipuAI without timeout must be flagged."""
        p = tmp_py_file("zhipu.py", "llm = ChatZhipuAI()\n")
        violations = check_r1_llm_timeout([p])
        assert len(violations) >= 1

    def test_tongyi_provider_requires_timeout(
        self, tmp_py_file: Callable[[str, str], Path],
    ) -> None:
        """Sample 3d: ChatTongyi without timeout must be flagged."""
        p = tmp_py_file("tongyi.py", "llm = ChatTongyi()\n")
        violations = check_r1_llm_timeout([p])
        assert len(violations) >= 1

    def test_non_llm_class_call_should_not_be_flagged(
        self, tmp_py_file: Callable[[str, str], Path],
    ) -> None:
        """Sample 4: ordinary function call should not be mis-flagged."""
        p = tmp_py_file(
            "normal.py",
            (
                "class MyService:\n"
                "    def __init__(self):\n"
                "        self.config = dict(timeout=30)\n"
                "\n"
                "MyService()\n"
            ),
        )
        violations = check_r1_llm_timeout([p])
        assert violations == []

    def test_attributed_call_should_also_be_detected(
        self, tmp_py_file: Callable[[str, str], Path],
    ) -> None:
        """Sample 5: openai.ChatOpenAI() attribute-call form must also be detected."""
        p = tmp_py_file(
            "attr.py",
            (
                "import openai\n"
                'llm = openai.ChatOpenAI(model="gpt-4o-mini")\n'
            ),
        )
        violations = check_r1_llm_timeout([p])
        assert len(violations) == 1
        assert "ChatOpenAI" in violations[0].message
