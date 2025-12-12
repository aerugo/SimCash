# Scenario Events

Scenario events allow **dynamic injection of changes** during simulation runtime. They can create transactions, adjust balances, modify arrival rates, and more.

---

## Overview

Events are scheduled actions that execute at specific ticks:

```yaml
scenario_events:
  - type: <EventType>
    # Event-specific fields
    schedule:
      type: OneTime | Repeating
      # Schedule-specific fields
```

---

## Event Types

| Type | Description |
|:-----|:------------|
| `DirectTransfer` | Move balance between agents |
| `CustomTransactionArrival` | Inject specific transaction |
| `CollateralAdjustment` | Add/remove collateral |
| `GlobalArrivalRateChange` | Multiply all arrival rates |
| `AgentArrivalRateChange` | Multiply one agent's rate |
| `CounterpartyWeightChange` | Adjust routing weights |
| `DeadlineWindowChange` | Adjust deadline ranges |

---

## Event Scheduling

All events require a `schedule` field with one of two types:

### `OneTime` Schedule

Execute once at a specific tick.

```yaml
schedule:
  type: OneTime
  tick: <int>        # Required, >= 0
```

#### Fields

| Field | Type | Constraint | Description |
|:------|:-----|:-----------|:------------|
| `tick` | `int` | `>= 0` | Tick to execute event |

#### Example

```yaml
schedule:
  type: OneTime
  tick: 100          # Execute at tick 100
```

### `Repeating` Schedule

Execute periodically starting from a tick.

```yaml
schedule:
  type: Repeating
  start_tick: <int>  # Required, >= 0
  interval: <int>    # Required, > 0
```

#### Fields

| Field | Type | Constraint | Description |
|:------|:-----|:-----------|:------------|
| `start_tick` | `int` | `>= 0` | First execution tick |
| `interval` | `int` | `> 0` | Ticks between executions |

#### Behavior

Executes at: `start_tick`, `start_tick + interval`, `start_tick + 2×interval`, ...

#### Example

```yaml
schedule:
  type: Repeating
  start_tick: 0
  interval: 100      # Every 100 ticks starting at 0
```

---

## `DirectTransfer`

Instantly move balance from one agent to another.

### Schema

```yaml
- type: DirectTransfer
  from_agent: <string>    # Required, existing agent ID
  to_agent: <string>      # Required, existing agent ID
  amount: <int>           # Required, cents, > 0
  schedule: <Schedule>
```

### Fields

| Field | Type | Constraint | Description |
|:------|:-----|:-----------|:------------|
| `from_agent` | `str` | Must exist | Sender agent ID |
| `to_agent` | `str` | Must exist | Receiver agent ID |
| `amount` | `int` | `> 0` | Transfer amount (cents) |

### Behavior

- Immediate balance adjustment
- Does **not** create a transaction
- Bypasses queues and settlement
- Useful for external funding, subsidies

### Example

```yaml
scenario_events:
  - type: DirectTransfer
    from_agent: CENTRAL_BANK
    to_agent: STRESSED_BANK
    amount: 5000000           # $50,000 emergency funding
    schedule:
      type: OneTime
      tick: 1000
```

---

## `CustomTransactionArrival`

Inject a specific transaction into the system.

### Schema

```yaml
- type: CustomTransactionArrival
  from_agent: <string>       # Required
  to_agent: <string>         # Required
  amount: <int>              # Required, cents, > 0
  priority: <int>            # Optional, 0-10
  deadline: <int>            # Optional, ticks > 0
  is_divisible: <bool>       # Optional
  schedule: <Schedule>
```

### Fields

| Field | Type | Constraint | Description |
|:------|:-----|:-----------|:------------|
| `from_agent` | `str` | Must exist | Sender |
| `to_agent` | `str` | Must exist | Receiver |
| `amount` | `int` | `> 0` | Amount (cents) |
| `priority` | `int` | `0-10` | Priority level |
| `deadline` | `int` | `> 0` | Ticks until deadline |
| `is_divisible` | `bool` | - | Can be split |

### Behavior

- Creates a real transaction
- Goes through normal Queue 1 → Queue 2 → Settlement flow
- Uses agent's policy for release decisions
- Deadline relative to arrival tick

### Example

```yaml
scenario_events:
  # Urgent payment at tick 500
  - type: CustomTransactionArrival
    from_agent: BANK_A
    to_agent: BANK_B
    amount: 1000000          # $10,000
    priority: 9              # Urgent
    deadline: 20             # 20 ticks to settle
    is_divisible: true
    schedule:
      type: OneTime
      tick: 500
```

---

## `CollateralAdjustment`

Add or remove collateral for an agent.

### Schema

```yaml
- type: CollateralAdjustment
  agent: <string>           # Required
  delta: <int>              # Required, cents (can be negative)
  schedule: <Schedule>
```

### Fields

| Field | Type | Constraint | Description |
|:------|:-----|:-----------|:------------|
| `agent` | `str` | Must exist | Target agent |
| `delta` | `int` | Any | Change amount (+ add, - remove) |

### Behavior

- Positive delta: Add collateral (increase credit capacity)
- Negative delta: Remove collateral (reduce credit capacity)
- Subject to collateral opportunity cost

### Example

```yaml
scenario_events:
  # Add $25,000 collateral to BANK_A on day 16
  - type: CollateralAdjustment
    agent: BANK_A
    delta: 2500000
    schedule:
      type: OneTime
      tick: 1560

  # Remove $10,000 collateral
  - type: CollateralAdjustment
    agent: BANK_A
    delta: -1000000
    schedule:
      type: OneTime
      tick: 2000
```

---

## `GlobalArrivalRateChange`

Multiply all agents' arrival rates.

### Schema

```yaml
- type: GlobalArrivalRateChange
  multiplier: <float>       # Required, > 0
  schedule: <Schedule>
```

### Fields

| Field | Type | Constraint | Description |
|:------|:-----|:-----------|:------------|
| `multiplier` | `float` | `> 0` | Rate multiplier |

### Behavior

- All `rate_per_tick` values multiplied
- Persists until next change
- Use 1.0 to restore original rate

### Example

```yaml
scenario_events:
  # Activity spike
  - type: GlobalArrivalRateChange
    multiplier: 2.5          # 2.5x normal activity
    schedule:
      type: OneTime
      tick: 1520

  # Back to normal
  - type: GlobalArrivalRateChange
    multiplier: 1.0          # Restore
    schedule:
      type: OneTime
      tick: 1580
```

---

## `AgentArrivalRateChange`

Multiply a single agent's arrival rate.

### Schema

```yaml
- type: AgentArrivalRateChange
  agent: <string>           # Required
  multiplier: <float>       # Required, > 0
  schedule: <Schedule>
```

### Fields

| Field | Type | Constraint | Description |
|:------|:-----|:-----------|:------------|
| `agent` | `str` | Must exist | Target agent |
| `multiplier` | `float` | `> 0` | Rate multiplier |

### Behavior

- Only affects specified agent
- Stacks with global multiplier
- Persists until next change

### Example

```yaml
scenario_events:
  # BANK_A goes quiet
  - type: AgentArrivalRateChange
    agent: BANK_A
    multiplier: 0.2          # 20% of normal
    schedule:
      type: OneTime
      tick: 800
```

---

## `CounterpartyWeightChange`

Adjust routing weights for an agent's outgoing payments.

### Schema

```yaml
- type: CounterpartyWeightChange
  agent: <string>              # Required
  counterparty: <string>       # Required
  new_weight: <float>          # Required, 0-1
  auto_balance_others: <bool>  # Optional, default: false
  schedule: <Schedule>
```

### Fields

| Field | Type | Constraint | Description |
|:------|:-----|:-----------|:------------|
| `agent` | `str` | Must exist | Agent generating payments |
| `counterparty` | `str` | Must exist | Target counterparty |
| `new_weight` | `float` | `0.0-1.0` | New weight |
| `auto_balance_others` | `bool` | - | Redistribute remaining weight |

### Behavior

- Changes probability of routing to counterparty
- `auto_balance_others=true`: Scales other weights to maintain sum=1
- `auto_balance_others=false`: Only changes specified weight

### Example

```yaml
scenario_events:
  # BANK_A stops sending to BANK_B
  - type: CounterpartyWeightChange
    agent: BANK_A
    counterparty: BANK_B
    new_weight: 0.0
    auto_balance_others: true    # Redistribute to others
    schedule:
      type: OneTime
      tick: 1000
```

---

## `DeadlineWindowChange`

Adjust deadline ranges for all agents.

### Schema

```yaml
- type: DeadlineWindowChange
  min_ticks_multiplier: <float>   # Optional, > 0
  max_ticks_multiplier: <float>   # Optional, > 0
  schedule: <Schedule>
```

### Fields

| Field | Type | Constraint | Description |
|:------|:-----|:-----------|:------------|
| `min_ticks_multiplier` | `float` | `> 0` | Multiply deadline min |
| `max_ticks_multiplier` | `float` | `> 0` | Multiply deadline max |

**Constraint**: At least one multiplier must be specified.

### Behavior

- Affects new transaction deadlines
- Does not change existing transactions
- Useful for simulating time pressure

### Example

```yaml
scenario_events:
  # Tighter deadlines (crisis mode)
  - type: DeadlineWindowChange
    min_ticks_multiplier: 0.5    # Half the minimum
    max_ticks_multiplier: 0.5    # Half the maximum
    schedule:
      type: OneTime
      tick: 1500
```

---

## Complete Examples

### Simple Stress Test

```yaml
scenario_events:
  # Activity spike at tick 500
  - type: GlobalArrivalRateChange
    multiplier: 2.0
    schedule:
      type: OneTime
      tick: 500

  # Large urgent payment
  - type: CustomTransactionArrival
    from_agent: BANK_A
    to_agent: BANK_B
    amount: 5000000
    priority: 9
    deadline: 15
    schedule:
      type: OneTime
      tick: 550

  # Return to normal
  - type: GlobalArrivalRateChange
    multiplier: 1.0
    schedule:
      type: OneTime
      tick: 600
```

### Multi-Day Crisis Scenario

```yaml
scenario_events:
  # Day 1: Normal operations with offset opportunity
  - type: CustomTransactionArrival
    from_agent: BIG_BANK_A
    to_agent: SMALL_BANK_B
    amount: 900000
    priority: 7
    deadline: 35
    schedule:
      type: OneTime
      tick: 15

  - type: CustomTransactionArrival
    from_agent: SMALL_BANK_B
    to_agent: BIG_BANK_A
    amount: 850000
    priority: 7
    deadline: 35
    schedule:
      type: OneTime
      tick: 16

  # Day 5: First liquidity pressure
  - type: CustomTransactionArrival
    from_agent: SMALL_BANK_B
    to_agent: BIG_BANK_B
    amount: 2200000
    priority: 7
    deadline: 40
    schedule:
      type: OneTime
      tick: 450

  # Day 6: Collateral boost
  - type: CollateralAdjustment
    agent: BIG_BANK_A
    delta: 2000000
    schedule:
      type: OneTime
      tick: 550

  # Day 10: Activity surge
  - type: GlobalArrivalRateChange
    multiplier: 2.0
    schedule:
      type: OneTime
      tick: 920

  - type: GlobalArrivalRateChange
    multiplier: 1.0
    schedule:
      type: OneTime
      tick: 980
```

### BIS-Style Deterministic Injections

```yaml
scenario_events:
  # Period 1: Incoming payments
  - type: CustomTransactionArrival
    from_agent: COUNTERPARTY
    to_agent: FOCAL_BANK
    amount: 500000
    priority: 5
    deadline: 5
    schedule:
      type: OneTime
      tick: 0

  # Period 2: Small outgoing
  - type: CustomTransactionArrival
    from_agent: FOCAL_BANK
    to_agent: COUNTERPARTY
    amount: 500000
    priority: 5
    deadline: 4
    schedule:
      type: OneTime
      tick: 1

  # Period 3: Large urgent outgoing
  - type: CustomTransactionArrival
    from_agent: FOCAL_BANK
    to_agent: COUNTERPARTY
    amount: 1000000
    priority: 9
    deadline: 4
    schedule:
      type: OneTime
      tick: 2
```

---

## Validation Rules

### Agent References

```
Error: Agent 'UNKNOWN' not found
```

**Fix**: All agent references must match IDs in `agents` list.

### Deadline Multipliers

```
Error: At least one multiplier required
```

**Fix**: `DeadlineWindowChange` needs at least one of `min_ticks_multiplier` or `max_ticks_multiplier`.

### Positive Amounts

```
Error: amount must be > 0
```

**Fix**: Transaction amounts must be positive.

---

## Navigation

**Previous**: [LSM Configuration](lsm-config.md)
**Next**: [Priority System](priority-system.md)
