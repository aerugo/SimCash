//! Orchestrator - main simulation loop (Phase 4b)
//!
//! Implements the complete tick loop integrating all simulation components.
//!
//! See `engine.rs` for full implementation.

pub mod checkpoint;
pub mod engine;

#[cfg(test)]
mod tests;

// Re-export main types for convenience
pub use engine::{
    AgentConfig, AgentLimitsConfig, CostAccumulator, CostBreakdown, CostRates, DailyMetrics, Orchestrator,
    OrchestratorConfig, PolicyConfig, PriorityEscalationConfig, Queue1Ordering, SimulationError, TickResult,
};

// Re-export checkpoint types
pub use checkpoint::{AgentSnapshot, StateSnapshot, TransactionSnapshot};
