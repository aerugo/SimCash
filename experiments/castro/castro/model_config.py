"""Model configuration for PydanticAI.

Provides a unified configuration for LLM models using the provider:model
string pattern supported by PydanticAI.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ModelConfig:
    """Configuration for PydanticAI model.

    Uses provider:model string format for unified model selection.
    Supports provider-specific reasoning/thinking settings.

    Supported Providers:
        - anthropic: Claude models (claude-sonnet-4-5, etc.)
        - openai: GPT models (gpt-5.1, gpt-4.1, etc.)
        - google: Gemini models (gemini-2.5-flash, etc.)

    Examples:
        >>> # Basic Anthropic model
        >>> config = ModelConfig("anthropic:claude-sonnet-4-5")

        >>> # OpenAI with high reasoning effort
        >>> config = ModelConfig("openai:gpt-5.1", reasoning_effort="high")

        >>> # Anthropic with extended thinking
        >>> config = ModelConfig(
        ...     "anthropic:claude-sonnet-4-5",
        ...     thinking_budget=8000,
        ... )

        >>> # Google Gemini with thinking
        >>> config = ModelConfig(
        ...     "google:gemini-2.5-flash",
        ...     thinking_config={"thinking_budget": 8000},
        ... )
    """

    model: str
    """Model string in provider:model format (e.g., 'anthropic:claude-sonnet-4-5')."""

    temperature: float = 0.0
    """Sampling temperature (0.0 = deterministic, higher = more creative)."""

    max_tokens: int = 4096
    """Maximum tokens in the response."""

    # Provider-specific settings
    thinking_budget: int | None = None
    """Token budget for Anthropic extended thinking (Claude only)."""

    reasoning_effort: str | None = None
    """OpenAI reasoning effort: 'low', 'medium', or 'high' (GPT models only)."""

    thinking_config: dict[str, Any] | None = None
    """Google Gemini thinking configuration."""

    max_retries: int = 3
    """Maximum retry attempts on validation failure."""

    timeout_seconds: int = 120
    """Request timeout in seconds."""

    @property
    def provider(self) -> str:
        """Extract provider from model string.

        Returns:
            Provider name (e.g., 'anthropic', 'openai', 'google').
            Defaults to 'anthropic' if no colon in model string.
        """
        if ":" in self.model:
            return self.model.split(":")[0]
        # Legacy support: infer provider from model name
        return _infer_provider(self.model)

    @property
    def model_name(self) -> str:
        """Extract model name from model string.

        Returns:
            Model name without provider prefix.
        """
        if ":" in self.model:
            return self.model.split(":", 1)[1]
        return self.model

    @property
    def full_model_string(self) -> str:
        """Get the full provider:model string for PydanticAI.

        Maps provider aliases to PydanticAI's expected names:
        - google -> google-gla (Google AI Language API)

        Returns:
            Full model string in provider:model format.
        """
        if ":" in self.model:
            provider, model_name = self.model.split(":", 1)
            # Map google alias to google-gla
            if provider == "google":
                return f"google-gla:{model_name}"
            return self.model
        inferred = _infer_provider(self.model)
        if inferred == "google":
            inferred = "google-gla"
        return f"{inferred}:{self.model}"

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
                settings["max_tokens"] = max(self.max_tokens, 16384)
        elif provider == "google" and self.thinking_config:
            # Google Gemini thinking config
            settings["google_thinking_config"] = self.thinking_config

        return settings


def _infer_provider(model_name: str) -> str:
    """Infer provider from model name for legacy support.

    Args:
        model_name: Model name without provider prefix.

    Returns:
        Inferred provider name.
    """
    model_lower = model_name.lower()

    # OpenAI models
    if any(
        model_lower.startswith(prefix)
        for prefix in ("gpt-", "o1", "o3", "davinci", "curie")
    ):
        return "openai"

    # Google models
    if any(model_lower.startswith(prefix) for prefix in ("gemini", "palm")):
        return "google"

    # Default to Anthropic
    return "anthropic"


@dataclass
class ModelConfigDefaults:
    """Default model configurations for common providers.

    Provides sensible defaults for each provider that can be used
    as starting points or for quick experimentation.
    """

    # Anthropic defaults
    ANTHROPIC_SONNET: ModelConfig = field(
        default_factory=lambda: ModelConfig("anthropic:claude-sonnet-4-5")
    )

    ANTHROPIC_SONNET_THINKING: ModelConfig = field(
        default_factory=lambda: ModelConfig(
            "anthropic:claude-sonnet-4-5",
            thinking_budget=8000,
        )
    )

    # OpenAI defaults
    OPENAI_GPT5: ModelConfig = field(
        default_factory=lambda: ModelConfig(
            "openai:gpt-5.1",
            reasoning_effort="high",
        )
    )

    OPENAI_GPT4: ModelConfig = field(
        default_factory=lambda: ModelConfig("openai:gpt-4.1")
    )

    # Google defaults
    GOOGLE_GEMINI: ModelConfig = field(
        default_factory=lambda: ModelConfig("google:gemini-2.5-flash")
    )


# Convenience function for creating configs
def create_model_config(
    model: str,
    *,
    temperature: float = 0.0,
    thinking_budget: int | None = None,
    reasoning_effort: str | None = None,
) -> ModelConfig:
    """Create a ModelConfig with common options.

    A convenience function for creating model configurations
    with the most commonly used options.

    Args:
        model: Model string in provider:model format.
        temperature: Sampling temperature.
        thinking_budget: Anthropic thinking token budget.
        reasoning_effort: OpenAI reasoning effort level.

    Returns:
        Configured ModelConfig instance.

    Examples:
        >>> config = create_model_config("anthropic:claude-sonnet-4-5")
        >>> config = create_model_config("openai:gpt-5.1", reasoning_effort="high")
    """
    return ModelConfig(
        model=model,
        temperature=temperature,
        thinking_budget=thinking_budget,
        reasoning_effort=reasoning_effort,
    )
