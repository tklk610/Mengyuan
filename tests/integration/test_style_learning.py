"""T09: 风格学习集成测试

测试 Phase 2 风格学习全流程：
  1. POST /api/styles → 创建风格档案（mock LLM）
  2. GET /api/styles → 列出用户风格档案
  3. POST /api/styles/search → 搜索相似风格（mock LLM）
  4. GET /api/preferences → 获取用户偏好
  5. PUT /api/preferences → 更新用户偏好
  6. Scribe Agent 创作时注入风格约束

依赖：
- Qdrant 服务（docker-compose up qdrant）
- LLM 调用被 Mock
"""
from __future__ import annotations

import json
from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from tests.conftest import NARRATOR_RESPONSE, SCRIBE_RESPONSE, TEST_USER_ID

# ============================================================================
# Test Data
# ============================================================================

STYLE_SAMPLE = """
少年李逍遥走在山间小路上，阳光透过树叶洒落，
忽然一道光芒从草丛中射出，直冲天际。他低头一看，
竟是一枚古朴的玉简，表面刻着密密麻麻的符文。
这玉简入手温热，仿佛有生命一般...
"""

MOCK_STYLE_PROFILES = [
    {
        "id": "mock-style-001",
        "name": "仙侠风格",
        "genre_tags": ["仙侠", "修真"],
        "characteristics": {"叙事视角": "第三人称", "语言风格": "古风典雅"},
        "banned_words": ["突然", "竟然"],
        "sample_phrases": ["直冲天际", "古朴的玉简"],
    }
]


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
# Style Profile Tests
# ============================================================================

@pytest.mark.asyncio
async def test_create_style_profile(client: httpx.AsyncClient) -> None:
    """POST /api/styles → 创建风格档案，返回 profile_id（mock LLM）."""
    from ai_agent.agents import stylist_agent as stylist_mod

    mock_profile = {
        "profile_id": "new-style-001",
        "name": "仙侠风格",
        "genre_tags": ["仙侠"],
        "characteristics": {"叙事视角": "第三人称"},
        "banned_words": [],
        "sample_phrases": [],
    }

    async def mock_create(*args, **kwargs):
        return mock_profile

    # Replace _get_stylist_agent to return a mock that doesn't init LLM
    original_getter = stylist_mod._get_stylist_agent
    mock_instance = MagicMock()
    mock_instance.create_style_profile = mock_create
    stylist_mod._get_stylist_agent = lambda: mock_instance
    try:
        response = await client.post(
            "/api/styles",
            json={
                "name": "仙侠风格",
                "text_sample": STYLE_SAMPLE,
                "genre_hint": "仙侠",
            },
        )
    finally:
        stylist_mod._get_stylist_agent = original_getter
    assert response.status_code == 200, response.text
    data = response.json()
    assert "profile_id" in data
    assert data["name"] == "仙侠风格"


@pytest.mark.asyncio
async def test_list_style_profiles(client: httpx.AsyncClient) -> None:
    """GET /api/styles → 列出用户所有风格档案."""
    from ai_agent.agents import stylist_agent as stylist_mod
    # Patch the _LazyStylistAgent instance directly
    mock_stylist = MagicMock()
    mock_stylist.list_user_styles = AsyncMock(return_value=MOCK_STYLE_PROFILES)
    original = stylist_mod.stylist_agent
    stylist_mod.stylist_agent = mock_stylist
    try:
        response = await client.get("/api/styles")
    finally:
        stylist_mod.stylist_agent = original
    assert response.status_code == 200, response.text
    data = response.json()
    assert isinstance(data, list)
    assert len(data) >= 1
    assert all("profile_id" in item for item in data)
    assert all("name" in item for item in data)


@pytest.mark.asyncio
async def test_search_similar_styles(client: httpx.AsyncClient) -> None:
    """POST /api/styles/search → 根据文本样本搜索相似风格（mock embedding）."""
    from ai_agent.agents import stylist_agent as stylist_mod
    mock_stylist = MagicMock()
    mock_stylist.find_similar_styles = AsyncMock(return_value=MOCK_STYLE_PROFILES)
    original = stylist_mod.stylist_agent
    stylist_mod.stylist_agent = mock_stylist
    try:
        with patch("ai_agent.rag.embeddings.generate_embedding", new_callable=AsyncMock) as mock_emb:
            mock_emb.return_value = [0.1] * 1536
            response = await client.post(
                "/api/styles/search",
                json={"text_sample": "少年行走在山谷之间，忽然天降异象"},
            )
    finally:
        stylist_mod.stylist_agent = original
    assert response.status_code == 200, response.text
    data = response.json()
    assert "styles" in data
    assert isinstance(data["styles"], list)


@pytest.mark.asyncio
async def test_create_style_profile_requires_auth(client: httpx.AsyncClient, app) -> None:
    """POST /api/styles 无 token 时返回 401."""
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://testclient",
        timeout=30.0,
    ) as ac:
        response = await ac.post(
            "/api/styles",
            json={"name": "test", "text_sample": STYLE_SAMPLE},
        )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_list_styles_requires_auth(client: httpx.AsyncClient, app) -> None:
    """GET /api/styles 无 token 时返回 401."""
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://testclient",
        timeout=30.0,
    ) as ac:
        response = await ac.get("/api/styles")
    assert response.status_code == 401


# ============================================================================
# User Preferences Tests
# ============================================================================

@pytest.mark.asyncio
async def test_get_preferences(client: httpx.AsyncClient) -> None:
    """GET /api/preferences → 返回用户默认偏好."""
    response = await client.get("/api/preferences")
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["user_id"] == TEST_USER_ID
    assert "narrative_pov" in data
    assert "target_word_count" in data
    assert "ending_preference" in data


@pytest.mark.asyncio
async def test_update_preferences(client: httpx.AsyncClient) -> None:
    """PUT /api/preferences → 更新用户偏好."""
    update_data = {
        "narrative_pov": "第一人称",
        "target_word_count": 5000,
        "ending_preference": "BE",
        "pacing_preference": "快节奏",
        "avoid_elements": ["死亡", "悲剧结局"],
        "preferred_tones": ["紧张", "悬疑"],
    }
    response = await client.put("/api/preferences", json=update_data)
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["narrative_pov"] == "第一人称"
    assert data["target_word_count"] == 5000
    assert data["ending_preference"] == "BE"
    assert data["avoid_elements"] == ["死亡", "悲剧结局"]


@pytest.mark.asyncio
async def test_preferences_persist_after_update(client: httpx.AsyncClient) -> None:
    """PUT 后 GET 能读到更新后的值."""
    await client.put(
        "/api/preferences",
        json={"narrative_pov": "第二人称", "target_word_count": 3500},
    )
    response = await client.get("/api/preferences")
    data = response.json()
    assert data["narrative_pov"] == "第二人称"
    assert data["target_word_count"] == 3500


@pytest.mark.asyncio
async def test_update_preferences_requires_auth(client: httpx.AsyncClient, app) -> None:
    """PUT /api/preferences 无 token 时返回 401."""
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://testclient",
        timeout=30.0,
    ) as ac:
        response = await ac.put(
            "/api/preferences",
            json={"narrative_pov": "第一人称"},
        )
    assert response.status_code == 401


# ============================================================================
# Scribe Agent Style Constraints Integration Test
# ============================================================================

@pytest.mark.skip(reason="New architecture changes call flow - needs update")
@pytest.mark.asyncio
async def test_scribe_node_receives_style_constraints(client: httpx.AsyncClient) -> None:
    """验证 Scribe Agent 创作时注入了风格约束."""
    from ai_agent.agents import novel_agent as na
    from ai_agent.agents.novel_agent import novel_graph

    thread_id = "test-style-constraints"
    captured_prompts: list[str] = []
    call_count = 0

    async def mock_ainvoke(prompt: str) -> MagicMock:
        nonlocal call_count
        call_count += 1
        captured_prompts.append(prompt)
        content = NARRATOR_RESPONSE if call_count == 1 else SCRIBE_RESPONSE
        result = MagicMock()
        result.content = content
        result.usage = MagicMock(prompt_tokens=10, completion_tokens=10, total_tokens=20)
        return result

    mock_llm = MagicMock()
    mock_llm.ainvoke = AsyncMock(side_effect=mock_ainvoke)

    mock_profile = {
        "profile_id": "mock-style-001",
        "name": "测试风格",
        "characteristics": {"叙事视角": "第三人称", "语言风格": "古风典雅"},
        "banned_words": ["突然", "竟然"],
        "sample_phrases": ["光芒从草丛中射出"],
    }

    with patch.object(na, "get_llm", return_value=mock_llm):
        initial_state = {
            "messages": [{"role": "user", "content": "我要写仙侠小说"}],
            "user_request": "我要写仙侠小说",
            "genre": "仙侠",
            "outline": None,
            "characters": None,
            "current_chapter": 1,
            "draft": None,
            "phase": "idle",
            "interrupt_type": None,
            "interrupt_options": None,
            "user_choice": None,
            "error": None,
            "style_profile": mock_profile,
        }

        async for event in novel_graph.astream_events(
            initial_state,
            config={"configurable": {"thread_id": f"{TEST_USER_ID}:{thread_id}", "user_id": TEST_USER_ID}},
            stream_mode="values",
        ):
            pass

    # narrator is call 1, scribe is call 2
    assert len(captured_prompts) >= 2, f"Expected at least 2 LLM calls, got {len(captured_prompts)}"
    scribe_prompt = captured_prompts[1]
    # Verify style constraints are in the prompt
    has_constraints = "风格约束" in scribe_prompt or "叙事视角" in scribe_prompt or "古风典雅" in scribe_prompt
    assert has_constraints, f"Style constraints not found in scribe prompt. Prompt excerpt: {scribe_prompt[:500]}"


@pytest.mark.asyncio
async def test_scribe_node_without_style_profile_still_works(client: httpx.AsyncClient) -> None:
    """无风格档案时，Scribe Agent 仍能正常生成草稿（向后兼容）."""
    from ai_agent.agents import novel_agent
    from ai_agent.agents.novel_agent import novel_graph

    thread_id = "test-no-style"
    mock_llm = _make_mock_llm(NARRATOR_RESPONSE, SCRIBE_RESPONSE)
    session_key = f"{TEST_USER_ID}:{thread_id}"
    config = {"configurable": {"thread_id": session_key, "user_id": TEST_USER_ID}}

    with patch.object(novel_agent, "get_llm", return_value=mock_llm):
        initial_state = {
            "messages": [{"role": "user", "content": "我要写仙侠小说"}],
            "user_request": "我要写仙侠小说",
            "genre": "仙侠",
            "outline": None,
            "characters": None,
            "current_chapter": 1,
            "draft": None,
            "phase": "idle",
            "interrupt_type": None,
            "interrupt_options": None,
            "user_choice": None,
            "error": None,
        }

        async for event in novel_graph.astream_events(
            initial_state, config=config, stream_mode="values"
        ):
            pass

    state = novel_graph.get_state(config)
    assert state is not None
    assert state.values.get("outline") is not None


# ============================================================================
# Helper
# ============================================================================

def _make_mock_llm(narrator_response: str, scribe_response: str):
    """Mock LLM using call order (deterministic: intent→planner→narrator→scribe)."""
    INTENT_RESPONSE = '{"intent": "new_story", "confidence": 0.9, "reasoning": "用户请求创作新故事"}'
    PLANNER_RESPONSE = json.dumps({
        "tasks": [
            {"task_id": "task-1", "type": "world_building", "description": "构建世界观", "dependencies": [], "estimated_words": 500},
            {"task_id": "task-2", "type": "chapter_write", "description": "创作第一章", "dependencies": ["task-1"], "estimated_words": 3000},
        ],
        "estimated_total_words": 3000,
        "estimated_chapters": 1,
        "story_arc": "少年修仙奇遇"
    })

    call_count = [0]

    async def mock_ainvoke(prompt: str) -> MagicMock:
        result = MagicMock()
        result.usage = MagicMock(prompt_tokens=10, completion_tokens=10, total_tokens=20)
        call_count[0] += 1

        if call_count[0] == 1:
            result.content = INTENT_RESPONSE
        elif call_count[0] == 2:
            result.content = PLANNER_RESPONSE
        elif call_count[0] == 3:
            result.content = narrator_response
        else:
            result.content = scribe_response

        return result

    llm = MagicMock()
    llm.ainvoke = AsyncMock(side_effect=mock_ainvoke)
    return llm
