use std::collections::BTreeMap;
/// Test LSM cycle detection with perfect 3-agent ring
///
/// This test creates the simplest possible scenario for cycle detection:
/// - 3 agents (A, B, C) in a perfect ring: A→B→C→A
/// - Equal transaction amounts ($1000 each)
/// - All transactions in Queue 2 simultaneously
/// - No bilateral pairs (pure unidirectional ring)
///
/// Expected: detect_cycles() finds one 3-agent cycle

use payment_simulator_core_rs::{
    settlement::{
        lsm::{detect_cycles, settle_cycle},
        submit_transaction,
    },
    Agent, SimulationState, Transaction,
};

fn create_agent(id: &str, balance: i64, unsecured_cap: i64) -> Agent {
    let mut agent = Agent::new(id.to_string(), balance);
    agent.set_unsecured_cap(unsecured_cap);
    agent
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

#[test]
fn test_detect_simple_3_agent_cycle() {
    // Setup: 3 agents with INSUFFICIENT balance to force queueing
    let agents = vec![
        create_agent("BANK_A", 10_000, 0), // $100 balance, no credit
        create_agent("BANK_B", 10_000, 0),
        create_agent("BANK_C", 10_000, 0),
    ];
    let mut state = SimulationState::new(agents);

    // Create perfect ring: A→B, B→C, C→A (all $1000, exceeds $100 balance)
    let tx_ab = create_transaction("BANK_A", "BANK_B", 100_000, 0, 10);
    let tx_bc = create_transaction("BANK_B", "BANK_C", 100_000, 0, 10);
    let tx_ca = create_transaction("BANK_C", "BANK_A", 100_000, 0, 10);

    // Capture IDs before submitting
    let tx_ab_id = tx_ab.id().to_string();
    let tx_bc_id = tx_bc.id().to_string();
    let tx_ca_id = tx_ca.id().to_string();

    // Submit transactions to Queue 2 (RTGS)
    submit_transaction(&mut state, tx_ab, 0).unwrap();
    submit_transaction(&mut state, tx_bc, 0).unwrap();
    submit_transaction(&mut state, tx_ca, 0).unwrap();

    // Verify all 3 transactions are in Queue 2
    assert_eq!(state.queue_size(), 3);

    // Run cycle detection
    let cycles = detect_cycles(&state, 4); // max_cycle_length = 4

    // EXPECTED: Find exactly 1 cycle with 3 agents
    assert!(!cycles.is_empty(), "Expected to find at least one cycle");

    let cycle = &cycles[0];
    assert_eq!(cycle.agents.len(), 4, "Cycle should have 4 entries (3 unique + closing)");

    // Verify cycle closes back to start node
    assert_eq!(cycle.agents[0], cycle.agents[3], "Cycle should close (first == last)");

    // Verify all 3 banks are in the cycle (any order)
    let agents_set: std::collections::HashSet<_> = cycle.agents[0..3].iter().collect();
    assert_eq!(agents_set.len(), 3, "Should have 3 unique agents");
    assert!(agents_set.contains(&"BANK_A".to_string()), "Should include BANK_A");
    assert!(agents_set.contains(&"BANK_B".to_string()), "Should include BANK_B");
    assert!(agents_set.contains(&"BANK_C".to_string()), "Should include BANK_C");

    assert_eq!(cycle.transactions.len(), 3);
    assert_eq!(cycle.min_amount, 100_000); // All equal, so min = $1000

    // Settle the cycle (with batch removal pattern)
    let mut to_remove = BTreeMap::new();
    let result = settle_cycle(&mut state, cycle, 0, &mut to_remove).expect("Cycle settlement failed");

    assert_eq!(result.cycle_length, 3);
    assert_eq!(
        result.settled_value, 300_000,
        "T2-compliant: settle total value (100k + 100k + 100k = 300k)"
    );
    assert_eq!(result.transactions_affected, 3);

    // Perform batch removal from queue
    state.rtgs_queue_mut().retain(|id| !to_remove.contains_key(id));

    // Verify Queue 2 is empty (all removed)
    assert_eq!(state.queue_size(), 0);

    // Verify all transactions are fully settled
    assert!(state.get_transaction(&tx_ab_id).unwrap().is_fully_settled());
    assert!(state.get_transaction(&tx_bc_id).unwrap().is_fully_settled());
    assert!(state.get_transaction(&tx_ca_id).unwrap().is_fully_settled());

    // Verify net-zero balance changes (cycle property)
    // Each agent sent $1000 and received $1000, so net = 0
    // We started with $100, should still be $100
    assert_eq!(state.get_agent("BANK_A").unwrap().balance(), 10_000);
    assert_eq!(state.get_agent("BANK_B").unwrap().balance(), 10_000);
    assert_eq!(state.get_agent("BANK_C").unwrap().balance(), 10_000);
}

#[test]
fn test_detect_cycle_with_unequal_amounts() {
    // Setup with insufficient balances to force queueing
    let agents = vec![
        create_agent("BANK_A", 10_000, 0),  // $100, but needs to send $500
        create_agent("BANK_B", 10_000, 0),
        create_agent("BANK_C", 10_000, 0),
    ];
    let mut state = SimulationState::new(agents);

    // Create ring with unequal amounts: A→B($500), B→C($300), C→A($400)
    // Min = $300, so cycle settles $300
    let tx_ab = create_transaction("BANK_A", "BANK_B", 50_000, 0, 10);
    let tx_bc = create_transaction("BANK_B", "BANK_C", 30_000, 0, 10);
    let tx_ca = create_transaction("BANK_C", "BANK_A", 40_000, 0, 10);

    let tx_ab_id = tx_ab.id().to_string();
    let tx_bc_id = tx_bc.id().to_string();
    let tx_ca_id = tx_ca.id().to_string();

    submit_transaction(&mut state, tx_ab, 0).unwrap();
    submit_transaction(&mut state, tx_bc, 0).unwrap();
    submit_transaction(&mut state, tx_ca, 0).unwrap();

    // Run cycle detection
    let cycles = detect_cycles(&state, 4);

    assert!(!cycles.is_empty(), "Expected to find cycle");

    let cycle = &cycles[0];
    assert_eq!(cycle.min_amount, 30_000); // Min of 50k, 30k, 40k = 30k

    // Settle cycle (with batch removal pattern)
    let mut to_remove = BTreeMap::new();
    let result = settle_cycle(&mut state, cycle, 0, &mut to_remove).expect("Cycle settlement failed");

    assert_eq!(
        result.settled_value, 120_000,
        "T2-compliant: settle total value (50k + 30k + 40k = 120k)"
    );
    assert_eq!(result.transactions_affected, 3);

    // Perform batch removal from queue
    state.rtgs_queue_mut().retain(|id| !to_remove.contains_key(id));

    // T2-compliant behavior: ALL transactions settle at FULL value
    // Net positions: A: -10k, B: +20k, C: -10k
    // Each agent has 10k, which covers their net position
    // Therefore ALL transactions settle fully
    assert_eq!(
        state.get_transaction(&tx_ab_id).unwrap().remaining_amount(), 0,
        "A→B should be fully settled"
    );
    assert_eq!(
        state.get_transaction(&tx_bc_id).unwrap().remaining_amount(), 0,
        "B→C should be fully settled"
    );
    assert_eq!(
        state.get_transaction(&tx_ca_id).unwrap().remaining_amount(), 0,
        "C→A should be fully settled"
    );

    // Verify final balances match net positions:
    // A: 10k - 10k net = 0
    // B: 10k + 20k net = 30k
    // C: 10k - 10k net = 0
    assert_eq!(state.get_agent("BANK_A").unwrap().balance(), 0);
    assert_eq!(state.get_agent("BANK_B").unwrap().balance(), 30_000);
    assert_eq!(state.get_agent("BANK_C").unwrap().balance(), 0);
}

#[test]
fn test_no_cycle_detection_with_incomplete_ring() {
    // Negative test: A→B, B→C exist, but C→A is missing
    // Should NOT detect a cycle

    let agents = vec![
        create_agent("BANK_A", 1_000_000, 0),
        create_agent("BANK_B", 1_000_000, 0),
        create_agent("BANK_C", 1_000_000, 0),
    ];
    let mut state = SimulationState::new(agents);

    let tx_ab = create_transaction("BANK_A", "BANK_B", 100_000, 0, 10);
    let tx_bc = create_transaction("BANK_B", "BANK_C", 100_000, 0, 10);
    // Missing: C→A

    submit_transaction(&mut state, tx_ab, 0).unwrap();
    submit_transaction(&mut state, tx_bc, 0).unwrap();

    let cycles = detect_cycles(&state, 4);

    assert!(cycles.is_empty(), "Should not find cycle with incomplete ring");
}
