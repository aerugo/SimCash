"""Tests for audit capture wrapper.

These tests verify the AuditCaptureLLMClient wrapper captures
all LLM interactions for later replay/audit.
"""

from __future__ import annotations

from typing import Any

import pytest


class MockLLMClient:
    """Mock LLM client for testing."""

    async def generate_text(
        self,
        prompt: str,
        system_prompt: str | None = None,
    ) -> str:
        return f"Response to: {prompt}"

    async def generate_structured_output(
        self,
        prompt: str,
        response_model: type[Any],
        system_prompt: str | None = None,
    ) -> Any:
        # Return an instance with model_dump for Pydantic compatibility
        instance = response_model()
        return instance


class TestLLMInteraction:
    """Tests for LLMInteraction dataclass."""

    def test_is_frozen(self) -> None:
        """LLMInteraction is immutable."""
        from payment_simulator.llm.audit_wrapper import LLMInteraction

        interaction = LLMInteraction(
            system_prompt="sys",
            user_prompt="user",
            raw_response="response",
            parsed_policy=None,
            parsing_error=None,
            prompt_tokens=100,
            completion_tokens=50,
            latency_seconds=1.5,
        )
        with pytest.raises(AttributeError):
            interaction.user_prompt = "modified"  # type: ignore

    def test_stores_all_fields(self) -> None:
        """LLMInteraction stores all provided fields."""
        from payment_simulator.llm.audit_wrapper import LLMInteraction

        interaction = LLMInteraction(
            system_prompt="sys",
            user_prompt="user",
            raw_response="response",
            parsed_policy={"key": "value"},
            parsing_error=None,
            prompt_tokens=100,
            completion_tokens=50,
            latency_seconds=1.5,
        )
        assert interaction.system_prompt == "sys"
        assert interaction.user_prompt == "user"
        assert interaction.raw_response == "response"
        assert interaction.parsed_policy == {"key": "value"}
        assert interaction.prompt_tokens == 100
        assert interaction.completion_tokens == 50
        assert interaction.latency_seconds == 1.5

    def test_stores_parsing_error(self) -> None:
        """LLMInteraction can store parsing errors."""
        from payment_simulator.llm.audit_wrapper import LLMInteraction

        interaction = LLMInteraction(
            system_prompt="sys",
            user_prompt="user",
            raw_response="",
            parsed_policy=None,
            parsing_error="Invalid JSON",
            prompt_tokens=0,
            completion_tokens=0,
            latency_seconds=0.5,
        )
        assert interaction.parsing_error == "Invalid JSON"
        assert interaction.parsed_policy is None


class TestAuditCaptureLLMClient:
    """Tests for AuditCaptureLLMClient."""

    def test_wraps_delegate_client(self) -> None:
        """Wrapper wraps a delegate client."""
        from payment_simulator.llm.audit_wrapper import AuditCaptureLLMClient

        mock = MockLLMClient()
        wrapper = AuditCaptureLLMClient(mock)
        assert wrapper._delegate is mock

    def test_get_last_interaction_returns_none_initially(self) -> None:
        """get_last_interaction returns None before any calls."""
        from payment_simulator.llm.audit_wrapper import AuditCaptureLLMClient

        mock = MockLLMClient()
        wrapper = AuditCaptureLLMClient(mock)
        assert wrapper.get_last_interaction() is None

    @pytest.mark.asyncio
    async def test_captures_text_interaction(self) -> None:
        """Captures interaction from generate_text call."""
        from payment_simulator.llm.audit_wrapper import AuditCaptureLLMClient

        mock = MockLLMClient()
        wrapper = AuditCaptureLLMClient(mock)

        await wrapper.generate_text("test prompt", "system prompt")

        interaction = wrapper.get_last_interaction()
        assert interaction is not None
        assert interaction.user_prompt == "test prompt"
        assert interaction.system_prompt == "system prompt"

    @pytest.mark.asyncio
    async def test_captures_response_in_interaction(self) -> None:
        """Captures response text in interaction."""
        from payment_simulator.llm.audit_wrapper import AuditCaptureLLMClient

        mock = MockLLMClient()
        wrapper = AuditCaptureLLMClient(mock)

        result = await wrapper.generate_text("test prompt")

        assert result == "Response to: test prompt"
        interaction = wrapper.get_last_interaction()
        assert interaction is not None
        assert interaction.raw_response == "Response to: test prompt"

    @pytest.mark.asyncio
    async def test_captures_latency(self) -> None:
        """Captures latency in interaction."""
        from payment_simulator.llm.audit_wrapper import AuditCaptureLLMClient

        mock = MockLLMClient()
        wrapper = AuditCaptureLLMClient(mock)

        await wrapper.generate_text("test prompt")

        interaction = wrapper.get_last_interaction()
        assert interaction is not None
        assert interaction.latency_seconds >= 0

    def test_get_all_interactions_returns_empty_list_initially(self) -> None:
        """get_all_interactions returns empty list before any calls."""
        from payment_simulator.llm.audit_wrapper import AuditCaptureLLMClient

        mock = MockLLMClient()
        wrapper = AuditCaptureLLMClient(mock)
        assert wrapper.get_all_interactions() == []

    @pytest.mark.asyncio
    async def test_get_all_interactions_returns_all_interactions(self) -> None:
        """get_all_interactions returns all captured interactions."""
        from payment_simulator.llm.audit_wrapper import AuditCaptureLLMClient

        mock = MockLLMClient()
        wrapper = AuditCaptureLLMClient(mock)

        await wrapper.generate_text("prompt1")
        await wrapper.generate_text("prompt2")

        interactions = wrapper.get_all_interactions()
        assert len(interactions) == 2
        assert interactions[0].user_prompt == "prompt1"
        assert interactions[1].user_prompt == "prompt2"

    @pytest.mark.asyncio
    async def test_handles_none_system_prompt(self) -> None:
        """Handles None system_prompt by storing empty string."""
        from payment_simulator.llm.audit_wrapper import AuditCaptureLLMClient

        mock = MockLLMClient()
        wrapper = AuditCaptureLLMClient(mock)

        await wrapper.generate_text("test prompt")

        interaction = wrapper.get_last_interaction()
        assert interaction is not None
        assert interaction.system_prompt == ""

    def test_can_export_from_llm_module(self) -> None:
        """AuditCaptureLLMClient can be imported from llm module."""
        from payment_simulator.llm import AuditCaptureLLMClient, LLMInteraction

        assert AuditCaptureLLMClient is not None
        assert LLMInteraction is not None
