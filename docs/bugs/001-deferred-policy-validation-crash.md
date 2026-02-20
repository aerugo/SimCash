# Bug Report: Deferred Policy Validation Causes Runtime Crash

**Severity:** High  
**Component:** `simulator/src/policy/tree/`  
**Reported:** 2026-02-20  
**Found by:** Nash (during web sandbox deployment testing)

## Summary

The Rust engine crashes at runtime when given a policy JSON containing invalid field references (e.g. `queue_size` instead of `outgoing_queue_size`). The engine should reject invalid policies at construction time, but instead defers validation to the first tick evaluation — causing an unrecoverable `SimulationError` mid-simulation.

## Reproduction

Feed this policy JSON to `Orchestrator::new()` via `InlineJson` config:

```json
{
  "version": "2.0",
  "policy_id": "bad_policy",
  "parameters": { "initial_liquidity_fraction": 0.8 },
  "payment_tree": { "type": "action", "node_id": "root", "action": "Release" },
  "bank_tree": {
    "type": "condition",
    "node_id": "root",
    "field": "queue_size",
    "operator": "greater_than",
    "threshold": 5,
    "true_branch": { "type": "action", "node_id": "t", "action": "NoAction" },
    "false_branch": { "type": "action", "node_id": "f", "action": "NoAction" }
  }
}
```

**Expected:** `Orchestrator::new()` returns an error: "Invalid field reference: 'queue_size'"  
**Actual:** `Orchestrator::new()` succeeds. First call to `orch.tick()` panics with:
```
Tick execution failed: Invalid config: Failed to evaluate bank_tree for CORRESPONDENT_HUB: 
Tree validation failed: [InvalidFieldReference("queue_size")]
```

## Root Cause

Policy validation is **deferred** to first use. The call chain:

1. `Orchestrator::new()` → `create_policy()` → `TreePolicy::from_json()` — only runs `serde_json::from_str()` (structural parse, no semantic validation)
2. `TreePolicy::new(tree)` sets `validated: false`
3. First `orch.tick()` → `evaluate_bank_tree()` → `validate_if_needed()` — NOW validation runs, finds `queue_size` is not a valid field, returns `Err`
4. Error propagates as `SimulationError::InvalidConfig`, surfaced to Python as `RuntimeError`

**Location of deferred validation:**
- `simulator/src/policy/tree/executor.rs:176-182` — `validate_if_needed()` only validates on first call
- `simulator/src/policy/tree/executor.rs:309` — bank_tree validation deferred to first `evaluate_bank_tree()`

**Why validation can't happen at construction time (current design):**  
`validate_tree()` requires an `EvalContext` (agent state, tick number, cost rates) to check field references against the available context fields. At `TreePolicy::new()` time, no `EvalContext` exists yet because the agent hasn't been initialized.

## Impact

- **Web sandbox:** LLM-generated policies with invalid field references crash the auto-run loop. The entire game stops and can't recover without rolling back policies (workaround added in `web/backend/app/game.py`).
- **Experiment runner:** Same issue — a bad policy from the LLM crashes the simulation mid-experiment.
- **Invariant violation:** The engine should never crash from bad input. Bad policies should be rejected at construction or handled gracefully.

## Proposed Fix

**Option A (minimal): Validate field references at parse time without EvalContext**

The set of valid field names is static and known at compile time (defined in `validation.rs:355-420`). Extract the field whitelist into a standalone function and call it from `TreePolicy::from_json()` / `TreePolicy::new()`:

```rust
// In factory.rs or executor.rs
impl TreePolicy {
    pub fn from_json(json: &str) -> Result<Self, TreePolicyError> {
        let tree: DecisionTreeDef = serde_json::from_str(json)?;
        // Validate field references eagerly (no EvalContext needed)
        validate_field_references(&tree)?;
        Ok(Self::new(tree))
    }
}
```

This catches the most common LLM error (invalid field names) without needing agent state.

**Option B (comprehensive): Split validation into static + dynamic**

1. **Static validation** at construction: field names, node IDs, tree depth, parameter references — everything that doesn't need runtime state
2. **Dynamic validation** at first tick: context-dependent checks (if any remain)

This preserves the deferred validation for anything that truly needs runtime context, while catching structural errors early.

## Valid Field References (for reference)

From `simulator/src/policy/tree/validation.rs`:

**Payment-level:** `transaction_value`, `transaction_deadline`, `ticks_until_deadline`, `urgency_ratio`, `is_overdue`, `counterparty_id`

**Agent-level:** `current_balance`, `available_balance`, `outgoing_queue_size`, `outgoing_queue_value`, `incoming_expected_value`, `net_position`, `liquidity_ratio`, `overdraft_utilization`, `posted_collateral`, `collateral_capacity`, `secured_credit`

**System-level:** `current_tick`, `time_of_day_fraction`, `is_end_of_day`, `rtgs_queue_size`, `rtgs_queue_value`, `system_total_liquidity`, `system_pending_value`

**NOT valid:** `queue_size` (should be `outgoing_queue_size` or `rtgs_queue_size`)

## Workaround (deployed)

The web backend now validates policies before applying them by creating a test `Orchestrator` and catching the error:

```python
# web/backend/app/game.py — _apply_result()
try:
    ffi_config = self._build_ffi_config(self._base_seed)
    Orchestrator.new(ffi_config)  # Validates config including policy trees
except Exception as e:
    self.policies[aid] = old_policy  # Roll back
    result["rejected"] = True
```

This is expensive (creates a throwaway orchestrator per policy) and only catches the error after the LLM has already wasted API tokens. The proper fix is in the Rust engine.
