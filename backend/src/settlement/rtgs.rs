//! RTGS (Real-Time Gross Settlement) Engine
//!
//! This module implements the core T2-style RTGS settlement logic.
//!
//! # Settlement Flow (T2-style)
//!
//! ```text
//! Client A → Bank A (internal) → RTGS @ Central Bank → Bank B (internal) → Client B
//!                                        ↓
//!                                 Debit Bank A's CB account
//!                                 Credit Bank B's CB account
//! ```
//!
//! The RTGS engine:
//! 1. Receives payment order (Transaction) - submitted by bank to RTGS
//! 2. Checks if sender bank has sufficient liquidity (balance + credit)
//! 3. If yes: Immediate settlement (debit sender, credit receiver)
//! 4. If no: Returns InsufficientLiquidity error (caller queues in Queue 2)
//!
//! # Queue Architecture Note
//!
//! This module operates on **Queue 2** (central RTGS queue):
//! - Transactions arrive here AFTER banks decide to submit them
//! - Settlement is mechanical: check liquidity, settle or queue, retry
//! - Bank policy decisions (Queue 1) will be added in Phase 4-5
//!
//! See `/docs/queue_architecture.md` for the two-queue model.
//!
//! # Critical Invariants
//!
//! - **Atomicity**: Debit and credit happen together, or neither
//! - **Balance Conservation**: Total system balance unchanged
//! - **Credit Limits**: Sender can go negative up to credit_limit
//! - **No Direct Transfer**: Settlement happens at central bank, not peer-to-peer

use crate::models::agent::{Agent, AgentError};
use crate::models::state::SimulationState;
use crate::models::transaction::{Transaction, TransactionError, TransactionStatus};
use thiserror::Error;

/// Errors that can occur during RTGS settlement
#[derive(Debug, Error, PartialEq)]
pub enum SettlementError {
    #[error("Insufficient liquidity: required {required}, available {available}")]
    InsufficientLiquidity { required: i64, available: i64 },

    #[error("Transaction already fully settled")]
    AlreadySettled,

    #[error("Transaction has been dropped")]
    Dropped,

    #[error("Agent error: {0}")]
    AgentError(#[from] AgentError),

    #[error("Transaction error: {0}")]
    TransactionError(#[from] TransactionError),
}

/// Attempt immediate RTGS settlement
///
/// This is the core T2-style settlement operation:
/// 1. Check sender has sufficient liquidity (balance + credit headroom)
/// 2. Debit sender's central bank account
/// 3. Credit receiver's central bank account
/// 4. Mark transaction as settled
///
/// If insufficient liquidity, returns `InsufficientLiquidity` error and **no state changes occur**.
///
/// # Arguments
///
/// * `sender` - Sending bank's agent
/// * `receiver` - Receiving bank's agent
/// * `transaction` - Payment transaction to settle
/// * `tick` - Current simulation tick
///
/// # Returns
///
/// - `Ok(())` if settlement succeeded
/// - `Err(SettlementError)` if settlement failed
///
/// # Example
///
/// ```rust
/// use payment_simulator_core_rs::{Agent, Transaction};
/// use payment_simulator_core_rs::settlement::try_settle;
///
/// let mut sender = Agent::new("BANK_A".to_string(), 1_000_000, 0);
/// let mut receiver = Agent::new("BANK_B".to_string(), 0, 0);
/// let mut transaction = Transaction::new(
///     "BANK_A".to_string(),
///     "BANK_B".to_string(),
///     500_000,
///     0,
///     100,
/// );
///
/// let result = try_settle(&mut sender, &mut receiver, &mut transaction, 5);
/// assert!(result.is_ok());
/// assert_eq!(sender.balance(), 500_000);
/// assert_eq!(receiver.balance(), 500_000);
/// assert!(transaction.is_fully_settled());
/// ```
pub fn try_settle(
    sender: &mut Agent,
    receiver: &mut Agent,
    transaction: &mut Transaction,
    tick: usize,
) -> Result<(), SettlementError> {
    // Validate transaction state
    if transaction.is_fully_settled() {
        return Err(SettlementError::AlreadySettled);
    }

    if matches!(transaction.status(), TransactionStatus::Dropped { .. }) {
        return Err(SettlementError::Dropped);
    }

    let amount = transaction.remaining_amount();

    // Check liquidity (balance + credit headroom)
    if !sender.can_pay(amount) {
        return Err(SettlementError::InsufficientLiquidity {
            required: amount,
            available: sender.available_liquidity(),
        });
    }

    // Execute settlement (atomic operation)
    // If debit fails (shouldn't happen after can_pay check), no credit occurs
    sender.debit(amount)?;
    receiver.credit(amount);
    transaction.settle(amount, tick)?;

    Ok(())
}

/// Result of submitting a transaction to RTGS
#[derive(Debug, PartialEq)]
pub enum SubmissionResult {
    /// Transaction settled immediately
    SettledImmediately { tick: usize },

    /// Transaction queued (insufficient liquidity)
    Queued {
        /// Position in queue (1-indexed)
        position: usize,
    },
}

/// Statistics from processing the RTGS queue
#[derive(Debug, Clone, PartialEq)]
pub struct QueueProcessingResult {
    /// Number of transactions settled this tick
    pub settled_count: usize,

    /// Total value settled (cents)
    pub settled_value: i64,

    /// Number of transactions remaining in queue
    pub remaining_queue_size: usize,

    /// Number of transactions dropped (past deadline)
    pub dropped_count: usize,
}

/// Submit a transaction to RTGS for settlement
///
/// This function attempts immediate settlement. If sender has insufficient liquidity,
/// the transaction is queued for retry on future ticks.
///
/// # Arguments
///
/// * `state` - Simulation state
/// * `transaction` - Transaction to submit
/// * `tick` - Current simulation tick
///
/// # Returns
///
/// - `Ok(SubmissionResult::SettledImmediately)` if settled immediately
/// - `Ok(SubmissionResult::Queued)` if queued due to insufficient liquidity
/// - `Err(SettlementError)` for other errors (invalid agents, etc.)
///
/// # Example
///
/// ```rust
/// use payment_simulator_core_rs::{Agent, Transaction, SimulationState};
/// use payment_simulator_core_rs::settlement::{submit_transaction, SubmissionResult};
///
/// let agents = vec![
///     Agent::new("BANK_A".to_string(), 1_000_000, 0),
///     Agent::new("BANK_B".to_string(), 0, 0),
/// ];
/// let mut state = SimulationState::new(agents);
///
/// let tx = Transaction::new(
///     "BANK_A".to_string(),
///     "BANK_B".to_string(),
///     500_000,
///     0,
///     100,
/// );
///
/// let result = submit_transaction(&mut state, tx, 5);
/// assert!(matches!(result, Ok(SubmissionResult::SettledImmediately { .. })));
/// ```
pub fn submit_transaction(
    state: &mut SimulationState,
    transaction: Transaction,
    tick: usize,
) -> Result<SubmissionResult, SettlementError> {
    let tx_id = transaction.id().to_string();
    let sender_id = transaction.sender_id().to_string();
    let receiver_id = transaction.receiver_id().to_string();
    let amount = transaction.remaining_amount();

    // Add transaction to state
    state.add_transaction(transaction);

    // Check if agents exist
    if !state.agents().contains_key(&sender_id) {
        return Err(SettlementError::AgentError(
            AgentError::InsufficientLiquidity {
                required: 0,
                available: 0,
            },
        ));
    }
    if !state.agents().contains_key(&receiver_id) {
        return Err(SettlementError::AgentError(
            AgentError::InsufficientLiquidity {
                required: 0,
                available: 0,
            },
        ));
    }

    // Check if sender can pay
    let can_pay = {
        let sender = state.get_agent(&sender_id).unwrap();
        sender.can_pay(amount)
    };

    if can_pay {
        // Perform settlement
        {
            let sender = state.get_agent_mut(&sender_id).unwrap();
            sender.debit(amount)?;
        }
        {
            let receiver = state.get_agent_mut(&receiver_id).unwrap();
            receiver.credit(amount);
        }
        {
            let transaction = state.get_transaction_mut(&tx_id).unwrap();
            transaction.settle(amount, tick)?;
        }

        Ok(SubmissionResult::SettledImmediately { tick })
    } else {
        // Queue the transaction
        state.queue_transaction(tx_id);
        let position = state.queue_size();
        Ok(SubmissionResult::Queued { position })
    }
}

/// Process the RTGS queue (retry pending transactions)
///
/// Called each tick to attempt settlement of queued transactions.
/// Uses FIFO ordering - transactions that arrived first are tried first.
///
/// Transactions are:
/// - Settled if sender now has sufficient liquidity
/// - Dropped if past deadline
/// - Re-queued if still insufficient liquidity
///
/// # Arguments
///
/// * `state` - Simulation state
/// * `tick` - Current simulation tick
///
/// # Returns
///
/// Statistics on settlements, drops, and remaining queue size
///
/// # Example
///
/// ```rust
/// use payment_simulator_core_rs::{Agent, Transaction, SimulationState};
/// use payment_simulator_core_rs::settlement::{submit_transaction, process_queue};
///
/// let agents = vec![
///     Agent::new("BANK_A".to_string(), 100_000, 0),  // Insufficient for 500k
///     Agent::new("BANK_B".to_string(), 0, 0),
/// ];
/// let mut state = SimulationState::new(agents);
///
/// let tx = Transaction::new(
///     "BANK_A".to_string(),
///     "BANK_B".to_string(),
///     500_000,
///     0,
///     100,
/// );
///
/// // Submit - will queue
/// submit_transaction(&mut state, tx, 5).unwrap();
///
/// // Add liquidity
/// state.get_agent_mut("BANK_A").unwrap().credit(500_000);
///
/// // Process queue - should settle now
/// let result = process_queue(&mut state, 6);
/// assert_eq!(result.settled_count, 1);
/// assert_eq!(result.remaining_queue_size, 0);
/// ```
pub fn process_queue(state: &mut SimulationState, tick: usize) -> QueueProcessingResult {
    let mut settled_count = 0;
    let mut settled_value = 0i64;
    let mut dropped_count = 0;
    let mut still_pending = Vec::new();

    // Drain queue and process each transaction
    let queue = state.rtgs_queue_mut();
    let tx_ids: Vec<String> = queue.drain(..).collect();

    for tx_id in tx_ids {
        let transaction = state.get_transaction_mut(&tx_id).unwrap();

        // Skip if already settled (defensive check)
        if transaction.is_fully_settled() {
            continue;
        }

        // Check if past deadline → drop
        if transaction.is_past_deadline(tick) {
            transaction.drop_transaction(tick);
            dropped_count += 1;
            continue;
        }

        let sender_id = transaction.sender_id().to_string();
        let receiver_id = transaction.receiver_id().to_string();
        let amount = transaction.remaining_amount();

        // Check if sender can pay
        let can_settle = {
            let sender = state.get_agent(&sender_id).unwrap();
            sender.can_pay(amount)
        };

        if can_settle {
            // Perform settlement
            {
                let sender = state.get_agent_mut(&sender_id).unwrap();
                sender.debit(amount).unwrap();
            }
            {
                let receiver = state.get_agent_mut(&receiver_id).unwrap();
                receiver.credit(amount);
            }
            {
                let transaction = state.get_transaction_mut(&tx_id).unwrap();
                transaction.settle(amount, tick).unwrap();
            }

            settled_count += 1;
            settled_value += amount;
        } else {
            // Still can't settle, re-queue
            still_pending.push(tx_id);
        }
    }

    // Replace queue with still-pending transactions
    *state.rtgs_queue_mut() = still_pending;

    QueueProcessingResult {
        settled_count,
        settled_value,
        remaining_queue_size: state.queue_size(),
        dropped_count,
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn create_agent(id: &str, balance: i64, credit_limit: i64) -> Agent {
        Agent::new(id.to_string(), balance, credit_limit)
    }

    fn create_transaction(
        sender: &str,
        receiver: &str,
        amount: i64,
        arrival: usize,
        deadline: usize,
    ) -> Transaction {
        Transaction::new(
            sender.to_string(),
            receiver.to_string(),
            amount,
            arrival,
            deadline,
        )
    }

    #[test]
    fn test_try_settle_basic() {
        let mut sender = create_agent("A", 1_000_000, 0);
        let mut receiver = create_agent("B", 0, 0);
        let mut tx = create_transaction("A", "B", 500_000, 0, 100);

        let result = try_settle(&mut sender, &mut receiver, &mut tx, 5);

        assert!(result.is_ok());
        assert_eq!(sender.balance(), 500_000);
        assert_eq!(receiver.balance(), 500_000);
        assert!(tx.is_fully_settled());
    }

    #[test]
    fn test_try_settle_with_credit() {
        let mut sender = create_agent("A", 300_000, 500_000);
        let mut receiver = create_agent("B", 0, 0);
        let mut tx = create_transaction("A", "B", 600_000, 0, 100);

        let result = try_settle(&mut sender, &mut receiver, &mut tx, 5);

        assert!(result.is_ok());
        assert_eq!(sender.balance(), -300_000);
        assert!(sender.is_using_credit());
        assert_eq!(receiver.balance(), 600_000);
    }

    #[test]
    fn test_insufficient_liquidity() {
        let mut sender = create_agent("A", 300_000, 500_000);
        let mut receiver = create_agent("B", 0, 0);
        let mut tx = create_transaction("A", "B", 900_000, 0, 100);

        let result = try_settle(&mut sender, &mut receiver, &mut tx, 5);

        assert!(result.is_err());
        assert_eq!(sender.balance(), 300_000); // Unchanged
        assert_eq!(receiver.balance(), 0); // Unchanged
    }
}
