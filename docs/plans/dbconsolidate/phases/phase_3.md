# Phase 3: Experiment → Simulation Linking

**Status**: In Progress
**Started**: 2025-12-14

---

## Goal

Modify the experiment runner to persist simulation runs with experiment linkage, enabling:
- Full traceability from experiment → iteration → evaluation simulation → events
- Replay capability for any simulation run within an experiment
- Unified database where `payment-sim replay <sim-id>` works for experiment simulations

---

## Background Analysis

### Current Gap

The experiment runner (`OptimizationLoop._run_simulation_with_events()`) executes simulations
internally but:
- Does NOT generate simulation IDs
- Does NOT persist to `simulation_runs` table
- Does NOT link simulations to experiments

### Existing Infrastructure (Phase 2 Complete)

The database schema already has all fields needed:

```python
# SimulationRunRecord (persistence/models.py)
experiment_id: str | None  # Link to experiments table
iteration: int | None       # Iteration number within experiment
sample_index: int | None    # Bootstrap sample index
run_purpose: str | None     # Purpose: 'evaluation', 'bootstrap', etc.
```

```python
# IterationRecord (experiments/persistence/repository.py)
evaluation_simulation_id: str | None  # Link to simulation_runs
```

### Structured Simulation ID Format

```
{experiment_id}-iter{N}-{purpose}[-sample{M}]

Examples:
  exp1-20251214-abc123-iter0-initial
  exp1-20251214-abc123-iter5-evaluation
  exp1-20251214-abc123-iter5-bootstrap-sample3
  exp1-20251214-abc123-iter49-final
```

---

## Design Decision

**Option B: Full Integration - Use SimulationRunner**

We will integrate experiment simulation execution with the existing SimulationRunner
infrastructure. This provides:
- Consistent persistence across CLI and experiment runs
- Full event capture and replay identity
- Reuse of tested persistence code

---

## Implementation Plan

### Sub-Phase 3.1: Simulation ID Generator for Experiments

Create a utility function to generate structured simulation IDs:

```python
def generate_experiment_simulation_id(
    experiment_id: str,
    iteration: int,
    purpose: SimulationRunPurpose,
    sample_index: int | None = None,
) -> str:
    """Generate structured simulation ID for experiment runs."""
    base = f"{experiment_id}-iter{iteration}-{purpose.value}"
    if sample_index is not None:
        base += f"-sample{sample_index}"
    return base
```

**Tests (RED first)**:
- `test_generates_correct_format_for_evaluation`
- `test_generates_correct_format_with_sample_index`
- `test_parses_back_to_components`

### Sub-Phase 3.2: ExperimentPersistencePolicy Dataclass

Create policy configuration for experiment persistence:

```python
@dataclass
class ExperimentPersistencePolicy:
    """Policy controlling what gets persisted during experiments."""

    # Persistence level for evaluation simulations
    simulation_persistence: SimulationPersistenceLevel = SimulationPersistenceLevel.FULL

    # Whether to persist bootstrap sample transactions (usually False)
    persist_bootstrap_transactions: bool = False

    # Always persist final evaluation
    persist_final_evaluation: bool = True

    # Persist all policy iterations (accepted AND rejected)
    persist_all_policy_iterations: bool = True
```

**Tests (RED first)**:
- `test_default_policy_values`
- `test_policy_serialization_to_config`

### Sub-Phase 3.3: ExperimentSimulationPersister

Create a class that wraps simulation execution with persistence:

```python
class ExperimentSimulationPersister:
    """Persists simulation runs executed during experiments."""

    def __init__(
        self,
        db_manager: DatabaseManager,
        experiment_id: str,
        policy: ExperimentPersistencePolicy,
    ) -> None:
        ...

    def run_and_persist_simulation(
        self,
        config: dict,
        seed: int,
        iteration: int,
        purpose: SimulationRunPurpose,
        sample_index: int | None = None,
    ) -> tuple[EnrichedEvaluationResult, str]:
        """Run simulation and persist to database.

        Returns:
            Tuple of (evaluation result, simulation_id)
        """
        ...
```

**Tests (RED first)**:
- `test_generates_simulation_id_before_run`
- `test_persists_simulation_run_record`
- `test_links_simulation_to_experiment`
- `test_respects_persistence_policy`
- `test_returns_simulation_id_with_result`

### Sub-Phase 3.4: Integrate with OptimizationLoop

Modify `OptimizationLoop` to use `ExperimentSimulationPersister`:

1. Add `_simulation_persister: ExperimentSimulationPersister | None` attribute
2. Modify `_run_simulation_with_events()` to delegate to persister
3. Store returned simulation IDs
4. Update `_save_iteration_record()` to include `evaluation_simulation_id`

**Tests (RED first)**:
- `test_optimization_loop_persists_evaluation_simulations`
- `test_iteration_record_links_to_simulation`
- `test_can_replay_experiment_simulation`

### Sub-Phase 3.5: Update IterationRecord Storage

Ensure IterationRecord stores the evaluation_simulation_id link:

```python
# In OptimizationLoop._save_iteration_record()
iter_record = IterationRecord(
    experiment_id=self._run_id,
    iteration=iteration,
    costs_per_agent=costs,
    accepted_changes=changes,
    policies=policies,
    timestamp=now_iso,
    evaluation_simulation_id=sim_id,  # NEW: Link to simulation
)
```

**Tests (RED first)**:
- `test_iteration_record_has_simulation_link`
- `test_can_query_simulation_from_iteration`

### Sub-Phase 3.6: Integration Tests

End-to-end tests verifying the full flow:

**Tests (RED first)**:
- `test_experiment_creates_linked_simulations`
- `test_experiment_simulations_appear_in_db_simulations_list`
- `test_can_query_all_simulations_for_experiment`
- `test_simulation_events_persisted_for_experiment_runs`

---

## Files to Modify

| File | Changes |
|------|---------|
| `experiments/simulation_id.py` | NEW: Simulation ID generator for experiments |
| `experiments/persistence/policy.py` | NEW: ExperimentPersistencePolicy dataclass |
| `experiments/persistence/simulation_persister.py` | NEW: ExperimentSimulationPersister class |
| `experiments/runner/optimization.py` | Integrate persister, update iteration records |
| `experiments/persistence/repository.py` | Ensure evaluation_simulation_id is saved |
| `tests/experiments/test_simulation_linking.py` | NEW: All Phase 3 tests |

---

## Files to Create

### 1. `experiments/simulation_id.py`

```python
"""Simulation ID generation for experiment runs.

Phase 3 Database Consolidation: Provides structured simulation IDs
that link experiments to their constituent simulation runs.
"""

from payment_simulator.persistence.models import SimulationRunPurpose


def generate_experiment_simulation_id(
    experiment_id: str,
    iteration: int,
    purpose: SimulationRunPurpose,
    sample_index: int | None = None,
) -> str:
    """Generate structured simulation ID for experiment runs.

    Format: {experiment_id}-iter{N}-{purpose}[-sample{M}]

    Args:
        experiment_id: Parent experiment ID
        iteration: Iteration number (0-indexed)
        purpose: Simulation purpose (evaluation, bootstrap, etc.)
        sample_index: Bootstrap sample index (optional)

    Returns:
        Structured simulation ID
    """
    base = f"{experiment_id}-iter{iteration}-{purpose.value}"
    if sample_index is not None:
        base += f"-sample{sample_index}"
    return base


def parse_experiment_simulation_id(sim_id: str) -> dict:
    """Parse structured simulation ID back to components.

    Args:
        sim_id: Structured simulation ID

    Returns:
        Dict with experiment_id, iteration, purpose, sample_index
    """
    # Implementation...
```

### 2. `experiments/persistence/policy.py`

```python
"""Experiment persistence policy configuration.

Phase 3 Database Consolidation: Controls what gets persisted
during experiment execution.
"""

from dataclasses import dataclass
from enum import Enum


class SimulationPersistenceLevel(str, Enum):
    """Level of simulation detail to persist."""

    NONE = "none"          # No persistence
    SUMMARY = "summary"    # Final metrics only
    EVENTS = "events"      # Events + summary
    FULL = "full"          # Full tick-level state


@dataclass
class ExperimentPersistencePolicy:
    """Policy controlling what gets persisted during experiments."""

    simulation_persistence: SimulationPersistenceLevel = SimulationPersistenceLevel.FULL
    persist_bootstrap_transactions: bool = False
    persist_final_evaluation: bool = True
    persist_all_policy_iterations: bool = True
```

---

## Test Plan (TDD)

### Test File: `tests/experiments/test_simulation_linking.py`

```python
"""TDD tests for Phase 3: Experiment → Simulation linking.

Write these tests FIRST, then implement.
"""

class TestSimulationIdGeneration:
    """Tests for structured simulation ID generation."""

    def test_generates_evaluation_format(self) -> None:
        """Should generate correct format for evaluation runs."""
        ...

    def test_generates_bootstrap_format_with_sample(self) -> None:
        """Should include sample index for bootstrap runs."""
        ...

    def test_parses_back_to_components(self) -> None:
        """Should parse ID back to original components."""
        ...


class TestExperimentPersistencePolicy:
    """Tests for persistence policy."""

    def test_default_values(self) -> None:
        """Should have correct default values."""
        ...


class TestExperimentSimulationPersister:
    """Tests for simulation persister."""

    def test_generates_id_before_run(self) -> None:
        """Should generate simulation ID before execution."""
        ...

    def test_persists_simulation_run_record(self) -> None:
        """Should persist to simulation_runs table."""
        ...

    def test_links_to_experiment(self) -> None:
        """Should set experiment_id in simulation record."""
        ...


class TestOptimizationLoopIntegration:
    """Tests for OptimizationLoop integration."""

    def test_persists_evaluation_simulations(self) -> None:
        """Should persist each evaluation simulation."""
        ...

    def test_links_iteration_to_simulation(self) -> None:
        """IterationRecord should have evaluation_simulation_id."""
        ...


class TestEndToEndExperimentPersistence:
    """End-to-end integration tests."""

    def test_experiment_creates_linked_simulations(self) -> None:
        """Full experiment should create linked simulations."""
        ...

    def test_simulations_queryable_from_unified_db(self) -> None:
        """Experiment simulations should be queryable via db commands."""
        ...
```

---

## Critical Invariants to Preserve

| Invariant | How We Preserve It |
|-----------|-------------------|
| **INV-1** | All costs in SimulationRunRecord use integer cents (BIGINT) |
| **INV-2** | Store simulation seed and experiment master_seed for replay |
| **INV-5** | Use existing EventWriter for replay-identical event persistence |
| **INV-6** | Events remain self-contained via existing event capture |

---

## Sub-Phase Checklist

- [x] **3.1** Simulation ID generator (`experiments/simulation_id.py`)
- [x] **3.2** ExperimentPersistencePolicy dataclass
- [x] **3.3** ExperimentSimulationPersister class
- [x] **3.4** Integrate with OptimizationLoop (infrastructure ready)
- [x] **3.5** Update IterationRecord storage
- [ ] **3.6** End-to-end integration tests
- [ ] **3.7** Run full test suite
- [ ] **3.8** Update work_notes.md

---

## Dependencies

- Phase 2 complete (unified schema with experiment tables)
- `SimulationRunRecord` has experiment linkage columns ✅
- `IterationRecord` has `evaluation_simulation_id` field ✅
- DatabaseManager creates all required tables ✅

---

## Risk Mitigation

1. **Performance**: Persisting full tick state may slow experiments
   - Mitigation: Use `SimulationPersistenceLevel.EVENTS` for faster runs

2. **Storage**: Full persistence uses ~2MB per simulation
   - Mitigation: Policy allows disabling bootstrap transaction persistence

3. **Backwards compatibility**: Existing experiments don't have linked simulations
   - Mitigation: This is expected - we said "no backwards compatibility"
