# Cost Rates Configuration

The `cost_rates` block configures **all costs, fees, and penalties** in the simulation. These drive agent decision-making and determine simulation outcomes.

---

## Schema

```yaml
cost_rates:
  # Recurring costs (per-tick)
  overdraft_bps_per_tick: <float>           # Default: 0.001
  delay_cost_per_tick_per_cent: <float>     # Default: 0.0001
  collateral_cost_per_tick_bps: <float>     # Default: 0.0002
  liquidity_cost_per_tick_bps: <float>      # Default: 0.0 (Enhancement 11.2)

  # One-time penalties
  eod_penalty_per_transaction: <int>        # Default: 10000 cents
  deadline_penalty: <int>                   # Default: 50000 cents
  split_friction_cost: <int>                # Default: 1000 cents

  # Multipliers
  overdue_delay_multiplier: <float>         # Default: 5.0
  priority_delay_multipliers:               # Optional (Enhancement 11.1)
    urgent_multiplier: <float>              # Default: 1.0
    normal_multiplier: <float>              # Default: 1.0
    low_multiplier: <float>                 # Default: 1.0
```

---

## Field Reference

### `overdraft_bps_per_tick`

**Type**: `float`
**Required**: No
**Constraint**: `>= 0`
**Default**: `0.001` (0.1 basis points)

Cost charged per tick for using overdraft (negative balance).

#### Implementation Details

**Python Schema** (`schemas.py:521-522`):
```python
overdraft_bps_per_tick: float = Field(default=0.001, ge=0)
```

**Rust** (`engine.rs:524-525`):
```rust
pub overdraft_bps_per_tick: f64,
```

#### Calculation

```
overdraft_cost = |negative_balance| × overdraft_bps_per_tick / 10000
```

#### Example Values

| Value | Description | Cost per $10,000 overdraft per tick |
|:------|:------------|:------------------------------------|
| `0.001` | Default | $0.001 |
| `0.01` | 10x default | $0.01 |
| `0.50` | Expensive | $0.50 |
| `0` | Free credit | $0 |

#### Example

```yaml
cost_rates:
  overdraft_bps_per_tick: 0.50    # Expensive overdraft
```

---

### `delay_cost_per_tick_per_cent`

**Type**: `float`
**Required**: No
**Constraint**: `>= 0`
**Default**: `0.0001`

Cost per tick per cent of unsettled transaction value.

#### Implementation Details

**Python Schema** (`schemas.py:523-524`):
```python
delay_cost_per_tick_per_cent: float = Field(default=0.0001, ge=0)
```

**Rust** (`engine.rs:528-529`):
```rust
pub delay_cost_per_tick_per_cent: f64,
```

#### Calculation

```
delay_cost = transaction_amount × delay_cost_per_tick_per_cent
```

For a $10,000 transaction with default rate:
```
delay_cost = 1,000,000 cents × 0.0001 = $100 per tick
```

#### Example Values

| Value | Description |
|:------|:------------|
| `0.0001` | Default |
| `0.01` | BIS model (1% delay per period) |
| `0.00035` | High-cost scenario |
| `0` | No delay penalty |

#### Example

```yaml
cost_rates:
  delay_cost_per_tick_per_cent: 0.01    # 1% per tick (BIS model)
```

---

### `collateral_cost_per_tick_bps`

**Type**: `float`
**Required**: No
**Constraint**: `>= 0`
**Default**: `0.0002`

Opportunity cost of posted collateral per tick (in basis points).

#### Implementation Details

**Python Schema** (`schemas.py:525-526`):
```python
collateral_cost_per_tick_bps: float = Field(default=0.0002, ge=0)
```

**Rust** (`engine.rs:532-533`):
```rust
pub collateral_cost_per_tick_bps: f64,
```

#### Calculation

```
collateral_cost = posted_collateral × collateral_cost_per_tick_bps / 10000
```

#### Use Case

- Represents lost investment returns on collateral
- Encourages agents to minimize posted collateral
- Balances against benefits of increased credit capacity

#### Example

```yaml
cost_rates:
  collateral_cost_per_tick_bps: 0.0003    # Cheap collateral
```

---

### `liquidity_cost_per_tick_bps`

**Type**: `float`
**Required**: No
**Constraint**: `>= 0`
**Default**: `0.0`

**Enhancement 11.2**: Opportunity cost of allocated liquidity from `liquidity_pool`.

#### Implementation Details

**Python Schema** (`schemas.py:535-536`):
```python
liquidity_cost_per_tick_bps: float = Field(default=0.0, ge=0)
```

**Rust** (`engine.rs:548-549`):
```rust
pub liquidity_cost_per_tick_bps: f64,
```

#### Calculation

```
liquidity_cost = allocated_liquidity × liquidity_cost_per_tick_bps / 10000
```

#### BIS Model Context

In BIS Box 3:
- `liquidity_cost_per_tick_bps: 150` represents 1.5% opportunity cost
- Balances against delay costs
- Optimal allocation minimizes total cost

#### Example

```yaml
cost_rates:
  liquidity_cost_per_tick_bps: 150    # 1.5% per tick (BIS model)
```

---

### `eod_penalty_per_transaction`

**Type**: `int` (cents)
**Required**: No
**Constraint**: `>= 0`
**Default**: `10000` ($100.00)

One-time penalty for each transaction unsettled at end of day.

#### Implementation Details

**Python Schema** (`schemas.py:527-528`):
```python
eod_penalty_per_transaction: int = Field(default=10000, ge=0)
```

**Rust** (`engine.rs:536-537`):
```rust
pub eod_penalty_per_transaction: i64,
```

#### Behavior

- Applied at the last tick of each day
- Per unsettled transaction (not per cent)
- Incentivizes clearing queues before EOD

#### Example Values

| Value | Dollars | Description |
|:------|:--------|:------------|
| `10000` | $100 | Default |
| `25000` | $250 | Heavy penalty |
| `0` | $0 | No EOD penalty |

#### Example

```yaml
cost_rates:
  eod_penalty_per_transaction: 25000    # $250 per unsettled
```

---

### `deadline_penalty`

**Type**: `int` (cents)
**Required**: No
**Constraint**: `>= 0`
**Default**: `50000` ($500.00)

One-time penalty when a transaction becomes overdue (passes its deadline).

#### Implementation Details

**Python Schema** (`schemas.py:529-530`):
```python
deadline_penalty: int = Field(default=50000, ge=0)
```

**Rust** (`engine.rs:540-541`):
```rust
pub deadline_penalty: i64,
```

#### Behavior

- Applied once when transaction transitions to overdue
- In addition to ongoing delay costs
- Can be compared against overdraft costs in policies

#### Example Values

| Value | Dollars | Description |
|:------|:--------|:------------|
| `50000` | $500 | Default |
| `12000` | $120 | Moderate |
| `0` | $0 | No deadline penalty |

#### Example

```yaml
cost_rates:
  deadline_penalty: 12000    # $120 one-time penalty
```

---

### `split_friction_cost`

**Type**: `int` (cents)
**Required**: No
**Constraint**: `>= 0`
**Default**: `1000` ($10.00)

Fixed cost per split operation.

#### Implementation Details

**Python Schema** (`schemas.py:531-532`):
```python
split_friction_cost: int = Field(default=1000, ge=0)
```

**Rust** (`engine.rs:544-545`):
```rust
pub split_friction_cost: i64,
```

#### Behavior

- Applied each time a transaction is split
- Discourages excessive splitting
- Balances against liquidity benefits of smaller payments

#### Example

```yaml
cost_rates:
  split_friction_cost: 8000    # $80 per split
```

---

### `overdue_delay_multiplier`

**Type**: `float`
**Required**: No
**Constraint**: `>= 0`
**Default**: `5.0`

Multiplier applied to delay costs once a transaction becomes overdue.

#### Implementation Details

**Python Schema** (`schemas.py:533-534`):
```python
overdue_delay_multiplier: float = Field(default=5.0, ge=0)
```

**Rust** (`engine.rs:552-553`):
```rust
pub overdue_delay_multiplier: f64,
```

#### Behavior

```
effective_delay_cost = base_delay_cost × overdue_delay_multiplier
```

For default values (5.0x):
- Before deadline: `amount × 0.0001` per tick
- After deadline: `amount × 0.0001 × 5.0` per tick

#### Example Values

| Value | Description |
|:------|:------------|
| `5.0` | Default (5x escalation) |
| `1.0` | No escalation (BIS model) |
| `10.0` | Severe escalation |

#### Example

```yaml
cost_rates:
  overdue_delay_multiplier: 1.0    # No escalation (BIS model)
```

---

### `priority_delay_multipliers`

**Type**: `PriorityDelayMultipliers` (optional object)
**Required**: No
**Default**: `None` (no priority-based adjustment)

**Enhancement 11.1**: Per-priority-band delay cost multipliers.

#### Schema

```yaml
priority_delay_multipliers:
  urgent_multiplier: <float>   # Default: 1.0, for priority 8-10
  normal_multiplier: <float>   # Default: 1.0, for priority 4-7
  low_multiplier: <float>      # Default: 1.0, for priority 0-3
```

#### Implementation Details

**Python Schema** (`schemas.py:500-517`):
```python
class PriorityDelayMultipliers(BaseModel):
    urgent_multiplier: float = Field(default=1.0, ge=0)
    normal_multiplier: float = Field(default=1.0, ge=0)
    low_multiplier: float = Field(default=1.0, ge=0)
```

**Rust** (`engine.rs:480-515`):
```rust
pub struct PriorityDelayMultipliers {
    pub urgent_multiplier: f64,
    pub normal_multiplier: f64,
    pub low_multiplier: f64,
}
```

#### Behavior

Delay cost is multiplied based on transaction priority:

```
delay_cost = base_delay_cost × priority_multiplier
```

Where `priority_multiplier` is:
- `urgent_multiplier` for priority 8-10
- `normal_multiplier` for priority 4-7
- `low_multiplier` for priority 0-3

#### BIS Model Example

```yaml
cost_rates:
  delay_cost_per_tick_per_cent: 0.01
  priority_delay_multipliers:
    urgent_multiplier: 1.5    # Urgent: 1.5% delay cost
    normal_multiplier: 1.0    # Normal: 1.0% delay cost
    low_multiplier: 0.5       # Low: 0.5% delay cost
```

---

## Complete Examples

### Default Configuration

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

### BIS Box 3 Model

```yaml
cost_rates:
  # Active BIS costs
  delay_cost_per_tick_per_cent: 0.01           # 1% base
  priority_delay_multipliers:
    urgent_multiplier: 1.5                      # 1.5% for urgent
    normal_multiplier: 1.0                      # 1.0% for normal
    low_multiplier: 0.5                         # 0.5% for low
  liquidity_cost_per_tick_bps: 150             # 1.5% opportunity cost

  # Disabled (not in BIS model)
  overdraft_bps_per_tick: 0
  collateral_cost_per_tick_bps: 0
  eod_penalty_per_transaction: 0
  deadline_penalty: 0
  split_friction_cost: 0
  overdue_delay_multiplier: 1.0
```

### High-Stress Crisis Scenario

```yaml
cost_rates:
  delay_cost_per_tick_per_cent: 0.00035        # High delay cost
  overdraft_bps_per_tick: 0.50                 # Expensive credit
  collateral_cost_per_tick_bps: 0.0003         # Cheap collateral
  eod_penalty_per_transaction: 25000           # Heavy EOD penalty
  deadline_penalty: 12000                       # Sharp deadline miss
  overdue_delay_multiplier: 5.0                # Severe escalation
  split_friction_cost: 8000                    # Splitting has friction
```

---

## Cost Calculation Summary

### Per-Tick Costs

| Cost Type | Formula |
|:----------|:--------|
| Overdraft | `abs(negative_balance) × overdraft_bps / 10000` |
| Delay (normal) | `amount × delay_rate × priority_multiplier` |
| Delay (overdue) | `amount × delay_rate × priority_multiplier × overdue_multiplier` |
| Collateral | `posted × collateral_bps / 10000` |
| Liquidity | `allocated × liquidity_bps / 10000` |

### One-Time Costs

| Cost Type | When Applied |
|:----------|:-------------|
| Deadline penalty | Transaction becomes overdue |
| EOD penalty | Per unsettled transaction at day end |
| Split friction | Per split operation |

---

## Policy Integration

Cost rates are available in JSON policies as fields:

| Field | Cost Rate |
|:------|:----------|
| `cost_overdraft_bps_per_tick` | `overdraft_bps_per_tick` |
| `cost_delay_per_tick_per_cent` | `delay_cost_per_tick_per_cent` |
| `cost_collateral_bps_per_tick` | `collateral_cost_per_tick_bps` |
| `cost_split_friction` | `split_friction_cost` |
| `cost_deadline_penalty` | `deadline_penalty` |
| `cost_eod_penalty` | `eod_penalty_per_transaction` |

Derived fields for current transaction:
- `cost_delay_this_tx_one_tick`
- `cost_overdraft_this_amount_one_tick`

---

## Implementation Location

| Component | File | Lines |
|:----------|:-----|:------|
| Python CostRates | `api/payment_simulator/config/schemas.py` | 520-550 |
| Python PriorityMultipliers | `api/payment_simulator/config/schemas.py` | 500-517 |
| Rust CostRates | `simulator/src/orchestrator/engine.rs` | 522-599 |
| Rust PriorityMultipliers | `simulator/src/orchestrator/engine.rs` | 480-515 |
| FFI Parsing | `simulator/src/ffi/types.rs` | 782-869 |

---

## Navigation

**Previous**: [Distributions](distributions.md)
**Next**: [LSM Configuration](lsm-config.md)
