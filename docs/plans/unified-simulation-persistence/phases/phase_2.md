# Phase 2: Integrate into Experiment Runner

**Status**: Pending
**Started**:

---

## Objective

Modify the experiment runner's `_run_simulation()` method to use `SimulationPersistenceProvider` instead of storing events as JSON blobs in `experiment_events`. This ensures experiments persist simulations identically to `payment-sim run --persist`.

---

## Invariants Enforced in This Phase

- **INV-11**: Simulation Persistence Identity - Experiments now use same persistence path as CLI
- **INV-5**: Replay Identity - Simulations from experiments will be replayable
- **INV-2**: Determinism - Seeds persisted for reproducibility

---

## Current State

In `api/payment_simulator/experiments/runner/optimization.py`, the `_run_simulation()` method (lines 561-582) currently does:

```python
# Current: Stores events as JSON blob in experiment_events
if self._repository and should_persist:
    event = EventRecord(
        event_type="simulation_run",
        event_data={
            "simulation_id": sim_id,
            "events": all_events,  # ← JSON blob
        },
    )
    self._repository.save_event(event)  # ← Goes to experiment_events
```

This needs to change to:

```python
# New: Uses SimulationPersistenceProvider
if self._simulation_persistence_provider and should_persist:
    self._simulation_persistence_provider.persist_tick_events(sim_id, tick, tick_events)
    # ... after simulation complete:
    self._simulation_persistence_provider.persist_simulation_complete(sim_id, metrics)
```

---

## TDD Steps

### Step 2.1: Write Failing Tests (RED)

Create `api/tests/integration/test_experiment_simulation_persistence.py`:

**Test Cases**:
1. `test_experiment_with_persist_creates_simulation_record` - Verify simulations table populated
2. `test_experiment_with_persist_writes_events_to_simulation_events` - Verify events in standard table
3. `test_experiment_simulation_has_experiment_context` - Verify run_id and iteration stored
4. `test_simulation_queryable_via_standard_queries` - Verify standard replay queries work
5. `test_experiment_without_persist_no_simulation_tables` - Backward compatibility
6. `test_multiple_simulations_per_experiment` - Multiple bootstrap samples persisted separately

```python
"""Integration tests for experiment simulation persistence.

These tests verify that experiments persist simulations to the standard
simulation tables (simulations, simulation_events) when --persist-bootstrap
is enabled, ensuring replay identity (INV-5) and persistence identity (INV-11).
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any

import pytest

from payment_simulator.persistence.connection import DatabaseManager
from payment_simulator.persistence.event_queries import get_simulation_events
from payment_simulator.persistence.queries import get_simulation_summary


class TestExperimentSimulationPersistence:
    """Tests for experiment simulation persistence integration."""

    @pytest.fixture
    def experiment_config(self) -> dict[str, Any]:
        """Minimal experiment configuration for testing."""
        return {
            "name": "test-experiment",
            "scenario": {
                "ticks_per_day": 10,
                "num_days": 1,
                "rng_seed": 12345,
                "agents": [
                    {
                        "id": "BANK_A",
                        "opening_balance": 1000000,
                        "unsecured_cap": 500000,
                    },
                    {
                        "id": "BANK_B",
                        "opening_balance": 1000000,
                        "unsecured_cap": 500000,
                    },
                ],
                "arrivals": [],  # No arrivals for simple test
            },
            "evaluation": {
                "mode": "deterministic",
                "ticks": 10,
            },
            "optimized_agents": ["BANK_A"],
        }

    @pytest.fixture
    def temp_db_path(self) -> Path:
        """Create temporary database path."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir) / "test_experiment.db"

    def test_experiment_with_persist_creates_simulation_record(
        self, experiment_config: dict[str, Any], temp_db_path: Path
    ) -> None:
        """Experiments with persist_bootstrap should create simulation records."""
        from payment_simulator.experiments.runner.optimization import (
            OptimizationRunner,
        )

        # Run experiment with persistence
        runner = OptimizationRunner(
            config=experiment_config,
            db_path=temp_db_path,
            persist_bootstrap=True,
        )

        # Run initial simulation
        result = runner._run_simulation(
            seed=12345,
            purpose="test_simulation",
            persist=True,
        )

        # Verify simulation record exists in standard table
        with DatabaseManager(str(temp_db_path)) as db:
            summary = get_simulation_summary(db.conn, result.simulation_id)
            assert summary is not None
            assert summary["simulation_id"] == result.simulation_id

    def test_experiment_with_persist_writes_events_to_simulation_events(
        self, experiment_config: dict[str, Any], temp_db_path: Path
    ) -> None:
        """Events should be written to simulation_events table, not experiment_events."""
        from payment_simulator.experiments.runner.optimization import (
            OptimizationRunner,
        )

        runner = OptimizationRunner(
            config=experiment_config,
            db_path=temp_db_path,
            persist_bootstrap=True,
        )

        result = runner._run_simulation(
            seed=12345,
            purpose="test_events",
            persist=True,
        )

        # Verify events in simulation_events table
        with DatabaseManager(str(temp_db_path)) as db:
            events_result = get_simulation_events(
                db.conn, result.simulation_id, limit=1000
            )
            # Should have at least some events (even with no arrivals, there may be system events)
            assert events_result["total"] >= 0

            # Events should NOT be in experiment_events as JSON blob
            blob_count = db.conn.execute(
                """
                SELECT COUNT(*) FROM experiment_events
                WHERE event_type = 'simulation_run'
                AND json_extract_string(event_data, '$.simulation_id') = ?
                """,
                [result.simulation_id],
            ).fetchone()[0]
            assert blob_count == 0, "Events should not be stored as JSON blob"

    def test_experiment_simulation_has_experiment_context(
        self, experiment_config: dict[str, Any], temp_db_path: Path
    ) -> None:
        """Simulation should store experiment run_id and iteration for cross-reference."""
        from payment_simulator.experiments.runner.optimization import (
            OptimizationRunner,
        )

        runner = OptimizationRunner(
            config=experiment_config,
            db_path=temp_db_path,
            persist_bootstrap=True,
        )

        # Simulate context
        runner._run_id = "exp-run-test-001"
        runner._current_iteration = 3

        result = runner._run_simulation(
            seed=12345,
            purpose="test_context",
            iteration=3,
            persist=True,
        )

        # Verify experiment context stored
        with DatabaseManager(str(temp_db_path)) as db:
            row = db.conn.execute(
                """
                SELECT experiment_run_id, experiment_iteration
                FROM simulations WHERE simulation_id = ?
                """,
                [result.simulation_id],
            ).fetchone()

            assert row is not None
            assert row[0] == "exp-run-test-001"
            assert row[1] == 3

    def test_simulation_queryable_via_standard_queries(
        self, experiment_config: dict[str, Any], temp_db_path: Path
    ) -> None:
        """Simulations should be queryable via standard persistence queries."""
        from payment_simulator.experiments.runner.optimization import (
            OptimizationRunner,
        )

        runner = OptimizationRunner(
            config=experiment_config,
            db_path=temp_db_path,
            persist_bootstrap=True,
        )

        result = runner._run_simulation(
            seed=12345,
            purpose="test_query",
            persist=True,
        )

        # Standard queries should work
        with DatabaseManager(str(temp_db_path)) as db:
            # get_simulation_summary
            summary = get_simulation_summary(db.conn, result.simulation_id)
            assert summary is not None

            # get_simulation_events
            events = get_simulation_events(db.conn, result.simulation_id)
            assert "events" in events
            assert "total" in events

    def test_experiment_without_persist_no_simulation_tables(
        self, experiment_config: dict[str, Any], temp_db_path: Path
    ) -> None:
        """Experiments without persist_bootstrap should not write to simulation tables."""
        from payment_simulator.experiments.runner.optimization import (
            OptimizationRunner,
        )

        runner = OptimizationRunner(
            config=experiment_config,
            db_path=temp_db_path,
            persist_bootstrap=False,  # Persistence disabled
        )

        result = runner._run_simulation(
            seed=12345,
            purpose="test_no_persist",
            persist=False,
        )

        # No simulation record should exist
        with DatabaseManager(str(temp_db_path)) as db:
            summary = get_simulation_summary(db.conn, result.simulation_id)
            assert summary is None, "Should not persist when flag is False"

    def test_multiple_simulations_per_experiment(
        self, experiment_config: dict[str, Any], temp_db_path: Path
    ) -> None:
        """Multiple bootstrap simulations should each be persisted separately."""
        from payment_simulator.experiments.runner.optimization import (
            OptimizationRunner,
        )

        runner = OptimizationRunner(
            config=experiment_config,
            db_path=temp_db_path,
            persist_bootstrap=True,
        )

        # Run multiple simulations (like bootstrap samples)
        sim_ids = []
        for i in range(3):
            result = runner._run_simulation(
                seed=12345 + i,
                purpose=f"bootstrap_sample_{i}",
                persist=True,
            )
            sim_ids.append(result.simulation_id)

        # All should be persisted separately
        with DatabaseManager(str(temp_db_path)) as db:
            for sim_id in sim_ids:
                summary = get_simulation_summary(db.conn, sim_id)
                assert summary is not None, f"Simulation {sim_id} should be persisted"

            # Count total simulations
            count = db.conn.execute(
                "SELECT COUNT(*) FROM simulations"
            ).fetchone()[0]
            assert count == 3
```

### Step 2.2: Implement to Pass Tests (GREEN)

Modify `api/payment_simulator/experiments/runner/optimization.py`:

1. Add `SimulationPersistenceProvider` as optional dependency
2. Initialize provider when `persist_bootstrap=True`
3. Modify `_run_simulation()` to use provider instead of JSON blob

```python
# In OptimizationRunner.__init__():
def __init__(
    self,
    config: ExperimentConfig | dict[str, Any],
    db_path: Path | str | None = None,
    persist_bootstrap: bool = False,
    # ... other params
) -> None:
    # ... existing init ...

    # Initialize simulation persistence provider
    self._simulation_persistence_provider: SimulationPersistenceProvider | None = None
    if persist_bootstrap and db_path:
        from payment_simulator.persistence.connection import DatabaseManager
        from payment_simulator.persistence.simulation_persistence_provider import (
            StandardSimulationPersistenceProvider,
        )
        # Use same DatabaseManager as repository
        self._simulation_persistence_provider = StandardSimulationPersistenceProvider(
            self._repository._db_manager  # or create new if needed
        )


# In _run_simulation():
def _run_simulation(
    self,
    seed: int,
    purpose: str,
    iteration: int | None = None,
    persist: bool | None = None,
) -> SimulationResult:
    # ... existing simulation execution ...

    # NEW: Persist using SimulationPersistenceProvider
    should_persist = persist if persist is not None else self._persist_bootstrap
    if self._simulation_persistence_provider and should_persist:
        # Persist simulation start
        self._simulation_persistence_provider.persist_simulation_start(
            simulation_id=sim_id,
            config=ffi_config,
            experiment_run_id=self._run_id,
            experiment_iteration=iteration,
        )

        # Events were collected per-tick, persist them
        # Note: may need to refactor to persist per-tick during execution
        for tick, tick_events in enumerate(all_events_by_tick):
            self._simulation_persistence_provider.persist_tick_events(
                simulation_id=sim_id,
                tick=tick,
                events=tick_events,
            )

        # Persist completion
        self._simulation_persistence_provider.persist_simulation_complete(
            simulation_id=sim_id,
            metrics={
                "total_arrivals": metrics.get("total_arrivals", 0),
                "total_settlements": metrics.get("total_settlements", 0),
                "total_costs": total_cost,
            },
        )

    # REMOVE: Old JSON blob persistence to experiment_events
    # if self._repository and should_persist:
    #     event = EventRecord(
    #         event_type="simulation_run",
    #         event_data={"simulation_id": sim_id, "events": all_events},
    #     )
    #     self._repository.save_event(event)

    return SimulationResult(...)
```

### Step 2.3: Refactor

- Ensure events are persisted per-tick during simulation (not batched at end)
- Add type hints throughout
- Handle database connection lifecycle properly
- Ensure backward compatibility when `persist_bootstrap=False`

---

## Implementation Details

### Event Collection Strategy

Current code collects all events at end:
```python
all_events: list[dict[str, Any]] = []
for tick in range(total_ticks):
    orch.tick()
    tick_events = orch.get_tick_events(tick)
    all_events.extend(tick_events)
```

Should be modified to persist per-tick:
```python
for tick in range(total_ticks):
    orch.tick()
    tick_events = orch.get_tick_events(tick)

    if self._simulation_persistence_provider and should_persist:
        self._simulation_persistence_provider.persist_tick_events(
            sim_id, tick, tick_events
        )

    # Still collect for return value / further processing
    all_events.extend(tick_events)
```

### Database Manager Sharing

The `ExperimentRepository` has its own database connection. For `SimulationPersistenceProvider` to use the same database file, we need to either:

1. Share the same `DatabaseManager` instance
2. Create a new `DatabaseManager` pointing to the same file

Option 1 is cleaner but requires exposing `_conn` from `ExperimentRepository`.

### Edge Cases to Handle

- **No database path**: When `db_path=None`, neither persistence should be active
- **Repository exists but persistence disabled**: Only experiment-level persistence
- **Simulation failure**: Handle partial persistence gracefully

---

## Files

| File | Action |
|------|--------|
| `api/payment_simulator/experiments/runner/optimization.py` | MODIFY |
| `api/tests/integration/test_experiment_simulation_persistence.py` | CREATE |

---

## Verification

```bash
# Run integration tests
cd /home/user/SimCash/api
uv run pytest tests/integration/test_experiment_simulation_persistence.py -v

# Run existing experiment tests to verify backward compatibility
uv run pytest tests/integration/ -k "experiment" -v

# Type check
uv run mypy payment_simulator/experiments/runner/optimization.py
```

---

## Completion Criteria

- [ ] All 6 test cases pass
- [ ] Existing experiment tests still pass (backward compatibility)
- [ ] Type check passes (mypy)
- [ ] Events written to `simulation_events` table, not `experiment_events` JSON blob
- [ ] Experiment context (run_id, iteration) stored in simulation record
- [ ] Simulations queryable via standard `get_simulation_summary()` and `get_simulation_events()`
- [ ] INV-11 verified by tests
