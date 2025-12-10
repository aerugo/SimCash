# Phase 4: Experiment Runner Framework

**Status:** In Progress
**Created:** 2025-12-10
**Risk:** Medium
**Breaking Changes:** None (parallel implementation)

---

## Objectives

1. Create `OutputHandlerProtocol` for experiment output callbacks
2. Create `SilentOutput` implementation for testing
3. Create `ExperimentResult` dataclass for run results
4. Create `ExperimentState` dataclass for tracking state
5. Create `ExperimentRunnerProtocol` for runners
6. (DEFERRED) Create `BaseExperimentRunner` - requires evaluator integration

---

## TDD Test Specifications

### Test File: `api/tests/experiments/runner/test_output.py`

```python
"""Tests for output handler implementations."""

import pytest

from payment_simulator.experiments.runner.output import (
    OutputHandlerProtocol,
    SilentOutput,
)


class TestOutputHandlerProtocol:
    """Tests for OutputHandlerProtocol interface."""

    def test_protocol_is_runtime_checkable(self) -> None:
        """Protocol can be used for isinstance checks."""
        output = SilentOutput()
        assert isinstance(output, OutputHandlerProtocol)

    def test_protocol_has_required_methods(self) -> None:
        """Protocol defines required callback methods."""
        assert hasattr(OutputHandlerProtocol, "on_experiment_start")
        assert hasattr(OutputHandlerProtocol, "on_iteration_start")
        assert hasattr(OutputHandlerProtocol, "on_iteration_complete")
        assert hasattr(OutputHandlerProtocol, "on_agent_optimized")
        assert hasattr(OutputHandlerProtocol, "on_convergence")
        assert hasattr(OutputHandlerProtocol, "on_experiment_complete")


class TestSilentOutput:
    """Tests for SilentOutput handler."""

    def test_on_experiment_start_is_noop(self) -> None:
        """on_experiment_start does nothing (silent)."""
        output = SilentOutput()
        # Should not raise
        output.on_experiment_start("test_experiment")

    def test_on_iteration_start_is_noop(self) -> None:
        """on_iteration_start does nothing."""
        output = SilentOutput()
        output.on_iteration_start(1)

    def test_on_iteration_complete_is_noop(self) -> None:
        """on_iteration_complete does nothing."""
        output = SilentOutput()
        output.on_iteration_complete(1, {"total_cost": 1000})

    def test_on_agent_optimized_is_noop(self) -> None:
        """on_agent_optimized does nothing."""
        output = SilentOutput()
        output.on_agent_optimized("BANK_A", accepted=True, delta=-100)

    def test_on_convergence_is_noop(self) -> None:
        """on_convergence does nothing."""
        output = SilentOutput()
        output.on_convergence("stability_reached")

    def test_on_experiment_complete_is_noop(self) -> None:
        """on_experiment_complete does nothing."""
        output = SilentOutput()
        output.on_experiment_complete(None)

    def test_can_import_from_runner_module(self) -> None:
        """SilentOutput can be imported from runner module."""
        from payment_simulator.experiments.runner import SilentOutput
        assert SilentOutput is not None
```

### Test File: `api/tests/experiments/runner/test_result.py`

```python
"""Tests for ExperimentResult and ExperimentState."""

import pytest
from datetime import datetime

from payment_simulator.experiments.runner.result import (
    ExperimentResult,
    ExperimentState,
    IterationRecord,
)


class TestIterationRecord:
    """Tests for IterationRecord dataclass."""

    def test_creates_with_required_fields(self) -> None:
        """IterationRecord creates with iteration and costs."""
        record = IterationRecord(
            iteration=1,
            costs_per_agent={"BANK_A": 1000, "BANK_B": 2000},
            accepted_changes={"BANK_A": True},
        )
        assert record.iteration == 1
        assert record.costs_per_agent["BANK_A"] == 1000

    def test_is_frozen(self) -> None:
        """IterationRecord is immutable."""
        record = IterationRecord(
            iteration=1,
            costs_per_agent={"BANK_A": 1000},
            accepted_changes={},
        )
        with pytest.raises(AttributeError):
            record.iteration = 2  # type: ignore


class TestExperimentState:
    """Tests for ExperimentState dataclass."""

    def test_creates_with_defaults(self) -> None:
        """ExperimentState creates with sensible defaults."""
        state = ExperimentState(experiment_name="test")
        assert state.experiment_name == "test"
        assert state.current_iteration == 0
        assert state.is_converged is False
        assert state.convergence_reason is None

    def test_is_frozen(self) -> None:
        """ExperimentState is immutable."""
        state = ExperimentState(experiment_name="test")
        with pytest.raises(AttributeError):
            state.current_iteration = 5  # type: ignore

    def test_with_iteration_creates_new_state(self) -> None:
        """with_iteration returns new state with updated iteration."""
        state = ExperimentState(experiment_name="test")
        new_state = state.with_iteration(5)
        assert new_state.current_iteration == 5
        assert state.current_iteration == 0  # Original unchanged


class TestExperimentResult:
    """Tests for ExperimentResult dataclass."""

    def test_creates_with_required_fields(self) -> None:
        """ExperimentResult creates with required fields."""
        result = ExperimentResult(
            experiment_name="test",
            num_iterations=10,
            converged=True,
            convergence_reason="stability_reached",
            final_costs={"BANK_A": 500},
            total_duration_seconds=120.5,
        )
        assert result.experiment_name == "test"
        assert result.num_iterations == 10
        assert result.converged is True

    def test_is_frozen(self) -> None:
        """ExperimentResult is immutable."""
        result = ExperimentResult(
            experiment_name="test",
            num_iterations=10,
            converged=False,
            convergence_reason="max_iterations",
            final_costs={},
            total_duration_seconds=60.0,
        )
        with pytest.raises(AttributeError):
            result.num_iterations = 20  # type: ignore

    def test_final_costs_are_integers(self) -> None:
        """Final costs are integer cents (INV-1)."""
        result = ExperimentResult(
            experiment_name="test",
            num_iterations=5,
            converged=True,
            convergence_reason="improvement_threshold",
            final_costs={"BANK_A": 100000, "BANK_B": 200000},
            total_duration_seconds=30.0,
        )
        for cost in result.final_costs.values():
            assert isinstance(cost, int)

    def test_can_import_from_runner_module(self) -> None:
        """ExperimentResult can be imported from runner module."""
        from payment_simulator.experiments.runner import ExperimentResult
        assert ExperimentResult is not None
```

### Test File: `api/tests/experiments/runner/test_protocol.py`

```python
"""Tests for ExperimentRunnerProtocol."""

import pytest

from payment_simulator.experiments.runner.protocol import ExperimentRunnerProtocol


class TestExperimentRunnerProtocol:
    """Tests for ExperimentRunnerProtocol interface."""

    def test_protocol_has_run_method(self) -> None:
        """Protocol defines async run method."""
        assert hasattr(ExperimentRunnerProtocol, "run")

    def test_protocol_has_get_state_method(self) -> None:
        """Protocol defines get_current_state method."""
        assert hasattr(ExperimentRunnerProtocol, "get_current_state")

    def test_protocol_is_runtime_checkable(self) -> None:
        """Protocol can be used for isinstance checks."""
        from typing import runtime_checkable, Protocol

        # Just verify it's a protocol - can't instantiate
        assert issubclass(ExperimentRunnerProtocol, Protocol)
```

---

## Implementation Plan

### Step 4.1: Create OutputHandlerProtocol and SilentOutput

```python
# api/payment_simulator/experiments/runner/output.py
"""Output handler protocol and implementations."""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class OutputHandlerProtocol(Protocol):
    """Protocol for experiment output handling.

    Defines callbacks for experiment lifecycle events.
    Implementations can render to console, log to file, etc.
    """

    def on_experiment_start(self, experiment_name: str) -> None:
        """Called when experiment starts."""
        ...

    def on_iteration_start(self, iteration: int) -> None:
        """Called at the start of each iteration."""
        ...

    def on_iteration_complete(
        self,
        iteration: int,
        metrics: dict[str, Any],
    ) -> None:
        """Called after iteration completes."""
        ...

    def on_agent_optimized(
        self,
        agent_id: str,
        accepted: bool,
        delta: int | None = None,
    ) -> None:
        """Called after agent optimization attempt."""
        ...

    def on_convergence(self, reason: str) -> None:
        """Called when convergence detected."""
        ...

    def on_experiment_complete(self, result: Any) -> None:
        """Called when experiment finishes."""
        ...


class SilentOutput:
    """Silent output handler for testing.

    All callbacks are no-ops.
    """

    def on_experiment_start(self, experiment_name: str) -> None:
        pass

    def on_iteration_start(self, iteration: int) -> None:
        pass

    def on_iteration_complete(
        self,
        iteration: int,
        metrics: dict[str, Any],
    ) -> None:
        pass

    def on_agent_optimized(
        self,
        agent_id: str,
        accepted: bool,
        delta: int | None = None,
    ) -> None:
        pass

    def on_convergence(self, reason: str) -> None:
        pass

    def on_experiment_complete(self, result: Any) -> None:
        pass
```

### Step 4.2: Create ExperimentResult and ExperimentState

```python
# api/payment_simulator/experiments/runner/result.py
"""Experiment result and state dataclasses."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class IterationRecord:
    """Record of a single iteration."""
    iteration: int
    costs_per_agent: dict[str, int]
    accepted_changes: dict[str, bool]


@dataclass(frozen=True)
class ExperimentState:
    """Current state of an experiment."""
    experiment_name: str
    current_iteration: int = 0
    is_converged: bool = False
    convergence_reason: str | None = None
    policies: dict[str, dict] = field(default_factory=dict)

    def with_iteration(self, iteration: int) -> ExperimentState:
        """Return new state with updated iteration."""
        return ExperimentState(
            experiment_name=self.experiment_name,
            current_iteration=iteration,
            is_converged=self.is_converged,
            convergence_reason=self.convergence_reason,
            policies=self.policies,
        )


@dataclass(frozen=True)
class ExperimentResult:
    """Final result of an experiment run."""
    experiment_name: str
    num_iterations: int
    converged: bool
    convergence_reason: str
    final_costs: dict[str, int]
    total_duration_seconds: float
    iteration_history: tuple[IterationRecord, ...] = ()
    final_policies: dict[str, dict] = field(default_factory=dict)
```

### Step 4.3: Create ExperimentRunnerProtocol

```python
# api/payment_simulator/experiments/runner/protocol.py
"""Experiment runner protocol."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from payment_simulator.experiments.runner.result import (
        ExperimentResult,
        ExperimentState,
    )


@runtime_checkable
class ExperimentRunnerProtocol(Protocol):
    """Protocol for experiment runners."""

    async def run(self) -> ExperimentResult:
        """Run experiment to completion."""
        ...

    def get_current_state(self) -> ExperimentState:
        """Get current experiment state."""
        ...
```

### Step 4.4: Update Module Exports

```python
# api/payment_simulator/experiments/runner/__init__.py
"""Experiment runner module."""

from payment_simulator.experiments.runner.output import (
    OutputHandlerProtocol,
    SilentOutput,
)
from payment_simulator.experiments.runner.protocol import ExperimentRunnerProtocol
from payment_simulator.experiments.runner.result import (
    ExperimentResult,
    ExperimentState,
    IterationRecord,
)

__all__ = [
    "OutputHandlerProtocol",
    "SilentOutput",
    "ExperimentRunnerProtocol",
    "ExperimentResult",
    "ExperimentState",
    "IterationRecord",
]
```

---

## Files to Create

| File | Purpose |
|------|---------|
| `api/payment_simulator/experiments/runner/output.py` | OutputHandler protocol and SilentOutput |
| `api/payment_simulator/experiments/runner/result.py` | ExperimentResult, ExperimentState, IterationRecord |
| `api/payment_simulator/experiments/runner/protocol.py` | ExperimentRunnerProtocol |
| `api/tests/experiments/runner/test_output.py` | Output handler tests |
| `api/tests/experiments/runner/test_result.py` | Result/State tests |
| `api/tests/experiments/runner/test_protocol.py` | Protocol tests |

## Files to Modify

| File | Change |
|------|--------|
| `api/payment_simulator/experiments/runner/__init__.py` | Add exports |

---

## Verification Checklist

### TDD Tests
- [ ] `test_protocol_is_runtime_checkable` passes (OutputHandler)
- [ ] `test_protocol_has_required_methods` passes
- [ ] `test_on_experiment_start_is_noop` passes
- [ ] `test_on_iteration_start_is_noop` passes
- [ ] `test_on_iteration_complete_is_noop` passes
- [ ] `test_on_agent_optimized_is_noop` passes
- [ ] `test_on_convergence_is_noop` passes
- [ ] `test_on_experiment_complete_is_noop` passes
- [ ] `test_creates_with_required_fields` passes (IterationRecord)
- [ ] `test_is_frozen` passes (IterationRecord)
- [ ] `test_creates_with_defaults` passes (ExperimentState)
- [ ] `test_with_iteration_creates_new_state` passes
- [ ] `test_final_costs_are_integers` passes (INV-1)
- [ ] `test_protocol_has_run_method` passes
- [ ] `test_protocol_has_get_state_method` passes
- [ ] All module exports work correctly

### Type Checking
```bash
cd api && .venv/bin/python -m mypy payment_simulator/experiments/runner/
```

---

## Notes

Phase 4 creates the runner framework foundation. The actual `BaseExperimentRunner`
implementation is deferred to Phase 4.5 because it requires:
- Integration with PolicyEvaluator (from ai_cash_mgmt)
- Integration with LLMClient (from llm module)
- Integration with ConstraintValidator

This phase focuses on the protocols, data structures, and output handlers
that form the skeleton of the runner framework.

Key design decisions:
- All result dataclasses are frozen (immutable)
- OutputHandlerProtocol uses @runtime_checkable for isinstance checks
- SilentOutput is intentionally minimal for testing
- ExperimentState.with_iteration() pattern for immutable updates
- All costs are integer cents (INV-1 compliance)

---

*Phase 4 Plan v1.0 - 2025-12-10*
