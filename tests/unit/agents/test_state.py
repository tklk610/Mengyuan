"""Unit tests for NovelState schema"""
from __future__ import annotations

from ai_agent.agents.state import NovelState


def test_novel_state_initial_values():
    """Test NovelState initial values"""
    state = NovelState(
        user_request="测试请求",
        genre="仙侠",
        messages=[],
        current_chapter=0,
    )

    assert state["user_request"] == "测试请求"
    assert state["genre"] == "仙侠"
    assert state.get("phase") is None  # NotRequired, no default
    assert state["current_chapter"] == 0
    assert state.get("outline") is None  # NotRequired
    assert state.get("draft") is None  # NotRequired


def test_novel_state_messages_accumulation():
    """Test messages list accumulation with reducer"""
    state = NovelState(
        user_request="测试",
        genre="仙侠",
        messages=[{"role": "user", "content": "Hello"}],
    )

    # Simulate adding more messages
    state["messages"].append({"role": "assistant", "content": "Hi"})

    assert len(state["messages"]) == 2
    assert state["messages"][0]["role"] == "user"
    assert state["messages"][1]["role"] == "assistant"
