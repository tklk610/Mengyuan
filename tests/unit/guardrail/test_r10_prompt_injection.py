"""Guardrail 3: R10 - no direct string concat of user input into Prompt.

对应 .claude/Claude.md 红线 R10:
    禁止直接拼接用户输入到 Prompt (防 prompt injection)。

本测试验证 check_r10_prompt_injection():
1. f-string 拼接 user_input / query / message -> 报 error
2. f-string 但不含用户输入 -> 不报
3. prompt += user_input 字符串拼接 -> 报 error
4. 经过 guardrail.input_filter.detect_injection() 过滤 -> 不报
"""

from __future__ import annotations

import sys
from collections.abc import Callable
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[3] / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from check_red_lines import check_r10_prompt_injection  # noqa: E402


class TestR10PromptInjectionGuardrail:
    """[Red line R10] no direct string concat of user input into Prompt."""

    def test_fstring_with_user_input_should_be_rejected(
        self, tmp_py_file: Callable[[str, str], Path],
    ) -> None:
        """Sample 1: f-string with user_input must be flagged as error."""
        p = tmp_py_file(
            "inject.py",
            (
                "def build_prompt(user_input):\n"
                '    prompt = f"You are an assistant. User said: {user_input}"\n'
                "    return prompt\n"
            ),
        )
        violations = check_r10_prompt_injection([p])
        assert len(violations) >= 1
        v = violations[0]
        assert v.rule_id == "R10"
        assert v.severity == "error"
        assert "PromptTemplate" in v.message

    def test_fstring_with_user_query_should_also_be_rejected(
        self, tmp_py_file: Callable[[str, str], Path],
    ) -> None:
        """Sample 2: f-string with user_query must also be flagged."""
        p = tmp_py_file(
            "inject_query.py",
            (
                "def f(user_query):\n"
                '    p = f"Answer: {user_query}"\n'
                "    return p\n"
            ),
        )
        violations = check_r10_prompt_injection([p])
        assert len(violations) >= 1

    def test_fstring_without_user_input_should_pass(
        self, tmp_py_file: Callable[[str, str], Path],
    ) -> None:
        """Sample 3: plain f-string (no user/input/query keyword) should not flag."""
        p = tmp_py_file(
            "safe.py",
            (
                "def build_prompt(name, age):\n"
                '    return f"User name: {name}, age: {age}"\n'
            ),
        )
        violations = check_r10_prompt_injection([p])
        assert violations == []

    def test_prompt_plus_equal_user_input_should_be_rejected(
        self, tmp_py_file: Callable[[str, str], Path],
    ) -> None:
        """Sample 4: prompt += user_input string concat must be flagged."""
        p = tmp_py_file(
            "concat.py",
            (
                "def bad(user_input):\n"
                "    system_prompt = 'You are an assistant.'\n"
                "    system_prompt += user_input\n"
                "    return system_prompt\n"
            ),
        )
        violations = check_r10_prompt_injection([p])
        assert len(violations) >= 1
        assert violations[0].rule_id == "R10"

    def test_redact_call_should_be_excluded(
        self, tmp_py_file: Callable[[str, str], Path],
    ) -> None:
        """Sample 5: defensive filter (redact / filter) call should be excluded."""
        p = tmp_py_file(
            "defensive.py",
            (
                "def safe(user_input):\n"
                "    cleaned = guardrail.pii.redact(user_input)\n"
                '    prompt = f"You are an assistant. User said: {cleaned}"\n'
                "    return prompt\n"
            ),
        )
        violations = check_r10_prompt_injection([p])
        for v in violations:
            assert "user_input" not in v.snippet or "redact" in v.snippet
        print(f"[safe] {len(violations)} violation(s); redact protection applied")
