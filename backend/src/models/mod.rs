//! Domain models for the payment simulator

pub mod agent;
pub mod collateral_event;
pub mod event;
pub mod state;
pub mod transaction;

// Re-exports
pub use agent::{Agent, AgentError};
pub use collateral_event::{CollateralAction, CollateralEvent, CollateralLayer};
pub use event::{Event, EventLog};
pub use transaction::{Transaction, TransactionError, TransactionStatus};
