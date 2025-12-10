//! Deferred Crediting Module
//!
//! Implements deferred crediting mode where credits are accumulated during
//! a tick and applied at the end.
//!
//! # Overview
//!
//! In standard RTGS, when a payment settles, the receiver's balance is credited
//! immediately. This allows "within-tick recycling" where incoming payments
//! become available for outgoing payments in the same tick.
//!
//! In deferred crediting mode, incoming payments R_t only become available in period t+1.
//! This module implements that behavior by:
//! 1. Accumulating credits during tick processing
//! 2. Applying all credits atomically at end of tick
//!
//! # Usage
//!
//! ```rust
//! use payment_simulator_core_rs::settlement::deferred::DeferredCredits;
//!
//! let mut dc = DeferredCredits::new();
//!
//! // During settlement, accumulate credits
//! dc.accumulate("BANK_B", 100_000, "tx_001");
//! dc.accumulate("BANK_B", 50_000, "tx_002");
//! dc.accumulate("BANK_C", 75_000, "tx_003");
//!
//! // At end of tick, apply all credits
//! // let events = dc.apply_all(&mut state, tick);
//! ```

use crate::models::event::Event;
use crate::models::state::SimulationState;
use std::collections::BTreeMap;

/// Accumulator for deferred credits during a tick.
///
/// Credits are accumulated as settlements occur, then applied atomically
/// at the end of the tick. This prevents "within-tick recycling" where
/// incoming payments become immediately available for outgoing payments.
#[derive(Debug, Default)]
pub struct DeferredCredits {
    /// Pending credits per agent: agent_id -> (total_amount, source_transaction_ids)
    ///
    /// Uses BTreeMap for deterministic iteration order (sorted by agent_id)
    pending: BTreeMap<String, (i64, Vec<String>)>,
}

impl DeferredCredits {
    /// Create a new empty accumulator.
    pub fn new() -> Self {
        Self {
            pending: BTreeMap::new(),
        }
    }

    /// Accumulate a credit for an agent.
    ///
    /// # Arguments
    ///
    /// * `agent_id` - The agent receiving the credit
    /// * `amount` - The credit amount (in cents, always positive)
    /// * `tx_id` - The source transaction ID for traceability
    pub fn accumulate(&mut self, agent_id: &str, amount: i64, tx_id: &str) {
        let entry = self
            .pending
            .entry(agent_id.to_string())
            .or_insert((0, Vec::new()));
        // Use saturating_add to prevent overflow
        entry.0 = entry.0.saturating_add(amount);
        entry.1.push(tx_id.to_string());
    }

    /// Check if the accumulator is empty.
    pub fn is_empty(&self) -> bool {
        self.pending.is_empty()
    }

    /// Get the total pending credit for an agent.
    ///
    /// Returns 0 if the agent has no pending credits.
    pub fn total_for_agent(&self, agent_id: &str) -> i64 {
        self.pending.get(agent_id).map(|(amt, _)| *amt).unwrap_or(0)
    }

    /// Apply all accumulated credits to agents.
    ///
    /// Credits are applied in sorted agent_id order for determinism.
    /// After application, the accumulator is cleared.
    ///
    /// # Arguments
    ///
    /// * `state` - The simulation state containing agents
    /// * `tick` - The current tick (for event timestamps)
    ///
    /// # Returns
    ///
    /// A vector of DeferredCreditApplied events, one per agent that received credits.
    pub fn apply_all(&mut self, state: &mut SimulationState, tick: usize) -> Vec<Event> {
        let mut events = Vec::new();

        // Extract keys to iterate in sorted order (BTreeMap guarantees this)
        // We need to collect keys first to avoid borrowing issues
        let agent_ids: Vec<String> = self.pending.keys().cloned().collect();

        for agent_id in agent_ids {
            if let Some((amount, tx_ids)) = self.pending.remove(&agent_id) {
                if let Some(agent) = state.get_agent_mut(&agent_id) {
                    // Apply the credit
                    agent.credit(amount);

                    // Create event for this credit application
                    events.push(Event::DeferredCreditApplied {
                        tick,
                        agent_id: agent_id.clone(),
                        amount,
                        source_transactions: tx_ids,
                    });
                }
            }
        }

        // Clear should be redundant (we removed all entries), but be explicit
        self.pending.clear();

        events
    }

    /// Clear all pending credits without applying them.
    ///
    /// This is typically only used in error handling scenarios.
    pub fn clear(&mut self) {
        self.pending.clear();
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_new_is_empty() {
        let dc = DeferredCredits::new();
        assert!(dc.is_empty());
    }

    #[test]
    fn test_accumulate_single() {
        let mut dc = DeferredCredits::new();
        dc.accumulate("BANK_A", 100_000, "tx_001");

        assert!(!dc.is_empty());
        assert_eq!(dc.total_for_agent("BANK_A"), 100_000);
    }

    #[test]
    fn test_accumulate_multiple_same_agent() {
        let mut dc = DeferredCredits::new();
        dc.accumulate("BANK_A", 100_000, "tx_001");
        dc.accumulate("BANK_A", 50_000, "tx_002");
        dc.accumulate("BANK_A", 25_000, "tx_003");

        assert_eq!(dc.total_for_agent("BANK_A"), 175_000);
    }

    #[test]
    fn test_accumulate_multiple_agents() {
        let mut dc = DeferredCredits::new();
        dc.accumulate("BANK_C", 300_000, "tx_003");
        dc.accumulate("BANK_A", 100_000, "tx_001");
        dc.accumulate("BANK_B", 200_000, "tx_002");

        assert_eq!(dc.total_for_agent("BANK_A"), 100_000);
        assert_eq!(dc.total_for_agent("BANK_B"), 200_000);
        assert_eq!(dc.total_for_agent("BANK_C"), 300_000);
    }

    #[test]
    fn test_total_for_unknown_agent() {
        let dc = DeferredCredits::new();
        assert_eq!(dc.total_for_agent("UNKNOWN"), 0);
    }

    #[test]
    fn test_clear() {
        let mut dc = DeferredCredits::new();
        dc.accumulate("BANK_A", 100_000, "tx_001");
        dc.accumulate("BANK_B", 200_000, "tx_002");

        dc.clear();

        assert!(dc.is_empty());
        assert_eq!(dc.total_for_agent("BANK_A"), 0);
        assert_eq!(dc.total_for_agent("BANK_B"), 0);
    }
}
