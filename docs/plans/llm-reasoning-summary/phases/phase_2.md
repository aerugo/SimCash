# Phase 2: Create LLMResult Wrapper

**Status**: Pending
**Started**:

---

## Objective

Create a typed `LLMResult[T]` wrapper that contains both the parsed response data and the optional reasoning summary. This enables the audit wrapper to capture reasoning without changing the public API contract.

---

## Invariants Enforced in This Phase

- None directly - this is internal infrastructure

---

## TDD Steps

### Step 2.1: Write Failing Tests (RED)

Create `api/tests/llm/test_llm_result.py`:

**Test Cases**:
1. `test_llm_result_creation` - Basic creation with data and reasoning
2. `test_llm_result_data_access` - Access the parsed data
3. `test_llm_result_reasoning_optional` - reasoning_summary can be None
4. `test_llm_result_is_frozen` - Immutable dataclass

```python
"""Tests for LLMResult wrapper."""

import pytest
from dataclasses import FrozenInstanceError

from payment_simulator.llm.result import LLMResult


class PolicyResponse:
    """Mock policy response for testing."""
    def __init__(self, name: str) -> None:
        self.name = name


class TestLLMResult:
    """Tests for LLMResult wrapper."""

    def test_llm_result_creation(self) -> None:
        """Verify LLMResult can be created with data and reasoning."""
        policy = PolicyResponse("test_policy")
        result = LLMResult(
            data=policy,
            reasoning_summary="The model considered X and Y...",
        )
        assert result.data == policy
        assert result.reasoning_summary == "The model considered X and Y..."

    def test_llm_result_data_access(self) -> None:
        """Verify data can be accessed from result."""
        policy = PolicyResponse("my_policy")
        result = LLMResult(data=policy, reasoning_summary=None)
        assert result.data.name == "my_policy"

    def test_llm_result_reasoning_optional(self) -> None:
        """Verify reasoning_summary can be None."""
        policy = PolicyResponse("policy")
        result = LLMResult(data=policy, reasoning_summary=None)
        assert result.reasoning_summary is None

    def test_llm_result_is_frozen(self) -> None:
        """Verify LLMResult is immutable."""
        policy = PolicyResponse("policy")
        result = LLMResult(data=policy, reasoning_summary="reasoning")
        with pytest.raises(FrozenInstanceError):
            result.reasoning_summary = "new_reasoning"  # type: ignore[misc]
```

### Step 2.2: Implement to Pass Tests (GREEN)

Create `api/payment_simulator/llm/result.py`:

```python
"""LLM result wrapper with reasoning support.

This module provides the LLMResult dataclass that wraps parsed LLM
responses together with optional reasoning summaries.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Generic, TypeVar

T = TypeVar("T")


@dataclass(frozen=True)
class LLMResult(Generic[T]):
    """Result from LLM call with optional reasoning summary.

    Wraps the parsed response data together with any reasoning/thinking
    content extracted from the LLM response. This enables the audit
    wrapper to capture reasoning for persistence without changing the
    core API contract.

    Type Parameters:
        T: The type of the parsed response data (typically a Pydantic model).

    Example:
        >>> from pydantic import BaseModel
        >>> class Policy(BaseModel):
        ...     name: str
        >>> result = LLMResult(
        ...     data=Policy(name="fifo"),
        ...     reasoning_summary="Selected FIFO because...",
        ... )
        >>> result.data.name
        'fifo'
        >>> result.reasoning_summary
        'Selected FIFO because...'

    Attributes:
        data: The parsed response from the LLM (e.g., a Pydantic model).
        reasoning_summary: Optional reasoning/thinking summary from the LLM.
            None if reasoning was not requested or not available.
    """

    data: T
    reasoning_summary: str | None
```

### Step 2.3: Refactor

- Ensure proper generic typing
- Add module to `__init__.py` exports if needed

---

## Implementation Details

### Generic Type Parameter

The `T` type parameter allows `LLMResult` to wrap any response type:

```python
from payment_simulator.llm.result import LLMResult
from my_models import PolicyConfig

# LLMResult[PolicyConfig] - type checker knows data is PolicyConfig
result: LLMResult[PolicyConfig] = ...
policy: PolicyConfig = result.data  # Type-safe access
```

### Frozen Dataclass

Using `frozen=True` ensures immutability, which aligns with the project's pattern of using immutable data structures for audit trails.

---

## Files

| File | Action |
|------|--------|
| `api/payment_simulator/llm/result.py` | CREATE |
| `api/tests/llm/test_llm_result.py` | CREATE |

---

## Verification

```bash
# Run tests
cd api
.venv/bin/python -m pytest tests/llm/test_llm_result.py -v

# Type check
.venv/bin/python -m mypy payment_simulator/llm/result.py

# Lint
.venv/bin/python -m ruff check payment_simulator/llm/result.py
```

---

## Completion Criteria

- [ ] All test cases pass
- [ ] Type check passes (mypy)
- [ ] Lint passes (ruff)
- [ ] Generic typing works correctly
- [ ] Dataclass is frozen (immutable)
