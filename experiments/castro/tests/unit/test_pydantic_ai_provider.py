"""Tests for PydanticAI provider integration.

These tests verify the PydanticAI provider interface and configuration
without requiring actual API calls.
"""

from __future__ import annotations

import pytest


class TestPydanticAIProviderConfig:
    """Tests for PydanticAI provider configuration."""

    def test_config_openai_format(self) -> None:
        """Config creates correct OpenAI model format."""
        from experiments.castro.generator.pydantic_ai_provider import PydanticAIConfig

        config = PydanticAIConfig.openai("gpt-4o")
        assert config.model == "openai:gpt-4o"

    def test_config_anthropic_format(self) -> None:
        """Config creates correct Anthropic model format."""
        from experiments.castro.generator.pydantic_ai_provider import PydanticAIConfig

        config = PydanticAIConfig.anthropic("claude-3-5-sonnet-20241022")
        assert config.model == "anthropic:claude-3-5-sonnet-20241022"

    def test_config_google_format(self) -> None:
        """Config creates correct Google model format."""
        from experiments.castro.generator.pydantic_ai_provider import PydanticAIConfig

        config = PydanticAIConfig.google("gemini-1.5-pro")
        assert config.model == "google-gla:gemini-1.5-pro"

    def test_config_ollama_format(self) -> None:
        """Config creates correct Ollama model format."""
        from experiments.castro.generator.pydantic_ai_provider import PydanticAIConfig

        config = PydanticAIConfig.ollama("llama3.1:8b")
        assert config.model == "ollama:llama3.1:8b"

    def test_config_default_retries(self) -> None:
        """Config has sensible default retries."""
        from experiments.castro.generator.pydantic_ai_provider import PydanticAIConfig

        config = PydanticAIConfig(model="openai:gpt-4o")
        assert config.retries == 3


class TestPydanticAIProvider:
    """Tests for PydanticAIProvider class."""

    def test_provider_initialization(self) -> None:
        """Provider initializes with model string."""
        from experiments.castro.generator.pydantic_ai_provider import PydanticAIProvider

        provider = PydanticAIProvider(model="openai:gpt-4o")
        assert provider.model == "openai:gpt-4o"
        assert provider.retries == 3

    def test_provider_name_format(self) -> None:
        """Provider name includes pydantic-ai prefix."""
        from experiments.castro.generator.pydantic_ai_provider import PydanticAIProvider

        provider = PydanticAIProvider(model="anthropic:claude-3-5-sonnet-20241022")
        assert provider.name == "pydantic-ai:anthropic:claude-3-5-sonnet-20241022"

    def test_provider_from_config(self) -> None:
        """Provider can be created from config."""
        from experiments.castro.generator.pydantic_ai_provider import (
            PydanticAIProvider,
            PydanticAIConfig,
        )

        config = PydanticAIConfig.openai("gpt-4o-mini")
        provider = PydanticAIProvider.from_config(config)
        assert provider.model == "openai:gpt-4o-mini"


class TestConvenienceFunctions:
    """Tests for convenience provider factory functions."""

    def test_openai_provider_factory(self) -> None:
        """openai_provider creates correct provider."""
        from experiments.castro.generator.pydantic_ai_provider import openai_provider

        provider = openai_provider("gpt-4o")
        assert provider.model == "openai:gpt-4o"

    def test_anthropic_provider_factory(self) -> None:
        """anthropic_provider creates correct provider."""
        from experiments.castro.generator.pydantic_ai_provider import anthropic_provider

        provider = anthropic_provider()
        assert "anthropic:" in provider.model

    def test_google_provider_factory(self) -> None:
        """google_provider creates correct provider."""
        from experiments.castro.generator.pydantic_ai_provider import google_provider

        provider = google_provider()
        assert "google-gla:" in provider.model

    def test_ollama_provider_factory(self) -> None:
        """ollama_provider creates correct provider."""
        from experiments.castro.generator.pydantic_ai_provider import ollama_provider

        provider = ollama_provider()
        assert "ollama:" in provider.model


class TestGetProviderWithPydanticAI:
    """Tests for get_provider with pydantic-ai option."""

    def test_get_pydantic_ai_provider(self) -> None:
        """get_provider creates PydanticAI provider."""
        from experiments.castro.generator.providers import get_provider
        from experiments.castro.generator.pydantic_ai_provider import PydanticAIProvider

        provider = get_provider("pydantic-ai", model="openai:gpt-4o")
        assert isinstance(provider, PydanticAIProvider)

    def test_get_pydantic_ai_default_model(self) -> None:
        """get_provider uses default model for pydantic-ai."""
        from experiments.castro.generator.providers import get_provider

        provider = get_provider("pydantic-ai")
        assert "openai:gpt-4o" in provider.model

    def test_get_pydantic_ai_anthropic_model(self) -> None:
        """get_provider accepts Anthropic model for pydantic-ai."""
        from experiments.castro.generator.providers import get_provider

        provider = get_provider("pydantic-ai", model="anthropic:claude-3-5-sonnet-20241022")
        assert provider.model == "anthropic:claude-3-5-sonnet-20241022"


class TestPydanticAIWithStructuredGenerator:
    """Tests for PydanticAI with StructuredPolicyGenerator."""

    def test_generator_accepts_pydantic_ai_provider(self) -> None:
        """Generator accepts PydanticAI provider."""
        from experiments.castro.generator.client import StructuredPolicyGenerator
        from experiments.castro.generator.pydantic_ai_provider import PydanticAIProvider

        provider = PydanticAIProvider(model="openai:gpt-4o")
        generator = StructuredPolicyGenerator(provider=provider)

        assert generator.provider is provider
        assert "pydantic-ai" in generator.provider.name

    def test_generator_with_provider_factory(self) -> None:
        """Generator works with get_provider factory."""
        from experiments.castro.generator.client import StructuredPolicyGenerator
        from experiments.castro.generator.providers import get_provider

        provider = get_provider("pydantic-ai", model="openai:gpt-4o")
        generator = StructuredPolicyGenerator(provider=provider)

        assert "pydantic-ai" in generator.provider.name


class TestCreatePolicyAgent:
    """Tests for create_policy_agent helper function."""

    def test_create_agent_function_exists(self) -> None:
        """create_policy_agent function is importable."""
        from experiments.castro.generator.pydantic_ai_provider import create_policy_agent

        assert callable(create_policy_agent)

    # Note: Actual agent creation requires pydantic-ai package
    # These tests verify the interface without API calls


class TestLLMProviderProtocolCompliance:
    """Tests verifying PydanticAIProvider implements LLMProvider protocol."""

    def test_provider_has_name_property(self) -> None:
        """Provider has name property."""
        from experiments.castro.generator.pydantic_ai_provider import PydanticAIProvider

        provider = PydanticAIProvider(model="openai:gpt-4o")
        assert hasattr(provider, "name")
        assert isinstance(provider.name, str)

    def test_provider_has_generate_structured_method(self) -> None:
        """Provider has generate_structured method."""
        from experiments.castro.generator.pydantic_ai_provider import PydanticAIProvider

        provider = PydanticAIProvider(model="openai:gpt-4o")
        assert hasattr(provider, "generate_structured")
        assert callable(provider.generate_structured)

    def test_provider_is_llm_provider_instance(self) -> None:
        """Provider satisfies LLMProvider protocol."""
        from experiments.castro.generator.providers import LLMProvider
        from experiments.castro.generator.pydantic_ai_provider import PydanticAIProvider

        provider = PydanticAIProvider(model="openai:gpt-4o")
        # Check it matches the protocol (duck typing)
        assert hasattr(provider, "name")
        assert hasattr(provider, "generate_structured")
