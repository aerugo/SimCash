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
//! }
//! ```
//!
//! # Baseline Policies
//!
//! Three baseline policies are provided:
//! 1. **FifoPolicy**: Submit oldest transaction first (simple baseline)
//! 2. **DeadlinePolicy**: Prioritize transactions approaching deadline
//! 3. **LiquidityAwarePolicy**: Hold transactions when liquidity is low
//!
//! # Example Usage
//!
//! ```
//! use payment_simulator_core_rs::policy::{LiquidityAwarePolicy, CashManagerPolicy};
//! use payment_simulator_core_rs::{Agent, SimulationState, CostRates};
//!
//! let mut policy = LiquidityAwarePolicy::new(100_000); // Keep 100k buffer
//! let agent = Agent::new("BANK_A".to_string(), 1_000_000, 500_000);
//! let state = SimulationState::new(vec![agent]);
//! let cost_rates = CostRates::default();
//!
//! let decisions = policy.evaluate_queue(
//!     state.get_agent("BANK_A").unwrap(),
//!     &state,
//!     5,
//!     &cost_rates,
//! );
//! // decisions contain Submit/Hold/Drop actions
//! ```

use crate::orchestrator::CostRates;
use crate::{Agent, SimulationState};

pub mod deadline;
pub mod fifo;
pub mod liquidity_aware;
pub mod splitting;
pub mod tree; // Phase 6: JSON decision tree policies

pub use deadline::DeadlinePolicy;
pub use fifo::FifoPolicy;
pub use liquidity_aware::LiquidityAwarePolicy;
pub use splitting::LiquiditySplittingPolicy;

// MockSplittingPolicy is exported to support integration tests
// It should only be used in test code
pub use splitting::MockSplittingPolicy;

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
}
