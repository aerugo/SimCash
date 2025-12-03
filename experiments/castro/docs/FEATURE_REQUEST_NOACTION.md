# Feature Request: Add `NoAction` to `ActionType` Enum

**Date:** 2025-12-03
**Requester:** Castro Experiment Module
**Priority:** High (blocking experiment validation)

## Summary

Add a `NoAction` variant to the `ActionType` enum in `backend/src/policy/tree/types.rs` to allow bank-level decision trees to explicitly take no action on a given tick.

## Current Behavior

The Rust `ActionType` enum does not include a `NoAction` variant. When a policy contains `"action": "NoAction"` in the `bank_tree`, Serde deserialization fails with:

```
JSON parsing failed: unknown variant `NoAction`, expected one of `Release`, `ReleaseWithCredit`, ...
```

## Expected Behavior

Policies should be able to specify `NoAction` as a valid action in `bank_tree` to indicate "do nothing this tick."

## Rationale

### 1. Semantic Correctness

The `bank_tree` is evaluated once per tick to make bank-level decisions (budgets, state changes, etc.). There are valid scenarios where the policy should explicitly do nothing:

- Normal operating conditions that don't require budget adjustments
- Cooldown periods between state changes
- Default fallback when no conditions trigger active management

### 2. Symmetry with Other Trees

The collateral trees have `HoldCollateral` for "take no action." The `bank_tree` needs an equivalent:

| Tree Type | "No-op" Action |
|-----------|----------------|
| `payment_tree` | `Hold` (hold in queue) |
| `strategic_collateral_tree` | `HoldCollateral` |
| `end_of_tick_collateral_tree` | `HoldCollateral` |
| `bank_tree` | **`NoAction` (missing!)** |

### 3. Schema Consistency

The Python experiment module (`experiments/castro/schemas/actions.py`) already defines:

```python
BANK_ACTIONS = [
    "SetReleaseBudget",
    "SetState",
    "AddState",
    "NoAction",  # <-- Defined in Python but not in Rust
]
```

This mismatch causes 100% of `INVALID_ACTION` errors in the Castro experiments.

## Proposed Change

In `backend/src/policy/tree/types.rs`, add to the `ActionType` enum:

```rust
/// Action type for terminal nodes
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "PascalCase")]
pub enum ActionType {
    // ... existing variants ...

    // Phase 3.3: Bank-Level No-Op Action
    /// Take no bank-level action this tick
    ///
    /// Used in bank_tree when no budget changes or state updates are needed.
    /// This is the bank-tree equivalent of HoldCollateral for collateral trees.
    NoAction,
}
```

In the executor (`backend/src/policy/tree/executor.rs` or similar), handle `NoAction`:

```rust
ActionType::NoAction => {
    // No operation - just return success with no side effects
    Ok(BankDecision::NoOp)
}
```

## Impact

- **Breaking changes:** None (additive change)
- **Existing policies:** Unaffected
- **New policies:** Can now use `NoAction` in `bank_tree`

## Validation

After implementation:

1. Existing test suite should pass
2. Policy with `"action": "NoAction"` in `bank_tree` should validate successfully
3. Castro experiments should see INVALID_ACTION errors drop to near zero

## Workaround (Current)

Until this is implemented, policies must use a no-op `SetState` as a workaround:

```json
{
  "type": "action",
  "node_id": "B1_noop",
  "action": "SetState",
  "parameters": {
    "key": {"value": "bank_state_noop"},
    "value": {"value": 0}
  }
}
```

This is verbose and semantically misleading.

## Related Files

- `backend/src/policy/tree/types.rs` - ActionType enum definition
- `backend/src/policy/tree/executor.rs` - Action execution logic
- `experiments/castro/schemas/actions.py` - Python action definitions (already has NoAction)
- `experiments/castro/schemas/registry.py` - Re-exports BANK_ACTIONS

## References

- Castro et al. (2025) bank-level policy decisions
- SimCash Phase 3.3: Policy Enhancements V2 (bank_tree introduction)
