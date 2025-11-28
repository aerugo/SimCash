//! Tests for PairIndex - Incremental Bilateral Offsetting Index
//!
//! Phase 1 of LSM optimization: Tests for the incremental pair index
//! that eliminates full queue rescans on every bilateral offset pass.
//!
//! These tests follow TDD principles and define the expected behavior
//! before implementation.

use payment_simulator_core_rs::{
    settlement::lsm::pair_index::{PairIndex, ReadyKey},
    Agent, SimulationState, Transaction,
};

// ============================================================================
// Test Helpers
// ============================================================================

fn create_test_state() -> SimulationState {
    let agents = vec![
        Agent::new("BANK_A".to_string(), 1_000_000),
        Agent::new("BANK_B".to_string(), 1_000_000),
        Agent::new("BANK_C".to_string(), 1_000_000),
    ];
    SimulationState::new(agents)
}

fn create_transaction(sender: &str, receiver: &str, amount: i64) -> Transaction {
    Transaction::new(
        sender.to_string(),
        receiver.to_string(),
        amount,
        0,    // arrival_tick
        100,  // deadline_tick
    )
}

// ============================================================================
// ReadyKey Tests - Deterministic Ordering
// ============================================================================

#[test]
fn test_ready_key_ordering_by_priority() {
    // Higher liquidity release (lower neg_priority) should come first
    let key1 = ReadyKey::new(1000, "BANK_A", "BANK_B");  // liquidity_release = 1000
    let key2 = ReadyKey::new(500, "BANK_A", "BANK_C");   // liquidity_release = 500

    // In BTreeSet, smaller values come first
    // We use negative priority, so higher release (1000) has lower neg value
    assert!(key1 < key2, "Higher liquidity release should have higher priority");
}

#[test]
fn test_ready_key_ordering_tie_break_by_agents() {
    // Same liquidity, tie-break by agent IDs lexicographically
    let key1 = ReadyKey::new(1000, "BANK_A", "BANK_B");
    let key2 = ReadyKey::new(1000, "BANK_A", "BANK_C");
    let key3 = ReadyKey::new(1000, "BANK_B", "BANK_C");

    assert!(key1 < key2, "A-B should come before A-C");
    assert!(key2 < key3, "A-C should come before B-C");
}

#[test]
fn test_ready_key_canonicalization() {
    // Keys should be canonicalized: a < b always
    let key1 = ReadyKey::new(1000, "BANK_B", "BANK_A");
    let key2 = ReadyKey::new(1000, "BANK_A", "BANK_B");

    // Both should represent the same pair (A, B) where A < B
    assert_eq!(key1.agent_a(), "BANK_A");
    assert_eq!(key1.agent_b(), "BANK_B");
    assert_eq!(key1, key2, "Different construction order should produce same key");
}

#[test]
fn test_ready_key_deterministic_in_btreeset() {
    // Verify ReadyKey works correctly in BTreeSet (deterministic iteration)
    use std::collections::BTreeSet;

    let mut ready_set = BTreeSet::new();

    // Insert in arbitrary order
    ready_set.insert(ReadyKey::new(500, "BANK_C", "BANK_A"));
    ready_set.insert(ReadyKey::new(1000, "BANK_B", "BANK_A"));
    ready_set.insert(ReadyKey::new(750, "BANK_C", "BANK_B"));

    // Pop should give highest priority first (largest liquidity release)
    let first = ready_set.iter().next().cloned();
    assert!(first.is_some());
    assert_eq!(first.unwrap().liquidity_release(), 1000);
}

// ============================================================================
// PairIndex Basic Operations
// ============================================================================

#[test]
fn test_pair_index_initialization() {
    let index = PairIndex::new();

    assert_eq!(index.ready_count(), 0, "New index should have no ready pairs");
    assert!(!index.has_ready_pairs(), "New index should report no ready pairs");
}

#[test]
fn test_pair_index_add_single_direction() {
    let mut index = PairIndex::new();

    // Add A→B transaction (no reverse yet)
    index.add_transaction("tx1", "BANK_A", "BANK_B", 100_000);

    assert_eq!(index.ready_count(), 0, "Single direction should not create ready pair");
    assert_eq!(index.flow_sum("BANK_A", "BANK_B"), 100_000);
    assert_eq!(index.flow_sum("BANK_B", "BANK_A"), 0);
}

#[test]
fn test_pair_index_add_bilateral_creates_ready() {
    let mut index = PairIndex::new();

    // Add A→B
    index.add_transaction("tx1", "BANK_A", "BANK_B", 100_000);
    assert_eq!(index.ready_count(), 0);

    // Add B→A (creates bilateral pair)
    index.add_transaction("tx2", "BANK_B", "BANK_A", 50_000);

    assert_eq!(index.ready_count(), 1, "Bilateral flow should create ready pair");
    assert!(index.has_ready_pairs());

    // Verify flow sums
    assert_eq!(index.flow_sum("BANK_A", "BANK_B"), 100_000);
    assert_eq!(index.flow_sum("BANK_B", "BANK_A"), 50_000);
}

#[test]
fn test_pair_index_multiple_transactions_same_direction() {
    let mut index = PairIndex::new();

    // Add multiple A→B transactions
    index.add_transaction("tx1", "BANK_A", "BANK_B", 100_000);
    index.add_transaction("tx2", "BANK_A", "BANK_B", 50_000);
    index.add_transaction("tx3", "BANK_A", "BANK_B", 75_000);

    assert_eq!(index.flow_sum("BANK_A", "BANK_B"), 225_000, "Should sum all transactions");
    assert_eq!(index.transaction_count("BANK_A", "BANK_B"), 3);
}

#[test]
fn test_pair_index_pop_ready_deterministic_order() {
    let mut index = PairIndex::new();

    // Create three bilateral pairs with different liquidity releases
    // Pair A-B: 1000 vs 500 → release = 500
    index.add_transaction("tx1", "BANK_A", "BANK_B", 1000);
    index.add_transaction("tx2", "BANK_B", "BANK_A", 500);

    // Pair B-C: 800 vs 800 → release = 800 (highest)
    index.add_transaction("tx3", "BANK_B", "BANK_C", 800);
    index.add_transaction("tx4", "BANK_C", "BANK_B", 800);

    // Pair A-C: 600 vs 600 → release = 600
    index.add_transaction("tx5", "BANK_A", "BANK_C", 600);
    index.add_transaction("tx6", "BANK_C", "BANK_A", 600);

    assert_eq!(index.ready_count(), 3);

    // Pop should give highest liquidity release first (B-C: 800)
    let first = index.pop_ready().expect("Should have ready pair");
    assert_eq!(first.liquidity_release(), 800);
    assert!(
        (first.agent_a() == "BANK_B" && first.agent_b() == "BANK_C") ||
        (first.agent_a() == "BANK_C" && first.agent_b() == "BANK_B")
    );

    // Next should be A-C: 600
    let second = index.pop_ready().expect("Should have second pair");
    assert_eq!(second.liquidity_release(), 600);

    // Last should be A-B: 500
    let third = index.pop_ready().expect("Should have third pair");
    assert_eq!(third.liquidity_release(), 500);

    assert_eq!(index.ready_count(), 0);
    assert!(index.pop_ready().is_none(), "No more ready pairs");
}

#[test]
fn test_pair_index_remove_transactions_updates_flows() {
    let mut index = PairIndex::new();

    // Create bilateral pair
    index.add_transaction("tx1", "BANK_A", "BANK_B", 100_000);
    index.add_transaction("tx2", "BANK_A", "BANK_B", 50_000);
    index.add_transaction("tx3", "BANK_B", "BANK_A", 80_000);

    assert_eq!(index.flow_sum("BANK_A", "BANK_B"), 150_000);
    assert_eq!(index.ready_count(), 1);

    // Remove one A→B transaction
    index.remove_transaction("tx1", "BANK_A", "BANK_B", 100_000);

    assert_eq!(index.flow_sum("BANK_A", "BANK_B"), 50_000);
    // Should still be ready (both directions have flow)
    assert_eq!(index.ready_count(), 1);

    // Remove all transactions in one direction
    index.remove_transaction("tx2", "BANK_A", "BANK_B", 50_000);

    assert_eq!(index.flow_sum("BANK_A", "BANK_B"), 0);
    // No longer ready (only one direction has flow)
    assert_eq!(index.ready_count(), 0);
}

#[test]
fn test_pair_index_settle_pair_removes_all_transactions() {
    let mut index = PairIndex::new();

    // Create bilateral pair with multiple transactions each direction
    index.add_transaction("tx1", "BANK_A", "BANK_B", 100_000);
    index.add_transaction("tx2", "BANK_A", "BANK_B", 50_000);
    index.add_transaction("tx3", "BANK_B", "BANK_A", 80_000);

    assert_eq!(index.ready_count(), 1);

    // Settle the pair (should remove ALL transactions in both directions)
    let key = index.pop_ready().unwrap();
    let (txs_ab, txs_ba) = index.get_transactions(&key);

    assert_eq!(txs_ab.len(), 2, "Should have 2 transactions A→B");
    assert_eq!(txs_ba.len(), 1, "Should have 1 transaction B→A");

    // Verify transaction IDs are returned in order
    assert_eq!(txs_ab[0], "tx1");
    assert_eq!(txs_ab[1], "tx2");
    assert_eq!(txs_ba[0], "tx3");
}

// ============================================================================
// PairIndex Integration Tests
// ============================================================================

#[test]
fn test_pair_index_from_queue_snapshot() {
    let mut state = create_test_state();

    // Add transactions to queue
    let tx1 = create_transaction("BANK_A", "BANK_B", 100_000);
    let tx2 = create_transaction("BANK_B", "BANK_A", 50_000);
    let tx3 = create_transaction("BANK_A", "BANK_C", 75_000);

    let tx1_id = tx1.id().to_string();
    let tx2_id = tx2.id().to_string();
    let tx3_id = tx3.id().to_string();

    state.add_transaction(tx1);
    state.add_transaction(tx2);
    state.add_transaction(tx3);

    state.rtgs_queue_mut().push(tx1_id.clone());
    state.rtgs_queue_mut().push(tx2_id.clone());
    state.rtgs_queue_mut().push(tx3_id.clone());

    // Build PairIndex from queue
    let index = PairIndex::from_queue(&state);

    // Should detect A-B bilateral pair
    assert_eq!(index.ready_count(), 1);
    assert_eq!(index.flow_sum("BANK_A", "BANK_B"), 100_000);
    assert_eq!(index.flow_sum("BANK_B", "BANK_A"), 50_000);

    // A-C is unilateral, not ready
    assert_eq!(index.flow_sum("BANK_A", "BANK_C"), 75_000);
}

#[test]
fn test_pair_index_determinism_multiple_runs() {
    // Run same sequence multiple times, verify identical order
    let mut results = Vec::new();

    for _ in 0..10 {
        let mut index = PairIndex::new();

        // Add transactions in same order
        index.add_transaction("tx1", "BANK_A", "BANK_B", 1000);
        index.add_transaction("tx2", "BANK_B", "BANK_A", 500);
        index.add_transaction("tx3", "BANK_B", "BANK_C", 800);
        index.add_transaction("tx4", "BANK_C", "BANK_B", 800);

        let mut order = Vec::new();
        while let Some(key) = index.pop_ready() {
            order.push((key.agent_a().to_string(), key.agent_b().to_string(), key.liquidity_release()));
        }

        results.push(order);
    }

    // All runs should produce identical order
    for i in 1..results.len() {
        assert_eq!(results[0], results[i], "Run {} differs from run 0", i);
    }
}

// ============================================================================
// Performance Characteristic Tests
// ============================================================================

#[test]
fn test_pair_index_incremental_update_performance() {
    // This is a conceptual test to verify incremental updates work
    // In practice, we'll measure with benchmarks

    let mut index = PairIndex::new();

    // Add many transactions incrementally
    for i in 0..1000 {
        let tx_id = format!("tx_{}", i);
        index.add_transaction(&tx_id, "BANK_A", "BANK_B", 1000);
    }

    // Add reverse direction (creates ready pair)
    index.add_transaction("tx_reverse", "BANK_B", "BANK_A", 500_000);

    // Should efficiently identify ready pair without scanning all 1000 transactions
    assert_eq!(index.ready_count(), 1);
    assert_eq!(index.flow_sum("BANK_A", "BANK_B"), 1_000_000);
}

#[test]
fn test_pair_index_no_memory_leak_on_remove() {
    let mut index = PairIndex::new();

    // Add and remove many times
    for i in 0..100 {
        let tx_id = format!("tx_{}", i);
        index.add_transaction(&tx_id, "BANK_A", "BANK_B", 1000);
    }

    for i in 0..100 {
        let tx_id = format!("tx_{}", i);
        index.remove_transaction(&tx_id, "BANK_A", "BANK_B", 1000);
    }

    // Should be back to empty state
    assert_eq!(index.flow_sum("BANK_A", "BANK_B"), 0);
    assert_eq!(index.transaction_count("BANK_A", "BANK_B"), 0);
}
