"""Fetch articles from RSS feeds and web sources."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import feedparser
import httpx
from bs4 import BeautifulSoup
from dateutil import parser as dateparser


@dataclass
class ResearchArticle:
    """A fetched article with extracted text."""

    url: str
    title: str
    source: str
    published: datetime | None
    summary: str
    full_text: str | None = None
    content_hash: str = ""

    def __post_init__(self) -> None:
        if not self.content_hash:
            self.content_hash = hashlib.sha256(
                (self.url + self.title).encode()
            ).hexdigest()

    @property
    def id(self) -> str:
        return self.content_hash[:12]


class ArticleFetcher:
    """Fetch and parse articles from RSS feeds and URLs."""

    def __init__(self, cache_dir: Path) -> None:
        self._cache_dir = cache_dir
        self._cache_dir.mkdir(parents=True, exist_ok=True)
        self._client = httpx.Client(
            timeout=30.0,
            headers={"User-Agent": "daccia.io research agent/0.1"},
            follow_redirects=True,
        )

    def fetch_feed(self, feed_url: str, max_articles: int = 10) -> list[ResearchArticle]:
        """Parse an RSS/Atom feed and return articles."""
        feed = feedparser.parse(feed_url)
        articles: list[ResearchArticle] = []

        for entry in feed.entries[:max_articles]:
            summary_raw = entry.get("summary", "")
            summary = BeautifulSoup(summary_raw, "html.parser").get_text()[:500]

            articles.append(
                ResearchArticle(
                    url=entry.get("link", ""),
                    title=entry.get("title", "Untitled"),
                    source=feed.feed.get("title", feed_url),
                    published=self._parse_date(entry.get("published")),
                    summary=summary,
                )
            )

        return articles

    def fetch_full_text(self, article: ResearchArticle) -> ResearchArticle:
        """Fetch and extract the full text of an article."""
        try:
            resp = self._client.get(article.url)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "html.parser")

            # Remove non-content elements
            for tag in soup(["script", "style", "nav", "header", "footer", "aside"]):
                tag.decompose()

            # Try common article selectors
            content = (
                soup.find("article")
                or soup.find("main")
                or soup.find(class_="post-content")
                or soup.find(class_="entry-content")
                or soup.find(class_="article-body")
            )
            if content:
                article.full_text = content.get_text(separator="\n", strip=True)[:5000]
        except (httpx.HTTPError, Exception):
            pass  # Gracefully skip failures

        return article

    @staticmethod
    def _parse_date(date_str: str | None) -> datetime | None:
        if not date_str:
            return None
        try:
            return dateparser.parse(date_str)
        except (ValueError, TypeError):
            return None

    def close(self) -> None:
        self._client.close()
