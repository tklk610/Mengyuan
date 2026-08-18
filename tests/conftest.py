"""
Harness Engineering — pytest 全局配置

依照 .harness/rules/工程结构规范.md 的「测试目录结构」规范：
- tests/unit/        单元测试
- tests/integration/ 集成测试（需 docker-compose 服务）
- tests/e2e/         端到端测试
- tests/conftest.py  全局 fixture（这里是它）

依赖 pyproject.toml 中 pytest 配置：
- asyncio_mode = "auto"        : 所有 async def 视为 asyncio 测试
- markers = unit/integration/e2e
- coverage = --cov=src --cov-fail-under=80
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

# 把项目根和 src 目录加入 sys.path
# - src/ai_agent/ 需要能以 `ai_agent` 导入（用于 `from ai_agent.main import app`）
# - scripts/ 需要能以 `scripts` 导入（用于 `from scripts.check_red_lines import ...`）
PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_ROOT = PROJECT_ROOT / "src"
for p in (str(SRC_ROOT), str(PROJECT_ROOT)):
    if p not in sys.path:
        sys.path.insert(0, p)

# ============================================================================
# T09 — NovelCraft E2E Integration Test Mock Responses
# ============================================================================

NARRATOR_RESPONSE = json.dumps({
    "title": "仙剑奇缘",
    "genre": "仙侠",
    "outline": {
        "act1": {
            "name": "第一幕：仙门开",
            "summary": "少年意外踏入修仙路",
            "chapters": [
                {
                    "ch_num": 1,
                    "title": "第1章：山中奇遇",
                    "summary": "主角捡到玉简",
                    "viewpoint": "第三人称",
                    "conflict": "奇遇",
                    "target_words": 2500,
                }
            ],
        },
        "act2": {"name": "第二幕：风云际会", "summary": "...", "chapters": []},
        "act3": {"name": "第三幕：尘埃落定", "summary": "...", "chapters": []},
    },
    "characters": {
        "protagonist": {
            "name": "李逍遥",
            "background": "...",
            "motivation": "求道",
            "weakness": "...",
        },
        "antagonist": {
            "name": "魔尊",
            "background": "...",
            "motivation": "...",
            "weakness": "...",
        },
        "allies": [],
    },
    "world_setting": {"system": "修真体系", "locations": ["蜀山", "人间"]},
})

SCRIBE_RESPONSE = (
    "少年李逍遥走在山间小路上，阳光透过树叶洒落，"
    "忽然一道光芒从草丛中射出，直冲天际..."
)

# ── Test JWT fixtures ─────────────────────────────────────────────────────────

TEST_USER_ID = "test-user-001"


@pytest.fixture
def test_token() -> str:
    """Create a short-lived JWT for test requests (no real auth needed)."""
    from ai_agent.auth.jwt import create_access_token
    from datetime import timedelta

    return create_access_token(TEST_USER_ID, expires_delta=timedelta(hours=1))


@pytest.fixture
def auth_headers(test_token: str) -> dict[str, str]:
    """Authorization header dict for test requests."""
    return {"Authorization": f"Bearer {test_token}"}

