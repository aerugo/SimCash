"""LLM configuration models for ai_cash_mgmt.

Defines configuration for LLM providers (OpenAI, Anthropic, Google) and
per-agent optimization settings, enabling different agents to use
different LLM models for research comparisons.
"""

from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field


class LLMProviderType(str, Enum):
    """Supported LLM providers."""

    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    GOOGLE = "google"


class ReasoningEffortType(str, Enum):
    """OpenAI reasoning effort levels for o1/o3 models."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class LLMConfig(BaseModel):
    """Configuration for an LLM provider.

    Supports OpenAI, Anthropic, and Google providers with their respective
    extended thinking/reasoning features.

    Example:
        >>> # OpenAI with reasoning
        >>> config = LLMConfig(
        ...     provider="openai",
        ...     model="gpt-5.1",
        ...     reasoning_effort="high",
        ... )

        >>> # Anthropic with thinking budget
        >>> config = LLMConfig(
        ...     provider="anthropic",
        ...     model="claude-sonnet-4-5-20250929",
        ...     thinking_budget=10000,
        ... )
    """

    provider: LLMProviderType | str = Field(
        default="openai",
        description="LLM provider (openai, anthropic, google)",
    )
    model: str = Field(
        default="gpt-4.1",
        description="Model identifier",
    )
    reasoning_effort: Literal["low", "medium", "high"] | None = Field(
        default=None,
        description="Reasoning effort level for OpenAI o1/o3 models",
    )
    thinking_budget: int | None = Field(
        default=None,
        ge=1,
        description="Token budget for extended thinking (Anthropic Claude only)",
    )
    temperature: float = Field(
        default=0.0,
        ge=0.0,
        le=2.0,
        description="Sampling temperature (0 for deterministic)",
    )
    max_retries: int = Field(
        default=3,
        ge=1,
        le=10,
        description="Max retries on validation failure",
    )
    timeout_seconds: int = Field(
        default=120,
        ge=10,
        le=600,
        description="Request timeout in seconds",
    )

    model_config = {"use_enum_values": True}


class AgentOptimizationConfig(BaseModel):
    """Per-agent optimization configuration.

    Allows different agents to use different LLM models/providers,
    enabling research comparing model performance on the same scenario.

    Example:
        >>> # Agent with specific LLM
        >>> config = AgentOptimizationConfig(
        ...     llm_config=LLMConfig(
        ...         provider="anthropic",
        ...         model="claude-sonnet-4-5-20250929",
        ...     )
        ... )

        >>> # Agent using default LLM (llm_config=None)
        >>> config = AgentOptimizationConfig()
    """

    llm_config: LLMConfig | None = Field(
        default=None,
        description="LLM config for this agent. If None, uses default_llm_config.",
    )

    # Future: per-agent convergence criteria, constraints, etc.
