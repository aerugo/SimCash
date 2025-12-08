# Agent Model

**Location:** `simulator/src/models/agent.rs`

Represents a bank participating in the payment system with settlement account, credit facilities, internal queue management, and policy state.

---

## Overview

An Agent represents a bank's position in the settlement system:
- **Settlement account balance** (positive = reserves, negative = using credit)
- **Credit facilities** (unsecured cap + collateralized credit)
- **Queue 1** (internal queue for cash manager decisions)
- **Policy state** (registers, budgets, timers)
- **Limits** (bilateral and multilateral outflow limits)

---

## Struct Definition

**Location:** `agent.rs:141-278`

```rust
pub struct Agent {
    // Identity
    id: String,

    // Settlement Account
    balance: i64,

    // Queue 1 (Internal)
    outgoing_queue: Vec<String>,
    incoming_expected: Vec<String>,
    last_decision_tick: Option<usize>,
    liquidity_buffer: i64,

    // Credit Facilities
    posted_collateral: i64,
    collateral_haircut: f64,
    unsecured_cap: i64,
    collateral_posted_at_tick: Option<usize>,

    // Policy State (Phase 3.3+)
    release_budget_max: Option<i64>,
    release_budget_remaining: i64,
    release_budget_focus_counterparties: Option<Vec<String>>,
    release_budget_per_counterparty_limit: Option<i64>,
    release_budget_per_counterparty_usage: HashMap<String, i64>,
    collateral_withdrawal_timers: HashMap<usize, Vec<(i64, String, usize)>>,
    state_registers: HashMap<String, f64>,

    // TARGET2 Limits (Phase 1)
    bilateral_limits: HashMap<String, i64>,
    multilateral_limit: Option<i64>,
    bilateral_outflows: HashMap<String, i64>,
    total_outflow: i64,

    // Liquidity Pool (Enhancement 11.2)
    allocated_liquidity: i64,
}
```

---

## Fields

### Identity

#### `id`

**Type:** `String`
**Location:** `agent.rs:144`

Unique agent identifier (e.g., "BANK_A").

---

### Settlement Account

#### `balance`

**Type:** `i64` (cents)
**Location:** `agent.rs:152`

Current balance in settlement account at central bank.

**Values:**
- Positive: Funds available (reserves)
- Negative: Using intraday credit
- Zero: No reserves, not in overdraft

**CRITICAL:** Always integer cents.

---

### Queue 1 (Internal Queue)

#### `outgoing_queue`

**Type:** `Vec<String>`
**Location:** `agent.rs:161`

Transaction IDs awaiting cash manager release decision.

**Usage:**
- Transactions enter when they arrive from clients
- Cash manager policy decides when to release to RTGS
- Ordered by arrival or by `Queue1Ordering` strategy

---

#### `incoming_expected`

**Type:** `Vec<String>`
**Location:** `agent.rs:167`

Expected incoming transaction IDs.

**Usage:**
- For liquidity forecasting
- Populated when this agent is a receiver

---

#### `last_decision_tick`

**Type:** `Option<usize>`
**Location:** `agent.rs:172`

Last tick when cash manager made a policy decision.

**Usage:**
- Avoid redundant policy evaluations within same tick
- `None` if never evaluated

---

#### `liquidity_buffer`

**Type:** `i64` (cents)
**Default:** `0`
**Location:** `agent.rs:178`

Target minimum balance to maintain.

**Usage:**
- Cash manager policies may hold transactions if `balance - amount < buffer`
- Override for urgent transactions

---

### Credit Facilities

#### `posted_collateral`

**Type:** `i64` (cents)
**Default:** `0`
**Location:** `agent.rs:185`

Collateral posted to secure intraday credit.

**Effects:**
- Provides credit capacity (discounted by haircut)
- Accrues opportunity cost per tick

---

#### `collateral_haircut`

**Type:** `f64`
**Default:** `0.02` (2%)
**Location:** `agent.rs:197`

Discount rate applied to collateral value.

**Values:**
- `0.00` = 0% haircut (high-quality bonds)
- `0.02` = 2% haircut (typical T2/CLM)
- `0.10` = 10% haircut (lower quality)

**Formula:**
```
collateral_capacity = posted_collateral × (1 - haircut)
```

---

#### `unsecured_cap`

**Type:** `i64` (cents)
**Default:** `0`
**Location:** `agent.rs:206`

Unsecured daylight overdraft capacity.

**Usage:**
- Credit without collateral
- Typically priced higher than collateralized

---

#### `collateral_posted_at_tick`

**Type:** `Option<usize>`
**Location:** `agent.rs:213`

Tick when collateral was last posted.

**Usage:**
- Enforce minimum holding period (default 5 ticks)
- Prevent posting/withdrawal oscillation

---

### Policy State

#### `release_budget_max` / `release_budget_remaining`

**Type:** `Option<i64>` / `i64`
**Location:** `agent.rs:218-221`

Release budget for current tick.

- `release_budget_max`: Maximum budget set (None = unlimited)
- `release_budget_remaining`: Amount remaining

**Usage:**
- Limit total releases per tick
- Set by `SetBudget` policy instruction

---

#### `release_budget_focus_counterparties`

**Type:** `Option<Vec<String>>`
**Location:** `agent.rs:226`

Allowed counterparties for releases.

- `None`: All counterparties allowed
- `Some([])`: No counterparties (blocks all)
- `Some([A, B])`: Only A and B allowed

---

#### `release_budget_per_counterparty_limit` / `usage`

**Type:** `Option<i64>` / `HashMap<String, i64>`
**Location:** `agent.rs:230-234`

Per-counterparty limits and tracking.

---

#### `collateral_withdrawal_timers`

**Type:** `HashMap<usize, Vec<(i64, String, usize)>>`
**Location:** `agent.rs:240`

Scheduled automatic collateral withdrawals.

**Structure:**
- Key: Tick number
- Value: Vec of (amount, reason, posted_at_tick)

---

#### `state_registers`

**Type:** `HashMap<String, f64>`
**Location:** `agent.rs:247`

State registers for policy micro-memory.

**Constraints:**
- Maximum 10 per agent
- Keys must be prefixed with "bank_state_"
- Reset at EOD

---

### TARGET2 Limits

#### `bilateral_limits`

**Type:** `HashMap<String, i64>`
**Location:** `agent.rs:253`

Maximum outflow per counterparty per day.

---

#### `multilateral_limit`

**Type:** `Option<i64>`
**Location:** `agent.rs:257`

Maximum total outflow per day.

---

#### `bilateral_outflows` / `total_outflow`

**Type:** `HashMap<String, i64>` / `i64`
**Location:** `agent.rs:262-266`

Daily outflow tracking (reset at start of each day).

---

### Liquidity Pool

#### `allocated_liquidity`

**Type:** `i64` (cents)
**Default:** `0`
**Location:** `agent.rs:277`

Liquidity allocated from external pool.

**Usage:**
- Tracks allocation for opportunity cost calculation
- Separate from opening_balance

---

## Key Methods

### Constructors

#### `Agent::new(id, balance)`

Create new agent with opening balance.

```rust
let agent = Agent::new("BANK_A".to_string(), 1_000_000);
```

#### `Agent::with_buffer(id, balance, liquidity_buffer)`

Create agent with specified liquidity buffer.

```rust
let agent = Agent::with_buffer("BANK_A".to_string(), 1_000_000, 100_000);
```

#### `Agent::restore(data: AgentRestoreData)`

Restore from checkpoint snapshot.

---

### Balance Operations

#### `balance() -> i64`

Get current balance (cents).

#### `credit_used() -> i64`

Amount of credit in use (absolute value of negative balance).

```rust
let agent = Agent::new("A".to_string(), -50_000);
assert_eq!(agent.credit_used(), 50_000);  // Using $500 credit
```

#### `available_liquidity() -> i64`

Calculate total available liquidity.

**Formula:**
```
available = max(0, balance) + max(0, headroom - credit_used)

where:
  headroom = unsecured_cap + floor(collateral × (1 - haircut))
  credit_used = max(0, -balance)
```

#### `can_pay(amount) -> bool`

Check if agent can afford payment.

```rust
if agent.can_pay(100_000) {
    // Sufficient liquidity
}
```

#### `debit(amount) -> Result<(), AgentError>`

Debit agent's balance (payment outflow).

**Errors:**
- `InsufficientLiquidity` if `amount > available_liquidity()`

#### `credit(amount)`

Credit agent's balance (payment inflow). Always succeeds.

---

### Credit Facility Methods

#### `allowed_overdraft_limit() -> i64`

Maximum negative balance allowed.

**Formula:**
```
limit = floor(collateral × (1 - haircut)) + unsecured_cap
```

#### `headroom() -> i64`

Remaining credit capacity.

```
headroom = allowed_overdraft_limit - credit_used
```

#### `max_withdrawable_collateral(buffer) -> i64`

Maximum collateral that can be safely withdrawn.

#### `collateral_capacity() -> i64`

Credit capacity from collateral (after haircut).

---

### Queue 1 Operations

#### `queue_outgoing(tx_id)`

Add transaction to Queue 1.

```rust
agent.queue_outgoing("tx_123".to_string());
```

#### `outgoing_queue() -> &Vec<String>`

Get Queue 1 contents.

#### `outgoing_queue_size() -> usize`

Get Queue 1 size.

#### `remove_from_outgoing(tx_id) -> bool`

Remove transaction from Queue 1. Returns true if found.

#### `replace_outgoing_queue(new_queue)`

Replace entire Queue 1 (for reordering).

---

### Collateral Operations

#### `set_posted_collateral(amount)`

Set collateral amount.

#### `posted_collateral() -> i64`

Get posted collateral.

#### `set_collateral_haircut(haircut)`

Set haircut rate (0.0 to 1.0).

#### `collateral_haircut() -> f64`

Get haircut rate.

---

### Limit Operations

#### `set_bilateral_limits(limits)`

Set per-counterparty limits.

#### `set_multilateral_limit(limit)`

Set total outflow limit.

#### `record_outflow(counterparty, amount)`

Record outflow for limit tracking.

#### `check_bilateral_limit(counterparty, amount) -> bool`

Check if within bilateral limit.

#### `check_multilateral_limit(amount) -> bool`

Check if within multilateral limit.

#### `reset_daily_outflows()`

Reset outflow tracking (called at EOD).

---

### State Register Operations

#### `set_state_register(key, value) -> Result<(), String>`

Set a state register value.

**Constraints:**
- Key must start with "bank_state_"
- Maximum 10 registers

#### `get_state_register(key) -> Option<f64>`

Get state register value.

#### `clear_state_registers()`

Clear all state registers (called at EOD).

---

### Budget Operations

#### `set_release_budget(max, focus, per_counterparty)`

Configure release budget for tick.

#### `can_release_to(counterparty, amount) -> bool`

Check if release is allowed within budget.

#### `record_release(counterparty, amount)`

Record release against budget.

#### `reset_release_budget()`

Reset budget (called each tick).

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

## Related Types

### `AgentRestoreData`

**Location:** `agent.rs:84-115`

Data structure for checkpoint restoration.

```rust
pub struct AgentRestoreData {
    pub id: String,
    pub balance: i64,
    pub unsecured_cap: i64,
    pub outgoing_queue: Vec<String>,
    pub incoming_expected: Vec<String>,
    pub last_decision_tick: Option<usize>,
    pub liquidity_buffer: i64,
    pub posted_collateral: i64,
    pub collateral_haircut: f64,
    pub collateral_posted_at_tick: Option<usize>,
    pub bilateral_limits: HashMap<String, i64>,
    pub multilateral_limit: Option<i64>,
    pub bilateral_outflows: HashMap<String, i64>,
    pub total_outflow: i64,
    pub allocated_liquidity: Option<i64>,
}
```

### `AgentError`

**Location:** `agent.rs:25-29`

```rust
pub enum AgentError {
    InsufficientLiquidity { required: i64, available: i64 },
}
```

### `WithdrawError`

**Location:** `agent.rs:32-49`

```rust
pub enum WithdrawError {
    NonPositive,
    MinHoldingPeriodNotMet { ticks_remaining: usize, posted_at_tick: usize },
    NoHeadroom { credit_used: i64, allowed_limit: i64, headroom: i64 },
}
```

---

## Configuration Mapping

| AgentConfig Field | Agent Field | Notes |
|-------------------|-------------|-------|
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

- [AgentConfig](../01-configuration/agent-config.md) - Configuration
- [Transaction](transaction.md) - Transaction model
- [SimulationState](simulation-state.md) - State management
- [Queue1 Internal](../04-queues/queue1-internal.md) - Queue details
- [Collateral Events](../07-events/collateral-events.md) - Collateral operations

---

*Last Updated: 2025-11-28*
