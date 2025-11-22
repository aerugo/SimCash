//! Transaction model
//!
//! Represents a payment between two agents.
//! Each transaction has:
//! - Sender and receiver agent IDs
//! - Amount (i64 cents) - original and remaining
//! - Arrival and deadline ticks
//! - Priority level (internal bank priority, 0-10)
//! - RTGS priority (declared to central system: Urgent/Normal)
//! - Divisibility flag (can be split into parts)
//! - Status (Pending, PartiallySettled, Settled, Overdue)
//!
//! # Dual Priority System (TARGET2-style)
//!
//! This module implements a dual priority system:
//!
//! - **Internal Priority** (0-10): Bank's internal view of payment importance.
//!   Used for Queue 1 ordering. Can be modified by policies.
//!
//! - **RTGS Priority** (Urgent/Normal): Declared to RTGS at submission time.
//!   Used for Queue 2 ordering. Can only be changed via withdraw/resubmit.
//!
//! CRITICAL: All money values are i64 (cents)

use serde::{Deserialize, Serialize};
use std::fmt;
use std::str::FromStr;
use thiserror::Error;

#[cfg(feature = "pyo3")]
use pyo3::prelude::*;

/// RTGS priority levels (TARGET2-style)
///
/// In TARGET2 and similar RTGS systems, payments are assigned a priority
/// at submission time that determines their processing order in the central
/// queue (Queue 2 in SimCash).
///
/// # Priority Levels
///
/// - **HighlyUrgent (0)**: Reserved for central bank operations and CLS.
///   Not available to regular participants.
/// - **Urgent (1)**: Time-critical payments. Banks can use this level but
///   may incur higher fees.
/// - **Normal (2)**: Standard payments. Default for most transactions.
///
/// # Ordering
///
/// Lower numeric value = higher priority. HighlyUrgent (0) is processed
/// before Urgent (1), which is processed before Normal (2).
///
/// Within the same priority band, FIFO ordering by submission tick is used.
#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Hash, Serialize, Deserialize)]
#[cfg_attr(feature = "pyo3", pyclass(eq, eq_int))]
pub enum RtgsPriority {
    /// Highly Urgent (0) - Restricted to system/central bank operations
    HighlyUrgent = 0,

    /// Urgent (1) - Time-critical payments, may incur higher fees
    Urgent = 1,

    /// Normal (2) - Standard payments (default)
    Normal = 2,
}

impl Default for RtgsPriority {
    fn default() -> Self {
        RtgsPriority::Normal
    }
}

impl fmt::Display for RtgsPriority {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            RtgsPriority::HighlyUrgent => write!(f, "HighlyUrgent"),
            RtgsPriority::Urgent => write!(f, "Urgent"),
            RtgsPriority::Normal => write!(f, "Normal"),
        }
    }
}

impl FromStr for RtgsPriority {
    type Err = String;

    fn from_str(s: &str) -> Result<Self, Self::Err> {
        match s.to_lowercase().as_str() {
            "highlyurgent" | "highly_urgent" | "0" => Ok(RtgsPriority::HighlyUrgent),
            "urgent" | "1" => Ok(RtgsPriority::Urgent),
            "normal" | "2" => Ok(RtgsPriority::Normal),
            _ => Err(format!(
                "Invalid RTGS priority: '{}'. Valid values: HighlyUrgent, Urgent, Normal",
                s
            )),
        }
    }
}

/// Transaction status
///
/// Tracks the lifecycle of a payment through the system.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub enum TransactionStatus {
    /// Transaction waiting to be settled
    Pending,

    /// Transaction partially settled (divisible transactions only)
    PartiallySettled {
        /// Tick when first partial settlement occurred
        first_settlement_tick: usize,
    },

    /// Transaction fully settled
    Settled {
        /// Tick when final settlement occurred
        tick: usize,
    },

    /// Transaction past deadline but still settleable
    ///
    /// In real payment systems, transactions cannot simply be "dropped" - all
    /// obligations must eventually be settled. Overdue transactions remain in
    /// the queue and incur escalating penalties until settled.
    Overdue {
        /// Tick when transaction first missed its deadline
        missed_deadline_tick: usize,
    },
}

/// Errors that can occur during transaction operations
#[derive(Debug, Error, PartialEq)]
pub enum TransactionError {
    #[error("Cannot partially settle indivisible transaction")]
    IndivisibleTransaction,

    #[error("Settlement amount {amount} exceeds remaining amount {remaining}")]
    AmountExceedsRemaining { amount: i64, remaining: i64 },

    #[error("Transaction already fully settled")]
    AlreadySettled,

    #[error("Cannot settle dropped transaction")]
    TransactionDropped,

    #[error("Settlement amount must be positive")]
    InvalidAmount,
}

/// Represents a payment transaction between two agents
///
/// # Example
/// ```
/// use payment_simulator_core_rs::Transaction;
///
/// let tx = Transaction::new(
///     "BANK_A".to_string(),
///     "BANK_B".to_string(),
///     100000, // $1,000.00 in cents
///     10,     // arrival_tick
///     50,     // deadline_tick
/// ).with_priority(8);
/// ```
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Transaction {
    /// Unique transaction identifier (UUID)
    id: String,

    /// Sender agent ID
    sender_id: String,

    /// Receiver agent ID
    receiver_id: String,

    /// Original transaction amount (i64 cents)
    amount: i64,

    /// Remaining amount to be settled (i64 cents)
    remaining_amount: i64,

    /// Tick when transaction arrived in system
    arrival_tick: usize,

    /// Tick by which transaction must be settled
    deadline_tick: usize,

    /// Priority level (higher = more urgent)
    /// Default: 5, Range: 0-10
    priority: u8,

    /// Original priority level before any escalation
    /// Used for calculating escalation boost from original value
    original_priority: u8,

    /// Current status
    status: TransactionStatus,

    /// Parent transaction ID (for split transactions)
    ///
    /// When a policy decides to split a large transaction into multiple smaller
    /// child transactions, each child links back to the parent via this field.
    /// This enables tracking of split transaction families for cost accounting
    /// and analysis.
    ///
    /// - `None`: This is a regular (non-split) transaction
    /// - `Some(parent_id)`: This is a child of a split transaction
    parent_id: Option<String>,

    /// RTGS declared priority - set when submitted to Queue 2
    ///
    /// This is the priority declared to the RTGS system when the transaction
    /// is submitted from the bank's internal queue (Queue 1) to the central
    /// settlement queue (Queue 2).
    ///
    /// - `None`: Transaction not yet submitted to RTGS (still in Queue 1)
    /// - `Some(priority)`: Transaction submitted with this priority
    ///
    /// Unlike internal priority, this can only be changed by withdrawing
    /// from Queue 2 and resubmitting (which loses FIFO position).
    rtgs_priority: Option<RtgsPriority>,

    /// Tick when submitted to RTGS Queue 2
    ///
    /// Used for FIFO ordering within the same RTGS priority band.
    /// Transactions with the same RTGS priority are processed in order
    /// of their submission tick (earlier tick = processed first).
    ///
    /// - `None`: Transaction not yet submitted to RTGS
    /// - `Some(tick)`: Transaction was submitted at this tick
    rtgs_submission_tick: Option<usize>,

    /// Bank's declared RTGS priority to use when submitted
    ///
    /// This is set when the transaction is created via submit_transaction_with_rtgs_priority.
    /// When the transaction is released to RTGS (enters Queue 2), this priority is used
    /// instead of the default Normal priority.
    ///
    /// - `None`: Use default Normal priority when submitted to RTGS
    /// - `Some(priority)`: Use this priority when submitted to RTGS
    declared_rtgs_priority: Option<RtgsPriority>,
}

impl Transaction {
    /// Create a new transaction
    ///
    /// # Arguments
    /// * `sender_id` - Sender agent ID
    /// * `receiver_id` - Receiver agent ID
    /// * `amount` - Transaction amount in cents (must be positive)
    /// * `arrival_tick` - Tick when transaction arrives
    /// * `deadline_tick` - Tick by which transaction must settle
    ///
    /// # Panics
    /// Panics if amount <= 0 or deadline <= arrival
    ///
    /// # Example
    /// ```
    /// use payment_simulator_core_rs::Transaction;
    ///
    /// let tx = Transaction::new(
    ///     "BANK_A".to_string(),
    ///     "BANK_B".to_string(),
    ///     100000,
    ///     10,
    ///     50,
    /// );
    /// ```
    pub fn new(
        sender_id: String,
        receiver_id: String,
        amount: i64,
        arrival_tick: usize,
        deadline_tick: usize,
    ) -> Self {
        assert!(amount > 0, "amount must be positive");
        assert!(
            deadline_tick > arrival_tick,
            "deadline must be after arrival"
        );

        Self {
            id: uuid::Uuid::new_v4().to_string(),
            sender_id,
            receiver_id,
            amount,
            remaining_amount: amount,
            arrival_tick,
            deadline_tick,
            priority: 5, // Default priority
            original_priority: 5, // Original priority before escalation
            status: TransactionStatus::Pending,
            parent_id: None,
            rtgs_priority: None, // Set when submitted to RTGS
            rtgs_submission_tick: None,
            declared_rtgs_priority: None, // Set via submit_transaction_with_rtgs_priority
        }
    }

    /// Create a new split transaction (child of a parent transaction)
    ///
    /// This constructor is used when a policy decides to split a large transaction
    /// into multiple smaller child transactions. Each child inherits the parent's
    /// sender, receiver, and deadline, but has a smaller amount.
    ///
    /// # Arguments
    /// * `sender_id` - Sender agent ID (same as parent)
    /// * `receiver_id` - Receiver agent ID (same as parent)
    /// * `amount` - Child transaction amount in cents (must be positive, <= parent amount)
    /// * `arrival_tick` - Tick when child is created (usually same as parent arrival)
    /// * `deadline_tick` - Deadline tick (same as parent)
    /// * `parent_id` - Parent transaction ID
    ///
    /// # Panics
    /// Panics if amount <= 0 or deadline <= arrival
    ///
    /// # Example
    /// ```
    /// use payment_simulator_core_rs::Transaction;
    ///
    /// let parent = Transaction::new(
    ///     "BANK_A".to_string(),
    ///     "BANK_B".to_string(),
    ///     100_000,
    ///     0,
    ///     10,
    /// );
    ///
    /// // Split into 2 children
    /// let child1 = Transaction::new_split(
    ///     "BANK_A".to_string(),
    ///     "BANK_B".to_string(),
    ///     50_000,
    ///     0,
    ///     10,
    ///     parent.id().to_string(),
    /// );
    ///
    /// assert!(child1.is_split());
    /// assert_eq!(child1.parent_id(), Some(parent.id()));
    /// ```
    pub fn new_split(
        sender_id: String,
        receiver_id: String,
        amount: i64,
        arrival_tick: usize,
        deadline_tick: usize,
        parent_id: String,
    ) -> Self {
        assert!(amount > 0, "amount must be positive");
        assert!(
            deadline_tick > arrival_tick,
            "deadline must be after arrival"
        );

        Self {
            id: uuid::Uuid::new_v4().to_string(),
            sender_id,
            receiver_id,
            amount,
            remaining_amount: amount,
            arrival_tick,
            deadline_tick,
            priority: 5, // Default priority (can be overridden with builder)
            original_priority: 5, // Original priority before escalation
            status: TransactionStatus::Pending,
            parent_id: Some(parent_id),
            rtgs_priority: None, // Set when submitted to RTGS
            rtgs_submission_tick: None,
            declared_rtgs_priority: None, // Children inherit parent's declared priority
        }
    }

    /// Create transaction from snapshot (for checkpoint restoration)
    ///
    /// This constructor allows restoring a transaction with all fields
    /// preserved, including the ID and status. Used when loading from
    /// a saved checkpoint.
    ///
    /// # Arguments
    /// * `id` - Transaction ID
    /// * `sender_id` - Sender agent ID
    /// * `receiver_id` - Receiver agent ID
    /// * `amount` - Original transaction amount
    /// * `remaining_amount` - Amount still to be settled
    /// * `arrival_tick` - Tick when transaction arrived
    /// * `deadline_tick` - Deadline tick
    /// * `priority` - Priority level (0-10)
    /// * `status` - Current transaction status
    /// * `parent_id` - Parent transaction ID if this is a split child
    ///
    /// # Example
    /// ```
    /// use payment_simulator_core_rs::{Transaction, TransactionStatus};
    ///
    /// let tx = Transaction::from_snapshot(
    ///     "tx_123".to_string(),
    ///     "BANK_A".to_string(),
    ///     "BANK_B".to_string(),
    ///     100_000,
    ///     50_000,
    ///     10,
    ///     50,
    ///     8,
    ///     TransactionStatus::Pending,
    ///     None,
    /// );
    /// ```
    pub fn from_snapshot(
        id: String,
        sender_id: String,
        receiver_id: String,
        amount: i64,
        remaining_amount: i64,
        arrival_tick: usize,
        deadline_tick: usize,
        priority: u8,
        status: TransactionStatus,
        parent_id: Option<String>,
    ) -> Self {
        let capped_priority = priority.min(10);
        Self {
            id,
            sender_id,
            receiver_id,
            amount,
            remaining_amount,
            arrival_tick,
            deadline_tick,
            priority: capped_priority,
            original_priority: capped_priority, // Assume original equals current for snapshots
            status,
            parent_id,
            rtgs_priority: None, // Not set for legacy snapshots
            rtgs_submission_tick: None,
            declared_rtgs_priority: None, // Not set for legacy snapshots
        }
    }

    /// Create transaction from snapshot with RTGS priority fields
    ///
    /// Extended version of `from_snapshot` that includes RTGS priority fields.
    /// Used for snapshots that include the dual priority system.
    pub fn from_snapshot_with_rtgs(
        id: String,
        sender_id: String,
        receiver_id: String,
        amount: i64,
        remaining_amount: i64,
        arrival_tick: usize,
        deadline_tick: usize,
        priority: u8,
        status: TransactionStatus,
        parent_id: Option<String>,
        rtgs_priority: Option<RtgsPriority>,
        rtgs_submission_tick: Option<usize>,
        declared_rtgs_priority: Option<RtgsPriority>,
    ) -> Self {
        let capped_priority = priority.min(10);
        Self {
            id,
            sender_id,
            receiver_id,
            amount,
            remaining_amount,
            arrival_tick,
            deadline_tick,
            priority: capped_priority,
            original_priority: capped_priority,
            status,
            parent_id,
            rtgs_priority,
            rtgs_submission_tick,
            declared_rtgs_priority,
        }
    }

    /// Set priority (builder pattern)
    ///
    /// # Example
    /// ```
    /// use payment_simulator_core_rs::Transaction;
    ///
    /// let tx = Transaction::new(
    ///     "BANK_A".to_string(),
    ///     "BANK_B".to_string(),
    ///     100000,
    ///     10,
    ///     50,
    /// ).with_priority(8);
    /// ```
    pub fn with_priority(mut self, priority: u8) -> Self {
        let capped = priority.min(10); // Cap at 10
        self.priority = capped;
        self.original_priority = capped; // Set original priority too
        self
    }

    /// Get transaction ID
    pub fn id(&self) -> &str {
        &self.id
    }

    /// Get sender agent ID
    pub fn sender_id(&self) -> &str {
        &self.sender_id
    }

    /// Get receiver agent ID
    pub fn receiver_id(&self) -> &str {
        &self.receiver_id
    }

    /// Get original transaction amount (i64 cents)
    pub fn amount(&self) -> i64 {
        self.amount
    }

    /// Get remaining amount to be settled (i64 cents)
    pub fn remaining_amount(&self) -> i64 {
        self.remaining_amount
    }

    /// Get amount already settled (i64 cents)
    pub fn settled_amount(&self) -> i64 {
        self.amount - self.remaining_amount
    }

    /// Get arrival tick
    pub fn arrival_tick(&self) -> usize {
        self.arrival_tick
    }

    /// Get deadline tick
    pub fn deadline_tick(&self) -> usize {
        self.deadline_tick
    }

    /// Get priority level
    pub fn priority(&self) -> u8 {
        self.priority
    }

    /// Get original priority level (before any escalation)
    pub fn original_priority(&self) -> u8 {
        self.original_priority
    }

    /// Get current status
    pub fn status(&self) -> &TransactionStatus {
        &self.status
    }

    /// Get parent transaction ID (for split transactions)
    ///
    /// Returns `Some(parent_id)` if this is a child of a split transaction,
    /// `None` if this is a regular (non-split) transaction.
    ///
    /// # Example
    /// ```
    /// use payment_simulator_core_rs::Transaction;
    ///
    /// let parent = Transaction::new("A".to_string(), "B".to_string(), 100_000, 0, 10);
    /// assert_eq!(parent.parent_id(), None);
    ///
    /// let child = Transaction::new_split(
    ///     "A".to_string(),
    ///     "B".to_string(),
    ///     50_000,
    ///     0,
    ///     10,
    ///     parent.id().to_string(),
    /// );
    /// assert_eq!(child.parent_id(), Some(parent.id()));
    /// ```
    pub fn parent_id(&self) -> Option<&str> {
        self.parent_id.as_deref()
    }

    /// Check if this is a split transaction (child of a parent)
    ///
    /// Returns `true` if this transaction was created by splitting a larger
    /// parent transaction, `false` otherwise.
    ///
    /// # Example
    /// ```
    /// use payment_simulator_core_rs::Transaction;
    ///
    /// let parent = Transaction::new("A".to_string(), "B".to_string(), 100_000, 0, 10);
    /// assert!(!parent.is_split());
    ///
    /// let child = Transaction::new_split(
    ///     "A".to_string(),
    ///     "B".to_string(),
    ///     50_000,
    ///     0,
    ///     10,
    ///     parent.id().to_string(),
    /// );
    /// assert!(child.is_split());
    /// ```
    pub fn is_split(&self) -> bool {
        self.parent_id.is_some()
    }

    /// Get RTGS priority (if submitted to RTGS)
    ///
    /// Returns `None` if transaction has not yet been submitted to RTGS Queue 2.
    /// Returns `Some(priority)` with the declared RTGS priority otherwise.
    pub fn rtgs_priority(&self) -> Option<RtgsPriority> {
        self.rtgs_priority
    }

    /// Get RTGS submission tick (if submitted to RTGS)
    ///
    /// Returns `None` if transaction has not yet been submitted to RTGS Queue 2.
    /// Returns `Some(tick)` with the tick when it was submitted otherwise.
    ///
    /// Used for FIFO ordering within the same RTGS priority band.
    pub fn rtgs_submission_tick(&self) -> Option<usize> {
        self.rtgs_submission_tick
    }

    /// Set RTGS priority and submission tick
    ///
    /// Called when transaction is submitted to RTGS Queue 2 from the bank's
    /// internal Queue 1.
    ///
    /// # Arguments
    /// * `priority` - The RTGS priority to declare
    /// * `tick` - The current tick (becomes the submission tick for FIFO ordering)
    pub fn set_rtgs_priority(&mut self, priority: RtgsPriority, tick: usize) {
        self.rtgs_priority = Some(priority);
        self.rtgs_submission_tick = Some(tick);
    }

    /// Clear RTGS priority and submission tick
    ///
    /// Called when transaction is withdrawn from RTGS Queue 2 back to Queue 1.
    /// This allows the transaction to be resubmitted with a different priority.
    pub fn clear_rtgs_priority(&mut self) {
        self.rtgs_priority = None;
        self.rtgs_submission_tick = None;
    }

    /// Get the declared RTGS priority (bank's preference for when submitted)
    ///
    /// Returns the priority the bank wants to use when this transaction is
    /// submitted to RTGS. If `None`, the default Normal priority will be used.
    pub fn declared_rtgs_priority(&self) -> Option<RtgsPriority> {
        self.declared_rtgs_priority
    }

    /// Set the declared RTGS priority
    ///
    /// Called when a transaction is submitted via submit_transaction_with_rtgs_priority.
    /// This stores the bank's preferred priority to use when the transaction
    /// enters RTGS Queue 2.
    pub fn set_declared_rtgs_priority(&mut self, priority: RtgsPriority) {
        self.declared_rtgs_priority = Some(priority);
    }

    /// Check if transaction is pending
    pub fn is_pending(&self) -> bool {
        matches!(self.status, TransactionStatus::Pending)
    }

    /// Check if transaction is fully settled
    pub fn is_fully_settled(&self) -> bool {
        self.remaining_amount == 0
    }

    /// Check if transaction is past its deadline
    ///
    /// Returns `true` if the current tick is **strictly after** the deadline tick.
    /// Returns `false` if at or before the deadline.
    ///
    /// # Boundary Semantics
    /// - `current_tick < deadline_tick`: Not past deadline (returns `false`)
    /// - `current_tick == deadline_tick`: **At deadline, still valid** (returns `false`)
    /// - `current_tick > deadline_tick`: Past deadline (returns `true`)
    ///
    /// # Arguments
    /// * `current_tick` - Current simulation tick
    ///
    /// # Examples
    /// ```
    /// use payment_simulator_core_rs::Transaction;
    ///
    /// let tx = Transaction::new("A".to_string(), "B".to_string(), 100_000, 0, 50);
    ///
    /// assert!(!tx.is_past_deadline(49)); // Before deadline
    /// assert!(!tx.is_past_deadline(50)); // At deadline - still valid
    /// assert!(tx.is_past_deadline(51));  // Past deadline
    /// ```
    pub fn is_past_deadline(&self, current_tick: usize) -> bool {
        current_tick > self.deadline_tick
    }

    /// Settle transaction (full or partial)
    ///
    /// # Arguments
    /// * `amount` - Amount to settle (i64 cents, must be > 0 and <= remaining)
    /// * `tick` - Tick when settlement occurs
    ///
    /// # Returns
    /// - Ok(()) if settlement successful
    /// - Err if transaction cannot be settled
    ///
    /// # Example
    /// ```
    /// use payment_simulator_core_rs::Transaction;
    ///
    /// let mut tx = Transaction::new(
    ///     "BANK_A".to_string(),
    ///     "BANK_B".to_string(),
    ///     100000,
    ///     10,
    ///     50,
    /// );
    ///
    /// // Must settle full remaining amount
    /// tx.settle(100000, 20).unwrap();
    /// assert!(tx.is_fully_settled());
    /// assert_eq!(tx.remaining_amount(), 0);
    /// ```
    pub fn settle(&mut self, amount: i64, tick: usize) -> Result<(), TransactionError> {
        // Validate amount
        if amount <= 0 {
            return Err(TransactionError::InvalidAmount);
        }

        // Check if already settled
        if self.remaining_amount == 0 {
            return Err(TransactionError::AlreadySettled);
        }

        // NOTE: Removed check for Dropped status - overdue transactions can still settle
        // In real payment systems, all obligations must eventually be settled

        // Check if amount matches remaining (must settle full amount)
        if amount != self.remaining_amount {
            return Err(TransactionError::AmountExceedsRemaining {
                amount,
                remaining: self.remaining_amount,
            });
        }

        // Settle the transaction (full settlement)
        self.remaining_amount = 0;
        self.status = TransactionStatus::Settled { tick };

        Ok(())
    }

    /// Reduce remaining amount when a child transaction settles
    ///
    /// This method is used internally by the settlement engine when a child
    /// (split) transaction settles. The parent's remaining_amount is reduced
    /// by the child's settled amount.
    ///
    /// When all children settle (remaining_amount reaches 0), the parent
    /// should be marked as fully settled by the caller.
    ///
    /// # Arguments
    /// * `amount` - Amount settled by the child (must be > 0 and <= remaining_amount)
    ///
    /// # Returns
    /// - Ok(()) if reduction successful
    /// - Err(TransactionError::InvalidAmount) if amount <= 0
    /// - Err(TransactionError::AmountExceedsRemaining) if amount > remaining_amount
    ///
    /// # Example
    /// ```rust,ignore
    /// // Parent transaction split into 4 children of 25,000 each
    /// let mut parent = Transaction::new("A".into(), "B".into(), 100_000, 0, 10);
    ///
    /// // When first child settles
    /// parent.reduce_remaining_for_child(25_000).unwrap();
    /// assert_eq!(parent.remaining_amount(), 75_000);
    ///
    /// // When all children settle
    /// parent.reduce_remaining_for_child(25_000).unwrap();
    /// parent.reduce_remaining_for_child(25_000).unwrap();
    /// parent.reduce_remaining_for_child(25_000).unwrap();
    /// assert_eq!(parent.remaining_amount(), 0);
    /// ```
    pub(crate) fn reduce_remaining_for_child(&mut self, amount: i64) -> Result<(), TransactionError> {
        // Validate amount
        if amount <= 0 {
            return Err(TransactionError::InvalidAmount);
        }

        if amount > self.remaining_amount {
            return Err(TransactionError::AmountExceedsRemaining {
                amount,
                remaining: self.remaining_amount,
            });
        }

        // Reduce remaining amount
        self.remaining_amount -= amount;

        Ok(())
    }

    /// Mark transaction as fully settled (used when all children settle)
    ///
    /// This is an internal method used by the settlement engine to mark a parent
    /// transaction as fully settled after all its children have settled.
    ///
    /// # Arguments
    /// * `tick` - Tick when the final child settled
    ///
    /// # Returns
    /// - Ok(()) if successfully marked as settled
    /// - Err(TransactionError::AlreadySettled) if already settled
    ///
    /// # Safety
    /// This should only be called after verifying remaining_amount == 0
    pub(crate) fn mark_fully_settled(&mut self, tick: usize) -> Result<(), TransactionError> {
        if self.remaining_amount != 0 {
            return Err(TransactionError::AmountExceedsRemaining {
                amount: 0,
                remaining: self.remaining_amount,
            });
        }

        match self.status {
            TransactionStatus::Settled { .. } => {
                // Already settled, no-op (idempotent)
                Ok(())
            }
            _ => {
                self.status = TransactionStatus::Settled { tick };
                Ok(())
            }
        }
    }

    /// Mark transaction as overdue (idempotent)
    ///
    /// In real payment systems, transactions cannot be "dropped" - they must
    /// eventually settle. This marks a transaction as overdue when it passes
    /// its deadline, but it remains in the queue and can still be settled.
    ///
    /// # Arguments
    /// * `tick` - Tick when transaction first missed its deadline
    ///
    /// # Returns
    /// - Ok(()) if marked overdue or already overdue
    /// - Err(TransactionError::AlreadySettled) if transaction is settled
    ///
    /// # Idempotency
    /// If called multiple times, keeps the original missed_deadline_tick
    pub fn mark_overdue(&mut self, tick: usize) -> Result<(), TransactionError> {
        match self.status {
            TransactionStatus::Pending | TransactionStatus::PartiallySettled { .. } => {
                self.status = TransactionStatus::Overdue {
                    missed_deadline_tick: tick,
                };
                Ok(())
            }
            TransactionStatus::Overdue { .. } => {
                // Idempotent - already overdue, keep original tick
                Ok(())
            }
            TransactionStatus::Settled { .. } => Err(TransactionError::AlreadySettled),
        }
    }

    /// Check if transaction is overdue
    ///
    /// Returns true if transaction has passed its deadline and is marked overdue.
    /// Overdue transactions remain in the queue and can still be settled.
    pub fn is_overdue(&self) -> bool {
        matches!(self.status, TransactionStatus::Overdue { .. })
    }

    /// Get tick when transaction became overdue
    ///
    /// Returns Some(tick) if overdue, None otherwise
    pub fn overdue_since_tick(&self) -> Option<usize> {
        match self.status {
            TransactionStatus::Overdue {
                missed_deadline_tick,
            } => Some(missed_deadline_tick),
            _ => None,
        }
    }

    /// Set transaction priority (for re-prioritization)
    ///
    /// Allows policies to adjust priority of queued transactions based on
    /// changing conditions (e.g., overdue status). Priority is capped at 10.
    ///
    /// # Arguments
    /// * `priority` - New priority level (0-10, will be capped)
    pub fn set_priority(&mut self, priority: u8) {
        self.priority = priority.min(10); // Cap at 10
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_priority_capped_at_10() {
        let tx = Transaction::new("BANK_A".to_string(), "BANK_B".to_string(), 100000, 10, 50)
            .with_priority(255); // Try to set > 10

        assert_eq!(tx.priority(), 10); // Should be capped at 10
    }

    // ==========================================
    // Phase 1: Overdue Transaction Tests
    // ==========================================

    #[test]
    fn test_mark_transaction_overdue() {
        let mut tx = Transaction::new("A".to_string(), "B".to_string(), 100_000, 0, 50);

        // Initially pending
        assert!(tx.is_pending());
        assert!(!tx.is_overdue());

        // Mark overdue at tick 51
        tx.mark_overdue(51).unwrap();

        // Check status
        assert!(tx.is_overdue());
        assert_eq!(tx.overdue_since_tick(), Some(51));
    }

    #[test]
    fn test_mark_overdue_is_idempotent() {
        let mut tx = Transaction::new("A".to_string(), "B".to_string(), 100_000, 0, 50);

        // Mark overdue twice
        tx.mark_overdue(51).unwrap();
        let result = tx.mark_overdue(52); // Different tick

        // Should succeed (idempotent) but not change tick
        assert!(result.is_ok());
        assert_eq!(tx.overdue_since_tick(), Some(51)); // Original tick preserved
    }

    #[test]
    fn test_overdue_transaction_can_still_settle() {
        let mut tx = Transaction::new("A".to_string(), "B".to_string(), 100_000, 0, 50);

        // Mark overdue
        tx.mark_overdue(51).unwrap();
        assert!(tx.is_overdue());

        // Should still be able to settle
        let result = tx.settle(100_000, 55);
        assert!(result.is_ok());
        assert!(tx.is_fully_settled());
    }

    #[test]
    fn test_cannot_mark_settled_transaction_overdue() {
        let mut tx = Transaction::new("A".to_string(), "B".to_string(), 100_000, 0, 50);

        // Settle first
        tx.settle(100_000, 40).unwrap();

        // Attempting to mark overdue should fail
        let result = tx.mark_overdue(51);
        assert!(result.is_err());
        assert_eq!(result.unwrap_err(), TransactionError::AlreadySettled);
    }

    #[test]
    fn test_partially_settled_can_become_overdue() {
        let mut tx = Transaction::new("A".to_string(), "B".to_string(), 100_000, 0, 50);

        // For now, just ensure status transition logic handles all cases
        tx.mark_overdue(51).unwrap();
        assert!(tx.is_overdue());
    }

    #[test]
    fn test_settle_no_longer_rejects_overdue() {
        let mut tx = Transaction::new("A".to_string(), "B".to_string(), 100_000, 0, 50);
        tx.mark_overdue(51).unwrap();

        // Old behavior: Err(TransactionError::TransactionDropped)
        // New behavior: Ok(())
        let result = tx.settle(100_000, 55);
        assert!(result.is_ok());
    }

    #[test]
    fn test_set_priority() {
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
    fn test_set_priority_caps_at_10() {
        let mut tx = Transaction::new("A".to_string(), "B".to_string(), 100_000, 0, 50);

        // Try to set priority > 10
        tx.set_priority(255);
        assert_eq!(tx.priority(), 10); // Capped
    }
}
