# Arrival Configuration

Arrival configuration controls **automatic transaction generation** for agents. Each tick, the simulation generates new transactions based on these settings.

There are two mutually exclusive approaches:
1. **`arrival_config`**: Single configuration for all transactions
2. **`arrival_bands`**: Per-priority-band configuration (Enhancement 11.3)

---

## `arrival_config`

Single arrival configuration where all generated transactions share the same characteristics.

### Schema

```yaml
arrival_config:
  rate_per_tick: <float>                  # Required, >= 0
  amount_distribution: <AmountDist>       # Required, see distributions.md
  counterparty_weights: <Dict[str, float]> # Optional, default: {}
  deadline_range: [<int>, <int>]          # Required, [min, max] ticks
  priority: <int>                         # Optional, 0-10, default: 5
  priority_distribution: <PriorityDist>   # Optional, overrides priority
  divisible: <bool>                       # Optional, default: false
```

---

## Field Reference

### `rate_per_tick`

**Type**: `float`
**Required**: Yes
**Constraint**: `>= 0`
**Default**: None (required)

The expected number of transactions generated per tick (Poisson λ parameter).

#### Implementation Details

**Python Schema** (`schemas.py:127`):
```python
rate_per_tick: float = Field(..., ge=0)
```

**Rust** (`arrivals/mod.rs:64`):
```rust
pub rate_per_tick: f64,
```

#### Behavior

Actual arrivals per tick are sampled from a Poisson distribution:
- `rate = 0.5`: Average 0.5 transactions/tick, ~50% chance of 0, ~30% chance of 1
- `rate = 1.0`: Average 1 transaction/tick
- `rate = 2.0`: Average 2 transactions/tick

#### Example Values

| Rate | Description | ~Transactions per 100-tick day |
|:-----|:------------|:-------------------------------|
| `0.1` | Low activity | ~10 |
| `0.5` | Moderate | ~50 |
| `1.0` | Active | ~100 |
| `2.0` | High activity | ~200 |

---

### `amount_distribution`

**Type**: `AmountDistribution` (union type)
**Required**: Yes
**Constraint**: Valid distribution type
**Default**: None (required)

Distribution for sampling transaction amounts. See [distributions.md](distributions.md) for complete reference.

#### Quick Reference

| Type | Parameters | Use Case |
|:-----|:-----------|:---------|
| `Normal` | `mean`, `std_dev` | Symmetric around mean |
| `LogNormal` | `mean`, `std_dev` | Right-skewed, realistic |
| `Uniform` | `min`, `max` | Equal probability range |
| `Exponential` | `lambda` | Many small, few large |

#### Example

```yaml
amount_distribution:
  type: LogNormal
  mean: 11.51      # Log-scale mean
  std_dev: 0.9     # Log-scale std dev
```

---

### `counterparty_weights`

**Type**: `Dict[str, float]`
**Required**: No
**Constraint**: Keys must be valid agent IDs, values > 0
**Default**: `{}` (empty = uniform distribution)

Weights for selecting transaction receivers.

#### Implementation Details

**Python Schema** (`schemas.py:129`):
```python
counterparty_weights: Dict[str, float] = {}
```

**Rust** (`arrivals/mod.rs:66`):
```rust
pub counterparty_weights: HashMap<String, f64>,
```

#### Behavior

- Weights are normalized to sum to 1.0
- Higher weight = more likely to receive
- Empty dict = uniform probability across all other agents
- Self-transactions (sender = receiver) are automatically excluded

#### Example

```yaml
counterparty_weights:
  BANK_B: 0.6      # 60% of transactions go to BANK_B
  BANK_C: 0.4      # 40% go to BANK_C
  # BANK_A (self) excluded automatically
```

#### Uniform Distribution

```yaml
counterparty_weights: {}    # Equal probability for all other agents
```

---

### `deadline_range`

**Type**: `List[int]` with exactly 2 elements
**Required**: Yes
**Constraint**: `min > 0`, `max >= min`
**Default**: `[10, 50]` (FFI default, Python requires explicit)

Range of ticks from arrival to deadline.

#### Implementation Details

**Python Schema** (`schemas.py:130-137`):
```python
deadline_range: List[int] = Field(..., min_length=2, max_length=2)

@field_validator('deadline_range')
def validate_deadline_range(cls, v):
    if len(v) != 2:
        raise ValueError("deadline_range must have exactly 2 elements")
    if v[0] <= 0:
        raise ValueError("deadline_range min must be > 0")
    if v[1] < v[0]:
        raise ValueError("deadline_range max must be >= min")
    return v
```

**Rust** (`arrivals/mod.rs:67`):
```rust
pub deadline_range: (usize, usize),
```

#### Behavior

- Deadline tick = `arrival_tick + uniform_random(min, max)`
- Deadlines are always capped at episode end (`num_days × ticks_per_day`)
- Transactions past deadline become "overdue"
- Overdue transactions incur `deadline_penalty` and `overdue_delay_multiplier`

#### End-of-Day Deadline Cap (Castro-Compatible Mode)

When `deadline_cap_at_eod: true` is set at the top level of the configuration, all generated deadlines are additionally capped at the **end of the current day**. This ensures payments must settle within the same business day they arrive.

```yaml
# Top-level setting
deadline_cap_at_eod: true

agents:
  - id: BANK_A
    arrival_config:
      deadline_range: [30, 100]  # Sample offset from [30, 100]
      # With 100 ticks/day:
      # - Arrival at tick 50, sampled offset 80 → raw deadline 130
      # - Capped to day end: min(130, 100) = 100
```

See [Advanced Settings: deadline_cap_at_eod](advanced-settings.md#deadline_cap_at_eod) for full details.

#### Example

```yaml
deadline_range: [30, 60]    # 30-60 ticks to complete
```

---

### `priority`

**Type**: `int`
**Required**: No
**Constraint**: `0 <= value <= 10`
**Default**: `5`

Fixed priority for all generated transactions.

#### Implementation Details

**Python Schema** (`schemas.py:138-139`):
```python
priority: int = Field(default=5, ge=0, le=10)
```

#### Priority Bands

| Range | Band | Description |
|:------|:-----|:------------|
| 8-10 | Urgent | Highest priority, processed first |
| 4-7 | Normal | Standard payments |
| 0-3 | Low | Discretionary, processed last |

#### Example

```yaml
priority: 7    # Normal-high priority
```

#### Relationship with `priority_distribution`

If `priority_distribution` is specified, it **overrides** the `priority` field.

---

### `priority_distribution`

**Type**: `PriorityDistribution` (union type)
**Required**: No
**Constraint**: Valid distribution type
**Default**: `None` (uses `priority` field)

Distribution for sampling transaction priorities. See [distributions.md](distributions.md) for complete reference.

#### Available Types

| Type | Parameters | Use Case |
|:-----|:-----------|:---------|
| `Fixed` | `value` | All same priority (like `priority` field) |
| `Categorical` | `values`, `weights` | Realistic mix of priorities |
| `Uniform` | `min`, `max` | Random in range |

#### Example

```yaml
priority_distribution:
  type: Categorical
  values: [3, 5, 7, 9]
  weights: [0.2, 0.5, 0.2, 0.1]   # 10% urgent, 20% high, 50% normal, 20% low
```

---

### `divisible`

**Type**: `bool`
**Required**: No
**Constraint**: None
**Default**: `false`

Whether generated transactions can be split by splitting policies.

#### Implementation Details

**Python Schema** (`schemas.py:143`):
```python
divisible: bool = False
```

**Rust** (`arrivals/mod.rs:70`):
```rust
pub divisible: bool,
```

#### Behavior

- `true`: Policies can split this transaction
- `false`: Transaction must settle as one unit

#### Example

```yaml
divisible: true    # Allow splitting
```

---

## `arrival_bands`

**Enhancement 11.3**: Per-priority-band arrival configuration.

Instead of single arrival config, define separate configurations for urgent, normal, and low priority bands.

### Schema

```yaml
arrival_bands:
  urgent: <ArrivalBandConfig>    # Optional, priority 8-10
  normal: <ArrivalBandConfig>    # Optional, priority 4-7
  low: <ArrivalBandConfig>       # Optional, priority 0-3
```

**Constraint**: At least one band must be specified.

### `ArrivalBandConfig`

```yaml
<band>:
  rate_per_tick: <float>                  # Required, >= 0
  amount_distribution: <AmountDist>       # Required
  deadline_offset_min: <int>              # Required, > 0
  deadline_offset_max: <int>              # Required, > 0
  counterparty_weights: <Dict[str, float]> # Optional, default: {}
  divisible: <bool>                       # Optional, default: false
```

---

## Band Field Reference

### `rate_per_tick`

Same as in `arrival_config`. Poisson λ parameter for this band.

### `amount_distribution`

Same as in `arrival_config`. Distribution for this band's transaction amounts.

### `deadline_offset_min`

**Type**: `int`
**Required**: Yes
**Constraint**: `> 0`

Minimum ticks from arrival to deadline for this band.

### `deadline_offset_max`

**Type**: `int`
**Required**: Yes
**Constraint**: `> 0`, `>= deadline_offset_min`

Maximum ticks from arrival to deadline for this band.

**Note**: When `deadline_cap_at_eod: true` is enabled, band deadlines are also capped at day end. See [Advanced Settings: deadline_cap_at_eod](advanced-settings.md#deadline_cap_at_eod).

### `counterparty_weights`

Same as in `arrival_config`. Per-band receiver weights.

### `divisible`

Same as in `arrival_config`. Per-band splitting permission.

---

## Band Priority Assignment

When using `arrival_bands`, priorities are assigned automatically:

| Band | Priority Range | Assignment |
|:-----|:---------------|:-----------|
| `urgent` | 8-10 | Uniform random in [8, 10] |
| `normal` | 4-7 | Uniform random in [4, 7] |
| `low` | 0-3 | Uniform random in [0, 3] |

---

## Complete Examples

### Simple Arrival Config

```yaml
agents:
  - id: ACTIVE_BANK
    arrival_config:
      rate_per_tick: 0.5
      amount_distribution:
        type: Uniform
        min: 100000
        max: 500000
      counterparty_weights:
        OTHER_BANK: 1.0
      deadline_range: [30, 60]
      priority: 5
      divisible: false
```

### Arrival Config with Priority Distribution

```yaml
agents:
  - id: REALISTIC_BANK
    arrival_config:
      rate_per_tick: 0.65
      amount_distribution:
        type: LogNormal
        mean: 11.51
        std_dev: 0.9
      counterparty_weights:
        BANK_B: 0.4
        BANK_C: 0.35
        BANK_D: 0.25
      deadline_range: [35, 70]
      priority_distribution:
        type: Categorical
        values: [3, 5, 7, 9]
        weights: [0.25, 0.50, 0.15, 0.10]
      divisible: true
```

### Per-Band Arrivals (Enhancement 11.3)

```yaml
agents:
  - id: T2_STYLE_BANK
    arrival_bands:
      urgent:
        rate_per_tick: 0.1
        amount_distribution:
          type: Uniform
          min: 500000
          max: 2000000
        deadline_offset_min: 10
        deadline_offset_max: 25
        divisible: false
      normal:
        rate_per_tick: 0.4
        amount_distribution:
          type: LogNormal
          mean: 11.0
          std_dev: 1.0
        deadline_offset_min: 30
        deadline_offset_max: 60
        counterparty_weights:
          BANK_B: 0.6
          BANK_C: 0.4
        divisible: true
      low:
        rate_per_tick: 0.2
        amount_distribution:
          type: Exponential
          lambda: 0.00001
        deadline_offset_min: 50
        deadline_offset_max: 100
        divisible: true
```

### No Automatic Arrivals

```yaml
agents:
  - id: PASSIVE_BANK
    opening_balance: 10000000
    policy:
      type: Fifo
    # No arrival_config or arrival_bands
    # Transactions only via scenario_events
```

---

## Validation Rules

### Mutual Exclusivity

```
Error: Cannot specify both arrival_config and arrival_bands
```

**Fix**: Use only one of `arrival_config` or `arrival_bands`.

### Band Requirement

```
Error: At least one band (urgent, normal, low) must be specified
```

**Fix**: Define at least one band in `arrival_bands`.

### Counterparty Reference

```
Error: Counterparty 'UNKNOWN_BANK' not found in agents
```

**Fix**: Only reference agents that exist in the `agents` list.

### Deadline Range

```
Error: deadline_range must have exactly 2 elements
Error: deadline_range max must be >= min
```

**Fix**: Provide `[min, max]` where `max >= min`.

---

## Implementation Location

| Component | File | Lines |
|:----------|:-----|:------|
| Python ArrivalConfig | `api/payment_simulator/config/schemas.py` | 126-199 |
| Python ArrivalBandConfig | `api/payment_simulator/config/schemas.py` | 205-249 |
| Python ArrivalBandsConfig | `api/payment_simulator/config/schemas.py` | 251-282 |
| Rust ArrivalConfig | `backend/src/arrivals/mod.rs` | 63-82 |
| Rust ArrivalBandConfig | `backend/src/arrivals/mod.rs` | 110-130 |
| Rust ArrivalBandsConfig | `backend/src/arrivals/mod.rs` | 144-151 |
| FFI Parsing | `backend/src/ffi/types.rs` | 464-634 |

---

## Navigation

**Previous**: [Policies](policies.md)
**Next**: [Distributions](distributions.md)

---

*Last updated: 2025-12-02*
