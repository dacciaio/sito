"""Tests for content generation modules."""

from __future__ import annotations

from daccia.content.article import ArticleGenerator
from daccia.content.base import ContentRequest, ContentType
from daccia.content.refiner import ContentRefiner
from daccia.content.streams import StreamGenerator
from daccia.content.base import GeneratedContent
from daccia.llm.client import ClaudeClient
from tests.conftest import make_mock_response


SAMPLE_ARTICLE_RESPONSE = """# AI Triage in the Emergency Department

## Introduction

Emergency departments are under pressure. AI can help.

## The Problem

Wait times are increasing while staffing decreases.

## The Solution

AI-powered triage systems can prioritize patients effectively.

## Conclusion

The future of ED triage is augmented, not replaced.
"""


def test_article_generator_medium(mock_claude_client: ClaudeClient) -> None:
    """Test Medium article generation parses title and body."""
    mock_claude_client._client.messages.create.return_value = make_mock_response(
        SAMPLE_ARTICLE_RESPONSE
    )

    generator = ArticleGenerator(mock_claude_client)
    request = ContentRequest(
        topic="AI Triage",
        content_type=ContentType.MEDIUM_ARTICLE,
        target_word_count=1500,
    )

    content = generator.generate(request)

    assert content.title == "AI Triage in the Emergency Department"
    assert "Emergency departments" in content.body
    assert content.content_type == ContentType.MEDIUM_ARTICLE
    assert content.metadata["word_count"] > 0
    assert "generation_time_seconds" in content.metadata


def test_article_generator_with_key_points(mock_claude_client: ClaudeClient) -> None:
    """Test that key points are passed to Claude."""
    mock_claude_client._client.messages.create.return_value = make_mock_response(
        "# Test\n\nBody"
    )

    generator = ArticleGenerator(mock_claude_client)
    request = ContentRequest(
        topic="AI Ethics",
        content_type=ContentType.BLOG_POST,
        key_points=["Bias in algorithms", "Transparency requirements"],
    )

    generator.generate(request)

    # Verify the user message included key points
    call_args = mock_claude_client._client.messages.create.call_args
    user_msg = call_args.kwargs["messages"][0]["content"]
    assert "Bias in algorithms" in user_msg
    assert "Transparency requirements" in user_msg


def test_stream_generator_patient(mock_claude_client: ClaudeClient) -> None:
    """Test patient conversation stream generation."""
    mock_claude_client._client.messages.create.return_value = make_mock_response(
        "# A Patient's First Encounter with AI\n\nSarah sat nervously..."
    )

    generator = StreamGenerator(mock_claude_client)
    request = ContentRequest(
        topic="First AI encounter in ICU",
        content_type=ContentType.PATIENT_CONVERSATION,
    )

    content = generator.generate(request)

    assert content.title == "A Patient's First Encounter with AI"
    assert content.content_type == ContentType.PATIENT_CONVERSATION
    assert content.metadata["stream"] == "patient_conversation"


def test_stream_generator_nurse(mock_claude_client: ClaudeClient) -> None:
    """Test nurse stream generation."""
    mock_claude_client._client.messages.create.return_value = make_mock_response(
        "# Early Warning Scores: A Nurse's Perspective\n\nAfter 15 years..."
    )

    generator = StreamGenerator(mock_claude_client)
    request = ContentRequest(
        topic="Early warning scores",
        content_type=ContentType.ASK_A_NURSE,
    )

    content = generator.generate(request)
    assert content.content_type == ContentType.ASK_A_NURSE
    assert content.metadata["stream"] == "ask_a_nurse"


def test_stream_generator_doctor(mock_claude_client: ClaudeClient) -> None:
    """Test ED doctor stream generation."""
    mock_claude_client._client.messages.create.return_value = make_mock_response(
        "# AI Triage: A Pragmatic View\n\nThe evidence is clear..."
    )

    generator = StreamGenerator(mock_claude_client)
    request = ContentRequest(
        topic="AI triage evidence",
        content_type=ContentType.ASK_AN_ED_DOCTOR,
    )

    content = generator.generate(request)
    assert content.content_type == ContentType.ASK_AN_ED_DOCTOR
    assert content.metadata["stream"] == "ask_an_ed_doctor"


def test_content_refiner(mock_claude_client: ClaudeClient) -> None:
    """Test iterative refinement workflow."""
    mock_claude_client._client.messages.create.return_value = make_mock_response(
        "I've reviewed the article. Ready for your feedback."
    )

    refiner = ContentRefiner(mock_claude_client)
    content = GeneratedContent(
        title="Test Article",
        body="Some body text here.",
        content_type=ContentType.MEDIUM_ARTICLE,
    )

    initial = refiner.start_refinement(content)
    assert "reviewed" in initial.lower() or len(initial) > 0
    assert refiner.revision_count == 0

    # Apply feedback
    mock_claude_client._client.messages.create.return_value = make_mock_response(
        "# Test Article (Revised)\n\nImproved body text."
    )

    revised = refiner.refine("Make it shorter and punchier")
    assert len(revised) > 0
    assert refiner.revision_count == 1


def test_refiner_without_start_raises(mock_claude_client: ClaudeClient) -> None:
    """Test that refining without starting raises an error."""
    refiner = ContentRefiner(mock_claude_client)
    try:
        refiner.refine("some feedback")
        assert False, "Should have raised RuntimeError"
    except RuntimeError:
        pass
