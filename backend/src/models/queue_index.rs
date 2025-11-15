//! Agent Queue Index - Performance Optimization
//!
//! Provides O(1) lookup of Queue 2 (RTGS) transactions by agent ID.
//!
//! # Problem
//!
//! Without an index, finding all Queue 2 transactions for a specific agent
//! requires scanning the entire queue: O(Queue2_Size).
//!
//! When this happens N times per tick (once per agent for cost calculations,
//! once per Queue 1 transaction for policy evaluation), we get O(N × M) complexity.
//!
//! # Solution
//!
//! Maintain a `HashMap<AgentID, Vec<TxID>>` that maps each agent to their
//! Queue 2 transactions. Rebuild once per tick after queue modifications.
//!
//! Rebuild cost: O(Queue2_Size) - single scan
//! Lookup cost: O(1) - hash table lookup
//!
//! Net win: O(Queue2_Size) instead of O(N × Queue2_Size)
//!
//! # Usage
//!
//! ```rust
//! use payment_simulator_core_rs::models::queue_index::AgentQueueIndex;
//! use payment_simulator_core_rs::SimulationState;
//!
//! let state = SimulationState::new(vec![/* agents */]);
//! let mut index = AgentQueueIndex::new();
//!
//! // Rebuild after queue modifications
//! index.rebuild(state.rtgs_queue(), state.transactions());
//!
//! // Fast O(1) lookup
//! let agent_txs = index.get_agent_transactions("BANK_A");
//! ```

use std::collections::HashMap;

/// Cached metrics for an agent's Queue 2 transactions
#[derive(Debug, Clone, Default, PartialEq)]
pub struct AgentQueue2Metrics {
    /// Number of this agent's transactions in Queue 2
    pub count: usize,

    /// Nearest deadline among this agent's Queue 2 transactions
    pub nearest_deadline: usize,

    /// Total value of this agent's Queue 2 transactions
    pub total_value: i64,
}

/// Agent-indexed view of RTGS queue for fast lookups
///
/// Maps agent IDs to their transactions in Queue 2, enabling O(1) lookup
/// instead of O(Queue2_Size) linear scans.
#[derive(Debug, Clone)]
pub struct AgentQueueIndex {
    /// Map: AgentID → Vec<TxID> (transactions in Queue 2 for this agent)
    by_agent: HashMap<String, Vec<String>>,

    /// Cached metrics per agent (computed once per tick)
    cached_metrics: HashMap<String, AgentQueue2Metrics>,
}

impl AgentQueueIndex {
    /// Create a new empty index
    pub fn new() -> Self {
        Self {
            by_agent: HashMap::new(),
            cached_metrics: HashMap::new(),
        }
    }

    /// Rebuild index from current RTGS queue
    ///
    /// Scans Queue 2 once to build the index: O(Queue2_Size)
    ///
    /// # Arguments
    ///
    /// * `rtgs_queue` - Vector of transaction IDs in Queue 2
    /// * `transactions` - BTreeMap of all transactions by ID
    ///
    /// # Example
    ///
    /// ```rust
    /// # use payment_simulator_core_rs::models::queue_index::AgentQueueIndex;
    /// # use payment_simulator_core_rs::SimulationState;
    /// # let state = SimulationState::new(vec![]);
    /// let mut index = AgentQueueIndex::new();
    /// index.rebuild(state.rtgs_queue(), state.transactions());
    /// ```
    pub fn rebuild(
        &mut self,
        rtgs_queue: &[String],
        transactions: &std::collections::BTreeMap<String, crate::models::transaction::Transaction>,
    ) {
        self.by_agent.clear();
        self.cached_metrics.clear();

        // Single pass through Queue 2: O(Queue2_Size)
        for tx_id in rtgs_queue {
            if let Some(tx) = transactions.get(tx_id) {
                let agent_id = tx.sender_id().to_string();

                // Update agent's transaction list
                self.by_agent
                    .entry(agent_id.clone())
                    .or_insert_with(Vec::new)
                    .push(tx_id.clone());

                // Update cached metrics
                let metrics = self.cached_metrics
                    .entry(agent_id)
                    .or_insert_with(AgentQueue2Metrics::default);

                metrics.count += 1;
                metrics.total_value += tx.remaining_amount();

                // Update nearest deadline (initialize to max first)
                if metrics.nearest_deadline == 0 {
                    metrics.nearest_deadline = usize::MAX;
                }
                metrics.nearest_deadline = metrics.nearest_deadline.min(tx.deadline_tick());
            }
        }
    }

    /// Get transactions for an agent: O(1) lookup
    ///
    /// Returns a slice of transaction IDs for the specified agent.
    /// If agent has no transactions in Queue 2, returns empty slice.
    ///
    /// # Arguments
    ///
    /// * `agent_id` - Agent identifier
    ///
    /// # Returns
    ///
    /// Slice of transaction IDs, or empty slice if none found
    pub fn get_agent_transactions(&self, agent_id: &str) -> &[String] {
        self.by_agent
            .get(agent_id)
            .map(|v| v.as_slice())
            .unwrap_or(&[])
    }

    /// Get cached metrics for an agent: O(1) lookup
    ///
    /// # Arguments
    ///
    /// * `agent_id` - Agent identifier
    ///
    /// # Returns
    ///
    /// Cached metrics, or default (zero) if agent has no Queue 2 transactions
    pub fn get_metrics(&self, agent_id: &str) -> AgentQueue2Metrics {
        self.cached_metrics
            .get(agent_id)
            .cloned()
            .unwrap_or_default()
    }

    /// Check if index is empty
    pub fn is_empty(&self) -> bool {
        self.by_agent.is_empty()
    }

    /// Get number of agents with Queue 2 transactions
    pub fn num_agents(&self) -> usize {
        self.by_agent.len()
    }
}

impl Default for AgentQueueIndex {
    fn default() -> Self {
        Self::new()
    }
}

// ============================================================================
// TESTS - Phase 1: AgentQueueIndex (TDD)
// ============================================================================

#[cfg(test)]
mod tests {
    use super::*;
    use crate::{Agent, SimulationState, Transaction};

    #[test]
    fn test_new_index_is_empty() {
        let index = AgentQueueIndex::new();

        assert!(index.is_empty());
        assert_eq!(index.num_agents(), 0);
        assert_eq!(index.get_agent_transactions("BANK_A").len(), 0);
    }

    #[test]
    fn test_empty_index_returns_default_metrics() {
        let index = AgentQueueIndex::new();

        let metrics = index.get_metrics("BANK_A");

        assert_eq!(metrics.count, 0);
        assert_eq!(metrics.nearest_deadline, 0);
        assert_eq!(metrics.total_value, 0);
    }

    #[test]
    fn test_rebuild_with_empty_queue() {
        let agents = vec![
            Agent::new("BANK_A".to_string(), 1_000_000),
            Agent::new("BANK_B".to_string(), 2_000_000),
        ];
        let state = SimulationState::new(agents);

        let mut index = AgentQueueIndex::new();
        index.rebuild(state.rtgs_queue(), state.transactions());

        assert!(index.is_empty());
        assert_eq!(index.get_agent_transactions("BANK_A").len(), 0);
    }

    #[test]
    fn test_rebuild_indexes_single_transaction() {
        // Create state with one transaction in Queue 2
        let mut state = create_state_with_agents();
        let tx = Transaction::new(
            "BANK_A".to_string(),
            "BANK_B".to_string(),
            100_000,
            0,
            100,
        );
        let tx_id = tx.id().to_string();

        state.add_transaction(tx);
        state.rtgs_queue_mut().push(tx_id.clone());

        // Rebuild index
        let mut index = AgentQueueIndex::new();
        index.rebuild(state.rtgs_queue(), state.transactions());

        // Verify index contains transaction
        let bank_a_txs = index.get_agent_transactions("BANK_A");
        assert_eq!(bank_a_txs.len(), 1);
        assert_eq!(bank_a_txs[0], tx_id);

        // Verify metrics
        let metrics = index.get_metrics("BANK_A");
        assert_eq!(metrics.count, 1);
        assert_eq!(metrics.total_value, 100_000);
        assert_eq!(metrics.nearest_deadline, 100);
    }

    #[test]
    fn test_rebuild_indexes_multiple_transactions_same_agent() {
        let mut state = create_state_with_agents();

        // Add 3 transactions from BANK_A
        let tx1 = Transaction::new("BANK_A".to_string(), "BANK_B".to_string(), 100_000, 0, 50);
        let tx2 = Transaction::new("BANK_A".to_string(), "BANK_B".to_string(), 200_000, 0, 100);
        let tx3 = Transaction::new("BANK_A".to_string(), "BANK_B".to_string(), 150_000, 0, 75);

        let tx1_id = tx1.id().to_string();
        let tx2_id = tx2.id().to_string();
        let tx3_id = tx3.id().to_string();

        state.add_transaction(tx1);
        state.add_transaction(tx2);
        state.add_transaction(tx3);

        state.rtgs_queue_mut().push(tx1_id.clone());
        state.rtgs_queue_mut().push(tx2_id.clone());
        state.rtgs_queue_mut().push(tx3_id.clone());

        // Rebuild index
        let mut index = AgentQueueIndex::new();
        index.rebuild(state.rtgs_queue(), state.transactions());

        // Verify index contains all transactions
        let bank_a_txs = index.get_agent_transactions("BANK_A");
        assert_eq!(bank_a_txs.len(), 3);
        assert!(bank_a_txs.contains(&tx1_id));
        assert!(bank_a_txs.contains(&tx2_id));
        assert!(bank_a_txs.contains(&tx3_id));

        // Verify metrics
        let metrics = index.get_metrics("BANK_A");
        assert_eq!(metrics.count, 3);
        assert_eq!(metrics.total_value, 450_000); // 100k + 200k + 150k
        assert_eq!(metrics.nearest_deadline, 50);  // min(50, 100, 75)
    }

    #[test]
    fn test_rebuild_indexes_multiple_agents() {
        let mut state = create_state_with_agents();

        // Add transactions from different agents
        let tx1 = Transaction::new("BANK_A".to_string(), "BANK_B".to_string(), 100_000, 0, 100);
        let tx2 = Transaction::new("BANK_B".to_string(), "BANK_A".to_string(), 200_000, 0, 100);
        let tx3 = Transaction::new("BANK_A".to_string(), "BANK_B".to_string(), 150_000, 0, 100);

        let tx1_id = tx1.id().to_string();
        let tx2_id = tx2.id().to_string();
        let tx3_id = tx3.id().to_string();

        state.add_transaction(tx1);
        state.add_transaction(tx2);
        state.add_transaction(tx3);

        state.rtgs_queue_mut().push(tx1_id.clone());
        state.rtgs_queue_mut().push(tx2_id.clone());
        state.rtgs_queue_mut().push(tx3_id.clone());

        // Rebuild index
        let mut index = AgentQueueIndex::new();
        index.rebuild(state.rtgs_queue(), state.transactions());

        // Verify BANK_A has 2 transactions
        let bank_a_txs = index.get_agent_transactions("BANK_A");
        assert_eq!(bank_a_txs.len(), 2);
        assert!(bank_a_txs.contains(&tx1_id));
        assert!(bank_a_txs.contains(&tx3_id));

        // Verify BANK_B has 1 transaction
        let bank_b_txs = index.get_agent_transactions("BANK_B");
        assert_eq!(bank_b_txs.len(), 1);
        assert!(bank_b_txs.contains(&tx2_id));

        // Verify num_agents
        assert_eq!(index.num_agents(), 2);
    }

    #[test]
    fn test_rebuild_clears_previous_index() {
        let mut state = create_state_with_agents();

        // First rebuild with one transaction
        let tx1 = Transaction::new("BANK_A".to_string(), "BANK_B".to_string(), 100_000, 0, 100);
        let tx1_id = tx1.id().to_string();
        state.add_transaction(tx1);
        state.rtgs_queue_mut().push(tx1_id.clone());

        let mut index = AgentQueueIndex::new();
        index.rebuild(state.rtgs_queue(), state.transactions());

        assert_eq!(index.get_agent_transactions("BANK_A").len(), 1);

        // Clear queue and rebuild
        state.rtgs_queue_mut().clear();
        index.rebuild(state.rtgs_queue(), state.transactions());

        // Index should be empty now
        assert!(index.is_empty());
        assert_eq!(index.get_agent_transactions("BANK_A").len(), 0);
    }

    // ========================================================================
    // Property Test: Index matches linear scan results
    // ========================================================================

    #[test]
    fn test_index_matches_linear_scan() {
        let mut state = create_state_with_agents();

        // Add various transactions
        let txs = vec![
            Transaction::new("BANK_A".to_string(), "BANK_B".to_string(), 100_000, 0, 100),
            Transaction::new("BANK_A".to_string(), "BANK_B".to_string(), 200_000, 0, 50),
            Transaction::new("BANK_B".to_string(), "BANK_A".to_string(), 150_000, 0, 75),
            Transaction::new("BANK_A".to_string(), "BANK_B".to_string(), 300_000, 0, 120),
        ];

        for tx in txs {
            let tx_id = tx.id().to_string();
            state.add_transaction(tx);
            state.rtgs_queue_mut().push(tx_id);
        }

        // Rebuild index
        let mut index = AgentQueueIndex::new();
        index.rebuild(state.rtgs_queue(), state.transactions());

        // For each agent, verify index matches linear scan
        for agent_id in ["BANK_A", "BANK_B"] {
            // Get transactions using index
            let indexed_txs = index.get_agent_transactions(agent_id);

            // Get transactions using linear scan (old way)
            let scanned_txs: Vec<String> = state
                .rtgs_queue()
                .iter()
                .filter(|tx_id| {
                    state
                        .get_transaction(tx_id)
                        .map(|tx| tx.sender_id() == agent_id)
                        .unwrap_or(false)
                })
                .cloned()
                .collect();

            // Must match exactly
            assert_eq!(indexed_txs.len(), scanned_txs.len(),
                "Index length mismatch for {}", agent_id);

            for tx_id in indexed_txs {
                assert!(scanned_txs.contains(tx_id),
                    "Index contains {} but linear scan doesn't", tx_id);
            }
        }
    }

    // ========================================================================
    // Helper Functions
    // ========================================================================

    fn create_state_with_agents() -> SimulationState {
        let agents = vec![
            Agent::new("BANK_A".to_string(), 1_000_000),
            Agent::new("BANK_B".to_string(), 2_000_000),
        ];
        SimulationState::new(agents)
    }
}
