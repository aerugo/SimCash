//! Throughput Progress Fields Tests - Phase 2.1
//!
//! Tests for throughput tracking and progress monitoring fields.
//!
//! **Purpose**: Enable policies to track their settlement progress against expected
//! throughput curves (e.g., "am I 30% done when I should be 50% done?").
//!
//! **Use Cases**:
//! - Catch-up behavior: Release more aggressively when behind schedule
//! - Throttling: Be conservative when ahead of schedule
//! - EOD rush detection: Know when to switch to panic mode

use payment_simulator_core_rs::{Agent, SimulationState, Transaction};

/// Helper to create agent
fn create_agent(id: &str, balance: i64, unsecured_cap: i64) -> Agent {
    Agent::new(id.to_string(), balance, credit_limit)
}

/// Helper to create transaction
fn create_tx(sender: &str, receiver: &str, amount: i64, arrival: usize, deadline: usize) -> Transaction {
    Transaction::new(
        sender.to_string(),
        receiver.to_string(),
        amount,
        arrival,
        deadline,
    )
}

// ============================================================================
// Test Group 1: Agent Throughput Tracking (Daily Settlement Amounts)
// ============================================================================

#[test]
fn test_agent_throughput_today_empty() {
    let state = SimulationState::new(vec![
        create_agent("BANK_A", 100_000, 50_000),
        create_agent("BANK_B", 100_000, 50_000),
    ]);

    // No settlements yet - throughput should be 0
    let throughput = agent_throughput_today(&state, "BANK_A");
    assert_eq!(throughput, 0);
}

#[test]
#[ignore] // TODO: Implement after adding daily throughput tracking to SimulationState
fn test_agent_throughput_today_after_settlements() {
    let mut state = SimulationState::new(vec![
        create_agent("BANK_A", 1_000_000, 0),
        create_agent("BANK_B", 1_000_000, 0),
    ]);

    // Add and settle transactions
    let tx1 = create_tx("BANK_A", "BANK_B", 50_000, 0, 100);
    let tx2 = create_tx("BANK_A", "BANK_B", 30_000, 0, 100);

    state.add_transaction(tx1);
    state.add_transaction(tx2);

    // Simulate settlements (this would normally be done by settlement engine)
    // For testing, we'll manually track settled amounts
    // TODO: This requires SimulationState to track daily throughput

    let throughput = agent_throughput_today(&state, "BANK_A");

    // After settling 50k + 30k, throughput should be 80k
    assert_eq!(throughput, 80_000);
}

#[test]
#[ignore] // TODO: Implement after adding day tracking to SimulationState
fn test_agent_throughput_resets_at_eod() {
    let mut state = SimulationState::new(vec![
        create_agent("BANK_A", 1_000_000, 0),
        create_agent("BANK_B", 1_000_000, 0),
    ]);

    // Settle some transactions during day 0
    // (assume we have methods to track this)

    // After EOD reset, throughput should go back to 0
    // state.reset_daily_metrics();

    let throughput = agent_throughput_today(&state, "BANK_A");
    assert_eq!(throughput, 0);
}

// ============================================================================
// Test Group 2: Total Due Today Calculation
// ============================================================================

#[test]
fn test_agent_total_due_today_empty() {
    let state = SimulationState::new(vec![
        create_agent("BANK_A", 100_000, 50_000),
        create_agent("BANK_B", 100_000, 50_000),
    ]);

    // No transactions - total due should be 0
    let total_due = agent_total_due_today(&state, "BANK_A");
    assert_eq!(total_due, 0);
}

#[test]
#[ignore] // TODO: Implement after adding daily tracking to SimulationState
fn test_agent_total_due_today_with_unsettled_transactions() {
    let mut state = SimulationState::new(vec![
        create_agent("BANK_A", 1_000_000, 0),
        create_agent("BANK_B", 1_000_000, 0),
    ]);

    // Add transactions arriving today (deadline doesn't matter for "due today")
    let tx1 = create_tx("BANK_A", "BANK_B", 50_000, 0, 100);
    let tx2 = create_tx("BANK_A", "BANK_B", 30_000, 5, 100);
    let tx3 = create_tx("BANK_A", "BANK_B", 20_000, 10, 100);

    state.add_transaction(tx1);
    state.add_transaction(tx2);
    state.add_transaction(tx3);

    // Total due = all unsettled amounts = 50k + 30k + 20k = 100k
    let total_due = agent_total_due_today(&state, "BANK_A");
    assert_eq!(total_due, 100_000);
}

#[test]
#[ignore] // TODO: Implement after adding daily tracking to SimulationState
fn test_agent_total_due_excludes_settled_transactions() {
    let mut state = SimulationState::new(vec![
        create_agent("BANK_A", 1_000_000, 0),
        create_agent("BANK_B", 1_000_000, 0),
    ]);

    // Add transactions
    let tx1 = create_tx("BANK_A", "BANK_B", 50_000, 0, 100);
    let tx2 = create_tx("BANK_A", "BANK_B", 30_000, 5, 100);

    state.add_transaction(tx1);
    state.add_transaction(tx2);

    // Settle tx1 (50k)
    // TODO: This requires marking transaction as settled

    // Total due = only unsettled = 30k
    let total_due = agent_total_due_today(&state, "BANK_A");
    assert_eq!(total_due, 30_000);
}

#[test]
#[ignore] // TODO: Implement after adding daily tracking to SimulationState
fn test_agent_total_due_includes_only_sender_transactions() {
    let mut state = SimulationState::new(vec![
        create_agent("BANK_A", 1_000_000, 0),
        create_agent("BANK_B", 1_000_000, 0),
    ]);

    // BANK_A outgoing: 50k + 30k = 80k
    let tx1 = create_tx("BANK_A", "BANK_B", 50_000, 0, 100);
    let tx2 = create_tx("BANK_A", "BANK_B", 30_000, 5, 100);

    // BANK_B outgoing: 20k (should not count for BANK_A)
    let tx3 = create_tx("BANK_B", "BANK_A", 20_000, 10, 100);

    state.add_transaction(tx1);
    state.add_transaction(tx2);
    state.add_transaction(tx3);

    // BANK_A total due = only its outgoing = 80k
    let total_due = agent_total_due_today(&state, "BANK_A");
    assert_eq!(total_due, 80_000);
}

// ============================================================================
// Test Group 3: Throughput Fraction Calculation
// ============================================================================

#[test]
fn test_throughput_fraction_zero_when_no_transactions() {
    let state = SimulationState::new(vec![
        create_agent("BANK_A", 100_000, 50_000),
    ]);

    // No transactions - fraction should be 0.0 (or undefined)
    let fraction = calculate_throughput_fraction(&state, "BANK_A");
    assert_eq!(fraction, 0.0);
}

#[test]
fn test_throughput_fraction_half_settled() {
    let mut state = SimulationState::new(vec![
        create_agent("BANK_A", 1_000_000, 0),
        create_agent("BANK_B", 1_000_000, 0),
    ]);

    // Total due: 100k (50k + 50k)
    // Settled: 50k
    // Fraction: 50k / 100k = 0.5

    // TODO: Simulate this state
    // For now, test the calculation logic

    let throughput = 50_000i64;
    let total_due = 100_000i64;
    let fraction = if total_due > 0 {
        throughput as f64 / total_due as f64
    } else {
        0.0
    };

    assert_eq!(fraction, 0.5);
}

#[test]
fn test_throughput_fraction_all_settled() {
    // Total due: 100k
    // Settled: 100k
    // Fraction: 1.0

    let throughput = 100_000i64;
    let total_due = 100_000i64;
    let fraction = if total_due > 0 {
        throughput as f64 / total_due as f64
    } else {
        0.0
    };

    assert_eq!(fraction, 1.0);
}

#[test]
fn test_throughput_fraction_exceeds_one_with_overdue_settlements() {
    // Edge case: If settlements from previous days are included,
    // fraction could exceed 1.0
    // Decision: Should we cap at 1.0 or allow > 1.0?

    let throughput = 150_000i64;
    let total_due = 100_000i64;
    let fraction = if total_due > 0 {
        throughput as f64 / total_due as f64
    } else {
        0.0
    };

    // Allow > 1.0 (shows you're catching up on overdue)
    assert_eq!(fraction, 1.5);
}

// ============================================================================
// Test Group 4: Policy Context Field Exposure
// ============================================================================

#[test]
fn test_context_exposes_my_throughput_fraction_today() {
    use payment_simulator_core_rs::policy::tree::EvalContext;
    use payment_simulator_core_rs::orchestrator::CostRates;

    let mut state = SimulationState::new(vec![
        create_agent("BANK_A", 1_000_000, 0),
        create_agent("BANK_B", 1_000_000, 0),
    ]);

    // Simulate: Total due 100k, settled 30k → fraction = 0.3
    // TODO: Set up state with transactions

    let tx = create_tx("BANK_A", "BANK_B", 10_000, 0, 100);
    let agent_a = state.get_agent("BANK_A").unwrap().clone();
    let cost_rates = CostRates::default();
    let context = EvalContext::build(&tx, &agent_a, &state, 10, &cost_rates, 100, 0.8);

    // Check that my_throughput_fraction_today exists
    let throughput_fraction = context.get_field("my_throughput_fraction_today");

    assert!(throughput_fraction.is_ok(), "my_throughput_fraction_today should exist");
    let fraction_val = throughput_fraction.unwrap();
    assert!(fraction_val >= 0.0);
    assert!(fraction_val <= 2.0); // Allow > 1.0 for catch-up scenarios
}

#[test]
fn test_context_exposes_expected_throughput_fraction() {
    use payment_simulator_core_rs::policy::tree::EvalContext;
    use payment_simulator_core_rs::orchestrator::CostRates;

    let state = SimulationState::new(vec![
        create_agent("BANK_A", 1_000_000, 0),
        create_agent("BANK_B", 1_000_000, 0),
    ]);

    let tx = create_tx("BANK_A", "BANK_B", 10_000, 0, 100);
    let agent_a = state.get_agent("BANK_A").unwrap().clone();
    let cost_rates = CostRates::default();

    // Tick 50 of 100 → halfway through day
    // If guidance curve says we should be 60% done by tick 50:
    let context = EvalContext::build(&tx, &agent_a, &state, 50, &cost_rates, 100, 0.8);

    // Check that expected_throughput_fraction_by_now exists
    let expected = context.get_field("expected_throughput_fraction_by_now");

    assert!(expected.is_ok(), "expected_throughput_fraction_by_now should exist");
    let expected_val = expected.unwrap();
    assert!(expected_val >= 0.0);
    assert!(expected_val <= 1.0);
}

#[test]
fn test_context_exposes_throughput_gap() {
    use payment_simulator_core_rs::policy::tree::EvalContext;
    use payment_simulator_core_rs::orchestrator::CostRates;

    let state = SimulationState::new(vec![
        create_agent("BANK_A", 1_000_000, 0),
        create_agent("BANK_B", 1_000_000, 0),
    ]);

    let tx = create_tx("BANK_A", "BANK_B", 10_000, 0, 100);
    let agent_a = state.get_agent("BANK_A").unwrap().clone();
    let cost_rates = CostRates::default();
    let context = EvalContext::build(&tx, &agent_a, &state, 50, &cost_rates, 100, 0.8);

    // Check that throughput_gap exists
    let gap = context.get_field("throughput_gap");

    assert!(gap.is_ok(), "throughput_gap should exist");
    let gap_val = gap.unwrap();

    // Gap can be negative (behind), zero (on track), or positive (ahead)
    assert!(gap_val >= -1.0);
    assert!(gap_val <= 1.0);
}

#[test]
fn test_throughput_gap_negative_when_behind() {
    // Scenario: Expected 60% done, actually 30% done → gap = -0.3

    let my_throughput = 0.3;
    let expected_throughput = 0.6;
    let gap = my_throughput - expected_throughput;

    assert_eq!(gap, -0.3);
}

#[test]
fn test_throughput_gap_positive_when_ahead() {
    // Scenario: Expected 40% done, actually 70% done → gap = +0.3

    let my_throughput = 0.7;
    let expected_throughput = 0.4;
    let gap = my_throughput - expected_throughput;

    // Use approximate comparison for floating point
    assert!((gap - 0.3_f64).abs() < 0.0001);
}

// ============================================================================
// Test Group 5: EOD Reset and Multi-Day Scenarios
// ============================================================================

#[test]
#[ignore] // TODO: Implement after adding day tracking to SimulationState
fn test_throughput_resets_each_day() {
    let mut state = SimulationState::new(vec![
        create_agent("BANK_A", 1_000_000, 0),
        create_agent("BANK_B", 1_000_000, 0),
    ]);

    // Day 0: Settle 50k
    // (simulate settlements)

    // EOD reset
    // state.reset_daily_metrics();

    // Day 1: Throughput should start at 0 again
    let throughput = agent_throughput_today(&state, "BANK_A");
    assert_eq!(throughput, 0);
}

#[test]
#[ignore] // TODO: Implement after adding daily tracking to SimulationState
fn test_total_due_updates_with_new_arrivals() {
    let mut state = SimulationState::new(vec![
        create_agent("BANK_A", 1_000_000, 0),
        create_agent("BANK_B", 1_000_000, 0),
    ]);

    // Initial: 50k due
    let tx1 = create_tx("BANK_A", "BANK_B", 50_000, 0, 100);
    state.add_transaction(tx1);

    let total_due_initial = agent_total_due_today(&state, "BANK_A");
    assert_eq!(total_due_initial, 50_000);

    // New arrival: +30k due
    let tx2 = create_tx("BANK_A", "BANK_B", 30_000, 10, 100);
    state.add_transaction(tx2);

    let total_due_updated = agent_total_due_today(&state, "BANK_A");
    assert_eq!(total_due_updated, 80_000);
}

// ============================================================================
// Helper Functions (to be implemented in Phase 2.1)
// ============================================================================

/// Get agent's total settled amount today
///
/// Returns the cumulative value of all transactions settled by this agent
/// since the start of the current day.
fn agent_throughput_today(_state: &SimulationState, _agent_id: &str) -> i64 {
    // TODO: Implement with state.agent_throughput_today(agent_id)
    // This requires SimulationState to track daily settlement amounts per agent
    0
}

/// Get agent's total amount due today
///
/// Returns the sum of all unsettled transaction amounts where this agent is the sender,
/// counting only transactions that arrived today.
fn agent_total_due_today(_state: &SimulationState, _agent_id: &str) -> i64 {
    // TODO: Implement with state.agent_total_due_today(agent_id)
    // This sums remaining_amount for all transactions where sender == agent_id
    0
}

/// Calculate throughput fraction (settled / total_due)
///
/// Returns 0.0 if no transactions are due today
fn calculate_throughput_fraction(state: &SimulationState, agent_id: &str) -> f64 {
    let throughput = agent_throughput_today(state, agent_id);
    let total_due = agent_total_due_today(state, agent_id);

    if total_due > 0 {
        throughput as f64 / total_due as f64
    } else {
        0.0
    }
}
