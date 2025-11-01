# Payment Simulator - Policy DSL Guide

## Introduction

This guide covers the **JSON Decision Tree DSL** - a declarative language for defining payment settlement policies without writing code. The DSL enables rapid iteration, safe editing, and clear logic expression for banking agent strategies.

**What This Guide Covers:**
- Complete JSON DSL syntax reference
- All available data fields and computations
- Payment, strategic collateral, and end-of-tick collateral trees
- Advanced features: cost optimization, time-based strategies, dynamic parameters
- Real-world examples and patterns

**Who This Is For:**
- Researchers designing agent strategies
- Simulation operators configuring scenarios
- AI/LLM agents editing policies safely
- Anyone who wants to avoid Rust compilation

---

## Table of Contents

1. [Quick Start](#quick-start)
2. [Core Concepts](#core-concepts)
3. [JSON Schema Reference](#json-schema-reference)
4. [Available Data Reference](#available-data-reference)
5. [Decision Tree Patterns](#decision-tree-patterns)
6. [Advanced Features](#advanced-features)
7. [Complete Examples](#complete-examples)
8. [Best Practices](#best-practices)
9. [Troubleshooting](#troubleshooting)

---

## Quick Start

### Your First Policy

Create a file `backend/policies/my_first_policy.json`:

```json
{
  "version": "1.0",
  "policy_id": "my_first_policy",
  "description": "Release urgent payments immediately, hold others",
  "payment_tree": {
    "type": "condition",
    "node_id": "root",
    "condition": {
      "op": "<=",
      "left": {"field": "ticks_to_deadline"},
      "right": {"value": 5.0}
    },
    "on_true": {
      "type": "action",
      "node_id": "release",
      "action": "Release"
    },
    "on_false": {
      "type": "action",
      "node_id": "hold",
      "action": "Hold",
      "parameters": {
        "reason": {"value": "NotUrgent"}
      }
    }
  }
}
```

**What This Does:**
- If transaction deadline is ≤5 ticks away → Release it
- Otherwise → Hold it in the queue

**How to Use It:**
Reference it in your simulation config:
```yaml
agents:
  - id: BANK_A
    policy:
      type: tree
      path: "my_first_policy.json"
```

The system automatically loads JSON files from `backend/policies/`.

---

## Core Concepts

### The Three Decision Trees

Every policy JSON can define up to three decision trees:

1. **`payment_tree`** (required)
   - **When**: Evaluated for each transaction in Queue 1 at Step 2 of the tick loop
   - **Purpose**: Decide whether to submit, hold, split, or drop transactions
   - **Returns**: `Release`, `Hold`, `Drop`, `Split`, or `PaceAndRelease` actions

2. **`strategic_collateral_tree`** (optional)
   - **When**: Evaluated once per agent at Step 1.5 (before settlements)
   - **Purpose**: Forward-looking collateral management (e.g., "post collateral to prepare for upcoming payments")
   - **Returns**: `PostCollateral`, `WithdrawCollateral`, or `HoldCollateral` actions

3. **`end_of_tick_collateral_tree`** (optional)
   - **When**: Evaluated once per agent at Step 5.5 (after all settlements)
   - **Purpose**: Reactive collateral management (e.g., "withdraw excess collateral at end of day")
   - **Returns**: `PostCollateral`, `WithdrawCollateral`, or `HoldCollateral` actions

### Node Types

Every tree is built from two types of nodes:

#### 1. Condition Node (Branch)
An `if/then/else` decision point:

```json
{
  "type": "condition",
  "node_id": "unique_identifier",
  "description": "Optional human-readable description",
  "condition": { /* Expression */ },
  "on_true": { /* TreeNode */ },
  "on_false": { /* TreeNode */ }
}
```

#### 2. Action Node (Leaf)
A terminal decision that returns an action:

```json
{
  "type": "action",
  "node_id": "unique_identifier",
  "action": "Release",
  "parameters": { /* Optional action-specific parameters */ }
}
```

### Evaluation Flow

1. Start at the root node of the tree
2. If it's a **condition node**:
   - Evaluate the condition expression
   - If true, recursively evaluate `on_true` subtree
   - If false, recursively evaluate `on_false` subtree
3. If it's an **action node**:
   - Return the action with its parameters
   - Stop evaluation for this transaction/agent

---

## JSON Schema Reference

### Root Object

```json
{
  "version": "1.0",                    // Schema version (currently "1.0")
  "policy_id": "unique_policy_name",   // Unique identifier
  "description": "What this policy does", // Optional
  "parameters": {                       // Default parameter values
    "urgency_threshold": 5.0,
    "target_buffer": 100000.0
  },
  "payment_tree": { /* TreeNode */ },           // Required
  "strategic_collateral_tree": { /* TreeNode */ }, // Optional
  "end_of_tick_collateral_tree": { /* TreeNode */ } // Optional
}
```

**Key Points:**
- `policy_id` must be unique across all policies
- `parameters` can be overridden in simulation config
- At least `payment_tree` must be defined

### Parameters

Parameters are default values that can be referenced in expressions and overridden per agent:

```json
"parameters": {
  "urgency_threshold": 5.0,
  "min_buffer": 50000.0,
  "max_splits": 4.0,
  "collateral_safety_margin": 1.2
}
```

**Usage in Trees:**
```json
{"param": "urgency_threshold"}  // References the parameter value
```

**Override in Config:**
```yaml
agents:
  - id: BANK_A
    policy:
      type: tree
      path: "my_policy.json"
      params:
        urgency_threshold: 10.0  # Override default 5.0
```

### TreeNode

A `TreeNode` is either a condition or an action.

#### Condition Node Schema

```json
{
  "type": "condition",
  "node_id": "N1",              // Unique within this tree
  "description": "Check urgency", // Optional
  "condition": {
    "op": "<=",
    "left": {"field": "ticks_to_deadline"},
    "right": {"value": 5.0}
  },
  "on_true": { /* TreeNode */ },
  "on_false": { /* TreeNode */ }
}
```

#### Action Node Schema

```json
{
  "type": "action",
  "node_id": "A1",
  "action": "Release",  // ActionType (see below)
  "parameters": {       // Optional action-specific parameters
    "reason": {"value": "Urgent"}
  }
}
```

### Expression (Conditions)

Expressions evaluate to boolean values. Supported operators:

#### Comparison Operators

```json
{
  "op": "==",  // Equal
  "left": {"field": "priority"},
  "right": {"value": 10.0}
}

{
  "op": "!=",  // Not equal
  "left": {"field": "is_split"},
  "right": {"value": 0.0}
}

{
  "op": "<",   // Less than
  "left": {"field": "balance"},
  "right": {"value": 100000.0}
}

{
  "op": "<=",  // Less than or equal
  "left": {"field": "ticks_to_deadline"},
  "right": {"param": "urgency_threshold"}
}

{
  "op": ">",   // Greater than
  "left": {"field": "available_liquidity"},
  "right": {"field": "amount"}
}

{
  "op": ">=",  // Greater than or equal
  "left": {"field": "queue_age"},
  "right": {"value": 10.0}
}
```

#### Logical Operators

```json
{
  "op": "and",
  "conditions": [
    {"op": "<", "left": {"field": "balance"}, "right": {"value": 0.0}},
    {"op": ">", "left": {"field": "priority"}, "right": {"value": 5.0}}
  ]
}

{
  "op": "or",
  "conditions": [
    {"op": "<=", "left": {"field": "ticks_to_deadline"}, "right": {"value": 5.0}},
    {"op": "==", "left": {"field": "is_past_deadline"}, "right": {"value": 1.0}}
  ]
}

{
  "op": "not",
  "condition": {
    "op": "==",
    "left": {"field": "is_using_credit"},
    "right": {"value": 1.0}
  }
}
```

**Note:** `and` and `or` use `"conditions"` (array), while `not` uses `"condition"` (single object).

### Value

A `Value` retrieves data for comparison or computation. Four types:

#### 1. Field Reference
Get a value from the evaluation context:

```json
{"field": "balance"}
{"field": "ticks_to_deadline"}
{"field": "cost_overdraft_bps_per_tick"}
```

See [Available Data Reference](#available-data-reference) for all fields.

#### 2. Parameter Reference
Get a value from the policy's `parameters`:

```json
{"param": "urgency_threshold"}
{"param": "target_buffer"}
```

#### 3. Literal Value
A constant number:

```json
{"value": 100000.0}
{"value": 5.0}
{"value": 0.0}
{"value": 1.0}  // Also used for boolean true
```

**Boolean Convention:**
- `1.0` = true
- `0.0` = false

#### 4. Computation
Perform arithmetic (see next section):

```json
{
  "compute": {
    "op": "+",
    "left": {"field": "balance"},
    "right": {"field": "credit_limit"}
  }
}
```

### Computation

Computations perform arithmetic on values. Supported operators:

#### Binary Arithmetic

```json
{
  "op": "+",  // Addition
  "left": {"field": "balance"},
  "right": {"field": "credit_limit"}
}

{
  "op": "-",  // Subtraction
  "left": {"field": "queue1_total_value"},
  "right": {"field": "available_liquidity"}
}

{
  "op": "*",  // Multiplication
  "left": {"field": "amount"},
  "right": {"value": 1.5}
}

{
  "op": "/",  // Division
  "left": {"field": "balance"},
  "right": {"value": 2.0}
}
```

#### N-ary Functions

```json
{
  "op": "max",  // Maximum of values
  "values": [
    {"field": "queue1_liquidity_gap"},
    {"value": 0.0},
    {"field": "posted_collateral"}
  ]
}

{
  "op": "min",  // Minimum of values
  "values": [
    {"field": "available_liquidity"},
    {"field": "amount"}
  ]
}
```

#### Nested Computations

Computations can be nested arbitrarily:

```json
{
  "compute": {
    "op": "*",
    "left": {"field": "amount"},
    "right": {
      "compute": {
        "op": "+",
        "left": {"value": 1.0},
        "right": {
          "compute": {
            "op": "*",
            "left": {"field": "day_progress_fraction"},
            "right": {"value": 0.5}
          }
        }
      }
    }
  }
}
```

**This computes:** `amount * (1.0 + (day_progress_fraction * 0.5))`

### ActionType

Actions are the terminal decisions returned by action nodes.

#### Payment Actions

Used in `payment_tree`:

##### Release
Submit the full transaction to Queue 2 (RTGS):

```json
{
  "type": "action",
  "node_id": "A1",
  "action": "Release"
}
```

##### Hold
Keep the transaction in Queue 1 (will be re-evaluated next tick):

```json
{
  "type": "action",
  "node_id": "A2",
  "action": "Hold",
  "parameters": {
    "reason": {"value": "InsufficientLiquidity"}
  }
}
```

**Common reasons:** `"InsufficientLiquidity"`, `"WaitingForIncoming"`, `"NotUrgent"`, `"CostOptimization"`

##### Drop
Remove the transaction from the simulation:

```json
{
  "type": "action",
  "node_id": "A3",
  "action": "Drop"
}
```

**Use case:** Transaction has expired or is invalid.

##### Split / PaceAndRelease
Split the transaction into N smaller "child" transactions and submit all to Queue 2:

```json
{
  "type": "action",
  "node_id": "A4",
  "action": "Split",
  "parameters": {
    "num_splits": {"value": 4.0}
  }
}
```

**Dynamic splits** using computation:

```json
{
  "type": "action",
  "node_id": "A5",
  "action": "PaceAndRelease",
  "parameters": {
    "num_splits": {
      "compute": {
        "op": "/",
        "left": {"field": "amount"},
        "right": {"value": 50000.0}
      }
    }
  }
}
```

**Note:** `Split` and `PaceAndRelease` are synonyms.

#### Collateral Actions

Used in `strategic_collateral_tree` and `end_of_tick_collateral_tree`:

##### PostCollateral
Post collateral to increase credit capacity:

```json
{
  "type": "action",
  "node_id": "SC1",
  "action": "PostCollateral",
  "parameters": {
    "amount": {"value": 200000.0},
    "reason": {"value": "StrategicReserve"}
  }
}
```

**Dynamic amount:**

```json
{
  "type": "action",
  "node_id": "SC2",
  "action": "PostCollateral",
  "parameters": {
    "amount": {
      "compute": {
        "op": "max",
        "values": [
          {"field": "queue1_liquidity_gap"},
          {"value": 0.0}
        ]
      }
    },
    "reason": {"value": "CoverLiquidityGap"}
  }
}
```

##### WithdrawCollateral
Withdraw collateral to reduce opportunity cost:

```json
{
  "type": "action",
  "node_id": "EC1",
  "action": "WithdrawCollateral",
  "parameters": {
    "amount": {"value": 100000.0},
    "reason": {"value": "ReduceCost"}
  }
}
```

##### HoldCollateral
Do nothing (no collateral action this tick):

```json
{
  "type": "action",
  "node_id": "SC3",
  "action": "HoldCollateral"
}
```

---

## Available Data Reference

When a tree is evaluated, you have access to 60+ fields from the simulation state. Use these in `{"field": "name"}` references.

### Transaction Fields

| Field | Type | Description |
|:------|:-----|:------------|
| `amount` | `f64` (cents) | Original transaction amount |
| `remaining_amount` | `f64` (cents) | Amount left to settle (for split children) |
| `settled_amount` | `f64` (cents) | Amount already settled (for splits) |
| `arrival_tick` | `f64` | Tick when transaction entered Queue 1 |
| `deadline_tick` | `f64` | Deadline tick for settlement |
| `priority` | `f64` | Priority level (0-10, higher = more urgent) |
| `is_split` | `f64` (bool) | `1.0` if this is a split child, `0.0` otherwise |
| `is_past_deadline` | `f64` (bool) | `1.0` if deadline missed, `0.0` otherwise |

### Derived Transaction Fields

| Field | Type | Description |
|:------|:-----|:------------|
| `ticks_to_deadline` | `f64` | `deadline_tick - current_tick` (can be negative) |
| `queue_age` | `f64` | `current_tick - arrival_tick` |

### Agent Balance Fields

| Field | Type | Description |
|:------|:-----|:------------|
| `balance` | `f64` (cents) | Agent's current settlement account balance |
| `credit_limit` | `f64` (cents) | Maximum overdraft allowed |
| `available_liquidity` | `f64` (cents) | `balance + credit_limit + posted_collateral` |
| `credit_used` | `f64` (cents) | Amount of overdraft currently in use |
| `is_using_credit` | `f64` (bool) | `1.0` if `balance < 0`, `0.0` otherwise |
| `liquidity_buffer` | `f64` (cents) | Configured soft target minimum balance |

### Agent Queue Fields

| Field | Type | Description |
|:------|:-----|:------------|
| `outgoing_queue_size` | `f64` | Number of transactions in Queue 1 |
| `incoming_expected_count` | `f64` | Number of incoming payments expected |
| `liquidity_pressure` | `f64` (0-1) | Stress metric: `1.0` = max stress, `0.0` = comfortable |

### Collateral Fields

| Field | Type | Description |
|:------|:-----|:------------|
| `posted_collateral` | `f64` (cents) | Collateral currently posted |
| `max_collateral_capacity` | `f64` (cents) | Maximum collateral agent can post |
| `remaining_collateral_capacity` | `f64` (cents) | `max_capacity - posted_collateral` |
| `collateral_utilization` | `f64` (0-1) | `posted_collateral / max_collateral_capacity` |
| `queue1_total_value` | `f64` (cents) | Total value of all Queue 1 items |
| `queue1_liquidity_gap` | `f64` (cents) | `max(queue1_total_value - available_liquidity, 0)` |
| `headroom` | `f64` (cents) | `available_liquidity - queue1_total_value` |

### Queue 2 (RTGS) Fields

| Field | Type | Description |
|:------|:-----|:------------|
| `queue2_count_for_agent` | `f64` | Number of this agent's items in Queue 2 |
| `queue2_nearest_deadline` | `f64` | Nearest deadline tick in Queue 2 for this agent |
| `ticks_to_nearest_queue2_deadline` | `f64` | Ticks until nearest Queue 2 deadline (INFINITY if empty) |

### Cost Rate Fields (Phase 9.5.1)

These are the configured cost parameters from `CostRates`:

| Field | Type | Description |
|:------|:-----|:------------|
| `cost_overdraft_bps_per_tick` | `f64` | Overdraft cost in basis points per tick |
| `cost_delay_per_tick_per_cent` | `f64` | Delay cost per tick per cent of transaction value |
| `cost_collateral_bps_per_tick` | `f64` | Collateral opportunity cost in bps per tick |
| `cost_split_friction` | `f64` (cents) | Fixed cost per split operation |
| `cost_deadline_penalty` | `f64` (cents) | Penalty for missing a deadline |
| `cost_eod_penalty` | `f64` (cents) | End-of-day penalty per unsettled transaction |

### Derived Cost Fields (Phase 9.5.1)

Pre-calculated costs for the current transaction:

| Field | Type | Description |
|:------|:-----|:------------|
| `cost_delay_this_tx_one_tick` | `f64` (cents) | Cost of delaying THIS transaction by 1 tick |
| `cost_overdraft_this_amount_one_tick` | `f64` (cents) | Cost of overdraft for THIS amount for 1 tick |

**Example calculation:**
- If `remaining_amount = 100000` (cents) and `cost_delay_per_tick_per_cent = 0.01`
- Then `cost_delay_this_tx_one_tick = 100000 * 0.01 / 100 = 10.0` cents

### Time-of-Day Fields (Phase 9.5.2)

System-level time configuration:

| Field | Type | Description |
|:------|:-----|:------------|
| `system_ticks_per_day` | `f64` | Number of ticks in a simulation day |
| `system_current_day` | `f64` | Current day number (0-indexed) |
| `system_tick_in_day` | `f64` | Current tick within day (0 to ticks_per_day-1) |
| `ticks_remaining_in_day` | `f64` | Ticks remaining in current day |
| `day_progress_fraction` | `f64` (0-1) | Progress through day: `0.0` = start, `1.0` = end |
| `is_eod_rush` | `f64` (bool) | `1.0` if in EOD rush period, `0.0` otherwise |

**EOD Rush:**
- Configurable threshold (default: last 20% of day)
- Example: With `ticks_per_day = 100`, rush starts at tick 80
- Use for aggressive end-of-day strategies

### System-Wide Fields

| Field | Type | Description |
|:------|:-----|:------------|
| `current_tick` | `f64` | Current simulation tick |
| `rtgs_queue_size` | `f64` | Total items in Queue 2 (all agents) |
| `rtgs_queue_value` | `f64` (cents) | Total value in Queue 2 (all agents) |
| `total_agents` | `f64` | Number of agents in simulation |

---

## Decision Tree Patterns

Common patterns for building effective policies.

### Pattern 1: Urgency Check

**Goal:** Release urgent payments immediately, apply other logic to non-urgent.

```json
{
  "type": "condition",
  "node_id": "N1_Urgency",
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
    "node_id": "N2_OtherLogic",
    "condition": { /* ... */ },
    "on_true": { /* ... */ },
    "on_false": { /* ... */ }
  }
}
```

### Pattern 2: Liquidity Buffer Check

**Goal:** Maintain minimum liquidity buffer, only release if buffer remains.

```json
{
  "type": "condition",
  "node_id": "N1_BufferCheck",
  "description": "Check if liquidity remains above buffer after payment",
  "condition": {
    "op": ">=",
    "left": {"field": "available_liquidity"},
    "right": {
      "compute": {
        "op": "+",
        "left": {"field": "remaining_amount"},
        "right": {"param": "target_buffer"}
      }
    }
  },
  "on_true": {
    "type": "action",
    "node_id": "A1_ReleaseSafe",
    "action": "Release"
  },
  "on_false": {
    "type": "action",
    "node_id": "A2_Hold",
    "action": "Hold",
    "parameters": {
      "reason": {"value": "BufferProtection"}
    }
  }
}
```

### Pattern 3: Combined AND Logic

**Goal:** Release only if BOTH conditions are true.

```json
{
  "type": "condition",
  "node_id": "N1_BothRequired",
  "condition": {
    "op": "and",
    "conditions": [
      {
        "op": ">=",
        "left": {"field": "available_liquidity"},
        "right": {"field": "remaining_amount"}
      },
      {
        "op": ">",
        "left": {"field": "priority"},
        "right": {"value": 5.0}
      }
    ]
  },
  "on_true": {
    "type": "action",
    "node_id": "A1_Release",
    "action": "Release"
  },
  "on_false": {
    "type": "action",
    "node_id": "A2_Hold",
    "action": "Hold",
    "parameters": {
      "reason": {"value": "RequiresBothConditions"}
    }
  }
}
```

### Pattern 4: Fallback OR Logic

**Goal:** Release if ANY condition is true.

```json
{
  "type": "condition",
  "node_id": "N1_AnyTrigger",
  "condition": {
    "op": "or",
    "conditions": [
      {
        "op": "<=",
        "left": {"field": "ticks_to_deadline"},
        "right": {"value": 3.0}
      },
      {
        "op": "==",
        "left": {"field": "is_past_deadline"},
        "right": {"value": 1.0}
      },
      {
        "op": ">=",
        "left": {"field": "priority"},
        "right": {"value": 9.0}
      }
    ]
  },
  "on_true": {
    "type": "action",
    "node_id": "A1_Release",
    "action": "Release"
  },
  "on_false": {
    "type": "action",
    "node_id": "A2_EvaluateFurther",
    "action": "Hold",
    "parameters": {
      "reason": {"value": "NoTriggerMet"}
    }
  }
}
```

### Pattern 5: Graduated Response

**Goal:** Different actions based on ranges (e.g., urgency levels).

```json
{
  "type": "condition",
  "node_id": "N1_VeryUrgent",
  "description": "Immediate action needed",
  "condition": {
    "op": "<=",
    "left": {"field": "ticks_to_deadline"},
    "right": {"value": 2.0}
  },
  "on_true": {
    "type": "action",
    "node_id": "A1_ReleaseNow",
    "action": "Release"
  },
  "on_false": {
    "type": "condition",
    "node_id": "N2_ModerateUrgency",
    "description": "Some urgency, split if large",
    "condition": {
      "op": "<=",
      "left": {"field": "ticks_to_deadline"},
      "right": {"value": 10.0}
    },
    "on_true": {
      "type": "condition",
      "node_id": "N3_CheckSize",
      "condition": {
        "op": ">",
        "left": {"field": "remaining_amount"},
        "right": {"value": 200000.0}
      },
      "on_true": {
        "type": "action",
        "node_id": "A2_Split",
        "action": "Split",
        "parameters": {
          "num_splits": {"value": 4.0}
        }
      },
      "on_false": {
        "type": "action",
        "node_id": "A3_ReleaseFull",
        "action": "Release"
      }
    },
    "on_false": {
      "type": "action",
      "node_id": "A4_HoldNonUrgent",
      "action": "Hold",
      "parameters": {
        "reason": {"value": "NotUrgent"}
      }
    }
  }
}
```

### Pattern 6: Strategic Collateral Posting

**Goal:** Post collateral when liquidity gap exists.

```json
{
  "type": "condition",
  "node_id": "SC1_CheckGap",
  "description": "Post collateral if gap exists",
  "condition": {
    "op": ">",
    "left": {"field": "queue1_liquidity_gap"},
    "right": {"value": 0.0}
  },
  "on_true": {
    "type": "condition",
    "node_id": "SC2_CheckCapacity",
    "description": "Ensure capacity available",
    "condition": {
      "op": ">",
      "left": {"field": "remaining_collateral_capacity"},
      "right": {"value": 0.0}
    },
    "on_true": {
      "type": "action",
      "node_id": "SC_Post",
      "action": "PostCollateral",
      "parameters": {
        "amount": {
          "compute": {
            "op": "min",
            "values": [
              {"field": "queue1_liquidity_gap"},
              {"field": "remaining_collateral_capacity"}
            ]
          }
        },
        "reason": {"value": "CoverGap"}
      }
    },
    "on_false": {
      "type": "action",
      "node_id": "SC_Hold",
      "action": "HoldCollateral"
    }
  },
  "on_false": {
    "type": "action",
    "node_id": "SC_Hold2",
    "action": "HoldCollateral"
  }
}
```

---

## Advanced Features

### Cost-Aware Optimization (Phase 9.5.1)

Make economic trade-off decisions by comparing costs.

#### Example: Delay vs. Overdraft Decision

```json
{
  "type": "condition",
  "node_id": "N1_CostDecision",
  "description": "Hold if delay is cheaper than using overdraft",
  "condition": {
    "op": "<",
    "left": {"field": "cost_delay_this_tx_one_tick"},
    "right": {"field": "cost_overdraft_this_amount_one_tick"}
  },
  "on_true": {
    "type": "action",
    "node_id": "A1_HoldCheaper",
    "action": "Hold",
    "parameters": {
      "reason": {"value": "DelayMoreEconomical"}
    }
  },
  "on_false": {
    "type": "action",
    "node_id": "A2_ReleaseWithCredit",
    "action": "Release"
  }
}
```

**When to use:**
- Balance is negative (using overdraft)
- Transaction is not past deadline
- You want to minimize total costs

**Cost fields available:**
- `cost_overdraft_bps_per_tick` - Base overdraft rate
- `cost_delay_per_tick_per_cent` - Base delay rate
- `cost_overdraft_this_amount_one_tick` - Calculated for this specific amount
- `cost_delay_this_tx_one_tick` - Calculated for this specific transaction
- `cost_deadline_penalty` - One-time penalty for missing deadline
- `cost_eod_penalty` - One-time penalty per unsettled transaction at EOD

#### Example: Deadline Penalty Threshold

```json
{
  "type": "condition",
  "node_id": "N1_PenaltyVsOverdraft",
  "description": "Accept deadline penalty if overdraft costs more",
  "condition": {
    "op": "<",
    "left": {"field": "cost_deadline_penalty"},
    "right": {
      "compute": {
        "op": "*",
        "left": {"field": "cost_overdraft_this_amount_one_tick"},
        "right": {"field": "ticks_to_deadline"}
      }
    }
  },
  "on_true": {
    "type": "action",
    "node_id": "A1_AcceptPenalty",
    "action": "Hold",
    "parameters": {
      "reason": {"value": "PenaltyCheaperThanCredit"}
    }
  },
  "on_false": {
    "type": "action",
    "node_id": "A2_AvoidPenalty",
    "action": "Release"
  }
}
```

**Logic:** If deadline penalty is less than `(overdraft_cost * ticks_remaining)`, accept the penalty.

### Time-Based Strategies (Phase 9.5.2)

Adapt behavior based on time of day and EOD rush.

#### Example: Progressive Aggression

```json
{
  "type": "condition",
  "node_id": "N1_EODCheck",
  "description": "Three-phase strategy based on time of day",
  "condition": {
    "op": "==",
    "left": {"field": "is_eod_rush"},
    "right": {"value": 1.0}
  },
  "on_true": {
    "type": "action",
    "node_id": "A1_PanicRelease",
    "action": "Release",
    "comment": "EOD rush: release everything to avoid EOD penalty"
  },
  "on_false": {
    "type": "condition",
    "node_id": "N2_TimeCheck",
    "description": "Check if in late day (60-80%)",
    "condition": {
      "op": ">=",
      "left": {"field": "day_progress_fraction"},
      "right": {"value": 0.6}
    },
    "on_true": {
      "type": "action",
      "node_id": "A2_AggressiveLate",
      "action": "Release",
      "comment": "Late day: be aggressive"
    },
    "on_false": {
      "type": "condition",
      "node_id": "N3_LiquidityCheck",
      "description": "Early day: conservative with buffer",
      "condition": {
        "op": ">=",
        "left": {"field": "available_liquidity"},
        "right": {
          "compute": {
            "op": "*",
            "left": {"field": "remaining_amount"},
            "right": {"value": 1.5}
          }
        }
      },
      "on_true": {
        "type": "action",
        "node_id": "A3_ConservativeRelease",
        "action": "Release"
      },
      "on_false": {
        "type": "action",
        "node_id": "A4_Hold",
        "action": "Hold",
        "parameters": {
          "reason": {"value": "ConservativeEarlyDay"}
        }
      }
    }
  }
}
```

**Strategy breakdown:**
- **0-60% of day:** Conservative (require 1.5x liquidity buffer)
- **60-80% of day:** Aggressive (release if any liquidity)
- **80-100% of day (EOD rush):** Panic mode (release everything)

#### Example: Time-Decaying Buffer

```json
{
  "condition": {
    "op": ">=",
    "left": {"field": "available_liquidity"},
    "right": {
      "compute": {
        "op": "*",
        "left": {"field": "remaining_amount"},
        "right": {
          "compute": {
            "op": "-",
            "left": {"value": 2.0},
            "right": {"field": "day_progress_fraction"}
          }
        }
      }
    }
  }
}
```

**Logic:**
- At 0% of day: require `amount * 2.0x` buffer (very conservative)
- At 50% of day: require `amount * 1.5x` buffer
- At 100% of day: require `amount * 1.0x` buffer (no buffer)

### Dynamic Action Parameters (Phase 9.5.3)

Compute action parameters based on context instead of using fixed values.

#### Example: Dynamic Split Count

```json
{
  "type": "action",
  "node_id": "A1_AdaptiveSplit",
  "action": "Split",
  "parameters": {
    "num_splits": {
      "compute": {
        "op": "/",
        "left": {"field": "remaining_amount"},
        "right": {"value": 50000.0}
      }
    }
  }
}
```

**Logic:** Split into chunks of 50,000 cents each. If amount is 200,000, splits into 4 pieces.

**Important:** The computed value will be rounded to an integer (e.g., 3.7 → 4).

#### Example: Percentage-Based Collateral

```json
{
  "type": "action",
  "node_id": "SC1_PercentageCollateral",
  "action": "PostCollateral",
  "parameters": {
    "amount": {
      "compute": {
        "op": "*",
        "left": {"field": "queue1_total_value"},
        "right": {"value": 0.2}
      }
    },
    "reason": {"value": "20PercentOfQueue"}
  }
}
```

**Logic:** Post collateral equal to 20% of total Queue 1 value.

#### Example: Collateral Gap with Safety Margin

```json
{
  "type": "action",
  "node_id": "SC2_GapWithMargin",
  "action": "PostCollateral",
  "parameters": {
    "amount": {
      "compute": {
        "op": "*",
        "left": {
          "compute": {
            "op": "max",
            "values": [
              {"field": "queue1_liquidity_gap"},
              {"value": 0.0}
            ]
          }
        },
        "right": {"param": "safety_margin"}
      }
    },
    "reason": {"value": "GapPlusSafetyMargin"}
  }
}
```

**Logic:** Post `liquidity_gap * 1.2` (if `safety_margin` parameter is 1.2).

### Combined Advanced Example: Sophisticated EOD Strategy

```json
{
  "type": "condition",
  "node_id": "N1_EODRush",
  "description": "EOD rush: aggressive multi-phase strategy",
  "condition": {
    "op": "==",
    "left": {"field": "is_eod_rush"},
    "right": {"value": 1.0}
  },
  "on_true": {
    "type": "condition",
    "node_id": "N2_DeadlineCheck",
    "description": "Prioritize near-deadline items",
    "condition": {
      "op": "<=",
      "left": {"field": "ticks_to_deadline"},
      "right": {"value": 5.0}
    },
    "on_true": {
      "type": "condition",
      "node_id": "N3_CostDecision",
      "description": "Use credit if cheaper than deadline penalty",
      "condition": {
        "op": "<",
        "left": {
          "compute": {
            "op": "*",
            "left": {"field": "cost_overdraft_this_amount_one_tick"},
            "right": {"field": "ticks_to_deadline"}
          }
        },
        "right": {"field": "cost_deadline_penalty"}
      },
      "on_true": {
        "type": "action",
        "node_id": "A1_ReleaseWithCredit",
        "action": "Release",
        "comment": "EOD + urgent + credit cheaper: go for it"
      },
      "on_false": {
        "type": "action",
        "node_id": "A2_AcceptPenalty",
        "action": "Hold",
        "parameters": {
          "reason": {"value": "PenaltyCheaper"}
        }
      }
    },
    "on_false": {
      "type": "action",
      "node_id": "A3_ReleaseEOD",
      "action": "Release",
      "comment": "EOD but not immediately urgent: release anyway"
    }
  },
  "on_false": {
    "type": "action",
    "node_id": "A4_NormalStrategy",
    "action": "Hold",
    "parameters": {
      "reason": {"value": "NotEOD"}
    }
  }
}
```

**Combined logic:**
- If EOD rush AND near deadline AND credit costs less than penalty → Release
- If EOD rush AND near deadline BUT penalty cheaper → Hold (accept penalty)
- If EOD rush BUT not near deadline → Release anyway (general EOD aggression)
- If not EOD rush → Hold (use normal strategy)

---

## Complete Examples

### Example 1: Simple Urgency-Based Policy

**File:** `backend/policies/simple_urgency.json`

```json
{
  "version": "1.0",
  "policy_id": "simple_urgency",
  "description": "Release urgent, hold non-urgent",
  "payment_tree": {
    "type": "condition",
    "node_id": "N1",
    "condition": {
      "op": "<=",
      "left": {"field": "ticks_to_deadline"},
      "right": {"param": "urgency_threshold"}
    },
    "on_true": {
      "type": "action",
      "node_id": "A1",
      "action": "Release"
    },
    "on_false": {
      "type": "action",
      "node_id": "A2",
      "action": "Hold",
      "parameters": {
        "reason": {"value": "NotUrgent"}
      }
    }
  },
  "parameters": {
    "urgency_threshold": 5.0
  }
}
```

### Example 2: Liquidity-Aware Policy

**File:** `backend/policies/liquidity_aware.json`

```json
{
  "version": "1.0",
  "policy_id": "liquidity_aware_policy",
  "description": "Releases if urgent or if balance remains above target buffer",
  "payment_tree": {
    "type": "condition",
    "node_id": "N1_IsUrgent",
    "description": "Check if transaction is urgent (near deadline)",
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
      "node_id": "N2_CheckBuffer",
      "description": "Not urgent. Check if we have enough liquidity",
      "condition": {
        "op": ">=",
        "left": {"field": "available_liquidity"},
        "right": {
          "compute": {
            "op": "+",
            "left": {"field": "amount"},
            "right": {"param": "target_buffer"}
          }
        }
      },
      "on_true": {
        "type": "action",
        "node_id": "A2_ReleaseSafe",
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
  "parameters": {
    "urgency_threshold": 5.0,
    "target_buffer": 100000.0
  }
}
```

### Example 3: Splitting Policy

**File:** `backend/policies/liquidity_splitting.json`

```json
{
  "version": "1.0",
  "policy_id": "liquidity_splitting",
  "description": "Split large payments, release small ones",
  "payment_tree": {
    "type": "condition",
    "node_id": "N1_IsLarge",
    "description": "Check if payment is large",
    "condition": {
      "op": ">",
      "left": {"field": "remaining_amount"},
      "right": {"param": "split_threshold"}
    },
    "on_true": {
      "type": "action",
      "node_id": "A1_Split",
      "action": "PaceAndRelease",
      "parameters": {
        "num_splits": {"param": "num_splits"}
      }
    },
    "on_false": {
      "type": "condition",
      "node_id": "N2_CheckLiquidity",
      "description": "Small payment: check liquidity",
      "condition": {
        "op": ">=",
        "left": {"field": "available_liquidity"},
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
  },
  "parameters": {
    "split_threshold": 200000.0,
    "num_splits": 4.0
  }
}
```

### Example 4: Cost-Optimizing Policy

**File:** `backend/policies/cost_optimizer.json`

```json
{
  "version": "1.0",
  "policy_id": "cost_optimizer",
  "description": "Make economic trade-offs between delay and overdraft costs",
  "payment_tree": {
    "type": "condition",
    "node_id": "N1_Urgent",
    "description": "Release if urgent regardless of cost",
    "condition": {
      "op": "<=",
      "left": {"field": "ticks_to_deadline"},
      "right": {"value": 3.0}
    },
    "on_true": {
      "type": "action",
      "node_id": "A1_ReleaseUrgent",
      "action": "Release"
    },
    "on_false": {
      "type": "condition",
      "node_id": "N2_HasLiquidity",
      "description": "Release immediately if have liquidity",
      "condition": {
        "op": ">=",
        "left": {"field": "available_liquidity"},
        "right": {"field": "remaining_amount"}
      },
      "on_true": {
        "type": "action",
        "node_id": "A2_ReleaseSafe",
        "action": "Release"
      },
      "on_false": {
        "type": "condition",
        "node_id": "N3_CostDecision",
        "description": "Hold if delay cheaper than overdraft",
        "condition": {
          "op": "<",
          "left": {"field": "cost_delay_this_tx_one_tick"},
          "right": {"field": "cost_overdraft_this_amount_one_tick"}
        },
        "on_true": {
          "type": "action",
          "node_id": "A3_HoldCheaper",
          "action": "Hold",
          "parameters": {
            "reason": {"value": "DelayMoreEconomical"}
          }
        },
        "on_false": {
          "type": "action",
          "node_id": "A4_UseCredit",
          "action": "Release"
        }
      }
    }
  }
}
```

### Example 5: Comprehensive Adaptive Policy

**File:** `backend/policies/adaptive_liquidity_manager.json`

This is a full 370-line policy demonstrating all Phase 9.5 features. Key sections:

**Payment Tree Strategy:**
1. **EOD Rush Priority (lines 8-98):** Aggressive release during last 20% of day
2. **Urgent Deadline Handling (lines 99-150):** Cost-based credit decisions for near-deadline payments
3. **Time-Based Strategies (lines 151-218):** Progressive aggression throughout the day

**Strategic Collateral Tree (lines 219-298):**
- Detects EOD liquidity gaps
- Posts dynamic collateral amounts based on `queue1_liquidity_gap`
- Uses safety margins

**End-of-Tick Collateral Tree (lines 299-368):**
- Withdraws excess collateral when headroom detected
- Cost-benefit analysis (collateral cost vs. benefit)

**See the full file at:** `backend/policies/adaptive_liquidity_manager.json`

---

## Best Practices

### 1. Start Simple, Add Complexity Gradually

Begin with a minimal tree and add branches incrementally:

```json
// Start here
{
  "payment_tree": {
    "type": "action",
    "node_id": "A1",
    "action": "Release"
  }
}

// Then add one condition
{
  "payment_tree": {
    "type": "condition",
    "node_id": "N1",
    "condition": { /* urgency check */ },
    "on_true": { "type": "action", "node_id": "A1", "action": "Release" },
    "on_false": { "type": "action", "node_id": "A2", "action": "Hold" }
  }
}

// Then add nested conditions as needed
```

### 2. Use Descriptive Node IDs

```json
// Good
"node_id": "N1_CheckUrgency"
"node_id": "N2_BufferSufficient"
"node_id": "A1_ReleaseUrgent"
"node_id": "A2_HoldInsufficientLiquidity"

// Bad
"node_id": "N1"
"node_id": "condition_2"
"node_id": "action"
```

### 3. Add Descriptions to Complex Conditions

```json
{
  "type": "condition",
  "node_id": "N3_ComplexLogic",
  "description": "Release if: (urgent OR high-priority) AND (has liquidity OR willing to use credit)",
  "condition": { /* ... */ }
}
```

### 4. Use Parameters for Configurability

```json
// Good - Parameterized
"parameters": {
  "urgency_threshold": 5.0,
  "high_priority_level": 8.0,
  "buffer_multiplier": 1.5
}

// Then in tree:
{"param": "urgency_threshold"}

// Bad - Hardcoded
{"value": 5.0}  // Magic number, hard to override
```

### 5. Boolean Field Conventions

Always compare boolean fields explicitly:

```json
// Good - Explicit
{
  "op": "==",
  "left": {"field": "is_eod_rush"},
  "right": {"value": 1.0}
}

// Bad - Implicit (might work but less clear)
{"field": "is_eod_rush"}
```

### 6. Use `max(value, 0)` for Non-Negative Values

When computing amounts that should never be negative:

```json
{
  "compute": {
    "op": "max",
    "values": [
      {
        "compute": {
          "op": "-",
          "left": {"field": "queue1_total_value"},
          "right": {"field": "available_liquidity"}
        }
      },
      {"value": 0.0}
    ]
  }
}
```

### 7. Validate Logic with Tests

Create test scenarios for your policy:

```yaml
# In simulation config
agents:
  - id: TEST_AGENT
    policy:
      type: tree
      path: "my_policy.json"
    initial_balance: 100000

transactions:
  - id: TX1
    sender: TEST_AGENT
    receiver: BANK_B
    amount: 50000
    arrival_tick: 10
    deadline_tick: 15  # Test urgent path

  - id: TX2
    sender: TEST_AGENT
    receiver: BANK_B
    amount: 50000
    arrival_tick: 10
    deadline_tick: 100  # Test non-urgent path
```

### 8. Collateral Tree Structure

Collateral trees should always end with `HoldCollateral` on one branch:

```json
{
  "type": "condition",
  "node_id": "SC1_ShouldAct",
  "condition": { /* ... */ },
  "on_true": {
    "type": "action",
    "node_id": "SC2_Post",
    "action": "PostCollateral",
    "parameters": { /* ... */ }
  },
  "on_false": {
    "type": "action",
    "node_id": "SC3_DoNothing",
    "action": "HoldCollateral"
  }
}
```

### 9. Avoid Deep Nesting

If your tree exceeds 5-6 levels, consider refactoring:

```json
// Instead of:
N1 → N2 → N3 → N4 → N5 → N6 → Action

// Use multiple smaller decisions:
N1 → A1 (early exit)
   → N2 → A2 (another early exit)
        → N3 → A3 (final logic)
```

### 10. Comment Complex Computations

Use `"comment"` fields (ignored by parser, useful for humans):

```json
{
  "compute": {
    "op": "*",
    "left": {"field": "amount"},
    "right": {
      "compute": {
        "op": "+",
        "left": {"value": 1.0},
        "right": {"field": "day_progress_fraction"}
      }
    }
  },
  "comment": "Required liquidity: amount * (1.0 + day_progress). Early day = 1x, EOD = 2x"
}
```

---

## Troubleshooting

### Common Errors

#### 1. Parse Error: "data did not match any variant"

**Cause:** Invalid JSON structure, often in `Computation` or `Value`.

**Fix:** Check syntax:
```json
// WRONG
{"compute": {"type": "Mul", "values": [...]}}

// CORRECT
{"compute": {"op": "*", "left": {...}, "right": {...}}}
```

#### 2. Field Not Found

**Cause:** Typo in field name or using non-existent field.

**Fix:** Check [Available Data Reference](#available-data-reference) for exact field names:
```json
// WRONG
{"field": "remaining_balance"}

// CORRECT
{"field": "balance"}
```

#### 3. Missing Parameters

**Cause:** Action requires parameters but none provided.

**Fix:** Add required parameters:
```json
// WRONG
{
  "type": "action",
  "action": "Split"
}

// CORRECT
{
  "type": "action",
  "action": "Split",
  "parameters": {
    "num_splits": {"value": 4.0}
  }
}
```

#### 4. Type Mismatch in Comparisons

**Cause:** Comparing incompatible types or missing `.0` on numbers.

**Fix:** Ensure all numbers are floats:
```json
// WRONG
{"value": 5}

// CORRECT
{"value": 5.0}
```

#### 5. Collateral Action in Payment Tree

**Cause:** Using `PostCollateral` or `WithdrawCollateral` in `payment_tree`.

**Fix:** Move to `strategic_collateral_tree` or `end_of_tick_collateral_tree`:
```json
{
  "payment_tree": {
    "type": "action",
    "action": "Release"  // Only payment actions here
  },
  "strategic_collateral_tree": {
    "type": "action",
    "action": "PostCollateral",  // Collateral actions here
    "parameters": { /* ... */ }
  }
}
```

### Validation Checklist

Before running your policy:

- [ ] Valid JSON syntax (use `jq` or JSON validator)
- [ ] All `node_id` values are unique within each tree
- [ ] All field references match [Available Data Reference](#available-data-reference)
- [ ] All parameter references exist in `parameters` object
- [ ] All numbers have `.0` (floats, not integers)
- [ ] Action nodes have required parameters (`num_splits` for Split, `amount` and `reason` for collateral actions)
- [ ] Collateral actions only in collateral trees, not payment tree
- [ ] Boolean comparisons use `1.0` for true, `0.0` for false

### Testing Your Policy

1. **Syntax validation:**
```bash
jq empty backend/policies/my_policy.json
# No output = valid JSON
```

2. **Load test:**
```bash
cargo test --test test_tree_policy -- --nocapture
# Should load without errors
```

3. **Simulation test:**
```yaml
# Create test config with your policy
agents:
  - id: TEST_BANK
    policy:
      type: tree
      path: "my_policy.json"
```

```bash
# Run simulation
python -m payment_simulator.cli run --config test_config.yaml --ticks 100
```

---

## Appendix: Quick Reference

### Action Summary

| Action | Tree | Parameters | Effect |
|:-------|:-----|:-----------|:-------|
| `Release` | Payment | None | Submit full transaction to Queue 2 |
| `Hold` | Payment | `reason` (optional) | Keep in Queue 1 for next tick |
| `Drop` | Payment | None | Remove transaction from simulation |
| `Split` / `PaceAndRelease` | Payment | `num_splits` (required) | Split into N parts, submit all |
| `PostCollateral` | Collateral | `amount`, `reason` | Post collateral to increase capacity |
| `WithdrawCollateral` | Collateral | `amount`, `reason` | Withdraw collateral to reduce cost |
| `HoldCollateral` | Collateral | None | Do nothing this tick |

### Operator Summary

| Category | Operators |
|:---------|:----------|
| Comparison | `==`, `!=`, `<`, `<=`, `>`, `>=` |
| Logical | `and`, `or`, `not` |
| Arithmetic | `+`, `-`, `*`, `/` |
| Functions | `max`, `min` |

### Field Categories

| Category | Count | Examples |
|:---------|:------|:---------|
| Transaction | 8 | `amount`, `deadline_tick`, `priority` |
| Derived Transaction | 2 | `ticks_to_deadline`, `queue_age` |
| Agent Balance | 6 | `balance`, `credit_limit`, `available_liquidity` |
| Agent Queue | 3 | `outgoing_queue_size`, `incoming_expected_count` |
| Collateral | 9 | `posted_collateral`, `queue1_liquidity_gap`, `headroom` |
| Queue 2 (RTGS) | 3 | `queue2_count_for_agent`, `queue2_nearest_deadline` |
| Cost Rates | 6 | `cost_overdraft_bps_per_tick`, `cost_deadline_penalty` |
| Derived Costs | 2 | `cost_delay_this_tx_one_tick`, `cost_overdraft_this_amount_one_tick` |
| Time-of-Day | 6 | `is_eod_rush`, `day_progress_fraction`, `ticks_remaining_in_day` |
| System | 4 | `current_tick`, `rtgs_queue_size`, `total_agents` |

**Total:** 49 fields available in payment tree, 47 in collateral trees (no transaction-specific fields)

---

## Getting Help

**Documentation:**
- Architecture overview: `docs/architecture.md`
- Game design & domain model: `docs/game-design.md`
- Project guidelines: `CLAUDE.md`

**Example Policies:**
- `backend/policies/liquidity_aware.json` - Simple buffer management
- `backend/policies/liquidity_splitting.json` - Payment splitting
- `backend/policies/adaptive_liquidity_manager.json` - Full Phase 9.5 example

**Source Code:**
- DSL types: `backend/src/policy/tree/types.rs`
- Context builder: `backend/src/policy/tree/context.rs`
- Tree executor: `backend/src/policy/tree/executor.rs`
- Policy factory: `backend/src/policy/tree/factory.rs`

---

*Last updated: 2025-11-01*
*DSL Version: 1.0*
*Phase 9.5 features included*
