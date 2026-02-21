# Phase 1: Rust Implementation

**Status**: Pending

---

## Objective

Add `Orchestrator::update_agent_policy(agent_id, policy_json)` with full test coverage.

---

## Invariants Enforced

- INV-2: Determinism — test that identical swap sequences produce identical output
- INV-4: Balance conservation — verify swap doesn't alter balances/queues
- INV-5: Replay identity — verify `get_agent_policies()` reflects the swap (prerequisite for save_state)
- INV-9: Policy eval identity — uses `create_policy()` same as init

---

## TDD Steps

### Step 1.1: Write Failing Tests (RED)

Create `simulator/tests/test_mid_sim_policy_update.rs`:

**Test Cases**:

1. `test_update_policy_basic` — Create orchestrator with known policy (e.g. FIFO). Run 50 ticks. Swap to a different policy (e.g. deadline-aware). Run 50 more ticks. Verify that the agent's decisions change after the swap (compare event logs before/after).

2. `test_update_policy_unknown_agent` — Call `update_agent_policy("NONEXISTENT", valid_json)`. Assert returns `Err` with "Unknown agent" message.

3. `test_update_policy_invalid_json` — Call `update_agent_policy("BANK_A", "not valid json")`. Assert returns `Err`.

4. `test_update_policy_determinism` — Run two identical orchestrators. Both: tick 50 times, swap same policy at tick 50, tick 50 more. Compare all events — must be identical (INV-2).

5. `test_update_policy_cross_day_boundary` — Run 100 ticks (1 full day). Swap policy. Run 100 more ticks (day 2). Verify day 2 events reflect new policy.

6. `test_update_policy_config_consistency` — After swap, call `get_agent_policies()`. Verify returned `PolicyConfig` is `FromJson` with the new JSON. This ensures `save_state()` would capture the correct policy.

### Step 1.2: Implement (GREEN)

Modify `simulator/src/orchestrator/engine.rs`:

```rust
pub fn update_agent_policy(&mut self, agent_id: &str, policy_json: &str) -> Result<(), SimulationError> {
    if !self.policies.contains_key(agent_id) {
        return Err(SimulationError::InvalidConfig(
            format!("Unknown agent: {}", agent_id)
        ));
    }

    let policy_config = PolicyConfig::FromJson { json: policy_json.to_string() };
    let new_policy = crate::policy::tree::create_policy(&policy_config)
        .map_err(|e| SimulationError::InvalidConfig(
            format!("Invalid policy JSON for {}: {}", agent_id, e)
        ))?;

    self.policies.insert(agent_id.to_string(), Box::new(new_policy));

    if let Some(ac) = self.config.agent_configs.iter_mut().find(|ac| ac.id == agent_id) {
        ac.policy = policy_config;
    }

    Ok(())
}
```

### Step 1.3: Refactor

- Ensure error types are consistent with existing `Orchestrator` methods
- Add doc comment with usage example

---

## Edge Cases

- Agent ID exists in config but not in policies HashMap (shouldn't happen, but guard)
- Valid JSON but not a valid policy tree structure (handled by `create_policy` returning `TreePolicyError`)
- Empty JSON string
- Policy swap at tick 0 (before any simulation)
- Multiple swaps for same agent in sequence

---

## Verification

```bash
cd simulator
cargo test test_mid_sim_policy_update --no-default-features
cargo test --no-default-features  # full suite
```

---

## Completion Criteria

- [ ] All 6 test cases pass
- [ ] Full Rust test suite passes (`cargo test --no-default-features`)
- [ ] `get_agent_policies()` returns updated config after swap
- [ ] No balance/queue corruption after swap
- [ ] Deterministic across identical runs
