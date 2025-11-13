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
//!         ticks_per_day: usize,
//!         eod_rush_threshold: f64,
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
    ///
    /// # Phase 3.2: RTGS Flags
    ///
    /// Optional parameters enable policies to control priority and timing:
    ///
    /// * `priority_override` - Override transaction's original priority (0-10)
    ///   - Useful for urgent deadlines or to lower priority during oversupply
    ///   - If None, uses transaction's original priority
    ///
    /// * `target_tick` - Target tick for release (for LSM coordination)
    ///   - If None or <= current tick, releases immediately
    ///   - If > current tick, schedules release for that tick
    ///   - Enables coordinating releases with expected inbound payments
    ///
    /// # Examples
    ///
    /// ```
    /// use payment_simulator_core_rs::policy::ReleaseDecision;
    ///
    /// // Boost priority for urgent transaction
    /// let decision1 = ReleaseDecision::SubmitFull {
    ///     tx_id: "urgent_tx".to_string(),
    ///     priority_override: Some(10), // HIGH priority
    ///     target_tick: None,           // Release now
    /// };
    ///
    /// // Coordinate with expected LSM offset
    /// let current_tick = 10;
    /// let decision2 = ReleaseDecision::SubmitFull {
    ///     tx_id: "lsm_tx".to_string(),
    ///     priority_override: None,
    ///     target_tick: Some(current_tick + 5), // Release in 5 ticks
    /// };
    /// ```
    SubmitFull {
        tx_id: String,
        /// Optional priority override (0-10). If None, uses transaction's original priority.
        priority_override: Option<u8>,
        /// Optional target tick for release. If None, releases immediately.
        target_tick: Option<usize>,
    },

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
    ///
    /// NOTE: This variant is DEPRECATED. Use `Hold` instead. Transactions should
    /// not be "dropped" - all obligations must eventually settle. See Phase 1
    /// of realistic dropped transactions plan.
    Drop { tx_id: String },

    /// Change transaction priority (Phase 4: Overdue Handling)
    ///
    /// Allows policy to adjust priority of queued transactions based on changing
    /// conditions (e.g., overdue status, approaching deadline). Transaction remains
    /// in Queue 1 after reprioritization.
    ///
    /// This action is independent of submission - a policy can reprioritize and
    /// then separately decide whether to submit, hold, or split.
    ///
    /// # Arguments
    ///
    /// * `tx_id` - Transaction to reprioritize
    /// * `new_priority` - New priority level (0-10, will be capped at 10)
    ///
    /// # Example Policy Use
    ///
    /// ```yaml
    /// # Step 1: Reprioritize overdue transactions to highest priority
    /// - if: is_overdue == 1
    ///   then:
    ///     action: reprioritize
    ///     new_priority: 10
    ///
    /// # Step 2: Submit if liquidity available (separate decision)
    /// - if: available_liquidity >= amount
    ///   then:
    ///     action: submit_full
    /// ```
    Reprioritize {
        tx_id: String,
        new_priority: u8,
    },

    /// Split transaction and release children with staggered timing (Phase 3.1)
    ///
    /// Creates `num_splits` child transactions from the parent, but unlike
    /// `SubmitPartial`, releases them gradually over time instead of all at once.
    ///
    /// # Timing Control
    ///
    /// * `stagger_first_now` - Number of children to release immediately
    /// * `stagger_gap_ticks` - Tick gap between subsequent releases
    /// * Remaining children are queued internally with scheduled release ticks
    ///
    /// # Example
    ///
    /// With `num_splits=5`, `stagger_first_now=2`, `stagger_gap_ticks=3`:
    /// - Children 1-2: Released at tick T (immediate)
    /// - Child 3: Released at tick T+3
    /// - Child 4: Released at tick T+6
    /// - Child 5: Released at tick T+9
    ///
    /// # Priority Boost
    ///
    /// * `priority_boost_children` - Added to parent priority (capped at 10)
    /// * Useful for ensuring staggered children don't get stuck behind new arrivals
    ///
    /// # Cost
    ///
    /// Split friction cost is charged once when split occurs:
    /// `split_friction_cost × (num_splits - 1)`
    ///
    /// Staggering timing is free (no additional cost beyond the split itself).
    ///
    /// # Use Cases
    ///
    /// 1. **Feed LSM gradually**: Release to counterparty A over multiple ticks
    ///    to trigger bilateral offsets as A's payments arrive
    /// 2. **Avoid Queue 2 flooding**: Pace releases to prevent overwhelming RTGS
    /// 3. **Wait for inflows**: Release first child now, delay others until
    ///    expected incoming settlements provide liquidity
    /// 4. **End-of-day strategy**: Release large payment in waves as deadline approaches
    ///
    /// # Constraints
    ///
    /// * `num_splits >= 2` (must actually split)
    /// * `stagger_first_now <= num_splits` (can't release more than exist)
    /// * `stagger_gap_ticks >= 0` (negative gaps invalid)
    /// * All children inherit parent's deadline (staggering doesn't extend it)
    ///
    /// # Phase 3.1 Implementation
    ///
    /// This action enables realistic cash manager behavior: pacing releases to
    /// manage liquidity flow and optimize LSM recycling opportunities.
    StaggerSplit {
        tx_id: String,
        num_splits: usize,
        stagger_first_now: usize,
        stagger_gap_ticks: usize,
        priority_boost_children: u8,
    },
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
    /// * `auto_withdraw_after_ticks` - Optional: automatically withdraw after N ticks (Phase 3.4)
    Post {
        amount: i64,
        reason: CollateralReason,
        auto_withdraw_after_ticks: Option<usize>,
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

/// Decision about bank-level resource management (Phase 3.3)
///
/// Bank-level decisions are evaluated once per agent per tick (not per transaction).
/// They set budgets and constraints that affect all transaction-level decisions
/// for that tick.
///
/// # Use Cases
///
/// 1. **Liquidity Budgeting**: Limit total releases per tick to conserve liquidity
/// 2. **Counterparty Focus**: Prioritize specific counterparties for strategic reasons
/// 3. **Risk Management**: Cap exposure to individual counterparties
/// 4. **Flow Control**: Prevent overwhelming RTGS with too many simultaneous releases
///
/// # Evaluation
///
/// Bank-level decisions are evaluated via the `bank_tree` in policy JSON:
/// - Evaluated once per agent at the start of each tick
/// - Sets budget state that persists for the tick
/// - Transaction-level `Release` decisions check budget and are blocked if exceeded
///
/// # Example
///
/// ```json
/// {
///   "bank_tree": {
///     "type": "action",
///     "node_id": "B1_SetBudget",
///     "action": "SetReleaseBudget",
///     "parameters": {
///       "max_value_to_release": {"value": 500000.0},
///       "focus_cpty_list": {"value": ["BANK_A", "BANK_B"]},
///       "max_per_cpty": {"value": 100000.0}
///     }
///   }
/// }
/// ```
#[derive(Debug, Clone, PartialEq)]
pub enum BankDecision {
    /// Set release budget for this tick
    ///
    /// Establishes limits on total and per-counterparty releases for the current tick.
    /// Budget resets at the start of each tick.
    ///
    /// # Parameters
    ///
    /// * `max_value_to_release` - Total value that can be released this tick (cents)
    /// * `focus_counterparties` - Optional list of allowed counterparties. If None, all allowed.
    /// * `max_per_counterparty` - Optional max value per counterparty (cents). If None, unlimited per counterparty.
    ///
    /// # Budget Enforcement
    ///
    /// When a `Release` decision is processed:
    /// 1. Check if total budget exceeded → convert to `Hold` with reason "BudgetExhausted"
    /// 2. Check if counterparty in focus list (if specified) → convert to `Hold` with reason "NotInFocusList"
    /// 3. Check if per-counterparty limit exceeded → convert to `Hold` with reason "CounterpartyLimitExceeded"
    /// 4. If all checks pass, proceed with release and deduct from budget
    ///
    /// # Example
    ///
    /// ```rust
    /// use payment_simulator_core_rs::policy::BankDecision;
    ///
    /// // Set budget: max $5,000 total, max $1,000 per counterparty, focus on BANK_A/B
    /// let decision = BankDecision::SetReleaseBudget {
    ///     max_value_to_release: 500_000,
    ///     focus_counterparties: Some(vec!["BANK_A".to_string(), "BANK_B".to_string()]),
    ///     max_per_counterparty: Some(100_000),
    /// };
    /// ```
    SetReleaseBudget {
        /// Total budget for this tick (cents)
        max_value_to_release: i64,
        /// Optional list of allowed counterparties. If None, all allowed.
        focus_counterparties: Option<Vec<String>>,
        /// Optional max per counterparty (cents). If None, unlimited per counterparty.
        max_per_counterparty: Option<i64>,
    },

    /// No bank-level action (default)
    ///
    /// Used when policy has no bank_tree or bank_tree evaluates to no-op.
    /// All transaction-level decisions proceed without budget constraints.
    NoAction,
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
///         _ticks_per_day: usize,
///         _eod_rush_threshold: f64,
///     ) -> Vec<ReleaseDecision> {
///         // Submit all queued transactions immediately
///         agent.outgoing_queue()
///             .iter()
///             .map(|tx_id| ReleaseDecision::SubmitFull {
///                 tx_id: tx_id.clone(),
///                 priority_override: None,
///                 target_tick: None,
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
        ticks_per_day: usize,
        eod_rush_threshold: f64,
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

#[cfg(test)]
mod tests {
    use super::*;
    use crate::models::Transaction;

    // ========================================================================
    // Phase 4: Reprioritize Action Tests (TDD)
    // ========================================================================

    #[test]
    fn test_reprioritize_decision() {
        let decision = ReleaseDecision::Reprioritize {
            tx_id: "tx_123".to_string(),
            new_priority: 10,
        };

        // Verify enum construction
        match decision {
            ReleaseDecision::Reprioritize { tx_id, new_priority } => {
                assert_eq!(tx_id, "tx_123");
                assert_eq!(new_priority, 10);
            }
            _ => panic!("Wrong variant"),
        }
    }

    #[test]
    fn test_reprioritize_changes_transaction_priority() {
        let mut tx = Transaction::new("A".to_string(), "B".to_string(), 100_000, 0, 50);
        assert_eq!(tx.priority(), 5); // Default

        // Reprioritize to 10
        tx.set_priority(10);
        assert_eq!(tx.priority(), 10);

        // Reprioritize to 3
        tx.set_priority(3);
        assert_eq!(tx.priority(), 3);
    }

    #[test]
    fn test_reprioritize_caps_at_10() {
        let mut tx = Transaction::new("A".to_string(), "B".to_string(), 100_000, 0, 50);

        // Try to set priority > 10
        tx.set_priority(255);
        assert_eq!(tx.priority(), 10); // Capped
    }
}
