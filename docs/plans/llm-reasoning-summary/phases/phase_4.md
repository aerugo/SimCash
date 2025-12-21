# Phase 4: Update Audit Wrapper

**Status**: Pending
**Started**:

---

## Objective

Update `AuditCaptureLLMClient` and `LLMInteraction` to capture reasoning summaries from `LLMResult` and ensure persistence to the database.

---

## Invariants Enforced in This Phase

- INV-2: Determinism - Reasoning capture doesn't affect simulation behavior
- INV-9: Policy Evaluation Identity - Reasoning is observational metadata only

---

## TDD Steps

### Step 4.1: Write Failing Tests (RED)

Update `api/tests/llm/test_audit_wrapper.py`:

**Test Cases**:
1. `test_llm_interaction_has_reasoning_field` - New field exists
2. `test_audit_wrapper_captures_reasoning` - Reasoning from LLMResult captured
3. `test_audit_wrapper_captures_none_reasoning` - None when not available
4. `test_get_last_interaction_includes_reasoning` - Reasoning in retrieved interaction

```python
"""Tests for AuditCaptureLLMClient reasoning capture."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
import pytest

from pydantic import BaseModel

from payment_simulator.llm.audit_wrapper import (
    AuditCaptureLLMClient,
    LLMInteraction,
)
from payment_simulator.llm.result import LLMResult


class MockPolicy(BaseModel):
    """Mock policy for testing."""
    name: str


class MockLLMClient:
    """Mock LLM client for testing."""

    def __init__(self, reasoning: str | None = None) -> None:
        self._reasoning = reasoning

    async def generate_structured_output(
        self,
        prompt: str,
        response_model: type,
        system_prompt: str | None = None,
    ) -> LLMResult:
        return LLMResult(
            data=MockPolicy(name="test"),
            reasoning_summary=self._reasoning,
        )

    async def generate_text(
        self,
        prompt: str,
        system_prompt: str | None = None,
    ) -> LLMResult[str]:
        return LLMResult(
            data="test response",
            reasoning_summary=self._reasoning,
        )


class TestLLMInteractionReasoningField:
    """Tests for reasoning field in LLMInteraction."""

    def test_llm_interaction_has_reasoning_field(self) -> None:
        """Verify LLMInteraction has reasoning_summary field."""
        interaction = LLMInteraction(
            system_prompt="system",
            user_prompt="user",
            raw_response="response",
            parsed_policy={"name": "test"},
            parsing_error=None,
            prompt_tokens=100,
            completion_tokens=50,
            latency_seconds=1.5,
            reasoning_summary="The model reasoned...",
        )
        assert interaction.reasoning_summary == "The model reasoned..."

    def test_llm_interaction_reasoning_optional(self) -> None:
        """Verify reasoning_summary can be None."""
        interaction = LLMInteraction(
            system_prompt="system",
            user_prompt="user",
            raw_response="response",
            parsed_policy=None,
            parsing_error=None,
            prompt_tokens=0,
            completion_tokens=0,
            latency_seconds=1.0,
            reasoning_summary=None,
        )
        assert interaction.reasoning_summary is None


class TestAuditWrapperReasoningCapture:
    """Tests for reasoning capture in AuditCaptureLLMClient."""

    @pytest.mark.asyncio
    async def test_audit_wrapper_captures_reasoning(self) -> None:
        """Verify reasoning is captured from LLMResult."""
        delegate = MockLLMClient(reasoning="I analyzed the situation...")
        wrapper = AuditCaptureLLMClient(delegate)

        await wrapper.generate_structured_output(
            prompt="test prompt",
            response_model=MockPolicy,
            system_prompt="test system",
        )

        interaction = wrapper.get_last_interaction()
        assert interaction is not None
        assert interaction.reasoning_summary == "I analyzed the situation..."

    @pytest.mark.asyncio
    async def test_audit_wrapper_captures_none_reasoning(self) -> None:
        """Verify None reasoning is captured correctly."""
        delegate = MockLLMClient(reasoning=None)
        wrapper = AuditCaptureLLMClient(delegate)

        await wrapper.generate_structured_output(
            prompt="test",
            response_model=MockPolicy,
        )

        interaction = wrapper.get_last_interaction()
        assert interaction is not None
        assert interaction.reasoning_summary is None

    @pytest.mark.asyncio
    async def test_audit_wrapper_captures_text_reasoning(self) -> None:
        """Verify reasoning captured for generate_text as well."""
        delegate = MockLLMClient(reasoning="Text generation reasoning...")
        wrapper = AuditCaptureLLMClient(delegate)

        await wrapper.generate_text(prompt="test", system_prompt="system")

        interaction = wrapper.get_last_interaction()
        assert interaction is not None
        assert interaction.reasoning_summary == "Text generation reasoning..."

    @pytest.mark.asyncio
    async def test_multiple_calls_capture_reasoning(self) -> None:
        """Verify each call captures its own reasoning."""
        delegate = MockLLMClient(reasoning="reasoning1")
        wrapper = AuditCaptureLLMClient(delegate)

        await wrapper.generate_structured_output("p1", MockPolicy)

        # Change the reasoning for next call
        delegate._reasoning = "reasoning2"
        await wrapper.generate_structured_output("p2", MockPolicy)

        interactions = wrapper.get_all_interactions()
        assert len(interactions) == 2
        assert interactions[0].reasoning_summary == "reasoning1"
        assert interactions[1].reasoning_summary == "reasoning2"
```

### Step 4.2: Implement to Pass Tests (GREEN)

Modify `api/payment_simulator/llm/audit_wrapper.py`:

```python
"""Audit capture wrapper for LLM clients.

This module provides the AuditCaptureLLMClient which wraps any
LLMClientProtocol implementation and captures all interactions
for later replay and auditing, including reasoning summaries.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, TypeVar

from payment_simulator.llm.result import LLMResult

if TYPE_CHECKING:
    from pydantic import BaseModel

    from payment_simulator.llm.protocol import LLMClientProtocol

T = TypeVar("T", bound="BaseModel")


@dataclass(frozen=True)
class LLMInteraction:
    """Captured LLM interaction for audit trail.

    Immutable record of a single LLM interaction, capturing all
    inputs, outputs, metadata, and reasoning for later replay.

    Attributes:
        system_prompt: The system prompt used for this interaction.
        user_prompt: The user prompt sent to the LLM.
        raw_response: The raw response text from the LLM.
        parsed_policy: Parsed policy dict if structured output succeeded.
        parsing_error: Error message if parsing failed.
        prompt_tokens: Number of input tokens (0 if unavailable).
        completion_tokens: Number of output tokens (0 if unavailable).
        latency_seconds: Time taken for the LLM call.
        reasoning_summary: Extracted reasoning/thinking from the LLM response.
    """

    system_prompt: str
    user_prompt: str
    raw_response: str
    parsed_policy: dict[str, Any] | None
    parsing_error: str | None
    prompt_tokens: int
    completion_tokens: int
    latency_seconds: float
    reasoning_summary: str | None  # NEW: Reasoning from LLM


class AuditCaptureLLMClient:
    """Wrapper that captures interactions for audit replay.

    Wraps any LLMClientProtocol implementation and captures
    all interactions for later replay, including reasoning. This enables:

    - Audit trails for compliance
    - Debugging and analysis of LLM behavior
    - Replay of experiments without calling the LLM
    - Understanding LLM reasoning/decision-making

    Example:
        >>> base_client = PydanticAILLMClient(config)
        >>> audit_client = AuditCaptureLLMClient(base_client)
        >>> result = await audit_client.generate_text("prompt")
        >>> interaction = audit_client.get_last_interaction()
        >>> interaction.reasoning_summary
        'The model considered...'
    """

    def __init__(self, delegate: LLMClientProtocol) -> None:
        """Initialize with delegate client."""
        self._delegate = delegate
        self._interactions: list[LLMInteraction] = []

    def get_last_interaction(self) -> LLMInteraction | None:
        """Get the most recent interaction."""
        return self._interactions[-1] if self._interactions else None

    def get_all_interactions(self) -> list[LLMInteraction]:
        """Get all captured interactions."""
        return list(self._interactions)

    async def generate_text(
        self,
        prompt: str,
        system_prompt: str | None = None,
    ) -> LLMResult[str]:
        """Generate text and capture interaction with reasoning."""
        start = time.perf_counter()
        result = await self._delegate.generate_text(prompt, system_prompt)
        latency = time.perf_counter() - start

        self._interactions.append(
            LLMInteraction(
                system_prompt=system_prompt or "",
                user_prompt=prompt,
                raw_response=result.data,
                parsed_policy=None,
                parsing_error=None,
                prompt_tokens=0,
                completion_tokens=0,
                latency_seconds=latency,
                reasoning_summary=result.reasoning_summary,
            )
        )

        return result

    async def generate_structured_output(
        self,
        prompt: str,
        response_model: type[T],
        system_prompt: str | None = None,
    ) -> LLMResult[T]:
        """Generate structured output and capture interaction with reasoning."""
        start = time.perf_counter()
        try:
            result = await self._delegate.generate_structured_output(
                prompt, response_model, system_prompt
            )
            latency = time.perf_counter() - start

            # Try to extract dict representation
            parsed: dict[str, Any] | None = None
            data = result.data
            if hasattr(data, "model_dump"):
                parsed = data.model_dump()
            elif hasattr(data, "__dict__"):
                parsed = data.__dict__

            self._interactions.append(
                LLMInteraction(
                    system_prompt=system_prompt or "",
                    user_prompt=prompt,
                    raw_response=str(data),
                    parsed_policy=parsed,
                    parsing_error=None,
                    prompt_tokens=0,
                    completion_tokens=0,
                    latency_seconds=latency,
                    reasoning_summary=result.reasoning_summary,
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
                    reasoning_summary=None,
                )
            )
            raise
```

### Step 4.3: Verify Database Persistence

Check that `GameRepository` stores the reasoning. The existing `llm_reasoning` column should be populated.

Review `api/payment_simulator/ai_cash_mgmt/persistence/repository.py` to ensure LLMInteractionRecord is properly mapped.

---

## Implementation Details

### LLMInteraction Changes

Add new field:
```python
@dataclass(frozen=True)
class LLMInteraction:
    # ... existing fields ...
    reasoning_summary: str | None  # NEW
```

### Return Type Change

Methods now return `LLMResult[T]` instead of just `T`:
```python
async def generate_structured_output(...) -> LLMResult[T]:
    ...
    return result  # LLMResult from delegate
```

### Error Handling

On exception, reasoning is set to None (no reasoning available on error).

---

## Files

| File | Action |
|------|--------|
| `api/payment_simulator/llm/audit_wrapper.py` | MODIFY |
| `api/tests/llm/test_audit_wrapper.py` | MODIFY/CREATE |

---

## Verification

```bash
# Run tests
cd api
.venv/bin/python -m pytest tests/llm/test_audit_wrapper.py -v

# Type check
.venv/bin/python -m mypy payment_simulator/llm/audit_wrapper.py

# Lint
.venv/bin/python -m ruff check payment_simulator/llm/audit_wrapper.py
```

---

## Completion Criteria

- [ ] All test cases pass
- [ ] Type check passes (mypy)
- [ ] Lint passes (ruff)
- [ ] LLMInteraction has reasoning_summary field
- [ ] AuditCaptureLLMClient captures reasoning from LLMResult
- [ ] Reasoning persisted to database (verify manually or in Phase 5)
