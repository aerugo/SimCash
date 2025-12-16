# Phase 1: SimulationPersistenceProvider Protocol

**Status**: Pending
**Started**:

---

## Objective

Define the `SimulationPersistenceProvider` protocol and create `StandardSimulationPersistenceProvider` implementation that wraps existing persistence infrastructure. This establishes the single source of truth for simulation persistence that both CLI and experiment runner will use.

---

## Invariants Enforced in This Phase

- **INV-1**: Money is Always i64 - All costs persisted as integer cents
- **INV-6**: Event Completeness - Events passed to provider must be complete
- **NEW INV-11**: Simulation Persistence Identity - This protocol IS the mechanism that enforces it

---

## TDD Steps

### Step 1.1: Write Failing Tests (RED)

Create `api/tests/unit/test_simulation_persistence_provider.py`:

**Test Cases**:
1. `test_protocol_is_runtime_checkable` - Verify Protocol can be checked at runtime
2. `test_standard_provider_implements_protocol` - Verify implementation satisfies Protocol
3. `test_persist_simulation_start_creates_record` - Verify simulation record created
4. `test_persist_tick_events_writes_to_table` - Verify events written to simulation_events
5. `test_persist_simulation_complete_updates_record` - Verify final metrics stored
6. `test_simulation_id_is_queryable` - Verify simulation can be found via standard queries
7. `test_events_are_queryable` - Verify events can be queried via get_simulation_events()
8. `test_experiment_context_stored` - Verify experiment_run_id and iteration stored when provided

```python
"""Unit tests for SimulationPersistenceProvider protocol and implementation."""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from payment_simulator.persistence.connection import DatabaseManager
from payment_simulator.persistence.event_queries import get_simulation_events
from payment_simulator.persistence.queries import get_simulation_summary
from payment_simulator.persistence.simulation_persistence_provider import (
    SimulationPersistenceProvider,
    StandardSimulationPersistenceProvider,
)

if TYPE_CHECKING:
    import duckdb


class TestSimulationPersistenceProviderProtocol:
    """Tests for the Protocol definition."""

    def test_protocol_is_runtime_checkable(self) -> None:
        """Protocol should be runtime checkable."""
        assert hasattr(SimulationPersistenceProvider, "__runtime_checkable__")

    def test_standard_provider_implements_protocol(self) -> None:
        """StandardSimulationPersistenceProvider should implement the Protocol."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            with DatabaseManager(str(db_path)) as db:
                provider = StandardSimulationPersistenceProvider(db)
                assert isinstance(provider, SimulationPersistenceProvider)


class TestStandardSimulationPersistenceProvider:
    """Tests for the standard implementation."""

    @pytest.fixture
    def db_manager(self) -> DatabaseManager:
        """Create a temporary database for testing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            with DatabaseManager(str(db_path)) as db:
                yield db

    @pytest.fixture
    def provider(self, db_manager: DatabaseManager) -> StandardSimulationPersistenceProvider:
        """Create a provider instance."""
        return StandardSimulationPersistenceProvider(db_manager)

    def test_persist_simulation_start_creates_record(
        self, provider: StandardSimulationPersistenceProvider, db_manager: DatabaseManager
    ) -> None:
        """persist_simulation_start should create a record in simulations table."""
        sim_id = "test-sim-001"
        config = {
            "ticks_per_day": 100,
            "num_days": 1,
            "rng_seed": 12345,
        }

        provider.persist_simulation_start(sim_id, config)

        # Verify record exists
        summary = get_simulation_summary(db_manager.conn, sim_id)
        assert summary is not None
        assert summary["simulation_id"] == sim_id

    def test_persist_tick_events_writes_to_table(
        self, provider: StandardSimulationPersistenceProvider, db_manager: DatabaseManager
    ) -> None:
        """persist_tick_events should write events to simulation_events table."""
        sim_id = "test-sim-002"
        config = {"ticks_per_day": 100, "num_days": 1}
        provider.persist_simulation_start(sim_id, config)

        events = [
            {
                "event_type": "Arrival",
                "tick": 0,
                "tx_id": "tx-001",
                "sender_id": "BANK_A",
                "receiver_id": "BANK_B",
                "amount": 100000,
            },
            {
                "event_type": "RtgsImmediateSettlement",
                "tick": 0,
                "tx_id": "tx-001",
                "sender_id": "BANK_A",
                "receiver_id": "BANK_B",
                "amount": 100000,
            },
        ]

        provider.persist_tick_events(sim_id, tick=0, events=events)

        # Verify events queryable
        result = get_simulation_events(db_manager.conn, sim_id, tick=0)
        assert result["total"] == 2

    def test_persist_simulation_complete_updates_record(
        self, provider: StandardSimulationPersistenceProvider, db_manager: DatabaseManager
    ) -> None:
        """persist_simulation_complete should update simulation record with metrics."""
        sim_id = "test-sim-003"
        config = {"ticks_per_day": 100, "num_days": 1}
        provider.persist_simulation_start(sim_id, config)

        metrics = {
            "total_arrivals": 50,
            "total_settlements": 48,
            "total_costs": 500000,  # $5,000 in cents
            "duration_seconds": 1.5,
        }

        provider.persist_simulation_complete(sim_id, metrics)

        # Verify metrics stored
        summary = get_simulation_summary(db_manager.conn, sim_id)
        assert summary["total_arrivals"] == 50
        assert summary["total_settlements"] == 48

    def test_simulation_id_is_queryable(
        self, provider: StandardSimulationPersistenceProvider, db_manager: DatabaseManager
    ) -> None:
        """Simulations should be queryable via standard queries."""
        sim_id = "test-sim-004"
        config = {"ticks_per_day": 100, "num_days": 1}
        provider.persist_simulation_start(sim_id, config)

        # Should be findable via standard query
        summary = get_simulation_summary(db_manager.conn, sim_id)
        assert summary is not None

    def test_events_are_queryable(
        self, provider: StandardSimulationPersistenceProvider, db_manager: DatabaseManager
    ) -> None:
        """Events should be queryable via get_simulation_events."""
        sim_id = "test-sim-005"
        config = {"ticks_per_day": 100, "num_days": 1}
        provider.persist_simulation_start(sim_id, config)

        events = [
            {"event_type": "Arrival", "tick": 5, "tx_id": "tx-100", "amount": 50000}
        ]
        provider.persist_tick_events(sim_id, tick=5, events=events)

        # Query by tick
        result = get_simulation_events(db_manager.conn, sim_id, tick=5)
        assert result["total"] == 1
        assert result["events"][0]["event_type"] == "Arrival"

    def test_experiment_context_stored(
        self, provider: StandardSimulationPersistenceProvider, db_manager: DatabaseManager
    ) -> None:
        """Experiment context (run_id, iteration) should be stored when provided."""
        sim_id = "test-sim-006"
        config = {"ticks_per_day": 100, "num_days": 1}

        # Provide experiment context
        provider.persist_simulation_start(
            sim_id,
            config,
            experiment_run_id="exp-run-001",
            experiment_iteration=5,
        )

        # Verify context stored (query raw table)
        result = db_manager.conn.execute(
            "SELECT experiment_run_id, experiment_iteration FROM simulations WHERE simulation_id = ?",
            [sim_id],
        ).fetchone()

        assert result is not None
        assert result[0] == "exp-run-001"
        assert result[1] == 5
```

### Step 1.2: Implement to Pass Tests (GREEN)

Create `api/payment_simulator/persistence/simulation_persistence_provider.py`:

```python
"""SimulationPersistenceProvider protocol for unified simulation persistence.

This module defines a Protocol-based abstraction for persisting simulation data.
The goal is to ensure IDENTICAL persistence across all code paths (CLI run command
and experiment runner).

INVARIANT (INV-11: Simulation Persistence Identity):
For any simulation S, persistence MUST produce identical database records
regardless of which code path executes the simulation.

This follows the same pattern as:
- INV-5 (Replay Identity) via StateProvider
- INV-9 (Policy Evaluation Identity) via PolicyConfigBuilder
- INV-10 (Scenario Config Identity) via ScenarioConfigBuilder

Example:
    >>> with DatabaseManager("simulation_data.db") as db:
    ...     provider = StandardSimulationPersistenceProvider(db)
    ...     provider.persist_simulation_start("sim-001", config)
    ...     provider.persist_tick_events("sim-001", tick=0, events=events)
    ...     provider.persist_simulation_complete("sim-001", metrics)
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from payment_simulator.persistence.connection import DatabaseManager
from payment_simulator.persistence.event_writer import write_events_batch


@runtime_checkable
class SimulationPersistenceProvider(Protocol):
    """Protocol for persisting simulation data.

    This interface ensures IDENTICAL persistence across all code paths
    (CLI and experiment runner).

    Implementations MUST satisfy the Simulation Persistence Identity (INV-11):
    For any simulation, output records MUST be identical regardless of which
    code path calls the provider.

    Example:
        >>> provider = StandardSimulationPersistenceProvider(db_manager)
        >>> provider.persist_simulation_start(sim_id, config)
        >>> for tick in range(total_ticks):
        ...     events = run_tick()
        ...     provider.persist_tick_events(sim_id, tick, events)
        >>> provider.persist_simulation_complete(sim_id, metrics)
    """

    def persist_simulation_start(
        self,
        simulation_id: str,
        config: dict[str, Any],
        experiment_run_id: str | None = None,
        experiment_iteration: int | None = None,
    ) -> None:
        """Persist simulation start record.

        Creates entry in simulations table with initial metadata.

        Args:
            simulation_id: Unique simulation identifier.
            config: Simulation configuration dict.
            experiment_run_id: Optional experiment run ID for cross-reference.
            experiment_iteration: Optional experiment iteration number.
        """
        ...

    def persist_tick_events(
        self,
        simulation_id: str,
        tick: int,
        events: list[dict[str, Any]],
    ) -> None:
        """Persist events for a single tick.

        Writes events to simulation_events table.

        Args:
            simulation_id: Simulation identifier.
            tick: Tick number.
            events: List of event dicts from Orchestrator.get_tick_events().
        """
        ...

    def persist_simulation_complete(
        self,
        simulation_id: str,
        metrics: dict[str, Any],
    ) -> None:
        """Persist final simulation metrics.

        Updates simulation record with final statistics.

        Args:
            simulation_id: Simulation identifier.
            metrics: Final metrics dict including total_arrivals, total_settlements, etc.
        """
        ...


class StandardSimulationPersistenceProvider:
    """Standard implementation of SimulationPersistenceProvider.

    Uses existing persistence infrastructure:
    - DatabaseManager for connection management
    - write_events_batch() for event persistence
    - simulations table for metadata

    This is the SINGLE implementation that ALL code paths must use.

    Example:
        >>> with DatabaseManager("simulation_data.db") as db:
        ...     provider = StandardSimulationPersistenceProvider(db)
        ...     provider.persist_simulation_start("sim-001", config)
    """

    def __init__(self, db_manager: DatabaseManager) -> None:
        """Initialize provider with database manager.

        Args:
            db_manager: DatabaseManager instance for database operations.
        """
        self._db = db_manager
        self._ticks_per_day: dict[str, int] = {}  # Cache for day calculation

    def persist_simulation_start(
        self,
        simulation_id: str,
        config: dict[str, Any],
        experiment_run_id: str | None = None,
        experiment_iteration: int | None = None,
    ) -> None:
        """Persist simulation start record.

        Creates entry in simulations table with initial metadata.

        Args:
            simulation_id: Unique simulation identifier.
            config: Simulation configuration dict.
            experiment_run_id: Optional experiment run ID for cross-reference.
            experiment_iteration: Optional experiment iteration number.
        """
        import json
        from datetime import datetime

        # Cache ticks_per_day for day calculation
        self._ticks_per_day[simulation_id] = config.get("ticks_per_day", 100)

        # Extract config values
        ticks_per_day = config.get("ticks_per_day", 100)
        num_days = config.get("num_days", 1)
        total_ticks = ticks_per_day * num_days
        config_json = json.dumps(config)

        # Insert into simulations table
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
        """Persist events for a single tick.

        Writes events to simulation_events table using existing write_events_batch().

        Args:
            simulation_id: Simulation identifier.
            tick: Tick number.
            events: List of event dicts from Orchestrator.get_tick_events().
        """
        if not events:
            return

        # Calculate day from tick
        ticks_per_day = self._ticks_per_day.get(simulation_id, 100)
        day = tick // ticks_per_day

        # Use existing write_events_batch
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
        """Persist final simulation metrics.

        Updates simulation record with final statistics.

        Args:
            simulation_id: Simulation identifier.
            metrics: Final metrics dict.
        """
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
                metrics.get("completed_at") or __import__("datetime").datetime.now().isoformat(),
                simulation_id,
            ],
        )

        # Clean up cache
        self._ticks_per_day.pop(simulation_id, None)
```

### Step 1.3: Refactor

- Ensure type safety (no bare `Any` where avoidable)
- Add comprehensive docstrings with examples
- Add `experiment_run_id` and `experiment_iteration` columns to simulations table schema if not present

---

## Implementation Details

### Schema Update Required

The `simulations` table needs two new nullable columns for experiment context:

```sql
ALTER TABLE simulations ADD COLUMN experiment_run_id VARCHAR;
ALTER TABLE simulations ADD COLUMN experiment_iteration INTEGER;
```

This should be added as a migration in `api/payment_simulator/persistence/migrations/`.

### Edge Cases to Handle

- **Empty events list**: `persist_tick_events` should handle gracefully (no-op)
- **Missing config keys**: Use sensible defaults for optional config values
- **Duplicate simulation_id**: Should raise error (primary key constraint)
- **No experiment context**: Columns remain NULL when not provided

---

## Files

| File | Action |
|------|--------|
| `api/payment_simulator/persistence/simulation_persistence_provider.py` | CREATE |
| `api/tests/unit/test_simulation_persistence_provider.py` | CREATE |
| `api/payment_simulator/persistence/__init__.py` | MODIFY (add exports) |
| `api/payment_simulator/persistence/migrations/XXX_add_experiment_context.sql` | CREATE |

---

## Verification

```bash
# Run tests
cd /home/user/SimCash/api
uv run pytest tests/unit/test_simulation_persistence_provider.py -v

# Type check
uv run mypy payment_simulator/persistence/simulation_persistence_provider.py

# Lint
uv run ruff check payment_simulator/persistence/simulation_persistence_provider.py
```

---

## Completion Criteria

- [ ] All 8 test cases pass
- [ ] Type check passes (mypy)
- [ ] Lint passes (ruff)
- [ ] Protocol is `@runtime_checkable`
- [ ] Implementation uses existing `write_events_batch()`
- [ ] Migration adds experiment context columns
- [ ] Docstrings with examples added
- [ ] INV-11 verified by tests
