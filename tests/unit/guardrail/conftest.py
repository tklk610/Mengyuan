"""Shared fixtures for guardrail tests."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest


@pytest.fixture
def tmp_py_file(tmp_path: Path) -> Callable[[str, str], Path]:
    """Factory: tmp_py_file('foo.py', 'print(1)') -> Path."""

    def _factory(name: str, content: str) -> Path:
        p = tmp_path / name
        p.write_text(content, encoding="utf-8")
        return p

    return _factory
