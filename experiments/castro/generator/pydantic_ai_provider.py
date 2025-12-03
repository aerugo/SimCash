"""PydanticAI-based provider for structured policy generation.

This module provides a clean integration with PydanticAI's Agent class
for generating structured policy output. PydanticAI handles:
- Model-agnostic LLM calls (OpenAI, Anthropic, Google, Ollama, etc.)
- Automatic structured output via Pydantic models
- Retry logic and validation
- Type-safe responses

Usage:
    from experiments.castro.generator.pydantic_ai_provider import (
        PydanticAIProvider,
        create_policy_agent,
    )

    # Create provider for any supported model
    provider = PydanticAIProvider(model="openai:gpt-4o")
    # or
    provider = PydanticAIProvider(model="anthropic:claude-3-5-sonnet-20241022")

    # Use with StructuredPolicyGenerator
    generator = StructuredPolicyGenerator(provider=provider)
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, TypeVar

from pydantic import BaseModel

from experiments.castro.generator.providers import (
    LLMProvider,
    StructuredOutputRequest,
    StructuredOutputResponse,
)


T = TypeVar("T", bound=BaseModel)


@dataclass
class PydanticAIConfig:
    """Configuration for PydanticAI provider."""

    model: str
    """Model identifier in format 'provider:model', e.g. 'openai:gpt-4o'"""

    retries: int = 3
    """Number of retries on validation failure"""

    @classmethod
    def openai(cls, model: str = "gpt-4o") -> "PydanticAIConfig":
        """Create config for OpenAI."""
        return cls(model=f"openai:{model}")

    @classmethod
    def anthropic(cls, model: str = "claude-3-5-sonnet-20241022") -> "PydanticAIConfig":
        """Create config for Anthropic."""
        return cls(model=f"anthropic:{model}")

    @classmethod
    def google(cls, model: str = "gemini-1.5-pro") -> "PydanticAIConfig":
        """Create config for Google."""
        return cls(model=f"google-gla:{model}")

    @classmethod
    def ollama(cls, model: str = "llama3.1:8b") -> "PydanticAIConfig":
        """Create config for Ollama."""
        return cls(model=f"ollama:{model}")


class PydanticAIProvider:
    """LLM provider using PydanticAI Agent for structured output.

    PydanticAI provides a unified interface for multiple LLM providers
    with built-in structured output support via Pydantic models.

    Supported model formats:
        - openai:gpt-4o
        - openai:gpt-4o-mini
        - anthropic:claude-3-5-sonnet-20241022
        - anthropic:claude-3-opus-20240229
        - google-gla:gemini-1.5-pro
        - ollama:llama3.1:8b
        - groq:llama-3.1-70b-versatile

    Example:
        provider = PydanticAIProvider(model="anthropic:claude-3-5-sonnet-20241022")
        generator = StructuredPolicyGenerator(provider=provider)
        policy = generator.generate_policy("payment_tree")
    """

    def __init__(
        self,
        model: str = "openai:gpt-4o",
        retries: int = 3,
    ) -> None:
        """Initialize PydanticAI provider.

        Args:
            model: Model identifier in 'provider:model' format
            retries: Number of retries on validation failure
        """
        self.model = model
        self.retries = retries
        self._agent: Any | None = None

    @classmethod
    def from_config(cls, config: PydanticAIConfig) -> "PydanticAIProvider":
        """Create provider from config."""
        return cls(model=config.model, retries=config.retries)

    @property
    def name(self) -> str:
        """Provider name for logging."""
        return f"pydantic-ai:{self.model}"

    def _get_agent(self, output_type: type[T], system_prompt: str) -> Any:
        """Create a PydanticAI Agent for the given output type."""
        try:
            from pydantic_ai import Agent
        except ImportError:
            raise ImportError(
                "pydantic-ai package required. Install with: pip install pydantic-ai"
            )

        return Agent(
            self.model,
            output_type=output_type,
            system_prompt=system_prompt,
            retries=self.retries,
        )

    def generate_structured(
        self,
        request: StructuredOutputRequest,
    ) -> StructuredOutputResponse:
        """Generate structured output using PydanticAI Agent.

        This method creates a dynamic Pydantic model from the JSON schema
        and uses PydanticAI's Agent to generate structured output.

        Args:
            request: The structured output request

        Returns:
            Response with parsed content
        """
        try:
            from pydantic_ai import Agent
        except ImportError:
            raise ImportError(
                "pydantic-ai package required. Install with: pip install pydantic-ai"
            )

        # Create a dynamic model from JSON schema for validation
        # PydanticAI handles the schema conversion internally
        from experiments.castro.schemas.tree import get_tree_model

        # Extract max_depth from schema name (e.g., "payment_tree_schema")
        # Default to depth 3 if not specified
        max_depth = 3
        tree_type = request.schema_name.replace("_schema", "")

        # Get the appropriate tree model
        TreeModel = get_tree_model(max_depth)

        # Create agent with the tree model as output type
        agent = Agent(
            self.model,
            output_type=TreeModel,  # type: ignore
            system_prompt=request.system_prompt,
            retries=self.retries,
        )

        # Run the agent synchronously
        result = agent.run_sync(request.user_prompt)

        # Extract content - PydanticAI returns validated Pydantic model
        if hasattr(result.output, "model_dump"):
            content = result.output.model_dump(exclude_none=True)
        else:
            # For union types, it might be a dict already
            content = result.output if isinstance(result.output, dict) else {"type": "action", "action": str(result.output)}

        # Extract usage if available
        usage = None
        if hasattr(result, "usage") and result.usage:
            usage = {
                "prompt_tokens": getattr(result.usage, "request_tokens", 0),
                "completion_tokens": getattr(result.usage, "response_tokens", 0),
                "total_tokens": getattr(result.usage, "total_tokens", 0),
            }

        return StructuredOutputResponse(
            content=content,
            raw_response=result,
            usage=usage,
            model=self.model,
        )

    def generate_with_model(
        self,
        output_type: type[T],
        system_prompt: str,
        user_prompt: str,
    ) -> T:
        """Generate structured output with a specific Pydantic model.

        This is a convenience method for direct model-based generation
        without going through the StructuredOutputRequest interface.

        Args:
            output_type: Pydantic model class for output
            system_prompt: System instructions
            user_prompt: User prompt

        Returns:
            Validated Pydantic model instance
        """
        try:
            from pydantic_ai import Agent
        except ImportError:
            raise ImportError(
                "pydantic-ai package required. Install with: pip install pydantic-ai"
            )

        agent = Agent(
            self.model,
            output_type=output_type,
            system_prompt=system_prompt,
            retries=self.retries,
        )

        result = agent.run_sync(user_prompt)
        return result.output


def create_policy_agent(
    model: str = "openai:gpt-4o",
    tree_type: str = "payment_tree",
    max_depth: int = 3,
    system_prompt: str | None = None,
) -> Any:
    """Create a PydanticAI Agent configured for policy generation.

    This is a convenience function for creating an Agent directly
    with the appropriate tree model type.

    Args:
        model: Model identifier in 'provider:model' format
        tree_type: Type of policy tree to generate
        max_depth: Maximum tree depth
        system_prompt: Optional custom system prompt

    Returns:
        Configured PydanticAI Agent

    Example:
        agent = create_policy_agent(
            model="anthropic:claude-3-5-sonnet-20241022",
            tree_type="payment_tree",
        )
        result = agent.run_sync("Generate a policy that prioritizes high-value payments")
        policy = result.output.model_dump()
    """
    try:
        from pydantic_ai import Agent
    except ImportError:
        raise ImportError(
            "pydantic-ai package required. Install with: pip install pydantic-ai"
        )

    from experiments.castro.schemas.tree import get_tree_model
    from experiments.castro.prompts.templates import SYSTEM_PROMPT

    TreeModel = get_tree_model(max_depth)

    return Agent(
        model,
        output_type=TreeModel,  # type: ignore
        system_prompt=system_prompt or SYSTEM_PROMPT,
        retries=3,
    )


# Convenience aliases for common configurations
def openai_provider(model: str = "gpt-4o") -> PydanticAIProvider:
    """Create PydanticAI provider for OpenAI."""
    return PydanticAIProvider(model=f"openai:{model}")


def anthropic_provider(model: str = "claude-3-5-sonnet-20241022") -> PydanticAIProvider:
    """Create PydanticAI provider for Anthropic."""
    return PydanticAIProvider(model=f"anthropic:{model}")


def google_provider(model: str = "gemini-1.5-pro") -> PydanticAIProvider:
    """Create PydanticAI provider for Google."""
    return PydanticAIProvider(model=f"google-gla:{model}")


def ollama_provider(model: str = "llama3.1:8b") -> PydanticAIProvider:
    """Create PydanticAI provider for Ollama."""
    return PydanticAIProvider(model=f"ollama:{model}")
