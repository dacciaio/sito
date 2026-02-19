"""Medium API client for publishing articles.

Note: The Medium API is officially deprecated (archived March 2023)
but self-issued access tokens and the POST endpoint still work.
"""

from __future__ import annotations

from dataclasses import dataclass

import httpx

MEDIUM_API_BASE = "https://api.medium.com/v1"


@dataclass
class MediumPost:
    """Result of a successful Medium publish."""

    post_id: str
    url: str
    title: str
    publish_status: str


class MediumClient:
    """Wrapper around the Medium API."""

    def __init__(self, token: str) -> None:
        self._token = token
        self._client = httpx.Client(
            base_url=MEDIUM_API_BASE,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            timeout=30.0,
        )
        self._user_id: str | None = None

    def get_user_id(self) -> str:
        """Fetch the authenticated user's ID (cached after first call)."""
        if self._user_id:
            return self._user_id

        resp = self._client.get("/me")
        resp.raise_for_status()
        data = resp.json()["data"]
        self._user_id = data["id"]
        return self._user_id

    def publish(
        self,
        title: str,
        content: str,
        *,
        publish_status: str = "draft",
        tags: list[str] | None = None,
        canonical_url: str | None = None,
    ) -> MediumPost:
        """Publish an article to Medium.

        Args:
            title: Article title (max 100 chars).
            content: Full article body in Markdown format.
            publish_status: "draft", "public", or "unlisted".
            tags: Up to 3 tags, each max 25 chars.
            canonical_url: Original content URL for SEO.

        Returns:
            MediumPost with the post ID and URL.
        """
        user_id = self.get_user_id()

        payload: dict = {
            "title": title[:100],
            "contentFormat": "markdown",
            "content": f"# {title}\n\n{content}",
            "publishStatus": publish_status,
        }
        if tags:
            payload["tags"] = [t[:25] for t in tags[:3]]
        if canonical_url:
            payload["canonicalUrl"] = canonical_url

        resp = self._client.post(f"/users/{user_id}/posts", json=payload)
        resp.raise_for_status()
        data = resp.json()["data"]

        return MediumPost(
            post_id=data["id"],
            url=data["url"],
            title=data["title"],
            publish_status=data["publishStatus"],
        )

    def close(self) -> None:
        self._client.close()
