//! FIFO (First-In-First-Out) Policy
//!
//! Simplest baseline policy: submit oldest transaction first.
//!
//! # Behavior
//!
//! - Submits all transactions immediately in queue order
//! - No consideration of liquidity, deadlines, or urgency
//! - Equivalent to Phase 3 behavior (direct submission to RTGS)
//!
//! # Use Case
//!
//! - Baseline for comparison with smarter policies
//! - Replicates "no policy" behavior (immediate submission)
//! - Testing and validation

use super::{CashManagerPolicy, ReleaseDecision};
use crate::orchestrator::CostRates;
use crate::{Agent, SimulationState};

/// FIFO policy: submit all transactions immediately
///
/// # Example
///
/// ```
/// use payment_simulator_core_rs::policy::{FifoPolicy, CashManagerPolicy};
/// use payment_simulator_core_rs::{Agent, SimulationState, Transaction, CostRates};
///
/// let mut policy = FifoPolicy;
/// let mut agent = Agent::new("BANK_A".to_string(), 1_000_000, 0);
/// agent.queue_outgoing("tx_001".to_string());
/// agent.queue_outgoing("tx_002".to_string());
///
/// let state = SimulationState::new(vec![agent.clone()]);
/// let cost_rates = CostRates::default();
/// let decisions = policy.evaluate_queue(&agent, &state, 5, &cost_rates);
///
/// assert_eq!(decisions.len(), 2); // Submit both transactions
/// ```
pub struct FifoPolicy;

impl FifoPolicy {
    /// Create new FIFO policy
    pub fn new() -> Self {
        Self
    }
}

impl Default for FifoPolicy {
    fn default() -> Self {
        Self::new()
    }
}

impl CashManagerPolicy for FifoPolicy {
    fn evaluate_queue(
        &mut self,
        agent: &Agent,
        _state: &SimulationState,
        _tick: usize,
        _cost_rates: &CostRates,
    ) -> Vec<ReleaseDecision> {
        // Submit all transactions in queue order (FIFO)
        // Note: cost_rates not used by FIFO (submits all immediately)
        agent
            .outgoing_queue()
            .iter()
            .map(|tx_id| ReleaseDecision::SubmitFull {
                tx_id: tx_id.clone(),
            })
            .collect()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn create_test_cost_rates() -> CostRates {
        CostRates {
            overdraft_bps_per_tick: 0.0001,
            delay_cost_per_tick_per_cent: 0.00001,
            eod_penalty_per_transaction: 10000,
            deadline_penalty: 5000,
            split_friction_cost: 1000,
        }
    }

    #[test]
    fn test_fifo_submits_all() {
        let mut policy = FifoPolicy::new();
        let mut agent = Agent::new("BANK_A".to_string(), 1_000_000, 0);

        agent.queue_outgoing("tx_001".to_string());
        agent.queue_outgoing("tx_002".to_string());
        agent.queue_outgoing("tx_003".to_string());

        let state = SimulationState::new(vec![agent.clone()]);
        let cost_rates = create_test_cost_rates();
        let decisions = policy.evaluate_queue(&agent, &state, 5, &cost_rates);

        assert_eq!(decisions.len(), 3);
        assert!(matches!(
            decisions[0],
            ReleaseDecision::SubmitFull { .. }
        ));
        assert!(matches!(
            decisions[1],
            ReleaseDecision::SubmitFull { .. }
        ));
        assert!(matches!(
            decisions[2],
            ReleaseDecision::SubmitFull { .. }
        ));
    }

    #[test]
    fn test_fifo_empty_queue() {
        let mut policy = FifoPolicy::new();
        let agent = Agent::new("BANK_A".to_string(), 1_000_000, 0);

        let state = SimulationState::new(vec![agent.clone()]);
        let cost_rates = create_test_cost_rates();
        let decisions = policy.evaluate_queue(&agent, &state, 5, &cost_rates);

        assert_eq!(decisions.len(), 0);
    }
}
