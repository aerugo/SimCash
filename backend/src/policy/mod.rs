//! Cash Manager Policy Module
//!
//! This module defines the policy interface for Queue 1 (internal bank queue) decisions.
//!
//! # Overview
//!
//! Cash managers at each bank must decide **when** to submit transactions from their
//! internal queue (Queue 1) to the central RTGS system (Queue 2). This decision is
//! strategic and affects:
//! - Liquidity usage (credit costs)
//! - Settlement delays (SLA penalties)
//! - Gridlock risk (coordination with other banks)
//!
//! See `/docs/queue_architecture.md` for complete explanation of Queue 1 vs. Queue 2.
//!
//! # Policy Interface
//!
//! All policies implement the `CashManagerPolicy` trait:
//! ```rust
//! use payment_simulator_core_rs::policy::{CashManagerPolicy, ReleaseDecision};
//! use payment_simulator_core_rs::{Agent, SimulationState, CostRates};
//!
//! struct MyPolicy;
//!
//! impl CashManagerPolicy for MyPolicy {
//!     fn evaluate_queue(
//!         &mut self,
//!         agent: &Agent,
//!         state: &SimulationState,
//!         tick: usize,
//!         cost_rates: &CostRates,
//!     ) -> Vec<ReleaseDecision> {
//!         // Decision logic here
//!         vec![]
//!     }
//!
//!     fn as_any_mut(&mut self) -> &mut dyn std::any::Any {
//!         self
//!     }
//! }
//! ```
//!
//! # JSON DSL Policies
//!
//! All policies are now defined using JSON-based decision trees in the `tree` module.
//! Use `PolicyConfig` enum with the orchestrator to load policies:
//!
//! Available policies:
//! 1. **Fifo**: Submit oldest transaction first (simple baseline)
//! 2. **Deadline**: Prioritize transactions approaching deadline
//! 3. **LiquidityAware**: Hold transactions when liquidity is low
//! 4. **MockSplitting**: Test-only policy that always splits
//! 5. **LiquiditySplitting**: Intelligent splitting based on liquidity
//!
//! # Example Usage
//!
//! See integration tests in `/backend/tests/` for complete examples of using
//! PolicyConfig with the orchestrator.
//!
//! Policies are loaded automatically via the factory pattern:
//!
//! ```rust
//! use payment_simulator_core_rs::orchestrator::PolicyConfig;
//!
//! // Configure liquidity-aware policy
//! let policy_config = PolicyConfig::LiquidityAware {
//!     target_buffer: 100_000,
//!     urgency_threshold: 5,
//! };
//! // Orchestrator automatically loads policies/liquidity_aware.json
//! // and injects these parameters
//! ```

use crate::orchestrator::CostRates;
use crate::{Agent, SimulationState};

pub mod tree; // JSON decision tree policies (DSL-based)

/// Decision about what to do with a transaction in Queue 1
#[derive(Debug, Clone, PartialEq)]
pub enum ReleaseDecision {
    /// Submit entire transaction to RTGS now
    ///
    /// Moves transaction from Queue 1 to Queue 2 (RTGS central queue).
    /// May settle immediately if liquidity sufficient, or queue in RTGS.
    SubmitFull { tx_id: String },

    /// Split transaction into multiple parts and submit all children
    ///
    /// Creates `num_splits` child transactions from the parent transaction.
    /// Each child has approximately `parent_amount / num_splits` amount.
    /// The last child gets any remainder to ensure exact sum.
    ///
    /// All child transactions are immediately submitted to RTGS.
    /// A split friction cost is charged: `split_friction_cost × (num_splits - 1)`
    ///
    /// # Phase 5 Implementation
    /// This enables policies to "pace" large payments by voluntarily splitting
    /// them into smaller chunks to manage liquidity constraints.
    SubmitPartial {
        tx_id: String,
        num_splits: usize, // Number of equal-sized children to create
    },

    /// Hold transaction in Queue 1 for later
    ///
    /// Transaction remains in internal queue. Will be re-evaluated next tick.
    /// Reasons include: insufficient liquidity, low priority, awaiting inflows.
    Hold { tx_id: String, reason: HoldReason },

    /// Drop transaction (will expire anyway)
    ///
    /// Removes transaction from Queue 1 without submitting to RTGS.
    /// Typically used when transaction is past deadline or about to expire.
    Drop { tx_id: String },
}

/// Reason for holding a transaction in Queue 1
#[derive(Debug, Clone, PartialEq)]
pub enum HoldReason {
    /// Insufficient liquidity to send without violating buffer
    InsufficientLiquidity,

    /// Waiting for expected incoming payments
    AwaitingInflows,

    /// Transaction has low priority, others more urgent
    LowPriority,

    /// Approaching deadline but not yet urgent
    NearDeadline { ticks_remaining: usize },

    /// Custom policy-specific reason
    Custom(String),
}

/// Decision about collateral management
///
/// Policies can return this to indicate whether to post or withdraw collateral.
/// This enables dynamic collateral management based on liquidity needs, deadlines,
/// and cost optimization.
#[derive(Debug, Clone, PartialEq)]
pub enum CollateralDecision {
    /// Post additional collateral to increase available liquidity
    ///
    /// # Arguments
    ///
    /// * `amount` - Amount of collateral to post (cents)
    /// * `reason` - Why collateral is being posted
    Post {
        amount: i64,
        reason: CollateralReason,
    },

    /// Withdraw collateral to reduce opportunity cost
    ///
    /// # Arguments
    ///
    /// * `amount` - Amount of collateral to withdraw (cents)
    /// * `reason` - Why collateral is being withdrawn
    Withdraw {
        amount: i64,
        reason: CollateralReason,
    },

    /// Hold current collateral level (no change)
    Hold,
}

/// Reason for posting or withdrawing collateral
#[derive(Debug, Clone, PartialEq)]
pub enum CollateralReason {
    /// Urgent transactions need liquidity immediately
    UrgentLiquidityNeed,

    /// Preemptive posting to prepare for upcoming liquidity needs
    PreemptivePosting,

    /// Liquidity has been restored, no longer need collateral
    LiquidityRestored,

    /// End-of-day cleanup (withdraw unused collateral)
    EndOfDayCleanup,

    /// Emergency posting due to imminent deadline
    DeadlineEmergency,

    /// Optimizing cost trade-offs
    CostOptimization,

    /// Custom policy-specific reason
    Custom(String),
}

/// Cash manager policy trait
///
/// Implement this trait to define custom decision logic for when to submit
/// transactions from internal queue (Queue 1) to RTGS (Queue 2).
///
/// # Decision Factors
///
/// Policies typically consider:
/// - **Liquidity**: `agent.available_liquidity()`, `agent.liquidity_pressure()`
/// - **Urgency**: `tx.deadline_tick()`, time remaining
/// - **Forecasting**: `agent.incoming_expected()`, expected inflows
/// - **System state**: `state.queue_size()`, RTGS queue pressure
///
/// # Policy State
///
/// Policies can maintain internal state (e.g., learning parameters, history).
/// The `&mut self` parameter allows mutable access.
///
/// # Example Implementation
///
/// ```
/// use payment_simulator_core_rs::policy::{CashManagerPolicy, ReleaseDecision, HoldReason};
/// use payment_simulator_core_rs::{Agent, SimulationState, CostRates};
///
/// struct AlwaysSubmitPolicy;
///
/// impl CashManagerPolicy for AlwaysSubmitPolicy {
///     fn evaluate_queue(
///         &mut self,
///         agent: &Agent,
///         _state: &SimulationState,
///         _tick: usize,
///         _cost_rates: &CostRates,
///     ) -> Vec<ReleaseDecision> {
///         // Submit all queued transactions immediately
///         agent.outgoing_queue()
///             .iter()
///             .map(|tx_id| ReleaseDecision::SubmitFull {
///                 tx_id: tx_id.clone(),
///             })
///             .collect()
///     }
///
///     fn as_any_mut(&mut self) -> &mut dyn std::any::Any {
///         self
///     }
/// }
/// ```
pub trait CashManagerPolicy: Send + Sync {
    /// Evaluate internal queue and decide what to submit to RTGS
    ///
    /// Called once per tick for each agent. Returns a vector of decisions
    /// for transactions in the agent's Queue 1 (internal outgoing queue).
    ///
    /// # Arguments
    ///
    /// * `agent` - Agent whose queue is being evaluated
    /// * `state` - Full simulation state (for querying transactions, other agents)
    /// * `tick` - Current simulation tick
    /// * `cost_rates` - Read-only access to simulation cost configuration
    ///
    /// # Returns
    ///
    /// Vector of decisions (Submit/Hold/Drop) for transactions in agent's queue
    ///
    /// # Notes
    ///
    /// - Not all transactions in queue need a decision (unmentioned = implicitly held)
    /// - Multiple Submit decisions can be returned (batch submission)
    /// - Policy can inspect `state` to see RTGS queue size, other agents, etc.
    /// - Agent's `last_decision_tick` is automatically updated by orchestrator
    /// - Policies can read cost_rates for decision-making but cannot modify them
    ///   (ensures LLM-safe design where external costs cannot be gamed)
    fn evaluate_queue(
        &mut self,
        agent: &Agent,
        state: &SimulationState,
        tick: usize,
        cost_rates: &CostRates,
    ) -> Vec<ReleaseDecision>;

    /// Evaluate collateral management decision
    ///
    /// Called once per tick for each agent (after queue evaluation).
    /// Returns a decision about whether to post, withdraw, or hold collateral.
    ///
    /// # Arguments
    ///
    /// * `agent` - Agent whose collateral is being evaluated
    /// * `state` - Full simulation state (for querying transactions, Queue 2, etc.)
    /// * `tick` - Current simulation tick
    /// * `cost_rates` - Read-only access to simulation cost configuration
    ///
    /// # Returns
    ///
    /// CollateralDecision (Post/Withdraw/Hold) with reason and amount
    ///
    /// # Default Implementation
    ///
    /// Returns `CollateralDecision::Hold`, making collateral management optional.
    /// Existing policies continue working without modification (backward compatible).
    ///
    /// # Notes
    ///
    /// - Policies can read cost_rates to balance collateral cost vs other costs
    /// - Can inspect Queue 2 to see pending transactions with imminent deadlines
    /// - Should consider current balance, credit usage, and liquidity pressure
    /// - Amount must be positive; orchestrator validates capacity constraints
    fn evaluate_collateral(
        &mut self,
        _agent: &Agent,
        _state: &SimulationState,
        _tick: usize,
        _cost_rates: &CostRates,
    ) -> CollateralDecision {
        // Default: no collateral management (backward compatible)
        CollateralDecision::Hold
    }

    /// Enable downcasting to concrete types (for accessing TreePolicy-specific methods)
    ///
    /// This method allows the orchestrator to downcast trait objects to their
    /// concrete types (e.g., TreePolicy) to access specialized methods like
    /// `evaluate_strategic_collateral()` and `evaluate_end_of_tick_collateral()`.
    fn as_any_mut(&mut self) -> &mut dyn std::any::Any;
}
