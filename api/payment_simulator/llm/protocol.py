"""LLM client protocol definitions.

This module defines the interface that all LLM clients must implement.
This allows the system to work with different LLM providers (OpenAI,
Anthropic, etc.) without tight coupling.

Example:
    >>> class MyLLMClient:
    ...     async def generate_structured_output(
    ...         self,
    ...         prompt: str,
    ...         response_model: type[T],
    ...         system_prompt: str | None = None,
    ...     ) -> LLMResult[T]: ...
    ...
    ...     async def generate_text(
    ...         self,
    ...         prompt: str,
    ...         system_prompt: str | None = None,
    ...     ) -> LLMResult[str]: ...
    >>>
    >>> isinstance(MyLLMClient(), LLMClientProtocol)  # Works with runtime_checkable
    True
"""

from __future__ import annotations

from typing import Protocol, TypeVar, runtime_checkable

from payment_simulator.llm.result import LLMResult

T = TypeVar("T")


@runtime_checkable
class LLMClientProtocol(Protocol):
    """Protocol for LLM clients.

    Any LLM client implementation must provide these methods to be
    compatible with the experiment system.

    Attributes:
        None - this is a structural protocol (duck typing).

    Note:
        Implementations don't need to inherit from this class.
        They just need to implement the required methods.
    """

    async def generate_structured_output(
        self,
        prompt: str,
        response_model: type[T],
        system_prompt: str | None = None,
    ) -> LLMResult[T]:
        """Generate structured output from LLM.

        Uses the LLM to generate a response that matches the given
        Pydantic model structure.

        Args:
            prompt: The prompt to send to the LLM.
            response_model: Pydantic model to parse response into.
            system_prompt: Optional system prompt for context.

        Returns:
            LLMResult containing response_model instance and optional reasoning.

        Raises:
            ValueError: If LLM response cannot be parsed into model.
        """
        ...

    async def generate_text(
        self,
        prompt: str,
        system_prompt: str | None = None,
    ) -> LLMResult[str]:
        """Generate plain text from LLM.

        Args:
            prompt: The prompt to send to the LLM.
            system_prompt: Optional system prompt for context.

        Returns:
            LLMResult containing text response and optional reasoning.
        """
        ...
