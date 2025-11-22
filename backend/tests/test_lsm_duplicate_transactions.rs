//! Test for LSM duplicate transaction bug
//!
//! Reproduces the issue where the same transaction appears in multiple LSM cycles.

use payment_simulator_core_rs::models::agent::Agent;
use payment_simulator_core_rs::models::state::SimulationState;
use payment_simulator_core_rs::models::transaction::{Transaction, TransactionStatus};
use payment_simulator_core_rs::settlement::lsm::{run_lsm_pass, LsmConfig};
use std::collections::HashSet;

/// Test that bilateral offsetting doesn't create duplicate transaction references
///
/// This test reproduces the bug where transaction c6979dfa appeared in two different cycles:
/// - Cycle 1: CORRESPONDENT_HUB ⇄ REGIONAL_TRUST (TX c6979dfa + TX 4b6bb32c)
/// - Cycle 2: REGIONAL_TRUST ⇄ CORRESPONDENT_HUB (TX d073dd61 + TX c6979dfa)
#[test]
fn test_bilateral_offset_no_duplicate_transactions() {
    // Setup: Create 2 agents
    let agent_a = Agent::new("AGENT_A".to_string(), 1_000_000);
    let agent_b = Agent::new("AGENT_B".to_string(), 1_000_000);

    let mut state = SimulationState::new(vec![agent_a, agent_b]);

    // Create multiple transactions in both directions to simulate real scenario
    // A→B: 2 transactions
    let tx1 = Transaction::new(
        "AGENT_A".to_string(),
        "AGENT_B".to_string(),
        420_300, // $4,203.00
        1,       // arrival tick
        100,     // deadline
    );

    let tx2 = Transaction::new(
        "AGENT_A".to_string(),
        "AGENT_B".to_string(),
        433_387, // $4,333.87
        1,
        100,
    );

    // B→A: 2 transactions
    let tx3 = Transaction::new(
        "AGENT_B".to_string(),
        "AGENT_A".to_string(),
        531_763, // $5,317.63
        1,
        100,
    );

    let tx4 = Transaction::new(
        "AGENT_B".to_string(),
        "AGENT_A".to_string(),
        200_000, // $2,000.00
        1,
        100,
    );

    // Get transaction IDs before adding to state
    let tx1_id = tx1.id().to_string();
    let tx2_id = tx2.id().to_string();
    let tx3_id = tx3.id().to_string();
    let tx4_id = tx4.id().to_string();

    // Add transactions to state
    state.add_transaction(tx1);
    state.add_transaction(tx2);
    state.add_transaction(tx3);
    state.add_transaction(tx4);

    // Queue all transactions to RTGS queue (Queue 2)
    state.rtgs_queue_mut().push(tx1_id.clone());
    state.rtgs_queue_mut().push(tx2_id.clone());
    state.rtgs_queue_mut().push(tx3_id.clone());
    state.rtgs_queue_mut().push(tx4_id.clone());

    // Run LSM pass
    let config = LsmConfig {
        enable_bilateral: true,
        enable_cycles: false, // Only test bilateral for now
        max_cycle_length: 4,
        max_cycles_per_tick: 10,
    };

    let result = run_lsm_pass(&mut state, &config, 5, 100, false);

    // ASSERTION 1: Only ONE bilateral pair should be created for AGENT_A ⇄ AGENT_B
    assert_eq!(
        result.bilateral_offsets, 1,
        "Expected exactly 1 bilateral offset pair, got {}",
        result.bilateral_offsets
    );

    // ASSERTION 2: Only ONE cycle event should be created
    assert_eq!(
        result.cycle_events.len(),
        1,
        "Expected exactly 1 cycle event, got {}",
        result.cycle_events.len()
    );

    // ASSERTION 3: No transaction should appear in multiple cycle events
    let cycle_event = &result.cycle_events[0];
    let transaction_set: HashSet<&String> = cycle_event.transactions.iter().collect();

    assert_eq!(
        transaction_set.len(),
        cycle_event.transactions.len(),
        "Duplicate transactions found in cycle event! Transactions: {:?}",
        cycle_event.transactions
    );

    // ASSERTION 4: All 4 transactions should be in the single bilateral event
    assert_eq!(
        cycle_event.transactions.len(),
        4,
        "Expected 4 transactions in bilateral event, got {}",
        cycle_event.transactions.len()
    );

    // ASSERTION 5: tx_amounts should have same length as transactions
    assert_eq!(
        cycle_event.tx_amounts.len(),
        cycle_event.transactions.len(),
        "tx_amounts length ({}) doesn't match transactions length ({})",
        cycle_event.tx_amounts.len(),
        cycle_event.transactions.len()
    );

    // ASSERTION 6: All transactions should be settled (removed from queue)
    assert_eq!(
        state.rtgs_queue().len(),
        0,
        "RTGS queue should be empty after LSM, but has {} transactions",
        state.rtgs_queue().len()
    );

    // ASSERTION 7: All transactions should be marked as settled
    for tx_id in &[&tx1_id, &tx2_id, &tx3_id, &tx4_id] {
        let tx = state.get_transaction(tx_id).unwrap();
        assert!(
            tx.is_fully_settled(),
            "Transaction {} should be fully settled",
            tx_id
        );
    }

    println!("✓ Test passed: No duplicate transactions in LSM cycles");
}

/// Test that if LSM runs multiple iterations, transactions aren't reprocessed
#[test]
fn test_lsm_multiple_iterations_no_duplicate_processing() {
    // Similar setup but designed to trigger multiple LSM iterations
    let agent_a = Agent::new("AGENT_A".to_string(), 100_000);
    let agent_b = Agent::new("AGENT_B".to_string(), 100_000);

    let mut state = SimulationState::new(vec![agent_a, agent_b]);

    // Create transactions
    let tx1 = Transaction::new(
        "AGENT_A".to_string(),
        "AGENT_B".to_string(),
        50_000,
        1,
        100,
    );

    let tx2 = Transaction::new(
        "AGENT_B".to_string(),
        "AGENT_A".to_string(),
        30_000,
        1,
        100,
    );

    let tx1_id = tx1.id().to_string();
    let tx2_id = tx2.id().to_string();

    state.add_transaction(tx1);
    state.add_transaction(tx2);
    state.rtgs_queue_mut().push(tx1_id);
    state.rtgs_queue_mut().push(tx2_id);

    let config = LsmConfig::default();
    let result = run_lsm_pass(&mut state, &config, 5, 100, false);

    // Track all transactions across all cycle events
    let mut all_transactions = Vec::new();
    for event in &result.cycle_events {
        all_transactions.extend(event.transactions.iter().cloned());
    }

    // Check for duplicates
    let unique_transactions: HashSet<String> = all_transactions.iter().cloned().collect();

    assert_eq!(
        unique_transactions.len(),
        all_transactions.len(),
        "Found duplicate transactions across cycle events! All: {:?}, Unique: {:?}",
        all_transactions,
        unique_transactions
    );

    println!("✓ Test passed: No transaction reprocessing across iterations");
}

/// Test that LSM iterations don't create duplicate cycle events
///
/// This reproduces the bug where the same bilateral pair creates multiple cycle events
/// across different LSM iterations within the same tick.
#[test]
fn test_lsm_no_duplicate_cycle_events_across_iterations() {
    // Setup: Create scenario that triggers multiple LSM iterations
    // Use agents with limited liquidity to prevent immediate settlement
    let agent_a = Agent::new("AGENT_A".to_string(), 50_000);
    let agent_b = Agent::new("AGENT_B".to_string(), 50_000);
    let agent_c = Agent::new("AGENT_C".to_string(), 50_000);

    let mut state = SimulationState::new(vec![agent_a, agent_b, agent_c]);

    // Create bilateral transactions A↔B that will settle via LSM
    let tx_ab = Transaction::new(
        "AGENT_A".to_string(),
        "AGENT_B".to_string(),
        40_000,
        1,
        100,
    );

    let tx_ba = Transaction::new(
        "AGENT_B".to_string(),
        "AGENT_A".to_string(),
        35_000,
        1,
        100,
    );

    // Create additional transactions to force multiple iterations
    let tx_bc = Transaction::new(
        "AGENT_B".to_string(),
        "AGENT_C".to_string(),
        20_000,
        1,
        100,
    );

    let tx_ab_id = tx_ab.id().to_string();
    let tx_ba_id = tx_ba.id().to_string();
    let tx_bc_id = tx_bc.id().to_string();

    state.add_transaction(tx_ab);
    state.add_transaction(tx_ba);
    state.add_transaction(tx_bc);
    state.rtgs_queue_mut().push(tx_ab_id.clone());
    state.rtgs_queue_mut().push(tx_ba_id.clone());
    state.rtgs_queue_mut().push(tx_bc_id.clone());

    // Run LSM with default config (allows multiple iterations)
    let config = LsmConfig::default();
    let result = run_lsm_pass(&mut state, &config, 5, 100, false);

    println!("DEBUG: LSM ran {} iterations", result.iterations_run);
    println!("DEBUG: Found {} bilateral offsets", result.bilateral_offsets);
    println!("DEBUG: Created {} cycle events", result.cycle_events.len());
    for (i, event) in result.cycle_events.iter().enumerate() {
        println!("DEBUG: Event {}: {} transactions, type: {}",
            i, event.transactions.len(), event.cycle_type);
    }

    // ASSERTION 1: Should have found at least 1 bilateral offset
    assert!(
        result.bilateral_offsets >= 1,
        "Expected at least 1 bilateral offset, got {}",
        result.bilateral_offsets
    );

    // ASSERTION 2: Number of cycle events should equal number of bilateral offsets
    // (Each bilateral offset should create exactly 1 cycle event, no duplicates)
    assert_eq!(
        result.cycle_events.len(),
        result.bilateral_offsets,
        "Expected {} cycle events (one per bilateral offset), but got {} (duplicate events created!)",
        result.bilateral_offsets,
        result.cycle_events.len()
    );

    // ASSERTION 3: Check for duplicate events by comparing transaction sets
    let mut seen_tx_sets: Vec<HashSet<String>> = Vec::new();
    for event in &result.cycle_events {
        if event.cycle_type == "bilateral" {
            let tx_set: HashSet<String> = event.transactions.iter().cloned().collect();

            // Check if we've seen this exact set of transactions before
            for (i, existing_set) in seen_tx_sets.iter().enumerate() {
                if &tx_set == existing_set {
                    panic!(
                        "Duplicate bilateral cycle event detected! Event with transactions {:?} \
                         appears multiple times (first at index {}, duplicate found)",
                        tx_set, i
                    );
                }
            }

            seen_tx_sets.push(tx_set);
        }
    }

    // ASSERTION 4: All bilateral transactions should be settled
    assert!(
        state.get_transaction(&tx_ab_id).unwrap().is_fully_settled(),
        "tx_ab should be fully settled"
    );
    assert!(
        state.get_transaction(&tx_ba_id).unwrap().is_fully_settled(),
        "tx_ba should be fully settled"
    );

    println!("✓ Test passed: No duplicate cycle events across {} iterations", result.iterations_run);
}

/// Test that bilateral offset and multilateral cycle detection don't create duplicate events
///
/// This reproduces the bug where:
/// 1. Bilateral offset settles A↔B pair
/// 2. Multilateral cycle detection finds the same pair as a "2-agent cycle"
/// 3. Both create events for the same transactions
#[test]
fn test_no_duplicate_between_bilateral_and_multilateral() {
    // Setup: 2 agents with bilateral transactions
    let agent_a = Agent::new("AGENT_A".to_string(), 100_000);
    let agent_b = Agent::new("AGENT_B".to_string(), 100_000);

    let mut state = SimulationState::new(vec![agent_a, agent_b]);

    // Create bilateral pair A↔B
    let tx_ab = Transaction::new(
        "AGENT_A".to_string(),
        "AGENT_B".to_string(),
        40_000,
        1,
        100,
    );

    let tx_ba = Transaction::new(
        "AGENT_B".to_string(),
        "AGENT_A".to_string(),
        35_000,
        1,
        100,
    );

    let tx_ab_id = tx_ab.id().to_string();
    let tx_ba_id = tx_ba.id().to_string();

    state.add_transaction(tx_ab);
    state.add_transaction(tx_ba);
    state.rtgs_queue_mut().push(tx_ab_id.clone());
    state.rtgs_queue_mut().push(tx_ba_id.clone());

    // Run LSM with BOTH bilateral AND cycles enabled
    let config = LsmConfig {
        enable_bilateral: true,
        enable_cycles: true,  // This is the key - both are enabled
        max_cycle_length: 5,
        max_cycles_per_tick: 10,
    };
    let result = run_lsm_pass(&mut state, &config, 5, 100, false);

    println!("DEBUG: bilateral_offsets={}, cycles_settled={}",
        result.bilateral_offsets, result.cycles_settled);
    println!("DEBUG: Created {} cycle events total", result.cycle_events.len());
    for (i, event) in result.cycle_events.iter().enumerate() {
        println!("DEBUG: Event {}: type={}, agents={}, txs={:?}",
            i, event.cycle_type, event.cycle_length, event.transactions);
    }

    // ASSERTION 1: Should have found exactly 1 bilateral offset
    assert_eq!(
        result.bilateral_offsets, 1,
        "Expected 1 bilateral offset"
    );

    // ASSERTION 2: Multilateral cycle detection should NOT have found the same pair
    // (2-agent cycles should be handled by bilateral offset, not multilateral detection)
    assert_eq!(
        result.cycles_settled, 0,
        "Expected 0 multilateral cycles (2-agent bilateral pairs should be handled by bilateral offset, not cycle detection)"
    );

    // ASSERTION 3: Should have created exactly 1 cycle event (from bilateral offset only)
    assert_eq!(
        result.cycle_events.len(), 1,
        "Expected exactly 1 cycle event (from bilateral offset), got {} (bilateral + multilateral both detected same pair!)",
        result.cycle_events.len()
    );

    // ASSERTION 4: The single event should be of type "bilateral"
    assert_eq!(
        result.cycle_events[0].cycle_type, "bilateral",
        "Expected bilateral event type"
    );

    // ASSERTION 5: Verify no duplicate transactions across events
    let mut all_tx_ids = Vec::new();
    for event in &result.cycle_events {
        all_tx_ids.extend(event.transactions.iter().cloned());
    }
    let unique_tx_ids: HashSet<String> = all_tx_ids.iter().cloned().collect();

    assert_eq!(
        all_tx_ids.len(), unique_tx_ids.len(),
        "Found duplicate transactions across cycle events!"
    );

    // ASSERTION 6: Both transactions should be settled
    assert!(state.get_transaction(&tx_ab_id).unwrap().is_fully_settled());
    assert!(state.get_transaction(&tx_ba_id).unwrap().is_fully_settled());

    println!("✓ Test passed: No duplicate between bilateral and multilateral detection");
}

/// Test complex scenario with insufficient liquidity that might trigger both bilateral and cycle detection
#[test]
fn test_complex_scenario_no_duplicates() {
    // Setup: 3 agents with limited liquidity
    let agent_a = Agent::new("AGENT_A".to_string(), 10_000);
    let agent_b = Agent::new("AGENT_B".to_string(), 10_000);
    let agent_c = Agent::new("AGENT_C".to_string(), 10_000);

    let mut state = SimulationState::new(vec![agent_a, agent_b, agent_c]);

    // Create multiple bilateral pairs and a potential 3-way cycle
    let tx1_ab = Transaction::new("AGENT_A".to_string(), "AGENT_B".to_string(), 8_000, 1, 100);
    let tx2_ab = Transaction::new("AGENT_A".to_string(), "AGENT_B".to_string(), 7_000, 1, 100);
    let tx1_ba = Transaction::new("AGENT_B".to_string(), "AGENT_A".to_string(), 9_000, 1, 100);
    let tx_bc = Transaction::new("AGENT_B".to_string(), "AGENT_C".to_string(), 6_000, 1, 100);
    let tx_ca = Transaction::new("AGENT_C".to_string(), "AGENT_A".to_string(), 5_000, 1, 100);

    state.add_transaction(tx1_ab);
    state.add_transaction(tx2_ab);
    state.add_transaction(tx1_ba);
    state.add_transaction(tx_bc);
    state.add_transaction(tx_ca);

    // Queue all - note we don't have IDs saved, they'll all just be in queue
    let all_tx_ids: Vec<String> = state.transactions().keys().cloned().collect();
    for tx_id in &all_tx_ids {
        state.rtgs_queue_mut().push(tx_id.clone());
    }

    println!("DEBUG: Starting with {} transactions in queue", state.rtgs_queue().len());

    // Run LSM with both bilateral and cycles enabled
    let config = LsmConfig {
        enable_bilateral: true,
        enable_cycles: true,
        max_cycle_length: 5,
        max_cycles_per_tick: 10,
    };
    let result = run_lsm_pass(&mut state, &config, 5, 100, false);

    println!("DEBUG: bilateral_offsets={}, cycles_settled={}",
        result.bilateral_offsets, result.cycles_settled);
    println!("DEBUG: Created {} cycle events total", result.cycle_events.len());
    for (i, event) in result.cycle_events.iter().enumerate() {
        println!("DEBUG: Event {}: type={}, length={}, txs={:?}",
            i, event.cycle_type, event.cycle_length, event.transactions);
    }

    // ASSERTION: Check for duplicate transactions across all events
    let mut all_tx_ids_in_events = Vec::new();
    for event in &result.cycle_events {
        all_tx_ids_in_events.extend(event.transactions.iter().cloned());
    }
    let unique_tx_ids: HashSet<String> = all_tx_ids_in_events.iter().cloned().collect();

    assert_eq!(
        all_tx_ids_in_events.len(), unique_tx_ids.len(),
        "Found {} duplicate transactions across cycle events! Total TXs in events: {}, Unique: {}",
        all_tx_ids_in_events.len() - unique_tx_ids.len(),
        all_tx_ids_in_events.len(),
        unique_tx_ids.len()
    );

    println!("✓ Test passed: No duplicate transactions in complex scenario");
}
