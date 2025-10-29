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

    /// Posted collateral amount (i64 cents) for Phase 8 cost model
    ///
    /// Collateral posted to secure intraday credit facility.
    /// Accrues opportunity cost per tick based on collateral_cost_per_tick_bps.
    /// This is a fixed amount (not dynamic) in Phase 8.
    posted_collateral: i64,
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
            posted_collateral: 0, // Default: no collateral posted
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
            posted_collateral: 0, // Default: no collateral posted
        }
    }

    /// Create agent from snapshot (for checkpoint restoration)
    ///
    /// This constructor allows restoring an agent with all fields
    /// preserved, including queues and state. Used when loading from
    /// a saved checkpoint.
    ///
    /// # Arguments
    /// * `id` - Agent ID
    /// * `balance` - Current balance
    /// * `credit_limit` - Credit limit
    /// * `outgoing_queue` - Queue 1 (internal queue) transaction IDs
    /// * `incoming_expected` - Expected incoming transaction IDs
    /// * `last_decision_tick` - Last tick policy was evaluated
    /// * `liquidity_buffer` - Target minimum balance
    /// * `posted_collateral` - Amount of collateral posted
    ///
    /// # Example
    /// ```
    /// use payment_simulator_core_rs::Agent;
    ///
    /// let agent = Agent::from_snapshot(
    ///     "BANK_A".to_string(),
    ///     1_000_000,
    ///     500_000,
    ///     vec!["tx_1".to_string()],
    ///     vec![],
    ///     Some(42),
    ///     100_000,
    ///     0,
    /// );
    /// ```
    pub fn from_snapshot(
        id: String,
        balance: i64,
        credit_limit: i64,
        outgoing_queue: Vec<String>,
        incoming_expected: Vec<String>,
        last_decision_tick: Option<usize>,
        liquidity_buffer: i64,
        posted_collateral: i64,
    ) -> Self {
        Self {
            id,
            balance,
            credit_limit,
            outgoing_queue,
            incoming_expected,
            last_decision_tick,
            liquidity_buffer,
            posted_collateral,
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

    /// Calculate available liquidity (balance + credit + posted collateral)
    ///
    /// Available liquidity = balance + credit_limit + posted_collateral
    ///
    /// This formula works for both positive and negative balances:
    /// - Positive balance: Full reserves + credit facility + collateral
    /// - Negative balance: Remaining credit + collateral after current usage
    ///
    /// # Example
    /// ```
    /// use payment_simulator_core_rs::Agent;
    ///
    /// let mut agent = Agent::new("BANK_A".to_string(), 1000000, 500000);
    /// assert_eq!(agent.available_liquidity(), 1500000); // 1M + 500k
    ///
    /// agent.set_posted_collateral(200000); // Post $2,000 collateral
    /// assert_eq!(agent.available_liquidity(), 1700000); // 1M + 500k + 200k
    ///
    /// agent.debit(1200000).unwrap(); // Use overdraft
    /// // Balance = -200k, available = -200k + 500k + 200k = 500k
    /// assert_eq!(agent.available_liquidity(), 500000);
    /// ```
    pub fn available_liquidity(&self) -> i64 {
        self.balance + self.credit_limit + self.posted_collateral
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

    /// Get posted collateral amount (Phase 8)
    ///
    /// Returns the amount of collateral posted to secure intraday credit.
    /// Accrues opportunity cost per tick.
    pub fn posted_collateral(&self) -> i64 {
        self.posted_collateral
    }

    /// Set posted collateral amount (Phase 8)
    ///
    /// # Arguments
    /// * `collateral` - Collateral amount in cents (must be non-negative)
    ///
    /// # Example
    /// ```
    /// use payment_simulator_core_rs::Agent;
    ///
    /// let mut agent = Agent::new("BANK_A".to_string(), 1000000, 500000);
    /// agent.set_posted_collateral(200000); // Post $2000 collateral
    /// assert_eq!(agent.posted_collateral(), 200000);
    /// ```
    pub fn set_posted_collateral(&mut self, collateral: i64) {
        assert!(collateral >= 0, "posted_collateral must be non-negative");
        self.posted_collateral = collateral;
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
        let total_liquidity = (self.balance + self.credit_limit + self.posted_collateral) as f64;
        if total_liquidity == 0.0 {
            return 1.0; // Maximum stress if no liquidity
        }

        // Pressure = how far from max liquidity
        // If balance = 1M, credit = 500k, collateral = 200k, total = 1.7M
        // Pressure = 1 - (1M / 1.7M) = 0.41 (41% into available liquidity)
        // If balance = 0, pressure = 1 - (0 / 1.7M) = 1.0 (100% stress)
        1.0 - (self.balance.max(0) as f64 / total_liquidity)
    }

    // =========================================================================
    // Collateral Management Helper Methods - Phase 8+
    // =========================================================================

    /// Calculate maximum collateral capacity
    ///
    /// Returns the theoretical maximum amount of collateral the agent could post.
    /// Uses a heuristic of 10x the credit limit (configurable in future).
    ///
    /// This represents the agent's total collateralizable assets.
    ///
    /// # Returns
    /// Maximum collateral capacity in cents
    ///
    /// # Example
    /// ```
    /// use payment_simulator_core_rs::Agent;
    ///
    /// let agent = Agent::new("BANK_A".to_string(), 1000000, 500000);
    /// // Max capacity = 10 × credit limit = 10 × 500k = 5M
    /// assert_eq!(agent.max_collateral_capacity(), 5_000_000);
    /// ```
    pub fn max_collateral_capacity(&self) -> i64 {
        // Heuristic: 10x credit limit
        // Rationale: If bank can borrow 500k intraday, they likely have
        // ~5M in collateralizable assets (bonds, reserves, etc.)
        self.credit_limit * 10
    }

    /// Calculate remaining collateral capacity
    ///
    /// Returns how much additional collateral the agent can post.
    ///
    /// # Returns
    /// Remaining capacity = max_capacity - posted_collateral
    ///
    /// # Example
    /// ```
    /// use payment_simulator_core_rs::Agent;
    ///
    /// let mut agent = Agent::new("BANK_A".to_string(), 1000000, 500000);
    /// assert_eq!(agent.remaining_collateral_capacity(), 5_000_000); // Full capacity
    ///
    /// agent.set_posted_collateral(1_000_000); // Post $10,000
    /// assert_eq!(agent.remaining_collateral_capacity(), 4_000_000); // 4M remaining
    /// ```
    pub fn remaining_collateral_capacity(&self) -> i64 {
        self.max_collateral_capacity() - self.posted_collateral
    }

    /// Calculate Queue 1 liquidity gap
    ///
    /// Returns how much additional liquidity is needed to settle all pending
    /// transactions in the agent's internal queue (Queue 1).
    ///
    /// # Arguments
    ///
    /// * `state` - Simulation state (needed to look up transaction amounts)
    ///
    /// # Returns
    ///
    /// - 0 if all Queue 1 transactions can be settled with current liquidity
    /// - Positive value indicating shortfall amount (cents)
    ///
    /// # Example
    ///
    /// ```ignore
    /// // Agent has 100k balance + 50k credit = 150k available
    /// // Queue 1 has transactions totaling 200k
    /// // Gap = 200k - 150k = 50k shortfall
    /// let gap = agent.queue1_liquidity_gap(&state);
    /// assert_eq!(gap, 50_000);
    /// ```
    pub fn queue1_liquidity_gap(&self, state: &crate::models::state::SimulationState) -> i64 {
        // Sum up all pending Queue 1 transaction amounts
        let mut total_pending = 0i64;

        for tx_id in self.outgoing_queue() {
            if let Some(tx) = state.get_transaction(tx_id) {
                total_pending += tx.remaining_amount();
            }
        }

        // Gap = total pending - available liquidity
        // If negative, there's no gap (surplus liquidity)
        (total_pending - self.available_liquidity()).max(0)
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::models::state::SimulationState;
    use crate::models::Transaction;

    #[test]
    #[should_panic(expected = "credit_limit must be non-negative")]
    fn test_negative_credit_limit_panics() {
        Agent::new("BANK_A".to_string(), 1000000, -500000);
    }

    // =========================================================================
    // Collateral Management Tests - Phase 8+
    // =========================================================================

    #[test]
    fn test_available_liquidity_includes_collateral() {
        let mut agent = Agent::new("BANK_A".to_string(), 1_000_000, 500_000);

        // Initially: balance + credit = 1M + 500k = 1.5M
        assert_eq!(agent.available_liquidity(), 1_500_000);

        // Post collateral
        agent.set_posted_collateral(200_000);

        // Now: balance + credit + collateral = 1M + 500k + 200k = 1.7M
        assert_eq!(agent.available_liquidity(), 1_700_000);
    }

    #[test]
    fn test_available_liquidity_with_negative_balance_and_collateral() {
        let mut agent = Agent::new("BANK_A".to_string(), 1_000_000, 500_000);
        agent.set_posted_collateral(200_000);

        // Use overdraft
        agent.debit(1_200_000).unwrap();

        // Balance = -200k
        // Available = -200k + 500k + 200k = 500k
        assert_eq!(agent.balance(), -200_000);
        assert_eq!(agent.available_liquidity(), 500_000);
    }

    #[test]
    fn test_max_collateral_capacity() {
        let agent = Agent::new("BANK_A".to_string(), 1_000_000, 500_000);

        // Max capacity = 10x credit limit
        assert_eq!(agent.max_collateral_capacity(), 5_000_000);
    }

    #[test]
    fn test_remaining_collateral_capacity() {
        let mut agent = Agent::new("BANK_A".to_string(), 1_000_000, 500_000);

        // Initially: full capacity available
        assert_eq!(agent.remaining_collateral_capacity(), 5_000_000);

        // Post some collateral
        agent.set_posted_collateral(1_000_000);

        // Remaining: 5M - 1M = 4M
        assert_eq!(agent.remaining_collateral_capacity(), 4_000_000);

        // Post more collateral
        agent.set_posted_collateral(3_000_000);

        // Remaining: 5M - 3M = 2M
        assert_eq!(agent.remaining_collateral_capacity(), 2_000_000);
    }

    #[test]
    fn test_queue1_liquidity_gap_no_gap() {
        let mut agent = Agent::new("BANK_A".to_string(), 1_000_000, 500_000);
        let mut state = SimulationState::new(vec![agent.clone()]);

        // Agent has 1.5M available liquidity
        // Queue 1 is empty
        let gap = agent.queue1_liquidity_gap(&state);
        assert_eq!(gap, 0);
    }

    #[test]
    fn test_queue1_liquidity_gap_with_transactions() {
        let mut agent = Agent::new("BANK_A".to_string(), 500_000, 300_000);
        let mut state = SimulationState::new(vec![
            agent.clone(),
            Agent::new("BANK_B".to_string(), 1_000_000, 0),
        ]);

        // Create transactions and add to Queue 1
        let tx1 = Transaction::new(
            "BANK_A".to_string(),
            "BANK_B".to_string(),
            400_000,
            0,  // arrival
            100, // deadline
        );
        let tx2 = Transaction::new(
            "BANK_A".to_string(),
            "BANK_B".to_string(),
            600_000,
            0,
            100,
        );

        let tx1_id = tx1.id().to_string();
        let tx2_id = tx2.id().to_string();

        state.add_transaction(tx1);
        state.add_transaction(tx2);

        agent.queue_outgoing(tx1_id);
        agent.queue_outgoing(tx2_id);

        // Available liquidity: 500k + 300k = 800k
        // Total pending: 400k + 600k = 1M
        // Gap: 1M - 800k = 200k
        let gap = agent.queue1_liquidity_gap(&state);
        assert_eq!(gap, 200_000);
    }

    #[test]
    fn test_queue1_liquidity_gap_with_collateral() {
        let mut agent = Agent::new("BANK_A".to_string(), 500_000, 300_000);
        agent.set_posted_collateral(200_000); // Add collateral

        let mut state = SimulationState::new(vec![
            agent.clone(),
            Agent::new("BANK_B".to_string(), 1_000_000, 0),
        ]);

        // Create transaction
        let tx = Transaction::new(
            "BANK_A".to_string(),
            "BANK_B".to_string(),
            900_000,
            0,
            100,
        );

        let tx_id = tx.id().to_string();
        state.add_transaction(tx);
        agent.queue_outgoing(tx_id);

        // Available liquidity: 500k + 300k + 200k = 1M
        // Total pending: 900k
        // Gap: max(0, 900k - 1M) = 0 (no gap!)
        let gap = agent.queue1_liquidity_gap(&state);
        assert_eq!(gap, 0);
    }

    #[test]
    fn test_liquidity_pressure_with_collateral() {
        let mut agent = Agent::new("BANK_A".to_string(), 1_000_000, 500_000);
        agent.set_posted_collateral(200_000);

        // Total liquidity: 1M + 500k + 200k = 1.7M
        // Pressure = 1 - (1M / 1.7M) ≈ 0.41
        let pressure = agent.liquidity_pressure();
        assert!((pressure - 0.41).abs() < 0.02);
    }

    #[test]
    fn test_can_pay_with_collateral() {
        let mut agent = Agent::new("BANK_A".to_string(), 500_000, 300_000);
        agent.set_posted_collateral(400_000);

        // Available: 500k + 300k + 400k = 1.2M
        assert!(agent.can_pay(1_000_000));
        assert!(agent.can_pay(1_200_000));
        assert!(!agent.can_pay(1_300_000)); // Exceeds available
    }

    #[test]
    fn test_collateral_post_and_withdraw_cycle() {
        let mut agent = Agent::new("BANK_A".to_string(), 1_000_000, 500_000);

        // Initial state
        assert_eq!(agent.posted_collateral(), 0);
        assert_eq!(agent.available_liquidity(), 1_500_000);

        // Post collateral
        agent.set_posted_collateral(300_000);
        assert_eq!(agent.posted_collateral(), 300_000);
        assert_eq!(agent.available_liquidity(), 1_800_000);

        // Post more
        agent.set_posted_collateral(800_000);
        assert_eq!(agent.posted_collateral(), 800_000);
        assert_eq!(agent.available_liquidity(), 2_300_000);

        // Withdraw
        agent.set_posted_collateral(200_000);
        assert_eq!(agent.posted_collateral(), 200_000);
        assert_eq!(agent.available_liquidity(), 1_700_000);

        // Withdraw all
        agent.set_posted_collateral(0);
        assert_eq!(agent.posted_collateral(), 0);
        assert_eq!(agent.available_liquidity(), 1_500_000);
    }
}
