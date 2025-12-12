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
    AgentConfig, AgentLimitsConfig, CostAccumulator, CostBreakdown, DailyMetrics, Orchestrator,
    OrchestratorConfig, PolicyConfig, PriorityEscalationConfig, Queue1Ordering, SimulationError, TickResult,
};
// BIS model support - CostRates and priority types are now in costs module
pub use crate::costs::{get_priority_band, CostRates, PriorityBand, PriorityDelayMultipliers};

// Re-export checkpoint types
pub use checkpoint::{AgentSnapshot, StateSnapshot, TransactionSnapshot};
