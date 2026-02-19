"""Propose new content topics based on research analysis."""

from __future__ import annotations

import json

from daccia.llm.client import ClaudeClient
from daccia.llm.prompts import render


class TopicProposer:
    """Generate content topic proposals from analyzed research."""

    def __init__(self, client: ClaudeClient) -> None:
        self._client = client

    def propose(
        self,
        analyses: list[dict],
        existing_topics: list[str] | None = None,
        count: int = 5,
    ) -> list[dict]:
        """Given article analyses, propose new content topics.

        Returns list of dicts with:
        - title: Proposed article title
        - content_type: Suggested content type
        - angle: The specific angle or argument
        - source_articles: Which research articles inspired this
        - urgency: high/medium/low
        """
        system = render(
            "research_propose.j2",
            existing_topics=existing_topics or [],
            count=count,
        )

        summaries = "\n\n".join(
            f"Article: {a.get('title', 'Unknown')}\n"
            f"Relevance: {a.get('relevance_score', 0)}/10\n"
            f"Summary: {a.get('summary', '')}\n"
            f"Angles: {', '.join(a.get('content_angles', []))}"
            for a in analyses
        )

        response = self._client.generate(
            system=system,
            messages=[{"role": "user", "content": summaries}],
            temperature=0.7,
        )

        try:
            return json.loads(response)
        except json.JSONDecodeError:
            return []
