"""Iterative content refinement with Socratic feedback."""

from __future__ import annotations

from daccia.content.base import GeneratedContent
from daccia.llm.client import ClaudeClient
from daccia.llm.conversation import Conversation


REFINER_SYSTEM_PROMPT = (
    "You are a content editor for daccia.io, specializing in AI for healthcare content. "
    "You are refining an article based on the author's feedback. "
    "When given feedback:\n"
    "1. If the feedback is vague, ask ONE clarifying question (Socratic method)\n"
    "2. Then produce a complete revised version incorporating the feedback\n"
    "3. Briefly explain what you changed and why\n"
    "Preserve the original voice and style. Do not add fluff. Be precise."
)


class ContentRefiner:
    """Manages iterative refinement of generated content via multi-turn conversation."""

    def __init__(self, client: ClaudeClient) -> None:
        self._client = client
        self._conversation: Conversation | None = None

    def start_refinement(self, content: GeneratedContent) -> str:
        """Initialize a refinement session with the generated content.

        Returns Claude's initial response (acknowledgment of the content).
        """
        self._conversation = Conversation(
            client=self._client,
            system_prompt=REFINER_SYSTEM_PROMPT,
        )
        return self._conversation.send(
            f"Here is the article to refine:\n\n"
            f"# {content.title}\n\n{content.body}"
        )

    def refine(self, feedback: str, *, socratic: bool = True) -> str:
        """Apply user feedback and return revised content.

        Args:
            feedback: User's textual feedback on the content.
            socratic: If True, the refiner may ask a clarifying question first.
        """
        if not self._conversation:
            raise RuntimeError("Call start_refinement() first")

        if not socratic:
            feedback = (
                f"Apply this feedback directly without asking questions. "
                f"Produce the complete revised article.\n\nFeedback: {feedback}"
            )

        return self._conversation.send(feedback)

    @property
    def revision_count(self) -> int:
        if not self._conversation:
            return 0
        return max(0, self._conversation.turn_count - 1)
