"""LLM Provider Protocol and Implementations.

This module defines a provider-agnostic interface for structured output
generation. New providers can be added by implementing the LLMProvider protocol.

Supported providers:
- OpenAI (gpt-5.1, gpt-5, gpt-4o, gpt-4o-mini)
- Anthropic (claude-3.5-sonnet) - requires anthropic package
- Google (gemini-1.5-pro) - requires google-generativeai package
- Ollama (local models) - requires ollama package

Usage:
    # Use default OpenAI provider
    generator = StructuredPolicyGenerator()

    # Use specific provider
    from experiments.castro.generator.providers import AnthropicProvider
    generator = StructuredPolicyGenerator(provider=AnthropicProvider(model="claude-3-5-sonnet-20241022"))
"""

from __future__ import annotations

import json
import os
from abc import abstractmethod
from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable


@dataclass
class StructuredOutputRequest:
    """Request for structured LLM output."""

    system_prompt: str
    user_prompt: str
    json_schema: dict[str, Any]
    schema_name: str = "policy_tree"
    temperature: float = 0.7
    max_tokens: int = 150000


@dataclass
class StructuredOutputResponse:
    """Response from structured LLM output."""

    content: dict[str, Any]
    raw_response: Any | None = None
    usage: dict[str, int] | None = None
    model: str | None = None


@runtime_checkable
class LLMProvider(Protocol):
    """Protocol for LLM providers that support structured output.

    Any LLM provider that can generate JSON conforming to a schema
    should implement this protocol. This allows the policy generator
    to work with any provider without code changes.

    Example implementation:
        class MyProvider:
            def __init__(self, api_key: str):
                self.api_key = api_key

            @property
            def name(self) -> str:
                return "my_provider"

            def generate_structured(
                self,
                request: StructuredOutputRequest,
            ) -> StructuredOutputResponse:
                # Call your API here
                ...
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Provider name for logging/debugging."""
        ...

    @abstractmethod
    def generate_structured(
        self,
        request: StructuredOutputRequest,
    ) -> StructuredOutputResponse:
        """Generate structured output conforming to the given JSON schema.

        Args:
            request: The structured output request with prompts and schema

        Returns:
            Response with parsed JSON content

        Raises:
            ValueError: If the API returns invalid JSON
            Exception: Provider-specific errors
        """
        ...


class OpenAIProvider:
    """OpenAI provider using structured output (json_schema mode).

    Requires the openai package: pip install openai

    Supports models: gpt-5.1, gpt-5, gpt-4o, gpt-4o-mini
    """

    DEFAULT_MODEL = "gpt-5.1"

    def __init__(
        self,
        model: str | None = None,
        api_key: str | None = None,
    ) -> None:
        """Initialize OpenAI provider.

        Args:
            model: Model to use (default: gpt-4o-2024-08-06)
            api_key: API key (defaults to OPENAI_API_KEY env var)
        """
        self.model = model or self.DEFAULT_MODEL
        self._api_key = api_key or os.environ.get("OPENAI_API_KEY")
        self._client: Any | None = None

    @property
    def name(self) -> str:
        return f"openai:{self.model}"

    def _get_client(self) -> Any:
        """Lazily initialize OpenAI client."""
        if self._client is None:
            try:
                from openai import OpenAI

                self._client = OpenAI(api_key=self._api_key)
            except ImportError:
                raise ImportError(
                    "openai package required. Install with: pip install openai"
                )
        return self._client

    def generate_structured(
        self,
        request: StructuredOutputRequest,
    ) -> StructuredOutputResponse:
        """Generate structured output using OpenAI's json_schema mode."""
        client = self._get_client()

        messages = [
            {"role": "system", "content": request.system_prompt},
            {"role": "user", "content": request.user_prompt},
        ]

        response = client.chat.completions.create(
            model=self.model,
            messages=messages,
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": request.schema_name,
                    "strict": True,
                    "schema": request.json_schema,
                },
            },
            temperature=request.temperature,
            max_tokens=request.max_tokens,
        )

        content = response.choices[0].message.content
        if not content:
            raise ValueError("Empty response from OpenAI API")

        parsed = json.loads(content)

        usage = None
        if response.usage:
            usage = {
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens,
            }

        return StructuredOutputResponse(
            content=parsed,
            raw_response=response,
            usage=usage,
            model=self.model,
        )


class AnthropicProvider:
    """Anthropic provider using tool-based structured output.

    Requires the anthropic package: pip install anthropic

    Supports models: claude-3-5-sonnet-20241022, claude-3-opus
    """

    DEFAULT_MODEL = "claude-3-5-sonnet-20241022"

    def __init__(
        self,
        model: str | None = None,
        api_key: str | None = None,
    ) -> None:
        """Initialize Anthropic provider.

        Args:
            model: Model to use (default: claude-3-5-sonnet-20241022)
            api_key: API key (defaults to ANTHROPIC_API_KEY env var)
        """
        self.model = model or self.DEFAULT_MODEL
        self._api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        self._client: Any | None = None

    @property
    def name(self) -> str:
        return f"anthropic:{self.model}"

    def _get_client(self) -> Any:
        """Lazily initialize Anthropic client."""
        if self._client is None:
            try:
                from anthropic import Anthropic

                self._client = Anthropic(api_key=self._api_key)
            except ImportError:
                raise ImportError(
                    "anthropic package required. Install with: pip install anthropic"
                )
        return self._client

    def generate_structured(
        self,
        request: StructuredOutputRequest,
    ) -> StructuredOutputResponse:
        """Generate structured output using Anthropic's tool use.

        Note: Anthropic doesn't have native json_schema mode like OpenAI.
        We use tool use with a single tool that has the desired schema.
        """
        client = self._get_client()

        # Define a tool with our schema
        tool = {
            "name": request.schema_name,
            "description": "Generate a policy tree matching this schema",
            "input_schema": request.json_schema,
        }

        response = client.messages.create(
            model=self.model,
            max_tokens=request.max_tokens,
            system=request.system_prompt,
            tools=[tool],
            tool_choice={"type": "tool", "name": request.schema_name},
            messages=[
                {"role": "user", "content": request.user_prompt},
            ],
        )

        # Extract tool use content
        tool_use_block = None
        for block in response.content:
            if block.type == "tool_use":
                tool_use_block = block
                break

        if not tool_use_block:
            raise ValueError("No tool use in Anthropic response")

        parsed = tool_use_block.input

        usage = None
        if response.usage:
            usage = {
                "prompt_tokens": response.usage.input_tokens,
                "completion_tokens": response.usage.output_tokens,
                "total_tokens": response.usage.input_tokens
                + response.usage.output_tokens,
            }

        return StructuredOutputResponse(
            content=parsed,
            raw_response=response,
            usage=usage,
            model=self.model,
        )


class GoogleProvider:
    """Google Gemini provider using controlled generation.

    Requires the google-generativeai package: pip install google-generativeai

    Supports models: gemini-1.5-pro, gemini-1.5-flash
    """

    DEFAULT_MODEL = "gemini-1.5-pro"

    def __init__(
        self,
        model: str | None = None,
        api_key: str | None = None,
    ) -> None:
        """Initialize Google provider.

        Args:
            model: Model to use (default: gemini-1.5-pro)
            api_key: API key (defaults to GOOGLE_API_KEY env var)
        """
        self.model = model or self.DEFAULT_MODEL
        self._api_key = api_key or os.environ.get("GOOGLE_API_KEY")
        self._client: Any | None = None

    @property
    def name(self) -> str:
        return f"google:{self.model}"

    def _get_client(self) -> Any:
        """Lazily initialize Google client."""
        if self._client is None:
            try:
                import google.generativeai as genai

                genai.configure(api_key=self._api_key)
                self._client = genai.GenerativeModel(self.model)
            except ImportError:
                raise ImportError(
                    "google-generativeai package required. "
                    "Install with: pip install google-generativeai"
                )
        return self._client

    def generate_structured(
        self,
        request: StructuredOutputRequest,
    ) -> StructuredOutputResponse:
        """Generate structured output using Gemini's controlled generation."""
        client = self._get_client()

        # Combine prompts for Gemini
        full_prompt = f"{request.system_prompt}\n\n{request.user_prompt}"

        # Use JSON mode with schema hint in prompt
        generation_config = {
            "temperature": request.temperature,
            "max_output_tokens": request.max_tokens,
            "response_mime_type": "application/json",
        }

        # Add schema context to prompt
        schema_hint = (
            f"\n\nYou must respond with valid JSON matching this schema:\n"
            f"```json\n{json.dumps(request.json_schema, indent=2)}\n```"
        )

        response = client.generate_content(
            full_prompt + schema_hint,
            generation_config=generation_config,
        )

        content = response.text
        if not content:
            raise ValueError("Empty response from Google API")

        parsed = json.loads(content)

        usage = None
        if hasattr(response, "usage_metadata"):
            usage = {
                "prompt_tokens": response.usage_metadata.prompt_token_count,
                "completion_tokens": response.usage_metadata.candidates_token_count,
                "total_tokens": response.usage_metadata.total_token_count,
            }

        return StructuredOutputResponse(
            content=parsed,
            raw_response=response,
            usage=usage,
            model=self.model,
        )


class OllamaProvider:
    """Ollama provider for local LLM inference.

    Requires the ollama package: pip install ollama

    Supports any model with JSON mode capability.
    """

    DEFAULT_MODEL = "llama3.1:8b"

    def __init__(
        self,
        model: str | None = None,
        host: str | None = None,
    ) -> None:
        """Initialize Ollama provider.

        Args:
            model: Model to use (default: llama3.1:8b)
            host: Ollama host URL (defaults to http://localhost:11434)
        """
        self.model = model or self.DEFAULT_MODEL
        self.host = host or os.environ.get("OLLAMA_HOST", "http://localhost:11434")
        self._client: Any | None = None

    @property
    def name(self) -> str:
        return f"ollama:{self.model}"

    def _get_client(self) -> Any:
        """Lazily initialize Ollama client."""
        if self._client is None:
            try:
                import ollama

                self._client = ollama.Client(host=self.host)
            except ImportError:
                raise ImportError(
                    "ollama package required. Install with: pip install ollama"
                )
        return self._client

    def generate_structured(
        self,
        request: StructuredOutputRequest,
    ) -> StructuredOutputResponse:
        """Generate structured output using Ollama's JSON mode."""
        client = self._get_client()

        # Combine prompts and add schema context
        full_prompt = (
            f"{request.system_prompt}\n\n"
            f"{request.user_prompt}\n\n"
            f"Respond with valid JSON matching this schema:\n"
            f"```json\n{json.dumps(request.json_schema, indent=2)}\n```"
        )

        response = client.generate(
            model=self.model,
            prompt=full_prompt,
            format="json",
            options={
                "temperature": request.temperature,
                "num_predict": request.max_tokens,
            },
        )

        content = response.get("response", "")
        if not content:
            raise ValueError("Empty response from Ollama")

        parsed = json.loads(content)

        usage = None
        if "prompt_eval_count" in response:
            usage = {
                "prompt_tokens": response.get("prompt_eval_count", 0),
                "completion_tokens": response.get("eval_count", 0),
                "total_tokens": (
                    response.get("prompt_eval_count", 0) + response.get("eval_count", 0)
                ),
            }

        return StructuredOutputResponse(
            content=parsed,
            raw_response=response,
            usage=usage,
            model=self.model,
        )


def get_provider(
    provider_type: str = "openai",
    model: str | None = None,
    **kwargs: Any,
) -> LLMProvider:
    """Factory function to create a provider by name.

    Args:
        provider_type: One of "openai", "anthropic", "google", "ollama", "pydantic-ai"
        model: Model name (optional, uses provider default)
            For pydantic-ai, use format "provider:model" like "openai:gpt-4o"
        **kwargs: Additional provider-specific arguments

    Returns:
        Configured LLMProvider instance

    Raises:
        ValueError: If provider_type is unknown

    Example:
        # Direct provider
        provider = get_provider("anthropic", model="claude-3-5-sonnet-20241022")

        # PydanticAI (recommended for multi-provider support)
        provider = get_provider("pydantic-ai", model="anthropic:claude-3-5-sonnet-20241022")
        generator = StructuredPolicyGenerator(provider=provider)
    """
    # Handle pydantic-ai specially since it uses a different model format
    if provider_type == "pydantic-ai":
        from experiments.castro.generator.pydantic_ai_provider import PydanticAIProvider

        # For pydantic-ai, model should be in format "provider:model"
        # Default to openai:gpt-4o if not specified
        pydantic_model = model or "openai:gpt-4o"
        return PydanticAIProvider(model=pydantic_model, **kwargs)

    providers: dict[str, type[LLMProvider]] = {
        "openai": OpenAIProvider,
        "anthropic": AnthropicProvider,
        "google": GoogleProvider,
        "ollama": OllamaProvider,
    }

    if provider_type not in providers:
        available = ", ".join(list(providers.keys()) + ["pydantic-ai"])
        raise ValueError(f"Unknown provider: {provider_type}. Available: {available}")

    return providers[provider_type](model=model, **kwargs)
