# OrchestratorConfig

**Location:** `backend/src/orchestrator/engine.rs:102-168`

The main configuration struct for initializing an Orchestrator instance. Controls all aspects of simulation behavior including time management, cost calculations, and settlement optimization.

---

## Struct Definition

```rust
#[derive(Debug, Clone, serde::Serialize, serde::Deserialize)]
pub struct OrchestratorConfig {
    pub ticks_per_day: usize,
    pub eod_rush_threshold: f64,
    pub num_days: usize,
    pub rng_seed: u64,
    pub agent_configs: Vec<AgentConfig>,
    pub cost_rates: CostRates,
    pub lsm_config: LsmConfig,
    pub scenario_events: Option<Vec<ScheduledEvent>>,
    pub queue1_ordering: Queue1Ordering,
    pub priority_mode: bool,
    pub priority_escalation: PriorityEscalationConfig,
    pub algorithm_sequencing: bool,
    pub entry_disposition_offsetting: bool,
    pub deferred_crediting: bool,
    pub deadline_cap_at_eod: bool,
}
```

---

## Fields

### `ticks_per_day`

**Type:** `usize`
**Required:** Yes
**Location:** `engine.rs:104`

Number of discrete time steps per business day.

**Description:**
Determines the granularity of the simulation. Higher values provide more realistic timing but increase computational cost.

**Example Values:**
- `100` ticks/day = ~5-6 minutes per tick (10-hour day)
- `50` ticks/day = ~12 minutes per tick
- `1000` ticks/day = ~36 seconds per tick (high-fidelity)

**Usage:**
```yaml
simulation:
  ticks_per_day: 100
```

**Related:**
- Used by `TimeManager` to track day boundaries
- Affects all time-based calculations (costs, deadlines)
- See [TimeManager](../09-time/time-manager.md)

---

### `eod_rush_threshold`

**Type:** `f64`
**Default:** `0.8`
**Location:** `engine.rs:107-111`

Fraction of day (0.0-1.0) when the end-of-day rush period begins.

**Description:**
Policies can check the `is_eod_rush` field in the evaluation context to enable time-based strategies. When `tick_in_day / ticks_per_day >= eod_rush_threshold`, the system is in EOD rush mode.

**Valid Values:** `0.0` to `1.0`

**Example:**
- `0.8` = Last 20% of day (default)
- `0.9` = Last 10% of day
- `0.7` = Last 30% of day

**Usage:**
```yaml
simulation:
  eod_rush_threshold: 0.8
```

**Implementation:**
```rust
// In tick processing (engine.rs)
let is_eod_rush = (tick_in_day as f64 / ticks_per_day as f64) >= eod_rush_threshold;
```

**Related:**
- Used by cash manager policies for urgency decisions
- See [Policy Overview](../08-policies/policy-overview.md)

---

### `num_days`

**Type:** `usize`
**Required:** Yes
**Location:** `engine.rs:114`

Total number of business days to simulate.

**Description:**
The simulation runs for `num_days × ticks_per_day` total ticks. At day boundaries (tick % ticks_per_day == 0), end-of-day processing occurs.

**Example:**
```yaml
simulation:
  num_days: 10
```

**Related:**
- `total_ticks = num_days × ticks_per_day`
- Daily metrics are tracked per day
- EOD penalties applied at each day boundary

---

### `rng_seed`

**Type:** `u64`
**Required:** Yes
**Location:** `engine.rs:117`

Seed for the deterministic random number generator.

**Description:**
Ensures reproducible simulation results. The same seed with the same configuration will always produce identical output.

**CRITICAL INVARIANT:** Same seed + same config = byte-for-byte identical results.

**Implementation:**
```rust
// Uses xorshift64* RNG (backend/src/rng/xorshift.rs)
let mut rng = RngManager::new(seed);
// 0 is converted to 1 internally (0 would cause infinite loop)
```

**Example:**
```yaml
simulation:
  rng_seed: 12345
```

**Related:**
- See [RNG System](../03-generators/rng-system.md)
- Used by `ArrivalGenerator` for transaction generation
- Used for all random decisions (amounts, priorities, deadlines)

---

### `agent_configs`

**Type:** `Vec<AgentConfig>`
**Required:** Yes (minimum 1 agent)
**Location:** `engine.rs:120`

Per-agent configuration for all participating banks.

**Description:**
Defines initial state, policies, and arrival patterns for each agent. Order matters for deterministic iteration.

**Example:**
```yaml
agents:
  - id: "BANK_A"
    opening_balance: 1000000
    unsecured_cap: 500000
    policy:
      type: Deadline
      urgency_threshold: 5
    arrival_config:
      rate_per_tick: 5.0
      # ...
```

**Validation:**
- Agent IDs must be unique
- At least one agent required
- Counterparty references must be valid

**Related:**
- See [AgentConfig](agent-config.md) for full details
- See [Agent Model](../02-models/agent.md)

---

### `cost_rates`

**Type:** `CostRates`
**Required:** Yes
**Location:** `engine.rs:123`

Parameters for cost calculation during simulation.

**Description:**
Defines rates for overdraft costs, delay costs, penalties, and other simulation costs. All monetary values in cents.

**Example:**
```yaml
cost_rates:
  overdraft_bps_per_tick: 0.001
  delay_cost_per_tick_per_cent: 0.0001
  eod_penalty_per_transaction: 10000
  deadline_penalty: 50000
  split_friction_cost: 1000
  overdue_delay_multiplier: 5.0
```

**Related:**
- See [CostRates](cost-rates.md) for full details
- See [Cost Calculations](../06-costs/cost-calculations.md)

---

### `lsm_config`

**Type:** `LsmConfig`
**Required:** Yes
**Location:** `engine.rs:126`

Configuration for Liquidity Saving Mechanism (LSM) optimization.

**Description:**
Controls bilateral offsetting and cycle detection for reducing liquidity needs.

**Default Values:**
```rust
LsmConfig {
    enable_bilateral: true,
    enable_cycles: true,
    max_cycle_length: 4,
    max_cycles_per_tick: 10,
}
```

**Example:**
```yaml
lsm_config:
  enable_bilateral: true
  enable_cycles: true
  max_cycle_length: 4
  max_cycles_per_tick: 10
```

**Related:**
- See [LsmConfig](lsm-config.md) for full details
- See [LSM Bilateral](../05-settlement/lsm-bilateral.md)
- See [LSM Cycles](../05-settlement/lsm-cycles.md)

---

### `scenario_events`

**Type:** `Option<Vec<ScheduledEvent>>`
**Default:** `None`
**Location:** `engine.rs:128-131`

Scheduled events that modify simulation state at specific ticks.

**Description:**
Allows dynamic interventions during simulation: balance transfers, arrival rate changes, collateral adjustments, custom transactions.

**Example:**
```yaml
scenario_events:
  - event:
      type: direct_transfer
      from_agent: "BANK_A"
      to_agent: "BANK_B"
      amount: 500000
    schedule:
      type: one_time
      tick: 50
```

**Event Types:**
- `direct_transfer` - Move balance between agents
- `custom_transaction_arrival` - Inject specific transaction
- `collateral_adjustment` - Modify agent's collateral
- `global_arrival_rate_change` - Scale all arrival rates
- `agent_arrival_rate_change` - Scale one agent's rate
- `counterparty_weight_change` - Modify counterparty preferences
- `deadline_window_change` - Adjust deadline ranges

**Schedule Types:**
- `one_time` - Execute once at specified tick
- `repeating` - Execute at intervals starting from tick

**Related:**
- See [Scenario Events](scenario-events.md) for full details

---

### `queue1_ordering`

**Type:** `Queue1Ordering`
**Default:** `Fifo`
**Location:** `engine.rs:133-137`

Strategy for ordering transactions in agent internal queues (Queue 1).

**Description:**
Determines how transactions are ordered when the cash manager policy iterates through Queue 1.

**Variants:**

```rust
pub enum Queue1Ordering {
    Fifo,            // First-In-First-Out (default)
    PriorityDeadline, // High priority first, then soonest deadline
}
```

**`Fifo`:**
- Transactions processed in arrival order
- Backward compatible (default)
- Simple, predictable behavior

**`PriorityDeadline`:**
- Sort by priority (descending): higher priority first
- Within same priority, sort by deadline (ascending): soonest first
- Better for time-critical payments

**Example:**
```yaml
queue1_ordering: priority_deadline
```

**Related:**
- See [Queue1 Internal](../04-queues/queue1-internal.md)
- See [Queue Ordering](../04-queues/queue-ordering.md)

---

### `priority_mode`

**Type:** `bool`
**Default:** `false`
**Location:** `engine.rs:139-146`

Enable TARGET2-style Queue 2 priority processing.

**Description:**
When enabled, Queue 2 (RTGS queue) processes transactions in priority band order:
1. **Urgent (8-10):** Processed first
2. **Normal (4-7):** Processed second
3. **Low (0-3):** Processed last

Within each band, FIFO ordering is preserved.

**Example:**
```yaml
priority_mode: true
```

**Use Case:**
- Models real-world RTGS systems like TARGET2
- Time-critical payments (CLS, margin calls) settle first
- Batch payments settle last

**Related:**
- See [Queue2 RTGS](../04-queues/queue2-rtgs.md)
- See [Priority Bands](#priorityband-enum)

---

### `priority_escalation`

**Type:** `PriorityEscalationConfig`
**Default:** Disabled
**Location:** `engine.rs:148-151`

Configuration for dynamic priority boosting as deadlines approach.

**Description:**
Prevents low-priority transactions from being starved when they become urgent due to time pressure. Priority is boosted based on ticks remaining until deadline.

**Default Values:**
```rust
PriorityEscalationConfig {
    enabled: false,
    curve: "linear",
    start_escalating_at_ticks: 20,
    max_boost: 3,
}
```

**Example:**
```yaml
priority_escalation:
  enabled: true
  curve: linear
  start_escalating_at_ticks: 20
  max_boost: 3
```

**Escalation Formula (linear):**
```
boost = max_boost × (1 - ticks_remaining / start_escalating_at_ticks)
```

**Example with `start_escalating_at_ticks=20, max_boost=3`:**
- 20 ticks remaining: +0 boost
- 10 ticks remaining: +1.5 boost (rounded)
- 5 ticks remaining: +2.25 boost (rounded)
- 1 tick remaining: +3 boost (max)

**Related:**
- See [PriorityEscalationConfig](#priorityescalationconfig)

---

### `algorithm_sequencing`

**Type:** `bool`
**Default:** `false`
**Location:** `engine.rs:153-159`

Enable algorithm execution event emission.

**Description:**
When enabled, emits `AlgorithmExecution` events for each settlement algorithm phase:
- **Algorithm 1:** FIFO settlement (RTGS immediate + Queue 2)
- **Algorithm 2:** Bilateral offsetting (LSM)
- **Algorithm 3:** Multilateral cycle settlement (LSM)

**Use Case:**
- Performance analysis
- Algorithm comparison
- Debugging settlement behavior

**Example:**
```yaml
algorithm_sequencing: true
```

**Related:**
- See [AlgorithmExecution Event](../07-events/system-events.md#algorithmexecution)

---

### `entry_disposition_offsetting`

**Type:** `bool`
**Default:** `false`
**Location:** `engine.rs:161-167`

Enable bilateral offset check at transaction entry time.

**Description:**
TARGET2 Phase 3 feature. When a new transaction enters Queue 2, the system immediately checks if there's an opposite payment queued. If so, they can be offset without waiting for periodic LSM runs.

**Example:**
```yaml
entry_disposition_offsetting: true
```

**Use Case:**
- Faster bilateral settlements
- Reduced queue depths
- Models TARGET2 behavior

**Related:**
- See [EntryDispositionOffset Event](../07-events/settlement-events.md#entrydispositionoffset)
- See [LSM Bilateral](../05-settlement/lsm-bilateral.md)

---

### `deferred_crediting`

**Type:** `bool`
**Default:** `false`
**Location:** `engine.rs:169-171`

Enable Castro et al. (2025) compatible settlement mode with batched credits.

**Description:**
When enabled, credits from settled transactions are batched and applied at the end of each tick rather than immediately. This prevents within-tick liquidity recycling.

**Behavior:**

When enabled:
- Credits are batched and applied at end of tick
- Prevents within-tick liquidity recycling
- Receivers cannot use incoming funds until next tick

When disabled (default):
- Credits are applied immediately after settlement
- Within-tick recycling: Agent A pays B, B can use funds to pay C in same tick

**Example:**
```yaml
deferred_crediting: true
```

**Use Case:**
- Castro et al. (2025) model replication
- Research on liquidity recycling effects
- Conservative settlement analysis

**Related:**
- See [Advanced Settings](../../scenario/advanced-settings.md#deferred_crediting)

---

### `deadline_cap_at_eod`

**Type:** `bool`
**Default:** `false`
**Location:** `engine.rs:173-175`

Enable Castro et al. (2025) compatible deadline generation with end-of-day caps.

**Description:**
When enabled, all generated transaction deadlines are capped at the end of the current simulation day. This ensures all payments must settle within the same business day they arrive, creating realistic intraday settlement pressure.

**Behavior:**

When enabled:
- All generated transaction deadlines capped at end of current day
- Day boundary = `(current_day + 1) × ticks_per_day`
- Creates realistic same-day settlement requirements

When disabled (default):
- Deadlines only capped at episode end (`num_days × ticks_per_day`)
- Transactions can span multiple days

**Implementation:**
```rust
// In ArrivalGenerator::generate_deadline()
if self.deadline_cap_at_eod {
    let current_day = arrival_tick / self.ticks_per_day;
    let day_end_tick = (current_day + 1) * self.ticks_per_day;
    deadline.min(day_end_tick)
}
```

**Example:**
```yaml
deadline_cap_at_eod: true
```

**Use Case:**
- Castro et al. (2025) model replication
- Realistic same-day settlement requirements
- Research on EOD settlement pressure

**Related:**
- See [Advanced Settings](../../scenario/advanced-settings.md#deadline_cap_at_eod)
- See [ArrivalConfig](arrival-config.md) for deadline_range configuration

---

## Related Types

### `PriorityEscalationConfig`

**Location:** `engine.rs:187-204`

```rust
pub struct PriorityEscalationConfig {
    pub enabled: bool,           // Enable escalation (default: false)
    pub curve: String,           // Curve type ("linear" only)
    pub start_escalating_at_ticks: usize,  // When to start (default: 20)
    pub max_boost: u8,           // Maximum boost (default: 3)
}
```

### `Queue1Ordering` Enum

**Location:** `engine.rs:230-238`

```rust
pub enum Queue1Ordering {
    Fifo,             // First-In-First-Out (default)
    PriorityDeadline, // High priority first, then soonest deadline
}
```

### `PriorityBand` Enum

**Location:** `engine.rs:428-435`

```rust
pub enum PriorityBand {
    Urgent,  // Priority 8-10
    Normal,  // Priority 4-7
    Low,     // Priority 0-3
}
```

**Band Ranges:**
| Band | Priority Range | Use Case |
|------|----------------|----------|
| Urgent | 8-10 | CLS, margin calls, time-critical |
| Normal | 4-7 | Standard interbank payments |
| Low | 0-3 | Batch payments, internal transfers |

---

## Python Configuration

**Location:** `api/payment_simulator/config/schemas.py`

```python
class SimulationSettings(BaseModel):
    ticks_per_day: int
    num_days: int
    rng_seed: int

class SimulationConfig(BaseModel):
    simulation: SimulationSettings
    agents: List[AgentConfig]
    cost_rates: CostRates
    lsm_config: LsmConfig
    scenario_events: Optional[List[ScenarioEvent]] = None
```

**FFI Conversion:**
The Python `SimulationConfig.to_ffi_dict()` method converts to Rust-compatible format:

```python
def to_ffi_dict(self) -> dict:
    return {
        "ticks_per_day": self.simulation.ticks_per_day,
        "num_days": self.simulation.num_days,
        "rng_seed": self.simulation.rng_seed,
        "agent_configs": [...],
        "cost_rates": {...},
        "lsm_config": {...},
        "scenario_events": [...] if self.scenario_events else None,
    }
```

---

## Example Configuration

### YAML Format

```yaml
simulation:
  ticks_per_day: 100
  num_days: 5
  rng_seed: 42

agents:
  - id: "BANK_A"
    opening_balance: 1000000
    unsecured_cap: 500000
    policy:
      type: Deadline
      urgency_threshold: 5
    arrival_config:
      rate_per_tick: 5.0
      amount_distribution:
        type: Normal
        mean: 100000
        std_dev: 30000
      counterparty_weights:
        BANK_B: 0.5
        BANK_C: 0.5
      deadline_range: [5, 20]
      priority: 5
      divisible: false

  - id: "BANK_B"
    opening_balance: 1000000
    unsecured_cap: 500000
    policy:
      type: Fifo
    arrival_config:
      rate_per_tick: 3.0
      amount_distribution:
        type: Normal
        mean: 80000
        std_dev: 20000
      counterparty_weights:
        BANK_A: 0.6
        BANK_C: 0.4
      deadline_range: [5, 20]
      priority: 5
      divisible: false

  - id: "BANK_C"
    opening_balance: 1000000
    unsecured_cap: 500000
    policy:
      type: Fifo
    arrival_config:
      rate_per_tick: 4.0
      amount_distribution:
        type: Normal
        mean: 90000
        std_dev: 25000
      counterparty_weights:
        BANK_A: 0.5
        BANK_B: 0.5
      deadline_range: [5, 20]
      priority: 5
      divisible: false

cost_rates:
  overdraft_bps_per_tick: 0.001
  delay_cost_per_tick_per_cent: 0.0001
  collateral_cost_per_tick_bps: 0.0002
  eod_penalty_per_transaction: 10000
  deadline_penalty: 50000
  split_friction_cost: 1000
  overdue_delay_multiplier: 5.0

lsm_config:
  enable_bilateral: true
  enable_cycles: true
  max_cycle_length: 4
  max_cycles_per_tick: 10

# Optional: Advanced settings
queue1_ordering: fifo
priority_mode: false
algorithm_sequencing: false
entry_disposition_offsetting: false
deferred_crediting: false
deadline_cap_at_eod: false
```

---

## See Also

- [AgentConfig](agent-config.md) - Per-agent configuration
- [CostRates](cost-rates.md) - Cost calculation parameters
- [LsmConfig](lsm-config.md) - LSM optimization settings
- [ArrivalConfig](arrival-config.md) - Transaction generation
- [Scenario Events](scenario-events.md) - Dynamic events
- [Orchestrator Bindings](../10-ffi/orchestrator-bindings.md) - FFI methods

---

*Last Updated: 2025-12-02*
