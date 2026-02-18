# Policy Decision Trees

*The DSL that controls bank behavior*

Every bank in SimCash is controlled by a **policy** — a JSON-based decision
tree that determines how payments are handled, how budgets are set, and how collateral
is managed. The policy DSL is expressive enough to encode strategies ranging from
"release everything immediately" to sophisticated multi-factor adaptive approaches.

## How Decision Trees Work

A policy tree is a binary decision tree. Each node is either a **condition**
(which branches on true/false) or an **action** (a terminal decision).
The tree is walked from root to leaf for each decision point, and the leaf action is executed.

```json
{
  "type": "condition",
  "node_id": "check_urgency",
  "condition": {
    "op": "<=",
    "left": {"field": "ticks_to_deadline"},
    "right": {"param": "urgency_threshold"}
  },
  "on_true": {
    "type": "action",
    "node_id": "release_urgent",
    "action": "Release"
  },
  "on_false": {
    "type": "condition",
    "node_id": "check_balance",
    "condition": {
      "op": ">",
      "left": {"field": "balance"},
      "right": {"compute": {
        "op": "*",
        "left": {"field": "amount"},
        "right": {"value": 1.5}
      }}
    },
    "on_true": {"type": "action", "action": "Release"},
    "on_false": {"type": "action", "action": "Hold"}
  }
}
```

## The Four Tree Types

A complete policy definition (`DecisionTreeDef`) contains up to four
independent trees, each evaluated at a different phase of the tick:

| Tree | When Evaluated | Scope |
|------|---------------|-------|
| `bank_tree` | Once per tick, before payment processing | Set budgets, write state registers |
| `payment_tree` | Per transaction in Queue 1 | Release / Hold / Split each payment |
| `strategic_collateral_tree` | Once per tick, after payment processing | Proactive collateral posting |
| `end_of_tick_collateral_tree` | Once per tick, at end of tick | Reactive collateral cleanup |

> ℹ️ The `bank_tree` runs first and can set a release budget
> via `SetReleaseBudget`. The `payment_tree` may
> return `Release`, but the engine converts it to `Hold` if
> the budget is exhausted. This two-level control lets a policy set macro limits
> and then make micro decisions per payment.

## Key Actions

### Payment Tree Actions

| Action | Description |
|--------|------------|
| `Release` | Submit payment to RTGS for settlement |
| `Hold` | Keep in queue for re-evaluation next tick |
| `Split` | Divide into N smaller payments and submit all |
| `StaggerSplit` | Split with staggered release timing |
| `ReleaseWithCredit` | Submit using intraday credit if needed |
| `Reprioritize` | Change payment priority without moving it |
| `WithdrawFromRtgs` | Pull payment back from Queue 2 |
| `ResubmitToRtgs` | Change RTGS priority (Normal → Urgent → HighlyUrgent) |

### Bank Tree Actions

| Action | Description |
|--------|------------|
| `SetReleaseBudget` | Set per-tick release limits (max value, per-counterparty caps) |
| `SetState` | Write a state register value (key must start with `bank_state_`) |
| `AddState` | Increment/decrement a state register |
| `NoAction` | Do nothing this tick |

### Collateral Tree Actions

| Action | Description |
|--------|------------|
| `PostCollateral` | Post collateral to increase borrowing capacity |
| `WithdrawCollateral` | Withdraw collateral to reduce opportunity costs |
| `HoldCollateral` | Keep current collateral level unchanged |

## Context Fields

Conditions can reference 80+ context fields. Here are the most important ones, organized by category:

### Balance & Liquidity

`balance` · `effective_liquidity` · `credit_limit` · `available_liquidity` · `credit_used` · `liquidity_buffer` · `liquidity_pressure` · `credit_headroom`

### Transaction

`amount` · `remaining_amount` · `priority` · `ticks_to_deadline` · `arrival_tick` · `deadline_tick` · `is_past_deadline` · `is_overdue` · `overdue_duration` · `is_split` · `is_divisible`

### Queue State

`outgoing_queue_size` · `queue1_total_value` · `queue1_liquidity_gap` · `headroom` · `rtgs_queue_size` · `queue2_count_for_agent`

### Timing

`current_tick` · `system_tick_in_day` · `ticks_remaining_in_day` · `day_progress_fraction` · `is_eod_rush` · `system_current_day`

### Costs

`cost_delay_this_tx_one_tick` · `cost_overdraft_this_amount_one_tick` · `cost_overdraft_bps_per_tick` · `cost_delay_per_tick_per_cent` · `cost_deadline_penalty` · `cost_eod_penalty`

### Collateral

`posted_collateral` · `remaining_collateral_capacity` · `collateral_utilization` · `overdraft_headroom` · `excess_collateral`

### Counterparty & LSM

`tx_counterparty_id` · `tx_is_top_counterparty` · `my_bilateral_net_q2` · `my_q2_out_value_to_counterparty` · `system_queue2_pressure_index`

## State Registers: Cross-Tick Memory

State registers let a policy maintain information across ticks within a day. They're
`f64` values identified by keys prefixed with `bank_state_`.

- Set via `SetState` action, incremented via `AddState`
- Read in any tree as a field: `{"field": "bank_state_cooldown"}`
- Default to 0.0 if never set, max 10 per agent
- **Reset at end of each day** — no multi-day memory

Use cases: cooldown timers, release counters, running totals, mode flags.

```json
// Bank tree: set a cooldown after releasing a lot
{
  "type": "condition",
  "condition": {
    "op": ">",
    "left": {"field": "bank_state_released_today"},
    "right": {"value": 500000}
  },
  "on_true": {
    "type": "action",
    "action": "SetState",
    "parameters": {
      "key": {"value": "bank_state_cooldown"},
      "value": {"value": 3},
      "reason": {"value": "high release volume, cooling off"}
    }
  },
  "on_false": {"type": "action", "action": "NoAction"}
}
```

## Policy Design Patterns

### The Cautious Banker

Conservative approach: maintain a large liquidity buffer, only release payments when
the deadline is imminent or when the balance is well above the buffer threshold.
Uses state registers to track how much has been released and enters a cooldown mode
after heavy release ticks.

- Bank tree: `SetReleaseBudget` with a conservative cap
- Payment tree: Release if `ticks_to_deadline ≤ 3` OR `balance > amount × 2.5`
- Collateral tree: `PostCollateral` proactively at start of day, `WithdrawCollateral` at end
- Good for: avoiding overdraft, minimizing risk, stable cost profiles
- Weakness: high delay costs from holding too long

### The Aggressive Market Maker

High-throughput strategy: release most payments immediately, use credit facilities
aggressively, split large payments to maintain flow. Prioritizes settlement speed
over liquidity conservation.

- Bank tree: `NoAction` (no budget constraints)
- Payment tree: Release everything except very large payments when balance is critically low
- Collateral tree: `PostCollateral` whenever overdraft utilization is high
- Good for: minimizing delay costs, high settlement rates
- Weakness: high liquidity and overdraft costs, vulnerable to rate spikes

> 💡 The optimal strategy typically falls between these extremes. The LLM optimization
> system can explore the space between "too cautious" and "too aggressive" by tuning
> parameters like `urgency_threshold` and `liquidity_buffer` and
> evolving the tree structure itself.
