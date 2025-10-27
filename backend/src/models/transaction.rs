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
/// ).with_priority(8).divisible();
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

    /// Can the transaction be split into multiple parts?
    is_divisible: bool,

    /// Current status
    status: TransactionStatus,
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
            is_divisible: false,
            status: TransactionStatus::Pending,
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

    /// Mark transaction as divisible (builder pattern)
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
    /// ).divisible();
    /// ```
    pub fn divisible(mut self) -> Self {
        self.is_divisible = true;
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

    /// Check if transaction is divisible
    pub fn is_divisible(&self) -> bool {
        self.is_divisible
    }

    /// Get current status
    pub fn status(&self) -> &TransactionStatus {
        &self.status
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
    /// # Arguments
    /// * `current_tick` - Current simulation tick
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
    /// ).divisible();
    ///
    /// // Partial settlement
    /// tx.settle(40000, 20).unwrap();
    /// assert_eq!(tx.remaining_amount(), 60000);
    ///
    /// // Final settlement
    /// tx.settle(60000, 30).unwrap();
    /// assert!(tx.is_fully_settled());
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

        // Check if amount exceeds remaining
        if amount > self.remaining_amount {
            return Err(TransactionError::AmountExceedsRemaining {
                amount,
                remaining: self.remaining_amount,
            });
        }

        // Check if partial settlement allowed
        if amount < self.remaining_amount && !self.is_divisible {
            return Err(TransactionError::IndivisibleTransaction);
        }

        // Update remaining amount
        self.remaining_amount -= amount;

        // Update status
        if self.remaining_amount == 0 {
            // Fully settled
            self.status = TransactionStatus::Settled { tick };
        } else {
            // Partially settled
            if matches!(self.status, TransactionStatus::Pending) {
                // First partial settlement
                self.status = TransactionStatus::PartiallySettled {
                    first_settlement_tick: tick,
                };
            }
            // If already PartiallySettled, keep the original first_settlement_tick
        }

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
