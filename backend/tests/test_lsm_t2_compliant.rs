//! T2-Compliant LSM Tests
//!
//! Tests for multilateral cycle settlement with unequal payment values,
//! following T2 RTGS specifications.
//!
//! Key T2 Principles Tested:
//! 1. Individual payments settle in full or not at all (no partial settlement)
//! 2. Multilateral cycles settle all transactions at full value
//! 3. Each participant must cover their net position (incoming - outgoing)
//! 4. All-or-nothing atomicity (if one participant can't cover, cycle fails)

use std::collections::BTreeMap;
use payment_simulator_core_rs::models::agent::Agent;
use payment_simulator_core_rs::models::state::SimulationState;
use payment_simulator_core_rs::models::transaction::{Transaction, TransactionStatus};
use payment_simulator_core_rs::settlement::lsm::{detect_cycles, settle_cycle};

// ============================================================================
// Test Helpers
// ============================================================================

/// Create a test state with specified agents (id, balance, credit_limit)
fn create_test_state_with_agents(agents: Vec<(&str, i64, i64)>) -> SimulationState {
    let agent_list: Vec<Agent> = agents
        .into_iter()
        .map(|(id, balance, credit)| {
            Agent::new(id.to_string(), balance, credit)
        })
        .collect();

    SimulationState::new(agent_list)
}

/// Create a queued transaction and add to RTGS queue
fn create_queued_transaction(
    state: &mut SimulationState,
    sender: &str,
    receiver: &str,
    amount: i64,
) -> String {
    let tx = Transaction::new(
        sender.to_string(),
        receiver.to_string(),
        amount,
        0,   // arrival_tick
        100, // deadline_tick
    );

    let tx_id = tx.id().to_string();
    state.add_transaction(tx);
    state.rtgs_queue_mut().push(tx_id.clone());
    tx_id
}

// ============================================================================
// Test 1: Bilateral Offsetting Still Works (Sanity Check)
// ============================================================================

#[test]
fn test_bilateral_offset_unequal_amounts_unchanged() {
    // Verify that bilateral offsetting (already correct) still works
    // A→B 500k, B→A 300k → both settle with A covering net 200k

    let mut state = create_test_state_with_agents(vec![
        ("A", 200_000, 0), // Has 200k to cover net outflow
        ("B", 0, 0),
    ]);

    let tx_ab = create_queued_transaction(&mut state, "A", "B", 500_000);
    let tx_ba = create_queued_transaction(&mut state, "B", "A", 300_000);

    // Detect cycle (bilateral is a 2-agent cycle)
    // Note: Bilateral cycles are detected twice (A→B→A and B→A→B), which is fine
    let cycles = detect_cycles(&state, 4);
    assert!(
        !cycles.is_empty(),
        "Should detect at least one bilateral cycle"
    );

    // Use first cycle (both are equivalent)
    let cycle = &cycles[0];
    assert_eq!(cycle.agents.len(), 3, "Cycle: A, B, A (3 nodes)");

    // Settle cycle
    let mut to_remove = BTreeMap::new();
    let result = settle_cycle(&mut state, cycle, 5, &mut to_remove).expect("Settlement should succeed");

    // Both transactions should settle
    assert_eq!(result.transactions_affected, 2);

    // Verify final balances: A=-200k, B=+200k (net 200k A→B)
    assert_eq!(state.get_agent("A").unwrap().balance(), 0); // Started at 200k, net -200k
    assert_eq!(state.get_agent("B").unwrap().balance(), 200_000);

    // Both transactions fully settled
    let tx_ab_final = state.get_transaction(&tx_ab).unwrap();
    let tx_ba_final = state.get_transaction(&tx_ba).unwrap();
    assert!(tx_ab_final.is_fully_settled());
    assert!(tx_ba_final.is_fully_settled());
}

// ============================================================================
// Test 2: Equal-Value Cycle (Backward Compatibility)
// ============================================================================

#[test]
fn test_cycle_equal_amounts_backward_compatible() {
    // A→B→C→A, all 500k (net-zero for everyone)
    // Should work exactly as before

    let mut state = create_test_state_with_agents(vec![
        ("A", 0, 0),
        ("B", 0, 0),
        ("C", 0, 0),
    ]);

    let tx_ab = create_queued_transaction(&mut state, "A", "B", 500_000);
    let tx_bc = create_queued_transaction(&mut state, "B", "C", 500_000);
    let tx_ca = create_queued_transaction(&mut state, "C", "A", 500_000);

    // Detect cycle
    let cycles = detect_cycles(&state, 4);
    assert!(!cycles.is_empty(), "Should detect at least one cycle");

    let cycle = &cycles[0];
    assert_eq!(cycle.agents.len(), 4, "Cycle: A, B, C, A");

    // Settle cycle
    let mut to_remove = BTreeMap::new();
    let result = settle_cycle(&mut state, cycle, 5, &mut to_remove).expect("Settlement should succeed");

    assert_eq!(result.transactions_affected, 3);
    // T2-compliant: settled_value is SUM of all transaction values, not min
    assert_eq!(
        result.settled_value, 1_500_000,
        "Should settle total value (500k + 500k + 500k = 1.5M)"
    );

    // All agents should have zero balance (net-zero cycle)
    assert_eq!(state.get_agent("A").unwrap().balance(), 0);
    assert_eq!(state.get_agent("B").unwrap().balance(), 0);
    assert_eq!(state.get_agent("C").unwrap().balance(), 0);

    // All transactions fully settled
    assert!(state.get_transaction(&tx_ab).unwrap().is_fully_settled());
    assert!(state.get_transaction(&tx_bc).unwrap().is_fully_settled());
    assert!(state.get_transaction(&tx_ca).unwrap().is_fully_settled());
}

// ============================================================================
// Test 3: NEW - Multilateral Cycle with Unequal Amounts (T2-Compliant)
// ============================================================================

#[test]
fn test_cycle_unequal_amounts_t2_compliant() {
    // A→B (500k), B→C (800k), C→A (700k)
    // Net positions: A=+200k, B=-300k, C=+100k
    // B has 300k balance → can cover net outflow → cycle should settle

    let mut state = create_test_state_with_agents(vec![
        ("A", 0, 500_000),    // Credit available but not needed
        ("B", 300_000, 0),    // Has exactly 300k to cover net outflow
        ("C", 0, 200_000),    // Credit available but not needed
    ]);

    let tx_ab = create_queued_transaction(&mut state, "A", "B", 500_000);
    let tx_bc = create_queued_transaction(&mut state, "B", "C", 800_000);
    let tx_ca = create_queued_transaction(&mut state, "C", "A", 700_000);

    // Detect cycle
    let cycles = detect_cycles(&state, 4);
    assert!(!cycles.is_empty(), "Should detect at least one 3-agent cycle");

    let cycle = &cycles[0];

    // Settle cycle
    let mut to_remove = BTreeMap::new();
    let result = settle_cycle(&mut state, cycle, 5, &mut to_remove).expect("Settlement should succeed");

    // ALL transactions should settle at FULL value (not min)
    assert_eq!(result.transactions_affected, 3, "All 3 transactions should settle");

    // CRITICAL: settled_value should be SUM of all transactions (2M), not min (500k)
    // This is the key difference from current implementation
    assert_eq!(
        result.settled_value, 2_000_000,
        "Should settle total value (500k + 800k + 700k = 2M), not min (500k)"
    );

    // Verify final balances match net positions
    // A: receives 700k, sends 500k → net +200k
    assert_eq!(
        state.get_agent("A").unwrap().balance(),
        200_000,
        "A should have net +200k"
    );

    // B: receives 500k, sends 800k → net -300k (started at 300k, ends at 0)
    assert_eq!(
        state.get_agent("B").unwrap().balance(),
        0,
        "B should have 0 (300k start - 300k net outflow)"
    );

    // C: receives 800k, sends 700k → net +100k
    assert_eq!(
        state.get_agent("C").unwrap().balance(),
        100_000,
        "C should have net +100k"
    );

    // All transactions fully settled (not partial)
    let tx_ab_final = state.get_transaction(&tx_ab).unwrap();
    let tx_bc_final = state.get_transaction(&tx_bc).unwrap();
    let tx_ca_final = state.get_transaction(&tx_ca).unwrap();

    assert!(tx_ab_final.is_fully_settled(), "A→B should be fully settled");
    assert_eq!(tx_ab_final.settled_amount(), 500_000, "A→B settled at full 500k");

    assert!(tx_bc_final.is_fully_settled(), "B→C should be fully settled");
    assert_eq!(tx_bc_final.settled_amount(), 800_000, "B→C settled at full 800k");

    assert!(tx_ca_final.is_fully_settled(), "C→A should be fully settled");
    assert_eq!(tx_ca_final.settled_amount(), 700_000, "C→A settled at full 700k");

    // Conservation check: sum of all balances should equal sum of initial balances
    let final_sum = state.get_agent("A").unwrap().balance()
        + state.get_agent("B").unwrap().balance()
        + state.get_agent("C").unwrap().balance();
    assert_eq!(final_sum, 300_000, "Balance conservation: started with 300k, should end with 300k");
}

// ============================================================================
// Test 4: Cycle Fails When Participant Lacks Liquidity (All-or-Nothing)
// ============================================================================

#[test]
fn test_cycle_insufficient_liquidity_fails_atomically() {
    // Same cycle as Test 3, but B only has 200k (needs 300k)
    // Entire cycle should fail, NO transactions settle

    let mut state = create_test_state_with_agents(vec![
        ("A", 0, 500_000),
        ("B", 200_000, 0),    // Only 200k, needs 300k → INSUFFICIENT
        ("C", 0, 200_000),
    ]);

    let tx_ab = create_queued_transaction(&mut state, "A", "B", 500_000);
    let tx_bc = create_queued_transaction(&mut state, "B", "C", 800_000);
    let tx_ca = create_queued_transaction(&mut state, "C", "A", 700_000);

    // Detect cycle
    let cycles = detect_cycles(&state, 4);
    assert!(!cycles.is_empty());

    let cycle = &cycles[0];

    // Attempt to settle cycle - should FAIL
    let mut to_remove = BTreeMap::new();
    let result = settle_cycle(&mut state, cycle, 5, &mut to_remove);

    assert!(result.is_err(), "Settlement should fail due to insufficient liquidity");

    // CRITICAL: Atomicity - NO transactions should have settled
    assert_eq!(
        state.rtgs_queue().len(),
        3,
        "All 3 transactions should remain in queue"
    );

    // Balances unchanged (atomicity)
    assert_eq!(state.get_agent("A").unwrap().balance(), 0);
    assert_eq!(state.get_agent("B").unwrap().balance(), 200_000);
    assert_eq!(state.get_agent("C").unwrap().balance(), 0);

    // All transactions still pending
    assert_eq!(
        *state.get_transaction(&tx_ab).unwrap().status(),
        TransactionStatus::Pending
    );
    assert_eq!(
        *state.get_transaction(&tx_bc).unwrap().status(),
        TransactionStatus::Pending
    );
    assert_eq!(
        *state.get_transaction(&tx_ca).unwrap().status(),
        TransactionStatus::Pending
    );
}

// ============================================================================
// Test 5: Cycle with Credit Available (Net Outflow Covered by Credit)
// ============================================================================

#[test]
fn test_cycle_net_outflow_covered_by_credit() {
    // A→B (500k), B→C (800k), C→A (700k)
    // B has 0 balance but 300k credit → should cover -300k net outflow

    let mut state = create_test_state_with_agents(vec![
        ("A", 0, 500_000),
        ("B", 0, 300_000),    // No balance, but 300k credit
        ("C", 0, 200_000),
    ]);

    let tx_ab = create_queued_transaction(&mut state, "A", "B", 500_000);
    let tx_bc = create_queued_transaction(&mut state, "B", "C", 800_000);
    let tx_ca = create_queued_transaction(&mut state, "C", "A", 700_000);

    let cycles = detect_cycles(&state, 4);
    let cycle = &cycles[0];

    let mut to_remove = BTreeMap::new();
    let result = settle_cycle(&mut state, cycle, 5, &mut to_remove).expect("Should settle using credit");

    assert_eq!(result.transactions_affected, 3);
    assert_eq!(result.settled_value, 2_000_000);

    // B should have -300k balance (using credit)
    assert_eq!(
        state.get_agent("B").unwrap().balance(),
        -300_000,
        "B should have -300k (within 300k credit limit)"
    );
}

// ============================================================================
// Test 6: Four-Agent Cycle with Unequal Amounts
// ============================================================================

#[test]
fn test_four_agent_cycle_unequal() {
    // A→B (1M), B→C (1.2M), C→D (800k), D→A (900k)
    // Net: A=-100k, B=-200k, C=+400k, D=-100k
    // Total net outflows: 400k (A+B+D)

    let mut state = create_test_state_with_agents(vec![
        ("A", 100_000, 0),    // Has 100k to cover -100k net
        ("B", 200_000, 0),    // Has 200k to cover -200k net
        ("C", 0, 0),          // Net inflow, no liquidity needed
        ("D", 100_000, 0),    // Has 100k to cover -100k net
    ]);

    let tx_ab = create_queued_transaction(&mut state, "A", "B", 1_000_000);
    let tx_bc = create_queued_transaction(&mut state, "B", "C", 1_200_000);
    let tx_cd = create_queued_transaction(&mut state, "C", "D", 800_000);
    let tx_da = create_queued_transaction(&mut state, "D", "A", 900_000);

    let cycles = detect_cycles(&state, 5); // Allow length 5
    assert!(!cycles.is_empty(), "Should detect 4-agent cycle");

    let cycle = &cycles[0];
    assert_eq!(cycle.agents.len(), 5, "Cycle: A, B, C, D, A");

    let mut to_remove = BTreeMap::new();
    let result = settle_cycle(&mut state, cycle, 5, &mut to_remove).expect("Should settle with available liquidity");

    assert_eq!(result.transactions_affected, 4);
    assert_eq!(
        result.settled_value,
        3_900_000,
        "Total: 1M + 1.2M + 800k + 900k = 3.9M"
    );

    // Verify net positions
    assert_eq!(state.get_agent("A").unwrap().balance(), 0); // 100k - 100k net = 0
    assert_eq!(state.get_agent("B").unwrap().balance(), 0); // 200k - 200k net = 0
    assert_eq!(state.get_agent("C").unwrap().balance(), 400_000); // 0 + 400k net
    assert_eq!(state.get_agent("D").unwrap().balance(), 0); // 100k - 100k net = 0
}

// ============================================================================
// Test 7: Net Position Calculation Correctness
// ============================================================================

#[test]
fn test_net_positions_sum_to_zero() {
    // For ANY valid cycle, sum of net positions must equal zero (conservation)
    // Test with various cycle configurations

    let mut state = create_test_state_with_agents(vec![
        ("A", 1_000_000, 0),
        ("B", 1_000_000, 0),
        ("C", 1_000_000, 0),
    ]);

    // Create cycle with arbitrary unequal amounts
    create_queued_transaction(&mut state, "A", "B", 123_456);
    create_queued_transaction(&mut state, "B", "C", 987_654);
    create_queued_transaction(&mut state, "C", "A", 456_789);

    let cycles = detect_cycles(&state, 4);
    let cycle = &cycles[0];

    let mut to_remove = BTreeMap::new();
    let result = settle_cycle(&mut state, cycle, 5, &mut to_remove).expect("Should settle");

    // Sum of all balance changes should be zero
    let balance_changes = state.get_agent("A").unwrap().balance()
        + state.get_agent("B").unwrap().balance()
        + state.get_agent("C").unwrap().balance();

    assert_eq!(
        balance_changes, 3_000_000,
        "Total balance unchanged (conservation)"
    );
}

// ============================================================================
// Test 8: Determinism with Unequal Cycles
// ============================================================================

#[test]
fn test_lsm_determinism_with_unequal_cycles() {
    // Run same simulation twice with same seed
    // Verify identical cycle detection and settlement order

    let run_simulation = || -> (Vec<i64>, i64) {
        let mut state = create_test_state_with_agents(vec![
            ("A", 500_000, 0),
            ("B", 500_000, 0),
            ("C", 500_000, 0),
        ]);

        let _tx_ab = create_queued_transaction(&mut state, "A", "B", 500_000);
        let _tx_bc = create_queued_transaction(&mut state, "B", "C", 800_000);
        let _tx_ca = create_queued_transaction(&mut state, "C", "A", 700_000);

        let cycles = detect_cycles(&state, 4);
        let cycle = &cycles[0];
        let mut to_remove = BTreeMap::new();
    let result = settle_cycle(&mut state, cycle, 5, &mut to_remove).expect("Should settle");

        let balances = vec![
            state.get_agent("A").unwrap().balance(),
            state.get_agent("B").unwrap().balance(),
            state.get_agent("C").unwrap().balance(),
        ];

        (balances, result.settled_value)
    };

    let (balances1, settled_value1) = run_simulation();
    let (balances2, settled_value2) = run_simulation();

    assert_eq!(balances1, balances2, "Balances should be deterministic");
    assert_eq!(
        settled_value1, settled_value2,
        "Settled value should be deterministic"
    );
}

// ============================================================================
// Test 9: Cycle Exceeding Credit Limit Fails
// ============================================================================

#[test]
fn test_cycle_exceeding_credit_limit_fails() {
    // B needs 300k net outflow but only has 100k balance + 100k credit = 200k total

    let mut state = create_test_state_with_agents(vec![
        ("A", 0, 500_000),
        ("B", 100_000, 100_000),  // 200k total, needs 300k
        ("C", 0, 200_000),
    ]);

    create_queued_transaction(&mut state, "A", "B", 500_000);
    create_queued_transaction(&mut state, "B", "C", 800_000);
    create_queued_transaction(&mut state, "C", "A", 700_000);

    let cycles = detect_cycles(&state, 4);
    let cycle = &cycles[0];

    let mut to_remove = BTreeMap::new();
    let result = settle_cycle(&mut state, cycle, 5, &mut to_remove);

    assert!(
        result.is_err(),
        "Should fail when net outflow exceeds balance + credit"
    );

    // All transactions remain queued
    assert_eq!(state.rtgs_queue().len(), 3);
}

// ============================================================================
// Test 10: Multiple Cycles - Process Highest Value First
// ============================================================================

#[test]
fn test_multiple_cycles_priority() {
    // Create two cycles, verify larger value cycle settles first

    let mut state = create_test_state_with_agents(vec![
        ("A", 1_000_000, 0),
        ("B", 1_000_000, 0),
        ("C", 1_000_000, 0),
        ("D", 1_000_000, 0),
    ]);

    // Cycle 1: A↔B (small values)
    create_queued_transaction(&mut state, "A", "B", 100_000);
    create_queued_transaction(&mut state, "B", "A", 90_000);

    // Cycle 2: C↔D (large values)
    create_queued_transaction(&mut state, "C", "D", 500_000);
    create_queued_transaction(&mut state, "D", "C", 480_000);

    let cycles = detect_cycles(&state, 4);
    assert!(cycles.len() >= 2, "Should detect at least both cycles");

    // Cycles should be sorted by total_value (descending)
    // First cycle should be largest (C↔D)
    assert!(
        cycles[0].total_value >= cycles[1].total_value,
        "Larger cycle should be first"
    );

    // First cycle should involve C and D (largest value)
    assert!(
        cycles[0].agents.contains(&"C".to_string())
            && cycles[0].agents.contains(&"D".to_string()),
        "First cycle should be C↔D (largest total_value)"
    );
}
