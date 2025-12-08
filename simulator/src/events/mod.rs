//! Scenario events module
//!
//! Provides functionality for scheduled events that modify simulation state.
//!
//! # Components
//!
//! - **types**: Event type definitions and schedules
//! - **handler**: Event execution and scheduling logic
//!
//! # Example
//!
//! ```rust
//! use payment_simulator_core_rs::events::{ScenarioEvent, EventSchedule, ScheduledEvent, ScenarioEventHandler};
//!
//! let events = vec![
//!     ScheduledEvent {
//!         event: ScenarioEvent::DirectTransfer {
//!             from_agent: "A".to_string(),
//!             to_agent: "B".to_string(),
//!             amount: 100_000,
//!         },
//!         schedule: EventSchedule::OneTime { tick: 10 },
//!     },
//! ];
//!
//! let handler = ScenarioEventHandler::new(events);
//! ```

pub mod handler;
pub mod types;

// Re-exports for convenience
pub use handler::ScenarioEventHandler;
pub use types::{EventSchedule, ScenarioEvent, ScheduledEvent};
