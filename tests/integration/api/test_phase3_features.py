"""Phase 3 高级功能集成测试

测试多章节创作、导出、会话管理、大纲编辑功能
"""
from __future__ import annotations

import json
from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from tests.conftest import NARRATOR_RESPONSE, SCRIBE_RESPONSE, TEST_USER_ID


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def app():
    """Import the FastAPI app directly."""
    from ai_agent.main import app
    return app


@pytest.fixture
async def client(app, auth_headers) -> AsyncGenerator[httpx.AsyncClient, None]:
    """Async HTTPX client with ASGI transport."""
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://testclient",
        headers=auth_headers,
        timeout=30.0,
    ) as ac:
        yield ac


# ============================================================================
# Helper
# ============================================================================

def _make_mock_llm(narrator_response: str, scribe_response: str):
    """Create a mock LLM with AsyncMock for ainvoke."""
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


# ============================================================================
# Multi-Chapter Tests
# ============================================================================

@pytest.mark.asyncio
async def test_chat_with_multi_chapter(client: httpx.AsyncClient) -> None:
    """验证 total_chapters 参数可以创作多章节小说."""
    from ai_agent.agents import novel_agent
    from ai_agent.agents.novel_agent import novel_graph

    thread_id = "test-multi-chapter"
    mock_llm = _make_mock_llm(NARRATOR_RESPONSE, SCRIBE_RESPONSE)
    session_key = f"{TEST_USER_ID}:{thread_id}"
    config = {"configurable": {"thread_id": session_key, "user_id": TEST_USER_ID}}

    with patch.object(novel_agent, "get_llm", return_value=mock_llm):
        # 创建多章节创作
        async with client.stream(
            "POST",
            "/api/chat",
            json={
                "user_id": TEST_USER_ID,
                "thread_id": thread_id,
                "message": "我要写一个仙侠小说",
                "genre": "仙侠",
                "total_chapters": 3,
            },
        ) as resp:
            await resp.aclose()

    # 验证状态
    state = novel_graph.get_state(config)
    assert state is not None
    # 章节1已触发HITL，current_chapter仍为1
    assert state.values.get("current_chapter") == 1
    assert state.values.get("total_chapters") == 3
    assert state.values.get("outline") is not None


@pytest.mark.asyncio
async def test_resume_accept_triggers_next_chapter(client: httpx.AsyncClient) -> None:
    """验证 accept 第1章后自动进入第2章."""
    from ai_agent.agents import novel_agent
    from ai_agent.agents.novel_agent import novel_graph

    thread_id = "test-chapter-flow"
    mock_llm = _make_mock_llm(NARRATOR_RESPONSE, SCRIBE_RESPONSE)
    session_key = f"{TEST_USER_ID}:{thread_id}"
    config = {"configurable": {"thread_id": session_key, "user_id": TEST_USER_ID}}

    with patch.object(novel_agent, "get_llm", return_value=mock_llm):
        # 触发第1章中断
        async with client.stream(
            "POST",
            "/api/chat",
            json={
                "user_id": TEST_USER_ID,
                "thread_id": thread_id,
                "message": "我要写一个仙侠小说",
                "genre": "仙侠",
                "total_chapters": 2,
            },
        ) as resp:
            await resp.aclose()

        # Accept 第1章
        resp2 = await client.post(
            "/api/resume",
            json={
                "user_id": TEST_USER_ID,
                "thread_id": thread_id,
                "choice": "accept",
                "instruction": None,
            },
        )
        assert resp2.status_code == 200

    # 验证进入了第2章
    state_after = novel_graph.get_state(config)
    assert state_after.values.get("current_chapter") == 2
    assert state_after.values.get("phase") == "writing"


# ============================================================================
# Export Tests
# ============================================================================

@pytest.mark.asyncio
async def test_export_requires_completed_chapters(client: httpx.AsyncClient) -> None:
    """导出需要已完成章节，无章节时返回400."""
    thread_id = "test-export-empty"

    # 先创建会话
    await client.post(
        "/api/session",
        json={"user_id": TEST_USER_ID},
    )

    resp = await client.post(
        "/api/export",
        json={
            "thread_id": thread_id,
            "title": "测试小说",
        },
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_export_requires_auth(client: httpx.AsyncClient, app) -> None:
    """导出需要认证，无token返回401."""
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://testclient",
        timeout=30.0,
    ) as ac:
        resp = await ac.post(
            "/api/export",
            json={
                "thread_id": "any-thread",
                "title": "测试",
            },
        )
    assert resp.status_code == 401


# ============================================================================
# Session Management Tests
# ============================================================================

@pytest.mark.asyncio
async def test_list_sessions_returns_user_sessions(client: httpx.AsyncClient) -> None:
    """列出该用户的所有会话."""
    # 创建几个会话
    await client.post("/api/session")
    await client.post("/api/session")

    response = await client.get("/api/sessions")
    assert response.status_code == 200
    data = response.json()
    assert "sessions" in data
    assert isinstance(data["sessions"], list)


@pytest.mark.asyncio
async def test_list_sessions_requires_auth(client: httpx.AsyncClient, app) -> None:
    """列出会话需要认证."""
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://testclient",
        timeout=30.0,
    ) as ac:
        response = await ac.get("/api/sessions")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_get_session_returns_details(client: httpx.AsyncClient) -> None:
    """获取指定会话详情."""
    from ai_agent.agents import novel_agent
    from ai_agent.agents.novel_agent import novel_graph

    thread_id = "test-get-session"
    mock_llm = _make_mock_llm(NARRATOR_RESPONSE, SCRIBE_RESPONSE)
    session_key = f"{TEST_USER_ID}:{thread_id}"
    config = {"configurable": {"thread_id": session_key, "user_id": TEST_USER_ID}}

    with patch.object(novel_agent, "get_llm", return_value=mock_llm):
        # 创建会话并生成大纲
        async with client.stream(
            "POST",
            "/api/chat",
            json={
                "user_id": TEST_USER_ID,
                "thread_id": thread_id,
                "message": "我要写一个仙侠小说",
                "genre": "仙侠",
                "total_chapters": 1,
            },
        ) as resp:
            await resp.aclose()

    # 获取会话详情
    response = await client.get(f"/api/sessions/{thread_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["thread_id"] == thread_id
    assert data["user_id"] == TEST_USER_ID
    assert data["phase"] == "planning"
    assert data["current_chapter"] == 1
    assert data["total_chapters"] == 1


@pytest.mark.asyncio
@pytest.mark.skip(reason="MemorySaver test isolation issue - skip for now")
async def test_get_nonexistent_session_returns_404(client: httpx.AsyncClient) -> None:
    """获取不存在的会话返回404.

    注意：由于 MemorySaver 是进程级的，不同测试之间可能共享状态。
    此测试验证在当前会话上下文中不存在的 thread_id 返回404。
    """
    # 使用一个极不可能存在的 thread_id
    fake_thread_id = "this-thread-definitely-does-not-exist-12345"
    response = await client.get(f"/api/sessions/{fake_thread_id}")
    assert response.status_code == 404


# ============================================================================
# Outline Edit Tests
# ============================================================================

@pytest.mark.asyncio
async def test_update_outline_modifies_state(client: httpx.AsyncClient) -> None:
    """验证大纲更新可以修改状态."""
    from ai_agent.agents import novel_agent
    from ai_agent.agents.novel_agent import novel_graph

    thread_id = "test-outline-edit"
    mock_llm = _make_mock_llm(NARRATOR_RESPONSE, SCRIBE_RESPONSE)
    session_key = f"{TEST_USER_ID}:{thread_id}"
    config = {"configurable": {"thread_id": session_key, "user_id": TEST_USER_ID}}

    with patch.object(novel_agent, "get_llm", return_value=mock_llm):
        # 创建会话
        async with client.stream(
            "POST",
            "/api/chat",
            json={
                "user_id": TEST_USER_ID,
                "thread_id": thread_id,
                "message": "我要写一个仙侠小说",
                "genre": "仙侠",
                "total_chapters": 1,
            },
        ) as resp:
            await resp.aclose()

    # 更新大纲
    new_outline = {
        "act1": {"name": "第一幕", "summary": "修改后的大纲"},
    }
    response = await client.put(
        "/api/outline",
        json={
            "outline": new_outline,
            "characters": {"protagonist": {"name": "新角色"}},
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["outline"] == new_outline
    assert data["phase"] == "planning"


@pytest.mark.asyncio
async def test_update_outline_requires_auth(client: httpx.AsyncClient, app) -> None:
    """大纲更新需要认证."""
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://testclient",
        timeout=30.0,
    ) as ac:
        response = await ac.put(
            "/api/outline",
            json={
                "outline": {"act1": {}},
            },
        )
    assert response.status_code == 401
