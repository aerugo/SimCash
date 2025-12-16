# Phase 1: SimulationPersistenceProvider Protocol

**Status**: Pending
**Started**:

---

## Objective

Define the `SimulationPersistenceProvider` protocol and create `StandardSimulationPersistenceProvider` implementation that wraps existing persistence infrastructure.

---

## Invariants Enforced in This Phase

- **INV-1**: Money is Always i64 - All costs persisted as integer cents
- **INV-6**: Event Completeness - Events passed to provider must be complete
- **NEW INV-11**: Simulation Persistence Identity - This protocol IS the mechanism that enforces it

---

## Strict TDD Workflow

**CRITICAL**: Follow this exact sequence. Do NOT skip steps or combine RED/GREEN phases.

```
┌─────────────────────────────────────────────────────────────────┐
│  Step 1: Write tests ONLY (no implementation)                   │
│  Step 2: Run tests → Verify they FAIL (RED)                     │
│  Step 3: Write MINIMAL code to pass tests (GREEN)               │
│  Step 4: Refactor while keeping tests green (REFACTOR)          │
└─────────────────────────────────────────────────────────────────┘
```

---

## Step 1.1: Write Failing Tests (RED)

**Action**: Create test file ONLY. Do NOT create the implementation file yet.

Create `api/tests/unit/test_simulation_persistence_provider.py`:

```python
"""Unit tests for SimulationPersistenceProvider protocol and implementation.

TDD Phase: RED - These tests define the expected behavior.
The implementation does not exist yet - tests MUST fail initially.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest


class TestSimulationPersistenceProviderProtocol:
    """Tests for the Protocol definition.

    These tests will fail with ImportError until the module is created.
    """

    def test_protocol_exists_and_is_importable(self) -> None:
        """Protocol should be importable from persistence module."""
        from payment_simulator.persistence.simulation_persistence_provider import (
            SimulationPersistenceProvider,
        )
        assert SimulationPersistenceProvider is not None

    def test_protocol_is_runtime_checkable(self) -> None:
        """Protocol should be runtime checkable for isinstance() checks."""
        from payment_simulator.persistence.simulation_persistence_provider import (
            SimulationPersistenceProvider,
        )
        # @runtime_checkable decorator adds this attribute
        assert hasattr(SimulationPersistenceProvider, "__protocol_attrs__") or \
               hasattr(SimulationPersistenceProvider, "__subclasshook__")

    def test_protocol_has_persist_simulation_start_method(self) -> None:
        """Protocol should define persist_simulation_start method."""
        from payment_simulator.persistence.simulation_persistence_provider import (
            SimulationPersistenceProvider,
        )
        assert hasattr(SimulationPersistenceProvider, "persist_simulation_start")

    def test_protocol_has_persist_tick_events_method(self) -> None:
        """Protocol should define persist_tick_events method."""
        from payment_simulator.persistence.simulation_persistence_provider import (
            SimulationPersistenceProvider,
        )
        assert hasattr(SimulationPersistenceProvider, "persist_tick_events")

    def test_protocol_has_persist_simulation_complete_method(self) -> None:
        """Protocol should define persist_simulation_complete method."""
        from payment_simulator.persistence.simulation_persistence_provider import (
            SimulationPersistenceProvider,
        )
        assert hasattr(SimulationPersistenceProvider, "persist_simulation_complete")


class TestStandardSimulationPersistenceProviderExists:
    """Tests that the standard implementation exists.

    These tests will fail with ImportError until implementation is created.
    """

    def test_standard_provider_exists_and_is_importable(self) -> None:
        """StandardSimulationPersistenceProvider should be importable."""
        from payment_simulator.persistence.simulation_persistence_provider import (
            StandardSimulationPersistenceProvider,
        )
        assert StandardSimulationPersistenceProvider is not None

    def test_standard_provider_implements_protocol(self) -> None:
        """StandardSimulationPersistenceProvider should implement the Protocol."""
        from payment_simulator.persistence.connection import DatabaseManager
        from payment_simulator.persistence.simulation_persistence_provider import (
            SimulationPersistenceProvider,
            StandardSimulationPersistenceProvider,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            with DatabaseManager(str(db_path)) as db:
                provider = StandardSimulationPersistenceProvider(db)
                assert isinstance(provider, SimulationPersistenceProvider)


class TestPersistSimulationStart:
    """Tests for persist_simulation_start behavior."""

    @pytest.fixture
    def db_and_provider(self):
        """Create database and provider for testing."""
        from payment_simulator.persistence.connection import DatabaseManager
        from payment_simulator.persistence.simulation_persistence_provider import (
            StandardSimulationPersistenceProvider,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            with DatabaseManager(str(db_path)) as db:
                provider = StandardSimulationPersistenceProvider(db)
                yield db, provider

    def test_creates_simulation_record(self, db_and_provider) -> None:
        """persist_simulation_start should create a record in simulations table."""
        from payment_simulator.persistence.queries import get_simulation_summary

        db, provider = db_and_provider
        sim_id = "test-sim-001"
        config = {"ticks_per_day": 100, "num_days": 1, "rng_seed": 12345}

        provider.persist_simulation_start(sim_id, config)

        summary = get_simulation_summary(db.conn, sim_id)
        assert summary is not None
        assert summary["simulation_id"] == sim_id

    def test_stores_experiment_context_when_provided(self, db_and_provider) -> None:
        """Experiment run_id and iteration should be stored when provided."""
        db, provider = db_and_provider
        sim_id = "test-sim-002"
        config = {"ticks_per_day": 100, "num_days": 1}

        provider.persist_simulation_start(
            sim_id,
            config,
            experiment_run_id="exp-run-001",
            experiment_iteration=5,
        )

        result = db.conn.execute(
            "SELECT experiment_run_id, experiment_iteration FROM simulations WHERE simulation_id = ?",
            [sim_id],
        ).fetchone()

        assert result is not None
        assert result[0] == "exp-run-001"
        assert result[1] == 5

    def test_experiment_context_null_when_not_provided(self, db_and_provider) -> None:
        """Experiment context columns should be NULL when not provided."""
        db, provider = db_and_provider
        sim_id = "test-sim-003"
        config = {"ticks_per_day": 100, "num_days": 1}

        provider.persist_simulation_start(sim_id, config)

        result = db.conn.execute(
            "SELECT experiment_run_id, experiment_iteration FROM simulations WHERE simulation_id = ?",
            [sim_id],
        ).fetchone()

        assert result[0] is None
        assert result[1] is None


class TestPersistTickEvents:
    """Tests for persist_tick_events behavior."""

    @pytest.fixture
    def db_and_provider_with_simulation(self):
        """Create database, provider, and initial simulation record."""
        from payment_simulator.persistence.connection import DatabaseManager
        from payment_simulator.persistence.simulation_persistence_provider import (
            StandardSimulationPersistenceProvider,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            with DatabaseManager(str(db_path)) as db:
                provider = StandardSimulationPersistenceProvider(db)
                sim_id = "test-sim-events"
                provider.persist_simulation_start(sim_id, {"ticks_per_day": 100, "num_days": 1})
                yield db, provider, sim_id

    def test_writes_events_to_simulation_events_table(self, db_and_provider_with_simulation) -> None:
        """Events should be written to simulation_events table."""
        from payment_simulator.persistence.event_queries import get_simulation_events

        db, provider, sim_id = db_and_provider_with_simulation
        events = [
            {"event_type": "Arrival", "tick": 0, "tx_id": "tx-001", "amount": 100000},
            {"event_type": "RtgsImmediateSettlement", "tick": 0, "tx_id": "tx-001", "amount": 100000},
        ]

        provider.persist_tick_events(sim_id, tick=0, events=events)

        result = get_simulation_events(db.conn, sim_id, tick=0)
        assert result["total"] == 2

    def test_handles_empty_events_list(self, db_and_provider_with_simulation) -> None:
        """Empty events list should not raise error."""
        from payment_simulator.persistence.event_queries import get_simulation_events

        db, provider, sim_id = db_and_provider_with_simulation

        # Should not raise
        provider.persist_tick_events(sim_id, tick=0, events=[])

        result = get_simulation_events(db.conn, sim_id, tick=0)
        assert result["total"] == 0

    def test_events_queryable_by_tick(self, db_and_provider_with_simulation) -> None:
        """Events should be queryable by tick number."""
        from payment_simulator.persistence.event_queries import get_simulation_events

        db, provider, sim_id = db_and_provider_with_simulation

        # Events at tick 5
        provider.persist_tick_events(sim_id, tick=5, events=[
            {"event_type": "Arrival", "tick": 5, "tx_id": "tx-100", "amount": 50000}
        ])
        # Events at tick 10
        provider.persist_tick_events(sim_id, tick=10, events=[
            {"event_type": "Arrival", "tick": 10, "tx_id": "tx-200", "amount": 60000}
        ])

        # Query tick 5 only
        result = get_simulation_events(db.conn, sim_id, tick=5)
        assert result["total"] == 1
        assert result["events"][0]["event_type"] == "Arrival"


class TestPersistSimulationComplete:
    """Tests for persist_simulation_complete behavior."""

    @pytest.fixture
    def db_and_provider_with_simulation(self):
        """Create database, provider, and initial simulation record."""
        from payment_simulator.persistence.connection import DatabaseManager
        from payment_simulator.persistence.simulation_persistence_provider import (
            StandardSimulationPersistenceProvider,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            with DatabaseManager(str(db_path)) as db:
                provider = StandardSimulationPersistenceProvider(db)
                sim_id = "test-sim-complete"
                provider.persist_simulation_start(sim_id, {"ticks_per_day": 100, "num_days": 1})
                yield db, provider, sim_id

    def test_updates_simulation_with_metrics(self, db_and_provider_with_simulation) -> None:
        """persist_simulation_complete should update simulation record with metrics."""
        from payment_simulator.persistence.queries import get_simulation_summary

        db, provider, sim_id = db_and_provider_with_simulation
        metrics = {
            "total_arrivals": 50,
            "total_settlements": 48,
            "total_costs": 500000,
        }

        provider.persist_simulation_complete(sim_id, metrics)

        summary = get_simulation_summary(db.conn, sim_id)
        assert summary["total_arrivals"] == 50
        assert summary["total_settlements"] == 48
```

---

## Step 1.2: Verify Tests Fail (RED)

**Action**: Run the tests and confirm they fail with `ImportError` or similar.

```bash
cd /home/user/SimCash/api
uv run pytest tests/unit/test_simulation_persistence_provider.py -v 2>&1 | head -50
```

**Expected Output**:
```
FAILED tests/unit/test_simulation_persistence_provider.py::TestSimulationPersistenceProviderProtocol::test_protocol_exists_and_is_importable
    ModuleNotFoundError: No module named 'payment_simulator.persistence.simulation_persistence_provider'
```

**CHECKPOINT**: Do NOT proceed to Step 1.3 until you have confirmed tests fail.

---

## Step 1.3: Write Minimal Implementation (GREEN)

**Action**: Now create the implementation file with MINIMAL code to pass tests.

Create `api/payment_simulator/persistence/simulation_persistence_provider.py`:

```python
"""SimulationPersistenceProvider protocol for unified simulation persistence.

INVARIANT (INV-11: Simulation Persistence Identity):
For any simulation S, persistence MUST produce identical database records
regardless of which code path executes the simulation.
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from payment_simulator.persistence.connection import DatabaseManager
from payment_simulator.persistence.event_writer import write_events_batch


@runtime_checkable
class SimulationPersistenceProvider(Protocol):
    """Protocol for persisting simulation data."""

    def persist_simulation_start(
        self,
        simulation_id: str,
        config: dict[str, Any],
        experiment_run_id: str | None = None,
        experiment_iteration: int | None = None,
    ) -> None:
        """Persist simulation start record."""
        ...

    def persist_tick_events(
        self,
        simulation_id: str,
        tick: int,
        events: list[dict[str, Any]],
    ) -> None:
        """Persist events for a single tick."""
        ...

    def persist_simulation_complete(
        self,
        simulation_id: str,
        metrics: dict[str, Any],
    ) -> None:
        """Persist final simulation metrics."""
        ...


class StandardSimulationPersistenceProvider:
    """Standard implementation of SimulationPersistenceProvider."""

    def __init__(self, db_manager: DatabaseManager) -> None:
        self._db = db_manager
        self._ticks_per_day: dict[str, int] = {}

    def persist_simulation_start(
        self,
        simulation_id: str,
        config: dict[str, Any],
        experiment_run_id: str | None = None,
        experiment_iteration: int | None = None,
    ) -> None:
        import json
        from datetime import datetime

        self._ticks_per_day[simulation_id] = config.get("ticks_per_day", 100)
        ticks_per_day = config.get("ticks_per_day", 100)
        num_days = config.get("num_days", 1)
        total_ticks = ticks_per_day * num_days
        config_json = json.dumps(config)

        self._db.conn.execute(
            """
            INSERT INTO simulations (
                simulation_id, config_json, config_file, created_at,
                total_ticks, ticks_per_day, num_days,
                experiment_run_id, experiment_iteration
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                simulation_id,
                config_json,
                config.get("config_file", ""),
                datetime.now().isoformat(),
                total_ticks,
                ticks_per_day,
                num_days,
                experiment_run_id,
                experiment_iteration,
            ],
        )

    def persist_tick_events(
        self,
        simulation_id: str,
        tick: int,
        events: list[dict[str, Any]],
    ) -> None:
        if not events:
            return

        ticks_per_day = self._ticks_per_day.get(simulation_id, 100)
        day = tick // ticks_per_day

        write_events_batch(
            conn=self._db.conn,
            simulation_id=simulation_id,
            tick=tick,
            day=day,
            events=events,
        )

    def persist_simulation_complete(
        self,
        simulation_id: str,
        metrics: dict[str, Any],
    ) -> None:
        from datetime import datetime

        self._db.conn.execute(
            """
            UPDATE simulations SET
                total_arrivals = ?,
                total_settlements = ?,
                total_costs = ?,
                completed_at = ?
            WHERE simulation_id = ?
            """,
            [
                metrics.get("total_arrivals", 0),
                metrics.get("total_settlements", 0),
                metrics.get("total_costs", 0),
                metrics.get("completed_at") or datetime.now().isoformat(),
                simulation_id,
            ],
        )

        self._ticks_per_day.pop(simulation_id, None)
```

---

## Step 1.4: Verify Tests Pass (GREEN)

**Action**: Run tests again - they should now pass.

```bash
cd /home/user/SimCash/api
uv run pytest tests/unit/test_simulation_persistence_provider.py -v
```

**Expected**: All tests pass.

**CHECKPOINT**: Do NOT proceed to Step 1.5 until ALL tests pass.

---

## Step 1.5: Refactor (REFACTOR)

**Action**: Clean up implementation while keeping tests green. After each change, run tests.

Refactoring tasks:
1. Add comprehensive docstrings with examples
2. Add type annotations where missing
3. Extract magic numbers to constants
4. Ensure INV-1 compliance (integer cents)

```bash
# After each refactoring change:
cd /home/user/SimCash/api
uv run pytest tests/unit/test_simulation_persistence_provider.py -v
```

---

## Step 1.6: Add Migration (if needed)

**Prerequisite**: Check if `simulations` table already has experiment context columns.

```bash
cd /home/user/SimCash/api
uv run python -c "
from payment_simulator.persistence.connection import DatabaseManager
import tempfile
from pathlib import Path

with tempfile.TemporaryDirectory() as tmpdir:
    with DatabaseManager(str(Path(tmpdir) / 'test.db')) as db:
        schema = db.conn.execute('DESCRIBE simulations').fetchall()
        columns = [row[0] for row in schema]
        print('Columns:', columns)
        print('Has experiment_run_id:', 'experiment_run_id' in columns)
        print('Has experiment_iteration:', 'experiment_iteration' in columns)
"
```

If columns are missing, create migration.

---

## Files

| File | Action | TDD Phase |
|------|--------|-----------|
| `api/tests/unit/test_simulation_persistence_provider.py` | CREATE | Step 1.1 (RED) |
| `api/payment_simulator/persistence/simulation_persistence_provider.py` | CREATE | Step 1.3 (GREEN) |
| `api/payment_simulator/persistence/__init__.py` | MODIFY | Step 1.5 (REFACTOR) |

---

## Verification Commands

```bash
# RED phase - tests must fail
uv run pytest tests/unit/test_simulation_persistence_provider.py -v 2>&1 | grep -E "FAILED|ERROR|ModuleNotFoundError"

# GREEN phase - tests must pass
uv run pytest tests/unit/test_simulation_persistence_provider.py -v

# REFACTOR phase - tests still pass + quality checks
uv run pytest tests/unit/test_simulation_persistence_provider.py -v
uv run mypy payment_simulator/persistence/simulation_persistence_provider.py
uv run ruff check payment_simulator/persistence/simulation_persistence_provider.py
```

---

## Completion Criteria

- [ ] Step 1.1 complete: Test file created
- [ ] Step 1.2 complete: Tests verified to FAIL (RED confirmed)
- [ ] Step 1.3 complete: Implementation created
- [ ] Step 1.4 complete: All tests PASS (GREEN confirmed)
- [ ] Step 1.5 complete: Code refactored, tests still pass
- [ ] Type check passes (mypy)
- [ ] Lint passes (ruff)
- [ ] Protocol is `@runtime_checkable`
- [ ] INV-11 verified by tests
