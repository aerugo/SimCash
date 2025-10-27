//! Agent (Bank) model
//!
//! Represents a bank participating in the payment system.
//! Each agent has:
//! - Settlement balance (i64 cents)
//! - Credit limit for intraday overdraft (i64 cents)
//! - Transaction queue (future)
//!
//! CRITICAL: All money values are i64 (cents)

use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Errors that can occur during agent operations
#[derive(Debug, Error, PartialEq)]
pub enum AgentError {
    #[error("Insufficient liquidity: required {required}, available {available}")]
    InsufficientLiquidity { required: i64, available: i64 },
}

/// Represents a bank (agent) in the payment system
///
/// # Example
/// ```
/// use payment_simulator_core_rs::Agent;
///
/// let mut agent = Agent::new("BANK_A".to_string(), 1000000, 500000);
/// assert_eq!(agent.balance(), 1000000); // $10,000.00 in cents
///
/// agent.debit(300000).unwrap(); // Pay $3,000
/// assert_eq!(agent.balance(), 700000);
/// ```
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Agent {
    /// Unique agent identifier (e.g., "BANK_A")
    id: String,

    /// Current balance in settlement account (i64 cents)
    /// Positive = funds available
    /// Negative = using intraday credit
    balance: i64,

    /// Maximum intraday credit/overdraft allowed (i64 cents)
    /// This is the absolute limit the agent can go negative
    credit_limit: i64,
}

impl Agent {
    /// Create a new agent
    ///
    /// # Arguments
    /// * `id` - Unique identifier (e.g., "BANK_A")
    /// * `balance` - Opening balance in cents (can be negative)
    /// * `credit_limit` - Maximum overdraft allowed in cents (positive)
    ///
    /// # Example
    /// ```
    /// use payment_simulator_core_rs::Agent;
    ///
    /// let agent = Agent::new("BANK_A".to_string(), 1000000, 500000);
    /// assert_eq!(agent.balance(), 1000000);
    /// ```
    pub fn new(id: String, balance: i64, credit_limit: i64) -> Self {
        assert!(credit_limit >= 0, "credit_limit must be non-negative");
        Self {
            id,
            balance,
            credit_limit,
        }
    }

    /// Get agent ID
    pub fn id(&self) -> &str {
        &self.id
    }

    /// Get current balance (i64 cents)
    ///
    /// # Example
    /// ```
    /// use payment_simulator_core_rs::Agent;
    ///
    /// let agent = Agent::new("BANK_A".to_string(), 1000000, 500000);
    /// assert_eq!(agent.balance(), 1000000);
    /// ```
    pub fn balance(&self) -> i64 {
        self.balance
    }

    /// Get credit limit (i64 cents)
    pub fn credit_limit(&self) -> i64 {
        self.credit_limit
    }

    /// Calculate available liquidity (balance + unused credit)
    ///
    /// # Returns
    /// - If balance >= 0: balance + credit_limit
    /// - If balance < 0: credit_limit - abs(balance)
    ///
    /// # Example
    /// ```
    /// use payment_simulator_core_rs::Agent;
    ///
    /// let agent = Agent::new("BANK_A".to_string(), 1000000, 500000);
    /// assert_eq!(agent.available_liquidity(), 1500000);
    /// ```
    pub fn available_liquidity(&self) -> i64 {
        if self.balance >= 0 {
            self.balance + self.credit_limit
        } else {
            // Already using credit, so available = credit_limit - used
            self.credit_limit - self.balance.abs()
        }
    }

    /// Check if agent can pay a given amount
    ///
    /// # Arguments
    /// * `amount` - Amount to check (i64 cents)
    ///
    /// # Example
    /// ```
    /// use payment_simulator_core_rs::Agent;
    ///
    /// let agent = Agent::new("BANK_A".to_string(), 1000000, 500000);
    /// assert!(agent.can_pay(500000)); // Can pay $5,000
    /// assert!(!agent.can_pay(2000000)); // Can't pay $20,000
    /// ```
    pub fn can_pay(&self, amount: i64) -> bool {
        amount <= self.available_liquidity()
    }

    /// Debit (decrease) balance
    ///
    /// # Arguments
    /// * `amount` - Amount to debit (i64 cents, must be positive)
    ///
    /// # Returns
    /// - Ok(()) if successful
    /// - Err if insufficient liquidity
    ///
    /// # Example
    /// ```
    /// use payment_simulator_core_rs::Agent;
    ///
    /// let mut agent = Agent::new("BANK_A".to_string(), 1000000, 500000);
    /// agent.debit(300000).unwrap();
    /// assert_eq!(agent.balance(), 700000);
    /// ```
    pub fn debit(&mut self, amount: i64) -> Result<(), AgentError> {
        assert!(amount >= 0, "amount must be positive");

        if !self.can_pay(amount) {
            return Err(AgentError::InsufficientLiquidity {
                required: amount,
                available: self.available_liquidity(),
            });
        }

        self.balance -= amount;
        Ok(())
    }

    /// Credit (increase) balance
    ///
    /// # Arguments
    /// * `amount` - Amount to credit (i64 cents, must be positive)
    ///
    /// # Example
    /// ```
    /// use payment_simulator_core_rs::Agent;
    ///
    /// let mut agent = Agent::new("BANK_A".to_string(), 1000000, 500000);
    /// agent.credit(500000);
    /// assert_eq!(agent.balance(), 1500000);
    /// ```
    pub fn credit(&mut self, amount: i64) {
        assert!(amount >= 0, "amount must be positive");
        self.balance += amount;
    }

    /// Check if agent is currently using intraday credit
    ///
    /// # Example
    /// ```
    /// use payment_simulator_core_rs::Agent;
    ///
    /// let mut agent = Agent::new("BANK_A".to_string(), 1000000, 500000);
    /// assert!(!agent.is_using_credit());
    ///
    /// agent.debit(1200000).unwrap();
    /// assert!(agent.is_using_credit());
    /// ```
    pub fn is_using_credit(&self) -> bool {
        self.balance < 0
    }

    /// Get amount of credit currently being used
    ///
    /// # Returns
    /// - 0 if balance >= 0
    /// - abs(balance) if balance < 0
    ///
    /// # Example
    /// ```
    /// use payment_simulator_core_rs::Agent;
    ///
    /// let mut agent = Agent::new("BANK_A".to_string(), 1000000, 500000);
    /// assert_eq!(agent.credit_used(), 0);
    ///
    /// agent.debit(1200000).unwrap();
    /// assert_eq!(agent.credit_used(), 200000);
    /// ```
    pub fn credit_used(&self) -> i64 {
        if self.balance < 0 {
            self.balance.abs()
        } else {
            0
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    #[should_panic(expected = "credit_limit must be non-negative")]
    fn test_negative_credit_limit_panics() {
        Agent::new("BANK_A".to_string(), 1000000, -500000);
    }
}
