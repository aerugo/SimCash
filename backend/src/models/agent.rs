//! Agent (Bank) model
//!
//! Represents a bank participating in the payment system.
//! Each agent has:
//! - Settlement balance at central bank (i64 cents)
//! - Credit limit for intraday overdraft (i64 cents)
//!
//! # Phase 4 Implementation Note
//!
//! This implementation models the agent's **settlement account at the central bank**
//! plus **internal transaction queues** (Queue 1) for cash manager policy decisions.
//!
//! **Two-Queue Architecture**:
//! - **Queue 1** (Phase 4): `Agent.outgoing_queue` for cash manager policy ← IMPLEMENTED
//! - **Queue 2** (Phase 3): `SimulationState.rtgs_queue` for central bank retry ← IMPLEMENTED
//!
//! See `/docs/queue_architecture.md` for complete architecture explanation.
//!
//! CRITICAL: All money values are i64 (cents)

use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Errors that can occur during agent operations
#[derive(Debug, Error, PartialEq)]
pub enum AgentError {
    #[error("Insufficient liquidity: required {required}, available {available}")]
    InsufficientLiquidity { required: i64, available: i64 },
}

/// Represents a bank (agent) in the payment system
///
/// # Interpretation (Phase 4)
///
/// This struct models the bank's **settlement account at the central bank**
/// plus internal queues for cash manager policy decisions:
/// - `balance` = Bank's reserves at central bank (what RTGS settlement operates on)
/// - `credit_limit` = Intraday overdraft facility (collateralized or priced)
/// - `outgoing_queue` = Transactions awaiting release decision (Queue 1)
/// - `incoming_expected` = Expected incoming payments (for forecasting)
///
/// See `/docs/queue_architecture.md` for complete two-queue model.
///
/// # Example
/// ```
/// use payment_simulator_core_rs::Agent;
///
/// let mut agent = Agent::new("BANK_A".to_string(), 1000000, 500000);
/// assert_eq!(agent.balance(), 1000000); // $10,000.00 in cents
///
/// agent.debit(300000).unwrap(); // Pay $3,000
/// assert_eq!(agent.balance(), 700000);
/// ```
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Agent {
    /// Unique agent identifier (e.g., "BANK_A")
    id: String,

    /// Current balance in settlement account at central bank (i64 cents)
    /// Positive = funds available
    /// Negative = using intraday credit
    ///
    /// This represents the bank's reserves at the central bank, where RTGS
    /// settlement debits and credits occur.
    balance: i64,

    /// Maximum intraday credit/overdraft allowed (i64 cents)
    /// This is the absolute limit the agent can go negative
    ///
    /// Represents collateralized intraday credit or priced overdraft facility
    /// provided by the central bank.
    credit_limit: i64,

    // Phase 4 additions: Queue 1 (Internal Bank Queue)
    /// Transaction IDs awaiting cash manager release decision (Queue 1)
    ///
    /// Transactions enter here when they arrive from clients.
    /// Cash manager policy decides when to submit them to RTGS (Queue 2).
    ///
    /// See `/docs/queue_architecture.md` Section 1 for Queue 1 explanation.
    outgoing_queue: Vec<String>,

    /// Expected incoming transaction IDs (for liquidity forecasting)
    ///
    /// When a payment is submitted to this agent (receiver), the TX ID
    /// is added here. Used for cash manager policy to forecast inflows.
    incoming_expected: Vec<String>,

    /// Last tick when cash manager made a policy decision
    ///
    /// Used to avoid redundant policy evaluations within same tick.
    last_decision_tick: Option<usize>,

    /// Target minimum balance to maintain (liquidity buffer)
    ///
    /// Cash manager policies may use this to preserve liquidity cushion.
    /// Example: hold transactions if balance - amount < liquidity_buffer.
    liquidity_buffer: i64,
}

impl Agent {
    /// Create a new agent
    ///
    /// # Arguments
    /// * `id` - Unique identifier (e.g., "BANK_A")
    /// * `balance` - Opening balance in cents (can be negative)
    /// * `credit_limit` - Maximum overdraft allowed in cents (positive)
    ///
    /// # Example
    /// ```
    /// use payment_simulator_core_rs::Agent;
    ///
    /// let agent = Agent::new("BANK_A".to_string(), 1000000, 500000);
    /// assert_eq!(agent.balance(), 1000000);
    /// ```
    pub fn new(id: String, balance: i64, credit_limit: i64) -> Self {
        assert!(credit_limit >= 0, "credit_limit must be non-negative");
        Self {
            id,
            balance,
            credit_limit,
            outgoing_queue: Vec::new(),
            incoming_expected: Vec::new(),
            last_decision_tick: None,
            liquidity_buffer: 0, // Default: no buffer requirement
        }
    }

    /// Create a new agent with specified liquidity buffer
    ///
    /// # Arguments
    /// * `id` - Unique identifier
    /// * `balance` - Opening balance in cents
    /// * `credit_limit` - Maximum overdraft in cents
    /// * `liquidity_buffer` - Minimum balance to maintain in cents
    ///
    /// # Example
    /// ```
    /// use payment_simulator_core_rs::Agent;
    ///
    /// // Bank wants to keep at least $1000 as buffer
    /// let agent = Agent::with_buffer("BANK_A".to_string(), 1000000, 500000, 100000);
    /// assert_eq!(agent.liquidity_buffer(), 100000);
    /// ```
    pub fn with_buffer(id: String, balance: i64, credit_limit: i64, liquidity_buffer: i64) -> Self {
        assert!(credit_limit >= 0, "credit_limit must be non-negative");
        assert!(liquidity_buffer >= 0, "liquidity_buffer must be non-negative");
        Self {
            id,
            balance,
            credit_limit,
            outgoing_queue: Vec::new(),
            incoming_expected: Vec::new(),
            last_decision_tick: None,
            liquidity_buffer,
        }
    }

    /// Get agent ID
    pub fn id(&self) -> &str {
        &self.id
    }

    /// Get current balance (i64 cents)
    ///
    /// # Example
    /// ```
    /// use payment_simulator_core_rs::Agent;
    ///
    /// let agent = Agent::new("BANK_A".to_string(), 1000000, 500000);
    /// assert_eq!(agent.balance(), 1000000);
    /// ```
    pub fn balance(&self) -> i64 {
        self.balance
    }

    /// Get credit limit (i64 cents)
    pub fn credit_limit(&self) -> i64 {
        self.credit_limit
    }

    /// Calculate available liquidity (balance + unused credit)
    ///
    /// # Returns
    /// - If balance >= 0: balance + credit_limit
    /// - If balance < 0: credit_limit - abs(balance)
    ///
    /// # Example
    /// ```
    /// use payment_simulator_core_rs::Agent;
    ///
    /// let agent = Agent::new("BANK_A".to_string(), 1000000, 500000);
    /// assert_eq!(agent.available_liquidity(), 1500000);
    /// ```
    pub fn available_liquidity(&self) -> i64 {
        if self.balance >= 0 {
            self.balance + self.credit_limit
        } else {
            // Already using credit, so available = credit_limit - used
            self.credit_limit - self.balance.abs()
        }
    }

    /// Check if agent can pay a given amount
    ///
    /// # Arguments
    /// * `amount` - Amount to check (i64 cents)
    ///
    /// # Example
    /// ```
    /// use payment_simulator_core_rs::Agent;
    ///
    /// let agent = Agent::new("BANK_A".to_string(), 1000000, 500000);
    /// assert!(agent.can_pay(500000)); // Can pay $5,000
    /// assert!(!agent.can_pay(2000000)); // Can't pay $20,000
    /// ```
    pub fn can_pay(&self, amount: i64) -> bool {
        amount <= self.available_liquidity()
    }

    /// Debit (decrease) balance
    ///
    /// # Arguments
    /// * `amount` - Amount to debit (i64 cents, must be positive)
    ///
    /// # Returns
    /// - Ok(()) if successful
    /// - Err if insufficient liquidity
    ///
    /// # Example
    /// ```
    /// use payment_simulator_core_rs::Agent;
    ///
    /// let mut agent = Agent::new("BANK_A".to_string(), 1000000, 500000);
    /// agent.debit(300000).unwrap();
    /// assert_eq!(agent.balance(), 700000);
    /// ```
    pub fn debit(&mut self, amount: i64) -> Result<(), AgentError> {
        assert!(amount >= 0, "amount must be positive");

        if !self.can_pay(amount) {
            return Err(AgentError::InsufficientLiquidity {
                required: amount,
                available: self.available_liquidity(),
            });
        }

        self.balance -= amount;
        Ok(())
    }

    /// Credit (increase) balance
    ///
    /// # Arguments
    /// * `amount` - Amount to credit (i64 cents, must be positive)
    ///
    /// # Example
    /// ```
    /// use payment_simulator_core_rs::Agent;
    ///
    /// let mut agent = Agent::new("BANK_A".to_string(), 1000000, 500000);
    /// agent.credit(500000);
    /// assert_eq!(agent.balance(), 1500000);
    /// ```
    pub fn credit(&mut self, amount: i64) {
        assert!(amount >= 0, "amount must be positive");
        self.balance += amount;
    }

    /// Adjust balance directly (for LSM atomic operations)
    ///
    /// # Safety
    /// This bypasses liquidity checks and should ONLY be used for LSM operations
    /// where bilateral/multilateral netting ensures balance conservation.
    ///
    /// # Arguments
    /// * `delta` - Change to apply (positive = credit, negative = debit)
    ///
    /// # Example
    /// ```
    /// use payment_simulator_core_rs::Agent;
    ///
    /// let mut agent = Agent::new("BANK_A".to_string(), 1000000, 500000);
    /// agent.adjust_balance(-300000); // Debit 300k
    /// assert_eq!(agent.balance(), 700000);
    /// agent.adjust_balance(300000); // Credit 300k
    /// assert_eq!(agent.balance(), 1000000);
    /// ```
    pub fn adjust_balance(&mut self, delta: i64) {
        self.balance += delta;
    }

    /// Check if agent is currently using intraday credit
    ///
    /// # Example
    /// ```
    /// use payment_simulator_core_rs::Agent;
    ///
    /// let mut agent = Agent::new("BANK_A".to_string(), 1000000, 500000);
    /// assert!(!agent.is_using_credit());
    ///
    /// agent.debit(1200000).unwrap();
    /// assert!(agent.is_using_credit());
    /// ```
    pub fn is_using_credit(&self) -> bool {
        self.balance < 0
    }

    /// Get amount of credit currently being used
    ///
    /// # Returns
    /// - 0 if balance >= 0
    /// - abs(balance) if balance < 0
    ///
    /// # Example
    /// ```
    /// use payment_simulator_core_rs::Agent;
    ///
    /// let mut agent = Agent::new("BANK_A".to_string(), 1000000, 500000);
    /// assert_eq!(agent.credit_used(), 0);
    ///
    /// agent.debit(1200000).unwrap();
    /// assert_eq!(agent.credit_used(), 200000);
    /// ```
    pub fn credit_used(&self) -> i64 {
        if self.balance < 0 {
            self.balance.abs()
        } else {
            0
        }
    }

    // =========================================================================
    // Queue 1 (Internal Bank Queue) Methods - Phase 4
    // =========================================================================

    /// Add transaction to internal outgoing queue (Queue 1)
    ///
    /// # Arguments
    /// * `tx_id` - Transaction ID to queue
    ///
    /// # Example
    /// ```
    /// use payment_simulator_core_rs::Agent;
    ///
    /// let mut agent = Agent::new("BANK_A".to_string(), 1000000, 0);
    /// agent.queue_outgoing("tx_001".to_string());
    /// assert_eq!(agent.outgoing_queue_size(), 1);
    /// ```
    pub fn queue_outgoing(&mut self, tx_id: String) {
        self.outgoing_queue.push(tx_id);
    }

    /// Get reference to outgoing queue (Queue 1)
    ///
    /// # Returns
    /// Slice of transaction IDs in queue
    pub fn outgoing_queue(&self) -> &[String] {
        &self.outgoing_queue
    }

    /// Get size of outgoing queue (Queue 1)
    ///
    /// # Example
    /// ```
    /// use payment_simulator_core_rs::Agent;
    ///
    /// let mut agent = Agent::new("BANK_A".to_string(), 1000000, 0);
    /// assert_eq!(agent.outgoing_queue_size(), 0);
    ///
    /// agent.queue_outgoing("tx_001".to_string());
    /// assert_eq!(agent.outgoing_queue_size(), 1);
    /// ```
    pub fn outgoing_queue_size(&self) -> usize {
        self.outgoing_queue.len()
    }

    /// Remove transaction from outgoing queue (Queue 1)
    ///
    /// Called when cash manager decides to submit transaction to RTGS.
    ///
    /// # Arguments
    /// * `tx_id` - Transaction ID to remove
    ///
    /// # Returns
    /// true if found and removed, false if not in queue
    ///
    /// # Example
    /// ```
    /// use payment_simulator_core_rs::Agent;
    ///
    /// let mut agent = Agent::new("BANK_A".to_string(), 1000000, 0);
    /// agent.queue_outgoing("tx_001".to_string());
    ///
    /// assert!(agent.remove_from_queue("tx_001"));
    /// assert_eq!(agent.outgoing_queue_size(), 0);
    /// assert!(!agent.remove_from_queue("tx_001")); // Already removed
    /// ```
    pub fn remove_from_queue(&mut self, tx_id: &str) -> bool {
        if let Some(pos) = self.outgoing_queue.iter().position(|id| id == tx_id) {
            self.outgoing_queue.remove(pos);
            true
        } else {
            false
        }
    }

    /// Add expected incoming transaction (for forecasting)
    ///
    /// When another bank submits a payment to this agent, the TX ID
    /// should be added here to help with liquidity forecasting.
    ///
    /// # Arguments
    /// * `tx_id` - Transaction ID that will pay this agent
    pub fn add_expected_inflow(&mut self, tx_id: String) {
        self.incoming_expected.push(tx_id);
    }

    /// Get reference to expected incoming transactions
    pub fn incoming_expected(&self) -> &[String] {
        &self.incoming_expected
    }

    /// Remove expected incoming transaction (when it settles)
    ///
    /// # Arguments
    /// * `tx_id` - Transaction ID that settled
    ///
    /// # Returns
    /// true if found and removed
    pub fn remove_expected_inflow(&mut self, tx_id: &str) -> bool {
        if let Some(pos) = self.incoming_expected.iter().position(|id| id == tx_id) {
            self.incoming_expected.remove(pos);
            true
        } else {
            false
        }
    }

    /// Get liquidity buffer setting
    pub fn liquidity_buffer(&self) -> i64 {
        self.liquidity_buffer
    }

    /// Set liquidity buffer (minimum balance to maintain)
    ///
    /// # Arguments
    /// * `buffer` - New buffer amount in cents (must be non-negative)
    ///
    /// # Example
    /// ```
    /// use payment_simulator_core_rs::Agent;
    ///
    /// let mut agent = Agent::new("BANK_A".to_string(), 1000000, 0);
    /// agent.set_liquidity_buffer(100000); // Keep at least $1000
    /// assert_eq!(agent.liquidity_buffer(), 100000);
    /// ```
    pub fn set_liquidity_buffer(&mut self, buffer: i64) {
        assert!(buffer >= 0, "liquidity_buffer must be non-negative");
        self.liquidity_buffer = buffer;
    }

    /// Get last decision tick
    pub fn last_decision_tick(&self) -> Option<usize> {
        self.last_decision_tick
    }

    /// Update last decision tick
    ///
    /// Called by policy evaluation to avoid redundant evaluations
    pub fn update_decision_tick(&mut self, tick: usize) {
        self.last_decision_tick = Some(tick);
    }

    // =========================================================================
    // Policy Query Methods - Phase 4
    // =========================================================================

    /// Check if agent can afford to send amount while maintaining buffer
    ///
    /// Unlike `can_pay()` which only checks absolute liquidity,
    /// this checks if sending would leave at least `liquidity_buffer`.
    ///
    /// # Arguments
    /// * `amount` - Amount to check
    ///
    /// # Returns
    /// true if balance - amount >= liquidity_buffer
    ///
    /// # Example
    /// ```
    /// use payment_simulator_core_rs::Agent;
    ///
    /// let mut agent = Agent::with_buffer("BANK_A".to_string(), 1000000, 0, 100000);
    ///
    /// assert!(agent.can_afford_to_send(800000));  // Would leave 200k (> buffer)
    /// assert!(!agent.can_afford_to_send(950000)); // Would leave 50k (< buffer)
    /// ```
    pub fn can_afford_to_send(&self, amount: i64) -> bool {
        self.balance - amount >= self.liquidity_buffer
    }

    /// Calculate liquidity pressure (0.0 = comfortable, 1.0 = stressed)
    ///
    /// Measures how close the agent is to using all available liquidity.
    /// Used by policies to decide when to hold vs. send transactions.
    ///
    /// # Returns
    /// - 0.0: Has full liquidity available (balance at max)
    /// - 0.5: Using half of available liquidity
    /// - 1.0: At credit limit (maximum stress)
    ///
    /// # Example
    /// ```
    /// use payment_simulator_core_rs::Agent;
    ///
    /// let agent = Agent::new("BANK_A".to_string(), 1000000, 500000);
    /// assert!((agent.liquidity_pressure() - 0.33).abs() < 0.01); // ~33% into available liquidity
    /// ```
    pub fn liquidity_pressure(&self) -> f64 {
        let total_liquidity = (self.balance + self.credit_limit) as f64;
        if total_liquidity == 0.0 {
            return 1.0; // Maximum stress if no liquidity
        }

        // Pressure = how far from max liquidity
        // If balance = 1M, credit = 500k, total = 1.5M
        // Pressure = 1 - (1M / 1.5M) = 0.33 (33% into available liquidity)
        // If balance = 0, pressure = 1 - (0 / 1.5M) = 1.0 (100% stress)
        1.0 - (self.balance.max(0) as f64 / total_liquidity)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    #[should_panic(expected = "credit_limit must be non-negative")]
    fn test_negative_credit_limit_panics() {
        Agent::new("BANK_A".to_string(), 1000000, -500000);
    }
}
