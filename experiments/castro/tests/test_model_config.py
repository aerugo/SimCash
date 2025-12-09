"""Tests for model configuration.

Tests cover:
- Provider extraction from model strings
- Model settings conversion for each provider
- Legacy model name inference
- Default value handling
"""

from __future__ import annotations

import pytest
from castro.model_config import ModelConfig, _infer_provider, create_model_config


class TestModelConfigBasics:
    """Tests for basic ModelConfig functionality."""

    def test_provider_extraction_with_colon(self) -> None:
        """Provider should be extracted from model string with colon."""
        config = ModelConfig("anthropic:claude-sonnet-4-5")
        assert config.provider == "anthropic"
        assert config.model_name == "claude-sonnet-4-5"

    def test_provider_extraction_openai(self) -> None:
        """Provider should be extracted for OpenAI model."""
        config = ModelConfig("openai:gpt-5.1")
        assert config.provider == "openai"
        assert config.model_name == "gpt-5.1"

    def test_provider_extraction_google(self) -> None:
        """Provider should be extracted for Google model."""
        config = ModelConfig("google:gemini-2.5-flash")
        assert config.provider == "google"
        assert config.model_name == "gemini-2.5-flash"

    def test_full_model_string_already_formatted(self) -> None:
        """full_model_string should return as-is if already formatted."""
        config = ModelConfig("anthropic:claude-sonnet-4-5")
        assert config.full_model_string == "anthropic:claude-sonnet-4-5"

    def test_full_model_string_infers_provider(self) -> None:
        """full_model_string should add provider if not present."""
        config = ModelConfig("claude-sonnet-4-5")
        assert config.full_model_string == "anthropic:claude-sonnet-4-5"

    def test_default_values(self) -> None:
        """Default values should be sensible."""
        config = ModelConfig("anthropic:claude-sonnet-4-5")
        assert config.temperature == 0.0
        assert config.max_tokens == 30000
        assert config.thinking_budget is None
        assert config.reasoning_effort is None
        assert config.max_retries == 3
        assert config.timeout_seconds == 120


class TestLegacyProviderInference:
    """Tests for legacy provider inference from model name."""

    def test_infer_anthropic_from_claude(self) -> None:
        """Claude model names should infer Anthropic provider."""
        assert _infer_provider("claude-sonnet-4-5-20250929") == "anthropic"
        assert _infer_provider("claude-3-opus") == "anthropic"

    def test_infer_openai_from_gpt(self) -> None:
        """GPT model names should infer OpenAI provider."""
        assert _infer_provider("gpt-4o") == "openai"
        assert _infer_provider("gpt-5.1") == "openai"
        assert _infer_provider("GPT-4") == "openai"

    def test_infer_openai_from_o1(self) -> None:
        """o1/o3 model names should infer OpenAI provider."""
        assert _infer_provider("o1-preview") == "openai"
        assert _infer_provider("o3-mini") == "openai"

    def test_infer_google_from_gemini(self) -> None:
        """Gemini model names should infer Google provider."""
        assert _infer_provider("gemini-pro") == "google"
        assert _infer_provider("gemini-2.5-flash") == "google"

    def test_default_to_anthropic(self) -> None:
        """Unknown model names should default to Anthropic."""
        assert _infer_provider("unknown-model") == "anthropic"


class TestModelSettingsConversion:
    """Tests for converting ModelConfig to PydanticAI ModelSettings."""

    def test_basic_settings(self) -> None:
        """Basic settings should be included."""
        config = ModelConfig(
            "anthropic:claude-sonnet-4-5",
            temperature=0.5,
            max_tokens=30000,
        )
        settings = config.to_model_settings()

        assert settings["temperature"] == 0.5
        assert settings["max_tokens"] == 30000
        assert "timeout" in settings

    def test_anthropic_thinking_budget(self) -> None:
        """Anthropic thinking budget should be converted to anthropic_thinking."""
        config = ModelConfig(
            "anthropic:claude-sonnet-4-5",
            thinking_budget=8000,
        )
        settings = config.to_model_settings()

        assert "anthropic_thinking" in settings
        assert settings["anthropic_thinking"]["budget_tokens"] == 8000

    def test_openai_reasoning_effort(self) -> None:
        """OpenAI reasoning effort should be converted."""
        config = ModelConfig(
            "openai:gpt-5.1",
            reasoning_effort="high",
        )
        settings = config.to_model_settings()

        assert settings["openai_reasoning_effort"] == "high"

    def test_openai_high_reasoning_increases_tokens(self) -> None:
        """High reasoning effort should increase max_tokens."""
        config = ModelConfig(
            "openai:gpt-5.1",
            reasoning_effort="high",
            max_tokens=30000,
        )
        settings = config.to_model_settings()

        assert settings["max_tokens"] >= 30000

    def test_openai_low_reasoning_preserves_tokens(self) -> None:
        """Low reasoning effort should preserve max_tokens."""
        config = ModelConfig(
            "openai:gpt-5.1",
            reasoning_effort="low",
            max_tokens=4096,
        )
        settings = config.to_model_settings()

        assert settings["max_tokens"] == 4096

    def test_google_thinking_config(self) -> None:
        """Google thinking config should be passed through."""
        config = ModelConfig(
            "google:gemini-2.5-flash",
            thinking_config={"thinking_budget": 8000},
        )
        settings = config.to_model_settings()

        assert "google_thinking_config" in settings
        assert settings["google_thinking_config"]["thinking_budget"] == 8000

    def test_no_provider_specific_settings(self) -> None:
        """No provider-specific settings when not configured."""
        config = ModelConfig("anthropic:claude-sonnet-4-5")
        settings = config.to_model_settings()

        assert "anthropic_thinking" not in settings
        assert "openai_reasoning_effort" not in settings
        assert "google_thinking_config" not in settings


class TestCreateModelConfig:
    """Tests for the create_model_config convenience function."""

    def test_basic_creation(self) -> None:
        """Basic model config creation."""
        config = create_model_config("anthropic:claude-sonnet-4-5")
        assert config.model == "anthropic:claude-sonnet-4-5"
        assert config.provider == "anthropic"

    def test_with_thinking_budget(self) -> None:
        """Config with thinking budget."""
        config = create_model_config(
            "anthropic:claude-sonnet-4-5",
            thinking_budget=8000,
        )
        assert config.thinking_budget == 8000

    def test_with_reasoning_effort(self) -> None:
        """Config with reasoning effort."""
        config = create_model_config(
            "openai:gpt-5.1",
            reasoning_effort="high",
        )
        assert config.reasoning_effort == "high"

    def test_with_temperature(self) -> None:
        """Config with custom temperature."""
        config = create_model_config(
            "anthropic:claude-sonnet-4-5",
            temperature=0.7,
        )
        assert config.temperature == 0.7
