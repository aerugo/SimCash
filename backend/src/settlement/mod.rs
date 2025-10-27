//! Settlement Module
//!
//! Phase 3: RTGS Settlement Engine
//!
//! This module implements the core T2-style RTGS settlement logic:
//! - Immediate settlement when liquidity is sufficient
//! - Central queue for transactions awaiting liquidity
//! - Queue processing with FIFO retry
//! - Balance conservation (atomic debit + credit)
//!
//! # Critical Invariants
//!
//! 1. **Atomicity**: Settlement is all-or-nothing (debit sender AND credit receiver, or neither)
//! 2. **Balance Conservation**: Total system balance never changes during settlement
//! 3. **Central Bank Model**: Settlement occurs at the central bank (not direct bank-to-bank)
//!
//! # Example
//!
//! ```rust
//! use payment_simulator_core_rs::{Agent, Transaction};
//! use payment_simulator_core_rs::settlement;
//!
//! let mut sender = Agent::new("BANK_A".to_string(), 1_000_000, 500_000);
//! let mut receiver = Agent::new("BANK_B".to_string(), 0, 0);
//! let mut transaction = Transaction::new(
//!     "BANK_A".to_string(),
//!     "BANK_B".to_string(),
//!     500_000,
//!     0,
//!     100,
//! );
//!
//! // Attempt immediate settlement (RTGS)
//! let result = settlement::try_settle(&mut sender, &mut receiver, &mut transaction, 5);
//! assert!(result.is_ok());
//! assert_eq!(sender.balance(), 500_000);
//! assert_eq!(receiver.balance(), 500_000);
//! ```

pub mod rtgs;

// Re-export public API
pub use rtgs::{
    process_queue, submit_transaction, try_settle, try_settle_partial, QueueProcessingResult,
    SettlementError, SubmissionResult,
};
