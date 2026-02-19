"""Shared test fixtures."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from daccia.config import Settings
from daccia.llm.client import ClaudeClient


@pytest.fixture
def tmp_data_dir(tmp_path: Path) -> Path:
    """Create a temporary data directory structure."""
    (tmp_path / "style_profiles").mkdir()
    (tmp_path / "drafts").mkdir()
    (tmp_path / "published").mkdir()
    (tmp_path / "research_cache").mkdir()
    return tmp_path


@pytest.fixture
def settings(tmp_data_dir: Path) -> Settings:
    """Create test settings with temporary paths."""
    return Settings(
        anthropic_api_key="test-key-not-real",
        model="claude-sonnet-4-20250514",
        max_tokens=1024,
        temperature=0.7,
        db_path=tmp_data_dir / "test.db",
        style_profiles_dir=tmp_data_dir / "style_profiles",
        drafts_dir=tmp_data_dir / "drafts",
        published_dir=tmp_data_dir / "published",
        research_cache_dir=tmp_data_dir / "research_cache",
    )


@pytest.fixture
def mock_claude_client(settings: Settings) -> ClaudeClient:
    """Create a ClaudeClient with a mocked Anthropic SDK."""
    client = ClaudeClient(settings)
    # Replace the internal Anthropic client with a mock
    mock_anthropic = MagicMock()
    client._client = mock_anthropic
    return client


def make_mock_response(text: str, input_tokens: int = 100, output_tokens: int = 200):
    """Helper to create a mock Anthropic API response."""
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text=text)]
    mock_response.usage.input_tokens = input_tokens
    mock_response.usage.output_tokens = output_tokens
    return mock_response
