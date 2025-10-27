//! Orchestrator - main simulation loop (Phase 4b)
//!
//! Implements the complete tick loop integrating all simulation components.
//!
//! See `engine.rs` for full implementation.

pub mod engine;

// Re-export main types for convenience
pub use engine::{
    AgentConfig, ArrivalConfig, CostAccumulator, CostBreakdown, CostRates, Orchestrator,
    OrchestratorConfig, PolicyConfig, SimulationError, TickResult,
};
