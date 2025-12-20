"""Tests for LLMResult wrapper.

These tests verify the LLMResult dataclass that wraps parsed LLM
responses together with optional reasoning summaries.
"""

from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest
from pydantic import BaseModel

from payment_simulator.llm.result import LLMResult


class MockPolicy(BaseModel):
    """Mock policy for testing."""

    name: str


class TestLLMResult:
    """Tests for LLMResult wrapper."""

    def test_llm_result_creation(self) -> None:
        """Verify LLMResult can be created with data and reasoning."""
        policy = MockPolicy(name="test_policy")
        result = LLMResult(
            data=policy,
            reasoning_summary="The model considered X and Y...",
        )
        assert result.data == policy
        assert result.reasoning_summary == "The model considered X and Y..."

    def test_llm_result_data_access(self) -> None:
        """Verify data can be accessed from result."""
        policy = MockPolicy(name="my_policy")
        result = LLMResult(data=policy, reasoning_summary=None)
        assert result.data.name == "my_policy"

    def test_llm_result_reasoning_optional(self) -> None:
        """Verify reasoning_summary can be None."""
        policy = MockPolicy(name="policy")
        result = LLMResult(data=policy, reasoning_summary=None)
        assert result.reasoning_summary is None

    def test_llm_result_is_frozen(self) -> None:
        """Verify LLMResult is immutable."""
        policy = MockPolicy(name="policy")
        result = LLMResult(data=policy, reasoning_summary="reasoning")
        with pytest.raises(FrozenInstanceError):
            result.reasoning_summary = "new_reasoning"  # type: ignore[misc]

    def test_llm_result_with_string_data(self) -> None:
        """Verify LLMResult works with string data type."""
        result = LLMResult(data="plain text response", reasoning_summary="I thought...")
        assert result.data == "plain text response"
        assert result.reasoning_summary == "I thought..."

    def test_llm_result_generic_typing(self) -> None:
        """Verify LLMResult generic typing works correctly."""
        # This is a type-checking test - if it compiles, it works
        result: LLMResult[MockPolicy] = LLMResult(
            data=MockPolicy(name="typed"),
            reasoning_summary=None,
        )
        # Type checker should know result.data is MockPolicy
        name: str = result.data.name
        assert name == "typed"
