# Mid-Simulation Policy Update — Development Plan

**Status**: Pending
**Created**: 2025-07-11
**Branch**: `feature/mid-sim-policy-update`
**Requested by**: Nash (web sandbox agent) via `docs/reports/handover-dennis-mid-sim-policy-update.md`

## Summary

Add `update_agent_policy(agent_id, policy_json)` to `Orchestrator` so the web sandbox can swap an agent's decision policy between ticks without tearing down the simulation. Enables day-by-day LLM optimization in multi-day crisis scenarios.

## Critical Invariants

- **INV-1**: Money is i64 — not directly affected, but policy swap must not corrupt cost accumulators
- **INV-2**: Determinism — same tick sequence + same policy swaps at same points = byte-identical output
- **INV-4**: Balance conservation — policy swap must not alter balances, queues, or collateral
- **INV-5**: Replay identity — `save_state`/`load_state` must round-trip correctly with swapped policies
- **INV-9**: Policy evaluation identity — new policy must go through `create_policy()`, same path as init

## Current State

- Policies live in `Orchestrator.policies: HashMap<String, Box<dyn CashManagerPolicy>>` (`engine.rs:755`)
- Policy creation from JSON: `PolicyConfig::FromJson { json }` → `create_policy()` (`factory.rs:140`)
- `tick()` reads from `self.policies` each tick — no caching or pre-computation
- `get_agent_policies()` reads from `self.config.agent_configs`, NOT from `self.policies` — this is a discrepancy we need to handle

### Key Observation

`get_agent_policies()` returns policies from `self.config.agent_configs[].policy`, which is the *original* config. After a mid-sim swap, `self.policies` has the new executor but `self.config` still has the old `PolicyConfig`. We must update both to keep them consistent (and for `save_state` to serialize the current policy).

### Files to Modify

| File | Current State | Planned Changes |
|------|---------------|-----------------|
| `simulator/src/orchestrator/engine.rs` | No `update_agent_policy` method | Add method: validate agent, parse JSON, create policy, update both `self.policies` and `self.config` |
| `simulator/src/ffi/orchestrator.rs` | No PyO3 wrapper | Add `update_agent_policy(agent_id, policy_json) -> PyResult<()>` |
| `simulator/tests/test_mid_sim_policy_update.rs` | Does not exist | Rust integration tests |

## Solution Design

```
Python caller
    │
    ▼
PyOrchestrator.update_agent_policy(agent_id, policy_json)   [ffi/orchestrator.rs]
    │
    ▼
Orchestrator.update_agent_policy(agent_id, policy_json)      [engine.rs]
    ├── 1. Verify agent_id exists in self.policies
    ├── 2. Build PolicyConfig::FromJson { json }
    ├── 3. create_policy(&config) → TreePolicy
    ├── 4. self.policies.insert(agent_id, Box::new(policy))
    └── 5. Update self.config.agent_configs[agent_id].policy = config
```

### Key Design Decisions

1. **Update both `self.policies` AND `self.config`**: Keeps `get_agent_policies()` and `save_state()` consistent with actual runtime behavior. Without this, checkpoint-restore would lose the swapped policy.
2. **Use `PolicyConfig::FromJson`**: Same creation path as init (INV-9). No new parsing logic.
3. **No event emission for policy swap**: This is an external control action, not a simulation event. The caller (Nash's web backend) tracks policy history separately.
4. **`liquidity_allocation_fraction` deferred**: As Nash noted, fraction only matters at day-start and is read from immutable `AgentConfig`. Follow-up work.

## Phase Overview

| Phase | Description | TDD Focus | Estimated Tests |
|-------|-------------|-----------|-----------------|
| 1 | Rust `Orchestrator::update_agent_policy` | Core swap logic, error cases, determinism | 6 tests |
| 2 | PyO3 FFI wrapper | Python-callable wrapper, error propagation | 2 tests |

This is a small feature. Two phases, ~8 tests total.

## Phase 1: Rust Implementation

**Goal**: Add `update_agent_policy` to `Orchestrator` with full test coverage.

### Test Cases (RED)

1. `test_update_policy_basic` — Run N ticks, swap policy, run N more. Verify new policy affects decisions.
2. `test_update_policy_unknown_agent` — `update_agent_policy("NONEXISTENT", ...)` → error.
3. `test_update_policy_invalid_json` — `update_agent_policy("BANK_A", "not json")` → error.
4. `test_update_policy_determinism` — Same ticks + same swap at same point = identical output.
5. `test_update_policy_cross_day_boundary` — Run 1 day, swap, run day 2. Verify day 2 uses new policy.
6. `test_update_policy_get_agent_policies_consistent` — After swap, `get_agent_policies()` returns the new policy config.

### Implementation

Add to `engine.rs`:
```rust
pub fn update_agent_policy(&mut self, agent_id: &str, policy_json: &str) -> Result<(), SimulationError> {
    // 1. Verify agent exists
    if !self.policies.contains_key(agent_id) {
        return Err(SimulationError::InvalidConfig(
            format!("Unknown agent: {}", agent_id)
        ));
    }
    // 2. Create new policy via standard path (INV-9)
    let policy_config = PolicyConfig::FromJson { json: policy_json.to_string() };
    let new_policy = crate::policy::tree::create_policy(&policy_config)
        .map_err(|e| SimulationError::InvalidConfig(
            format!("Invalid policy JSON for {}: {}", agent_id, e)
        ))?;
    // 3. Swap executor
    self.policies.insert(agent_id.to_string(), Box::new(new_policy));
    // 4. Update config for consistency (save_state, get_agent_policies)
    if let Some(ac) = self.config.agent_configs.iter_mut().find(|ac| ac.id == agent_id) {
        ac.policy = policy_config;
    }
    Ok(())
}
```

### Success Criteria
- [ ] All 6 tests pass
- [ ] `cargo test --no-default-features` — full suite still green
- [ ] Policy swap does not alter balances or queues (INV-4)
- [ ] Determinism preserved (INV-2)

## Phase 2: PyO3 FFI Wrapper

**Goal**: Expose `update_agent_policy` to Python.

### Test Cases

1. `test_ffi_update_agent_policy_success` — Round-trip through PyO3.
2. `test_ffi_update_agent_policy_error` — Error propagation to Python exception.

### Implementation

Add to `ffi/orchestrator.rs` in `#[pymethods] impl PyOrchestrator`:
```rust
fn update_agent_policy(&mut self, agent_id: &str, policy_json: &str) -> PyResult<()> {
    self.inner.update_agent_policy(agent_id, policy_json)
        .map_err(|e| PyErr::new::<pyo3::exceptions::PyValueError, _>(e.to_string()))
}
```

### Success Criteria
- [ ] PyO3 wrapper compiles
- [ ] Python can call `orch.update_agent_policy(agent_id, json_str)`
- [ ] Errors surface as Python exceptions

## Testing Strategy

### Rust Integration Tests (`simulator/tests/test_mid_sim_policy_update.rs`)
- All 6 test cases from Phase 1
- Use existing test helper patterns (see `test_penalty_mode.rs`, `test_cost_accrual.rs`)

### Python Integration Tests
- Deferred to Nash's web backend — he'll exercise the PyO3 wrapper in his integration tests
- We verify the FFI compiles and the Rust method works correctly

## Documentation Updates

- [ ] Update `docs/reference/architecture/` if needed (likely not — this is additive)
- [ ] No new invariants introduced
- [ ] No new patterns introduced

## Progress Tracking

| Phase | Status | Notes |
|-------|--------|-------|
| Phase 1 | Pending | |
| Phase 2 | Pending | |
