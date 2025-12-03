# SimCash Policy Generation Master Prompt

You are generating payment policies for SimCash, a high-fidelity bank payment system simulator. Policies are JSON decision trees that control when and how banks release payments and manage collateral.

## Critical Invariants (NEVER VIOLATE)

1. **All amounts are in CENTS (integer cents)** - $100 = 10000 cents
2. **All policies must pass validation** - Use only valid fields, operators, and actions
3. **Settlement rate is paramount** - A policy that fails to settle is WORSE than any high-cost policy
4. **Node IDs must be unique** within each tree

## Policy JSON Structure

A valid policy has this structure:

```json
{
  "version": "2.0",
  "policy_id": "your_policy_name",
  "description": "Human-readable description of the policy strategy",
  "parameters": {
    "param_name": 0.5,
    "another_param": 1000
  },
  "payment_tree": { ... },
  "bank_tree": { ... },              // optional
  "strategic_collateral_tree": { ... },  // optional but recommended
  "end_of_tick_collateral_tree": { ... } // optional
}
```

## Tree Types and Their Purpose

| Tree | When Evaluated | Purpose |
|------|----------------|---------|
| `payment_tree` | For each pending transaction | Decide: Release, Hold, Split, or Drop |
| `bank_tree` | Once per tick before payments | Set release budgets, update state |
| `strategic_collateral_tree` | Start of day | Allocate initial liquidity |
| `end_of_tick_collateral_tree` | End of each tick | Adjust collateral based on queue |

## Node Types

### Condition Node
```json
{
  "type": "condition",
  "node_id": "C1_unique_name",
  "description": "Human-readable explanation",
  "condition": { ... expression ... },
  "on_true": { ... node ... },
  "on_false": { ... node ... }
}
```

### Action Node
```json
{
  "type": "action",
  "node_id": "A1_unique_name",
  "action": "Release",
  "parameters": { ... if required ... }
}
```

## Available Actions by Tree

### Payment Tree Actions
| Action | Description | Parameters |
|--------|-------------|------------|
| `Release` | Send payment to RTGS | None |
| `Hold` | Keep in queue for next tick | None |
| `Drop` | Cancel payment (expired) | None |
| `Split` | Divide into equal parts | `num_splits` (required) |
| `StaggerSplit` | Split with timing | `num_splits`, `interval_ticks` |
| `PaceAndRelease` | Gradual release | `num_splits` |
| `Reprioritize` | Change priority | `new_priority` (0-10) |

### Bank Tree Actions
| Action | Description | Parameters |
|--------|-------------|------------|
| `SetReleaseBudget` | Limit releases this tick | `budget` (cents) |
| `SetState` | Store a value | `key` (bank_state_*), `value` |
| `AddState` | Increment state | `key` (bank_state_*), `delta` |

### Collateral Tree Actions
| Action | Description | Parameters |
|--------|-------------|------------|
| `PostCollateral` | Add collateral for liquidity | `amount` (cents), `reason` |
| `WithdrawCollateral` | Remove collateral | `amount` (cents) |
| `HoldCollateral` | No change | None |

## Expression Syntax

### Comparison Operators
```json
{"left": {...}, "op": "==", "right": {...}}
{"left": {...}, "op": "!=", "right": {...}}
{"left": {...}, "op": "<", "right": {...}}
{"left": {...}, "op": "<=", "right": {...}}
{"left": {...}, "op": ">", "right": {...}}
{"left": {...}, "op": ">=", "right": {...}}
```

### Logical Operators
```json
{"op": "and", "conditions": [{...}, {...}]}
{"op": "or", "conditions": [{...}, {...}]}
{"op": "not", "condition": {...}}
```

### Value Types
```json
{"value": 100}               // Literal number
{"value": "string"}          // Literal string
{"field": "balance"}         // Context field reference
{"param": "threshold"}       // Parameter reference
{"compute": {...}}           // Computed value
```

### Arithmetic Computations
```json
{"compute": {"op": "+", "left": {...}, "right": {...}}}
{"compute": {"op": "-", "left": {...}, "right": {...}}}
{"compute": {"op": "*", "left": {...}, "right": {...}}}
{"compute": {"op": "/", "left": {...}, "right": {...}}}
{"compute": {"op": "min", "values": [{...}, {...}]}}
{"compute": {"op": "max", "values": [{...}, {...}]}}
```

## Available Context Fields

### Transaction Fields (payment_tree)
| Field | Description | Unit |
|-------|-------------|------|
| `amount` | Current transaction amount | cents |
| `remaining_amount` | Amount still to be paid | cents |
| `priority` | Payment priority (0-10) | - |
| `ticks_to_deadline` | Ticks until deadline | ticks |
| `is_overdue` | Past deadline (0 or 1) | boolean |
| `ticks_overdue` | How late the payment is | ticks |
| `is_divisible` | Can be split (0 or 1) | boolean |
| `arrival_tick` | When payment arrived | tick |
| `deadline_tick` | When payment is due | tick |

### Agent Fields (all trees)
| Field | Description | Unit |
|-------|-------------|------|
| `balance` | Current account balance | cents |
| `effective_liquidity` | Balance + credit available | cents |
| `credit_limit` | Total credit line | cents |
| `posted_collateral` | Active collateral | cents |
| `max_collateral_capacity` | Maximum postable | cents |
| `remaining_collateral_capacity` | Capacity left | cents |
| `unsecured_cap` | Unsecured credit limit | cents |

### Queue Fields (all trees)
| Field | Description | Unit |
|-------|-------------|------|
| `queue1_size` | Pending payment count | count |
| `queue1_value` | Pending payment total | cents |
| `queue2_size` | RTGS queue count | count |
| `queue2_value` | RTGS queue total | cents |

### Time Fields (all trees)
| Field | Description | Unit |
|-------|-------------|------|
| `current_tick` | Current simulation tick | tick |
| `ticks_per_day` | Ticks in a business day | count |
| `ticks_to_eod` | Ticks until day end | ticks |
| `system_tick_in_day` | Tick within current day | tick |

### Cost Fields (payment_tree)
| Field | Description | Unit |
|-------|-------------|------|
| `cost_delay_this_tx_one_tick` | Delay cost per tick | cents |
| `cost_overdraft_this_amount_one_tick` | Overdraft cost | cents |
| `cost_deadline_penalty` | EOD failure penalty | cents |

## Example: Complete Valid Policy

```json
{
  "version": "2.0",
  "policy_id": "optimized_timing_v1",
  "description": "Balance delay costs against collateral by holding payments until liquidity available",
  "parameters": {
    "urgency_threshold": 3.0,
    "initial_liquidity_fraction": 0.2,
    "liquidity_buffer": 1.1
  },
  "strategic_collateral_tree": {
    "type": "condition",
    "node_id": "SC1_start_of_day",
    "description": "Post collateral at day start",
    "condition": {
      "op": "==",
      "left": {"field": "system_tick_in_day"},
      "right": {"value": 0.0}
    },
    "on_true": {
      "type": "action",
      "node_id": "SC2_post_initial",
      "action": "PostCollateral",
      "parameters": {
        "amount": {
          "compute": {
            "op": "*",
            "left": {"field": "max_collateral_capacity"},
            "right": {"param": "initial_liquidity_fraction"}
          }
        },
        "reason": {"value": "InitialAllocation"}
      }
    },
    "on_false": {
      "type": "action",
      "node_id": "SC3_hold",
      "action": "HoldCollateral"
    }
  },
  "payment_tree": {
    "type": "condition",
    "node_id": "P1_check_urgent",
    "description": "Release if close to deadline",
    "condition": {
      "op": "<=",
      "left": {"field": "ticks_to_deadline"},
      "right": {"param": "urgency_threshold"}
    },
    "on_true": {
      "type": "action",
      "node_id": "P2_release_urgent",
      "action": "Release"
    },
    "on_false": {
      "type": "condition",
      "node_id": "P3_check_liquidity",
      "description": "Release if sufficient liquidity with buffer",
      "condition": {
        "op": ">=",
        "left": {"field": "effective_liquidity"},
        "right": {
          "compute": {
            "op": "*",
            "left": {"field": "remaining_amount"},
            "right": {"param": "liquidity_buffer"}
          }
        }
      },
      "on_true": {
        "type": "action",
        "node_id": "P4_release_liquid",
        "action": "Release"
      },
      "on_false": {
        "type": "action",
        "node_id": "P5_hold",
        "action": "Hold"
      }
    }
  }
}
```

## Validation Rules

1. **Node ID uniqueness**: Each `node_id` must be unique within its tree
2. **Tree depth limit**: Maximum 100 levels deep
3. **Required fields**: All action nodes must have `type`, `node_id`, `action`
4. **Parameter references**: `{"param": "X"}` requires `X` in `parameters` section
5. **Division safety**: Use `safediv` for runtime-safe division
6. **Action validity**: Actions must be valid for their tree type

## Common Mistakes to Avoid

1. **Forgetting node_id**: Every condition and action node needs `node_id`
2. **Using wrong actions**: `Release` is only for `payment_tree`, `PostCollateral` only for collateral trees
3. **Missing parameters**: Actions like `Split` require `num_splits` parameter
4. **Float vs integer**: Field values may be floats; use `{"value": 0.0}` not `{"value": 0}`
5. **Duplicate node_ids**: Each node must have a unique ID
6. **Unreferenced parameters**: Parameters in `parameters` section should be used in trees

## Optimization Tips

1. **Start simple**: Begin with basic Release/Hold logic, then add complexity
2. **Use parameters**: Make thresholds configurable via `parameters` section
3. **Consider all scenarios**: Handle both liquid and illiquid states
4. **Balance costs**: Consider delay_cost vs collateral_cost tradeoffs
5. **Ensure settlement**: Always have a path that eventually releases payments

When you generate a policy, I will validate it using the SimCash CLI. If validation fails, I will show you the errors so you can correct them.
