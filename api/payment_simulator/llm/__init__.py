"""LLM integration layer.

This module provides unified LLM abstraction for all modules
needing LLM capabilities. It supports multiple providers through
a common protocol interface.

Components:
    - LLMClientProtocol: Protocol interface for LLM clients
    - LLMConfig: Unified configuration for all providers
    - PydanticAILLMClient: PydanticAI-based implementation (requires pydantic-ai)
    - AuditCaptureLLMClient: Wrapper that captures interactions
    - LLMInteraction: Immutable record of an LLM interaction

Example:
    >>> from payment_simulator.llm import LLMConfig, PydanticAILLMClient
    >>> config = LLMConfig(model="anthropic:claude-sonnet-4-5")
    >>> client = PydanticAILLMClient(config)
    >>>
    >>> # With audit capture:
    >>> from payment_simulator.llm import AuditCaptureLLMClient
    >>> audit_client = AuditCaptureLLMClient(client)
    >>> result = await audit_client.generate_text("Hello")
    >>> interaction = audit_client.get_last_interaction()

Note:
    PydanticAILLMClient requires the optional pydantic-ai dependency.
    Install with: pip install pydantic-ai
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from payment_simulator.llm.audit_wrapper import (
    AuditCaptureLLMClient,
    LLMInteraction,
)
from payment_simulator.llm.config import LLMConfig
from payment_simulator.llm.protocol import LLMClientProtocol

# Lazy import for PydanticAILLMClient to avoid requiring pydantic-ai
# for modules that don't need the actual client implementation
if TYPE_CHECKING:
    from payment_simulator.llm.pydantic_client import PydanticAILLMClient

__all__ = [
    "LLMClientProtocol",
    "LLMConfig",
    "PydanticAILLMClient",
    "AuditCaptureLLMClient",
    "LLMInteraction",
]


def __getattr__(name: str) -> type:
    """Lazy import for optional dependencies."""
    if name == "PydanticAILLMClient":
        from payment_simulator.llm.pydantic_client import PydanticAILLMClient

        return PydanticAILLMClient
    msg = f"module {__name__!r} has no attribute {name!r}"
    raise AttributeError(msg)
