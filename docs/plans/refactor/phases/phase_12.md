# Phase 12: Castro Migration to Core Infrastructure (Revised)

**Status:** Planned
**Created:** 2025-12-11
**Revised:** 2025-12-11
**Dependencies:** Phase 11 (StateProvider Protocol and Unified Persistence)
**Risk:** Medium (large deletion, but well-tested core modules)
**Breaking Changes:** Castro internal APIs removed (intentional simplification)

---

## Purpose

Phase 12 eliminates Castro's duplicated infrastructure by:

1. **Moving event system to core** - Event types and helpers belong in `ai_cash_mgmt`
2. **Deleting Castro infrastructure** - Use core `experiments/` directly
3. **Reducing Castro to configs + CLI** - Castro becomes a thin entry point

**Target outcome**: Castro reduced from ~1,500 lines to ~200 lines. All infrastructure in core.

---

## Key Insight: What Belongs Where?

### Core `ai_cash_mgmt/` - LLM-Driven Policy Optimization
- Bootstrap evaluation ✅ (already there)
- LLM prompts ✅ (already there)
- Policy representations ✅ (already there)
- **Event types for LLM optimization** ❌ (currently in Castro)
- **Event creation helpers** ❌ (currently in Castro)

### Core `experiments/` - Generic Experiment Infrastructure
- ExperimentRunnerProtocol ✅ (already there)
- ExperimentStateProviderProtocol ✅ (Phase 11)
- ExperimentRepository ✅ (Phase 11)
- EventRecord ✅ (Phase 11)

### Castro - Specific Experiment Definitions
- YAML configs (exp1, exp2, exp3)
- CLI entry point
- **Nothing else**

---

## Current Castro Structure (~1,500 lines)

```
experiments/castro/castro/
├── __init__.py
├── cli.py                    # CLI - KEEP (modify to use core)
├── events.py                 # ~418 lines - MOVE to ai_cash_mgmt
├── state_provider.py         # ~354 lines - DELETE (use core)
├── persistence/
│   ├── __init__.py
│   ├── repository.py         # ~300 lines - DELETE (use core)
│   └── models.py             # ~48 lines - DELETE (use core)
├── runner.py                 # ~200 lines - KEEP (uses core)
├── display.py                # ~150 lines - KEEP (Castro-specific output)
└── configs/                  # KEEP
    ├── exp1.yaml
    ├── exp2.yaml
    └── exp3.yaml
```

---

## Target Castro Structure (~200 lines)

```
experiments/castro/castro/
├── __init__.py               # Re-exports from core
├── cli.py                    # CLI entry point (~100 lines)
├── runner.py                 # Thin wrapper using core (~50 lines)
├── display.py                # Castro-specific output (~50 lines)
└── configs/
    ├── exp1.yaml
    ├── exp2.yaml
    └── exp3.yaml
```

---

## Phase 12 Tasks

### Task 12.1: Move Event System to Core

**Location:** `api/payment_simulator/ai_cash_mgmt/events.py`
**Impact:** Move ~418 lines from Castro to core
**Risk:** Low - just relocating code

Event types and creation helpers are about LLM-driven policy optimization, not Castro-specific.

**What to move:**
- Event type constants (`EVENT_LLM_INTERACTION`, `EVENT_POLICY_CHANGE`, etc.)
- Event creation helpers (`create_llm_interaction_event()`, etc.)
- Convert to return core `EventRecord` instead of Castro `ExperimentEvent`

---

### Task 12.2: Delete Castro Infrastructure

**Impact:** Delete ~700 lines
**Risk:** Medium - ensure nothing breaks

**Files to delete:**
- `castro/state_provider.py` (~354 lines)
- `castro/persistence/repository.py` (~300 lines)
- `castro/persistence/models.py` (~48 lines)
- `castro/events.py` (after moving to core)

---

### Task 12.3: Update Castro to Use Core Directly

**Impact:** Modify ~200 lines
**Risk:** Low - straightforward replacements

**Changes:**
- `runner.py`: Use core `LiveStateProvider`, `ExperimentRepository`
- `cli.py`: Use core persistence for replay
- `display.py`: Use core `DatabaseStateProvider` for replay

---

## TDD Test Specifications

### Test File 1: `api/tests/ai_cash_mgmt/test_events.py`

```python
"""TDD tests for LLM optimization event system.

Tests for event types and creation helpers moved from Castro to core.

Write these tests FIRST, then implement.
"""

from __future__ import annotations

import pytest
from datetime import datetime
from typing import Any


class TestEventTypeConstants:
    """Tests for event type constants."""

    def test_event_types_importable(self) -> None:
        """Event type constants should be importable from ai_cash_mgmt."""
        from payment_simulator.ai_cash_mgmt.events import (
            EVENT_EXPERIMENT_START,
            EVENT_ITERATION_START,
            EVENT_BOOTSTRAP_EVALUATION,
            EVENT_LLM_CALL,
            EVENT_LLM_INTERACTION,
            EVENT_POLICY_CHANGE,
            EVENT_POLICY_REJECTED,
            EVENT_EXPERIMENT_END,
        )

        assert EVENT_EXPERIMENT_START == "experiment_start"
        assert EVENT_LLM_INTERACTION == "llm_interaction"
        assert EVENT_POLICY_CHANGE == "policy_change"

    def test_all_event_types_list(self) -> None:
        """ALL_EVENT_TYPES should contain all event types."""
        from payment_simulator.ai_cash_mgmt.events import (
            ALL_EVENT_TYPES,
            EVENT_EXPERIMENT_START,
            EVENT_LLM_INTERACTION,
        )

        assert EVENT_EXPERIMENT_START in ALL_EVENT_TYPES
        assert EVENT_LLM_INTERACTION in ALL_EVENT_TYPES
        assert len(ALL_EVENT_TYPES) == 8


class TestEventCreationHelpers:
    """Tests for event creation helpers."""

    def test_create_experiment_start_event(self) -> None:
        """Should create experiment start event."""
        from payment_simulator.ai_cash_mgmt.events import (
            create_experiment_start_event,
            EVENT_EXPERIMENT_START,
        )
        from payment_simulator.experiments.persistence import EventRecord

        event = create_experiment_start_event(
            run_id="test-run",
            experiment_name="exp1",
            description="Test experiment",
            model="claude-3",
            max_iterations=10,
            num_samples=5,
        )

        assert isinstance(event, EventRecord)
        assert event.event_type == EVENT_EXPERIMENT_START
        assert event.run_id == "test-run"
        assert event.iteration == 0
        assert event.event_data["experiment_name"] == "exp1"
        assert event.event_data["model"] == "claude-3"

    def test_create_iteration_start_event(self) -> None:
        """Should create iteration start event."""
        from payment_simulator.ai_cash_mgmt.events import (
            create_iteration_start_event,
            EVENT_ITERATION_START,
        )
        from payment_simulator.experiments.persistence import EventRecord

        event = create_iteration_start_event(
            run_id="test-run",
            iteration=5,
            total_cost=100000,  # Integer cents (INV-1)
        )

        assert isinstance(event, EventRecord)
        assert event.event_type == EVENT_ITERATION_START
        assert event.iteration == 5
        assert event.event_data["total_cost"] == 100000

    def test_create_bootstrap_evaluation_event(self) -> None:
        """Should create bootstrap evaluation event."""
        from payment_simulator.ai_cash_mgmt.events import (
            create_bootstrap_evaluation_event,
            EVENT_BOOTSTRAP_EVALUATION,
        )
        from payment_simulator.experiments.persistence import EventRecord

        seed_results = [
            {"seed": 1, "cost": 1000, "settled": 95, "total": 100},
            {"seed": 2, "cost": 1100, "settled": 94, "total": 100},
        ]

        event = create_bootstrap_evaluation_event(
            run_id="test-run",
            iteration=0,
            seed_results=seed_results,
            mean_cost=1050,  # Integer cents
            std_cost=50,     # Integer cents
        )

        assert isinstance(event, EventRecord)
        assert event.event_type == EVENT_BOOTSTRAP_EVALUATION
        assert event.event_data["mean_cost"] == 1050
        assert len(event.event_data["seed_results"]) == 2

    def test_create_llm_interaction_event(self) -> None:
        """Should create LLM interaction event with full audit data."""
        from payment_simulator.ai_cash_mgmt.events import (
            create_llm_interaction_event,
            EVENT_LLM_INTERACTION,
        )
        from payment_simulator.experiments.persistence import EventRecord

        event = create_llm_interaction_event(
            run_id="test-run",
            iteration=1,
            agent_id="BANK_A",
            system_prompt="You are a policy optimizer...",
            user_prompt="Current cost is 1000. Suggest improvement.",
            raw_response="```json\n{\"type\": \"release\"}\n```",
            parsed_policy={"type": "release"},
            parsing_error=None,
            model="claude-3",
            prompt_tokens=100,
            completion_tokens=50,
            latency_seconds=1.5,
        )

        assert isinstance(event, EventRecord)
        assert event.event_type == EVENT_LLM_INTERACTION
        assert event.event_data["agent_id"] == "BANK_A"
        assert event.event_data["system_prompt"] == "You are a policy optimizer..."
        assert event.event_data["parsed_policy"] == {"type": "release"}

    def test_create_policy_change_event(self) -> None:
        """Should create policy change event."""
        from payment_simulator.ai_cash_mgmt.events import (
            create_policy_change_event,
            EVENT_POLICY_CHANGE,
        )
        from payment_simulator.experiments.persistence import EventRecord

        event = create_policy_change_event(
            run_id="test-run",
            iteration=1,
            agent_id="BANK_A",
            old_policy={"type": "hold"},
            new_policy={"type": "release"},
            old_cost=1000,  # Integer cents
            new_cost=800,   # Integer cents
            accepted=True,
        )

        assert isinstance(event, EventRecord)
        assert event.event_type == EVENT_POLICY_CHANGE
        assert event.event_data["old_cost"] == 1000
        assert event.event_data["new_cost"] == 800
        assert event.event_data["accepted"] is True

    def test_create_policy_rejected_event(self) -> None:
        """Should create policy rejected event."""
        from payment_simulator.ai_cash_mgmt.events import (
            create_policy_rejected_event,
            EVENT_POLICY_REJECTED,
        )
        from payment_simulator.experiments.persistence import EventRecord

        event = create_policy_rejected_event(
            run_id="test-run",
            iteration=1,
            agent_id="BANK_A",
            proposed_policy={"type": "invalid"},
            validation_errors=["Unknown policy type"],
            rejection_reason="validation_failed",
        )

        assert isinstance(event, EventRecord)
        assert event.event_type == EVENT_POLICY_REJECTED
        assert "Unknown policy type" in event.event_data["validation_errors"]

    def test_create_experiment_end_event(self) -> None:
        """Should create experiment end event."""
        from payment_simulator.ai_cash_mgmt.events import (
            create_experiment_end_event,
            EVENT_EXPERIMENT_END,
        )
        from payment_simulator.experiments.persistence import EventRecord

        event = create_experiment_end_event(
            run_id="test-run",
            iteration=10,
            final_cost=800,   # Integer cents
            best_cost=750,    # Integer cents
            converged=True,
            convergence_reason="stability",
            duration_seconds=120.5,
        )

        assert isinstance(event, EventRecord)
        assert event.event_type == EVENT_EXPERIMENT_END
        assert event.event_data["converged"] is True
        assert event.event_data["final_cost"] == 800


class TestCostsAreIntegerCents:
    """Tests ensuring all costs are integer cents (INV-1)."""

    def test_iteration_start_cost_is_integer(self) -> None:
        """Iteration start total_cost must be integer cents."""
        from payment_simulator.ai_cash_mgmt.events import (
            create_iteration_start_event,
        )

        event = create_iteration_start_event(
            run_id="test",
            iteration=0,
            total_cost=100050,  # $1,000.50 in cents
        )

        assert isinstance(event.event_data["total_cost"], int)

    def test_bootstrap_costs_are_integers(self) -> None:
        """Bootstrap mean_cost and std_cost must be integer cents."""
        from payment_simulator.ai_cash_mgmt.events import (
            create_bootstrap_evaluation_event,
        )

        event = create_bootstrap_evaluation_event(
            run_id="test",
            iteration=0,
            seed_results=[],
            mean_cost=100050,
            std_cost=5025,
        )

        assert isinstance(event.event_data["mean_cost"], int)
        assert isinstance(event.event_data["std_cost"], int)

    def test_policy_change_costs_are_integers(self) -> None:
        """Policy change old_cost and new_cost must be integer cents."""
        from payment_simulator.ai_cash_mgmt.events import (
            create_policy_change_event,
        )

        event = create_policy_change_event(
            run_id="test",
            iteration=0,
            agent_id="BANK_A",
            old_policy={},
            new_policy={},
            old_cost=100050,
            new_cost=90025,
            accepted=True,
        )

        assert isinstance(event.event_data["old_cost"], int)
        assert isinstance(event.event_data["new_cost"], int)


class TestEventTimestamps:
    """Tests for event timestamps."""

    def test_events_have_iso_timestamp(self) -> None:
        """All events should have ISO format timestamp."""
        from payment_simulator.ai_cash_mgmt.events import (
            create_experiment_start_event,
        )

        event = create_experiment_start_event(
            run_id="test",
            experiment_name="exp1",
            description="Test",
            model="claude-3",
            max_iterations=10,
            num_samples=5,
        )

        # Should be ISO format string
        assert isinstance(event.timestamp, str)
        # Should be parseable
        from datetime import datetime
        parsed = datetime.fromisoformat(event.timestamp)
        assert parsed is not None
```

---

### Test File 2: `experiments/castro/tests/test_castro_uses_core.py`

```python
"""TDD tests verifying Castro uses core modules directly.

Tests that Castro infrastructure is deleted and core is used instead.

Write these tests FIRST, then implement.
"""

from __future__ import annotations

import pytest
from pathlib import Path
from typing import Any


class TestCastroInfrastructureDeleted:
    """Tests that Castro infrastructure files are deleted."""

    def test_castro_state_provider_deleted(self) -> None:
        """castro/state_provider.py should not exist."""
        castro_path = Path(__file__).parent.parent / "castro" / "state_provider.py"
        assert not castro_path.exists(), "state_provider.py should be deleted"

    def test_castro_persistence_repository_deleted(self) -> None:
        """castro/persistence/repository.py should not exist."""
        castro_path = (
            Path(__file__).parent.parent / "castro" / "persistence" / "repository.py"
        )
        assert not castro_path.exists(), "persistence/repository.py should be deleted"

    def test_castro_persistence_models_deleted(self) -> None:
        """castro/persistence/models.py should not exist."""
        castro_path = (
            Path(__file__).parent.parent / "castro" / "persistence" / "models.py"
        )
        assert not castro_path.exists(), "persistence/models.py should be deleted"

    def test_castro_events_deleted(self) -> None:
        """castro/events.py should not exist (moved to core)."""
        castro_path = Path(__file__).parent.parent / "castro" / "events.py"
        assert not castro_path.exists(), "events.py should be moved to core"


class TestCastroImportsCore:
    """Tests that Castro imports from core modules."""

    def test_castro_imports_event_types_from_core(self) -> None:
        """Castro should import event types from ai_cash_mgmt."""
        # This import should work (Castro re-exports from core)
        from payment_simulator.ai_cash_mgmt.events import (
            EVENT_LLM_INTERACTION,
            EVENT_POLICY_CHANGE,
            create_llm_interaction_event,
        )

        assert EVENT_LLM_INTERACTION == "llm_interaction"

    def test_castro_imports_state_provider_from_core(self) -> None:
        """Castro should use StateProvider from core."""
        from payment_simulator.experiments.runner import (
            LiveStateProvider,
            DatabaseStateProvider,
            ExperimentStateProviderProtocol,
        )

        assert LiveStateProvider is not None
        assert DatabaseStateProvider is not None

    def test_castro_imports_repository_from_core(self) -> None:
        """Castro should use ExperimentRepository from core."""
        from payment_simulator.experiments.persistence import (
            ExperimentRepository,
            ExperimentRecord,
            IterationRecord,
            EventRecord,
        )

        assert ExperimentRepository is not None
        assert EventRecord is not None


class TestCastroRunnerUsesCore:
    """Tests that Castro runner uses core infrastructure."""

    def test_runner_uses_core_state_provider(self) -> None:
        """Castro runner should use core LiveStateProvider."""
        # Import Castro runner
        from castro.runner import CastroRunner
        from payment_simulator.experiments.runner import LiveStateProvider

        # Runner should accept or create LiveStateProvider
        # (exact API depends on implementation)
        assert hasattr(CastroRunner, "run") or hasattr(CastroRunner, "__call__")

    def test_runner_uses_core_repository(self) -> None:
        """Castro runner should use core ExperimentRepository."""
        from payment_simulator.experiments.persistence import ExperimentRepository

        # ExperimentRepository should be usable by Castro
        assert ExperimentRepository is not None


class TestCastroReplayUsesCore:
    """Tests that Castro replay uses core infrastructure."""

    def test_replay_uses_core_database_provider(self, tmp_path: Path) -> None:
        """Castro replay should use core DatabaseStateProvider."""
        from payment_simulator.experiments.persistence import (
            ExperimentRepository,
            ExperimentRecord,
            EventRecord,
        )
        from payment_simulator.experiments.runner import DatabaseStateProvider
        from payment_simulator.ai_cash_mgmt.events import (
            create_experiment_start_event,
        )

        # Create database with core
        db_path = tmp_path / "test.db"
        repo = ExperimentRepository(db_path)

        # Save experiment
        record = ExperimentRecord(
            run_id="test-run",
            experiment_name="exp1",
            experiment_type="castro",
            config={},
            created_at="2025-12-11T10:00:00",
            completed_at=None,
            num_iterations=0,
            converged=False,
            convergence_reason=None,
        )
        repo.save_experiment(record)

        # Save event using core event helper
        event = create_experiment_start_event(
            run_id="test-run",
            experiment_name="exp1",
            description="Test",
            model="claude-3",
            max_iterations=10,
            num_samples=5,
        )
        repo.save_event(event)

        # Create provider for replay
        provider = DatabaseStateProvider(repo, "test-run")

        # Should work
        info = provider.get_experiment_info()
        assert info["experiment_name"] == "exp1"

        events = provider.get_iteration_events(0)
        assert len(events) == 1
        assert events[0]["event_type"] == "experiment_start"

        repo.close()
```

---

### Test File 3: `experiments/castro/tests/test_castro_minimal.py`

```python
"""TDD tests verifying Castro is minimal.

Tests that Castro only contains configs and CLI.

Write these tests FIRST, then implement.
"""

from __future__ import annotations

import pytest
from pathlib import Path


class TestCastroStructure:
    """Tests for Castro's minimal structure."""

    def test_castro_has_configs_directory(self) -> None:
        """Castro should have configs directory."""
        configs_path = Path(__file__).parent.parent / "castro" / "configs"
        # Or wherever YAML configs are stored
        assert configs_path.exists() or (
            Path(__file__).parent.parent / "configs"
        ).exists()

    def test_castro_has_cli(self) -> None:
        """Castro should have CLI module."""
        cli_path = Path(__file__).parent.parent / "castro" / "cli.py"
        assert cli_path.exists()

    def test_castro_has_runner(self) -> None:
        """Castro should have runner module (thin wrapper)."""
        runner_path = Path(__file__).parent.parent / "castro" / "runner.py"
        assert runner_path.exists()


class TestCastroLineCount:
    """Tests that Castro code is minimal."""

    def test_castro_total_lines_under_500(self) -> None:
        """Total Castro Python code should be under 500 lines."""
        castro_dir = Path(__file__).parent.parent / "castro"

        total_lines = 0
        for py_file in castro_dir.glob("**/*.py"):
            if "__pycache__" not in str(py_file):
                with open(py_file) as f:
                    # Count non-empty, non-comment lines
                    lines = [
                        line for line in f.readlines()
                        if line.strip() and not line.strip().startswith("#")
                    ]
                    total_lines += len(lines)

        assert total_lines < 500, f"Castro has {total_lines} lines, should be <500"


class TestCastroNoInfrastructure:
    """Tests that Castro has no infrastructure code."""

    def test_no_protocol_definitions(self) -> None:
        """Castro should not define any Protocol classes."""
        castro_dir = Path(__file__).parent.parent / "castro"

        for py_file in castro_dir.glob("**/*.py"):
            if "__pycache__" not in str(py_file):
                content = py_file.read_text()
                assert "class " not in content or "Protocol" not in content, (
                    f"{py_file} should not define Protocol classes"
                )

    def test_no_database_code(self) -> None:
        """Castro should not have database code."""
        castro_dir = Path(__file__).parent.parent / "castro"

        for py_file in castro_dir.glob("**/*.py"):
            if "__pycache__" not in str(py_file):
                content = py_file.read_text()
                # Should not import duckdb directly
                assert "import duckdb" not in content, (
                    f"{py_file} should not import duckdb directly"
                )
```

---

## Implementation Plan

### Task 12.1: Move Event System to Core

**TDD Test File:** `api/tests/ai_cash_mgmt/test_events.py`

**Steps:**
1. Write TDD tests (above)
2. Run tests → FAIL
3. Create `api/payment_simulator/ai_cash_mgmt/events.py`:
   - Copy event type constants from Castro
   - Copy event creation helpers from Castro
   - Modify helpers to return `EventRecord` instead of `ExperimentEvent`
4. Update `api/payment_simulator/ai_cash_mgmt/__init__.py` to export
5. Run tests → PASS

**Files to create:**
- `api/payment_simulator/ai_cash_mgmt/events.py`

**Files to modify:**
- `api/payment_simulator/ai_cash_mgmt/__init__.py`

---

### Task 12.2: Delete Castro Infrastructure

**TDD Test File:** `experiments/castro/tests/test_castro_uses_core.py`

**Steps:**
1. Write TDD tests (above)
2. Run tests → FAIL (files still exist)
3. Delete Castro infrastructure:
   - `castro/state_provider.py`
   - `castro/persistence/repository.py`
   - `castro/persistence/models.py`
   - `castro/events.py`
   - `castro/persistence/__init__.py` (if empty)
4. Run tests → PASS

---

### Task 12.3: Update Castro to Use Core

**TDD Test File:** `experiments/castro/tests/test_castro_minimal.py`

**Steps:**
1. Write TDD tests (above)
2. Run tests → FAIL
3. Update `castro/runner.py`:
   - Import `LiveStateProvider` from core
   - Import `ExperimentRepository` from core
   - Import event helpers from `ai_cash_mgmt.events`
   - Remove all infrastructure code
4. Update `castro/cli.py`:
   - Use core `DatabaseStateProvider` for replay
   - Use core `ExperimentRepository` for persistence
5. Update `castro/__init__.py`:
   - Re-export from core for convenience
6. Run tests → PASS

---

## Verification Checklist

### Before Starting
- [ ] All Phase 11 tests pass
- [ ] All Castro tests pass (baseline)
- [ ] Record Castro line count

### TDD Verification
- [ ] `test_events.py` all pass (Task 12.1)
- [ ] `test_castro_uses_core.py` all pass (Task 12.2)
- [ ] `test_castro_minimal.py` all pass (Task 12.3)

### Integration Verification
- [ ] All API tests pass
- [ ] All Castro tests pass
- [ ] Type checking passes: `mypy`
- [ ] Castro CLI works: `castro run exp1 --max-iter 1 --dry-run`
- [ ] Castro replay works: `castro replay <db>`

### Deletion Verification
- [ ] `castro/state_provider.py` deleted
- [ ] `castro/persistence/` deleted
- [ ] `castro/events.py` deleted
- [ ] Castro line count < 500

---

## Expected Outcomes

### Lines of Code

| Category | Before Phase 12 | After Phase 12 | Delta |
|----------|-----------------|----------------|-------|
| Castro state_provider.py | ~354 | 0 | -354 |
| Castro persistence/ | ~348 | 0 | -348 |
| Castro events.py | ~418 | 0 | -418 |
| Core ai_cash_mgmt/events.py | 0 | ~350 | +350 |
| Castro runner.py | ~200 | ~50 | -150 |
| Castro cli.py | ~100 | ~100 | 0 |
| **Net Castro Reduction** | ~1,420 | ~200 | **-1,220** |
| **Net Core Addition** | | | **+350** |

### Test Summary

| Test File | Test Count |
|-----------|------------|
| test_events.py | ~20 |
| test_castro_uses_core.py | ~10 |
| test_castro_minimal.py | ~5 |
| **Total New Tests** | **~35** |

---

## What Castro Becomes

```
experiments/castro/
├── castro/
│   ├── __init__.py       # Re-exports from core (~10 lines)
│   ├── cli.py            # CLI entry point (~100 lines)
│   ├── runner.py         # Thin wrapper (~50 lines)
│   └── display.py        # Castro output formatting (~50 lines)
├── configs/
│   ├── exp1.yaml
│   ├── exp2.yaml
│   └── exp3.yaml
├── tests/
│   └── ...
└── pyproject.toml
```

**Castro is now just:**
1. YAML experiment configurations
2. CLI entry point that invokes core
3. Thin runner wrapper
4. Output formatting (optional)

All infrastructure lives in core where it belongs.

---

## Related Documents

- [Phase 11: StateProvider and Persistence](./phase_11.md) - Core infrastructure
- [Conceptual Plan](../refactor-conceptual-plan.md) - Architecture overview
- [Development Plan](../development-plan.md) - Timeline

---

*Phase 12 Plan v2.0 (Revised) - 2025-12-11*
