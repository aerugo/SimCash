// Phase 6: Policy DSL Decision Trees
//
// This module implements JSON-based decision tree policies that can be:
// - Edited by LLMs (safe, no code execution)
// - Validated before execution (schema + safety checks)
// - Hot-reloaded at runtime (no simulation restart)
// - Version-controlled (git-based policy evolution)
//
// Architecture:
// - types.rs: Core type definitions (DecisionTreeDef, TreeNode, Expression, etc.)
// - context.rs: Evaluation context (field values from simulation state)
// - interpreter.rs: Tree interpreter (expression evaluation, decision building)
// - validation.rs: Safety validation (uniqueness, depth, references, etc.)
// - executor.rs: PolicyExecutor enum (unified interface for Trait + Tree)

pub mod context;
pub mod executor;
pub mod factory; // Phase 3: Policy factory for orchestrator integration
pub mod interpreter;
pub mod scenario_tests; // Real-world scenario tests for policy evaluation
pub mod schema_docs; // Auto-generated schema documentation
pub mod types;
pub mod validation;

#[cfg(test)]
mod tests; // Phase 9.5: Complex policy DSL tests

// Re-export main types for convenience
pub use context::{ContextError, EvalContext};
pub use executor::{TreePolicy, TreePolicyError};
pub use factory::create_policy; // Phase 3: Policy factory function
pub use interpreter::{
    build_bank_decision_with_path, build_collateral_decision, build_decision,
    evaluate_computation, evaluate_expression, evaluate_value, traverse_bank_tree_with_path,
    traverse_end_of_tick_collateral_tree, traverse_strategic_collateral_tree, traverse_tree,
    EvalError,
};
pub use types::{
    ActionType, Computation, DecisionPath, DecisionPathNode, DecisionTreeDef, Expression,
    TreeNode, Value, ValueOrCompute,
};
pub use validation::{validate_tree, ValidationError, ValidationResult};
pub use schema_docs::{
    PolicySchemaDoc, SchemaCategory, SchemaDocumented, SchemaElement, ParameterDoc,
};
