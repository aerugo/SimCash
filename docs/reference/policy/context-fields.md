# Evaluation Context Fields

> **Reference: All 140+ Fields Available for Policy Evaluation**

## Overview

The evaluation context provides access to simulation state during policy evaluation. All fields are stored as `f64` for uniform arithmetic operations.

## Field Availability by Tree Type

| Category | payment_tree | bank_tree | collateral_trees |
|----------|:------------:|:---------:|:----------------:|
| Transaction | ✅ | ❌ | ❌ |
| Agent/Balance | ✅ | ✅ | ✅ |
| Queue 1 | ✅ | ✅ | ✅ |
| Queue 2 | ✅ | ✅ | ✅ |
| Collateral | ✅ | ✅ | ✅ |
| Cost Rates | ✅ | ✅ | ✅ |
| Time/System | ✅ | ✅ | ✅ |
| LSM-Aware | ✅ | ❌ | ❌ |
| Throughput | ✅ | ✅ | ✅ |
| State Registers | ✅ | ✅ | ✅ |

---

# Transaction Fields

**Availability**: `payment_tree` only

## amount
- **Type**: f64 (from i64)
- **Unit**: cents
- **Description**: Original transaction amount
- **Source**: `tx.amount()`
- **Example**: `100000` = $1,000.00

## remaining_amount
- **Type**: f64 (from i64)
- **Unit**: cents
- **Description**: Amount still to be settled (decreases as partial settlements occur)
- **Source**: `tx.remaining_amount()`
- **Use Case**: Checking affordability, calculating split sizes

## settled_amount
- **Type**: f64 (from i64)
- **Unit**: cents
- **Description**: Amount already settled (for partially settled transactions)
- **Source**: `tx.settled_amount()`

## arrival_tick
- **Type**: f64 (from usize)
- **Unit**: ticks
- **Description**: Tick when transaction entered the system
- **Source**: `tx.arrival_tick()`

## deadline_tick
- **Type**: f64 (from usize)
- **Unit**: ticks
- **Description**: Latest tick for settlement without penalty
- **Source**: `tx.deadline_tick()`

## priority
- **Type**: f64 (from u8)
- **Range**: 0-10
- **Description**: Transaction urgency (higher = more important)
- **Source**: `tx.priority()`

## is_split
- **Type**: f64 (boolean: 0.0 or 1.0)
- **Description**: Whether this is a child transaction from a split
- **Source**: `tx.is_split()`

## is_past_deadline
- **Type**: f64 (boolean: 0.0 or 1.0)
- **Description**: Whether current tick exceeds deadline
- **Source**: `tx.is_past_deadline(tick)`
- **Calculation**: `1.0` if `current_tick > deadline_tick`

## is_overdue
- **Type**: f64 (boolean: 0.0 or 1.0)
- **Description**: Whether transaction has been marked overdue
- **Source**: `tx.is_overdue()`
- **Note**: Different from is_past_deadline (overdue is a persistent status)

## is_in_queue2
- **Type**: f64 (boolean: 0.0 or 1.0)
- **Description**: Whether transaction is in RTGS Queue 2
- **Source**: `tx.rtgs_priority().is_some()`
- **Use Case**: Policies managing Queue 2 transactions

## overdue_duration
- **Type**: f64 (from usize)
- **Unit**: ticks
- **Description**: How long transaction has been overdue
- **Calculation**: `current_tick - overdue_since_tick` (0 if not overdue)

## ticks_to_deadline
- **Type**: f64 (from i64)
- **Unit**: ticks
- **Description**: Ticks until deadline (can be negative)
- **Calculation**: `deadline_tick - current_tick`
- **Use Case**: Urgency detection (e.g., `<= 5` means urgent)

## queue_age
- **Type**: f64 (from usize)
- **Unit**: ticks
- **Description**: How long transaction has been in Queue 1
- **Calculation**: `current_tick - arrival_tick`

---

# Agent/Balance Fields

**Availability**: All trees

## balance
- **Type**: f64 (from i64)
- **Unit**: cents
- **Description**: Current account balance (can be negative if using credit)
- **Source**: `agent.balance()`

## credit_limit
- **Type**: f64 (from i64)
- **Unit**: cents
- **Description**: Maximum daylight overdraft allowed (same as unsecured_cap)
- **Source**: `agent.unsecured_cap()`
- **Note**: Alias for unsecured_cap for backward compatibility

## available_liquidity
- **Type**: f64 (from i64)
- **Unit**: cents
- **Description**: Positive balance portion (max(balance, 0))
- **Source**: `agent.available_liquidity()`

## credit_used
- **Type**: f64 (from i64)
- **Unit**: cents
- **Description**: Current overdraft amount (0 if balance >= 0)
- **Source**: `agent.credit_used()`

## effective_liquidity
- **Type**: f64 (from i64)
- **Unit**: cents
- **Description**: Total available capacity (balance + credit_headroom)
- **Calculation**: `balance + (unsecured_cap - credit_used)`
- **Use Case**: "Can I afford this payment?" checks
- **Important**: This is what policies should use for affordability checks

## credit_headroom
- **Type**: f64 (from i64)
- **Unit**: cents
- **Description**: Remaining credit capacity
- **Calculation**: `unsecured_cap - credit_used`
- **Use Case**: Checking if credit is available

## is_using_credit
- **Type**: f64 (boolean: 0.0 or 1.0)
- **Description**: Whether balance is negative
- **Source**: `agent.is_using_credit()`

## liquidity_buffer
- **Type**: f64 (from i64)
- **Unit**: cents
- **Description**: Agent's target minimum balance
- **Source**: `agent.liquidity_buffer()`

## liquidity_pressure
- **Type**: f64
- **Range**: 0.0 to 1.0
- **Description**: Normalized pressure metric
- **Source**: `agent.liquidity_pressure()`
- **Use Case**: Detecting stress conditions

## is_overdraft_capped
- **Type**: f64 (boolean: always 1.0)
- **Description**: Whether credit limits are enforced
- **Note**: Always 1.0 in current implementation (Option B: capped overdraft)

---

# Queue 1 Fields

**Availability**: All trees

## outgoing_queue_size
- **Type**: f64 (from usize)
- **Description**: Number of transactions in agent's Queue 1
- **Source**: `agent.outgoing_queue_size()`

## queue1_total_value
- **Type**: f64 (from i64)
- **Unit**: cents
- **Description**: Total value of all transactions in Queue 1
- **Calculation**: Sum of remaining_amount for all Queue 1 transactions

## queue1_liquidity_gap
- **Type**: f64 (from i64)
- **Unit**: cents
- **Description**: Shortfall to clear entire Queue 1
- **Calculation**: `queue1_total_value - available_liquidity` (0 if negative)
- **Use Case**: Determining collateral needs

## headroom
- **Type**: f64 (from i64)
- **Unit**: cents
- **Description**: Excess liquidity after Queue 1 coverage
- **Calculation**: `available_liquidity - queue1_total_value`
- **Note**: Can be negative (indicates gap)

## incoming_expected_count
- **Type**: f64 (from usize)
- **Description**: Number of expected incoming payments
- **Source**: `agent.incoming_expected().len()`

---

# Queue 2 (RTGS) Fields

**Availability**: All trees

## rtgs_queue_size
- **Type**: f64 (from usize)
- **Description**: Total number of transactions in RTGS Queue 2 (system-wide)
- **Source**: `state.queue_size()`

## rtgs_queue_value
- **Type**: f64 (from i64)
- **Unit**: cents
- **Description**: Total value in RTGS Queue 2 (system-wide)
- **Source**: `state.queue_value()`

## queue2_size
- **Type**: f64 (from usize)
- **Description**: Same as rtgs_queue_size
- **Source**: `state.rtgs_queue().len()`

## queue2_count_for_agent
- **Type**: f64 (from usize)
- **Description**: Agent's transactions currently in Queue 2
- **Source**: `state.queue2_index().get_metrics(agent_id).count`

## queue2_nearest_deadline
- **Type**: f64 (from usize)
- **Unit**: tick number
- **Description**: Nearest deadline among agent's Queue 2 transactions
- **Source**: `state.queue2_index().get_metrics(agent_id).nearest_deadline`
- **Note**: Returns max usize if no transactions in Queue 2

## ticks_to_nearest_queue2_deadline
- **Type**: f64
- **Unit**: ticks
- **Description**: Ticks until nearest Queue 2 deadline
- **Calculation**: `queue2_nearest_deadline - current_tick`
- **Special**: Returns `f64::INFINITY` if no Queue 2 transactions

---

# Collateral Fields

**Availability**: All trees

## posted_collateral
- **Type**: f64 (from i64)
- **Unit**: cents
- **Description**: Amount of collateral currently posted
- **Source**: `agent.posted_collateral()`

## max_collateral_capacity
- **Type**: f64 (from i64)
- **Unit**: cents
- **Description**: Maximum collateral agent can post
- **Source**: `agent.max_collateral_capacity()`

## remaining_collateral_capacity
- **Type**: f64 (from i64)
- **Unit**: cents
- **Description**: Additional collateral that can be posted
- **Calculation**: `max_collateral_capacity - posted_collateral`

## collateral_utilization
- **Type**: f64
- **Range**: 0.0 to 1.0+
- **Description**: Fraction of collateral capacity used
- **Calculation**: `posted_collateral / max_collateral_capacity`

## collateral_haircut
- **Type**: f64
- **Range**: 0.0 to 1.0
- **Description**: Discount applied to collateral value
- **Source**: `agent.collateral_haircut()`
- **Example**: 0.1 means collateral valued at 90%

## unsecured_cap
- **Type**: f64 (from i64)
- **Unit**: cents
- **Description**: Unsecured daylight overdraft capacity
- **Source**: `agent.unsecured_cap()`

## allowed_overdraft_limit
- **Type**: f64 (from i64)
- **Unit**: cents
- **Description**: Total overdraft limit (collateral-backed + unsecured)
- **Source**: `agent.allowed_overdraft_limit()`

## overdraft_headroom
- **Type**: f64 (from i64)
- **Unit**: cents
- **Description**: Remaining overdraft capacity
- **Calculation**: `allowed_overdraft_limit - credit_used`
- **Source**: `agent.headroom()`

## overdraft_utilization
- **Type**: f64
- **Range**: 0.0 to 1.0+
- **Description**: Fraction of overdraft limit used
- **Calculation**: `credit_used / allowed_overdraft_limit`

## required_collateral_for_usage
- **Type**: f64
- **Unit**: cents
- **Description**: Minimum collateral needed for current credit usage
- **Calculation**: `(credit_used - unsecured_cap) / (1 - haircut)`
- **Note**: Accounts for unsecured portion

## excess_collateral
- **Type**: f64
- **Unit**: cents
- **Description**: Collateral available for withdrawal
- **Calculation**: `posted_collateral - required_collateral_for_usage`
- **Minimum**: 0.0

---

# Cost Rate Fields

**Availability**: All trees

## cost_overdraft_bps_per_tick
- **Type**: f64
- **Unit**: basis points per tick
- **Description**: Overdraft interest rate
- **Source**: `cost_rates.overdraft_bps_per_tick`
- **Example**: 0.5 = 0.5 bps per tick

## cost_delay_per_tick_per_cent
- **Type**: f64
- **Unit**: cost per tick per cent
- **Description**: Delay penalty rate
- **Source**: `cost_rates.delay_cost_per_tick_per_cent`

## cost_collateral_bps_per_tick
- **Type**: f64
- **Unit**: basis points per tick
- **Description**: Collateral opportunity cost
- **Source**: `cost_rates.collateral_cost_per_tick_bps`

## cost_split_friction
- **Type**: f64
- **Unit**: cents
- **Description**: Fixed cost per split operation
- **Source**: `cost_rates.split_friction_cost`

## cost_deadline_penalty
- **Type**: f64
- **Unit**: cents
- **Description**: One-time penalty when transaction becomes overdue
- **Source**: `cost_rates.deadline_penalty`

## cost_eod_penalty
- **Type**: f64
- **Unit**: cents
- **Description**: End-of-day penalty per unsettled transaction
- **Source**: `cost_rates.eod_penalty_per_transaction`

## cost_delay_this_tx_one_tick
- **Type**: f64
- **Unit**: cents
- **Description**: Delay cost for THIS transaction for one tick
- **Calculation**: `remaining_amount * cost_delay_per_tick_per_cent`
- **Availability**: `payment_tree` only

## cost_overdraft_this_amount_one_tick
- **Type**: f64
- **Unit**: cents
- **Description**: Overdraft cost for THIS amount for one tick
- **Calculation**: `(cost_overdraft_bps_per_tick / 10000) * remaining_amount`
- **Availability**: `payment_tree` only

---

# Time/System Fields

**Availability**: All trees

## current_tick
- **Type**: f64 (from usize)
- **Description**: Current simulation tick
- **Source**: tick parameter

## system_ticks_per_day
- **Type**: f64 (from usize)
- **Description**: Number of ticks in a simulation day
- **Source**: ticks_per_day parameter

## system_current_day
- **Type**: f64 (from usize)
- **Description**: Current day number (0-indexed)
- **Calculation**: `current_tick / ticks_per_day`

## system_tick_in_day
- **Type**: f64 (from usize)
- **Description**: Current tick within the day
- **Calculation**: `current_tick % ticks_per_day`
- **Range**: 0 to ticks_per_day - 1

## ticks_remaining_in_day
- **Type**: f64 (from usize)
- **Description**: Ticks left in current day
- **Calculation**: `ticks_per_day - tick_in_day - 1`

## day_progress_fraction
- **Type**: f64
- **Range**: 0.0 to 1.0
- **Description**: Progress through the day
- **Calculation**: `tick_in_day / ticks_per_day`
- **Use Case**: Time-based strategy adjustments

## is_eod_rush
- **Type**: f64 (boolean: 0.0 or 1.0)
- **Description**: Whether in end-of-day rush period
- **Calculation**: `1.0` if `day_progress_fraction >= eod_rush_threshold`
- **Use Case**: Switching to aggressive EOD strategy

## total_agents
- **Type**: f64 (from usize)
- **Description**: Number of agents in simulation
- **Source**: `state.num_agents()`

---

# LSM-Aware Fields

**Availability**: `payment_tree` only

## my_q2_out_value_to_counterparty
- **Type**: f64 (from i64)
- **Unit**: cents
- **Description**: Value of agent's Queue 2 outflows TO this transaction's counterparty
- **Use Case**: Detecting bilateral offset opportunities

## my_q2_in_value_from_counterparty
- **Type**: f64 (from i64)
- **Unit**: cents
- **Description**: Value of Queue 2 inflows FROM this transaction's counterparty
- **Use Case**: Detecting bilateral offset opportunities

## my_bilateral_net_q2
- **Type**: f64 (from i64)
- **Unit**: cents
- **Description**: Net Queue 2 position with counterparty (out - in)
- **Calculation**: `my_q2_out_value_to_counterparty - my_q2_in_value_from_counterparty`
- **Interpretation**: Positive = net creditor, Negative = net debtor

## my_q2_out_value_top_1 through my_q2_out_value_top_5
- **Type**: f64 (from i64)
- **Unit**: cents
- **Description**: Queue 2 outflow values to top 5 counterparties
- **Note**: Sorted by value (top_1 is highest)

## my_q2_in_value_top_1 through my_q2_in_value_top_5
- **Type**: f64 (from i64)
- **Unit**: cents
- **Description**: Queue 2 inflow values from top 5 counterparties

## my_bilateral_net_q2_top_1 through my_bilateral_net_q2_top_5
- **Type**: f64 (from i64)
- **Unit**: cents
- **Description**: Net Queue 2 positions with top 5 counterparties by absolute net

## tx_counterparty_id
- **Type**: f64 (hash)
- **Description**: Hash of counterparty ID for categorical comparison
- **Use Case**: Comparing against top counterparty hashes

## tx_is_top_counterparty
- **Type**: f64 (boolean: 0.0 or 1.0)
- **Description**: Whether counterparty is in agent's top 5 by volume
- **Use Case**: Prioritizing major trading relationships

---

# Throughput/Progress Fields

**Availability**: All trees

## system_queue2_pressure_index
- **Type**: f64
- **Range**: 0.0 (low) to 1.0 (high)
- **Description**: System-wide Queue 2 pressure indicator
- **Use Case**: Adjusting aggression based on system state

## my_throughput_fraction_today
- **Type**: f64
- **Range**: 0.0 to 1.0
- **Description**: Agent's settlement progress today
- **Calculation**: settled_value / total_due_value

## expected_throughput_fraction_by_now
- **Type**: f64
- **Range**: 0.0 to 1.0
- **Description**: Expected progress from guidance curve
- **Default**: Linear model (tick_in_day / ticks_per_day)

## throughput_gap
- **Type**: f64
- **Range**: -1.0 to 1.0
- **Description**: Progress vs expectation
- **Calculation**: `my_throughput_fraction_today - expected_throughput_fraction_by_now`
- **Interpretation**: Negative = behind, Positive = ahead

---

# State Register Fields

**Availability**: All trees

## bank_state_* (user-defined)
- **Type**: f64
- **Description**: Policy-defined state registers
- **Naming**: Must start with `bank_state_` prefix
- **Default**: 0.0 if not set
- **Persistence**: Within day only (reset at EOD)
- **Maximum**: 10 registers per agent

### Common Patterns

```json
{"field": "bank_state_cooldown"}     // Timer countdown
{"field": "bank_state_counter"}      // Action counter
{"field": "bank_state_budget_used"}  // Budget tracking
{"field": "bank_state_mode"}         // Strategy mode (0/1/2)
```

### Setting State Registers

Via `bank_tree` with `SetState` or `AddState` actions:
```json
{
  "action": "SetState",
  "parameters": {
    "key": {"value": "bank_state_cooldown"},
    "value": {"value": 10.0},
    "reason": {"value": "Initialize cooldown"}
  }
}
```

---

# Field Validation

## Transaction-Only Fields
These fields are **only available in payment_tree**:
- amount, remaining_amount, settled_amount
- arrival_tick, deadline_tick, priority
- is_split, is_past_deadline, is_overdue, is_in_queue2
- overdue_duration, ticks_to_deadline, queue_age
- cost_delay_this_tx_one_tick, cost_overdraft_this_amount_one_tick
- my_q2_out_value_to_counterparty, my_q2_in_value_from_counterparty
- my_bilateral_net_q2, tx_counterparty_id, tx_is_top_counterparty

Using these in bank_tree or collateral trees will cause validation error.

## Validation Implementation

See `backend/src/policy/tree/validation.rs`:
- `is_transaction_only_field()` - lines 327-353
- `is_bank_level_field()` - lines 355-418
- `validate_field_references()` - lines 244-324

---

# Source Code Reference

| Component | File | Line |
|-----------|------|------|
| EvalContext struct | `backend/src/policy/tree/context.rs` | 114-117 |
| EvalContext::build() | `backend/src/policy/tree/context.rs` | 152-611 |
| EvalContext::bank_level() | `backend/src/policy/tree/context.rs` | 646-869 |
| get_field() | `backend/src/policy/tree/context.rs` | 920-927 |
| Transaction field validation | `backend/src/policy/tree/validation.rs` | 327-353 |
| Bank-level field validation | `backend/src/policy/tree/validation.rs` | 355-418 |
