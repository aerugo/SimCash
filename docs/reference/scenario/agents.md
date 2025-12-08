# Agent Configuration

Agents represent **participating banks** in the payment system. Each agent has a settlement account, may generate transactions, and uses a policy to make payment decisions.

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

    # Enhancement 11.2: External liquidity pool
    liquidity_pool: <int>                 # Optional, cents
    liquidity_allocation_fraction: <float> # Optional, 0.0-1.0
```

---

## Field Reference

### `id`

**Type**: `str`
**Required**: Yes
**Constraint**: Non-empty string, must be unique across all agents
**Default**: None (required)

Unique identifier for the agent. Used in:
- Transaction routing (sender/receiver references)
- Counterparty weights
- Limit configurations
- Scenario event targeting

#### Implementation Details

**Python Schema** (`schemas.py:448-449`):
```python
id: str = Field(..., min_length=1)
```

**Validation** (`schemas.py:462-477`):
```python
@model_validator(mode='after')
def validate_agent_ids_unique(self) -> 'SimulationConfig':
    agent_ids = [a.id for a in self.agents]
    if len(agent_ids) != len(set(agent_ids)):
        raise ValueError("Agent IDs must be unique")
```

#### Best Practices

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

**Type**: `int` (cents)
**Required**: Yes
**Constraint**: None (can be negative)
**Default**: None (required)

Initial balance in the agent's settlement account at simulation start.

#### Implementation Details

**Python Schema** (`schemas.py:450`):
```python
opening_balance: int
```

**Rust** (`engine.rs:251`):
```rust
pub opening_balance: i64,
```

#### Monetary Values

**CRITICAL INVARIANT**: All monetary values are **integer cents**.

| Dollars | Cents (Config Value) |
|:--------|:---------------------|
| $1,000.00 | `100000` |
| $100,000.00 | `10000000` |
| -$5,000.00 | `-500000` |

#### Use Cases

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

**Type**: `int` (cents)
**Required**: No
**Constraint**: `>= 0`
**Default**: `0`

Maximum **unsecured overdraft capacity**. This is daylight credit that doesn't require collateral.

#### Implementation Details

**Python Schema** (`schemas.py:451`):
```python
unsecured_cap: int = Field(default=0, ge=0)
```

**Rust** (`engine.rs:252`):
```rust
pub unsecured_cap: i64,
```

#### Behavior

- Allows balance to go negative up to `-unsecured_cap`
- Subject to `overdraft_bps_per_tick` cost when used
- Additional overdraft requires posted collateral

#### Example

```yaml
agents:
  - id: BANK_A
    opening_balance: 10000000   # $100,000
    unsecured_cap: 5000000      # $50,000 credit line
    # Can overdraw up to $150,000 total before needing collateral
```

---

### `policy`

**Type**: `PolicyConfig` (union type)
**Required**: Yes
**Constraint**: Must be valid policy type
**Default**: None (required)

The decision-making strategy for the agent. See [policies.md](policies.md) for complete documentation.

#### Quick Reference

| Policy Type | Description |
|:------------|:------------|
| `Fifo` | Submit all transactions immediately |
| `Deadline` | Submit when deadline approaches |
| `LiquidityAware` | Maintain target buffer |
| `LiquiditySplitting` | Split large payments |
| `MockSplitting` | Testing: deterministic splits |
| `FromJson` | JSON DSL policy tree |

#### Example

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

**Type**: `ArrivalConfig`
**Required**: No
**Constraint**: Mutually exclusive with `arrival_bands`
**Default**: `None`

Configuration for automatic transaction generation. See [arrivals.md](arrivals.md) for complete documentation.

#### Quick Example

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

**Type**: `ArrivalBandsConfig`
**Required**: No
**Constraint**: Mutually exclusive with `arrival_config`
**Default**: `None`

**Enhancement 11.3**: Per-priority-band arrival configuration. See [arrivals.md](arrivals.md) for complete documentation.

#### Quick Example

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

**Type**: `int` (cents)
**Required**: No
**Constraint**: None
**Default**: `None`

Initial collateral posted at simulation start.

#### Implementation Details

**Python Schema** (`schemas.py:457`):
```python
posted_collateral: Optional[int] = None
```

**Rust** (`engine.rs:260`):
```rust
pub posted_collateral: Option<i64>,
```

#### Behavior

- Increases overdraft capacity beyond `unsecured_cap`
- Subject to `collateral_cost_per_tick_bps` opportunity cost
- Can be adjusted during simulation via `CollateralAdjustment` events
- Dynamic posting/withdrawal available via policy collateral trees

#### Example

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

**Type**: `float`
**Required**: No
**Constraint**: `0.0 <= value <= 1.0`
**Default**: `None` (no haircut)

Discount applied to posted collateral value.

#### Implementation Details

**Python Schema** (`schemas.py:458`):
```python
collateral_haircut: Optional[float] = Field(None, ge=0.0, le=1.0)
```

**Rust** (`engine.rs:261`):
```rust
pub collateral_haircut: Option<f64>,
```

#### Behavior

Effective collateral value = `posted_collateral × (1 - haircut)`

#### Example

```yaml
agents:
  - id: BANK_A
    posted_collateral: 1000000   # $10,000 posted
    collateral_haircut: 0.15     # 15% haircut
    # Effective value: $10,000 × 0.85 = $8,500
```

---

### `limits`

**Type**: `Dict` with `bilateral_limits` and/or `multilateral_limit`
**Required**: No
**Constraint**: Referenced agents must exist
**Default**: `None`

Payment limits that constrain outflows.

#### Schema

```yaml
limits:
  bilateral_limits:              # Per-counterparty limits
    <agent_id>: <int>            # Max daily outflow to this agent (cents)
  multilateral_limit: <int>      # Total daily outflow limit (cents)
```

#### Implementation Details

**Python Schema** (`schemas.py:460-461`):
```python
limits: Optional[Dict] = None
```

**Rust Struct** (`engine.rs:329-339`):
```rust
pub struct AgentLimitsConfig {
    pub bilateral_limits: HashMap<String, i64>,
    pub multilateral_limit: Option<i64>,
}
```

#### Behavior

- Limits reset at the start of each day
- Transactions blocked when limits exceeded
- LSM can help by finding offsetting transactions
- Limit breaches are logged as events

#### Example

```yaml
agents:
  - id: SMALL_BANK
    limits:
      bilateral_limits:
        BIG_BANK_A: 3000000      # Max $30,000/day to BIG_BANK_A
        BIG_BANK_B: 3500000      # Max $35,000/day to BIG_BANK_B
      multilateral_limit: 7500000  # Max $75,000/day total outflow
```

#### Use Cases

- **Risk management**: Limit exposure to individual counterparties
- **Systemic risk modeling**: Test cascading failures from limit breaches
- **T2 simulation**: Bilateral sender limits are a T2 feature

---

### `liquidity_pool`

**Type**: `int` (cents)
**Required**: No
**Constraint**: `>= 0`
**Default**: `None`

**Enhancement 11.2**: External liquidity pool available for allocation.

#### Implementation Details

**Python Schema** (`schemas.py:463-464`):
```python
liquidity_pool: Optional[int] = Field(None, ge=0)
```

**Rust** (`engine.rs:266-267`):
```rust
pub liquidity_pool: Option<i64>,
```

#### Behavior

- Represents external funding source (central bank facility, etc.)
- Agent allocates fraction of pool at day start via `liquidity_allocation_fraction`
- Allocated liquidity subject to `liquidity_cost_per_tick_bps` opportunity cost
- Used in BIS Box 3 liquidity-delay trade-off modeling

#### Example

```yaml
agents:
  - id: FOCAL_BANK
    opening_balance: 0
    liquidity_pool: 1000000              # $10,000 available pool
    liquidity_allocation_fraction: 0.5   # Allocate 50% = $5,000
```

---

### `liquidity_allocation_fraction`

**Type**: `float`
**Required**: No
**Constraint**: `0.0 <= value <= 1.0`
**Default**: `None`

**Enhancement 11.2**: Fraction of `liquidity_pool` to allocate.

#### Implementation Details

**Python Schema** (`schemas.py:465-466`):
```python
liquidity_allocation_fraction: Optional[float] = Field(None, ge=0.0, le=1.0)
```

**Rust** (`engine.rs:268-269`):
```rust
pub liquidity_allocation_fraction: Option<f64>,
```

#### Behavior

- Only meaningful if `liquidity_pool` is set
- Allocation = `liquidity_pool × liquidity_allocation_fraction`
- Allocated amount added to available liquidity
- Subject to opportunity cost

#### Example

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

### BIS Model Agent (Enhancement 11.2)

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

### Agent ID Uniqueness

```python
Error: Agent IDs must be unique
```

**Fix**: Ensure all `id` values are distinct.

### Counterparty References

```python
Error: Counterparty 'UNKNOWN_BANK' not found in agents
```

**Fix**: Only reference agents that exist in the `agents` list.

### Arrival Exclusivity

```python
Error: Cannot specify both arrival_config and arrival_bands
```

**Fix**: Use either `arrival_config` OR `arrival_bands`, not both.

### Minimum Agents

```python
Error: At least one agent required
```

**Fix**: Define at least one agent in the `agents` list.

---

## Implementation Location

| Component | File | Lines |
|:----------|:-----|:------|
| Python AgentConfig | `api/payment_simulator/config/schemas.py` | 447-494 |
| Rust AgentConfig | `simulator/src/orchestrator/engine.rs` | 244-321 |
| FFI Parsing | `simulator/src/ffi/types.rs` | 260-322 |
| Limits Struct | `simulator/src/orchestrator/engine.rs` | 329-339 |

---

## Navigation

**Previous**: [Simulation Settings](simulation-settings.md)
**Next**: [Policies](policies.md)
