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
