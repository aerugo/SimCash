"""Tests for PydanticAI provider integration.

These tests verify the PydanticAI provider interface and configuration
without requiring actual API calls.
"""

from __future__ import annotations

import os
from unittest import mock

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


class TestGoogleGeminiApiKey:
    """Tests for Google Gemini API key configuration."""

    def test_config_google_with_explicit_api_key(self) -> None:
        """Config accepts explicit API key for Google."""
        from experiments.castro.generator.pydantic_ai_provider import PydanticAIConfig

        config = PydanticAIConfig.google("gemini-2.0-flash", api_key="test-api-key")
        assert config.model == "google-gla:gemini-2.0-flash"
        assert config.api_key == "test-api-key"

    def test_config_google_reads_google_ai_studio_env_var(self) -> None:
        """Config reads GOOGLE_AI_STUDIO_API_KEY environment variable."""
        from experiments.castro.generator.pydantic_ai_provider import PydanticAIConfig

        with mock.patch.dict(os.environ, {"GOOGLE_AI_STUDIO_API_KEY": "env-api-key"}):
            config = PydanticAIConfig.google("gemini-2.0-flash")
            assert config.api_key == "env-api-key"

    def test_config_google_reads_gemini_env_var_fallback(self) -> None:
        """Config reads GEMINI_API_KEY as fallback."""
        from experiments.castro.generator.pydantic_ai_provider import PydanticAIConfig

        with mock.patch.dict(
            os.environ,
            {"GEMINI_API_KEY": "gemini-env-key"},
            clear=True,
        ):
            # Remove GOOGLE_AI_STUDIO_API_KEY if present
            os.environ.pop("GOOGLE_AI_STUDIO_API_KEY", None)
            config = PydanticAIConfig.google("gemini-2.0-flash")
            assert config.api_key == "gemini-env-key"

    def test_config_google_prefers_google_ai_studio_over_gemini_key(self) -> None:
        """GOOGLE_AI_STUDIO_API_KEY takes precedence over GEMINI_API_KEY."""
        from experiments.castro.generator.pydantic_ai_provider import PydanticAIConfig

        with mock.patch.dict(
            os.environ,
            {
                "GOOGLE_AI_STUDIO_API_KEY": "studio-key",
                "GEMINI_API_KEY": "gemini-key",
            },
        ):
            config = PydanticAIConfig.google("gemini-2.0-flash")
            assert config.api_key == "studio-key"

    def test_provider_google_with_explicit_api_key(self) -> None:
        """Provider accepts explicit API key for Google models."""
        from experiments.castro.generator.pydantic_ai_provider import PydanticAIProvider

        provider = PydanticAIProvider(
            model="google-gla:gemini-2.0-flash",
            api_key="test-provider-key",
        )
        assert provider.model == "google-gla:gemini-2.0-flash"
        assert provider._api_key == "test-provider-key"

    def test_provider_google_reads_env_var(self) -> None:
        """Provider reads GOOGLE_AI_STUDIO_API_KEY for Google models."""
        from experiments.castro.generator.pydantic_ai_provider import PydanticAIProvider

        with mock.patch.dict(os.environ, {"GOOGLE_AI_STUDIO_API_KEY": "env-provider-key"}):
            provider = PydanticAIProvider(model="google-gla:gemini-2.0-flash")
            assert provider._api_key == "env-provider-key"

    def test_provider_non_google_ignores_api_key(self) -> None:
        """Non-Google providers don't use the Google API key env var."""
        from experiments.castro.generator.pydantic_ai_provider import PydanticAIProvider

        with mock.patch.dict(os.environ, {"GOOGLE_AI_STUDIO_API_KEY": "should-not-use"}):
            provider = PydanticAIProvider(model="openai:gpt-4o")
            # Should not have picked up the Google API key
            assert provider._api_key is None

    def test_google_provider_factory_with_api_key(self) -> None:
        """google_provider factory accepts API key."""
        from experiments.castro.generator.pydantic_ai_provider import google_provider

        provider = google_provider("gemini-2.0-flash", api_key="factory-key")
        assert "google-gla:" in provider.model
        assert provider._api_key == "factory-key"

    def test_google_provider_factory_reads_env_var(self) -> None:
        """google_provider factory reads env var when no key provided."""
        from experiments.castro.generator.pydantic_ai_provider import google_provider

        with mock.patch.dict(os.environ, {"GOOGLE_AI_STUDIO_API_KEY": "factory-env-key"}):
            provider = google_provider("gemini-2.0-flash")
            assert provider._api_key == "factory-env-key"


class TestRobustPolicyAgentGoogleSupport:
    """Tests for Google Gemini support in RobustPolicyAgent."""

    def test_agent_accepts_google_model(self) -> None:
        """RobustPolicyAgent accepts Google model string."""
        from experiments.castro.generator.robust_policy_agent import RobustPolicyAgent
        from experiments.castro.schemas.parameter_config import (
            ParameterSpec,
            ScenarioConstraints,
        )

        constraints = ScenarioConstraints(
            allowed_parameters=[
                ParameterSpec(
                    name="urgency",
                    min_value=0,
                    max_value=20,
                    default=3,
                    description="Urgency",
                )
            ],
            allowed_fields=["balance"],
            allowed_actions=["Release", "Hold"],
        )

        agent = RobustPolicyAgent(
            constraints=constraints,
            model="google-gla:gemini-2.0-flash",
            api_key="test-agent-key",
        )
        assert agent.model == "google-gla:gemini-2.0-flash"
        assert agent._api_key == "test-agent-key"

    def test_agent_reads_google_env_var(self) -> None:
        """RobustPolicyAgent reads GOOGLE_AI_STUDIO_API_KEY env var."""
        from experiments.castro.generator.robust_policy_agent import RobustPolicyAgent
        from experiments.castro.schemas.parameter_config import (
            ParameterSpec,
            ScenarioConstraints,
        )

        constraints = ScenarioConstraints(
            allowed_parameters=[
                ParameterSpec(
                    name="urgency",
                    min_value=0,
                    max_value=20,
                    default=3,
                    description="Urgency",
                )
            ],
            allowed_fields=["balance"],
            allowed_actions=["Release", "Hold"],
        )

        with mock.patch.dict(os.environ, {"GOOGLE_AI_STUDIO_API_KEY": "agent-env-key"}):
            agent = RobustPolicyAgent(
                constraints=constraints,
                model="google-gla:gemini-2.0-flash",
            )
            assert agent._api_key == "agent-env-key"

    def test_agent_non_google_ignores_api_key(self) -> None:
        """RobustPolicyAgent with non-Google model ignores Google API key."""
        from experiments.castro.generator.robust_policy_agent import RobustPolicyAgent
        from experiments.castro.schemas.parameter_config import (
            ParameterSpec,
            ScenarioConstraints,
        )

        constraints = ScenarioConstraints(
            allowed_parameters=[
                ParameterSpec(
                    name="urgency",
                    min_value=0,
                    max_value=20,
                    default=3,
                    description="Urgency",
                )
            ],
            allowed_fields=["balance"],
            allowed_actions=["Release", "Hold"],
        )

        with mock.patch.dict(os.environ, {"GOOGLE_AI_STUDIO_API_KEY": "should-not-use"}):
            agent = RobustPolicyAgent(
                constraints=constraints,
                model="openai:gpt-4o",
            )
            # Should not have picked up the Google API key automatically
            assert agent._api_key is None
