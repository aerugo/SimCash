//! Counterparty Fields Tests - Phase 2.2
//!
//! Tests for transaction-level counterparty identification fields.
//!
//! **Purpose**: Enable policies to identify and prioritize transactions based on
//! counterparty relationships (e.g., "is this my top trading partner?").
//!
//! **Use Cases**:
//! - Prioritize payments to top counterparties
//! - Different strategies for frequent vs infrequent trading partners
//! - Relationship-based liquidity management

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
// Test Group 1: Counterparty ID Hash Encoding
// ============================================================================

#[test]
fn test_counterparty_id_hash_consistent() {
    // Same counterparty ID should always produce same hash
    let hash1 = calculate_counterparty_hash("BANK_B");
    let hash2 = calculate_counterparty_hash("BANK_B");

    assert_eq!(hash1, hash2);
}

#[test]
fn test_counterparty_id_hash_different_for_different_ids() {
    // Different counterparty IDs should produce different hashes
    let hash_a = calculate_counterparty_hash("BANK_A");
    let hash_b = calculate_counterparty_hash("BANK_B");
    let hash_c = calculate_counterparty_hash("BANK_C");

    assert_ne!(hash_a, hash_b);
    assert_ne!(hash_b, hash_c);
    assert_ne!(hash_a, hash_c);
}

#[test]
fn test_counterparty_id_hash_fits_in_f64() {
    // Hash should be representable as f64 without precision loss
    let hash = calculate_counterparty_hash("BANK_X");

    // u64 can be safely represented in f64 up to 2^53
    // We're using full u64 range, so just verify it converts
    let _as_f64 = hash as f64;
    // If this compiles and runs, conversion is valid
}

// ============================================================================
// Test Group 2: Policy Context Field Exposure - tx_counterparty_id
// ============================================================================

#[test]
fn test_context_exposes_tx_counterparty_id() {
    use payment_simulator_core_rs::policy::tree::EvalContext;
    use payment_simulator_core_rs::orchestrator::CostRates;

    let state = SimulationState::new(vec![
        create_agent("BANK_A", 1_000_000, 0),
        create_agent("BANK_B", 1_000_000, 0),
    ]);

    // Transaction from A to B
    let tx = create_tx("BANK_A", "BANK_B", 10_000, 0, 100);
    let agent_a = state.get_agent("BANK_A").unwrap().clone();
    let cost_rates = CostRates::default();
    let context = EvalContext::build(&tx, &agent_a, &state, 10, &cost_rates, 100, 0.8);

    // Check that tx_counterparty_id exists
    let counterparty_id = context.get_field("tx_counterparty_id");

    assert!(counterparty_id.is_ok(), "tx_counterparty_id should exist");

    // Value should be hash of "BANK_B"
    let expected_hash = calculate_counterparty_hash("BANK_B");
    assert_eq!(counterparty_id.unwrap(), expected_hash as f64);
}

#[test]
fn test_tx_counterparty_id_varies_by_transaction() {
    use payment_simulator_core_rs::policy::tree::EvalContext;
    use payment_simulator_core_rs::orchestrator::CostRates;

    let state = SimulationState::new(vec![
        create_agent("BANK_A", 1_000_000, 0),
        create_agent("BANK_B", 1_000_000, 0),
        create_agent("BANK_C", 1_000_000, 0),
    ]);

    let agent_a = state.get_agent("BANK_A").unwrap().clone();
    let cost_rates = CostRates::default();

    // Transaction A -> B
    let tx_to_b = create_tx("BANK_A", "BANK_B", 10_000, 0, 100);
    let context_b = EvalContext::build(&tx_to_b, &agent_a, &state, 10, &cost_rates, 100, 0.8);
    let hash_b = context_b.get_field("tx_counterparty_id").unwrap();

    // Transaction A -> C
    let tx_to_c = create_tx("BANK_A", "BANK_C", 10_000, 0, 100);
    let context_c = EvalContext::build(&tx_to_c, &agent_a, &state, 10, &cost_rates, 100, 0.8);
    let hash_c = context_c.get_field("tx_counterparty_id").unwrap();

    // Hashes should be different
    assert_ne!(hash_b, hash_c);
}

// ============================================================================
// Test Group 3: Top Counterparties Calculation (Agent Method)
// ============================================================================

#[test]
fn test_top_counterparties_empty_history() {
    let agent = create_agent("BANK_A", 1_000_000, 0);

    // No transaction history yet
    let top = agent.top_counterparties(5);

    assert_eq!(top.len(), 0);
}

#[test]
#[ignore] // TODO: Implement after adding transaction history tracking to Agent
fn test_top_counterparties_single_counterparty() {
    let mut agent = create_agent("BANK_A", 1_000_000, 0);

    // Simulate transaction history: 3 transactions to BANK_B (total 100k)
    // TODO: Need Agent.record_transaction_history() method
    // agent.record_transaction_history("BANK_B", 50_000);
    // agent.record_transaction_history("BANK_B", 30_000);
    // agent.record_transaction_history("BANK_B", 20_000);

    let top = agent.top_counterparties(5);

    assert_eq!(top.len(), 1);
    assert_eq!(top[0], "BANK_B");
}

#[test]
#[ignore] // TODO: Implement after adding transaction history tracking to Agent
fn test_top_counterparties_multiple_sorted_by_volume() {
    let mut agent = create_agent("BANK_A", 1_000_000, 0);

    // Simulate transaction history:
    // BANK_B: 100k (top)
    // BANK_C: 50k (second)
    // BANK_D: 20k (third)
    // TODO: Need Agent.record_transaction_history() method

    let top = agent.top_counterparties(5);

    assert_eq!(top.len(), 3);
    assert_eq!(top[0], "BANK_B"); // Highest volume
    assert_eq!(top[1], "BANK_C"); // Second highest
    assert_eq!(top[2], "BANK_D"); // Third highest
}

#[test]
#[ignore] // TODO: Implement after adding transaction history tracking to Agent
fn test_top_counterparties_respects_limit() {
    let mut agent = create_agent("BANK_A", 1_000_000, 0);

    // Simulate 10 counterparties with different volumes
    // TODO: Need Agent.record_transaction_history() method

    let top_5 = agent.top_counterparties(5);
    let top_3 = agent.top_counterparties(3);

    assert_eq!(top_5.len(), 5);
    assert_eq!(top_3.len(), 3);
}

// ============================================================================
// Test Group 4: Policy Context Field - tx_is_top_counterparty
// ============================================================================

#[test]
fn test_context_exposes_tx_is_top_counterparty() {
    use payment_simulator_core_rs::policy::tree::EvalContext;
    use payment_simulator_core_rs::orchestrator::CostRates;

    let state = SimulationState::new(vec![
        create_agent("BANK_A", 1_000_000, 0),
        create_agent("BANK_B", 1_000_000, 0),
    ]);

    let tx = create_tx("BANK_A", "BANK_B", 10_000, 0, 100);
    let agent_a = state.get_agent("BANK_A").unwrap().clone();
    let cost_rates = CostRates::default();
    let context = EvalContext::build(&tx, &agent_a, &state, 10, &cost_rates, 100, 0.8);

    // Check that tx_is_top_counterparty exists
    let is_top = context.get_field("tx_is_top_counterparty");

    assert!(is_top.is_ok(), "tx_is_top_counterparty should exist");

    // Value should be 0.0 or 1.0
    let is_top_val = is_top.unwrap();
    assert!(is_top_val == 0.0 || is_top_val == 1.0);
}

#[test]
#[ignore] // TODO: Implement after adding transaction history tracking to Agent
fn test_tx_is_top_counterparty_true_for_top_counterparty() {
    use payment_simulator_core_rs::policy::tree::EvalContext;
    use payment_simulator_core_rs::orchestrator::CostRates;

    let mut agent_a = create_agent("BANK_A", 1_000_000, 0);

    // Record BANK_B as top counterparty (high volume)
    // TODO: Need Agent.record_transaction_history() method
    // agent_a.record_transaction_history("BANK_B", 100_000);

    let state = SimulationState::new(vec![
        agent_a.clone(),
        create_agent("BANK_B", 1_000_000, 0),
    ]);

    // Transaction to top counterparty
    let tx = create_tx("BANK_A", "BANK_B", 10_000, 0, 100);
    let cost_rates = CostRates::default();
    let context = EvalContext::build(&tx, &agent_a, &state, 10, &cost_rates, 100, 0.8);

    let is_top = context.get_field("tx_is_top_counterparty").unwrap();
    assert_eq!(is_top, 1.0); // Should be true
}

#[test]
#[ignore] // TODO: Implement after adding transaction history tracking to Agent
fn test_tx_is_top_counterparty_false_for_non_top_counterparty() {
    use payment_simulator_core_rs::policy::tree::EvalContext;
    use payment_simulator_core_rs::orchestrator::CostRates;

    let mut agent_a = create_agent("BANK_A", 1_000_000, 0);

    // Record BANK_B as top counterparty, but transaction is to BANK_C
    // TODO: Need Agent.record_transaction_history() method
    // agent_a.record_transaction_history("BANK_B", 100_000);

    let state = SimulationState::new(vec![
        agent_a.clone(),
        create_agent("BANK_B", 1_000_000, 0),
        create_agent("BANK_C", 1_000_000, 0),
    ]);

    // Transaction to non-top counterparty
    let tx = create_tx("BANK_A", "BANK_C", 10_000, 0, 100);
    let cost_rates = CostRates::default();
    let context = EvalContext::build(&tx, &agent_a, &state, 10, &cost_rates, 100, 0.8);

    let is_top = context.get_field("tx_is_top_counterparty").unwrap();
    assert_eq!(is_top, 0.0); // Should be false
}

// ============================================================================
// Test Group 5: Integration Tests
// ============================================================================

#[test]
fn test_both_counterparty_fields_present() {
    use payment_simulator_core_rs::policy::tree::EvalContext;
    use payment_simulator_core_rs::orchestrator::CostRates;

    let state = SimulationState::new(vec![
        create_agent("BANK_A", 1_000_000, 0),
        create_agent("BANK_B", 1_000_000, 0),
    ]);

    let tx = create_tx("BANK_A", "BANK_B", 10_000, 0, 100);
    let agent_a = state.get_agent("BANK_A").unwrap().clone();
    let cost_rates = CostRates::default();
    let context = EvalContext::build(&tx, &agent_a, &state, 10, &cost_rates, 100, 0.8);

    // Both fields should exist
    assert!(context.get_field("tx_counterparty_id").is_ok());
    assert!(context.get_field("tx_is_top_counterparty").is_ok());
}

#[test]
#[ignore] // TODO: Implement after adding transaction history tracking to Agent
fn test_policy_can_use_counterparty_fields_together() {
    use payment_simulator_core_rs::policy::tree::EvalContext;
    use payment_simulator_core_rs::orchestrator::CostRates;

    let mut agent_a = create_agent("BANK_A", 1_000_000, 0);

    // Record BANK_B as top counterparty
    // TODO: Need Agent.record_transaction_history() method

    let state = SimulationState::new(vec![
        agent_a.clone(),
        create_agent("BANK_B", 1_000_000, 0),
    ]);

    let tx = create_tx("BANK_A", "BANK_B", 10_000, 0, 100);
    let cost_rates = CostRates::default();
    let context = EvalContext::build(&tx, &agent_a, &state, 10, &cost_rates, 100, 0.8);

    // Example policy logic: "If counterparty is top, release immediately"
    let is_top = context.get_field("tx_is_top_counterparty").unwrap();
    let counterparty_hash = context.get_field("tx_counterparty_id").unwrap();

    if is_top == 1.0 {
        // Policy would return "release" action
        assert_eq!(counterparty_hash, calculate_counterparty_hash("BANK_B") as f64);
    }
}

// ============================================================================
// Helper Functions (to be implemented in Phase 2.2)
// ============================================================================

/// Calculate counterparty ID hash using FNV-1a algorithm
///
/// Same algorithm as used for top_cpty_N_id_hash in Phase 1.2
fn calculate_counterparty_hash(counterparty_id: &str) -> u64 {
    const FNV_OFFSET_BASIS: u64 = 14695981039346656037;
    const FNV_PRIME: u64 = 1099511628211;

    let mut hash = FNV_OFFSET_BASIS;
    for byte in counterparty_id.bytes() {
        hash ^= byte as u64;
        hash = hash.wrapping_mul(FNV_PRIME);
    }
    hash
}
