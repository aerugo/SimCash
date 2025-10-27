//! Deadline-Aware Policy
//!
//! Prioritizes transactions approaching their deadline.
//!
//! # Behavior
//!
//! - Submits transactions within `urgency_threshold` ticks of deadline
//! - Holds transactions with time remaining (non-urgent)
//! - Drops transactions past deadline (already expired)
//!
//! # Parameters
//!
//! - `urgency_threshold`: Ticks before deadline to consider urgent (default: 5)
//!
//! # Use Case
//!
//! - Minimize SLA violations (deadline penalties)
//! - Balance urgency vs. liquidity preservation
//! - Realistic cash manager behavior (urgent items first)

use super::{CashManagerPolicy, HoldReason, ReleaseDecision};
use crate::{Agent, SimulationState};

/// Deadline-aware policy: prioritize expiring transactions
///
/// # Example
///
/// ```
/// use payment_simulator_core_rs::policy::{DeadlinePolicy, CashManagerPolicy};
/// use payment_simulator_core_rs::{Agent, SimulationState, Transaction};
///
/// let mut policy = DeadlinePolicy::new(5); // Urgent if deadline within 5 ticks
/// let agent = Agent::new("BANK_A".to_string(), 1_000_000, 0);
/// let mut state = SimulationState::new(vec![agent.clone()]);
///
/// // tx_urgent: deadline at tick 10 (urgent at tick 8: 10 - 8 = 2 < 5)
/// let tx_urgent = Transaction::new("BANK_A".to_string(), "BANK_B".to_string(), 100_000, 0, 10);
/// let id_urgent = tx_urgent.id().to_string();
/// state.add_transaction(tx_urgent);
///
/// // tx_later: deadline at tick 50 (not urgent at tick 8: 50 - 8 = 42 > 5)
/// let tx_later = Transaction::new("BANK_A".to_string(), "BANK_B".to_string(), 200_000, 0, 50);
/// let id_later = tx_later.id().to_string();
/// state.add_transaction(tx_later);
///
/// // Queue transactions
/// state.get_agent_mut("BANK_A").unwrap().queue_outgoing(id_urgent);
/// state.get_agent_mut("BANK_A").unwrap().queue_outgoing(id_later);
///
/// let agent = state.get_agent("BANK_A").unwrap();
/// let decisions = policy.evaluate_queue(agent, &state, 8);
///
/// // Should submit urgent, hold non-urgent
/// assert_eq!(decisions.len(), 2);
/// ```
pub struct DeadlinePolicy {
    /// Ticks before deadline to consider transaction urgent
    urgency_threshold: usize,
}

impl DeadlinePolicy {
    /// Create new deadline policy
    ///
    /// # Arguments
    ///
    /// * `urgency_threshold` - Ticks before deadline to consider urgent
    ///
    /// # Example
    ///
    /// ```
    /// use payment_simulator_core_rs::policy::DeadlinePolicy;
    ///
    /// let policy = DeadlinePolicy::new(10); // Urgent if deadline within 10 ticks
    /// ```
    pub fn new(urgency_threshold: usize) -> Self {
        Self { urgency_threshold }
    }
}

impl Default for DeadlinePolicy {
    fn default() -> Self {
        Self::new(5) // Default: urgent if deadline within 5 ticks
    }
}

impl CashManagerPolicy for DeadlinePolicy {
    fn evaluate_queue(
        &mut self,
        agent: &Agent,
        state: &SimulationState,
        tick: usize,
    ) -> Vec<ReleaseDecision> {
        let mut decisions = Vec::new();

        for tx_id in agent.outgoing_queue() {
            if let Some(tx) = state.get_transaction(tx_id) {
                let deadline = tx.deadline_tick();

                if deadline <= tick {
                    // Already past deadline: drop
                    decisions.push(ReleaseDecision::Drop {
                        tx_id: tx_id.clone(),
                    });
                } else {
                    let ticks_remaining = deadline - tick;

                    if ticks_remaining <= self.urgency_threshold {
                        // Urgent: submit immediately
                        decisions.push(ReleaseDecision::SubmitFull {
                            tx_id: tx_id.clone(),
                        });
                    } else {
                        // Not urgent: hold for later
                        decisions.push(ReleaseDecision::Hold {
                            tx_id: tx_id.clone(),
                            reason: HoldReason::NearDeadline { ticks_remaining },
                        });
                    }
                }
            }
        }

        decisions
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::Transaction;

    #[test]
    fn test_deadline_submits_urgent() {
        let mut policy = DeadlinePolicy::new(5);
        let agent = Agent::new("BANK_A".to_string(), 1_000_000, 0);
        let mut state = SimulationState::new(vec![agent.clone()]);

        // Create and add transaction
        // Deadline at tick 10, current tick 8: 10 - 8 = 2 ticks remaining (< 5)
        let tx = Transaction::new("BANK_A".to_string(), "BANK_B".to_string(), 100_000, 0, 10);
        let tx_id = tx.id().to_string();
        state.add_transaction(tx);

        // Queue transaction in agent
        state.get_agent_mut("BANK_A").unwrap().queue_outgoing(tx_id);

        let agent = state.get_agent("BANK_A").unwrap();
        let decisions = policy.evaluate_queue(agent, &state, 8);

        assert_eq!(decisions.len(), 1);
        assert!(matches!(
            decisions[0],
            ReleaseDecision::SubmitFull { .. }
        ));
    }

    #[test]
    fn test_deadline_holds_non_urgent() {
        let mut policy = DeadlinePolicy::new(5);
        let agent = Agent::new("BANK_A".to_string(), 1_000_000, 0);
        let mut state = SimulationState::new(vec![agent.clone()]);

        // Deadline at tick 50, current tick 8: 50 - 8 = 42 ticks remaining (> 5)
        let tx = Transaction::new("BANK_A".to_string(), "BANK_B".to_string(), 100_000, 0, 50);
        let tx_id = tx.id().to_string();
        state.add_transaction(tx);
        state.get_agent_mut("BANK_A").unwrap().queue_outgoing(tx_id);

        let agent = state.get_agent("BANK_A").unwrap();
        let decisions = policy.evaluate_queue(agent, &state, 8);

        assert_eq!(decisions.len(), 1);
        assert!(matches!(decisions[0], ReleaseDecision::Hold { .. }));
    }

    #[test]
    fn test_deadline_drops_expired() {
        let mut policy = DeadlinePolicy::new(5);
        let agent = Agent::new("BANK_A".to_string(), 1_000_000, 0);
        let mut state = SimulationState::new(vec![agent.clone()]);

        // Deadline at tick 5, current tick 10: already expired
        let tx = Transaction::new("BANK_A".to_string(), "BANK_B".to_string(), 100_000, 0, 5);
        let tx_id = tx.id().to_string();
        state.add_transaction(tx);
        state.get_agent_mut("BANK_A").unwrap().queue_outgoing(tx_id);

        let agent = state.get_agent("BANK_A").unwrap();
        let decisions = policy.evaluate_queue(agent, &state, 10);

        assert_eq!(decisions.len(), 1);
        assert!(matches!(decisions[0], ReleaseDecision::Drop { .. }));
    }

    #[test]
    fn test_deadline_mixed_urgencies() {
        let mut policy = DeadlinePolicy::new(5);
        let agent = Agent::new("BANK_A".to_string(), 1_000_000, 0);
        let mut state = SimulationState::new(vec![agent.clone()]);

        let tx_urgent = Transaction::new("BANK_A".to_string(), "BANK_B".to_string(), 100_000, 0, 10);
        let tx_later = Transaction::new("BANK_A".to_string(), "BANK_B".to_string(), 200_000, 0, 50);
        let tx_expired = Transaction::new("BANK_A".to_string(), "BANK_B".to_string(), 300_000, 0, 5);

        let id_urgent = tx_urgent.id().to_string();
        let id_later = tx_later.id().to_string();
        let id_expired = tx_expired.id().to_string();

        state.add_transaction(tx_urgent);
        state.add_transaction(tx_later);
        state.add_transaction(tx_expired);

        let agent_mut = state.get_agent_mut("BANK_A").unwrap();
        agent_mut.queue_outgoing(id_urgent);
        agent_mut.queue_outgoing(id_later);
        agent_mut.queue_outgoing(id_expired);

        let agent = state.get_agent("BANK_A").unwrap();
        let decisions = policy.evaluate_queue(agent, &state, 8);

        assert_eq!(decisions.len(), 3);

        // Should have 1 submit (urgent), 1 hold (later), 1 drop (expired)
        let submits = decisions
            .iter()
            .filter(|d| matches!(d, ReleaseDecision::SubmitFull { .. }))
            .count();
        let holds = decisions
            .iter()
            .filter(|d| matches!(d, ReleaseDecision::Hold { .. }))
            .count();
        let drops = decisions
            .iter()
            .filter(|d| matches!(d, ReleaseDecision::Drop { .. }))
            .count();

        assert_eq!(submits, 1);
        assert_eq!(holds, 1);
        assert_eq!(drops, 1);
    }
}
