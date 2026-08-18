"""Guardrail 6: R14 - model fallback chain must be defined.

对应 .claude/Claude.md 红线 R14:
    模型降级链必须定义（主 -> 备 -> 默认回复）。

本测试验证 check_r14_fallback_chain():
1. config/llm_config.py 缺 MODEL_FALLBACK_CHAIN -> error
2. 含 MODEL_FALLBACK_CHAIN 定义 -> 通过
3. config 目录不存在 -> 跳过（PoC 阶段合理）
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
from check_red_lines import check_r14_fallback_chain  # noqa: E402


@pytest.fixture
def restore_project_root() -> Generator[Callable[[Path], None], None, None]:
    """Temporarily override PROJECT_ROOT; restore after the test."""
    original = scanner.PROJECT_ROOT

    def _set(root: Path) -> None:
        scanner.PROJECT_ROOT = root

    yield _set
    scanner.PROJECT_ROOT = original


class TestR14FallbackChainGuardrail:
    """[Red line R14] model fallback chain must be defined."""

    def test_missing_fallback_chain_should_be_rejected(
        self,
        tmp_path: Path,
        restore_project_root: Callable[[Path], None],
    ) -> None:
        """Sample 1: config/llm_config.py exists but no MODEL_FALLBACK_CHAIN -> error."""
        src = tmp_path / "src" / "ai_agent" / "config"
        src.mkdir(parents=True)
        (src / "llm_config.py").write_text(
            "# only defines the primary model\n"
            'PRIMARY_MODEL = "gpt-4o-mini"\n',
            encoding="utf-8",
        )
        restore_project_root(tmp_path)
        violations = check_r14_fallback_chain([])
        assert len(violations) >= 1
        v = violations[0]
        assert v.rule_id == "R14"
        assert v.severity == "error"
        assert "MODEL_FALLBACK_CHAIN" in v.message

    def test_fallback_chain_defined_should_pass(
        self,
        tmp_path: Path,
        restore_project_root: Callable[[Path], None],
    ) -> None:
        """Sample 2: explicit MODEL_FALLBACK_CHAIN must pass."""
        src = tmp_path / "src" / "ai_agent" / "config"
        src.mkdir(parents=True)
        (src / "llm_config.py").write_text(
            'MODEL_FALLBACK_CHAIN = ["gpt-4o-mini", "claude-3-5-haiku", "glm-4-flash"]\n',
            encoding="utf-8",
        )
        restore_project_root(tmp_path)
        violations = check_r14_fallback_chain([])
        assert violations == []

    def test_missing_src_directory_should_skip(
        self,
        tmp_path: Path,
        restore_project_root: Callable[[Path], None],
    ) -> None:
        """Sample 3: src/ not exist (PoC stage) should skip without false positive."""
        restore_project_root(tmp_path)
        violations = check_r14_fallback_chain([])
        assert violations == []
