"""Tests for the research agent modules."""

from __future__ import annotations

import json
from pathlib import Path

from daccia.llm.client import ClaudeClient
from daccia.research.analyzer import ArticleAnalyzer
from daccia.research.fetcher import ArticleFetcher, ResearchArticle
from daccia.research.proposer import TopicProposer
from tests.conftest import make_mock_response


def test_research_article_hash() -> None:
    """Test that ResearchArticle generates a content hash."""
    article = ResearchArticle(
        url="https://example.com/article",
        title="Test Article",
        source="Test Source",
        published=None,
        summary="Some summary.",
    )
    assert len(article.content_hash) == 64  # SHA-256 hex
    assert len(article.id) == 12


def test_research_article_deterministic_hash() -> None:
    """Test that the same URL+title produces the same hash."""
    a1 = ResearchArticle(
        url="https://example.com/a", title="Title", source="S", published=None, summary=""
    )
    a2 = ResearchArticle(
        url="https://example.com/a", title="Title", source="S", published=None, summary=""
    )
    assert a1.content_hash == a2.content_hash


def test_article_fetcher_creates_cache_dir(tmp_path: Path) -> None:
    """Test that ArticleFetcher creates the cache directory."""
    cache = tmp_path / "cache"
    fetcher = ArticleFetcher(cache)
    assert cache.exists()
    fetcher.close()


def test_article_analyzer_parses_json(mock_claude_client: ClaudeClient) -> None:
    """Test that ArticleAnalyzer parses Claude's JSON response."""
    analysis_json = json.dumps({
        "relevance_score": 8,
        "relevant_focus_areas": ["AI in emergency medicine and critical care"],
        "summary": "This article discusses AI triage in the ED.",
        "content_angles": ["Compare AI triage accuracy to nurse triage"],
    })
    mock_claude_client._client.messages.create.return_value = make_mock_response(
        analysis_json
    )

    analyzer = ArticleAnalyzer(mock_claude_client)
    article = ResearchArticle(
        url="https://example.com/article",
        title="AI Triage Study",
        source="Nature Medicine",
        published=None,
        summary="A new study shows AI triage matches expert performance.",
    )

    result = analyzer.analyze(article)
    assert result["relevance_score"] == 8
    assert "AI in emergency medicine" in result["relevant_focus_areas"][0]
    assert result["title"] == "AI Triage Study"
    assert result["url"] == "https://example.com/article"


def test_article_analyzer_handles_bad_json(mock_claude_client: ClaudeClient) -> None:
    """Test that ArticleAnalyzer handles non-JSON responses gracefully."""
    mock_claude_client._client.messages.create.return_value = make_mock_response(
        "This is not JSON at all."
    )

    analyzer = ArticleAnalyzer(mock_claude_client)
    article = ResearchArticle(
        url="https://example.com/bad",
        title="Bad Article",
        source="Unknown",
        published=None,
        summary="Summary.",
    )

    result = analyzer.analyze(article)
    assert result["relevance_score"] == 0
    assert result["title"] == "Bad Article"


def test_topic_proposer_parses_proposals(mock_claude_client: ClaudeClient) -> None:
    """Test that TopicProposer parses Claude's topic proposals."""
    proposals_json = json.dumps([
        {
            "title": "Why ED Nurses Should Embrace AI Triage",
            "content_type": "ask_a_nurse",
            "angle": "Practical benefits of AI triage from a nursing workflow perspective",
            "source_articles": ["AI Triage Study"],
            "urgency": "high",
        },
        {
            "title": "Explaining AI Decisions to Patients in the ICU",
            "content_type": "patient_conversation",
            "angle": "How explainable AI builds trust in critical care settings",
            "source_articles": ["XAI Review"],
            "urgency": "medium",
        },
    ])
    mock_claude_client._client.messages.create.return_value = make_mock_response(
        proposals_json
    )

    proposer = TopicProposer(mock_claude_client)
    analyses = [
        {"title": "AI Triage Study", "relevance_score": 8, "summary": "...", "content_angles": []},
        {"title": "XAI Review", "relevance_score": 7, "summary": "...", "content_angles": []},
    ]

    proposals = proposer.propose(analyses)
    assert len(proposals) == 2
    assert proposals[0]["title"] == "Why ED Nurses Should Embrace AI Triage"
    assert proposals[0]["urgency"] == "high"
    assert proposals[1]["content_type"] == "patient_conversation"


def test_topic_proposer_handles_bad_json(mock_claude_client: ClaudeClient) -> None:
    """Test that TopicProposer returns empty list on bad JSON."""
    mock_claude_client._client.messages.create.return_value = make_mock_response(
        "Not valid JSON."
    )

    proposer = TopicProposer(mock_claude_client)
    proposals = proposer.propose([{"title": "Test", "relevance_score": 5}])
    assert proposals == []
