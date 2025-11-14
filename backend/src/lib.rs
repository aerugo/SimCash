//! Payment Simulator Core - Rust Engine
//!
//! High-performance payment settlement simulator with deterministic execution.
//!
//! # Architecture
//!
//! - **core**: Time management and initialization
//! - **models**: Domain types (Agent, Transaction, State)
//! - **policy**: Cash manager policies (Queue 1 decisions)
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
pub mod arrivals;
pub mod core;
pub mod events;
pub mod models;
pub mod orchestrator;
pub mod policy;
pub mod rng;
pub mod settlement;

// Re-exports for convenience
pub use arrivals::{AmountDistribution, ArrivalConfig};
pub use core::time::TimeManager;
pub use models::{
    agent::{Agent, AgentError, WithdrawError},
    event::{Event, EventLog},
    state::SimulationState,
    transaction::{Transaction, TransactionError, TransactionStatus},
};
pub use orchestrator::{
    AgentConfig, CostAccumulator, CostBreakdown, CostRates, Orchestrator, OrchestratorConfig,
    PolicyConfig, SimulationError, TickResult,
};
pub use rng::RngManager;
pub use settlement::{try_settle, SettlementError};

// FFI module (when feature enabled)
#[cfg(feature = "pyo3")]
pub mod ffi;

// PyO3 exports (when feature enabled)
#[cfg(feature = "pyo3")]
use pyo3::prelude::*;

#[cfg(feature = "pyo3")]
#[pymodule]
fn payment_simulator_core_rs(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<ffi::orchestrator::PyOrchestrator>()?;
    Ok(())
}
