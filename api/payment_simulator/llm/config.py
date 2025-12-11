"""Unified LLM configuration.

This module defines the LLMConfig dataclass that provides unified
configuration for all LLM providers (Anthropic, OpenAI, Google).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class LLMConfig:
    """Unified LLM configuration.

    Supports multiple LLM providers with provider-specific options.
    All fields are immutable (frozen dataclass) for safety.

    The model string uses the format "provider:model_name", e.g.:
    - "anthropic:claude-sonnet-4-5"
    - "openai:gpt-4o"
    - "openai:o1"
    - "google:gemini-2.5-flash"

    Example:
        >>> config = LLMConfig(
        ...     model="anthropic:claude-sonnet-4-5",
        ...     thinking_budget=8000,
        ... )
        >>> config.provider
        'anthropic'
        >>> config.model_name
        'claude-sonnet-4-5'
        >>> config.full_model_string
        'anthropic:claude-sonnet-4-5'

    Attributes:
        model: Model specification in provider:model format.
        temperature: Sampling temperature (default 0.0 for determinism).
        max_retries: Maximum retry attempts on failure (default 3).
        timeout_seconds: Request timeout in seconds (default 120).
        max_tokens: Maximum tokens in the response (default 30000).
        thinking_budget: Anthropic extended thinking budget tokens.
        reasoning_effort: OpenAI reasoning effort level (low/medium/high).
        thinking_config: Google Gemini thinking configuration.
    """

    # Model specification in provider:model format
    model: str

    # Common settings
    temperature: float = 0.0
    max_retries: int = 3
    timeout_seconds: int = 120
    max_tokens: int = 30000

    # Provider-specific options (mutually exclusive by convention)
    thinking_budget: int | None = None  # Anthropic extended thinking
    reasoning_effort: str | None = None  # OpenAI: low, medium, high
    thinking_config: dict[str, Any] | None = None  # Google Gemini thinking

    @property
    def provider(self) -> str:
        """Extract provider from model string.

        Returns:
            Provider name (e.g., "anthropic", "openai", "google").
        """
        return self.model.split(":")[0]

    @property
    def model_name(self) -> str:
        """Extract model name from model string.

        Returns:
            Model name (e.g., "claude-sonnet-4-5", "gpt-4o").
        """
        return self.model.split(":", 1)[1]

    @property
    def full_model_string(self) -> str:
        """Get the full provider:model string for PydanticAI.

        Maps provider aliases to PydanticAI's expected names:
        - google → google-gla (Google AI Language API)

        Returns:
            Full model string in provider:model format.
        """
        provider = self.provider
        model_name = self.model_name
        if provider == "google":
            return f"google-gla:{model_name}"
        return self.model

    def to_model_settings(self) -> dict[str, Any]:
        """Convert to PydanticAI ModelSettings dict.

        Returns model settings appropriate for the provider,
        including any thinking/reasoning configuration.

        Returns:
            Dict suitable for pydantic_ai.settings.ModelSettings.
        """
        settings: dict[str, Any] = {
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "timeout": self.timeout_seconds,
        }

        provider = self.provider

        if provider == "anthropic" and self.thinking_budget:
            # Anthropic extended thinking configuration
            settings["anthropic_thinking"] = {"budget_tokens": self.thinking_budget}
        elif provider == "openai" and self.reasoning_effort:
            # OpenAI reasoning effort (for GPT-5, o1, o3 models)
            settings["openai_reasoning_effort"] = self.reasoning_effort
            # Reasoning models need more tokens for verbose output
            if self.reasoning_effort == "high":
                settings["max_tokens"] = max(self.max_tokens, 30000)
        elif provider == "google" and self.thinking_config:
            # Google Gemini thinking config
            settings["google_thinking_config"] = self.thinking_config

        return settings
