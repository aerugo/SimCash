//! Transaction splitting policies (Phase 5)
//!
//! Policies that can voluntarily split large transactions into multiple smaller
//! child transactions to manage liquidity constraints.
//!
//! # Key Concepts
//!
//! - **Splitting is a policy decision**: Not a system capability. Agents choose
//!   to split payments to manage their liquidity.
//! - **Split friction cost**: Each split incurs overhead cost (f_s × (N-1))
//! - **Trade-off**: Split to avoid delay/overdraft costs vs pay friction cost
//!
//! # Policies
//!
//! 1. **MockSplittingPolicy**: Testing-only policy that always splits
//! 2. **LiquiditySplittingPolicy**: Intelligent policy balancing costs

use crate::models::agent::Agent;
use crate::models::state::SimulationState;
use crate::models::Transaction;
use crate::orchestrator::CostRates;
use crate::policy::{CashManagerPolicy, HoldReason, ReleaseDecision};

// ============================================================================
// Mock Splitting Policy (For Testing)
// ============================================================================

/// Mock policy that always splits transactions into fixed number of parts.
///
/// **Testing use only** - Not a realistic policy!
///
/// This policy unconditionally splits every transaction it sees into
/// `num_splits` equal parts. Used in tests to verify that the splitting
/// mechanics work correctly.
///
/// # Note
///
/// This policy is always compiled (not just in test mode) to support
/// integration tests. However, it should only be used in test code and
/// never in production.
#[doc(hidden)]
pub struct MockSplittingPolicy {
    /// Number of splits to create for each transaction
    num_splits: usize,
}

impl MockSplittingPolicy {
    /// Create new mock splitting policy
    ///
    /// # Testing use only
    ///
    /// This should only be called from test code.
    pub fn new(num_splits: usize) -> Self {
        assert!(num_splits >= 2, "num_splits must be >= 2");
        Self { num_splits }
    }
}

impl CashManagerPolicy for MockSplittingPolicy {
    fn evaluate_queue(
        &mut self,
        agent: &Agent,
        _state: &SimulationState,
        _current_tick: usize,
        _cost_rates: &CostRates,
    ) -> Vec<ReleaseDecision> {
        // Note: cost_rates not used by MockSplittingPolicy (testing only)
        // Split every transaction in the queue
        agent
            .outgoing_queue()
            .iter()
            .map(|tx_id| ReleaseDecision::SubmitPartial {
                tx_id: tx_id.to_string(),
                num_splits: self.num_splits,
            })
            .collect()
    }
}

// ============================================================================
// Liquidity Splitting Policy (Production Policy)
// ============================================================================

/// Intelligently splits large payments when liquidity is constrained.
///
/// # Decision Algorithm
///
/// For each transaction in Queue 1, decides whether to:
/// 1. **Submit whole** - If affordable and no benefit from splitting
/// 2. **Split into N parts** - If liquidity tight, deadline urgent, or queue pressure high
/// 3. **Hold** - If even splitting wouldn't help
///
/// # Cost Trade-off
///
/// Splitting incurs friction cost but can:
/// - Avoid overdraft costs (send what you can now, rest later)
/// - Avoid delay costs (make progress instead of waiting)
/// - Meet deadlines (partial payment better than none)
///
/// The policy estimates whether splitting saves more than it costs.
///
/// # Parameters
///
/// - `max_splits`: Maximum splits per transaction (e.g., 4)
/// - `min_split_amount`: Don't create splits smaller than this (e.g., $100)
///
/// # Example
///
/// ```rust,ignore
/// let policy = LiquiditySplittingPolicy::new(
///     4,       // max 4 splits
///     10_000,  // min $100 per split
/// );
/// ```
pub struct LiquiditySplittingPolicy {
    /// Maximum number of splits allowed
    max_splits: usize,

    /// Minimum amount per split (cents)
    min_split_amount: i64,
}

impl LiquiditySplittingPolicy {
    /// Create new liquidity splitting policy
    ///
    /// # Arguments
    ///
    /// * `max_splits` - Maximum splits per transaction (must be >= 2)
    /// * `min_split_amount` - Minimum amount per child (cents, must be > 0)
    ///
    /// # Panics
    ///
    /// Panics if max_splits < 2 or min_split_amount <= 0
    pub fn new(max_splits: usize, min_split_amount: i64) -> Self {
        assert!(max_splits >= 2, "max_splits must be >= 2");
        assert!(min_split_amount > 0, "min_split_amount must be positive");

        Self {
            max_splits,
            min_split_amount,
        }
    }

    /// Decide whether and how to split a transaction
    ///
    /// Returns `Some(num_splits)` if splitting is beneficial, `None` otherwise.
    fn decide_split(
        &self,
        tx: &Transaction,
        agent: &Agent,
        current_tick: usize,
        split_friction_cost_rate: i64,
    ) -> Option<usize> {
        let amount = tx.amount();
        let balance = agent.balance();

        // Check if we can afford the whole transaction
        let can_afford_whole = balance >= amount;

        // If we can afford it whole and deadline isn't urgent, don't split
        let ticks_to_deadline = tx.deadline_tick().saturating_sub(current_tick);
        let deadline_urgent = ticks_to_deadline <= 5; // Urgent if <= 5 ticks left

        if can_afford_whole && !deadline_urgent {
            return None; // Submit whole, no need to split
        }

        // Can't afford whole or deadline is urgent - consider splitting

        // Calculate how many splits would be beneficial
        // Strategy: Split into as many parts as needed to make each affordable
        // or use urgency-based splitting

        let num_splits_needed = if balance > 0 {
            // Calculate splits needed to make each part affordable
            let splits = (amount / balance.max(1)).max(2) as usize;
            splits.min(self.max_splits)
        } else {
            // Negative balance or zero - split into max to send smallest parts
            if deadline_urgent {
                self.max_splits
            } else {
                return None; // Hold until balance improves
            }
        };

        // Check min_split_amount constraint
        let split_amount = amount / num_splits_needed as i64;
        if split_amount < self.min_split_amount {
            // Would create splits that are too small
            // Try fewer splits
            let max_affordable_splits = (amount / self.min_split_amount).max(2) as usize;
            if max_affordable_splits < 2 {
                return None; // Can't split without violating min_split_amount
            }
            return Some(max_affordable_splits.min(self.max_splits));
        }

        // Estimate cost-benefit of splitting
        let friction_cost = split_friction_cost_rate * (num_splits_needed as i64 - 1);

        // Very simplified cost-benefit (can be made more sophisticated):
        // If deadline is urgent, split regardless of friction cost
        // Otherwise, only split if friction cost is reasonable relative to amount
        if deadline_urgent {
            return Some(num_splits_needed);
        }

        // For non-urgent: only split if friction cost < 1% of amount
        if friction_cost < amount / 100 {
            return Some(num_splits_needed);
        }

        None // Not worth splitting
    }
}

impl CashManagerPolicy for LiquiditySplittingPolicy {
    fn evaluate_queue(
        &mut self,
        agent: &Agent,
        state: &SimulationState,
        current_tick: usize,
        cost_rates: &CostRates,
    ) -> Vec<ReleaseDecision> {
        let mut decisions = Vec::new();

        // Get split friction cost from simulation configuration (read-only, external)
        let split_friction_cost_rate = cost_rates.split_friction_cost;

        for tx_id in agent.outgoing_queue() {
            if let Some(tx) = state.get_transaction(tx_id) {
                // Check if past deadline
                if tx.is_past_deadline(current_tick) {
                    decisions.push(ReleaseDecision::Drop {
                        tx_id: tx_id.to_string(),
                    });
                    continue;
                }

                // Decide if we should split
                if let Some(num_splits) = self.decide_split(
                    tx,
                    agent,
                    current_tick,
                    split_friction_cost_rate,
                ) {
                    // Split transaction
                    decisions.push(ReleaseDecision::SubmitPartial {
                        tx_id: tx_id.to_string(),
                        num_splits,
                    });
                } else {
                    // Check if we can afford to send whole
                    if agent.balance() >= tx.amount() {
                        // Submit whole
                        decisions.push(ReleaseDecision::SubmitFull {
                            tx_id: tx_id.to_string(),
                        });
                    } else {
                        // Hold - can't afford and splitting not beneficial
                        decisions.push(ReleaseDecision::Hold {
                            tx_id: tx_id.to_string(),
                            reason: HoldReason::InsufficientLiquidity,
                        });
                    }
                }
            }
        }

        decisions
    }
}

// Unit tests removed - covered by integration tests in tests/test_transaction_splitting.rs
