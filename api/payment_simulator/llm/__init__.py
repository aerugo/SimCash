"""LLM integration layer.

Provides a unified interface for working with different LLM providers.

This module abstracts away the specifics of different LLM providers
(OpenAI, Anthropic, etc.) behind a common protocol interface.

Usage:
    >>> from payment_simulator.llm import LLMClientProtocol
    >>>
    >>> class MyClient:
    ...     async def generate_structured_output(self, prompt, response_model, system_prompt=None):
    ...         ...
    ...     async def generate_text(self, prompt, system_prompt=None):
    ...         ...
    >>>
    >>> assert isinstance(MyClient(), LLMClientProtocol)  # Duck typing check
"""

from payment_simulator.llm.protocol import LLMClientProtocol

__all__ = ["LLMClientProtocol"]
