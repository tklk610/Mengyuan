"""Guardrail 5: R12 - PII must be redacted.

对应 .claude/Claude.md 红线 R12:
    PII 必须脱敏（邮箱 / 手机 / 身份证 / 银行卡）。
    三处必须脱敏：进入 Prompt 前 / 写入日志前 / 写入审计库前。

本测试验证 check_r12_pii_redaction():
1. logger.info() 包含 PII 字段 -> warning
2. 函数体内含 redact() 调用 -> 通过
3. 不含 PII 字段的日志不报
"""

from __future__ import annotations

import sys
from collections.abc import Callable
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[3] / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from check_red_lines import check_r12_pii_redaction  # noqa: E402


class TestR12PIIRedactionGuardrail:
    """[Red line R12] PII must be redacted."""

    def test_logger_info_with_pii_field_should_be_rejected(
        self, tmp_py_file: Callable[[str, str], Path],
    ) -> None:
        """Sample 1: logger.info() with email but no redact() in function -> warning."""
        p = tmp_py_file(
            "no_redact.py",
            (
                "import structlog\n"
                "logger = structlog.get_logger(__name__)\n"
                "\n"
                "def handle(user_email):\n"
                '    logger.info("user.contact", email=user_email)\n'
            ),
        )
        violations = check_r12_pii_redaction([p])
        assert len(violations) >= 1
        v = violations[0]
        assert v.rule_id == "R12"
        assert v.severity == "warning"
        assert "redact" in v.message.lower()

    def test_logger_with_redact_call_should_pass(
        self, tmp_py_file: Callable[[str, str], Path],
    ) -> None:
        """Sample 2: function with redact() call must pass."""
        p = tmp_py_file(
            "with_redact.py",
            (
                "import structlog\n"
                "from ai_agent.guardrail.pii import redact\n"
                "logger = structlog.get_logger(__name__)\n"
                "\n"
                "def handle(user_email):\n"
                "    safe = redact(user_email)\n"
                '    logger.info("user.contact", email=safe)\n'
            ),
        )
        violations = check_r12_pii_redaction([p])
        assert violations == []

    @pytest.mark.parametrize(
        "pii_keyword",
        ["email", "phone", "id_card"],
    )
    def test_english_pii_fields_should_be_detected(
        self, tmp_py_file: Callable[[str, str], Path], pii_keyword: str,
    ) -> None:
        """Sample 3: all English PII field names should be covered."""
        p = tmp_py_file(
            "pii.py",
            (
                "import structlog\n"
                "logger = structlog.get_logger(__name__)\n"
                "\n"
                "def handle(val):\n"
                f'    logger.info("evt", {pii_keyword}=val)\n'
            ),
        )
        violations = check_r12_pii_redaction([p])
        assert len(violations) >= 1, (
            f"field '{pii_keyword}' should be flagged by R12"
        )

    def test_logger_info_without_pii_should_not_be_flagged(
        self, tmp_py_file: Callable[[str, str], Path],
    ) -> None:
        """Sample 4: log without PII field should not be flagged."""
        p = tmp_py_file(
            "safe.py",
            (
                "import structlog\n"
                "logger = structlog.get_logger(__name__)\n"
                "\n"
                "def handle(request_id, latency_ms):\n"
                '    logger.info("api.call", request_id=request_id, latency_ms=latency_ms)\n'
            ),
        )
        violations = check_r12_pii_redaction([p])
        assert violations == []
