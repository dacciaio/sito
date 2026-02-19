"""Style profile data model — stores learned writing preferences."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from pydantic import BaseModel, Field


class StyleDimension(BaseModel):
    """A single dimension of writing style with learned value."""

    name: str
    description: str
    value: str
    confidence: float = 0.0  # 0.0 to 1.0, increases with more data
    examples: list[str] = Field(default_factory=list)


class StyleProfile(BaseModel):
    """Complete style profile learned from user's editing patterns."""

    user_id: str = "default"
    dimensions: dict[str, StyleDimension] = Field(default_factory=dict)
    edit_count: int = 0
    last_updated: datetime = Field(default_factory=datetime.now)

    @classmethod
    def default(cls) -> StyleProfile:
        """Create a profile with empty default dimensions."""
        return cls(
            dimensions={
                "sentence_length": StyleDimension(
                    name="Sentence Length",
                    description="Preference for short, punchy vs. long, flowing sentences",
                    value="balanced",
                ),
                "formality": StyleDimension(
                    name="Formality",
                    description="Formal/academic vs. conversational tone",
                    value="professional but accessible",
                ),
                "jargon_level": StyleDimension(
                    name="Technical Jargon",
                    description="Heavy use of medical/AI terminology vs. plain language",
                    value="moderate -- explains terms when first used",
                ),
                "structure": StyleDimension(
                    name="Structure Preference",
                    description="Headers and lists vs. flowing prose",
                    value="mixed",
                ),
                "opening_style": StyleDimension(
                    name="Opening Style",
                    description="How articles begin: anecdote, question, statistic, statement",
                    value="not yet determined",
                ),
                "closing_style": StyleDimension(
                    name="Closing Style",
                    description="How articles end: call to action, summary, question, reflection",
                    value="not yet determined",
                ),
                "humor": StyleDimension(
                    name="Humor Usage",
                    description="Frequency and type of humor",
                    value="not yet determined",
                ),
                "personal_anecdotes": StyleDimension(
                    name="Personal Anecdotes",
                    description="Use of personal stories and experiences",
                    value="not yet determined",
                ),
            }
        )

    def to_prompt_fragment(self) -> str:
        """Convert this profile into a prompt fragment for content generation."""
        if self.edit_count == 0:
            return ""

        lines = ["AUTHOR STYLE PREFERENCES (learned from previous edits):"]
        for dim in self.dimensions.values():
            if dim.confidence > 0.2:
                lines.append(f"- {dim.name}: {dim.value}")
                if dim.examples:
                    lines.append(f'  Example: "{dim.examples[-1]}"')
        return "\n".join(lines)

    def save(self, directory: Path) -> None:
        """Persist the profile as a JSON file."""
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / f"style_{self.user_id}.json"
        path.write_text(self.model_dump_json(indent=2))

    @classmethod
    def load(cls, directory: Path, user_id: str = "default") -> StyleProfile:
        """Load a profile from disk, or return default if not found."""
        path = directory / f"style_{user_id}.json"
        if path.exists():
            return cls.model_validate_json(path.read_text())
        return cls.default()
