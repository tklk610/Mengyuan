"""Unit tests conftest — mock external LLM packages at collection time."""

from __future__ import annotations

import sys
from unittest.mock import MagicMock

# Mock ONLY the LLM client packages (not langchain_core itself).
# Mocking langchain_core breaks langgraph's ability to import RunnableConfig.
for mod_name in (
    "langchain_anthropic",
    "langchain_openai",
):
    if mod_name not in sys.modules:
        mock_module = MagicMock()
        mock_module.ChatAnthropic = MagicMock()
        mock_module.ChatOpenAI = MagicMock()
        sys.modules[mod_name] = mock_module
