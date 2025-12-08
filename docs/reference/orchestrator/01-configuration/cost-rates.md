# CostRates

**Location:** `simulator/src/orchestrator/engine.rs:522-599`

Configuration for all cost calculations in the simulation. Defines rates for overdraft costs, delay penalties, collateral opportunity costs, and other simulation expenses.

---

## Struct Definition

```rust
#[derive(Debug, Clone, serde::Serialize, serde::Deserialize)]
pub struct CostRates {
    pub overdraft_bps_per_tick: f64,
    pub delay_cost_per_tick_per_cent: f64,
    pub collateral_cost_per_tick_bps: f64,
    pub eod_penalty_per_transaction: i64,
    pub deadline_penalty: i64,
    pub split_friction_cost: i64,
    pub overdue_delay_multiplier: f64,
    pub priority_delay_multipliers: Option<PriorityDelayMultipliers>,
    pub liquidity_cost_per_tick_bps: f64,
}
```

---

## Fields

### `overdraft_bps_per_tick`

**Type:** `f64`
**Default:** `0.001`
**Location:** `engine.rs:523-525`

Overdraft cost rate in basis points per tick.

**Description:**
Applied when agent's balance is negative. Cost calculated on the overdraft amount (negative balance portion).

**Formula:**
```
overdraft_cost = |min(balance, 0)| × overdraft_bps_per_tick / 10000
```

**Example Values:**
- `0.001` = 1 bp/tick ≈ 10 bp/day (for 100 ticks/day)
- `0.01` = 10 bp/tick ≈ 100 bp/day

**Example:**
```yaml
cost_rates:
  overdraft_bps_per_tick: 0.001
```

**Calculation Example:**
- Balance: -$100,000 (in cents: -10,000,000)
- Rate: 0.001 (1 bp/tick)
- Cost: 10,000,000 × 0.001 / 10000 = 1 cent/tick = $0.01/tick

**Related:**
- See [Cost Calculations](../06-costs/cost-calculations.md)
- See [CostAccumulator](../06-costs/cost-accumulator.md)

---

### `delay_cost_per_tick_per_cent`

**Type:** `f64`
**Default:** `0.0001`
**Location:** `engine.rs:527-529`

Queue delay cost per tick per cent of queued value.

**Description:**
Applied to transactions waiting in Queue 1 or Queue 2. Represents opportunity cost of delayed settlement.

**Formula:**
```
delay_cost = remaining_amount × delay_cost_per_tick_per_cent × delay_multiplier
```

Where `delay_multiplier` depends on priority (if configured) and overdue status.

**Example Values:**
- `0.0001` = 0.01% per tick
- `0.001` = 0.1% per tick (higher urgency penalty)

**Example:**
```yaml
cost_rates:
  delay_cost_per_tick_per_cent: 0.0001
```

**Calculation Example:**
- Queued amount: $10,000 (1,000,000 cents)
- Rate: 0.0001
- Cost: 1,000,000 × 0.0001 = 100 cents/tick = $1.00/tick

**Related:**
- Modified by `overdue_delay_multiplier` when transaction is overdue
- Modified by `priority_delay_multipliers` when configured

---

### `collateral_cost_per_tick_bps`

**Type:** `f64`
**Default:** `0.0002`
**Location:** `engine.rs:531-533`

Collateral opportunity cost in basis points per tick (Phase 8).

**Description:**
Represents the opportunity cost of posting collateral with the central bank instead of earning interest in the market.

**Formula:**
```
collateral_cost = posted_collateral × collateral_cost_per_tick_bps / 10000
```

**Example Values:**
- `0.0002` = 0.02 bp/tick ≈ 2 bp/day (for 100 ticks/day)
- `0.0005` = 0.05 bp/tick ≈ 5 bp/day

**Example:**
```yaml
cost_rates:
  collateral_cost_per_tick_bps: 0.0002
```

**Calculation Example:**
- Posted collateral: $100,000 (10,000,000 cents)
- Rate: 0.0002 (0.02 bp/tick)
- Cost: 10,000,000 × 0.0002 / 10000 = 0.2 cents/tick

**Related:**
- See [Collateral Events](../07-events/collateral-events.md)

---

### `eod_penalty_per_transaction`

**Type:** `i64` (cents)
**Default:** `10_000`
**Location:** `engine.rs:535-536`

End-of-day penalty for each unsettled transaction.

**Description:**
One-time penalty applied at day boundary for each transaction still unsettled. Represents regulatory/operational cost of overnight carryover.

**Example Values:**
- `10_000` = $100 per unsettled transaction
- `50_000` = $500 per unsettled transaction

**Example:**
```yaml
cost_rates:
  eod_penalty_per_transaction: 10000  # $100
```

**Application:**
- Applied at end of each business day
- Accumulated in `penalty_cost` field of CostBreakdown
- See [EndOfDay Event](../07-events/system-events.md#endofday)

---

### `deadline_penalty`

**Type:** `i64` (cents)
**Default:** `50_000`
**Location:** `engine.rs:538-539`

One-time penalty for missing a transaction deadline.

**Description:**
Applied once when a transaction becomes overdue (passes its deadline tick without settlement). Represents regulatory/customer relationship cost.

**Example Values:**
- `50_000` = $500 per missed deadline
- `100_000` = $1,000 per missed deadline

**Example:**
```yaml
cost_rates:
  deadline_penalty: 50000  # $500
```

**Application:**
- Applied once when `current_tick > deadline_tick`
- Transaction status changes to `Overdue`
- See [TransactionWentOverdue Event](../07-events/cost-events.md#transactionwentoverdue)

---

### `split_friction_cost`

**Type:** `i64` (cents)
**Default:** `1_000`
**Location:** `engine.rs:541-548`

Cost per split when a transaction is divided.

**Description:**
Represents operational overhead of creating and processing multiple payment instructions instead of one. Applied when a policy splits a large transaction.

**Formula:**
```
total_split_cost = split_friction_cost × (num_splits - 1)
```

**Example:**
- 1 split into 3 parts: cost = 1,000 × 2 = $20
- 1 split into 5 parts: cost = 1,000 × 4 = $40

**Example:**
```yaml
cost_rates:
  split_friction_cost: 1000  # $10 per split
```

**Related:**
- See [LiquiditySplitting Policy](../08-policies/liquidity-splitting.md)
- See [PolicySplit Event](../07-events/arrival-events.md#policysplit)

---

### `overdue_delay_multiplier`

**Type:** `f64`
**Default:** `5.0`
**Location:** `engine.rs:550-557`

Multiplier for delay cost when transaction is overdue.

**Description:**
Overdue transactions incur escalating costs to represent urgency. The base delay cost is multiplied by this factor.

**Formula:**
```
overdue_delay_cost = base_delay_cost × overdue_delay_multiplier
```

**Example Values:**
- `5.0` = 5x penalty for overdue (default)
- `10.0` = 10x penalty (high urgency environment)
- `1.0` = No additional penalty

**Example:**
```yaml
cost_rates:
  overdue_delay_multiplier: 5.0
```

**Calculation Example:**
- Base delay cost: $1.00/tick
- Multiplier: 5.0
- Overdue delay cost: $5.00/tick

---

### `priority_delay_multipliers`

**Type:** `Option<PriorityDelayMultipliers>`
**Default:** `None`
**Location:** `engine.rs:559-569`

Priority-based delay cost differentiation (BIS model support).

**Description:**
When configured, applies different multipliers to delay costs based on transaction priority bands. Allows modeling different urgency levels.

**Example:**
```yaml
cost_rates:
  priority_delay_multipliers:
    urgent_multiplier: 1.5   # 50% higher for urgent
    normal_multiplier: 1.0   # Standard rate
    low_multiplier: 0.5      # 50% lower for low priority
```

**Application:**
```
effective_delay_cost = base_delay_cost × priority_multiplier
```

**Priority Bands:**
| Band | Priority Range | Default Multiplier |
|------|----------------|-------------------|
| Urgent | 8-10 | 1.0 |
| Normal | 4-7 | 1.0 |
| Low | 0-3 | 1.0 |

**Related:**
- See [PriorityDelayMultipliers](#prioritydelaymultipliers)
- See [Priority Multipliers](../06-costs/priority-multipliers.md)

---

### `liquidity_cost_per_tick_bps`

**Type:** `f64`
**Default:** `0.0`
**Location:** `engine.rs:571-582`

Liquidity opportunity cost in basis points per tick (Enhancement 11.2).

**Description:**
Applied to allocated liquidity (from `liquidity_pool × allocation_fraction`) to represent the opportunity cost of holding funds in the settlement system rather than earning interest elsewhere.

**Formula:**
```
liquidity_cost = allocated_liquidity × liquidity_cost_per_tick_bps / 10000
```

**NOTE:** Only applies to allocated liquidity, not to `opening_balance`.

**Example Values:**
- `0.0` = No opportunity cost (default)
- `15.0` = 15 bp/tick for allocated liquidity

**Example:**
```yaml
cost_rates:
  liquidity_cost_per_tick_bps: 15.0
```

**Calculation Example:**
- Allocated liquidity: $100,000 (10,000,000 cents)
- Rate: 15 bp/tick
- Cost: 10,000,000 × 15 / 10000 = 15,000 cents/tick = $150/tick

**Related:**
- See [AgentConfig.liquidity_pool](agent-config.md#liquidity_pool)

---

## Related Types

### `PriorityDelayMultipliers`

**Location:** `engine.rs:481-498`

```rust
#[derive(Debug, Clone, serde::Serialize, serde::Deserialize)]
pub struct PriorityDelayMultipliers {
    /// Multiplier for urgent priority (8-10). Default: 1.0
    pub urgent_multiplier: f64,
    /// Multiplier for normal priority (4-7). Default: 1.0
    pub normal_multiplier: f64,
    /// Multiplier for low priority (0-3). Default: 1.0
    pub low_multiplier: f64,
}
```

**Default Values:**
```rust
impl Default for PriorityDelayMultipliers {
    fn default() -> Self {
        Self {
            urgent_multiplier: 1.0,
            normal_multiplier: 1.0,
            low_multiplier: 1.0,
        }
    }
}
```

**Method:**
```rust
/// Get the delay cost multiplier for a given priority level
pub fn get_multiplier_for_priority(&self, priority: u8) -> f64 {
    match get_priority_band(priority) {
        PriorityBand::Urgent => self.urgent_multiplier,
        PriorityBand::Normal => self.normal_multiplier,
        PriorityBand::Low => self.low_multiplier,
    }
}
```

---

## Default Configuration

**Location:** `engine.rs:585-599`

```rust
impl Default for CostRates {
    fn default() -> Self {
        Self {
            overdraft_bps_per_tick: 0.001,        // 1 bp/tick
            delay_cost_per_tick_per_cent: 0.0001, // 0.1 bp/tick
            collateral_cost_per_tick_bps: 0.0002, // 2 bps annualized / 100 ticks
            eod_penalty_per_transaction: 10_000,  // $100 per unsettled tx
            deadline_penalty: 50_000,             // $500 per missed deadline
            split_friction_cost: 1000,            // $10 per split
            overdue_delay_multiplier: 5.0,        // 5x multiplier for overdue
            priority_delay_multipliers: None,     // No priority differentiation
            liquidity_cost_per_tick_bps: 0.0,     // No liquidity opportunity cost
        }
    }
}
```

---

## Python Configuration

**Location:** `api/payment_simulator/config/schemas.py`

```python
class PriorityDelayMultipliers(BaseModel):
    urgent_multiplier: float = 1.0
    normal_multiplier: float = 1.0
    low_multiplier: float = 1.0

class CostRates(BaseModel):
    overdraft_bps_per_tick: float = 0.001
    delay_cost_per_tick_per_cent: float = 0.0001
    collateral_cost_per_tick_bps: float = 0.0002
    eod_penalty_per_transaction: int = 10000
    deadline_penalty: int = 50000
    split_friction_cost: int = 1000
    overdue_delay_multiplier: float = 5.0
    priority_delay_multipliers: Optional[PriorityDelayMultipliers] = None
    liquidity_cost_per_tick_bps: float = 0.0
```

---

## Example Configurations

### Standard Configuration

```yaml
cost_rates:
  overdraft_bps_per_tick: 0.001
  delay_cost_per_tick_per_cent: 0.0001
  collateral_cost_per_tick_bps: 0.0002
  eod_penalty_per_transaction: 10000
  deadline_penalty: 50000
  split_friction_cost: 1000
  overdue_delay_multiplier: 5.0
```

### BIS Model Configuration (with priority differentiation)

```yaml
cost_rates:
  overdraft_bps_per_tick: 0.001
  delay_cost_per_tick_per_cent: 0.0001
  collateral_cost_per_tick_bps: 0.0002
  eod_penalty_per_transaction: 10000
  deadline_penalty: 50000
  split_friction_cost: 1000
  overdue_delay_multiplier: 5.0
  priority_delay_multipliers:
    urgent_multiplier: 1.5
    normal_multiplier: 1.0
    low_multiplier: 0.5
  liquidity_cost_per_tick_bps: 15.0
```

### High-Penalty Environment

```yaml
cost_rates:
  overdraft_bps_per_tick: 0.01      # 10x higher overdraft cost
  delay_cost_per_tick_per_cent: 0.001
  collateral_cost_per_tick_bps: 0.001
  eod_penalty_per_transaction: 100000  # $1,000
  deadline_penalty: 250000             # $2,500
  split_friction_cost: 5000            # $50
  overdue_delay_multiplier: 10.0       # 10x for overdue
```

---

## Cost Calculation Summary

| Cost Type | Rate Parameter | Formula | Accrues To |
|-----------|----------------|---------|------------|
| Overdraft | `overdraft_bps_per_tick` | `|min(balance,0)| × rate / 10000` | `liquidity_cost` |
| Delay | `delay_cost_per_tick_per_cent` | `remaining × rate × multipliers` | `delay_cost` |
| Collateral | `collateral_cost_per_tick_bps` | `collateral × rate / 10000` | `collateral_cost` |
| EOD Penalty | `eod_penalty_per_transaction` | `count × penalty` | `penalty_cost` |
| Deadline Penalty | `deadline_penalty` | `penalty` (once) | `penalty_cost` |
| Split Friction | `split_friction_cost` | `cost × (N-1)` | `split_friction_cost` |
| Liquidity Opp. | `liquidity_cost_per_tick_bps` | `allocated × rate / 10000` | `liquidity_opportunity_cost` |

---

## See Also

- [CostBreakdown](../06-costs/cost-breakdown.md) - Per-tick cost structure
- [CostAccumulator](../06-costs/cost-accumulator.md) - Accumulated costs
- [Cost Calculations](../06-costs/cost-calculations.md) - Detailed formulas
- [CostAccrual Event](../07-events/cost-events.md#costaccrual)
- [OrchestratorConfig](orchestrator-config.md) - Parent configuration

---

*Last Updated: 2025-11-28*
