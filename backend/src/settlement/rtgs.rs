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
use crate::models::transaction::{Transaction, TransactionError};
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
/// let mut sender = Agent::new("BANK_A".to_string(), 1_000_000);
/// let mut receiver = Agent::new("BANK_B".to_string(), 0);
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

    // NOTE: Removed check for Dropped status - overdue transactions can still settle
    // In real payment systems, all obligations must eventually be settled

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

/// Details of a transaction that settled from Queue 2 (RTGS queue)
#[derive(Debug, Clone, PartialEq)]
pub struct SettledTransactionDetail {
    pub tx_id: String,
    pub sender_id: String,
    pub receiver_id: String,
    pub amount: i64,
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
    /// DEPRECATED: Always 0 - transactions are now marked overdue, not dropped
    #[deprecated(note = "Transactions are now marked overdue, not dropped")]
    pub dropped_count: usize,

    /// Number of transactions newly marked overdue this tick
    pub overdue_count: usize,

    /// Details of transactions that settled from Queue 2 this tick
    /// Added to support event emission for Queue 2 settlements (Issue #2)
    pub settled_transactions: Vec<SettledTransactionDetail>,
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
///     Agent::new("BANK_A".to_string(), 1_000_000),
///     Agent::new("BANK_B".to_string(), 0),
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

    // Check if sender can pay (liquidity)
    let can_pay = {
        let sender = state.get_agent(&sender_id).unwrap();
        sender.can_pay(amount)
    };

    // Check bilateral and multilateral limits (Phase 1 TARGET2 LSM)
    let (bilateral_ok, multilateral_ok) = {
        let sender = state.get_agent(&sender_id).unwrap();
        let (bilateral_ok, _, _) = sender.check_bilateral_limit(&receiver_id, amount);
        let (multilateral_ok, _, _) = sender.check_multilateral_limit(amount);
        (bilateral_ok, multilateral_ok)
    };

    if can_pay && bilateral_ok && multilateral_ok {
        // Perform settlement
        {
            let sender = state.get_agent_mut(&sender_id).unwrap();
            sender.debit(amount)?;
            // Record outflow for bilateral/multilateral limit tracking
            sender.record_outflow(&receiver_id, amount);
        }
        {
            let receiver = state.get_agent_mut(&receiver_id).unwrap();
            receiver.credit(amount);
        }

        // Get parent_id before settling (need to read before mut borrow)
        let parent_id = {
            let transaction = state.get_transaction(&tx_id).unwrap();
            transaction.parent_id().map(|s| s.to_string())
        };

        {
            let transaction = state.get_transaction_mut(&tx_id).unwrap();
            transaction.settle(amount, tick)?;
        }

        // If this is a child transaction, update parent's remaining_amount
        if let Some(parent_id) = parent_id {
            let parent = state.get_transaction_mut(&parent_id).unwrap();
            parent.reduce_remaining_for_child(amount)?;

            // If parent now fully settled, mark it as settled
            if parent.remaining_amount() == 0 {
                parent.mark_fully_settled(tick)?;
            }
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
///     Agent::new("BANK_A".to_string(), 100_000),  // Insufficient for 500k
///     Agent::new("BANK_B".to_string(), 0),
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
    // Call with no deferred credits (immediate crediting mode)
    process_queue_with_deferred(state, tick, None)
}

/// Process Queue 2 with optional deferred crediting.
///
/// Same as `process_queue`, but accepts an optional `DeferredCredits` accumulator.
/// When provided, credits are accumulated instead of applied immediately.
/// This supports Castro et al. (2025) compatible deferred crediting mode.
///
/// # Arguments
///
/// * `state` - The simulation state
/// * `tick` - Current tick number
/// * `deferred_credits` - Optional accumulator for deferred credits (Castro mode)
pub fn process_queue_with_deferred(
    state: &mut SimulationState,
    tick: usize,
    mut deferred_credits: Option<&mut super::deferred::DeferredCredits>,
) -> QueueProcessingResult {
    let mut settled_count = 0;
    let mut settled_value = 0i64;
    let mut overdue_count = 0; // NEW: Count newly overdue transactions
    let mut still_pending = Vec::new();
    let mut settled_transactions = Vec::new(); // Track settled tx details for event emission

    // Drain queue and process each transaction
    let queue = state.rtgs_queue_mut();
    let tx_ids: Vec<String> = queue.drain(..).collect();

    for tx_id in tx_ids {
        let transaction = state.get_transaction_mut(&tx_id).unwrap();

        // Skip if already settled (defensive check)
        if transaction.is_fully_settled() {
            continue;
        }

        // CRITICAL: System automatically marks overdue (not policy-driven!)
        // This must happen here because Queue 2 has NO policy
        if transaction.is_past_deadline(tick) && !transaction.is_overdue() {
            transaction.mark_overdue(tick).ok(); // Ignore errors (defensive)
            overdue_count += 1;
            // One-time penalty will be charged in orchestrator cost calculation
        }

        // Attempt settlement (regardless of overdue status)
        let sender_id = transaction.sender_id().to_string();
        let receiver_id = transaction.receiver_id().to_string();
        let amount = transaction.remaining_amount();

        // Check if sender can pay (liquidity)
        let can_pay = {
            let sender = state.get_agent(&sender_id).unwrap();
            sender.can_pay(amount)
        };

        // Check bilateral and multilateral limits (Phase 1 TARGET2 LSM)
        let (bilateral_ok, multilateral_ok) = {
            let sender = state.get_agent(&sender_id).unwrap();
            let (bilateral_ok, _, _) = sender.check_bilateral_limit(&receiver_id, amount);
            let (multilateral_ok, _, _) = sender.check_multilateral_limit(amount);
            (bilateral_ok, multilateral_ok)
        };

        if can_pay && bilateral_ok && multilateral_ok {
            // Perform settlement
            {
                let sender = state.get_agent_mut(&sender_id).unwrap();
                sender.debit(amount).unwrap();
                // Record outflow for bilateral/multilateral limit tracking
                sender.record_outflow(&receiver_id, amount);
            }

            // Credit handling: immediate or deferred based on mode
            match deferred_credits {
                Some(ref mut dc) => {
                    // Deferred mode: accumulate credit
                    dc.accumulate(&receiver_id, amount, &tx_id);
                }
                None => {
                    // Immediate mode: credit directly
                    let receiver = state.get_agent_mut(&receiver_id).unwrap();
                    receiver.credit(amount);
                }
            }

            // Get parent_id before settling (need to read before mut borrow)
            let parent_id = {
                let transaction = state.get_transaction(&tx_id).unwrap();
                transaction.parent_id().map(|s| s.to_string())
            };

            {
                let transaction = state.get_transaction_mut(&tx_id).unwrap();
                transaction.settle(amount, tick).unwrap();
            }

            // If this is a child transaction, update parent's remaining_amount
            if let Some(parent_id) = parent_id {
                let parent = state.get_transaction_mut(&parent_id).unwrap();
                parent.reduce_remaining_for_child(amount).ok(); // Defensive - ignore errors

                // If parent now fully settled, mark it as settled
                if parent.remaining_amount() == 0 {
                    parent.mark_fully_settled(tick).ok(); // Defensive - ignore errors
                }
            }

            settled_count += 1;
            settled_value += amount;

            // Collect settlement details for event emission (Issue #2 fix)
            settled_transactions.push(SettledTransactionDetail {
                tx_id: tx_id.clone(),
                sender_id: sender_id.clone(),
                receiver_id: receiver_id.clone(),
                amount,
            });
        } else {
            // Still can't settle, re-queue (even if overdue)
            still_pending.push(tx_id.clone());
        }
    }

    // Replace queue with still-pending transactions
    *state.rtgs_queue_mut() = still_pending;

    #[allow(deprecated)] // Still need to populate for API compatibility
    QueueProcessingResult {
        settled_count,
        settled_value,
        remaining_queue_size: state.queue_size(),
        dropped_count: 0, // Deprecated - always 0
        overdue_count,
        settled_transactions, // Issue #2 fix: Return details for event emission
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn create_agent(id: &str, balance: i64, unsecured_cap: i64) -> Agent {
        let mut agent = Agent::new(id.to_string(), balance);
        agent.set_unsecured_cap(unsecured_cap);
        agent
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

    // ==========================================
    // Phase 2: Overdue Transaction Tests (RTGS)
    // ==========================================

    #[test]
    fn test_try_settle_accepts_overdue_transactions() {
        let mut sender = create_agent("A", 1_000_000, 0);
        let mut receiver = create_agent("B", 0, 0);
        let mut tx = create_transaction("A", "B", 500_000, 0, 50);

        // Mark overdue
        tx.mark_overdue(51).unwrap();

        // Should settle successfully
        let result = try_settle(&mut sender, &mut receiver, &mut tx, 55);

        assert!(result.is_ok());
        assert!(tx.is_fully_settled());
        assert_eq!(sender.balance(), 500_000);
        assert_eq!(receiver.balance(), 500_000);
    }

    #[test]
    fn test_overdue_transactions_remain_in_queue() {
        let agents = vec![
            create_agent("BANK_A", 100_000, 0), // Insufficient
            create_agent("BANK_B", 0, 0),
        ];
        let mut state = SimulationState::new(agents);

        let tx = create_transaction("BANK_A", "BANK_B", 500_000, 0, 50);
        submit_transaction(&mut state, tx, 5).unwrap();

        // Process at tick 51 (past deadline)
        let result = process_queue(&mut state, 51);

        // Old behavior: dropped_count = 1, remaining_queue_size = 0
        // New behavior: transaction marked overdue but stays in queue
        assert_eq!(result.overdue_count, 1); // New metric
        assert_eq!(result.remaining_queue_size, 1);

        // Transaction should be overdue but still in queue
        let tx = state.transactions().values().next().unwrap();
        assert!(tx.is_overdue());
        assert_eq!(tx.overdue_since_tick(), Some(51));
    }

    #[test]
    fn test_overdue_transaction_settles_when_liquidity_arrives() {
        let agents = vec![
            create_agent("BANK_A", 100_000, 0),
            create_agent("BANK_B", 0, 0),
        ];
        let mut state = SimulationState::new(agents);

        let tx = create_transaction("BANK_A", "BANK_B", 500_000, 0, 50);
        submit_transaction(&mut state, tx, 5).unwrap();

        // Tick 51: Past deadline, becomes overdue
        process_queue(&mut state, 51);

        // Verify overdue but still in queue
        assert_eq!(state.queue_size(), 1);
        let tx = state.transactions().values().next().unwrap();
        assert!(tx.is_overdue());

        // Add liquidity
        state.get_agent_mut("BANK_A").unwrap().credit(500_000);

        // Tick 52: Should settle despite being overdue
        let result = process_queue(&mut state, 52);

        assert_eq!(result.settled_count, 1);
        assert_eq!(result.remaining_queue_size, 0);

        let tx = state.transactions().values().next().unwrap();
        assert!(tx.is_fully_settled());
    }

    #[test]
    fn test_system_enforces_overdue_without_policy() {
        // This test verifies the CRITICAL design decision:
        // The system marks transactions overdue automatically,
        // not relying on policy (which doesn't exist in Queue 2)

        let agents = vec![
            create_agent("BANK_A", 0, 0), // No liquidity
            create_agent("BANK_B", 0, 0),
        ];
        let mut state = SimulationState::new(agents);

        let tx = create_transaction("BANK_A", "BANK_B", 100_000, 0, 50);
        submit_transaction(&mut state, tx, 5).unwrap();

        // Process through deadline - NO POLICY INVOLVED
        for tick in 6..=55 {
            process_queue(&mut state, tick);
        }

        // Transaction should be overdue (system-enforced)
        let tx = state.transactions().values().next().unwrap();
        assert!(tx.is_overdue());
        assert_eq!(tx.overdue_since_tick(), Some(51));
    }
}
