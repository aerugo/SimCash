# Phase 11: Infrastructure Generalization - StateProvider and Persistence

**Status:** Planned
**Created:** 2025-12-11
**Dependencies:** Phase 10 (Core Module Consolidation)
**Risk:** High (protocol design, database schema changes)
**Breaking Changes:** Potentially (database migration required for 11.2)

---

## Purpose

Phase 11 addresses the high-risk tasks deferred from Phase 10. These tasks involve generalizing Castro's infrastructure patterns into core SimCash modules:

1. **StateProvider Protocol** (Task 11.1): Enable experiment replay identity by abstracting state access
2. **Unified Persistence** (Task 11.2): Consolidate experiment persistence into a single repository pattern

**Target outcome**: A reusable experiment infrastructure that any future experiment can leverage, maintaining replay identity and audit capabilities.

---

## Background: Why These Were Deferred

### StateProvider (from Phase 10.4)

The StateProvider pattern enables **replay identity** - the ability to replay an experiment and get identical output to the original run. This is critical for:
- Debugging experiment behavior
- Auditing LLM decisions
- Reproducing results for research papers

**Deferral reason**: High complexity - requires careful protocol design that works for both live experiments and database replay.

### Unified Persistence (from Phase 10.5)

Castro has its own persistence layer (`castro/persistence/`) separate from core SimCash persistence. Unification would:
- Reduce code duplication
- Enable cross-experiment analysis
- Simplify experiment development

**Deferral reason**: Database schema changes required, migration risk, needs careful backward compatibility planning.

---

## Current State Analysis

### StateProvider in Castro

**Location:** `experiments/castro/castro/state_provider.py` (~250 lines)

```python
# Current Castro StateProvider pattern
@runtime_checkable
class ExperimentStateProvider(Protocol):
    """Protocol for accessing experiment state."""

    def get_experiment_info(self) -> dict[str, Any]: ...
    def get_iteration_count(self) -> int: ...
    def get_iteration_events(self, iteration: int) -> list[dict]: ...
    def get_policies(self, iteration: int) -> dict[str, Any]: ...
    def get_costs(self, iteration: int) -> dict[str, int]: ...
```

**Implementations:**
- `LiveExperimentProvider`: Wraps running experiment
- `DatabaseExperimentProvider`: Wraps database queries for replay

### Persistence in Castro

**Location:** `experiments/castro/castro/persistence/` (~300 lines)

**Tables:**
- `experiments`: Experiment metadata
- `iterations`: Per-iteration results
- `policies`: Policy snapshots
- `events`: Detailed event log
- `llm_interactions`: LLM audit trail

---

## Phase 11 Tasks

### Task 11.1: Generalize StateProvider Protocol (High Risk)

**Impact:** ~250 lines abstracted to core
**Risk:** High - protocol design must satisfy multiple use cases
**TDD Test File:** `api/tests/experiments/runner/test_state_provider_core.py`

**Goals:**
1. Define `ExperimentStateProviderProtocol` in core
2. Create `DatabaseStateProvider` implementation
3. Create `LiveStateProvider` implementation
4. Enable Castro to use core providers (or implement the protocol)

**Protocol Design:**

```python
# api/payment_simulator/experiments/runner/state_provider.py
from typing import Protocol, runtime_checkable, Any

@runtime_checkable
class ExperimentStateProviderProtocol(Protocol):
    """Protocol for accessing experiment state.

    Enables replay identity by providing a consistent interface
    for both live experiments and database replay.
    """

    def get_experiment_info(self) -> dict[str, Any]:
        """Get experiment metadata (name, config, start time)."""
        ...

    def get_total_iterations(self) -> int:
        """Get total number of completed iterations."""
        ...

    def get_iteration_events(self, iteration: int) -> list[dict[str, Any]]:
        """Get all events for a specific iteration."""
        ...

    def get_iteration_policies(self, iteration: int) -> dict[str, Any]:
        """Get policy state at end of iteration."""
        ...

    def get_iteration_costs(self, iteration: int) -> dict[str, int]:
        """Get per-agent costs for iteration (integer cents - INV-1)."""
        ...

    def get_iteration_accepted_changes(self, iteration: int) -> dict[str, bool]:
        """Get which agents had policy changes accepted."""
        ...
```

---

### Task 11.2: Unify Persistence Layer (High Risk)

**Impact:** ~300 lines unified
**Risk:** High - database schema migration
**TDD Test File:** `api/tests/experiments/persistence/test_experiment_repository.py`

**Goals:**
1. Create unified `ExperimentRepository` in core
2. Define schema that supports any experiment type
3. Migrate Castro to use core repository
4. Maintain backward compatibility with existing databases

**Repository Design:**

```python
# api/payment_simulator/experiments/persistence/repository.py
from dataclasses import dataclass
from pathlib import Path
from typing import Any
import duckdb

@dataclass(frozen=True)
class ExperimentRecord:
    """Stored experiment record."""
    run_id: str
    experiment_name: str
    experiment_type: str  # "castro", "custom", etc.
    config: dict[str, Any]
    created_at: str
    completed_at: str | None
    num_iterations: int
    converged: bool
    convergence_reason: str | None

@dataclass(frozen=True)
class IterationRecord:
    """Stored iteration record."""
    run_id: str
    iteration: int
    costs_per_agent: dict[str, int]  # Integer cents (INV-1)
    accepted_changes: dict[str, bool]
    policies: dict[str, Any]
    timestamp: str

class ExperimentRepository:
    """Unified repository for experiment persistence.

    Supports any experiment type with flexible schema.
    All costs are integer cents (INV-1 compliance).
    """

    def __init__(self, db_path: Path) -> None:
        self._conn = duckdb.connect(str(db_path))
        self._ensure_schema()

    def save_experiment(self, record: ExperimentRecord) -> None:
        """Save experiment metadata."""
        ...

    def save_iteration(self, record: IterationRecord) -> None:
        """Save iteration results."""
        ...

    def save_event(
        self,
        run_id: str,
        iteration: int,
        event_type: str,
        event_data: dict[str, Any],
    ) -> None:
        """Save an event with flexible schema."""
        ...

    def load_experiment(self, run_id: str) -> ExperimentRecord | None:
        """Load experiment by run ID."""
        ...

    def list_experiments(
        self,
        experiment_type: str | None = None,
    ) -> list[ExperimentRecord]:
        """List experiments, optionally filtered by type."""
        ...

    def get_iterations(self, run_id: str) -> list[IterationRecord]:
        """Get all iterations for an experiment."""
        ...

    def as_state_provider(self, run_id: str) -> ExperimentStateProviderProtocol:
        """Create a StateProvider for replay."""
        return DatabaseStateProvider(self, run_id)
```

**Database Schema:**

```sql
-- Core experiments table (flexible for any experiment type)
CREATE TABLE experiments (
    run_id VARCHAR PRIMARY KEY,
    experiment_name VARCHAR NOT NULL,
    experiment_type VARCHAR NOT NULL,  -- 'castro', 'custom', etc.
    config JSON NOT NULL,
    created_at TIMESTAMP NOT NULL,
    completed_at TIMESTAMP,
    num_iterations INTEGER,
    converged BOOLEAN,
    convergence_reason VARCHAR
);

-- Iterations table
CREATE TABLE experiment_iterations (
    run_id VARCHAR NOT NULL,
    iteration INTEGER NOT NULL,
    costs_per_agent JSON NOT NULL,      -- {agent_id: cost_cents}
    accepted_changes JSON NOT NULL,      -- {agent_id: bool}
    policies JSON NOT NULL,
    timestamp TIMESTAMP NOT NULL,
    PRIMARY KEY (run_id, iteration),
    FOREIGN KEY (run_id) REFERENCES experiments(run_id)
);

-- Events table (flexible schema)
CREATE TABLE experiment_events (
    id INTEGER PRIMARY KEY,
    run_id VARCHAR NOT NULL,
    iteration INTEGER NOT NULL,
    event_type VARCHAR NOT NULL,
    event_data JSON NOT NULL,
    timestamp TIMESTAMP NOT NULL,
    FOREIGN KEY (run_id) REFERENCES experiments(run_id)
);

-- LLM interactions (audit trail)
CREATE TABLE llm_interactions (
    id INTEGER PRIMARY KEY,
    run_id VARCHAR NOT NULL,
    iteration INTEGER NOT NULL,
    agent_id VARCHAR NOT NULL,
    system_prompt TEXT,
    user_prompt TEXT NOT NULL,
    response TEXT NOT NULL,
    parsed_policy JSON,
    parsing_error TEXT,
    prompt_tokens INTEGER,
    completion_tokens INTEGER,
    latency_seconds REAL,
    timestamp TIMESTAMP NOT NULL,
    FOREIGN KEY (run_id) REFERENCES experiments(run_id)
);
```

---

## TDD Test Specifications

### Test File 1: `api/tests/experiments/runner/test_state_provider_core.py`

```python
"""TDD tests for core StateProvider protocol.

Tests for generalizing StateProvider pattern for experiment replay.

Write these tests FIRST, then implement.
"""

from __future__ import annotations

import pytest
from typing import Any


class TestExperimentStateProviderProtocol:
    """Tests for ExperimentStateProviderProtocol definition."""

    def test_protocol_importable(self) -> None:
        """Protocol should be importable from experiments.runner."""
        from payment_simulator.experiments.runner import (
            ExperimentStateProviderProtocol,
        )
        assert ExperimentStateProviderProtocol is not None

    def test_protocol_is_runtime_checkable(self) -> None:
        """Protocol should be @runtime_checkable for isinstance checks."""
        from payment_simulator.experiments.runner import (
            ExperimentStateProviderProtocol,
        )

        class MockProvider:
            def get_experiment_info(self) -> dict[str, Any]:
                return {}

            def get_total_iterations(self) -> int:
                return 0

            def get_iteration_events(self, iteration: int) -> list[dict[str, Any]]:
                return []

            def get_iteration_policies(self, iteration: int) -> dict[str, Any]:
                return {}

            def get_iteration_costs(self, iteration: int) -> dict[str, int]:
                return {}

            def get_iteration_accepted_changes(self, iteration: int) -> dict[str, bool]:
                return {}

        provider = MockProvider()
        assert isinstance(provider, ExperimentStateProviderProtocol)

    def test_protocol_requires_get_experiment_info(self) -> None:
        """Protocol should require get_experiment_info method."""
        from payment_simulator.experiments.runner import (
            ExperimentStateProviderProtocol,
        )
        assert hasattr(ExperimentStateProviderProtocol, "get_experiment_info")

    def test_protocol_requires_get_total_iterations(self) -> None:
        """Protocol should require get_total_iterations method."""
        from payment_simulator.experiments.runner import (
            ExperimentStateProviderProtocol,
        )
        assert hasattr(ExperimentStateProviderProtocol, "get_total_iterations")

    def test_protocol_requires_get_iteration_events(self) -> None:
        """Protocol should require get_iteration_events method."""
        from payment_simulator.experiments.runner import (
            ExperimentStateProviderProtocol,
        )
        assert hasattr(ExperimentStateProviderProtocol, "get_iteration_events")

    def test_protocol_requires_get_iteration_costs(self) -> None:
        """Protocol should require get_iteration_costs method."""
        from payment_simulator.experiments.runner import (
            ExperimentStateProviderProtocol,
        )
        assert hasattr(ExperimentStateProviderProtocol, "get_iteration_costs")


class TestDatabaseStateProvider:
    """Tests for DatabaseStateProvider implementation."""

    def test_importable_from_runner(self) -> None:
        """DatabaseStateProvider should be importable."""
        from payment_simulator.experiments.runner import DatabaseStateProvider
        assert DatabaseStateProvider is not None

    def test_implements_protocol(self) -> None:
        """DatabaseStateProvider should implement protocol."""
        from payment_simulator.experiments.runner import (
            DatabaseStateProvider,
            ExperimentStateProviderProtocol,
        )
        # Check it has required methods
        assert hasattr(DatabaseStateProvider, "get_experiment_info")
        assert hasattr(DatabaseStateProvider, "get_total_iterations")
        assert hasattr(DatabaseStateProvider, "get_iteration_events")
        assert hasattr(DatabaseStateProvider, "get_iteration_costs")

    def test_requires_run_id(self) -> None:
        """DatabaseStateProvider should require run_id."""
        from payment_simulator.experiments.runner import DatabaseStateProvider
        import inspect

        sig = inspect.signature(DatabaseStateProvider.__init__)
        params = list(sig.parameters.keys())
        assert "run_id" in params

    def test_costs_are_integer_cents(self, tmp_path: Any) -> None:
        """All costs from DatabaseStateProvider must be integer cents (INV-1)."""
        from payment_simulator.experiments.runner import DatabaseStateProvider
        from payment_simulator.experiments.persistence import ExperimentRepository

        # Create test database with sample data
        db_path = tmp_path / "test.db"
        repo = ExperimentRepository(db_path)

        # Insert test experiment with known integer costs
        # (implementation details depend on repository API)

        # Verify costs returned are integers
        # provider = DatabaseStateProvider(repo, "test_run_id")
        # costs = provider.get_iteration_costs(0)
        # for agent_id, cost in costs.items():
        #     assert isinstance(cost, int), f"Cost for {agent_id} must be int"
        pytest.skip("Requires repository implementation")


class TestLiveStateProvider:
    """Tests for LiveStateProvider implementation."""

    def test_importable_from_runner(self) -> None:
        """LiveStateProvider should be importable."""
        from payment_simulator.experiments.runner import LiveStateProvider
        assert LiveStateProvider is not None

    def test_implements_protocol(self) -> None:
        """LiveStateProvider should implement protocol."""
        from payment_simulator.experiments.runner import (
            LiveStateProvider,
            ExperimentStateProviderProtocol,
        )
        assert hasattr(LiveStateProvider, "get_experiment_info")
        assert hasattr(LiveStateProvider, "get_total_iterations")


def _castro_available() -> bool:
    """Check if castro module is available."""
    try:
        import castro  # noqa: F401
        return True
    except ImportError:
        return False


class TestCastroBackwardCompatibility:
    """Tests ensuring Castro can use core StateProvider."""

    @pytest.mark.skipif(
        not _castro_available(),
        reason="Castro module not available in this environment",
    )
    def test_castro_can_import_core_protocol(self) -> None:
        """Castro should be able to import core protocol."""
        from payment_simulator.experiments.runner import (
            ExperimentStateProviderProtocol,
        )
        assert ExperimentStateProviderProtocol is not None

    @pytest.mark.skipif(
        not _castro_available(),
        reason="Castro module not available in this environment",
    )
    def test_castro_provider_compatible_with_core(self) -> None:
        """Castro's provider should be compatible with core protocol."""
        from castro.state_provider import CastroStateProvider
        from payment_simulator.experiments.runner import (
            ExperimentStateProviderProtocol,
        )

        # Castro provider should implement core protocol methods
        assert hasattr(CastroStateProvider, "get_experiment_info")
        assert hasattr(CastroStateProvider, "get_total_iterations")
```

---

### Test File 2: `api/tests/experiments/persistence/test_experiment_repository.py`

```python
"""TDD tests for unified ExperimentRepository.

Tests for the core experiment persistence layer.

Write these tests FIRST, then implement.
"""

from __future__ import annotations

import pytest
from pathlib import Path
from typing import Any


class TestExperimentRepositoryImport:
    """Tests for importing ExperimentRepository."""

    def test_importable_from_persistence(self) -> None:
        """ExperimentRepository should be importable from experiments.persistence."""
        from payment_simulator.experiments.persistence import ExperimentRepository
        assert ExperimentRepository is not None

    def test_record_classes_importable(self) -> None:
        """Record dataclasses should be importable."""
        from payment_simulator.experiments.persistence import (
            ExperimentRecord,
            IterationRecord,
        )
        assert ExperimentRecord is not None
        assert IterationRecord is not None


class TestExperimentRepositoryCreation:
    """Tests for creating ExperimentRepository."""

    def test_creates_database_file(self, tmp_path: Path) -> None:
        """Repository should create database file."""
        from payment_simulator.experiments.persistence import ExperimentRepository

        db_path = tmp_path / "experiments.db"
        repo = ExperimentRepository(db_path)

        assert db_path.exists()
        repo.close()

    def test_creates_required_tables(self, tmp_path: Path) -> None:
        """Repository should create required tables."""
        from payment_simulator.experiments.persistence import ExperimentRepository
        import duckdb

        db_path = tmp_path / "experiments.db"
        repo = ExperimentRepository(db_path)
        repo.close()

        # Verify tables exist
        conn = duckdb.connect(str(db_path))
        tables = conn.execute(
            "SELECT table_name FROM information_schema.tables WHERE table_schema='main'"
        ).fetchall()
        table_names = [t[0] for t in tables]
        conn.close()

        assert "experiments" in table_names
        assert "experiment_iterations" in table_names
        assert "experiment_events" in table_names


class TestExperimentRecordOperations:
    """Tests for experiment record CRUD operations."""

    @pytest.fixture
    def repo(self, tmp_path: Path) -> Any:
        """Create repository for testing."""
        from payment_simulator.experiments.persistence import ExperimentRepository

        db_path = tmp_path / "test.db"
        repository = ExperimentRepository(db_path)
        yield repository
        repository.close()

    def test_save_and_load_experiment(self, repo: Any) -> None:
        """Should save and load experiment record."""
        from payment_simulator.experiments.persistence import ExperimentRecord

        record = ExperimentRecord(
            run_id="test-run-001",
            experiment_name="test_experiment",
            experiment_type="castro",
            config={"num_samples": 10, "ticks": 12},
            created_at="2025-12-11T10:00:00",
            completed_at=None,
            num_iterations=0,
            converged=False,
            convergence_reason=None,
        )

        repo.save_experiment(record)
        loaded = repo.load_experiment("test-run-001")

        assert loaded is not None
        assert loaded.run_id == "test-run-001"
        assert loaded.experiment_name == "test_experiment"
        assert loaded.experiment_type == "castro"
        assert loaded.config == {"num_samples": 10, "ticks": 12}

    def test_list_experiments_by_type(self, repo: Any) -> None:
        """Should list experiments filtered by type."""
        from payment_simulator.experiments.persistence import ExperimentRecord

        # Save experiments of different types
        for i, exp_type in enumerate(["castro", "castro", "custom"]):
            record = ExperimentRecord(
                run_id=f"run-{i}",
                experiment_name=f"exp-{i}",
                experiment_type=exp_type,
                config={},
                created_at="2025-12-11T10:00:00",
                completed_at=None,
                num_iterations=0,
                converged=False,
                convergence_reason=None,
            )
            repo.save_experiment(record)

        castro_experiments = repo.list_experiments(experiment_type="castro")
        assert len(castro_experiments) == 2

        all_experiments = repo.list_experiments()
        assert len(all_experiments) == 3


class TestIterationRecordOperations:
    """Tests for iteration record operations."""

    @pytest.fixture
    def repo_with_experiment(self, tmp_path: Path) -> Any:
        """Create repository with a test experiment."""
        from payment_simulator.experiments.persistence import (
            ExperimentRepository,
            ExperimentRecord,
        )

        db_path = tmp_path / "test.db"
        repository = ExperimentRepository(db_path)

        record = ExperimentRecord(
            run_id="test-run",
            experiment_name="test",
            experiment_type="castro",
            config={},
            created_at="2025-12-11T10:00:00",
            completed_at=None,
            num_iterations=0,
            converged=False,
            convergence_reason=None,
        )
        repository.save_experiment(record)

        yield repository
        repository.close()

    def test_save_and_get_iterations(self, repo_with_experiment: Any) -> None:
        """Should save and retrieve iterations."""
        from payment_simulator.experiments.persistence import IterationRecord

        record = IterationRecord(
            run_id="test-run",
            iteration=0,
            costs_per_agent={"BANK_A": 1000, "BANK_B": 1500},
            accepted_changes={"BANK_A": True, "BANK_B": False},
            policies={"BANK_A": {"type": "release"}, "BANK_B": {"type": "hold"}},
            timestamp="2025-12-11T10:01:00",
        )

        repo_with_experiment.save_iteration(record)
        iterations = repo_with_experiment.get_iterations("test-run")

        assert len(iterations) == 1
        assert iterations[0].iteration == 0
        assert iterations[0].costs_per_agent == {"BANK_A": 1000, "BANK_B": 1500}

    def test_costs_are_integer_cents(self, repo_with_experiment: Any) -> None:
        """All costs must be integer cents (INV-1 compliance)."""
        from payment_simulator.experiments.persistence import IterationRecord

        record = IterationRecord(
            run_id="test-run",
            iteration=0,
            costs_per_agent={"BANK_A": 100050, "BANK_B": 200075},  # Integer cents
            accepted_changes={},
            policies={},
            timestamp="2025-12-11T10:01:00",
        )

        repo_with_experiment.save_iteration(record)
        iterations = repo_with_experiment.get_iterations("test-run")

        for agent_id, cost in iterations[0].costs_per_agent.items():
            assert isinstance(cost, int), f"Cost for {agent_id} must be integer cents"


class TestStateProviderIntegration:
    """Tests for creating StateProvider from repository."""

    @pytest.fixture
    def repo_with_data(self, tmp_path: Path) -> Any:
        """Create repository with test data."""
        from payment_simulator.experiments.persistence import (
            ExperimentRepository,
            ExperimentRecord,
            IterationRecord,
        )

        db_path = tmp_path / "test.db"
        repository = ExperimentRepository(db_path)

        # Add experiment
        exp_record = ExperimentRecord(
            run_id="test-run",
            experiment_name="test",
            experiment_type="castro",
            config={"master_seed": 42},
            created_at="2025-12-11T10:00:00",
            completed_at="2025-12-11T10:30:00",
            num_iterations=3,
            converged=True,
            convergence_reason="stability",
        )
        repository.save_experiment(exp_record)

        # Add iterations
        for i in range(3):
            iter_record = IterationRecord(
                run_id="test-run",
                iteration=i,
                costs_per_agent={"BANK_A": 1000 - i * 100, "BANK_B": 1500 - i * 50},
                accepted_changes={"BANK_A": i > 0, "BANK_B": False},
                policies={},
                timestamp=f"2025-12-11T10:{i:02d}:00",
            )
            repository.save_iteration(iter_record)

        yield repository
        repository.close()

    def test_as_state_provider_returns_protocol_impl(self, repo_with_data: Any) -> None:
        """as_state_provider should return ExperimentStateProviderProtocol."""
        from payment_simulator.experiments.runner import (
            ExperimentStateProviderProtocol,
        )

        provider = repo_with_data.as_state_provider("test-run")
        assert isinstance(provider, ExperimentStateProviderProtocol)

    def test_state_provider_get_total_iterations(self, repo_with_data: Any) -> None:
        """StateProvider should return correct iteration count."""
        provider = repo_with_data.as_state_provider("test-run")
        assert provider.get_total_iterations() == 3

    def test_state_provider_get_experiment_info(self, repo_with_data: Any) -> None:
        """StateProvider should return experiment info."""
        provider = repo_with_data.as_state_provider("test-run")
        info = provider.get_experiment_info()

        assert info["run_id"] == "test-run"
        assert info["experiment_name"] == "test"
        assert info["converged"] is True

    def test_state_provider_get_iteration_costs(self, repo_with_data: Any) -> None:
        """StateProvider should return iteration costs."""
        provider = repo_with_data.as_state_provider("test-run")
        costs = provider.get_iteration_costs(0)

        assert costs["BANK_A"] == 1000
        assert costs["BANK_B"] == 1500
        assert isinstance(costs["BANK_A"], int)  # INV-1


def _castro_available() -> bool:
    """Check if castro module is available."""
    try:
        import castro  # noqa: F401
        return True
    except ImportError:
        return False


class TestCastroMigration:
    """Tests for Castro migration to unified repository."""

    @pytest.mark.skipif(
        not _castro_available(),
        reason="Castro module not available in this environment",
    )
    def test_castro_can_use_core_repository(self) -> None:
        """Castro should be able to use ExperimentRepository."""
        from payment_simulator.experiments.persistence import ExperimentRepository
        assert ExperimentRepository is not None

    @pytest.mark.skipif(
        not _castro_available(),
        reason="Castro module not available in this environment",
    )
    def test_castro_persistence_backward_compatible(self, tmp_path: Path) -> None:
        """Castro's existing persistence should remain functional."""
        # This test ensures we don't break Castro during migration
        from castro.persistence import CastroRepository

        db_path = tmp_path / "castro.db"
        repo = CastroRepository(db_path)
        # Basic functionality check
        assert repo is not None
```

---

## Implementation Plan

### Task 11.1: StateProvider Protocol (High Risk)

**TDD Test File:** `api/tests/experiments/runner/test_state_provider_core.py`

**Steps:**
1. Write TDD tests for protocol definition (above)
2. Write TDD tests for DatabaseStateProvider
3. Write TDD tests for LiveStateProvider
4. Run tests -> FAIL
5. Create `api/payment_simulator/experiments/runner/state_provider.py`:
   - Define `ExperimentStateProviderProtocol`
   - Implement `DatabaseStateProvider`
   - Implement `LiveStateProvider`
6. Update `api/payment_simulator/experiments/runner/__init__.py` to export
7. Run tests -> PASS
8. Update Castro to use or implement core protocol

**Files to create:**
- `api/payment_simulator/experiments/runner/state_provider.py`

**Files to modify:**
- `api/payment_simulator/experiments/runner/__init__.py`: Add exports
- `experiments/castro/castro/state_provider.py`: Adapt to core protocol

---

### Task 11.2: Unified Persistence (High Risk)

**TDD Test File:** `api/tests/experiments/persistence/test_experiment_repository.py`

**Steps:**
1. Write TDD tests for ExperimentRepository (above)
2. Write TDD tests for record classes
3. Write TDD tests for StateProvider integration
4. Run tests -> FAIL
5. Create `api/payment_simulator/experiments/persistence/repository.py`:
   - Define `ExperimentRecord`, `IterationRecord`
   - Implement `ExperimentRepository`
   - Implement `as_state_provider()` method
6. Update `api/payment_simulator/experiments/persistence/__init__.py` to export
7. Run tests -> PASS
8. Create database migration script for Castro
9. Update Castro to use core repository (optional - can be phased)

**Files to create:**
- `api/payment_simulator/experiments/persistence/repository.py`
- `api/payment_simulator/experiments/persistence/schema.py` (optional)
- `scripts/migrate_castro_db.py` (migration utility)

**Files to modify:**
- `api/payment_simulator/experiments/persistence/__init__.py`: Add exports

---

## Verification Checklist

### Before Starting (Capture Baseline)
- [ ] Record total API test count
- [ ] Record total Castro test count
- [ ] All tests pass

### TDD Verification (Per Task)
- [ ] Task 11.1: `test_state_provider_core.py` all pass
- [ ] Task 11.2: `test_experiment_repository.py` all pass

### Integration Verification
- [ ] All API tests pass: `cd api && .venv/bin/python -m pytest`
- [ ] All Castro tests pass: `cd experiments/castro && uv run pytest tests/`
- [ ] Type checking passes: `mypy payment_simulator/`
- [ ] Castro CLI still works: `uv run castro run exp1 --max-iter 1 --dry-run`
- [ ] Replay identity works: Same input produces same output

### Migration Verification (Task 11.2)
- [ ] Existing Castro databases can be read
- [ ] New experiments persist correctly
- [ ] Replay from database produces identical output

---

## Risk Mitigation

### StateProvider (Task 11.1)
- **Risk:** Protocol doesn't satisfy all use cases
- **Mitigation:** Start with minimal protocol, extend as needed
- **Fallback:** Castro keeps its own provider, imports core for type hints only

### Persistence (Task 11.2)
- **Risk:** Database migration breaks existing data
- **Mitigation:**
  1. New tables alongside old (don't modify existing schema)
  2. Migration script with dry-run mode
  3. Backup before migration
- **Fallback:** Castro keeps own persistence, core repository is optional

---

## Expected Outcomes

### Lines of Code

| Category | Before Phase 11 | After Phase 11 | Delta |
|----------|-----------------|----------------|-------|
| Core experiments/runner | existing | +150 | +150 |
| Core experiments/persistence | existing | +300 | +300 |
| Castro state_provider.py | ~250 | ~50 (re-export) | -200 |
| Castro persistence/ | ~300 | ~100 (wrapper) | -200 |
| **Net Castro Reduction** | | | **-400** |

### New Tests Added

| Test File | Test Count |
|-----------|------------|
| test_state_provider_core.py | ~15 |
| test_experiment_repository.py | ~20 |
| **Total** | **~35** |

---

## Related Documents

- [Phase 10: Deep Integration](./phase_10.md) - Prerequisite (deferred these tasks)
- [Conceptual Plan](../conceptual-plan.md) - Architecture overview
- [Development Plan](../development-plan.md) - Timeline
- [Castro StateProvider](../../../../experiments/castro/castro/state_provider.py) - Current implementation

---

*Phase 11 Plan v1.0 - 2025-12-11*
