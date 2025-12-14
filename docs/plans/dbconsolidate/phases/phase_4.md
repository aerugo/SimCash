# Phase 4: Unified CLI Commands

**Status**: In Progress
**Started**: 2025-12-14

---

## Goal

Make all CLI commands work on any unified database, enabling:
- Query both standalone AND experiment-linked simulations
- List experiments with iteration counts
- Replay any simulation regardless of how it was created
- Show experiment context for linked simulations

---

## Background Analysis

### Current State

The CLI already has:
- `payment-sim db simulations` - Lists simulations from `simulation_runs` table
- `payment-sim db info` - Shows database statistics
- `payment-sim replay` - Replays a simulation by ID

### Gap

1. `db simulations` doesn't show experiment linkage columns
2. No `db experiments` command to list experiments
3. No way to drill into experiment iterations
4. Replay doesn't know about experiment simulations

### Phase 3 Infrastructure (Ready)

- `simulation_runs` table has `experiment_id`, `iteration`, `run_purpose` columns
- `experiments` table exists with full metadata
- `experiment_iterations` table links iterations to simulations
- ExperimentSimulationPersister generates structured simulation IDs

---

## Implementation Plan

### Sub-Phase 4.1: Extend `db simulations` to Show Experiment Context

Modify existing `db_simulations` command to display:
- experiment_id (if linked)
- iteration number (if linked)
- run_purpose (evaluation, bootstrap, etc.)

**Tests (RED first)**:
- `test_db_simulations_shows_experiment_id_column`
- `test_db_simulations_shows_standalone_as_none`
- `test_db_simulations_shows_purpose_column`

### Sub-Phase 4.2: Add `db experiments` Command

New command to list experiments:

```python
@db_app.command("experiments")
def db_experiments(
    db_path: str = "simulation_data.db",
    limit: int = 20,
) -> None:
    """List experiments in the database."""
    ...
```

Display columns:
- experiment_id
- experiment_name
- num_iterations
- converged
- created_at
- final_cost (in dollars)

**Tests (RED first)**:
- `test_db_experiments_lists_experiments`
- `test_db_experiments_shows_iteration_count`
- `test_db_experiments_shows_converged_status`
- `test_db_experiments_shows_final_cost_in_dollars`

### Sub-Phase 4.3: Add `db experiment-details` Command

New command to show experiment details and its simulations:

```python
@db_app.command("experiment-details")
def db_experiment_details(
    experiment_id: str,
    db_path: str = "simulation_data.db",
) -> None:
    """Show details for a specific experiment."""
    ...
```

Display:
- Experiment metadata (name, type, converged, dates)
- List of linked simulations with their purposes
- Cost summary per iteration

**Tests (RED first)**:
- `test_experiment_details_shows_metadata`
- `test_experiment_details_lists_linked_simulations`
- `test_experiment_details_shows_cost_by_iteration`

### Sub-Phase 4.4: Update Replay Command for Experiment Simulations

Ensure `payment-sim replay <sim-id>` works for experiment simulations:
- Works with structured simulation IDs (exp-123-iter5-evaluation)
- Shows experiment context in output

**Tests (RED first)**:
- `test_replay_works_with_experiment_simulation_id`
- `test_replay_shows_experiment_context`

### Sub-Phase 4.5: Integration Tests

End-to-end tests:
- Create experiment, run iterations, verify CLI output
- Query simulations and experiments in same database

---

## Files to Modify

| File | Changes |
|------|---------|
| `cli/commands/db.py` | Extend simulations, add experiments commands |
| `cli/commands/replay.py` | Show experiment context |
| `tests/cli/test_db_commands_unified.py` | NEW: Phase 4 tests |

---

## Test Plan (TDD)

### Test File: `tests/cli/test_db_commands_unified.py`

```python
"""TDD tests for Phase 4: Unified CLI commands.

Write these tests FIRST, then implement.
"""

import pytest
from typer.testing import CliRunner


class TestDbSimulationsWithExperiments:
    """Tests for db simulations showing experiment context."""

    def test_shows_experiment_id_column(self) -> None:
        """Should display experiment_id for linked simulations."""
        ...

    def test_shows_standalone_as_none(self) -> None:
        """Standalone simulations should show no experiment link."""
        ...


class TestDbExperimentsCommand:
    """Tests for new db experiments command."""

    def test_lists_experiments(self) -> None:
        """Should list all experiments in database."""
        ...

    def test_shows_iteration_count(self) -> None:
        """Should show num_iterations for each experiment."""
        ...


class TestDbExperimentDetailsCommand:
    """Tests for experiment-details command."""

    def test_shows_metadata(self) -> None:
        """Should display experiment metadata."""
        ...

    def test_lists_linked_simulations(self) -> None:
        """Should list all simulations linked to experiment."""
        ...


class TestReplayWithExperimentSimulations:
    """Tests for replay command with experiment simulations."""

    def test_replay_works_with_structured_id(self) -> None:
        """Should replay simulation by structured experiment ID."""
        ...
```

---

## Sub-Phase Checklist

- [x] **4.1** Extend db simulations to show experiment context
- [x] **4.2** Add db experiments command
- [x] **4.3** Add db experiment-details command
- [x] **4.4** Update replay for experiment simulations (skipped - deferred to Phase 5)
- [ ] **4.5** Integration tests
- [ ] **4.6** Run full test suite
- [ ] **4.7** Update work_notes.md

---

## Dependencies

- Phase 3 complete (experiment → simulation linking infrastructure)
- `experiments` table populated by experiment runs
- `simulation_runs.experiment_id` column populated

---

## Critical Invariants to Preserve

| Invariant | How We Preserve It |
|-----------|-------------------|
| **INV-1** | Display costs in dollars but store as integer cents |
| **INV-2** | Show seeds in listings for reproducibility |
| **INV-5** | Replay must work identically for experiment simulations |

---

## Risk Mitigation

1. **Backwards compatibility**: CLI commands should work on databases without experiments
   - Mitigation: Handle NULL experiment_id gracefully

2. **Performance**: Joining experiments table on every query
   - Mitigation: LEFT JOIN with minimal columns, lazy load details
