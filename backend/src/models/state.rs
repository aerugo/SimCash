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
use crate::models::transaction::Transaction;
use std::collections::HashMap;

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
/// let bank_a = Agent::new("BANK_A".to_string(), 1_000_000, 500_000);
/// let bank_b = Agent::new("BANK_B".to_string(), 2_000_000, 0);
///
/// let state = SimulationState::new(vec![bank_a, bank_b]);
/// assert_eq!(state.num_agents(), 2);
/// assert_eq!(state.queue_size(), 0);
/// ```
#[derive(Debug, Clone)]
pub struct SimulationState {
    /// All agents (banks) in the system, indexed by ID
    agents: HashMap<String, Agent>,

    /// All transactions, indexed by transaction ID
    transactions: HashMap<String, Transaction>,

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
    ///     Agent::new("BANK_A".to_string(), 1_000_000, 0),
    ///     Agent::new("BANK_B".to_string(), 2_000_000, 0),
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
            transactions: HashMap::new(),
            rtgs_queue: Vec::new(),
        }
    }

    /// Get reference to an agent by ID
    pub fn get_agent(&self, id: &str) -> Option<&Agent> {
        self.agents.get(id)
    }

    /// Get mutable reference to an agent by ID
    pub fn get_agent_mut(&mut self, id: &str) -> Option<&mut Agent> {
        self.agents.get_mut(id)
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
    pub fn agents(&self) -> &HashMap<String, Agent> {
        &self.agents
    }

    /// Get mutable reference to all agents
    pub fn agents_mut(&mut self) -> &mut HashMap<String, Agent> {
        &mut self.agents
    }

    /// Get reference to all transactions
    pub fn transactions(&self) -> &HashMap<String, Transaction> {
        &self.transactions
    }

    /// Get mutable reference to all transactions
    pub fn transactions_mut(&mut self) -> &mut HashMap<String, Transaction> {
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

    /// Calculate total value in RTGS queue
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
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_new_state() {
        let agents = vec![
            Agent::new("A".to_string(), 1_000_000, 0),
            Agent::new("B".to_string(), 2_000_000, 0),
        ];

        let state = SimulationState::new(agents);

        assert_eq!(state.num_agents(), 2);
        assert_eq!(state.num_transactions(), 0);
        assert_eq!(state.queue_size(), 0);
        assert_eq!(state.total_balance(), 3_000_000);
    }

    #[test]
    fn test_add_transaction() {
        let agents = vec![Agent::new("A".to_string(), 1_000_000, 0)];
        let mut state = SimulationState::new(agents);

        let tx = Transaction::new("A".to_string(), "B".to_string(), 500_000, 0, 100);
        let tx_id = tx.id().to_string();

        state.add_transaction(tx);

        assert_eq!(state.num_transactions(), 1);
        assert!(state.get_transaction(&tx_id).is_some());
    }

    #[test]
    fn test_queue_transaction() {
        let agents = vec![Agent::new("A".to_string(), 1_000_000, 0)];
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
            Agent::new("A".to_string(), 1_000_000, 0),
            Agent::new("B".to_string(), 2_000_000, 0),
            Agent::new("C".to_string(), 500_000, 0),
        ];

        let state = SimulationState::new(agents);

        assert_eq!(state.total_balance(), 3_500_000);
    }

    #[test]
    fn test_queue_value() {
        let agents = vec![Agent::new("A".to_string(), 5_000_000, 0)];
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
