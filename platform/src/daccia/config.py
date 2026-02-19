"""Configuration loading from environment variables with validation."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict

# Anchor all paths to the platform/ directory (two levels up from this file)
_PLATFORM_DIR = Path(__file__).resolve().parent.parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="DACCIA_",
        case_sensitive=False,
    )

    # Anthropic (loaded separately, no prefix)
    anthropic_api_key: str = ""

    # Medium (loaded separately, no prefix)
    medium_token: str = ""

    # Model settings
    model: str = "claude-sonnet-4-20250514"
    max_tokens: int = 4096
    temperature: float = 0.7

    # Medium publishing
    medium_publish_status: str = "draft"  # draft | public | unlisted

    # Website root (one level up from platform/)
    site_root: Path = _PLATFORM_DIR.parent

    # Storage paths (absolute, anchored to platform/)
    db_path: Path = _PLATFORM_DIR / "data" / "daccia.db"
    style_profiles_dir: Path = _PLATFORM_DIR / "data" / "style_profiles"
    drafts_dir: Path = _PLATFORM_DIR / "data" / "drafts"
    published_dir: Path = _PLATFORM_DIR / "data" / "published"
    research_cache_dir: Path = _PLATFORM_DIR / "data" / "research_cache"

    # Logging
    log_level: str = "INFO"

    # Research feeds
    research_feeds: list[str] = [
        "https://news.mit.edu/topic/artificial-intelligence2/feed",
        "https://healthitanalytics.com/feed",
    ]


def get_settings() -> Settings:
    """Load settings from environment and .env file."""
    # Load .env from the platform/ directory regardless of cwd
    load_dotenv(_PLATFORM_DIR / ".env")
    api_key = os.getenv("ANTHROPIC_API_KEY", "")
    medium_token = os.getenv("MEDIUM_TOKEN", "")
    return Settings(anthropic_api_key=api_key, medium_token=medium_token)
