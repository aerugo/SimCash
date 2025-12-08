# BIS AI Cash Management Model Enhancements - TDD Implementation Plan

**Created:** 2025-11-27
**Status:** Planning
**Parent Document:** `bis-simcash-research-briefing.md`

---

## Overview

This document provides **detailed TDD implementation plans** for enhancing SimCash to support the BIS Working Paper 1310 experimental scenarios. Each enhancement is evaluated against existing features, and strict TDD principles are followed.

### Proposed Enhancements

| # | Enhancement | Existing Similar Feature | Status |
|---|-------------|-------------------------|--------|
| 1 | Priority-Based Delay Cost Multipliers | `overdue_delay_multiplier` (different purpose) | **New Feature** |
| 2 | Liquidity Pool and Allocation | None | **New Feature** |
| 3 | Per-Band Arrival Functions | Single `arrival_config` with `priority_distribution` | **Enhancement** |

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

### 3. Per-Band Arrival Functions

**Searched:** `arrival_config`, `priority_distribution`, `ArrivalConfig`

**Existing Features Found:**
- `ArrivalConfig`: Per-agent arrival configuration with single `rate_per_tick`
- `priority_distribution`: Assigns priority to generated arrivals, but all arrivals share the same `amount_distribution`
- `counterparty_weights`: Controls receiver selection

**Current Configuration:**
```yaml
arrival_config:
  rate_per_tick: 5.0              # Total arrival rate
  amount_distribution:            # Same for ALL priorities
    type: log_normal
    mean: 50000
  priority_distribution:          # Assigns priority per arrival
    type: discrete
    values:
      - value: 10  # Urgent
        weight: 0.1
      - value: 5   # Normal
        weight: 0.9
```

**Gap Analysis:**
The BIS model implies urgent payments are rare AND large, while normal payments are common AND smaller. Current SimCash can make urgent payments rare (via `priority_distribution` weights) but cannot give them different amount distributions. Real-world payment systems have distinct characteristics per urgency band:
- **Urgent/critical** (CLS, margin calls): Rare but large
- **Normal**: Common, varied sizes
- **Low priority** (batch): Numerous, small

**Verdict:** ✅ **Enhancement Required** - Add per-band arrival configurations

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
// ✅ CORRECT - Seeded RNG with persisted seed
let (random_value, new_seed) = rng_manager.next_f64(state.rng_seed);
state.rng_seed = new_seed;  // CRITICAL: Always persist new seed
```

### Event Persistence Pattern

All new events follow the standard pattern for replay identity:

```rust
// 1. Define in simulator/src/models/event.rs
Event::NewEventType { tick, field1, field2, ... }

// 2. Serialize in simulator/src/ffi/orchestrator.rs
// 3. Display in api/payment_simulator/cli/execution/display.py
// 4. Test replay identity
```

---

## TDD Implementation Procedure

This section defines the strict TDD workflow for implementing all enhancements. Every feature MUST follow this procedure to ensure correctness, maintainability, and comprehensive coverage.

### Core Principles

#### 1. Red-Green-Refactor Cycle

Every implementation follows the strict Red-Green-Refactor cycle:

```
┌──────────────────────────────────────────────────────────────────┐
│                        TDD CYCLE                                  │
├──────────────────────────────────────────────────────────────────┤
│                                                                   │
│   ┌─────────┐                                                     │
│   │  RED    │  Write a failing test FIRST                         │
│   │         │  - Test must fail for the RIGHT reason              │
│   │         │  - Test must be specific and focused                │
│   └────┬────┘                                                     │
│        │                                                          │
│        ▼                                                          │
│   ┌─────────┐                                                     │
│   │  GREEN  │  Write MINIMAL code to make test pass               │
│   │         │  - No extra features                                │
│   │         │  - No "while I'm here" additions                    │
│   └────┬────┘                                                     │
│        │                                                          │
│        ▼                                                          │
│   ┌─────────┐                                                     │
│   │REFACTOR │  Clean up while keeping tests green                 │
│   │         │  - Improve names, reduce duplication                │
│   │         │  - Run ALL tests after refactoring                  │
│   └────┬────┘                                                     │
│        │                                                          │
│        └──────────────────────► Repeat                            │
│                                                                   │
└──────────────────────────────────────────────────────────────────┘
```

**Rules:**
- NEVER write implementation code before the test
- NEVER write more than one failing test at a time
- NEVER commit with failing tests
- ALWAYS run the full test suite after each Green phase

#### 2. Test-First Workflow

For each feature increment:

```bash
# Step 1: Write failing test
cd api
.venv/bin/python -m pytest tests/integration/test_new_feature.py::test_specific_case -v
# Expected: FAIL (test not found or assertion fails)

# Step 2: Implement MINIMAL code
cd ../simulator
# Edit Rust code...
cargo test --no-default-features  # Rust unit tests

# Step 3: Rebuild and verify
cd ../api
uv sync --extra dev --reinstall-package payment-simulator
.venv/bin/python -m pytest tests/integration/test_new_feature.py::test_specific_case -v
# Expected: PASS

# Step 4: Run full suite
.venv/bin/python -m pytest
# Expected: ALL PASS
```

### Test Categories and Coverage Requirements

Each enhancement MUST have tests in ALL of the following categories:

#### Category 1: Configuration Parsing Tests

**Purpose:** Verify that configuration is correctly parsed and validated.

**Location:** `api/tests/integration/test_<feature>_config.py`

**Required Scenarios:**

| Scenario | Description | Example |
|----------|-------------|---------|
| Valid minimal | Simplest valid config | Only required fields |
| Valid complete | All fields specified | All optional fields included |
| Valid defaults | Defaults applied correctly | Omit optional fields, verify defaults |
| Invalid type | Wrong type for field | String where int expected |
| Invalid range | Out-of-bounds value | Negative amount, priority > 10 |
| Invalid structure | Malformed structure | Missing required nested field |
| Backwards compatible | Old config still works | Config without new fields |

```python
# Example test structure
class TestFeatureConfigParsing:
    def test_valid_minimal_config(self):
        """Feature works with only required fields."""

    def test_valid_complete_config(self):
        """Feature works with all fields specified."""

    def test_defaults_applied_when_omitted(self):
        """Default values are correctly applied."""

    def test_invalid_type_raises_error(self):
        """Appropriate error for wrong type."""

    def test_invalid_range_raises_error(self):
        """Appropriate error for out-of-range values."""

    def test_backwards_compatible_with_old_config(self):
        """Existing configs without new fields still work."""
```

#### Category 2: Core Logic Tests (Rust)

**Purpose:** Verify the core algorithm/logic is correct.

**Location:** `simulator/tests/<feature>_tests.rs`

**Required Scenarios:**

| Scenario | Description | Example |
|----------|-------------|---------|
| Happy path | Normal successful operation | Standard calculation |
| Boundary values | Edge of valid ranges | Priority 0, 7, 8, 10 |
| Zero values | Zero amounts/rates | Amount = 0, rate = 0 |
| Maximum values | Large but valid values | i64::MAX / 1000 |
| Precision | Integer arithmetic correctness | No floating point errors |
| Determinism | Same seed = same result | Run 10x with same seed |

```rust
// Example test structure
#[cfg(test)]
mod feature_tests {
    #[test]
    fn test_happy_path_calculation() { }

    #[test]
    fn test_boundary_value_low() { }

    #[test]
    fn test_boundary_value_high() { }

    #[test]
    fn test_zero_amount_handled() { }

    #[test]
    fn test_large_values_no_overflow() { }

    #[test]
    fn test_integer_precision_maintained() { }

    #[test]
    fn test_determinism_with_seed() { }
}
```

#### Category 3: Integration Tests (Python)

**Purpose:** Verify end-to-end behavior through FFI.

**Location:** `api/tests/integration/test_<feature>.py`

**Required Scenarios:**

| Scenario | Description | Example |
|----------|-------------|---------|
| Single tick | Feature works in isolation | One transaction, one tick |
| Multi-tick | Feature works over time | 100 ticks, accumulating effects |
| Multi-agent | Feature works with many agents | 5+ agents interacting |
| High volume | Feature handles load | 1000+ transactions |
| Combined features | Interacts with existing features | LSM + new feature together |
| Policy integration | Works with policy trees | Policy references new fields |

```python
# Example test structure
class TestFeatureIntegration:
    def test_single_tick_behavior(self):
        """Feature operates correctly in one tick."""

    def test_multi_tick_accumulation(self):
        """Feature effects accumulate correctly over time."""

    def test_multi_agent_interaction(self):
        """Feature works correctly with multiple agents."""

    def test_high_volume_transactions(self):
        """Feature handles high transaction volume."""

    def test_combined_with_lsm(self):
        """Feature interacts correctly with LSM."""

    def test_policy_tree_integration(self):
        """Policy trees can reference new feature fields."""
```

#### Category 4: Replay Identity Tests

**Purpose:** Verify run output matches replay output exactly.

**Location:** `api/tests/integration/test_replay_identity_<feature>.py`

**Required Scenarios:**

| Scenario | Description | Example |
|----------|-------------|---------|
| Event fields complete | All fields present in event | No missing data |
| Event round-trips | DB → Python identical | Serialize/deserialize match |
| Verbose output identical | run --verbose == replay --verbose | Byte-for-byte output |
| Event ordering | Events in correct order | Timestamp/tick ordering |

```python
# Example test structure
class TestFeatureReplayIdentity:
    def test_event_has_all_required_fields(self):
        """Event contains all fields needed for replay."""
        events = orch.get_tick_events(tick)
        event = [e for e in events if e['event_type'] == 'new_event'][0]
        assert 'field1' in event
        assert 'field2' in event
        # ... all fields

    def test_event_round_trip_through_database(self):
        """Event survives persistence and retrieval."""

    def test_verbose_output_matches_replay(self):
        """Run verbose output matches replay verbose output."""
```

#### Category 5: Edge Cases and Error Handling

**Purpose:** Verify robust behavior in unusual situations.

**Location:** Distributed across test files as `test_edge_*` or `test_error_*`

**Required Scenarios:**

| Scenario | Description | Example |
|----------|-------------|---------|
| Empty state | No transactions/agents | Empty queue processing |
| Single element | Minimum non-empty | One agent, one transaction |
| All same priority | No differentiation needed | All priority 5 |
| All different priority | Maximum differentiation | 0, 1, 2, ... 10 |
| Rapid changes | State changes every tick | Priority changes mid-simulation |
| Recovery | System recovers from issues | After failed settlement attempt |

### Test Naming Convention

All tests MUST follow this naming pattern:

```
test_<what>_<condition>_<expected>
```

**Examples:**
- `test_delay_cost_with_urgent_priority_returns_multiplied_amount`
- `test_config_parsing_with_missing_field_raises_validation_error`
- `test_arrival_generation_with_zero_rate_produces_no_arrivals`
- `test_replay_output_with_new_event_matches_run_output`

### Scenario Variety Matrix

For each enhancement, create a test matrix covering combinations:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                       SCENARIO VARIETY MATRIX                                │
├─────────────┬──────────────┬──────────────┬──────────────┬──────────────────┤
│ Dimension   │ Value 1      │ Value 2      │ Value 3      │ Value 4          │
├─────────────┼──────────────┼──────────────┼──────────────┼──────────────────┤
│ Agents      │ 1            │ 2            │ 5            │ 20               │
│ Ticks       │ 1            │ 10           │ 100          │ 1000             │
│ Transactions│ 0            │ 1            │ 10           │ 100              │
│ Priority    │ All low (0-3)│ All mid (4-7)│ All high(8-10)│ Mixed           │
│ Liquidity   │ Zero         │ Scarce       │ Ample        │ Unlimited        │
│ Config      │ Minimal      │ Typical      │ Complex      │ BIS scenario     │
└─────────────┴──────────────┴──────────────┴──────────────┴──────────────────┘
```

Not all combinations are needed, but ensure coverage of:
- All single-column values (minimum)
- Key diagonal combinations (typical usage)
- Stress combinations (high values across multiple dimensions)

### BIS Scenario Coverage

Each enhancement MUST include tests for the relevant BIS scenario:

| Enhancement | Primary BIS Scenario | Test Requirement |
|-------------|---------------------|------------------|
| 1: Priority Delay Costs | Scenario 1 (Precautionary) | Verify urgent/normal cost difference affects decisions |
| 2: Liquidity Allocation | Scenario 3 (Trade-off) | Verify allocation decision at day start |
| 3: Per-Band Arrivals | All scenarios | Verify rare-large-urgent vs common-small-normal |

### Test Execution Checklist

Before marking any implementation step complete:

```
□ Rust unit tests pass: cargo test --no-default-features
□ Python integration tests pass: pytest tests/integration/
□ Replay identity verified: diff run.txt replay.txt
□ Full test suite green: pytest
□ No new warnings introduced
□ Test coverage maintained/improved
□ BIS scenario test included
```

### Debugging Failed Tests

When a test fails:

1. **Read the failure message carefully** - Often indicates exact issue
2. **Check determinism first** - Run test with explicit seed, run 3x
3. **Isolate the failure** - Run just that one test in verbose mode
4. **Add debug output** - Temporary prints/logs to trace execution
5. **Check FFI boundary** - Verify data crosses correctly
6. **Check replay** - Compare run vs replay for differences

```bash
# Isolate failing test
.venv/bin/python -m pytest tests/integration/test_feature.py::test_specific -v -s

# Run with specific seed
SIMCASH_SEED=12345 .venv/bin/python -m pytest tests/integration/test_feature.py::test_specific -v

# Compare run vs replay
payment-sim run --config test.yaml --persist out.db --verbose > run.txt
payment-sim replay out.db --verbose > replay.txt
diff run.txt replay.txt
```

### Test Organization

```
api/tests/
├── integration/
│   ├── test_priority_delay_costs.py         # Enhancement 1
│   ├── test_priority_delay_costs_config.py  # Enhancement 1 config
│   ├── test_liquidity_allocation.py         # Enhancement 2
│   ├── test_liquidity_allocation_config.py  # Enhancement 2 config
│   ├── test_per_band_arrivals.py            # Enhancement 3
│   ├── test_per_band_arrivals_config.py     # Enhancement 3 config
│   ├── test_replay_identity_priority_costs.py    # Enhancement 1 replay
│   ├── test_replay_identity_liquidity.py         # Enhancement 2 replay
│   ├── test_replay_identity_per_band.py          # Enhancement 3 replay
│   └── test_bis_scenarios.py                # All BIS scenarios
│
simulator/tests/
├── priority_delay_costs_tests.rs    # Enhancement 1 Rust
├── liquidity_allocation_tests.rs    # Enhancement 2 Rust
└── per_band_arrivals_tests.rs       # Enhancement 3 Rust
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

**File:** `simulator/tests/priority_delay_costs.rs`

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

1. **Define Types** (`simulator/src/orchestrator/engine.rs`)
   - Add `PriorityDelayMultipliers` struct
   - Add `priority_delay_multipliers: Option<PriorityDelayMultipliers>` to `CostRates`
   - Add `PriorityBand` enum (Urgent, Normal, Low)
   - Add `get_priority_band(priority: u8) -> PriorityBand` function

2. **Update Cost Calculation** (`simulator/src/settlement/costs.rs` or appropriate module)
   - Modify delay cost calculation to use priority multiplier
   - Formula: `delay_cost = amount * base_rate * ticks * priority_multiplier`

3. **FFI Parsing** (`simulator/src/ffi/types.rs`)
   - Parse `priority_delay_multipliers` from Python dict

4. **Policy Context** (`simulator/src/policy/tree/context.rs`)
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

**File:** `simulator/tests/liquidity_allocation.rs`

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

**File:** `simulator/src/orchestrator/engine.rs`

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

**File:** `simulator/src/models/agent.rs`

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

**File:** `simulator/src/models/event.rs`

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

**File:** `simulator/src/orchestrator/engine.rs`

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

**File:** `simulator/src/ffi/types.rs`

Parse config and serialize event.

#### Step 6: Policy Context Fields

**File:** `simulator/src/policy/tree/context.rs`

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

## Enhancement 3: Per-Band Arrival Functions

### Purpose

Enable different arrival characteristics (rate, amount distribution, deadline) for each priority band, allowing realistic modeling where urgent payments are rare but large, and normal payments are common but smaller.

### Design

**Replace single `arrival_config` with per-band configurations:**

```yaml
agent_configs:
  - id: BANK_A
    # NEW: Per-band arrival functions
    arrival_bands:
      urgent:                         # Priority 8-10
        rate_per_tick: 0.1            # Rare (~1 per 10 ticks)
        amount_distribution:
          type: log_normal
          mean: 1_000_000             # Large ($10k average)
          std: 500_000
        deadline_offset:
          min_ticks: 2                # Tight deadlines
          max_ticks: 5

      normal:                         # Priority 4-7
        rate_per_tick: 3.0            # Common (~3 per tick)
        amount_distribution:
          type: log_normal
          mean: 50_000                # Medium ($500 average)
          std: 30_000
        deadline_offset:
          min_ticks: 10
          max_ticks: 50

      low:                            # Priority 0-3
        rate_per_tick: 5.0            # Frequent (~5 per tick)
        amount_distribution:
          type: log_normal
          mean: 10_000                # Small ($100 average)
          std: 8_000
        deadline_offset:
          min_ticks: 50
          max_ticks: 100
```

**Backwards Compatibility:**

Existing `arrival_config` continues to work unchanged. New `arrival_bands` is an alternative configuration style.

```yaml
# OLD (still supported): Single config, priority assigned via distribution
arrival_config:
  rate_per_tick: 5.0
  priority_distribution: {...}

# NEW: Per-band configs with implicit priority assignment
arrival_bands:
  urgent: {...}   # Generates priority 8-10
  normal: {...}   # Generates priority 4-7
  low: {...}      # Generates priority 0-3
```

### TDD Test Cases

#### Category 1: Configuration Parsing

**File:** `api/tests/integration/test_arrival_bands_config.py`

```python
"""
Configuration parsing tests for per-band arrival functions.
"""

import pytest
from payment_simulator.backends.rust import Orchestrator


class TestArrivalBandsParsing:
    """Tests for parsing arrival_bands configuration."""

    def test_parse_single_band(self):
        """Single band configuration should be parsed correctly."""
        config = {
            "ticks_per_day": 10,
            "agent_configs": [
                {
                    "id": "BANK_A",
                    "opening_balance": 1_000_000,
                    "arrival_bands": {
                        "urgent": {
                            "rate_per_tick": 0.5,
                            "amount_distribution": {
                                "type": "fixed",
                                "value": 100_000
                            }
                        }
                    }
                },
                {"id": "BANK_B", "opening_balance": 1_000_000}
            ]
        }
        orch = Orchestrator.new(config)

        # Should not raise
        assert orch is not None

    def test_parse_all_three_bands(self):
        """All three bands should be parseable."""
        config = {
            "ticks_per_day": 10,
            "agent_configs": [
                {
                    "id": "BANK_A",
                    "opening_balance": 1_000_000,
                    "arrival_bands": {
                        "urgent": {
                            "rate_per_tick": 0.1,
                            "amount_distribution": {"type": "fixed", "value": 1_000_000}
                        },
                        "normal": {
                            "rate_per_tick": 2.0,
                            "amount_distribution": {"type": "fixed", "value": 50_000}
                        },
                        "low": {
                            "rate_per_tick": 5.0,
                            "amount_distribution": {"type": "fixed", "value": 10_000}
                        }
                    }
                },
                {"id": "BANK_B", "opening_balance": 1_000_000}
            ]
        }
        orch = Orchestrator.new(config)
        assert orch is not None

    def test_reject_invalid_band_name(self):
        """Invalid band names should be rejected."""
        config = {
            "ticks_per_day": 10,
            "agent_configs": [
                {
                    "id": "BANK_A",
                    "opening_balance": 1_000_000,
                    "arrival_bands": {
                        "critical": {  # Invalid - should be "urgent"
                            "rate_per_tick": 0.1,
                            "amount_distribution": {"type": "fixed", "value": 100_000}
                        }
                    }
                },
                {"id": "BANK_B", "opening_balance": 1_000_000}
            ]
        }

        with pytest.raises(ValueError, match="invalid.*band"):
            Orchestrator.new(config)

    def test_backwards_compatible_arrival_config(self):
        """Old arrival_config style should still work."""
        config = {
            "ticks_per_day": 10,
            "agent_configs": [
                {
                    "id": "BANK_A",
                    "opening_balance": 1_000_000,
                    "arrival_config": {  # OLD STYLE
                        "rate_per_tick": 2.0,
                        "amount_distribution": {"type": "fixed", "value": 50_000},
                        "priority_distribution": {
                            "type": "discrete",
                            "values": [
                                {"value": 10, "weight": 0.1},
                                {"value": 5, "weight": 0.9}
                            ]
                        }
                    }
                },
                {"id": "BANK_B", "opening_balance": 1_000_000}
            ]
        }
        orch = Orchestrator.new(config)
        assert orch is not None

    def test_reject_both_arrival_config_and_bands(self):
        """Cannot specify both arrival_config and arrival_bands."""
        config = {
            "ticks_per_day": 10,
            "agent_configs": [
                {
                    "id": "BANK_A",
                    "opening_balance": 1_000_000,
                    "arrival_config": {"rate_per_tick": 2.0},
                    "arrival_bands": {"urgent": {"rate_per_tick": 0.1}}
                },
                {"id": "BANK_B", "opening_balance": 1_000_000}
            ]
        }

        with pytest.raises(ValueError, match="both.*arrival_config.*arrival_bands"):
            Orchestrator.new(config)
```

#### Category 2: Arrival Generation

**File:** `api/tests/integration/test_arrival_bands_generation.py`

```python
"""
Arrival generation tests for per-band arrival functions.
"""

import pytest
from payment_simulator.backends.rust import Orchestrator


class TestArrivalBandGeneration:
    """Tests for generating arrivals from per-band configs."""

    def test_urgent_band_generates_high_priority(self):
        """Urgent band should generate priority 8-10 transactions."""
        config = {
            "ticks_per_day": 100,
            "seed": 42,
            "agent_configs": [
                {
                    "id": "BANK_A",
                    "opening_balance": 10_000_000,
                    "arrival_bands": {
                        "urgent": {
                            "rate_per_tick": 1.0,  # Expect ~1 per tick
                            "amount_distribution": {"type": "fixed", "value": 100_000}
                        }
                    }
                },
                {"id": "BANK_B", "opening_balance": 10_000_000}
            ]
        }
        orch = Orchestrator.new(config)

        # Run several ticks
        for _ in range(10):
            orch.tick()

        # Check generated transactions
        events = orch.get_all_events()
        arrivals = [e for e in events if e["event_type"] == "Arrival"]

        # All arrivals should be priority 8-10
        for arr in arrivals:
            assert 8 <= arr["priority"] <= 10, f"Expected urgent priority, got {arr['priority']}"

    def test_normal_band_generates_mid_priority(self):
        """Normal band should generate priority 4-7 transactions."""
        config = {
            "ticks_per_day": 100,
            "seed": 42,
            "agent_configs": [
                {
                    "id": "BANK_A",
                    "opening_balance": 10_000_000,
                    "arrival_bands": {
                        "normal": {
                            "rate_per_tick": 2.0,
                            "amount_distribution": {"type": "fixed", "value": 50_000}
                        }
                    }
                },
                {"id": "BANK_B", "opening_balance": 10_000_000}
            ]
        }
        orch = Orchestrator.new(config)

        for _ in range(10):
            orch.tick()

        events = orch.get_all_events()
        arrivals = [e for e in events if e["event_type"] == "Arrival"]

        for arr in arrivals:
            assert 4 <= arr["priority"] <= 7, f"Expected normal priority, got {arr['priority']}"

    def test_low_band_generates_low_priority(self):
        """Low band should generate priority 0-3 transactions."""
        config = {
            "ticks_per_day": 100,
            "seed": 42,
            "agent_configs": [
                {
                    "id": "BANK_A",
                    "opening_balance": 10_000_000,
                    "arrival_bands": {
                        "low": {
                            "rate_per_tick": 3.0,
                            "amount_distribution": {"type": "fixed", "value": 10_000}
                        }
                    }
                },
                {"id": "BANK_B", "opening_balance": 10_000_000}
            ]
        }
        orch = Orchestrator.new(config)

        for _ in range(10):
            orch.tick()

        events = orch.get_all_events()
        arrivals = [e for e in events if e["event_type"] == "Arrival"]

        for arr in arrivals:
            assert 0 <= arr["priority"] <= 3, f"Expected low priority, got {arr['priority']}"

    def test_multiple_bands_generate_mixed_priorities(self):
        """Multiple bands should generate arrivals with appropriate priorities."""
        config = {
            "ticks_per_day": 100,
            "seed": 42,
            "agent_configs": [
                {
                    "id": "BANK_A",
                    "opening_balance": 10_000_000,
                    "arrival_bands": {
                        "urgent": {
                            "rate_per_tick": 0.5,
                            "amount_distribution": {"type": "fixed", "value": 500_000}
                        },
                        "normal": {
                            "rate_per_tick": 2.0,
                            "amount_distribution": {"type": "fixed", "value": 50_000}
                        }
                    }
                },
                {"id": "BANK_B", "opening_balance": 10_000_000}
            ]
        }
        orch = Orchestrator.new(config)

        for _ in range(50):
            orch.tick()

        events = orch.get_all_events()
        arrivals = [e for e in events if e["event_type"] == "Arrival"]

        urgent_count = sum(1 for a in arrivals if a["priority"] >= 8)
        normal_count = sum(1 for a in arrivals if 4 <= a["priority"] <= 7)

        # Should have both types
        assert urgent_count > 0, "Expected some urgent arrivals"
        assert normal_count > 0, "Expected some normal arrivals"

        # Normal should be more common (rate 2.0 vs 0.5)
        assert normal_count > urgent_count, "Normal should be more frequent than urgent"


class TestArrivalBandAmounts:
    """Tests for amount distributions per band."""

    def test_urgent_band_uses_its_amount_distribution(self):
        """Urgent arrivals should use urgent band's amount distribution."""
        config = {
            "ticks_per_day": 100,
            "seed": 42,
            "agent_configs": [
                {
                    "id": "BANK_A",
                    "opening_balance": 100_000_000,
                    "arrival_bands": {
                        "urgent": {
                            "rate_per_tick": 2.0,
                            "amount_distribution": {
                                "type": "fixed",
                                "value": 1_000_000  # $10,000
                            }
                        }
                    }
                },
                {"id": "BANK_B", "opening_balance": 100_000_000}
            ]
        }
        orch = Orchestrator.new(config)

        for _ in range(10):
            orch.tick()

        events = orch.get_all_events()
        arrivals = [e for e in events if e["event_type"] == "Arrival"]

        for arr in arrivals:
            assert arr["amount"] == 1_000_000

    def test_different_bands_have_different_amounts(self):
        """Each band should use its own amount distribution."""
        config = {
            "ticks_per_day": 100,
            "seed": 42,
            "agent_configs": [
                {
                    "id": "BANK_A",
                    "opening_balance": 100_000_000,
                    "arrival_bands": {
                        "urgent": {
                            "rate_per_tick": 1.0,
                            "amount_distribution": {"type": "fixed", "value": 1_000_000}
                        },
                        "normal": {
                            "rate_per_tick": 1.0,
                            "amount_distribution": {"type": "fixed", "value": 100_000}
                        },
                        "low": {
                            "rate_per_tick": 1.0,
                            "amount_distribution": {"type": "fixed", "value": 10_000}
                        }
                    }
                },
                {"id": "BANK_B", "opening_balance": 100_000_000}
            ]
        }
        orch = Orchestrator.new(config)

        for _ in range(20):
            orch.tick()

        events = orch.get_all_events()
        arrivals = [e for e in events if e["event_type"] == "Arrival"]

        for arr in arrivals:
            if arr["priority"] >= 8:
                assert arr["amount"] == 1_000_000, "Urgent should be $10k"
            elif arr["priority"] >= 4:
                assert arr["amount"] == 100_000, "Normal should be $1k"
            else:
                assert arr["amount"] == 10_000, "Low should be $100"
```

#### Category 3: Determinism and Replay

**File:** `api/tests/integration/test_arrival_bands_determinism.py`

```python
"""
Determinism and replay tests for per-band arrival functions.
"""

import pytest
from payment_simulator.backends.rust import Orchestrator


class TestArrivalBandsDeterminism:
    """Tests for deterministic behavior of per-band arrivals."""

    def test_same_seed_produces_identical_arrivals(self):
        """Same seed should produce identical arrival sequences."""
        config = {
            "ticks_per_day": 50,
            "seed": 12345,
            "agent_configs": [
                {
                    "id": "BANK_A",
                    "opening_balance": 10_000_000,
                    "arrival_bands": {
                        "urgent": {
                            "rate_per_tick": 0.5,
                            "amount_distribution": {"type": "fixed", "value": 500_000}
                        },
                        "normal": {
                            "rate_per_tick": 3.0,
                            "amount_distribution": {"type": "fixed", "value": 50_000}
                        }
                    }
                },
                {"id": "BANK_B", "opening_balance": 10_000_000}
            ]
        }

        # Run 1
        orch1 = Orchestrator.new(config)
        for _ in range(20):
            orch1.tick()
        events1 = orch1.get_all_events()
        arrivals1 = [e for e in events1 if e["event_type"] == "Arrival"]

        # Run 2 (same seed)
        orch2 = Orchestrator.new(config)
        for _ in range(20):
            orch2.tick()
        events2 = orch2.get_all_events()
        arrivals2 = [e for e in events2 if e["event_type"] == "Arrival"]

        # Should be identical
        assert len(arrivals1) == len(arrivals2)
        for a1, a2 in zip(arrivals1, arrivals2):
            assert a1["tick"] == a2["tick"]
            assert a1["amount"] == a2["amount"]
            assert a1["priority"] == a2["priority"]

    def test_different_seeds_produce_different_arrivals(self):
        """Different seeds should produce different arrival sequences."""
        def run_with_seed(seed):
            config = {
                "ticks_per_day": 50,
                "seed": seed,
                "agent_configs": [
                    {
                        "id": "BANK_A",
                        "opening_balance": 10_000_000,
                        "arrival_bands": {
                            "normal": {
                                "rate_per_tick": 3.0,
                                "amount_distribution": {"type": "fixed", "value": 50_000}
                            }
                        }
                    },
                    {"id": "BANK_B", "opening_balance": 10_000_000}
                ]
            }
            orch = Orchestrator.new(config)
            for _ in range(20):
                orch.tick()
            events = orch.get_all_events()
            return [e for e in events if e["event_type"] == "Arrival"]

        arrivals1 = run_with_seed(42)
        arrivals2 = run_with_seed(43)

        # Should be different (extremely unlikely to be identical)
        assert len(arrivals1) != len(arrivals2) or any(
            a1["tick"] != a2["tick"] for a1, a2 in zip(arrivals1, arrivals2)
        )
```

### Implementation Steps

#### Step 1: Define Types

**File:** `simulator/src/arrivals/config.rs`

```rust
/// Per-band arrival configuration
#[derive(Debug, Clone)]
pub struct ArrivalBandsConfig {
    pub urgent: Option<BandArrivalConfig>,   // Priority 8-10
    pub normal: Option<BandArrivalConfig>,   // Priority 4-7
    pub low: Option<BandArrivalConfig>,      // Priority 0-3
}

#[derive(Debug, Clone)]
pub struct BandArrivalConfig {
    pub rate_per_tick: f64,
    pub amount_distribution: Distribution,
    pub deadline_offset: Option<DeadlineConfig>,
    pub counterparty_weights: Option<HashMap<String, f64>>,
}

impl ArrivalBandsConfig {
    pub fn validate(&self) -> Result<(), ConfigError> {
        // At least one band must be specified
        if self.urgent.is_none() && self.normal.is_none() && self.low.is_none() {
            return Err(ConfigError::InvalidValue(
                "arrival_bands must specify at least one band".to_string()
            ));
        }
        Ok(())
    }
}
```

#### Step 2: Update Arrival Generator

**File:** `simulator/src/arrivals/generator.rs`

```rust
impl ArrivalGenerator {
    pub fn generate_arrivals(
        &self,
        agent_id: &str,
        tick: usize,
        rng_seed: u64,
    ) -> (Vec<Transaction>, u64) {
        let mut arrivals = Vec::new();
        let mut current_seed = rng_seed;

        if let Some(bands) = &self.arrival_bands {
            // Generate from each configured band
            if let Some(urgent) = &bands.urgent {
                let (txs, new_seed) = self.generate_for_band(
                    agent_id, tick, current_seed, urgent, PriorityBand::Urgent
                );
                arrivals.extend(txs);
                current_seed = new_seed;
            }
            if let Some(normal) = &bands.normal {
                let (txs, new_seed) = self.generate_for_band(
                    agent_id, tick, current_seed, normal, PriorityBand::Normal
                );
                arrivals.extend(txs);
                current_seed = new_seed;
            }
            if let Some(low) = &bands.low {
                let (txs, new_seed) = self.generate_for_band(
                    agent_id, tick, current_seed, low, PriorityBand::Low
                );
                arrivals.extend(txs);
                current_seed = new_seed;
            }
        } else if let Some(config) = &self.arrival_config {
            // Legacy single-config path
            let (txs, new_seed) = self.generate_legacy(agent_id, tick, current_seed, config);
            arrivals.extend(txs);
            current_seed = new_seed;
        }

        (arrivals, current_seed)
    }

    fn generate_for_band(
        &self,
        agent_id: &str,
        tick: usize,
        seed: u64,
        config: &BandArrivalConfig,
        band: PriorityBand,
    ) -> (Vec<Transaction>, u64) {
        let (count, seed1) = sample_poisson(config.rate_per_tick, seed);
        let mut current_seed = seed1;
        let mut txs = Vec::new();

        for _ in 0..count {
            let (amount, seed2) = sample_distribution(&config.amount_distribution, current_seed);
            let (priority, seed3) = sample_priority_in_band(band, seed2);
            let (receiver, seed4) = select_counterparty(&config.counterparty_weights, seed3);

            txs.push(Transaction::new(
                agent_id.to_string(),
                receiver,
                amount,
                priority,
                tick,
                calculate_deadline(tick, &config.deadline_offset),
            ));

            current_seed = seed4;
        }

        (txs, current_seed)
    }
}

fn sample_priority_in_band(band: PriorityBand, seed: u64) -> (u8, u64) {
    let (value, new_seed) = xorshift64_next(seed);
    let priority = match band {
        PriorityBand::Urgent => 8 + (value % 3) as u8,  // 8, 9, or 10
        PriorityBand::Normal => 4 + (value % 4) as u8,  // 4, 5, 6, or 7
        PriorityBand::Low => (value % 4) as u8,         // 0, 1, 2, or 3
    };
    (priority, new_seed)
}
```

#### Step 3: FFI Parsing

**File:** `simulator/src/ffi/types.rs`

Add parsing for `arrival_bands` configuration from Python dict.

#### Step 4: Documentation

Update `docs/policy_dsl_guide.md` and configuration examples.

---

## Implementation Order

### Recommended Sequence

1. **Enhancement 1: Priority-Based Delay Costs**
   - Lowest risk, cleanest addition to existing cost system
   - No changes to tick loop or event system
   - Enables BIS Scenario 2 immediately

2. **Enhancement 2: Liquidity Pool and Allocation**
   - More complex, touches tick lifecycle
   - Enables BIS Scenario 1 fully
   - Could be simplified to fixed allocation first

3. **Enhancement 3: Per-Band Arrival Functions**
   - Extends arrival generator with band-specific configs
   - Enables realistic Monte Carlo simulations
   - Backwards compatible with existing `arrival_config`

### Dependencies

```
Enhancement 1 ─────────────────────────────────► BIS Scenario 2

Enhancement 2 ─────────────────────────────────► BIS Scenario 1

Enhancement 3 ─────────────────────────────────► Realistic Monte Carlo
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
- [ ] Monte Carlo analysis possible (deterministic with different seeds)
- [ ] Realistic arrival patterns with per-band characteristics

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

### Scenario 3: Realistic Monte Carlo with Per-Band Arrivals

```yaml
# bis-scenario-3-monte-carlo.yaml
ticks_per_day: 100
num_days: 5
seed: 12345  # Vary for Monte Carlo

cost_rates:
  delay_cost_per_tick_per_cent: 0.01
  priority_delay_multipliers:
    urgent_multiplier: 1.5
    normal_multiplier: 1.0
  liquidity_cost_per_tick_bps: 15

agent_configs:
  - id: BANK_A
    liquidity_pool: 5000000
    liquidity_allocation_fraction: 0.5
    credit_limit: 0
    # NEW: Per-band arrival functions
    arrival_bands:
      urgent:                         # Rare, large, tight deadlines
        rate_per_tick: 0.1
        amount_distribution:
          type: log_normal
          mean: 1000000               # $10k average
          std: 500000
        deadline_offset:
          min_ticks: 5
          max_ticks: 15
      normal:                         # Common, medium amounts
        rate_per_tick: 2.0
        amount_distribution:
          type: log_normal
          mean: 50000                 # $500 average
          std: 30000
        deadline_offset:
          min_ticks: 20
          max_ticks: 60
      low:                            # Frequent, small, flexible deadlines
        rate_per_tick: 5.0
        amount_distribution:
          type: log_normal
          mean: 10000                 # $100 average
          std: 8000
        deadline_offset:
          min_ticks: 50
          max_ticks: 100

  - id: BANK_B
    liquidity_pool: 5000000
    liquidity_allocation_fraction: 0.5
    credit_limit: 0
    arrival_bands:
      urgent:
        rate_per_tick: 0.1
        amount_distribution:
          type: log_normal
          mean: 1000000
          std: 500000
      normal:
        rate_per_tick: 2.0
        amount_distribution:
          type: log_normal
          mean: 50000
          std: 30000
      low:
        rate_per_tick: 5.0
        amount_distribution:
          type: log_normal
          mean: 10000
          std: 8000

lsm_config:
  enable_bilateral: false
  enable_cycles: false
```

---

*Last updated: 2025-11-27*
