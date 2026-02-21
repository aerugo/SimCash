# Phase 2: PyO3 FFI Wrapper

**Status**: Pending

---

## Objective

Expose `update_agent_policy` to Python via PyO3.

---

## TDD Steps

### Step 2.1: Write Failing Tests (RED)

Add to `simulator/src/ffi/orchestrator.rs` (inline Rust FFI tests) or verify via Python integration test.

Since PyO3 tests require the Python interpreter linked, we verify:
1. The method compiles as part of `PyOrchestrator`
2. Error propagation works (Rust `SimulationError` → Python `ValueError`)

### Step 2.2: Implement (GREEN)

Add to `#[pymethods] impl PyOrchestrator` in `simulator/src/ffi/orchestrator.rs`:

```rust
/// Update an agent's policy mid-simulation.
///
/// The new policy takes effect starting from the next tick.
/// Uses the same policy creation path as initialization (INV-9).
///
/// Args:
///     agent_id: The agent whose policy to update
///     policy_json: Full policy tree JSON string
///
/// Raises:
///     ValueError: If agent_id is unknown or policy_json is invalid
#[pyo3(text_signature = "(agent_id, policy_json)")]
fn update_agent_policy(&mut self, agent_id: &str, policy_json: &str) -> PyResult<()> {
    self.inner.update_agent_policy(agent_id, policy_json)
        .map_err(|e| PyErr::new::<pyo3::exceptions::PyValueError, _>(e.to_string()))
}
```

---

## Verification

```bash
cd simulator
cargo test --no-default-features  # compilation check (no PyO3 link)
cargo build                        # full build with PyO3 (if Python env available)
```

---

## Completion Criteria

- [ ] `PyOrchestrator::update_agent_policy` compiles
- [ ] Errors surface as `ValueError` in Python
- [ ] Docstring matches Nash's expected signature
