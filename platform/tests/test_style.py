"""Tests for the style learning module."""

from __future__ import annotations

import json
from pathlib import Path

from daccia.llm.client import ClaudeClient
from daccia.style.analyzer import StyleAnalyzer
from daccia.style.applier import StyleApplier
from daccia.style.profile import StyleProfile
from tests.conftest import make_mock_response


def test_default_profile_has_all_dimensions() -> None:
    """Test that the default profile includes all 8 dimensions."""
    profile = StyleProfile.default()
    assert len(profile.dimensions) == 8
    assert "sentence_length" in profile.dimensions
    assert "formality" in profile.dimensions
    assert "jargon_level" in profile.dimensions
    assert "structure" in profile.dimensions
    assert "opening_style" in profile.dimensions
    assert "closing_style" in profile.dimensions
    assert "humor" in profile.dimensions
    assert "personal_anecdotes" in profile.dimensions


def test_profile_save_and_load(tmp_path: Path) -> None:
    """Test that a profile can be saved and loaded."""
    profile = StyleProfile.default()
    profile.edit_count = 3
    profile.dimensions["formality"].value = "very casual"
    profile.dimensions["formality"].confidence = 0.45

    profile.save(tmp_path)
    loaded = StyleProfile.load(tmp_path)

    assert loaded.edit_count == 3
    assert loaded.dimensions["formality"].value == "very casual"
    assert loaded.dimensions["formality"].confidence == 0.45


def test_profile_load_missing_returns_default(tmp_path: Path) -> None:
    """Test that loading from a non-existent path returns the default profile."""
    profile = StyleProfile.load(tmp_path)
    assert profile.edit_count == 0
    assert len(profile.dimensions) == 8


def test_to_prompt_fragment_empty_profile() -> None:
    """Test that an empty profile produces no prompt fragment."""
    profile = StyleProfile.default()
    assert profile.to_prompt_fragment() == ""


def test_to_prompt_fragment_with_data() -> None:
    """Test that a profile with data produces a meaningful fragment."""
    profile = StyleProfile.default()
    profile.edit_count = 5
    profile.dimensions["formality"].value = "casual and direct"
    profile.dimensions["formality"].confidence = 0.5
    profile.dimensions["formality"].examples = ["Here's what happened..."]

    fragment = profile.to_prompt_fragment()
    assert "AUTHOR STYLE PREFERENCES" in fragment
    assert "casual and direct" in fragment
    assert "Here's what happened..." in fragment


def test_style_analyzer_updates_profile(mock_claude_client: ClaudeClient) -> None:
    """Test that the analyzer updates the profile from Claude's analysis."""
    analysis_json = json.dumps({
        "sentence_length": {
            "preference": "short and punchy, under 12 words",
            "example": "The AI flagged it. She acted."
        },
        "formality": {
            "preference": "conversational, like talking to a colleague",
            "example": "Look, here's the thing about sepsis alerts..."
        },
    })

    mock_claude_client._client.messages.create.return_value = make_mock_response(
        analysis_json
    )

    analyzer = StyleAnalyzer(mock_claude_client)
    profile = StyleProfile.default()
    assert profile.edit_count == 0

    updated = analyzer.analyze_edit(
        original="Some original text here.",
        edited="Some edited text that's different.",
        profile=profile,
    )

    assert updated.edit_count == 1
    assert updated.dimensions["sentence_length"].value == "short and punchy, under 12 words"
    assert updated.dimensions["sentence_length"].confidence == 0.15
    assert "The AI flagged it. She acted." in updated.dimensions["sentence_length"].examples
    assert updated.dimensions["formality"].value == "conversational, like talking to a colleague"


def test_style_analyzer_handles_bad_json(mock_claude_client: ClaudeClient) -> None:
    """Test that the analyzer gracefully handles non-JSON responses."""
    mock_claude_client._client.messages.create.return_value = make_mock_response(
        "Sorry, I couldn't parse that properly."
    )

    analyzer = StyleAnalyzer(mock_claude_client)
    profile = StyleProfile.default()

    updated = analyzer.analyze_edit("original", "edited", profile)
    # Should not crash, edit count should not increment (failed parse)
    assert updated.edit_count == 0


def test_style_applier_default_temperature() -> None:
    """Test temperature suggestion for default profile."""
    applier = StyleApplier()
    profile = StyleProfile.default()
    assert applier.suggest_temperature(profile) == 0.7


def test_style_applier_formal_temperature() -> None:
    """Test temperature suggestion for formal style."""
    applier = StyleApplier()
    profile = StyleProfile.default()
    profile.dimensions["formality"].value = "formal and academic"
    profile.dimensions["formality"].confidence = 0.5

    assert applier.suggest_temperature(profile) == 0.5


def test_style_applier_casual_temperature() -> None:
    """Test temperature suggestion for casual style."""
    applier = StyleApplier()
    profile = StyleProfile.default()
    profile.dimensions["formality"].value = "casual and conversational"
    profile.dimensions["formality"].confidence = 0.5

    assert applier.suggest_temperature(profile) == 0.8
