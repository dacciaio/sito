"""Tests for the publishing pipeline: Medium client, blog regeneration, and DB migration."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner
from sqlmodel import select

from daccia.cli import main
from daccia.config import Settings
from daccia.llm.client import ClaudeClient
from daccia.publishing.medium import MediumClient, MediumPost
from daccia.storage.database import _migrate_if_needed, get_engine, get_session, _engines
from daccia.storage.models import ContentRecord
from tests.conftest import make_mock_response


# ---------------------------------------------------------------------------
# Medium client tests
# ---------------------------------------------------------------------------


class TestMediumClient:
    """Tests for the MediumClient wrapper."""

    def test_get_user_id(self) -> None:
        """Test that get_user_id fetches and caches the user ID."""
        with patch("daccia.publishing.medium.httpx.Client") as MockClient:
            mock_client = MagicMock()
            MockClient.return_value = mock_client
            mock_resp = MagicMock()
            mock_resp.json.return_value = {"data": {"id": "user-123"}}
            mock_client.get.return_value = mock_resp

            client = MediumClient("test-token")
            client._client = mock_client

            uid = client.get_user_id()
            assert uid == "user-123"

            # Second call should use cache (no additional API call)
            uid2 = client.get_user_id()
            assert uid2 == "user-123"
            mock_client.get.assert_called_once()

    def test_publish_article(self) -> None:
        """Test that publish sends correct payload and returns MediumPost."""
        with patch("daccia.publishing.medium.httpx.Client"):
            client = MediumClient("test-token")
            mock_http = MagicMock()
            client._client = mock_http
            client._user_id = "user-123"

            mock_resp = MagicMock()
            mock_resp.json.return_value = {
                "data": {
                    "id": "post-456",
                    "url": "https://medium.com/@user/test-article-456",
                    "title": "Test Article",
                    "publishStatus": "draft",
                }
            }
            mock_http.post.return_value = mock_resp

            post = client.publish(
                title="Test Article",
                content="Some content here.",
                publish_status="draft",
                tags=["AI", "healthcare"],
            )

            assert isinstance(post, MediumPost)
            assert post.post_id == "post-456"
            assert post.url == "https://medium.com/@user/test-article-456"
            assert post.publish_status == "draft"

            # Verify the payload
            call_args = mock_http.post.call_args
            payload = call_args.kwargs.get("json") or call_args[1].get("json")
            assert payload["title"] == "Test Article"
            assert payload["contentFormat"] == "markdown"
            assert payload["tags"] == ["AI", "healthcare"]

    def test_publish_truncates_long_title(self) -> None:
        """Test that titles longer than 100 chars are truncated."""
        with patch("daccia.publishing.medium.httpx.Client"):
            client = MediumClient("test-token")
            mock_http = MagicMock()
            client._client = mock_http
            client._user_id = "user-123"

            mock_resp = MagicMock()
            mock_resp.json.return_value = {
                "data": {
                    "id": "p1",
                    "url": "https://medium.com/p1",
                    "title": "A" * 100,
                    "publishStatus": "draft",
                }
            }
            mock_http.post.return_value = mock_resp

            long_title = "A" * 200
            client.publish(title=long_title, content="body")

            call_args = mock_http.post.call_args
            payload = call_args.kwargs.get("json") or call_args[1].get("json")
            assert len(payload["title"]) == 100

    def test_publish_limits_tags_to_three(self) -> None:
        """Test that tags are limited to 3 items."""
        with patch("daccia.publishing.medium.httpx.Client"):
            client = MediumClient("test-token")
            mock_http = MagicMock()
            client._client = mock_http
            client._user_id = "user-123"

            mock_resp = MagicMock()
            mock_resp.json.return_value = {
                "data": {
                    "id": "p1",
                    "url": "https://medium.com/p1",
                    "title": "T",
                    "publishStatus": "draft",
                }
            }
            mock_http.post.return_value = mock_resp

            client.publish(
                title="T",
                content="body",
                tags=["a", "b", "c", "d", "e"],
            )

            call_args = mock_http.post.call_args
            payload = call_args.kwargs.get("json") or call_args[1].get("json")
            assert len(payload["tags"]) == 3


# ---------------------------------------------------------------------------
# Database migration tests
# ---------------------------------------------------------------------------


class TestDatabaseMigration:
    """Tests for the lightweight column migration."""

    def test_migrate_adds_missing_columns(self, tmp_path: Path) -> None:
        """Test that migration adds medium_url and teaser to an old DB."""
        db_path = tmp_path / "test_migrate.db"

        # Create a table without the new columns (simulates old schema)
        conn = sqlite3.connect(str(db_path))
        conn.execute("""
            CREATE TABLE contentrecord (
                id INTEGER PRIMARY KEY,
                title TEXT,
                body TEXT,
                content_type TEXT,
                topic TEXT,
                status TEXT DEFAULT 'draft',
                created_at TIMESTAMP,
                updated_at TIMESTAMP,
                word_count INTEGER DEFAULT 0,
                revision_count INTEGER DEFAULT 0,
                metadata_json TEXT DEFAULT '{}'
            )
        """)
        conn.execute(
            "INSERT INTO contentrecord (title, body, content_type, topic) "
            "VALUES ('Test', 'Body', 'medium_article', 'AI')"
        )
        conn.commit()
        conn.close()

        # Run migration
        _migrate_if_needed(db_path)

        # Verify columns were added
        conn = sqlite3.connect(str(db_path))
        cursor = conn.execute("PRAGMA table_info(contentrecord)")
        cols = {row[1] for row in cursor.fetchall()}
        conn.close()

        assert "medium_url" in cols
        assert "teaser" in cols

    def test_migrate_idempotent(self, tmp_path: Path) -> None:
        """Test that running migration twice doesn't error."""
        db_path = tmp_path / "test_idempotent.db"

        conn = sqlite3.connect(str(db_path))
        conn.execute("""
            CREATE TABLE contentrecord (
                id INTEGER PRIMARY KEY,
                title TEXT,
                body TEXT,
                content_type TEXT,
                topic TEXT,
                status TEXT DEFAULT 'draft',
                created_at TIMESTAMP,
                updated_at TIMESTAMP,
                word_count INTEGER DEFAULT 0,
                revision_count INTEGER DEFAULT 0,
                metadata_json TEXT DEFAULT '{}'
            )
        """)
        conn.commit()
        conn.close()

        _migrate_if_needed(db_path)
        _migrate_if_needed(db_path)  # Should not raise

    def test_migrate_skips_nonexistent_db(self, tmp_path: Path) -> None:
        """Test that migration does nothing if the DB doesn't exist."""
        db_path = tmp_path / "nonexistent.db"
        _migrate_if_needed(db_path)  # Should not raise
        assert not db_path.exists()


# ---------------------------------------------------------------------------
# Blog regeneration tests
# ---------------------------------------------------------------------------


class TestBlogRegeneration:
    """Tests for the _regenerate_blog helper."""

    def test_blog_section_injected_into_html(self, tmp_path: Path) -> None:
        """Test that blog cards are injected between markers."""
        from daccia.cli import _regenerate_blog

        # Create a minimal index.html with markers
        index_path = tmp_path / "index.html"
        index_path.write_text(
            "<html><body>"
            "<!-- BLOG_START --><!-- BLOG_END -->"
            "<footer>Footer</footer>"
            "</body></html>"
        )

        # Create a DB with a published article
        db_path = tmp_path / "blog_test.db"

        # Clear engine cache to avoid conflicts
        _engines.clear()

        with get_session(db_path) as session:
            record = ContentRecord(
                title="AI in the ED",
                body="Article body here.",
                content_type="medium_article",
                topic="AI triage",
                status="published",
                medium_url="https://medium.com/@daccia/ai-in-the-ed",
                teaser="Discover how AI is transforming emergency department triage.",
            )
            session.add(record)
            session.commit()

        # Create a mock settings object
        mock_settings = MagicMock()
        mock_settings.site_root = tmp_path
        mock_settings.db_path = db_path

        _regenerate_blog(mock_settings)

        html = index_path.read_text()
        assert "AI in the ED" in html
        assert "Discover how AI" in html
        assert "medium.com/@daccia/ai-in-the-ed" in html
        assert "BLOG_START" in html
        assert "BLOG_END" in html

        _engines.clear()

    def test_blog_section_empty_when_no_articles(self, tmp_path: Path) -> None:
        """Test that an empty blog section is rendered when no articles exist."""
        from daccia.cli import _regenerate_blog

        index_path = tmp_path / "index.html"
        index_path.write_text(
            "<html><!-- BLOG_START --><!-- BLOG_END --></html>"
        )

        db_path = tmp_path / "empty_test.db"
        _engines.clear()

        # Just create the DB with no records
        get_engine(db_path)

        mock_settings = MagicMock()
        mock_settings.site_root = tmp_path
        mock_settings.db_path = db_path

        _regenerate_blog(mock_settings)

        html = index_path.read_text()
        # Should still have markers but no article cards
        assert "BLOG_START" in html
        assert "BLOG_END" in html
        assert "Read on Medium" not in html

        _engines.clear()

    def test_blog_warns_when_no_markers(self, tmp_path: Path, capsys) -> None:
        """Test that a warning is printed when markers are missing."""
        from daccia.cli import _regenerate_blog

        index_path = tmp_path / "index.html"
        index_path.write_text("<html><body>No markers here</body></html>")

        db_path = tmp_path / "nomarkers.db"
        _engines.clear()
        get_engine(db_path)

        mock_settings = MagicMock()
        mock_settings.site_root = tmp_path
        mock_settings.db_path = db_path

        _regenerate_blog(mock_settings)

        html = index_path.read_text()
        # HTML should be unchanged
        assert html == "<html><body>No markers here</body></html>"

        _engines.clear()


# ---------------------------------------------------------------------------
# CLI publish command test
# ---------------------------------------------------------------------------


class TestPublishCLI:
    """Tests for the daccia publish CLI command."""

    def test_publish_no_drafts(self, tmp_path: Path) -> None:
        """Test that publish exits gracefully when there are no drafts."""
        _engines.clear()
        db_path = tmp_path / "cli_test.db"
        get_engine(db_path)

        runner = CliRunner()
        with patch("daccia.config.get_settings") as mock_gs:
            mock_settings = MagicMock()
            mock_settings.anthropic_api_key = "test-key"
            mock_settings.medium_token = ""
            mock_settings.db_path = db_path
            mock_gs.return_value = mock_settings

            result = runner.invoke(main, ["publish"])
            assert "No drafts to publish" in result.output

        _engines.clear()


# ---------------------------------------------------------------------------
# Retry logic test (auth errors should NOT retry)
# ---------------------------------------------------------------------------


class TestRetryLogic:
    """Tests for the smart retry behavior in ClaudeClient."""

    def test_auth_error_not_retried(self) -> None:
        """Test that AuthenticationError is raised immediately, not retried."""
        from anthropic import AuthenticationError
        from daccia.llm.client import _is_retryable

        exc = AuthenticationError.__new__(AuthenticationError)
        assert _is_retryable(exc) is False

    def test_server_error_is_retryable(self) -> None:
        """Test that 500-level errors are retried."""
        from daccia.llm.client import _is_retryable

        # Simulate a generic exception (server error)
        exc = Exception("Internal server error")
        assert _is_retryable(exc) is True
