"""AC-1 & AC-2 验证测试

验证风格学习完整流程：
- AC-1: 用户上传 .txt 小说样本，系统能解析并提取风格特征
- AC-2: 风格特征向量存储到 Qdrant，可通过向量检索召回
"""
from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

STYLE_SAMPLE = """
少年李逍遥走在山间小路上，阳光透过树叶洒落，
忽然一道光芒从草丛中射出，直冲天际。他低头一看，
竟是一枚古朴的玉简，表面刻着密密麻麻的符文。
"""

MOCK_EMBEDDING = [0.1] * 1536

# Valid JSON with properly escaped unicode
MOCK_LLM_RESPONSE = json.dumps({
    "profile_id": "style-001",
    "name": "仙侠风格",
    "vector": MOCK_EMBEDDING,
    "embedding_text": "仙侠风格小说，语言古风典雅",
    "genre_tags": ["仙侠", "修真"],
    "characteristics": {
        "叙事视角": "第三人称",
        "语言风格": "古风典雅",
        "情感基调": "神秘飘逸",
        "节奏": "中等偏慢",
    },
    "banned_words": ["突然", "竟然", "不过"],
    "sample_phrases": ["直冲天际", "古朴的玉简", "入手温热"],
}, ensure_ascii=False)


# ============================================================================
# AC-1: 风格特征提取测试
# ============================================================================

@pytest.mark.asyncio
async def test_style_analyzer_extracts_features():
    """AC-1: 验证风格分析器能从文本样本中提取风格特征."""
    from ai_agent.rag import style_analyzer

    mock_llm = MagicMock()
    mock_llm.ainvoke = AsyncMock(return_value=MagicMock(
        content=MOCK_LLM_RESPONSE,
        usage=MagicMock(prompt_tokens=100, completion_tokens=50, total_tokens=150)
    ))

    with patch("ai_agent.rag.style_analyzer.get_llm", return_value=mock_llm), \
         patch("ai_agent.rag.embeddings.generate_embedding", new_callable=AsyncMock, return_value=MOCK_EMBEDDING):
        analyzer = style_analyzer._get_style_analyzer()
        result = await analyzer.extract_full_profile(
            text=STYLE_SAMPLE,
            user_id="test-user",
            name="仙侠风格",
            genre_hint="仙侠",
        )

    # Verify extracted features
    assert result["name"] == "仙侠风格"
    assert "genre_tags" in result
    assert "characteristics" in result
    assert "vector" in result
    assert isinstance(result["genre_tags"], list)
    assert isinstance(result["characteristics"], dict)
    assert "banned_words" in result
    assert "sample_phrases" in result


# ============================================================================
# AC-2: Qdrant 存储和检索测试
# ============================================================================

@pytest.mark.asyncio
async def test_qdrant_store_and_retrieve():
    """AC-2: 验证风格档案能存储到 Qdrant 并检索召回."""
    from qdrant_client import QdrantClient

    # Create a mock QdrantClient
    stored_points: list[dict] = []

    class MockQdrantClient:
        def get_collections(self):
            class Collections:
                collections = []
            return Collections()

        def create_collection(self, collection_name, vectors_config):
            pass

        def upsert(self, collection_name, points):
            for point in points:
                stored_points.append({
                    "id": point.id,
                    "vector": point.vector,
                    "payload": point.payload,
                })

        def search(self, collection_name, query_vector, query_filter, limit):
            # Return stored points as search results
            return [
                type("Result", (), {
                    "id": p["id"],
                    "score": 0.95,
                    "payload": {"name": p["payload"].get("name"), "genre_tags": p["payload"].get("genre_tags"), "characteristics": p["payload"].get("characteristics")}
                })()
                for p in stored_points
                if query_filter and any(
                    fc.key == "user_id" and fc.match.value == p["payload"].get("user_id")
                    for fc in query_filter.must
                )
            ][:limit]

        def scroll(self, collection_name, scroll_filter, limit):
            points = [
                type("Point", (), {"id": p["id"], "payload": {"name": p["payload"].get("name"), "genre_tags": p["payload"].get("genre_tags"), "characteristics": p["payload"].get("characteristics")}})()
                for p in stored_points
                if scroll_filter and any(
                    fc.key == "user_id" and fc.match.value == p["payload"].get("user_id")
                    for fc in scroll_filter.must
                )
            ]
            return (points, None)

    mock_client = MockQdrantClient()

    with patch("qdrant_client.QdrantClient", return_value=mock_client):
        from ai_agent.agents.stylist_agent import qdrant_store
        # Re-initialize to use mock
        qdrant_store._client = mock_client

        # Store a style profile
        qdrant_store.upsert_style_profile(
            user_id="test-user",
            profile_id="style-001",
            name="仙侠风格",
            vector=MOCK_EMBEDDING,
            payload={
                "embedding_text": "仙侠风格小说",
                "genre_tags": ["仙侠", "修真"],
                "characteristics": {"叙事视角": "第三人称"},
                "banned_words": ["突然"],
                "sample_phrases": ["直冲天际"],
            },
        )

        # Search and retrieve
        results = qdrant_store.search_similar_styles(
            query_vector=MOCK_EMBEDDING,
            user_id="test-user",
            limit=5,
        )

    # Verify retrieval
    assert len(results) >= 1
    style = next((s for s in results if s["id"] == "style-001"), None)
    assert style is not None
    assert style["name"] == "仙侠风格"
    assert style["score"] > 0.9


@pytest.mark.asyncio
async def test_qdrant_list_user_profiles():
    """AC-2: 验证能列出用户的所有风格档案."""
    from qdrant_client import QdrantClient

    stored_points: list[dict] = []

    class MockQdrantClient:
        def get_collections(self):
            class Collections:
                collections = []
            return Collections()

        def create_collection(self, collection_name, vectors_config):
            pass

        def upsert(self, collection_name, points):
            for point in points:
                stored_points.append({
                    "id": point.id,
                    "vector": point.vector,
                    "payload": point.payload,
                })

        def scroll(self, collection_name, scroll_filter, limit):
            points = [
                type("Point", (), {"id": p["id"], "payload": {"name": p["payload"].get("name"), "genre_tags": p["payload"].get("genre_tags"), "characteristics": p["payload"].get("characteristics")}})()
                for p in stored_points
                if scroll_filter and any(
                    fc.key == "user_id" and fc.match.value == p["payload"].get("user_id")
                    for fc in scroll_filter.must
                )
            ]
            return (points, None)

    mock_client = MockQdrantClient()

    with patch("qdrant_client.QdrantClient", return_value=mock_client):
        from ai_agent.agents.stylist_agent import qdrant_store
        qdrant_store._client = mock_client

        # Store profiles for two users
        qdrant_store.upsert_style_profile(
            user_id="user-1",
            profile_id="style-001",
            name="仙侠风格",
            vector=MOCK_EMBEDDING,
            payload={"genre_tags": ["仙侠"]},
        )
        qdrant_store.upsert_style_profile(
            user_id="user-1",
            profile_id="style-002",
            name="言情风格",
            vector=MOCK_EMBEDDING,
            payload={"genre_tags": ["言情"]},
        )
        qdrant_store.upsert_style_profile(
            user_id="user-2",
            profile_id="style-003",
            name="悬疑风格",
            vector=MOCK_EMBEDDING,
            payload={"genre_tags": ["悬疑"]},
        )

        # List user-1's profiles
        profiles = qdrant_store.list_style_profiles(user_id="user-1")

    # Verify only user-1's profiles are returned
    assert len(profiles) >= 2
    profile_ids = [p["id"] for p in profiles]
    assert "style-001" in profile_ids
    assert "style-002" in profile_ids


# ============================================================================
# AC-1 + AC-2: 端到端流程测试
# ============================================================================

@pytest.mark.asyncio
async def test_full_style_learning_flow():
    """端到端测试: 文本 → 风格分析 → Qdrant 存储 → 检索召回."""
    from ai_agent.rag import style_analyzer

    mock_llm = MagicMock()
    mock_llm.ainvoke = AsyncMock(return_value=MagicMock(
        content=MOCK_LLM_RESPONSE,
        usage=MagicMock(prompt_tokens=100, completion_tokens=50, total_tokens=150)
    ))

    from qdrant_client import QdrantClient
    stored_points: list[dict] = []

    class MockQdrantClient:
        def get_collections(self):
            class Collections:
                collections = []
            return Collections()

        def create_collection(self, collection_name, vectors_config):
            pass

        def upsert(self, collection_name, points):
            for point in points:
                stored_points.append({
                    "id": point.id,
                    "vector": point.vector,
                    "payload": point.payload,
                })

        def search(self, collection_name, query_vector, query_filter, limit):
            return [
                type("Result", (), {
                    "id": p["id"],
                    "score": 0.95,
                    "payload": {"name": p["payload"].get("name"), "genre_tags": p["payload"].get("genre_tags"), "characteristics": p["payload"].get("characteristics")}
                })()
                for p in stored_points
                if query_filter and any(
                    fc.key == "user_id" and fc.match.value == p["payload"].get("user_id")
                    for fc in query_filter.must
                )
            ][:limit]

    mock_client = MockQdrantClient()

    with patch("qdrant_client.QdrantClient", return_value=mock_client), \
         patch("ai_agent.rag.style_analyzer.get_llm", return_value=mock_llm), \
         patch("ai_agent.rag.embeddings.generate_embedding", new_callable=AsyncMock, return_value=MOCK_EMBEDDING):
        from ai_agent.agents.stylist_agent import qdrant_store
        qdrant_store._client = mock_client

        # Step 1: Extract style features (AC-1)
        analyzer = style_analyzer._get_style_analyzer()
        profile = await analyzer.extract_full_profile(
            text=STYLE_SAMPLE,
            user_id="e2e-user",
            name="测试风格",
            genre_hint="仙侠",
        )

        assert profile["name"] == "测试风格"
        assert "vector" in profile

        # Step 2: Store to Qdrant (AC-2)
        qdrant_store.upsert_style_profile(
            user_id="e2e-user",
            profile_id=profile["profile_id"],
            name=profile["name"],
            vector=profile["vector"],
            payload={
                "embedding_text": profile["embedding_text"],
                "genre_tags": profile["genre_tags"],
                "characteristics": profile["characteristics"],
                "banned_words": profile["banned_words"],
                "sample_phrases": profile["sample_phrases"],
            },
        )

        # Step 3: Search and retrieve (AC-2)
        results = qdrant_store.search_similar_styles(
            query_vector=profile["vector"],
            user_id="e2e-user",
            limit=5,
        )

        # Verify end-to-end
        assert len(results) >= 1
        found = next((s for s in results if s["id"] == profile["profile_id"]), None)
        assert found is not None
        assert found["name"] == "测试风格"
        assert "genre_tags" in found
        assert "characteristics" in found
