//! LSM Awareness Fields Tests - Phase 1.2
//!
//! Tests for own-bank Queue 2 composition fields that enable policies to
//! intentionally feed LSM by releasing to counterparties with matching inflows.
//!
//! **Privacy Constraint**: Only own-bank information is exposed. Policies cannot
//! see other banks' queue compositions or balances.
//!
//! **Use Case**: Agent A sees it has $100k outgoing to Agent B and $80k incoming
//! from Agent B in Queue 2. Policy can choose to release more to B to trigger
//! bilateral offset via LSM.

use payment_simulator_core_rs::{Agent, SimulationState, Transaction};

/// Helper to create agent
fn create_agent(id: &str, balance: i64, credit_limit: i64) -> Agent {
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
// Test Group 1: Per-Counterparty Queue 2 Value Calculations
// ============================================================================

#[test]
fn test_calculate_q2_out_value_to_counterparty_empty_queue() {
    // Agent has no transactions in Queue 2
    let agent = create_agent("BANK_A", 100_000, 50_000);
    let state = SimulationState::new(vec![
        agent.clone(),
        create_agent("BANK_B", 100_000, 50_000),
    ]);

    // Calculate outgoing value to BANK_B
    let q2_out = calculate_q2_out_to_counterparty(&state, "BANK_A", "BANK_B");

    assert_eq!(q2_out, 0);
}

#[test]
fn test_calculate_q2_out_value_to_counterparty_single_transaction() {
    let mut state = SimulationState::new(vec![
        create_agent("BANK_A", 100_000, 50_000),
        create_agent("BANK_B", 100_000, 50_000),
    ]);

    // Add transaction from A→B in Queue 2
    let tx1 = create_tx("BANK_A", "BANK_B", 50_000, 0, 100);
    state.add_transaction(tx1);
    state.queue_transaction(state.transactions().keys().next().unwrap().clone());

    // Calculate outgoing value to BANK_B
    let q2_out = calculate_q2_out_to_counterparty(&state, "BANK_A", "BANK_B");

    assert_eq!(q2_out, 50_000);
}

#[test]
fn test_calculate_q2_out_value_to_counterparty_multiple_transactions() {
    let mut state = SimulationState::new(vec![
        create_agent("BANK_A", 100_000, 50_000),
        create_agent("BANK_B", 100_000, 50_000),
        create_agent("BANK_C", 100_000, 50_000),
    ]);

    // Add transactions from A→B and A→C in Queue 2
    let tx1 = create_tx("BANK_A", "BANK_B", 30_000, 0, 100);
    let tx2 = create_tx("BANK_A", "BANK_B", 20_000, 0, 100);
    let tx3 = create_tx("BANK_A", "BANK_C", 40_000, 0, 100);

    state.add_transaction(tx1);
    state.add_transaction(tx2);
    state.add_transaction(tx3);

    // Queue all transactions
    for tx_id in state.transactions().keys().cloned().collect::<Vec<_>>() {
        state.queue_transaction(tx_id);
    }

    // Calculate outgoing value to BANK_B (should be sum of tx1 + tx2)
    let q2_out_b = calculate_q2_out_to_counterparty(&state, "BANK_A", "BANK_B");
    assert_eq!(q2_out_b, 50_000);

    // Calculate outgoing value to BANK_C
    let q2_out_c = calculate_q2_out_to_counterparty(&state, "BANK_A", "BANK_C");
    assert_eq!(q2_out_c, 40_000);
}

#[test]
fn test_calculate_q2_in_value_from_counterparty() {
    let mut state = SimulationState::new(vec![
        create_agent("BANK_A", 100_000, 50_000),
        create_agent("BANK_B", 100_000, 50_000),
    ]);

    // Add transaction from B→A in Queue 2
    let tx1 = create_tx("BANK_B", "BANK_A", 60_000, 0, 100);
    state.add_transaction(tx1);
    state.queue_transaction(state.transactions().keys().next().unwrap().clone());

    // Calculate incoming value from BANK_B (A's perspective)
    let q2_in = calculate_q2_in_from_counterparty(&state, "BANK_A", "BANK_B");

    assert_eq!(q2_in, 60_000);
}

#[test]
fn test_calculate_bilateral_net_q2_balanced() {
    let mut state = SimulationState::new(vec![
        create_agent("BANK_A", 100_000, 50_000),
        create_agent("BANK_B", 100_000, 50_000),
    ]);

    // Add transactions: A→B (50k) and B→A (50k)
    let tx1 = create_tx("BANK_A", "BANK_B", 50_000, 0, 100);
    let tx2 = create_tx("BANK_B", "BANK_A", 50_000, 0, 100);

    state.add_transaction(tx1);
    state.add_transaction(tx2);

    for tx_id in state.transactions().keys().cloned().collect::<Vec<_>>() {
        state.queue_transaction(tx_id);
    }

    // Calculate bilateral net (A's perspective)
    let q2_out = calculate_q2_out_to_counterparty(&state, "BANK_A", "BANK_B");
    let q2_in = calculate_q2_in_from_counterparty(&state, "BANK_A", "BANK_B");
    let bilateral_net = (q2_out as i64) - (q2_in as i64);

    assert_eq!(q2_out, 50_000);
    assert_eq!(q2_in, 50_000);
    assert_eq!(bilateral_net, 0); // Balanced - perfect bilateral offset candidate!
}

#[test]
fn test_calculate_bilateral_net_q2_net_outflow() {
    let mut state = SimulationState::new(vec![
        create_agent("BANK_A", 100_000, 50_000),
        create_agent("BANK_B", 100_000, 50_000),
    ]);

    // Add transactions: A→B (70k) and B→A (30k)
    let tx1 = create_tx("BANK_A", "BANK_B", 70_000, 0, 100);
    let tx2 = create_tx("BANK_B", "BANK_A", 30_000, 0, 100);

    state.add_transaction(tx1);
    state.add_transaction(tx2);

    for tx_id in state.transactions().keys().cloned().collect::<Vec<_>>() {
        state.queue_transaction(tx_id);
    }

    // Calculate bilateral net (A's perspective)
    let q2_out = calculate_q2_out_to_counterparty(&state, "BANK_A", "BANK_B");
    let q2_in = calculate_q2_in_from_counterparty(&state, "BANK_A", "BANK_B");
    let bilateral_net = (q2_out as i64) - (q2_in as i64);

    assert_eq!(q2_out, 70_000);
    assert_eq!(q2_in, 30_000);
    assert_eq!(bilateral_net, 40_000); // Net outflow - A owes B more
}

// ============================================================================
// Test Group 2: Policy Context Field Exposure
// ============================================================================

#[test]
fn test_context_exposes_q2_counterparty_fields() {
    use payment_simulator_core_rs::policy::tree::EvalContext;
    use payment_simulator_core_rs::orchestrator::CostRates;

    let mut state = SimulationState::new(vec![
        create_agent("BANK_A", 100_000, 50_000),
        create_agent("BANK_B", 100_000, 50_000),
    ]);

    // Add transactions in Queue 2: A→B (50k), B→A (30k)
    let tx_ab = create_tx("BANK_A", "BANK_B", 50_000, 0, 100);
    let tx_ba = create_tx("BANK_B", "BANK_A", 30_000, 0, 100);

    state.add_transaction(tx_ab.clone());
    state.add_transaction(tx_ba);

    for tx_id in state.transactions().keys().cloned().collect::<Vec<_>>() {
        state.queue_transaction(tx_id);
    }

    // Build context for a transaction from A→B
    let agent_a = state.get_agent("BANK_A").unwrap().clone();
    let cost_rates = CostRates::default();
    let context = EvalContext::build(&tx_ab, &agent_a, &state, 10, &cost_rates, 100, 0.8);

    // Check that LSM-relevant fields exist
    // These fields don't exist yet - test will fail until implemented
    let q2_out = context.get_field("my_q2_out_value_to_counterparty");
    let q2_in = context.get_field("my_q2_in_value_from_counterparty");
    let bilateral_net = context.get_field("my_bilateral_net_q2");

    assert!(q2_out.is_ok(), "my_q2_out_value_to_counterparty should exist");
    assert!(q2_in.is_ok(), "my_q2_in_value_from_counterparty should exist");
    assert!(bilateral_net.is_ok(), "my_bilateral_net_q2 should exist");

    assert_eq!(q2_out.unwrap(), 50_000.0);
    assert_eq!(q2_in.unwrap(), 30_000.0);
    assert_eq!(bilateral_net.unwrap(), 20_000.0); // 50k - 30k
}

#[test]
fn test_context_q2_fields_for_transaction_with_no_matching_inflow() {
    use payment_simulator_core_rs::policy::tree::EvalContext;
    use payment_simulator_core_rs::orchestrator::CostRates;

    let mut state = SimulationState::new(vec![
        create_agent("BANK_A", 100_000, 50_000),
        create_agent("BANK_B", 100_000, 50_000),
    ]);

    // Only A→B in Queue 2, no B→A
    let tx_ab = create_tx("BANK_A", "BANK_B", 40_000, 0, 100);
    state.add_transaction(tx_ab.clone());
    state.queue_transaction(state.transactions().keys().next().unwrap().clone());

    let agent_a = state.get_agent("BANK_A").unwrap().clone();
    let cost_rates = CostRates::default();
    let context = EvalContext::build(&tx_ab, &agent_a, &state, 10, &cost_rates, 100, 0.8);

    // Fields should exist but show no inflow
    let q2_out = context.get_field("my_q2_out_value_to_counterparty").unwrap();
    let q2_in = context.get_field("my_q2_in_value_from_counterparty").unwrap();
    let bilateral_net = context.get_field("my_bilateral_net_q2").unwrap();

    assert_eq!(q2_out, 40_000.0);
    assert_eq!(q2_in, 0.0); // No inflow from B
    assert_eq!(bilateral_net, 40_000.0); // Pure outflow
}

// ============================================================================
// Test Group 3: Top Counterparties Aggregation
// ============================================================================

#[test]
fn test_calculate_top_counterparties_by_q2_outflow() {
    let mut state = SimulationState::new(vec![
        create_agent("BANK_A", 100_000, 50_000),
        create_agent("BANK_B", 100_000, 50_000),
        create_agent("BANK_C", 100_000, 50_000),
        create_agent("BANK_D", 100_000, 50_000),
        create_agent("BANK_E", 100_000, 50_000),
        create_agent("BANK_F", 100_000, 50_000),
    ]);

    // Create transactions with varying amounts to different counterparties
    let transactions = vec![
        ("BANK_A", "BANK_B", 80_000),  // Largest outflow
        ("BANK_A", "BANK_C", 60_000),  // 2nd largest
        ("BANK_A", "BANK_D", 40_000),  // 3rd
        ("BANK_A", "BANK_E", 20_000),  // 4th
        ("BANK_A", "BANK_F", 10_000),  // 5th
    ];

    for (sender, receiver, amount) in transactions {
        let tx = create_tx(sender, receiver, amount, 0, 100);
        state.add_transaction(tx);
    }

    // Queue all transactions
    for tx_id in state.transactions().keys().cloned().collect::<Vec<_>>() {
        state.queue_transaction(tx_id);
    }

    // Calculate top 5 counterparties for BANK_A
    let top_cpty = calculate_top_counterparties_by_q2_outflow(&state, "BANK_A", 5);

    assert_eq!(top_cpty.len(), 5);
    assert_eq!(top_cpty[0], ("BANK_B".to_string(), 80_000));
    assert_eq!(top_cpty[1], ("BANK_C".to_string(), 60_000));
    assert_eq!(top_cpty[2], ("BANK_D".to_string(), 40_000));
    assert_eq!(top_cpty[3], ("BANK_E".to_string(), 20_000));
    assert_eq!(top_cpty[4], ("BANK_F".to_string(), 10_000));
}

#[test]
fn test_context_exposes_top_counterparty_fields() {
    use payment_simulator_core_rs::policy::tree::EvalContext;
    use payment_simulator_core_rs::orchestrator::CostRates;

    let mut state = SimulationState::new(vec![
        create_agent("BANK_A", 100_000, 50_000),
        create_agent("BANK_B", 100_000, 50_000),
        create_agent("BANK_C", 100_000, 50_000),
        create_agent("BANK_D", 100_000, 50_000),
    ]);

    // Create Q2 transactions
    for (sender, receiver, amount) in [
        ("BANK_A", "BANK_B", 90_000),
        ("BANK_A", "BANK_C", 70_000),
        ("BANK_A", "BANK_D", 50_000),
    ] {
        let tx = create_tx(sender, receiver, amount, 0, 100);
        state.add_transaction(tx);
    }

    for tx_id in state.transactions().keys().cloned().collect::<Vec<_>>() {
        state.queue_transaction(tx_id);
    }

    // Build context
    let tx = create_tx("BANK_A", "BANK_B", 10_000, 0, 100);
    let agent_a = state.get_agent("BANK_A").unwrap().clone();
    let cost_rates = CostRates::default();
    let context = EvalContext::build(&tx, &agent_a, &state, 10, &cost_rates, 100, 0.8);

    // Check top counterparty fields exist
    // These fields don't exist yet - test will fail until implemented
    let top_1_value = context.get_field("my_q2_out_value_top_1");
    let top_2_value = context.get_field("my_q2_out_value_top_2");
    let top_3_value = context.get_field("my_q2_out_value_top_3");

    let top_1_id = context.get_field("top_cpty_1_id");
    let top_2_id = context.get_field("top_cpty_2_id");
    let top_3_id = context.get_field("top_cpty_3_id");

    assert!(top_1_value.is_ok(), "my_q2_out_value_top_1 should exist");
    assert!(top_2_value.is_ok(), "my_q2_out_value_top_2 should exist");
    assert!(top_3_value.is_ok(), "my_q2_out_value_top_3 should exist");

    assert_eq!(top_1_value.unwrap(), 90_000.0); // BANK_B
    assert_eq!(top_2_value.unwrap(), 70_000.0); // BANK_C
    assert_eq!(top_3_value.unwrap(), 50_000.0); // BANK_D

    // Note: Categorical fields (top_cpty_*_id) will be handled differently
    // For now, we'll store as f64 hash or enum value (TBD)
}

// ============================================================================
// Test Group 4: Privacy Constraint Verification
// ============================================================================

#[test]
fn test_context_does_not_expose_other_banks_queues() {
    use payment_simulator_core_rs::policy::tree::EvalContext;
    use payment_simulator_core_rs::orchestrator::CostRates;

    let mut state = SimulationState::new(vec![
        create_agent("BANK_A", 100_000, 50_000),
        create_agent("BANK_B", 100_000, 50_000),
        create_agent("BANK_C", 100_000, 50_000),
    ]);

    // Add B→C transaction (BANK_A should NOT see this)
    let tx_bc = create_tx("BANK_B", "BANK_C", 80_000, 0, 100);
    state.add_transaction(tx_bc);
    state.queue_transaction(state.transactions().keys().next().unwrap().clone());

    // Build context for BANK_A
    let tx_a = create_tx("BANK_A", "BANK_B", 10_000, 0, 100);
    let agent_a = state.get_agent("BANK_A").unwrap().clone();
    let cost_rates = CostRates::default();
    let context = EvalContext::build(&tx_a, &agent_a, &state, 10, &cost_rates, 100, 0.8);

    // BANK_A should only see its own Q2 composition
    // Fields like "bank_b_q2_out_value" should NOT exist
    let field_names = context.field_names();

    // Check that no fields expose other banks' specific queue data
    for field_name in field_names {
        assert!(
            !field_name.contains("bank_b_q2") && !field_name.contains("bank_c_q2"),
            "Context should not expose other banks' queue compositions"
        );
    }
}

// ============================================================================
// Helper Functions (to be implemented in Phase 1.2)
// ============================================================================

/// Calculate total value of agent's outgoing Queue 2 transactions to a specific counterparty
fn calculate_q2_out_to_counterparty(state: &SimulationState, agent_id: &str, counterparty_id: &str) -> i64 {
    let mut total = 0i64;

    for tx_id in state.rtgs_queue() {
        if let Some(tx) = state.get_transaction(tx_id) {
            if tx.sender_id() == agent_id && tx.receiver_id() == counterparty_id {
                total += tx.remaining_amount();
            }
        }
    }

    total
}

/// Calculate total value of counterparty's outgoing Queue 2 transactions to this agent (inflows)
fn calculate_q2_in_from_counterparty(state: &SimulationState, agent_id: &str, counterparty_id: &str) -> i64 {
    let mut total = 0i64;

    for tx_id in state.rtgs_queue() {
        if let Some(tx) = state.get_transaction(tx_id) {
            if tx.sender_id() == counterparty_id && tx.receiver_id() == agent_id {
                total += tx.remaining_amount();
            }
        }
    }

    total
}

/// Calculate top N counterparties by outgoing Queue 2 value
fn calculate_top_counterparties_by_q2_outflow(
    state: &SimulationState,
    agent_id: &str,
    n: usize,
) -> Vec<(String, i64)> {
    use std::collections::HashMap;

    // Aggregate by counterparty
    let mut by_counterparty: HashMap<String, i64> = HashMap::new();

    for tx_id in state.rtgs_queue() {
        if let Some(tx) = state.get_transaction(tx_id) {
            if tx.sender_id() == agent_id {
                *by_counterparty.entry(tx.receiver_id().to_string()).or_insert(0) += tx.remaining_amount();
            }
        }
    }

    // Sort by value descending
    let mut sorted: Vec<_> = by_counterparty.into_iter().collect();
    sorted.sort_by(|a, b| b.1.cmp(&a.1)); // Descending by value

    // Take top N
    sorted.into_iter().take(n).collect()
}
