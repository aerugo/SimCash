# Phase 1: Create SimulationResult Dataclass

**Goal**: Define a unified result type that captures all simulation output, following TDD principles.

## Background

The `SimulationResult` dataclass will be the single return type for the new `_run_simulation()` method. It must capture all data that either `_run_initial_simulation()` or `_run_simulation_with_events()` currently produce.

## Requirements from Feature Request

```python
@dataclass(frozen=True)
class SimulationResult:
    """Complete simulation output. Callers use what they need."""
    seed: int
    simulation_id: str
    total_cost: int
    per_agent_costs: dict[str, int]
    events: tuple[dict[str, Any], ...]
    cost_breakdown: CostBreakdown
    settlement_rate: float
    avg_delay: float
```

## Invariants to Enforce

1. **INV-1: Integer Cents** - All cost fields (`total_cost`, `per_agent_costs`, and `CostBreakdown` fields) must be `int`
2. **INV-5: Strict Typing** - Complete type annotations, modern Python syntax

## TDD Approach

### Step 1: Write Tests First

Create `api/tests/experiments/runner/test_simulation_result.py`:

```python
"""Unit tests for SimulationResult dataclass."""

import pytest
from payment_simulator.experiments.runner.bootstrap_support import SimulationResult
from payment_simulator.ai_cash_mgmt.bootstrap.enriched_models import CostBreakdown


class TestSimulationResult:
    """Tests for SimulationResult dataclass."""

    def test_create_simulation_result_with_all_fields(self) -> None:
        """Test creating SimulationResult with all required fields."""
        result = SimulationResult(
            seed=12345,
            simulation_id="exp1-20251214-143022-a1b2c3-sim-001-init",
            total_cost=15000,  # $150.00 in cents
            per_agent_costs={"BANK_A": 7500, "BANK_B": 7500},
            events=({"event_type": "Arrival", "tick": 0},),
            cost_breakdown=CostBreakdown(
                delay_cost=5000,
                overdraft_cost=8000,
                deadline_penalty=2000,
                eod_penalty=0,
            ),
            settlement_rate=0.95,
            avg_delay=5.2,
        )

        assert result.seed == 12345
        assert result.simulation_id == "exp1-20251214-143022-a1b2c3-sim-001-init"
        assert result.total_cost == 15000
        assert result.per_agent_costs == {"BANK_A": 7500, "BANK_B": 7500}
        assert len(result.events) == 1
        assert result.settlement_rate == 0.95
        assert result.avg_delay == 5.2

    def test_simulation_result_is_frozen(self) -> None:
        """Test that SimulationResult is immutable."""
        result = SimulationResult(
            seed=12345,
            simulation_id="test-sim-001",
            total_cost=10000,
            per_agent_costs={},
            events=(),
            cost_breakdown=CostBreakdown(
                delay_cost=0,
                overdraft_cost=0,
                deadline_penalty=0,
                eod_penalty=0,
            ),
            settlement_rate=1.0,
            avg_delay=0.0,
        )

        with pytest.raises(AttributeError):
            result.total_cost = 20000  # type: ignore[misc]

    def test_costs_are_integer_cents(self) -> None:
        """Test that cost fields accept only integers (INV-1)."""
        # This test verifies the type annotation is correct
        # The actual type checking is done by mypy
        result = SimulationResult(
            seed=1,
            simulation_id="test",
            total_cost=10000,  # Must be int
            per_agent_costs={"A": 5000, "B": 5000},  # Must be int values
            events=(),
            cost_breakdown=CostBreakdown(
                delay_cost=1000,  # Must be int
                overdraft_cost=2000,
                deadline_penalty=3000,
                eod_penalty=4000,
            ),
            settlement_rate=1.0,
            avg_delay=0.0,
        )

        # Verify types at runtime
        assert isinstance(result.total_cost, int)
        assert all(isinstance(v, int) for v in result.per_agent_costs.values())
        assert isinstance(result.cost_breakdown.delay_cost, int)

    def test_events_are_immutable_tuple(self) -> None:
        """Test that events are stored as immutable tuple."""
        events_list = [{"tick": 0}, {"tick": 1}]
        result = SimulationResult(
            seed=1,
            simulation_id="test",
            total_cost=0,
            per_agent_costs={},
            events=tuple(events_list),
            cost_breakdown=CostBreakdown(0, 0, 0, 0),
            settlement_rate=1.0,
            avg_delay=0.0,
        )

        # Events should be a tuple
        assert isinstance(result.events, tuple)
        # Modifying original list shouldn't affect result
        events_list.append({"tick": 2})
        assert len(result.events) == 2
```

### Step 2: Implement SimulationResult

Add to `api/payment_simulator/experiments/runner/bootstrap_support.py`:

```python
@dataclass(frozen=True)
class SimulationResult:
    """Complete simulation output. Callers use what they need.

    This is the unified result type from _run_simulation(). It captures
    all data that any caller might need, allowing callers to transform
    or filter as required.

    All costs are integer cents (INV-1: Money is ALWAYS i64).

    Attributes:
        seed: RNG seed used for this simulation.
        simulation_id: Unique identifier for replay and debugging.
        total_cost: Sum of all agent costs in integer cents.
        per_agent_costs: Cost per agent in integer cents.
        events: All events from the simulation (immutable tuple).
        cost_breakdown: Breakdown of costs by type.
        settlement_rate: Fraction of transactions settled (0.0 to 1.0).
        avg_delay: Average settlement delay in ticks.

    Example:
        >>> result = SimulationResult(
        ...     seed=12345,
        ...     simulation_id="exp1-sim-001-init",
        ...     total_cost=15000,  # $150.00 in cents
        ...     per_agent_costs={"BANK_A": 7500, "BANK_B": 7500},
        ...     events=({"event_type": "Arrival", "tick": 0},),
        ...     cost_breakdown=CostBreakdown(
        ...         delay_cost=5000,
        ...         overdraft_cost=8000,
        ...         deadline_penalty=2000,
        ...         eod_penalty=0,
        ...     ),
        ...     settlement_rate=0.95,
        ...     avg_delay=5.2,
        ... )
    """

    seed: int
    simulation_id: str
    total_cost: int  # INV-1: Integer cents
    per_agent_costs: dict[str, int]  # INV-1: Integer cents
    events: tuple[dict[str, Any], ...]
    cost_breakdown: CostBreakdown
    settlement_rate: float
    avg_delay: float
```

### Step 3: Verify Type Checking

Run mypy and ruff:
```bash
cd api
.venv/bin/python -m mypy payment_simulator/experiments/runner/bootstrap_support.py
.venv/bin/python -m ruff check payment_simulator/experiments/runner/bootstrap_support.py
```

### Step 4: Run Tests

```bash
cd api
.venv/bin/python -m pytest tests/experiments/runner/test_simulation_result.py -v
```

## Success Criteria

- [ ] Tests written before implementation (TDD)
- [ ] All tests pass
- [ ] mypy reports no errors
- [ ] ruff reports no errors
- [ ] SimulationResult is frozen (immutable)
- [ ] All costs are int type (INV-1)
- [ ] Events stored as tuple (immutable)
- [ ] Docstrings complete with examples

## Files to Create/Modify

| File | Action |
|------|--------|
| `api/tests/experiments/runner/test_simulation_result.py` | Create (tests first) |
| `api/payment_simulator/experiments/runner/bootstrap_support.py` | Modify (add SimulationResult) |

## Notes

- The `CostBreakdown` class already exists in `enriched_models.py`
- Using `frozen=True` ensures immutability
- Using `tuple` for events ensures the collection is immutable
- This is a pure Python change, no Rust/FFI changes needed
