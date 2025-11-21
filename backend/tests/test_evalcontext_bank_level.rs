//! Tests for EvalContext::bank_level() method
//!
//! bank_level() creates context without a specific transaction,
//! used for bank-wide policy decisions like budget setting.
//!
//! TDD Approach: These tests document expected behavior for bank-level context.

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

fn default_cost_rates() -> CostRates {
    CostRates::default()
}

fn create_bank_level_context(agent: &Agent, state: &SimulationState, tick: usize) -> EvalContext {
    EvalContext::bank_level(agent, state, tick, &default_cost_rates(), 100, 0.8)
}

// ============================================================================
// Agent Field Availability in bank_level()
// ============================================================================

#[test]
fn test_bank_level_has_balance() {
    let agent = create_agent("BANK_A", 1_000_000, 500_000);
    let state = SimulationState::new(vec![agent.clone()]);
    let context = create_bank_level_context(&agent, &state, 50);

    assert!(context.get_field("balance").is_ok());
    assert_eq!(context.get_field("balance").unwrap(), 1_000_000.0);
}

#[test]
fn test_bank_level_has_credit_limit() {
    let agent = create_agent("BANK_A", 1_000_000, 500_000);
    let state = SimulationState::new(vec![agent.clone()]);
    let context = create_bank_level_context(&agent, &state, 50);

    assert!(context.get_field("credit_limit").is_ok());
    assert_eq!(context.get_field("credit_limit").unwrap(), 500_000.0);
}

#[test]
fn test_bank_level_has_available_liquidity() {
    let agent = create_agent("BANK_A", 1_000_000, 500_000);
    let state = SimulationState::new(vec![agent.clone()]);
    let context = create_bank_level_context(&agent, &state, 50);

    assert!(context.get_field("available_liquidity").is_ok());
    assert_eq!(context.get_field("available_liquidity").unwrap(), 1_500_000.0);
}

#[test]
fn test_bank_level_has_credit_used() {
    let agent = create_agent("BANK_A", -30_000, 500_000);
    let state = SimulationState::new(vec![agent.clone()]);
    let context = create_bank_level_context(&agent, &state, 50);

    assert!(context.get_field("credit_used").is_ok());
    assert_eq!(context.get_field("credit_used").unwrap(), 30_000.0);
}

#[test]
fn test_bank_level_has_effective_liquidity() {
    let agent = create_agent("BANK_A", 1_000_000, 500_000);
    let state = SimulationState::new(vec![agent.clone()]);
    let context = create_bank_level_context(&agent, &state, 50);

    assert!(context.get_field("effective_liquidity").is_ok());
    assert_eq!(context.get_field("effective_liquidity").unwrap(), 1_500_000.0);
}

#[test]
fn test_bank_level_has_credit_headroom() {
    let agent = create_agent("BANK_A", -30_000, 500_000);
    let state = SimulationState::new(vec![agent.clone()]);
    let context = create_bank_level_context(&agent, &state, 50);

    assert!(context.get_field("credit_headroom").is_ok());
    // 500k - 30k = 470k
    assert_eq!(context.get_field("credit_headroom").unwrap(), 470_000.0);
}

#[test]
fn test_bank_level_has_is_using_credit() {
    let agent = create_agent("BANK_A", -30_000, 500_000);
    let state = SimulationState::new(vec![agent.clone()]);
    let context = create_bank_level_context(&agent, &state, 50);

    assert!(context.get_field("is_using_credit").is_ok());
    assert_eq!(context.get_field("is_using_credit").unwrap(), 1.0);
}

#[test]
fn test_bank_level_has_liquidity_buffer() {
    let mut agent = Agent::with_buffer("BANK_A".to_string(), 1_000_000, 100_000);
    agent.set_unsecured_cap(500_000);
    let state = SimulationState::new(vec![agent.clone()]);
    let context = create_bank_level_context(&agent, &state, 50);

    assert!(context.get_field("liquidity_buffer").is_ok());
    assert_eq!(context.get_field("liquidity_buffer").unwrap(), 100_000.0);
}

#[test]
fn test_bank_level_has_outgoing_queue_size() {
    let agent = create_agent("BANK_A", 1_000_000, 500_000);
    let state = SimulationState::new(vec![agent.clone()]);
    let context = create_bank_level_context(&agent, &state, 50);

    assert!(context.get_field("outgoing_queue_size").is_ok());
}

#[test]
fn test_bank_level_has_incoming_expected_count() {
    let agent = create_agent("BANK_A", 1_000_000, 500_000);
    let state = SimulationState::new(vec![agent.clone()]);
    let context = create_bank_level_context(&agent, &state, 50);

    assert!(context.get_field("incoming_expected_count").is_ok());
}

#[test]
fn test_bank_level_has_liquidity_pressure() {
    let agent = create_agent("BANK_A", 1_000_000, 500_000);
    let state = SimulationState::new(vec![agent.clone()]);
    let context = create_bank_level_context(&agent, &state, 50);

    assert!(context.get_field("liquidity_pressure").is_ok());
}

#[test]
fn test_bank_level_has_is_overdraft_capped() {
    let agent = create_agent("BANK_A", 1_000_000, 500_000);
    let state = SimulationState::new(vec![agent.clone()]);
    let context = create_bank_level_context(&agent, &state, 50);

    assert!(context.get_field("is_overdraft_capped").is_ok());
    assert_eq!(context.get_field("is_overdraft_capped").unwrap(), 1.0);
}

// ============================================================================
// System Field Availability in bank_level()
// ============================================================================

#[test]
fn test_bank_level_has_current_tick() {
    let agent = create_agent("BANK_A", 1_000_000, 500_000);
    let state = SimulationState::new(vec![agent.clone()]);
    let context = create_bank_level_context(&agent, &state, 50);

    assert!(context.get_field("current_tick").is_ok());
    assert_eq!(context.get_field("current_tick").unwrap(), 50.0);
}

#[test]
fn test_bank_level_has_rtgs_queue_size() {
    let agent = create_agent("BANK_A", 1_000_000, 500_000);
    let state = SimulationState::new(vec![agent.clone()]);
    let context = create_bank_level_context(&agent, &state, 50);

    assert!(context.get_field("rtgs_queue_size").is_ok());
}

#[test]
fn test_bank_level_has_rtgs_queue_value() {
    let agent = create_agent("BANK_A", 1_000_000, 500_000);
    let state = SimulationState::new(vec![agent.clone()]);
    let context = create_bank_level_context(&agent, &state, 50);

    assert!(context.get_field("rtgs_queue_value").is_ok());
}

#[test]
fn test_bank_level_has_total_agents() {
    let agent = create_agent("BANK_A", 1_000_000, 500_000);
    let state = SimulationState::new(vec![
        agent.clone(),
        create_agent("BANK_B", 1_000_000, 500_000),
        create_agent("BANK_C", 1_000_000, 500_000),
    ]);
    let context = create_bank_level_context(&agent, &state, 50);

    assert!(context.get_field("total_agents").is_ok());
    assert_eq!(context.get_field("total_agents").unwrap(), 3.0);
}

#[test]
fn test_bank_level_has_system_ticks_per_day() {
    let agent = create_agent("BANK_A", 1_000_000, 500_000);
    let state = SimulationState::new(vec![agent.clone()]);
    let context = create_bank_level_context(&agent, &state, 50);

    assert!(context.get_field("system_ticks_per_day").is_ok());
    assert_eq!(context.get_field("system_ticks_per_day").unwrap(), 100.0);
}

#[test]
fn test_bank_level_has_system_current_day() {
    let agent = create_agent("BANK_A", 1_000_000, 500_000);
    let state = SimulationState::new(vec![agent.clone()]);
    let context = create_bank_level_context(&agent, &state, 150);

    assert!(context.get_field("system_current_day").is_ok());
    assert_eq!(context.get_field("system_current_day").unwrap(), 1.0);
}

#[test]
fn test_bank_level_has_system_tick_in_day() {
    let agent = create_agent("BANK_A", 1_000_000, 500_000);
    let state = SimulationState::new(vec![agent.clone()]);
    let context = create_bank_level_context(&agent, &state, 150);

    assert!(context.get_field("system_tick_in_day").is_ok());
    assert_eq!(context.get_field("system_tick_in_day").unwrap(), 50.0);
}

#[test]
fn test_bank_level_has_ticks_remaining_in_day() {
    let agent = create_agent("BANK_A", 1_000_000, 500_000);
    let state = SimulationState::new(vec![agent.clone()]);
    let context = create_bank_level_context(&agent, &state, 50);

    assert!(context.get_field("ticks_remaining_in_day").is_ok());
    assert_eq!(context.get_field("ticks_remaining_in_day").unwrap(), 49.0);
}

#[test]
fn test_bank_level_has_day_progress_fraction() {
    let agent = create_agent("BANK_A", 1_000_000, 500_000);
    let state = SimulationState::new(vec![agent.clone()]);
    let context = create_bank_level_context(&agent, &state, 50);

    assert!(context.get_field("day_progress_fraction").is_ok());
    assert_eq!(context.get_field("day_progress_fraction").unwrap(), 0.5);
}

#[test]
fn test_bank_level_has_is_eod_rush() {
    let agent = create_agent("BANK_A", 1_000_000, 500_000);
    let state = SimulationState::new(vec![agent.clone()]);
    let context = create_bank_level_context(&agent, &state, 90);

    assert!(context.get_field("is_eod_rush").is_ok());
    assert_eq!(context.get_field("is_eod_rush").unwrap(), 1.0);
}

// ============================================================================
// Collateral Field Availability in bank_level()
// ============================================================================

#[test]
fn test_bank_level_has_posted_collateral() {
    let agent = create_agent("BANK_A", 1_000_000, 500_000);
    let state = SimulationState::new(vec![agent.clone()]);
    let context = create_bank_level_context(&agent, &state, 50);

    assert!(context.get_field("posted_collateral").is_ok());
}

#[test]
fn test_bank_level_has_max_collateral_capacity() {
    let agent = create_agent("BANK_A", 1_000_000, 500_000);
    let state = SimulationState::new(vec![agent.clone()]);
    let context = create_bank_level_context(&agent, &state, 50);

    assert!(context.get_field("max_collateral_capacity").is_ok());
}

#[test]
fn test_bank_level_has_remaining_collateral_capacity() {
    let agent = create_agent("BANK_A", 1_000_000, 500_000);
    let state = SimulationState::new(vec![agent.clone()]);
    let context = create_bank_level_context(&agent, &state, 50);

    assert!(context.get_field("remaining_collateral_capacity").is_ok());
}

#[test]
fn test_bank_level_has_collateral_utilization() {
    let agent = create_agent("BANK_A", 1_000_000, 500_000);
    let state = SimulationState::new(vec![agent.clone()]);
    let context = create_bank_level_context(&agent, &state, 50);

    assert!(context.get_field("collateral_utilization").is_ok());
}

#[test]
fn test_bank_level_has_queue1_fields() {
    let agent = create_agent("BANK_A", 1_000_000, 500_000);
    let state = SimulationState::new(vec![agent.clone()]);
    let context = create_bank_level_context(&agent, &state, 50);

    assert!(context.get_field("queue1_liquidity_gap").is_ok());
    assert!(context.get_field("queue1_total_value").is_ok());
    assert!(context.get_field("headroom").is_ok());
}

#[test]
fn test_bank_level_has_queue2_fields() {
    let agent = create_agent("BANK_A", 1_000_000, 500_000);
    let state = SimulationState::new(vec![agent.clone()]);
    let context = create_bank_level_context(&agent, &state, 50);

    assert!(context.get_field("queue2_size").is_ok());
    assert!(context.get_field("queue2_count_for_agent").is_ok());
    assert!(context.get_field("queue2_nearest_deadline").is_ok());
    assert!(context.get_field("ticks_to_nearest_queue2_deadline").is_ok());
}

#[test]
fn test_bank_level_has_t2_clm_fields() {
    let agent = create_agent("BANK_A", 1_000_000, 500_000);
    let state = SimulationState::new(vec![agent.clone()]);
    let context = create_bank_level_context(&agent, &state, 50);

    assert!(context.get_field("allowed_overdraft_limit").is_ok());
    assert!(context.get_field("overdraft_headroom").is_ok());
    assert!(context.get_field("collateral_haircut").is_ok());
    assert!(context.get_field("unsecured_cap").is_ok());
    assert!(context.get_field("required_collateral_for_usage").is_ok());
    assert!(context.get_field("excess_collateral").is_ok());
}

// ============================================================================
// Cost Field Availability in bank_level()
// ============================================================================

#[test]
fn test_bank_level_has_cost_fields() {
    let agent = create_agent("BANK_A", 1_000_000, 500_000);
    let state = SimulationState::new(vec![agent.clone()]);
    let context = create_bank_level_context(&agent, &state, 50);

    assert!(context.get_field("cost_overdraft_bps_per_tick").is_ok());
    assert!(context.get_field("cost_delay_per_tick_per_cent").is_ok());
    assert!(context.get_field("cost_collateral_bps_per_tick").is_ok());
    assert!(context.get_field("cost_split_friction").is_ok());
    assert!(context.get_field("cost_deadline_penalty").is_ok());
    assert!(context.get_field("cost_eod_penalty").is_ok());
}

// ============================================================================
// Throughput Field Availability in bank_level()
// ============================================================================

#[test]
fn test_bank_level_has_throughput_fields() {
    let agent = create_agent("BANK_A", 1_000_000, 500_000);
    let state = SimulationState::new(vec![agent.clone()]);
    let context = create_bank_level_context(&agent, &state, 50);

    assert!(context.get_field("my_throughput_fraction_today").is_ok());
    assert!(context.get_field("expected_throughput_fraction_by_now").is_ok());
    assert!(context.get_field("throughput_gap").is_ok());
}

// ============================================================================
// Public Signal Field Availability in bank_level()
// ============================================================================

#[test]
fn test_bank_level_has_public_signal_fields() {
    let agent = create_agent("BANK_A", 1_000_000, 500_000);
    let state = SimulationState::new(vec![agent.clone()]);
    let context = create_bank_level_context(&agent, &state, 50);

    assert!(context.get_field("system_queue2_pressure_index").is_ok());
}

// ============================================================================
// State Register Availability in bank_level()
// ============================================================================

#[test]
fn test_bank_level_has_state_registers() {
    let mut agent = create_agent("BANK_A", 1_000_000, 500_000);
    agent.set_state_register("bank_state_budget".to_string(), 200_000.0).unwrap();
    let state = SimulationState::new(vec![agent.clone()]);
    let context = create_bank_level_context(&agent, &state, 50);

    assert!(context.get_field("bank_state_budget").is_ok());
    assert_eq!(context.get_field("bank_state_budget").unwrap(), 200_000.0);
}

// ============================================================================
// Value Consistency Between build() and bank_level()
// ============================================================================

#[test]
fn test_bank_level_balance_matches_build() {
    let agent = create_agent("BANK_A", 1_000_000, 500_000);
    let state = SimulationState::new(vec![agent.clone()]);
    let tx = create_tx("BANK_A", "BANK_B", 10_000, 0, 100);

    let bank_context = create_bank_level_context(&agent, &state, 50);
    let tx_context = EvalContext::build(&tx, &agent, &state, 50, &default_cost_rates(), 100, 0.8);

    assert_eq!(
        bank_context.get_field("balance").unwrap(),
        tx_context.get_field("balance").unwrap()
    );
}

#[test]
fn test_bank_level_credit_fields_match_build() {
    let agent = create_agent("BANK_A", -30_000, 500_000);
    let state = SimulationState::new(vec![agent.clone()]);
    let tx = create_tx("BANK_A", "BANK_B", 10_000, 0, 100);

    let bank_context = create_bank_level_context(&agent, &state, 50);
    let tx_context = EvalContext::build(&tx, &agent, &state, 50, &default_cost_rates(), 100, 0.8);

    assert_eq!(
        bank_context.get_field("credit_headroom").unwrap(),
        tx_context.get_field("credit_headroom").unwrap()
    );
    assert_eq!(
        bank_context.get_field("credit_used").unwrap(),
        tx_context.get_field("credit_used").unwrap()
    );
    assert_eq!(
        bank_context.get_field("effective_liquidity").unwrap(),
        tx_context.get_field("effective_liquidity").unwrap()
    );
}

#[test]
fn test_bank_level_system_fields_match_build() {
    let agent = create_agent("BANK_A", 1_000_000, 500_000);
    let state = SimulationState::new(vec![agent.clone()]);
    let tx = create_tx("BANK_A", "BANK_B", 10_000, 0, 100);

    let bank_context = create_bank_level_context(&agent, &state, 50);
    let tx_context = EvalContext::build(&tx, &agent, &state, 50, &default_cost_rates(), 100, 0.8);

    assert_eq!(
        bank_context.get_field("current_tick").unwrap(),
        tx_context.get_field("current_tick").unwrap()
    );
    assert_eq!(
        bank_context.get_field("day_progress_fraction").unwrap(),
        tx_context.get_field("day_progress_fraction").unwrap()
    );
    assert_eq!(
        bank_context.get_field("is_eod_rush").unwrap(),
        tx_context.get_field("is_eod_rush").unwrap()
    );
}

#[test]
fn test_bank_level_collateral_fields_match_build() {
    let mut agent = create_agent("BANK_A", 1_000_000, 500_000);
    agent.set_posted_collateral(100_000);
    let state = SimulationState::new(vec![agent.clone()]);
    let tx = create_tx("BANK_A", "BANK_B", 10_000, 0, 100);

    let bank_context = create_bank_level_context(&agent, &state, 50);
    let tx_context = EvalContext::build(&tx, &agent, &state, 50, &default_cost_rates(), 100, 0.8);

    assert_eq!(
        bank_context.get_field("posted_collateral").unwrap(),
        tx_context.get_field("posted_collateral").unwrap()
    );
    assert_eq!(
        bank_context.get_field("collateral_utilization").unwrap(),
        tx_context.get_field("collateral_utilization").unwrap()
    );
}
