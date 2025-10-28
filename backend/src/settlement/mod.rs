//! Settlement Module
//!
//! Phase 3: RTGS Settlement Engine + LSM Optimization
//!
//! This module implements T2-style settlement:
//! - **RTGS**: Immediate settlement when liquidity is sufficient
//! - **Queue**: Central queue for transactions awaiting liquidity
//! - **LSM**: Liquidity-saving mechanisms (bilateral offsetting, cycle detection)
//! - **Balance conservation**: Atomic debit + credit
//!
//! # Queue Architecture Context
//!
//! This module operates on **Queue 2** (central RTGS queue):
//! - Transactions arrive here AFTER being submitted to RTGS
//! - Settlement is mechanical: liquidity checks, retry, LSM optimization
//! - No policy decisions (those happen in Queue 1, future Phase 4-5)
//!
//! See `/docs/queue_architecture.md` for the complete two-queue model.
//!
//! # Critical Invariants
//!
//! 1. **Atomicity**: Settlement is all-or-nothing (debit sender AND credit receiver, or neither)
//! 2. **Balance Conservation**: Total system balance never changes during settlement
//! 3. **Central Bank Model**: Settlement occurs at the central bank (not direct bank-to-bank)
//!
//! # Example: Basic RTGS
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
//!
//! # Example: LSM Optimization
//!
//! ```no_run
//! use payment_simulator_core_rs::settlement::lsm::{run_lsm_pass, LsmConfig};
//!
//! # let mut state = todo!();
//! # let tick = 5;
//! // After queue processing, run LSM to resolve gridlock
//! let lsm_config = LsmConfig::default();
//! let result = run_lsm_pass(&mut state, &lsm_config, tick);
//! println!("LSM settled {} transactions", result.total_settled_value);
//! ```

pub mod lsm;
pub mod rtgs;

// Re-export public API
pub use rtgs::{
    process_queue, submit_transaction, try_settle, QueueProcessingResult,
    SettlementError, SubmissionResult,
};

pub use lsm::{
    bilateral_offset, detect_cycles, run_lsm_pass, settle_cycle, BilateralOffsetResult, Cycle,
    CycleSettlementResult, LsmConfig, LsmPassResult,
};
