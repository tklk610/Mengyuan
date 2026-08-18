"""Guardrail 7: R15 - token budget 100% must hard-reject.

对应 .claude/Claude.md 红线 R15:
    Token 配额 100% 必须硬拒绝（80% 警告 / 100% 抛 AgentBudgetExhaustedException）。

本测试验证 check_r15_budget_hard_reject():
1. token_counter.py 无 100% 硬拒绝 -> error
2. 含 AgentBudgetExhaustedException + quota 关键字 -> 通过
3. src/ 不存在 -> 跳过
"""

from __future__ import annotations

import sys
from collections.abc import Callable, Generator
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[3] / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import check_red_lines as scanner  # noqa: E402
from check_red_lines import check_r15_budget_hard_reject  # noqa: E402


@pytest.fixture
def restore_project_root() -> Generator[Callable[[Path], None], None, None]:
    """Temporarily override PROJECT_ROOT; restore after the test."""
    original = scanner.PROJECT_ROOT

    def _set(root: Path) -> None:
        scanner.PROJECT_ROOT = root

    yield _set
    scanner.PROJECT_ROOT = original


class TestR15BudgetHardRejectGuardrail:
    """[Red line R15] token budget 100% must hard-reject."""

    def test_token_counter_without_hard_reject_should_be_rejected(
        self,
        tmp_path: Path,
        restore_project_root: Callable[[Path], None],
    ) -> None:
        """Sample 1: token_counter.py only counts, no hard reject -> error."""
        src = tmp_path / "src" / "ai_agent" / "guardrail"
        src.mkdir(parents=True)
        (src / "token_counter.py").write_text(
            "def track(*args, **kwargs):\n"
            "    return 1\n",
            encoding="utf-8",
        )
        restore_project_root(tmp_path)
        violations = check_r15_budget_hard_reject([])
        assert len(violations) >= 1
        v = violations[0]
        assert v.rule_id == "R15"
        assert v.severity == "error"
        assert "AgentBudgetExhaustedException" in v.message

    def test_token_counter_with_hard_reject_should_pass(
        self,
        tmp_path: Path,
        restore_project_root: Callable[[Path], None],
    ) -> None:
        """Sample 2: complete budget hard-reject implementation must pass."""
        src = tmp_path / "src" / "ai_agent" / "guardrail"
        src.mkdir(parents=True)
        (src / "token_counter.py").write_text(
            (
                "class AgentBudgetExhaustedException(Exception):\n"
                "    pass\n"
                "\n"
                "def check_quota(used, quota):\n"
                "    if used >= quota * 1.0:\n"
                "        raise AgentBudgetExhaustedException('quota 100% reached')\n"
            ),
            encoding="utf-8",
        )
        restore_project_root(tmp_path)
        violations = check_r15_budget_hard_reject([])
        assert violations == []

    def test_missing_src_directory_should_skip(
        self,
        tmp_path: Path,
        restore_project_root: Callable[[Path], None],
    ) -> None:
        """Sample 3: src/ not exist should skip."""
        restore_project_root(tmp_path)
        violations = check_r15_budget_hard_reject([])
        assert violations == []
