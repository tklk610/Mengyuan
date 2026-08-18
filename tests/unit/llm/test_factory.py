"""Unit tests for LLM factory"""
from __future__ import annotations

from unittest.mock import patch

import pytest

from ai_agent.llm.factory import get_llm


def test_get_llm_minimax():
    """Test getting LLM with minimax provider"""
    with patch("ai_agent.llm.factory.settings") as mock_settings:
        mock_settings.llm_provider = "minimax"
        mock_settings.minimax_api_key = "test-key"
        mock_settings.minimax_model = "MiniMax-Text-01"
        mock_settings.llm_temperature = 0.7
        mock_settings.llm_max_tokens = 4096
        mock_settings.llm_timeout_seconds = 120

        llm = get_llm(provider="minimax")

        assert llm is not None
        assert hasattr(llm, "model_name") or hasattr(llm, "model")


def test_get_llm_openai():
    """Test getting LLM with openai provider"""
    with patch("ai_agent.llm.factory.settings") as mock_settings:
        mock_settings.llm_provider = "openai"
        mock_settings.openai_api_key = "test-key"
        mock_settings.openai_model = "gpt-4o-mini"
        mock_settings.llm_temperature = 0.7
        mock_settings.llm_max_tokens = 4096
        mock_settings.llm_timeout_seconds = 120

        llm = get_llm(provider="openai")

        assert llm is not None


def test_get_llm_anthropic():
    """Test getting LLM with anthropic provider"""
    with patch("ai_agent.llm.factory.settings") as mock_settings:
        mock_settings.llm_provider = "anthropic"
        mock_settings.anthropic_api_key = "test-key"
        mock_settings.anthropic_model = "claude-3-5-sonnet-latest"
        mock_settings.llm_temperature = 0.7
        mock_settings.llm_max_tokens = 4096
        mock_settings.llm_timeout_seconds = 120

        llm = get_llm(provider="anthropic")

        assert llm is not None


def test_get_llm_custom_params():
    """Test getting LLM with custom parameters"""
    with patch("ai_agent.llm.factory.settings") as mock_settings:
        mock_settings.llm_provider = "openai"
        mock_settings.llm_temperature = 0.7
        mock_settings.llm_max_tokens = 4096
        mock_settings.llm_timeout_seconds = 120

        llm = get_llm(
            provider="openai",
            model="gpt-4o",
            temperature=0.5,
            max_tokens=2000,
        )

        assert llm is not None


def test_get_llm_unsupported_provider():
    """Test getting LLM with unsupported provider raises error"""
    with pytest.raises(ValueError, match="Unsupported LLM provider"):
        get_llm(provider="unsupported")
