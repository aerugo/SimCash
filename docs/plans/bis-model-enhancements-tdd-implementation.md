# BIS AI Cash Management Model Enhancements - TDD Implementation Plan

**Created:** 2025-11-27
**Status:** Planning
**Parent Document:** `../research/bis-simcash-model-comparison.md`

---

## Overview

This document provides **detailed TDD implementation plans** for enhancing SimCash to support the BIS Working Paper 1310 experimental scenarios. Each enhancement is evaluated against existing features, and strict TDD principles are followed.

### Proposed Enhancements

| # | Enhancement | Existing Similar Feature | Status |
|---|-------------|-------------------------|--------|
| 1 | Priority-Based Delay Cost Multipliers | `overdue_delay_multiplier` (different purpose) | **New Feature** |
| 2 | Liquidity Allocation Decision | None | **New Feature** |
| 3 | Probabilistic Policy Reasoning | `incoming_expected_count` (count only) | **Enhancement** |
| 4 | Probabilistic Scenario Events | `EventSchedule::OneTime/Repeating` | **Enhancement** |

---

## Research Summary: Existing Features Analysis

### 1. Priority-Based Delay Costs

**Searched:** `priority.*cost`, `cost.*priority`, `delay_multiplier`, `PriorityEscalationConfig`

**Existing Features Found:**
- `overdue_delay_multiplier` (default 5.0): Applies to ALL transactions once they become overdue, **regardless of priority**. Located in `CostRates` struct in `orchestrator/engine.rs:25-36`.
- `PriorityEscalationConfig`: Dynamically **changes** transaction priority as deadline approaches (not cost multipliers). Used for queue ordering optimization.

**Gap Analysis:**
The BIS model requires different delay costs based on priority (urgent=1.5%, normal=1.0%). Current implementation has a single `delay_cost_per_tick_per_cent` that applies uniformly to all transactions. There is no mapping from priority level to delay cost multiplier.

**Verdict:** ✅ **New Feature Required**

### 2. Liquidity Allocation Decision

**Searched:** `liquidity.*allocat`, `allocat.*liquidity`, `opening_balance`

**Existing Features Found:**
- `opening_balance`: Fixed configuration value per agent, not a decision point
- `collateral_adjustment`: Scenario event for changing credit limits mid-simulation
- No mechanism for agents to choose how much liquidity to allocate from a pool

**Gap Analysis:**
The BIS model has agents decide how much of available liquidity to bring into the payment system (Period 0 decision). SimCash has fixed `opening_balance` per agent with no decision-making component.

**Verdict:** ✅ **New Feature Required**

### 3. Probabilistic Policy Reasoning

**Searched:** `incoming_expected`, `probability`, `probabilistic`

**Existing Features Found:**
- `incoming_expected_count`: Exposed in `EvalContext` (policy context), provides COUNT of expected incoming payments (not value)
- Located in `policy/tree/context.rs:241-243`: `agent.incoming_expected().len() as f64`
- Agent tracks `incoming_expected: Vec<String>` (transaction IDs)

**Gap Analysis:**
The BIS model requires reasoning about expected MONETARY VALUE of inflows (e.g., "there's a 50% chance I'll receive $500"). Current implementation only provides a count of expected incoming transactions, not:
1. Expected total value of inflows
2. Probability distribution of inflows
3. Expected value (probability × amount) for decision-making

**Verdict:** ✅ **Enhancement Required** - Build on existing `incoming_expected` infrastructure

### 4. Probabilistic Scenario Events

**Searched:** `EventSchedule`, `ScenarioEvent`, `probability`

**Existing Features Found:**
- `EventSchedule::OneTime { tick }`: Execute once at specific tick
- `EventSchedule::Repeating { start_tick, interval }`: Execute at regular intervals
- Both are **deterministic** - no randomness in triggering

**Gap Analysis:**
The BIS model includes stochastic payment arrivals (50% chance of receiving a payment). Current scenario events are deterministic (always trigger at scheduled time). Need to add probability field for random triggering.

**Verdict:** ✅ **Enhancement Required** - Add probability field to `EventSchedule`

---

## Critical Invariants (Apply to ALL Phases)

### Money is ALWAYS i64

All monetary values (amounts, costs, balances) MUST be `i64` representing cents. No floats for money.

```rust
// ✅ CORRECT
let priority_multiplier: f64 = 1.5;  // Multiplier can be float
let delay_cost = (base_cost as f64 * priority_multiplier) as i64;  // Final cost is i64

// ❌ WRONG
let delay_cost: f64 = 15.5;  // Never use float for money
```

### Determinism is Sacred

All random operations MUST use seeded RNG and persist the new seed:

```rust
// ✅ CORRECT - For probabilistic events
let (random_value, new_seed) = rng_manager.next_f64(state.rng_seed);
state.rng_seed = new_seed;  // CRITICAL: Always persist new seed
if random_value < event_probability {
    execute_event();
}
```

### Event Persistence Pattern

All new events follow the standard pattern for replay identity:

```rust
// 1. Define in backend/src/models/event.rs
Event::NewEventType { tick, field1, field2, ... }

// 2. Serialize in backend/src/ffi/orchestrator.rs
// 3. Display in api/payment_simulator/cli/execution/display.py
// 4. Test replay identity
```

---

## Enhancement 1: Priority-Based Delay Cost Multipliers

### Purpose
Enable different delay costs for transactions based on their priority level, matching BIS model where urgent payments (priority 8-10) have higher delay costs than normal payments (priority 4-7).

### Design

**Approach A (Configuration-Based):** Add priority→multiplier mapping to `CostRates`

```rust
pub struct CostRates {
    // ... existing fields ...

    /// Priority-based delay cost multipliers
    /// Maps priority bands to multipliers applied to base delay_cost_per_tick_per_cent
    /// Default: None (all priorities use base rate)
    pub priority_delay_multipliers: Option<PriorityDelayMultipliers>,
}

pub struct PriorityDelayMultipliers {
    /// Multiplier for urgent priority (8-10). Default: 1.5
    pub urgent_multiplier: f64,
    /// Multiplier for normal priority (4-7). Default: 1.0
    pub normal_multiplier: f64,
    /// Multiplier for low priority (0-3). Default: 1.0
    pub low_multiplier: f64,
}
```

**Configuration YAML:**
```yaml
cost_rates:
  delay_cost_per_tick_per_cent: 0.01  # Base rate
  priority_delay_multipliers:
    urgent_multiplier: 1.5   # Urgent pays 1.5x
    normal_multiplier: 1.0   # Normal pays base
    low_multiplier: 0.5      # Low pays 0.5x (optional discount)
```

### TDD Test Cases

#### Phase 1.1: Configuration Parsing

**File:** `api/tests/integration/test_priority_delay_costs.py`

```python
# TEST 1: Default behavior unchanged (no multipliers configured)
def test_delay_cost_without_priority_multipliers():
    """Delay cost should use base rate when no multipliers configured."""
    config = create_config(
        cost_rates={"delay_cost_per_tick_per_cent": 0.01}
        # No priority_delay_multipliers
    )
    orch = Orchestrator.new(config)

    # Create urgent and normal priority transactions
    urgent_tx = create_transaction(priority=9, amount=100_000)
    normal_tx = create_transaction(priority=5, amount=100_000)

    # Both should have same delay cost
    urgent_cost = orch.calculate_delay_cost(urgent_tx.id, ticks=10)
    normal_cost = orch.calculate_delay_cost(normal_tx.id, ticks=10)

    assert urgent_cost == normal_cost  # No differentiation

# TEST 2: Priority multipliers applied correctly
def test_delay_cost_with_priority_multipliers():
    """Urgent transactions should have higher delay costs."""
    config = create_config(
        cost_rates={
            "delay_cost_per_tick_per_cent": 0.01,
            "priority_delay_multipliers": {
                "urgent_multiplier": 1.5,
                "normal_multiplier": 1.0,
            }
        }
    )
    orch = Orchestrator.new(config)

    urgent_tx = create_transaction(priority=9, amount=100_000)
    normal_tx = create_transaction(priority=5, amount=100_000)

    urgent_cost = orch.calculate_delay_cost(urgent_tx.id, ticks=10)
    normal_cost = orch.calculate_delay_cost(normal_tx.id, ticks=10)

    # urgent_cost should be 1.5x normal_cost
    assert urgent_cost == int(normal_cost * 1.5)

# TEST 3: Priority band boundaries
def test_priority_band_boundaries():
    """Priority 7 should be normal, priority 8 should be urgent."""
    config = create_config(
        cost_rates={
            "delay_cost_per_tick_per_cent": 0.01,
            "priority_delay_multipliers": {
                "urgent_multiplier": 2.0,
                "normal_multiplier": 1.0,
            }
        }
    )
    orch = Orchestrator.new(config)

    priority_7_tx = create_transaction(priority=7, amount=100_000)
    priority_8_tx = create_transaction(priority=8, amount=100_000)

    cost_7 = orch.calculate_delay_cost(priority_7_tx.id, ticks=10)
    cost_8 = orch.calculate_delay_cost(priority_8_tx.id, ticks=10)

    # Priority 7 (normal band) should cost less than priority 8 (urgent band)
    assert cost_8 == cost_7 * 2
```

#### Phase 1.2: Rust Implementation

**File:** `backend/tests/priority_delay_costs.rs`

```rust
#[test]
fn test_delay_cost_calculation_with_priority_multiplier() {
    let cost_rates = CostRates {
        delay_cost_per_tick_per_cent: 0.01,
        priority_delay_multipliers: Some(PriorityDelayMultipliers {
            urgent_multiplier: 1.5,
            normal_multiplier: 1.0,
            low_multiplier: 0.5,
        }),
        ..Default::default()
    };

    // Test urgent priority (9)
    let urgent_cost = calculate_delay_cost(100_000, 9, 10, &cost_rates);
    // Expected: 100_000 * 0.01 * 10 * 1.5 = 15000 cents
    assert_eq!(urgent_cost, 15000);

    // Test normal priority (5)
    let normal_cost = calculate_delay_cost(100_000, 5, 10, &cost_rates);
    // Expected: 100_000 * 0.01 * 10 * 1.0 = 10000 cents
    assert_eq!(normal_cost, 10000);
}

#[test]
fn test_priority_band_classification() {
    assert_eq!(get_priority_band(10), PriorityBand::Urgent);
    assert_eq!(get_priority_band(9), PriorityBand::Urgent);
    assert_eq!(get_priority_band(8), PriorityBand::Urgent);
    assert_eq!(get_priority_band(7), PriorityBand::Normal);
    assert_eq!(get_priority_band(4), PriorityBand::Normal);
    assert_eq!(get_priority_band(3), PriorityBand::Low);
    assert_eq!(get_priority_band(0), PriorityBand::Low);
}
```

### Implementation Steps

1. **Define Types** (`backend/src/orchestrator/engine.rs`)
   - Add `PriorityDelayMultipliers` struct
   - Add `priority_delay_multipliers: Option<PriorityDelayMultipliers>` to `CostRates`
   - Add `PriorityBand` enum (Urgent, Normal, Low)
   - Add `get_priority_band(priority: u8) -> PriorityBand` function

2. **Update Cost Calculation** (`backend/src/settlement/costs.rs` or appropriate module)
   - Modify delay cost calculation to use priority multiplier
   - Formula: `delay_cost = amount * base_rate * ticks * priority_multiplier`

3. **FFI Parsing** (`backend/src/ffi/types.rs`)
   - Parse `priority_delay_multipliers` from Python dict

4. **Policy Context** (`backend/src/policy/tree/context.rs`)
   - Add `priority_delay_multiplier_for_this_tx` field to EvalContext

5. **Documentation**
   - Update `docs/policy_dsl_guide.md` with new cost fields

---

## Enhancement 2: Liquidity Allocation Decision

### Purpose
Enable agents to decide how much liquidity to allocate to the payment system at the start of each day, matching BIS model Period 0 decision.

### Design

**Approach:** New lifecycle hook + policy evaluation point

```yaml
# Configuration
agent_configs:
  - id: BANK_A
    # Instead of fixed opening_balance, specify pool
    liquidity_pool: 2000000  # Total available liquidity
    liquidity_allocation_policy: "aggressive"  # or use policy DSL
```

**Lifecycle Flow:**
```
Day Start → liquidity_allocation_policy evaluated → opening_balance set → normal tick processing
```

### TDD Test Cases

#### Phase 2.1: Configuration and Setup

**File:** `api/tests/integration/test_liquidity_allocation.py`

```python
# TEST 1: Fixed allocation (backwards compatible)
def test_fixed_liquidity_allocation():
    """When liquidity_pool not specified, use opening_balance directly."""
    config = create_config(
        agent_configs=[
            {"id": "BANK_A", "opening_balance": 1000000}
        ]
    )
    orch = Orchestrator.new(config)

    assert orch.get_agent_balance("BANK_A") == 1000000

# TEST 2: Pool-based allocation with policy
def test_pool_based_liquidity_allocation():
    """Agent should allocate portion of liquidity_pool based on policy."""
    config = create_config(
        agent_configs=[
            {
                "id": "BANK_A",
                "liquidity_pool": 2000000,
                "liquidity_allocation_fraction": 0.5,  # Allocate 50%
            }
        ]
    )
    orch = Orchestrator.new(config)

    # Agent should start with 50% of pool
    assert orch.get_agent_balance("BANK_A") == 1000000

# TEST 3: Policy-based allocation using DSL
def test_policy_based_liquidity_allocation():
    """Allocation should be determined by policy expression."""
    config = create_config(
        agent_configs=[
            {
                "id": "BANK_A",
                "liquidity_pool": 2000000,
                "allocation_policy": {
                    "type": "expression",
                    "expr": "0.3 + 0.4 * system_pressure"  # 30-70% based on pressure
                }
            }
        ]
    )
    orch = Orchestrator.new(config)

    # Low pressure → allocate ~30%
    low_pressure_balance = orch.get_agent_balance("BANK_A")
    assert 500000 <= low_pressure_balance <= 800000

# TEST 4: Multi-day allocation changes
def test_daily_reallocation():
    """Agent should reallocate liquidity at start of each day."""
    config = create_config(
        ticks_per_day=10,
        num_days=3,
        agent_configs=[
            {
                "id": "BANK_A",
                "liquidity_pool": 2000000,
                "liquidity_allocation_fraction": 0.5,
            }
        ]
    )
    orch = Orchestrator.new(config)

    # Day 0
    assert orch.get_agent_balance("BANK_A") == 1000000

    # Advance to day 1 (tick 10)
    for _ in range(10):
        orch.tick()

    # Balance should be reset to allocation
    # (or carried forward - document expected behavior)
```

#### Phase 2.2: Events and Replay

```python
# TEST 5: LiquidityAllocation event generation
def test_liquidity_allocation_event():
    """LiquidityAllocation event should be generated at day start."""
    config = create_config(
        agent_configs=[
            {
                "id": "BANK_A",
                "liquidity_pool": 2000000,
                "liquidity_allocation_fraction": 0.5,
            }
        ]
    )
    orch = Orchestrator.new(config)

    events = orch.get_tick_events(0)
    alloc_events = [e for e in events if e["event_type"] == "LiquidityAllocation"]

    assert len(alloc_events) == 1
    assert alloc_events[0]["agent_id"] == "BANK_A"
    assert alloc_events[0]["liquidity_pool"] == 2000000
    assert alloc_events[0]["allocated_amount"] == 1000000
    assert alloc_events[0]["allocation_fraction"] == 0.5
```

### Implementation Steps

1. **Event Definition** (`backend/src/models/event.rs`)
   ```rust
   Event::LiquidityAllocation {
       tick: usize,
       agent_id: String,
       liquidity_pool: i64,
       allocated_amount: i64,
       allocation_fraction: f64,
       reserved_amount: i64,  // pool - allocated
   }
   ```

2. **Agent Config Extension** (`backend/src/orchestrator/engine.rs`)
   - Add `liquidity_pool: Option<i64>` to `AgentConfig`
   - Add `liquidity_allocation_fraction: Option<f64>` to `AgentConfig`

3. **Day-Start Hook** (`backend/src/orchestrator/engine.rs`)
   - Add `allocate_liquidity()` method called at day start
   - Evaluate allocation policy for each agent
   - Set agent balance and emit event

4. **FFI** (`backend/src/ffi/types.rs`)
   - Parse new config fields
   - Serialize `LiquidityAllocation` event

5. **Display** (`api/payment_simulator/cli/execution/display.py`)
   - Add `log_liquidity_allocation()` function

---

## Enhancement 3: Probabilistic Policy Reasoning

### Purpose
Enable policies to reason about expected monetary value of incoming payments, matching BIS model probabilistic inflow expectations.

### Design

**Build on existing infrastructure:**
- Agent already tracks `incoming_expected: Vec<String>` (transaction IDs)
- Policy context already has `incoming_expected_count`

**New fields to add:**
- `incoming_expected_total_value`: Sum of expected incoming payment amounts
- `incoming_expected_avg_value`: Average value of expected inflows
- `incoming_probability_weight`: Probability weight for expected inflows (configurable)

### TDD Test Cases

#### Phase 3.1: Policy Context Fields

**File:** `api/tests/integration/test_probabilistic_policy.py`

```python
# TEST 1: incoming_expected_total_value calculation
def test_incoming_expected_total_value():
    """Policy context should include total value of expected inflows."""
    config = create_config(
        agent_configs=[
            {"id": "BANK_A", "opening_balance": 1000000},
            {"id": "BANK_B", "opening_balance": 1000000},
        ]
    )
    orch = Orchestrator.new(config)

    # Create pending transactions where BANK_A is receiver
    tx1_id = orch.inject_transaction("BANK_B", "BANK_A", 100000)
    tx2_id = orch.inject_transaction("BANK_B", "BANK_A", 200000)

    # BANK_A should see expected inflows
    context = orch.get_policy_context("BANK_A", tx1_id)

    assert context["incoming_expected_count"] == 2
    assert context["incoming_expected_total_value"] == 300000

# TEST 2: Policy using expected value in decision
def test_policy_uses_expected_inflow_value():
    """Policy can compare expected inflows to payment amount."""
    policy_yaml = """
    queue_tree:
      - if: "incoming_expected_total_value >= amount"
        then: "wait"  # Expect inflows to cover this payment
      - else: "release"
    """

    config = create_config(
        policy=policy_yaml,
        agent_configs=[
            {"id": "BANK_A", "opening_balance": 100000},  # Low balance
            {"id": "BANK_B", "opening_balance": 1000000},
        ]
    )
    orch = Orchestrator.new(config)

    # Create expected inflow larger than pending payment
    orch.inject_transaction("BANK_B", "BANK_A", 500000)  # Expected inflow

    # Create outgoing payment from BANK_A
    tx_id = orch.inject_transaction("BANK_A", "BANK_B", 300000)

    # Policy should decide to wait (expected inflow > payment amount)
    decision = orch.evaluate_policy("BANK_A", tx_id)
    assert decision == "wait"
```

#### Phase 3.2: Rust Implementation Tests

**File:** `backend/tests/policy_expected_inflows.rs`

```rust
#[test]
fn test_incoming_expected_total_value_in_context() {
    // Setup: Agent BANK_A with two expected incoming transactions
    let mut state = SimulationState::new(vec![
        Agent::new("BANK_A".to_string(), 1_000_000),
        Agent::new("BANK_B".to_string(), 1_000_000),
    ]);

    // Create transactions where BANK_A is receiver
    let tx1 = Transaction::new("BANK_B", "BANK_A", 100_000, 0, 50);
    let tx2 = Transaction::new("BANK_B", "BANK_A", 200_000, 0, 50);

    state.add_transaction(tx1.clone());
    state.add_transaction(tx2.clone());

    // Mark as expected by BANK_A
    let agent_a = state.get_agent_mut("BANK_A").unwrap();
    agent_a.add_expected_inflow(tx1.id().to_string());
    agent_a.add_expected_inflow(tx2.id().to_string());

    // Build context
    let tx_out = Transaction::new("BANK_A", "BANK_B", 50_000, 0, 50);
    let agent = state.get_agent("BANK_A").unwrap();
    let context = EvalContext::build(&tx_out, agent, &state, 10, &CostRates::default(), 100, 0.8);

    // Verify new fields
    assert_eq!(context.get_field("incoming_expected_count").unwrap(), 2.0);
    assert_eq!(context.get_field("incoming_expected_total_value").unwrap(), 300_000.0);
    assert_eq!(context.get_field("incoming_expected_avg_value").unwrap(), 150_000.0);
}
```

### Implementation Steps

1. **Policy Context Fields** (`backend/src/policy/tree/context.rs`)
   ```rust
   // In EvalContext::build()
   let mut incoming_total_value = 0i64;
   for tx_id in agent.incoming_expected() {
       if let Some(tx) = state.get_transaction(tx_id) {
           incoming_total_value += tx.remaining_amount();
       }
   }
   fields.insert("incoming_expected_total_value".to_string(), incoming_total_value as f64);

   let count = agent.incoming_expected().len();
   let avg_value = if count > 0 { incoming_total_value / count as i64 } else { 0 };
   fields.insert("incoming_expected_avg_value".to_string(), avg_value as f64);
   ```

2. **Documentation** (`docs/policy_dsl_guide.md`)
   - Document new fields in Agent Queue Fields section

---

## Enhancement 4: Probabilistic Scenario Events

### Purpose
Enable scenario events to trigger with specified probability rather than deterministically, matching BIS model stochastic payment arrivals.

### Design

**Extend EventSchedule:**

```rust
pub enum EventSchedule {
    OneTime { tick: usize },
    Repeating { start_tick: usize, interval: usize },

    // NEW: Probabilistic variants
    ProbabilisticOneTime {
        tick: usize,
        probability: f64,  // 0.0 to 1.0
    },
    ProbabilisticRepeating {
        start_tick: usize,
        interval: usize,
        probability: f64,
    },
}
```

**Configuration YAML:**
```yaml
scenario_events:
  - event:
      type: custom_transaction_arrival
      from_agent: BANK_B
      to_agent: BANK_A
      amount: 500000
    schedule:
      tick: 5
      probability: 0.5  # 50% chance of occurring
```

### TDD Test Cases

#### Phase 4.1: Configuration Parsing

**File:** `api/tests/integration/test_probabilistic_events.py`

```python
# TEST 1: Deterministic events unchanged
def test_deterministic_events_unchanged():
    """Events without probability should always trigger."""
    config = create_config(
        scenario_events=[
            {
                "event": {"type": "direct_transfer", "from_agent": "BANK_A", "to_agent": "BANK_B", "amount": 100000},
                "schedule": {"tick": 5}
            }
        ]
    )

    # Run multiple times - should always trigger
    for _ in range(10):
        orch = Orchestrator.new(config)
        for _ in range(10):
            orch.tick()

        events = orch.get_all_events()
        transfers = [e for e in events if e["event_type"] == "DirectTransfer"]
        assert len(transfers) == 1

# TEST 2: Probabilistic events respect probability
def test_probabilistic_event_respects_probability():
    """Events with probability should trigger approximately that fraction."""
    config_template = lambda seed: create_config(
        seed=seed,
        scenario_events=[
            {
                "event": {"type": "direct_transfer", "from_agent": "BANK_A", "to_agent": "BANK_B", "amount": 100000},
                "schedule": {"tick": 5, "probability": 0.5}
            }
        ]
    )

    # Run 100 times with different seeds
    trigger_count = 0
    for seed in range(100):
        orch = Orchestrator.new(config_template(seed))
        for _ in range(10):
            orch.tick()

        events = orch.get_all_events()
        transfers = [e for e in events if e["event_type"] == "DirectTransfer"]
        if len(transfers) > 0:
            trigger_count += 1

    # Should trigger approximately 50% of the time (with some variance)
    assert 35 <= trigger_count <= 65  # Allow for statistical variance

# TEST 3: Determinism with same seed
def test_probabilistic_event_determinism():
    """Same seed should produce same probabilistic outcome."""
    config = create_config(
        seed=42,
        scenario_events=[
            {
                "event": {"type": "direct_transfer", "from_agent": "BANK_A", "to_agent": "BANK_B", "amount": 100000},
                "schedule": {"tick": 5, "probability": 0.5}
            }
        ]
    )

    results = []
    for _ in range(3):
        orch = Orchestrator.new(config)
        for _ in range(10):
            orch.tick()

        events = orch.get_all_events()
        transfers = [e for e in events if e["event_type"] == "DirectTransfer"]
        results.append(len(transfers))

    # All runs with same seed should have same outcome
    assert results[0] == results[1] == results[2]

# TEST 4: Event records whether it triggered
def test_probabilistic_event_logs_outcome():
    """ScenarioEventEvaluated event should log trigger decision."""
    config = create_config(
        seed=42,
        scenario_events=[
            {
                "event": {"type": "direct_transfer", "from_agent": "BANK_A", "to_agent": "BANK_B", "amount": 100000},
                "schedule": {"tick": 5, "probability": 0.5}
            }
        ]
    )
    orch = Orchestrator.new(config)
    for _ in range(10):
        orch.tick()

    events = orch.get_all_events()
    eval_events = [e for e in events if e["event_type"] == "ScenarioEventEvaluated"]

    assert len(eval_events) == 1
    assert eval_events[0]["tick"] == 5
    assert eval_events[0]["probability"] == 0.5
    assert "triggered" in eval_events[0]  # Boolean
    assert "random_value" in eval_events[0]  # For debugging
```

#### Phase 4.2: Rust Implementation Tests

**File:** `backend/tests/probabilistic_events.rs`

```rust
#[test]
fn test_probabilistic_schedule_parsing() {
    let schedule = EventSchedule::ProbabilisticOneTime {
        tick: 10,
        probability: 0.5,
    };

    assert!(schedule.should_evaluate(10));
    assert!(!schedule.should_evaluate(9));
    assert!(!schedule.should_evaluate(11));
}

#[test]
fn test_probabilistic_event_execution_with_rng() {
    let mut state = create_test_state();
    state.rng_seed = 12345;

    let event = ScheduledEvent {
        event: ScenarioEvent::DirectTransfer {
            from_agent: "A".to_string(),
            to_agent: "B".to_string(),
            amount: 100_000,
        },
        schedule: EventSchedule::ProbabilisticOneTime {
            tick: 5,
            probability: 0.5,
        },
    };

    // Execute and verify RNG consumed
    let (triggered, new_seed) = evaluate_probabilistic_event(&event, state.rng_seed, 5);

    assert_ne!(new_seed, state.rng_seed);  // Seed should change
    // triggered will be true or false based on RNG
}

#[test]
fn test_probabilistic_event_determinism() {
    let seed = 42u64;

    let event = ScheduledEvent {
        event: ScenarioEvent::DirectTransfer {
            from_agent: "A".to_string(),
            to_agent: "B".to_string(),
            amount: 100_000,
        },
        schedule: EventSchedule::ProbabilisticOneTime {
            tick: 5,
            probability: 0.5,
        },
    };

    // Same seed should give same result
    let (result1, _) = evaluate_probabilistic_event(&event, seed, 5);
    let (result2, _) = evaluate_probabilistic_event(&event, seed, 5);

    assert_eq!(result1, result2);
}
```

### Implementation Steps

1. **Extend EventSchedule** (`backend/src/events/types.rs`)
   ```rust
   pub enum EventSchedule {
       OneTime { tick: usize },
       Repeating { start_tick: usize, interval: usize },
       ProbabilisticOneTime { tick: usize, probability: f64 },
       ProbabilisticRepeating { start_tick: usize, interval: usize, probability: f64 },
   }

   impl EventSchedule {
       pub fn is_probabilistic(&self) -> bool { ... }
       pub fn probability(&self) -> Option<f64> { ... }
   }
   ```

2. **New Event Type** (`backend/src/models/event.rs`)
   ```rust
   Event::ScenarioEventEvaluated {
       tick: usize,
       event_type: String,  // "DirectTransfer", etc.
       probability: f64,
       random_value: f64,   // The RNG output
       triggered: bool,
   }
   ```

3. **RNG Integration** (`backend/src/orchestrator/engine.rs`)
   - In event processing loop, consume RNG for probabilistic events
   - Always emit `ScenarioEventEvaluated` event

4. **FFI Parsing** (`backend/src/ffi/types.rs`)
   - Parse `probability` field in schedule

5. **Display** (`api/payment_simulator/cli/execution/display.py`)
   - Add `log_scenario_event_evaluated()` function

---

## Implementation Order

### Recommended Sequence

1. **Enhancement 1: Priority-Based Delay Costs** (2-3 days)
   - Lowest risk, cleanest addition to existing cost system
   - No changes to tick loop or event system
   - Enables BIS Scenario 2 immediately

2. **Enhancement 3: Probabilistic Policy Reasoning** (1-2 days)
   - Builds on existing `incoming_expected` infrastructure
   - Pure addition to EvalContext
   - Enables better agent decision-making

3. **Enhancement 4: Probabilistic Scenario Events** (2-3 days)
   - Requires careful RNG handling
   - Enables BIS Scenario 3 immediately
   - Foundation for more complex stochastic scenarios

4. **Enhancement 2: Liquidity Allocation Decision** (3-4 days)
   - Most complex, touches tick lifecycle
   - Enables BIS Scenario 1 fully
   - Could be simplified to fixed allocation first

### Dependencies

```
Enhancement 1 ─────────────────────────────────► BIS Scenario 2

Enhancement 3 ─────┬───────────────────────────► Better Policies
                   │
Enhancement 4 ─────┴───────────────────────────► BIS Scenario 3

Enhancement 2 ─────────────────────────────────► BIS Scenario 1
```

### Testing Strategy

For each enhancement:
1. Write Python integration tests first (TDD)
2. Write Rust unit tests
3. Implement minimal code to pass tests
4. Verify replay identity
5. Document new fields/events

---

## Success Criteria

### Per Enhancement

- [ ] All TDD tests pass
- [ ] Existing tests unchanged/passing
- [ ] New events serialize correctly via FFI
- [ ] Replay identity maintained (run == replay output)
- [ ] Documentation updated (policy_dsl_guide.md, config examples)

### Overall

- [ ] BIS Scenario 1 runnable with liquidity allocation
- [ ] BIS Scenario 2 runnable with priority delay costs
- [ ] BIS Scenario 3 runnable with probabilistic events
- [ ] Monte Carlo analysis possible (deterministic with different seeds)

---

## Appendix: BIS Scenario Configuration Templates

### Scenario 1: Precautionary Liquidity Allocation

```yaml
# bis-scenario-1.yaml
ticks_per_day: 2
num_days: 1
seed: 12345

cost_rates:
  delay_cost_per_tick_per_cent: 0.01
  # liquidity_cost handled via opening balance allocation

agent_configs:
  - id: BANK_A
    liquidity_pool: 2000000
    liquidity_allocation_fraction: 0.5  # Agent decides this
    credit_limit: 0
  - id: BANK_B
    liquidity_pool: 2000000
    liquidity_allocation_fraction: 0.5
    credit_limit: 0

scenario_events:
  - event:
      type: custom_transaction_arrival
      from_agent: BANK_A
      to_agent: BANK_B
      amount: 500000
      priority: 5
    schedule:
      tick: 0
```

### Scenario 2: Priority-Based Delay Costs

```yaml
# bis-scenario-2.yaml
ticks_per_day: 2
num_days: 1
seed: 12345

cost_rates:
  delay_cost_per_tick_per_cent: 0.01
  priority_delay_multipliers:
    urgent_multiplier: 1.5
    normal_multiplier: 1.0

agent_configs:
  - id: BANK_A
    opening_balance: 1000000
    credit_limit: 0
  - id: BANK_B
    opening_balance: 1000000
    credit_limit: 0

scenario_events:
  - event:
      type: custom_transaction_arrival
      from_agent: BANK_A
      to_agent: BANK_B
      amount: 500000
      priority: 9  # Urgent
    schedule:
      tick: 0
  - event:
      type: custom_transaction_arrival
      from_agent: BANK_A
      to_agent: BANK_B
      amount: 500000
      priority: 5  # Normal
    schedule:
      tick: 0
```

### Scenario 3: Probabilistic Payment Arrival

```yaml
# bis-scenario-3.yaml
ticks_per_day: 2
num_days: 1
seed: 12345

cost_rates:
  delay_cost_per_tick_per_cent: 0.01

agent_configs:
  - id: BANK_A
    opening_balance: 500000
    credit_limit: 0
  - id: BANK_B
    opening_balance: 500000
    credit_limit: 0

scenario_events:
  # Outgoing payment (deterministic)
  - event:
      type: custom_transaction_arrival
      from_agent: BANK_A
      to_agent: BANK_B
      amount: 500000
    schedule:
      tick: 0

  # Expected incoming payment (probabilistic)
  - event:
      type: custom_transaction_arrival
      from_agent: BANK_B
      to_agent: BANK_A
      amount: 500000
    schedule:
      tick: 1
      probability: 0.5  # 50% chance
```

---

*Last updated: 2025-11-27*
