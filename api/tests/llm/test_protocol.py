"""Tests for LLM protocol definitions.

These tests verify the LLMClientProtocol interface is correctly defined
and can be used for structural typing (duck typing) checks.
"""

from __future__ import annotations

from typing import Any

import pytest


class TestLLMClientProtocol:
    """Tests for LLMClientProtocol interface."""

    def test_protocol_can_be_imported(self) -> None:
        """LLMClientProtocol can be imported from llm module."""
        from payment_simulator.llm.protocol import LLMClientProtocol

        assert LLMClientProtocol is not None

    def test_protocol_has_generate_structured_output(self) -> None:
        """LLMClientProtocol defines generate_structured_output method."""
        from payment_simulator.llm.protocol import LLMClientProtocol

        assert hasattr(LLMClientProtocol, "generate_structured_output")

    def test_protocol_has_generate_text(self) -> None:
        """LLMClientProtocol defines generate_text method."""
        from payment_simulator.llm.protocol import LLMClientProtocol

        assert hasattr(LLMClientProtocol, "generate_text")

    def test_protocol_is_runtime_checkable(self) -> None:
        """LLMClientProtocol is decorated with @runtime_checkable."""
        from payment_simulator.llm.protocol import LLMClientProtocol

        # A runtime checkable protocol can be used with isinstance
        # We test this indirectly - if not runtime_checkable, isinstance would raise TypeError
        class NotAnLLMClient:
            pass

        # This should work (return False) rather than raising TypeError
        result = isinstance(NotAnLLMClient(), LLMClientProtocol)
        assert result is False  # NotAnLLMClient doesn't implement the protocol

    def test_mock_implementation_satisfies_protocol(self) -> None:
        """A class with correct methods satisfies the protocol."""
        from payment_simulator.llm.protocol import LLMClientProtocol

        class MockLLMClient:
            """Mock LLM client that satisfies the protocol."""

            async def generate_structured_output(
                self,
                prompt: str,
                response_model: type[Any],
                system_prompt: str | None = None,
            ) -> Any:
                return response_model()

            async def generate_text(
                self,
                prompt: str,
                system_prompt: str | None = None,
            ) -> str:
                return "mock response"

        client = MockLLMClient()
        assert isinstance(client, LLMClientProtocol)

    def test_module_exports_protocol(self) -> None:
        """LLMClientProtocol is exported from llm module."""
        from payment_simulator.llm import LLMClientProtocol

        assert LLMClientProtocol is not None
