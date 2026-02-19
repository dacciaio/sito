"""Analyze fetched articles for relevance to daccia.io's focus areas."""

from __future__ import annotations

import json

from daccia.llm.client import ClaudeClient
from daccia.llm.prompts import render
from daccia.research.fetcher import ResearchArticle

FOCUS_AREAS = [
    "Explainable AI (XAI) in healthcare",
    "AI in emergency medicine and critical care",
    "Clinical decision support systems",
    "Patient safety and AI",
    "AI regulation in healthcare",
    "Machine learning in ICU/ED settings",
    "Nurse and clinician perspectives on AI",
    "AI ethics in medicine",
]


class ArticleAnalyzer:
    """Score and summarize articles for relevance to daccia.io."""

    def __init__(self, client: ClaudeClient) -> None:
        self._client = client

    def analyze(self, article: ResearchArticle) -> dict:
        """Analyze an article and return relevance assessment.

        Returns dict with:
        - relevance_score: 0-10
        - relevant_focus_areas: list of matching focus areas
        - summary: 2-3 sentence summary
        - content_angles: suggested angles for daccia.io content
        """
        system = render("research_analyze.j2", focus_areas=FOCUS_AREAS)
        text = article.full_text or article.summary

        response = self._client.generate(
            system=system,
            messages=[
                {
                    "role": "user",
                    "content": (
                        f"Title: {article.title}\n"
                        f"Source: {article.source}\n"
                        f"Content:\n{text[:3000]}"
                    ),
                }
            ],
            temperature=0.3,
        )

        try:
            result = json.loads(response)
            result["title"] = article.title
            result["url"] = article.url
            return result
        except json.JSONDecodeError:
            return {
                "title": article.title,
                "url": article.url,
                "relevance_score": 0,
                "summary": response[:200],
                "relevant_focus_areas": [],
                "content_angles": [],
            }
