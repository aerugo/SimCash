//! Domain models for the payment simulator

pub mod agent;
pub mod event;
pub mod state;
pub mod transaction;

// Re-exports
pub use agent::{Agent, AgentError};
pub use event::{Event, EventLog};
pub use transaction::{Transaction, TransactionError, TransactionStatus};
