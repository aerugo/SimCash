//! Liquidity-Aware Policy
//!
//! Preserves liquidity buffer while prioritizing urgent transactions.
//!
//! # Behavior
//!
//! - Submits transactions only if sufficient liquidity buffer remains
//! - Submits urgent transactions regardless (deadline override)
//! - Holds transactions when liquidity is low
//! - Drops expired transactions
//!
//! # Parameters
//!
//! - `target_buffer`: Minimum balance to maintain (i64 cents)
//! - `urgency_threshold`: Ticks before deadline to override liquidity check (default: 5)
//!
//! # Decision Logic
//!
//! For each transaction:
//! 1. If past deadline → **Drop**
//! 2. If urgent (deadline within threshold) → **Submit** (override liquidity)
//! 3. If sending would violate buffer → **Hold** (await inflows)
//! 4. Otherwise → **Submit**
//!
//! # Use Case
//!
//! - Minimize credit usage (reduce overdraft costs)
//! - Balance liquidity preservation vs. deadline penalties
//! - Realistic strategic behavior (hold non-urgent when low liquidity)

use super::{CashManagerPolicy, HoldReason, ReleaseDecision};
use crate::orchestrator::CostRates;
use crate::{Agent, SimulationState};

/// Liquidity-aware policy: preserve liquidity buffer
///
/// # Example
///
/// ```
/// use payment_simulator_core_rs::policy::{LiquidityAwarePolicy, CashManagerPolicy};
/// use payment_simulator_core_rs::{Agent, SimulationState, Transaction};
///
/// // Policy: keep at least 100k balance
/// let mut policy = LiquidityAwarePolicy::new(100_000);
///
/// // Agent with 200k balance
/// let agent = Agent::new("BANK_A".to_string(), 200_000, 0);
/// let mut state = SimulationState::new(vec![agent.clone()]);
///
/// // Transaction for 150k (would leave only 50k < 100k buffer)
/// let tx = Transaction::new("BANK_A".to_string(), "BANK_B".to_string(), 150_000, 0, 100);
/// let tx_id = tx.id().to_string();
/// state.add_transaction(tx);
/// state.get_agent_mut("BANK_A").unwrap().queue_outgoing(tx_id);
///
/// let agent = state.get_agent("BANK_A").unwrap();
/// let decisions = policy.evaluate_queue(agent, &state, 5);
///
/// // Should hold transaction (preserve buffer)
/// assert_eq!(decisions.len(), 1);
/// assert!(matches!(decisions[0], payment_simulator_core_rs::policy::ReleaseDecision::Hold { .. }));
/// ```
pub struct LiquidityAwarePolicy {
    /// Target minimum balance to maintain (cents)
    target_buffer: i64,

    /// Ticks before deadline to override liquidity check
    urgency_threshold: usize,
}

impl LiquidityAwarePolicy {
    /// Create new liquidity-aware policy
    ///
    /// # Arguments
    ///
    /// * `target_buffer` - Minimum balance to maintain in cents
    ///
    /// # Example
    ///
    /// ```
    /// use payment_simulator_core_rs::policy::LiquidityAwarePolicy;
    ///
    /// // Keep at least $1000 (100,000 cents) as buffer
    /// let policy = LiquidityAwarePolicy::new(100_000);
    /// ```
    pub fn new(target_buffer: i64) -> Self {
        Self {
            target_buffer,
            urgency_threshold: 5, // Default: urgent if deadline within 5 ticks
        }
    }

    /// Create policy with custom urgency threshold
    ///
    /// # Arguments
    ///
    /// * `target_buffer` - Minimum balance to maintain in cents
    /// * `urgency_threshold` - Ticks before deadline to override liquidity check
    pub fn with_urgency_threshold(target_buffer: i64, urgency_threshold: usize) -> Self {
        Self {
            target_buffer,
            urgency_threshold,
        }
    }
}

impl Default for LiquidityAwarePolicy {
    fn default() -> Self {
        Self::new(0) // Default: no buffer requirement
    }
}

impl CashManagerPolicy for LiquidityAwarePolicy {
    fn evaluate_queue(
        &mut self,
        agent: &Agent,
        state: &SimulationState,
        tick: usize,
        _cost_rates: &CostRates,
    ) -> Vec<ReleaseDecision> {
        // Note: cost_rates not used by LiquidityAwarePolicy (decision based on liquidity and urgency)
        let mut decisions = Vec::new();
        let current_balance = agent.balance();

        for tx_id in agent.outgoing_queue() {
            if let Some(tx) = state.get_transaction(tx_id) {
                let amount = tx.remaining_amount();
                let deadline = tx.deadline_tick();

                // Check if expired
                if deadline <= tick {
                    decisions.push(ReleaseDecision::Drop {
                        tx_id: tx_id.clone(),
                    });
                    continue;
                }

                let ticks_remaining = deadline - tick;
                let is_urgent = ticks_remaining <= self.urgency_threshold;

                // Calculate if sending would violate buffer
                // For zero buffer: just check if agent can physically pay (balance + credit)
                // For non-zero buffer: check if balance - amount >= buffer
                let can_send = if self.target_buffer == 0 {
                    agent.can_pay(amount)
                } else {
                    current_balance - amount >= self.target_buffer
                };

                if is_urgent {
                    // Urgent: submit regardless of liquidity (if physically possible)
                    if agent.can_pay(amount) {
                        decisions.push(ReleaseDecision::SubmitFull {
                            tx_id: tx_id.clone(),
                        });
                    } else {
                        // Can't pay even with all liquidity: hold (will likely expire)
                        decisions.push(ReleaseDecision::Hold {
                            tx_id: tx_id.clone(),
                            reason: HoldReason::InsufficientLiquidity,
                        });
                    }
                } else if can_send {
                    // Safe to send: either no buffer requirement or buffer will be maintained
                    decisions.push(ReleaseDecision::SubmitFull {
                        tx_id: tx_id.clone(),
                    });
                } else {
                    // Would violate buffer and not urgent: hold
                    decisions.push(ReleaseDecision::Hold {
                        tx_id: tx_id.clone(),
                        reason: HoldReason::InsufficientLiquidity,
                    });
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
    fn test_liquidity_aware_submits_when_safe() {
        let mut policy = LiquidityAwarePolicy::new(100_000);
        let agent = Agent::new("BANK_A".to_string(), 500_000, 0);
        let mut state = SimulationState::new(vec![agent.clone()]);

        // Transaction for 300k (would leave 200k > 100k buffer)
        let tx = Transaction::new("BANK_A".to_string(), "BANK_B".to_string(), 300_000, 0, 100);
        let tx_id = tx.id().to_string();
        state.add_transaction(tx);
        state.get_agent_mut("BANK_A").unwrap().queue_outgoing(tx_id);

        let agent = state.get_agent("BANK_A").unwrap();
        let cost_rates = create_test_cost_rates();
        let decisions = policy.evaluate_queue(agent, &state, 5, &cost_rates);

        assert_eq!(decisions.len(), 1);
        assert!(matches!(
            decisions[0],
            ReleaseDecision::SubmitFull { .. }
        ));
    }

    #[test]
    fn test_liquidity_aware_holds_when_buffer_violated() {
        let mut policy = LiquidityAwarePolicy::new(100_000);
        let agent = Agent::new("BANK_A".to_string(), 200_000, 0);
        let mut state = SimulationState::new(vec![agent.clone()]);

        // Transaction for 150k (would leave only 50k < 100k buffer)
        let tx = Transaction::new("BANK_A".to_string(), "BANK_B".to_string(), 150_000, 0, 100);
        let tx_id = tx.id().to_string();
        state.add_transaction(tx);
        state.get_agent_mut("BANK_A").unwrap().queue_outgoing(tx_id);

        let agent = state.get_agent("BANK_A").unwrap();
        let cost_rates = create_test_cost_rates();
        let decisions = policy.evaluate_queue(agent, &state, 5, &cost_rates);

        assert_eq!(decisions.len(), 1);
        assert!(matches!(decisions[0], ReleaseDecision::Hold { .. }));
    }

    #[test]
    fn test_liquidity_aware_urgent_overrides_buffer() {
        let mut policy = LiquidityAwarePolicy::new(100_000);
        let agent = Agent::new("BANK_A".to_string(), 200_000, 0);
        let mut state = SimulationState::new(vec![agent.clone()]);

        // Transaction for 150k (would violate buffer)
        // BUT deadline at tick 10, current tick 8 (2 ticks remaining < 5 urgency threshold)
        let tx = Transaction::new("BANK_A".to_string(), "BANK_B".to_string(), 150_000, 0, 10);
        let tx_id = tx.id().to_string();
        state.add_transaction(tx);
        state.get_agent_mut("BANK_A").unwrap().queue_outgoing(tx_id);

        let agent = state.get_agent("BANK_A").unwrap();
        let cost_rates = create_test_cost_rates();
        let decisions = policy.evaluate_queue(agent, &state, 8, &cost_rates);

        assert_eq!(decisions.len(), 1);
        // Should submit despite buffer violation (urgency override)
        assert!(matches!(
            decisions[0],
            ReleaseDecision::SubmitFull { .. }
        ));
    }

    #[test]
    fn test_liquidity_aware_drops_expired() {
        let mut policy = LiquidityAwarePolicy::new(100_000);
        let agent = Agent::new("BANK_A".to_string(), 200_000, 0);
        let mut state = SimulationState::new(vec![agent.clone()]);

        // Transaction past deadline
        let tx = Transaction::new("BANK_A".to_string(), "BANK_B".to_string(), 150_000, 0, 5);
        let tx_id = tx.id().to_string();
        state.add_transaction(tx);
        state.get_agent_mut("BANK_A").unwrap().queue_outgoing(tx_id);

        let agent = state.get_agent("BANK_A").unwrap();
        let cost_rates = create_test_cost_rates();
        let decisions = policy.evaluate_queue(agent, &state, 10, &cost_rates);

        assert_eq!(decisions.len(), 1);
        assert!(matches!(decisions[0], ReleaseDecision::Drop { .. }));
    }

    #[test]
    fn test_liquidity_aware_mixed_scenarios() {
        let mut policy = LiquidityAwarePolicy::new(100_000);
        let agent = Agent::new("BANK_A".to_string(), 300_000, 0);
        let mut state = SimulationState::new(vec![agent.clone()]);

        // tx_safe: 100k (would leave 200k > buffer) → Submit
        let tx_safe = Transaction::new("BANK_A".to_string(), "BANK_B".to_string(), 100_000, 0, 100);
        let id_safe = tx_safe.id().to_string();
        state.add_transaction(tx_safe);

        // tx_violates: 250k (would leave 50k < buffer), not urgent → Hold
        let tx_violates = Transaction::new("BANK_A".to_string(), "BANK_B".to_string(), 250_000, 0, 100);
        let id_violates = tx_violates.id().to_string();
        state.add_transaction(tx_violates);

        // tx_urgent_violates: 250k (violates buffer), but urgent (deadline in 2 ticks) → Submit
        let tx_urgent = Transaction::new("BANK_A".to_string(), "BANK_B".to_string(), 250_000, 0, 7);
        let id_urgent = tx_urgent.id().to_string();
        state.add_transaction(tx_urgent);

        let agent_mut = state.get_agent_mut("BANK_A").unwrap();
        agent_mut.queue_outgoing(id_safe);
        agent_mut.queue_outgoing(id_violates);
        agent_mut.queue_outgoing(id_urgent);

        let agent = state.get_agent("BANK_A").unwrap();
        let cost_rates = create_test_cost_rates();
        let decisions = policy.evaluate_queue(agent, &state, 5, &cost_rates);

        assert_eq!(decisions.len(), 3);

        let submits = decisions
            .iter()
            .filter(|d| matches!(d, ReleaseDecision::SubmitFull { .. }))
            .count();
        let holds = decisions
            .iter()
            .filter(|d| matches!(d, ReleaseDecision::Hold { .. }))
            .count();

        assert_eq!(submits, 2); // tx_safe + tx_urgent_violates
        assert_eq!(holds, 1); // tx_violates
    }

    #[test]
    fn test_liquidity_aware_zero_buffer() {
        // Zero buffer = submit everything (like FIFO)
        let mut policy = LiquidityAwarePolicy::new(0);
        let agent = Agent::new("BANK_A".to_string(), 100_000, 500_000);
        let mut state = SimulationState::new(vec![agent.clone()]);

        // Large transaction (uses all balance + credit)
        let tx = Transaction::new("BANK_A".to_string(), "BANK_B".to_string(), 600_000, 0, 100);
        let tx_id = tx.id().to_string();
        state.add_transaction(tx);
        state.get_agent_mut("BANK_A").unwrap().queue_outgoing(tx_id);

        let agent = state.get_agent("BANK_A").unwrap();
        let cost_rates = create_test_cost_rates();
        let decisions = policy.evaluate_queue(agent, &state, 5, &cost_rates);

        assert_eq!(decisions.len(), 1);
        // Should submit (no buffer requirement)
        assert!(matches!(
            decisions[0],
            ReleaseDecision::SubmitFull { .. }
        ));
    }
}
