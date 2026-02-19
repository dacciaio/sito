"""Multi-turn conversation manager for iterative content refinement."""

from __future__ import annotations

from dataclasses import dataclass, field

from daccia.llm.client import ClaudeClient


@dataclass
class Conversation:
    """Manages a multi-turn conversation with Claude."""

    client: ClaudeClient
    system_prompt: str
    messages: list[dict] = field(default_factory=list)

    def send(self, user_message: str, *, stream: bool = False) -> str:
        """Send a user message and get the assistant response."""
        self.messages.append({"role": "user", "content": user_message})

        if stream:
            chunks: list[str] = []
            for chunk in self.client.generate_streaming(
                system=self.system_prompt,
                messages=self.messages,
            ):
                chunks.append(chunk)
            response_text = "".join(chunks)
        else:
            response_text = self.client.generate(
                system=self.system_prompt,
                messages=self.messages,
            )

        self.messages.append({"role": "assistant", "content": response_text})
        return response_text

    @property
    def turn_count(self) -> int:
        return len(self.messages) // 2
