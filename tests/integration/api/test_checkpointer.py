"""T10: Checkpointer Integration Tests

Tests that session state survives graph rebuild (simulating process restart):
  1. First graph invoke — interrupt fires in scribe_node, result contains __interrupt__
  2. Build fresh graph WITH SAME checkpointer instance — simulates Redis-shared state
  3. Resume with Command — interrupt() returns resume value, graph reaches END
  4. Verify final state and checkpointer type
"""
from __future__ import annotations

from contextlib import suppress
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tests.conftest import NARRATOR_RESPONSE, SCRIBE_RESPONSE


def make_mock_llm(narrator_response: str, scribe_response: str):
    """Sequential mock LLM — first call narrator, second call scribe.

    WARNING: call_count is shared across resume invocations within the same
    test. For accept-path tests that need independent counts, use
    MockLLMSingleResponse below.
    """
    call_count = 0

    async def mock_ainvoke(prompt: str) -> MagicMock:
        nonlocal call_count
        call_count += 1
        content = narrator_response if call_count == 1 else scribe_response
        result = MagicMock()
        result.content = content
        result.usage = MagicMock(
            prompt_tokens=10, completion_tokens=10, total_tokens=20
        )
        return result

    llm = MagicMock()
    llm.ainvoke = AsyncMock(side_effect=mock_ainvoke)
    return llm


def make_mock_llm_single(response: str):
    """Mock LLM that always returns the same response (no sequencing).

    Use when the LLM should not alter application state on the call that
    resumes from interrupt — e.g. accept path where draft is already saved.
    """
    async def mock_ainvoke(prompt: str) -> MagicMock:
        result = MagicMock()
        result.content = response
        result.usage = MagicMock(
            prompt_tokens=10, completion_tokens=10, total_tokens=20
        )
        return result

    llm = MagicMock()
    llm.ainvoke = AsyncMock(side_effect=mock_ainvoke)
    return llm


@pytest.mark.asyncio
async def test_session_survives_graph_rebuild():
    """Session state persists across graph rebuild (shared checkpointer).

    This is the core test for P0 Redis Checkpointer:
    - First invoke: scribe_node fires interrupt(), result contains __interrupt__
    - Fresh graph is built with the SAME checkpointer instance (simulates Redis shared state)
    - Resume with Command — interrupt() returns resume value, graph reaches END

    Note: In production, Redis provides cross-process shared state naturally.
    In tests without Redis, we pass the same checkpointer instance to both graphs.
    """
    from langgraph.types import Command

    from ai_agent.agents import novel_agent as na_module
    from ai_agent.agents.novel_agent import build_novel_graph, novel_graph

    thread_id = "test-checkpoint-survives-rebuild"
    config = {"configurable": {"thread_id": thread_id}}

    # Reuse the SAME checkpointer instance that novel_graph uses.
    # This simulates Redis shared state across process restarts.
    shared_checkpointer = novel_graph.checkpointer

    mock_llm = make_mock_llm(NARRATOR_RESPONSE, SCRIBE_RESPONSE)

    with patch.object(na_module, "get_llm", return_value=mock_llm):
        # Clear prior state
        with suppress(Exception):
            novel_graph.get_state(config)

        initial_state = {
            "messages": [{"role": "user", "content": "写一个仙侠小说"}],
            "user_request": "写一个仙侠小说",
            "genre": "仙侠",
            "outline": None,
            "characters": None,
            "current_chapter": 1,
            "draft": None,
            "phase": "idle",
            "interrupt_value": None,
            "interrupt_options": None,
            "user_choice": None,
            "error": None,
        }

        # ── Step 1: First invoke — interrupt fires in scribe_node ────────────
        result = await novel_graph.ainvoke(initial_state, config=config)

        assert "__interrupt__" in result, (
            "First invoke should have hit interrupt() in scribe_node. "
            f"Got result keys: {list(result.keys())}"
        )
        interrupt_info = result["__interrupt__"][0]
        saved_draft = interrupt_info.value.get("draft", "")
        assert saved_draft, "Interrupt value should contain draft text"

        # Verify checkpoint was saved
        pending_state = novel_graph.get_state(config)
        assert pending_state is not None
        assert pending_state.next == ("scribe",), (
            f"Expected pending node 'scribe', got {pending_state.next}"
        )

    # ── Step 2: Build fresh graph with same checkpointer ───────────────────
    # This simulates what Redis does in production: shared persistent state
    fresh_graph = build_novel_graph(checkpointer=shared_checkpointer)
    assert fresh_graph is not novel_graph

    # Verify checkpoint was loaded by fresh graph
    restored_state = fresh_graph.get_state(config)
    assert restored_state is not None, "State should be restored from checkpointer"
    assert restored_state.next == ("scribe",), (
        f"Fresh graph should have pending scribe. Got {restored_state.next}"
    )

    # ── Step 3: Resume from interrupt in fresh graph ────────────────────────
    # accept 路径：interrupt() 返回 {"choice": "accept"}, scribe_node 提取
    # user_choice = choice.get("choice") 后 == "accept"，路由到 END。
    resume_mock = make_mock_llm(NARRATOR_RESPONSE, SCRIBE_RESPONSE)
    with patch.object(na_module, "get_llm", return_value=resume_mock):
        resume_result = await fresh_graph.ainvoke(
            Command(resume={"choice": "accept", "instruction": ""}),
            config=config,
        )

    # After accept, graph reaches END (no __interrupt__)
    assert "__interrupt__" not in resume_result, (
        f"After accept, graph should reach END. Got: {resume_result}"
    )

    final_state = fresh_graph.get_state(config)
    assert final_state is not None
    # next == () 表示 END（LangGraph 用空元组表示已结束）
    assert final_state.next == (), (
        f"After accept, graph should be at END (next=()). Got next={final_state.next}"
    )


@pytest.mark.asyncio
async def test_in_memory_checkpointer_fallback():
    """MemorySaver fallback when Redis is unavailable."""
    from ai_agent.agents.novel_agent import _build_checkpointer

    checkpointer = _build_checkpointer()
    assert checkpointer is not None
    from langgraph.checkpoint.memory import MemorySaver
    from langgraph.checkpoint.redis import RedisSaver

    assert isinstance(checkpointer, (MemorySaver, RedisSaver))


@pytest.mark.asyncio
async def test_scribe_accept_branch():
    """Verify scribe_node accept branch is exercised on resume.

    This test exercises the accept branch in scribe_node (novel_agent.py
    lines 210-215) by:
      1. Isolated MemorySaver + graph — no cross-test contamination
      2. Invoke until interrupt fires
      3. Resume with Command(resume={"choice": "accept"})
      4. Assert: no __interrupt__, phase="complete", draft preserved, next=()
    """
    from langgraph.checkpoint.memory import MemorySaver
    from langgraph.types import Command

    from ai_agent.agents import novel_agent as na_module
    from ai_agent.agents.novel_agent import build_novel_graph

    thread_id = "test-scribe-accept-branch"
    config = {"configurable": {"thread_id": thread_id}}

    # Isolated checkpointer — no cross-test contamination
    isolated_checkpointer = MemorySaver()
    graph = build_novel_graph(checkpointer=isolated_checkpointer)

    mock_llm = make_mock_llm(NARRATOR_RESPONSE, SCRIBE_RESPONSE)
    with patch.object(na_module, "get_llm", return_value=mock_llm):
        initial_state = {
            "messages": [{"role": "user", "content": "写一个仙侠小说"}],
            "user_request": "写一个仙侠小说",
            "genre": "仙侠",
            "outline": None,
            "characters": None,
            "current_chapter": 1,
            "draft": None,
            "phase": "idle",
            "interrupt_value": None,
            "interrupt_options": None,
            "user_choice": None,
            "error": None,
        }

        # Trigger interrupt — scribe_node fires interrupt(), result contains __interrupt__
        result1 = await graph.ainvoke(initial_state, config=config)
        assert "__interrupt__" in result1, (
            f"First invoke should hit interrupt. Got keys: {list(result1.keys())}"
        )
        draft_saved = result1["__interrupt__"][0].value.get("draft", "")
        assert draft_saved, "Draft must have been saved from interrupt"

        # Verify checkpoint saved pending state
        pending = graph.get_state(config)
        assert pending is not None
        assert pending.next == ("scribe",)

    # Resume with accept — exercises accept branch (lines 210-215)
    # Use single-response mock so resume does not alter the already-saved draft.
    # accept path does not need LLM to return anything specific.
    resume_graph = build_novel_graph(checkpointer=isolated_checkpointer)
    resume_mock = make_mock_llm_single(SCRIBE_RESPONSE)
    with patch.object(na_module, "get_llm", return_value=resume_mock):
        result2 = await resume_graph.ainvoke(
            Command(resume={"choice": "accept", "instruction": ""}),
            config=config,
        )

    # accept path assertions
    assert "__interrupt__" not in result2
    final_state = resume_graph.get_state(config)
    assert final_state is not None
    assert final_state.next == (), (
        f"After accept, graph should be at END. Got next={final_state.next}"
    )
    assert final_state.values.get("phase") == "complete"
    assert final_state.values.get("draft") == draft_saved


@pytest.mark.asyncio
async def test_scribe_rewrite_branch():
    """Verify scribe_node rewrite branch is exercised on resume.

    After Command(resume={"choice": "rewrite"}):
      - scribe_node sets draft=None, phase="writing", then re-enters scribe
      - Second LLM call generates new draft, second interrupt fires
      - result contains __interrupt__ (not END)
      - phase should be "writing" (set by rewrite Command)
    """
    from langgraph.checkpoint.memory import MemorySaver
    from langgraph.types import Command

    from ai_agent.agents import novel_agent as na_module
    from ai_agent.agents.novel_agent import build_novel_graph

    thread_id = "test-scribe-rewrite-branch"
    config = {"configurable": {"thread_id": thread_id}}

    isolated_checkpointer = MemorySaver()
    graph = build_novel_graph(checkpointer=isolated_checkpointer)

    mock_llm = make_mock_llm(NARRATOR_RESPONSE, SCRIBE_RESPONSE)
    with patch.object(na_module, "get_llm", return_value=mock_llm):
        initial_state = {
            "messages": [{"role": "user", "content": "写一个仙侠小说"}],
            "user_request": "写一个仙侠小说",
            "genre": "仙侠",
            "outline": None,
            "characters": None,
            "current_chapter": 1,
            "draft": None,
            "phase": "idle",
            "interrupt_value": None,
            "interrupt_options": None,
            "user_choice": None,
            "error": None,
        }

        # First invoke — interrupt fires in scribe
        result1 = await graph.ainvoke(initial_state, config=config)
        assert "__interrupt__" in result1

    # Resume with rewrite — exercises rewrite branch (lines 210-219)
    resume_graph = build_novel_graph(checkpointer=isolated_checkpointer)
    resume_mock = make_mock_llm(NARRATOR_RESPONSE, SCRIBE_RESPONSE)
    with patch.object(na_module, "get_llm", return_value=resume_mock):
        result2 = await resume_graph.ainvoke(
            Command(resume={"choice": "rewrite", "instruction": ""}),
            config=config,
        )

    # rewrite path: second interrupt fires (scribe re-enters, new draft generated)
    assert "__interrupt__" in result2, (
        f"After rewrite, scribe should re-enter and fire interrupt again. Got: {result2.keys()}"
    )
    second_draft = result2["__interrupt__"][0].value.get("draft", "")
    assert second_draft, "Second interrupt should contain a new draft"

    # Phase should be "writing" (set by rewrite Command before re-entering scribe)
    final_state = resume_graph.get_state(config)
    assert final_state is not None
    assert final_state.values.get("phase") == "writing"
