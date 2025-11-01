# Implementation Plan: Complex Policy DSL Features
## Enabling Realistic Multi-Agent Payment Strategies

**Document Version**: 1.0
**Date**: 2025-11-01
**Target**: Phase 9.5 (DSL Enhancement)
**Estimated Effort**: 5-7 days
**Development Approach**: Strict TDD (Test-Driven Development)

---

## Executive Summary

This plan extends the Phase 9 Policy DSL to support the complex, realistic policies described in the game design document. The "Adaptive Liquidity & Gridlock Manager" example policy reveals five critical gaps in the current implementation:

1. **Cost-Aware Context** - Policies need access to cost parameters to make economic trade-offs
2. **System Configuration Context** - Policies need system-wide parameters (ticks_per_day, cut-offs)
3. **Enhanced Collateral Context** - Strategic and reactive collateral trees need specialized context
4. **Dynamic Action Parameters** - All action parameters must support computed values
5. **Validation & Integration** - End-to-end validation with the complex example policy

**Development Philosophy**: Write tests FIRST, implement SECOND, validate THIRD. Every feature begins with a failing test.

---

## Part I: Current State Assessment

### What Works Today ✅

From Phase 9 completion:
- ✅ Expression evaluator with 50+ context fields ([backend/src/policy/tree/context.rs](backend/src/policy/tree/context.rs))
- ✅ Three-tree architecture (`payment_tree`, `strategic_collateral_tree`, `end_of_tick_collateral_tree`)
- ✅ `ValueOrCompute` type for dynamic values in expressions
- ✅ Validation pipeline (schema, cycles, field references)
- ✅ Basic collateral fields (`posted_collateral`, `max_collateral_capacity`, `collateral_utilization`)

### Identified Gaps ❌

**Gap 1: Cost Parameters Not Exposed**
- `CostRates` passed to `evaluate_queue()` but not accessible in `EvalContext`
- Policies cannot make cost-based decisions (e.g., "overdraft cheaper than delay?")
- **Impact**: Cannot implement economic optimization policies

**Gap 2: System Configuration Missing**
- No access to `ticks_per_day`, `split_friction`, or system-wide settings
- Cannot reason about "% through the day" or "approaching EOD"
- **Impact**: Cannot implement time-of-day strategies (morning vs. EOD behavior)

**Gap 3: Collateral Trees Need Specialized Context**
- Strategic collateral tree needs forward-looking context (Queue 1 gap)
- End-of-tick collateral tree needs post-settlement context (headroom)
- Currently using same context as payment tree (transaction-focused)
- **Impact**: Collateral decisions are not context-appropriate

**Gap 4: Action Parameters Partially Dynamic**
- `ValueOrCompute` exists but not fully wired for all action types
- `num_splits` in `Split` action needs computed value support
- `amount` in `PostCollateral`/`WithdrawCollateral` needs computed value support
- **Impact**: Cannot dynamically calculate split count or collateral amounts

**Gap 5: Missing Derived Fields**
- No `ticks_remaining_in_day` field
- No `time_to_eod` field
- No `cost_if_hold_one_tick` computed field
- **Impact**: Policies must manually compute common values

---

## Part II: Implementation Phases (TDD Approach)

### Phase 9.5.1: Cost-Aware Context (Days 1-2)

**Goal**: Expose cost parameters and derived cost calculations to policy context.

#### Step 1.1: Write Failing Tests FIRST

**File**: `backend/src/policy/tree/tests/test_cost_context.rs` (new file)

```rust
#[cfg(test)]
mod test_cost_context {
    use super::*;

    #[test]
    fn test_cost_fields_available_in_context() {
        let context = create_test_context_with_costs();

        // THESE TESTS WILL FAIL INITIALLY
        assert!(context.has_field("cost_overdraft_bps_per_tick"));
        assert!(context.has_field("cost_delay_per_tick_per_cent"));
        assert!(context.has_field("cost_collateral_bps_per_tick"));
        assert!(context.has_field("cost_split_friction"));
        assert!(context.has_field("cost_deadline_penalty"));
        assert!(context.has_field("cost_eod_penalty"));
    }

    #[test]
    fn test_derived_cost_calculations() {
        let context = create_test_context_with_costs();

        // Derived field: "What would one tick of delay cost for THIS transaction?"
        // Formula: cost_delay_per_tick_per_cent * amount
        assert!(context.has_field("cost_delay_this_tx_one_tick"));

        // Derived field: "What would overdraft cost for THIS amount for one tick?"
        // Formula: (cost_overdraft_bps_per_tick / 10000) * amount
        assert!(context.has_field("cost_overdraft_this_amount_one_tick"));
    }

    #[test]
    fn test_cost_comparison_logic() {
        let (tx, agent, state, tick) = create_scenario_where_delay_cheaper_than_overdraft();
        let cost_rates = CostRates {
            overdraft_bps_per_tick: 0.01,  // Expensive overdraft
            delay_cost_per_tick_per_cent: 0.0001,  // Cheap delay
            ..Default::default()
        };

        let context = EvalContext::build(&tx, &agent, &state, tick, &cost_rates);

        // Should be able to compare costs
        let delay_cost = context.get_field("cost_delay_this_tx_one_tick").unwrap();
        let overdraft_cost = context.get_field("cost_overdraft_this_amount_one_tick").unwrap();

        assert!(delay_cost < overdraft_cost, "Delay should be cheaper");
    }
}
```

**Tests to Write** (15 tests total):
1. ✅ `test_cost_fields_available_in_context` - All 6 cost rate fields accessible
2. ✅ `test_cost_values_match_input` - Values match CostRates struct
3. ✅ `test_derived_cost_delay_one_tick` - Delay cost calculation correct
4. ✅ `test_derived_cost_overdraft_one_tick` - Overdraft cost calculation correct
5. ✅ `test_cost_comparison_logic` - Can compare costs in expressions
6. ✅ `test_cost_context_with_zero_rates` - Handles zero costs gracefully
7. ✅ `test_cost_context_integration_with_tree` - Costs work in decision tree
8. ✅ `test_split_friction_available` - Split friction in context
9. ✅ `test_deadline_penalty_available` - Deadline penalty in context
10. ✅ `test_eod_penalty_available` - EOD penalty in context
11. ✅ `test_cost_based_hold_decision` - Policy can hold based on cost comparison
12. ✅ `test_cost_based_release_decision` - Policy can release based on cost comparison
13. ✅ `test_cost_precision_no_float_contamination` - All costs as integers or safe conversions
14. ✅ `test_cost_context_determinism` - Same inputs = same costs (no system time)
15. ✅ `test_cost_integration_with_validation` - Validator accepts cost field references

#### Step 1.2: Implement to Pass Tests

**File**: `backend/src/policy/tree/context.rs`

**Changes**:
```rust
// Add to EvalContext::build() signature
pub fn build(
    tx: &Transaction,
    agent: &Agent,
    state: &SimulationState,
    tick: usize,
    cost_rates: &CostRates  // NEW PARAMETER
) -> Self {
    let mut fields = HashMap::new();

    // ... existing fields ...

    // NEW: Cost rate fields
    fields.insert("cost_overdraft_bps_per_tick".to_string(), cost_rates.overdraft_bps_per_tick);
    fields.insert("cost_delay_per_tick_per_cent".to_string(), cost_rates.delay_cost_per_tick_per_cent);
    fields.insert("cost_collateral_bps_per_tick".to_string(), cost_rates.collateral_cost_per_tick_bps);
    fields.insert("cost_split_friction".to_string(), cost_rates.split_friction_cost as f64);
    fields.insert("cost_deadline_penalty".to_string(), cost_rates.deadline_penalty as f64);
    fields.insert("cost_eod_penalty".to_string(), cost_rates.eod_penalty_per_transaction as f64);

    // NEW: Derived cost calculations
    let amount_f64 = tx.remaining_amount() as f64;

    // Delay cost for THIS transaction for one tick
    let delay_cost_one_tick = amount_f64 * cost_rates.delay_cost_per_tick_per_cent;
    fields.insert("cost_delay_this_tx_one_tick".to_string(), delay_cost_one_tick);

    // Overdraft cost for THIS amount for one tick
    let overdraft_cost_one_tick = (cost_rates.overdraft_bps_per_tick / 10_000.0) * amount_f64;
    fields.insert("cost_overdraft_this_amount_one_tick".to_string(), overdraft_cost_one_tick);

    Self { fields }
}
```

**Propagate Changes**:
- Update all `EvalContext::build()` call sites to pass `cost_rates`
- Update `TreePolicy::evaluate_queue()` to pass cost_rates to context
- Update tests to use new signature

#### Step 1.3: Validation Tests

**File**: `backend/policies/cost_aware_test.json` (new test policy)

```json
{
  "version": "1.0",
  "policy_id": "cost_aware_test",
  "description": "Test policy that uses cost fields",
  "payment_tree": {
    "type": "condition",
    "node_id": "N1",
    "description": "Hold if delay is cheaper than overdraft",
    "condition": {
      "op": "<",
      "left": {"field": "cost_delay_this_tx_one_tick"},
      "right": {"field": "cost_overdraft_this_amount_one_tick"}
    },
    "on_true": {
      "type": "action",
      "node_id": "A1",
      "action": "Hold",
      "parameters": {
        "reason": {"value": "DelayCheaperThanOverdraft"}
      }
    },
    "on_false": {
      "type": "action",
      "node_id": "A2",
      "action": "Release"
    }
  },
  "parameters": {}
}
```

**Integration Test**:
```rust
#[test]
fn test_cost_aware_policy_integration() {
    let policy = TreePolicy::from_file("backend/policies/cost_aware_test.json").unwrap();

    // Scenario: High overdraft cost, low delay cost
    let cost_rates = CostRates {
        overdraft_bps_per_tick: 0.05,  // 50 bps per tick (expensive)
        delay_cost_per_tick_per_cent: 0.0001,  // 1 bp per tick (cheap)
        ..Default::default()
    };

    let mut agent = Agent::new("BANK_A".to_string(), -100_000, 500_000);  // Negative balance
    let tx = Transaction::new("BANK_A".to_string(), "BANK_B".to_string(), 1_000_000, 0, 100);
    agent.queue_outgoing(tx.id().to_string());

    let mut state = SimulationState::new(vec![agent.clone()]);
    state.add_transaction(tx.clone());

    let decisions = policy.evaluate_queue(&agent, &state, 50, &cost_rates);

    // Should HOLD because delay is cheaper
    assert_eq!(decisions.len(), 1);
    assert!(matches!(decisions[0], ReleaseDecision::Hold { .. }));
}
```

**Success Criteria**:
- ✅ All 15 tests pass
- ✅ Cost fields accessible in decision trees
- ✅ Policies can make cost-based trade-off decisions
- ✅ Integration test validates end-to-end flow

---

### Phase 9.5.2: System Configuration Context (Days 2-3)

**Goal**: Expose system-wide configuration parameters to policies.

#### Step 2.1: Write Failing Tests FIRST

**File**: `backend/src/policy/tree/tests/test_system_context.rs` (new file)

```rust
#[cfg(test)]
mod test_system_context {
    use super::*;

    #[test]
    fn test_system_config_fields_available() {
        let context = create_test_context_with_system_config();

        // THESE WILL FAIL INITIALLY
        assert!(context.has_field("system_ticks_per_day"));
        assert!(context.has_field("system_current_day"));
        assert!(context.has_field("system_tick_in_day"));  // 0 to ticks_per_day-1
    }

    #[test]
    fn test_derived_time_fields() {
        let context = create_test_context_at_tick_80_of_100();

        // Derived: How many ticks left in this day?
        assert!(context.has_field("ticks_remaining_in_day"));
        assert_eq!(context.get_field("ticks_remaining_in_day").unwrap(), 20.0);

        // Derived: What fraction of the day has elapsed? (0.0 to 1.0)
        assert!(context.has_field("day_progress_fraction"));
        assert_eq!(context.get_field("day_progress_fraction").unwrap(), 0.8);
    }

    #[test]
    fn test_eod_rush_detection() {
        let context_early = create_test_context_at_tick_20_of_100();
        let context_late = create_test_context_at_tick_90_of_100();

        // Derived boolean: Are we in the last 20% of the day?
        assert!(context_late.has_field("is_eod_rush"));
        assert_eq!(context_late.get_field("is_eod_rush").unwrap(), 1.0);  // True
        assert_eq!(context_early.get_field("is_eod_rush").unwrap(), 0.0);  // False
    }
}
```

**Tests to Write** (12 tests total):
1. ✅ `test_system_ticks_per_day_available`
2. ✅ `test_system_current_day_available`
3. ✅ `test_system_tick_in_day_available`
4. ✅ `test_derived_ticks_remaining_in_day`
5. ✅ `test_derived_day_progress_fraction`
6. ✅ `test_is_eod_rush_boolean_field`
7. ✅ `test_eod_rush_threshold_configurable` - EOD threshold as parameter
8. ✅ `test_system_context_integration_with_tree`
9. ✅ `test_time_based_policy_behavior` - Different actions based on time
10. ✅ `test_system_config_determinism`
11. ✅ `test_multi_day_simulation_context` - Day counter increments correctly
12. ✅ `test_system_fields_validation`

#### Step 2.2: Implement to Pass Tests

**File**: `backend/src/policy/tree/context.rs`

**Changes**:
```rust
// Update signature to include system config
pub fn build(
    tx: &Transaction,
    agent: &Agent,
    state: &SimulationState,
    tick: usize,
    cost_rates: &CostRates,
    ticks_per_day: usize,  // NEW
    eod_rush_threshold: f64  // NEW (e.g., 0.8 = last 20% of day)
) -> Self {
    let mut fields = HashMap::new();

    // ... existing fields ...

    // NEW: System configuration
    fields.insert("system_ticks_per_day".to_string(), ticks_per_day as f64);

    let current_day = tick / ticks_per_day;
    let tick_in_day = tick % ticks_per_day;

    fields.insert("system_current_day".to_string(), current_day as f64);
    fields.insert("system_tick_in_day".to_string(), tick_in_day as f64);

    // Derived: Ticks remaining in current day
    let ticks_remaining_in_day = ticks_per_day - tick_in_day - 1;
    fields.insert("ticks_remaining_in_day".to_string(), ticks_remaining_in_day as f64);

    // Derived: Progress through day (0.0 to 1.0)
    let day_progress_fraction = (tick_in_day as f64) / (ticks_per_day as f64);
    fields.insert("day_progress_fraction".to_string(), day_progress_fraction);

    // Derived: Boolean flag for EOD rush
    let is_eod_rush = if day_progress_fraction >= eod_rush_threshold { 1.0 } else { 0.0 };
    fields.insert("is_eod_rush".to_string(), is_eod_rush);

    Self { fields }
}
```

**Add to Orchestrator Config**:
```rust
// backend/src/orchestrator/engine.rs
pub struct Orchestrator {
    // ... existing fields ...
    eod_rush_threshold: f64,  // NEW: Default 0.8 (last 20% of day)
}
```

#### Step 2.3: Validation Tests

**File**: `backend/policies/time_aware_test.json`

```json
{
  "version": "1.0",
  "policy_id": "time_aware_test",
  "description": "Release all at EOD, otherwise hold unless urgent",
  "payment_tree": {
    "type": "condition",
    "node_id": "N1",
    "description": "Check if EOD rush",
    "condition": {
      "op": "==",
      "left": {"field": "is_eod_rush"},
      "right": {"value": 1.0}
    },
    "on_true": {
      "type": "action",
      "node_id": "A1",
      "action": "Release"
    },
    "on_false": {
      "type": "condition",
      "node_id": "N2",
      "description": "Check if urgent",
      "condition": {
        "op": "<=",
        "left": {"field": "ticks_to_deadline"},
        "right": {"value": 5.0}
      },
      "on_true": {
        "type": "action",
        "node_id": "A2",
        "action": "Release"
      },
      "on_false": {
        "type": "action",
        "node_id": "A3",
        "action": "Hold",
        "parameters": {
          "reason": {"value": "WaitingForEOD"}
        }
      }
    }
  }
}
```

**Success Criteria**:
- ✅ All 12 tests pass
- ✅ Time-of-day context available
- ✅ EOD rush detection works
- ✅ Policies can implement time-based strategies

---

### Phase 9.5.3: Dynamic Action Parameters (Days 3-4)

[... rest of the plan continues as in the original document ...]

---

## Part III: Testing Strategy

### Test Pyramid

**Unit Tests (60%)**: Backend Rust
- Context field extraction (30 tests)
- Parameter evaluation (20 tests)
- Tree execution logic (25 tests)
- Validation rules (15 tests)

**Integration Tests (30%)**: Python FFI + API
- Policy loading and execution (20 tests)
- Orchestrator integration (15 tests)
- Multi-agent scenarios (10 tests)

**End-to-End Tests (10%)**: Full simulation
- Adaptive policy full-day simulation (5 tests)
- Comparison benchmarks (5 tests)

### TDD Workflow

**For Each Feature**:
```bash
# 1. Write failing test
touch backend/src/policy/tree/tests/test_feature.rs
# Write test that calls non-existent function
cargo test test_feature -- --nocapture
# ❌ FAILS (as expected)

# 2. Implement minimal code to pass
# Edit backend/src/policy/tree/context.rs
cargo test test_feature
# ✅ PASSES

# 3. Refactor
# Clean up, optimize, document
cargo test  # All tests still pass

# 4. Integration test
# Write Python test in api/tests/integration/
pytest api/tests/integration/test_feature.py
# ✅ PASSES

# 5. Commit
git add .
git commit -m "feat(policy): Add cost-aware context fields"
```

---

**Full implementation details continue in original document...**
