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

## Enhancement 2: Liquidity Pool and Allocation

### Purpose

Enable agents to allocate liquidity from an external pool into the payment system, distinct from collateral-based credit. This models the BIS Period 0 decision where agents choose how much actual cash to bring into the settlement system.

### Conceptual Distinction: Liquidity vs Collateral

| Aspect | Liquidity Allocation | Collateral Posting |
|--------|---------------------|-------------------|
| **Source** | External liquidity pool | Pledged assets |
| **Provides** | Positive cash balance | Credit capacity (overdraft) |
| **Balance effect** | `balance += allocated` | `credit_limit += posted * (1-haircut)` |
| **Policy tree** | `liquidity_allocation_tree` (new) | `strategic_collateral_tree` |
| **Timing** | Day start (Step 0) | Step 1.5 (before settlements) |
| **Cost field** | `liquidity_cost_per_tick_bps` | `collateral_cost_per_tick_bps` |

### Design

**New Configuration Fields:**

```yaml
agent_configs:
  - id: BANK_A
    # Traditional (unchanged)
    opening_balance: 500000           # Initial balance (still supported)

    # New: Liquidity Pool
    liquidity_pool: 2000000           # Total available external liquidity
    liquidity_allocation_fraction: 0.5 # Fixed fraction to allocate (simple mode)

    # OR: Policy-driven allocation
    liquidity_allocation_tree: {...}   # Policy tree for dynamic allocation

cost_rates:
  liquidity_cost_per_tick_bps: 15     # Opportunity cost of allocated liquidity
```

**Lifecycle Flow:**

```
┌─────────────────────────────────────────────────────────────────────┐
│                         DAY START (Tick 0)                          │
├─────────────────────────────────────────────────────────────────────┤
│ Step 0: Liquidity Allocation                                        │
│   For each agent with liquidity_pool:                               │
│     1. Evaluate liquidity_allocation_tree (or use fixed fraction)   │
│     2. Calculate: allocated = pool × fraction                       │
│     3. Set: agent.balance += allocated                              │
│     4. Emit: LiquidityAllocation event                              │
├─────────────────────────────────────────────────────────────────────┤
│ Step 1.5: Strategic Collateral (existing)                           │
│ Step 1.75: Bank Tree (existing)                                     │
│ Step 2: Payment Processing (existing)                               │
│ ...                                                                 │
└─────────────────────────────────────────────────────────────────────┘
```

**Interaction with Opening Balance:**

- If both `opening_balance` and `liquidity_pool` specified: `balance = opening_balance + allocated`
- If only `liquidity_pool` specified: `balance = allocated`
- If only `opening_balance` specified: `balance = opening_balance` (backwards compatible)

---

### TDD Test Cases - Comprehensive Coverage

#### Category 1: Configuration Parsing and Validation

**File:** `api/tests/integration/test_liquidity_allocation_config.py`

```python
"""
Configuration parsing and validation tests for liquidity pool feature.
Tests FFI boundary, validation rules, and backwards compatibility.
"""

import pytest
from payment_simulator.backends.rust import Orchestrator


class TestLiquidityPoolConfigParsing:
    """Tests for parsing liquidity_pool configuration from Python to Rust."""

    def test_parse_liquidity_pool_basic(self):
        """Liquidity pool value should be parsed correctly."""
        config = {
            "ticks_per_day": 10,
            "agent_configs": [
                {"id": "BANK_A", "liquidity_pool": 2_000_000}
            ]
        }
        orch = Orchestrator.new(config)

        # Verify pool was parsed (via new FFI method)
        assert orch.get_agent_liquidity_pool("BANK_A") == 2_000_000

    def test_parse_liquidity_allocation_fraction(self):
        """Allocation fraction should be parsed correctly."""
        config = {
            "ticks_per_day": 10,
            "agent_configs": [
                {
                    "id": "BANK_A",
                    "liquidity_pool": 2_000_000,
                    "liquidity_allocation_fraction": 0.75
                }
            ]
        }
        orch = Orchestrator.new(config)

        assert orch.get_agent_liquidity_allocation_fraction("BANK_A") == 0.75

    def test_parse_liquidity_pool_as_integer_cents(self):
        """Liquidity pool must be integer cents (i64), not float."""
        config = {
            "ticks_per_day": 10,
            "agent_configs": [
                {"id": "BANK_A", "liquidity_pool": 1_500_000}  # $15,000.00
            ]
        }
        orch = Orchestrator.new(config)

        # Should be exact integer, no float conversion
        pool = orch.get_agent_liquidity_pool("BANK_A")
        assert pool == 1_500_000
        assert isinstance(pool, int)


class TestLiquidityPoolValidation:
    """Tests for validation rules on liquidity pool configuration."""

    def test_reject_negative_liquidity_pool(self):
        """Negative liquidity pool should be rejected."""
        config = {
            "ticks_per_day": 10,
            "agent_configs": [
                {"id": "BANK_A", "liquidity_pool": -1_000_000}
            ]
        }

        with pytest.raises(ValueError, match="liquidity_pool.*negative"):
            Orchestrator.new(config)

    def test_reject_allocation_fraction_below_zero(self):
        """Allocation fraction < 0 should be rejected."""
        config = {
            "ticks_per_day": 10,
            "agent_configs": [
                {
                    "id": "BANK_A",
                    "liquidity_pool": 2_000_000,
                    "liquidity_allocation_fraction": -0.1
                }
            ]
        }

        with pytest.raises(ValueError, match="allocation_fraction.*0"):
            Orchestrator.new(config)

    def test_reject_allocation_fraction_above_one(self):
        """Allocation fraction > 1.0 should be rejected."""
        config = {
            "ticks_per_day": 10,
            "agent_configs": [
                {
                    "id": "BANK_A",
                    "liquidity_pool": 2_000_000,
                    "liquidity_allocation_fraction": 1.5
                }
            ]
        }

        with pytest.raises(ValueError, match="allocation_fraction.*1"):
            Orchestrator.new(config)

    def test_allow_allocation_fraction_exactly_zero(self):
        """Allocation fraction of exactly 0 should be valid (allocate nothing)."""
        config = {
            "ticks_per_day": 10,
            "agent_configs": [
                {
                    "id": "BANK_A",
                    "liquidity_pool": 2_000_000,
                    "liquidity_allocation_fraction": 0.0
                }
            ]
        }
        orch = Orchestrator.new(config)

        assert orch.get_agent_balance("BANK_A") == 0

    def test_allow_allocation_fraction_exactly_one(self):
        """Allocation fraction of exactly 1.0 should be valid (allocate all)."""
        config = {
            "ticks_per_day": 10,
            "agent_configs": [
                {
                    "id": "BANK_A",
                    "liquidity_pool": 2_000_000,
                    "liquidity_allocation_fraction": 1.0
                }
            ]
        }
        orch = Orchestrator.new(config)

        assert orch.get_agent_balance("BANK_A") == 2_000_000

    def test_liquidity_pool_zero_is_valid(self):
        """Liquidity pool of 0 should be valid (no external liquidity)."""
        config = {
            "ticks_per_day": 10,
            "agent_configs": [
                {
                    "id": "BANK_A",
                    "liquidity_pool": 0,
                    "liquidity_allocation_fraction": 0.5
                }
            ]
        }
        orch = Orchestrator.new(config)

        assert orch.get_agent_balance("BANK_A") == 0

    def test_default_allocation_fraction_when_pool_specified(self):
        """When liquidity_pool specified without fraction, default to 1.0."""
        config = {
            "ticks_per_day": 10,
            "agent_configs": [
                {"id": "BANK_A", "liquidity_pool": 1_000_000}
                # No liquidity_allocation_fraction specified
            ]
        }
        orch = Orchestrator.new(config)

        # Should allocate full pool by default
        assert orch.get_agent_balance("BANK_A") == 1_000_000


class TestBackwardsCompatibility:
    """Tests ensuring existing configurations continue to work."""

    def test_opening_balance_only_unchanged(self):
        """Config with only opening_balance should work as before."""
        config = {
            "ticks_per_day": 10,
            "agent_configs": [
                {"id": "BANK_A", "opening_balance": 1_000_000}
            ]
        }
        orch = Orchestrator.new(config)

        assert orch.get_agent_balance("BANK_A") == 1_000_000
        assert orch.get_agent_liquidity_pool("BANK_A") is None

    def test_opening_balance_with_zero_pool(self):
        """Opening balance with explicit zero pool should use opening_balance."""
        config = {
            "ticks_per_day": 10,
            "agent_configs": [
                {
                    "id": "BANK_A",
                    "opening_balance": 500_000,
                    "liquidity_pool": 0
                }
            ]
        }
        orch = Orchestrator.new(config)

        # Should have opening_balance only (no allocation from empty pool)
        assert orch.get_agent_balance("BANK_A") == 500_000

    def test_opening_balance_plus_liquidity_pool(self):
        """Both opening_balance and liquidity_pool should be additive."""
        config = {
            "ticks_per_day": 10,
            "agent_configs": [
                {
                    "id": "BANK_A",
                    "opening_balance": 500_000,      # Base balance
                    "liquidity_pool": 1_000_000,    # Additional pool
                    "liquidity_allocation_fraction": 0.5  # Allocate 50% of pool
                }
            ]
        }
        orch = Orchestrator.new(config)

        # balance = opening_balance + (pool * fraction)
        # balance = 500,000 + (1,000,000 * 0.5) = 1,000,000
        assert orch.get_agent_balance("BANK_A") == 1_000_000

    def test_existing_simulations_unaffected(self):
        """Existing config files without liquidity_pool should work unchanged."""
        # This is a typical existing config
        config = {
            "ticks_per_day": 100,
            "num_days": 1,
            "seed": 42,
            "agent_configs": [
                {"id": "BANK_A", "opening_balance": 1_000_000, "credit_limit": 500_000},
                {"id": "BANK_B", "opening_balance": 800_000, "credit_limit": 400_000},
            ],
            "cost_rates": {
                "delay_cost_per_tick_per_cent": 0.001,
                "overdraft_bps_per_tick": 5,
            }
        }
        orch = Orchestrator.new(config)

        assert orch.get_agent_balance("BANK_A") == 1_000_000
        assert orch.get_agent_balance("BANK_B") == 800_000
```

#### Category 2: Basic Allocation Mechanics

**File:** `api/tests/integration/test_liquidity_allocation_basic.py`

```python
"""
Basic liquidity allocation mechanics tests.
Tests the core allocation logic and balance calculations.
"""

import pytest
from payment_simulator.backends.rust import Orchestrator


class TestBasicAllocation:
    """Tests for basic allocation from liquidity pool to balance."""

    def test_full_pool_allocation(self):
        """Allocating 100% of pool should set balance to pool amount."""
        config = {
            "ticks_per_day": 10,
            "agent_configs": [
                {
                    "id": "BANK_A",
                    "liquidity_pool": 2_000_000,
                    "liquidity_allocation_fraction": 1.0
                }
            ]
        }
        orch = Orchestrator.new(config)

        assert orch.get_agent_balance("BANK_A") == 2_000_000

    def test_half_pool_allocation(self):
        """Allocating 50% of pool should set balance to half pool amount."""
        config = {
            "ticks_per_day": 10,
            "agent_configs": [
                {
                    "id": "BANK_A",
                    "liquidity_pool": 2_000_000,
                    "liquidity_allocation_fraction": 0.5
                }
            ]
        }
        orch = Orchestrator.new(config)

        assert orch.get_agent_balance("BANK_A") == 1_000_000

    def test_zero_allocation(self):
        """Allocating 0% should leave balance at zero (or opening_balance)."""
        config = {
            "ticks_per_day": 10,
            "agent_configs": [
                {
                    "id": "BANK_A",
                    "liquidity_pool": 2_000_000,
                    "liquidity_allocation_fraction": 0.0
                }
            ]
        }
        orch = Orchestrator.new(config)

        assert orch.get_agent_balance("BANK_A") == 0

    def test_fractional_allocation_rounds_down(self):
        """Fractional cents should round down (floor) to maintain i64."""
        config = {
            "ticks_per_day": 10,
            "agent_configs": [
                {
                    "id": "BANK_A",
                    "liquidity_pool": 1_000_001,  # Odd number
                    "liquidity_allocation_fraction": 0.5
                }
            ]
        }
        orch = Orchestrator.new(config)

        # 1,000,001 * 0.5 = 500,000.5 → should floor to 500,000
        assert orch.get_agent_balance("BANK_A") == 500_000

    def test_very_small_fraction_allocation(self):
        """Very small fraction should allocate small amount."""
        config = {
            "ticks_per_day": 10,
            "agent_configs": [
                {
                    "id": "BANK_A",
                    "liquidity_pool": 10_000_000,  # $100,000
                    "liquidity_allocation_fraction": 0.001  # 0.1%
                }
            ]
        }
        orch = Orchestrator.new(config)

        # 10,000,000 * 0.001 = 10,000 cents = $100
        assert orch.get_agent_balance("BANK_A") == 10_000

    def test_allocation_across_multiple_agents(self):
        """Each agent should have independent allocation."""
        config = {
            "ticks_per_day": 10,
            "agent_configs": [
                {
                    "id": "BANK_A",
                    "liquidity_pool": 2_000_000,
                    "liquidity_allocation_fraction": 0.8
                },
                {
                    "id": "BANK_B",
                    "liquidity_pool": 1_000_000,
                    "liquidity_allocation_fraction": 0.5
                },
                {
                    "id": "BANK_C",
                    "opening_balance": 500_000  # Traditional config
                }
            ]
        }
        orch = Orchestrator.new(config)

        assert orch.get_agent_balance("BANK_A") == 1_600_000  # 2M * 0.8
        assert orch.get_agent_balance("BANK_B") == 500_000   # 1M * 0.5
        assert orch.get_agent_balance("BANK_C") == 500_000   # Direct balance


class TestReservedLiquidity:
    """Tests for tracking unallocated (reserved) liquidity."""

    def test_reserved_liquidity_calculated(self):
        """Reserved = pool - allocated."""
        config = {
            "ticks_per_day": 10,
            "agent_configs": [
                {
                    "id": "BANK_A",
                    "liquidity_pool": 2_000_000,
                    "liquidity_allocation_fraction": 0.6
                }
            ]
        }
        orch = Orchestrator.new(config)

        # Allocated: 2M * 0.6 = 1.2M
        # Reserved: 2M - 1.2M = 0.8M
        assert orch.get_agent_reserved_liquidity("BANK_A") == 800_000

    def test_reserved_liquidity_zero_when_full_allocation(self):
        """Reserved should be 0 when allocating 100%."""
        config = {
            "ticks_per_day": 10,
            "agent_configs": [
                {
                    "id": "BANK_A",
                    "liquidity_pool": 2_000_000,
                    "liquidity_allocation_fraction": 1.0
                }
            ]
        }
        orch = Orchestrator.new(config)

        assert orch.get_agent_reserved_liquidity("BANK_A") == 0

    def test_reserved_liquidity_full_when_zero_allocation(self):
        """Reserved should equal pool when allocating 0%."""
        config = {
            "ticks_per_day": 10,
            "agent_configs": [
                {
                    "id": "BANK_A",
                    "liquidity_pool": 2_000_000,
                    "liquidity_allocation_fraction": 0.0
                }
            ]
        }
        orch = Orchestrator.new(config)

        assert orch.get_agent_reserved_liquidity("BANK_A") == 2_000_000

    def test_reserved_liquidity_none_without_pool(self):
        """Reserved liquidity should be None when no pool configured."""
        config = {
            "ticks_per_day": 10,
            "agent_configs": [
                {"id": "BANK_A", "opening_balance": 1_000_000}
            ]
        }
        orch = Orchestrator.new(config)

        assert orch.get_agent_reserved_liquidity("BANK_A") is None


class TestLiquidityCostCalculation:
    """Tests for opportunity cost of allocated liquidity."""

    def test_liquidity_cost_on_allocated_amount(self):
        """Cost should be calculated on allocated amount only."""
        config = {
            "ticks_per_day": 10,
            "agent_configs": [
                {
                    "id": "BANK_A",
                    "liquidity_pool": 2_000_000,
                    "liquidity_allocation_fraction": 0.5
                }
            ],
            "cost_rates": {
                "liquidity_cost_per_tick_bps": 10  # 0.1% per tick
            }
        }
        orch = Orchestrator.new(config)

        # Run one tick
        orch.tick()

        # Cost = allocated * rate = 1,000,000 * 0.001 = 1,000 cents
        metrics = orch.get_metrics()
        assert metrics["total_liquidity_cost"] == 1_000

    def test_liquidity_cost_accumulates_over_ticks(self):
        """Cost should accumulate each tick."""
        config = {
            "ticks_per_day": 10,
            "agent_configs": [
                {
                    "id": "BANK_A",
                    "liquidity_pool": 1_000_000,
                    "liquidity_allocation_fraction": 1.0
                }
            ],
            "cost_rates": {
                "liquidity_cost_per_tick_bps": 10
            }
        }
        orch = Orchestrator.new(config)

        # Run 5 ticks
        for _ in range(5):
            orch.tick()

        # Cost = 1,000,000 * 0.001 * 5 = 5,000 cents
        metrics = orch.get_metrics()
        assert metrics["total_liquidity_cost"] == 5_000

    def test_no_liquidity_cost_when_no_pool(self):
        """No liquidity cost when using traditional opening_balance."""
        config = {
            "ticks_per_day": 10,
            "agent_configs": [
                {"id": "BANK_A", "opening_balance": 1_000_000}
            ],
            "cost_rates": {
                "liquidity_cost_per_tick_bps": 10
            }
        }
        orch = Orchestrator.new(config)

        for _ in range(5):
            orch.tick()

        metrics = orch.get_metrics()
        assert metrics.get("total_liquidity_cost", 0) == 0

    def test_liquidity_cost_separate_from_collateral_cost(self):
        """Liquidity cost and collateral cost should be tracked separately."""
        config = {
            "ticks_per_day": 10,
            "agent_configs": [
                {
                    "id": "BANK_A",
                    "liquidity_pool": 1_000_000,
                    "liquidity_allocation_fraction": 1.0,
                    "max_collateral_capacity": 500_000
                }
            ],
            "cost_rates": {
                "liquidity_cost_per_tick_bps": 10,
                "collateral_cost_per_tick_bps": 20
            }
        }
        orch = Orchestrator.new(config)

        # Post some collateral
        orch.post_collateral("BANK_A", 200_000)

        for _ in range(5):
            orch.tick()

        metrics = orch.get_metrics()
        # Liquidity cost: 1,000,000 * 0.001 * 5 = 5,000
        # Collateral cost: 200,000 * 0.002 * 5 = 2,000
        assert metrics["total_liquidity_cost"] == 5_000
        assert metrics["total_collateral_cost"] == 2_000
```

#### Category 3: Multi-Day Behavior

**File:** `api/tests/integration/test_liquidity_allocation_multiday.py`

```python
"""
Multi-day liquidity allocation tests.
Tests reallocation at day boundaries and balance carryover behavior.
"""

import pytest
from payment_simulator.backends.rust import Orchestrator


class TestDailyReallocation:
    """Tests for liquidity reallocation at day boundaries."""

    def test_reallocation_at_day_start(self):
        """Liquidity should be reallocated at start of each day."""
        config = {
            "ticks_per_day": 5,
            "num_days": 3,
            "agent_configs": [
                {
                    "id": "BANK_A",
                    "liquidity_pool": 2_000_000,
                    "liquidity_allocation_fraction": 0.5
                }
            ]
        }
        orch = Orchestrator.new(config)

        # Day 0: Should have initial allocation
        assert orch.get_agent_balance("BANK_A") == 1_000_000

        # Simulate spending during day 0
        # (would need transaction to actually change balance)

        # Advance to Day 1 (tick 5)
        for _ in range(5):
            orch.tick()

        # Day 1: Should have fresh allocation
        # Note: behavior depends on design - reset or additive?
        # This test assumes RESET behavior (BIS model style)
        day1_balance = orch.get_agent_balance("BANK_A")
        assert day1_balance == 1_000_000  # Reset to allocation

    def test_allocation_event_each_day(self):
        """LiquidityAllocation event should be emitted at start of each day."""
        config = {
            "ticks_per_day": 3,
            "num_days": 3,
            "agent_configs": [
                {
                    "id": "BANK_A",
                    "liquidity_pool": 1_000_000,
                    "liquidity_allocation_fraction": 0.5
                }
            ]
        }
        orch = Orchestrator.new(config)

        # Run full simulation
        for _ in range(9):  # 3 days * 3 ticks
            orch.tick()

        all_events = orch.get_all_events()
        alloc_events = [e for e in all_events if e["event_type"] == "LiquidityAllocation"]

        # Should have allocation event at tick 0, 3, 6 (start of each day)
        assert len(alloc_events) == 3
        assert alloc_events[0]["tick"] == 0
        assert alloc_events[1]["tick"] == 3
        assert alloc_events[2]["tick"] == 6

    def test_end_of_day_balance_before_reallocation(self):
        """Balance at end of day should reflect activity before reallocation."""
        config = {
            "ticks_per_day": 3,
            "num_days": 2,
            "agent_configs": [
                {
                    "id": "BANK_A",
                    "liquidity_pool": 1_000_000,
                    "liquidity_allocation_fraction": 1.0
                },
                {
                    "id": "BANK_B",
                    "liquidity_pool": 1_000_000,
                    "liquidity_allocation_fraction": 1.0
                }
            ],
            "scenario_events": [
                {
                    "event": {
                        "type": "custom_transaction_arrival",
                        "from_agent": "BANK_A",
                        "to_agent": "BANK_B",
                        "amount": 300_000
                    },
                    "schedule": {"tick": 0}
                }
            ]
        }
        orch = Orchestrator.new(config)

        # Run through day 0
        for _ in range(3):
            orch.tick()

        # At end of day 0, after transaction:
        # BANK_A: 1,000,000 - 300,000 = 700,000
        # BANK_B: 1,000,000 + 300,000 = 1,300,000

        # But at start of day 1, should reset:
        # BANK_A: 1,000,000 (fresh allocation)
        # BANK_B: 1,000,000 (fresh allocation)

        assert orch.get_agent_balance("BANK_A") == 1_000_000
        assert orch.get_agent_balance("BANK_B") == 1_000_000


class TestCarryoverBehavior:
    """Tests for different balance carryover modes."""

    def test_reset_mode_clears_balance(self):
        """In reset mode, balance returns to pool for reallocation."""
        config = {
            "ticks_per_day": 3,
            "num_days": 2,
            "liquidity_carryover_mode": "reset",  # Explicit reset
            "agent_configs": [
                {
                    "id": "BANK_A",
                    "liquidity_pool": 1_000_000,
                    "liquidity_allocation_fraction": 0.5
                }
            ]
        }
        orch = Orchestrator.new(config)

        # Run day 0
        for _ in range(3):
            orch.tick()

        # Day 1 should start fresh
        assert orch.get_agent_balance("BANK_A") == 500_000

    def test_accumulate_mode_adds_to_balance(self):
        """In accumulate mode, allocation adds to existing balance."""
        config = {
            "ticks_per_day": 3,
            "num_days": 2,
            "liquidity_carryover_mode": "accumulate",
            "agent_configs": [
                {
                    "id": "BANK_A",
                    "liquidity_pool": 1_000_000,
                    "liquidity_allocation_fraction": 0.5
                }
            ]
        }
        orch = Orchestrator.new(config)

        # Day 0: balance = 500,000
        assert orch.get_agent_balance("BANK_A") == 500_000

        # Run day 0
        for _ in range(3):
            orch.tick()

        # Day 1: balance = 500,000 (carryover) + 500,000 (new allocation)
        assert orch.get_agent_balance("BANK_A") == 1_000_000
```

#### Category 4: Event Generation and Replay Identity

**File:** `api/tests/integration/test_liquidity_allocation_events.py`

```python
"""
Event generation and replay identity tests for liquidity allocation.
Ensures events contain all required fields for replay.
"""

import pytest
from payment_simulator.backends.rust import Orchestrator


class TestLiquidityAllocationEvent:
    """Tests for LiquidityAllocation event structure and content."""

    def test_event_contains_all_required_fields(self):
        """LiquidityAllocation event must have all fields for replay."""
        config = {
            "ticks_per_day": 10,
            "agent_configs": [
                {
                    "id": "BANK_A",
                    "liquidity_pool": 2_000_000,
                    "liquidity_allocation_fraction": 0.6
                }
            ]
        }
        orch = Orchestrator.new(config)

        events = orch.get_tick_events(0)
        alloc_events = [e for e in events if e["event_type"] == "LiquidityAllocation"]

        assert len(alloc_events) == 1
        event = alloc_events[0]

        # All required fields for replay
        assert event["event_type"] == "LiquidityAllocation"
        assert event["tick"] == 0
        assert event["agent_id"] == "BANK_A"
        assert event["liquidity_pool"] == 2_000_000
        assert event["allocated_amount"] == 1_200_000
        assert event["allocation_fraction"] == 0.6
        assert event["reserved_amount"] == 800_000
        assert event["balance_before"] == 0
        assert event["balance_after"] == 1_200_000

    def test_event_for_each_agent_with_pool(self):
        """Each agent with liquidity_pool should have an event."""
        config = {
            "ticks_per_day": 10,
            "agent_configs": [
                {
                    "id": "BANK_A",
                    "liquidity_pool": 2_000_000,
                    "liquidity_allocation_fraction": 0.5
                },
                {
                    "id": "BANK_B",
                    "liquidity_pool": 1_000_000,
                    "liquidity_allocation_fraction": 0.8
                },
                {
                    "id": "BANK_C",
                    "opening_balance": 500_000  # No pool - no event
                }
            ]
        }
        orch = Orchestrator.new(config)

        events = orch.get_tick_events(0)
        alloc_events = [e for e in events if e["event_type"] == "LiquidityAllocation"]

        # Only BANK_A and BANK_B have pools
        assert len(alloc_events) == 2
        agent_ids = {e["agent_id"] for e in alloc_events}
        assert agent_ids == {"BANK_A", "BANK_B"}

    def test_no_event_when_no_pool(self):
        """No LiquidityAllocation event for agents without liquidity_pool."""
        config = {
            "ticks_per_day": 10,
            "agent_configs": [
                {"id": "BANK_A", "opening_balance": 1_000_000}
            ]
        }
        orch = Orchestrator.new(config)

        events = orch.get_tick_events(0)
        alloc_events = [e for e in events if e["event_type"] == "LiquidityAllocation"]

        assert len(alloc_events) == 0


class TestReplayIdentity:
    """Tests ensuring replay produces identical output."""

    def test_replay_matches_run_output(self, tmp_path):
        """Replay of persisted simulation should match original run."""
        db_path = tmp_path / "sim.db"

        config = {
            "ticks_per_day": 5,
            "num_days": 2,
            "seed": 42,
            "agent_configs": [
                {
                    "id": "BANK_A",
                    "liquidity_pool": 1_000_000,
                    "liquidity_allocation_fraction": 0.7
                },
                {
                    "id": "BANK_B",
                    "liquidity_pool": 800_000,
                    "liquidity_allocation_fraction": 0.5
                }
            ]
        }

        # Run and persist
        orch = Orchestrator.new(config)
        run_events = []
        for _ in range(10):
            orch.tick()
            run_events.extend(orch.get_tick_events(orch.current_tick() - 1))

        # Persist to database
        orch.persist(str(db_path))

        # Replay from database
        from payment_simulator.cli.commands.replay import replay_simulation
        replay_events = replay_simulation(str(db_path))

        # Filter to allocation events
        run_alloc = [e for e in run_events if e["event_type"] == "LiquidityAllocation"]
        replay_alloc = [e for e in replay_events if e["event_type"] == "LiquidityAllocation"]

        assert len(run_alloc) == len(replay_alloc)
        for run_e, replay_e in zip(run_alloc, replay_alloc):
            assert run_e == replay_e

    def test_allocation_events_deterministic_across_runs(self):
        """Same config should produce identical allocation events."""
        config = {
            "ticks_per_day": 5,
            "seed": 12345,
            "agent_configs": [
                {
                    "id": "BANK_A",
                    "liquidity_pool": 1_000_000,
                    "liquidity_allocation_fraction": 0.6
                }
            ]
        }

        # Run 1
        orch1 = Orchestrator.new(config)
        events1 = orch1.get_tick_events(0)

        # Run 2
        orch2 = Orchestrator.new(config)
        events2 = orch2.get_tick_events(0)

        alloc1 = [e for e in events1 if e["event_type"] == "LiquidityAllocation"]
        alloc2 = [e for e in events2 if e["event_type"] == "LiquidityAllocation"]

        assert alloc1 == alloc2
```

#### Category 5: Policy Context Integration

**File:** `api/tests/integration/test_liquidity_allocation_policy.py`

```python
"""
Policy context integration tests for liquidity allocation.
Tests that policies can access and use liquidity pool information.
"""

import pytest
from payment_simulator.backends.rust import Orchestrator


class TestPolicyContextFields:
    """Tests for liquidity-related fields in policy evaluation context."""

    def test_liquidity_pool_in_context(self):
        """Policy context should include liquidity_pool field."""
        config = {
            "ticks_per_day": 10,
            "agent_configs": [
                {
                    "id": "BANK_A",
                    "liquidity_pool": 2_000_000,
                    "liquidity_allocation_fraction": 0.5
                },
                {"id": "BANK_B", "opening_balance": 1_000_000}
            ],
            "scenario_events": [
                {
                    "event": {
                        "type": "custom_transaction_arrival",
                        "from_agent": "BANK_A",
                        "to_agent": "BANK_B",
                        "amount": 100_000
                    },
                    "schedule": {"tick": 0}
                }
            ]
        }
        orch = Orchestrator.new(config)
        orch.tick()

        # Get policy context for BANK_A
        tx_id = orch.get_agent_queue("BANK_A")[0]
        context = orch.get_policy_context("BANK_A", tx_id)

        assert context["liquidity_pool"] == 2_000_000

    def test_allocated_liquidity_in_context(self):
        """Policy context should include allocated_liquidity field."""
        config = {
            "ticks_per_day": 10,
            "agent_configs": [
                {
                    "id": "BANK_A",
                    "liquidity_pool": 2_000_000,
                    "liquidity_allocation_fraction": 0.6
                },
                {"id": "BANK_B", "opening_balance": 1_000_000}
            ],
            "scenario_events": [
                {
                    "event": {
                        "type": "custom_transaction_arrival",
                        "from_agent": "BANK_A",
                        "to_agent": "BANK_B",
                        "amount": 100_000
                    },
                    "schedule": {"tick": 0}
                }
            ]
        }
        orch = Orchestrator.new(config)
        orch.tick()

        tx_id = orch.get_agent_queue("BANK_A")[0]
        context = orch.get_policy_context("BANK_A", tx_id)

        assert context["allocated_liquidity"] == 1_200_000

    def test_reserved_liquidity_in_context(self):
        """Policy context should include reserved_liquidity field."""
        config = {
            "ticks_per_day": 10,
            "agent_configs": [
                {
                    "id": "BANK_A",
                    "liquidity_pool": 2_000_000,
                    "liquidity_allocation_fraction": 0.7
                },
                {"id": "BANK_B", "opening_balance": 1_000_000}
            ],
            "scenario_events": [
                {
                    "event": {
                        "type": "custom_transaction_arrival",
                        "from_agent": "BANK_A",
                        "to_agent": "BANK_B",
                        "amount": 100_000
                    },
                    "schedule": {"tick": 0}
                }
            ]
        }
        orch = Orchestrator.new(config)
        orch.tick()

        tx_id = orch.get_agent_queue("BANK_A")[0]
        context = orch.get_policy_context("BANK_A", tx_id)

        # Reserved = 2,000,000 - 1,400,000 = 600,000
        assert context["reserved_liquidity"] == 600_000

    def test_allocation_fraction_in_context(self):
        """Policy context should include allocation_fraction field."""
        config = {
            "ticks_per_day": 10,
            "agent_configs": [
                {
                    "id": "BANK_A",
                    "liquidity_pool": 1_000_000,
                    "liquidity_allocation_fraction": 0.65
                },
                {"id": "BANK_B", "opening_balance": 500_000}
            ],
            "scenario_events": [
                {
                    "event": {
                        "type": "custom_transaction_arrival",
                        "from_agent": "BANK_A",
                        "to_agent": "BANK_B",
                        "amount": 100_000
                    },
                    "schedule": {"tick": 0}
                }
            ]
        }
        orch = Orchestrator.new(config)
        orch.tick()

        tx_id = orch.get_agent_queue("BANK_A")[0]
        context = orch.get_policy_context("BANK_A", tx_id)

        assert context["allocation_fraction"] == 0.65

    def test_context_fields_zero_when_no_pool(self):
        """Liquidity fields should be 0/None when no pool configured."""
        config = {
            "ticks_per_day": 10,
            "agent_configs": [
                {"id": "BANK_A", "opening_balance": 1_000_000},
                {"id": "BANK_B", "opening_balance": 500_000}
            ],
            "scenario_events": [
                {
                    "event": {
                        "type": "custom_transaction_arrival",
                        "from_agent": "BANK_A",
                        "to_agent": "BANK_B",
                        "amount": 100_000
                    },
                    "schedule": {"tick": 0}
                }
            ]
        }
        orch = Orchestrator.new(config)
        orch.tick()

        tx_id = orch.get_agent_queue("BANK_A")[0]
        context = orch.get_policy_context("BANK_A", tx_id)

        assert context["liquidity_pool"] == 0
        assert context["allocated_liquidity"] == 0
        assert context["reserved_liquidity"] == 0


class TestPolicyDecisionsWithLiquidity:
    """Tests for policies using liquidity information in decisions."""

    def test_policy_can_compare_amount_to_reserved(self):
        """Policy should be able to compare transaction amount to reserved liquidity."""
        policy_json = """
        {
            "payment_tree": {
                "type": "condition",
                "condition": {
                    "op": "<=",
                    "left": "amount",
                    "right": "reserved_liquidity"
                },
                "on_true": {"type": "action", "action": "Hold"},
                "on_false": {"type": "action", "action": "Release"}
            }
        }
        """

        config = {
            "ticks_per_day": 10,
            "agent_configs": [
                {
                    "id": "BANK_A",
                    "liquidity_pool": 1_000_000,
                    "liquidity_allocation_fraction": 0.5,
                    "policy": policy_json
                },
                {"id": "BANK_B", "opening_balance": 1_000_000}
            ],
            "scenario_events": [
                {
                    "event": {
                        "type": "custom_transaction_arrival",
                        "from_agent": "BANK_A",
                        "to_agent": "BANK_B",
                        "amount": 400_000  # Less than reserved (500,000)
                    },
                    "schedule": {"tick": 0}
                }
            ]
        }
        orch = Orchestrator.new(config)
        orch.tick()

        # Transaction amount (400K) <= reserved (500K) → Hold
        # Check that transaction is still in queue (not released)
        queue = orch.get_agent_queue("BANK_A")
        assert len(queue) == 1  # Transaction held

    def test_policy_liquidity_utilization_ratio(self):
        """Policy can calculate liquidity utilization ratio."""
        policy_json = """
        {
            "payment_tree": {
                "type": "condition",
                "condition": {
                    "op": ">",
                    "left": {
                        "op": "/",
                        "left": "allocated_liquidity",
                        "right": "liquidity_pool"
                    },
                    "right": 0.8
                },
                "on_true": {"type": "action", "action": "Hold"},
                "on_false": {"type": "action", "action": "Release"}
            }
        }
        """

        config = {
            "ticks_per_day": 10,
            "agent_configs": [
                {
                    "id": "BANK_A",
                    "liquidity_pool": 1_000_000,
                    "liquidity_allocation_fraction": 0.9,  # 90% > 80%
                    "policy": policy_json
                },
                {"id": "BANK_B", "opening_balance": 1_000_000}
            ],
            "scenario_events": [
                {
                    "event": {
                        "type": "custom_transaction_arrival",
                        "from_agent": "BANK_A",
                        "to_agent": "BANK_B",
                        "amount": 100_000
                    },
                    "schedule": {"tick": 0}
                }
            ]
        }
        orch = Orchestrator.new(config)
        orch.tick()

        # Utilization (0.9) > threshold (0.8) → Hold
        queue = orch.get_agent_queue("BANK_A")
        assert len(queue) == 1
```

#### Category 6: Edge Cases and Error Handling

**File:** `api/tests/integration/test_liquidity_allocation_edge_cases.py`

```python
"""
Edge case and error handling tests for liquidity allocation.
"""

import pytest
from payment_simulator.backends.rust import Orchestrator


class TestEdgeCases:
    """Tests for edge cases in liquidity allocation."""

    def test_very_large_liquidity_pool(self):
        """Should handle very large liquidity pool values."""
        config = {
            "ticks_per_day": 10,
            "agent_configs": [
                {
                    "id": "BANK_A",
                    "liquidity_pool": 9_000_000_000_000_000,  # $90 trillion (i64 max is ~9.2e18)
                    "liquidity_allocation_fraction": 0.5
                }
            ]
        }
        orch = Orchestrator.new(config)

        expected = 4_500_000_000_000_000
        assert orch.get_agent_balance("BANK_A") == expected

    def test_very_small_allocation_fraction(self):
        """Should handle very small allocation fractions."""
        config = {
            "ticks_per_day": 10,
            "agent_configs": [
                {
                    "id": "BANK_A",
                    "liquidity_pool": 1_000_000_000,  # $10M
                    "liquidity_allocation_fraction": 0.000001  # 0.0001%
                }
            ]
        }
        orch = Orchestrator.new(config)

        # 1,000,000,000 * 0.000001 = 1,000 cents = $10
        assert orch.get_agent_balance("BANK_A") == 1_000

    def test_allocation_rounds_to_zero_for_tiny_pool(self):
        """Very small pool with small fraction may round to zero."""
        config = {
            "ticks_per_day": 10,
            "agent_configs": [
                {
                    "id": "BANK_A",
                    "liquidity_pool": 10,  # 10 cents
                    "liquidity_allocation_fraction": 0.05  # 5%
                }
            ]
        }
        orch = Orchestrator.new(config)

        # 10 * 0.05 = 0.5 → floors to 0
        assert orch.get_agent_balance("BANK_A") == 0

    def test_single_cent_allocation(self):
        """Should correctly allocate a single cent."""
        config = {
            "ticks_per_day": 10,
            "agent_configs": [
                {
                    "id": "BANK_A",
                    "liquidity_pool": 100,
                    "liquidity_allocation_fraction": 0.01
                }
            ]
        }
        orch = Orchestrator.new(config)

        # 100 * 0.01 = 1 cent
        assert orch.get_agent_balance("BANK_A") == 1

    def test_many_agents_with_different_pools(self):
        """Should handle many agents with varied configurations."""
        config = {
            "ticks_per_day": 10,
            "agent_configs": [
                {"id": f"BANK_{i}", "liquidity_pool": (i + 1) * 100_000, "liquidity_allocation_fraction": 0.1 * (i + 1)}
                for i in range(10)
            ]
        }
        orch = Orchestrator.new(config)

        for i in range(10):
            pool = (i + 1) * 100_000
            fraction = 0.1 * (i + 1)
            expected = int(pool * fraction)
            assert orch.get_agent_balance(f"BANK_{i}") == expected


class TestInteractionWithOtherFeatures:
    """Tests for interaction between liquidity pool and other features."""

    def test_liquidity_pool_with_credit_limit(self):
        """Liquidity pool and credit limit should be independent."""
        config = {
            "ticks_per_day": 10,
            "agent_configs": [
                {
                    "id": "BANK_A",
                    "liquidity_pool": 1_000_000,
                    "liquidity_allocation_fraction": 0.5,
                    "credit_limit": 500_000
                }
            ]
        }
        orch = Orchestrator.new(config)

        # Balance from allocation
        assert orch.get_agent_balance("BANK_A") == 500_000

        # Credit limit unchanged
        assert orch.get_agent_credit_limit("BANK_A") == 500_000

        # Available liquidity = balance + credit_limit
        assert orch.get_agent_available_liquidity("BANK_A") == 1_000_000

    def test_liquidity_pool_with_collateral(self):
        """Liquidity pool and collateral should work together."""
        config = {
            "ticks_per_day": 10,
            "agent_configs": [
                {
                    "id": "BANK_A",
                    "liquidity_pool": 1_000_000,
                    "liquidity_allocation_fraction": 0.5,
                    "max_collateral_capacity": 500_000
                }
            ]
        }
        orch = Orchestrator.new(config)

        # Initial balance from allocation
        assert orch.get_agent_balance("BANK_A") == 500_000

        # Can still post collateral
        orch.post_collateral("BANK_A", 200_000)
        assert orch.get_agent_posted_collateral("BANK_A") == 200_000

    def test_liquidity_with_scenario_events(self):
        """Scenario events should work correctly with liquidity pool."""
        config = {
            "ticks_per_day": 10,
            "agent_configs": [
                {
                    "id": "BANK_A",
                    "liquidity_pool": 1_000_000,
                    "liquidity_allocation_fraction": 1.0
                },
                {"id": "BANK_B", "opening_balance": 1_000_000}
            ],
            "scenario_events": [
                {
                    "event": {
                        "type": "direct_transfer",
                        "from_agent": "BANK_A",
                        "to_agent": "BANK_B",
                        "amount": 200_000
                    },
                    "schedule": {"tick": 1}
                }
            ]
        }
        orch = Orchestrator.new(config)

        # Tick 0: allocation
        assert orch.get_agent_balance("BANK_A") == 1_000_000

        # Tick 1: direct transfer
        orch.tick()
        orch.tick()

        assert orch.get_agent_balance("BANK_A") == 800_000
        assert orch.get_agent_balance("BANK_B") == 1_200_000
```

---

### Rust Unit Tests

**File:** `backend/tests/liquidity_allocation.rs`

```rust
//! Unit tests for liquidity pool and allocation feature.

use payment_simulator_core_rs::orchestrator::{AgentConfig, OrchestratorConfig};
use payment_simulator_core_rs::models::Agent;

mod config_parsing {
    use super::*;

    #[test]
    fn test_parse_liquidity_pool() {
        let config = AgentConfig {
            id: "BANK_A".to_string(),
            liquidity_pool: Some(2_000_000),
            liquidity_allocation_fraction: Some(0.5),
            ..Default::default()
        };

        assert_eq!(config.liquidity_pool, Some(2_000_000));
        assert_eq!(config.liquidity_allocation_fraction, Some(0.5));
    }

    #[test]
    fn test_default_allocation_fraction_is_one() {
        let config = AgentConfig {
            id: "BANK_A".to_string(),
            liquidity_pool: Some(1_000_000),
            liquidity_allocation_fraction: None,
            ..Default::default()
        };

        assert_eq!(config.effective_allocation_fraction(), 1.0);
    }
}

mod allocation_calculation {
    use super::*;

    #[test]
    fn test_calculate_allocated_amount() {
        let pool = 2_000_000i64;
        let fraction = 0.6f64;

        let allocated = calculate_allocation(pool, fraction);

        assert_eq!(allocated, 1_200_000);
    }

    #[test]
    fn test_calculate_allocation_rounds_down() {
        let pool = 1_000_001i64;
        let fraction = 0.5f64;

        let allocated = calculate_allocation(pool, fraction);

        // 1,000,001 * 0.5 = 500,000.5 → floor to 500,000
        assert_eq!(allocated, 500_000);
    }

    #[test]
    fn test_calculate_reserved_amount() {
        let pool = 2_000_000i64;
        let allocated = 1_200_000i64;

        let reserved = pool - allocated;

        assert_eq!(reserved, 800_000);
    }

    fn calculate_allocation(pool: i64, fraction: f64) -> i64 {
        ((pool as f64) * fraction).floor() as i64
    }
}

mod validation {
    use super::*;

    #[test]
    fn test_reject_negative_pool() {
        let result = validate_liquidity_pool(-1_000_000);
        assert!(result.is_err());
    }

    #[test]
    fn test_reject_fraction_below_zero() {
        let result = validate_allocation_fraction(-0.1);
        assert!(result.is_err());
    }

    #[test]
    fn test_reject_fraction_above_one() {
        let result = validate_allocation_fraction(1.5);
        assert!(result.is_err());
    }

    #[test]
    fn test_accept_fraction_exactly_zero() {
        let result = validate_allocation_fraction(0.0);
        assert!(result.is_ok());
    }

    #[test]
    fn test_accept_fraction_exactly_one() {
        let result = validate_allocation_fraction(1.0);
        assert!(result.is_ok());
    }

    fn validate_liquidity_pool(pool: i64) -> Result<(), String> {
        if pool < 0 {
            Err("liquidity_pool cannot be negative".to_string())
        } else {
            Ok(())
        }
    }

    fn validate_allocation_fraction(fraction: f64) -> Result<(), String> {
        if fraction < 0.0 || fraction > 1.0 {
            Err("allocation_fraction must be between 0 and 1".to_string())
        } else {
            Ok(())
        }
    }
}

mod event_generation {
    use super::*;
    use payment_simulator_core_rs::models::Event;

    #[test]
    fn test_liquidity_allocation_event_fields() {
        let event = Event::LiquidityAllocation {
            tick: 0,
            agent_id: "BANK_A".to_string(),
            liquidity_pool: 2_000_000,
            allocated_amount: 1_200_000,
            allocation_fraction: 0.6,
            reserved_amount: 800_000,
            balance_before: 0,
            balance_after: 1_200_000,
        };

        match event {
            Event::LiquidityAllocation {
                tick,
                agent_id,
                liquidity_pool,
                allocated_amount,
                allocation_fraction,
                reserved_amount,
                balance_before,
                balance_after,
            } => {
                assert_eq!(tick, 0);
                assert_eq!(agent_id, "BANK_A");
                assert_eq!(liquidity_pool, 2_000_000);
                assert_eq!(allocated_amount, 1_200_000);
                assert!((allocation_fraction - 0.6).abs() < f64::EPSILON);
                assert_eq!(reserved_amount, 800_000);
                assert_eq!(balance_before, 0);
                assert_eq!(balance_after, 1_200_000);
            }
            _ => panic!("Wrong event type"),
        }
    }
}

mod policy_context {
    use super::*;

    #[test]
    fn test_liquidity_fields_in_context() {
        let mut agent = Agent::new("BANK_A".to_string(), 1_200_000);
        agent.set_liquidity_pool(2_000_000);
        agent.set_allocated_liquidity(1_200_000);

        assert_eq!(agent.liquidity_pool(), Some(2_000_000));
        assert_eq!(agent.allocated_liquidity(), Some(1_200_000));
        assert_eq!(agent.reserved_liquidity(), Some(800_000));
    }

    #[test]
    fn test_liquidity_fields_none_without_pool() {
        let agent = Agent::new("BANK_A".to_string(), 1_000_000);

        assert_eq!(agent.liquidity_pool(), None);
        assert_eq!(agent.allocated_liquidity(), None);
        assert_eq!(agent.reserved_liquidity(), None);
    }
}
```

---

### Implementation Steps

#### Step 1: Define Types and Validation

**File:** `backend/src/orchestrator/engine.rs`

```rust
/// Liquidity pool configuration for an agent
#[derive(Debug, Clone, Default)]
pub struct LiquidityPoolConfig {
    /// Total external liquidity available to the agent
    pub pool: i64,
    /// Fraction of pool to allocate (0.0 to 1.0)
    pub allocation_fraction: f64,
}

impl LiquidityPoolConfig {
    pub fn validate(&self) -> Result<(), ConfigError> {
        if self.pool < 0 {
            return Err(ConfigError::InvalidValue(
                "liquidity_pool cannot be negative".to_string()
            ));
        }
        if self.allocation_fraction < 0.0 || self.allocation_fraction > 1.0 {
            return Err(ConfigError::InvalidValue(
                "liquidity_allocation_fraction must be between 0 and 1".to_string()
            ));
        }
        Ok(())
    }

    pub fn calculate_allocation(&self) -> i64 {
        ((self.pool as f64) * self.allocation_fraction).floor() as i64
    }

    pub fn calculate_reserved(&self) -> i64 {
        self.pool - self.calculate_allocation()
    }
}
```

#### Step 2: Extend Agent Model

**File:** `backend/src/models/agent.rs`

Add fields:
```rust
pub struct Agent {
    // ... existing fields ...

    /// External liquidity pool (None if not configured)
    liquidity_pool: Option<i64>,
    /// Amount allocated from pool to balance
    allocated_liquidity: Option<i64>,
}
```

#### Step 3: Define Event

**File:** `backend/src/models/event.rs`

```rust
Event::LiquidityAllocation {
    tick: usize,
    agent_id: String,
    liquidity_pool: i64,
    allocated_amount: i64,
    allocation_fraction: f64,
    reserved_amount: i64,
    balance_before: i64,
    balance_after: i64,
}
```

#### Step 4: Implement Day-Start Allocation

**File:** `backend/src/orchestrator/engine.rs`

Add new step at tick 0 (and start of each day):
```rust
fn allocate_liquidity_at_day_start(&mut self) -> Vec<Event> {
    let mut events = Vec::new();

    for agent_id in self.agent_ids() {
        if let Some(pool_config) = self.get_liquidity_pool_config(&agent_id) {
            let balance_before = self.get_agent_balance(&agent_id);
            let allocated = pool_config.calculate_allocation();
            let reserved = pool_config.calculate_reserved();

            // Update agent balance
            self.set_agent_balance(&agent_id, balance_before + allocated);

            // Record allocation
            self.set_agent_allocated_liquidity(&agent_id, allocated);

            events.push(Event::LiquidityAllocation {
                tick: self.current_tick,
                agent_id: agent_id.clone(),
                liquidity_pool: pool_config.pool,
                allocated_amount: allocated,
                allocation_fraction: pool_config.allocation_fraction,
                reserved_amount: reserved,
                balance_before,
                balance_after: balance_before + allocated,
            });
        }
    }

    events
}
```

#### Step 5: FFI Serialization

**File:** `backend/src/ffi/types.rs`

Parse config and serialize event.

#### Step 6: Policy Context Fields

**File:** `backend/src/policy/tree/context.rs`

```rust
// In EvalContext::build()
fields.insert("liquidity_pool".to_string(),
    agent.liquidity_pool().unwrap_or(0) as f64);
fields.insert("allocated_liquidity".to_string(),
    agent.allocated_liquidity().unwrap_or(0) as f64);
fields.insert("reserved_liquidity".to_string(),
    agent.reserved_liquidity().unwrap_or(0) as f64);
fields.insert("allocation_fraction".to_string(),
    agent.allocation_fraction().unwrap_or(0.0));
```

#### Step 7: Display Function

**File:** `api/payment_simulator/cli/execution/display.py`

```python
def log_liquidity_allocation(event: dict):
    """Display LiquidityAllocation event."""
    console.print(f"[blue]💰 Liquidity Allocation:[/blue] {event['agent_id']}")
    console.print(f"  Pool: ${event['liquidity_pool']/100:,.2f}")
    console.print(f"  Allocated: ${event['allocated_amount']/100:,.2f} ({event['allocation_fraction']*100:.1f}%)")
    console.print(f"  Reserved: ${event['reserved_amount']/100:,.2f}")
    console.print(f"  Balance: ${event['balance_before']/100:,.2f} → ${event['balance_after']/100:,.2f}")
```

#### Step 8: Documentation

Update `docs/policy_dsl_guide.md` with new fields:
- `liquidity_pool`
- `allocated_liquidity`
- `reserved_liquidity`
- `allocation_fraction`

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
