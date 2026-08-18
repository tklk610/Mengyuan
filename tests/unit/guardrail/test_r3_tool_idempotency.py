"""Guardrail 2: R3 - all tools must implement idempotency_key.

对应 .claude/Claude.md 红线 R3:
    所有工具必须幂等（Agent 重跑不能重复扣费/发消息）。

本测试验证 check_r3_tool_idempotency():
1. 继承 BaseTool 但缺 idempotency_key -> 报 error
2. 实现 idempotency_key -> 通过
3. 非 BaseTool 子类不报错
4. 多个工具类都被扫描
"""

from __future__ import annotations

import sys
from collections.abc import Callable
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[3] / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from check_red_lines import check_r3_tool_idempotency  # noqa: E402


class TestR3ToolIdempotencyGuardrail:
    """[Red line R3] all tools must implement idempotency_key."""

    def test_tool_without_idempotency_key_should_be_rejected(
        self, tmp_py_file: Callable[[str, str], Path],
    ) -> None:
        """Sample 1: inheriting BaseTool without idempotency_key must be flagged."""
        p = tmp_py_file(
            "tool_no_idem.py",
            (
                "from ai_agent.tool.base import BaseTool\n"
                "\n"
                "class SendEmailTool(BaseTool):\n"
                '    name = "send_email"\n'
                "    async def _arun(self, to, body):\n"
                "        await send(to, body)\n"
            ),
        )
        violations = check_r3_tool_idempotency([p])
        assert len(violations) == 1
        assert violations[0].rule_id == "R3"
        assert violations[0].severity == "error"
        assert "idempotency_key" in violations[0].message

    def test_tool_with_idempotency_key_should_pass(
        self, tmp_py_file: Callable[[str, str], Path],
    ) -> None:
        """Sample 2: correctly implementing idempotency_key must pass."""
        p = tmp_py_file(
            "tool_ok.py",
            (
                "from ai_agent.tool.base import BaseTool\n"
                "\n"
                "class SendEmailTool(BaseTool):\n"
                '    name = "send_email"\n'
                "    async def _arun(self, to, body):\n"
                "        await send(to, body)\n"
                "    def idempotency_key(self, **kwargs):\n"
                "        return str(kwargs.get('message_id', ''))\n"
            ),
        )
        violations = check_r3_tool_idempotency([p])
        assert violations == []

    def test_non_base_tool_class_should_not_be_flagged(
        self, tmp_py_file: Callable[[str, str], Path],
    ) -> None:
        """Sample 3: non-BaseTool subclass should not be mis-flagged."""
        p = tmp_py_file(
            "not_a_tool.py",
            (
                "class UserService:\n"
                "    def create_user(self, name):\n"
                "        self.db.insert(name)\n"
            ),
        )
        violations = check_r3_tool_idempotency([p])
        assert violations == []

    def test_multiple_tools_all_checked(
        self, tmp_py_file: Callable[[str, str], Path],
    ) -> None:
        """Sample 4: multiple tool classes are all scanned."""
        p = tmp_py_file(
            "two_tools.py",
            (
                "from ai_agent.tool.base import BaseTool\n"
                "\n"
                "class A(BaseTool):\n"
                '    name = "a"\n'
                "    async def _arun(self):\n"
                "        pass\n"
                "\n"
                "class B(BaseTool):\n"
                '    name = "b"\n'
                "    async def _arun(self):\n"
                "        pass\n"
            ),
        )
        violations = check_r3_tool_idempotency([p])
        assert len(violations) == 2
        messages = {v.message for v in violations}
        assert any("A" in m for m in messages)
        assert any("B" in m for m in messages)
