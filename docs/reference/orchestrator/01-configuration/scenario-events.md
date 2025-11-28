# Scenario Events

**Location:** `backend/src/events/mod.rs`

Scheduled events that modify simulation state at specific ticks. Enable dynamic interventions like balance transfers, arrival rate changes, and custom transactions during simulation.

---

## Overview

Scenario events allow researchers to:
- Inject specific transactions for testing
- Model liquidity shocks (balance transfers)
- Simulate market conditions (arrival rate changes)
- Test policy responses to changing conditions

---

## Event Structure

### ScheduledEvent

**Location:** `events/mod.rs`

```rust
#[derive(Debug, Clone, serde::Serialize, serde::Deserialize)]
pub struct ScheduledEvent {
    pub event: ScenarioEventType,
    pub schedule: EventSchedule,
}
```

### EventSchedule

```rust
#[derive(Debug, Clone, serde::Serialize, serde::Deserialize)]
pub enum EventSchedule {
    OneTime { tick: usize },
    Repeating { start_tick: usize, interval: usize },
}
```

**OneTime:**
- Execute once at specified tick
- Used for one-off interventions

**Repeating:**
- Execute at `start_tick`, then every `interval` ticks
- Used for periodic events

---

## Event Types

### DirectTransferEvent

**Purpose:** Move balance directly between agents.

**Parameters:**
| Field | Type | Description |
|-------|------|-------------|
| `from_agent` | `String` | Source agent ID |
| `to_agent` | `String` | Destination agent ID |
| `amount` | `i64` | Amount in cents |

**Example:**
```yaml
scenario_events:
  - event:
      type: direct_transfer
      from_agent: "BANK_A"
      to_agent: "BANK_B"
      amount: 500000  # $5,000
    schedule:
      type: one_time
      tick: 50
```

**Use Cases:**
- Model liquidity injection
- Simulate collateral movements
- Create liquidity stress tests

**Emits:** `ScenarioEventExecuted` event

---

### CustomTransactionArrivalEvent

**Purpose:** Inject a specific transaction into the system.

**Parameters:**
| Field | Type | Description |
|-------|------|-------------|
| `from_agent` | `String` | Sender ID |
| `to_agent` | `String` | Receiver ID |
| `amount` | `i64` | Amount in cents |
| `priority` | `u8` | Priority (0-10) |
| `deadline` | `usize` | Deadline tick |
| `divisible` | `bool` | Can be split |

**Example:**
```yaml
scenario_events:
  - event:
      type: custom_transaction_arrival
      from_agent: "BANK_A"
      to_agent: "BANK_B"
      amount: 1000000  # $10,000
      priority: 8
      deadline: 75
      divisible: false
    schedule:
      type: one_time
      tick: 50
```

**Use Cases:**
- Test specific settlement scenarios
- Inject high-priority CLS-like payments
- Create deadline pressure tests

**Emits:** `Arrival` event (like normal arrivals)

---

### CollateralAdjustmentEvent

**Purpose:** Modify an agent's posted collateral.

**Parameters:**
| Field | Type | Description |
|-------|------|-------------|
| `agent` | `String` | Agent ID |
| `delta` | `i64` | Change amount (positive or negative) |

**Example:**
```yaml
scenario_events:
  - event:
      type: collateral_adjustment
      agent: "BANK_A"
      delta: -500000  # Withdraw $5,000 collateral
    schedule:
      type: one_time
      tick: 30
```

**Use Cases:**
- Model collateral calls
- Simulate intraday credit changes
- Test credit capacity stress

**Emits:** `CollateralPost` or `CollateralWithdraw` event

---

### GlobalArrivalRateChangeEvent

**Purpose:** Scale all agents' arrival rates.

**Parameters:**
| Field | Type | Description |
|-------|------|-------------|
| `multiplier` | `f64` | Scale factor (1.0 = no change) |

**Example:**
```yaml
scenario_events:
  - event:
      type: global_arrival_rate_change
      multiplier: 1.5  # 50% increase in all arrivals
    schedule:
      type: one_time
      tick: 50
```

**Important:** Multiplier is applied to BASE rates, not current rates. This prevents compounding.

```rust
// Implementation
new_rate = base_config.rate_per_tick × multiplier
```

**Use Cases:**
- Model market stress (2x arrivals)
- Model quiet periods (0.5x arrivals)
- End-of-day rush simulation

---

### AgentArrivalRateChangeEvent

**Purpose:** Scale a specific agent's arrival rate.

**Parameters:**
| Field | Type | Description |
|-------|------|-------------|
| `agent` | `String` | Agent ID |
| `multiplier` | `f64` | Scale factor |

**Example:**
```yaml
scenario_events:
  - event:
      type: agent_arrival_rate_change
      agent: "BANK_A"
      multiplier: 2.0  # Double BANK_A's arrivals
    schedule:
      type: one_time
      tick: 50
```

**Use Cases:**
- Model agent-specific volume spikes
- Simulate institution stress
- Test policy responses to volume changes

---

### CounterpartyWeightChangeEvent

**Purpose:** Modify counterparty selection weights.

**Parameters:**
| Field | Type | Description |
|-------|------|-------------|
| `agent` | `String` | Agent ID |
| `counterparty` | `String` | Target counterparty ID |
| `new_weight` | `f64` | New weight value |
| `auto_balance_others` | `bool` | Adjust other weights proportionally |

**Example:**
```yaml
scenario_events:
  - event:
      type: counterparty_weight_change
      agent: "BANK_A"
      counterparty: "BANK_B"
      new_weight: 0.8  # 80% to BANK_B
      auto_balance_others: true
    schedule:
      type: one_time
      tick: 25
```

**Use Cases:**
- Model correspondent banking relationships
- Simulate market concentration
- Test network effects

---

### DeadlineWindowChangeEvent

**Purpose:** Modify deadline ranges globally.

**Parameters:**
| Field | Type | Description |
|-------|------|-------------|
| `min_ticks_multiplier` | `f64` | Scale factor for minimum offset |
| `max_ticks_multiplier` | `f64` | Scale factor for maximum offset |

**Example:**
```yaml
scenario_events:
  - event:
      type: deadline_window_change
      min_ticks_multiplier: 0.5  # Halve minimum deadline
      max_ticks_multiplier: 0.5  # Halve maximum deadline
    schedule:
      type: one_time
      tick: 50
```

**Use Cases:**
- Model deadline pressure
- Simulate tighter settlement requirements
- Test urgent transaction handling

---

## Schedule Types

### OneTime Schedule

Execute event once at specified tick.

```yaml
schedule:
  type: one_time
  tick: 50
```

### Repeating Schedule

Execute at intervals starting from specified tick.

```yaml
schedule:
  type: repeating
  start_tick: 10
  interval: 25  # Execute at ticks 10, 35, 60, 85, ...
```

---

## Python Configuration

**Location:** `api/payment_simulator/config/schemas.py`

```python
class DirectTransferEvent(BaseModel):
    type: Literal["direct_transfer"]
    from_agent: str
    to_agent: str
    amount: int

class CustomTransactionArrivalEvent(BaseModel):
    type: Literal["custom_transaction_arrival"]
    from_agent: str
    to_agent: str
    amount: int
    priority: int = 5
    deadline: int
    divisible: bool = False

class CollateralAdjustmentEvent(BaseModel):
    type: Literal["collateral_adjustment"]
    agent: str
    delta: int

class GlobalArrivalRateChangeEvent(BaseModel):
    type: Literal["global_arrival_rate_change"]
    multiplier: float

class AgentArrivalRateChangeEvent(BaseModel):
    type: Literal["agent_arrival_rate_change"]
    agent: str
    multiplier: float

class CounterpartyWeightChangeEvent(BaseModel):
    type: Literal["counterparty_weight_change"]
    agent: str
    counterparty: str
    new_weight: float
    auto_balance_others: bool = True

class DeadlineWindowChangeEvent(BaseModel):
    type: Literal["deadline_window_change"]
    min_ticks_multiplier: float
    max_ticks_multiplier: float

# Schedule types
class OneTimeSchedule(BaseModel):
    type: Literal["one_time"]
    tick: int

class RepeatingSchedule(BaseModel):
    type: Literal["repeating"]
    start_tick: int
    interval: int
```

---

## Example Scenarios

### Liquidity Shock Test

```yaml
scenario_events:
  # Remove liquidity at tick 25
  - event:
      type: direct_transfer
      from_agent: "BANK_A"
      to_agent: "BANK_B"
      amount: 500000
    schedule:
      type: one_time
      tick: 25

  # Restore liquidity at tick 75
  - event:
      type: direct_transfer
      from_agent: "BANK_B"
      to_agent: "BANK_A"
      amount: 500000
    schedule:
      type: one_time
      tick: 75
```

### Market Stress Simulation

```yaml
scenario_events:
  # Double arrivals mid-day
  - event:
      type: global_arrival_rate_change
      multiplier: 2.0
    schedule:
      type: one_time
      tick: 30

  # Tighten deadlines
  - event:
      type: deadline_window_change
      min_ticks_multiplier: 0.5
      max_ticks_multiplier: 0.5
    schedule:
      type: one_time
      tick: 30

  # Return to normal end-of-day
  - event:
      type: global_arrival_rate_change
      multiplier: 1.0
    schedule:
      type: one_time
      tick: 80
```

### Periodic Collateral Calls

```yaml
scenario_events:
  - event:
      type: collateral_adjustment
      agent: "BANK_A"
      delta: -100000
    schedule:
      type: repeating
      start_tick: 20
      interval: 50  # Every 50 ticks
```

### Targeted Transaction Injection

```yaml
scenario_events:
  # Inject CLS-like time-critical payment
  - event:
      type: custom_transaction_arrival
      from_agent: "BANK_A"
      to_agent: "BANK_B"
      amount: 5000000  # $50,000
      priority: 10
      deadline: 55  # 5 ticks after arrival
      divisible: false
    schedule:
      type: one_time
      tick: 50
```

---

## Event Execution Order

Each tick, events are processed in the following order:

1. **Scheduled events** (scenario_events) - First, modify state
2. **Automatic arrivals** - Generate new transactions
3. **Policy evaluation** - Cash manager decisions
4. **Settlement processing** - RTGS and LSM
5. **Cost calculation** - Accrue costs
6. **EOD processing** (if day boundary) - Apply EOD penalties

---

## Validation Rules

### Python Validation

- Agent IDs must reference existing agents
- Amounts must be positive (except `delta` can be negative)
- Tick values must be within simulation range
- Interval must be positive for repeating schedules

### Rust Validation

- Agent references validated at event execution time
- Invalid references logged as warnings, event skipped

---

## Related Events Emitted

| Scenario Event | Events Emitted |
|----------------|----------------|
| `DirectTransferEvent` | `ScenarioEventExecuted` |
| `CustomTransactionArrivalEvent` | `Arrival`, `ScenarioEventExecuted` |
| `CollateralAdjustmentEvent` | `CollateralPost`/`CollateralWithdraw`, `ScenarioEventExecuted` |
| `GlobalArrivalRateChangeEvent` | `ScenarioEventExecuted` |
| `AgentArrivalRateChangeEvent` | `ScenarioEventExecuted` |
| `CounterpartyWeightChangeEvent` | `ScenarioEventExecuted` |
| `DeadlineWindowChangeEvent` | `ScenarioEventExecuted` |

---

## See Also

- [OrchestratorConfig](orchestrator-config.md) - Parent configuration
- [ScenarioEventExecuted Event](../07-events/system-events.md#scenarioeventexecuted)
- [Tick Lifecycle](../09-time/tick-lifecycle.md) - Event execution order

---

*Last Updated: 2025-11-28*
