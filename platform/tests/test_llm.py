"""Tests for the LLM client wrapper."""

from __future__ import annotations

from daccia.llm.client import ClaudeClient
from daccia.llm.conversation import Conversation
from daccia.llm.prompts import render
from tests.conftest import make_mock_response


def test_generate_returns_text(mock_claude_client: ClaudeClient) -> None:
    """Test that generate() returns the text from Claude's response."""
    mock_claude_client._client.messages.create.return_value = make_mock_response(
        "Hello, this is a test response."
    )

    result = mock_claude_client.generate(
        system="You are a test assistant.",
        messages=[{"role": "user", "content": "Say hello"}],
    )

    assert result == "Hello, this is a test response."
    assert mock_claude_client._total_input_tokens == 100
    assert mock_claude_client._total_output_tokens == 200


def test_usage_summary_accumulates(mock_claude_client: ClaudeClient) -> None:
    """Test that token usage accumulates across calls."""
    mock_claude_client._client.messages.create.return_value = make_mock_response(
        "Response 1", input_tokens=50, output_tokens=100
    )
    mock_claude_client.generate(system="test", messages=[{"role": "user", "content": "1"}])

    mock_claude_client._client.messages.create.return_value = make_mock_response(
        "Response 2", input_tokens=75, output_tokens=150
    )
    mock_claude_client.generate(system="test", messages=[{"role": "user", "content": "2"}])

    summary = mock_claude_client.usage_summary
    assert summary["total_input_tokens"] == 125
    assert summary["total_output_tokens"] == 250


def test_conversation_multi_turn(mock_claude_client: ClaudeClient) -> None:
    """Test that Conversation manages multi-turn message history."""
    mock_claude_client._client.messages.create.return_value = make_mock_response(
        "Assistant reply 1"
    )

    conv = Conversation(
        client=mock_claude_client,
        system_prompt="You are helpful.",
    )

    reply1 = conv.send("Hello")
    assert reply1 == "Assistant reply 1"
    assert conv.turn_count == 1
    assert len(conv.messages) == 2  # user + assistant

    mock_claude_client._client.messages.create.return_value = make_mock_response(
        "Assistant reply 2"
    )

    reply2 = conv.send("Follow up")
    assert reply2 == "Assistant reply 2"
    assert conv.turn_count == 2
    assert len(conv.messages) == 4


def test_render_template() -> None:
    """Test that Jinja2 templates render correctly."""
    rendered = render(
        "article_medium.j2",
        topic="AI Triage",
        audience="clinicians",
        word_count=1500,
        key_points=["Point A", "Point B"],
        style_context="",
        references=[],
        brand_voice="Test brand voice.",
    )

    assert "AI Triage" in rendered
    assert "clinicians" in rendered
    assert "1500" in rendered
    assert "Point A" in rendered
    assert "Point B" in rendered
