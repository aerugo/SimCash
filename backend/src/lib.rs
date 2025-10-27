//! Payment Simulator Core - Rust Engine
//!
//! High-performance payment settlement simulator with deterministic execution.
//!
//! # Architecture
//!
//! - **core**: Time management and initialization
//! - **models**: Domain types (Agent, Transaction, State)
//! - **orchestrator**: Main simulation loop
//! - **settlement**: Settlement engines (RTGS, LSM)
//! - **rng**: Deterministic random number generation
//!
//! # Critical Invariants
//!
//! 1. All money values are i64 (cents)
//! 2. All randomness is deterministic (seeded RNG)
//! 3. FFI boundary is minimal and safe

// Module declarations
pub mod core;
pub mod models;
pub mod orchestrator;
pub mod rng;
pub mod settlement;

// Re-exports for convenience
pub use core::time::TimeManager;
pub use models::{
    agent::{Agent, AgentError},
    state::SimulationState,
    transaction::{Transaction, TransactionError, TransactionStatus},
};
pub use orchestrator::Orchestrator;
pub use rng::RngManager;
pub use settlement::{try_settle, try_settle_partial, SettlementError};

// PyO3 exports (when feature enabled)
#[cfg(feature = "pyo3")]
use pyo3::prelude::*;

#[cfg(feature = "pyo3")]
#[pymodule]
fn payment_simulator_core_rs(_py: Python, _m: &PyModule) -> PyResult<()> {
    // PyO3 exports will be added in Phase 5
    Ok(())
}
