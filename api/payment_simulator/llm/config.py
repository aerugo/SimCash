"""Unified LLM configuration.

This module defines the LLMConfig dataclass that provides unified
configuration for all LLM providers (Anthropic, OpenAI, etc.).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class LLMConfig:
    """Unified LLM configuration.

    Supports multiple LLM providers with provider-specific options.
    All fields are immutable (frozen dataclass) for safety.

    The model string uses the format "provider:model_name", e.g.:
    - "anthropic:claude-sonnet-4-5"
    - "openai:gpt-4o"
    - "openai:o1"

    Example:
        >>> config = LLMConfig(
        ...     model="anthropic:claude-sonnet-4-5",
        ...     thinking_budget=8000,
        ... )
        >>> config.provider
        'anthropic'
        >>> config.model_name
        'claude-sonnet-4-5'

    Attributes:
        model: Model specification in provider:model format.
        temperature: Sampling temperature (default 0.0 for determinism).
        max_retries: Maximum retry attempts on failure (default 3).
        timeout_seconds: Request timeout in seconds (default 120).
        thinking_budget: Anthropic extended thinking budget tokens.
        reasoning_effort: OpenAI reasoning effort level (low/medium/high).
    """

    # Model specification in provider:model format
    model: str

    # Common settings
    temperature: float = 0.0
    max_retries: int = 3
    timeout_seconds: int = 120

    # Provider-specific options (mutually exclusive by convention)
    thinking_budget: int | None = None  # Anthropic extended thinking
    reasoning_effort: str | None = None  # OpenAI: low, medium, high

    @property
    def provider(self) -> str:
        """Extract provider from model string.

        Returns:
            Provider name (e.g., "anthropic", "openai").
        """
        return self.model.split(":")[0]

    @property
    def model_name(self) -> str:
        """Extract model name from model string.

        Returns:
            Model name (e.g., "claude-sonnet-4-5", "gpt-4o").
        """
        return self.model.split(":", 1)[1]
