# Appendix C: Configuration Reference

**Version**: 1.0
**Last Updated**: 2025-11-28

---

## Configuration Schema

### Root Structure

```yaml
# SimulationConfig
ticks_per_day: 100          # Ticks per business day
num_days: 1                 # Number of days to simulate
seed: 12345                 # RNG seed for determinism
agents: [...]               # Agent configurations
rails: [...]                # Settlement rail configs
costs: {...}                # Cost rate configuration
lsm_config: {...}           # LSM settings
scenario_events: [...]      # Optional external events
```

---

## Agent Configuration

```yaml
agents:
  - id: BANK_A                      # Unique identifier (uppercase)
    opening_balance: 1000000        # Initial balance (cents)
    credit_limit: 500000            # Total credit limit (cents)
    unsecured_cap: 200000           # Unsecured overdraft limit (cents)
    liquidity_buffer: 100000        # Target minimum balance (cents)
    collateral_haircut: 0.02        # Haircut rate (0.02 = 2%)

    # Policy configuration
    policy:
      type: tree                    # fifo | deadline | liquidity_aware | tree
      payment_tree: {...}           # Decision tree for payments
      bank_tree: {...}              # Decision tree for bank-level
      strategic_collateral_tree: {...}
      end_of_tick_collateral_tree: {...}
      parameters:
        buffer: 50000

    # Arrival configuration
    arrival_config:
      rate_per_tick: 2.0            # Poisson λ
      amount_distribution:
        type: lognormal             # normal | lognormal | uniform | exponential
        mean: 100000
        std_dev: 50000
      counterparty_weights:
        BANK_B: 0.6
        BANK_C: 0.4
      deadline_range: [50, 150]     # [min, max] ticks after arrival
      priority_distribution:
        type: categorical           # fixed | categorical | uniform
        values: [3, 5, 8]
        weights: [0.2, 0.6, 0.2]
      divisible: true

    # Per-band arrivals (Enhancement 11.3)
    arrival_bands:
      urgent:                       # Priority 8-10
        rate_per_tick: 0.5
        amount_distribution: {...}
      normal:                       # Priority 4-7
        rate_per_tick: 1.5
        amount_distribution: {...}
      low:                          # Priority 0-3
        rate_per_tick: 0.5
        amount_distribution: {...}

    # TARGET2 LSM limits
    bilateral_limits:
      BANK_B: 500000               # Max outflow to BANK_B
      BANK_C: 300000               # Max outflow to BANK_C
    multilateral_limit: 1000000    # Max total outflow
```

---

## Cost Configuration

```yaml
costs:
  overdraft_cost_bps: 10.0              # Annualized overdraft rate (basis points)
  collateral_cost_per_tick_bps: 5.0     # Collateral opportunity cost
  delay_penalty_per_tick: 100           # Delay cost per tick (cents)
  overdue_delay_multiplier: 5.0         # Multiplier after deadline
  deadline_penalty: 10000               # One-time deadline penalty (cents)
  split_friction_cost: 1000             # Cost per split (cents)
  eod_unsettled_penalty: 100000         # EOD unsettled penalty (cents)
```

---

## LSM Configuration

```yaml
lsm_config:
  enable_bilateral: true                # Enable bilateral offsetting
  enable_cycles: true                   # Enable cycle detection
  max_cycle_length: 5                   # Maximum cycle length
  max_cycles_per_tick: 100              # Max cycles per tick

# Additional orchestrator settings
queue1_ordering: priority_deadline      # fifo | priority_deadline
priority_mode: true                     # Enable T2 priority bands
algorithm_sequencing: true              # Emit algorithm events
entry_disposition_offsetting: true      # Pre-queue offset check
deferred_crediting: false               # Castro-compatible deferred credits

priority_escalation:
  enabled: true
  start_ticks_before_deadline: 20
  escalation_curve: linear              # linear | exponential
  max_boost: 3
```

---

## Deferred Crediting

```yaml
deferred_crediting: true    # Enable Castro-compatible settlement (default: false)
```

When enabled, credits from settlements are accumulated during a tick and applied at the end (step 5.7), rather than being immediately available. This prevents "within-tick recycling" of liquidity.

**Behavioral Impact**:
- Mutual payments between agents with zero balance will gridlock
- Incoming payments are only available in the next tick
- Matches Castro et al. (2025) academic model

**Default**: `false` (immediate crediting for backward compatibility)

---

## Amount Distributions

### Normal

```yaml
amount_distribution:
  type: normal
  mean: 100000      # Mean (cents)
  std_dev: 50000    # Standard deviation
```

### LogNormal

```yaml
amount_distribution:
  type: lognormal
  mean: 11.5        # Log-space mean
  std_dev: 0.8      # Log-space std dev
```

### Uniform

```yaml
amount_distribution:
  type: uniform
  min: 10000        # Minimum (cents)
  max: 500000       # Maximum (cents)
```

### Exponential

```yaml
amount_distribution:
  type: exponential
  lambda: 0.00001   # Rate parameter
```

---

## Priority Distributions

### Fixed

```yaml
priority_distribution:
  type: fixed
  value: 5          # All transactions get priority 5
```

### Categorical

```yaml
priority_distribution:
  type: categorical
  values: [3, 5, 8]           # Priority values
  weights: [0.2, 0.6, 0.2]    # Probabilities
```

### Uniform

```yaml
priority_distribution:
  type: uniform
  min: 1            # Minimum priority
  max: 10           # Maximum priority
```

---

## Scenario Events

### Direct Transfer

```yaml
scenario_events:
  - type: direct_transfer
    from_agent: EXTERNAL
    to_agent: BANK_A
    amount: 1000000
    schedule:
      type: one_time
      tick: 50
```

### Custom Transaction

```yaml
scenario_events:
  - type: custom_transaction_arrival
    sender_id: BANK_A
    receiver_id: BANK_B
    amount: 500000
    priority: 9
    deadline_offset: 20
    divisible: false
    schedule:
      type: repeating
      start_tick: 10
      interval: 50
```

### Arrival Rate Change

```yaml
scenario_events:
  - type: agent_arrival_rate_change
    agent_id: BANK_A
    new_rate: 5.0
    schedule:
      type: one_time
      tick: 100
```

### Collateral Adjustment

```yaml
scenario_events:
  - type: collateral_adjustment
    agent_id: BANK_A
    delta: -200000      # Negative = reduce capacity
    schedule:
      type: one_time
      tick: 75
```

---

## Policy Trees

### Simple Submit

```yaml
policy:
  type: tree
  payment_tree:
    action: submit
```

### Conditional Release

```yaml
policy:
  type: tree
  payment_tree:
    condition:
      left: tx.priority
      operator: gte
      right: 5
    if_true:
      action: submit
    if_false:
      condition:
        left: tx.ticks_until_deadline
        operator: lte
        right: 10
      if_true:
        action: submit
      if_false:
        action: hold
        reason: low_priority_not_urgent
```

### With Parameters

```yaml
policy:
  type: tree
  payment_tree:
    condition:
      left: agent.available_liquidity
      operator: gte
      right:
        left: tx.remaining_amount
        operator: add
        right:
          param: buffer
    if_true:
      action: submit
    if_false:
      action: hold
  parameters:
    buffer: 100000
```

---

## Complete Example

```yaml
# sim_config_complete.yaml
ticks_per_day: 100
num_days: 5
seed: 42

agents:
  - id: BANK_A
    opening_balance: 5000000
    credit_limit: 2000000
    unsecured_cap: 1000000
    liquidity_buffer: 500000
    collateral_haircut: 0.02
    bilateral_limits:
      BANK_B: 1000000
    multilateral_limit: 2000000
    policy:
      type: tree
      payment_tree:
        condition:
          left: tx.priority
          operator: gte
          right: 8
        if_true:
          action: submit
        if_false:
          condition:
            left: agent.available_liquidity
            operator: gte
            right: tx.remaining_amount
          if_true:
            action: submit
          if_false:
            action: hold
            reason: insufficient_liquidity
    arrival_config:
      rate_per_tick: 3.0
      amount_distribution:
        type: lognormal
        mean: 11.5
        std_dev: 0.8
      counterparty_weights:
        BANK_B: 1.0
      deadline_range: [30, 100]
      priority_distribution:
        type: categorical
        values: [3, 5, 8]
        weights: [0.3, 0.5, 0.2]
      divisible: true

  - id: BANK_B
    opening_balance: 5000000
    credit_limit: 2000000
    unsecured_cap: 1000000
    policy:
      type: fifo
    arrival_config:
      rate_per_tick: 3.0
      amount_distribution:
        type: lognormal
        mean: 11.5
        std_dev: 0.8
      counterparty_weights:
        BANK_A: 1.0
      deadline_range: [30, 100]
      divisible: true

rails:
  - name: RTGS
    type: rtgs

costs:
  overdraft_cost_bps: 10.0
  collateral_cost_per_tick_bps: 5.0
  delay_penalty_per_tick: 100
  overdue_delay_multiplier: 5.0
  deadline_penalty: 10000
  split_friction_cost: 1000
  eod_unsettled_penalty: 100000

lsm_config:
  enable_bilateral: true
  enable_cycles: true
  max_cycle_length: 5
  max_cycles_per_tick: 100

queue1_ordering: priority_deadline
priority_mode: true
algorithm_sequencing: true
entry_disposition_offsetting: true

priority_escalation:
  enabled: true
  start_ticks_before_deadline: 20
  escalation_curve: linear
  max_boost: 3

scenario_events:
  - type: direct_transfer
    from_agent: EXTERNAL
    to_agent: BANK_A
    amount: 2000000
    schedule:
      type: one_time
      tick: 250
```

---

## Validation Rules

| Field | Rule |
|-------|------|
| `id` | Uppercase alphanumeric |
| `opening_balance` | Integer (cents) |
| `credit_limit` | Integer (cents) |
| `rate_per_tick` | Positive float |
| `counterparty_weights` | Sum > 0 |
| `deadline_range` | [min, max] where min ≤ max |
| `priority` | 0-10 |
| `seed` | Any u64 |

---

## Related Documents

- [03-python-api-layer.md](./03-python-api-layer.md) - Schema implementation
- [07-policy-system.md](./07-policy-system.md) - Policy tree reference

---

*End of Architecture Documentation*
