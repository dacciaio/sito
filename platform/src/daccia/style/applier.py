"""Apply learned style preferences to content generation prompts."""

from __future__ import annotations

from daccia.style.profile import StyleProfile


class StyleApplier:
    """Takes a StyleProfile and modifies generation parameters."""

    def build_style_instruction(self, profile: StyleProfile) -> str:
        """Build a style instruction block for injection into system prompts."""
        return profile.to_prompt_fragment()

    def suggest_temperature(self, profile: StyleProfile) -> float:
        """Suggest a generation temperature based on learned style.

        More creative/casual styles get higher temperature.
        More formal/structured styles get lower temperature.
        """
        formality = profile.dimensions.get("formality")
        if formality and formality.confidence > 0.3:
            val = formality.value.lower()
            if "formal" in val or "academic" in val:
                return 0.5
            if "casual" in val or "conversational" in val:
                return 0.8
        return 0.7
