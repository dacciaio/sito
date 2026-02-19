"""Abstract base class for all content generators."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum

from daccia.llm.client import ClaudeClient
from daccia.style.profile import StyleProfile


class ContentType(str, Enum):
    MEDIUM_ARTICLE = "medium_article"
    BLOG_POST = "blog_post"
    PATIENT_CONVERSATION = "patient_conversation"
    ASK_A_NURSE = "ask_a_nurse"
    ASK_AN_ED_DOCTOR = "ask_an_ed_doctor"


@dataclass
class ContentRequest:
    """Input parameters for content generation."""

    topic: str
    content_type: ContentType
    target_audience: str = "general"
    target_word_count: int = 1500
    key_points: list[str] | None = None
    tone: str | None = None
    references: list[str] | None = None


@dataclass
class GeneratedContent:
    """Output from a content generator."""

    title: str
    body: str
    content_type: ContentType
    metadata: dict = field(default_factory=dict)
    conversation_id: str | None = None


BRAND_VOICE = (
    "You write for daccia.io, a company focused on Explainable AI for "
    "Critical Care. The tone is authoritative yet accessible. You bridge "
    "the gap between clinical practice and AI technology. You use concrete "
    "examples from emergency medicine and critical care settings."
)


class BaseGenerator(ABC):
    """Base class for content generators."""

    def __init__(
        self, client: ClaudeClient, style_profile: StyleProfile | None = None
    ) -> None:
        self._client = client
        self._style_profile = style_profile

    @abstractmethod
    def generate(self, request: ContentRequest) -> GeneratedContent:
        """Generate content from a request."""
        ...

    @abstractmethod
    def get_system_prompt(self, request: ContentRequest) -> str:
        """Build the system prompt for this content type."""
        ...

    def _build_style_context(self) -> str:
        """Convert style profile into prompt context."""
        if not self._style_profile:
            return ""
        return self._style_profile.to_prompt_fragment()
