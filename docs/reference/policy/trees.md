# Policy Tree Types

> **Reference: The 4 Policy Tree Types and Their Evaluation Contexts**

## Overview

Each policy JSON file can contain up to **4 independent decision trees**. Each tree serves a different purpose and is evaluated at a different point in the tick lifecycle.

## Tree Type Summary

| Tree | Evaluation Timing | Frequency | Purpose | Valid Actions |
|------|-------------------|-----------|---------|---------------|
| `bank_tree` | Step 1.75 | Once per agent per tick | Bank-level budgeting | SetReleaseBudget, SetState, AddState, NoAction |
| `payment_tree` | Step 2 | For each tx in Queue 1 | Payment release decisions | Release, Hold, Drop, Split, etc. |
| `strategic_collateral_tree` | Step 1.5 | Once per agent per tick | Forward-looking collateral | PostCollateral, WithdrawCollateral, HoldCollateral |
| `end_of_tick_collateral_tree` | Step 5.5 | Once per agent per tick | Reactive collateral cleanup | PostCollateral, WithdrawCollateral, HoldCollateral |

## Tick Lifecycle and Tree Evaluation Order

```
Tick N Start
    │
    ├─► Step 1: Transaction arrivals
    │
    ├─► Step 1.5: strategic_collateral_tree evaluation (once per agent)
    │             - Forward-looking collateral decisions
    │             - Posted before any settlements
    │
    ├─► Step 1.75: bank_tree evaluation (once per agent)
    │              - Sets budgets and state registers
    │              - Constrains subsequent payment decisions
    │
    ├─► Step 2: payment_tree evaluation (for each tx in Queue 1)
    │           - Decides Release, Hold, Split, etc.
    │           - Budget constraints applied
    │
    ├─► Step 3: RTGS settlement attempts
    │
    ├─► Step 4: LSM cycle detection and settlement
    │
    ├─► Step 5: Queue 2 processing
    │
    ├─► Step 5.5: end_of_tick_collateral_tree evaluation (once per agent)
    │             - Reactive collateral cleanup
    │             - Based on end-of-tick state
    │
    ├─► Step 6: Cost accrual and metrics
    │
    └─► Step 7: End of tick
```

---

## 1. bank_tree

### Purpose
Evaluates once per agent at the start of each tick to set bank-level constraints that affect all payment decisions for that tick.

### Evaluation Context
Uses `EvalContext::bank_level()` - **NO transaction-specific fields**.

### Available Fields
See [context-fields.md](context-fields.md) for full list. Includes:
- Agent fields: `balance`, `credit_limit`, `effective_liquidity`, etc.
- Queue fields: `queue1_total_value`, `outgoing_queue_size`, etc.
- System fields: `current_tick`, `rtgs_queue_size`, etc.
- Time fields: `day_progress_fraction`, `is_eod_rush`, etc.
- State registers: Any `bank_state_*` fields

### Valid Actions
| Action | Description | Required Parameters |
|--------|-------------|---------------------|
| `SetReleaseBudget` | Set total and per-counterparty release limits | `max_value_to_release` (required), `focus_counterparties` (optional), `max_per_counterparty` (optional) |
| `SetState` | Set a state register value | `key`, `value`, `reason` |
| `AddState` | Add to a state register value | `key`, `value`, `reason` |
| `NoAction` | No bank-level action | None |

### Example
```json
{
  "bank_tree": {
    "type": "condition",
    "node_id": "B1_CheckPressure",
    "description": "High liquidity pressure? Limit releases.",
    "condition": {
      "op": ">",
      "left": {"field": "liquidity_pressure"},
      "right": {"value": 0.7}
    },
    "on_true": {
      "type": "action",
      "node_id": "B2_LimitBudget",
      "action": "SetReleaseBudget",
      "parameters": {
        "max_value_to_release": {"value": 100000.0}
      }
    },
    "on_false": {
      "type": "action",
      "node_id": "B3_NormalBudget",
      "action": "SetReleaseBudget",
      "parameters": {
        "max_value_to_release": {"field": "queue1_total_value"}
      }
    }
  }
}
```

### Implementation Location
- Trait method: `CashManagerPolicy::evaluate_queue()` (calls bank tree first)
- Tree traversal: `traverse_bank_tree()` in `interpreter.rs:474`
- Decision builder: `build_bank_decision()` in `interpreter.rs:1107`

---

## 2. payment_tree

### Purpose
Evaluates for each transaction in the agent's Queue 1 to decide whether to release, hold, split, or drop the payment.

### Evaluation Context
Uses `EvalContext::build()` - **FULL context including transaction-specific fields**.

### Available Fields
All fields from [context-fields.md](context-fields.md), including:
- **Transaction fields**: `amount`, `remaining_amount`, `deadline_tick`, `priority`, `ticks_to_deadline`, `is_overdue`, etc.
- Plus all bank-level fields

### Valid Actions
| Action | Description | Required Parameters |
|--------|-------------|---------------------|
| `Release` | Submit full transaction to RTGS | `priority_flag` (optional), `timed_for_tick` (optional) |
| `ReleaseWithCredit` | Release using credit if needed | Same as Release |
| `Split` / `PaceAndRelease` | Split into N parts, submit all | `num_splits` |
| `StaggerSplit` | Split with staggered timing | `num_splits`, `stagger_first_now`, `stagger_gap_ticks`, `priority_boost_children` |
| `Hold` | Keep in Queue 1 | `reason` (optional) |
| `Drop` | Remove from simulation | None |
| `Reprioritize` | Change priority | `new_priority` |
| `WithdrawFromRtgs` | Remove from Queue 2 | None |
| `ResubmitToRtgs` | Change RTGS priority | `rtgs_priority` |

### Example
```json
{
  "payment_tree": {
    "type": "condition",
    "node_id": "N1_CheckDeadline",
    "description": "Is transaction past deadline?",
    "condition": {
      "op": "<=",
      "left": {"field": "deadline_tick"},
      "right": {"field": "current_tick"}
    },
    "on_true": {
      "type": "action",
      "node_id": "A1_Drop",
      "action": "Drop"
    },
    "on_false": {
      "type": "condition",
      "node_id": "N2_CheckLiquidity",
      "condition": {
        "op": ">=",
        "left": {"field": "effective_liquidity"},
        "right": {"field": "remaining_amount"}
      },
      "on_true": {
        "type": "action",
        "node_id": "A2_Release",
        "action": "Release"
      },
      "on_false": {
        "type": "action",
        "node_id": "A3_Hold",
        "action": "Hold",
        "parameters": {
          "reason": {"value": "InsufficientLiquidity"}
        }
      }
    }
  }
}
```

### Implementation Location
- Trait method: `CashManagerPolicy::evaluate_queue()`
- Tree traversal: `traverse_tree()` in `interpreter.rs:430`
- Decision builder: `build_decision()` in `interpreter.rs:622`

---

## 3. strategic_collateral_tree

### Purpose
Evaluates once per agent BEFORE settlements to make forward-looking collateral decisions. Posts collateral to prepare for anticipated liquidity needs.

### Evaluation Context
Uses `EvalContext::bank_level()` - **NO transaction-specific fields**.

### Available Fields
Same as `bank_tree` - all bank-level and system fields, plus state registers.

### Valid Actions
| Action | Description | Required Parameters |
|--------|-------------|---------------------|
| `PostCollateral` | Post collateral to increase liquidity | `amount`, `reason` (optional), `auto_withdraw_after_ticks` (optional) |
| `WithdrawCollateral` | Withdraw collateral to reduce cost | `amount`, `reason` (optional) |
| `HoldCollateral` | No change to collateral | None |

### Example
```json
{
  "strategic_collateral_tree": {
    "type": "condition",
    "node_id": "SC1_CheckGap",
    "description": "Is there a liquidity gap?",
    "condition": {
      "op": ">",
      "left": {"field": "queue1_liquidity_gap"},
      "right": {"value": 0}
    },
    "on_true": {
      "type": "action",
      "node_id": "SC2_PostCollateral",
      "action": "PostCollateral",
      "parameters": {
        "amount": {"field": "queue1_liquidity_gap"},
        "reason": {"value": "UrgentLiquidityNeed"},
        "auto_withdraw_after_ticks": {"value": 10.0}
      }
    },
    "on_false": {
      "type": "action",
      "node_id": "SC3_Hold",
      "action": "HoldCollateral"
    }
  }
}
```

### Implementation Location
- Tree traversal: `traverse_strategic_collateral_tree()` in `interpreter.rs:446`
- Decision builder: `build_collateral_decision()` in `interpreter.rs:949`

---

## 4. end_of_tick_collateral_tree

### Purpose
Evaluates once per agent AFTER all settlements to make reactive collateral decisions. Typically used to withdraw excess collateral or clean up at end of day.

### Evaluation Context
Uses `EvalContext::bank_level()` - **NO transaction-specific fields**.

### Available Fields
Same as `strategic_collateral_tree`.

### Valid Actions
Same as `strategic_collateral_tree`:
- `PostCollateral`
- `WithdrawCollateral`
- `HoldCollateral`

### Example
```json
{
  "end_of_tick_collateral_tree": {
    "type": "condition",
    "node_id": "EOT1_CheckExcess",
    "description": "Is there excess collateral that can be withdrawn?",
    "condition": {
      "op": ">",
      "left": {"field": "excess_collateral"},
      "right": {"value": 0}
    },
    "on_true": {
      "type": "action",
      "node_id": "EOT2_Withdraw",
      "action": "WithdrawCollateral",
      "parameters": {
        "amount": {"field": "excess_collateral"},
        "reason": {"value": "CostOptimization"}
      }
    },
    "on_false": {
      "type": "action",
      "node_id": "EOT3_Hold",
      "action": "HoldCollateral"
    }
  }
}
```

### Implementation Location
- Tree traversal: `traverse_end_of_tick_collateral_tree()` in `interpreter.rs:460`
- Decision builder: `build_collateral_decision()` in `interpreter.rs:949`

---

## Field Availability Matrix

| Field Category | bank_tree | payment_tree | strategic_collateral | end_of_tick_collateral |
|---------------|:---------:|:------------:|:-------------------:|:---------------------:|
| Transaction fields | ❌ | ✅ | ❌ | ❌ |
| Agent/balance fields | ✅ | ✅ | ✅ | ✅ |
| Queue fields | ✅ | ✅ | ✅ | ✅ |
| Collateral fields | ✅ | ✅ | ✅ | ✅ |
| Cost rate fields | ✅ | ✅ | ✅ | ✅ |
| Time/system fields | ✅ | ✅ | ✅ | ✅ |
| LSM-aware fields | ❌ | ✅ | ❌ | ❌ |
| State registers | ✅ | ✅ | ✅ | ✅ |

---

## Tree Presence Requirements

All trees are **optional**. A valid policy file can have:
- Only `payment_tree` (most common)
- `payment_tree` + `bank_tree` (with budget constraints)
- All four trees (full collateral management)
- `strategic_collateral_tree` + `end_of_tick_collateral_tree` only (collateral-only policy)

### Minimum Valid Policy
```json
{
  "version": "1.0",
  "policy_id": "minimal",
  "payment_tree": {
    "type": "action",
    "node_id": "A1",
    "action": "Release"
  },
  "parameters": {}
}
```

---

## Source Code Reference

| Component | File | Line |
|-----------|------|------|
| DecisionTreeDef struct | `simulator/src/policy/tree/types.rs` | 22-58 |
| bank_tree field | `simulator/src/policy/tree/types.rs` | 37-38 |
| payment_tree field | `simulator/src/policy/tree/types.rs` | 40-43 |
| strategic_collateral_tree field | `simulator/src/policy/tree/types.rs` | 45-48 |
| end_of_tick_collateral_tree field | `simulator/src/policy/tree/types.rs` | 50-53 |
| EvalContext::build() | `simulator/src/policy/tree/context.rs` | 152-611 |
| EvalContext::bank_level() | `simulator/src/policy/tree/context.rs` | 646-869 |
