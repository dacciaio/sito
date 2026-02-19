"""SQLModel database models."""

from __future__ import annotations

from datetime import datetime

from sqlmodel import Field, SQLModel


class ContentRecord(SQLModel, table=True):
    """Persisted record of generated content."""

    id: int | None = Field(default=None, primary_key=True)
    title: str
    body: str
    content_type: str
    topic: str
    status: str = "draft"  # draft | reviewing | published
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    word_count: int = 0
    revision_count: int = 0
    metadata_json: str = "{}"
    medium_url: str = ""  # URL after publishing to Medium
    teaser: str = ""  # AI-generated short blurb for blog cards


class ResearchRecord(SQLModel, table=True):
    """Persisted research article analysis."""

    id: int | None = Field(default=None, primary_key=True)
    url: str = Field(index=True)
    title: str
    source: str
    relevance_score: float = 0.0
    summary: str = ""
    content_angles_json: str = "[]"
    fetched_at: datetime = Field(default_factory=datetime.now)
    content_hash: str = Field(index=True)


class TopicProposal(SQLModel, table=True):
    """Proposed content topics from the research agent."""

    id: int | None = Field(default=None, primary_key=True)
    title: str
    content_type: str
    angle: str
    urgency: str = "medium"  # high | medium | low
    status: str = "proposed"  # proposed | accepted | rejected | completed
    source_article_ids: str = "[]"
    created_at: datetime = Field(default_factory=datetime.now)


class EditRecord(SQLModel, table=True):
    """Record of user edits for style learning."""

    id: int | None = Field(default=None, primary_key=True)
    content_id: int | None = Field(default=None, foreign_key="contentrecord.id")
    original_hash: str
    edited_hash: str
    analysis_json: str = "{}"
    created_at: datetime = Field(default_factory=datetime.now)
