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

    api_key: str | None = None
    """Optional API key (provider-specific). If not provided, uses environment variables."""

    @classmethod
    def openai(cls, model: str = "gpt-4o") -> "PydanticAIConfig":
        """Create config for OpenAI."""
        return cls(model=f"openai:{model}")

    @classmethod
    def anthropic(cls, model: str = "claude-3-5-sonnet-20241022") -> "PydanticAIConfig":
        """Create config for Anthropic."""
        return cls(model=f"anthropic:{model}")

    @classmethod
    def google(
        cls,
        model: str = "gemini-1.5-pro",
        api_key: str | None = None,
    ) -> "PydanticAIConfig":
        """Create config for Google Gemini (Google AI Studio / GLA).

        Args:
            model: Gemini model name (e.g., 'gemini-1.5-pro', 'gemini-2.0-flash')
            api_key: API key for Google AI Studio. If not provided, reads from
                     GOOGLE_AI_STUDIO_API_KEY or GEMINI_API_KEY environment variables.

        Returns:
            PydanticAIConfig for Google Gemini model
        """
        resolved_api_key = api_key or os.environ.get(
            "GOOGLE_AI_STUDIO_API_KEY"
        ) or os.environ.get("GEMINI_API_KEY")
        return cls(model=f"google-gla:{model}", api_key=resolved_api_key)

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
        - google-gla:gemini-2.0-flash
        - ollama:llama3.1:8b
        - groq:llama-3.1-70b-versatile

    Example:
        provider = PydanticAIProvider(model="anthropic:claude-3-5-sonnet-20241022")
        generator = StructuredPolicyGenerator(provider=provider)
        policy = generator.generate_policy("payment_tree")

        # Using Google Gemini with explicit API key:
        provider = PydanticAIProvider(
            model="google-gla:gemini-2.0-flash",
            api_key=os.environ.get("GOOGLE_AI_STUDIO_API_KEY"),
        )
    """

    def __init__(
        self,
        model: str = "openai:gpt-4o",
        retries: int = 3,
        api_key: str | None = None,
    ) -> None:
        """Initialize PydanticAI provider.

        Args:
            model: Model identifier in 'provider:model' format
            retries: Number of retries on validation failure
            api_key: Optional API key (used for Google Gemini models).
                     If not provided for Google models, reads from
                     GOOGLE_AI_STUDIO_API_KEY or GEMINI_API_KEY env vars.
        """
        self.model = model
        self.retries = retries
        self._api_key = api_key
        self._agent: Any | None = None

        # For Google models, resolve API key from environment if not provided
        if model.startswith("google-gla:") and not self._api_key:
            self._api_key = os.environ.get(
                "GOOGLE_AI_STUDIO_API_KEY"
            ) or os.environ.get("GEMINI_API_KEY")

    @classmethod
    def from_config(cls, config: PydanticAIConfig) -> "PydanticAIProvider":
        """Create provider from config."""
        return cls(model=config.model, retries=config.retries, api_key=config.api_key)

    @property
    def name(self) -> str:
        """Provider name for logging."""
        return f"pydantic-ai:{self.model}"

    def _get_model(self) -> Any:
        """Create the appropriate model instance for PydanticAI.

        For Google models, creates a GoogleModel with explicit API key configuration.
        For other models, returns the model string for automatic provider detection.
        """
        if self.model.startswith("google-gla:") and self._api_key:
            try:
                from pydantic_ai.models.google import GoogleModel
                from pydantic_ai.providers.google import GoogleProvider
            except ImportError:
                raise ImportError(
                    "pydantic-ai[google] required. Install with: "
                    "pip install 'pydantic-ai[google]'"
                )

            # Extract the model name after 'google-gla:'
            model_name = self.model.split(":", 1)[1]
            provider = GoogleProvider(api_key=self._api_key)
            return GoogleModel(model_name, provider=provider)

        # For other providers, use the string format for automatic detection
        return self.model

    def _get_agent(self, output_type: type[T], system_prompt: str) -> Any:
        """Create a PydanticAI Agent for the given output type."""
        try:
            from pydantic_ai import Agent
        except ImportError:
            raise ImportError(
                "pydantic-ai package required. Install with: pip install pydantic-ai"
            )

        model = self._get_model()
        return Agent(
            model,
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

        # Get the model instance (handles Google API key configuration)
        model = self._get_model()

        # Create agent with the tree model as output type
        agent = Agent(
            model,
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

        # Get the model instance (handles Google API key configuration)
        model = self._get_model()

        agent = Agent(
            model,
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


def google_provider(
    model: str = "gemini-1.5-pro",
    api_key: str | None = None,
) -> PydanticAIProvider:
    """Create PydanticAI provider for Google Gemini (Google AI Studio / GLA).

    Args:
        model: Gemini model name (e.g., 'gemini-1.5-pro', 'gemini-2.0-flash')
        api_key: API key for Google AI Studio. If not provided, reads from
                 GOOGLE_AI_STUDIO_API_KEY or GEMINI_API_KEY environment variables.

    Returns:
        Configured PydanticAIProvider for Google Gemini

    Example:
        # Using environment variable (recommended):
        # Set GOOGLE_AI_STUDIO_API_KEY=your-api-key
        provider = google_provider("gemini-2.0-flash")

        # Using explicit API key:
        provider = google_provider("gemini-2.0-flash", api_key="your-api-key")
    """
    return PydanticAIProvider(model=f"google-gla:{model}", api_key=api_key)


def ollama_provider(model: str = "llama3.1:8b") -> PydanticAIProvider:
    """Create PydanticAI provider for Ollama."""
    return PydanticAIProvider(model=f"ollama:{model}")
