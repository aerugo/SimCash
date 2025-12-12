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
pub mod costs;
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
    transaction::{RtgsPriority, Transaction, TransactionError, TransactionStatus},
};
pub use costs::{get_priority_band, CostRates, PriorityBand, PriorityDelayMultipliers};
pub use orchestrator::{
    AgentConfig, CostAccumulator, CostBreakdown, Orchestrator, OrchestratorConfig, PolicyConfig,
    SimulationError, TickResult,
};
pub use rng::RngManager;
pub use settlement::{try_settle, SettlementError};

// FFI module (when feature enabled)
#[cfg(feature = "pyo3")]
pub mod ffi;

// PyO3 exports (when feature enabled)
#[cfg(feature = "pyo3")]
use pyo3::prelude::*;

/// Get the policy schema documentation as a JSON string.
///
/// This function generates comprehensive documentation of all policy DSL
/// elements including expressions, computations, actions, and values.
///
/// Returns a JSON string containing the PolicySchemaDoc structure.
#[cfg(feature = "pyo3")]
#[pyfunction]
#[pyo3(name = "get_policy_schema")]
fn py_get_policy_schema() -> PyResult<String> {
    Ok(policy::tree::schema_docs::get_policy_schema())
}

/// Get the cost schema documentation as a JSON string.
///
/// This function generates comprehensive documentation of all cost type
/// elements including per-tick costs, one-time penalties, and modifiers.
///
/// Returns a JSON string containing the CostSchemaDoc structure.
#[cfg(feature = "pyo3")]
#[pyfunction]
#[pyo3(name = "get_cost_schema")]
fn py_get_cost_schema() -> PyResult<String> {
    Ok(costs::schema_docs::get_cost_schema())
}

/// Validate a policy tree JSON string.
///
/// This function performs comprehensive validation of a policy JSON file:
/// 1. JSON parsing (syntax validation)
/// 2. Schema validation (all required fields present)
/// 3. Semantic validation:
///    - Node ID uniqueness
///    - Tree depth limits
///    - Field reference validity
///    - Parameter reference validity
///    - Division-by-zero safety
///    - Action reachability
///
/// # Arguments
///
/// * `policy_json` - JSON string containing the policy definition
///
/// # Returns
///
/// JSON string with validation results:
/// - On success: `{"valid": true, "policy_id": "...", "trees": {...}}`
/// - On failure: `{"valid": false, "errors": [{"type": "...", "message": "..."}]}`
#[cfg(feature = "pyo3")]
#[pyfunction]
#[pyo3(name = "validate_policy")]
fn py_validate_policy(policy_json: &str) -> PyResult<String> {
    use policy::tree::{validate_tree, DecisionTreeDef, EvalContext};
    use serde_json::json;

    // Step 1: Parse JSON
    let tree_def: DecisionTreeDef = match serde_json::from_str(policy_json) {
        Ok(def) => def,
        Err(e) => {
            let result = json!({
                "valid": false,
                "errors": [{
                    "type": "ParseError",
                    "message": format!("JSON parsing failed: {}", e)
                }]
            });
            return Ok(result.to_string());
        }
    };

    // Step 2: Create a sample context for validation
    // We need a context with all valid field names for validation
    let agent = Agent::new("VALIDATION_AGENT".to_string(), 1_000_000);
    let tx = Transaction::new(
        "VALIDATION_AGENT".to_string(),
        "OTHER_AGENT".to_string(),
        100_000,
        0,
        100,
    );
    let state = SimulationState::new(vec![agent.clone()]);
    let cost_rates = CostRates::default();
    let sample_context = EvalContext::build(&tx, &agent, &state, 0, &cost_rates, 100, 0.8);

    // Step 3: Run semantic validation
    let validation_result = validate_tree(&tree_def, &sample_context);

    match validation_result {
        Ok(()) => {
            // Gather tree information
            let trees = json!({
                "has_payment_tree": tree_def.payment_tree.is_some(),
                "has_bank_tree": tree_def.bank_tree.is_some(),
                "has_strategic_collateral_tree": tree_def.strategic_collateral_tree.is_some(),
                "has_end_of_tick_collateral_tree": tree_def.end_of_tick_collateral_tree.is_some(),
                "parameter_count": tree_def.parameters.len(),
                "parameters": tree_def.parameters.keys().collect::<Vec<_>>(),
            });

            let result = json!({
                "valid": true,
                "policy_id": tree_def.policy_id,
                "version": tree_def.version,
                "description": tree_def.description,
                "trees": trees,
            });
            Ok(result.to_string())
        }
        Err(errors) => {
            let error_list: Vec<_> = errors
                .iter()
                .map(|e| {
                    let (error_type, message) = match e {
                        policy::tree::ValidationError::DuplicateNodeId(id) => {
                            ("DuplicateNodeId", format!("Duplicate node ID: {}", id))
                        }
                        policy::tree::ValidationError::ExcessiveDepth { actual, max } => (
                            "ExcessiveDepth",
                            format!("Tree depth {} exceeds maximum {}", actual, max),
                        ),
                        policy::tree::ValidationError::InvalidFieldReference(field) => (
                            "InvalidFieldReference",
                            format!("Invalid field reference: '{}'", field),
                        ),
                        policy::tree::ValidationError::InvalidParameterReference(param) => (
                            "InvalidParameterReference",
                            format!("Parameter '{}' not found in tree parameters", param),
                        ),
                        policy::tree::ValidationError::DivisionByZeroRisk(node) => (
                            "DivisionByZeroRisk",
                            format!("Potential division by zero at node {}", node),
                        ),
                        policy::tree::ValidationError::UnreachableAction(node) => {
                            ("UnreachableAction", format!("Unreachable action node: {}", node))
                        }
                    };
                    json!({
                        "type": error_type,
                        "message": message
                    })
                })
                .collect();

            let result = json!({
                "valid": false,
                "errors": error_list
            });
            Ok(result.to_string())
        }
    }
}

#[cfg(feature = "pyo3")]
#[pymodule]
fn payment_simulator_core_rs(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<ffi::orchestrator::PyOrchestrator>()?;
    m.add_class::<models::transaction::RtgsPriority>()?;
    m.add_function(wrap_pyfunction!(py_get_policy_schema, m)?)?;
    m.add_function(wrap_pyfunction!(py_get_cost_schema, m)?)?;
    m.add_function(wrap_pyfunction!(py_validate_policy, m)?)?;
    Ok(())
}
