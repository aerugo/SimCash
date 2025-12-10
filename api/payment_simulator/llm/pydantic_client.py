"""PydanticAI-based LLM client implementation.

This module provides the PydanticAILLMClient which uses PydanticAI
to interact with LLM providers and generate structured output.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, TypeVar

from pydantic_ai import Agent

from payment_simulator.llm.config import LLMConfig

if TYPE_CHECKING:
    from pydantic import BaseModel

T = TypeVar("T", bound="BaseModel")


class PydanticAILLMClient:
    """LLM client using PydanticAI for structured output.

    Implements LLMClientProtocol. Uses PydanticAI's Agent abstraction
    to handle LLM interactions and structured output parsing.

    Example:
        >>> config = LLMConfig(model="anthropic:claude-sonnet-4-5")
        >>> client = PydanticAILLMClient(config)
        >>> result = await client.generate_text("Hello, world!")
        'Hello! How can I help you today?'

    Attributes:
        _config: The LLM configuration.
    """

    def __init__(self, config: LLMConfig) -> None:
        """Initialize with configuration.

        Args:
            config: LLM configuration specifying model and settings.
        """
        self._config = config

    async def generate_structured_output(
        self,
        prompt: str,
        response_model: type[T],
        system_prompt: str | None = None,
    ) -> T:
        """Generate structured output from LLM.

        Uses PydanticAI to parse the LLM response into the specified
        Pydantic model type.

        Args:
            prompt: The user prompt to send to the LLM.
            response_model: Pydantic model type to parse response into.
            system_prompt: Optional system prompt for context.

        Returns:
            Instance of response_model populated by the LLM.

        Raises:
            Various PydanticAI exceptions on failure.
        """
        agent: Agent[None, T] = Agent(
            model=self._config.model,
            result_type=response_model,
            system_prompt=system_prompt or "",
        )
        result = await agent.run(prompt)
        return result.data

    async def generate_text(
        self,
        prompt: str,
        system_prompt: str | None = None,
    ) -> str:
        """Generate plain text from LLM.

        Args:
            prompt: The user prompt to send to the LLM.
            system_prompt: Optional system prompt for context.

        Returns:
            Plain text response from the LLM.

        Raises:
            Various PydanticAI exceptions on failure.
        """
        agent: Agent[None, str] = Agent(
            model=self._config.model,
            result_type=str,
            system_prompt=system_prompt or "",
        )
        result = await agent.run(prompt)
        return result.data
