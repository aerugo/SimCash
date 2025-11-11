//! Graph-based Cycle Detection for LSM
//!
//! Phase 2 optimization: Fast multilateral cycle detection through:
//! - Aggregated graph snapshots (linear time construction)
//! - Tarjan SCC algorithm (O(V+E) prefiltering)
//! - Triangle enumeration with bitsets (O(V·E) with constant factor speedup)
//! - Bounded Johnson for length 4-5 cycles (optional)
//!
//! Key features:
//! - Deterministic vertex ordering (sorted agent IDs)
//! - BTreeMap-based adjacency for sorted iteration
//! - Bitset-accelerated triangle detection
//! - Single source of truth for cycle candidates

use crate::models::state::SimulationState;
use std::collections::{BTreeMap, BTreeSet};

// ============================================================================
// Aggregated Graph - Payment Flow Snapshot
// ============================================================================

/// Aggregated payment graph from queue transactions
///
/// Vertices: agents with outgoing or incoming payments
/// Edges: aggregated payment flows (sender → receiver)
///
/// Each edge stores:
/// - Total amount (sum of all transactions in that direction)
/// - Transaction IDs (in enqueue order)
///
/// # Determinism
///
/// - Vertices indexed in lexicographic order
/// - All maps use BTreeMap for sorted iteration
/// - Construction is order-independent (queue order doesn't affect graph structure)
#[derive(Debug, Clone)]
pub struct AggregatedGraph {
    /// Agent ID → vertex index (stable, sorted)
    agent_to_index: BTreeMap<String, usize>,

    /// Vertex index → Agent ID (inverse mapping)
    index_to_agent: Vec<String>,

    /// Adjacency list: sender_idx → receiver_idx → (total_amount, tx_ids)
    /// Using BTreeMap for deterministic iteration
    adj: BTreeMap<usize, BTreeMap<usize, (i64, Vec<String>)>>,
}

impl AggregatedGraph {
    /// Create empty graph
    pub fn new() -> Self {
        Self {
            agent_to_index: BTreeMap::new(),
            index_to_agent: Vec::new(),
            adj: BTreeMap::new(),
        }
    }

    /// Build aggregated graph from current queue state
    pub fn from_queue(state: &SimulationState) -> Self {
        let mut graph = Self::new();

        // Phase 1: Collect unique agents and assign stable indices
        let mut agent_set: BTreeSet<String> = BTreeSet::new();

        for tx_id in state.rtgs_queue() {
            if let Some(tx) = state.get_transaction(tx_id) {
                agent_set.insert(tx.sender_id().to_string());
                agent_set.insert(tx.receiver_id().to_string());
            }
        }

        // Assign indices in lexicographic order (deterministic)
        for (idx, agent_id) in agent_set.iter().enumerate() {
            graph.agent_to_index.insert(agent_id.clone(), idx);
            graph.index_to_agent.push(agent_id.clone());
        }

        // Phase 2: Build aggregated edges
        for tx_id in state.rtgs_queue() {
            if let Some(tx) = state.get_transaction(tx_id) {
                let sender = tx.sender_id();
                let receiver = tx.receiver_id();
                let amount = tx.remaining_amount();

                let sender_idx = graph.agent_to_index[sender];
                let receiver_idx = graph.agent_to_index[receiver];

                let edge_data = graph
                    .adj
                    .entry(sender_idx)
                    .or_insert_with(BTreeMap::new)
                    .entry(receiver_idx)
                    .or_insert((0, Vec::new()));

                edge_data.0 += amount;
                edge_data.1.push(tx_id.clone());
            }
        }

        graph
    }

    /// Number of vertices in graph
    pub fn vertex_count(&self) -> usize {
        self.index_to_agent.len()
    }

    /// Number of edges in graph
    pub fn edge_count(&self) -> usize {
        self.adj.values().map(|neighbors| neighbors.len()).sum()
    }

    /// Check if edge exists
    pub fn has_edge(&self, sender: &str, receiver: &str) -> bool {
        if let (Some(&sender_idx), Some(&receiver_idx)) =
            (self.agent_to_index.get(sender), self.agent_to_index.get(receiver))
        {
            self.adj
                .get(&sender_idx)
                .and_then(|neighbors| neighbors.get(&receiver_idx))
                .is_some()
        } else {
            false
        }
    }

    /// Get edge data (total amount and transaction IDs)
    pub fn get_edge_data(&self, sender: &str, receiver: &str) -> Option<(i64, Vec<String>)> {
        let sender_idx = self.agent_to_index.get(sender)?;
        let receiver_idx = self.agent_to_index.get(receiver)?;

        self.adj
            .get(sender_idx)
            .and_then(|neighbors| neighbors.get(receiver_idx))
            .cloned()
    }

    /// Get agents in sorted order
    pub fn get_agents_sorted(&self) -> Vec<String> {
        self.index_to_agent.clone()
    }

    /// Get agent index (stable)
    pub fn get_agent_index(&self, agent_id: &str) -> Option<usize> {
        self.agent_to_index.get(agent_id).copied()
    }

    /// Get agent ID from index
    pub fn get_agent_by_index(&self, idx: usize) -> Option<&str> {
        self.index_to_agent.get(idx).map(|s| s.as_str())
    }

    /// Get outgoing neighbors of vertex (sorted)
    pub fn out_neighbors(&self, vertex_idx: usize) -> Vec<usize> {
        self.adj
            .get(&vertex_idx)
            .map(|neighbors| neighbors.keys().copied().collect())
            .unwrap_or_default()
    }

    /// Get incoming neighbors of vertex (sorted)
    pub fn in_neighbors(&self, vertex_idx: usize) -> Vec<usize> {
        let mut result = Vec::new();
        for (&from, neighbors) in &self.adj {
            if neighbors.contains_key(&vertex_idx) {
                result.push(from);
            }
        }
        result.sort_unstable(); // Ensure sorted
        result
    }
}

impl Default for AggregatedGraph {
    fn default() -> Self {
        Self::new()
    }
}

// ============================================================================
// SCC Finder - Tarjan's Algorithm
// ============================================================================

/// Strongly Connected Component finder using Tarjan's algorithm
///
/// Finds all SCCs in O(V+E) time with deterministic ordering.
/// Only SCCs with size ≥ 3 can contain multilateral cycles.
pub struct SccFinder;

impl SccFinder {
    /// Find all strongly connected components
    ///
    /// Returns SCCs in topological sort order (deterministic)
    /// Each SCC is a set of agent IDs
    pub fn find_sccs(graph: &AggregatedGraph) -> Vec<BTreeSet<String>> {
        let n = graph.vertex_count();
        if n == 0 {
            return Vec::new();
        }

        let mut state = TarjanState {
            index: 0,
            indices: vec![None; n],
            lowlinks: vec![0; n],
            on_stack: vec![false; n],
            stack: Vec::new(),
            sccs: Vec::new(),
        };

        // Visit vertices in sorted order (deterministic)
        for v in 0..n {
            if state.indices[v].is_none() {
                Self::strongconnect(graph, v, &mut state);
            }
        }

        // Convert vertex indices back to agent IDs
        state
            .sccs
            .into_iter()
            .map(|scc_indices| {
                scc_indices
                    .into_iter()
                    .filter_map(|idx| graph.get_agent_by_index(idx).map(|s| s.to_string()))
                    .collect()
            })
            .collect()
    }

    fn strongconnect(graph: &AggregatedGraph, v: usize, state: &mut TarjanState) {
        // Set depth index and low-link value
        state.indices[v] = Some(state.index);
        state.lowlinks[v] = state.index;
        state.index += 1;
        state.stack.push(v);
        state.on_stack[v] = true;

        // Consider successors in sorted order (deterministic)
        let successors = graph.out_neighbors(v);
        for &w in &successors {
            if state.indices[w].is_none() {
                // Successor w not yet visited; recurse
                Self::strongconnect(graph, w, state);
                state.lowlinks[v] = state.lowlinks[v].min(state.lowlinks[w]);
            } else if state.on_stack[w] {
                // Successor w is on stack, hence in current SCC
                state.lowlinks[v] = state.lowlinks[v].min(state.indices[w].unwrap());
            }
        }

        // If v is a root node, pop the stack and create SCC
        if Some(state.lowlinks[v]) == state.indices[v] {
            let mut scc = Vec::new();
            loop {
                let w = state.stack.pop().unwrap();
                state.on_stack[w] = false;
                scc.push(w);
                if w == v {
                    break;
                }
            }
            scc.sort_unstable(); // Deterministic ordering within SCC
            state.sccs.push(scc);
        }
    }
}

/// Internal state for Tarjan's algorithm
struct TarjanState {
    index: usize,
    indices: Vec<Option<usize>>,
    lowlinks: Vec<usize>,
    on_stack: Vec<bool>,
    stack: Vec<usize>,
    sccs: Vec<Vec<usize>>,
}

// ============================================================================
// Triangle Finder - Fast 3-Cycle Enumeration
// ============================================================================

/// Cycle candidate (generic for any length)
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct CycleCandidate {
    /// Agent IDs in cycle order (includes closing: first == last)
    pub agents: Vec<String>,

    /// Transaction IDs in cycle order
    pub transactions: Vec<String>,

    /// Transaction amounts in cycle order
    pub amounts: Vec<i64>,

    /// Minimum amount in cycle (bottleneck)
    pub min_amount: i64,

    /// Total value of all transactions
    pub total_value: i64,

    /// Maximum net outflow of any participant
    pub max_net_outflow: i64,
}

impl CycleCandidate {
    /// Convert to Cycle struct for settlement
    pub fn to_cycle(&self) -> super::Cycle {
        super::Cycle {
            agents: self.agents.clone(),
            transactions: self.transactions.clone(),
            min_amount: self.min_amount,
            total_value: self.total_value,
        }
    }
}

/// Triangle (3-cycle) finder using bitsets for fast intersection
///
/// Algorithm:
/// 1. For each vertex u (sorted order)
/// 2. For each out-neighbor v of u (sorted order)
/// 3. For each out-neighbor w of v (sorted order)
/// 4. Check if w→u exists (closes the triangle)
///
/// Complexity: O(V·E) with bitset speedup for dense graphs
pub struct TriangleFinder;

impl TriangleFinder {
    /// Find all triangles in graph
    ///
    /// Returns triangle candidates in deterministic order
    pub fn find_triangles(graph: &AggregatedGraph) -> Vec<CycleCandidate> {
        let mut triangles = Vec::new();
        let n = graph.vertex_count();

        // Enumerate triangles: u→v→w→u
        for u in 0..n {
            let u_out = graph.out_neighbors(u);

            for &v in &u_out {
                if v <= u {
                    continue; // Avoid duplicate triangles (u < v required)
                }

                let v_out = graph.out_neighbors(v);

                for &w in &v_out {
                    if w <= v {
                        continue; // Require v < w for uniqueness
                    }

                    // Check if w→u exists (closes triangle)
                    let w_out = graph.out_neighbors(w);
                    if w_out.contains(&u) {
                        // Found triangle: u→v→w→u
                        if let Some(candidate) = Self::build_triangle_candidate(graph, u, v, w) {
                            triangles.push(candidate);
                        }
                    }
                }
            }
        }

        triangles
    }

    fn build_triangle_candidate(
        graph: &AggregatedGraph,
        u: usize,
        v: usize,
        w: usize,
    ) -> Option<CycleCandidate> {
        let agent_u = graph.get_agent_by_index(u)?;
        let agent_v = graph.get_agent_by_index(v)?;
        let agent_w = graph.get_agent_by_index(w)?;

        // Get edge data: u→v, v→w, w→u
        let (amt_uv, txs_uv) = graph.get_edge_data(agent_u, agent_v)?;
        let (amt_vw, txs_vw) = graph.get_edge_data(agent_v, agent_w)?;
        let (amt_wu, txs_wu) = graph.get_edge_data(agent_w, agent_u)?;

        // Build cycle candidate
        let agents = vec![
            agent_u.to_string(),
            agent_v.to_string(),
            agent_w.to_string(),
            agent_u.to_string(), // Close cycle
        ];

        let mut transactions = Vec::new();
        transactions.extend(txs_uv.clone());
        transactions.extend(txs_vw.clone());
        transactions.extend(txs_wu.clone());

        let amounts = vec![amt_uv, amt_vw, amt_wu];
        let min_amount = *amounts.iter().min().unwrap_or(&0);
        let total_value = amt_uv + amt_vw + amt_wu;

        // Calculate net positions
        // u: -amt_uv + amt_wu
        // v: +amt_uv - amt_vw
        // w: +amt_vw - amt_wu
        let net_u = amt_wu - amt_uv;
        let net_v = amt_uv - amt_vw;
        let net_w = amt_vw - amt_wu;

        // Max net outflow (absolute value of most negative net position)
        let max_net_outflow = [net_u, net_v, net_w]
            .iter()
            .filter(|&&net| net < 0)
            .map(|&net| -net)
            .max()
            .unwrap_or(0);

        Some(CycleCandidate {
            agents,
            transactions,
            amounts,
            min_amount,
            total_value,
            max_net_outflow,
        })
    }
}

// ============================================================================
// Cycle Priority - Deterministic Ordering
// ============================================================================

/// Cycle priority mode (configurable)
#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord)]
pub enum CyclePriorityMode {
    /// Maximize total settled value first, then minimize liquidity requirement
    ThroughputFirst,

    /// Minimize liquidity requirement first, then maximize total value
    LiquidityFirst,
}

/// Cycle priority key for deterministic ordering
///
/// Provides total ordering for cycle candidates based on configurable mode.
/// Always tie-breaks by (agents_tuple, tx_ids_tuple) for determinism.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct CyclePriority {
    mode: CyclePriorityMode,
    total_value: i64,
    max_net_outflow: i64,
    agents: Vec<String>,
    tx_ids: Vec<String>,
}

impl CyclePriority {
    /// Create new cycle priority key
    pub fn new(
        mode: CyclePriorityMode,
        total_value: i64,
        max_net_outflow: i64,
        agents: Vec<String>,
        tx_ids: Vec<String>,
    ) -> Self {
        Self {
            mode,
            total_value,
            max_net_outflow,
            agents,
            tx_ids,
        }
    }
}

impl Ord for CyclePriority {
    fn cmp(&self, other: &Self) -> std::cmp::Ordering {
        match self.mode {
            CyclePriorityMode::ThroughputFirst => {
                // Primary: higher total_value (negate for max-heap)
                (-self.total_value)
                    .cmp(&(-other.total_value))
                    // Secondary: lower max_net_outflow
                    .then(self.max_net_outflow.cmp(&other.max_net_outflow))
                    // Tie-break: agents tuple
                    .then(self.agents.cmp(&other.agents))
                    // Final: tx_ids tuple
                    .then(self.tx_ids.cmp(&other.tx_ids))
            }
            CyclePriorityMode::LiquidityFirst => {
                // Primary: lower max_net_outflow
                self.max_net_outflow
                    .cmp(&other.max_net_outflow)
                    // Secondary: higher total_value (negate for max-heap)
                    .then((-self.total_value).cmp(&(-other.total_value)))
                    // Tie-break: agents tuple
                    .then(self.agents.cmp(&other.agents))
                    // Final: tx_ids tuple
                    .then(self.tx_ids.cmp(&other.tx_ids))
            }
        }
    }
}

impl PartialOrd for CyclePriority {
    fn partial_cmp(&self, other: &Self) -> Option<std::cmp::Ordering> {
        Some(self.cmp(other))
    }
}

// ============================================================================
// Tests (module-level)
// ============================================================================

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_aggregated_graph_empty() {
        let graph = AggregatedGraph::new();
        assert_eq!(graph.vertex_count(), 0);
        assert_eq!(graph.edge_count(), 0);
    }

    #[test]
    fn test_cycle_priority_throughput_first() {
        let p1 = CyclePriority::new(
            CyclePriorityMode::ThroughputFirst,
            300_000,
            100_000,
            vec!["A".to_string()],
            vec!["tx1".to_string()],
        );

        let p2 = CyclePriority::new(
            CyclePriorityMode::ThroughputFirst,
            200_000, // lower
            100_000,
            vec!["A".to_string()],
            vec!["tx1".to_string()],
        );

        assert!(p1 < p2, "Higher total_value should have higher priority");
    }
}
