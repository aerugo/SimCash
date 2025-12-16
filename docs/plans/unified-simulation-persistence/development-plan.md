# Unified Simulation Persistence - Development Plan

**Status**: In Progress
**Created**: 2025-12-16
**Branch**: `claude/simcash-experiment-replay-fAM35`

## Summary

Ensure that simulations run through `payment-sim experiment run` persist to the same database tables as `payment-sim run --persist --full-replay`, enabling `payment-sim replay --simulation-id <id> --verbose` to work identically for both execution contexts.

## Problem Statement

Currently, two completely separate persistence paths exist:

```
payment-sim run --persist:
┌─────────────────┐    ┌─────────────────┐    ┌──────────────────────┐
│ SimulationRunner│───▶│PersistenceManager│───▶│ simulations table    │
│                 │    │                 │    │ simulation_events    │
└─────────────────┘    └─────────────────┘    │ transactions         │
                                              └──────────────────────┘

payment-sim experiment run:
┌─────────────────────┐    ┌────────────────────┐    ┌──────────────────────┐
│ OptimizationRunner  │───▶│ ExperimentRepository│───▶│ experiments table    │
│ _run_simulation()   │    │                    │    │ experiment_events    │
└─────────────────────┘    └────────────────────┘    │ (JSON blob in        │
                                                     │  event_data)         │
                                                     └──────────────────────┘
```

Commit `d1cf8c6` (2025-12-14) documented a "unified database architecture" but the implementation was incomplete. Commit `926d552` persisted simulation events as JSON blobs in `experiment_events.event_data`, not to the standard `simulation_events` table.

**Result**: `payment-sim replay --simulation-id` cannot replay simulations from experiment databases.

## Definition of Success

1. **Same Code Path**: Exactly the same persistence code executes when running simulations through experiments as when running `payment-sim run --verbose --persist --full-replay`

2. **Full Replay Support**: All simulations can be replayed with:
   ```bash
   payment-sim replay --simulation-id <sim-id> --verbose
   ```
   producing output identical to the original run

3. **Path Non-Divergence**: A protocol pattern ensures CLI and experiment runner paths can NEVER diverge in the future

## Critical Invariants to Respect

- **INV-1**: Money is ALWAYS i64 - All costs persisted as integer cents
- **INV-2**: Determinism is Sacred - Same seed produces identical results; persist seed for reproducibility
- **INV-5**: Replay Identity - `replay --verbose` output MUST match `run --verbose` output
- **INV-6**: Event Completeness - Events contain ALL fields needed for display

### NEW Invariant to Add

- **NEW INV-11**: Simulation Persistence Identity

  **Rule**: For any simulation S, persistence MUST produce identical database records regardless of which code path executes the simulation.

  ```python
  # Both paths MUST use SimulationPersistenceProvider
  persistence(cli_path, S) == persistence(experiment_path, S)
  ```

  **Requirements**:
  - ALL code paths that run simulations MUST use `SimulationPersistenceProvider`
  - Event capture, transformation, and storage logic MUST be in one place
  - Table schema MUST be consistent across all paths
  - Simulation IDs MUST be stored in `simulations` table regardless of context

## Current State Analysis

### Files That Persist Simulations (CLI Path)

| File | Role |
|------|------|
| `cli/execution/runner.py` | `SimulationRunner` - main execution loop |
| `cli/execution/persistence.py` | `PersistenceManager` - wraps persistence calls |
| `cli/commands/run.py` | `_persist_simulation_metadata()`, `_persist_day_data()` |
| `persistence/event_writer.py` | `write_events_batch()` - writes to `simulation_events` |
| `persistence/connection.py` | `DatabaseManager` - creates tables |

### Files That Run Simulations (Experiment Path)

| File | Role |
|------|------|
| `experiments/runner/optimization.py` | `_run_simulation()` - unified simulation execution |
| `experiments/persistence/repository.py` | `ExperimentRepository` - separate schema |

### The Gap

`_run_simulation()` in `optimization.py` (lines 561-582) stores events like this:

```python
event = EventRecord(
    event_type="simulation_run",
    event_data={
        "simulation_id": sim_id,
        "events": all_events,  # ← JSON blob, NOT in simulation_events table!
    },
)
self._repository.save_event(event)  # ← Goes to experiment_events table
```

This bypasses the standard persistence path entirely.

## Solution Design

Introduce a `SimulationPersistenceProvider` protocol that both paths MUST use:

```
┌──────────────────────────────────────────────────────────────────────┐
│                  SimulationPersistenceProvider Protocol              │
│  persist_simulation_start(sim_id, config)                            │
│  persist_tick_events(sim_id, tick, events)                           │
│  persist_simulation_complete(sim_id, metrics)                        │
└───────────────────────────┬──────────────────────────────────────────┘
                            │
            ┌───────────────┴───────────────┐
            │                               │
            ▼                               ▼
┌───────────────────────┐       ┌───────────────────────┐
│ StandardSimulation    │       │ (Future: other        │
│ PersistenceProvider   │       │  implementations)     │
│                       │       │                       │
│ Uses:                 │       │                       │
│ - write_events_batch()│       │                       │
│ - simulations table   │       │                       │
│ - simulation_events   │       │                       │
└───────────────────────┘       └───────────────────────┘
            │
            │ Used by BOTH:
            │
    ┌───────┴───────┐
    │               │
    ▼               ▼
┌─────────┐    ┌─────────────────┐
│ CLI     │    │ Experiment      │
│ Runner  │    │ Runner          │
└─────────┘    └─────────────────┘
```

### Key Design Decisions

1. **Protocol-Based Abstraction**: Following Pattern 1 (StateProvider) and existing ConfigBuilder patterns, use a Protocol to define the interface

2. **Single Implementation**: `StandardSimulationPersistenceProvider` wraps existing persistence infrastructure (`DatabaseManager`, `write_events_batch`, etc.)

3. **Optional Persistence**: Both CLI and experiments can optionally enable persistence (via `--persist` flag or `persist_bootstrap` config)

4. **Experiment Context Linking**: When persisting from experiments, also store `experiment_run_id` and `iteration` in simulation metadata for cross-referencing

5. **No Breaking Changes**: Existing `ExperimentRepository` continues to work for experiment-level data; this only adds simulation-level persistence

## Phase Overview

| Phase | Description | TDD Focus | Estimated Tests |
|-------|-------------|-----------|-----------------|
| 1 | Define `SimulationPersistenceProvider` protocol and implementation | Protocol contract, basic persistence | 8 tests |
| 2 | Integrate into experiment runner | Experiments persist to standard tables | 6 tests |
| 3 | Verify replay identity | End-to-end replay from experiment simulations | 4 tests |
| 4 | Documentation and cleanup | Update docs, add invariant | - |

## Phase 1: SimulationPersistenceProvider Protocol

**Goal**: Define the protocol and create `StandardSimulationPersistenceProvider` that wraps existing persistence infrastructure.

### Deliverables

1. `api/payment_simulator/persistence/simulation_persistence_provider.py` - Protocol and implementation
2. `api/tests/unit/test_simulation_persistence_provider.py` - Unit tests

### TDD Approach

1. Write failing tests for protocol methods
2. Implement `StandardSimulationPersistenceProvider` using existing `write_events_batch()`, `DatabaseManager`
3. Refactor for clarity and type safety

### Success Criteria

- [ ] Protocol defines `persist_simulation_start()`, `persist_tick_events()`, `persist_simulation_complete()`
- [ ] Implementation writes to `simulations` and `simulation_events` tables
- [ ] All unit tests pass
- [ ] Type checking passes

## Phase 2: Integrate into Experiment Runner

**Goal**: Modify `_run_simulation()` to use `SimulationPersistenceProvider` instead of storing JSON blobs.

### Deliverables

1. Modified `api/payment_simulator/experiments/runner/optimization.py`
2. `api/tests/integration/test_experiment_simulation_persistence.py` - Integration tests

### TDD Approach

1. Write failing tests that verify experiments persist to `simulation_events` table
2. Modify `_run_simulation()` to optionally use `SimulationPersistenceProvider`
3. Ensure backward compatibility (experiments without `--persist-bootstrap` don't require DB)

### Success Criteria

- [ ] Experiments with `--persist-bootstrap` write to `simulations` table
- [ ] Experiments with `--persist-bootstrap` write to `simulation_events` table
- [ ] Simulation IDs from experiments are discoverable via `payment-sim db list`
- [ ] Backward compatible: experiments without persistence flag still work

## Phase 3: Verify Replay Identity

**Goal**: Ensure `payment-sim replay --simulation-id <exp-sim-id> --verbose` works identically to original run.

### Deliverables

1. `api/tests/integration/test_experiment_replay_identity.py` - Gold standard tests
2. Verification script

### TDD Approach

1. Write test that runs experiment with `--persist-bootstrap`
2. Extract simulation ID from experiment
3. Run `payment-sim replay --simulation-id <id> --verbose`
4. Compare output to what would be produced by `payment-sim run`

### Success Criteria

- [ ] Replay command finds simulation from experiment database
- [ ] Verbose output matches expected format
- [ ] Events are complete (no missing fields)
- [ ] All replay identity tests pass

## Phase 4: Documentation and Cleanup

**Goal**: Update documentation, add INV-11, clean up any remaining issues.

### Deliverables

1. Update `docs/reference/patterns-and-conventions.md` with INV-11
2. Update `CLAUDE.md` with unified persistence notes
3. Update `docs/reference/architecture/09-persistence-layer.md`

### Success Criteria

- [ ] INV-11 documented in patterns-and-conventions.md
- [ ] All relevant documentation updated
- [ ] Work notes complete

## Testing Strategy

### Unit Tests

- **Protocol contract**: Verify interface methods exist and have correct signatures
- **Persistence operations**: Verify writes go to correct tables
- **Event transformation**: Verify events are correctly formatted

### Integration Tests

- **Experiment persistence**: Run experiment, verify simulation tables populated
- **Cross-context queries**: Query simulations from experiment DB using standard queries
- **Full lifecycle**: Experiment → persist → replay → verify output

### Identity/Invariant Tests

- **INV-5 (Replay Identity)**: Compare replay output to run output
- **INV-11 (Persistence Identity)**: Compare records from CLI vs experiment paths

## Documentation Updates

After implementation is complete, update the following:

- [ ] `docs/reference/patterns-and-conventions.md` - Add INV-11: Simulation Persistence Identity
- [ ] `docs/reference/architecture/09-persistence-layer.md` - Add experiment integration section
- [ ] `CLAUDE.md` - Update unified database architecture section
- [ ] `docs/reference/cli/commands/replay.md` - Note support for experiment simulations

## Progress Tracking

| Phase | Status | Notes |
|-------|--------|-------|
| Phase 1 | ✅ Complete | Protocol and implementation |
| Phase 2 | ✅ Complete | Experiment runner integration |
| Phase 3 | ✅ Complete | Replay identity verification |
| Phase 4 | ✅ Complete | Config format fix (store YAML, not FFI) |
| Phase 5 | **In Progress** | Primary simulation persistence by default |

---

## Phase 5: Primary Simulation Persistence by Default

**Goal**: Ensure all "primary" simulations in experiments persist by default, while bootstrap sample simulations only persist with `--persist-bootstrap`.

### Problem Statement

Current behavior is incorrect:

```
Current:
┌─────────────────────────────────────────────────────────────────────┐
│ Deterministic Mode                                                  │
│ - _evaluate_policies() calls _run_simulation_with_events()          │
│ - persist=False (hardcoded) ❌                                      │
│ - Primary simulation NOT persisted                                  │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│ Bootstrap Mode                                                      │
│ - _run_initial_simulation() calls _run_simulation(persist=flag)     │
│ - Only "init" simulation persists with --persist-bootstrap          │
│ - Primary iteration simulations NOT persisted ❌                    │
└─────────────────────────────────────────────────────────────────────┘
```

Expected behavior per user specification:

```
Expected:
┌─────────────────────────────────────────────────────────────────────┐
│ ALL Modes - Primary Simulations                                     │
│ - The main scenario simulation each iteration                       │
│ - Should persist BY DEFAULT (when repository is present)            │
│ - Enables replay with: payment-sim replay -s <sim-id> --verbose     │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│ Bootstrap Mode - Bootstrap Sample Simulations                       │
│ - Resampled transaction simulations for policy comparison           │
│ - Should ONLY persist with --persist-bootstrap flag                 │
│ - Potentially hundreds per experiment (expensive to persist)        │
└─────────────────────────────────────────────────────────────────────┘
```

### Simulation Classification

| Method | Purpose | Type | Should Persist |
|--------|---------|------|----------------|
| `_evaluate_policies()` → `_run_simulation_with_events()` | Main iteration simulation | **Primary** | By default ✓ |
| `_run_initial_simulation()` | Initial simulation for bootstrap | **Primary** | By default ✓ |
| `_run_single_simulation()` | Bootstrap sample comparison | Bootstrap sample | Only with flag |
| `_evaluate_single_agent_deterministic()` → `_run_simulation()` | Policy comparison | Bootstrap sample | Only with flag |
| `_evaluate_policy_on_samples()` → `_run_single_simulation()` | Policy comparison | Bootstrap sample | Only with flag |

### Design

Add a new parameter to distinguish primary vs sample simulations:

```python
def _run_simulation(
    self,
    seed: int,
    *,
    purpose: str = "eval",
    iteration: int | None = None,
    sample_idx: int | None = None,
    persist: bool | None = None,  # None = use default based on is_primary
    is_primary: bool = True,  # NEW: Primary simulations persist by default
) -> SimulationResult:
    """Run a simulation.

    Args:
        ...
        is_primary: If True, this is a primary simulation (main scenario run)
                   that should persist by default when repository is present.
                   If False, this is a bootstrap sample that only persists
                   when persist=True explicitly (via --persist-bootstrap).
    """
    # Determine if we should persist
    if persist is not None:
        should_persist = persist
    elif is_primary:
        # Primary simulations persist by default when repository exists
        should_persist = self._repository is not None
    else:
        # Bootstrap samples only persist with explicit flag
        should_persist = self._persist_bootstrap
```

### Deliverables

1. Modified `api/payment_simulator/experiments/runner/optimization.py`:
   - Add `is_primary` parameter to `_run_simulation()`
   - Update all call sites with correct classification

2. `api/tests/integration/test_primary_simulation_persistence.py`:
   - Tests for deterministic mode primary persistence
   - Tests for bootstrap mode primary persistence
   - Tests that bootstrap samples DON'T persist without flag

### TDD Test Plan

#### Test 1: Deterministic Mode Primary Simulation Persists by Default

```python
def test_deterministic_mode_primary_simulation_persists_by_default():
    """Primary simulation in deterministic mode should persist without any flag."""
    # Create experiment with deterministic mode, repository, NO persist flag
    loop = OptimizationLoop(
        config=deterministic_config,
        repository=experiment_repository,
        persist_bootstrap=False,  # Explicitly False
    )

    # Run one iteration (which runs _evaluate_policies)
    await loop._run_iteration()

    # Query database - should find the primary simulation
    simulations = query_simulations(repository)
    assert len(simulations) >= 1, "Primary simulation should persist by default"

    # Verify it has correct format for replay
    config = json.loads(simulations[0].config_json)
    assert "agents" in config, "Config should be YAML format"
```

#### Test 2: Bootstrap Mode Primary Simulation Persists by Default

```python
def test_bootstrap_mode_primary_simulation_persists_by_default():
    """Primary simulation in bootstrap mode should persist without flag."""
    loop = OptimizationLoop(
        config=bootstrap_config,
        repository=experiment_repository,
        persist_bootstrap=False,
    )

    # Run one iteration
    await loop._run_iteration()

    # Should find primary simulations (init + iteration primary)
    simulations = query_simulations(repository)
    assert len(simulations) >= 1, "Primary simulation should persist"
```

#### Test 3: Bootstrap Samples Don't Persist Without Flag

```python
def test_bootstrap_samples_dont_persist_without_flag():
    """Bootstrap sample simulations should NOT persist without --persist-bootstrap."""
    loop = OptimizationLoop(
        config=bootstrap_config,
        repository=experiment_repository,
        persist_bootstrap=False,
    )

    # Run iteration with policy evaluation (triggers bootstrap samples)
    await loop._run_iteration()

    # Count simulations - should only have primary, not N bootstrap samples
    simulations = query_simulations(repository)
    # If num_samples=50, we should NOT have 50+ simulations
    assert len(simulations) < 10, "Bootstrap samples should not persist"
```

#### Test 4: Bootstrap Samples Persist With Flag

```python
def test_bootstrap_samples_persist_with_flag():
    """Bootstrap sample simulations should persist with --persist-bootstrap."""
    loop = OptimizationLoop(
        config=bootstrap_config,
        repository=experiment_repository,
        persist_bootstrap=True,  # Flag enabled
    )

    # Run iteration with policy evaluation
    await loop._run_iteration()

    # Should have primary + bootstrap samples
    simulations = query_simulations(repository)
    num_samples = bootstrap_config.evaluation.num_samples
    assert len(simulations) >= num_samples, "Bootstrap samples should persist with flag"
```

#### Test 5: Replay Works for Primary Simulation

```python
def test_replay_works_for_primary_simulation():
    """Primary simulations should be replayable with verbose output."""
    loop = OptimizationLoop(
        config=deterministic_config,
        repository=experiment_repository,
    )

    await loop._run_iteration()

    # Get simulation ID
    simulations = query_simulations(repository)
    sim_id = simulations[0].simulation_id

    # Replay should work
    output = run_replay(sim_id, verbose=True)
    assert "Tick 0" in output, "Replay should produce verbose output"
```

### Call Site Updates

| Location | Current | Change To |
|----------|---------|-----------|
| `_run_simulation_with_events()` line 1324 | `persist=False` | `is_primary=False` (bootstrap samples) |
| `_evaluate_policies()` | Calls `_run_simulation_with_events()` | Add wrapper call with `is_primary=True` for primary |
| `_run_initial_simulation()` line 1199 | `persist=self._persist_bootstrap` | `is_primary=True` |
| `_evaluate_single_agent_deterministic()` line 1661 | `persist=False` | `is_primary=False` |

### Implementation Order (Strict TDD)

1. **RED**: Write failing test `test_deterministic_mode_primary_simulation_persists_by_default`
2. **GREEN**: Add `is_primary` parameter, update `_evaluate_policies()` to persist primary
3. **REFACTOR**: Clean up persistence logic

4. **RED**: Write failing test `test_bootstrap_samples_dont_persist_without_flag`
5. **GREEN**: Ensure `_run_simulation_with_events()` passes `is_primary=False`
6. **REFACTOR**: Verify no regressions

7. **RED**: Write failing test `test_bootstrap_samples_persist_with_flag`
8. **GREEN**: Ensure `persist_bootstrap` flag controls sample persistence
9. **REFACTOR**: Clean up

10. **RED**: Write failing test `test_replay_works_for_primary_simulation`
11. **GREEN**: Should already work if previous tests pass
12. **REFACTOR**: Final cleanup

### Success Criteria

- [ ] Deterministic mode: Primary simulation persists by default (no flag needed)
- [ ] Bootstrap mode: Primary iteration simulation persists by default
- [ ] Bootstrap samples only persist with `--persist-bootstrap` flag
- [ ] All persisted simulations can be replayed with `payment-sim replay -s <id> --verbose`
- [ ] All tests pass
- [ ] Type checking passes
- [ ] No regressions in existing experiment functionality

## Appendix: Existing Patterns to Follow

### ScenarioConfigBuilder (INV-10)

```python
@runtime_checkable
class ScenarioConfigBuilder(Protocol):
    def extract_agent_config(self, agent_id: str) -> AgentScenarioConfig: ...

class StandardScenarioConfigBuilder:
    # Single implementation used by ALL code paths
```

### StateProvider (INV-5)

```python
class StateProvider(Protocol):
    def get_agent_balance(self, agent_id: str) -> int: ...
    def get_events_for_tick(self, tick: int) -> list[dict]: ...

# Two implementations: OrchestratorStateProvider, DatabaseStateProvider
# Same display function works for both
```

### SimulationPersistenceProvider (NEW - INV-11)

Following the same pattern:

```python
@runtime_checkable
class SimulationPersistenceProvider(Protocol):
    def persist_simulation_start(self, sim_id: str, config: dict) -> None: ...
    def persist_tick_events(self, sim_id: str, tick: int, events: list[dict]) -> None: ...
    def persist_simulation_complete(self, sim_id: str, metrics: dict) -> None: ...

class StandardSimulationPersistenceProvider:
    # Single implementation used by ALL code paths (CLI and experiments)
```
