"""Audit capture wrapper for LLM clients.

This module provides the AuditCaptureLLMClient which wraps any
LLMClientProtocol implementation and captures all interactions
for later replay and auditing.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, TypeVar

if TYPE_CHECKING:
    from pydantic import BaseModel

    from payment_simulator.llm.protocol import LLMClientProtocol

T = TypeVar("T", bound="BaseModel")


@dataclass(frozen=True)
class LLMInteraction:
    """Captured LLM interaction for audit trail.

    Immutable record of a single LLM interaction, capturing all
    inputs, outputs, and metadata for later replay.

    Attributes:
        system_prompt: The system prompt used for this interaction.
        user_prompt: The user prompt sent to the LLM.
        raw_response: The raw response text from the LLM.
        parsed_policy: Parsed policy dict if structured output succeeded.
        parsing_error: Error message if parsing failed.
        prompt_tokens: Number of input tokens (0 if unavailable).
        completion_tokens: Number of output tokens (0 if unavailable).
        latency_seconds: Time taken for the LLM call.
    """

    system_prompt: str
    user_prompt: str
    raw_response: str
    parsed_policy: dict[str, Any] | None
    parsing_error: str | None
    prompt_tokens: int
    completion_tokens: int
    latency_seconds: float


class AuditCaptureLLMClient:
    """Wrapper that captures interactions for audit replay.

    Wraps any LLMClientProtocol implementation and captures
    all interactions for later replay. This enables:

    - Audit trails for compliance
    - Debugging and analysis of LLM behavior
    - Replay of experiments without calling the LLM

    Example:
        >>> base_client = PydanticAILLMClient(config)
        >>> audit_client = AuditCaptureLLMClient(base_client)
        >>> result = await audit_client.generate_text("prompt")
        >>> interaction = audit_client.get_last_interaction()
        >>> interaction.user_prompt
        'prompt'

    Attributes:
        _delegate: The wrapped LLM client.
        _interactions: List of captured interactions.
    """

    def __init__(self, delegate: LLMClientProtocol) -> None:
        """Initialize with delegate client.

        Args:
            delegate: The LLM client to wrap and capture from.
        """
        self._delegate = delegate
        self._interactions: list[LLMInteraction] = []

    def get_last_interaction(self) -> LLMInteraction | None:
        """Get the most recent interaction.

        Returns:
            The last captured interaction, or None if no calls made.
        """
        return self._interactions[-1] if self._interactions else None

    def get_all_interactions(self) -> list[LLMInteraction]:
        """Get all captured interactions.

        Returns:
            List of all captured interactions in order.
        """
        return list(self._interactions)

    async def generate_text(
        self,
        prompt: str,
        system_prompt: str | None = None,
    ) -> str:
        """Generate text and capture interaction.

        Args:
            prompt: The user prompt to send.
            system_prompt: Optional system prompt.

        Returns:
            Text response from the LLM.
        """
        start = time.perf_counter()
        result = await self._delegate.generate_text(prompt, system_prompt)
        latency = time.perf_counter() - start

        self._interactions.append(
            LLMInteraction(
                system_prompt=system_prompt or "",
                user_prompt=prompt,
                raw_response=result,
                parsed_policy=None,
                parsing_error=None,
                prompt_tokens=0,  # Not available from base client
                completion_tokens=0,
                latency_seconds=latency,
            )
        )

        return result

    async def generate_structured_output(
        self,
        prompt: str,
        response_model: type[T],
        system_prompt: str | None = None,
    ) -> T:
        """Generate structured output and capture interaction.

        Args:
            prompt: The user prompt to send.
            response_model: Pydantic model type for parsing.
            system_prompt: Optional system prompt.

        Returns:
            Instance of response_model populated by the LLM.

        Raises:
            Re-raises any exception from the delegate after capturing.
        """
        start = time.perf_counter()
        try:
            result = await self._delegate.generate_structured_output(
                prompt, response_model, system_prompt
            )
            latency = time.perf_counter() - start

            # Try to extract dict representation
            parsed: dict[str, Any] | None = None
            if hasattr(result, "model_dump"):
                parsed = result.model_dump()
            elif hasattr(result, "__dict__"):
                parsed = result.__dict__

            self._interactions.append(
                LLMInteraction(
                    system_prompt=system_prompt or "",
                    user_prompt=prompt,
                    raw_response=str(result),
                    parsed_policy=parsed,
                    parsing_error=None,
                    prompt_tokens=0,
                    completion_tokens=0,
                    latency_seconds=latency,
                )
            )

            return result

        except Exception as e:
            latency = time.perf_counter() - start
            self._interactions.append(
                LLMInteraction(
                    system_prompt=system_prompt or "",
                    user_prompt=prompt,
                    raw_response="",
                    parsed_policy=None,
                    parsing_error=str(e),
                    prompt_tokens=0,
                    completion_tokens=0,
                    latency_seconds=latency,
                )
            )
            raise
