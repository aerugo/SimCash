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

/// Errors that can occur during collateral withdrawal operations
#[derive(Debug, Error, PartialEq)]
pub enum WithdrawError {
    #[error("Withdrawal amount must be positive")]
    NonPositive,

    #[error("Minimum holding period not met: {ticks_remaining} tick(s) remaining (posted at tick {posted_at_tick})")]
    MinHoldingPeriodNotMet {
        ticks_remaining: usize,
        posted_at_tick: usize,
    },

    #[error("No headroom available for withdrawal: credit_used={credit_used}, allowed_limit={allowed_limit}, headroom={headroom}")]
    NoHeadroom {
        credit_used: i64,
        allowed_limit: i64,
        headroom: i64,
    },
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
/// let mut agent = Agent::new("BANK_A".to_string(), 1000000);
/// agent.set_unsecured_cap(500000);
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

    /// Collateral haircut (discount rate) - defaults to 0.02 (2%)
    ///
    /// The discount applied to collateral value for credit capacity calculation.
    /// Example: haircut of 0.02 (2%) means $100K collateral provides $98K of headroom.
    /// This accounts for valuation risk of the collateral assets.
    ///
    /// **IMPORTANT**: This is the HAIRCUT (discount), not the retention factor.
    /// - 0.00 = 0% haircut → 100% of collateral value counts (high-quality bonds)
    /// - 0.02 = 2% haircut → 98% of collateral value counts (typical T2/CLM)
    /// - 0.10 = 10% haircut → 90% of collateral value counts (lower quality)
    collateral_haircut: f64,

    /// Unsecured daylight overdraft cap (i64 cents) - defaults to 0
    ///
    /// Optional unsecured intraday credit limit separate from collateralized capacity.
    /// Allows limited overdraft without posting collateral, typically priced higher.
    /// Example: $20K unsecured cap allows small overdrafts for operational flexibility.
    ///
    /// Total allowed overdraft = floor(posted_collateral × (1 - haircut)) + unsecured_cap
    unsecured_cap: i64,

    /// Tick when collateral was last posted (for minimum holding period)
    ///
    /// Used to enforce minimum holding period (default 5 ticks) to prevent
    /// oscillation (posting and immediately withdrawing collateral).
    /// None if no collateral is currently posted.
    collateral_posted_at_tick: Option<usize>,

    // Phase 3.3: Bank-Level Budget State (Policy Enhancements V2)
    /// Maximum release budget set for current tick (i64 cents)
    /// None if no budget has been set (unlimited releases)
    release_budget_max: Option<i64>,

    /// Remaining release budget for current tick (i64 cents)
    release_budget_remaining: i64,

    /// Focus list: allowed counterparties for releases this tick
    /// None means all counterparties allowed
    /// Some(vec![]) means no counterparties allowed (blocks all)
    release_budget_focus_counterparties: Option<Vec<String>>,

    /// Maximum amount per counterparty this tick (i64 cents)
    /// None means unlimited per counterparty
    release_budget_per_counterparty_limit: Option<i64>,

    /// Per-counterparty usage tracking for current tick
    /// Maps counterparty_id -> total_released_amount
    release_budget_per_counterparty_usage: std::collections::HashMap<String, i64>,

    // Phase 3.4: Collateral Auto-Withdraw Timers (Policy Enhancements V2)
    /// Scheduled automatic collateral withdrawals
    /// Maps tick_number -> Vec<(amount, reason, posted_at_tick)>
    /// When tick is reached, collateral is automatically withdrawn
    collateral_withdrawal_timers: std::collections::HashMap<usize, Vec<(i64, String, usize)>>,

    // Phase 4.5: Stateful Micro-Memory (Policy Enhancements V2)
    /// State registers for policy micro-memory (max 10 per agent)
    /// Keys MUST be prefixed with "bank_state_"
    /// Values are f64 for flexibility
    /// Reset at EOD for daily scope (not multi-day strategies)
    state_registers: std::collections::HashMap<String, f64>,
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
    /// let agent = Agent::new("BANK_A".to_string(), 1000000);
    /// assert_eq!(agent.balance(), 1000000);
    /// ```
    pub fn new(id: String, balance: i64) -> Self {
        Self {
            id,
            balance,
            outgoing_queue: Vec::new(),
            incoming_expected: Vec::new(),
            last_decision_tick: None,
            liquidity_buffer: 0,  // Default: no buffer requirement
            posted_collateral: 0, // Default: no collateral posted
            collateral_haircut: 0.02, // Default: 2% haircut (typical T2/CLM)
            unsecured_cap: 0, // Default: no unsecured overdraft capacity
            collateral_posted_at_tick: None, // No collateral posted initially
            // Phase 3.3: Budget state (unlimited by default)
            release_budget_max: None,
            release_budget_remaining: i64::MAX, // Unlimited initially
            release_budget_focus_counterparties: None,
            release_budget_per_counterparty_limit: None,
            release_budget_per_counterparty_usage: std::collections::HashMap::new(),
            // Phase 3.4: Collateral timers (none by default)
            collateral_withdrawal_timers: std::collections::HashMap::new(),
            // Phase 4.5: State registers (none by default)
            state_registers: std::collections::HashMap::new(),
        }
    }

    /// Create a new agent with specified liquidity buffer
    ///
    /// # Arguments
    /// * `id` - Unique identifier
    /// * `balance` - Opening balance in cents
    /// * `liquidity_buffer` - Minimum balance to maintain in cents
    ///
    /// # Example
    /// ```
    /// use payment_simulator_core_rs::Agent;
    ///
    /// // Bank wants to keep at least $1000 as buffer
    /// let agent = Agent::with_buffer("BANK_A".to_string(), 1000000, 100000);
    /// assert_eq!(agent.liquidity_buffer(), 100000);
    /// ```
    pub fn with_buffer(id: String, balance: i64, liquidity_buffer: i64) -> Self {
        assert!(
            liquidity_buffer >= 0,
            "liquidity_buffer must be non-negative"
        );
        Self {
            id,
            balance,
            outgoing_queue: Vec::new(),
            incoming_expected: Vec::new(),
            last_decision_tick: None,
            liquidity_buffer,
            posted_collateral: 0, // Default: no collateral posted
            collateral_haircut: 0.02, // Default: 2% haircut
            unsecured_cap: 0, // Default: no unsecured capacity
            collateral_posted_at_tick: None, // Not yet posted
            // Phase 3.3: Budget state (unlimited by default)
            release_budget_max: None,
            release_budget_remaining: i64::MAX,
            release_budget_focus_counterparties: None,
            release_budget_per_counterparty_limit: None,
            release_budget_per_counterparty_usage: std::collections::HashMap::new(),
            // Phase 3.4: Collateral timers (none by default)
            collateral_withdrawal_timers: std::collections::HashMap::new(),
            // Phase 4.5: State registers (none by default)
            state_registers: std::collections::HashMap::new(),
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
    /// * `unsecured_cap` - Unsecured overdraft capacity
    /// * `outgoing_queue` - Queue 1 (internal queue) transaction IDs
    /// * `incoming_expected` - Expected incoming transaction IDs
    /// * `last_decision_tick` - Last tick policy was evaluated
    /// * `liquidity_buffer` - Target minimum balance
    /// * `posted_collateral` - Amount of collateral posted
    /// * `collateral_haircut` - Collateral discount factor (0.0 to 1.0)
    /// * `collateral_posted_at_tick` - Tick when collateral was last posted
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
    ///     0.02,
    ///     None,
    /// );
    /// ```
    pub fn from_snapshot(
        id: String,
        balance: i64,
        unsecured_cap: i64,
        outgoing_queue: Vec<String>,
        incoming_expected: Vec<String>,
        last_decision_tick: Option<usize>,
        liquidity_buffer: i64,
        posted_collateral: i64,
        collateral_haircut: f64,
        collateral_posted_at_tick: Option<usize>,
    ) -> Self {
        Self {
            id,
            balance,
            outgoing_queue,
            incoming_expected,
            last_decision_tick,
            liquidity_buffer,
            posted_collateral,
            collateral_haircut,
            unsecured_cap,
            collateral_posted_at_tick,
            // Phase 3.3: Budget state (unlimited by default)
            release_budget_max: None,
            release_budget_remaining: i64::MAX,
            release_budget_focus_counterparties: None,
            release_budget_per_counterparty_limit: None,
            release_budget_per_counterparty_usage: std::collections::HashMap::new(),
            // Phase 3.4: Collateral timers (none by default)
            collateral_withdrawal_timers: std::collections::HashMap::new(),
            // Phase 4.5: State registers (none by default)
            state_registers: std::collections::HashMap::new(),
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
    /// let agent = Agent::new("BANK_A".to_string(), 1000000);
    /// assert_eq!(agent.balance(), 1000000);
    /// ```
    pub fn balance(&self) -> i64 {
        self.balance
    }

    /// Get amount of credit currently in use
    ///
    /// Returns the absolute value of negative balance (amount below zero).
    /// If balance is positive, credit used is 0.
    ///
    /// # Example
    /// ```
    /// use payment_simulator_core_rs::Agent;
    ///
    /// let mut agent = Agent::new("BANK_A".to_string(), -50000);
    /// agent.set_unsecured_cap(100000);
    /// assert_eq!(agent.credit_used(), 50000); // Using $500 of credit
    ///
    /// let mut agent2 = Agent::new("BANK_B".to_string(), 100000);
    /// agent2.set_unsecured_cap(50000);
    /// assert_eq!(agent2.credit_used(), 0); // Positive balance, no credit used
    /// ```
    pub fn credit_used(&self) -> i64 {
        (-self.balance).max(0)
    }

    /// Calculate allowed overdraft limit based on collateral and unsecured cap
    ///
    /// This is the maximum negative balance the agent can have, derived from:
    /// - Posted collateral (discounted by haircut)
    /// - Unsecured daylight cap (if any)
    ///
    /// Formula:
    /// ```text
    /// allowed_overdraft_limit = floor(posted_collateral × (1 - haircut)) + unsecured_cap
    /// ```
    ///
    /// # Example
    /// ```
    /// use payment_simulator_core_rs::Agent;
    ///
    /// let mut agent = Agent::new("BANK_A".to_string(), 0);
    /// agent.set_posted_collateral(100_000_00); // $100k
    /// agent.set_collateral_haircut(0.10); // 10% haircut
    /// agent.set_unsecured_cap(20_000_00); // $20k unsecured
    ///
    /// // Collateralized: 100k × 0.9 = 90k
    /// // Total: 90k + 20k = 110k
    /// assert_eq!(agent.allowed_overdraft_limit(), 110_000_00);
    /// ```
    pub fn allowed_overdraft_limit(&self) -> i64 {
        let one_minus_haircut = (1.0 - self.collateral_haircut).max(0.0);
        let collateral_capacity = (self.posted_collateral as f64 * one_minus_haircut).floor() as i64;
        collateral_capacity + self.unsecured_cap
    }

    /// Calculate current overdraft headroom
    ///
    /// Headroom is the amount of additional credit the agent can use before
    /// hitting their allowed overdraft limit.
    ///
    /// Formula:
    /// ```text
    /// headroom = allowed_overdraft_limit - credit_used
    /// ```
    ///
    /// A negative headroom indicates a violation of Invariant I1 (should never occur).
    ///
    /// # Example
    /// ```
    /// use payment_simulator_core_rs::Agent;
    ///
    /// let mut agent = Agent::new("BANK_A".to_string(), -60_000_00);
    /// agent.set_posted_collateral(100_000_00);
    /// agent.set_collateral_haircut(0.10);
    ///
    /// // credit_used = 60k
    /// // allowed_limit = 90k (100k × 0.9)
    /// // headroom = 30k
    /// assert_eq!(agent.headroom(), 30_000_00);
    /// ```
    pub fn headroom(&self) -> i64 {
        self.allowed_overdraft_limit() - self.credit_used()
    }

    /// Calculate maximum collateral that can be safely withdrawn
    ///
    /// Returns the maximum amount of collateral that can be withdrawn while:
    /// 1. Maintaining allowed_overdraft_limit ≥ credit_used + buffer
    /// 2. Not going negative on posted collateral
    ///
    /// Formula:
    /// ```text
    /// required_collateral = ceil((credit_used + buffer - unsecured_cap) / (1 - haircut))
    /// max_withdrawable = max(0, posted_collateral - required_collateral)
    /// ```
    ///
    /// # Arguments
    /// * `buffer` - Safety buffer to maintain (cents)
    ///
    /// # Returns
    /// Maximum withdrawable amount in cents (0 if none can be withdrawn)
    ///
    /// # Example
    /// ```
    /// use payment_simulator_core_rs::Agent;
    ///
    /// let mut agent = Agent::new("BANK_A".to_string(), -60_000_00);
    /// agent.set_posted_collateral(100_000_00);
    /// agent.set_collateral_haircut(0.10);
    ///
    /// // credit_used = 60k
    /// // Need: C × 0.9 ≥ 60k → C ≥ 66,667
    /// // Can withdraw: 100k - 66,667 ≈ 33,333
    /// let max_w = agent.max_withdrawable_collateral(0);
    /// assert!(max_w >= 33_333_00 && max_w <= 33_334_00);
    /// ```
    pub fn max_withdrawable_collateral(&self, buffer: i64) -> i64 {
        let one_minus_haircut = (1.0 - self.collateral_haircut).max(0.0);

        // Edge case: 100% haircut means collateral provides no capacity
        if one_minus_haircut <= 0.0 {
            // Can withdraw all since it's not backing anything
            return self.posted_collateral;
        }

        // Calculate required collateral to maintain: allowed_limit ≥ credit_used + buffer
        // Need: C × (1 - h) + unsecured_cap ≥ credit_used + buffer
        // Therefore: C ≥ (credit_used + buffer - unsecured_cap) / (1 - h)
        let credit_used = self.credit_used();
        let target_limit = credit_used + buffer;
        let unsecured_contribution = self.unsecured_cap.min(target_limit); // Can't use more than needed

        let required_from_collateral = target_limit.saturating_sub(unsecured_contribution);
        let required_collateral_f = required_from_collateral as f64 / one_minus_haircut;
        let required_collateral = required_collateral_f.ceil() as i64;

        // Max withdrawable is the excess
        (self.posted_collateral - required_collateral).max(0)
    }

    /// Calculate available liquidity with collateral haircut
    ///
    /// Formula:
    /// ```text
    /// available_liquidity = max(0, balance) + max(0, headroom - credit_used)
    ///
    /// where:
    ///   headroom = credit_limit + floor(posted_collateral × (1 - haircut)) + unsecured_cap
    ///   credit_used = max(0, -balance)  // Amount of credit currently in use
    /// ```
    ///
    /// This accounts for:
    /// - Positive balance contributes directly to liquidity
    /// - Negative balance means credit is in use, reducing available headroom
    /// - Posted collateral adds to headroom, discounted by haircut (e.g., 2% haircut → 98% value)
    /// - Unsecured cap provides additional overdraft capacity
    ///
    /// # Example
    /// ```
    /// use payment_simulator_core_rs::Agent;
    ///
    /// // Scenario 1: Positive balance
    /// let mut agent = Agent::new("BANK_A".to_string(), 1000000);
    /// agent.set_unsecured_cap(500000);
    /// // available = 1000000 + (500000 + 0 + 0 - 0) = 1,500,000
    /// assert_eq!(agent.available_liquidity(), 1500000);
    ///
    /// // Scenario 2: Overdraft with collateral (2% haircut)
    /// let mut agent2 = Agent::new("BANK_B".to_string(), -50000);
    /// agent2.set_unsecured_cap(60000);
    /// agent2.set_posted_collateral(100000); // Post $1000 collateral
    /// agent2.set_collateral_haircut(0.02); // 2% haircut
    /// // credit_used = 50000, collateral_value = 100000 × 0.98 = 98000
    /// // headroom = 60000 + 98000 + 0 = 158000
    /// // available = 0 + (158000 - 50000) = 108,000
    /// assert_eq!(agent2.available_liquidity(), 108000);
    /// ```
    pub fn available_liquidity(&self) -> i64 {
        // Calculate usable funds from positive balance
        let balance_liquidity = self.balance.max(0);

        // Calculate credit in use (negative balance means using credit)
        let credit_used = (-self.balance).max(0);

        // Calculate total headroom with collateral (discounted by haircut)
        // haircut is now the discount rate, so use (1 - haircut)
        let one_minus_haircut = (1.0 - self.collateral_haircut).max(0.0);
        let collateral_headroom = (self.posted_collateral as f64 * one_minus_haircut).floor() as i64;

        // Total overdraft headroom = unsecured + collateralized
        let unsecured_headroom = self.unsecured_cap;
        let total_headroom = unsecured_headroom + collateral_headroom;

        // Available headroom is what's left after subtracting credit in use
        let available_headroom = (total_headroom - credit_used).max(0);

        balance_liquidity + available_headroom
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
    /// let mut agent = Agent::new("BANK_A".to_string(), 1000000);
    /// agent.set_unsecured_cap(500000);
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
    /// let mut agent = Agent::new("BANK_A".to_string(), 1000000);
    /// agent.set_unsecured_cap(500000);
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
    /// let mut agent = Agent::new("BANK_A".to_string(), 1000000);
    /// agent.set_unsecured_cap(500000);
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
    /// let mut agent = Agent::new("BANK_A".to_string(), 1000000);
    /// agent.set_unsecured_cap(500000);
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
    /// let mut agent = Agent::new("BANK_A".to_string(), 1000000);
    /// agent.set_unsecured_cap(500000);
    /// assert!(!agent.is_using_credit());
    ///
    /// agent.debit(1200000).unwrap();
    /// assert!(agent.is_using_credit());
    /// ```
    pub fn is_using_credit(&self) -> bool {
        self.balance < 0
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
    /// let mut agent = Agent::new("BANK_A".to_string(), 1000000);
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
    /// let mut agent = Agent::new("BANK_A".to_string(), 1000000);
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
    /// let mut agent = Agent::new("BANK_A".to_string(), 1000000);
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

    /// Replace the entire outgoing queue with a new sorted list
    ///
    /// Used by the orchestrator to apply queue ordering (priority/deadline sorting).
    /// This replaces the queue contents while preserving any other agent state.
    ///
    /// # Arguments
    /// * `new_queue` - New ordered list of transaction IDs
    ///
    /// # Example
    /// ```
    /// use payment_simulator_core_rs::Agent;
    ///
    /// let mut agent = Agent::new("BANK_A".to_string(), 1000000);
    /// agent.queue_outgoing("tx_001".to_string());
    /// agent.queue_outgoing("tx_002".to_string());
    ///
    /// // Reorder: tx_002 before tx_001
    /// agent.replace_outgoing_queue(vec!["tx_002".to_string(), "tx_001".to_string()]);
    ///
    /// assert_eq!(agent.outgoing_queue()[0], "tx_002");
    /// assert_eq!(agent.outgoing_queue()[1], "tx_001");
    /// ```
    pub fn replace_outgoing_queue(&mut self, new_queue: Vec<String>) {
        self.outgoing_queue = new_queue;
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
    /// let mut agent = Agent::new("BANK_A".to_string(), 1000000);
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
    /// let mut agent = Agent::new("BANK_A".to_string(), 1000000);
    /// agent.set_unsecured_cap(500000);
    /// agent.set_posted_collateral(200000); // Post $2000 collateral
    /// assert_eq!(agent.posted_collateral(), 200000);
    /// ```
    pub fn set_posted_collateral(&mut self, collateral: i64) {
        assert!(collateral >= 0, "posted_collateral must be non-negative");
        self.posted_collateral = collateral;
    }

    /// Set collateral haircut (discount rate)
    ///
    /// # Arguments
    /// * `haircut` - Discount rate (0.0 to 1.0)
    ///   - 0.00 = 0% haircut (100% of value counts)
    ///   - 0.02 = 2% haircut (98% of value counts, typical T2/CLM)
    ///   - 0.10 = 10% haircut (90% of value counts)
    ///
    /// # Panics
    /// Panics if haircut is not in range [0.0, 1.0]
    pub fn set_collateral_haircut(&mut self, haircut: f64) {
        assert!((0.0..=1.0).contains(&haircut), "collateral_haircut must be between 0.0 and 1.0");
        self.collateral_haircut = haircut;
    }

    /// Get collateral haircut (discount rate)
    pub fn collateral_haircut(&self) -> f64 {
        self.collateral_haircut
    }

    /// Set unsecured daylight overdraft cap
    ///
    /// # Arguments
    /// * `cap` - Unsecured overdraft capacity in cents (must be non-negative)
    ///
    /// # Example
    /// ```
    /// use payment_simulator_core_rs::Agent;
    ///
    /// let mut agent = Agent::new("BANK_A".to_string(), 100_000);
    /// agent.set_unsecured_cap(20_000_00); // $20k unsecured cap
    /// assert_eq!(agent.unsecured_cap(), 20_000_00);
    /// ```
    pub fn set_unsecured_cap(&mut self, cap: i64) {
        assert!(cap >= 0, "unsecured_cap must be non-negative");
        self.unsecured_cap = cap;
    }

    /// Get unsecured daylight overdraft cap
    pub fn unsecured_cap(&self) -> i64 {
        self.unsecured_cap
    }

    /// Set the tick when collateral was posted (for minimum holding period)
    pub fn set_collateral_posted_at_tick(&mut self, tick: usize) {
        self.collateral_posted_at_tick = Some(tick);
    }

    /// Get the tick when collateral was posted
    pub fn collateral_posted_at_tick(&self) -> Option<usize> {
        self.collateral_posted_at_tick
    }

    /// Check if collateral can be withdrawn (minimum holding period elapsed)
    ///
    /// # Arguments
    /// * `current_tick` - Current simulation tick
    /// * `min_holding_ticks` - Minimum ticks to hold collateral (default: 5)
    ///
    /// # Returns
    /// true if collateral can be withdrawn, false if still in holding period
    pub fn can_withdraw_collateral(&self, current_tick: usize, min_holding_ticks: usize) -> bool {
        match self.collateral_posted_at_tick {
            None => true, // No collateral posted, withdrawal N/A but return true for flexibility
            Some(posted_tick) => current_tick >= posted_tick + min_holding_ticks,
        }
    }

    /// Attempt to withdraw collateral with full guard checks (Invariant I2 enforcement)
    ///
    /// This is the **single source of truth** for all collateral withdrawals.
    /// Both timer-based and manual/policy withdrawals MUST use this method to
    /// ensure Invariant I2 is never violated.
    ///
    /// # Enforces
    /// 1. Minimum holding period (if posted_at_tick is set)
    /// 2. Invariant I2: Withdrawal headroom protection
    /// 3. Non-negative collateral
    ///
    /// # Arguments
    /// * `requested` - Requested withdrawal amount (cents)
    /// * `current_tick` - Current simulation tick
    /// * `min_holding_ticks` - Minimum ticks to hold (default 5)
    /// * `safety_buffer` - Additional headroom buffer (cents, default 100)
    ///
    /// # Returns
    /// * `Ok(actual)` - Actual amount withdrawn (may be less than requested if clamped)
    /// * `Err(WithdrawError)` - Withdrawal blocked with reason
    ///
    /// # Invariant Guarantee
    /// After successful withdrawal:
    /// ```text
    /// floor((posted_collateral - actual) × (1 - haircut)) + unsecured_cap ≥ credit_used + buffer
    /// ```
    ///
    /// # Example
    /// ```
    /// use payment_simulator_core_rs::Agent;
    ///
    /// let mut agent = Agent::new("BANK_A".to_string(), -60_000_00);
    /// agent.set_posted_collateral(100_000_00);
    /// agent.set_collateral_haircut(0.10);
    /// agent.set_collateral_posted_at_tick(5);
    ///
    /// // Try to withdraw at tick 10 (5 ticks after posting)
    /// match agent.try_withdraw_collateral_guarded(80_000_00, 10, 5, 100) {
    ///     Ok(actual) => println!("Withdrew: ${}", actual / 100),
    ///     Err(e) => println!("Blocked: {}", e),
    /// }
    /// ```
    pub fn try_withdraw_collateral_guarded(
        &mut self,
        requested: i64,
        current_tick: usize,
        min_holding_ticks: usize,
        safety_buffer: i64,
    ) -> Result<i64, WithdrawError> {
        // Validation 1: Positive amount
        if requested <= 0 {
            return Err(WithdrawError::NonPositive);
        }

        // Validation 2: Minimum holding period
        if !self.can_withdraw_collateral(current_tick, min_holding_ticks) {
            let posted_at = self.collateral_posted_at_tick.unwrap_or(0);
            let ticks_held = current_tick.saturating_sub(posted_at);
            let ticks_remaining = min_holding_ticks.saturating_sub(ticks_held);
            return Err(WithdrawError::MinHoldingPeriodNotMet {
                ticks_remaining,
                posted_at_tick: posted_at,
            });
        }

        // Validation 3: Headroom protection (Invariant I2)
        let max_safe = self.max_withdrawable_collateral(safety_buffer);
        if max_safe <= 0 {
            return Err(WithdrawError::NoHeadroom {
                credit_used: self.credit_used(),
                allowed_limit: self.allowed_overdraft_limit(),
                headroom: self.headroom(),
            });
        }

        // Clamp to safe amount (partial withdrawal allowed)
        let actual = requested.min(max_safe).min(self.posted_collateral);

        // Apply withdrawal
        let new_total = self.posted_collateral - actual;
        self.set_posted_collateral(new_total);

        // Clear posted_at_tick if all collateral withdrawn
        if new_total == 0 {
            self.collateral_posted_at_tick = None;
        }

        Ok(actual)
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
    /// let mut agent = Agent::with_buffer("BANK_A".to_string(), 1000000, 100000);
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
    /// let mut agent = Agent::new("BANK_A".to_string(), 1000000);
    /// agent.set_unsecured_cap(500000);
    /// assert!((agent.liquidity_pressure() - 0.33).abs() < 0.01); // ~33% into available liquidity
    /// ```
    pub fn liquidity_pressure(&self) -> f64 {
        let total_liquidity = (self.balance + self.unsecured_cap + self.posted_collateral) as f64;
        if total_liquidity == 0.0 {
            return 1.0; // Maximum stress if no liquidity
        }

        // Pressure = how far from max liquidity
        // If balance = 1M, unsecured_cap = 500k, collateral = 200k, total = 1.7M
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
    /// let mut agent = Agent::new("BANK_A".to_string(), 1000000);
    /// agent.set_unsecured_cap(500000);
    /// // Max capacity = 10 × unsecured cap = 10 × 500k = 5M
    /// assert_eq!(agent.max_collateral_capacity(), 5_000_000);
    /// ```
    pub fn max_collateral_capacity(&self) -> i64 {
        // Heuristic: 10x unsecured overdraft capacity
        // Rationale: If bank can borrow 500k unsecured intraday, they likely have
        // ~5M in collateralizable assets (bonds, reserves, etc.)
        self.unsecured_cap * 10
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
    /// let mut agent = Agent::new("BANK_A".to_string(), 1000000);
    /// agent.set_unsecured_cap(500000);
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

    /// Get top N counterparties by historical transaction volume (Phase 2.2)
    ///
    /// Returns vector of counterparty IDs sorted by total transaction volume (descending).
    ///
    /// **Purpose**: Enable policies to identify and prioritize key trading partners.
    ///
    /// **Note**: This is a placeholder implementation that returns empty vector.
    /// Full implementation requires transaction history tracking (30-day rolling window).
    ///
    /// TODO: Implement transaction history tracking per agent
    /// TODO: Track counterparty volumes over 30-day window
    /// TODO: Sort by volume and return top N
    pub fn top_counterparties(&self, _n: usize) -> Vec<String> {
        // Placeholder: Returns empty until transaction history tracking is added
        Vec::new()
    }

    // ========================================================================
    // Phase 3.3: Bank-Level Budget Management (Policy Enhancements V2)
    // ========================================================================

    /// Set release budget for current tick (apply BankDecision::SetReleaseBudget)
    ///
    /// Configures total budget, focus list, and per-counterparty limits for this tick.
    /// Resets per-counterparty usage tracking.
    ///
    /// # Arguments
    ///
    /// * `max_value` - Total budget for releases this tick (cents)
    /// * `focus_counterparties` - Optional list of allowed counterparties (None = all allowed)
    /// * `max_per_counterparty` - Optional max per counterparty (None = unlimited)
    pub fn set_release_budget(
        &mut self,
        max_value: i64,
        focus_counterparties: Option<Vec<String>>,
        max_per_counterparty: Option<i64>,
    ) {
        self.release_budget_max = Some(max_value);
        self.release_budget_remaining = max_value;
        self.release_budget_focus_counterparties = focus_counterparties;
        self.release_budget_per_counterparty_limit = max_per_counterparty;
        self.release_budget_per_counterparty_usage.clear(); // Reset usage
    }

    /// Check if release to counterparty is allowed under current budget constraints
    ///
    /// Checks:
    /// 1. Total budget remaining
    /// 2. Focus list (if set)
    /// 3. Per-counterparty limit (if set)
    ///
    /// # Arguments
    ///
    /// * `counterparty_id` - Target counterparty for release
    /// * `amount` - Amount to release (cents)
    ///
    /// # Returns
    ///
    /// true if release is allowed, false otherwise
    pub fn can_release_to_counterparty(&self, counterparty_id: &str, amount: i64) -> bool {
        // Check 1: Total budget
        if amount > self.release_budget_remaining {
            return false;
        }

        // Check 2: Focus list (if set)
        if let Some(ref focus_list) = self.release_budget_focus_counterparties {
            if !focus_list.contains(&counterparty_id.to_string()) {
                return false;
            }
        }

        // Check 3: Per-counterparty limit (if set)
        if let Some(per_counterparty_limit) = self.release_budget_per_counterparty_limit {
            let current_usage = self
                .release_budget_per_counterparty_usage
                .get(counterparty_id)
                .copied()
                .unwrap_or(0);

            if current_usage + amount > per_counterparty_limit {
                return false;
            }
        }

        true
    }

    /// Track a release (decrement budget and update per-counterparty usage)
    ///
    /// Should be called after a release is approved and submitted.
    ///
    /// # Arguments
    ///
    /// * `counterparty_id` - Target counterparty for release
    /// * `amount` - Amount released (cents)
    pub fn track_release(&mut self, counterparty_id: &str, amount: i64) {
        // Decrement total budget
        self.release_budget_remaining = self.release_budget_remaining.saturating_sub(amount);

        // Update per-counterparty usage
        *self
            .release_budget_per_counterparty_usage
            .entry(counterparty_id.to_string())
            .or_insert(0) += amount;
    }

    /// Reset release budget (called at end of tick or start of new tick)
    ///
    /// Clears budget constraints and resets to unlimited state.
    pub fn reset_release_budget(&mut self) {
        self.release_budget_max = None;
        self.release_budget_remaining = i64::MAX;
        self.release_budget_focus_counterparties = None;
        self.release_budget_per_counterparty_limit = None;
        self.release_budget_per_counterparty_usage.clear();
    }

    /// Get remaining release budget for current tick
    pub fn release_budget_remaining(&self) -> i64 {
        self.release_budget_remaining
    }

    /// Check if budget has been set for current tick
    pub fn has_release_budget(&self) -> bool {
        self.release_budget_max.is_some()
    }

    // =========================================================================
    // Phase 3.4: Collateral Auto-Withdraw Timer Management
    // =========================================================================

    /// Schedule automatic collateral withdrawal at specified tick
    ///
    /// # Arguments
    /// * `withdrawal_tick` - Tick when withdrawal should occur
    /// * `amount` - Amount to withdraw (i64 cents)
    /// * `reason` - Reason for posting (e.g., "TemporaryBoost")
    pub fn schedule_collateral_withdrawal(
        &mut self,
        withdrawal_tick: usize,
        amount: i64,
        reason: String,
    ) {
        // Use current tick as posted_at_tick (will be set correctly by orchestrator)
        self.schedule_collateral_withdrawal_with_posted_tick(
            withdrawal_tick,
            amount,
            reason,
            0, // Placeholder, will be set correctly when called from orchestrator
        );
    }

    /// Schedule automatic collateral withdrawal with explicit posted_at_tick
    ///
    /// # Arguments
    /// * `withdrawal_tick` - Tick when withdrawal should occur
    /// * `amount` - Amount to withdraw (i64 cents)
    /// * `reason` - Reason for posting (e.g., "TemporaryBoost")
    /// * `posted_at_tick` - Tick when collateral was originally posted
    pub fn schedule_collateral_withdrawal_with_posted_tick(
        &mut self,
        withdrawal_tick: usize,
        amount: i64,
        reason: String,
        posted_at_tick: usize,
    ) {
        self.collateral_withdrawal_timers
            .entry(withdrawal_tick)
            .or_insert_with(Vec::new)
            .push((amount, reason, posted_at_tick));
    }

    /// Get pending collateral withdrawals due at specified tick
    ///
    /// Returns Vec<(amount, reason)> for all timers scheduled for this tick.
    /// Does not remove the timers - use remove_collateral_withdrawal_timer() for that.
    pub fn get_pending_collateral_withdrawals(&self, tick: usize) -> Vec<(i64, String)> {
        self.collateral_withdrawal_timers
            .get(&tick)
            .map(|timers| {
                timers
                    .iter()
                    .map(|(amount, reason, _posted_at)| (*amount, reason.clone()))
                    .collect()
            })
            .unwrap_or_else(Vec::new)
    }

    /// Get pending collateral withdrawals with posted_at_tick information
    ///
    /// Returns Vec<(amount, reason, posted_at_tick)> for all timers scheduled for this tick.
    pub fn get_pending_collateral_withdrawals_with_posted_tick(
        &self,
        tick: usize,
    ) -> Vec<(i64, String, usize)> {
        self.collateral_withdrawal_timers
            .get(&tick)
            .map(|timers| timers.clone())
            .unwrap_or_else(Vec::new)
    }

    /// Remove all timers scheduled for specified tick
    ///
    /// Call this after processing withdrawals to clean up.
    pub fn remove_collateral_withdrawal_timer(&mut self, tick: usize) {
        self.collateral_withdrawal_timers.remove(&tick);
    }

    /// Check if there are any pending collateral withdrawal timers
    pub fn has_pending_collateral_withdrawals(&self) -> bool {
        !self.collateral_withdrawal_timers.is_empty()
    }

    /// Clear all pending collateral withdrawal timers
    ///
    /// Useful for resetting agent state or cancelling all scheduled withdrawals.
    pub fn clear_collateral_withdrawal_timers(&mut self) {
        self.collateral_withdrawal_timers.clear();
    }

    /// Get all pending timers for debugging/inspection
    ///
    /// Returns reference to the internal timer map.
    pub fn get_all_collateral_withdrawal_timers(
        &self,
    ) -> &std::collections::HashMap<usize, Vec<(i64, String, usize)>> {
        &self.collateral_withdrawal_timers
    }

    // ===== Phase 4.5: State Register Methods (Policy Enhancements V2) =====

    /// Set a state register value (for policy micro-memory)
    ///
    /// # Arguments
    /// * `key` - Register key (MUST start with "bank_state_")
    /// * `value` - New value (f64)
    ///
    /// # Returns
    /// - Ok((old_value, new_value)) if successful
    /// - Err(message) if validation fails
    ///
    /// # Design Constraints
    /// - Maximum 10 registers per agent
    /// - Keys MUST be prefixed with "bank_state_"
    /// - Updating existing register doesn't count against limit
    ///
    /// # Example
    /// ```
    /// use payment_simulator_core_rs::Agent;
    ///
    /// let mut agent = Agent::new("BANK_A".to_string(), 100_000);
    /// agent.set_unsecured_cap(50_000);
    /// let (old, new) = agent.set_state_register("bank_state_cooldown".to_string(), 42.0).unwrap();
    /// assert_eq!(old, 0.0);
    /// assert_eq!(new, 42.0);
    /// ```
    pub fn set_state_register(&mut self, key: String, value: f64) -> Result<(f64, f64), String> {
        // Validation: Key must have correct prefix
        if !key.starts_with("bank_state_") {
            return Err(format!(
                "Register key must start with 'bank_state_', got: '{}'",
                key
            ));
        }

        // Validation: Maximum 10 registers (unless updating existing)
        if self.state_registers.len() >= 10 && !self.state_registers.contains_key(&key) {
            return Err("Maximum 10 state registers per agent".to_string());
        }

        // Get old value (0.0 if doesn't exist)
        let old_value = self.state_registers.get(&key).copied().unwrap_or(0.0);

        // Set new value
        self.state_registers.insert(key, value);

        Ok((old_value, value))
    }

    /// Get a state register value
    ///
    /// Returns 0.0 if register doesn't exist (default value).
    ///
    /// # Arguments
    /// * `key` - Register key
    ///
    /// # Example
    /// ```
    /// use payment_simulator_core_rs::Agent;
    ///
    /// let mut agent = Agent::new("BANK_A".to_string(), 100_000);
    /// agent.set_unsecured_cap(50_000);
    /// // Non-existent register returns 0.0
    /// assert_eq!(agent.get_state_register("bank_state_foo"), 0.0);
    /// ```
    pub fn get_state_register(&self, key: &str) -> f64 {
        self.state_registers.get(key).copied().unwrap_or(0.0)
    }

    /// Reset all state registers (used at end of day)
    ///
    /// Returns vector of (key, old_value) pairs for event emission.
    ///
    /// # Example
    /// ```
    /// use payment_simulator_core_rs::Agent;
    ///
    /// let mut agent = Agent::new("BANK_A".to_string(), 100_000);
    /// agent.set_unsecured_cap(50_000);
    /// agent.set_state_register("bank_state_cooldown".to_string(), 42.0).unwrap();
    ///
    /// let old_values = agent.reset_state_registers();
    /// assert_eq!(old_values.len(), 1);
    /// assert_eq!(agent.get_state_register("bank_state_cooldown"), 0.0);
    /// ```
    pub fn reset_state_registers(&mut self) -> Vec<(String, f64)> {
        // Capture all old values
        let old_values: Vec<_> = self
            .state_registers
            .iter()
            .map(|(k, v)| (k.clone(), *v))
            .collect();

        // Clear all registers
        self.state_registers.clear();

        old_values
    }

    /// Get reference to all state registers (for context building)
    pub fn state_registers(&self) -> &std::collections::HashMap<String, f64> {
        &self.state_registers
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::models::state::SimulationState;
    use crate::models::Transaction;

    // =========================================================================
    // Collateral Management Tests - Phase 8+
    // =========================================================================

    #[test]
    fn test_available_liquidity_includes_collateral() {
        let mut agent = Agent::new("BANK_A".to_string(), 1_000_000);
        agent.set_unsecured_cap(500_000);

        // Initially: balance + credit = 1M + 500k = 1.5M
        assert_eq!(agent.available_liquidity(), 1_500_000);

        // Post collateral with default 2% haircut
        agent.set_posted_collateral(200_000);

        // Now: balance + credit + collateral*(1-haircut) = 1M + 500k + (200k * 0.98) = 1.696M
        assert_eq!(agent.available_liquidity(), 1_696_000);
    }

    #[test]
    fn test_available_liquidity_with_negative_balance_and_collateral() {
        let mut agent = Agent::new("BANK_A".to_string(), 1_000_000);
        agent.set_unsecured_cap(500_000);
        agent.set_posted_collateral(200_000);

        // Use overdraft
        agent.debit(1_200_000).unwrap();

        // Balance = -200k (credit_used = 200k)
        // collateral_value = 200k × (1 - 0.02) = 196k
        // total_headroom = 500k credit + 196k collateral = 696k
        // available_headroom = 696k - 200k used = 496k
        // Available = 0 (balance capped) + 496k available_headroom = 496k
        assert_eq!(agent.balance(), -200_000);
        assert_eq!(agent.available_liquidity(), 496_000);
    }

    #[test]
    fn test_max_collateral_capacity() {
        let mut agent = Agent::new("BANK_A".to_string(), 1_000_000);
        agent.set_unsecured_cap(500_000);

        // Max capacity = 10x credit limit
        assert_eq!(agent.max_collateral_capacity(), 5_000_000);
    }

    #[test]
    fn test_remaining_collateral_capacity() {
        let mut agent = Agent::new("BANK_A".to_string(), 1_000_000);
        agent.set_unsecured_cap(500_000);

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
        let mut agent = Agent::new("BANK_A".to_string(), 1_000_000);
        agent.set_unsecured_cap(500_000);
        let mut state = SimulationState::new(vec![agent.clone()]);

        // Agent has 1.5M available liquidity
        // Queue 1 is empty
        let gap = agent.queue1_liquidity_gap(&state);
        assert_eq!(gap, 0);
    }

    #[test]
    fn test_queue1_liquidity_gap_with_transactions() {
        let mut agent = Agent::new("BANK_A".to_string(), 500_000);
        agent.set_unsecured_cap(300_000);
        let mut state = SimulationState::new(vec![
            agent.clone(),
            Agent::new("BANK_B".to_string(), 1_000_000),
        ]);

        // Create transactions and add to Queue 1
        let tx1 = Transaction::new(
            "BANK_A".to_string(),
            "BANK_B".to_string(),
            400_000,
            0,   // arrival
            100, // deadline
        );
        let tx2 = Transaction::new("BANK_A".to_string(), "BANK_B".to_string(), 600_000, 0, 100);

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
        let mut agent = Agent::new("BANK_A".to_string(), 500_000);
        agent.set_unsecured_cap(300_000);
        agent.set_posted_collateral(200_000); // Add collateral

        let mut state = SimulationState::new(vec![
            agent.clone(),
            Agent::new("BANK_B".to_string(), 1_000_000),
        ]);

        // Create transaction
        let tx = Transaction::new("BANK_A".to_string(), "BANK_B".to_string(), 900_000, 0, 100);

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
        let mut agent = Agent::new("BANK_A".to_string(), 1_000_000);
        agent.set_unsecured_cap(500_000);
        agent.set_posted_collateral(200_000);

        // Total liquidity: 1M + 500k + 200k = 1.7M
        // Pressure = 1 - (1M / 1.7M) ≈ 0.41
        let pressure = agent.liquidity_pressure();
        assert!((pressure - 0.41).abs() < 0.02);
    }

    #[test]
    fn test_can_pay_with_collateral() {
        let mut agent = Agent::new("BANK_A".to_string(), 500_000);
        agent.set_unsecured_cap(300_000);
        agent.set_posted_collateral(400_000);

        // Available: 500k + 300k + (400k × 0.98) = 500k + 300k + 392k = 1.192M
        assert!(agent.can_pay(1_000_000));
        assert!(agent.can_pay(1_192_000));
        assert!(!agent.can_pay(1_200_000)); // Exceeds available (only 1.192M)
    }

    #[test]
    fn test_collateral_post_and_withdraw_cycle() {
        let mut agent = Agent::new("BANK_A".to_string(), 1_000_000);
        agent.set_unsecured_cap(500_000);

        // Initial state
        assert_eq!(agent.posted_collateral(), 0);
        assert_eq!(agent.available_liquidity(), 1_500_000);

        // Post collateral (default 2% haircut)
        agent.set_posted_collateral(300_000);
        assert_eq!(agent.posted_collateral(), 300_000);
        assert_eq!(agent.available_liquidity(), 1_794_000); // 1M + 500k + (300k × 0.98)

        // Post more
        agent.set_posted_collateral(800_000);
        assert_eq!(agent.posted_collateral(), 800_000);
        assert_eq!(agent.available_liquidity(), 2_284_000); // 1M + 500k + (800k × 0.98)

        // Withdraw
        agent.set_posted_collateral(200_000);
        assert_eq!(agent.posted_collateral(), 200_000);
        assert_eq!(agent.available_liquidity(), 1_696_000); // 1M + 500k + (200k × 0.98)

        // Withdraw all
        agent.set_posted_collateral(0);
        assert_eq!(agent.posted_collateral(), 0);
        assert_eq!(agent.available_liquidity(), 1_500_000);
    }
}
