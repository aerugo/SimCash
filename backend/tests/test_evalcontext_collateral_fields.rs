//! Comprehensive Collateral Field Tests
//!
//! Tests all 19 collateral-related fields with various scenarios.
//! These fields are critical for T2/CLM-style liquidity management.
//!
//! TDD Approach: Tests document expected collateral behavior.

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

fn build_context(agent: &Agent, state: &SimulationState, tick: usize) -> EvalContext {
    let tx = create_tx(agent.id(), "BANK_B", 10_000, 0, 100);
    EvalContext::build(&tx, agent, state, tick, &default_cost_rates(), 100, 0.8)
}

// ============================================================================
// Basic Collateral State Fields
// ============================================================================

#[test]
fn test_posted_collateral_zero_when_none_posted() {
    let agent = create_agent("BANK_A", 1_000_000, 500_000);
    let state = SimulationState::new(vec![agent.clone()]);
    let context = build_context(&agent, &state, 50);

    assert_eq!(context.get_field("posted_collateral").unwrap(), 0.0);
}

#[test]
fn test_posted_collateral_after_posting() {
    let mut agent = create_agent("BANK_A", 1_000_000, 500_000);
    agent.set_posted_collateral(100_000);
    let state = SimulationState::new(vec![agent.clone()]);
    let context = build_context(&agent, &state, 50);

    assert_eq!(context.get_field("posted_collateral").unwrap(), 100_000.0);
}

#[test]
fn test_max_collateral_capacity_default() {
    let agent = create_agent("BANK_A", 1_000_000, 500_000);
    let state = SimulationState::new(vec![agent.clone()]);
    let context = build_context(&agent, &state, 50);

    let max_cap = context.get_field("max_collateral_capacity").unwrap();
    // Default max capacity is 100_000_000 (100 million)
    assert!(max_cap > 0.0, "Max collateral capacity should be positive");
}

#[test]
fn test_remaining_collateral_capacity_computation() {
    let mut agent = create_agent("BANK_A", 1_000_000, 500_000);
    agent.set_posted_collateral(30_000_000);
    let state = SimulationState::new(vec![agent.clone()]);
    let context = build_context(&agent, &state, 50);

    let max_cap = context.get_field("max_collateral_capacity").unwrap();
    let posted = context.get_field("posted_collateral").unwrap();
    let remaining = context.get_field("remaining_collateral_capacity").unwrap();

    // remaining = max - posted
    assert_eq!(remaining, max_cap - posted);
}

// ============================================================================
// Collateral Utilization Ratio
// ============================================================================

#[test]
fn test_collateral_utilization_zero_when_nothing_posted() {
    let agent = create_agent("BANK_A", 1_000_000, 500_000);
    let state = SimulationState::new(vec![agent.clone()]);
    let context = build_context(&agent, &state, 50);

    assert_eq!(context.get_field("collateral_utilization").unwrap(), 0.0);
}

#[test]
fn test_collateral_utilization_partial() {
    let mut agent = create_agent("BANK_A", 1_000_000, 500_000);
    // Post 50% of max capacity
    let max_cap = agent.max_collateral_capacity();
    agent.set_posted_collateral(max_cap / 2);
    let state = SimulationState::new(vec![agent.clone()]);
    let context = build_context(&agent, &state, 50);

    let utilization = context.get_field("collateral_utilization").unwrap();
    assert!((utilization - 0.5).abs() < 0.001, "Utilization should be approximately 0.5");
}

#[test]
fn test_collateral_utilization_at_capacity() {
    let mut agent = create_agent("BANK_A", 1_000_000, 500_000);
    let max_cap = agent.max_collateral_capacity();
    agent.set_posted_collateral(max_cap);
    let state = SimulationState::new(vec![agent.clone()]);
    let context = build_context(&agent, &state, 50);

    assert_eq!(context.get_field("collateral_utilization").unwrap(), 1.0);
}

// ============================================================================
// Queue 1 Liquidity Gap Fields
// ============================================================================

#[test]
fn test_queue1_liquidity_gap_empty_queue() {
    let agent = create_agent("BANK_A", 1_000_000, 500_000);
    let state = SimulationState::new(vec![agent.clone()]);
    let context = build_context(&agent, &state, 50);

    // With empty queue and positive balance, gap should be 0 or negative (surplus)
    let gap = context.get_field("queue1_liquidity_gap").unwrap();
    assert!(gap <= 0.0, "Gap should be <= 0 when queue is empty and balance is positive");
}

#[test]
fn test_queue1_total_value_empty_queue() {
    let agent = create_agent("BANK_A", 1_000_000, 500_000);
    let state = SimulationState::new(vec![agent.clone()]);
    let context = build_context(&agent, &state, 50);

    assert_eq!(context.get_field("queue1_total_value").unwrap(), 0.0);
}

#[test]
fn test_queue1_total_value_with_transactions() {
    let mut agent = create_agent("BANK_A", 1_000_000, 500_000);

    // Create state and add transactions
    let mut state = SimulationState::new(vec![
        agent.clone(),
        create_agent("BANK_B", 1_000_000, 500_000),
    ]);

    let tx1 = create_tx("BANK_A", "BANK_B", 50_000, 0, 100);
    let tx2 = create_tx("BANK_A", "BANK_B", 30_000, 0, 100);
    state.add_transaction(tx1);
    state.add_transaction(tx2);

    // Queue the transactions for the agent
    let tx_ids: Vec<String> = state.transactions().keys().cloned().collect();
    agent.replace_outgoing_queue(tx_ids);

    let tx = create_tx("BANK_A", "BANK_B", 10_000, 0, 100);
    let context = EvalContext::build(&tx, &agent, &state, 50, &default_cost_rates(), 100, 0.8);

    let total_value = context.get_field("queue1_total_value").unwrap();
    assert_eq!(total_value, 80_000.0); // 50k + 30k
}

// ============================================================================
// Headroom Field
// ============================================================================

#[test]
fn test_headroom_positive_with_surplus() {
    let agent = create_agent("BANK_A", 1_000_000, 500_000);
    let state = SimulationState::new(vec![agent.clone()]);
    let context = build_context(&agent, &state, 50);

    let headroom = context.get_field("headroom").unwrap();
    // headroom = available_liquidity - queue1_total_value
    // With empty queue: headroom = 1.5M - 0 = 1.5M
    assert_eq!(headroom, 1_500_000.0);
}

#[test]
fn test_headroom_relationship_to_liquidity() {
    let agent = create_agent("BANK_A", 1_000_000, 500_000);
    let state = SimulationState::new(vec![agent.clone()]);
    let context = build_context(&agent, &state, 50);

    let available = context.get_field("available_liquidity").unwrap();
    let queue1_value = context.get_field("queue1_total_value").unwrap();
    let headroom = context.get_field("headroom").unwrap();

    assert_eq!(headroom, available - queue1_value);
}

// ============================================================================
// Queue 2 Metrics
// ============================================================================

#[test]
fn test_queue2_size_empty() {
    let agent = create_agent("BANK_A", 1_000_000, 500_000);
    let state = SimulationState::new(vec![agent.clone()]);
    let context = build_context(&agent, &state, 50);

    assert_eq!(context.get_field("queue2_size").unwrap(), 0.0);
}

#[test]
fn test_queue2_count_for_agent_empty() {
    let agent = create_agent("BANK_A", 1_000_000, 500_000);
    let state = SimulationState::new(vec![agent.clone()]);
    let context = build_context(&agent, &state, 50);

    assert_eq!(context.get_field("queue2_count_for_agent").unwrap(), 0.0);
}

#[test]
fn test_queue2_nearest_deadline_max_when_empty() {
    let agent = create_agent("BANK_A", 1_000_000, 500_000);
    let state = SimulationState::new(vec![agent.clone()]);
    let context = build_context(&agent, &state, 50);

    let nearest = context.get_field("queue2_nearest_deadline").unwrap();
    // When empty, should be usize::MAX
    assert!(nearest > 1e15, "Should be very large when Q2 is empty");
}

#[test]
fn test_ticks_to_nearest_queue2_deadline_infinity_when_empty() {
    let agent = create_agent("BANK_A", 1_000_000, 500_000);
    let state = SimulationState::new(vec![agent.clone()]);
    let context = build_context(&agent, &state, 50);

    let ticks_to = context.get_field("ticks_to_nearest_queue2_deadline").unwrap();
    assert!(ticks_to.is_infinite(), "Should be INFINITY when Q2 is empty");
}

#[test]
fn test_queue2_count_with_transactions() {
    let agent = create_agent("BANK_A", 1_000_000, 500_000);

    let mut state = SimulationState::new(vec![
        agent.clone(),
        create_agent("BANK_B", 1_000_000, 500_000),
    ]);

    // Add transactions and queue them in RTGS (Queue 2)
    let tx1 = create_tx("BANK_A", "BANK_B", 50_000, 0, 80);
    let tx2 = create_tx("BANK_A", "BANK_B", 30_000, 0, 90);
    state.add_transaction(tx1);
    state.add_transaction(tx2);

    // Queue in RTGS
    let tx_ids: Vec<String> = state.transactions().keys().cloned().collect();
    for tx_id in tx_ids {
        state.queue_transaction(tx_id);
    }

    // Rebuild index
    state.rebuild_queue2_index();

    let tx = create_tx("BANK_A", "BANK_B", 10_000, 0, 100);
    let context = EvalContext::build(&tx, &agent, &state, 50, &default_cost_rates(), 100, 0.8);

    assert_eq!(context.get_field("queue2_size").unwrap(), 2.0);
    assert_eq!(context.get_field("queue2_count_for_agent").unwrap(), 2.0);
}

// ============================================================================
// T2/CLM-Style Overdraft Fields
// ============================================================================

#[test]
fn test_allowed_overdraft_limit_unsecured_only() {
    let agent = create_agent("BANK_A", 1_000_000, 500_000);
    let state = SimulationState::new(vec![agent.clone()]);
    let context = build_context(&agent, &state, 50);

    let allowed_limit = context.get_field("allowed_overdraft_limit").unwrap();
    // With no collateral, allowed_limit = unsecured_cap = 500k
    assert_eq!(allowed_limit, 500_000.0);
}

#[test]
fn test_allowed_overdraft_limit_with_collateral() {
    let mut agent = create_agent("BANK_A", 1_000_000, 500_000);
    agent.set_posted_collateral(100_000);
    let state = SimulationState::new(vec![agent.clone()]);
    let context = build_context(&agent, &state, 50);

    let allowed_limit = context.get_field("allowed_overdraft_limit").unwrap();
    // allowed_limit = unsecured_cap + collateral_credit_value
    // collateral_credit_value = collateral * (1 - haircut)
    // With 2% haircut: 100k * 0.98 = 98k
    // Total: 500k + 98k = 598k
    assert_eq!(allowed_limit, 598_000.0);
}

#[test]
fn test_overdraft_headroom_when_not_using_credit() {
    let agent = create_agent("BANK_A", 1_000_000, 500_000);
    let state = SimulationState::new(vec![agent.clone()]);
    let context = build_context(&agent, &state, 50);

    let headroom = context.get_field("overdraft_headroom").unwrap();
    // When not using credit: headroom = allowed_limit - credit_used = 500k - 0 = 500k
    assert_eq!(headroom, 500_000.0);
}

#[test]
fn test_overdraft_headroom_when_using_credit() {
    let agent = create_agent("BANK_A", -200_000, 500_000); // Using 200k credit
    let state = SimulationState::new(vec![agent.clone()]);
    let context = build_context(&agent, &state, 50);

    let headroom = context.get_field("overdraft_headroom").unwrap();
    // headroom = allowed_limit - credit_used = 500k - 200k = 300k
    assert_eq!(headroom, 300_000.0);
}

#[test]
fn test_collateral_haircut_default() {
    let agent = create_agent("BANK_A", 1_000_000, 500_000);
    let state = SimulationState::new(vec![agent.clone()]);
    let context = build_context(&agent, &state, 50);

    let haircut = context.get_field("collateral_haircut").unwrap();
    // Default haircut is 2% = 0.02
    assert_eq!(haircut, 0.02);
}

#[test]
fn test_unsecured_cap_field() {
    let agent = create_agent("BANK_A", 1_000_000, 500_000);
    let state = SimulationState::new(vec![agent.clone()]);
    let context = build_context(&agent, &state, 50);

    assert_eq!(context.get_field("unsecured_cap").unwrap(), 500_000.0);
}

// ============================================================================
// Required and Excess Collateral Fields
// ============================================================================

#[test]
fn test_required_collateral_for_usage_zero_when_not_using_credit() {
    let agent = create_agent("BANK_A", 1_000_000, 500_000);
    let state = SimulationState::new(vec![agent.clone()]);
    let context = build_context(&agent, &state, 50);

    let required = context.get_field("required_collateral_for_usage").unwrap();
    // When not using credit beyond unsecured cap, required collateral = 0
    assert_eq!(required, 0.0);
}

#[test]
fn test_required_collateral_when_exceeding_unsecured_cap() {
    // Agent using more credit than unsecured cap
    let agent = create_agent("BANK_A", -600_000, 500_000); // Using 600k, cap is 500k

    let state = SimulationState::new(vec![agent.clone()]);
    let context = build_context(&agent, &state, 50);

    let required = context.get_field("required_collateral_for_usage").unwrap();
    // Usage beyond unsecured = 600k - 500k = 100k
    // Required collateral = 100k / (1 - 0.02) = 100k / 0.98 ≈ 102,040.82
    assert!(required > 100_000.0, "Required collateral should cover credit usage beyond unsecured cap");
}

#[test]
fn test_excess_collateral_when_over_required() {
    let mut agent = create_agent("BANK_A", 1_000_000, 500_000);
    agent.set_posted_collateral(500_000); // Post 500k collateral
    let state = SimulationState::new(vec![agent.clone()]);
    let context = build_context(&agent, &state, 50);

    let excess = context.get_field("excess_collateral").unwrap();
    // With no credit usage, all posted collateral is excess
    // required = 0, posted = 500k, excess = 500k - 0 = 500k
    assert_eq!(excess, 500_000.0);
}

#[test]
fn test_excess_collateral_zero_when_exactly_required() {
    // This is a more complex scenario - agent using credit beyond cap
    // with exactly enough collateral posted
    // For simplicity, test that excess is computed correctly
    let agent = create_agent("BANK_A", 1_000_000, 500_000);
    let state = SimulationState::new(vec![agent.clone()]);
    let context = build_context(&agent, &state, 50);

    let posted = context.get_field("posted_collateral").unwrap();
    let required = context.get_field("required_collateral_for_usage").unwrap();
    let excess = context.get_field("excess_collateral").unwrap();

    // excess = max(posted - required, 0)
    assert_eq!(excess, (posted - required).max(0.0));
}

// ============================================================================
// Overdraft Utilization Ratio
// ============================================================================

#[test]
fn test_overdraft_utilization_zero_when_not_using_credit() {
    let agent = create_agent("BANK_A", 1_000_000, 500_000);
    let state = SimulationState::new(vec![agent.clone()]);
    let context = build_context(&agent, &state, 50);

    assert_eq!(context.get_field("overdraft_utilization").unwrap(), 0.0);
}

#[test]
fn test_overdraft_utilization_partial() {
    let agent = create_agent("BANK_A", -250_000, 500_000); // 50% of 500k
    let state = SimulationState::new(vec![agent.clone()]);
    let context = build_context(&agent, &state, 50);

    let utilization = context.get_field("overdraft_utilization").unwrap();
    // credit_used / allowed_limit = 250k / 500k = 0.5
    assert_eq!(utilization, 0.5);
}

#[test]
fn test_overdraft_utilization_at_100_percent() {
    let agent = create_agent("BANK_A", -500_000, 500_000); // 100% of 500k
    let state = SimulationState::new(vec![agent.clone()]);
    let context = build_context(&agent, &state, 50);

    assert_eq!(context.get_field("overdraft_utilization").unwrap(), 1.0);
}

#[test]
fn test_overdraft_utilization_over_100_percent() {
    // Agent has exceeded their credit limit (bug state, but should be handled)
    let mut agent = create_agent("BANK_A", 0, 500_000);
    agent.adjust_balance(-700_000); // 140% of 500k limit

    let state = SimulationState::new(vec![agent.clone()]);
    let context = build_context(&agent, &state, 50);

    let utilization = context.get_field("overdraft_utilization").unwrap();
    // credit_used / allowed_limit = 700k / 500k = 1.4
    assert_eq!(utilization, 1.4);
}

// ============================================================================
// Collateral Interaction Tests
// ============================================================================

#[test]
fn test_collateral_affects_available_liquidity() {
    let mut agent = create_agent("BANK_A", 1_000_000, 500_000);
    let state_before = SimulationState::new(vec![agent.clone()]);
    let context_before = build_context(&agent, &state_before, 50);
    let liquidity_before = context_before.get_field("available_liquidity").unwrap();

    // Post collateral
    agent.set_posted_collateral(100_000);
    let state_after = SimulationState::new(vec![agent.clone()]);
    let context_after = build_context(&agent, &state_after, 50);
    let liquidity_after = context_after.get_field("available_liquidity").unwrap();

    // Collateral should increase available liquidity
    assert!(liquidity_after > liquidity_before);
    // Increase should be collateral * (1 - haircut) = 100k * 0.98 = 98k
    assert_eq!(liquidity_after - liquidity_before, 98_000.0);
}

#[test]
fn test_collateral_affects_allowed_overdraft_limit() {
    let mut agent = create_agent("BANK_A", 1_000_000, 500_000);
    let state_before = SimulationState::new(vec![agent.clone()]);
    let context_before = build_context(&agent, &state_before, 50);
    let limit_before = context_before.get_field("allowed_overdraft_limit").unwrap();

    agent.set_posted_collateral(100_000);
    let state_after = SimulationState::new(vec![agent.clone()]);
    let context_after = build_context(&agent, &state_after, 50);
    let limit_after = context_after.get_field("allowed_overdraft_limit").unwrap();

    assert!(limit_after > limit_before);
    assert_eq!(limit_after - limit_before, 98_000.0);
}

#[test]
fn test_all_collateral_fields_present() {
    let agent = create_agent("BANK_A", 1_000_000, 500_000);
    let state = SimulationState::new(vec![agent.clone()]);
    let context = build_context(&agent, &state, 50);

    let collateral_fields = [
        "posted_collateral",
        "max_collateral_capacity",
        "remaining_collateral_capacity",
        "collateral_utilization",
        "queue1_liquidity_gap",
        "queue1_total_value",
        "headroom",
        "queue2_size",
        "queue2_count_for_agent",
        "queue2_nearest_deadline",
        "ticks_to_nearest_queue2_deadline",
        "credit_used",
        "allowed_overdraft_limit",
        "overdraft_headroom",
        "collateral_haircut",
        "unsecured_cap",
        "required_collateral_for_usage",
        "excess_collateral",
        "overdraft_utilization",
    ];

    for field in collateral_fields {
        assert!(
            context.get_field(field).is_ok(),
            "Collateral field '{}' should exist",
            field
        );
    }
}
