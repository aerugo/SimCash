# Work Notes: Consolidate Simulation Execution Methods

## Session Log

### 2025-12-14 - Initial Setup

**Status**: Starting Phase 1

**Completed**:
1. Read feature request at `docs/request/run-sim.md`
2. Analyzed current implementation in `optimization.py`
3. Understood invariants from CLAUDE.md files
4. Created development plan at `docs/plans/runsim/development-plan.md`
5. Created directory structure for phased development

**Key Observations**:
- Two methods (`_run_initial_simulation()` and `_run_simulation_with_events()`) share ~80% identical code
- Main differences are post-processing (TransactionHistoryCollector vs BootstrapEvent wrapping)
- Both already support event capture and cost extraction
- VerboseLogger already has `log_simulation_start()` method ready to use
- `--persist-bootstrap` flag already exists but persistence is only in `_run_initial_simulation()`

**Invariants to Track**:
- INV-1: Money as integer cents (checked - all costs are `int`)
- INV-2: Determinism (seed is passed through properly)
- INV-3: Replay identity (events must be complete for replay)
- INV-4: FFI boundary (already minimal)
- INV-5: Strict typing (must maintain)

**Files Identified for Changes**:
- `api/payment_simulator/experiments/runner/optimization.py` (main changes)
- `api/payment_simulator/experiments/runner/bootstrap_support.py` (add SimulationResult)
- `api/tests/experiments/runner/` (new tests)

**Next Steps**:
1. Create Phase 1 detailed plan
2. Write unit tests for SimulationResult dataclass (TDD)
3. Implement SimulationResult in bootstrap_support.py

---

## Phase Progress

### Phase 1: SimulationResult Dataclass - COMPLETED ✓
- [x] Write tests first (TDD) - 11 tests in `test_simulation_result.py`
- [x] Define SimulationResult dataclass in `bootstrap_support.py`
- [x] Ensure mypy/ruff pass - both pass clean
- [x] Document with examples - docstring includes full example

**Files Changed:**
- `api/payment_simulator/experiments/runner/bootstrap_support.py` - Added SimulationResult
- `api/tests/experiments/runner/test_simulation_result.py` - New test file (11 tests)

### Phase 2: _run_simulation() Method - COMPLETED ✓
- [x] Write integration tests - 16 tests in `test_run_simulation.py`
- [x] Implement method in `optimization.py` lines 406-541
- [x] Add simulation ID logging via VerboseLogger.log_simulation_start()
- [x] Add persistence support with persist parameter override

**Files Changed:**
- `api/payment_simulator/experiments/runner/optimization.py` - Added `_run_simulation()` method
- `api/tests/experiments/runner/test_run_simulation.py` - New test file (16 tests)

**Key Implementation Details:**
- Method signature: `_run_simulation(seed, purpose, *, iteration=None, sample_idx=None, persist=None)`
- Returns `SimulationResult` with all data (events, costs, metrics)
- Supports optional persistence override via `persist` parameter
- Logs to terminal when VerboseLogger is configured

### Phase 3: Refactor _run_initial_simulation() - COMPLETED ✓
- [x] Update to call _run_simulation()
- [x] Verify existing tests pass - 7 passed, 2 skipped (pre-existing)
- [x] mypy passes clean

**Files Changed:**
- `api/payment_simulator/experiments/runner/optimization.py` - Refactored `_run_initial_simulation()` to use `_run_simulation()` internally

**Key Changes:**
- Method reduced from ~109 lines to ~30 lines
- Delegates simulation execution to `_run_simulation(seed=master_seed, purpose="init", ...)`
- Still builds TransactionHistoryCollector from result.events
- Still formats events for LLM context via `_format_events_for_llm()`

### Phase 4: Refactor _run_simulation_with_events() - COMPLETED ✓
- [x] Update to call _run_simulation()
- [x] Verify existing tests pass - 28 passed, 1 skipped (same as baseline)
- [x] mypy passes clean

**Files Changed:**
- `api/payment_simulator/experiments/runner/optimization.py` - Refactored `_run_simulation_with_events()` to use `_run_simulation()` internally

**Key Changes:**
- Method reduced from ~105 lines to ~44 lines
- Delegates simulation execution to `_run_simulation(seed=seed, purpose="bootstrap", sample_idx=sample_idx, persist=False)`
- Transforms raw events from `tuple[dict[str, Any], ...]` to `tuple[BootstrapEvent, ...]`
- Reuses cost_breakdown directly from SimulationResult

### Phase 5: Integration & Docs - COMPLETED ✓
- [x] Run full test suite - 280 passed, 14 failed (all failures pre-existing)
- [x] mypy passes clean
- [x] All tests related to this feature pass:
  - `test_run_simulation.py` - 16 passed
  - `test_simulation_result.py` - 11 passed
  - Initial simulation tests - 7 passed
  - Bootstrap/enriched tests - 28 passed

**Pre-existing test failures (not regressions):**
- 3 castro module failures (missing external `castro.state_provider` module)
- 7 missing scenario file failures (tests use `test_scenario.yaml` that doesn't exist)
- 1 ExperimentLLMClient missing (test references non-existent attribute)
- 3 verbose config failures (simulations default=True breaking old tests)

**Files Created:**
- `docs/plans/runsim/development-plan.md` - Main development plan
- `docs/plans/runsim/work_notes.md` - Progress tracking
- `docs/plans/runsim/phases/phase_1.md` - Phase 1 detailed plan
- `docs/plans/runsim/phases/phase_2.md` - Phase 2 detailed plan
- `docs/plans/runsim/phases/phase_3.md` - Phase 3 detailed plan
- `api/tests/experiments/runner/test_simulation_result.py` - 11 unit tests
- `api/tests/experiments/runner/test_run_simulation.py` - 16 integration tests

**Files Modified:**
- `api/payment_simulator/experiments/runner/bootstrap_support.py` - Added `SimulationResult` dataclass
- `api/payment_simulator/experiments/runner/optimization.py`:
  - Added `_run_simulation()` unified method (~135 lines)
  - Refactored `_run_initial_simulation()` (reduced from ~109 to ~30 lines)
  - Refactored `_run_simulation_with_events()` (reduced from ~105 to ~44 lines)

## Summary

**Lines of code impact:**
- Added: ~135 lines (unified `_run_simulation()` method)
- Removed: ~140 lines (duplicated code from refactored methods)
- Net: ~5 lines reduced, plus single source of truth for simulation execution

**Key achievements:**
1. Created ONE unified method for simulation execution (`_run_simulation()`)
2. All callers now transform `SimulationResult` to their specific needs
3. Determinism guaranteed via seed parameter
4. Persistence support via `persist` parameter override
5. Verbose logging via `VerboseLogger.log_simulation_start()`
6. All costs remain as integer cents (INV-1)
7. Events captured as immutable tuple (INV-3 replay identity)
