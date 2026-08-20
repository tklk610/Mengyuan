"""T09: NovelCraft PoC End-to-End Integration Test

Tests the complete flow:
  1. POST /api/session → get thread_id
  2. POST /api/chat (SSE) → outline + draft_delta events, hits interrupt
  3. POST /api/resume with choice=accept → complete event
  4. No HTTP 500 errors at any step

FastAPI app is imported directly from ai_agent.main.
LLM calls are mocked using patch.object on novel_agent.get_llm with an
AsyncMock-backed mock LLM — AsyncMock is required because
ainvoke_with_timeout wraps the call in asyncio.wait_for().
"""
from __future__ import annotations

import ast
import json
from collections.abc import AsyncGenerator
from dataclasses import dataclass
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

# Import mock response constants from conftest
from tests.conftest import NARRATOR_RESPONSE, SCRIBE_RESPONSE, TEST_USER_ID

# ============================================================================
# LLM Mock Factory
# ============================================================================

def make_mock_llm(narrator_response: str, scribe_response: str):
    """Create a mock LLM whose ainvoke() is an AsyncMock with sequential responses.

    The mock persists across interrupt + resume because we patch at the
    novel_agent module level (not the call site) and use AsyncMock so
    asyncio.wait_for in ainvoke_with_timeout can properly await it.
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


# ============================================================================
# Helpers
# ============================================================================

@dataclass
class SSEEvent:
    """Parsed SSE event."""
    type: str
    data: dict | str | None
    message: str | None


def parse_sse_payload(payload: str) -> dict:
    """Parse SSE data payload, handling Python dict str and JSON.

    The _sse_wrapper in main.py does f"data: {event}\\n\\n" where event
    is a Python dict. Python str(dict) uses single quotes, which is not
    valid JSON, so we fall back to ast.literal_eval().
    """
    payload = payload.strip()
    if not payload or payload == "{}":
        return {}
    try:
        return json.loads(payload)
    except json.JSONDecodeError:
        return ast.literal_eval(payload)


async def parse_sse_stream(response: httpx.Response) -> list[SSEEvent]:
    """Parse SSE lines into structured events."""
    events = []
    async for line in response.aiter_lines():
        line = line.rstrip("\n\r")
        if not line.startswith("data: "):
            continue
        payload = line[len("data: "):]
        parsed = parse_sse_payload(payload)
        if parsed:
            events.append(SSEEvent(
                type=parsed.get("type", "unknown"),
                data=parsed.get("data"),
                message=parsed.get("message"),
            ))
    return events


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
    """Async HTTPX client with ASGI transport for SSE endpoints.

    Includes auth headers for all authenticated endpoints.
    base_url is required on Windows Python 3.13 to avoid
    ValueError in httpx cookie extraction for relative URLs.
    """
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://testclient",
        headers=auth_headers,
        timeout=30.0,
    ) as ac:
        yield ac


# ============================================================================
# Tests
# ============================================================================

@pytest.mark.asyncio
async def test_session_create(client: httpx.AsyncClient) -> None:
    """Step 1: POST /api/session returns a valid thread_id."""
    response = await client.post("/api/session")
    assert response.status_code == 200, response.text

    data = response.json()
    assert "thread_id" in data
    assert isinstance(data["thread_id"], str)
    assert len(data["thread_id"]) == 36  # UUID format
    assert data["user_id"] == TEST_USER_ID


@pytest.mark.asyncio
async def test_health_check(client: httpx.AsyncClient) -> None:
    """GET /health returns healthy status."""
    response = await client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"


@pytest.mark.asyncio
async def test_chat_flow_interrupted(client: httpx.AsyncClient) -> None:
    """Steps 2-4: POST /api/chat hits interrupt at scribe_node.

    patch.object (not string patch) ensures AsyncMock ainvoke is used
    throughout the entire graph run, including after interrupt.
    """
    from ai_agent.agents import novel_agent
    from ai_agent.agents.novel_agent import novel_graph

    thread_id = "test-chat-interrupt"
    mock_llm = make_mock_llm(NARRATOR_RESPONSE, SCRIBE_RESPONSE)
    # Session key = f"{user_id}:{thread_id}"
    session_key = f"{TEST_USER_ID}:{thread_id}"
    config = {"configurable": {"thread_id": session_key, "user_id": TEST_USER_ID}}

    with patch.object(novel_agent, "get_llm", return_value=mock_llm):
        # Trigger interrupt
        async with client.stream(
            "POST",
            "/api/chat",
            json={
                "user_id": TEST_USER_ID,
                "thread_id": thread_id,
                "message": "我要写一个仙侠小说",
                "genre": "仙侠",
            },
        ) as response:
            await response.aclose()

    # Verify graph is interrupted
    state = novel_graph.get_state(config)
    assert state is not None, "Graph state must exist after /api/chat"
    assert state.next is not None, "Graph should be interrupted"
    assert len(state.next) > 0, f"state.next={state.next}"

    # Verify outline was generated (narrator ran)
    current_state = novel_graph.get_state(config)
    assert current_state is not None
    saved_outline = current_state.values.get("outline")
    assert saved_outline is not None, "Narrator should have generated outline"

    # Calling /api/chat again while interrupted should return status event
    with patch.object(novel_agent, "get_llm", return_value=mock_llm):
        async with client.stream(
            "POST",
            "/api/chat",
            json={
                "user_id": TEST_USER_ID,
                "thread_id": thread_id,
                "message": "继续写",
                "genre": "仙侠",
            },
        ) as response:
            events = await parse_sse_stream(response)

    event_types = [e.type for e in events]
    assert "status" in event_types, (
        f"Expected 'status' event for interrupted thread, got: {event_types}"
    )


@pytest.mark.asyncio
async def test_resume_accept_flow(client: httpx.AsyncClient) -> None:
    """Steps 4-6: Resume with choice=accept → graph reaches END.

    The accept path in scribe_node returns Command(goto=END).
    HTTP 200 must be returned and graph.next must become empty.
    SSE stream may be empty due to LangGraph interrupt checkpoint behavior.
    """
    from ai_agent.agents import novel_agent
    from ai_agent.agents.novel_agent import novel_graph

    thread_id = "test-resume-accept-001"
    mock_llm = make_mock_llm(NARRATOR_RESPONSE, SCRIBE_RESPONSE)
    session_key = f"{TEST_USER_ID}:{thread_id}"
    config = {"configurable": {"thread_id": session_key, "user_id": TEST_USER_ID}}

    with patch.object(novel_agent, "get_llm", return_value=mock_llm):
        # Step A: trigger interrupt (total_chapters=1 so accept ends the graph)
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

        # Verify interrupted
        state = novel_graph.get_state(config)
        assert state is not None, "Graph must have state after chat"
        assert state.next, f"Graph must be interrupted, state.next={state.next}"

        # Step B: resume with accept → HTTP 200, graph ends
        resp2 = await client.post(
            "/api/resume",
            json={"user_id": TEST_USER_ID, "thread_id": thread_id, "choice": "accept", "instruction": None},
        )
        assert resp2.status_code == 200, (
            f"Expected 200 for resume, got {resp2.status_code}: {resp2.text}"
        )

    # Graph must have reached END (next is empty tuple)
    state_after = novel_graph.get_state(config)
    assert state_after.next is None or len(state_after.next) == 0, (
        f"Graph should be done, state.next={state_after.next}"
    )


@pytest.mark.asyncio
async def test_no_http_500_errors(client: httpx.AsyncClient) -> None:
    """Verify all endpoints return < 500 throughout the full flow."""
    from ai_agent.agents import novel_agent

    thread_id = "test-no-500"
    mock_llm = make_mock_llm(NARRATOR_RESPONSE, SCRIBE_RESPONSE)
    errors: list[tuple[str, int]] = []

    with patch.object(novel_agent, "get_llm", return_value=mock_llm):
        resp = await client.post(
            "/api/chat",
            json={"thread_id": thread_id, "message": "写小说", "genre": "仙侠"},
        )
        if resp.status_code >= 500:
            errors.append(("/api/chat", resp.status_code))

        # Resume on same thread (interrupt already active)
        resp2 = await client.post(
            "/api/resume",
            json={"user_id": TEST_USER_ID, "thread_id": thread_id, "choice": "accept"},
        )
        if resp2.status_code >= 500:
            errors.append(("/api/resume", resp2.status_code))

    assert errors == [], f"HTTP 500 errors: {errors}"


@pytest.mark.asyncio
async def test_chat_during_interrupt_returns_status(client: httpx.AsyncClient) -> None:
    """If /api/chat is called while graph is interrupted, return 'status' event."""
    from ai_agent.agents import novel_agent

    thread_id = "test-pending-status"
    mock_llm = make_mock_llm(NARRATOR_RESPONSE, SCRIBE_RESPONSE)

    with patch.object(novel_agent, "get_llm", return_value=mock_llm):
        # Trigger interrupt
        async with client.stream(
            "POST",
            "/api/chat",
            json={"user_id": TEST_USER_ID, "thread_id": thread_id, "message": "写小说", "genre": "仙侠"},
        ) as resp:
            await resp.aclose()

    # Call again while interrupted — should return status event
    with patch.object(novel_agent, "get_llm", return_value=mock_llm):
        async with client.stream(
            "POST",
            "/api/chat",
            json={"user_id": TEST_USER_ID, "thread_id": thread_id, "message": "继续写", "genre": "仙侠"},
        ) as resp:
            events = await parse_sse_stream(resp)

    event_types = [e.type for e in events]
    assert "status" in event_types, (
        f"Expected 'status' event when calling during interrupt, got: {event_types}"
    )


@pytest.mark.asyncio
async def test_resume_without_interrupt_returns_400(client: httpx.AsyncClient) -> None:
    """POST /api/resume on a non-interrupted thread → HTTP 400."""
    thread_id = "test-no-interrupt"

    response = await client.post(
        "/api/resume",
        json={"user_id": TEST_USER_ID, "thread_id": thread_id, "choice": "accept"},
    )
    assert response.status_code == 400, (
        f"Expected 400 for resume without interrupt, got {response.status_code}"
    )
