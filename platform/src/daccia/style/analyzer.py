"""Analyze user edits to learn style preferences."""

from __future__ import annotations

import json
from datetime import datetime

from daccia.llm.client import ClaudeClient
from daccia.llm.prompts import render
from daccia.style.profile import StyleProfile


class StyleAnalyzer:
    """Compares original vs. edited content to extract style preferences.

    Flow:
    1. User generates content via the platform
    2. User edits the content externally (Medium, Google Docs, etc.)
    3. User pastes back the edited version
    4. Analyzer diffs the two and asks Claude to characterize the changes
    5. Style profile is updated with learned preferences
    """

    def __init__(self, client: ClaudeClient) -> None:
        self._client = client

    def analyze_edit(
        self,
        original: str,
        edited: str,
        profile: StyleProfile,
    ) -> StyleProfile:
        """Compare original and edited content, update the style profile."""
        system_prompt = render(
            "style_analysis.j2",
            dimensions=[
                {"name": d.name, "description": d.description}
                for d in profile.dimensions.values()
            ],
        )

        user_message = (
            f"ORIGINAL CONTENT:\n{original}\n\n"
            f"EDITED CONTENT:\n{edited}\n\n"
            f"Analyze the edits. For each style dimension, describe the preference "
            f"shown by the edits. Respond in JSON format with dimension names as keys."
        )

        response = self._client.generate(
            system=system_prompt,
            messages=[{"role": "user", "content": user_message}],
            temperature=0.3,
        )

        try:
            analysis = json.loads(response)
            for dim_key, dim in profile.dimensions.items():
                if dim_key in analysis:
                    entry = analysis[dim_key]
                    if isinstance(entry, dict):
                        dim.value = entry.get("preference", dim.value)
                        dim.confidence = min(1.0, dim.confidence + 0.15)
                        if "example" in entry:
                            dim.examples.append(entry["example"])
                            dim.examples = dim.examples[-5:]  # keep last 5
            profile.edit_count += 1
            profile.last_updated = datetime.now()
        except (json.JSONDecodeError, KeyError, TypeError):
            # If Claude's response is not valid JSON, skip this update.
            # The profile will improve over time with more edits.
            pass

        return profile
