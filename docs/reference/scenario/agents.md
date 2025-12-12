# Agent Configuration

Agents represent **participating banks** in the payment system. Each agent has a settlement account, may generate transactions, and uses a policy to make payment decisions.

---

## Quick Start

```yaml
agents:
  - id: BANK_A
    opening_balance: 10000000    # $100,000 in cents
    policy:
      type: Fifo
```

---

## Schema

```yaml
agents:
  - id: <string>                          # Required, unique identifier
    opening_balance: <int>                # Required, cents
    unsecured_cap: <int>                  # Optional, default: 0
    policy: <PolicyConfig>                # Required, see policies.md

    # Transaction generation (mutually exclusive)
    arrival_config: <ArrivalConfig>       # Optional, see arrivals.md
    arrival_bands: <ArrivalBandsConfig>   # Optional, see arrivals.md

    # Collateral settings
    posted_collateral: <int>              # Optional, cents
    collateral_haircut: <float>           # Optional, 0.0-1.0

    # Limit settings
    limits:
      bilateral_limits: <Dict[str, int]>  # Optional, per-counterparty limits
      multilateral_limit: <int>           # Optional, total daily outflow

    # External liquidity pool
    liquidity_pool: <int>                 # Optional, cents
    liquidity_allocation_fraction: <float> # Optional, 0.0-1.0
```

---

## Field Reference

### `id`

| Attribute | Value |
|-----------|-------|
| **Type** | `str` |
| **Required** | Yes |
| **Constraint** | Non-empty, unique across all agents |

Unique identifier for the agent. Used in transaction routing, counterparty weights, limit configurations, and scenario event targeting.

```yaml
# GOOD: Clear, descriptive names
agents:
  - id: BIG_BANK_A
  - id: REGIONAL_TRUST
  - id: METRO_CENTRAL

# AVOID: Generic names that confuse analysis
agents:
  - id: agent1
  - id: agent2
```

---

### `opening_balance`

| Attribute | Value |
|-----------|-------|
| **Type** | `int` (cents) |
| **Required** | Yes |
| **Constraint** | None (can be negative) |

Initial balance in the agent's settlement account at simulation start.

**CRITICAL INVARIANT**: All monetary values are **integer cents**.

| Dollars | Cents (Config Value) |
|---------|---------------------|
| $1,000.00 | `100000` |
| $100,000.00 | `10000000` |
| -$5,000.00 | `-500000` |

```yaml
# Well-capitalized bank
opening_balance: 15000000    # $150,000

# Constrained bank
opening_balance: 5000000     # $50,000

# Starting in debt (valid, but unusual)
opening_balance: -1000000    # -$10,000
```

---

### `unsecured_cap`

| Attribute | Value |
|-----------|-------|
| **Type** | `int` (cents) |
| **Required** | No |
| **Default** | `0` |
| **Constraint** | `>= 0` |

Maximum **unsecured overdraft capacity**. This is daylight credit that doesn't require collateral.

**Behavior:**
- Allows balance to go negative up to `-unsecured_cap`
- Subject to `overdraft_bps_per_tick` cost when used
- Additional overdraft requires posted collateral

```yaml
agents:
  - id: BANK_A
    opening_balance: 10000000   # $100,000
    unsecured_cap: 5000000      # $50,000 credit line
    # Can overdraw up to $150,000 total before needing collateral
```

---

### `policy`

| Attribute | Value |
|-----------|-------|
| **Type** | `PolicyConfig` (union type) |
| **Required** | Yes |
| **Constraint** | Must be valid policy type |

The decision-making strategy for the agent. See [policies.md](policies.md) for complete documentation.

| Policy Type | Description |
|-------------|-------------|
| `Fifo` | Submit all transactions immediately |
| `Deadline` | Submit when deadline approaches |
| `LiquidityAware` | Maintain target buffer |
| `LiquiditySplitting` | Split large payments |
| `MockSplitting` | Testing: deterministic splits |
| `FromJson` | JSON DSL policy tree |

```yaml
agents:
  - id: BANK_A
    policy:
      type: LiquidityAware
      target_buffer: 500000      # Maintain $5,000 buffer
      urgency_threshold: 10      # Submit if <= 10 ticks to deadline
```

---

### `arrival_config`

| Attribute | Value |
|-----------|-------|
| **Type** | `ArrivalConfig` |
| **Required** | No |
| **Constraint** | Mutually exclusive with `arrival_bands` |

Configuration for automatic transaction generation. See [arrivals.md](arrivals.md) for complete documentation.

```yaml
agents:
  - id: BANK_A
    arrival_config:
      rate_per_tick: 0.5
      amount_distribution:
        type: LogNormal
        mean: 11.51
        std_dev: 0.9
      counterparty_weights:
        BANK_B: 0.6
        BANK_C: 0.4
      deadline_range: [30, 60]
      priority: 5
      divisible: false
```

---

### `arrival_bands`

| Attribute | Value |
|-----------|-------|
| **Type** | `ArrivalBandsConfig` |
| **Required** | No |
| **Constraint** | Mutually exclusive with `arrival_config` |

Per-priority-band arrival configuration. See [arrivals.md](arrivals.md) for complete documentation.

```yaml
agents:
  - id: BANK_A
    arrival_bands:
      urgent:
        rate_per_tick: 0.1
        amount_distribution:
          type: Uniform
          min: 500000
          max: 2000000
        deadline_offset_min: 10
        deadline_offset_max: 25
      normal:
        rate_per_tick: 0.4
        amount_distribution:
          type: LogNormal
          mean: 11.0
          std_dev: 1.0
        deadline_offset_min: 30
        deadline_offset_max: 60
```

---

### `posted_collateral`

| Attribute | Value |
|-----------|-------|
| **Type** | `int` (cents) |
| **Required** | No |
| **Default** | `None` |

Initial collateral posted at simulation start.

**Behavior:**
- Increases overdraft capacity beyond `unsecured_cap`
- Subject to `collateral_cost_per_tick_bps` opportunity cost
- Can be adjusted during simulation via `CollateralAdjustment` events
- Dynamic posting/withdrawal available via policy collateral trees

```yaml
agents:
  - id: BANK_A
    opening_balance: 10000000
    unsecured_cap: 5000000
    posted_collateral: 3000000   # $30,000 collateral posted
    # Total credit capacity: $50,000 + $30,000 = $80,000
```

---

### `collateral_haircut`

| Attribute | Value |
|-----------|-------|
| **Type** | `float` |
| **Required** | No |
| **Constraint** | `0.0 <= value <= 1.0` |
| **Default** | `None` (no haircut) |

Discount applied to posted collateral value.

**Formula:** `Effective collateral value = posted_collateral × (1 - haircut)`

```yaml
agents:
  - id: BANK_A
    posted_collateral: 1000000   # $10,000 posted
    collateral_haircut: 0.15     # 15% haircut
    # Effective value: $10,000 × 0.85 = $8,500
```

---

### `limits`

| Attribute | Value |
|-----------|-------|
| **Type** | Object with `bilateral_limits` and/or `multilateral_limit` |
| **Required** | No |
| **Constraint** | Referenced agents must exist |

Payment limits that constrain outflows.

```yaml
limits:
  bilateral_limits:              # Per-counterparty limits
    <agent_id>: <int>            # Max daily outflow to this agent (cents)
  multilateral_limit: <int>      # Total daily outflow limit (cents)
```

**Behavior:**
- Limits reset at the start of each day
- Transactions blocked when limits exceeded
- LSM can help by finding offsetting transactions
- Limit breaches are logged as events

```yaml
agents:
  - id: SMALL_BANK
    limits:
      bilateral_limits:
        BIG_BANK_A: 3000000      # Max $30,000/day to BIG_BANK_A
        BIG_BANK_B: 3500000      # Max $35,000/day to BIG_BANK_B
      multilateral_limit: 7500000  # Max $75,000/day total outflow
```

**Use Cases:**
- Risk management: Limit exposure to individual counterparties
- Systemic risk modeling: Test cascading failures from limit breaches
- TARGET2 simulation: Bilateral sender limits are a T2 feature

---

### `liquidity_pool`

| Attribute | Value |
|-----------|-------|
| **Type** | `int` (cents) |
| **Required** | No |
| **Constraint** | `>= 0` |

External liquidity pool available for allocation.

**Behavior:**
- Represents external funding source (central bank facility, etc.)
- Agent allocates fraction of pool at day start via `liquidity_allocation_fraction`
- Allocated liquidity subject to `liquidity_cost_per_tick_bps` opportunity cost
- Used in BIS Box 3 liquidity-delay trade-off modeling

```yaml
agents:
  - id: FOCAL_BANK
    opening_balance: 0
    liquidity_pool: 1000000              # $10,000 available pool
    liquidity_allocation_fraction: 0.5   # Allocate 50% = $5,000
```

---

### `liquidity_allocation_fraction`

| Attribute | Value |
|-----------|-------|
| **Type** | `float` |
| **Required** | No |
| **Constraint** | `0.0 <= value <= 1.0` |

Fraction of `liquidity_pool` to allocate.

**Behavior:**
- Only meaningful if `liquidity_pool` is set
- Allocation = `liquidity_pool × liquidity_allocation_fraction`
- Allocated amount added to available liquidity
- Subject to opportunity cost

```yaml
agents:
  - id: FOCAL_BANK
    liquidity_pool: 1000000              # $10,000 pool
    liquidity_allocation_fraction: 0.3   # Allocate 30% = $3,000
```

---

## Complete Examples

### Simple Agent

```yaml
agents:
  - id: BANK_A
    opening_balance: 10000000    # $100,000
    policy:
      type: Fifo
```

### Agent with Arrivals

```yaml
agents:
  - id: ACTIVE_BANK
    opening_balance: 15000000    # $150,000
    unsecured_cap: 5000000       # $50,000 credit
    policy:
      type: LiquidityAware
      target_buffer: 500000
      urgency_threshold: 10
    arrival_config:
      rate_per_tick: 0.65
      amount_distribution:
        type: LogNormal
        mean: 11.51
        std_dev: 0.9
      counterparty_weights:
        OTHER_BANK: 1.0
      deadline_range: [35, 70]
      priority: 5
      divisible: true
```

### Agent with Limits and Collateral

```yaml
agents:
  - id: CONSTRAINED_BANK
    opening_balance: 10000000
    unsecured_cap: 3000000
    posted_collateral: 2000000
    collateral_haircut: 0.10
    limits:
      bilateral_limits:
        BIG_BANK_A: 3000000
        BIG_BANK_B: 3500000
      multilateral_limit: 7500000
    policy:
      type: FromJson
      json_path: "simulator/policies/limit_aware.json"
```

### BIS Model Agent

```yaml
agents:
  - id: FOCAL_BANK
    opening_balance: 0
    unsecured_cap: 0
    liquidity_pool: 1000000
    liquidity_allocation_fraction: 0.5
    policy:
      type: Fifo
```

---

## Validation Rules

| Error | Fix |
|-------|-----|
| Agent IDs must be unique | Ensure all `id` values are distinct |
| Counterparty not found | Only reference agents that exist in the `agents` list |
| Cannot specify both arrival_config and arrival_bands | Use either `arrival_config` OR `arrival_bands`, not both |
| At least one agent required | Define at least one agent in the `agents` list |

---

## Related Documentation

- [Policies](policies.md) - Policy configuration options
- [Arrivals](arrivals.md) - Transaction generation configuration
- [Cost Rates](cost-rates.md) - Overdraft and delay costs

---

*Last updated: 2025-12-12*
