# Phase 13: Complete Experiment StateProvider Migration

**Status:** PLANNED
**Created:** 2025-12-11
**Prerequisites:** Phase 12.2 (Runner and CLI migrated to core ExperimentRepository)

---

## Goal

Complete the StateProvider pattern migration for experiments:
1. Extend core `ExperimentStateProviderProtocol` with Castro's audit methods
2. Migrate Castro's `DatabaseExperimentProvider` to use core's implementation
3. Update Castro's replay/audit display to use core StateProvider
4. Delete Castro's infrastructure files (`state_provider.py`, `persistence/`, `event_compat.py`)

---

## Background: StateProvider Pattern

The StateProvider pattern (see `docs/reference/architecture/09-persistence-layer.md`) ensures **replay identity**:

```
┌─────────────────────────────────────────────────────────┐
│          display_experiment_output()                     │
│          (Single Source of Truth for Display)            │
└────────────────┬───────────────────────────────────────┘
                 │
         ┌───────┴────────┐
         │ StateProvider  │  ← Protocol (interface)
         │   Protocol     │
         └───────┬────────┘
                 │
    ┌────────────┴─────────────┐
    │                          │
    ▼                          ▼
┌────────────────┐      ┌──────────────────┐
│ LiveStateProvider│    │ DatabaseStateProvider│
│ (Live execution) │    │ (Replay)             │
└────────────────┘      └──────────────────┘
```

Same display function, same output, whether live or replay.

---

## Gap Analysis

### Core Protocol (Phase 11)

```python
class ExperimentStateProviderProtocol(Protocol):
    def get_experiment_info(self) -> dict[str, Any]: ...
    def get_total_iterations(self) -> int: ...
    def get_iteration_events(iteration) -> list[dict[str, Any]]: ...
    def get_iteration_policies(iteration) -> dict[str, Any]: ...
    def get_iteration_costs(iteration) -> dict[str, int]: ...
    def get_iteration_accepted_changes(iteration) -> dict[str, bool]: ...
```

### Castro Protocol (Current)

```python
class ExperimentStateProvider(Protocol):
    @property
    def run_id(self) -> str: ...
    def get_run_metadata(self) -> dict[str, Any] | None: ...
    def get_all_events(self) -> Iterator[ExperimentEvent]: ...
    def get_events_for_iteration(iteration) -> list[ExperimentEvent]: ...
    def get_final_result(self) -> dict[str, Any]: ...
```

### Missing in Core

| Method | Purpose | Required For |
|--------|---------|--------------|
| `run_id` property | Get run identifier | Display header |
| `get_run_metadata()` | Run details (name, model) | Display header |
| `get_all_events()` | Iterator over all events | Audit display |
| `get_final_result()` | Final cost, converged | Results display |

---

## Tasks

### Task 13.1: Extend Core Protocol with Audit Methods

**Goal:** Add missing methods to core `ExperimentStateProviderProtocol`

**TDD Tests First:**
```python
# tests/experiments/runner/test_state_provider_audit.py

class TestAuditMethods:
    def test_protocol_has_run_id_property(self) -> None:
        """Protocol should include run_id property."""
        assert hasattr(ExperimentStateProviderProtocol, 'run_id')

    def test_protocol_has_get_run_metadata(self) -> None:
        """Protocol should include get_run_metadata method."""
        assert hasattr(ExperimentStateProviderProtocol, 'get_run_metadata')

    def test_protocol_has_get_all_events(self) -> None:
        """Protocol should include get_all_events method."""
        assert hasattr(ExperimentStateProviderProtocol, 'get_all_events')

    def test_protocol_has_get_final_result(self) -> None:
        """Protocol should include get_final_result method."""
        assert hasattr(ExperimentStateProviderProtocol, 'get_final_result')

class TestLiveStateProviderAudit:
    def test_run_id_returns_identifier(self) -> None:
        provider = LiveStateProvider(
            experiment_name="exp1",
            experiment_type="castro",
            config={},
            run_id="exp1-123",
        )
        assert provider.run_id == "exp1-123"

    def test_get_all_events_iterates_all(self) -> None:
        provider = LiveStateProvider(...)
        provider.record_event(0, "llm_interaction", {"agent_id": "A"})
        provider.record_event(1, "llm_interaction", {"agent_id": "B"})

        events = list(provider.get_all_events())
        assert len(events) == 2

    def test_get_run_metadata_returns_dict(self) -> None:
        provider = LiveStateProvider(...)
        metadata = provider.get_run_metadata()
        assert "experiment_name" in metadata
        assert "run_id" in metadata

    def test_get_final_result_after_set(self) -> None:
        provider = LiveStateProvider(...)
        provider.set_final_result(
            final_cost=15000,
            best_cost=14000,
            converged=True,
            convergence_reason="stability",
        )
        result = provider.get_final_result()
        assert result["final_cost"] == 15000  # Integer cents

class TestDatabaseStateProviderAudit:
    def test_get_all_events_from_database(self, tmp_path) -> None:
        # Create database with events
        repo = ExperimentRepository(tmp_path / "test.db")
        # ... save experiment and events ...

        provider = repo.as_state_provider("run-123")
        events = list(provider.get_all_events())
        assert len(events) > 0

    def test_get_run_metadata_from_database(self, tmp_path) -> None:
        repo = ExperimentRepository(tmp_path / "test.db")
        # ... save experiment ...

        provider = repo.as_state_provider("run-123")
        metadata = provider.get_run_metadata()
        assert metadata["experiment_name"] == "exp1"

    def test_get_final_result_from_database(self, tmp_path) -> None:
        repo = ExperimentRepository(tmp_path / "test.db")
        # ... save completed experiment ...

        provider = repo.as_state_provider("run-123")
        result = provider.get_final_result()
        assert isinstance(result["final_cost"], int)  # INV-1
```

**Implementation:**
1. Add methods to `ExperimentStateProviderProtocol`
2. Implement in `LiveStateProvider`
3. Implement in `DatabaseStateProvider`

**Files to modify:**
- `api/payment_simulator/experiments/runner/state_provider.py`

---

### Task 13.2: Update Castro Display to Use Core Protocol

**Goal:** Update Castro's display/audit_display to use core's `ExperimentStateProviderProtocol`

**TDD Tests First:**
```python
# experiments/castro/tests/test_display_uses_core_provider.py

def _get_display_source() -> str:
    display_path = Path(__file__).parent.parent / "castro" / "display.py"
    return display_path.read_text()

def _get_audit_display_source() -> str:
    audit_path = Path(__file__).parent.parent / "castro" / "audit_display.py"
    return audit_path.read_text()

class TestDisplayImports:
    def test_display_imports_from_core(self) -> None:
        source = _get_display_source()
        assert "from payment_simulator.experiments.runner import" in source
        assert "ExperimentStateProviderProtocol" in source

    def test_display_does_not_import_castro_state_provider(self) -> None:
        source = _get_display_source()
        assert "from castro.state_provider import" not in source

    def test_audit_display_imports_from_core(self) -> None:
        source = _get_audit_display_source()
        assert "from payment_simulator.experiments.runner import" in source

    def test_audit_display_does_not_import_castro_state_provider(self) -> None:
        source = _get_audit_display_source()
        assert "from castro.state_provider import" not in source

class TestDisplayUsesProtocol:
    def test_display_works_with_core_live_provider(self) -> None:
        from payment_simulator.experiments.runner import LiveStateProvider
        from castro.display import display_experiment_output

        provider = LiveStateProvider(...)
        # Should work without errors
        display_experiment_output(provider, Console(), VerboseConfig())

    def test_audit_works_with_core_database_provider(self, tmp_path) -> None:
        from payment_simulator.experiments.persistence import ExperimentRepository
        from castro.audit_display import display_audit_output

        repo = ExperimentRepository(tmp_path / "test.db")
        # ... save experiment with events ...

        provider = repo.as_state_provider("run-123")
        # Should work without errors
        display_audit_output(provider, Console())
```

**Implementation:**
1. Update `castro/display.py` to import from core
2. Update `castro/audit_display.py` to import from core
3. Update functions to use core's protocol methods

**Files to modify:**
- `experiments/castro/castro/display.py`
- `experiments/castro/castro/audit_display.py`

---

### Task 13.3: Update Castro CLI Replay to Use Core Provider

**Goal:** CLI `replay` command uses core `DatabaseStateProvider`

**TDD Tests First:**
```python
# experiments/castro/tests/test_cli_replay_uses_core.py

def _get_cli_source() -> str:
    cli_path = Path(__file__).parent.parent / "cli.py"
    return cli_path.read_text()

class TestReplayImports:
    def test_replay_imports_from_core(self) -> None:
        source = _get_cli_source()
        # In the replay function block
        assert "from payment_simulator.experiments.persistence import ExperimentRepository" in source

    def test_replay_does_not_import_castro_state_provider(self) -> None:
        source = _get_cli_source()
        assert "from castro.state_provider import DatabaseExperimentProvider" not in source

class TestReplayUsesCore:
    def test_replay_uses_repository_as_state_provider(self, tmp_path) -> None:
        # Create test database with experiment
        repo = ExperimentRepository(tmp_path / "test.db")
        # ... save experiment with events ...

        # CLI should use repo.as_state_provider()
        provider = repo.as_state_provider("run-123")
        assert provider.run_id == "run-123"
```

**Implementation:**
1. Update CLI `replay` command to use `ExperimentRepository.as_state_provider()`
2. Remove import of `DatabaseExperimentProvider` from castro

**Files to modify:**
- `experiments/castro/cli.py`

---

### Task 13.4: Delete Castro Infrastructure

**Goal:** Remove Castro's duplicated infrastructure files

**TDD Tests First:**
```python
# experiments/castro/tests/test_castro_infrastructure_deleted.py

class TestInfrastructureDeleted:
    def test_state_provider_deleted(self) -> None:
        state_provider_path = Path(__file__).parent.parent / "castro" / "state_provider.py"
        assert not state_provider_path.exists(), "castro/state_provider.py should be deleted"

    def test_persistence_directory_deleted(self) -> None:
        persistence_path = Path(__file__).parent.parent / "castro" / "persistence"
        assert not persistence_path.exists(), "castro/persistence/ should be deleted"

    def test_event_compat_deleted(self) -> None:
        event_compat_path = Path(__file__).parent.parent / "castro" / "event_compat.py"
        assert not event_compat_path.exists(), "castro/event_compat.py should be deleted"

class TestCastroImportsFromCore:
    def test_castro_init_exports_from_core(self) -> None:
        # Castro should re-export commonly used types from core
        from castro import LiveStateProvider, DatabaseStateProvider
        # These should be core types, not castro types
        from payment_simulator.experiments.runner import (
            LiveStateProvider as CoreLive,
            DatabaseStateProvider as CoreDB,
        )
        assert LiveStateProvider is CoreLive
        assert DatabaseStateProvider is CoreDB
```

**Implementation:**
1. Delete `experiments/castro/castro/state_provider.py`
2. Delete `experiments/castro/castro/persistence/` directory
3. Delete `experiments/castro/castro/event_compat.py`
4. Update `experiments/castro/castro/__init__.py` to re-export from core

**Files to delete:**
- `experiments/castro/castro/state_provider.py`
- `experiments/castro/castro/persistence/repository.py`
- `experiments/castro/castro/persistence/models.py`
- `experiments/castro/castro/persistence/__init__.py`
- `experiments/castro/castro/event_compat.py`

---

### Task 13.5: Update All Castro Test Imports

**Goal:** Update remaining test files to import from core

**TDD Tests First:**
```python
# Check no test files import from deleted modules
def test_no_tests_import_castro_state_provider() -> None:
    tests_dir = Path(__file__).parent
    for test_file in tests_dir.glob("test_*.py"):
        source = test_file.read_text()
        assert "from castro.state_provider import" not in source, f"{test_file.name}"

def test_no_tests_import_castro_persistence() -> None:
    tests_dir = Path(__file__).parent
    for test_file in tests_dir.glob("test_*.py"):
        source = test_file.read_text()
        assert "from castro.persistence import" not in source, f"{test_file.name}"

def test_no_tests_import_castro_event_compat() -> None:
    tests_dir = Path(__file__).parent
    for test_file in tests_dir.glob("test_*.py"):
        source = test_file.read_text()
        assert "from castro.event_compat import" not in source, f"{test_file.name}"
```

**Implementation:**
1. Find all test files importing from deleted modules
2. Update imports to use core modules
3. Update test assertions to use core types

**Files to modify:**
- Multiple test files in `experiments/castro/tests/`

---

## Execution Order

```
Task 13.1: Extend Core Protocol (TDD)
    ├── Write tests for audit methods
    ├── Run tests → FAIL
    ├── Implement protocol methods
    └── Run tests → PASS

Task 13.2: Update Castro Display (TDD)
    ├── Write tests for display imports
    ├── Run tests → FAIL
    ├── Update display.py and audit_display.py
    └── Run tests → PASS

Task 13.3: Update CLI Replay (TDD)
    ├── Write tests for replay imports
    ├── Run tests → FAIL
    ├── Update cli.py replay command
    └── Run tests → PASS

Task 13.4: Delete Infrastructure (TDD)
    ├── Write tests for file deletion
    ├── Run tests → FAIL
    ├── Delete files
    └── Run tests → PASS

Task 13.5: Update Test Imports
    ├── Write meta-tests for test imports
    ├── Run tests → FAIL
    ├── Update all test file imports
    └── Run tests → PASS

Final Verification:
    ├── Run full core test suite
    ├── Run full Castro test suite
    └── Verify replay works end-to-end
```

---

## Invariants to Maintain

### INV-1: Integer Cents
All cost values must be `int` (not `float`):
```python
def get_iteration_costs(iteration: int) -> dict[str, int]:  # Not float!
def get_final_result() -> dict[str, Any]:
    # result["final_cost"] must be int
    # result["best_cost"] must be int
```

### Replay Identity
Run and replay must produce identical output:
```bash
castro run exp1 --verbose > run.txt
castro replay run-id --verbose > replay.txt
diff <(grep -v "Duration:" run.txt) <(grep -v "Duration:" replay.txt)
# Must be empty (no differences)
```

### Protocol Compatibility
Core protocol must be a superset of Castro's needs:
- All methods Castro display uses must exist in core protocol
- Event format must be compatible (dict with `event_type` key)

---

## Expected Outcomes

### Lines Changed

| Category | Added | Removed | Net |
|----------|-------|---------|-----|
| Core state_provider.py | ~80 | 0 | +80 |
| Castro display.py | ~10 | ~10 | 0 |
| Castro audit_display.py | ~10 | ~15 | -5 |
| Castro cli.py | ~10 | ~15 | -5 |
| Castro state_provider.py | 0 | ~370 | -370 |
| Castro persistence/ | 0 | ~500 | -500 |
| Castro event_compat.py | 0 | ~150 | -150 |
| Tests | ~200 | ~50 | +150 |
| **Total** | ~310 | ~1110 | **-800** |

### Final State

After Phase 13:
- Castro uses **only** core infrastructure for persistence and state
- Castro contains: YAML configs, CLI entry point, constraints, display
- Core `experiments/` is complete StateProvider pattern
- ~800 lines removed from Castro
- Full replay identity maintained

---

## Test Coverage Targets

| Component | Target |
|-----------|--------|
| Core state_provider.py | 90% |
| Castro display.py | 85% |
| Castro cli.py replay | 85% |
| Integration tests | 80% |

---

## Risk Mitigation

| Risk | Mitigation |
|------|------------|
| Event format incompatibility | Use dict[str, Any] as common format |
| Missing database columns | Core schema includes all needed fields |
| Display function signature | Use protocol type hints |
| pydantic_ai not installed | Tests use file parsing, not import |

---

*Phase 13 Plan v1.0 - 2025-12-11*
