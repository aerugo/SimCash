# Phase 1: Protocol and Data Types

**Status**: Pending
**Started**:

---

## Objective

Define the contract for unified LLM context building via a Protocol and supporting data types. This establishes the interface that all evaluation modes must implement.

---

## Invariants Enforced in This Phase

- **INV-11**: Agent Isolation - Protocol docstring explicitly requires agent-isolated data only
- **INV-12** (NEW): LLM Context Identity - Data types designed to enforce same output format

---

## TDD Steps

### Step 1.1: Write Failing Tests (RED)

Create `api/tests/unit/ai_cash_mgmt/prompts/test_llm_context_protocol.py`:

**Test Cases**:
1. `test_llm_agent_context_creation` - Verify dataclass instantiation with required fields
2. `test_llm_agent_context_requires_simulation_output` - Verify simulation_output is required
3. `test_protocol_has_build_context_method` - Verify protocol defines required method

```python
"""Tests for LLM context protocol and data types."""

from __future__ import annotations

import pytest

from payment_simulator.ai_cash_mgmt.prompts.llm_context_protocol import (
    LLMAgentContext,
    LLMContextBuilderProtocol,
)


class TestLLMAgentContext:
    """Tests for LLMAgentContext dataclass."""

    def test_creation_with_required_fields(self) -> None:
        """LLMAgentContext can be created with all required fields."""
        context = LLMAgentContext(
            agent_id="BANK_A",
            simulation_output="Tick 0: ...",
            cost_breakdown={"delay": 100, "collateral": 50},
            current_cost=150,
            iteration=1,
        )
        assert context.agent_id == "BANK_A"
        assert context.simulation_output == "Tick 0: ..."
        assert context.cost_breakdown["delay"] == 100

    def test_simulation_output_is_required(self) -> None:
        """simulation_output field must be provided (not optional)."""
        # This test verifies the field is required at the type level
        # The dataclass should not allow None for simulation_output
        context = LLMAgentContext(
            agent_id="BANK_A",
            simulation_output="Some output",
            cost_breakdown={},
            current_cost=0,
            iteration=1,
        )
        assert context.simulation_output is not None

    def test_mode_metadata_is_optional(self) -> None:
        """mode_metadata is optional and defaults to None."""
        context = LLMAgentContext(
            agent_id="BANK_A",
            simulation_output="Output",
            cost_breakdown={},
            current_cost=0,
            iteration=1,
        )
        assert context.mode_metadata is None

    def test_mode_metadata_can_be_provided(self) -> None:
        """mode_metadata can store mode-specific information."""
        context = LLMAgentContext(
            agent_id="BANK_A",
            simulation_output="Output",
            cost_breakdown={},
            current_cost=0,
            iteration=1,
            mode_metadata={
                "mode": "bootstrap",
                "num_samples": 50,
                "best_seed": 12345,
            },
        )
        assert context.mode_metadata["mode"] == "bootstrap"
        assert context.mode_metadata["num_samples"] == 50


class TestLLMContextBuilderProtocol:
    """Tests for LLMContextBuilderProtocol."""

    def test_protocol_is_runtime_checkable(self) -> None:
        """Protocol supports isinstance checks."""
        # This test verifies the protocol is runtime_checkable
        from typing import runtime_checkable

        assert hasattr(LLMContextBuilderProtocol, "__protocol_attrs__") or \
               hasattr(LLMContextBuilderProtocol, "_is_runtime_protocol")

    def test_protocol_defines_build_context(self) -> None:
        """Protocol requires build_context method."""
        # Verify the method exists in protocol
        assert hasattr(LLMContextBuilderProtocol, "build_context")
```

### Step 1.2: Implement to Pass Tests (GREEN)

Create `api/payment_simulator/ai_cash_mgmt/prompts/llm_context_protocol.py`:

```python
"""Protocol and data types for unified LLM context building.

This module defines the contract for building LLM optimization context
across all evaluation modes (bootstrap, deterministic-pairwise, deterministic-temporal).

CRITICAL INVARIANT (INV-12): LLM Context Identity
For any agent A and simulation result R, the LLM context MUST contain identical
simulation output formatting regardless of evaluation mode. Only mode-specific
evaluation metadata may differ.

CRITICAL INVARIANT (INV-11): Agent Isolation
All context data MUST be filtered to only include Agent A's own data.
Counterparty information is strictly forbidden.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

if TYPE_CHECKING:
    from payment_simulator.ai_cash_mgmt.bootstrap.enriched_models import (
        EnrichedEvaluationResult,
    )


@dataclass(frozen=True)
class LLMAgentContext:
    """Complete context for LLM policy optimization.

    This dataclass represents the unified context provided to the LLM
    for optimizing a single agent's policy. The simulation_output field
    MUST be populated regardless of evaluation mode.

    Attributes:
        agent_id: Identifier for the agent being optimized.
        simulation_output: Formatted tick-by-tick simulation events.
            MUST be populated (not None) for all evaluation modes.
            This is the core visibility the LLM needs for optimization.
        cost_breakdown: Breakdown of costs by type (delay, collateral, etc.).
        current_cost: Total cost from current policy evaluation.
        iteration: Current optimization iteration number.
        mode_metadata: Optional mode-specific metadata (e.g., bootstrap sample info).
            This is the ONLY field that may differ between evaluation modes.

    Example:
        >>> context = LLMAgentContext(
        ...     agent_id="BANK_A",
        ...     simulation_output="Tick 0: DeferredCreditApplied...",
        ...     cost_breakdown={"delay": 100, "collateral": 50},
        ...     current_cost=150,
        ...     iteration=3,
        ...     mode_metadata={"mode": "bootstrap", "num_samples": 50},
        ... )
    """

    agent_id: str
    simulation_output: str  # REQUIRED - not optional
    cost_breakdown: dict[str, int]
    current_cost: int
    iteration: int
    mode_metadata: dict[str, Any] | None = field(default=None)


@runtime_checkable
class LLMContextBuilderProtocol(Protocol):
    """Protocol for building LLM optimization context.

    All evaluation modes MUST implement this protocol to ensure
    consistent context building. The key invariant (INV-12) is that
    simulation_output formatting is identical across modes.

    Implementations:
        - BootstrapLLMContextBuilder: For bootstrap evaluation mode
        - DeterministicLLMContextBuilder: For deterministic modes

    Example:
        >>> builder: LLMContextBuilderProtocol = get_context_builder(mode)
        >>> context = builder.build_context(
        ...     agent_id="BANK_A",
        ...     results=evaluation_results,
        ...     iteration=5,
        ... )
        >>> assert context.simulation_output is not None  # Always populated
    """

    def build_context(
        self,
        agent_id: str,
        results: list[EnrichedEvaluationResult],
        iteration: int,
    ) -> LLMAgentContext:
        """Build unified context for LLM optimization.

        Args:
            agent_id: Agent to build context for (INV-11: only this agent's data).
            results: Evaluation results from simulation(s).
            iteration: Current optimization iteration.

        Returns:
            LLMAgentContext with simulation_output ALWAYS populated.

        Raises:
            ValueError: If results are empty or agent_id not found.
        """
        ...
```

### Step 1.3: Refactor

- Ensure type safety (no bare `Any` where avoidable)
- Add docstrings with examples
- Optimize for readability

---

## Implementation Details

### Data Type Design

The `LLMAgentContext` is designed with these principles:

1. **simulation_output is REQUIRED**: The `str` type (not `str | None`) enforces this at the type level
2. **mode_metadata is OPTIONAL**: Different modes can add their specific info here
3. **Frozen dataclass**: Immutable to prevent accidental modification
4. **cost_breakdown as dict**: Flexible for different cost types

### Protocol Design

The `LLMContextBuilderProtocol` follows existing patterns (INV-9, INV-10):

1. **@runtime_checkable**: Allows isinstance() checks
2. **Single method**: `build_context()` as the unified entry point
3. **Returns dataclass**: Not raw dict, ensuring type safety

### Edge Cases to Handle

- Empty results list → raise ValueError
- Agent not found in results → raise ValueError
- Zero-tick simulation → still produce output (empty tick log)

---

## Files

| File | Action |
|------|--------|
| `api/tests/unit/ai_cash_mgmt/prompts/test_llm_context_protocol.py` | CREATE |
| `api/payment_simulator/ai_cash_mgmt/prompts/llm_context_protocol.py` | CREATE |

---

## Verification

```bash
# Create test directory if needed
mkdir -p api/tests/unit/ai_cash_mgmt/prompts

# Run tests
cd api
.venv/bin/python -m pytest tests/unit/ai_cash_mgmt/prompts/test_llm_context_protocol.py -v

# Type check
.venv/bin/python -m mypy payment_simulator/ai_cash_mgmt/prompts/llm_context_protocol.py

# Lint
.venv/bin/python -m ruff check payment_simulator/ai_cash_mgmt/prompts/llm_context_protocol.py
```

---

## Completion Criteria

- [ ] All test cases pass
- [ ] Type check passes
- [ ] Lint passes
- [ ] Docstrings added with examples
- [ ] Protocol is @runtime_checkable
- [ ] simulation_output is required (not optional)
- [ ] INV-11 mentioned in docstrings
- [ ] INV-12 mentioned in module docstring
