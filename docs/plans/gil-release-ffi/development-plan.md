# GIL-Release FFI Methods for Thread-Parallel Simulation

**Date**: 2026-02-17  
**Author**: Nash  
**Status**: ✅ Complete  
**Branch**: `feature/interactive-web-sandbox`

## Goal

Add new FFI methods to the Rust `PyOrchestrator` that release the Python GIL during simulation execution. This enables the web backend to run multiple simulations in parallel using Python threads (e.g., `ThreadPoolExecutor`), which directly improves:

1. Bootstrap evaluation latency (50 paired samples run concurrently)
2. Multi-sample day evaluation latency
3. Concurrent user experience (one user's simulation doesn't block another)

## Why This Is Safe

The Rust `Orchestrator` struct:
- Contains **no Python references** — `PyOrchestrator.inner` is a pure `RustOrchestrator`
- Uses **no `Rc`, `RefCell`, `Cell`, `UnsafeCell`, or raw pointers**
- All trait objects implement **`Send + Sync`** (`CashManagerPolicy: Send + Sync`)
- Each simulation creates its own independent `Orchestrator` instance
- `py.allow_threads()` only requires that no `Py<T>` or `&PyAny` references are held — verified: the closure only touches `self.inner` (pure Rust)

## What Changes

### Rust (simulator/src/ffi/orchestrator.rs)

Two new methods on `PyOrchestrator`:

1. **`run_and_get_total_cost(agent_id, num_ticks)`** → `i64`  
   Runs N ticks inside `py.allow_threads()`, returns one agent's total cost.  
   This is the "bootstrap fast path" — the only thing bootstrap needs is the cost integer.

2. **`run_and_get_all_costs(num_ticks)`** → `String` (JSON)  
   Runs N ticks inside `py.allow_threads()`, returns all agents' costs as a JSON string.  
   This is the "day evaluation fast path" — needed when we want costs for all agents.

Both methods:
- Validate inputs **before** releasing GIL (agent exists, num_ticks > 0)
- Run the tick loop **with GIL released** (`py.allow_threads()`)
- Return Rust-native types (i64, String) — no Python dict construction needed

### Python (web/backend/app/bootstrap_eval.py)

- Replace sequential `_run_sim()` loop with `ThreadPoolExecutor`
- Each thread creates its own `Orchestrator` and calls `run_and_get_total_cost()`
- Statistical analysis code unchanged

### Python (web/backend/app/game.py)

- Replace sequential multi-sample loop in `run_day()` with `ThreadPoolExecutor`
- Each thread creates its own `Orchestrator` and calls `run_and_get_all_costs()`

## What Does NOT Change

- **`tick()` method** — unchanged, still returns `Py<PyDict>`, still holds GIL. Used for single-step replay.
- **All existing FFI methods** — untouched. The new methods are additive.
- **All existing tests** — must continue to pass unchanged.
- **Simulation logic** — zero changes to the engine. Same tick loop, same cost model, same determinism.
- **Frontend** — no changes needed.

## Test Baselines (must remain green throughout)

| Suite | Count | Command |
|-------|-------|---------|
| Rust unit/doc tests | 105 passed, 18 ignored | `cargo test --manifest-path simulator/Cargo.toml --no-default-features` |
| Python API unit tests | 581 passed, 4 skipped | `cd api && uv run pytest tests/unit/ -v` |
| Web backend tests | 63 passed | `uv run pytest web/backend/tests/ -v --ignore=.../test_real_llm.py` |

## Phases

### Phase 1: Rust FFI Methods (RED → GREEN → REFACTOR)
See `phases/phase_1.md`

### Phase 2: Python Thread-Parallel Bootstrap (RED → GREEN → REFACTOR)
See `phases/phase_2.md`

### Phase 3: Python Thread-Parallel Day Evaluation
See `phases/phase_3.md`

### Phase 4: Full Regression Suite
See `phases/phase_4.md`

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Rust `allow_threads` panics | Very low | High | Validate all inputs before releasing GIL; map Rust errors to PyErr |
| Non-determinism under threading | Very low | Critical | Each thread creates its own Orchestrator with its own RNG — complete isolation. Add determinism test. |
| Deadlock in `allow_threads` | None | N/A | No locks in Rust engine. No Python callbacks during `allow_threads`. |
| Maturin build breaks | Low | Medium | Build + test before any Python changes |
| Performance regression on single-thread path | None | N/A | New methods are additive — existing code paths unchanged |

## Determinism Invariant

**This is the most important thing to verify.** The guarantee:

> Given identical `(config, seed)`, the simulation produces identical output regardless of which thread runs it, how many threads run simultaneously, or whether `run_and_get_total_cost()` vs `tick()` is used.

This holds because:
1. Each `Orchestrator` is an independent state machine with its own `RngManager`
2. No shared mutable state between instances
3. The tick loop is identical in both code paths
4. `py.allow_threads()` doesn't affect Rust execution — it only releases/reacquires the GIL
