"""Tests for LLM provider interface and implementations.

These tests verify the provider protocol and mock implementations
without requiring actual API calls.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest

from experiments.castro.generator.client import (
    GenerationResult,
    PolicyContext,
    StructuredPolicyGenerator,
)
from experiments.castro.generator.providers import (
    AnthropicProvider,
    GoogleProvider,
    LLMProvider,
    OllamaProvider,
    OpenAIProvider,
    StructuredOutputRequest,
    StructuredOutputResponse,
    get_provider,
)


class TestStructuredOutputRequest:
    """Test StructuredOutputRequest dataclass."""

    def test_request_creation(self) -> None:
        """Request can be created with all fields."""
        request = StructuredOutputRequest(
            system_prompt="You are a helpful assistant.",
            user_prompt="Generate a policy",
            json_schema={"type": "object"},
        )

        assert request.system_prompt == "You are a helpful assistant."
        assert request.user_prompt == "Generate a policy"
        assert request.json_schema == {"type": "object"}
        assert request.schema_name == "policy_tree"  # default
        assert request.temperature == 0.7  # default
        assert request.max_tokens == 50000  # default

    def test_request_custom_values(self) -> None:
        """Request accepts custom values."""
        request = StructuredOutputRequest(
            system_prompt="System",
            user_prompt="User",
            json_schema={},
            schema_name="custom_schema",
            temperature=0.5,
            max_tokens=50000,
        )

        assert request.schema_name == "custom_schema"
        assert request.temperature == 0.5
        assert request.max_tokens == 50000


class TestStructuredOutputResponse:
    """Test StructuredOutputResponse dataclass."""

    def test_response_creation(self) -> None:
        """Response can be created with content."""
        response = StructuredOutputResponse(
            content={"type": "action", "action": "Hold"},
        )

        assert response.content == {"type": "action", "action": "Hold"}
        assert response.raw_response is None
        assert response.usage is None
        assert response.model is None

    def test_response_with_metadata(self) -> None:
        """Response can include metadata."""
        response = StructuredOutputResponse(
            content={"type": "action"},
            raw_response={"id": "123"},
            usage={"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150},
            model="gpt-4o",
        )

        assert response.usage["total_tokens"] == 150
        assert response.model == "gpt-4o"


class MockProvider:
    """Mock provider for testing."""

    def __init__(self, response_content: dict[str, Any] | None = None):
        self._response_content = response_content or {
            "type": "action",
            "action": "Release",
            "parameters": {},
        }
        self.call_count = 0
        self.last_request: StructuredOutputRequest | None = None

    @property
    def name(self) -> str:
        return "mock:test"

    def generate_structured(
        self,
        request: StructuredOutputRequest,
    ) -> StructuredOutputResponse:
        self.call_count += 1
        self.last_request = request
        return StructuredOutputResponse(
            content=self._response_content,
            usage={"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150},
            model="mock-model",
        )


class TestLLMProviderProtocol:
    """Test LLMProvider protocol compliance."""

    def test_mock_provider_implements_protocol(self) -> None:
        """Mock provider implements the protocol."""
        provider = MockProvider()

        # Should have name property
        assert provider.name == "mock:test"

        # Should have generate_structured method
        request = StructuredOutputRequest(
            system_prompt="sys",
            user_prompt="user",
            json_schema={},
        )
        response = provider.generate_structured(request)

        assert isinstance(response, StructuredOutputResponse)
        assert response.content is not None

    def test_openai_provider_has_name(self) -> None:
        """OpenAI provider has correct name format."""
        provider = OpenAIProvider(model="gpt-4o")
        assert provider.name == "openai:gpt-4o"

    def test_anthropic_provider_has_name(self) -> None:
        """Anthropic provider has correct name format."""
        provider = AnthropicProvider(model="claude-3-5-sonnet-20241022")
        assert provider.name == "anthropic:claude-3-5-sonnet-20241022"

    def test_google_provider_has_name(self) -> None:
        """Google provider has correct name format."""
        provider = GoogleProvider(model="gemini-1.5-pro")
        assert provider.name == "google:gemini-1.5-pro"

    def test_ollama_provider_has_name(self) -> None:
        """Ollama provider has correct name format."""
        provider = OllamaProvider(model="llama3.1:8b")
        assert provider.name == "ollama:llama3.1:8b"


class TestGetProvider:
    """Test get_provider factory function."""

    def test_get_openai_provider(self) -> None:
        """Factory creates OpenAI provider."""
        provider = get_provider("openai")
        assert isinstance(provider, OpenAIProvider)

    def test_get_anthropic_provider(self) -> None:
        """Factory creates Anthropic provider."""
        provider = get_provider("anthropic")
        assert isinstance(provider, AnthropicProvider)

    def test_get_google_provider(self) -> None:
        """Factory creates Google provider."""
        provider = get_provider("google")
        assert isinstance(provider, GoogleProvider)

    def test_get_ollama_provider(self) -> None:
        """Factory creates Ollama provider."""
        provider = get_provider("ollama")
        assert isinstance(provider, OllamaProvider)

    def test_get_provider_with_model(self) -> None:
        """Factory passes model to provider."""
        provider = get_provider("openai", model="gpt-4o-mini")
        assert provider.model == "gpt-4o-mini"

    def test_unknown_provider_raises_error(self) -> None:
        """Factory raises error for unknown provider."""
        with pytest.raises(ValueError, match="Unknown provider"):
            get_provider("unknown")


class TestStructuredPolicyGeneratorWithProvider:
    """Test StructuredPolicyGenerator with custom providers."""

    def test_generator_accepts_custom_provider(self) -> None:
        """Generator accepts custom provider."""
        provider = MockProvider()
        generator = StructuredPolicyGenerator(provider=provider)

        assert generator.provider is provider

    def test_generator_uses_provider_for_generation(self) -> None:
        """Generator calls provider.generate_structured."""
        provider = MockProvider()
        generator = StructuredPolicyGenerator(provider=provider)

        policy = generator.generate_policy("payment_tree")

        assert provider.call_count == 1
        assert provider.last_request is not None
        assert "payment_tree" in provider.last_request.schema_name

    def test_generator_returns_provider_content(self) -> None:
        """Generator returns content from provider response."""
        expected_policy = {
            "type": "action",
            "action": "Hold",
            "parameters": {},
        }
        provider = MockProvider(response_content=expected_policy)
        generator = StructuredPolicyGenerator(provider=provider)

        policy = generator.generate_policy("payment_tree")

        assert policy == expected_policy

    def test_generator_with_metadata_includes_provider_name(self) -> None:
        """Generation result includes provider name."""
        provider = MockProvider()
        generator = StructuredPolicyGenerator(provider=provider)

        result = generator.generate_policy_with_metadata("payment_tree")

        assert result.provider == "mock:test"
        assert result.attempts == 1
        assert result.usage is not None

    def test_with_provider_factory_method(self) -> None:
        """with_provider creates generator with specified provider type."""
        # This will fail to call API but should create the generator
        generator = StructuredPolicyGenerator.with_provider(
            "anthropic",
            model="claude-3-5-sonnet-20241022",
            max_depth=3,
        )

        assert isinstance(generator.provider, AnthropicProvider)
        assert generator.provider.model == "claude-3-5-sonnet-20241022"
        assert generator.max_depth == 3

    def test_generator_retries_on_invalid_response(self) -> None:
        """Generator retries when validation fails."""
        # First response is invalid, second is valid
        call_count = 0

        class RetryMockProvider:
            @property
            def name(self) -> str:
                return "retry-mock"

            def generate_structured(
                self, request: StructuredOutputRequest
            ) -> StructuredOutputResponse:
                nonlocal call_count
                call_count += 1
                if call_count == 1:
                    # Invalid action
                    return StructuredOutputResponse(
                        content={
                            "type": "action",
                            "action": "InvalidAction",
                            "parameters": {},
                        },
                    )
                else:
                    # Valid action
                    return StructuredOutputResponse(
                        content={
                            "type": "action",
                            "action": "Release",
                            "parameters": {},
                        },
                    )

        provider = RetryMockProvider()
        generator = StructuredPolicyGenerator(provider=provider, max_retries=3)

        policy = generator.generate_policy("payment_tree")

        assert call_count == 2
        assert policy["action"] == "Release"


class TestProviderDefaults:
    """Test default values for providers."""

    def test_openai_default_model(self) -> None:
        """OpenAI provider has sensible default model (GPT-5.1)."""
        provider = OpenAIProvider()
        assert provider.model == "gpt-5.1"

    def test_anthropic_default_model(self) -> None:
        """Anthropic provider has sensible default model."""
        provider = AnthropicProvider()
        assert provider.model == "claude-3-5-sonnet-20241022"

    def test_google_default_model(self) -> None:
        """Google provider has sensible default model."""
        provider = GoogleProvider()
        assert provider.model == "gemini-1.5-pro"

    def test_ollama_default_model(self) -> None:
        """Ollama provider has sensible default model."""
        provider = OllamaProvider()
        assert provider.model == "llama3.1:8b"


class TestProviderInitialization:
    """Test provider initialization without API calls."""

    def test_openai_lazy_client(self) -> None:
        """OpenAI client is not created until needed."""
        provider = OpenAIProvider()
        # Client should not be created yet
        assert provider._client is None

    def test_anthropic_lazy_client(self) -> None:
        """Anthropic client is not created until needed."""
        provider = AnthropicProvider()
        assert provider._client is None

    def test_google_lazy_client(self) -> None:
        """Google client is not created until needed."""
        provider = GoogleProvider()
        assert provider._client is None

    def test_ollama_lazy_client(self) -> None:
        """Ollama client is not created until needed."""
        provider = OllamaProvider()
        assert provider._client is None


class TestGenerationResult:
    """Test GenerationResult dataclass."""

    def test_result_creation(self) -> None:
        """Result can be created with required fields."""
        result = GenerationResult(
            policy={"type": "action"},
            provider="openai:gpt-4o",
            attempts=1,
        )

        assert result.policy == {"type": "action"}
        assert result.provider == "openai:gpt-4o"
        assert result.attempts == 1
        assert result.usage is None

    def test_result_with_usage(self) -> None:
        """Result can include usage stats."""
        result = GenerationResult(
            policy={},
            provider="test",
            attempts=2,
            usage={"total_tokens": 500},
        )

        assert result.usage["total_tokens"] == 500
        assert result.attempts == 2
