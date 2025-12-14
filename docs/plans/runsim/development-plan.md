# Development Plan: Consolidate Simulation Execution Methods

**Feature Request**: `docs/request/run-sim.md`
**Target File**: `api/payment_simulator/experiments/runner/optimization.py`
**Start Date**: 2025-12-14
**Branch**: `claude/implement-run-sim-feature-HinjI`

## Summary

Consolidate `_run_initial_simulation()` and `_run_simulation_with_events()` into a single `_run_simulation()` method. These methods do the same thing (run a simulation) but evolved separately, creating unnecessary code duplication.

## Critical Invariants to Respect

### 1. Money is ALWAYS i64 (Integer Cents) - INV-1
All costs, amounts, and balances MUST be `int` representing cents. Never use floats for money calculations.

### 2. Determinism is Sacred - INV-2
Same seed + same inputs = same outputs. All RNG must be seeded and reproducible.

### 3. Replay Identity - INV-3
Simulation output must be reproducible via replay. Events persisted to database must contain all fields needed for replay without reconstruction.

### 4. FFI Boundary is Minimal - INV-4
Pass only primitives, strings, and simple dicts/lists across FFI. Validate all inputs at boundary.

### 5. Strict Python Typing - INV-5
All functions must have complete type annotations. Use modern syntax (`str | None`, `list[str]`).

## Current State Analysis

### `_run_initial_simulation()` (Lines 876-984)
- Purpose: Bootstrap mode initial data collection
- Generates simulation ID and logs to terminal
- Captures ALL events from simulation
- Builds TransactionHistoryCollector for bootstrap sampling
- Persists to database if `--persist-bootstrap` flag is set
- Returns: `InitialSimulationResult`

### `_run_simulation_with_events()` (Lines 1057-1160)
- Purpose: Policy evaluation with enriched metrics
- Captures events as `BootstrapEvent` objects
- Extracts cost breakdown (delay, overdraft, deadline, collateral)
- Calculates settlement rate and average delay
- Returns: `EnrichedEvaluationResult`

### Common Core (Identical in Both)
1. Build config with `_build_simulation_config()`
2. Set RNG seed
3. Create `Orchestrator.new(ffi_config)`
4. Loop `for tick in range(total_ticks): orch.tick()`
5. Capture events with `orch.get_tick_events(tick)`
6. Extract costs with `orch.get_agent_accumulated_costs(agent_id)`

## Proposed Design

### New `SimulationResult` Dataclass

```python
@dataclass(frozen=True)
class SimulationResult:
    """Complete simulation output. Callers use what they need.

    All costs are integer cents (INV-1).
    """
    seed: int
    simulation_id: str
    total_cost: int
    per_agent_costs: dict[str, int]
    events: tuple[dict[str, Any], ...]
    cost_breakdown: CostBreakdown
    settlement_rate: float
    avg_delay: float
```

### New `_run_simulation()` Method

Single method that:
1. Generates simulation ID
2. Logs to terminal (if verbose)
3. Runs simulation with full event capture
4. Extracts ALL costs and metrics
5. Persists if `--persist-bootstrap` flag is set
6. Returns `SimulationResult`

### Caller Transformations

- `_run_initial_simulation()` → calls `_run_simulation()` + builds `TransactionHistoryCollector`
- `_run_simulation_with_events()` → calls `_run_simulation()` + wraps events in `BootstrapEvent`

---

## Development Phases

### Phase 1: Create SimulationResult Dataclass (TDD)
**Goal**: Define the unified result type with tests

Tasks:
1. Write tests for `SimulationResult` dataclass
2. Define `SimulationResult` in `bootstrap_support.py`
3. Ensure all fields follow INV-1 (integer cents)
4. Add docstrings with examples

**Success Criteria**:
- All unit tests pass
- Type annotations complete
- mypy and ruff pass

### Phase 2: Implement `_run_simulation()` Method (TDD)
**Goal**: Create the unified simulation execution method

Tasks:
1. Write integration tests for `_run_simulation()`
2. Implement method with full event capture
3. Add simulation ID generation and logging
4. Add persistence support (conditional on flag)
5. Extract complete cost breakdown and metrics

**Success Criteria**:
- Integration tests pass
- Simulation ID logged to terminal
- Events persisted when flag is set
- Determinism verified (same seed = same output)

### Phase 3: Refactor `_run_initial_simulation()`
**Goal**: Refactor to use `_run_simulation()` as core

Tasks:
1. Update `_run_initial_simulation()` to call `_run_simulation()`
2. Transform `SimulationResult` to `InitialSimulationResult`
3. Keep TransactionHistoryCollector logic
4. Ensure existing tests pass

**Success Criteria**:
- All existing tests pass
- No behavior change for callers
- Code duplication removed

### Phase 4: Refactor `_run_simulation_with_events()`
**Goal**: Refactor to use `_run_simulation()` as core

Tasks:
1. Update `_run_simulation_with_events()` to call `_run_simulation()`
2. Transform `SimulationResult` to `EnrichedEvaluationResult`
3. Ensure event wrapping (BootstrapEvent) preserved
4. Verify existing tests pass

**Success Criteria**:
- All existing tests pass
- No behavior change for callers
- Code duplication removed

### Phase 5: Integration Tests and Documentation
**Goal**: Verify end-to-end behavior and update docs

Tasks:
1. Run full experiment integration tests
2. Verify replay identity invariant
3. Test `--persist-bootstrap` flag behavior
4. Update reference documentation
5. Clean up any remaining duplication

**Success Criteria**:
- All integration tests pass
- Replay identity verified
- Documentation updated
- ~120 lines of duplication removed

---

## Testing Strategy

### Unit Tests (Phase 1-2)
- `test_simulation_result_fields()` - all fields typed correctly
- `test_simulation_result_frozen()` - immutability verified
- `test_cost_breakdown_integer_cents()` - INV-1 enforced

### Integration Tests (Phase 2-4)
- `test_run_simulation_determinism()` - same seed = same output
- `test_run_simulation_captures_all_events()` - event completeness
- `test_run_simulation_logs_id()` - terminal output includes ID
- `test_run_simulation_persists_when_flag_set()` - persistence works
- `test_initial_simulation_uses_run_simulation()` - refactor works
- `test_simulation_with_events_uses_run_simulation()` - refactor works

### E2E Tests (Phase 5)
- `test_full_experiment_with_persist_bootstrap()` - end-to-end
- `test_replay_identity_for_bootstrap_simulations()` - replay works

---

## File Changes Summary

| File | Change |
|------|--------|
| `api/payment_simulator/experiments/runner/optimization.py` | Add `_run_simulation()`, refactor two methods |
| `api/payment_simulator/experiments/runner/bootstrap_support.py` | Add `SimulationResult` dataclass |
| `api/tests/experiments/runner/test_simulation_result.py` | New unit tests |
| `api/tests/experiments/runner/test_run_simulation.py` | New integration tests |
| `docs/reference/experiments/runner.md` | Update documentation |

---

## Progress Tracking

| Phase | Status | Notes |
|-------|--------|-------|
| Phase 1 | Pending | SimulationResult dataclass |
| Phase 2 | Pending | _run_simulation() implementation |
| Phase 3 | Pending | Refactor _run_initial_simulation() |
| Phase 4 | Pending | Refactor _run_simulation_with_events() |
| Phase 5 | Pending | Integration tests and docs |

---

## Reference Documents

- Feature Request: `docs/request/run-sim.md`
- Patterns & Conventions: `docs/reference/patterns-and-conventions.md`
- Experiment Runner: `docs/reference/experiments/runner.md`
- Python Style Guide: `api/CLAUDE.md`
- Rust Style Guide: `simulator/CLAUDE.md`
