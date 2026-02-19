# Policy Tree Specification

> Complete reference for the SimCash JSON decision tree DSL — the same specification given to the LLM for building policy trees.

---

## Table of Contents

- [Overview](#overview)
- [Tree Types](#tree-types)
- [Node Types](#node-types)
- [Actions](#actions)
- [Context Fields](#context-fields)
- [Expression System](#expression-system)
- [Value Types](#value-types)
- [Computations](#computations)
- [Validation Rules](#validation-rules)
- [Complete Example](#complete-example)

---

## Overview

A policy is a JSON file containing up to **4 independent decision trees**. Each tree is a binary decision tree composed of **condition** and **action** nodes. The engine evaluates these trees at specific points in the tick lifecycle to determine payment release, budgeting, and collateral decisions.

```
┌─────────────────────────────────────────────────────────────┐
│                     Policy JSON File                         │
│  ┌──────────────┬──────────────┬─────────────┬────────────┐ │
│  │  bank_tree   │ payment_tree │ strategic_  │ end_of_    │ │
│  │              │              │ collateral_ │ tick_       │ │
│  │              │              │ tree        │ collateral_ │ │
│  │              │              │             │ tree        │ │
│  └──────┬───────┴──────┬───────┴──────┬──────┴─────┬──────┘ │
│    Step 1.75      Step 2         Step 1.5     Step 5.5      │
│    (Budget)       (Payments)     (Pre-settle) (Post-settle) │
└─────────────────────────────────────────────────────────────┘
```

### Minimal Valid Policy

```json
{
  "version": "1.0",
  "policy_id": "minimal",
  "parameters": {},
  "payment_tree": {
    "type": "action",
    "node_id": "A1",
    "action": "Release"
  }
}
```

---

## Tree Types

All trees are **optional**. A policy can contain any combination.

| Tree | Eval Step | Frequency | Purpose |
|------|-----------|-----------|---------|
| `strategic_collateral_tree` | 1.5 | Once/agent/tick | Forward-looking collateral posting |
| `bank_tree` | 1.75 | Once/agent/tick | Set release budgets and state registers |
| `payment_tree` | 2 | Per transaction in Queue 1 | Release, hold, split, or drop payments |
| `end_of_tick_collateral_tree` | 5.5 | Once/agent/tick | Reactive collateral cleanup |

### Field Availability by Tree

| Field Category | `payment_tree` | `bank_tree` | `strategic_collateral_tree` | `end_of_tick_collateral_tree` |
|----------------|:-:|:-:|:-:|:-:|
| Transaction fields | ✅ | ❌ | ❌ | ❌ |
| Agent / balance | ✅ | ✅ | ✅ | ✅ |
| Queue fields | ✅ | ✅ | ✅ | ✅ |
| Collateral fields | ✅ | ✅ | ✅ | ✅ |
| Cost rate fields | ✅ | ✅ | ✅ | ✅ |
| Time / system | ✅ | ✅ | ✅ | ✅ |
| LSM-aware fields | ✅ | ❌ | ❌ | ❌ |
| Throughput fields | ✅ | ✅ | ✅ | ✅ |
| State registers (`bank_state_*`) | ✅ | ✅ | ✅ | ✅ |

---

## Node Types

Every tree is composed of exactly two node types:

### Condition Node

Evaluates a boolean expression and branches.

```json
{
  "type": "condition",
  "node_id": "N1_CheckLiquidity",
  "description": "Optional human-readable description",
  "condition": { /* Expression */ },
  "on_true": { /* TreeNode */ },
  "on_false": { /* TreeNode */ }
}
```

| Field | Type | Required | Description |
|-------|------|:--------:|-------------|
| `type` | `"condition"` | ✅ | Node type discriminator |
| `node_id` | string | ✅ | Unique across **all** trees in the policy |
| `description` | string | | Human-readable note |
| `condition` | Expression | ✅ | Boolean expression to evaluate |
| `on_true` | TreeNode | ✅ | Branch if condition is true |
| `on_false` | TreeNode | ✅ | Branch if condition is false |

### Action Node

Terminal node that returns a decision.

```json
{
  "type": "action",
  "node_id": "A1_Release",
  "action": "Release",
  "parameters": { /* optional action params */ }
}
```

| Field | Type | Required | Description |
|-------|------|:--------:|-------------|
| `type` | `"action"` | ✅ | Node type discriminator |
| `node_id` | string | ✅ | Unique across all trees |
| `action` | string | ✅ | Action type (see Actions section) |
| `parameters` | object | | Action-specific parameters (ValueOrCompute) |

### Node ID Conventions (Recommended)

| Prefix | Use |
|--------|-----|
| `N<n>_<desc>` | Condition nodes |
| `A<n>_<desc>` | Action nodes in payment_tree |
| `B<n>_<desc>` | Nodes in bank_tree |
| `SC<n>_<desc>` | Nodes in strategic_collateral_tree |
| `EOT<n>_<desc>` | Nodes in end_of_tick_collateral_tree |

---

## Actions

### Action Validity Matrix

| Action | `payment_tree` | `bank_tree` | Collateral trees |
|--------|:-:|:-:|:-:|
| Release | ✅ | | |
| ReleaseWithCredit | ✅ | | |
| Split / PaceAndRelease | ✅ | | |
| StaggerSplit | ✅ | | |
| Hold | ✅ | | |
| Drop | ✅ | | |
| Reprioritize | ✅ | | |
| WithdrawFromRtgs | ✅ | | |
| ResubmitToRtgs | ✅ | | |
| SetReleaseBudget | | ✅ | |
| SetState | | ✅ | |
| AddState | | ✅ | |
| NoAction | | ✅ | |
| PostCollateral | | | ✅ |
| WithdrawCollateral | | | ✅ |
| HoldCollateral | | | ✅ |

---

### Payment Actions (`payment_tree`)

#### Release

Submit the full transaction to RTGS Queue 2 for settlement.

| Parameter | Type | Required | Description |
|-----------|------|:--------:|-------------|
| `priority_flag` | string | | `"HIGH"` (10), `"MEDIUM"` (5), `"LOW"` (1) |
| `timed_for_tick` | number | | Target tick for release |

```json
{ "type": "action", "node_id": "A1", "action": "Release" }
```

#### ReleaseWithCredit

Same as Release — credit usage handled by the settlement engine.

#### Split / PaceAndRelease

Split transaction into N equal parts, submit all immediately.

| Parameter | Type | Required | Description |
|-----------|------|:--------:|-------------|
| `num_splits` | number | ✅ | Parts to split into (≥ 2) |

```json
{
  "type": "action", "node_id": "A1", "action": "Split",
  "parameters": { "num_splits": {"value": 4} }
}
```

#### StaggerSplit

Split transaction with staggered timing.

| Parameter | Type | Required | Description |
|-----------|------|:--------:|-------------|
| `num_splits` | number | ✅ | Parts to split into (≥ 2) |
| `stagger_first_now` | number | ✅ | Children released immediately |
| `stagger_gap_ticks` | number | ✅ | Ticks between subsequent releases |
| `priority_boost_children` | number | ✅ | Priority boost (0–10) |

Example: `num_splits=5, stagger_first_now=2, stagger_gap_ticks=3` → children 1–2 at tick T, child 3 at T+3, child 4 at T+6, child 5 at T+9.

#### Hold

Keep transaction in Queue 1 for re-evaluation next tick.

| Parameter | Type | Required | Description |
|-----------|------|:--------:|-------------|
| `reason` | string | | `"InsufficientLiquidity"`, `"AwaitingInflows"`, `"LowPriority"`, or custom |

#### Drop

Remove transaction from simulation. **Deprecated** — prefer Hold.

#### Reprioritize

Change transaction priority without releasing.

| Parameter | Type | Required | Description |
|-----------|------|:--------:|-------------|
| `new_priority` | number | ✅ | New priority (0–10) |

#### WithdrawFromRtgs

Pull transaction back from RTGS Queue 2 to Queue 1. No parameters.

#### ResubmitToRtgs

Change RTGS priority of a Queue 2 transaction.

| Parameter | Type | Required | Description |
|-----------|------|:--------:|-------------|
| `rtgs_priority` | string | ✅ | `"HighlyUrgent"`, `"Urgent"`, `"Normal"` |

---

### Bank Actions (`bank_tree`)

#### SetReleaseBudget

Set tick-level release constraints that gate `payment_tree` decisions.

| Parameter | Type | Required | Description |
|-----------|------|:--------:|-------------|
| `max_value_to_release` | number | ✅ | Total release budget (cents) |
| `focus_counterparties` | array | | Allowed counterparties (null = all) |
| `max_per_counterparty` | number | | Per-counterparty cap |

#### SetState / AddState

Write to a state register (`bank_state_*` prefix, max 10 per agent, reset at EOD).

| Parameter | Type | Required | Description |
|-----------|------|:--------:|-------------|
| `key` | string | ✅ | Must start with `bank_state_` |
| `value` | number | ✅ | New value (SetState) or delta (AddState) |
| `reason` | string | | Audit trail explanation |

#### NoAction

No bank-level action this tick. No parameters.

---

### Collateral Actions (`strategic_collateral_tree`, `end_of_tick_collateral_tree`)

#### PostCollateral

| Parameter | Type | Required | Description |
|-----------|------|:--------:|-------------|
| `amount` | number | ✅ | Amount to post (cents). ≤ 0 → HoldCollateral |
| `reason` | string | | `"UrgentLiquidityNeed"`, `"PreemptivePosting"`, `"DeadlineEmergency"`, `"CostOptimization"` |
| `auto_withdraw_after_ticks` | number | | Auto-withdraw after N ticks |

#### WithdrawCollateral

| Parameter | Type | Required | Description |
|-----------|------|:--------:|-------------|
| `amount` | number | ✅ | Amount to withdraw (cents). Capped at `posted_collateral` |
| `reason` | string | | `"LiquidityRestored"`, `"EndOfDayCleanup"`, `"CostOptimization"` |

#### HoldCollateral

No change to collateral. No parameters.

---

## Context Fields

All values stored as `f64`. Boolean fields use `0.0` / `1.0`.

### Transaction Fields (payment_tree only)

| Field | Unit | Description |
|-------|------|-------------|
| `amount` | cents | Original transaction amount |
| `remaining_amount` | cents | Amount still to be settled |
| `settled_amount` | cents | Amount already settled |
| `arrival_tick` | tick | Tick when transaction entered the system |
| `deadline_tick` | tick | Latest tick for on-time settlement |
| `priority` | 0–10 | Transaction urgency |
| `is_split` | bool | Whether this is a split child |
| `is_past_deadline` | bool | `current_tick > deadline_tick` |
| `is_overdue` | bool | Persistent overdue status |
| `is_in_queue2` | bool | Transaction is in RTGS Queue 2 |
| `overdue_duration` | ticks | How long overdue |
| `ticks_to_deadline` | ticks | `deadline_tick - current_tick` (can be negative) |
| `queue_age` | ticks | `current_tick - arrival_tick` |
| `cost_delay_this_tx_one_tick` | cents | Delay cost for this tx for one tick |
| `cost_overdraft_this_amount_one_tick` | cents | Overdraft cost for this amount for one tick |

### Agent / Balance Fields

| Field | Unit | Description |
|-------|------|-------------|
| `balance` | cents | Current account balance (can be negative) |
| `credit_limit` | cents | Maximum daylight overdraft (alias: `unsecured_cap`) |
| `available_liquidity` | cents | `max(balance, 0)` |
| `credit_used` | cents | Current overdraft amount |
| `effective_liquidity` | cents | `balance + credit_headroom` — **use for affordability checks** |
| `credit_headroom` | cents | `unsecured_cap - credit_used` |
| `is_using_credit` | bool | Balance is negative |
| `liquidity_buffer` | cents | Agent's target minimum balance |
| `liquidity_pressure` | 0–1 | Normalized pressure metric |
| `is_overdraft_capped` | bool | Always 1.0 |

### Queue 1 Fields

| Field | Unit | Description |
|-------|------|-------------|
| `outgoing_queue_size` | count | Transactions in agent's Queue 1 |
| `queue1_total_value` | cents | Total value in Queue 1 |
| `queue1_liquidity_gap` | cents | `max(queue1_total_value - available_liquidity, 0)` |
| `headroom` | cents | `available_liquidity - queue1_total_value` |
| `incoming_expected_count` | count | Expected incoming payments |

### Queue 2 (RTGS) Fields

| Field | Unit | Description |
|-------|------|-------------|
| `rtgs_queue_size` / `queue2_size` | count | System-wide Queue 2 count |
| `rtgs_queue_value` | cents | System-wide Queue 2 value |
| `queue2_count_for_agent` | count | Agent's transactions in Queue 2 |
| `queue2_nearest_deadline` | tick | Nearest Queue 2 deadline for agent |
| `ticks_to_nearest_queue2_deadline` | ticks | Ticks until nearest Queue 2 deadline (∞ if none) |

### Collateral Fields

| Field | Unit | Description |
|-------|------|-------------|
| `posted_collateral` | cents | Currently posted collateral |
| `max_collateral_capacity` | cents | Maximum postable |
| `remaining_collateral_capacity` | cents | Additional capacity |
| `collateral_utilization` | 0–1 | Fraction used |
| `collateral_haircut` | 0–1 | Discount on collateral value |
| `unsecured_cap` | cents | Unsecured daylight overdraft capacity |
| `allowed_overdraft_limit` | cents | Total overdraft limit |
| `overdraft_headroom` | cents | Remaining overdraft capacity |
| `overdraft_utilization` | 0–1 | Fraction of overdraft used |
| `required_collateral_for_usage` | cents | Minimum collateral for current credit |
| `excess_collateral` | cents | Withdrawable collateral |

### Cost Rate Fields

| Field | Unit | Description |
|-------|------|-------------|
| `cost_overdraft_bps_per_tick` | bps/tick | Overdraft interest rate |
| `cost_delay_per_tick_per_cent` | cost/tick/cent | Delay penalty rate |
| `cost_collateral_bps_per_tick` | bps/tick | Collateral opportunity cost |
| `cost_split_friction` | cents | Fixed cost per split |
| `cost_deadline_penalty` | cents | One-time overdue penalty |
| `cost_eod_penalty` | cents | EOD penalty per unsettled tx |

### Time / System Fields

| Field | Unit | Description |
|-------|------|-------------|
| `current_tick` | tick | Current simulation tick |
| `system_ticks_per_day` | ticks | Ticks in a day |
| `system_current_day` | day | Current day (0-indexed) |
| `system_tick_in_day` | tick | Tick within the day |
| `ticks_remaining_in_day` | ticks | Ticks left today |
| `day_progress_fraction` | 0–1 | Progress through the day |
| `is_eod_rush` | bool | In end-of-day rush period |
| `total_agents` | count | Number of agents |

### LSM-Aware Fields (payment_tree only)

| Field | Unit | Description |
|-------|------|-------------|
| `my_q2_out_value_to_counterparty` | cents | Agent's Q2 outflows to this tx's counterparty |
| `my_q2_in_value_from_counterparty` | cents | Q2 inflows from this tx's counterparty |
| `my_bilateral_net_q2` | cents | Net Q2 position with counterparty (out − in) |
| `my_q2_out_value_top_1` … `top_5` | cents | Q2 outflows to top 5 counterparties |
| `my_q2_in_value_top_1` … `top_5` | cents | Q2 inflows from top 5 counterparties |
| `my_bilateral_net_q2_top_1` … `top_5` | cents | Net Q2 positions with top 5 |
| `tx_counterparty_id` | hash | Hash of counterparty ID |
| `tx_is_top_counterparty` | bool | Counterparty in agent's top 5 |

### Throughput / Progress Fields

| Field | Range | Description |
|-------|-------|-------------|
| `system_queue2_pressure_index` | 0–1 | System-wide Q2 pressure |
| `my_throughput_fraction_today` | 0–1 | Agent's settlement progress today |
| `expected_throughput_fraction_by_now` | 0–1 | Expected progress from guidance curve |
| `throughput_gap` | −1 to 1 | `actual − expected` (negative = behind) |

### State Registers

| Field | Description |
|-------|-------------|
| `bank_state_*` | User-defined registers. Default 0.0. Max 10 per agent. Reset at EOD. |

---

## Expression System

Expressions are boolean operations used in condition nodes.

### Comparison Operators

All comparisons follow: `{ "op": "<op>", "left": <Value>, "right": <Value> }`

| Operator | Description | Notes |
|----------|-------------|-------|
| `==` | Equal | Epsilon tolerance `1e-9` |
| `!=` | Not equal | Epsilon tolerance `1e-9` |
| `<` | Less than | Strict comparison |
| `<=` | Less than or equal | |
| `>` | Greater than | Strict comparison |
| `>=` | Greater than or equal | |

### Logical Operators

| Operator | Syntax | Description |
|----------|--------|-------------|
| `and` | `{ "op": "and", "conditions": [ ... ] }` | All must be true (short-circuit) |
| `or` | `{ "op": "or", "conditions": [ ... ] }` | Any must be true (short-circuit) |
| `not` | `{ "op": "not", "condition": { ... } }` | Inverts result |

### Example: Complex Expression

```json
{
  "op": "and",
  "conditions": [
    { "op": ">=", "left": {"field": "effective_liquidity"}, "right": {"field": "remaining_amount"} },
    { "op": "<=", "left": {"field": "ticks_to_deadline"}, "right": {"value": 10} },
    { "op": "not", "condition": { "op": "==", "left": {"field": "is_overdue"}, "right": {"value": 1} } }
  ]
}
```

---

## Value Types

Values are the building blocks of expressions and computations. All evaluate to `f64`.

| Type | JSON Syntax | Example |
|------|-------------|---------|
| **Literal** | `{"value": <number\|bool>}` | `{"value": 100000}`, `{"value": true}` → 1.0 |
| **Field** | `{"field": "<name>"}` | `{"field": "balance"}` |
| **Parameter** | `{"param": "<name>"}` | `{"param": "urgency_threshold"}` |
| **Computation** | `{"compute": { ... }}` | `{"compute": {"op": "+", "left": ..., "right": ...}}` |

Parameters are defined in the policy's `parameters` object and can be overridden at runtime:

```json
{
  "parameters": {
    "urgency_threshold": 5.0,
    "target_buffer": 100000.0
  }
}
```

**⚠️ Critical:** Arithmetic must always be wrapped in `{"compute": {...}}`.

---

## Computations

Arithmetic operations that transform values. All must be wrapped in `{"compute": {...}}`.

### Binary Operators

| Op | Syntax | Description |
|----|--------|-------------|
| `+` | `{"op": "+", "left": V, "right": V}` | Addition |
| `-` | `{"op": "-", "left": V, "right": V}` | Subtraction |
| `*` | `{"op": "*", "left": V, "right": V}` | Multiplication |
| `/` | `{"op": "/", "left": V, "right": V}` | Division (errors on ÷0) |

### N-ary Operators

| Op | Syntax | Description |
|----|--------|-------------|
| `max` | `{"op": "max", "values": [V, V, ...]}` | Maximum of list |
| `min` | `{"op": "min", "values": [V, V, ...]}` | Minimum of list |

### Unary Operators

| Op | Syntax | Description |
|----|--------|-------------|
| `ceil` | `{"op": "ceil", "value": V}` | Round up |
| `floor` | `{"op": "floor", "value": V}` | Round down |
| `round` | `{"op": "round", "value": V}` | Round to nearest |
| `abs` | `{"op": "abs", "value": V}` | Absolute value |

### Special Operators

| Op | Syntax | Description |
|----|--------|-------------|
| `clamp` | `{"op": "clamp", "value": V, "min": V, "max": V}` | Constrain to range |
| `div0` | `{"op": "div0", "numerator": V, "denominator": V, "default": V}` | Safe division (returns default on ÷0) |

### Example: Dynamic Split Count

```json
{
  "compute": {
    "op": "max",
    "values": [
      { "compute": { "op": "ceil", "value": {
        "compute": { "op": "/",
          "left": {"field": "remaining_amount"},
          "right": {"field": "effective_liquidity"}
        }
      }}},
      {"value": 2}
    ]
  }
}
```

---

## Validation Rules

Policies are validated before execution. All errors are collected (not just the first).

| Rule | Error | Description |
|------|-------|-------------|
| Unique node IDs | `DuplicateNodeId` | Every `node_id` must be unique across **all** trees |
| Tree depth ≤ 100 | `ExcessiveDepth` | Prevents stack overflow |
| Valid field refs | `InvalidFieldReference` | Fields must exist and be appropriate for the tree type |
| Valid param refs | `InvalidParameterReference` | All `{"param": "..."}` must exist in `parameters` |
| No constant ÷0 | `DivisionByZeroRisk` | Static detection of literal zero denominators |
| Reachable actions | `UnreachableAction` | All action nodes should be reachable from root |

### Best Practices

- Use `div0` instead of `/` when the denominator could be zero
- Test edge cases: empty queues, zero balance, no Queue 2 transactions
- Use descriptive `node_id` values for readable decision paths
- Validate with `payment-sim validate-policy <file>` before deployment

---

## Complete Example

A full policy with bank-level budgeting, payment decisions, and collateral management:

```json
{
  "version": "1.0",
  "policy_id": "comprehensive_example",
  "parameters": {
    "urgency_threshold": 5.0,
    "target_buffer": 100000.0,
    "pressure_limit": 0.7
  },
  "bank_tree": {
    "type": "condition",
    "node_id": "B1_CheckPressure",
    "description": "High liquidity pressure? Limit releases.",
    "condition": {
      "op": ">",
      "left": {"field": "liquidity_pressure"},
      "right": {"param": "pressure_limit"}
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
      "node_id": "B3_FullBudget",
      "action": "SetReleaseBudget",
      "parameters": {
        "max_value_to_release": {"field": "queue1_total_value"}
      }
    }
  },
  "payment_tree": {
    "type": "condition",
    "node_id": "N1_CheckUrgent",
    "description": "Is transaction near deadline?",
    "condition": {
      "op": "<=",
      "left": {"field": "ticks_to_deadline"},
      "right": {"param": "urgency_threshold"}
    },
    "on_true": {
      "type": "action",
      "node_id": "A1_ReleaseUrgent",
      "action": "Release"
    },
    "on_false": {
      "type": "condition",
      "node_id": "N2_CheckAffordability",
      "description": "Can we afford this without violating buffer?",
      "condition": {
        "op": ">=",
        "left": {
          "compute": {
            "op": "-",
            "left": {"field": "effective_liquidity"},
            "right": {"field": "remaining_amount"}
          }
        },
        "right": {"param": "target_buffer"}
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
  },
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
      "node_id": "SC2_Post",
      "action": "PostCollateral",
      "parameters": {
        "amount": {"field": "queue1_liquidity_gap"},
        "reason": {"value": "UrgentLiquidityNeed"},
        "auto_withdraw_after_ticks": {"value": 10}
      }
    },
    "on_false": {
      "type": "action",
      "node_id": "SC3_Hold",
      "action": "HoldCollateral"
    }
  },
  "end_of_tick_collateral_tree": {
    "type": "condition",
    "node_id": "EOT1_CheckExcess",
    "description": "Withdraw excess collateral to reduce cost.",
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
