//! Transaction model
//!
//! Represents a payment between two agents.
//! Each transaction has:
//! - Sender and receiver agent IDs
//! - Amount (i64 cents) - original and remaining
//! - Arrival and deadline ticks
//! - Priority level
//! - Divisibility flag (can be split into parts)
//! - Status (Pending, PartiallySettled, Settled, Dropped)
//!
//! CRITICAL: All money values are i64 (cents)

use serde::{Deserialize, Serialize};
use thiserror::Error;

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

    /// Transaction dropped (e.g., past deadline, rejected)
    Dropped {
        /// Tick when transaction was dropped
        tick: usize,
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
            status: TransactionStatus::Pending,
            parent_id: None,
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
            status: TransactionStatus::Pending,
            parent_id: Some(parent_id),
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
        Self {
            id,
            sender_id,
            receiver_id,
            amount,
            remaining_amount,
            arrival_tick,
            deadline_tick,
            priority: priority.min(10),
            status,
            parent_id,
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
        self.priority = priority.min(10); // Cap at 10
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

        // Check if dropped
        if matches!(self.status, TransactionStatus::Dropped { .. }) {
            return Err(TransactionError::TransactionDropped);
        }

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

    /// Drop transaction (e.g., past deadline, rejected)
    ///
    /// # Arguments
    /// * `tick` - Tick when transaction is dropped
    pub fn drop_transaction(&mut self, tick: usize) {
        self.status = TransactionStatus::Dropped { tick };
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_priority_capped_at_10() {
        let tx = Transaction::new(
            "BANK_A".to_string(),
            "BANK_B".to_string(),
            100000,
            10,
            50,
        )
        .with_priority(255); // Try to set > 10

        assert_eq!(tx.priority(), 10); // Should be capped at 10
    }
}
