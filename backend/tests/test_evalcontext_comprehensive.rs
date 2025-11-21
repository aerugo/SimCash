//! Comprehensive EvalContext Field Validation Tests
//!
//! This file ensures every single EvalContext field:
//! 1. Exists and is accessible
//! 2. Returns the correct type (f64)
//! 3. Has reasonable value ranges
//!
//! TDD Approach: These tests document expected behavior. If tests fail
//! due to erroneous implementation, the test is the source of truth.

use payment_simulator_core_rs::orchestrator::CostRates;
use payment_simulator_core_rs::policy::tree::EvalContext;
use payment_simulator_core_rs::{Agent, SimulationState, Transaction};

// ============================================================================
// Test Helpers
// ============================================================================

fn create_agent(id: &str, balance: i64, unsecured_cap: i64) -> Agent {
    let mut agent = Agent::new(id.to_string(), balance);
    agent.set_unsecured_cap(unsecured_cap);
    agent
}

fn create_tx(sender: &str, receiver: &str, amount: i64, arrival: usize, deadline: usize) -> Transaction {
    Transaction::new(
        sender.to_string(),
        receiver.to_string(),
        amount,
        arrival,
        deadline,
    )
}

fn create_standard_test_context() -> EvalContext {
    let agent = create_agent("BANK_A", 1_000_000, 500_000);
    let tx = create_tx("BANK_A", "BANK_B", 100_000, 10, 100);
    let state = SimulationState::new(vec![
        agent.clone(),
        create_agent("BANK_B", 1_000_000, 500_000),
    ]);
    let cost_rates = CostRates::default();

    EvalContext::build(&tx, &agent, &state, 50, &cost_rates, 100, 0.8)
}

fn create_bank_level_test_context() -> EvalContext {
    let agent = create_agent("BANK_A", 1_000_000, 500_000);
    let state = SimulationState::new(vec![
        agent.clone(),
        create_agent("BANK_B", 1_000_000, 500_000),
    ]);
    let cost_rates = CostRates::default();

    EvalContext::bank_level(&agent, &state, 50, &cost_rates, 100, 0.8)
}

// ============================================================================
// Category 1: Transaction Fields (12 fields)
// ============================================================================

#[test]
fn test_transaction_field_amount_exists() {
    let context = create_standard_test_context();
    let result = context.get_field("amount");
    assert!(result.is_ok(), "Field 'amount' should exist");
    assert_eq!(result.unwrap(), 100_000.0);
}

#[test]
fn test_transaction_field_remaining_amount_exists() {
    let context = create_standard_test_context();
    let result = context.get_field("remaining_amount");
    assert!(result.is_ok(), "Field 'remaining_amount' should exist");
    assert_eq!(result.unwrap(), 100_000.0);
}

#[test]
fn test_transaction_field_settled_amount_exists() {
    let context = create_standard_test_context();
    let result = context.get_field("settled_amount");
    assert!(result.is_ok(), "Field 'settled_amount' should exist");
    assert_eq!(result.unwrap(), 0.0); // Not settled yet
}

#[test]
fn test_transaction_field_arrival_tick_exists() {
    let context = create_standard_test_context();
    let result = context.get_field("arrival_tick");
    assert!(result.is_ok(), "Field 'arrival_tick' should exist");
    assert_eq!(result.unwrap(), 10.0);
}

#[test]
fn test_transaction_field_deadline_tick_exists() {
    let context = create_standard_test_context();
    let result = context.get_field("deadline_tick");
    assert!(result.is_ok(), "Field 'deadline_tick' should exist");
    assert_eq!(result.unwrap(), 100.0);
}

#[test]
fn test_transaction_field_priority_exists() {
    let context = create_standard_test_context();
    let result = context.get_field("priority");
    assert!(result.is_ok(), "Field 'priority' should exist");
    // Default priority is 0
}

#[test]
fn test_transaction_field_is_split_exists() {
    let context = create_standard_test_context();
    let result = context.get_field("is_split");
    assert!(result.is_ok(), "Field 'is_split' should exist");
    assert_eq!(result.unwrap(), 0.0); // Not a split transaction
}

#[test]
fn test_transaction_field_is_past_deadline_exists() {
    let context = create_standard_test_context();
    let result = context.get_field("is_past_deadline");
    assert!(result.is_ok(), "Field 'is_past_deadline' should exist");
    assert_eq!(result.unwrap(), 0.0); // tick 50 < deadline 100
}

#[test]
fn test_transaction_field_is_overdue_exists() {
    let context = create_standard_test_context();
    let result = context.get_field("is_overdue");
    assert!(result.is_ok(), "Field 'is_overdue' should exist");
    assert_eq!(result.unwrap(), 0.0); // Not overdue
}

#[test]
fn test_transaction_field_overdue_duration_exists() {
    let context = create_standard_test_context();
    let result = context.get_field("overdue_duration");
    assert!(result.is_ok(), "Field 'overdue_duration' should exist");
    assert_eq!(result.unwrap(), 0.0); // Not overdue, so 0
}

#[test]
fn test_transaction_field_ticks_to_deadline_exists() {
    let context = create_standard_test_context();
    let result = context.get_field("ticks_to_deadline");
    assert!(result.is_ok(), "Field 'ticks_to_deadline' should exist");
    // tick 50, deadline 100 -> 50 ticks to deadline
    assert_eq!(result.unwrap(), 50.0);
}

#[test]
fn test_transaction_field_queue_age_exists() {
    let context = create_standard_test_context();
    let result = context.get_field("queue_age");
    assert!(result.is_ok(), "Field 'queue_age' should exist");
    // tick 50, arrival 10 -> 40 ticks in queue
    assert_eq!(result.unwrap(), 40.0);
}

// ============================================================================
// Category 2: Agent Fields (12 fields)
// ============================================================================

#[test]
fn test_agent_field_balance_exists() {
    let context = create_standard_test_context();
    let result = context.get_field("balance");
    assert!(result.is_ok(), "Field 'balance' should exist");
    assert_eq!(result.unwrap(), 1_000_000.0);
}

#[test]
fn test_agent_field_credit_limit_exists() {
    let context = create_standard_test_context();
    let result = context.get_field("credit_limit");
    assert!(result.is_ok(), "Field 'credit_limit' should exist");
    assert_eq!(result.unwrap(), 500_000.0);
}

#[test]
fn test_agent_field_available_liquidity_exists() {
    let context = create_standard_test_context();
    let result = context.get_field("available_liquidity");
    assert!(result.is_ok(), "Field 'available_liquidity' should exist");
    // balance + credit_limit = 1,000,000 + 500,000 = 1,500,000
    assert_eq!(result.unwrap(), 1_500_000.0);
}

#[test]
fn test_agent_field_credit_used_exists() {
    let context = create_standard_test_context();
    let result = context.get_field("credit_used");
    assert!(result.is_ok(), "Field 'credit_used' should exist");
    assert_eq!(result.unwrap(), 0.0); // No credit used
}

#[test]
fn test_agent_field_effective_liquidity_exists() {
    let context = create_standard_test_context();
    let result = context.get_field("effective_liquidity");
    assert!(result.is_ok(), "Field 'effective_liquidity' should exist");
    // balance + credit_headroom = 1,000,000 + 500,000 = 1,500,000
    assert_eq!(result.unwrap(), 1_500_000.0);
}

#[test]
fn test_agent_field_is_using_credit_exists() {
    let context = create_standard_test_context();
    let result = context.get_field("is_using_credit");
    assert!(result.is_ok(), "Field 'is_using_credit' should exist");
    assert_eq!(result.unwrap(), 0.0); // Not using credit
}

#[test]
fn test_agent_field_liquidity_buffer_exists() {
    let context = create_standard_test_context();
    let result = context.get_field("liquidity_buffer");
    assert!(result.is_ok(), "Field 'liquidity_buffer' should exist");
}

#[test]
fn test_agent_field_outgoing_queue_size_exists() {
    let context = create_standard_test_context();
    let result = context.get_field("outgoing_queue_size");
    assert!(result.is_ok(), "Field 'outgoing_queue_size' should exist");
}

#[test]
fn test_agent_field_incoming_expected_count_exists() {
    let context = create_standard_test_context();
    let result = context.get_field("incoming_expected_count");
    assert!(result.is_ok(), "Field 'incoming_expected_count' should exist");
}

#[test]
fn test_agent_field_liquidity_pressure_exists() {
    let context = create_standard_test_context();
    let result = context.get_field("liquidity_pressure");
    assert!(result.is_ok(), "Field 'liquidity_pressure' should exist");
}

#[test]
fn test_agent_field_credit_headroom_exists() {
    let context = create_standard_test_context();
    let result = context.get_field("credit_headroom");
    assert!(result.is_ok(), "Field 'credit_headroom' should exist");
    // credit_limit - credit_used = 500,000 - 0 = 500,000
    assert_eq!(result.unwrap(), 500_000.0);
}

#[test]
fn test_agent_field_is_overdraft_capped_exists() {
    let context = create_standard_test_context();
    let result = context.get_field("is_overdraft_capped");
    assert!(result.is_ok(), "Field 'is_overdraft_capped' should exist");
    assert_eq!(result.unwrap(), 1.0); // Always 1.0 in Option B
}

// ============================================================================
// Category 3: Collateral Fields (19 fields)
// ============================================================================

#[test]
fn test_collateral_field_posted_collateral_exists() {
    let context = create_standard_test_context();
    let result = context.get_field("posted_collateral");
    assert!(result.is_ok(), "Field 'posted_collateral' should exist");
}

#[test]
fn test_collateral_field_max_collateral_capacity_exists() {
    let context = create_standard_test_context();
    let result = context.get_field("max_collateral_capacity");
    assert!(result.is_ok(), "Field 'max_collateral_capacity' should exist");
}

#[test]
fn test_collateral_field_remaining_collateral_capacity_exists() {
    let context = create_standard_test_context();
    let result = context.get_field("remaining_collateral_capacity");
    assert!(result.is_ok(), "Field 'remaining_collateral_capacity' should exist");
}

#[test]
fn test_collateral_field_collateral_utilization_exists() {
    let context = create_standard_test_context();
    let result = context.get_field("collateral_utilization");
    assert!(result.is_ok(), "Field 'collateral_utilization' should exist");
}

#[test]
fn test_collateral_field_queue1_liquidity_gap_exists() {
    let context = create_standard_test_context();
    let result = context.get_field("queue1_liquidity_gap");
    assert!(result.is_ok(), "Field 'queue1_liquidity_gap' should exist");
}

#[test]
fn test_collateral_field_queue1_total_value_exists() {
    let context = create_standard_test_context();
    let result = context.get_field("queue1_total_value");
    assert!(result.is_ok(), "Field 'queue1_total_value' should exist");
}

#[test]
fn test_collateral_field_headroom_exists() {
    let context = create_standard_test_context();
    let result = context.get_field("headroom");
    assert!(result.is_ok(), "Field 'headroom' should exist");
}

#[test]
fn test_collateral_field_queue2_size_exists() {
    let context = create_standard_test_context();
    let result = context.get_field("queue2_size");
    assert!(result.is_ok(), "Field 'queue2_size' should exist");
}

#[test]
fn test_collateral_field_queue2_count_for_agent_exists() {
    let context = create_standard_test_context();
    let result = context.get_field("queue2_count_for_agent");
    assert!(result.is_ok(), "Field 'queue2_count_for_agent' should exist");
}

#[test]
fn test_collateral_field_queue2_nearest_deadline_exists() {
    let context = create_standard_test_context();
    let result = context.get_field("queue2_nearest_deadline");
    assert!(result.is_ok(), "Field 'queue2_nearest_deadline' should exist");
}

#[test]
fn test_collateral_field_ticks_to_nearest_queue2_deadline_exists() {
    let context = create_standard_test_context();
    let result = context.get_field("ticks_to_nearest_queue2_deadline");
    assert!(result.is_ok(), "Field 'ticks_to_nearest_queue2_deadline' should exist");
}

#[test]
fn test_collateral_field_allowed_overdraft_limit_exists() {
    let context = create_standard_test_context();
    let result = context.get_field("allowed_overdraft_limit");
    assert!(result.is_ok(), "Field 'allowed_overdraft_limit' should exist");
}

#[test]
fn test_collateral_field_overdraft_headroom_exists() {
    let context = create_standard_test_context();
    let result = context.get_field("overdraft_headroom");
    assert!(result.is_ok(), "Field 'overdraft_headroom' should exist");
}

#[test]
fn test_collateral_field_collateral_haircut_exists() {
    let context = create_standard_test_context();
    let result = context.get_field("collateral_haircut");
    assert!(result.is_ok(), "Field 'collateral_haircut' should exist");
}

#[test]
fn test_collateral_field_unsecured_cap_exists() {
    let context = create_standard_test_context();
    let result = context.get_field("unsecured_cap");
    assert!(result.is_ok(), "Field 'unsecured_cap' should exist");
}

#[test]
fn test_collateral_field_required_collateral_for_usage_exists() {
    let context = create_standard_test_context();
    let result = context.get_field("required_collateral_for_usage");
    assert!(result.is_ok(), "Field 'required_collateral_for_usage' should exist");
}

#[test]
fn test_collateral_field_excess_collateral_exists() {
    let context = create_standard_test_context();
    let result = context.get_field("excess_collateral");
    assert!(result.is_ok(), "Field 'excess_collateral' should exist");
}

#[test]
fn test_collateral_field_overdraft_utilization_exists() {
    let context = create_standard_test_context();
    let result = context.get_field("overdraft_utilization");
    assert!(result.is_ok(), "Field 'overdraft_utilization' should exist");
}

// ============================================================================
// Category 4: Cost Fields (8 fields)
// ============================================================================

#[test]
fn test_cost_field_cost_overdraft_bps_per_tick_exists() {
    let context = create_standard_test_context();
    let result = context.get_field("cost_overdraft_bps_per_tick");
    assert!(result.is_ok(), "Field 'cost_overdraft_bps_per_tick' should exist");
}

#[test]
fn test_cost_field_cost_delay_per_tick_per_cent_exists() {
    let context = create_standard_test_context();
    let result = context.get_field("cost_delay_per_tick_per_cent");
    assert!(result.is_ok(), "Field 'cost_delay_per_tick_per_cent' should exist");
}

#[test]
fn test_cost_field_cost_collateral_bps_per_tick_exists() {
    let context = create_standard_test_context();
    let result = context.get_field("cost_collateral_bps_per_tick");
    assert!(result.is_ok(), "Field 'cost_collateral_bps_per_tick' should exist");
}

#[test]
fn test_cost_field_cost_split_friction_exists() {
    let context = create_standard_test_context();
    let result = context.get_field("cost_split_friction");
    assert!(result.is_ok(), "Field 'cost_split_friction' should exist");
}

#[test]
fn test_cost_field_cost_deadline_penalty_exists() {
    let context = create_standard_test_context();
    let result = context.get_field("cost_deadline_penalty");
    assert!(result.is_ok(), "Field 'cost_deadline_penalty' should exist");
}

#[test]
fn test_cost_field_cost_eod_penalty_exists() {
    let context = create_standard_test_context();
    let result = context.get_field("cost_eod_penalty");
    assert!(result.is_ok(), "Field 'cost_eod_penalty' should exist");
}

#[test]
fn test_cost_field_cost_delay_this_tx_one_tick_exists() {
    let context = create_standard_test_context();
    let result = context.get_field("cost_delay_this_tx_one_tick");
    assert!(result.is_ok(), "Field 'cost_delay_this_tx_one_tick' should exist");
}

#[test]
fn test_cost_field_cost_overdraft_this_amount_one_tick_exists() {
    let context = create_standard_test_context();
    let result = context.get_field("cost_overdraft_this_amount_one_tick");
    assert!(result.is_ok(), "Field 'cost_overdraft_this_amount_one_tick' should exist");
}

// ============================================================================
// Category 5: System Configuration Fields (6 fields)
// ============================================================================

#[test]
fn test_system_field_current_tick_exists() {
    let context = create_standard_test_context();
    let result = context.get_field("current_tick");
    assert!(result.is_ok(), "Field 'current_tick' should exist");
    assert_eq!(result.unwrap(), 50.0);
}

#[test]
fn test_system_field_rtgs_queue_size_exists() {
    let context = create_standard_test_context();
    let result = context.get_field("rtgs_queue_size");
    assert!(result.is_ok(), "Field 'rtgs_queue_size' should exist");
}

#[test]
fn test_system_field_rtgs_queue_value_exists() {
    let context = create_standard_test_context();
    let result = context.get_field("rtgs_queue_value");
    assert!(result.is_ok(), "Field 'rtgs_queue_value' should exist");
}

#[test]
fn test_system_field_total_agents_exists() {
    let context = create_standard_test_context();
    let result = context.get_field("total_agents");
    assert!(result.is_ok(), "Field 'total_agents' should exist");
    assert_eq!(result.unwrap(), 2.0);
}

#[test]
fn test_system_field_system_ticks_per_day_exists() {
    let context = create_standard_test_context();
    let result = context.get_field("system_ticks_per_day");
    assert!(result.is_ok(), "Field 'system_ticks_per_day' should exist");
    assert_eq!(result.unwrap(), 100.0);
}

#[test]
fn test_system_field_system_current_day_exists() {
    let context = create_standard_test_context();
    let result = context.get_field("system_current_day");
    assert!(result.is_ok(), "Field 'system_current_day' should exist");
    assert_eq!(result.unwrap(), 0.0); // tick 50 / 100 = day 0
}

#[test]
fn test_system_field_system_tick_in_day_exists() {
    let context = create_standard_test_context();
    let result = context.get_field("system_tick_in_day");
    assert!(result.is_ok(), "Field 'system_tick_in_day' should exist");
    assert_eq!(result.unwrap(), 50.0); // tick 50 % 100 = 50
}

#[test]
fn test_system_field_ticks_remaining_in_day_exists() {
    let context = create_standard_test_context();
    let result = context.get_field("ticks_remaining_in_day");
    assert!(result.is_ok(), "Field 'ticks_remaining_in_day' should exist");
    // 100 - 50 - 1 = 49
    assert_eq!(result.unwrap(), 49.0);
}

#[test]
fn test_system_field_day_progress_fraction_exists() {
    let context = create_standard_test_context();
    let result = context.get_field("day_progress_fraction");
    assert!(result.is_ok(), "Field 'day_progress_fraction' should exist");
    assert_eq!(result.unwrap(), 0.5); // tick 50 / 100 = 0.5
}

#[test]
fn test_system_field_is_eod_rush_exists() {
    let context = create_standard_test_context();
    let result = context.get_field("is_eod_rush");
    assert!(result.is_ok(), "Field 'is_eod_rush' should exist");
    // tick 50, threshold 0.8, progress 0.5 < 0.8 -> not in EOD rush
    assert_eq!(result.unwrap(), 0.0);
}

// ============================================================================
// Category 6: LSM-Aware Fields (25 fields)
// ============================================================================

#[test]
fn test_lsm_field_my_q2_out_value_to_counterparty_exists() {
    let context = create_standard_test_context();
    let result = context.get_field("my_q2_out_value_to_counterparty");
    assert!(result.is_ok(), "Field 'my_q2_out_value_to_counterparty' should exist");
}

#[test]
fn test_lsm_field_my_q2_in_value_from_counterparty_exists() {
    let context = create_standard_test_context();
    let result = context.get_field("my_q2_in_value_from_counterparty");
    assert!(result.is_ok(), "Field 'my_q2_in_value_from_counterparty' should exist");
}

#[test]
fn test_lsm_field_my_bilateral_net_q2_exists() {
    let context = create_standard_test_context();
    let result = context.get_field("my_bilateral_net_q2");
    assert!(result.is_ok(), "Field 'my_bilateral_net_q2' should exist");
}

#[test]
fn test_lsm_field_my_q2_out_value_top_1_exists() {
    let context = create_standard_test_context();
    let result = context.get_field("my_q2_out_value_top_1");
    assert!(result.is_ok(), "Field 'my_q2_out_value_top_1' should exist");
}

#[test]
fn test_lsm_field_my_q2_out_value_top_2_exists() {
    let context = create_standard_test_context();
    let result = context.get_field("my_q2_out_value_top_2");
    assert!(result.is_ok(), "Field 'my_q2_out_value_top_2' should exist");
}

#[test]
fn test_lsm_field_my_q2_out_value_top_3_exists() {
    let context = create_standard_test_context();
    let result = context.get_field("my_q2_out_value_top_3");
    assert!(result.is_ok(), "Field 'my_q2_out_value_top_3' should exist");
}

#[test]
fn test_lsm_field_my_q2_out_value_top_4_exists() {
    let context = create_standard_test_context();
    let result = context.get_field("my_q2_out_value_top_4");
    assert!(result.is_ok(), "Field 'my_q2_out_value_top_4' should exist");
}

#[test]
fn test_lsm_field_my_q2_out_value_top_5_exists() {
    let context = create_standard_test_context();
    let result = context.get_field("my_q2_out_value_top_5");
    assert!(result.is_ok(), "Field 'my_q2_out_value_top_5' should exist");
}

#[test]
fn test_lsm_field_my_q2_in_value_top_1_exists() {
    let context = create_standard_test_context();
    let result = context.get_field("my_q2_in_value_top_1");
    assert!(result.is_ok(), "Field 'my_q2_in_value_top_1' should exist");
}

#[test]
fn test_lsm_field_my_q2_in_value_top_2_exists() {
    let context = create_standard_test_context();
    let result = context.get_field("my_q2_in_value_top_2");
    assert!(result.is_ok(), "Field 'my_q2_in_value_top_2' should exist");
}

#[test]
fn test_lsm_field_my_q2_in_value_top_3_exists() {
    let context = create_standard_test_context();
    let result = context.get_field("my_q2_in_value_top_3");
    assert!(result.is_ok(), "Field 'my_q2_in_value_top_3' should exist");
}

#[test]
fn test_lsm_field_my_q2_in_value_top_4_exists() {
    let context = create_standard_test_context();
    let result = context.get_field("my_q2_in_value_top_4");
    assert!(result.is_ok(), "Field 'my_q2_in_value_top_4' should exist");
}

#[test]
fn test_lsm_field_my_q2_in_value_top_5_exists() {
    let context = create_standard_test_context();
    let result = context.get_field("my_q2_in_value_top_5");
    assert!(result.is_ok(), "Field 'my_q2_in_value_top_5' should exist");
}

#[test]
fn test_lsm_field_my_bilateral_net_q2_top_1_exists() {
    let context = create_standard_test_context();
    let result = context.get_field("my_bilateral_net_q2_top_1");
    assert!(result.is_ok(), "Field 'my_bilateral_net_q2_top_1' should exist");
}

#[test]
fn test_lsm_field_my_bilateral_net_q2_top_2_exists() {
    let context = create_standard_test_context();
    let result = context.get_field("my_bilateral_net_q2_top_2");
    assert!(result.is_ok(), "Field 'my_bilateral_net_q2_top_2' should exist");
}

#[test]
fn test_lsm_field_my_bilateral_net_q2_top_3_exists() {
    let context = create_standard_test_context();
    let result = context.get_field("my_bilateral_net_q2_top_3");
    assert!(result.is_ok(), "Field 'my_bilateral_net_q2_top_3' should exist");
}

#[test]
fn test_lsm_field_my_bilateral_net_q2_top_4_exists() {
    let context = create_standard_test_context();
    let result = context.get_field("my_bilateral_net_q2_top_4");
    assert!(result.is_ok(), "Field 'my_bilateral_net_q2_top_4' should exist");
}

#[test]
fn test_lsm_field_my_bilateral_net_q2_top_5_exists() {
    let context = create_standard_test_context();
    let result = context.get_field("my_bilateral_net_q2_top_5");
    assert!(result.is_ok(), "Field 'my_bilateral_net_q2_top_5' should exist");
}

#[test]
fn test_lsm_field_top_cpty_1_id_hash_exists() {
    let context = create_standard_test_context();
    let result = context.get_field("top_cpty_1_id_hash");
    assert!(result.is_ok(), "Field 'top_cpty_1_id_hash' should exist");
}

#[test]
fn test_lsm_field_top_cpty_2_id_hash_exists() {
    let context = create_standard_test_context();
    let result = context.get_field("top_cpty_2_id_hash");
    assert!(result.is_ok(), "Field 'top_cpty_2_id_hash' should exist");
}

#[test]
fn test_lsm_field_top_cpty_3_id_hash_exists() {
    let context = create_standard_test_context();
    let result = context.get_field("top_cpty_3_id_hash");
    assert!(result.is_ok(), "Field 'top_cpty_3_id_hash' should exist");
}

#[test]
fn test_lsm_field_top_cpty_4_id_hash_exists() {
    let context = create_standard_test_context();
    let result = context.get_field("top_cpty_4_id_hash");
    assert!(result.is_ok(), "Field 'top_cpty_4_id_hash' should exist");
}

#[test]
fn test_lsm_field_top_cpty_5_id_hash_exists() {
    let context = create_standard_test_context();
    let result = context.get_field("top_cpty_5_id_hash");
    assert!(result.is_ok(), "Field 'top_cpty_5_id_hash' should exist");
}

// ============================================================================
// Category 7: Public Signal Fields (3 fields)
// ============================================================================

#[test]
fn test_public_signal_field_system_queue2_pressure_index_exists() {
    let context = create_standard_test_context();
    let result = context.get_field("system_queue2_pressure_index");
    assert!(result.is_ok(), "Field 'system_queue2_pressure_index' should exist");
}

#[test]
fn test_public_signal_field_lsm_run_rate_last_10_ticks_exists() {
    let context = create_standard_test_context();
    let result = context.get_field("lsm_run_rate_last_10_ticks");
    assert!(result.is_ok(), "Field 'lsm_run_rate_last_10_ticks' should exist");
    // Placeholder - currently always 0.0
    assert_eq!(result.unwrap(), 0.0);
}

#[test]
fn test_public_signal_field_system_throughput_guidance_fraction_by_tick_exists() {
    let context = create_standard_test_context();
    let result = context.get_field("system_throughput_guidance_fraction_by_tick");
    assert!(result.is_ok(), "Field 'system_throughput_guidance_fraction_by_tick' should exist");
    // Placeholder - currently always 0.0
    assert_eq!(result.unwrap(), 0.0);
}

// ============================================================================
// Category 8: Throughput Progress Fields (3 fields)
// ============================================================================

#[test]
fn test_throughput_field_my_throughput_fraction_today_exists() {
    let context = create_standard_test_context();
    let result = context.get_field("my_throughput_fraction_today");
    assert!(result.is_ok(), "Field 'my_throughput_fraction_today' should exist");
}

#[test]
fn test_throughput_field_expected_throughput_fraction_by_now_exists() {
    let context = create_standard_test_context();
    let result = context.get_field("expected_throughput_fraction_by_now");
    assert!(result.is_ok(), "Field 'expected_throughput_fraction_by_now' should exist");
    // Linear model: tick 50 / 100 = 0.5
    assert_eq!(result.unwrap(), 0.5);
}

#[test]
fn test_throughput_field_throughput_gap_exists() {
    let context = create_standard_test_context();
    let result = context.get_field("throughput_gap");
    assert!(result.is_ok(), "Field 'throughput_gap' should exist");
}

// ============================================================================
// Category 9: Counterparty Fields (2 fields)
// ============================================================================

#[test]
fn test_counterparty_field_tx_counterparty_id_exists() {
    let context = create_standard_test_context();
    let result = context.get_field("tx_counterparty_id");
    assert!(result.is_ok(), "Field 'tx_counterparty_id' should exist");
}

#[test]
fn test_counterparty_field_tx_is_top_counterparty_exists() {
    let context = create_standard_test_context();
    let result = context.get_field("tx_is_top_counterparty");
    assert!(result.is_ok(), "Field 'tx_is_top_counterparty' should exist");
}

// ============================================================================
// Category 10: Dynamic State Registers
// ============================================================================

#[test]
fn test_state_register_default_to_zero_in_context() {
    let context = create_standard_test_context();

    // Non-existent state register should return 0.0 (not error)
    let result = context.get_field("bank_state_test_register");
    assert!(result.is_ok(), "State registers should default to 0.0");
    assert_eq!(result.unwrap(), 0.0);
}

#[test]
fn test_state_register_appears_in_context_when_set() {
    let mut agent = create_agent("BANK_A", 1_000_000, 500_000);
    agent.set_state_register("bank_state_custom".to_string(), 42.0).unwrap();

    let tx = create_tx("BANK_A", "BANK_B", 100_000, 10, 100);
    let state = SimulationState::new(vec![
        agent.clone(),
        create_agent("BANK_B", 1_000_000, 500_000),
    ]);
    let cost_rates = CostRates::default();

    let context = EvalContext::build(&tx, &agent, &state, 50, &cost_rates, 100, 0.8);

    let result = context.get_field("bank_state_custom");
    assert!(result.is_ok(), "Custom state register should be accessible");
    assert_eq!(result.unwrap(), 42.0);
}

// ============================================================================
// bank_level() Method Tests
// ============================================================================

#[test]
fn test_bank_level_includes_agent_fields() {
    let context = create_bank_level_test_context();

    assert!(context.get_field("balance").is_ok());
    assert!(context.get_field("credit_headroom").is_ok());
    assert!(context.get_field("effective_liquidity").is_ok());
    assert!(context.get_field("is_using_credit").is_ok());
}

#[test]
fn test_bank_level_includes_system_fields() {
    let context = create_bank_level_test_context();

    assert!(context.get_field("current_tick").is_ok());
    assert!(context.get_field("day_progress_fraction").is_ok());
    assert!(context.get_field("is_eod_rush").is_ok());
    assert!(context.get_field("system_ticks_per_day").is_ok());
}

#[test]
fn test_bank_level_includes_throughput_fields() {
    let context = create_bank_level_test_context();

    assert!(context.get_field("my_throughput_fraction_today").is_ok());
    assert!(context.get_field("expected_throughput_fraction_by_now").is_ok());
    assert!(context.get_field("throughput_gap").is_ok());
}

#[test]
fn test_bank_level_includes_collateral_fields() {
    let context = create_bank_level_test_context();

    assert!(context.get_field("posted_collateral").is_ok());
    assert!(context.get_field("collateral_utilization").is_ok());
    assert!(context.get_field("overdraft_headroom").is_ok());
}

#[test]
fn test_bank_level_includes_queue_fields() {
    let context = create_bank_level_test_context();

    assert!(context.get_field("queue1_total_value").is_ok());
    assert!(context.get_field("queue1_liquidity_gap").is_ok());
    assert!(context.get_field("headroom").is_ok());
    assert!(context.get_field("queue2_size").is_ok());
}

// ============================================================================
// Field Count Summary Test
// ============================================================================

#[test]
fn test_total_field_count_at_least_90() {
    let context = create_standard_test_context();
    let field_names = context.field_names();

    assert!(
        field_names.len() >= 90,
        "Expected at least 90 fields, got {}. Fields: {:?}",
        field_names.len(),
        field_names
    );
}
