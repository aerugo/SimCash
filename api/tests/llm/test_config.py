"""Tests for LLMConfig dataclass.

These tests verify the LLMConfig unified configuration dataclass
supports multiple LLM providers with provider-specific options.
"""

from __future__ import annotations

import pytest


class TestLLMConfig:
    """Tests for LLMConfig dataclass."""

    def test_creates_with_model_string(self) -> None:
        """LLMConfig creates from provider:model string."""
        from payment_simulator.llm.config import LLMConfig

        config = LLMConfig(model="anthropic:claude-sonnet-4-5")
        assert config.model == "anthropic:claude-sonnet-4-5"

    def test_provider_property_extracts_provider(self) -> None:
        """provider property extracts provider from model string."""
        from payment_simulator.llm.config import LLMConfig

        config = LLMConfig(model="anthropic:claude-sonnet-4-5")
        assert config.provider == "anthropic"

    def test_model_name_property_extracts_model(self) -> None:
        """model_name property extracts model from string."""
        from payment_simulator.llm.config import LLMConfig

        config = LLMConfig(model="anthropic:claude-sonnet-4-5")
        assert config.model_name == "claude-sonnet-4-5"

    def test_defaults_temperature_to_zero(self) -> None:
        """Default temperature is 0.0 for determinism."""
        from payment_simulator.llm.config import LLMConfig

        config = LLMConfig(model="openai:gpt-4o")
        assert config.temperature == 0.0

    def test_anthropic_thinking_budget(self) -> None:
        """Anthropic models support thinking_budget."""
        from payment_simulator.llm.config import LLMConfig

        config = LLMConfig(
            model="anthropic:claude-sonnet-4-5",
            thinking_budget=8000,
        )
        assert config.thinking_budget == 8000

    def test_openai_reasoning_effort(self) -> None:
        """OpenAI models support reasoning_effort."""
        from payment_simulator.llm.config import LLMConfig

        config = LLMConfig(
            model="openai:o1",
            reasoning_effort="high",
        )
        assert config.reasoning_effort == "high"

    def test_defaults_max_retries_to_three(self) -> None:
        """Default max_retries is 3."""
        from payment_simulator.llm.config import LLMConfig

        config = LLMConfig(model="anthropic:claude-sonnet-4-5")
        assert config.max_retries == 3

    def test_defaults_timeout_to_120_seconds(self) -> None:
        """Default timeout is 120 seconds."""
        from payment_simulator.llm.config import LLMConfig

        config = LLMConfig(model="anthropic:claude-sonnet-4-5")
        assert config.timeout_seconds == 120

    def test_is_immutable(self) -> None:
        """LLMConfig is immutable (frozen dataclass)."""
        from payment_simulator.llm.config import LLMConfig

        config = LLMConfig(model="anthropic:claude-sonnet-4-5")
        with pytest.raises(AttributeError):
            config.model = "different"  # type: ignore

    def test_provider_property_with_openai(self) -> None:
        """provider property works with OpenAI models."""
        from payment_simulator.llm.config import LLMConfig

        config = LLMConfig(model="openai:gpt-4o")
        assert config.provider == "openai"
        assert config.model_name == "gpt-4o"

    def test_can_export_from_llm_module(self) -> None:
        """LLMConfig can be imported from llm module."""
        from payment_simulator.llm import LLMConfig

        config = LLMConfig(model="anthropic:claude-sonnet-4-5")
        assert config is not None


class TestLLMConfigExtended:
    """Tests for extended LLMConfig features needed by castro migration."""

    def test_max_tokens_has_default(self) -> None:
        """LLMConfig has default max_tokens."""
        from payment_simulator.llm.config import LLMConfig

        config = LLMConfig(model="anthropic:claude-sonnet-4-5")
        assert config.max_tokens == 30000

    def test_max_tokens_can_be_set(self) -> None:
        """LLMConfig max_tokens can be customized."""
        from payment_simulator.llm.config import LLMConfig

        config = LLMConfig(model="anthropic:claude-sonnet-4-5", max_tokens=50000)
        assert config.max_tokens == 50000

    def test_thinking_config_for_google(self) -> None:
        """LLMConfig supports thinking_config for Google."""
        from payment_simulator.llm.config import LLMConfig

        config = LLMConfig(
            model="google:gemini-2.5-flash",
            thinking_config={"thinking_budget": 8000},
        )
        assert config.thinking_config == {"thinking_budget": 8000}

    def test_thinking_config_defaults_to_none(self) -> None:
        """thinking_config defaults to None."""
        from payment_simulator.llm.config import LLMConfig

        config = LLMConfig(model="google:gemini-2.5-flash")
        assert config.thinking_config is None

    def test_full_model_string_maps_google_to_google_gla(self) -> None:
        """full_model_string maps google provider to google-gla."""
        from payment_simulator.llm.config import LLMConfig

        config = LLMConfig(model="google:gemini-2.5-flash")
        assert config.full_model_string == "google-gla:gemini-2.5-flash"

    def test_full_model_string_preserves_anthropic(self) -> None:
        """full_model_string preserves anthropic provider."""
        from payment_simulator.llm.config import LLMConfig

        config = LLMConfig(model="anthropic:claude-sonnet-4-5")
        assert config.full_model_string == "anthropic:claude-sonnet-4-5"

    def test_full_model_string_preserves_openai(self) -> None:
        """full_model_string preserves openai provider."""
        from payment_simulator.llm.config import LLMConfig

        config = LLMConfig(model="openai:gpt-4o")
        assert config.full_model_string == "openai:gpt-4o"

    def test_to_model_settings_basic(self) -> None:
        """to_model_settings returns basic settings dict."""
        from payment_simulator.llm.config import LLMConfig

        config = LLMConfig(model="anthropic:claude-sonnet-4-5")
        settings = config.to_model_settings()

        assert settings["temperature"] == 0.0
        assert settings["max_tokens"] == 30000
        assert settings["timeout"] == 120

    def test_to_model_settings_with_custom_values(self) -> None:
        """to_model_settings includes custom values."""
        from payment_simulator.llm.config import LLMConfig

        config = LLMConfig(
            model="anthropic:claude-sonnet-4-5",
            temperature=0.5,
            max_tokens=50000,
            timeout_seconds=300,
        )
        settings = config.to_model_settings()

        assert settings["temperature"] == 0.5
        assert settings["max_tokens"] == 50000
        assert settings["timeout"] == 300

    def test_to_model_settings_with_anthropic_thinking(self) -> None:
        """to_model_settings includes Anthropic thinking config."""
        from payment_simulator.llm.config import LLMConfig

        config = LLMConfig(
            model="anthropic:claude-sonnet-4-5",
            thinking_budget=8000,
        )
        settings = config.to_model_settings()

        assert "anthropic_thinking" in settings
        assert settings["anthropic_thinking"]["budget_tokens"] == 8000

    def test_to_model_settings_without_anthropic_thinking(self) -> None:
        """to_model_settings omits anthropic_thinking when not set."""
        from payment_simulator.llm.config import LLMConfig

        config = LLMConfig(model="anthropic:claude-sonnet-4-5")
        settings = config.to_model_settings()

        assert "anthropic_thinking" not in settings

    def test_to_model_settings_with_openai_reasoning(self) -> None:
        """to_model_settings includes OpenAI reasoning effort."""
        from payment_simulator.llm.config import LLMConfig

        config = LLMConfig(
            model="openai:gpt-5.2",
            reasoning_effort="high",
        )
        settings = config.to_model_settings()

        assert settings["openai_reasoning_effort"] == "high"

    def test_to_model_settings_openai_high_reasoning_increases_tokens(self) -> None:
        """to_model_settings increases max_tokens for high reasoning effort."""
        from payment_simulator.llm.config import LLMConfig

        config = LLMConfig(
            model="openai:gpt-5.2",
            reasoning_effort="high",
            max_tokens=10000,  # Lower than 30000
        )
        settings = config.to_model_settings()

        # Should be at least 30000 for high reasoning
        assert settings["max_tokens"] >= 30000

    def test_to_model_settings_with_google_thinking(self) -> None:
        """to_model_settings includes Google thinking config."""
        from payment_simulator.llm.config import LLMConfig

        config = LLMConfig(
            model="google:gemini-2.5-flash",
            thinking_config={"thinking_budget": 8000},
        )
        settings = config.to_model_settings()

        assert "google_thinking_config" in settings
        assert settings["google_thinking_config"]["thinking_budget"] == 8000

    def test_to_model_settings_without_google_thinking(self) -> None:
        """to_model_settings omits google_thinking_config when not set."""
        from payment_simulator.llm.config import LLMConfig

        config = LLMConfig(model="google:gemini-2.5-flash")
        settings = config.to_model_settings()

        assert "google_thinking_config" not in settings
