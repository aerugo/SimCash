# Orchestrator System Documentation Plan

**Status:** In Progress
**Created:** 2025-11-28
**Scope:** Complete technical reference documentation for the SimCash orchestrator and transaction system

---

## Overview

This document outlines the comprehensive documentation effort to capture **every** aspect of the orchestrator system. The goal is to document all generators, functions, helper functions, fields, variables, parameters, and settings with:

- Exact function/field name and location
- Implementation details
- Desired functionality and use case
- Code references (file:line)

---

## Documentation Structure

```
docs/reference/orchestrator/
├── DOCUMENTATION_PLAN.md          ← This file (tracking progress)
├── index.md                       ← Master index and navigation
│
├── 01-configuration/
│   ├── orchestrator-config.md     ← OrchestratorConfig fields
│   ├── agent-config.md            ← AgentConfig and limits
│   ├── cost-rates.md              ← CostRates and multipliers
│   ├── lsm-config.md              ← LsmConfig settings
│   ├── arrival-config.md          ← ArrivalConfig and bands
│   └── scenario-events.md         ← Scheduled event types
│
├── 02-models/
│   ├── transaction.md             ← Transaction struct and lifecycle
│   ├── agent.md                   ← Agent struct and methods
│   ├── simulation-state.md        ← SimulationState management
│   └── metrics.md                 ← SystemMetrics, DailyMetrics
│
├── 03-generators/
│   ├── arrival-generator.md       ← ArrivalGenerator class
│   ├── amount-distributions.md    ← All amount distribution types
│   ├── priority-distributions.md  ← All priority distribution types
│   └── rng-system.md              ← RngManager (xorshift64*)
│
├── 04-queues/
│   ├── queue1-internal.md         ← Agent internal queue
│   ├── queue2-rtgs.md             ← Central RTGS queue
│   ├── queue-index.md             ← AgentQueueIndex optimization
│   └── queue-ordering.md          ← Queue1Ordering strategies
│
├── 05-settlement/
│   ├── rtgs-engine.md             ← Real-time gross settlement
│   ├── lsm-bilateral.md           ← Bilateral offset algorithm
│   ├── lsm-cycles.md              ← Cycle detection and settlement
│   └── settlement-errors.md       ← Error types and handling
│
├── 06-costs/
│   ├── cost-accumulator.md        ← Per-agent cost tracking
│   ├── cost-breakdown.md          ← Per-tick cost components
│   ├── cost-calculations.md       ← Formulas and examples
│   └── priority-multipliers.md    ← BIS model priority costs
│
├── 07-events/
│   ├── event-system-overview.md   ← EventLog and architecture
│   ├── arrival-events.md          ← Arrival, PolicySubmit, etc.
│   ├── settlement-events.md       ← RTGS, LSM settlement events
│   ├── cost-events.md             ← CostAccrual, penalties
│   ├── collateral-events.md       ← Collateral management events
│   └── system-events.md           ← EOD, scenario events
│
├── 08-policies/
│   ├── policy-overview.md         ← Cash manager policy system
│   ├── fifo-policy.md             ← FIFO policy details
│   ├── deadline-policy.md         ← Deadline-aware policy
│   ├── liquidity-aware-policy.md  ← Buffer-maintaining policy
│   ├── liquidity-splitting.md     ← Smart splitting policy
│   └── custom-policies.md         ← FromJson and testing policies
│
├── 09-time/
│   ├── time-manager.md            ← TimeManager struct
│   ├── tick-lifecycle.md          ← What happens each tick
│   └── eod-processing.md          ← End-of-day handling
│
├── 10-ffi/
│   ├── ffi-overview.md            ← PyO3 boundary design
│   ├── orchestrator-bindings.md   ← Python Orchestrator methods
│   ├── type-conversions.md        ← Python ↔ Rust type mapping
│   └── state-provider.md          ← StateProvider abstraction
│
└── 11-cli/
    ├── run-command.md             ← payment-sim run
    ├── replay-command.md          ← payment-sim replay
    ├── output-modes.md            ← verbose, stream, event-stream
    └── persistence.md             ← Database persistence
```

---

## Component Inventory

### 1. OrchestratorConfig (Rust)
**Location:** `backend/src/orchestrator/engine.rs`

| Field | Type | Default | Purpose |
|-------|------|---------|---------|
| `ticks_per_day` | `usize` | - | Ticks per business day |
| `eod_rush_threshold` | `f64` | 0.8 | EOD rush trigger fraction |
| `num_days` | `usize` | - | Simulation duration |
| `rng_seed` | `u64` | - | Deterministic RNG seed |
| `agent_configs` | `Vec<AgentConfig>` | - | Per-agent settings |
| `cost_rates` | `CostRates` | - | Cost calculation params |
| `lsm_config` | `LsmConfig` | - | LSM optimization settings |
| `scenario_events` | `Option<Vec<ScheduledEvent>>` | None | Scheduled interventions |
| `queue1_ordering` | `Queue1Ordering` | FIFO | Queue 1 ordering strategy |
| `priority_mode` | `bool` | false | T2-style Queue 2 priority |
| `priority_escalation` | `PriorityEscalationConfig` | - | Dynamic priority boost |
| `algorithm_sequencing` | `bool` | false | Emit algorithm events |
| `entry_disposition_offsetting` | `bool` | false | Bilateral at entry |

**Status:** [ ] Documented

---

### 2. AgentConfig (Rust)
**Location:** `backend/src/orchestrator/engine.rs`

| Field | Type | Default | Purpose |
|-------|------|---------|---------|
| `id` | `String` | - | Unique identifier |
| `opening_balance` | `i64` | - | Starting balance (cents) |
| `unsecured_cap` | `i64` | - | Unsecured overdraft |
| `policy` | `PolicyConfig` | - | Cash manager policy |
| `arrival_config` | `Option<ArrivalConfig>` | None | Auto-generation config |
| `arrival_bands` | `Option<ArrivalBandsConfig>` | None | Per-band generation |
| `posted_collateral` | `Option<i64>` | None | Initial collateral |
| `collateral_haircut` | `Option<f64>` | 0.02 | Haircut discount |
| `limits` | `Option<AgentLimitsConfig>` | None | Bilateral/multilateral |
| `liquidity_pool` | `Option<i64>` | None | External liquidity |
| `liquidity_allocation_fraction` | `Option<f64>` | None | Pool allocation |

**Status:** [ ] Documented

---

### 3. CostRates (Rust)
**Location:** `backend/src/models/cost.rs`

| Field | Type | Default | Purpose |
|-------|------|---------|---------|
| `overdraft_bps_per_tick` | `f64` | - | Overdraft cost (bps/tick) |
| `delay_cost_per_tick_per_cent` | `i64` | - | Queue delay cost |
| `collateral_cost_per_tick_bps` | `f64` | - | Collateral opportunity |
| `eod_penalty_per_transaction` | `i64` | - | EOD penalty (cents) |
| `deadline_penalty` | `i64` | - | Deadline miss penalty |
| `split_friction_cost` | `i64` | - | Split cost (cents) |
| `overdue_delay_multiplier` | `f64` | 5.0 | Overdue cost multiplier |
| `priority_delay_multipliers` | `Option<...>` | None | Per-band delay costs |
| `liquidity_cost_per_tick_bps` | `f64` | - | Liquidity pool cost |

**Status:** [ ] Documented

---

### 4. Transaction (Rust)
**Location:** `backend/src/models/transaction.rs`

**Fields:**
| Field | Type | Purpose |
|-------|------|---------|
| `id` | `String` | UUID identifier |
| `sender_id` | `String` | Sending agent |
| `receiver_id` | `String` | Receiving agent |
| `amount` | `i64` | Original amount (immutable) |
| `remaining_amount` | `i64` | Unsettled portion |
| `arrival_tick` | `usize` | When entered system |
| `deadline_tick` | `usize` | Latest settlement |
| `priority` | `u8` | Internal priority (0-10) |
| `original_priority` | `u8` | Pre-escalation priority |
| `declared_rtgs_priority` | `Option<RtgsPriority>` | Bank's declared level |
| `rtgs_priority` | `Option<RtgsPriority>` | Assigned RTGS priority |
| `rtgs_submission_tick` | `Option<usize>` | RTGS submission time |
| `status` | `TransactionStatus` | Current lifecycle state |
| `parent_id` | `Option<String>` | Parent for splits |
| `is_divisible` | `bool` | Can be split |

**Methods:**
- `new(sender, receiver, amount, arrival_tick, deadline_tick)`
- `new_split(sender, receiver, amount, arrival_tick, deadline_tick, parent_id)`
- `settle(amount, tick)`
- `mark_overdue(tick)`
- `is_past_deadline(tick)`
- `is_settled()`, `is_pending()`, `is_overdue()`
- `set_priority(priority)`
- `set_rtgs_priority(priority, tick)`
- `clear_rtgs_priority()`

**Status:** [ ] Documented

---

### 5. Agent (Rust)
**Location:** `backend/src/models/agent.rs`

**Fields:**
| Field | Type | Purpose |
|-------|------|---------|
| `id` | `String` | Unique identifier |
| `balance` | `i64` | CB settlement account |
| `outgoing_queue` | `Vec<String>` | Queue 1 (internal) |
| `incoming_expected` | `Vec<String>` | Forecasted inflows |
| `last_decision_tick` | `Option<usize>` | Policy evaluation time |
| `liquidity_buffer` | `i64` | Target minimum balance |
| `posted_collateral` | `i64` | Collateral amount |
| `collateral_haircut` | `f64` | Haircut rate |
| `unsecured_cap` | `i64` | Unsecured overdraft limit |
| `collateral_posted_at_tick` | `Option<usize>` | Posting time |
| `release_budget_max` | `Option<i64>` | Budget cap |
| `release_budget_remaining` | `i64` | Budget remaining |
| `release_budget_focus_counterparties` | `Option<Vec<String>>` | Allowed receivers |
| `release_budget_per_counterparty_limit` | `Option<i64>` | Per-counterparty cap |
| `release_budget_per_counterparty_usage` | `HashMap<String, i64>` | Usage tracking |
| `collateral_withdrawal_timers` | `HashMap<usize, Vec<...>>` | Auto-withdraw |
| `state_registers` | `HashMap<String, f64>` | Policy micro-memory |
| `bilateral_limits` | `HashMap<String, i64>` | Per-counterparty limits |
| `multilateral_limit` | `Option<i64>` | Total outflow limit |
| `bilateral_outflows` | `HashMap<String, i64>` | Daily outflow tracking |
| `total_outflow` | `i64` | Daily total outflow |
| `allocated_liquidity` | `i64` | External liquidity |

**Methods:**
- `new(id, balance)`
- `debit(amount)`, `credit(amount)`
- `available_liquidity()`
- `can_pay(amount)`
- `queue_outgoing(tx_id)`
- `remove_from_outgoing(tx_id)`
- `outgoing_queue_size()`
- `collateral_capacity()`

**Status:** [ ] Documented

---

### 6. SimulationState (Rust)
**Location:** `backend/src/models/state.rs`

**Fields:**
| Field | Type | Purpose |
|-------|------|---------|
| `agents` | `BTreeMap<String, Agent>` | All agents |
| `transactions` | `BTreeMap<String, Transaction>` | All transactions |
| `rtgs_queue` | `Vec<String>` | Queue 2 (RTGS) |
| `queue2_index` | `AgentQueueIndex` | Performance index |
| `event_log` | `EventLog` | Event recorder |

**Methods:**
- `get_agent(id)`, `get_agent_mut(id)`
- `get_transaction(id)`
- `add_transaction(tx)`
- `queue_transaction(tx_id)`
- `rtgs_queue()`, `rtgs_queue_mut()`
- `queue_size()`, `queue_value()`
- `total_balance()`
- `rebuild_queue2_index()`

**Status:** [ ] Documented

---

### 7. ArrivalGenerator (Rust)
**Location:** `backend/src/arrivals/mod.rs`

**Fields:**
| Field | Type | Purpose |
|-------|------|---------|
| `configs` | `HashMap<String, ArrivalConfig>` | Current configs |
| `base_configs` | `HashMap<String, ArrivalConfig>` | Original configs |
| `band_configs` | `HashMap<String, ArrivalBandsConfig>` | Per-band configs |
| `all_agent_ids` | `Vec<String>` | All participants |
| `next_tx_id` | `usize` | TX ID counter |
| `episode_end_tick` | `usize` | Deadline cap |

**Methods:**
- `new(configs, all_agent_ids, episode_end_tick)`
- `new_with_bands(band_configs, all_agent_ids, episode_end_tick)`
- `new_mixed(band_configs, legacy_configs, all_agent_ids, episode_end_tick)`
- `generate_for_agent(agent_id, tick, rng)`
- `generate_from_bands(agent_id, tick, rng)`
- `sample_amount(distribution, rng)`
- `sample_priority(distribution, rng)`
- `select_counterparty(sender, weights, rng)`
- `generate_deadline(arrival_tick, range, rng)`
- `set_rate(agent_id, rate)`
- `multiply_all_rates(multiplier)`
- `set_counterparty_weight(agent_id, counterparty, weight)`

**Status:** [ ] Documented

---

### 8. Amount Distributions (Rust)
**Location:** `backend/src/arrivals/mod.rs`

| Type | Parameters | Sampling Method |
|------|------------|-----------------|
| `Uniform` | `min, max` | `rng.range(min, max+1)` |
| `Normal` | `mean, std_dev` | Box-Muller, clipped ≥1 |
| `LogNormal` | `mean, std_dev` | `exp(Z * σ + μ)` |
| `Exponential` | `rate` | `-ln(U) / λ` |

**Status:** [ ] Documented

---

### 9. Priority Distributions (Rust)
**Location:** `backend/src/arrivals/mod.rs`

| Type | Parameters | Sampling Method |
|------|------------|-----------------|
| `Fixed` | `value` | Return constant |
| `Categorical` | `values, weights` | Weighted selection |
| `Uniform` | `min, max` | `rng.range(min, max+1)` |

**Status:** [ ] Documented

---

### 10. Event Types (Rust)
**Location:** `backend/src/models/event.rs`

**Arrival & Submission Events:**
- `Arrival` - Transaction enters system
- `PolicySubmit` - Policy releases to RTGS
- `PolicyHold` - Policy holds in Queue 1
- `PolicyDrop` - Policy drops transaction
- `PolicySplit` - Policy splits transaction
- `RtgsSubmission` - Transaction enters Queue 2

**Priority Events:**
- `TransactionReprioritized` - Priority changed by policy
- `PriorityEscalated` - Dynamic escalation applied

**Settlement Events:**
- `RtgsImmediateSettlement` - Direct RTGS settlement
- `QueuedRtgs` - Added to Queue 2 (insufficient liquidity)
- `RtgsWithdrawal` - Withdrawn from Queue 2
- `RtgsResubmission` - Resubmitted with new priority
- `Queue2LiquidityRelease` - Queued tx released on liquidity

**LSM Events:**
- `LsmBilateralOffset` - A↔B netting
- `LsmCycleSettlement` - Cycle settlement
- `EntryDispositionOffset` - Entry-time bilateral check

**Collateral Events:**
- `CollateralPost` - Collateral deposited
- `CollateralWithdraw` - Collateral withdrawn
- `CollateralTimerWithdrawn` - Auto-withdrawal triggered
- `CollateralTimerBlocked` - Auto-withdrawal blocked

**Cost Events:**
- `CostAccrual` - Per-tick costs recorded
- `TransactionWentOverdue` - Deadline missed
- `OverdueTransactionSettled` - Overdue tx settled

**System Events:**
- `EndOfDay` - Day boundary
- `ScenarioEventExecuted` - Scheduled event fired

**Limit Events:**
- `BilateralLimitExceeded` - Per-counterparty limit hit
- `MultilateralLimitExceeded` - Total outflow limit hit
- `AlgorithmExecution` - Algorithm step recorded

**State Events:**
- `StateRegisterSet` - Policy register updated
- `BankBudgetSet` - Release budget configured

**Status:** [ ] Documented (each event needs full field documentation)

---

### 11. Policy Types (Rust)
**Location:** `backend/src/cash_manager/policies/`

| Policy | Parameters | Description |
|--------|------------|-------------|
| `Fifo` | - | Submit all immediately |
| `Deadline` | `urgency_threshold` | Prioritize approaching deadlines |
| `LiquidityAware` | `target_buffer, urgency_threshold` | Preserve liquidity buffer |
| `LiquiditySplitting` | `max_splits, min_split_amount` | Smart payment splitting |
| `MockSplitting` | `num_splits` | Test: always split N ways |
| `MockStaggerSplit` | `...` | Test: staggered release |
| `FromJson` | `json` | External JSON policy |

**Status:** [ ] Documented

---

### 12. Settlement Functions (Rust)
**Location:** `backend/src/settlement/`

**RTGS Functions:**
- `try_settle()` - Attempt immediate settlement
- `submit_transaction()` - Submit to Queue 2
- `process_queue()` - Retry queued transactions

**LSM Functions:**
- `bilateral_offset()` - A↔B netting
- `detect_cycles()` - Find cycles in queue
- `settle_cycle()` - Settle detected cycle
- `run_lsm_pass()` - Complete LSM pass

**Status:** [ ] Documented

---

### 13. RngManager (Rust)
**Location:** `backend/src/rng/xorshift.rs`

**Methods:**
- `new(seed)` - Create with seed
- `next()` - Generate u64
- `range(min, max)` - Random in [min, max)
- `next_f64()` - Random in [0.0, 1.0)
- `poisson(lambda)` - Poisson sampling
- `get_state()` - Current seed state

**Status:** [ ] Documented

---

### 14. Python Configuration Schemas
**Location:** `api/payment_simulator/config/schemas.py`

**Classes:**
- `SimulationConfig` - Top-level config
- `SimulationSettings` - ticks_per_day, num_days, rng_seed
- `AgentConfig` - Per-agent Python config
- `CostRates` - Python cost rates
- `LsmConfig` - Python LSM config
- `ArrivalConfig` - Python arrival config
- `ArrivalBandsConfig` - Per-band config (11.3)
- `ArrivalBandConfig` - Single band config

**Distribution Classes:**
- `NormalDistribution`
- `LogNormalDistribution`
- `UniformDistribution`
- `ExponentialDistribution`
- `FixedPriorityDistribution`
- `CategoricalPriorityDistribution`
- `UniformPriorityDistribution`

**Policy Classes:**
- `FifoPolicy`
- `DeadlinePolicy`
- `LiquidityAwarePolicy`
- `LiquiditySplittingPolicy`
- `MockSplittingPolicy`
- `FromJsonPolicy`

**Scenario Event Classes:**
- `DirectTransferEvent`
- `CustomTransactionArrivalEvent`
- `CollateralAdjustmentEvent`
- `GlobalArrivalRateChangeEvent`
- `AgentArrivalRateChangeEvent`
- `CounterpartyWeightChangeEvent`
- `DeadlineWindowChangeEvent`

**Key Method:**
- `to_ffi_dict()` - Convert to Rust FFI format

**Status:** [ ] Documented

---

### 15. FFI Bindings
**Location:** `backend/src/lib.rs`, `api/payment_simulator/_core.py`

**Orchestrator Methods (Python-exposed):**
- `new(config_dict)` - Create orchestrator
- `tick()` - Execute one tick
- `current_tick()`, `current_day()`
- `get_agent_ids()`
- `get_agent_balance(agent_id)`
- `get_agent_unsecured_cap(agent_id)`
- `get_agent_queue1_contents(agent_id)`
- `get_rtgs_queue_contents()`
- `get_agent_accumulated_costs(agent_id)`
- `get_transaction_details(tx_id)`
- `get_tick_events(tick)`
- `get_all_events()`
- `get_agent_policies()`
- `get_system_metrics()`
- `submit_transaction(...)`
- `withdraw_from_rtgs(tx_id)`
- `resubmit_to_rtgs(tx_id, priority)`
- `save_state()`, `load_state(json)`
- `simulation_id()`

**Status:** [ ] Documented

---

### 16. CLI Commands
**Location:** `api/payment_simulator/cli/commands/`

**Commands:**
- `run` - Execute simulation
- `replay` - Replay from database
- `checkpoint` - Checkpoint management
- `db` - Database utilities

**Run Options:**
- `--config` - Config file path
- `--ticks` - Override tick count
- `--seed` - Override RNG seed
- `--quiet` - Suppress output
- `--verbose` - Detailed events
- `--stream` - JSONL tick output
- `--event-stream` - JSONL event output
- `--persist` - Save to database
- `--full-replay` - Enable replay capture
- `--db-path` - Database file path
- `--simulation-id` - Custom simulation ID
- `--filter-*` - Event filtering options
- `--cost-chart` - Generate cost charts

**Status:** [ ] Documented

---

### 17. Execution Layer
**Location:** `api/payment_simulator/cli/execution/`

**Classes:**
- `SimulationRunner` - Template Method execution
- `SimulationConfig` - Runner configuration
- `SimulationStats` - Statistics tracking
- `TickResult` - Single tick output
- `PersistenceManager` - Database operations

**Output Strategies:**
- `VerboseModeOutput`
- `NormalModeOutput`
- `StreamModeOutput`
- `EventStreamModeOutput`

**State Providers:**
- `OrchestratorStateProvider` - Live FFI wrapper
- `DatabaseStateProvider` - Replay from DB

**Status:** [ ] Documented

---

## Progress Tracking

| Section | Status | Assigned | Notes |
|---------|--------|----------|-------|
| 01-configuration | [ ] | - | - |
| 02-models | [ ] | - | - |
| 03-generators | [ ] | - | - |
| 04-queues | [ ] | - | - |
| 05-settlement | [ ] | - | - |
| 06-costs | [ ] | - | - |
| 07-events | [ ] | - | - |
| 08-policies | [ ] | - | - |
| 09-time | [ ] | - | - |
| 10-ffi | [ ] | - | - |
| 11-cli | [ ] | - | - |
| index.md | [ ] | - | - |

---

## Documentation Standards

### Field Documentation Template
```markdown
### `field_name`
**Type:** `type`
**Default:** `value` (or "Required")
**Location:** `file_path:line_number`

**Description:**
Brief description of purpose.

**Valid Values:**
- Value constraints
- Range limits

**Usage:**
```rust/python
// Example usage
```

**Related:**
- [Link to related field](#related-field)
```

### Function Documentation Template
```markdown
### `function_name(params)`
**Location:** `file_path:line_number`
**Signature:** `fn function_name(param1: Type1, ...) -> ReturnType`

**Description:**
What this function does.

**Parameters:**
| Name | Type | Description |
|------|------|-------------|
| `param1` | `Type1` | Description |

**Returns:**
Description of return value.

**Example:**
```rust/python
// Example usage
```

**Errors:**
- `ErrorType1` - When this happens
```

### Event Documentation Template
```markdown
### `EventName`
**Location:** `backend/src/models/event.rs:line`

**Description:**
When and why this event is emitted.

**Fields:**
| Field | Type | Description |
|-------|------|-------------|
| `tick` | `usize` | When event occurred |
| `field2` | `Type` | Description |

**Emitted By:**
- `file.rs:function_name()` - Description

**Display Format:**
```
[T=5] EventName: detail1, detail2
```

**Example:**
```json
{
  "event_type": "EventName",
  "tick": 5,
  "field2": "value"
}
```
```

---

## Next Steps

1. Create directory structure
2. Create index.md with navigation
3. Document configuration types first (foundation)
4. Document models (transaction, agent, state)
5. Document generators and distributions
6. Document queues and settlement
7. Document events and costs
8. Document policies
9. Document FFI and CLI
10. Review and cross-reference

---

*Last updated: 2025-11-28*
