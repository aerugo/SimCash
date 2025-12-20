"""PydanticAI-based LLM client implementation.

This module provides the PydanticAILLMClient which uses PydanticAI
to interact with LLM providers and generate structured output.
Now supports reasoning/thinking capture for OpenAI reasoning models.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, TypeVar

from pydantic_ai import Agent

from payment_simulator.llm.config import LLMConfig
from payment_simulator.llm.result import LLMResult

if TYPE_CHECKING:
    from pydantic import BaseModel

T = TypeVar("T", bound="BaseModel")


class PydanticAILLMClient:
    """LLM client using PydanticAI for structured output.

    Implements LLMClientProtocol. Uses PydanticAI's Agent abstraction
    to handle LLM interactions and structured output parsing.

    Now supports reasoning/thinking capture for OpenAI reasoning models.
    Configure via LLMConfig.reasoning_summary to capture reasoning.

    Example:
        >>> config = LLMConfig(
        ...     model="openai:o1",
        ...     reasoning_effort="medium",
        ...     reasoning_summary="detailed",
        ... )
        >>> client = PydanticAILLMClient(config)
        >>> result = await client.generate_structured_output(prompt, PolicyModel)
        >>> result.data  # The parsed policy
        >>> result.reasoning_summary  # The LLM's reasoning (if captured)

    Attributes:
        _config: The LLM configuration.
    """

    def __init__(self, config: LLMConfig) -> None:
        """Initialize with configuration.

        Args:
            config: LLM configuration specifying model and settings.
        """
        self._config = config

    def _extract_reasoning(self, messages: list[Any]) -> str | None:
        """Extract reasoning/thinking content from messages.

        Iterates through all messages and parts, extracting content from
        ThinkingPart objects. Multiple thinking parts are concatenated
        with double newlines.

        Args:
            messages: List of messages from agent.run() result.

        Returns:
            Concatenated reasoning content, or None if no thinking parts found.
        """
        reasoning_parts: list[str] = []

        for message in messages:
            if not hasattr(message, "parts"):
                continue
            for part in message.parts:
                # Check for ThinkingPart by class name (avoids import issues)
                if part.__class__.__name__ == "ThinkingPart":
                    content = getattr(part, "content", None)
                    if content:
                        reasoning_parts.append(str(content))

        if not reasoning_parts:
            return None
        return "\n\n".join(reasoning_parts)

    async def generate_structured_output(
        self,
        prompt: str,
        response_model: type[T],
        system_prompt: str | None = None,
    ) -> LLMResult[T]:
        """Generate structured output from LLM.

        Uses PydanticAI to parse the LLM response into the specified
        Pydantic model type. If reasoning is configured, extracts
        thinking content from the response.

        Args:
            prompt: The user prompt to send to the LLM.
            response_model: Pydantic model type to parse response into.
            system_prompt: Optional system prompt for context.

        Returns:
            LLMResult containing the parsed model and optional reasoning.

        Raises:
            Various PydanticAI exceptions on failure.
        """
        # Get model settings from config
        model_settings = self._config.to_model_settings()

        agent: Agent[None, T] = Agent(  # type: ignore[call-overload]
            model=self._config.full_model_string,
            output_type=response_model,
            system_prompt=system_prompt or "",
            model_settings=model_settings,
            defer_model_check=True,  # Dynamic model name
        )
        result = await agent.run(prompt)

        # Extract reasoning from messages
        reasoning = self._extract_reasoning(result.all_messages())

        return LLMResult(data=result.output, reasoning_summary=reasoning)

    async def generate_text(
        self,
        prompt: str,
        system_prompt: str | None = None,
    ) -> LLMResult[str]:
        """Generate plain text from LLM.

        Args:
            prompt: The user prompt to send to the LLM.
            system_prompt: Optional system prompt for context.

        Returns:
            LLMResult containing the text response and optional reasoning.

        Raises:
            Various PydanticAI exceptions on failure.
        """
        model_settings = self._config.to_model_settings()

        agent: Agent[None, str] = Agent(  # type: ignore[call-overload]
            model=self._config.full_model_string,
            output_type=str,
            system_prompt=system_prompt or "",
            model_settings=model_settings,
            defer_model_check=True,  # Dynamic model name
        )
        result = await agent.run(prompt)

        reasoning = self._extract_reasoning(result.all_messages())

        return LLMResult(data=result.output, reasoning_summary=reasoning)
