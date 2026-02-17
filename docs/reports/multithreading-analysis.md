# Multithreading Analysis: SimCash Web Backend

**Date**: 2026-02-17  
**Author**: Nash  
**Status**: Analysis complete, implementation not started

## Executive Summary

The SimCash web backend is **entirely single-threaded** today. All Rust simulation calls hold the Python GIL and execute sequentially. The good news: the Rust engine's internal architecture is perfectly clean for multithreading — no `Rc`, no `RefCell`, no raw pointers, all trait objects are `Send + Sync`. There are **three viable paths** to parallelism, ranging from a quick 2-hour fix to a more invasive but optimal solution.

## Current State

### What's Serial Today

1. **`Game.run_day()`** — When `num_eval_samples > 1`, runs N simulations in a `for` loop, sequentially
2. **`WebBootstrapEvaluator.evaluate()`** — Runs 2×N simulations (old + new policy on each seed) in a `for` loop
3. **`Game._run_single_sim()`** — Each simulation creates an `Orchestrator`, runs tick loop, extracts results — all synchronous, all holding GIL
4. **Concurrent user requests** — Two users triggering simulations at the same time: one blocks the other

### Why It's Single-Threaded

```
Python (async FastAPI) → PyO3 FFI → Rust Orchestrator
                           ↑
                     GIL held here
```

Every call from Python into Rust goes through PyO3, which acquires the GIL. The Rust `tick()` method signature is:

```rust
fn tick(&mut self, py: Python) -> PyResult<Py<PyDict>> {
    let result = self.inner.tick()...;  // Pure Rust — doesn't need GIL
    tick_result_to_py(py, &result)      // Converts to Python dict — needs GIL
}
```

The `py: Python` token proves GIL is held for the entire call. But looking at the implementation, only the **result conversion** at the end needs the GIL. The actual simulation work (`self.inner.tick()`) is pure Rust with zero Python interaction.

### The Rust Engine Is Already Thread-Safe

Verified by code inspection:

| Check | Result |
|-------|--------|
| `Rc<T>` usage | ❌ None found |
| `RefCell<T>` usage | ❌ None found |
| `Cell<T>` usage | ❌ None found |
| `*mut` raw pointers | ❌ None found |
| `UnsafeCell` | ❌ None found |
| `CashManagerPolicy` trait | `Send + Sync` ✅ |
| `Orchestrator` struct | All owned data, no interior mutability ✅ |
| `PyOrchestrator.inner` | Pure `RustOrchestrator`, no Python refs ✅ |

The Rust engine can safely run on any thread. The only GIL dependency is at the FFI boundary — creating Python dicts from Rust results.

## Three Paths to Parallelism

### Option A: `ProcessPoolExecutor` (Quick Win, No Rust Changes)

**Effort**: ~2-3 hours  
**Speedup**: Near-linear for bootstrap (limited by CPU cores)  
**Constraint**: Does NOT require modifying files outside `web/`

The idea: offload entire simulation runs to worker processes. Each process has its own GIL, so they truly run in parallel.

```python
# web/backend/app/bootstrap_eval.py
import concurrent.futures
import multiprocessing

class WebBootstrapEvaluator:
    def __init__(self, num_samples=10, cv_threshold=0.5, max_workers=None):
        self.max_workers = max_workers or min(num_samples, multiprocessing.cpu_count())
    
    def evaluate(self, raw_yaml, agent_id, old_policy, new_policy, base_seed, other_policies=None):
        seeds = [base_seed + i * 1000 for i in range(self.num_samples)]
        
        with concurrent.futures.ProcessPoolExecutor(max_workers=self.max_workers) as pool:
            # Submit all old-policy and new-policy runs in parallel
            old_futures = [pool.submit(_run_sim_standalone, raw_yaml, agent_id, old_policy, s, other_policies) for s in seeds]
            new_futures = [pool.submit(_run_sim_standalone, raw_yaml, agent_id, new_policy, s, other_policies) for s in seeds]
            
            old_costs = [f.result() for f in old_futures]
            new_costs = [f.result() for f in new_futures]
        
        # ... rest of evaluation logic unchanged

def _run_sim_standalone(raw_yaml, agent_id, policy, seed, other_policies):
    """Top-level function (must be picklable for ProcessPoolExecutor)."""
    # Each worker process imports and runs independently
    import copy, json
    from payment_simulator._core import Orchestrator
    from payment_simulator.config.schemas import SimulationConfig
    
    scenario = copy.deepcopy(raw_yaml)
    # ... same setup as current _run_sim ...
    orch = Orchestrator.new(ffi_config)
    for _ in range(ticks):
        orch.tick()
    ac = orch.get_agent_accumulated_costs(agent_id)
    return int(ac.get("total_cost", 0))
```

**Pros**:
- No Rust changes needed (stays within `web/` directory)
- True parallelism — each process has its own GIL
- Works today with Python 3.13

**Cons**:
- Process startup overhead (~50-100ms per pool creation). Mitigate by keeping a persistent pool.
- Pickling overhead for `raw_yaml` dict (negligible — it's small)
- Memory overhead: each worker process loads the Rust extension (~30MB per process)
- On Cloud Run with 1 vCPU, you only have 1 core — parallelism doesn't help. Need `--cpu 2` or higher.

**Expected performance (2 vCPU Cloud Run)**:

| Scenario | Current (serial) | With ProcessPool (2 workers) |
|----------|-----------------|------------------------------|
| Bootstrap-50, 2 banks | ~200ms | ~110ms |
| Bootstrap-50, 5 banks | ~1s | ~550ms |

### Option B: `py.allow_threads()` in Rust FFI (Best Performance, Requires Core Changes)

**Effort**: ~4-6 hours  
**Speedup**: Near-linear with threads (lower overhead than processes)  
**Constraint**: Requires modifying `simulator/src/ffi/orchestrator.rs` (outside `web/`)

The idea: release the GIL during the pure-Rust computation, only reacquiring it for Python object creation.

```rust
// simulator/src/ffi/orchestrator.rs

/// Run a complete simulation and return total cost for an agent.
/// Releases GIL during Rust execution for parallelism.
fn run_to_completion_cost(&mut self, py: Python, agent_id: String, num_ticks: usize) -> PyResult<i64> {
    // Release GIL — other Python threads can run while Rust computes
    let cost = py.allow_threads(|| {
        for _ in 0..num_ticks {
            self.inner.tick().expect("tick failed");
        }
        self.inner.accumulated_costs()
            .get(&agent_id)
            .map(|c| c.total_cost)
            .unwrap_or(0)
    });
    Ok(cost)
}
```

Then on the Python side, use `ThreadPoolExecutor`:

```python
import concurrent.futures

class WebBootstrapEvaluator:
    def evaluate(self, ...):
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
            old_futures = [pool.submit(self._run_sim_gil_free, ...) for s in seeds]
            new_futures = [pool.submit(self._run_sim_gil_free, ...) for s in seeds]
            # ...
    
    def _run_sim_gil_free(self, raw_yaml, agent_id, policy, seed, other_policies):
        # Setup (needs GIL — but fast)
        orch = Orchestrator.new(ffi_config)
        # This call releases GIL internally
        cost = orch.run_to_completion_cost(agent_id, ticks)
        return cost
```

**Pros**:
- Threads are lightweight (~8KB stack vs ~30MB per process)
- No pickling overhead
- GIL released during the expensive part (simulation), held only for fast setup/teardown
- Works with a single vCPU if there are I/O waits interleaved (and definitely with 2+ vCPUs)

**Cons**:
- Requires modifying core Rust FFI code (violates "don't touch outside `web/`" rule)
- Need to ensure `Orchestrator` doesn't hold any PyO3 references during `allow_threads` (verified: it doesn't)
- `&mut self` means one thread per Orchestrator (but each bootstrap sample creates its own — so this is fine)
- New FFI method needs tests

**Detailed Rust changes needed**:

```rust
// Add to simulator/src/ffi/orchestrator.rs, inside #[pymethods] impl PyOrchestrator

/// Run N ticks and return agent's total cost.
/// Releases the GIL during simulation for thread-level parallelism.
fn run_and_get_cost(&mut self, py: Python, agent_id: String, num_ticks: usize) -> PyResult<i64> {
    // Validate agent exists before releasing GIL
    if !self.inner.agent_ids().contains(&agent_id) {
        return Err(PyErr::new::<pyo3::exceptions::PyValueError, _>(
            format!("Unknown agent: {}", agent_id)
        ));
    }
    
    py.allow_threads(|| {
        for _ in 0..num_ticks {
            self.inner.tick().map_err(|e| format!("{}", e))
        }
        .map(|_| {
            self.inner.get_accumulated_costs(&agent_id)
                .map(|c| c.total_cost())
                .unwrap_or(0)
        })
    })
    .map_err(|e| PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(e))
}

/// Run N ticks and return full results as JSON string.
/// GIL-free execution with JSON serialization in Rust.
fn run_and_get_results_json(&mut self, py: Python, num_ticks: usize) -> PyResult<String> {
    py.allow_threads(|| {
        for _ in 0..num_ticks {
            self.inner.tick()?;
        }
        // Serialize to JSON in Rust — no Python objects needed
        serde_json::to_string(&self.inner.get_summary())
            .map_err(|e| format!("{}", e))
    })
    .map_err(|e| PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(e))
}
```

**Key insight**: The current `tick()` method returns a `Py<PyDict>` (Python object), which forces GIL retention. A new method that returns a Rust-native type (i64 or JSON string) can release the GIL for the entire simulation.

### Option C: Free-Threaded Python 3.13t (Future-Proof, Experimental)

**Effort**: ~1-2 hours to try, unknown debugging time  
**Speedup**: True thread-level parallelism without any Rust changes  
**Constraint**: Experimental; PyO3 support is still maturing

Python 3.13 introduced an experimental free-threaded build (`python3.13t`) that disables the GIL entirely. PyO3 has initial support for this.

```bash
# Install free-threaded Python
uv python install 3.13t

# Rebuild the Rust extension for free-threaded Python
cd api && maturin develop --release
```

Then standard `ThreadPoolExecutor` works without any `py.allow_threads()`:

```python
with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
    futures = [pool.submit(self._run_sim, ...) for s in seeds]
    results = [f.result() for f in futures]
```

**Pros**:
- No Rust changes needed
- No pickling overhead
- Threads are cheap
- The "correct" long-term solution

**Cons**:
- **Experimental** — pydantic-ai, FastAPI, uvicorn may not be compatible yet
- PyO3 free-threaded support requires `Py_GIL_DISABLED` feature flag and careful testing
- Performance may actually be worse for single-threaded workloads (GIL removal adds per-object locking overhead)
- Not recommended for production in 2026 yet
- Docker base image would need `python:3.13t-slim` (if it exists) or custom build

## Recommendation

### For Cloud Run Deployment (Now)

**Do Option A (ProcessPoolExecutor)**. It's the only option that stays within `web/` and works today.

Implementation plan:
1. Create a persistent `ProcessPoolExecutor` in `bootstrap_eval.py` (module-level, lazy-init)
2. Move `_run_sim` to a top-level function (picklable)
3. Submit all 2×N simulation runs as futures
4. Collect results, compute statistics (unchanged)
5. Also parallelize `Game.run_day()` when `num_eval_samples > 1`

Set Cloud Run to `--cpu 2` for meaningful parallelism (~$5-10/month extra).

### For Maximum Performance (Later)

**Do Option B (`py.allow_threads()`)**. If Hugi approves core Rust changes:

1. Add `run_and_get_cost()` method to `PyOrchestrator` — 30 lines of Rust
2. Switch `WebBootstrapEvaluator` to `ThreadPoolExecutor` using the new method
3. 10× less memory overhead than processes, lower latency

### Don't Do Yet

**Option C (free-threaded Python)** — wait for the ecosystem to stabilize. Revisit in late 2026/2027.

## Impact on Concurrent Users

With Option A implemented, here's how multiple users interact:

| Situation | Before (serial) | After (ProcessPool, 2 vCPU) |
|-----------|-----------------|----------------------------|
| User A runs bootstrap-50 while User B browses | B blocked ~200ms | B blocked ~20ms (only result aggregation) |
| Two users trigger bootstrap-50 simultaneously | Second waits ~400ms | Both complete in ~200ms (separate processes) |
| User A in LLM optimization, User B triggers sim | B unblocked (LLM is async) | Same — LLM doesn't hold GIL |
| 10 concurrent games all stepping | Serial: ~10×71ms = 710ms | Parallel: ~2×71ms = 142ms |

The LLM call remains the dominant bottleneck (10-60s). Parallelizing simulation removes the only other source of user-visible latency.

## Appendix: Benchmark Data

All benchmarks on Apple M1 (single performance core, Python 3.13.12).

```
100 sims (2 banks, 12 ticks):        71ms total, 0.71ms/sim
100 sims (5 banks, 20 ticks):       342ms total, 3.42ms/sim  
100 sims (5 banks, 20 ticks, LSM):  349ms total, 3.49ms/sim
```

Cloud Run 1 vCPU estimated at 2-4× slower → worst case:

```
Bootstrap-50 (2 banks, 12 ticks):   ~200ms serial
Bootstrap-50 (5 banks, 20 ticks):   ~1s serial
Bootstrap-50 (5 banks, 20 ticks):   ~550ms with 2 workers
```
