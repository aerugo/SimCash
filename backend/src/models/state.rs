//! Simulation State
//!
//! Represents the complete state of the payment system simulation.
//! Contains all agents, transactions, and the central RTGS queue.
//!
//! # Queue Architecture Note
//!
//! This module implements **Queue 2** (central RTGS queue) from the two-queue architecture:
//! - **Queue 1** (future): Per-agent internal queues for policy decisions (Phase 4-5)
//! - **Queue 2** (current): Central bank queue for liquidity-based retry (Phase 3)
//!
//! See `/docs/queue_architecture.md` for detailed explanation.
//!
//! # Critical Invariants
//!
//! 1. **Balance Conservation**: Sum of all agent balances is constant
//! 2. **Transaction Uniqueness**: Each transaction ID appears exactly once
//! 3. **Queue Validity**: All transaction IDs in rtgs_queue exist in transactions map
//! 4. **No Orphan Transactions**: Every transaction references valid sender and receiver agents

use crate::models::agent::Agent;
use crate::models::collateral_event::CollateralEvent;
use crate::models::event::{Event, EventLog};
use crate::models::queue_index::AgentQueueIndex;
use crate::models::transaction::Transaction;
use crate::settlement::lsm::LsmCycleEvent;
use std::collections::BTreeMap;

/// Complete simulation state
///
/// This struct holds all state for a running payment simulation:
/// - Agent settlement accounts (banks at central bank)
/// - All transactions (pending, settled, dropped)
/// - Central RTGS queue (transactions awaiting liquidity)
///
/// # Example
///
/// ```rust
/// use payment_simulator_core_rs::{Agent, SimulationState};
///
/// let bank_a = Agent::new("BANK_A".to_string(), 1_000_000);
/// let bank_b = Agent::new("BANK_B".to_string(), 2_000_000);
///
/// let state = SimulationState::new(vec![bank_a, bank_b]);
/// assert_eq!(state.num_agents(), 2);
/// assert_eq!(state.queue_size(), 0);
/// ```
#[derive(Debug, Clone)]
pub struct SimulationState {
    /// All agents (banks) in the system, indexed by ID
    agents: BTreeMap<String, Agent>,

    /// All transactions, indexed by transaction ID
    transactions: BTreeMap<String, Transaction>,

    /// Central RTGS queue: transaction IDs awaiting settlement
    ///
    /// This is **Queue 2** in the two-queue architecture:
    /// - **Queue 1** (Phase 4-5): Internal agent queues for cash manager policy decisions
    /// - **Queue 2** (Phase 3): Central bank queue for mechanical liquidity retry ← YOU ARE HERE
    ///
    /// Transactions enter this queue when:
    /// - Submitted to RTGS via settlement functions
    /// - Sender has insufficient liquidity (balance + credit < amount)
    ///
    /// Transactions leave this queue when:
    /// - Settlement succeeds (liquidity became available via incoming payments)
    /// - Deadline expires (transaction dropped)
    /// - LSM finds offsetting opportunities (Phase 3b)
    ///
    /// See `/docs/queue_architecture.md` for complete two-queue model explanation.
    rtgs_queue: Vec<String>,

    /// Event log for replay and auditing
    ///
    /// Records all significant state changes during simulation.
    /// Enables deterministic replay and debugging.
    event_log: EventLog,

    /// Collateral management events (Phase 10 persistence)
    ///
    /// Tracks every collateral post/withdraw/hold decision with full context.
    /// Enables granular analysis of collateral behavior.
    pub collateral_events: Vec<CollateralEvent>,

    /// LSM cycle events (Phase 4 persistence)
    ///
    /// Tracks every LSM cycle settled (bilateral offsets and multilateral cycles).
    /// Enables analysis of liquidity-saving mechanism effectiveness.
    pub lsm_cycle_events: Vec<LsmCycleEvent>,

    /// Agent-indexed view of RTGS queue for O(1) lookups
    ///
    /// Performance optimization: Maps agent IDs to their Queue 2 transactions.
    /// Eliminates O(N × M) nested loops in cost calculations and policy evaluation.
    ///
    /// Must be rebuilt after any modification to rtgs_queue via `rebuild_queue2_index()`.
    queue2_index: AgentQueueIndex,
}

impl SimulationState {
    /// Create a new simulation state with given agents
    ///
    /// # Arguments
    ///
    /// * `agents` - Vector of agents to initialize system with
    ///
    /// # Example
    ///
    /// ```rust
    /// use payment_simulator_core_rs::{Agent, SimulationState};
    ///
    /// let agents = vec![
    ///     Agent::new("BANK_A".to_string(), 1_000_000),
    ///     Agent::new("BANK_B".to_string(), 2_000_000),
    /// ];
    ///
    /// let state = SimulationState::new(agents);
    /// assert_eq!(state.num_agents(), 2);
    /// ```
    pub fn new(agents: Vec<Agent>) -> Self {
        let agents_map = agents
            .into_iter()
            .map(|agent| (agent.id().to_string(), agent))
            .collect();

        Self {
            agents: agents_map,
            transactions: BTreeMap::new(),
            rtgs_queue: Vec::new(),
            event_log: EventLog::new(),
            collateral_events: Vec::new(),
            lsm_cycle_events: Vec::new(),
            queue2_index: AgentQueueIndex::new(),
        }
    }

    /// Create simulation state from existing components (for checkpoint restoration)
    ///
    /// # Arguments
    ///
    /// * `agents` - BTreeMap of agents by ID
    /// * `transactions` - BTreeMap of transactions by ID
    /// * `rtgs_queue` - Vector of transaction IDs in RTGS queue
    ///
    /// # Returns
    ///
    /// Result containing SimulationState or error if invalid
    ///
    /// # Errors
    ///
    /// Returns error if:
    /// - RTGS queue contains transaction IDs not in transactions map
    /// - Agents reference invalid transaction IDs in their queues
    pub fn from_parts(
        agents: BTreeMap<String, Agent>,
        transactions: BTreeMap<String, Transaction>,
        rtgs_queue: Vec<String>,
    ) -> Result<Self, String> {
        // Validate RTGS queue references
        for tx_id in &rtgs_queue {
            if !transactions.contains_key(tx_id) {
                return Err(format!(
                    "RTGS queue contains invalid transaction ID: {}",
                    tx_id
                ));
            }
        }

        // Validate agent queue references
        for (agent_id, agent) in &agents {
            for tx_id in agent.outgoing_queue() {
                if !transactions.contains_key(tx_id) {
                    return Err(format!(
                        "Agent {} queue contains invalid transaction ID: {}",
                        agent_id, tx_id
                    ));
                }
            }
        }

        Ok(Self {
            agents,
            transactions,
            rtgs_queue,
            event_log: EventLog::new(),
            collateral_events: Vec::new(),
            lsm_cycle_events: Vec::new(),
            queue2_index: AgentQueueIndex::new(),
        })
    }

    /// Get rtgs queue (alias for compatibility)
    pub fn get_rtgs_queue(&self) -> &Vec<String> {
        &self.rtgs_queue
    }

    /// Get reference to an agent by ID
    pub fn get_agent(&self, id: &str) -> Option<&Agent> {
        self.agents.get(id)
    }

    /// Get mutable reference to an agent by ID
    pub fn get_agent_mut(&mut self, id: &str) -> Option<&mut Agent> {
        self.agents.get_mut(id)
    }

    /// Get all agent IDs in the simulation
    ///
    /// Returns agent IDs in deterministic sorted order to ensure
    /// reproducible behavior (important for checkpoint determinism).
    pub fn get_all_agent_ids(&self) -> Vec<String> {
        let mut ids: Vec<String> = self.agents.keys().cloned().collect();
        ids.sort(); // Deterministic order for reproducibility
        ids
    }

    /// Get reference to a transaction by ID
    pub fn get_transaction(&self, id: &str) -> Option<&Transaction> {
        self.transactions.get(id)
    }

    /// Get mutable reference to a transaction by ID
    pub fn get_transaction_mut(&mut self, id: &str) -> Option<&mut Transaction> {
        self.transactions.get_mut(id)
    }

    /// Add a transaction to the system
    ///
    /// # Arguments
    ///
    /// * `transaction` - Transaction to add
    ///
    /// # Panics
    ///
    /// Panics if transaction ID already exists (duplicate transaction)
    pub fn add_transaction(&mut self, transaction: Transaction) {
        let id = transaction.id().to_string();
        assert!(
            !self.transactions.contains_key(&id),
            "Transaction ID {} already exists",
            id
        );
        self.transactions.insert(id, transaction);
    }

    /// Add a transaction to the RTGS queue
    ///
    /// # Arguments
    ///
    /// * `transaction_id` - ID of transaction to queue
    ///
    /// # Panics
    ///
    /// Panics if transaction ID doesn't exist in transactions map
    pub fn queue_transaction(&mut self, transaction_id: String) {
        assert!(
            self.transactions.contains_key(&transaction_id),
            "Cannot queue non-existent transaction {}",
            transaction_id
        );
        self.rtgs_queue.push(transaction_id);
    }

    /// Get current size of RTGS queue
    pub fn queue_size(&self) -> usize {
        self.rtgs_queue.len()
    }

    /// Get reference to RTGS queue
    pub fn rtgs_queue(&self) -> &Vec<String> {
        &self.rtgs_queue
    }

    /// Get mutable reference to RTGS queue
    pub fn rtgs_queue_mut(&mut self) -> &mut Vec<String> {
        &mut self.rtgs_queue
    }

    /// Get reference to all agents
    pub fn agents(&self) -> &BTreeMap<String, Agent> {
        &self.agents
    }

    /// Get mutable reference to all agents
    pub fn agents_mut(&mut self) -> &mut BTreeMap<String, Agent> {
        &mut self.agents
    }

    /// Get reference to all transactions
    pub fn transactions(&self) -> &BTreeMap<String, Transaction> {
        &self.transactions
    }

    /// Get mutable reference to all transactions
    pub fn transactions_mut(&mut self) -> &mut BTreeMap<String, Transaction> {
        &mut self.transactions
    }

    /// Get number of agents in system
    pub fn num_agents(&self) -> usize {
        self.agents.len()
    }

    /// Get number of transactions in system
    pub fn num_transactions(&self) -> usize {
        self.transactions.len()
    }

    /// Calculate total system balance (for invariant checking)
    ///
    /// # Returns
    ///
    /// Sum of all agent balances. This should remain constant during settlement.
    pub fn total_balance(&self) -> i64 {
        self.agents.values().map(|agent| agent.balance()).sum()
    }

    /// Calculate total value in RTGS queue (Queue 2)
    ///
    /// # Returns
    ///
    /// Sum of remaining amounts for all queued transactions
    pub fn queue_value(&self) -> i64 {
        self.rtgs_queue
            .iter()
            .filter_map(|tx_id| self.transactions.get(tx_id))
            .map(|tx| tx.remaining_amount())
            .sum()
    }

    // =========================================================================
    // Queue 1 (Internal Bank Queues) Accessor Methods - Phase 4
    // =========================================================================

    /// Get total number of transactions in all internal queues (Queue 1)
    ///
    /// Aggregates across all agents' outgoing_queue.
    ///
    /// # Returns
    ///
    /// Sum of all agents' internal queue sizes
    ///
    /// # Example
    ///
    /// ```
    /// use payment_simulator_core_rs::{Agent, SimulationState};
    ///
    /// let mut agents = vec![
    ///     Agent::new("BANK_A".to_string(), 1_000_000),
    ///     Agent::new("BANK_B".to_string(), 1_000_000),
    /// ];
    /// agents[0].queue_outgoing("tx_001".to_string());
    /// agents[1].queue_outgoing("tx_002".to_string());
    ///
    /// let state = SimulationState::new(agents);
    /// assert_eq!(state.total_internal_queue_size(), 2);
    /// ```
    pub fn total_internal_queue_size(&self) -> usize {
        self.agents
            .values()
            .map(|agent| agent.outgoing_queue_size())
            .sum()
    }

    /// Get total value in all internal queues (Queue 1)
    ///
    /// Aggregates across all agents' outgoing_queue.
    ///
    /// # Returns
    ///
    /// Sum of remaining amounts for all transactions in Queue 1
    ///
    /// # Example
    ///
    /// ```
    /// use payment_simulator_core_rs::{Agent, SimulationState, Transaction};
    ///
    /// let agents = vec![Agent::new("BANK_A".to_string(), 1_000_000)];
    /// let mut state = SimulationState::new(agents);
    ///
    /// let tx = Transaction::new("BANK_A".to_string(), "BANK_B".to_string(), 500_000, 0, 100);
    /// let tx_id = tx.id().to_string();
    /// state.add_transaction(tx);
    /// state.get_agent_mut("BANK_A").unwrap().queue_outgoing(tx_id);
    ///
    /// assert_eq!(state.total_internal_queue_value(), 500_000);
    /// ```
    pub fn total_internal_queue_value(&self) -> i64 {
        self.agents
            .values()
            .flat_map(|agent| agent.outgoing_queue())
            .filter_map(|tx_id| self.transactions.get(tx_id))
            .map(|tx| tx.remaining_amount())
            .sum()
    }

    /// Get transactions approaching deadline (urgent transactions)
    ///
    /// Scans all agents' internal queues for transactions with deadline
    /// within `urgency_threshold` ticks from current tick.
    ///
    /// # Arguments
    ///
    /// * `current_tick` - Current simulation tick
    /// * `urgency_threshold` - Number of ticks before deadline to consider urgent
    ///
    /// # Returns
    ///
    /// Vector of (agent_id, transaction_id) pairs for urgent transactions
    ///
    /// # Example
    ///
    /// ```
    /// use payment_simulator_core_rs::{Agent, SimulationState, Transaction};
    ///
    /// let agents = vec![Agent::new("BANK_A".to_string(), 1_000_000)];
    /// let mut state = SimulationState::new(agents);
    ///
    /// // Transaction with deadline at tick 10
    /// let tx = Transaction::new("BANK_A".to_string(), "BANK_B".to_string(), 500_000, 0, 10);
    /// let tx_id = tx.id().to_string();
    /// state.add_transaction(tx);
    /// state.get_agent_mut("BANK_A").unwrap().queue_outgoing(tx_id);
    ///
    /// // At tick 8, with threshold 5, this is urgent (deadline - current = 2 < 5)
    /// let urgent = state.get_urgent_transactions(8, 5);
    /// assert_eq!(urgent.len(), 1);
    /// assert_eq!(urgent[0].0, "BANK_A");
    /// ```
    pub fn get_urgent_transactions(
        &self,
        current_tick: usize,
        urgency_threshold: usize,
    ) -> Vec<(String, String)> {
        let mut urgent = Vec::new();

        for (agent_id, agent) in &self.agents {
            for tx_id in agent.outgoing_queue() {
                if let Some(tx) = self.transactions.get(tx_id) {
                    let ticks_to_deadline = tx.deadline_tick().saturating_sub(current_tick);
                    if ticks_to_deadline <= urgency_threshold {
                        urgent.push((agent_id.clone(), tx_id.clone()));
                    }
                }
            }
        }

        urgent
    }

    /// Get list of agents with non-empty internal queues
    ///
    /// # Returns
    ///
    /// Vector of agent IDs that have transactions in Queue 1
    pub fn agents_with_queued_transactions(&self) -> Vec<String> {
        self.agents
            .iter()
            .filter(|(_, agent)| agent.outgoing_queue_size() > 0)
            .map(|(id, _)| id.clone())
            .collect()
    }

    /// Get outgoing queue value for specific agent
    ///
    /// # Arguments
    ///
    /// * `agent_id` - Agent to query
    ///
    /// # Returns
    ///
    /// Total value in agent's outgoing queue, or 0 if agent not found
    pub fn agent_queue_value(&self, agent_id: &str) -> i64 {
        if let Some(agent) = self.agents.get(agent_id) {
            agent
                .outgoing_queue()
                .iter()
                .filter_map(|tx_id| self.transactions.get(tx_id))
                .map(|tx| tx.remaining_amount())
                .sum()
        } else {
            0
        }
    }

    // =========================================================================
    // Event Log Methods
    // =========================================================================

    /// Get reference to event log
    pub fn event_log(&self) -> &EventLog {
        &self.event_log
    }

    /// Get mutable reference to event log
    pub fn event_log_mut(&mut self) -> &mut EventLog {
        &mut self.event_log
    }

    /// Log an event
    ///
    /// # Arguments
    ///
    /// * `event` - Event to log
    pub fn log_event(&mut self, event: Event) {
        self.event_log.log(event);
    }

    // =========================================================================
    // Scenario Event Support Methods
    // =========================================================================

    /// Set credit limit for an agent
    ///
    /// # Arguments
    ///
    /// * `agent_id` - Agent to modify
    /// * `new_limit` - New credit limit (must be non-negative)
    ///
    /// # Panics
    ///
    /// Panics if agent not found or new_limit is negative
    pub fn set_credit_limit(&mut self, agent_id: &str, new_limit: i64) {
        assert!(new_limit >= 0, "Credit limit must be non-negative");

        if let Some(agent) = self.agents.get_mut(agent_id) {
            agent.set_unsecured_cap(new_limit);
        } else {
            panic!("Agent not found: {}", agent_id);
        }
    }

    // =========================================================================
    // Queue 2 Index Methods - Performance Optimization
    // =========================================================================

    /// Rebuild Queue 2 index after modifications
    ///
    /// **MUST** be called after any operation that modifies rtgs_queue:
    /// - Adding transactions to queue
    /// - Removing transactions from queue
    /// - Settling transactions via RTGS or LSM
    ///
    /// Complexity: O(Queue2_Size) - single scan to rebuild index
    ///
    /// # Example
    ///
    /// ```rust
    /// # use payment_simulator_core_rs::{Agent, SimulationState, Transaction};
    /// let agents = vec![Agent::new("BANK_A".to_string(), 1_000_000)];
    /// let mut state = SimulationState::new(agents);
    ///
    /// let tx = Transaction::new("BANK_A".to_string(), "BANK_B".to_string(), 100_000, 0, 100);
    /// state.add_transaction(tx.clone());
    /// state.rtgs_queue_mut().push(tx.id().to_string());
    ///
    /// // CRITICAL: Rebuild index after modifying queue
    /// state.rebuild_queue2_index();
    ///
    /// // Now index can be used for O(1) lookups
    /// assert_eq!(state.queue2_index().get_agent_transactions("BANK_A").len(), 1);
    /// ```
    pub fn rebuild_queue2_index(&mut self) {
        let rtgs_queue = &self.rtgs_queue;
        let transactions = &self.transactions;
        self.queue2_index.rebuild(rtgs_queue, transactions);
    }

    /// Get reference to Queue 2 index
    ///
    /// Provides O(1) lookup of transactions by agent ID instead of O(Queue2_Size) linear scan.
    ///
    /// # Returns
    ///
    /// Reference to AgentQueueIndex for transaction lookups
    ///
    /// # Example
    ///
    /// ```rust
    /// # use payment_simulator_core_rs::{Agent, SimulationState, Transaction};
    /// let agents = vec![Agent::new("BANK_A".to_string(), 1_000_000)];
    /// let mut state = SimulationState::new(agents);
    ///
    /// let tx = Transaction::new("BANK_A".to_string(), "BANK_B".to_string(), 100_000, 0, 100);
    /// state.add_transaction(tx.clone());
    /// state.rtgs_queue_mut().push(tx.id().to_string());
    /// state.rebuild_queue2_index();
    ///
    /// // Fast O(1) lookup via index
    /// let agent_txs = state.queue2_index().get_agent_transactions("BANK_A");
    /// assert_eq!(agent_txs.len(), 1);
    ///
    /// // Get cached metrics
    /// let metrics = state.queue2_index().get_metrics("BANK_A");
    /// assert_eq!(metrics.count, 1);
    /// assert_eq!(metrics.total_value, 100_000);
    /// ```
    pub fn queue2_index(&self) -> &AgentQueueIndex {
        &self.queue2_index
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_new_state() {
        let agents = vec![
            Agent::new("A".to_string(), 1_000_000),
            Agent::new("B".to_string(), 2_000_000),
        ];

        let state = SimulationState::new(agents);

        assert_eq!(state.num_agents(), 2);
        assert_eq!(state.num_transactions(), 0);
        assert_eq!(state.queue_size(), 0);
        assert_eq!(state.total_balance(), 3_000_000);
    }

    #[test]
    fn test_add_transaction() {
        let agents = vec![Agent::new("A".to_string(), 1_000_000)];
        let mut state = SimulationState::new(agents);

        let tx = Transaction::new("A".to_string(), "B".to_string(), 500_000, 0, 100);
        let tx_id = tx.id().to_string();

        state.add_transaction(tx);

        assert_eq!(state.num_transactions(), 1);
        assert!(state.get_transaction(&tx_id).is_some());
    }

    #[test]
    fn test_queue_transaction() {
        let agents = vec![Agent::new("A".to_string(), 1_000_000)];
        let mut state = SimulationState::new(agents);

        let tx = Transaction::new("A".to_string(), "B".to_string(), 500_000, 0, 100);
        let tx_id = tx.id().to_string();

        state.add_transaction(tx);
        state.queue_transaction(tx_id.clone());

        assert_eq!(state.queue_size(), 1);
        assert_eq!(state.rtgs_queue()[0], tx_id);
    }

    #[test]
    fn test_total_balance() {
        let agents = vec![
            Agent::new("A".to_string(), 1_000_000),
            Agent::new("B".to_string(), 2_000_000),
            Agent::new("C".to_string(), 500_000),
        ];

        let state = SimulationState::new(agents);

        assert_eq!(state.total_balance(), 3_500_000);
    }

    #[test]
    fn test_queue_value() {
        let agents = vec![Agent::new("A".to_string(), 5_000_000)];
        let mut state = SimulationState::new(agents);

        let tx1 = Transaction::new("A".to_string(), "B".to_string(), 1_000_000, 0, 100);
        let tx2 = Transaction::new("A".to_string(), "C".to_string(), 2_000_000, 0, 100);

        let tx1_id = tx1.id().to_string();
        let tx2_id = tx2.id().to_string();

        state.add_transaction(tx1);
        state.add_transaction(tx2);

        state.queue_transaction(tx1_id);
        state.queue_transaction(tx2_id);

        assert_eq!(state.queue_value(), 3_000_000);
    }
}
