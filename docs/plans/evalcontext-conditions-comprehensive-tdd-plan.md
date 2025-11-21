# Comprehensive TDD Testing Plan for EvalContext Conditions

## Executive Summary

EvalContext provides **94 fixed fields** (plus dynamic state registers) across **12 categories** for policy decision trees. This plan ensures every single condition is thoroughly tested for various cases and edge cases, adhering to strict TDD principles.

**Key Principle**: Tests document expected behavior. If tests fail due to erroneous implementation, the test is the source of truth - the implementation needs fixing.

---

## Current Test Coverage Analysis

### Existing Test Files

| File | Tests | Status |
|------|-------|--------|
| `context.rs` (inline) | 18 | ✅ Passing |
| `test_cost_context.rs` | 15 | ✅ Passing |
| `test_system_context.rs` | 12 | ✅ Passing |
| `test_lsm_awareness_fields.rs` | 9 | ✅ Passing |
| `test_counterparty_fields.rs` | 12 | ⚠️ 5 ignored |
| `test_public_signal_fields.rs` | 15 | ✅ Passing |
| `test_throughput_progress_fields.rs` | 18 | ⚠️ 7 ignored |
| `test_overdraft_regime.rs` | 18 | ⚠️ 4 ignored |
| `test_state_registers.rs` | 12 | ✅ Passing |

### Coverage Gaps Identified

1. **Collateral fields** - Minimal testing for T2/CLM-style fields
2. **Edge cases** - Division by zero, negative values, overflow
3. **bank_level() method** - Fewer tests than build()
4. **Placeholder fields** - `lsm_run_rate_last_10_ticks`, `system_throughput_guidance_fraction_by_tick` always return 0.0
5. **Cross-field interactions** - Testing fields in combination
6. **Dynamic state registers** - More edge cases needed

---

## Complete Field Inventory (94 Fields)

### Category 1: Transaction Fields (12 fields)

| Field | Type | Test Coverage | Priority |
|-------|------|--------------|----------|
| `amount` | i64→f64 | ✅ Basic | Medium |
| `remaining_amount` | i64→f64 | ✅ Basic | High |
| `settled_amount` | i64→f64 | ✅ Basic | Medium |
| `arrival_tick` | usize→f64 | ✅ Basic | Low |
| `deadline_tick` | usize→f64 | ✅ Basic | Medium |
| `priority` | u8→f64 | ✅ Basic | Low |
| `is_split` | bool→0/1 | ✅ Basic | Medium |
| `is_past_deadline` | bool→0/1 | ✅ Basic | High |
| `is_overdue` | bool→0/1 | ✅ Basic | High |
| `overdue_duration` | usize→f64 | ✅ Basic | High |
| `ticks_to_deadline` | i64→f64 | ✅ Basic | High |
| `queue_age` | usize→f64 | ✅ Basic | Medium |

**Tests Needed:**
```rust
// Edge cases for each field
#[test] fn test_amount_zero();
#[test] fn test_amount_max_i64();
#[test] fn test_remaining_amount_after_partial_settlement();
#[test] fn test_ticks_to_deadline_exact_zero();
#[test] fn test_ticks_to_deadline_large_negative();
#[test] fn test_is_overdue_transitions();
#[test] fn test_overdue_duration_at_exact_deadline();
#[test] fn test_priority_full_range_0_to_10();
#[test] fn test_queue_age_zero_when_just_arrived();
```

### Category 2: Agent Fields (12 fields)

| Field | Type | Test Coverage | Priority |
|-------|------|--------------|----------|
| `balance` | i64→f64 | ✅ Basic | High |
| `credit_limit` | i64→f64 | ✅ Basic | High |
| `available_liquidity` | i64→f64 | ✅ Basic | Critical |
| `credit_used` | i64→f64 | ✅ Basic | High |
| `effective_liquidity` | i64→f64 | ⚠️ Partial | Critical |
| `is_using_credit` | bool→0/1 | ✅ Basic | Medium |
| `liquidity_buffer` | i64→f64 | ✅ Basic | Medium |
| `outgoing_queue_size` | usize→f64 | ✅ Basic | Medium |
| `incoming_expected_count` | usize→f64 | ✅ Basic | Low |
| `liquidity_pressure` | f64 | ✅ Basic | Medium |
| `credit_headroom` | i64→f64 | ✅ Basic | High |
| `is_overdraft_capped` | const 1.0 | ✅ Basic | Low |

**Tests Needed:**
```rust
// Balance edge cases
#[test] fn test_balance_negative_at_credit_limit();
#[test] fn test_balance_negative_beyond_credit_limit_bug_detection();
#[test] fn test_balance_zero_boundary();

// Effective liquidity critical tests (Phase 11 fix)
#[test] fn test_effective_liquidity_positive_balance_positive_credit();
#[test] fn test_effective_liquidity_negative_balance_remaining_credit();
#[test] fn test_effective_liquidity_at_exact_credit_limit();
#[test] fn test_effective_liquidity_vs_available_liquidity_difference();

// Credit usage
#[test] fn test_credit_used_exactly_at_limit();
#[test] fn test_credit_headroom_zero_at_limit();
#[test] fn test_credit_headroom_negative_when_exceeded();
#[test] fn test_is_using_credit_boundary_at_zero_balance();

// Liquidity pressure
#[test] fn test_liquidity_pressure_empty_queue();
#[test] fn test_liquidity_pressure_full_queue();
#[test] fn test_liquidity_pressure_computation_formula();
```

### Category 3: Collateral Fields (19 fields)

| Field | Type | Test Coverage | Priority |
|-------|------|--------------|----------|
| `posted_collateral` | i64→f64 | ⚠️ Basic | High |
| `max_collateral_capacity` | i64→f64 | ⚠️ Basic | Medium |
| `remaining_collateral_capacity` | i64→f64 | ⚠️ Basic | Medium |
| `collateral_utilization` | f64 (0-1) | ⚠️ Basic | High |
| `queue1_liquidity_gap` | i64→f64 | ⚠️ Basic | High |
| `queue1_total_value` | i64→f64 | ⚠️ Basic | High |
| `headroom` | i64→f64 | ⚠️ Basic | Critical |
| `queue2_size` | usize→f64 | ⚠️ Basic | Medium |
| `queue2_count_for_agent` | usize→f64 | ⚠️ Basic | Medium |
| `queue2_nearest_deadline` | usize→f64 | ⚠️ Basic | High |
| `ticks_to_nearest_queue2_deadline` | f64/INF | ⚠️ Minimal | High |
| `credit_used` | i64→f64 | ✅ Duplicate | - |
| `allowed_overdraft_limit` | i64→f64 | ⚠️ Basic | High |
| `overdraft_headroom` | i64→f64 | ⚠️ Basic | High |
| `collateral_haircut` | f64 (0-1) | ⚠️ Basic | Medium |
| `unsecured_cap` | i64→f64 | ⚠️ Basic | Medium |
| `required_collateral_for_usage` | f64 | ⚠️ Basic | High |
| `excess_collateral` | f64 | ⚠️ Basic | Medium |
| `overdraft_utilization` | f64 (0-1+) | ⚠️ Basic | High |

**Tests Needed:**
```rust
// File: backend/tests/test_collateral_context_fields.rs (NEW)

// Collateral posting scenarios
#[test] fn test_posted_collateral_zero_when_none_posted();
#[test] fn test_posted_collateral_after_posting();
#[test] fn test_posted_collateral_after_withdrawal();
#[test] fn test_max_collateral_capacity_default();
#[test] fn test_remaining_collateral_capacity_computation();

// Collateral utilization edge cases
#[test] fn test_collateral_utilization_zero_when_no_capacity();
#[test] fn test_collateral_utilization_at_100_percent();
#[test] fn test_collateral_utilization_partial();

// Queue 1 liquidity gap
#[test] fn test_queue1_liquidity_gap_empty_queue();
#[test] fn test_queue1_liquidity_gap_with_sufficient_liquidity();
#[test] fn test_queue1_liquidity_gap_with_shortfall();
#[test] fn test_queue1_total_value_empty_queue();
#[test] fn test_queue1_total_value_multiple_transactions();

// Headroom critical tests
#[test] fn test_headroom_positive_when_excess_liquidity();
#[test] fn test_headroom_negative_when_shortfall();
#[test] fn test_headroom_zero_exact_match();

// Queue 2 deadline tracking
#[test] fn test_queue2_count_for_agent_empty();
#[test] fn test_queue2_count_for_agent_with_transactions();
#[test] fn test_queue2_nearest_deadline_no_transactions_is_max();
#[test] fn test_queue2_nearest_deadline_with_transactions();
#[test] fn test_ticks_to_nearest_queue2_deadline_infinity_when_empty();
#[test] fn test_ticks_to_nearest_queue2_deadline_computation();

// T2/CLM-style fields
#[test] fn test_allowed_overdraft_limit_with_collateral();
#[test] fn test_allowed_overdraft_limit_without_collateral();
#[test] fn test_overdraft_headroom_computation();
#[test] fn test_required_collateral_for_usage_formula();
#[test] fn test_required_collateral_haircut_100_percent();
#[test] fn test_excess_collateral_computation();
#[test] fn test_overdraft_utilization_under_100_percent();
#[test] fn test_overdraft_utilization_at_100_percent();
#[test] fn test_overdraft_utilization_over_100_percent();
```

### Category 4: Cost Fields (8 fields)

| Field | Type | Test Coverage | Priority |
|-------|------|--------------|----------|
| `cost_overdraft_bps_per_tick` | f64 | ✅ Good | Medium |
| `cost_delay_per_tick_per_cent` | f64 | ✅ Good | Medium |
| `cost_collateral_bps_per_tick` | f64 | ✅ Good | Low |
| `cost_split_friction` | i64→f64 | ✅ Good | Low |
| `cost_deadline_penalty` | i64→f64 | ✅ Good | Medium |
| `cost_eod_penalty` | i64→f64 | ✅ Good | Medium |
| `cost_delay_this_tx_one_tick` | f64 | ✅ Good | High |
| `cost_overdraft_this_amount_one_tick` | f64 | ✅ Good | High |

**Additional Tests Needed:**
```rust
// Edge cases not yet covered
#[test] fn test_cost_delay_zero_amount_transaction();
#[test] fn test_cost_overdraft_extreme_bps_value();
#[test] fn test_cost_comparison_equal_costs();
#[test] fn test_cost_fields_with_negative_rates_prevented();
```

### Category 5: System Configuration Fields (6 fields)

| Field | Type | Test Coverage | Priority |
|-------|------|--------------|----------|
| `system_ticks_per_day` | usize→f64 | ✅ Good | Medium |
| `system_current_day` | usize→f64 | ✅ Good | Medium |
| `system_tick_in_day` | usize→f64 | ✅ Good | Medium |
| `ticks_remaining_in_day` | usize→f64 | ✅ Good | High |
| `day_progress_fraction` | f64 (0-1) | ✅ Good | High |
| `is_eod_rush` | f64 (0/1) | ✅ Good | High |

**Additional Tests Needed:**
```rust
// Edge cases
#[test] fn test_system_ticks_per_day_one_tick_day();
#[test] fn test_system_current_day_large_tick_number();
#[test] fn test_day_progress_fraction_at_exact_boundaries();
#[test] fn test_is_eod_rush_exact_threshold();
#[test] fn test_ticks_remaining_at_last_tick_of_day();
```

### Category 6: LSM-Aware Fields (25 fields)

| Field | Type | Test Coverage | Priority |
|-------|------|--------------|----------|
| `my_q2_out_value_to_counterparty` | i64→f64 | ✅ Good | High |
| `my_q2_in_value_from_counterparty` | i64→f64 | ✅ Good | High |
| `my_bilateral_net_q2` | i64→f64 | ✅ Good | High |
| `my_q2_out_value_top_1..5` | i64→f64 | ✅ Good | Medium |
| `my_q2_in_value_top_1..5` | i64→f64 | ⚠️ Basic | Medium |
| `my_bilateral_net_q2_top_1..5` | i64→f64 | ⚠️ Basic | Medium |
| `top_cpty_1..5_id_hash` | u64→f64 | ✅ Basic | Low |

**Additional Tests Needed:**
```rust
// File: backend/tests/test_lsm_awareness_fields.rs (EXTEND)

// Top counterparty edge cases
#[test] fn test_top_counterparties_fewer_than_5();
#[test] fn test_top_counterparties_exactly_5();
#[test] fn test_top_counterparties_more_than_5();
#[test] fn test_top_counterparties_with_ties();
#[test] fn test_my_q2_in_value_top_fields_populated();
#[test] fn test_my_bilateral_net_q2_top_fields_sorting();

// Hash collision awareness
#[test] fn test_counterparty_hash_uniqueness_sample();

// Empty queue scenarios
#[test] fn test_lsm_fields_all_zero_when_empty_queue2();
#[test] fn test_bilateral_net_zero_when_balanced();
```

### Category 7: Public Signal Fields (3 fields)

| Field | Type | Test Coverage | Priority |
|-------|------|--------------|----------|
| `system_queue2_pressure_index` | f64 (0-1) | ✅ Good | High |
| `lsm_run_rate_last_10_ticks` | f64 | ⚠️ Placeholder | Medium |
| `system_throughput_guidance_fraction_by_tick` | f64 | ⚠️ Placeholder | Medium |

**Tests Needed:**
```rust
// Pressure index edge cases
#[test] fn test_queue2_pressure_index_empty_system();
#[test] fn test_queue2_pressure_index_single_agent_system();
#[test] fn test_queue2_pressure_index_sigmoid_curve_shape();
#[test] fn test_queue2_pressure_index_never_exceeds_one();

// Placeholder field documentation tests
#[test] fn test_lsm_run_rate_currently_returns_zero();
#[test] fn test_throughput_guidance_currently_returns_zero();
```

### Category 8: Throughput Progress Fields (3 fields)

| Field | Type | Test Coverage | Priority |
|-------|------|--------------|----------|
| `my_throughput_fraction_today` | f64 | ⚠️ Basic | High |
| `expected_throughput_fraction_by_now` | f64 | ✅ Good | High |
| `throughput_gap` | f64 | ✅ Good | High |

**Tests Needed:**
```rust
// Throughput calculation
#[test] fn test_throughput_fraction_no_transactions();
#[test] fn test_throughput_fraction_all_settled();
#[test] fn test_throughput_fraction_partial_settlement();
#[test] fn test_throughput_gap_behind_schedule();
#[test] fn test_throughput_gap_ahead_schedule();
#[test] fn test_throughput_gap_on_schedule();
#[test] fn test_expected_throughput_linear_model();
```

### Category 9: Counterparty Fields (2 fields)

| Field | Type | Test Coverage | Priority |
|-------|------|--------------|----------|
| `tx_counterparty_id` | u64→f64 | ✅ Good | Medium |
| `tx_is_top_counterparty` | f64 (0/1) | ⚠️ Partial | Medium |

**Tests Needed:**
```rust
// Counterparty identification
#[test] fn test_tx_counterparty_id_consistent_across_builds();
#[test] fn test_tx_is_top_counterparty_with_history();
#[test] fn test_tx_is_top_counterparty_no_history();
```

### Category 10: Dynamic State Registers

| Pattern | Type | Test Coverage | Priority |
|---------|------|--------------|----------|
| `bank_state_*` | f64 | ✅ Good | High |

**Additional Tests Needed:**
```rust
// State register in context
#[test] fn test_state_register_appears_in_context();
#[test] fn test_state_register_default_zero_in_context();
#[test] fn test_state_register_updated_value_in_context();
#[test] fn test_state_register_persists_across_context_builds();
#[test] fn test_multiple_state_registers_in_context();
```

---

## New Test Files to Create

### 1. `backend/tests/test_evalcontext_comprehensive.rs`

Master test file that validates ALL fields exist and have correct types.

```rust
//! Comprehensive EvalContext Field Validation Tests
//!
//! This file ensures every single EvalContext field:
//! 1. Exists and is accessible
//! 2. Returns the correct type (f64)
//! 3. Has reasonable value ranges
//! 4. Is documented

use payment_simulator_core_rs::{Agent, SimulationState, Transaction};
use payment_simulator_core_rs::policy::tree::EvalContext;
use payment_simulator_core_rs::orchestrator::CostRates;

/// Complete list of all 94+ expected fields
const EXPECTED_TRANSACTION_FIELDS: &[&str] = &[
    "amount", "remaining_amount", "settled_amount",
    "arrival_tick", "deadline_tick", "priority",
    "is_split", "is_past_deadline", "is_overdue", "overdue_duration",
    "ticks_to_deadline", "queue_age",
];

const EXPECTED_AGENT_FIELDS: &[&str] = &[
    "balance", "credit_limit", "available_liquidity", "credit_used",
    "effective_liquidity", "is_using_credit", "liquidity_buffer",
    "outgoing_queue_size", "incoming_expected_count", "liquidity_pressure",
    "credit_headroom", "is_overdraft_capped",
];

const EXPECTED_COLLATERAL_FIELDS: &[&str] = &[
    "posted_collateral", "max_collateral_capacity", "remaining_collateral_capacity",
    "collateral_utilization", "queue1_liquidity_gap", "queue1_total_value",
    "headroom", "queue2_size", "queue2_count_for_agent", "queue2_nearest_deadline",
    "ticks_to_nearest_queue2_deadline", "allowed_overdraft_limit",
    "overdraft_headroom", "collateral_haircut", "unsecured_cap",
    "required_collateral_for_usage", "excess_collateral", "overdraft_utilization",
];

const EXPECTED_COST_FIELDS: &[&str] = &[
    "cost_overdraft_bps_per_tick", "cost_delay_per_tick_per_cent",
    "cost_collateral_bps_per_tick", "cost_split_friction",
    "cost_deadline_penalty", "cost_eod_penalty",
    "cost_delay_this_tx_one_tick", "cost_overdraft_this_amount_one_tick",
];

const EXPECTED_SYSTEM_FIELDS: &[&str] = &[
    "current_tick", "rtgs_queue_size", "rtgs_queue_value", "total_agents",
    "system_ticks_per_day", "system_current_day", "system_tick_in_day",
    "ticks_remaining_in_day", "day_progress_fraction", "is_eod_rush",
];

const EXPECTED_LSM_FIELDS: &[&str] = &[
    "my_q2_out_value_to_counterparty", "my_q2_in_value_from_counterparty",
    "my_bilateral_net_q2",
    "my_q2_out_value_top_1", "my_q2_out_value_top_2", "my_q2_out_value_top_3",
    "my_q2_out_value_top_4", "my_q2_out_value_top_5",
    "my_q2_in_value_top_1", "my_q2_in_value_top_2", "my_q2_in_value_top_3",
    "my_q2_in_value_top_4", "my_q2_in_value_top_5",
    "my_bilateral_net_q2_top_1", "my_bilateral_net_q2_top_2",
    "my_bilateral_net_q2_top_3", "my_bilateral_net_q2_top_4",
    "my_bilateral_net_q2_top_5",
    "top_cpty_1_id_hash", "top_cpty_2_id_hash", "top_cpty_3_id_hash",
    "top_cpty_4_id_hash", "top_cpty_5_id_hash",
];

const EXPECTED_PUBLIC_SIGNAL_FIELDS: &[&str] = &[
    "system_queue2_pressure_index",
    "lsm_run_rate_last_10_ticks",
    "system_throughput_guidance_fraction_by_tick",
];

const EXPECTED_THROUGHPUT_FIELDS: &[&str] = &[
    "my_throughput_fraction_today",
    "expected_throughput_fraction_by_now",
    "throughput_gap",
];

const EXPECTED_COUNTERPARTY_FIELDS: &[&str] = &[
    "tx_counterparty_id",
    "tx_is_top_counterparty",
];

#[test]
fn test_all_transaction_fields_exist() {
    let context = create_standard_test_context();
    for field in EXPECTED_TRANSACTION_FIELDS {
        assert!(
            context.get_field(field).is_ok(),
            "Transaction field '{}' should exist", field
        );
    }
}

#[test]
fn test_all_agent_fields_exist() {
    let context = create_standard_test_context();
    for field in EXPECTED_AGENT_FIELDS {
        assert!(
            context.get_field(field).is_ok(),
            "Agent field '{}' should exist", field
        );
    }
}

#[test]
fn test_all_collateral_fields_exist() {
    let context = create_standard_test_context();
    for field in EXPECTED_COLLATERAL_FIELDS {
        assert!(
            context.get_field(field).is_ok(),
            "Collateral field '{}' should exist", field
        );
    }
}

// ... continue for all categories ...

fn create_standard_test_context() -> EvalContext {
    let agent = Agent::new("BANK_A".to_string(), 1_000_000);
    let tx = Transaction::new(
        "BANK_A".to_string(),
        "BANK_B".to_string(),
        100_000,
        10,
        100,
    );
    let state = SimulationState::new(vec![
        agent.clone(),
        Agent::new("BANK_B".to_string(), 1_000_000),
    ]);
    let cost_rates = CostRates::default();

    EvalContext::build(&tx, &agent, &state, 50, &cost_rates, 100, 0.8)
}
```

### 2. `backend/tests/test_evalcontext_edge_cases.rs`

Edge case testing for all fields.

```rust
//! Edge Case Tests for EvalContext Fields
//!
//! Tests boundary conditions, zero values, negative values,
//! infinity, and other edge cases.

// === Division by Zero Protection ===
#[test]
fn test_collateral_utilization_zero_capacity() {
    // max_collateral_capacity = 0 should give utilization = 0, not panic
}

#[test]
fn test_overdraft_utilization_zero_limit() {
    // allowed_overdraft_limit = 0 should give utilization = 0, not panic
}

#[test]
fn test_day_progress_zero_ticks_per_day() {
    // ticks_per_day = 0 should give progress = 0, not panic
}

#[test]
fn test_throughput_fraction_zero_total_due() {
    // total_due = 0 should give fraction = 0, not panic
}

// === Infinity Handling ===
#[test]
fn test_ticks_to_nearest_queue2_deadline_infinity() {
    // When no transactions in Q2, should be f64::INFINITY
}

// === Negative Values ===
#[test]
fn test_ticks_to_deadline_deeply_negative() {
    // 1000 ticks past deadline
}

#[test]
fn test_credit_headroom_negative() {
    // When agent has exceeded credit limit
}

#[test]
fn test_headroom_negative() {
    // When Queue 1 value exceeds available liquidity
}

#[test]
fn test_throughput_gap_negative() {
    // Behind schedule
}

// === Boolean Fields Strict 0/1 ===
#[test]
fn test_is_split_only_zero_or_one() {
    // Should never be 0.5 or other values
}

#[test]
fn test_is_past_deadline_only_zero_or_one();
#[test]
fn test_is_overdue_only_zero_or_one();
#[test]
fn test_is_using_credit_only_zero_or_one();
#[test]
fn test_is_overdraft_capped_only_zero_or_one();
#[test]
fn test_is_eod_rush_only_zero_or_one();
#[test]
fn test_tx_is_top_counterparty_only_zero_or_one();

// === Large Values ===
#[test]
fn test_amount_max_safe_integer() {
    // i64::MAX / 2 or similar large value
}

#[test]
fn test_tick_very_large_number() {
    // Multi-year simulation
}

// === Zero Values ===
#[test]
fn test_all_zero_agent_scenario() {
    // Agent with zero balance, zero credit, zero collateral
}

#[test]
fn test_zero_amount_transaction();
#[test]
fn test_zero_priority_transaction();
```

### 3. `backend/tests/test_evalcontext_bank_level.rs`

Specific tests for the `bank_level()` method (no transaction context).

```rust
//! Tests for EvalContext::bank_level() method
//!
//! bank_level() creates context without a specific transaction,
//! used for bank-wide policy decisions like budget setting.

#[test]
fn test_bank_level_excludes_transaction_fields() {
    let context = create_bank_level_context();

    // Transaction-specific fields should not exist
    assert!(context.get_field("amount").is_err());
    assert!(context.get_field("remaining_amount").is_err());
    assert!(context.get_field("deadline_tick").is_err());
    assert!(context.get_field("ticks_to_deadline").is_err());
}

#[test]
fn test_bank_level_includes_agent_fields() {
    let context = create_bank_level_context();

    // Agent fields should exist
    assert!(context.get_field("balance").is_ok());
    assert!(context.get_field("credit_headroom").is_ok());
    assert!(context.get_field("effective_liquidity").is_ok());
}

#[test]
fn test_bank_level_includes_system_fields() {
    let context = create_bank_level_context();

    // System fields should exist
    assert!(context.get_field("current_tick").is_ok());
    assert!(context.get_field("day_progress_fraction").is_ok());
    assert!(context.get_field("is_eod_rush").is_ok());
}

#[test]
fn test_bank_level_includes_throughput_fields() {
    let context = create_bank_level_context();

    // Throughput fields should exist for bank-level decisions
    assert!(context.get_field("my_throughput_fraction_today").is_ok());
    assert!(context.get_field("throughput_gap").is_ok());
}

#[test]
fn test_bank_level_field_values_match_build() {
    // For fields that exist in both, values should match
    let agent = Agent::new("BANK_A".to_string(), 500_000);
    let state = SimulationState::new(vec![agent.clone()]);
    let cost_rates = CostRates::default();

    let bank_context = EvalContext::bank_level(&agent, &state, 50, &cost_rates, 100, 0.8);

    let tx = Transaction::new("BANK_A".to_string(), "BANK_B".to_string(), 10000, 0, 100);
    let tx_context = EvalContext::build(&tx, &agent, &state, 50, &cost_rates, 100, 0.8);

    // Agent fields should match
    assert_eq!(
        bank_context.get_field("balance").unwrap(),
        tx_context.get_field("balance").unwrap()
    );
    assert_eq!(
        bank_context.get_field("credit_headroom").unwrap(),
        tx_context.get_field("credit_headroom").unwrap()
    );
}
```

### 4. `backend/tests/test_evalcontext_collateral_fields.rs`

Comprehensive collateral field testing.

```rust
//! Comprehensive Collateral Field Tests
//!
//! Tests all 19 collateral-related fields with various scenarios.

// === Basic Collateral State ===
#[test]
fn test_posted_collateral_initial_zero();
#[test]
fn test_posted_collateral_after_posting();
#[test]
fn test_max_collateral_capacity_default_100_million();
#[test]
fn test_remaining_collateral_capacity_computation();

// === Utilization Ratio ===
#[test]
fn test_collateral_utilization_zero_when_nothing_posted();
#[test]
fn test_collateral_utilization_fifty_percent();
#[test]
fn test_collateral_utilization_at_capacity();
#[test]
fn test_collateral_utilization_zero_capacity_edge_case();

// === Queue 1 Metrics ===
#[test]
fn test_queue1_liquidity_gap_positive_shortfall();
#[test]
fn test_queue1_liquidity_gap_negative_surplus();
#[test]
fn test_queue1_liquidity_gap_zero_exact_match();
#[test]
fn test_queue1_total_value_empty();
#[test]
fn test_queue1_total_value_multiple_transactions();
#[test]
fn test_queue1_total_value_after_partial_settlement();

// === Headroom ===
#[test]
fn test_headroom_positive_surplus();
#[test]
fn test_headroom_negative_deficit();
#[test]
fn test_headroom_zero_exact();
#[test]
fn test_headroom_with_collateral();

// === Queue 2 Metrics ===
#[test]
fn test_queue2_size_total_system();
#[test]
fn test_queue2_count_for_agent_only_this_agent();
#[test]
fn test_queue2_nearest_deadline_finds_minimum();
#[test]
fn test_queue2_nearest_deadline_max_when_empty();

// === T2/CLM-Style Fields ===
#[test]
fn test_allowed_overdraft_limit_unsecured_only();
#[test]
fn test_allowed_overdraft_limit_with_collateral_haircut();
#[test]
fn test_overdraft_headroom_remaining_capacity();
#[test]
fn test_collateral_haircut_applied_correctly();
#[test]
fn test_required_collateral_for_usage_formula();
#[test]
fn test_required_collateral_100_percent_haircut();
#[test]
fn test_excess_collateral_when_over_required();
#[test]
fn test_excess_collateral_zero_when_under();
#[test]
fn test_overdraft_utilization_under_100();
#[test]
fn test_overdraft_utilization_over_100();
```

---

## Test Execution Strategy

### Phase 1: Inventory Validation (Week 1)

1. Create `test_evalcontext_comprehensive.rs`
2. Run tests to verify all 94 fields exist
3. Document any missing fields discovered

### Phase 2: Edge Cases (Week 2)

1. Create `test_evalcontext_edge_cases.rs`
2. Run tests to find edge case bugs
3. Do NOT fix bugs - document them

### Phase 3: Category-Specific Tests (Weeks 3-4)

1. Create/extend category-specific test files
2. Run tests for each category
3. Document failures

### Phase 4: Integration Testing (Week 5)

1. Test fields in combination
2. Test with realistic scenarios
3. Test with policy trees that use conditions

---

## TDD Principles Applied

### 1. Write Tests First

All new tests should be written BEFORE any implementation changes.

### 2. Tests Document Expected Behavior

```rust
/// GIVEN an agent at exactly their credit limit
/// WHEN we build an EvalContext
/// THEN credit_headroom should be exactly 0.0
#[test]
fn test_credit_headroom_at_exact_limit() {
    // Arrange
    let mut agent = Agent::new("A".to_string(), -50_000);
    agent.set_unsecured_cap(50_000);

    // Act
    let context = EvalContext::build(...);

    // Assert
    assert_eq!(context.get_field("credit_headroom").unwrap(), 0.0);
}
```

### 3. Red-Green-Refactor

1. **Red**: Write a failing test
2. **Green**: Write minimal code to pass (NOT IN THIS PHASE)
3. **Refactor**: Improve without changing behavior (NOT IN THIS PHASE)

For this review phase, we ONLY do step 1 - write tests and document failures.

### 4. Test Independence

Each test should:
- Set up its own state
- Not depend on other tests
- Clean up after itself

### 5. Descriptive Test Names

```rust
#[test]
fn test_credit_headroom_negative_when_agent_exceeds_credit_limit()

#[test]
fn test_ticks_to_deadline_returns_negative_1000_when_1000_ticks_past_deadline()

#[test]
fn test_is_eod_rush_returns_1_when_day_progress_equals_threshold()
```

---

## Validation Checklist

For each field, verify:

- [ ] Field exists in `build()` method
- [ ] Field exists in `bank_level()` method (if applicable)
- [ ] Field has correct type (f64)
- [ ] Field has correct value range
- [ ] Field handles zero/empty cases
- [ ] Field handles edge cases
- [ ] Field has documentation in struct docstring
- [ ] Field has at least 3 test cases

---

## Expected Outcomes

After completing this test plan:

1. **Complete inventory** of all EvalContext fields
2. **Edge case coverage** for all fields
3. **Documentation** of any implementation bugs found
4. **Regression test suite** for future changes
5. **Confidence** that policy conditions work correctly

---

## Appendix: Running the Tests

```bash
# Run all context tests
cargo test --no-default-features context

# Run comprehensive tests
cargo test --no-default-features test_evalcontext_comprehensive

# Run edge case tests
cargo test --no-default-features test_evalcontext_edge_cases

# Run with verbose output
cargo test --no-default-features -- --nocapture

# Run specific test
cargo test --no-default-features test_credit_headroom_at_exact_limit
```
