"""Unit tests for chat schemas"""
from __future__ import annotations

from ai_agent.schemas.chat import ChatRequest, ResumeRequest, SessionCreateResponse

_USER_ID = "test-user-123"


def test_chat_request_defaults():
    """Test ChatRequest default values"""
    request = ChatRequest(
        user_id=_USER_ID,
        thread_id="test-thread",
        message="测试消息",
    )

    assert request.user_id == _USER_ID
    assert request.thread_id == "test-thread"
    assert request.message == "测试消息"
    assert request.genre == "仙侠"  # default


def test_chat_request_all_genres():
    """Test ChatRequest with all genre options"""
    genres = ["仙侠", "修仙", "奇幻", "悬疑", "言情", "科幻"]

    for genre in genres:
        request = ChatRequest(
            user_id=_USER_ID,
            thread_id="test",
            message="test",
            genre=genre,
        )
        assert request.genre == genre


def test_resume_request_choices():
    """Test ResumeRequest with different choices"""
    choices = ["accept", "rewrite", "restart"]

    for choice in choices:
        request = ResumeRequest(
            user_id=_USER_ID,
            thread_id="test",
            choice=choice,
        )
        assert request.choice == choice


def test_session_create_response():
    """Test SessionCreateResponse"""
    response = SessionCreateResponse(
        user_id=_USER_ID,
        thread_id="new-thread-id",
        status="created",
    )

    assert response.user_id == _USER_ID
    assert response.thread_id == "new-thread-id"
    assert response.status == "created"
