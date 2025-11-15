//! Tests for LSM Graph Module - Aggregated Graph, SCC, and Triangle Enumeration
//!
//! Phase 2 of LSM optimization: Tests for fast multilateral cycle detection
//! through SCC prefiltering and triangle enumeration.
//!
//! These tests follow TDD principles and define expected behavior before implementation.

use payment_simulator_core_rs::{
    settlement::lsm::graph::{
        AggregatedGraph, CyclePriority, CyclePriorityMode, SccFinder, TriangleFinder,
    },
    Agent, SimulationState, Transaction,
};
use std::collections::{BTreeMap, BTreeSet};

// ============================================================================
// Test Helpers
// ============================================================================

fn create_test_state() -> SimulationState {
    let agents = vec![
        Agent::new("BANK_A".to_string(), 1_000_000),
        Agent::new("BANK_B".to_string(), 1_000_000),
        Agent::new("BANK_C".to_string(), 1_000_000),
        Agent::new("BANK_D".to_string(), 1_000_000),
    ];
    SimulationState::new(agents)
}

fn create_transaction(sender: &str, receiver: &str, amount: i64) -> Transaction {
    Transaction::new(
        sender.to_string(),
        receiver.to_string(),
        amount,
        0,   // arrival_tick
        100, // deadline_tick
    )
}

// ============================================================================
// AggregatedGraph Tests
// ============================================================================

#[test]
fn test_aggregated_graph_initialization() {
    let state = create_test_state();
    let graph = AggregatedGraph::from_queue(&state);

    assert_eq!(graph.vertex_count(), 0, "Empty queue should produce empty graph");
    assert_eq!(graph.edge_count(), 0, "No edges in empty graph");
}

#[test]
fn test_aggregated_graph_single_edge() {
    let mut state = create_test_state();

    // Add A→B transaction
    let tx = create_transaction("BANK_A", "BANK_B", 100_000);
    let tx_id = tx.id().to_string();
    state.add_transaction(tx);
    state.rtgs_queue_mut().push(tx_id);

    let graph = AggregatedGraph::from_queue(&state);

    assert_eq!(graph.vertex_count(), 2, "Should have 2 vertices (A, B)");
    assert_eq!(graph.edge_count(), 1, "Should have 1 edge (A→B)");
    assert!(graph.has_edge("BANK_A", "BANK_B"));
    assert!(!graph.has_edge("BANK_B", "BANK_A"), "No reverse edge");
}

#[test]
fn test_aggregated_graph_multiple_transactions_same_edge() {
    let mut state = create_test_state();

    // Add multiple A→B transactions
    for i in 0..3 {
        let tx = create_transaction("BANK_A", "BANK_B", 50_000 + i * 10_000);
        let tx_id = tx.id().to_string();
        state.add_transaction(tx);
        state.rtgs_queue_mut().push(tx_id);
    }

    let graph = AggregatedGraph::from_queue(&state);

    assert_eq!(graph.vertex_count(), 2);
    assert_eq!(graph.edge_count(), 1, "Multiple txs aggregate to single edge");

    // Verify aggregated amount
    let (total_amount, tx_ids) = graph.get_edge_data("BANK_A", "BANK_B").unwrap();
    assert_eq!(total_amount, 50_000 + 60_000 + 70_000);
    assert_eq!(tx_ids.len(), 3);
}

#[test]
fn test_aggregated_graph_triangle() {
    let mut state = create_test_state();

    // Create triangle: A→B→C→A
    let tx_ab = create_transaction("BANK_A", "BANK_B", 100_000);
    let tx_bc = create_transaction("BANK_B", "BANK_C", 80_000);
    let tx_ca = create_transaction("BANK_C", "BANK_A", 90_000);

    state.add_transaction(tx_ab.clone());
    state.add_transaction(tx_bc.clone());
    state.add_transaction(tx_ca.clone());

    state.rtgs_queue_mut().push(tx_ab.id().to_string());
    state.rtgs_queue_mut().push(tx_bc.id().to_string());
    state.rtgs_queue_mut().push(tx_ca.id().to_string());

    let graph = AggregatedGraph::from_queue(&state);

    assert_eq!(graph.vertex_count(), 3);
    assert_eq!(graph.edge_count(), 3);
    assert!(graph.has_edge("BANK_A", "BANK_B"));
    assert!(graph.has_edge("BANK_B", "BANK_C"));
    assert!(graph.has_edge("BANK_C", "BANK_A"));
}

#[test]
fn test_aggregated_graph_vertex_index_stable() {
    let mut state = create_test_state();

    // Add transactions in arbitrary order
    let tx1 = create_transaction("BANK_C", "BANK_A", 100_000);
    let tx2 = create_transaction("BANK_A", "BANK_B", 100_000);
    let tx3 = create_transaction("BANK_B", "BANK_C", 100_000);

    state.add_transaction(tx1.clone());
    state.add_transaction(tx2.clone());
    state.add_transaction(tx3.clone());

    state.rtgs_queue_mut().push(tx1.id().to_string());
    state.rtgs_queue_mut().push(tx2.id().to_string());
    state.rtgs_queue_mut().push(tx3.id().to_string());

    let graph = AggregatedGraph::from_queue(&state);

    // Verify lexicographic ordering (A < B < C)
    let agents = graph.get_agents_sorted();
    assert_eq!(agents[0], "BANK_A");
    assert_eq!(agents[1], "BANK_B");
    assert_eq!(agents[2], "BANK_C");

    // Verify indices are stable (sorted)
    let idx_a = graph.get_agent_index("BANK_A").unwrap();
    let idx_b = graph.get_agent_index("BANK_B").unwrap();
    let idx_c = graph.get_agent_index("BANK_C").unwrap();

    assert!(idx_a < idx_b);
    assert!(idx_b < idx_c);
}

// ============================================================================
// SCC Finder Tests (Tarjan Algorithm)
// ============================================================================

#[test]
fn test_scc_single_node() {
    let mut state = create_test_state();

    // Single transaction A→B (no cycle)
    let tx = create_transaction("BANK_A", "BANK_B", 100_000);
    state.add_transaction(tx.clone());
    state.rtgs_queue_mut().push(tx.id().to_string());

    let graph = AggregatedGraph::from_queue(&state);
    let sccs = SccFinder::find_sccs(&graph);

    // Each node is its own SCC
    assert_eq!(sccs.len(), 2, "Two SCCs: [A], [B]");
    assert!(sccs.iter().all(|scc| scc.len() == 1), "Each SCC has size 1");
}

#[test]
fn test_scc_simple_triangle() {
    let mut state = create_test_state();

    // Triangle: A→B→C→A
    let tx_ab = create_transaction("BANK_A", "BANK_B", 100_000);
    let tx_bc = create_transaction("BANK_B", "BANK_C", 100_000);
    let tx_ca = create_transaction("BANK_C", "BANK_A", 100_000);

    state.add_transaction(tx_ab.clone());
    state.add_transaction(tx_bc.clone());
    state.add_transaction(tx_ca.clone());

    state.rtgs_queue_mut().push(tx_ab.id().to_string());
    state.rtgs_queue_mut().push(tx_bc.id().to_string());
    state.rtgs_queue_mut().push(tx_ca.id().to_string());

    let graph = AggregatedGraph::from_queue(&state);
    let sccs = SccFinder::find_sccs(&graph);

    // Should find one SCC containing all 3 nodes
    let large_sccs: Vec<_> = sccs.iter().filter(|scc| scc.len() >= 3).collect();
    assert_eq!(large_sccs.len(), 1, "Should find one SCC of size 3");

    let scc = large_sccs[0];
    assert_eq!(scc.len(), 3);
    assert!(scc.contains(&"BANK_A".to_string()));
    assert!(scc.contains(&"BANK_B".to_string()));
    assert!(scc.contains(&"BANK_C".to_string()));
}

#[test]
fn test_scc_four_agent_ring() {
    let mut state = create_test_state();

    // Ring: A→B→C→D→A
    let tx_ab = create_transaction("BANK_A", "BANK_B", 100_000);
    let tx_bc = create_transaction("BANK_B", "BANK_C", 100_000);
    let tx_cd = create_transaction("BANK_C", "BANK_D", 100_000);
    let tx_da = create_transaction("BANK_D", "BANK_A", 100_000);

    state.add_transaction(tx_ab.clone());
    state.add_transaction(tx_bc.clone());
    state.add_transaction(tx_cd.clone());
    state.add_transaction(tx_da.clone());

    state.rtgs_queue_mut().push(tx_ab.id().to_string());
    state.rtgs_queue_mut().push(tx_bc.id().to_string());
    state.rtgs_queue_mut().push(tx_cd.id().to_string());
    state.rtgs_queue_mut().push(tx_da.id().to_string());

    let graph = AggregatedGraph::from_queue(&state);
    let sccs = SccFinder::find_sccs(&graph);

    let large_sccs: Vec<_> = sccs.iter().filter(|scc| scc.len() >= 4).collect();
    assert_eq!(large_sccs.len(), 1, "Should find one SCC of size 4");

    let scc = large_sccs[0];
    assert_eq!(scc.len(), 4);
}

#[test]
fn test_scc_incomplete_cycle() {
    let mut state = create_test_state();

    // Chain: A→B→C (no back edge)
    let tx_ab = create_transaction("BANK_A", "BANK_B", 100_000);
    let tx_bc = create_transaction("BANK_B", "BANK_C", 100_000);

    state.add_transaction(tx_ab.clone());
    state.add_transaction(tx_bc.clone());

    state.rtgs_queue_mut().push(tx_ab.id().to_string());
    state.rtgs_queue_mut().push(tx_bc.id().to_string());

    let graph = AggregatedGraph::from_queue(&state);
    let sccs = SccFinder::find_sccs(&graph);

    // No SCC should have size >= 3
    assert!(
        sccs.iter().all(|scc| scc.len() < 3),
        "No large SCCs in chain (no cycles)"
    );
}

#[test]
fn test_scc_deterministic_ordering() {
    // Run SCC finder multiple times, verify same order
    let mut results = Vec::new();

    for _ in 0..10 {
        let mut state = create_test_state();

        // Add triangle in same order
        let tx_ab = create_transaction("BANK_A", "BANK_B", 100_000);
        let tx_bc = create_transaction("BANK_B", "BANK_C", 100_000);
        let tx_ca = create_transaction("BANK_C", "BANK_A", 100_000);

        state.add_transaction(tx_ab.clone());
        state.add_transaction(tx_bc.clone());
        state.add_transaction(tx_ca.clone());

        state.rtgs_queue_mut().push(tx_ab.id().to_string());
        state.rtgs_queue_mut().push(tx_bc.id().to_string());
        state.rtgs_queue_mut().push(tx_ca.id().to_string());

        let graph = AggregatedGraph::from_queue(&state);
        let sccs = SccFinder::find_sccs(&graph);

        results.push(sccs);
    }

    // All runs should produce identical results
    for i in 1..results.len() {
        assert_eq!(results[0], results[i], "Run {} differs from run 0", i);
    }
}

// ============================================================================
// Triangle Finder Tests
// ============================================================================

#[test]
fn test_triangle_finder_simple_triangle() {
    let mut state = create_test_state();

    // Triangle: A→B→C→A
    let tx_ab = create_transaction("BANK_A", "BANK_B", 100_000);
    let tx_bc = create_transaction("BANK_B", "BANK_C", 100_000);
    let tx_ca = create_transaction("BANK_C", "BANK_A", 100_000);

    state.add_transaction(tx_ab.clone());
    state.add_transaction(tx_bc.clone());
    state.add_transaction(tx_ca.clone());

    state.rtgs_queue_mut().push(tx_ab.id().to_string());
    state.rtgs_queue_mut().push(tx_bc.id().to_string());
    state.rtgs_queue_mut().push(tx_ca.id().to_string());

    let graph = AggregatedGraph::from_queue(&state);
    let triangles = TriangleFinder::find_triangles(&graph);

    assert_eq!(triangles.len(), 1, "Should find exactly one triangle");

    let triangle = &triangles[0];
    assert_eq!(triangle.agents.len(), 4, "Triangle: [A, B, C, A]");
    assert_eq!(triangle.agents[0], triangle.agents[3], "Cycle closes");
}

#[test]
fn test_triangle_finder_no_triangles() {
    let mut state = create_test_state();

    // Chain: A→B→C (no cycle)
    let tx_ab = create_transaction("BANK_A", "BANK_B", 100_000);
    let tx_bc = create_transaction("BANK_B", "BANK_C", 100_000);

    state.add_transaction(tx_ab.clone());
    state.add_transaction(tx_bc.clone());

    state.rtgs_queue_mut().push(tx_ab.id().to_string());
    state.rtgs_queue_mut().push(tx_bc.id().to_string());

    let graph = AggregatedGraph::from_queue(&state);
    let triangles = TriangleFinder::find_triangles(&graph);

    assert_eq!(triangles.len(), 0, "No triangles in chain");
}

#[test]
fn test_triangle_finder_multiple_triangles() {
    let mut state = create_test_state();

    // Triangle 1: A→B→C→A
    // Triangle 2: A→B→D→A (shares edge A→B)

    let agents = vec![
        Agent::new("BANK_A".to_string(), 1_000_000),
        Agent::new("BANK_B".to_string(), 1_000_000),
        Agent::new("BANK_C".to_string(), 1_000_000),
        Agent::new("BANK_D".to_string(), 1_000_000),
    ];
    let mut state = SimulationState::new(agents);

    let tx_ab = create_transaction("BANK_A", "BANK_B", 100_000);
    let tx_bc = create_transaction("BANK_B", "BANK_C", 100_000);
    let tx_ca = create_transaction("BANK_C", "BANK_A", 100_000);
    let tx_bd = create_transaction("BANK_B", "BANK_D", 100_000);
    let tx_da = create_transaction("BANK_D", "BANK_A", 100_000);

    state.add_transaction(tx_ab.clone());
    state.add_transaction(tx_bc.clone());
    state.add_transaction(tx_ca.clone());
    state.add_transaction(tx_bd.clone());
    state.add_transaction(tx_da.clone());

    state.rtgs_queue_mut().push(tx_ab.id().to_string());
    state.rtgs_queue_mut().push(tx_bc.id().to_string());
    state.rtgs_queue_mut().push(tx_ca.id().to_string());
    state.rtgs_queue_mut().push(tx_bd.id().to_string());
    state.rtgs_queue_mut().push(tx_da.id().to_string());

    let graph = AggregatedGraph::from_queue(&state);
    let triangles = TriangleFinder::find_triangles(&graph);

    assert_eq!(triangles.len(), 2, "Should find two triangles");
}

#[test]
fn test_triangle_finder_deterministic() {
    // Run triangle finder multiple times on SAME state, verify same order
    // Transaction IDs are UUIDs (non-deterministic), but graph structure is deterministic

    let mut state = create_test_state();

    let tx_ab = create_transaction("BANK_A", "BANK_B", 100_000);
    let tx_bc = create_transaction("BANK_B", "BANK_C", 100_000);
    let tx_ca = create_transaction("BANK_C", "BANK_A", 100_000);

    state.add_transaction(tx_ab.clone());
    state.add_transaction(tx_bc.clone());
    state.add_transaction(tx_ca.clone());

    state.rtgs_queue_mut().push(tx_ab.id().to_string());
    state.rtgs_queue_mut().push(tx_bc.id().to_string());
    state.rtgs_queue_mut().push(tx_ca.id().to_string());

    // Build graph once
    let graph = AggregatedGraph::from_queue(&state);

    // Find triangles multiple times - should be identical
    let mut results = Vec::new();
    for _ in 0..10 {
        let triangles = TriangleFinder::find_triangles(&graph);
        results.push(triangles);
    }

    // All runs should produce identical results
    for i in 1..results.len() {
        assert_eq!(results[0], results[i], "Run {} differs from run 0", i);
    }

    // Verify structure is deterministic
    assert_eq!(results[0].len(), 1, "Should find exactly one triangle");
    let triangle = &results[0][0];
    assert_eq!(triangle.agents.len(), 4);
    assert_eq!(triangle.agents[0], "BANK_A");
    assert_eq!(triangle.agents[1], "BANK_B");
    assert_eq!(triangle.agents[2], "BANK_C");
    assert_eq!(triangle.agents[3], "BANK_A");
    assert_eq!(triangle.total_value, 300_000);
    assert_eq!(triangle.max_net_outflow, 0);
}

// ============================================================================
// Cycle Priority Tests
// ============================================================================

#[test]
fn test_cycle_priority_throughput_first() {
    // ThroughputFirst: higher total_value first, then lower max_net_outflow

    let cycle1 = CyclePriority::new(
        CyclePriorityMode::ThroughputFirst,
        300_000,  // total_value
        100_000,  // max_net_outflow
        vec!["BANK_A".to_string(), "BANK_B".to_string(), "BANK_C".to_string()],
        vec!["tx1".to_string(), "tx2".to_string(), "tx3".to_string()],
    );

    let cycle2 = CyclePriority::new(
        CyclePriorityMode::ThroughputFirst,
        200_000,  // lower total_value
        50_000,   // lower max_net_outflow
        vec!["BANK_A".to_string(), "BANK_B".to_string(), "BANK_C".to_string()],
        vec!["tx4".to_string(), "tx5".to_string(), "tx6".to_string()],
    );

    assert!(
        cycle1 < cycle2,
        "Cycle1 (higher total_value) should have higher priority"
    );
}

#[test]
fn test_cycle_priority_liquidity_first() {
    // LiquidityFirst: lower max_net_outflow first, then higher total_value

    let cycle1 = CyclePriority::new(
        CyclePriorityMode::LiquidityFirst,
        300_000,  // total_value
        50_000,   // max_net_outflow (lower)
        vec!["BANK_A".to_string(), "BANK_B".to_string(), "BANK_C".to_string()],
        vec!["tx1".to_string(), "tx2".to_string(), "tx3".to_string()],
    );

    let cycle2 = CyclePriority::new(
        CyclePriorityMode::LiquidityFirst,
        200_000,  // lower total_value
        100_000,  // higher max_net_outflow
        vec!["BANK_A".to_string(), "BANK_B".to_string(), "BANK_C".to_string()],
        vec!["tx4".to_string(), "tx5".to_string(), "tx6".to_string()],
    );

    assert!(
        cycle1 < cycle2,
        "Cycle1 (lower max_net_outflow) should have higher priority"
    );
}

#[test]
fn test_cycle_priority_tie_break_by_agents() {
    // Same metrics, tie-break by agent tuple

    let cycle1 = CyclePriority::new(
        CyclePriorityMode::ThroughputFirst,
        300_000,
        100_000,
        vec!["BANK_A".to_string(), "BANK_B".to_string(), "BANK_C".to_string()],
        vec!["tx1".to_string(), "tx2".to_string(), "tx3".to_string()],
    );

    let cycle2 = CyclePriority::new(
        CyclePriorityMode::ThroughputFirst,
        300_000,  // same
        100_000,  // same
        vec!["BANK_A".to_string(), "BANK_B".to_string(), "BANK_D".to_string()], // D > C
        vec!["tx1".to_string(), "tx2".to_string(), "tx3".to_string()],
    );

    assert!(cycle1 < cycle2, "A-B-C should come before A-B-D lexicographically");
}

#[test]
fn test_cycle_priority_tie_break_by_tx_ids() {
    // Same metrics and agents, tie-break by tx_ids

    let cycle1 = CyclePriority::new(
        CyclePriorityMode::ThroughputFirst,
        300_000,
        100_000,
        vec!["BANK_A".to_string(), "BANK_B".to_string(), "BANK_C".to_string()],
        vec!["tx1".to_string(), "tx2".to_string(), "tx3".to_string()],
    );

    let cycle2 = CyclePriority::new(
        CyclePriorityMode::ThroughputFirst,
        300_000,
        100_000,
        vec!["BANK_A".to_string(), "BANK_B".to_string(), "BANK_C".to_string()],
        vec!["tx1".to_string(), "tx2".to_string(), "tx4".to_string()], // tx4 > tx3
    );

    assert!(cycle1 < cycle2, "tx3 should come before tx4 lexicographically");
}
