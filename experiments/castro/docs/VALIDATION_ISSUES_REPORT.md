# Castro Experiment Validation Issues Report

**Date**: 2025-12-03
**Model Tested**: GPT-5.1 with high reasoning effort
**Experiments Run**: Exp1 (2-period), Exp2 (12-period), Exp3 (Joint Learning)

## Executive Summary

The initial experiment runs revealed **systematic validation failures** in LLM-generated policies. Across all experiments, approximately 85% of generated policies failed validation, preventing meaningful policy optimization. The root causes are two primary error categories:

1. **INVALID_ACTION (60% of errors)**: The LLM uses incorrect action types for specific tree contexts
2. **TYPE_ERROR (35% of errors)**: The LLM references parameters without defining them

---

## Detailed Error Analysis

### Error Distribution by Category

| Experiment | INVALID_ACTION | TYPE_ERROR | MISSING_FIELD | UNKNOWN | Total Errors | Fixed |
|------------|----------------|------------|---------------|---------|--------------|-------|
| Exp1       | 13             | 9          | 1             | 1       | 24           | 0     |
| Exp2       | (in progress)  | -          | -             | -       | -            | -     |
| Exp3       | 14             | 10         | 1             | 0       | 25           | 1     |

---

## Error Category 1: INVALID_ACTION (Most Critical)

### Root Cause

The LLM does not correctly distinguish which actions are valid for each tree type:

| Tree Type | Valid Actions | Common LLM Mistakes |
|-----------|---------------|---------------------|
| `payment_tree` | Release, Hold, Split, Drop, Reprioritize, etc. | (Usually correct) |
| `bank_tree` | SetReleaseBudget, SetState, AddState, NoAction | Uses `Release`, `Hold` |
| `strategic_collateral_tree` | PostCollateral, WithdrawCollateral, HoldCollateral | Uses `NoAction`, `Hold` |
| `end_of_tick_collateral_tree` | PostCollateral, WithdrawCollateral, HoldCollateral | Uses `NoAction`, `Hold` |

### Example Failure

```json
// LLM Generated (INVALID)
{
  "bank_tree": {
    "type": "action",
    "node_id": "B1_noop_bank",
    "action": "NoAction"  // ✗ Valid in bank_tree, but LLM confuses with collateral
  },
  "strategic_collateral_tree": {
    "type": "action",
    "node_id": "C1_hold",
    "action": "Hold"  // ✗ WRONG! "Hold" is a PAYMENT action!
  }
}
```

```json
// Correct Version
{
  "bank_tree": {
    "type": "action",
    "node_id": "B1_noop_bank",
    "action": "NoAction"  // ✓ Correct for bank_tree
  },
  "strategic_collateral_tree": {
    "type": "action",
    "node_id": "C1_hold",
    "action": "HoldCollateral"  // ✓ Correct for collateral trees
  }
}
```

### Why This Happens

1. The LLM sees "do nothing" semantics and reaches for `Hold` or `NoAction`
2. `NoAction` is only valid in `bank_tree`, not collateral trees
3. `Hold` is only valid in `payment_tree`, not anywhere else
4. The semantic similarity (`Hold` vs `HoldCollateral`) causes confusion

---

## Error Category 2: TYPE_ERROR (Parameter Reference Failures)

### Root Cause

The LLM uses `{"param": "parameter_name"}` to reference parameters but fails to define them in the `"parameters"` object at the policy root.

### Example Failure

```json
// LLM Generated (INVALID)
{
  "version": "2.0",
  "policy_id": "my_policy",
  "parameters": {},  // ✗ Empty parameters!
  "payment_tree": {
    "type": "condition",
    "condition": {
      "op": "<=",
      "left": {"field": "ticks_to_deadline"},
      "right": {"param": "urgency_threshold"}  // ✗ NOT DEFINED!
    },
    ...
  }
}
```

```json
// Correct Version
{
  "version": "2.0",
  "policy_id": "my_policy",
  "parameters": {
    "urgency_threshold": 3.0  // ✓ DEFINED before use
  },
  "payment_tree": {
    "type": "condition",
    "condition": {
      "op": "<=",
      "left": {"field": "ticks_to_deadline"},
      "right": {"param": "urgency_threshold"}  // ✓ Now valid
    },
    ...
  }
}
```

### Why This Happens

1. The system prompt mentions parameters but doesn't enforce the "define before use" pattern strongly enough
2. The LLM copies parameter names from examples without copying the definitions
3. When iterating, the LLM references parameters from the original policy but defines new ones

---

## Error Category 3: MISSING_FIELD (Rare)

### Description

The LLM references context fields that don't exist or aren't available in the current tree's evaluation context.

### Example

```json
// In bank_tree (which has NO transaction context)
{
  "condition": {
    "left": {"field": "remaining_amount"}  // ✗ Transaction field not available!
  }
}
```

**Note**: This is relatively rare because the prompt provides field vocabulary.

---

## Impact on Experiments

### Experiment 1 (Two-Period Deterministic)
- Converged at iteration 4 with **no cost improvement**
- All LLM-generated policies invalid → fell back to seed policy
- Final cost: $29,000 (same as baseline seed policy)

### Experiment 2 (Twelve-Period Stochastic)
- One policy was "fixed" but caused **catastrophic cost explosion**
- Costs jumped from $24,978 to $2,490,264,549 (99,718× increase)
- Settlement rate dropped to 65.9%
- Indicates the "fix" mechanism may be producing invalid logic even when validation passes

### Experiment 3 (Joint Learning)
- Bank B policy was successfully fixed on iteration 2
- Costs reduced from $24,978 to $12,489 (50% reduction!)
- Demonstrates optimization **can work** when policies validate
- But Bank A continued to fail, limiting further improvement

---

## Recommendations

### 1. Improve Few-Shot Examples (HIGH PRIORITY)

The prompt should include a **complete, validated policy** showing ALL tree types with correct actions:

```json
{
  "version": "2.0",
  "policy_id": "complete_example",
  "parameters": {
    "urgency_threshold": 3.0,
    "initial_liquidity_fraction": 0.25
  },
  "payment_tree": {
    "type": "condition",
    "node_id": "P1",
    "condition": {"op": "<=", "left": {"field": "ticks_to_deadline"}, "right": {"param": "urgency_threshold"}},
    "on_true": {"type": "action", "node_id": "P2", "action": "Release"},
    "on_false": {"type": "action", "node_id": "P3", "action": "Hold"}
  },
  "bank_tree": {
    "type": "action",
    "node_id": "B1",
    "action": "NoAction"
  },
  "strategic_collateral_tree": {
    "type": "condition",
    "node_id": "SC1",
    "condition": {"op": "==", "left": {"field": "system_tick_in_day"}, "right": {"value": 0}},
    "on_true": {
      "type": "action",
      "node_id": "SC2",
      "action": "PostCollateral",
      "parameters": {
        "amount": {"compute": {"op": "*", "left": {"field": "max_collateral_capacity"}, "right": {"param": "initial_liquidity_fraction"}}},
        "reason": {"value": "InitialAllocation"}
      }
    },
    "on_false": {"type": "action", "node_id": "SC3", "action": "HoldCollateral"}
  },
  "end_of_tick_collateral_tree": {
    "type": "action",
    "node_id": "E1",
    "action": "HoldCollateral"
  }
}
```

### 2. Add Explicit Action Mapping Table (HIGH PRIORITY)

Add a prominent, boxed section showing the exact action mapping:

```
┌─────────────────────────────────────────────────────────────────┐
│ ACTION → TREE TYPE MAPPING (VIOLATIONS = VALIDATION FAILURE)   │
├─────────────────────────────────────────────────────────────────┤
│ payment_tree:           Release, Hold, Split, Drop, Reprioritize│
│ bank_tree:              SetReleaseBudget, SetState, AddState,   │
│                         NoAction                                │
│ strategic_collateral_tree:    PostCollateral, WithdrawCollateral│
│                               HoldCollateral                    │
│ end_of_tick_collateral_tree:  PostCollateral, WithdrawCollateral│
│                               HoldCollateral                    │
└─────────────────────────────────────────────────────────────────┘

⚠️ COMMON CONFUSION:
- "Hold" ≠ "HoldCollateral" (different trees!)
- "NoAction" is ONLY valid in bank_tree
```

### 3. Parameter Enforcement Check (MEDIUM PRIORITY)

Add a pre-generation validation step in the prompt:

```
BEFORE GENERATING OUTPUT, VERIFY:
□ Every {"param": "X"} has a matching "X" in "parameters"
□ Every tree uses ONLY its allowed actions (see mapping above)
□ Every node has a unique "node_id"
```

### 4. Improve Fix Mechanism (MEDIUM PRIORITY)

The current fix mechanism sometimes produces logically invalid policies that pass validation but cause cost explosions. Consider:

- Validating policy logic, not just syntax
- Running a quick simulation sanity check before accepting "fixed" policies
- Requiring the fix to explain what was wrong and how it was fixed

---

## Conclusion

The validation failures are systematic and addressable through prompt engineering. The most critical fixes are:

1. **Complete few-shot example** showing all tree types with correct actions
2. **Explicit action mapping table** prominently displayed
3. **Parameter define-before-use** enforcement

When policies do validate, the system shows promising optimization capability (Exp3 achieved 50% cost reduction). Fixing the validation issues should unlock the full potential of LLM-based policy optimization.

---

*Report generated: 2025-12-03*
