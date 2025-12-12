# Agent Model

> Runtime representation of a bank participating in the payment system

An Agent represents a bank's position in the settlement system during simulation execution. For YAML configuration, see [Agent Configuration](../../scenario/agents.md).

---

## Overview

An Agent maintains:
- **Settlement account balance** (positive = reserves, negative = using credit)
- **Credit facilities** (unsecured cap + collateralized credit)
- **Queue 1** (internal queue for cash manager decisions)
- **Policy state** (registers, budgets, timers)
- **Limits** (bilateral and multilateral outflow limits)

---

## State Fields

### Identity

| Field | Type | Description |
|-------|------|-------------|
| `id` | `String` | Unique agent identifier (e.g., "BANK_A") |

### Settlement Account

| Field | Type | Description |
|-------|------|-------------|
| `balance` | `i64` (cents) | Current balance at central bank. Positive = reserves, negative = using credit, zero = neither |

**CRITICAL:** Balance is always integer cents (INV-1).

### Queue 1 (Internal Queue)

| Field | Type | Description |
|-------|------|-------------|
| `outgoing_queue` | `Vec<String>` | Transaction IDs awaiting cash manager release decision |
| `incoming_expected` | `Vec<String>` | Expected incoming transaction IDs for liquidity forecasting |
| `last_decision_tick` | `Option<usize>` | Last tick when cash manager made a policy decision |
| `liquidity_buffer` | `i64` (cents) | Target minimum balance to maintain (default: 0) |

### Credit Facilities

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `posted_collateral` | `i64` (cents) | 0 | Collateral posted to secure intraday credit |
| `collateral_haircut` | `f64` | 0.02 | Discount rate applied to collateral (0.02 = 2%) |
| `unsecured_cap` | `i64` (cents) | 0 | Unsecured daylight overdraft capacity |
| `collateral_posted_at_tick` | `Option<usize>` | None | Tick when collateral was last posted |

### Policy State

| Field | Type | Description |
|-------|------|-------------|
| `release_budget_max` | `Option<i64>` | Maximum release budget for current tick (None = unlimited) |
| `release_budget_remaining` | `i64` | Remaining budget amount |
| `release_budget_focus_counterparties` | `Option<Vec<String>>` | Allowed counterparties (None = all, Some([]) = none) |
| `release_budget_per_counterparty_limit` | `Option<i64>` | Per-counterparty release limit |
| `release_budget_per_counterparty_usage` | `HashMap<String, i64>` | Per-counterparty usage tracking |
| `collateral_withdrawal_timers` | `HashMap<usize, Vec<...>>` | Scheduled automatic collateral withdrawals |
| `state_registers` | `HashMap<String, f64>` | Policy micro-memory (max 10, reset at EOD) |

### TARGET2 Limits

| Field | Type | Description |
|-------|------|-------------|
| `bilateral_limits` | `HashMap<String, i64>` | Maximum outflow per counterparty per day |
| `multilateral_limit` | `Option<i64>` | Maximum total outflow per day |
| `bilateral_outflows` | `HashMap<String, i64>` | Daily outflow tracking (reset at day start) |
| `total_outflow` | `i64` | Total outflow tracking (reset at day start) |

### Liquidity Pool

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `allocated_liquidity` | `i64` (cents) | 0 | Liquidity allocated from external pool |

---

## Key Methods

### Constructors

| Method | Description |
|--------|-------------|
| `Agent::new(id, balance)` | Create agent with opening balance |
| `Agent::with_buffer(id, balance, buffer)` | Create agent with specified liquidity buffer |
| `Agent::restore(data)` | Restore from checkpoint snapshot |

### Balance Operations

| Method | Returns | Description |
|--------|---------|-------------|
| `balance()` | `i64` | Current balance (cents) |
| `credit_used()` | `i64` | Amount of credit in use (absolute value of negative balance) |
| `available_liquidity()` | `i64` | Total available liquidity (see formula below) |
| `can_pay(amount)` | `bool` | Check if agent can afford payment |
| `debit(amount)` | `Result<(), AgentError>` | Debit balance (payment outflow) |
| `credit(amount)` | `()` | Credit balance (payment inflow, always succeeds) |

### Credit Facility Methods

| Method | Returns | Description |
|--------|---------|-------------|
| `allowed_overdraft_limit()` | `i64` | Maximum negative balance allowed |
| `headroom()` | `i64` | Remaining credit capacity |
| `max_withdrawable_collateral(buffer)` | `i64` | Maximum collateral safely withdrawable |
| `collateral_capacity()` | `i64` | Credit capacity from collateral (after haircut) |

### Queue 1 Operations

| Method | Description |
|--------|-------------|
| `queue_outgoing(tx_id)` | Add transaction to Queue 1 |
| `outgoing_queue()` | Get Queue 1 contents |
| `outgoing_queue_size()` | Get Queue 1 size |
| `remove_from_outgoing(tx_id)` | Remove transaction from Queue 1 |
| `replace_outgoing_queue(new_queue)` | Replace entire Queue 1 (for reordering) |

### Limit Operations

| Method | Description |
|--------|-------------|
| `set_bilateral_limits(limits)` | Set per-counterparty limits |
| `set_multilateral_limit(limit)` | Set total outflow limit |
| `record_outflow(counterparty, amount)` | Record outflow for limit tracking |
| `check_bilateral_limit(counterparty, amount)` | Check if within bilateral limit |
| `check_multilateral_limit(amount)` | Check if within multilateral limit |
| `reset_daily_outflows()` | Reset outflow tracking (called at EOD) |

### State Register Operations

| Method | Description |
|--------|-------------|
| `set_state_register(key, value)` | Set register (key must start with "bank_state_", max 10) |
| `get_state_register(key)` | Get register value |
| `clear_state_registers()` | Clear all registers (called at EOD) |

### Budget Operations

| Method | Description |
|--------|-------------|
| `set_release_budget(max, focus, per_counterparty)` | Configure release budget for tick |
| `can_release_to(counterparty, amount)` | Check if release allowed within budget |
| `record_release(counterparty, amount)` | Record release against budget |
| `reset_release_budget()` | Reset budget (called each tick) |

---

## Credit Capacity Formula

```
Total Available Liquidity = Balance Component + Credit Component

Balance Component:
  = max(0, balance)

Credit Component:
  = max(0, total_headroom - credit_used)

where:
  credit_used = max(0, -balance)
  total_headroom = unsecured_cap + collateral_capacity
  collateral_capacity = floor(posted_collateral × (1 - haircut))
```

**Example:**
```
Agent has:
- balance = -$500 (using credit)
- posted_collateral = $1,000
- collateral_haircut = 0.02 (2%)
- unsecured_cap = $200

Calculation:
- credit_used = $500
- collateral_capacity = $1,000 × 0.98 = $980
- total_headroom = $200 + $980 = $1,180
- available_credit = $1,180 - $500 = $680
- total_available = $0 + $680 = $680
```

---

## Daily Reset Operations

At end of each day:

1. **Outflow limits reset:**
   - `bilateral_outflows` cleared
   - `total_outflow` set to 0

2. **State registers cleared:**
   - `state_registers` emptied

3. **Collateral timers processed:**
   - Check for scheduled withdrawals

---

## Error Types

### AgentError

| Variant | Description |
|---------|-------------|
| `InsufficientLiquidity { required, available }` | Payment exceeds available liquidity |

### WithdrawError

| Variant | Description |
|---------|-------------|
| `NonPositive` | Withdrawal amount must be positive |
| `MinHoldingPeriodNotMet { ticks_remaining, posted_at_tick }` | Collateral minimum hold period not met |
| `NoHeadroom { credit_used, allowed_limit, headroom }` | Insufficient headroom for withdrawal |

---

## Configuration Mapping

How `AgentConfig` YAML fields map to runtime `Agent` fields:

| Config Field | Runtime Field | Notes |
|--------------|---------------|-------|
| `id` | `id` | Direct |
| `opening_balance` | `balance` | Initial value |
| `unsecured_cap` | `unsecured_cap` | Direct |
| `posted_collateral` | `posted_collateral` | Direct |
| `collateral_haircut` | `collateral_haircut` | Default 0.02 |
| `limits.bilateral_limits` | `bilateral_limits` | Direct |
| `limits.multilateral_limit` | `multilateral_limit` | Direct |
| `liquidity_pool × fraction` | `allocated_liquidity` | Calculated |

---

## See Also

- [Agent Configuration](../../scenario/agents.md) - YAML configuration reference
- [Transaction](transaction.md) - Transaction model
- [Architecture: Domain Models](../../architecture/05-domain-models.md) - High-level overview

---

*Last Updated: 2025-12-12*
