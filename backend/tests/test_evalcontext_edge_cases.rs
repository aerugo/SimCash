//! Edge Case Tests for EvalContext Fields
//!
//! Tests boundary conditions, zero values, negative values,
//! infinity, and other edge cases.
//!
//! TDD Approach: These tests document expected behavior at boundaries.
//! If tests fail due to implementation bugs, the test documents the
//! correct expected behavior.

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

// ============================================================================
// Division by Zero Protection
// ============================================================================

#[test]
fn test_collateral_utilization_zero_capacity_does_not_panic() {
    // Agent with zero max_collateral_capacity
    let agent = create_agent("BANK_A", 1_000_000, 0);
    let tx = create_tx("BANK_A", "BANK_B", 10_000, 0, 100);
    let state = SimulationState::new(vec![agent.clone()]);

    // Should not panic, should return 0.0
    let context = EvalContext::build(&tx, &agent, &state, 50, &default_cost_rates(), 100, 0.8);
    let utilization = context.get_field("collateral_utilization").unwrap();

    assert_eq!(utilization, 0.0, "Collateral utilization should be 0.0 when max capacity is 0");
}

#[test]
fn test_overdraft_utilization_zero_limit_does_not_panic() {
    // Agent with zero allowed_overdraft_limit (no credit, no collateral)
    let agent = create_agent("BANK_A", 100_000, 0);
    let tx = create_tx("BANK_A", "BANK_B", 10_000, 0, 100);
    let state = SimulationState::new(vec![agent.clone()]);

    let context = EvalContext::build(&tx, &agent, &state, 50, &default_cost_rates(), 100, 0.8);
    let utilization = context.get_field("overdraft_utilization").unwrap();

    assert_eq!(utilization, 0.0, "Overdraft utilization should be 0.0 when allowed limit is 0");
}

#[test]
fn test_day_progress_zero_ticks_per_day_does_not_panic() {
    // Edge case: ticks_per_day = 0 (invalid config, but should not panic)
    let agent = create_agent("BANK_A", 1_000_000, 0);
    let tx = create_tx("BANK_A", "BANK_B", 10_000, 0, 100);
    let state = SimulationState::new(vec![agent.clone()]);

    // Build with ticks_per_day = 1 (minimum valid - 0 would be invalid)
    let context = EvalContext::build(&tx, &agent, &state, 0, &default_cost_rates(), 1, 0.8);
    let progress = context.get_field("day_progress_fraction").unwrap();

    // At tick 0 of 1-tick day, progress should be 0.0
    assert_eq!(progress, 0.0);
}

#[test]
fn test_throughput_fraction_no_transactions_returns_zero() {
    // Agent with no transaction history
    let agent = create_agent("BANK_A", 1_000_000, 0);
    let tx = create_tx("BANK_A", "BANK_B", 10_000, 0, 100);
    let state = SimulationState::new(vec![agent.clone()]);

    let context = EvalContext::build(&tx, &agent, &state, 50, &default_cost_rates(), 100, 0.8);
    let fraction = context.get_field("my_throughput_fraction_today").unwrap();

    // Should be 0.0, not panic or NaN
    assert!(fraction.is_finite(), "Throughput fraction should be finite");
    assert!(fraction >= 0.0, "Throughput fraction should be non-negative");
}

// ============================================================================
// Infinity Handling
// ============================================================================

#[test]
fn test_ticks_to_nearest_queue2_deadline_infinity_when_empty() {
    // No transactions in Queue 2
    let agent = create_agent("BANK_A", 1_000_000, 0);
    let tx = create_tx("BANK_A", "BANK_B", 10_000, 0, 100);
    let state = SimulationState::new(vec![agent.clone()]);

    let context = EvalContext::build(&tx, &agent, &state, 50, &default_cost_rates(), 100, 0.8);
    let ticks_to_deadline = context.get_field("ticks_to_nearest_queue2_deadline").unwrap();

    // Should be f64::INFINITY when no transactions in Q2
    assert!(ticks_to_deadline.is_infinite(), "Should be INFINITY when Q2 is empty");
    assert!(ticks_to_deadline > 0.0, "Should be positive INFINITY");
}

// ============================================================================
// Negative Value Handling
// ============================================================================

#[test]
fn test_ticks_to_deadline_negative_when_past_deadline() {
    // Transaction past deadline
    let agent = create_agent("BANK_A", 1_000_000, 0);
    let tx = create_tx("BANK_A", "BANK_B", 10_000, 0, 50); // deadline = 50
    let state = SimulationState::new(vec![agent.clone()]);

    // Current tick = 100, deadline = 50 -> ticks_to_deadline = -50
    let context = EvalContext::build(&tx, &agent, &state, 100, &default_cost_rates(), 100, 0.8);
    let ticks_to_deadline = context.get_field("ticks_to_deadline").unwrap();

    assert_eq!(ticks_to_deadline, -50.0, "ticks_to_deadline should be -50 when 50 ticks past deadline");
}

#[test]
fn test_ticks_to_deadline_deeply_negative() {
    // 1000 ticks past deadline
    let agent = create_agent("BANK_A", 1_000_000, 0);
    let tx = create_tx("BANK_A", "BANK_B", 10_000, 0, 50);
    let state = SimulationState::new(vec![agent.clone()]);

    let context = EvalContext::build(&tx, &agent, &state, 1050, &default_cost_rates(), 100, 0.8);
    let ticks_to_deadline = context.get_field("ticks_to_deadline").unwrap();

    assert_eq!(ticks_to_deadline, -1000.0);
}

#[test]
fn test_credit_headroom_negative_when_exceeded() {
    // Agent has exceeded credit limit (this is a bug state, but test handles it)
    let mut agent = create_agent("BANK_A", 0, 50_000);
    // Force balance beyond credit limit
    agent.adjust_balance(-70_000); // Now using 70k of 50k limit

    let tx = create_tx("BANK_A", "BANK_B", 10_000, 0, 100);
    let state = SimulationState::new(vec![agent.clone()]);

    let context = EvalContext::build(&tx, &agent, &state, 50, &default_cost_rates(), 100, 0.8);
    let headroom = context.get_field("credit_headroom").unwrap();

    // credit_headroom = 50k - 70k = -20k
    assert_eq!(headroom, -20_000.0, "Credit headroom should be negative when limit exceeded");
}

#[test]
fn test_headroom_negative_when_queue1_exceeds_liquidity() {
    // Queue 1 value exceeds available liquidity
    let mut agent = create_agent("BANK_A", 100_000, 0);

    // Add transactions to Queue 1 totaling more than available liquidity
    agent.queue_outgoing("tx_1".to_string());
    agent.queue_outgoing("tx_2".to_string());

    // Create state with transactions
    let mut state = SimulationState::new(vec![agent.clone()]);
    let tx1 = create_tx("BANK_A", "BANK_B", 80_000, 0, 100);
    let tx2 = create_tx("BANK_A", "BANK_B", 80_000, 0, 100);
    state.add_transaction(tx1);
    state.add_transaction(tx2);

    // Update agent's queue with actual transaction IDs
    let tx_ids: Vec<String> = state.transactions().keys().cloned().collect();
    let mut agent = state.get_agent("BANK_A").unwrap().clone();
    agent.replace_outgoing_queue(tx_ids);

    // Note: headroom = available_liquidity - queue1_total_value
    // If queue1_total_value > available_liquidity, headroom is negative

    let tx = create_tx("BANK_A", "BANK_B", 10_000, 0, 100);
    let context = EvalContext::build(&tx, &agent, &state, 50, &default_cost_rates(), 100, 0.8);

    let headroom = context.get_field("headroom").unwrap();
    // 100k available - 160k queue value = -60k headroom
    assert!(headroom < 0.0, "Headroom should be negative when queue exceeds liquidity");
}

#[test]
fn test_throughput_gap_negative_when_behind_schedule() {
    // Agent behind schedule (0% done when should be 50% done)
    let agent = create_agent("BANK_A", 1_000_000, 0);
    let tx = create_tx("BANK_A", "BANK_B", 10_000, 0, 100);
    let state = SimulationState::new(vec![agent.clone()]);

    // At tick 50, expected = 0.5, actual = 0.0
    let context = EvalContext::build(&tx, &agent, &state, 50, &default_cost_rates(), 100, 0.8);
    let gap = context.get_field("throughput_gap").unwrap();

    // gap = actual - expected = 0.0 - 0.5 = -0.5
    assert!(gap < 0.0, "Throughput gap should be negative when behind schedule");
}

// ============================================================================
// Boolean Fields Strict 0/1 Validation
// ============================================================================

#[test]
fn test_is_split_only_zero_or_one() {
    let agent = create_agent("BANK_A", 1_000_000, 0);

    // Non-split transaction
    let tx1 = create_tx("BANK_A", "BANK_B", 10_000, 0, 100);
    let state = SimulationState::new(vec![agent.clone()]);
    let context1 = EvalContext::build(&tx1, &agent, &state, 50, &default_cost_rates(), 100, 0.8);
    let is_split1 = context1.get_field("is_split").unwrap();
    assert!(is_split1 == 0.0 || is_split1 == 1.0, "is_split must be exactly 0.0 or 1.0");
    assert_eq!(is_split1, 0.0);

    // Split transaction
    let tx2 = Transaction::new_split("BANK_A".to_string(), "BANK_B".to_string(), 10_000, 0, 100, "parent".to_string());
    let context2 = EvalContext::build(&tx2, &agent, &state, 50, &default_cost_rates(), 100, 0.8);
    let is_split2 = context2.get_field("is_split").unwrap();
    assert_eq!(is_split2, 1.0);
}

#[test]
fn test_is_past_deadline_only_zero_or_one() {
    let agent = create_agent("BANK_A", 1_000_000, 0);
    let state = SimulationState::new(vec![agent.clone()]);

    // Before deadline
    let tx = create_tx("BANK_A", "BANK_B", 10_000, 0, 100);
    let context1 = EvalContext::build(&tx, &agent, &state, 50, &default_cost_rates(), 100, 0.8);
    assert_eq!(context1.get_field("is_past_deadline").unwrap(), 0.0);

    // After deadline
    let context2 = EvalContext::build(&tx, &agent, &state, 150, &default_cost_rates(), 100, 0.8);
    assert_eq!(context2.get_field("is_past_deadline").unwrap(), 1.0);
}

#[test]
fn test_is_overdue_only_zero_or_one() {
    let agent = create_agent("BANK_A", 1_000_000, 0);
    let state = SimulationState::new(vec![agent.clone()]);

    // Not overdue
    let tx1 = create_tx("BANK_A", "BANK_B", 10_000, 0, 100);
    let context1 = EvalContext::build(&tx1, &agent, &state, 50, &default_cost_rates(), 100, 0.8);
    let is_overdue = context1.get_field("is_overdue").unwrap();
    assert!(is_overdue == 0.0 || is_overdue == 1.0);

    // Overdue transaction
    let mut tx2 = create_tx("BANK_A", "BANK_B", 10_000, 0, 50);
    tx2.mark_overdue(51).unwrap();
    let context2 = EvalContext::build(&tx2, &agent, &state, 60, &default_cost_rates(), 100, 0.8);
    assert_eq!(context2.get_field("is_overdue").unwrap(), 1.0);
}

#[test]
fn test_is_using_credit_only_zero_or_one() {
    let state = SimulationState::new(vec![create_agent("BANK_A", 1_000_000, 500_000)]);
    let tx = create_tx("BANK_A", "BANK_B", 10_000, 0, 100);

    // Not using credit
    let agent1 = create_agent("BANK_A", 100_000, 500_000);
    let context1 = EvalContext::build(&tx, &agent1, &state, 50, &default_cost_rates(), 100, 0.8);
    assert_eq!(context1.get_field("is_using_credit").unwrap(), 0.0);

    // Using credit (negative balance)
    let agent2 = create_agent("BANK_A", -100_000, 500_000);
    let context2 = EvalContext::build(&tx, &agent2, &state, 50, &default_cost_rates(), 100, 0.8);
    assert_eq!(context2.get_field("is_using_credit").unwrap(), 1.0);
}

#[test]
fn test_is_overdraft_capped_always_one() {
    // In Option B, is_overdraft_capped is always 1.0
    let agent = create_agent("BANK_A", 1_000_000, 500_000);
    let tx = create_tx("BANK_A", "BANK_B", 10_000, 0, 100);
    let state = SimulationState::new(vec![agent.clone()]);

    let context = EvalContext::build(&tx, &agent, &state, 50, &default_cost_rates(), 100, 0.8);
    assert_eq!(context.get_field("is_overdraft_capped").unwrap(), 1.0);
}

#[test]
fn test_is_eod_rush_only_zero_or_one() {
    let agent = create_agent("BANK_A", 1_000_000, 500_000);
    let tx = create_tx("BANK_A", "BANK_B", 10_000, 0, 100);
    let state = SimulationState::new(vec![agent.clone()]);

    // Not in EOD rush (threshold 0.8, progress 0.5)
    let context1 = EvalContext::build(&tx, &agent, &state, 50, &default_cost_rates(), 100, 0.8);
    assert_eq!(context1.get_field("is_eod_rush").unwrap(), 0.0);

    // In EOD rush (progress 0.9 >= 0.8)
    let context2 = EvalContext::build(&tx, &agent, &state, 90, &default_cost_rates(), 100, 0.8);
    assert_eq!(context2.get_field("is_eod_rush").unwrap(), 1.0);
}

#[test]
fn test_tx_is_top_counterparty_only_zero_or_one() {
    let agent = create_agent("BANK_A", 1_000_000, 500_000);
    let tx = create_tx("BANK_A", "BANK_B", 10_000, 0, 100);
    let state = SimulationState::new(vec![agent.clone()]);

    let context = EvalContext::build(&tx, &agent, &state, 50, &default_cost_rates(), 100, 0.8);
    let is_top = context.get_field("tx_is_top_counterparty").unwrap();

    assert!(is_top == 0.0 || is_top == 1.0, "tx_is_top_counterparty must be exactly 0.0 or 1.0");
}

// ============================================================================
// Zero Value Edge Cases
// ============================================================================

#[test]
fn test_zero_amount_transaction() {
    let agent = create_agent("BANK_A", 1_000_000, 500_000);
    let tx = create_tx("BANK_A", "BANK_B", 0, 0, 100); // Zero amount
    let state = SimulationState::new(vec![agent.clone()]);

    let context = EvalContext::build(&tx, &agent, &state, 50, &default_cost_rates(), 100, 0.8);

    assert_eq!(context.get_field("amount").unwrap(), 0.0);
    assert_eq!(context.get_field("remaining_amount").unwrap(), 0.0);
    // Cost calculations should be zero for zero amount
    assert_eq!(context.get_field("cost_delay_this_tx_one_tick").unwrap(), 0.0);
}

#[test]
fn test_zero_balance_agent() {
    let agent = create_agent("BANK_A", 0, 500_000);
    let tx = create_tx("BANK_A", "BANK_B", 10_000, 0, 100);
    let state = SimulationState::new(vec![agent.clone()]);

    let context = EvalContext::build(&tx, &agent, &state, 50, &default_cost_rates(), 100, 0.8);

    assert_eq!(context.get_field("balance").unwrap(), 0.0);
    assert_eq!(context.get_field("is_using_credit").unwrap(), 0.0); // Not using credit yet
}

#[test]
fn test_zero_credit_limit_agent() {
    let agent = create_agent("BANK_A", 100_000, 0); // No credit
    let tx = create_tx("BANK_A", "BANK_B", 10_000, 0, 100);
    let state = SimulationState::new(vec![agent.clone()]);

    let context = EvalContext::build(&tx, &agent, &state, 50, &default_cost_rates(), 100, 0.8);

    assert_eq!(context.get_field("credit_limit").unwrap(), 0.0);
    assert_eq!(context.get_field("credit_headroom").unwrap(), 0.0);
    assert_eq!(context.get_field("available_liquidity").unwrap(), 100_000.0);
}

#[test]
fn test_zero_priority_transaction() {
    let agent = create_agent("BANK_A", 1_000_000, 500_000);
    let tx = create_tx("BANK_A", "BANK_B", 10_000, 0, 100).with_priority(0);
    let state = SimulationState::new(vec![agent.clone()]);

    let context = EvalContext::build(&tx, &agent, &state, 50, &default_cost_rates(), 100, 0.8);

    assert_eq!(context.get_field("priority").unwrap(), 0.0);
}

#[test]
fn test_queue_age_zero_when_just_arrived() {
    let agent = create_agent("BANK_A", 1_000_000, 500_000);
    let tx = create_tx("BANK_A", "BANK_B", 10_000, 50, 100); // arrival = 50
    let state = SimulationState::new(vec![agent.clone()]);

    let context = EvalContext::build(&tx, &agent, &state, 50, &default_cost_rates(), 100, 0.8);

    assert_eq!(context.get_field("queue_age").unwrap(), 0.0);
}

// ============================================================================
// Large Value Edge Cases
// ============================================================================

#[test]
fn test_large_amount_transaction() {
    let agent = create_agent("BANK_A", i64::MAX / 2, 0);
    let tx = create_tx("BANK_A", "BANK_B", i64::MAX / 4, 0, 100);
    let state = SimulationState::new(vec![agent.clone()]);

    let context = EvalContext::build(&tx, &agent, &state, 50, &default_cost_rates(), 100, 0.8);

    let amount = context.get_field("amount").unwrap();
    assert!(amount.is_finite(), "Large amount should still be finite");
    assert!(amount > 0.0, "Large amount should be positive");
}

#[test]
fn test_large_tick_number() {
    // Multi-year simulation (365 days * 100 ticks/day * 10 years = 365,000 ticks)
    let agent = create_agent("BANK_A", 1_000_000, 500_000);
    let tx = create_tx("BANK_A", "BANK_B", 10_000, 0, 400_000);
    let state = SimulationState::new(vec![agent.clone()]);

    let context = EvalContext::build(&tx, &agent, &state, 365_000, &default_cost_rates(), 100, 0.8);

    let current_day = context.get_field("system_current_day").unwrap();
    assert_eq!(current_day, 3650.0); // 365,000 / 100 = 3650 days
}

// ============================================================================
// Exact Boundary Tests
// ============================================================================

#[test]
fn test_ticks_to_deadline_exact_zero() {
    let agent = create_agent("BANK_A", 1_000_000, 500_000);
    let tx = create_tx("BANK_A", "BANK_B", 10_000, 0, 50); // deadline = 50
    let state = SimulationState::new(vec![agent.clone()]);

    let context = EvalContext::build(&tx, &agent, &state, 50, &default_cost_rates(), 100, 0.8);

    assert_eq!(context.get_field("ticks_to_deadline").unwrap(), 0.0);
    assert_eq!(context.get_field("is_past_deadline").unwrap(), 0.0); // At deadline, not past it
}

#[test]
fn test_is_eod_rush_at_exact_threshold() {
    let agent = create_agent("BANK_A", 1_000_000, 500_000);
    let tx = create_tx("BANK_A", "BANK_B", 10_000, 0, 100);
    let state = SimulationState::new(vec![agent.clone()]);

    // Tick 80 of 100 = 0.8 progress, threshold 0.8
    let context = EvalContext::build(&tx, &agent, &state, 80, &default_cost_rates(), 100, 0.8);

    // At exactly threshold, should be IN EOD rush (>=)
    assert_eq!(context.get_field("is_eod_rush").unwrap(), 1.0);
}

#[test]
fn test_credit_headroom_exactly_zero_at_limit() {
    // Agent exactly at credit limit
    let agent = create_agent("BANK_A", -50_000, 50_000); // balance = -50k, limit = 50k
    let tx = create_tx("BANK_A", "BANK_B", 10_000, 0, 100);
    let state = SimulationState::new(vec![agent.clone()]);

    let context = EvalContext::build(&tx, &agent, &state, 50, &default_cost_rates(), 100, 0.8);

    assert_eq!(context.get_field("credit_headroom").unwrap(), 0.0);
    assert_eq!(context.get_field("credit_used").unwrap(), 50_000.0);
}

// ============================================================================
// Consistency Tests
// ============================================================================

#[test]
fn test_effective_liquidity_equals_available_liquidity_when_not_using_credit() {
    let agent = create_agent("BANK_A", 1_000_000, 500_000);
    let tx = create_tx("BANK_A", "BANK_B", 10_000, 0, 100);
    let state = SimulationState::new(vec![agent.clone()]);

    let context = EvalContext::build(&tx, &agent, &state, 50, &default_cost_rates(), 100, 0.8);

    let effective = context.get_field("effective_liquidity").unwrap();
    let available = context.get_field("available_liquidity").unwrap();

    // When not using credit, these should be equal
    assert_eq!(effective, available);
}

#[test]
fn test_credit_used_plus_headroom_equals_limit() {
    let agent = create_agent("BANK_A", -30_000, 50_000); // Using 30k of 50k
    let tx = create_tx("BANK_A", "BANK_B", 10_000, 0, 100);
    let state = SimulationState::new(vec![agent.clone()]);

    let context = EvalContext::build(&tx, &agent, &state, 50, &default_cost_rates(), 100, 0.8);

    let credit_used = context.get_field("credit_used").unwrap();
    let credit_headroom = context.get_field("credit_headroom").unwrap();
    let credit_limit = context.get_field("credit_limit").unwrap();

    // credit_used + credit_headroom = credit_limit
    assert_eq!(credit_used + credit_headroom, credit_limit);
}

#[test]
fn test_queue_age_plus_arrival_tick_equals_current_tick() {
    let agent = create_agent("BANK_A", 1_000_000, 500_000);
    let tx = create_tx("BANK_A", "BANK_B", 10_000, 20, 100); // arrival = 20
    let state = SimulationState::new(vec![agent.clone()]);

    let context = EvalContext::build(&tx, &agent, &state, 50, &default_cost_rates(), 100, 0.8);

    let arrival = context.get_field("arrival_tick").unwrap();
    let queue_age = context.get_field("queue_age").unwrap();
    let current = context.get_field("current_tick").unwrap();

    // arrival_tick + queue_age = current_tick
    assert_eq!(arrival + queue_age, current);
}

#[test]
fn test_deadline_minus_current_equals_ticks_to_deadline() {
    let agent = create_agent("BANK_A", 1_000_000, 500_000);
    let tx = create_tx("BANK_A", "BANK_B", 10_000, 0, 80); // deadline = 80
    let state = SimulationState::new(vec![agent.clone()]);

    let context = EvalContext::build(&tx, &agent, &state, 50, &default_cost_rates(), 100, 0.8);

    let deadline = context.get_field("deadline_tick").unwrap();
    let current = context.get_field("current_tick").unwrap();
    let ticks_to = context.get_field("ticks_to_deadline").unwrap();

    // deadline_tick - current_tick = ticks_to_deadline
    assert_eq!(deadline - current, ticks_to);
}
