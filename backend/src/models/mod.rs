//! Domain models for the payment simulator

pub mod agent;
pub mod state;
pub mod transaction;

// Re-exports
pub use agent::{Agent, AgentError};
pub use transaction::{Transaction, TransactionError, TransactionStatus};
