# Advanced Settings

Advanced settings control **TARGET2 alignment features** and simulation internals. These are top-level configuration options typically used for research scenarios.

---

## Overview

| Setting | Purpose | Default |
|---------|---------|---------|
| `algorithm_sequencing` | Sequenced FIFO→Bilateral→Multilateral LSM | `false` |
| `entry_disposition_offsetting` | Check offsets at payment entry | `false` |
| `deferred_crediting` | Batch credits at end of tick | `false` |
| `eod_rush_threshold` | When EOD rush behavior begins | `0.8` |
| `deadline_cap_at_eod` | Cap deadlines at end of current day | `false` |

---

## `algorithm_sequencing`

| Attribute | Value |
|-----------|-------|
| **Type** | `bool` |
| **Location** | Top-level config |
| **Default** | `false` |

Enables TARGET2-style algorithm sequencing where LSM algorithms run in a defined order.

```yaml
algorithm_sequencing: true
```

### Behavior

When enabled, each tick processes in sequence:

```
1. FIFO Settlement (RTGS)
   ↓
2. Bilateral Offset Detection
   ↓
3. Multilateral Cycle Detection
```

When disabled:
- LSM runs integrated with RTGS
- May find different offset opportunities

### Use Cases

- TARGET2 model replication
- Testing algorithm interaction
- Research on settlement sequencing

```yaml
algorithm_sequencing: true

lsm_config:
  enable_bilateral: true
  enable_cycles: true
```

---

## `entry_disposition_offsetting`

| Attribute | Value |
|-----------|-------|
| **Type** | `bool` |
| **Location** | Top-level config |
| **Default** | `false` |

Enables bilateral offset checking when payments **enter** Queue 2.

```yaml
entry_disposition_offsetting: true
```

### Behavior

When enabled:
- Each incoming Queue 2 payment checks for bilateral offset
- Immediate netting if matching payment exists
- Can settle before tick-end LSM runs

When disabled:
- Offsets only found during scheduled LSM runs
- Payments wait in queue until LSM phase

### Use Cases

- TARGET2 entry disposition behavior
- Real-time bilateral netting
- Reducing queue depth

```yaml
entry_disposition_offsetting: true
algorithm_sequencing: true    # Often used together
```

---

## `deferred_crediting`

| Attribute | Value |
|-----------|-------|
| **Type** | `bool` |
| **Location** | Top-level config |
| **Default** | `false` |

Enables deferred crediting mode where credits from settlements are accumulated during a tick and applied at the end.

```yaml
deferred_crediting: true
```

### Behavior

When enabled:
- Credits from RTGS and LSM settlements are accumulated during the tick
- Credits are applied at end of tick, before cost accrual
- Prevents "within-tick recycling" of liquidity
- Emits `DeferredCreditApplied` event per receiving agent

When disabled (default):
- Credits are applied immediately when settlements occur
- Incoming payments can fund outgoing payments in same tick
- Backward-compatible with existing scenarios

### Use Cases

- **Gridlock research**: Study payment gridlock under strict liquidity constraints
- **Academic validation**: Compare with theoretical models
- **Strict liquidity constraints**: Matches ℓ_t = ℓ_{t-1} - P_t x_t + R_t

### Behavioral Impact

| Scenario | Immediate (default) | Deferred |
|----------|---------------------|----------|
| Mutual A→B, B→A (zero balance) | May settle if B→A first | Gridlock |
| Chain A→B→C | C has funds same tick | C has funds next tick |
| LSM bilateral net receiver | Funds available same tick | Funds available end of tick |

```yaml
deferred_crediting: true
lsm_config:
  enable_bilateral: false  # May want to disable LSM for pure gridlock study
  enable_cycles: false
```

---

## `eod_rush_threshold`

| Attribute | Value |
|-----------|-------|
| **Type** | `float` |
| **Location** | Top-level config |
| **Constraint** | `0.0 <= value <= 1.0` |
| **Default** | `0.8` |

Fraction of day when EOD rush behavior activates.

```yaml
eod_rush_threshold: 0.8
```

### Behavior

EOD rush activates when:
```
current_tick_in_day >= ticks_per_day × eod_rush_threshold
```

For 100 ticks/day with threshold 0.8:
- Ticks 0-79: Normal operation
- Ticks 80-99: EOD rush

### Policy Integration

Available in JSON policies as field `is_eod_rush`:
- `1.0` if in EOD rush period
- `0.0` otherwise

### Threshold Values

| Threshold | Rush Starts At | Description |
|-----------|----------------|-------------|
| `0.6` | 60% of day | Early rush |
| `0.8` | 80% of day | Default |
| `0.9` | 90% of day | Late rush |
| `1.0` | Never | No rush |

```yaml
eod_rush_threshold: 0.75    # Rush at 75% of day
```

---

## `deadline_cap_at_eod`

| Attribute | Value |
|-----------|-------|
| **Type** | `bool` |
| **Location** | Top-level config |
| **Default** | `false` |

Enables deadline generation mode where all deadlines are capped at end of current day.

```yaml
deadline_cap_at_eod: true
```

### Behavior

When enabled:
- **All transaction deadlines** are capped at **end of current day**
- Applies uniformly to all transaction sources:
  1. Automatic arrivals from arrival generator
  2. API `submit_transaction()` calls
  3. `CustomTransactionArrival` scenario events
- Transaction arriving at tick 50 with deadline offset 80 → deadline = tick 99 (last tick of day)
- Creates realistic intraday settlement pressure
- All payments must settle by end-of-day or incur penalties

When disabled (default):
- Deadlines only capped at episode end (`num_days × ticks_per_day`)
- Transactions can span multiple days
- Day 1 transaction can have deadline in Day 3

### Use Cases

- Realistic same-day settlement requirements
- Research on EOD settlement pressure
- Modeling payment systems with strict daily cutoffs
- Academic model replication

### Interaction with Arrival Config

The cap is applied **after** the deadline offset is sampled:

```yaml
arrival_config:
  deadline_range: [30, 100]  # Sample offset from [30, 100]

# With deadline_cap_at_eod: true and 100 ticks/day:
# Day 0 has ticks 0-99, so last tick of day 0 is 99
# - Arrival at tick 50, sampled offset 80 → raw deadline 130
# - Capped to day end: min(130, 99) = 99
# - Arrival at tick 90, sampled offset 30 → raw deadline 120
# - Capped to day end: min(120, 99) = 99
```

### Multi-Day Behavior

For multi-day simulations (100 ticks/day):
- Day 0 transactions (ticks 0-99): deadlines capped at tick 99 (last tick of day 0)
- Day 1 transactions (ticks 100-199): deadlines capped at tick 199 (last tick of day 1)
- Each day's arrivals respect that day's EOD boundary

---

## Complete Configuration Examples

### TARGET2 Full Alignment

```yaml
simulation:
  ticks_per_day: 100
  num_days: 25
  rng_seed: 42

# TARGET2 alignment
algorithm_sequencing: true
entry_disposition_offsetting: true

# T2 priority handling
queue1_ordering: "priority_deadline"
priority_mode: true

priority_escalation:
  enabled: true
  curve: "linear"
  start_escalating_at_ticks: 25
  max_boost: 4

lsm_config:
  enable_bilateral: true
  enable_cycles: true
  max_cycle_length: 4
  max_cycles_per_tick: 20

cost_rates:
  delay_cost_per_tick_per_cent: 0.00035
  overdraft_bps_per_tick: 0.50
  overdue_delay_multiplier: 5.0
```

### Strict Same-Day Settlement Mode

```yaml
simulation:
  ticks_per_day: 100
  num_days: 10
  rng_seed: 42

# Enable same-day settlement constraints
deferred_crediting: true      # Batch credits at tick end
deadline_cap_at_eod: true     # All deadlines within same day

# Standard LSM
lsm_config:
  enable_bilateral: true
  enable_cycles: true
  max_cycle_length: 4
  max_cycles_per_tick: 10

agents:
  - id: BANK_A
    opening_balance: 10000000
    arrival_config:
      rate_per_tick: 0.5
      deadline_range: [30, 100]  # Will be capped to day end
```

### BIS-Minimal Configuration

```yaml
simulation:
  ticks_per_day: 3
  num_days: 1
  rng_seed: 42

# Simple model - disable advanced features
algorithm_sequencing: false
entry_disposition_offsetting: false

lsm_config:
  enable_bilateral: true
  enable_cycles: false
```

### Research Scenario

```yaml
simulation:
  ticks_per_day: 100
  num_days: 10
  rng_seed: 12345

# Experiment with sequencing
algorithm_sequencing: true
entry_disposition_offsetting: true

# Earlier EOD rush
eod_rush_threshold: 0.7

# Full LSM
lsm_config:
  enable_bilateral: true
  enable_cycles: true
  max_cycle_length: 5
  max_cycles_per_tick: 15
```

---

## Interaction Matrix

How advanced settings interact with other configurations:

| Setting | Interacts With | Effect |
|---------|----------------|--------|
| `algorithm_sequencing` | `lsm_config` | Defines when LSM runs |
| `algorithm_sequencing` | `priority_mode` | Priority respected in sequence |
| `entry_disposition_offsetting` | `lsm_config.enable_bilateral` | Entry-time bilateral check |
| `deferred_crediting` | `lsm_config` | LSM credits also deferred |
| `deferred_crediting` | Agent balances | Credits applied end of tick |
| `eod_rush_threshold` | `ticks_per_day` | Determines rush start tick |
| `eod_rush_threshold` | Policy `is_eod_rush` | Enables time-based policy |
| `deadline_cap_at_eod` | `ticks_per_day` | Day boundary for deadline cap |
| `deadline_cap_at_eod` | `arrival_config.deadline_range` | Raw deadline capped to day end |

---

## Events Generated

Advanced settings affect event generation:

### Algorithm Sequencing Events

When `algorithm_sequencing: true`:
- `AlgorithmPhaseStart` events mark each phase
- Phase: FIFO, Bilateral, Multilateral

### Entry Disposition Events

When `entry_disposition_offsetting: true`:
- `EntryDispositionOffset` when immediate bilateral found
- Includes matched transaction details

### Deferred Crediting Events

When `deferred_crediting: true`:
- `DeferredCreditApplied` for each agent receiving credits
- Emitted at end of tick
- Includes agent_id, amount, and source_transactions

---

## Performance Considerations

| Setting | Performance Impact |
|---------|-------------------|
| `algorithm_sequencing` | Slight overhead from phase separation |
| `entry_disposition_offsetting` | Extra check per Queue 2 entry |
| `deferred_crediting` | Minimal - BTreeMap operations |
| `eod_rush_threshold` | No performance impact |

---

## Related Settings

| Setting | Documentation |
|---------|---------------|
| `queue1_ordering` | [Priority System](priority-system.md) |
| `priority_mode` | [Priority System](priority-system.md) |
| `priority_escalation` | [Priority System](priority-system.md) |

---

## Related Documentation

- [Priority System](priority-system.md) - Queue ordering and priority settings
- [LSM Config](lsm-config.md) - Liquidity saving mechanism settings
- [Examples](examples.md) - Full configuration examples

---

*Last updated: 2025-12-12*
