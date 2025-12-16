# Phase 2: Integrate into Experiment Runner

**Status**: Pending
**Started**:

**Prerequisite**: Phase 1 must be complete (all tests pass, provider implemented).

---

## Objective

Modify the experiment runner's `_run_simulation()` method to use `SimulationPersistenceProvider` instead of storing events as JSON blobs in `experiment_events`.

---

## Invariants Enforced in This Phase

- **INV-11**: Simulation Persistence Identity - Experiments now use same persistence path as CLI
- **INV-5**: Replay Identity - Simulations from experiments will be replayable
- **INV-2**: Determinism - Seeds persisted for reproducibility

---

## Strict TDD Workflow

**CRITICAL**: Follow this exact sequence. Do NOT skip steps or combine RED/GREEN phases.

```
┌─────────────────────────────────────────────────────────────────┐
│  Step 1: Write integration tests ONLY (no implementation)       │
│  Step 2: Run tests → Verify they FAIL (RED)                     │
│  Step 3: Modify experiment runner to pass tests (GREEN)         │
│  Step 4: Refactor while keeping tests green (REFACTOR)          │
│  Step 5: Verify existing tests still pass (regression)          │
└─────────────────────────────────────────────────────────────────┘
```

---

## Step 2.1: Write Failing Tests (RED)

**Action**: Create integration test file ONLY. Do NOT modify `optimization.py` yet.

Create `api/tests/integration/test_experiment_simulation_persistence.py`:

```python
"""Integration tests for experiment simulation persistence.

TDD Phase: RED - These tests define the expected behavior.
The experiment runner has NOT been modified yet - tests MUST fail initially.

These tests verify that experiments persist simulations to the standard
simulation tables (simulations, simulation_events) when --persist-bootstrap
is enabled, ensuring replay identity (INV-5) and persistence identity (INV-11).
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any

import pytest


class TestExperimentSimulationPersistenceIntegration:
    """Integration tests for experiment → simulation table persistence.

    These tests will FAIL until optimization.py is modified to use
    SimulationPersistenceProvider.
    """

    @pytest.fixture
    def minimal_experiment_config(self) -> dict[str, Any]:
        """Minimal experiment configuration for testing."""
        return {
            "name": "test-experiment",
            "scenario": {
                "ticks_per_day": 10,
                "num_days": 1,
                "rng_seed": 12345,
                "agents": [
                    {"id": "BANK_A", "opening_balance": 1000000, "unsecured_cap": 500000},
                    {"id": "BANK_B", "opening_balance": 1000000, "unsecured_cap": 500000},
                ],
                "arrivals": [],
            },
            "evaluation": {"mode": "deterministic", "ticks": 10},
            "optimized_agents": ["BANK_A"],
        }

    @pytest.fixture
    def temp_db_path(self):
        """Create temporary database path."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir) / "test_experiment.db"

    def test_experiment_simulation_creates_record_in_simulations_table(
        self, minimal_experiment_config: dict[str, Any], temp_db_path: Path
    ) -> None:
        """When persist_bootstrap=True, simulations table should have a record.

        This is the KEY test that verifies INV-11 compliance.
        """
        from payment_simulator.experiments.runner.optimization import OptimizationRunner
        from payment_simulator.persistence.connection import DatabaseManager
        from payment_simulator.persistence.queries import get_simulation_summary

        runner = OptimizationRunner(
            config=minimal_experiment_config,
            db_path=temp_db_path,
            persist_bootstrap=True,
        )

        result = runner._run_simulation(seed=12345, purpose="test", persist=True)

        # KEY ASSERTION: Simulation must be in simulations table
        with DatabaseManager(str(temp_db_path)) as db:
            summary = get_simulation_summary(db.conn, result.simulation_id)
            assert summary is not None, (
                f"Simulation {result.simulation_id} not found in simulations table. "
                "This means SimulationPersistenceProvider is not being used."
            )
            assert summary["simulation_id"] == result.simulation_id

    def test_experiment_simulation_events_in_simulation_events_table(
        self, minimal_experiment_config: dict[str, Any], temp_db_path: Path
    ) -> None:
        """Events should be written to simulation_events table, NOT experiment_events."""
        from payment_simulator.experiments.runner.optimization import OptimizationRunner
        from payment_simulator.persistence.connection import DatabaseManager
        from payment_simulator.persistence.event_queries import get_simulation_events

        # Add an arrival to generate events
        minimal_experiment_config["scenario"]["arrivals"] = [
            {
                "sender": "BANK_A",
                "receiver": "BANK_B",
                "amount": 100000,
                "arrival_tick": 0,
                "deadline_tick": 9,
                "priority": 5,
            }
        ]

        runner = OptimizationRunner(
            config=minimal_experiment_config,
            db_path=temp_db_path,
            persist_bootstrap=True,
        )

        result = runner._run_simulation(seed=12345, purpose="test_events", persist=True)

        with DatabaseManager(str(temp_db_path)) as db:
            # Events MUST be in simulation_events table
            events_result = get_simulation_events(db.conn, result.simulation_id, limit=1000)
            assert events_result["total"] > 0, (
                "No events found in simulation_events table. "
                "Events may be stored as JSON blob in experiment_events instead."
            )

    def test_experiment_simulation_NOT_stored_as_json_blob(
        self, minimal_experiment_config: dict[str, Any], temp_db_path: Path
    ) -> None:
        """Events should NOT be stored as JSON blob in experiment_events.

        This tests that the OLD behavior (JSON blob) is NOT happening.
        """
        from payment_simulator.experiments.runner.optimization import OptimizationRunner
        from payment_simulator.persistence.connection import DatabaseManager

        runner = OptimizationRunner(
            config=minimal_experiment_config,
            db_path=temp_db_path,
            persist_bootstrap=True,
        )

        result = runner._run_simulation(seed=12345, purpose="test_no_blob", persist=True)

        with DatabaseManager(str(temp_db_path)) as db:
            # Check experiment_events does NOT contain simulation_run with events blob
            try:
                blob_count = db.conn.execute(
                    """
                    SELECT COUNT(*) FROM experiment_events
                    WHERE event_type = 'simulation_run'
                    AND json_extract_string(event_data, '$.simulation_id') = ?
                    """,
                    [result.simulation_id],
                ).fetchone()[0]
            except Exception:
                # Table may not exist if only simulation tables are used
                blob_count = 0

            assert blob_count == 0, (
                "Found simulation events as JSON blob in experiment_events. "
                "This is the OLD behavior - should use simulation_events table instead."
            )

    def test_experiment_context_stored_in_simulation_record(
        self, minimal_experiment_config: dict[str, Any], temp_db_path: Path
    ) -> None:
        """Simulation record should include experiment_run_id and iteration."""
        from payment_simulator.experiments.runner.optimization import OptimizationRunner
        from payment_simulator.persistence.connection import DatabaseManager

        runner = OptimizationRunner(
            config=minimal_experiment_config,
            db_path=temp_db_path,
            persist_bootstrap=True,
        )

        # Set experiment context
        runner._run_id = "exp-run-test-001"
        runner._current_iteration = 3

        result = runner._run_simulation(
            seed=12345, purpose="test_context", iteration=3, persist=True
        )

        with DatabaseManager(str(temp_db_path)) as db:
            row = db.conn.execute(
                """
                SELECT experiment_run_id, experiment_iteration
                FROM simulations WHERE simulation_id = ?
                """,
                [result.simulation_id],
            ).fetchone()

            assert row is not None, "Simulation record not found"
            assert row[0] == "exp-run-test-001", f"Expected exp-run-test-001, got {row[0]}"
            assert row[1] == 3, f"Expected iteration 3, got {row[1]}"

    def test_backward_compatibility_no_persist_no_tables(
        self, minimal_experiment_config: dict[str, Any], temp_db_path: Path
    ) -> None:
        """When persist=False, no simulation records should be created."""
        from payment_simulator.experiments.runner.optimization import OptimizationRunner
        from payment_simulator.persistence.connection import DatabaseManager
        from payment_simulator.persistence.queries import get_simulation_summary

        runner = OptimizationRunner(
            config=minimal_experiment_config,
            db_path=temp_db_path,
            persist_bootstrap=False,  # Persistence DISABLED
        )

        result = runner._run_simulation(seed=12345, purpose="test_no_persist", persist=False)

        with DatabaseManager(str(temp_db_path)) as db:
            summary = get_simulation_summary(db.conn, result.simulation_id)
            assert summary is None, (
                "Simulation record found when persist=False. "
                "Should not persist when flag is disabled."
            )

    def test_replay_command_finds_experiment_simulation(
        self, minimal_experiment_config: dict[str, Any], temp_db_path: Path
    ) -> None:
        """Simulations should be findable via standard replay queries."""
        from payment_simulator.experiments.runner.optimization import OptimizationRunner
        from payment_simulator.persistence.connection import DatabaseManager
        from payment_simulator.persistence.event_queries import get_simulation_events
        from payment_simulator.persistence.queries import get_simulation_summary

        runner = OptimizationRunner(
            config=minimal_experiment_config,
            db_path=temp_db_path,
            persist_bootstrap=True,
        )

        result = runner._run_simulation(seed=12345, purpose="test_replay", persist=True)

        # Verify all replay-required queries work
        with DatabaseManager(str(temp_db_path)) as db:
            # 1. Can find simulation summary
            summary = get_simulation_summary(db.conn, result.simulation_id)
            assert summary is not None

            # 2. Can query events
            events = get_simulation_events(db.conn, result.simulation_id)
            assert "events" in events
            assert "total" in events
```

---

## Step 2.2: Verify Tests Fail (RED)

**Action**: Run the integration tests and confirm they fail.

```bash
cd /home/user/SimCash/api
uv run pytest tests/integration/test_experiment_simulation_persistence.py -v 2>&1 | head -80
```

**Expected Output**: Tests should fail with assertions like:
```
AssertionError: Simulation xxx not found in simulations table.
This means SimulationPersistenceProvider is not being used.
```

**CHECKPOINT**: Do NOT proceed to Step 2.3 until you have confirmed tests fail.

---

## Step 2.3: Modify Experiment Runner (GREEN)

**Action**: Now modify `optimization.py` with MINIMAL changes to pass tests.

### Changes to `api/payment_simulator/experiments/runner/optimization.py`:

**1. Add import at top:**
```python
from payment_simulator.persistence.simulation_persistence_provider import (
    SimulationPersistenceProvider,
    StandardSimulationPersistenceProvider,
)
```

**2. Add provider attribute in `__init__`:**
```python
def __init__(
    self,
    config: ExperimentConfig | dict[str, Any],
    db_path: Path | str | None = None,
    persist_bootstrap: bool = False,
    # ... other params
) -> None:
    # ... existing init code ...

    # NEW: Initialize simulation persistence provider
    self._simulation_persistence_provider: SimulationPersistenceProvider | None = None
    if persist_bootstrap and db_path:
        from payment_simulator.persistence.connection import DatabaseManager
        # Create or reuse database manager
        if not hasattr(self, '_db_manager') or self._db_manager is None:
            self._db_manager = DatabaseManager(str(db_path))
        self._simulation_persistence_provider = StandardSimulationPersistenceProvider(
            self._db_manager
        )
```

**3. Modify `_run_simulation()` to use provider:**

Find the section that currently does:
```python
# OLD: Store as JSON blob
if self._repository and should_persist:
    event = EventRecord(
        event_type="simulation_run",
        event_data={"simulation_id": sim_id, "events": all_events},
    )
    self._repository.save_event(event)
```

Replace with:
```python
# NEW: Use SimulationPersistenceProvider
should_persist = persist if persist is not None else self._persist_bootstrap
if self._simulation_persistence_provider and should_persist:
    # Persist simulation start
    self._simulation_persistence_provider.persist_simulation_start(
        simulation_id=sim_id,
        config=ffi_config,
        experiment_run_id=self._run_id if hasattr(self, '_run_id') else None,
        experiment_iteration=iteration,
    )

    # Persist events per tick (need to track tick -> events mapping)
    # If events are collected per-tick during loop, persist there
    # Otherwise batch persist all events by tick
    events_by_tick: dict[int, list[dict]] = {}
    for event in all_events:
        tick = event.get("tick", 0)
        if tick not in events_by_tick:
            events_by_tick[tick] = []
        events_by_tick[tick].append(event)

    for tick, tick_events in sorted(events_by_tick.items()):
        self._simulation_persistence_provider.persist_tick_events(
            simulation_id=sim_id,
            tick=tick,
            events=tick_events,
        )

    # Persist completion metrics
    self._simulation_persistence_provider.persist_simulation_complete(
        simulation_id=sim_id,
        metrics={
            "total_arrivals": metrics.get("total_arrivals", 0),
            "total_settlements": metrics.get("total_settlements", 0),
            "total_costs": total_cost,
        },
    )

# REMOVE the old JSON blob persistence code
```

---

## Step 2.4: Verify Tests Pass (GREEN)

**Action**: Run integration tests - they should now pass.

```bash
cd /home/user/SimCash/api
uv run pytest tests/integration/test_experiment_simulation_persistence.py -v
```

**Expected**: All 6 tests pass.

**CHECKPOINT**: Do NOT proceed to Step 2.5 until ALL tests pass.

---

## Step 2.5: Verify Regression (No Breaking Changes)

**Action**: Run existing experiment tests to ensure backward compatibility.

```bash
cd /home/user/SimCash/api
uv run pytest tests/ -k "experiment" -v --tb=short 2>&1 | tail -30
```

**Expected**: All existing experiment tests still pass.

---

## Step 2.6: Refactor (REFACTOR)

**Action**: Clean up implementation while keeping all tests green.

Refactoring tasks:
1. Move event grouping by tick into simulation loop (persist per-tick instead of batching)
2. Add proper type hints
3. Handle database manager lifecycle properly
4. Add logging for persistence operations

After each change:
```bash
cd /home/user/SimCash/api
uv run pytest tests/integration/test_experiment_simulation_persistence.py -v
uv run pytest tests/ -k "experiment" -v --tb=short
```

---

## Files

| File | Action | TDD Phase |
|------|--------|-----------|
| `api/tests/integration/test_experiment_simulation_persistence.py` | CREATE | Step 2.1 (RED) |
| `api/payment_simulator/experiments/runner/optimization.py` | MODIFY | Step 2.3 (GREEN) |

---

## Verification Commands

```bash
# RED phase - integration tests must fail
uv run pytest tests/integration/test_experiment_simulation_persistence.py -v 2>&1 | grep -E "FAILED|AssertionError"

# GREEN phase - integration tests pass
uv run pytest tests/integration/test_experiment_simulation_persistence.py -v

# Regression check - existing tests still pass
uv run pytest tests/ -k "experiment" -v --tb=short

# Full verification
uv run pytest tests/integration/test_experiment_simulation_persistence.py tests/unit/test_simulation_persistence_provider.py -v
```

---

## Completion Criteria

- [ ] Step 2.1 complete: Integration test file created
- [ ] Step 2.2 complete: Tests verified to FAIL (RED confirmed)
- [ ] Step 2.3 complete: optimization.py modified
- [ ] Step 2.4 complete: All integration tests PASS (GREEN confirmed)
- [ ] Step 2.5 complete: Existing experiment tests still pass (no regression)
- [ ] Step 2.6 complete: Code refactored, all tests still pass
- [ ] Simulations written to `simulations` table
- [ ] Events written to `simulation_events` table (NOT as JSON blob)
- [ ] Experiment context (run_id, iteration) stored
- [ ] INV-11 verified by tests
