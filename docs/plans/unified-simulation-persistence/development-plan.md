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
| Phase 1 | Pending | Protocol and implementation |
| Phase 2 | Pending | Experiment runner integration |
| Phase 3 | Pending | Replay identity verification |
| Phase 4 | Pending | Documentation |

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
