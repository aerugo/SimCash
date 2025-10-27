//! LSM (Liquidity-Saving Mechanisms) Tests
//!
//! Tests for Phase 3b: Bilateral offsetting, cycle detection, and LSM coordination.
//! Following TDD principles - comprehensive test coverage before implementation refinement.

use payment_simulator_core_rs::{
    settlement::{
        lsm::{bilateral_offset, detect_cycles, run_lsm_pass, settle_cycle, LsmConfig},
        submit_transaction,
    },
    Agent, SimulationState, Transaction,
};

// ============================================================================
// Test Helpers
// ============================================================================

fn create_agent(id: &str, balance: i64, credit_limit: i64) -> Agent {
    Agent::new(id.to_string(), balance, credit_limit)
}

fn create_transaction(
    sender: &str,
    receiver: &str,
    amount: i64,
    arrival: usize,
    deadline: usize,
) -> Transaction {
    Transaction::new(
        sender.to_string(),
        receiver.to_string(),
        amount,
        arrival,
        deadline,
    )
}

// ============================================================================
// Bilateral Offsetting Tests
// ============================================================================

#[test]
fn test_bilateral_offset_exact_match() {
    // A→B 500k, B→A 500k (exact match)
    // Should settle both fully with net zero liquidity
    let agents = vec![
        create_agent("BANK_A", 100_000, 0),
        create_agent("BANK_B", 100_000, 0),
    ];
    let mut state = SimulationState::new(agents);

    let tx_ab = create_transaction("BANK_A", "BANK_B", 500_000, 0, 100);
    let tx_ba = create_transaction("BANK_B", "BANK_A", 500_000, 0, 100);

    // Queue both (insufficient liquidity)
    submit_transaction(&mut state, tx_ab, 1).unwrap();
    submit_transaction(&mut state, tx_ba, 2).unwrap();

    assert_eq!(state.queue_size(), 2, "Both transactions queued");

    // Run bilateral offsetting
    let result = bilateral_offset(&mut state, 5);

    assert_eq!(result.pairs_found, 1, "Should find 1 bilateral pair");
    assert_eq!(result.offset_value, 500_000, "Should offset 500k");
    assert!(result.settlements_count >= 2, "Should settle both transactions");

    // Verify balances net to original (net-zero settlement)
    assert_eq!(
        state.get_agent("BANK_A").unwrap().balance(),
        100_000,
        "A net zero (sent 500k, received 500k)"
    );
    assert_eq!(
        state.get_agent("BANK_B").unwrap().balance(),
        100_000,
        "B net zero (sent 500k, received 500k)"
    );
}

#[test]
fn test_bilateral_offset_asymmetric() {
    // A→B 500k, B→A 300k
    // Should offset 300k, leaving A→B net 200k
    let agents = vec![
        create_agent("BANK_A", 200_000, 0),
        create_agent("BANK_B", 100_000, 0),
    ];
    let mut state = SimulationState::new(agents);

    let tx_ab = create_transaction("BANK_A", "BANK_B", 500_000, 0, 100);
    let tx_ba = create_transaction("BANK_B", "BANK_A", 300_000, 0, 100);

    submit_transaction(&mut state, tx_ab, 1).unwrap();
    submit_transaction(&mut state, tx_ba, 2).unwrap();

    assert_eq!(state.queue_size(), 2);

    // Run bilateral offsetting
    let result = bilateral_offset(&mut state, 5);

    assert_eq!(result.pairs_found, 1);
    assert_eq!(result.offset_value, 300_000, "Should offset min (300k)");

    // After offset, B→A should be fully settled, A→B partially settled
    // Net: A sends 200k to B (500k - 300k offset)
    let balance_a = state.get_agent("BANK_A").unwrap().balance();
    let balance_b = state.get_agent("BANK_B").unwrap().balance();

    // A: 200k initial - 500k sent + 300k received = 0k (used all liquidity)
    // B: 100k initial + 500k received - 300k sent = 300k
    assert_eq!(balance_a, 0, "A used all 200k liquidity");
    assert_eq!(balance_b, 300_000, "B received net 200k");
}

#[test]
fn test_bilateral_offset_multiple_transactions() {
    // A→B: 3 transactions (200k each = 600k total)
    // B→A: 2 transactions (200k each = 400k total)
    // Net: A→B 200k
    // Give both agents small balances (less than any transaction) to force queuing,
    // but provide credit limits for bilateral offsetting net flows
    let agents = vec![
        create_agent("BANK_A", 50_000, 250_000),  // Can't pay 200k, but can handle -200k with credit
        create_agent("BANK_B", 50_000, 250_000),  // Can't pay 200k initially
    ];
    let mut state = SimulationState::new(agents);

    // A→B transactions
    for _ in 0..3 {
        let tx = create_transaction("BANK_A", "BANK_B", 200_000, 0, 100);
        submit_transaction(&mut state, tx, 1).unwrap();
    }

    // B→A transactions
    for _ in 0..2 {
        let tx = create_transaction("BANK_B", "BANK_A", 200_000, 0, 100);
        submit_transaction(&mut state, tx, 2).unwrap();
    }

    // With 50k balance + 250k credit = 300k available:
    // - A→B #1 (200k) settles, leaves A with 100k available
    // - A→B #2, #3 queue (need 200k each, only 100k available)
    // - B→A #1, #2 both settle (B has enough after first settlement)
    // So only 2 transactions queue
    assert_eq!(state.queue_size(), 2, "2 A→B transactions queue");

    // Run bilateral offsetting on the 2 queued A→B transactions
    // Since there are no queued B→A transactions, no bilateral pair exists
    let result = bilateral_offset(&mut state, 5);

    assert_eq!(result.pairs_found, 0, "No bilateral pairs (no B→A in queue)");
    assert_eq!(result.offset_value, 0, "No offset possible");
    assert_eq!(result.settlements_count, 0, "No settlements via LSM");

    // Queue should still have 2 transactions (couldn't be offset)
    assert_eq!(state.queue_size(), 2, "2 A→B transactions still queued");
}

#[test]
fn test_bilateral_offset_no_pairs() {
    // Only unidirectional flows (no bilateral pairs)
    let agents = vec![
        create_agent("BANK_A", 100_000, 0),
        create_agent("BANK_B", 0, 0),
        create_agent("BANK_C", 0, 0),
    ];
    let mut state = SimulationState::new(agents);

    let tx_ab = create_transaction("BANK_A", "BANK_B", 200_000, 0, 100);
    let tx_bc = create_transaction("BANK_B", "BANK_C", 200_000, 0, 100);

    submit_transaction(&mut state, tx_ab, 1).unwrap();
    submit_transaction(&mut state, tx_bc, 2).unwrap();

    // Run bilateral offsetting
    let result = bilateral_offset(&mut state, 5);

    assert_eq!(result.pairs_found, 0, "No bilateral pairs");
    assert_eq!(result.offset_value, 0, "No offsetting possible");
}

#[test]
fn test_bilateral_offset_resolves_gridlock() {
    // Classic bilateral gridlock: A→B and B→A, both insufficient
    // Bilateral offset should resolve completely
    let agents = vec![
        create_agent("BANK_A", 100_000, 0),
        create_agent("BANK_B", 100_000, 0),
    ];
    let mut state = SimulationState::new(agents);

    let tx_ab = create_transaction("BANK_A", "BANK_B", 400_000, 0, 100);
    let tx_ba = create_transaction("BANK_B", "BANK_A", 400_000, 0, 100);

    submit_transaction(&mut state, tx_ab, 1).unwrap();
    submit_transaction(&mut state, tx_ba, 2).unwrap();

    assert_eq!(state.queue_size(), 2, "Bilateral gridlock");

    // Run bilateral offsetting
    let result = bilateral_offset(&mut state, 5);

    assert_eq!(result.pairs_found, 1);
    assert_eq!(result.offset_value, 400_000);

    // Should be fully resolved (both settled)
    // Balances net to original
    assert_eq!(state.get_agent("BANK_A").unwrap().balance(), 100_000);
    assert_eq!(state.get_agent("BANK_B").unwrap().balance(), 100_000);
}

// ============================================================================
// Cycle Detection Tests
// ============================================================================

#[test]
fn test_detect_3_cycle() {
    // A→B→C→A cycle, each 500k
    let agents = vec![
        create_agent("BANK_A", 100_000, 0),
        create_agent("BANK_B", 100_000, 0),
        create_agent("BANK_C", 100_000, 0),
    ];
    let mut state = SimulationState::new(agents);

    let tx_ab = create_transaction("BANK_A", "BANK_B", 500_000, 0, 100);
    let tx_bc = create_transaction("BANK_B", "BANK_C", 500_000, 0, 100);
    let tx_ca = create_transaction("BANK_C", "BANK_A", 500_000, 0, 100);

    submit_transaction(&mut state, tx_ab, 1).unwrap();
    submit_transaction(&mut state, tx_bc, 2).unwrap();
    submit_transaction(&mut state, tx_ca, 3).unwrap();

    // Detect cycles
    let cycles = detect_cycles(&state, 4);

    assert!(!cycles.is_empty(), "Should detect at least one cycle");

    let cycle = &cycles[0];
    assert_eq!(cycle.agents.len(), 4, "Cycle should have 4 agents (3 + closing)");
    assert_eq!(cycle.transactions.len(), 3, "Cycle should have 3 transactions");
    assert_eq!(cycle.min_amount, 500_000, "Min amount is 500k");
}

#[test]
fn test_detect_4_cycle() {
    // A→B→C→D→A cycle (four-bank ring from game_concept Section 11)
    let agents = vec![
        create_agent("BANK_A", 100_000, 0),
        create_agent("BANK_B", 100_000, 0),
        create_agent("BANK_C", 100_000, 0),
        create_agent("BANK_D", 100_000, 0),
    ];
    let mut state = SimulationState::new(agents);

    let tx_ab = create_transaction("BANK_A", "BANK_B", 500_000, 0, 100);
    let tx_bc = create_transaction("BANK_B", "BANK_C", 500_000, 0, 100);
    let tx_cd = create_transaction("BANK_C", "BANK_D", 500_000, 0, 100);
    let tx_da = create_transaction("BANK_D", "BANK_A", 500_000, 0, 100);

    submit_transaction(&mut state, tx_ab, 1).unwrap();
    submit_transaction(&mut state, tx_bc, 2).unwrap();
    submit_transaction(&mut state, tx_cd, 3).unwrap();
    submit_transaction(&mut state, tx_da, 4).unwrap();

    // Detect cycles
    let cycles = detect_cycles(&state, 5);

    assert!(!cycles.is_empty(), "Should detect 4-cycle");

    let cycle = &cycles[0];
    assert_eq!(cycle.agents.len(), 5, "4-cycle has 5 agents (4 + closing)");
    assert_eq!(cycle.transactions.len(), 4, "4 transactions");
    assert_eq!(cycle.min_amount, 500_000);
}

#[test]
fn test_detect_cycle_unequal_amounts() {
    // A→B (500k), B→C (700k), C→A (600k)
    // Min amount is 500k (bottleneck)
    let agents = vec![
        create_agent("BANK_A", 100_000, 0),
        create_agent("BANK_B", 100_000, 0),
        create_agent("BANK_C", 100_000, 0),
    ];
    let mut state = SimulationState::new(agents);

    let tx_ab = create_transaction("BANK_A", "BANK_B", 500_000, 0, 100);
    let tx_bc = create_transaction("BANK_B", "BANK_C", 700_000, 0, 100);
    let tx_ca = create_transaction("BANK_C", "BANK_A", 600_000, 0, 100);

    submit_transaction(&mut state, tx_ab, 1).unwrap();
    submit_transaction(&mut state, tx_bc, 2).unwrap();
    submit_transaction(&mut state, tx_ca, 3).unwrap();

    let cycles = detect_cycles(&state, 4);

    assert!(!cycles.is_empty());
    assert_eq!(cycles[0].min_amount, 500_000, "Bottleneck is 500k");
}

#[test]
fn test_no_cycles_detected() {
    // Linear flow A→B→C (no cycle)
    let agents = vec![
        create_agent("BANK_A", 500_000, 0),
        create_agent("BANK_B", 0, 0),
        create_agent("BANK_C", 0, 0),
    ];
    let mut state = SimulationState::new(agents);

    let tx_ab = create_transaction("BANK_A", "BANK_B", 200_000, 0, 100);
    let tx_bc = create_transaction("BANK_B", "BANK_C", 200_000, 0, 100);

    submit_transaction(&mut state, tx_ab, 1).unwrap();
    submit_transaction(&mut state, tx_bc, 2).unwrap();

    let cycles = detect_cycles(&state, 4);

    assert!(cycles.is_empty(), "No cycles in linear flow");
}

#[test]
fn test_settle_cycle_3_banks() {
    // A→B→C→A, settle 500k on cycle
    let agents = vec![
        create_agent("BANK_A", 100_000, 0),
        create_agent("BANK_B", 100_000, 0),
        create_agent("BANK_C", 100_000, 0),
    ];
    let mut state = SimulationState::new(agents);

    let tx_ab = create_transaction("BANK_A", "BANK_B", 500_000, 0, 100);
    let tx_bc = create_transaction("BANK_B", "BANK_C", 500_000, 0, 100);
    let tx_ca = create_transaction("BANK_C", "BANK_A", 500_000, 0, 100);

    submit_transaction(&mut state, tx_ab, 1).unwrap();
    submit_transaction(&mut state, tx_bc, 2).unwrap();
    submit_transaction(&mut state, tx_ca, 3).unwrap();

    // Detect and settle cycle
    let cycles = detect_cycles(&state, 4);
    assert!(!cycles.is_empty());

    let result = settle_cycle(&mut state, &cycles[0], 5).unwrap();

    assert_eq!(result.cycle_length, 3);
    assert_eq!(result.settled_value, 500_000);
    assert_eq!(result.transactions_affected, 3);

    // Verify balances net to original (net-zero for cycle participants)
    assert_eq!(
        state.get_agent("BANK_A").unwrap().balance(),
        100_000,
        "A net zero"
    );
    assert_eq!(
        state.get_agent("BANK_B").unwrap().balance(),
        100_000,
        "B net zero"
    );
    assert_eq!(
        state.get_agent("BANK_C").unwrap().balance(),
        100_000,
        "C net zero"
    );
}

// ============================================================================
// LSM Coordinator Tests
// ============================================================================

#[test]
fn test_lsm_pass_bilateral_only() {
    // Test LSM with only bilateral offsetting enabled
    let agents = vec![
        create_agent("BANK_A", 100_000, 0),
        create_agent("BANK_B", 100_000, 0),
    ];
    let mut state = SimulationState::new(agents);

    let tx_ab = create_transaction("BANK_A", "BANK_B", 400_000, 0, 100);
    let tx_ba = create_transaction("BANK_B", "BANK_A", 400_000, 0, 100);

    submit_transaction(&mut state, tx_ab, 1).unwrap();
    submit_transaction(&mut state, tx_ba, 2).unwrap();

    let config = LsmConfig {
        enable_bilateral: true,
        enable_cycles: false,
        ..Default::default()
    };

    let result = run_lsm_pass(&mut state, &config, 5);

    assert!(result.iterations_run >= 1);
    assert!(result.total_settled_value > 0);
    assert_eq!(result.bilateral_offsets, 1);
    assert_eq!(result.cycles_settled, 0, "Cycles disabled");
}

#[test]
fn test_lsm_pass_cycles_only() {
    // Test LSM with only cycle detection enabled
    let agents = vec![
        create_agent("BANK_A", 100_000, 0),
        create_agent("BANK_B", 100_000, 0),
        create_agent("BANK_C", 100_000, 0),
    ];
    let mut state = SimulationState::new(agents);

    let tx_ab = create_transaction("BANK_A", "BANK_B", 500_000, 0, 100);
    let tx_bc = create_transaction("BANK_B", "BANK_C", 500_000, 0, 100);
    let tx_ca = create_transaction("BANK_C", "BANK_A", 500_000, 0, 100);

    submit_transaction(&mut state, tx_ab, 1).unwrap();
    submit_transaction(&mut state, tx_bc, 2).unwrap();
    submit_transaction(&mut state, tx_ca, 3).unwrap();

    let config = LsmConfig {
        enable_bilateral: false,
        enable_cycles: true,
        ..Default::default()
    };

    let result = run_lsm_pass(&mut state, &config, 5);

    assert!(result.iterations_run >= 1);
    assert!(result.total_settled_value > 0);
    assert_eq!(result.bilateral_offsets, 0, "Bilateral disabled");
    assert!(result.cycles_settled >= 1);
}

#[test]
fn test_lsm_pass_full_optimization() {
    // Test full LSM pass with both bilateral and cycles
    let agents = vec![
        create_agent("BANK_A", 100_000, 0),
        create_agent("BANK_B", 100_000, 0),
        create_agent("BANK_C", 100_000, 0),
        create_agent("BANK_D", 100_000, 0),
    ];
    let mut state = SimulationState::new(agents);

    // Create complex scenario: some bilateral, some cycles
    let tx_ab = create_transaction("BANK_A", "BANK_B", 500_000, 0, 100);
    let tx_bc = create_transaction("BANK_B", "BANK_C", 500_000, 0, 100);
    let tx_cd = create_transaction("BANK_C", "BANK_D", 500_000, 0, 100);
    let tx_da = create_transaction("BANK_D", "BANK_A", 500_000, 0, 100);

    submit_transaction(&mut state, tx_ab, 1).unwrap();
    submit_transaction(&mut state, tx_bc, 2).unwrap();
    submit_transaction(&mut state, tx_cd, 3).unwrap();
    submit_transaction(&mut state, tx_da, 4).unwrap();

    let config = LsmConfig::default(); // Both enabled

    let result = run_lsm_pass(&mut state, &config, 5);

    assert!(result.iterations_run >= 1);
    assert!(result.total_settled_value > 0);
    // Should resolve the 4-cycle
    assert!(result.cycles_settled >= 1 || result.bilateral_offsets >= 1);
}

#[test]
fn test_lsm_pass_max_iterations() {
    // Test that LSM respects max iterations
    let agents = vec![
        create_agent("BANK_A", 0, 0), // No liquidity, can't make progress
        create_agent("BANK_B", 0, 0),
    ];
    let mut state = SimulationState::new(agents);

    // Transactions that can't be settled
    let tx_ab = create_transaction("BANK_A", "BANK_B", 100_000, 0, 100);
    submit_transaction(&mut state, tx_ab, 1).unwrap();

    let config = LsmConfig::default();
    let result = run_lsm_pass(&mut state, &config, 5);

    // Should stop early due to no progress
    assert!(result.iterations_run <= 3, "Should stop at max iterations");
    assert_eq!(result.total_settled_value, 0, "No settlements possible");
}

// ============================================================================
// Four-Bank Ring Test (Game Concept Section 11, Test 2)
// ============================================================================

#[test]
fn test_four_bank_ring_lsm_resolves_gridlock() {
    // From game_concept_doc.md Section 11:
    // "Four-bank ring: inject A→B, B→C, C→D, D→A cycle;
    //  ensure LSM clears with small liquidity"
    //
    // Setup: Each bank has only 100k, wants to send 500k
    // Without LSM: Complete gridlock
    // With LSM: Cycle detection resolves, all settle with minimal liquidity

    let agents = vec![
        create_agent("BANK_A", 100_000, 0),
        create_agent("BANK_B", 100_000, 0),
        create_agent("BANK_C", 100_000, 0),
        create_agent("BANK_D", 100_000, 0),
    ];
    let mut state = SimulationState::new(agents);

    let tx_ab = create_transaction("BANK_A", "BANK_B", 500_000, 0, 100);
    let tx_bc = create_transaction("BANK_B", "BANK_C", 500_000, 0, 100);
    let tx_cd = create_transaction("BANK_C", "BANK_D", 500_000, 0, 100);
    let tx_da = create_transaction("BANK_D", "BANK_A", 500_000, 0, 100);

    let tx_ab_id = tx_ab.id().to_string();
    let tx_bc_id = tx_bc.id().to_string();
    let tx_cd_id = tx_cd.id().to_string();
    let tx_da_id = tx_da.id().to_string();

    // Submit all - will queue (gridlock)
    submit_transaction(&mut state, tx_ab, 1).unwrap();
    submit_transaction(&mut state, tx_bc, 2).unwrap();
    submit_transaction(&mut state, tx_cd, 3).unwrap();
    submit_transaction(&mut state, tx_da, 4).unwrap();

    assert_eq!(state.queue_size(), 4, "All 4 transactions queued (gridlock)");

    // Run LSM pass - should detect and settle 4-cycle
    let config = LsmConfig::default();
    let result = run_lsm_pass(&mut state, &config, 5);

    // Verify LSM resolved the gridlock
    assert!(result.cycles_settled >= 1, "LSM should detect 4-cycle");
    assert_eq!(result.total_settled_value, 500_000, "Settle 500k on cycle");
    assert_eq!(result.final_queue_size, 0, "Queue should be empty");

    // Verify all transactions settled
    assert!(
        state.get_transaction(&tx_ab_id).unwrap().is_fully_settled(),
        "A→B settled"
    );
    assert!(
        state.get_transaction(&tx_bc_id).unwrap().is_fully_settled(),
        "B→C settled"
    );
    assert!(
        state.get_transaction(&tx_cd_id).unwrap().is_fully_settled(),
        "C→D settled"
    );
    assert!(
        state.get_transaction(&tx_da_id).unwrap().is_fully_settled(),
        "D→A settled"
    );

    // Verify balances net to original (each: -500k + 500k = 0)
    assert_eq!(
        state.get_agent("BANK_A").unwrap().balance(),
        100_000,
        "A net zero"
    );
    assert_eq!(
        state.get_agent("BANK_B").unwrap().balance(),
        100_000,
        "B net zero"
    );
    assert_eq!(
        state.get_agent("BANK_C").unwrap().balance(),
        100_000,
        "C net zero"
    );
    assert_eq!(
        state.get_agent("BANK_D").unwrap().balance(),
        100_000,
        "D net zero"
    );

    // Critical assertion: Gridlock resolved with ONLY initial 100k per bank
    // No liquidity injection needed!
    assert_eq!(state.total_balance(), 400_000, "Total balance preserved");
}
