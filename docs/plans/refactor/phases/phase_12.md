# Phase 12: Castro Migration to Core Infrastructure

**Status:** Planned
**Created:** 2025-12-11
**Dependencies:** Phase 11 (StateProvider Protocol and Unified Persistence)
**Risk:** Medium (backward compatibility, replay identity preservation)
**Breaking Changes:** None (maintains Castro's public API)

---

## Purpose

Phase 12 migrates Castro experiments to use the core infrastructure created in Phase 11:

1. **StateProvider Migration** (Task 12.1): Castro uses core `ExperimentStateProviderProtocol`
2. **Persistence Migration** (Task 12.2): Castro uses core `ExperimentRepository`
3. **Event System Alignment** (Task 12.3): Align Castro events with core `EventRecord`

**Target outcome**: Reduce Castro code by ~400 lines while maintaining full backward compatibility and replay identity.

---

## Current State Analysis

### Castro's StateProvider (`castro/state_provider.py` ~354 lines)

```python
# Castro's current protocol
@runtime_checkable
class ExperimentStateProvider(Protocol):
    @property
    def run_id(self) -> str: ...
    def get_run_metadata(self) -> dict[str, Any] | None: ...
    def get_all_events(self) -> Iterator[ExperimentEvent]: ...
    def get_events_for_iteration(self, iteration: int) -> list[ExperimentEvent]: ...
    def get_final_result(self) -> dict[str, Any]: ...

# Implementations
class LiveExperimentProvider: ...  # ~90 lines
class DatabaseExperimentProvider: ...  # ~120 lines
class EventEmitter: ...  # ~40 lines
```

### Castro's Persistence (`castro/persistence/` ~400 lines)

```python
# castro/persistence/repository.py
class ExperimentEventRepository:
    def initialize_schema(self) -> None: ...
    def save_run_record(self, record: ExperimentRunRecord) -> None: ...
    def get_run_record(self, run_id: str) -> ExperimentRunRecord | None: ...
    def update_run_status(self, run_id: str, ...) -> None: ...
    def list_runs(self, ...) -> list[ExperimentRunRecord]: ...
    def save_event(self, event: ExperimentEvent) -> None: ...
    def get_events_for_run(self, run_id: str) -> Iterator[ExperimentEvent]: ...
    def get_events_for_iteration(self, run_id: str, iteration: int) -> Iterator[ExperimentEvent]: ...

# castro/persistence/models.py
@dataclass
class ExperimentRunRecord: ...
```

### Castro's Events (`castro/events.py` ~418 lines)

```python
# Event types
EVENT_EXPERIMENT_START = "experiment_start"
EVENT_ITERATION_START = "iteration_start"
EVENT_BOOTSTRAP_EVALUATION = "bootstrap_evaluation"
EVENT_LLM_CALL = "llm_call"
EVENT_LLM_INTERACTION = "llm_interaction"
EVENT_POLICY_CHANGE = "policy_change"
EVENT_POLICY_REJECTED = "policy_rejected"
EVENT_EXPERIMENT_END = "experiment_end"

@dataclass
class ExperimentEvent:
    event_type: str
    run_id: str
    iteration: int
    timestamp: datetime
    details: dict[str, Any]

# Event creation helpers (~250 lines)
def create_experiment_start_event(...) -> ExperimentEvent: ...
def create_iteration_start_event(...) -> ExperimentEvent: ...
# ... etc
```

### Core Modules (from Phase 11)

```python
# Core StateProvider Protocol
@runtime_checkable
class ExperimentStateProviderProtocol(Protocol):
    def get_experiment_info(self) -> dict[str, Any]: ...
    def get_total_iterations(self) -> int: ...
    def get_iteration_events(self, iteration: int) -> list[dict[str, Any]]: ...
    def get_iteration_policies(self, iteration: int) -> dict[str, Any]: ...
    def get_iteration_costs(self, iteration: int) -> dict[str, int]: ...
    def get_iteration_accepted_changes(self, iteration: int) -> dict[str, bool]: ...

# Core Persistence
class ExperimentRepository:
    def save_experiment(self, record: ExperimentRecord) -> None: ...
    def load_experiment(self, run_id: str) -> ExperimentRecord | None: ...
    def save_iteration(self, record: IterationRecord) -> None: ...
    def get_iterations(self, run_id: str) -> list[IterationRecord]: ...
    def save_event(self, event: EventRecord) -> None: ...
    def get_events(self, run_id: str, iteration: int) -> list[EventRecord]: ...
    def as_state_provider(self, run_id: str) -> ExperimentStateProviderProtocol: ...
```

---

## Migration Strategy

### Option A: Full Replacement (NOT RECOMMENDED)
- Replace all Castro classes with core classes
- Risk: Breaking changes, loss of Castro-specific features
- Rejected

### Option B: Adapter Pattern (RECOMMENDED)
- Castro keeps its public API
- Internal implementation wraps core modules
- Castro-specific features (LLM events) remain in Castro
- Gradual, safe migration

### Option C: Re-export with Thin Wrappers
- Similar to Option B but simpler
- Castro re-exports core classes where API matches
- Thin wrappers where API differs

**Selected: Option B (Adapter Pattern)**

Rationale:
- Maintains backward compatibility for existing Castro users
- Allows Castro-specific extensions (LLM interaction events)
- Reduces code while keeping clear separation
- Can be done incrementally

---

## Phase 12 Tasks

### Task 12.1: Adapt Castro StateProvider to Core Protocol

**Impact:** ~200 lines removed from Castro
**Risk:** Medium - protocol method signature alignment
**TDD Test File:** `experiments/castro/tests/test_state_provider_migration.py`

**Goals:**
1. Make `LiveExperimentProvider` implement core protocol
2. Make `DatabaseExperimentProvider` use core `DatabaseStateProvider` internally
3. Keep Castro's `ExperimentEvent` for event-specific features
4. Deprecate `EventEmitter` (merge into LiveExperimentProvider)

**API Mapping:**

| Castro Method | Core Method | Notes |
|---------------|-------------|-------|
| `run_id` property | N/A (pass as param) | Keep in Castro |
| `get_run_metadata()` | `get_experiment_info()` | Rename wrapper |
| `get_all_events()` | N/A | Castro-specific, keep |
| `get_events_for_iteration()` | `get_iteration_events()` | Adapt return type |
| `get_final_result()` | N/A | Castro-specific, keep |
| N/A | `get_total_iterations()` | Add to Castro |
| N/A | `get_iteration_policies()` | Add to Castro |
| N/A | `get_iteration_costs()` | Add to Castro |
| N/A | `get_iteration_accepted_changes()` | Add to Castro |

---

### Task 12.2: Migrate Castro Persistence to Core Repository

**Impact:** ~200 lines removed from Castro
**Risk:** Medium - database schema compatibility
**TDD Test File:** `experiments/castro/tests/test_persistence_migration.py`

**Goals:**
1. `ExperimentEventRepository` wraps core `ExperimentRepository`
2. Castro keeps `ExperimentRunRecord` as facade over `ExperimentRecord`
3. Castro keeps its `ExperimentEvent` for typed events
4. Add schema migration for existing databases (optional)

**Database Schema Mapping:**

| Castro Table | Core Table | Migration |
|--------------|------------|-----------|
| `experiment_runs` | `experiments` | Adapter handles both |
| `experiment_events` | `experiment_events` | Compatible |
| N/A | `experiment_iterations` | New in core |

---

### Task 12.3: Event System Alignment

**Impact:** ~100 lines refactored
**Risk:** Low - events are self-contained
**TDD Test File:** `experiments/castro/tests/test_event_migration.py`

**Goals:**
1. Castro's `ExperimentEvent` can convert to/from core `EventRecord`
2. Event creation helpers remain in Castro (domain-specific)
3. Persistence uses core `EventRecord` internally

---

## TDD Test Specifications

### Test File 1: `experiments/castro/tests/test_state_provider_migration.py`

```python
"""TDD tests for Castro StateProvider migration to core.

Verifies Castro providers implement core protocol while
maintaining backward compatibility.

Write these tests FIRST, then implement.
"""

from __future__ import annotations

import pytest
from typing import Any


class TestCastroProviderImplementsCoreProtocol:
    """Tests that Castro providers implement core protocol."""

    def test_live_provider_is_core_protocol_instance(self) -> None:
        """LiveExperimentProvider should satisfy core protocol isinstance."""
        from castro.state_provider import LiveExperimentProvider
        from payment_simulator.experiments.runner import (
            ExperimentStateProviderProtocol,
        )

        provider = LiveExperimentProvider(
            run_id="test-run",
            experiment_name="test",
            description="Test experiment",
            model="test-model",
            max_iterations=10,
            num_samples=5,
        )

        assert isinstance(provider, ExperimentStateProviderProtocol)

    def test_live_provider_has_get_experiment_info(self) -> None:
        """LiveExperimentProvider should have get_experiment_info."""
        from castro.state_provider import LiveExperimentProvider

        provider = LiveExperimentProvider(
            run_id="test-run",
            experiment_name="test",
            description="desc",
            model="model",
            max_iterations=10,
            num_samples=5,
        )

        info = provider.get_experiment_info()
        assert isinstance(info, dict)
        assert "experiment_name" in info

    def test_live_provider_has_get_total_iterations(self) -> None:
        """LiveExperimentProvider should have get_total_iterations."""
        from castro.state_provider import LiveExperimentProvider

        provider = LiveExperimentProvider(
            run_id="test-run",
            experiment_name="test",
            description="desc",
            model="model",
            max_iterations=10,
            num_samples=5,
        )

        count = provider.get_total_iterations()
        assert isinstance(count, int)
        assert count >= 0

    def test_live_provider_has_get_iteration_events(self) -> None:
        """LiveExperimentProvider should have get_iteration_events."""
        from castro.state_provider import LiveExperimentProvider

        provider = LiveExperimentProvider(
            run_id="test-run",
            experiment_name="test",
            description="desc",
            model="model",
            max_iterations=10,
            num_samples=5,
        )

        events = provider.get_iteration_events(0)
        assert isinstance(events, list)

    def test_live_provider_has_get_iteration_costs(self) -> None:
        """LiveExperimentProvider should have get_iteration_costs."""
        from castro.state_provider import LiveExperimentProvider

        provider = LiveExperimentProvider(
            run_id="test-run",
            experiment_name="test",
            description="desc",
            model="model",
            max_iterations=10,
            num_samples=5,
        )

        costs = provider.get_iteration_costs(0)
        assert isinstance(costs, dict)

    def test_live_provider_costs_are_integer_cents(self) -> None:
        """All costs must be integer cents (INV-1)."""
        from castro.state_provider import LiveExperimentProvider

        provider = LiveExperimentProvider(
            run_id="test-run",
            experiment_name="test",
            description="desc",
            model="model",
            max_iterations=10,
            num_samples=5,
        )

        # Simulate recording iteration with costs
        provider.record_iteration_costs(0, {"BANK_A": 100050})

        costs = provider.get_iteration_costs(0)
        for agent_id, cost in costs.items():
            assert isinstance(cost, int), f"Cost for {agent_id} must be int"


class TestCastroBackwardCompatibility:
    """Tests that Castro's existing API still works."""

    def test_run_id_property_still_works(self) -> None:
        """run_id property should still work."""
        from castro.state_provider import LiveExperimentProvider

        provider = LiveExperimentProvider(
            run_id="test-run-123",
            experiment_name="test",
            description="desc",
            model="model",
            max_iterations=10,
            num_samples=5,
        )

        assert provider.run_id == "test-run-123"

    def test_get_run_metadata_still_works(self) -> None:
        """get_run_metadata should still work (backward compat)."""
        from castro.state_provider import LiveExperimentProvider

        provider = LiveExperimentProvider(
            run_id="test-run",
            experiment_name="my_experiment",
            description="desc",
            model="model",
            max_iterations=10,
            num_samples=5,
        )

        metadata = provider.get_run_metadata()
        assert metadata["experiment_name"] == "my_experiment"

    def test_get_events_for_iteration_still_works(self) -> None:
        """get_events_for_iteration should still work."""
        from castro.state_provider import LiveExperimentProvider
        from castro.events import create_iteration_start_event

        provider = LiveExperimentProvider(
            run_id="test-run",
            experiment_name="test",
            description="desc",
            model="model",
            max_iterations=10,
            num_samples=5,
        )

        # Capture an event
        event = create_iteration_start_event("test-run", 0, 1000)
        provider.capture_event(event)

        # Old API should still work
        events = provider.get_events_for_iteration(0)
        assert len(events) == 1

    def test_capture_event_still_works(self) -> None:
        """capture_event should still work."""
        from castro.state_provider import LiveExperimentProvider
        from castro.events import ExperimentEvent
        from datetime import datetime

        provider = LiveExperimentProvider(
            run_id="test-run",
            experiment_name="test",
            description="desc",
            model="model",
            max_iterations=10,
            num_samples=5,
        )

        event = ExperimentEvent(
            event_type="test_event",
            run_id="test-run",
            iteration=0,
            timestamp=datetime.now(),
            details={"key": "value"},
        )

        provider.capture_event(event)
        events = provider.get_events_for_iteration(0)
        assert len(events) == 1


class TestDatabaseProviderMigration:
    """Tests for DatabaseExperimentProvider migration."""

    def test_database_provider_implements_core_protocol(
        self, tmp_path: Any
    ) -> None:
        """DatabaseExperimentProvider should implement core protocol."""
        import duckdb
        from castro.state_provider import DatabaseExperimentProvider
        from castro.persistence import ExperimentEventRepository
        from payment_simulator.experiments.runner import (
            ExperimentStateProviderProtocol,
        )

        # Setup database
        conn = duckdb.connect(str(tmp_path / "test.db"))
        repo = ExperimentEventRepository(conn)
        repo.initialize_schema()

        # Create provider (will have no data, but should still work)
        provider = DatabaseExperimentProvider(conn, "test-run")

        # Should implement protocol
        assert hasattr(provider, "get_experiment_info")
        assert hasattr(provider, "get_total_iterations")
        assert hasattr(provider, "get_iteration_events")
        assert hasattr(provider, "get_iteration_costs")

        conn.close()

    def test_database_provider_has_get_experiment_info(
        self, tmp_path: Any
    ) -> None:
        """DatabaseExperimentProvider should have get_experiment_info."""
        import duckdb
        from castro.state_provider import DatabaseExperimentProvider
        from castro.persistence import ExperimentEventRepository

        conn = duckdb.connect(str(tmp_path / "test.db"))
        repo = ExperimentEventRepository(conn)
        repo.initialize_schema()

        provider = DatabaseExperimentProvider(conn, "test-run")
        info = provider.get_experiment_info()

        # Should return dict (empty or with data)
        assert isinstance(info, dict)
        conn.close()
```

---

### Test File 2: `experiments/castro/tests/test_persistence_migration.py`

```python
"""TDD tests for Castro persistence migration to core.

Verifies Castro repository can use core ExperimentRepository
while maintaining backward compatibility.

Write these tests FIRST, then implement.
"""

from __future__ import annotations

import pytest
from pathlib import Path
from typing import Any
from datetime import datetime


class TestCastroRepositoryUsesCoreInternally:
    """Tests that Castro repository wraps core repository."""

    def test_castro_repo_creates_core_tables(self, tmp_path: Path) -> None:
        """Castro repository should create core-compatible tables."""
        import duckdb
        from castro.persistence import ExperimentEventRepository

        db_path = tmp_path / "test.db"
        conn = duckdb.connect(str(db_path))
        repo = ExperimentEventRepository(conn)
        repo.initialize_schema()

        # Check tables exist
        tables = conn.execute(
            "SELECT table_name FROM information_schema.tables WHERE table_schema='main'"
        ).fetchall()
        table_names = [t[0] for t in tables]

        # Should have experiment tables
        assert "experiment_runs" in table_names or "experiments" in table_names
        assert "experiment_events" in table_names

        conn.close()

    def test_castro_repo_can_use_core_repository(self, tmp_path: Path) -> None:
        """Castro repository should be able to wrap core repository."""
        from castro.persistence import ExperimentEventRepository
        from payment_simulator.experiments.persistence import ExperimentRepository

        # Both should be able to use same database
        db_path = tmp_path / "shared.db"

        # Create via core
        core_repo = ExperimentRepository(db_path)
        core_repo.close()

        # Castro should work with same database
        import duckdb
        conn = duckdb.connect(str(db_path))
        castro_repo = ExperimentEventRepository(conn)
        # Should not fail
        castro_repo.initialize_schema()
        conn.close()


class TestCastroRepositoryBackwardCompat:
    """Tests that Castro repository API still works."""

    @pytest.fixture
    def castro_repo(self, tmp_path: Path) -> Any:
        """Create Castro repository."""
        import duckdb
        from castro.persistence import ExperimentEventRepository

        conn = duckdb.connect(str(tmp_path / "test.db"))
        repo = ExperimentEventRepository(conn)
        repo.initialize_schema()
        yield repo
        conn.close()

    def test_save_run_record_still_works(self, castro_repo: Any) -> None:
        """save_run_record should still work."""
        from castro.persistence.models import ExperimentRunRecord

        record = ExperimentRunRecord(
            run_id="test-run",
            experiment_name="test",
            started_at=datetime.now(),
            status="running",
        )

        castro_repo.save_run_record(record)
        loaded = castro_repo.get_run_record("test-run")

        assert loaded is not None
        assert loaded.run_id == "test-run"

    def test_save_event_still_works(self, castro_repo: Any) -> None:
        """save_event should still work with ExperimentEvent."""
        from castro.events import ExperimentEvent

        event = ExperimentEvent(
            event_type="test_event",
            run_id="test-run",
            iteration=0,
            timestamp=datetime.now(),
            details={"key": "value"},
        )

        castro_repo.save_event(event)
        events = list(castro_repo.get_events_for_run("test-run"))

        assert len(events) == 1
        assert events[0].event_type == "test_event"

    def test_get_events_for_iteration_still_works(self, castro_repo: Any) -> None:
        """get_events_for_iteration should still work."""
        from castro.events import ExperimentEvent

        # Save events for different iterations
        for i in range(3):
            event = ExperimentEvent(
                event_type=f"event_{i}",
                run_id="test-run",
                iteration=i,
                timestamp=datetime.now(),
                details={},
            )
            castro_repo.save_event(event)

        # Get events for specific iteration
        events = list(castro_repo.get_events_for_iteration("test-run", 1))

        assert len(events) == 1
        assert events[0].event_type == "event_1"

    def test_list_runs_still_works(self, castro_repo: Any) -> None:
        """list_runs should still work."""
        from castro.persistence.models import ExperimentRunRecord

        # Save multiple runs
        for i in range(3):
            record = ExperimentRunRecord(
                run_id=f"run-{i}",
                experiment_name="test",
                started_at=datetime.now(),
                status="completed",
            )
            castro_repo.save_run_record(record)

        runs = castro_repo.list_runs()
        assert len(runs) == 3


class TestCastroEventConversion:
    """Tests for converting between Castro and core event formats."""

    def test_experiment_event_to_event_record(self) -> None:
        """ExperimentEvent should convert to EventRecord."""
        from castro.events import ExperimentEvent
        from payment_simulator.experiments.persistence import EventRecord

        castro_event = ExperimentEvent(
            event_type="bootstrap_evaluation",
            run_id="test-run",
            iteration=0,
            timestamp=datetime.now(),
            details={"mean_cost": 1000, "std_cost": 100},
        )

        # Should be able to convert
        core_record = EventRecord(
            run_id=castro_event.run_id,
            iteration=castro_event.iteration,
            event_type=castro_event.event_type,
            event_data=castro_event.details,
            timestamp=castro_event.timestamp.isoformat(),
        )

        assert core_record.event_type == "bootstrap_evaluation"
        assert core_record.event_data["mean_cost"] == 1000

    def test_event_record_to_experiment_event(self) -> None:
        """EventRecord should convert to ExperimentEvent."""
        from castro.events import ExperimentEvent
        from payment_simulator.experiments.persistence import EventRecord

        core_record = EventRecord(
            run_id="test-run",
            iteration=0,
            event_type="policy_change",
            event_data={"agent_id": "BANK_A", "accepted": True},
            timestamp="2025-12-11T10:00:00",
        )

        # Should be able to convert
        castro_event = ExperimentEvent.from_dict({
            "event_type": core_record.event_type,
            "run_id": core_record.run_id,
            "iteration": core_record.iteration,
            "timestamp": core_record.timestamp,
            "details": core_record.event_data,
        })

        assert castro_event.event_type == "policy_change"
        assert castro_event.details["agent_id"] == "BANK_A"
```

---

### Test File 3: `experiments/castro/tests/test_replay_identity_preserved.py`

```python
"""TDD tests ensuring replay identity is preserved after migration.

This is the CRITICAL test - migration must not break replay identity.

Write these tests FIRST, then implement.
"""

from __future__ import annotations

import pytest
from pathlib import Path
from typing import Any


class TestReplayIdentityPreserved:
    """Tests that replay produces identical output after migration."""

    @pytest.fixture
    def sample_experiment_db(self, tmp_path: Path) -> Path:
        """Create a sample experiment database with known data."""
        import duckdb
        from castro.persistence import ExperimentEventRepository
        from castro.persistence.models import ExperimentRunRecord
        from castro.events import (
            create_experiment_start_event,
            create_iteration_start_event,
            create_bootstrap_evaluation_event,
            create_experiment_end_event,
        )
        from datetime import datetime

        db_path = tmp_path / "experiment.db"
        conn = duckdb.connect(str(db_path))
        repo = ExperimentEventRepository(conn)
        repo.initialize_schema()

        # Create run record
        run_record = ExperimentRunRecord(
            run_id="replay-test",
            experiment_name="exp1",
            started_at=datetime(2025, 12, 11, 10, 0, 0),
            status="completed",
            completed_at=datetime(2025, 12, 11, 10, 30, 0),
            final_cost=1000,
            best_cost=900,
            num_iterations=3,
            converged=True,
            convergence_reason="stability",
            model="test-model",
            master_seed=42,
        )
        repo.save_run_record(run_record)

        # Create events
        events = [
            create_experiment_start_event(
                "replay-test", "exp1", "Test", "model", 10, 5
            ),
            create_iteration_start_event("replay-test", 0, 1000),
            create_bootstrap_evaluation_event(
                "replay-test", 0,
                [{"seed": 1, "cost": 1000}],
                1000, 0
            ),
            create_iteration_start_event("replay-test", 1, 950),
            create_bootstrap_evaluation_event(
                "replay-test", 1,
                [{"seed": 1, "cost": 950}],
                950, 0
            ),
            create_experiment_end_event(
                "replay-test", 2, 900, 900, True, "stability", 30.0
            ),
        ]
        for event in events:
            repo.save_event(event)

        conn.close()
        return db_path

    def test_live_and_database_provider_same_events(
        self, sample_experiment_db: Path
    ) -> None:
        """Live and database provider should return same events."""
        import duckdb
        from castro.state_provider import (
            LiveExperimentProvider,
            DatabaseExperimentProvider,
        )
        from castro.events import (
            create_experiment_start_event,
            create_iteration_start_event,
        )

        # Create live provider and capture same events
        live_provider = LiveExperimentProvider(
            run_id="replay-test",
            experiment_name="exp1",
            description="Test",
            model="model",
            max_iterations=10,
            num_samples=5,
        )
        live_provider.capture_event(
            create_experiment_start_event(
                "replay-test", "exp1", "Test", "model", 10, 5
            )
        )
        live_provider.capture_event(
            create_iteration_start_event("replay-test", 0, 1000)
        )

        # Create database provider
        conn = duckdb.connect(str(sample_experiment_db))
        db_provider = DatabaseExperimentProvider(conn, "replay-test")

        # Compare iteration 0 events
        live_events = live_provider.get_iteration_events(0)
        db_events = db_provider.get_iteration_events(0)

        # Event types should match
        live_types = [e["event_type"] for e in live_events]
        db_types = [e["event_type"] for e in db_events]

        assert "iteration_start" in live_types
        assert "iteration_start" in db_types

        conn.close()

    def test_core_protocol_methods_work_on_both_providers(
        self, sample_experiment_db: Path
    ) -> None:
        """Core protocol methods should work on both providers."""
        import duckdb
        from castro.state_provider import (
            LiveExperimentProvider,
            DatabaseExperimentProvider,
        )

        # Live provider
        live = LiveExperimentProvider(
            run_id="test",
            experiment_name="exp1",
            description="Test",
            model="model",
            max_iterations=10,
            num_samples=5,
        )

        # Database provider
        conn = duckdb.connect(str(sample_experiment_db))
        db = DatabaseExperimentProvider(conn, "replay-test")

        # Both should have these methods
        assert callable(getattr(live, "get_experiment_info", None))
        assert callable(getattr(db, "get_experiment_info", None))

        assert callable(getattr(live, "get_total_iterations", None))
        assert callable(getattr(db, "get_total_iterations", None))

        assert callable(getattr(live, "get_iteration_events", None))
        assert callable(getattr(db, "get_iteration_events", None))

        conn.close()

    def test_costs_remain_integer_cents(self, sample_experiment_db: Path) -> None:
        """Costs must remain integer cents after migration (INV-1)."""
        import duckdb
        from castro.state_provider import DatabaseExperimentProvider

        conn = duckdb.connect(str(sample_experiment_db))
        provider = DatabaseExperimentProvider(conn, "replay-test")

        # If provider has costs, they must be integers
        costs = provider.get_iteration_costs(0)
        for agent_id, cost in costs.items():
            assert isinstance(cost, int), f"Cost for {agent_id} must be int"

        conn.close()
```

---

## Implementation Plan

### Task 12.1: Adapt Castro StateProvider (Medium Risk)

**Steps:**
1. Write TDD tests (above)
2. Run tests -> FAIL
3. Add core protocol methods to `LiveExperimentProvider`:
   - `get_experiment_info()` - wraps `get_run_metadata()`
   - `get_total_iterations()` - new method
   - `get_iteration_events()` - wraps `get_events_for_iteration()`, converts return type
   - `get_iteration_policies()` - new method (track internally)
   - `get_iteration_costs()` - new method (track internally)
   - `get_iteration_accepted_changes()` - new method (track internally)
4. Add core protocol methods to `DatabaseExperimentProvider`:
   - Same methods, query from database
5. Keep existing methods for backward compatibility
6. Run tests -> PASS
7. Optionally merge `EventEmitter` into `LiveExperimentProvider`

**Files to modify:**
- `experiments/castro/castro/state_provider.py`

---

### Task 12.2: Migrate Castro Persistence (Medium Risk)

**Steps:**
1. Write TDD tests (above)
2. Run tests -> FAIL
3. Option A: Castro repo wraps core repo internally
   - `ExperimentEventRepository.__init__` creates internal `ExperimentRepository`
   - Existing methods delegate to core
4. Option B: Castro repo uses core tables directly
   - Modify Castro schema to match core
   - Add compatibility layer for old API
5. Add conversion methods: `ExperimentEvent <-> EventRecord`
6. Run tests -> PASS
7. Update Castro runner to use migrated repository

**Files to modify:**
- `experiments/castro/castro/persistence/repository.py`
- `experiments/castro/castro/persistence/models.py` (add conversion methods)

---

### Task 12.3: Event System Alignment (Low Risk)

**Steps:**
1. Write TDD tests (above)
2. Run tests -> FAIL
3. Add `to_event_record()` method to `ExperimentEvent`
4. Add `from_event_record()` class method to `ExperimentEvent`
5. Keep all event creation helpers (domain-specific)
6. Run tests -> PASS

**Files to modify:**
- `experiments/castro/castro/events.py`

---

## Verification Checklist

### Before Starting
- [ ] All Phase 11 tests pass
- [ ] All Castro tests pass
- [ ] Record baseline test counts

### TDD Verification
- [ ] Task 12.1: `test_state_provider_migration.py` all pass
- [ ] Task 12.2: `test_persistence_migration.py` all pass
- [ ] Task 12.3: `test_replay_identity_preserved.py` all pass

### Integration Verification
- [ ] All API tests pass
- [ ] All Castro tests pass
- [ ] Type checking passes: `mypy castro/`
- [ ] Castro CLI still works: `castro run exp1 --max-iter 1 --dry-run`
- [ ] Replay identity preserved: `castro replay <db>` matches original

### Backward Compatibility
- [ ] Existing Castro scripts work without changes
- [ ] Existing databases can be read
- [ ] `ExperimentStateProvider` protocol still works
- [ ] All event creation helpers still work

---

## Expected Outcomes

### Lines of Code

| Category | Before Phase 12 | After Phase 12 | Delta |
|----------|-----------------|----------------|-------|
| Castro state_provider.py | ~354 | ~200 | -154 |
| Castro persistence/ | ~400 | ~200 | -200 |
| Castro events.py | ~418 | ~440 | +22 |
| **Net Castro Reduction** | | | **~332** |

### New Tests Added

| Test File | Test Count |
|-----------|------------|
| test_state_provider_migration.py | ~15 |
| test_persistence_migration.py | ~12 |
| test_replay_identity_preserved.py | ~5 |
| **Total** | **~32** |

---

## Risk Mitigation

### Replay Identity
- **Risk:** Migration breaks replay - different output from same database
- **Mitigation:**
  1. Golden test: Capture known-good output before migration
  2. Compare output after migration
  3. Test at event level, not just final output
- **Fallback:** Revert migration, keep Castro separate

### Database Compatibility
- **Risk:** New schema incompatible with old databases
- **Mitigation:**
  1. Castro keeps its own tables
  2. Core tables are additional (not replacement)
  3. Migration script with dry-run
- **Fallback:** Castro keeps own persistence entirely

### API Breaking Changes
- **Risk:** Existing Castro users see errors
- **Mitigation:**
  1. All existing methods remain (deprecation warnings optional)
  2. New methods are additions, not replacements
  3. Test backward compatibility explicitly

---

## Related Documents

- [Phase 11: StateProvider and Persistence](./phase_11.md) - Core infrastructure
- [Conceptual Plan](../refactor-conceptual-plan.md) - Architecture overview
- [Development Plan](../development-plan.md) - Timeline
- [Castro StateProvider](../../../../experiments/castro/castro/state_provider.py) - Current implementation
- [Castro Persistence](../../../../experiments/castro/castro/persistence/) - Current implementation

---

*Phase 12 Plan v1.0 - 2025-12-11*
