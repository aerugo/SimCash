// Phase 6: Decision Tree Interpreter
//
// Evaluates expressions and traverses decision trees to produce policy decisions.
// Implements recursive evaluation of values, computations, and boolean expressions.

use crate::policy::tree::context::{ContextError, EvalContext};
use crate::policy::tree::types::{
    Computation, DecisionTreeDef, Expression, TreeNode, Value, ValueOrCompute,
};
use crate::policy::{HoldReason, ReleaseDecision};
use std::collections::HashMap;
use thiserror::Error;

/// Errors that can occur during tree interpretation
#[derive(Debug, Error, PartialEq)]
pub enum EvalError {
    #[error("Field not found: {0}")]
    FieldNotFound(String),

    #[error("Parameter not found: {0}")]
    ParameterNotFound(String),

    #[error("Division by zero in computation")]
    DivisionByZero,

    #[error("Invalid literal type: expected number")]
    InvalidLiteralType,

    #[error("Empty value list for min/max computation")]
    EmptyValueList,

    #[error("Tree traversal exceeded maximum depth (100)")]
    MaxDepthExceeded,

    #[error("Expected action node, found condition node")]
    ExpectedActionNode,

    #[error("Missing required action parameter: {0}")]
    MissingActionParameter(String),

    #[error("Invalid action parameter type: {0}")]
    InvalidActionParameter(String),

    #[error("Invalid action type: {0}")]
    InvalidActionType(String),

    #[error("Invalid tree: {0}")]
    InvalidTree(String),

    #[error("Context error: {0}")]
    ContextError(#[from] ContextError),
}

// ============================================================================
// VALUE EVALUATION (Phase 6.3)
// ============================================================================

/// Evaluate a value to a numeric result
///
/// Resolves field references, parameter references, literals, and computations.
///
/// # Arguments
///
/// * `value` - Value to evaluate
/// * `context` - Evaluation context with field values
/// * `params` - Tree parameters (named constants/thresholds)
///
/// # Returns
///
/// Ok(f64) if evaluation succeeds, Err otherwise
///
/// # Example
///
/// ```rust
/// use payment_simulator_core_rs::policy::tree::{Value, EvalContext};
/// use payment_simulator_core_rs::{Agent, Transaction, SimulationState};
/// use payment_simulator_core_rs::orchestrator::CostRates;
/// use std::collections::HashMap;
///
/// # fn main() -> Result<(), Box<dyn std::error::Error>> {
/// let agent = Agent::new("BANK_A".to_string(), 1_000_000, 0);
/// let tx = Transaction::new("BANK_A".to_string(), "BANK_B".to_string(), 100_000, 0, 100);
/// let state = SimulationState::new(vec![agent.clone()]);
/// let cost_rates = CostRates::default();
/// let context = EvalContext::build(&tx, &agent, &state, 10, &cost_rates, 100, 0.8);
/// let params = HashMap::new();
///
/// let value = Value::Field { field: "balance".to_string() };
/// let result = payment_simulator_core_rs::policy::tree::evaluate_value(&value, &context, &params)?;
/// assert_eq!(result, 1_000_000.0);
/// # Ok(())
/// # }
/// ```
pub fn evaluate_value(
    value: &Value,
    context: &EvalContext,
    params: &HashMap<String, f64>,
) -> Result<f64, EvalError> {
    match value {
        // Field reference: Look up in context
        Value::Field { field } => context
            .get_field(field)
            .map_err(|_| EvalError::FieldNotFound(field.clone())),

        // Parameter reference: Look up in tree parameters
        Value::Param { param } => params
            .get(param)
            .copied()
            .ok_or_else(|| EvalError::ParameterNotFound(param.clone())),

        // Literal: Extract numeric value
        Value::Literal { value: json_value } => {
            if let Some(num) = json_value.as_f64() {
                Ok(num)
            } else if let Some(bool_val) = json_value.as_bool() {
                // Convert boolean to float (true = 1.0, false = 0.0)
                Ok(if bool_val { 1.0 } else { 0.0 })
            } else if let Some(int_val) = json_value.as_i64() {
                // Convert integer to float
                Ok(int_val as f64)
            } else {
                Err(EvalError::InvalidLiteralType)
            }
        }

        // Computation: Recursively evaluate arithmetic expression
        Value::Compute { compute } => evaluate_computation(compute, context, params),
    }
}

// ============================================================================
// COMPUTATION EVALUATION (Phase 6.4)
// ============================================================================

/// Evaluate an arithmetic computation
///
/// # Arguments
///
/// * `computation` - Computation to evaluate
/// * `context` - Evaluation context
/// * `params` - Tree parameters
///
/// # Returns
///
/// Ok(f64) if computation succeeds, Err otherwise
pub fn evaluate_computation(
    computation: &Computation,
    context: &EvalContext,
    params: &HashMap<String, f64>,
) -> Result<f64, EvalError> {
    match computation {
        Computation::Add { left, right } => {
            let left_val = evaluate_value(left, context, params)?;
            let right_val = evaluate_value(right, context, params)?;
            Ok(left_val + right_val)
        }

        Computation::Subtract { left, right } => {
            let left_val = evaluate_value(left, context, params)?;
            let right_val = evaluate_value(right, context, params)?;
            Ok(left_val - right_val)
        }

        Computation::Multiply { left, right } => {
            let left_val = evaluate_value(left, context, params)?;
            let right_val = evaluate_value(right, context, params)?;
            Ok(left_val * right_val)
        }

        Computation::Divide { left, right } => {
            let left_val = evaluate_value(left, context, params)?;
            let right_val = evaluate_value(right, context, params)?;

            // Check for division by zero
            if right_val.abs() < f64::EPSILON {
                return Err(EvalError::DivisionByZero);
            }

            Ok(left_val / right_val)
        }

        Computation::Max { values } => {
            if values.is_empty() {
                return Err(EvalError::EmptyValueList);
            }

            let mut max_val = f64::NEG_INFINITY;
            for value in values {
                let val = evaluate_value(value, context, params)?;
                if val > max_val {
                    max_val = val;
                }
            }
            Ok(max_val)
        }

        Computation::Min { values } => {
            if values.is_empty() {
                return Err(EvalError::EmptyValueList);
            }

            let mut min_val = f64::INFINITY;
            for value in values {
                let val = evaluate_value(value, context, params)?;
                if val < min_val {
                    min_val = val;
                }
            }
            Ok(min_val)
        }

        // Phase 2.3: Math Helper Functions (Policy Enhancements V2)
        Computation::Ceil { value } => {
            let val = evaluate_value(value, context, params)?;
            Ok(val.ceil())
        }

        Computation::Floor { value } => {
            let val = evaluate_value(value, context, params)?;
            Ok(val.floor())
        }

        Computation::Round { value } => {
            let val = evaluate_value(value, context, params)?;
            Ok(val.round())
        }

        Computation::Abs { value } => {
            let val = evaluate_value(value, context, params)?;
            Ok(val.abs())
        }

        Computation::Clamp { value, min, max } => {
            let val = evaluate_value(value, context, params)?;
            let min_val = evaluate_value(min, context, params)?;
            let max_val = evaluate_value(max, context, params)?;

            // Clamp: constrain value to [min, max]
            Ok(val.max(min_val).min(max_val))
        }

        Computation::SafeDiv {
            numerator,
            denominator,
            default,
        } => {
            let num = evaluate_value(numerator, context, params)?;
            let denom = evaluate_value(denominator, context, params)?;

            // Check for zero or near-zero denominator
            // Use epsilon threshold to avoid numerical issues
            const EPSILON: f64 = 1e-9;
            if denom.abs() < EPSILON {
                // Return default value instead of error
                evaluate_value(default, context, params)
            } else {
                Ok(num / denom)
            }
        }
    }
}

// ============================================================================
// EXPRESSION EVALUATION (Phase 6.5 & 6.6)
// ============================================================================

/// Epsilon for floating point equality comparison
const FLOAT_EPSILON: f64 = 1e-9;

/// Evaluate a boolean expression
///
/// # Arguments
///
/// * `expr` - Expression to evaluate
/// * `context` - Evaluation context
/// * `params` - Tree parameters
///
/// # Returns
///
/// Ok(bool) if evaluation succeeds, Err otherwise
///
/// # Example
///
/// ```rust
/// use payment_simulator_core_rs::policy::tree::{Expression, Value, EvalContext};
/// use payment_simulator_core_rs::{Agent, Transaction, SimulationState};
/// use payment_simulator_core_rs::orchestrator::CostRates;
/// use std::collections::HashMap;
///
/// # fn main() -> Result<(), Box<dyn std::error::Error>> {
/// let agent = Agent::new("BANK_A".to_string(), 1_000_000, 0);
/// let tx = Transaction::new("BANK_A".to_string(), "BANK_B".to_string(), 100_000, 0, 100);
/// let state = SimulationState::new(vec![agent.clone()]);
/// let cost_rates = CostRates::default();
/// let context = EvalContext::build(&tx, &agent, &state, 10, &cost_rates, 100, 0.8);
/// let params = HashMap::new();
///
/// let expr = Expression::GreaterThan {
///     left: Value::Field { field: "balance".to_string() },
///     right: Value::Field { field: "amount".to_string() },
/// };
/// let result = payment_simulator_core_rs::policy::tree::evaluate_expression(&expr, &context, &params)?;
/// assert!(result); // 1_000_000 > 100_000
/// # Ok(())
/// # }
/// ```
pub fn evaluate_expression(
    expr: &Expression,
    context: &EvalContext,
    params: &HashMap<String, f64>,
) -> Result<bool, EvalError> {
    match expr {
        // Comparison operators
        Expression::Equal { left, right } => {
            let left_val = evaluate_value(left, context, params)?;
            let right_val = evaluate_value(right, context, params)?;
            Ok((left_val - right_val).abs() < FLOAT_EPSILON)
        }

        Expression::NotEqual { left, right } => {
            let left_val = evaluate_value(left, context, params)?;
            let right_val = evaluate_value(right, context, params)?;
            Ok((left_val - right_val).abs() >= FLOAT_EPSILON)
        }

        Expression::LessThan { left, right } => {
            let left_val = evaluate_value(left, context, params)?;
            let right_val = evaluate_value(right, context, params)?;
            Ok(left_val < right_val)
        }

        Expression::LessOrEqual { left, right } => {
            let left_val = evaluate_value(left, context, params)?;
            let right_val = evaluate_value(right, context, params)?;
            Ok(left_val <= right_val || (left_val - right_val).abs() < FLOAT_EPSILON)
        }

        Expression::GreaterThan { left, right } => {
            let left_val = evaluate_value(left, context, params)?;
            let right_val = evaluate_value(right, context, params)?;
            Ok(left_val > right_val)
        }

        Expression::GreaterOrEqual { left, right } => {
            let left_val = evaluate_value(left, context, params)?;
            let right_val = evaluate_value(right, context, params)?;
            Ok(left_val >= right_val || (left_val - right_val).abs() < FLOAT_EPSILON)
        }

        // Logical operators (with short-circuit evaluation)
        Expression::And { conditions } => {
            for condition in conditions {
                if !evaluate_expression(condition, context, params)? {
                    // Short-circuit: if any condition is false, return false immediately
                    return Ok(false);
                }
            }
            // All conditions true
            Ok(true)
        }

        Expression::Or { conditions } => {
            for condition in conditions {
                if evaluate_expression(condition, context, params)? {
                    // Short-circuit: if any condition is true, return true immediately
                    return Ok(true);
                }
            }
            // All conditions false
            Ok(false)
        }

        Expression::Not { condition } => {
            let result = evaluate_expression(condition, context, params)?;
            Ok(!result)
        }
    }
}

// ============================================================================
// TREE TRAVERSAL (Phase 6.7)
// ============================================================================

/// Maximum tree depth to prevent infinite recursion
const MAX_TREE_DEPTH: usize = 100;

/// Traverse a decision tree to find the action node
///
/// Evaluates condition nodes recursively until reaching an action node.
/// Implements depth limiting to prevent infinite recursion.
///
/// # Arguments
///
/// * `tree` - Decision tree definition
/// * `context` - Evaluation context
///
/// # Returns
///
/// Ok(&TreeNode::Action) if traversal succeeds, Err otherwise
///
/// # Example
///
/// ```rust
/// use payment_simulator_core_rs::policy::tree::{DecisionTreeDef, EvalContext, traverse_tree};
/// use payment_simulator_core_rs::{Agent, Transaction, SimulationState};
/// use payment_simulator_core_rs::orchestrator::CostRates;
///
/// # fn main() -> Result<(), Box<dyn std::error::Error>> {
/// let agent = Agent::new("BANK_A".to_string(), 1_000_000, 0);
/// let tx = Transaction::new("BANK_A".to_string(), "BANK_B".to_string(), 100_000, 0, 100);
/// let state = SimulationState::new(vec![agent.clone()]);
/// let cost_rates = CostRates::default();
/// let context = EvalContext::build(&tx, &agent, &state, 10, &cost_rates, 100, 0.8);
///
/// // Simple always-release policy
/// let json = r#"{
///   "version": "1.0",
///   "policy_id": "test_policy",
///   "payment_tree": {
///     "type": "action",
///     "node_id": "A1",
///     "action": "Release"
///   }
/// }"#;
/// let tree: DecisionTreeDef = serde_json::from_str(json)?;
/// let action_node = traverse_tree(&tree, &context)?;
/// # Ok(())
/// # }
/// ```
pub fn traverse_tree<'a>(
    tree: &'a DecisionTreeDef,
    context: &EvalContext,
) -> Result<&'a TreeNode, EvalError> {
    // For backward compatibility, traverse payment_tree by default
    let root = tree
        .payment_tree
        .as_ref()
        .ok_or_else(|| EvalError::InvalidTree("payment_tree is not defined".to_string()))?;
    traverse_node(root, context, &tree.parameters, 0)
}

/// Traverse the strategic collateral tree to reach an action node.
///
/// Returns the terminal action node reached.
/// Returns error if strategic_collateral_tree is not defined.
pub fn traverse_strategic_collateral_tree<'a>(
    tree: &'a DecisionTreeDef,
    context: &EvalContext,
) -> Result<&'a TreeNode, EvalError> {
    let root = tree.strategic_collateral_tree.as_ref().ok_or_else(|| {
        EvalError::InvalidTree("strategic_collateral_tree is not defined".to_string())
    })?;
    traverse_node(root, context, &tree.parameters, 0)
}

/// Traverse the end-of-tick collateral tree to reach an action node.
///
/// Returns the terminal action node reached.
/// Returns error if end_of_tick_collateral_tree is not defined.
pub fn traverse_end_of_tick_collateral_tree<'a>(
    tree: &'a DecisionTreeDef,
    context: &EvalContext,
) -> Result<&'a TreeNode, EvalError> {
    let root = tree.end_of_tick_collateral_tree.as_ref().ok_or_else(|| {
        EvalError::InvalidTree("end_of_tick_collateral_tree is not defined".to_string())
    })?;
    traverse_node(root, context, &tree.parameters, 0)
}

/// Traverse the bank-level decision tree to reach an action node (Phase 3.3)
///
/// Returns the terminal action node reached.
/// Returns error if bank_tree is not defined.
pub fn traverse_bank_tree<'a>(
    tree: &'a DecisionTreeDef,
    context: &EvalContext,
) -> Result<&'a TreeNode, EvalError> {
    let root = tree.bank_tree.as_ref().ok_or_else(|| {
        EvalError::InvalidTree("bank_tree is not defined".to_string())
    })?;
    traverse_node(root, context, &tree.parameters, 0)
}

/// Internal recursive tree traversal with depth tracking
fn traverse_node<'a>(
    node: &'a TreeNode,
    context: &EvalContext,
    params: &HashMap<String, f64>,
    depth: usize,
) -> Result<&'a TreeNode, EvalError> {
    // Check depth limit
    if depth > MAX_TREE_DEPTH {
        return Err(EvalError::MaxDepthExceeded);
    }

    match node {
        TreeNode::Action { .. } => {
            // Reached action node, return it
            Ok(node)
        }

        TreeNode::Condition {
            condition,
            on_true,
            on_false,
            ..
        } => {
            // Evaluate condition
            let result = evaluate_expression(condition, context, params)?;

            // Traverse appropriate branch
            let next_node = if result { on_true } else { on_false };
            traverse_node(next_node, context, params, depth + 1)
        }
    }
}

// ============================================================================
// ACTION BUILDING (Phase 6.8)
// ============================================================================

/// Build a ReleaseDecision from an action node
///
/// Converts ActionType and its parameters into a policy decision.
/// Action parameters are evaluated using the context (e.g., computing num_splits).
///
/// # Arguments
///
/// * `action_node` - Action node from tree traversal
/// * `tx_id` - Transaction ID to include in decision
/// * `context` - Evaluation context
/// * `params` - Tree parameters
///
/// # Returns
///
/// Ok(ReleaseDecision) if conversion succeeds, Err otherwise
///
/// # Example
///
/// ```rust
/// use payment_simulator_core_rs::policy::tree::{build_decision, TreeNode, ActionType, EvalContext};
/// use payment_simulator_core_rs::{Agent, Transaction, SimulationState};
/// use payment_simulator_core_rs::orchestrator::CostRates;
/// use std::collections::HashMap;
///
/// # fn main() -> Result<(), Box<dyn std::error::Error>> {
/// let agent = Agent::new("BANK_A".to_string(), 1_000_000, 0);
/// let tx = Transaction::new("BANK_A".to_string(), "BANK_B".to_string(), 100_000, 0, 100);
/// let tx_id = tx.id().to_string();
/// let state = SimulationState::new(vec![agent.clone()]);
/// let cost_rates = CostRates::default();
/// let context = EvalContext::build(&tx, &agent, &state, 10, &cost_rates, 100, 0.8);
///
/// // Create action node directly for testing
/// let action_node = TreeNode::Action {
///     node_id: "A1".to_string(),
///     action: ActionType::Release,
///     parameters: HashMap::new(),
/// };
///
/// let params = HashMap::new();
/// let decision = build_decision(&action_node, tx_id, &context, &params)?;
/// # Ok(())
/// # }
/// ```
pub fn build_decision(
    action_node: &TreeNode,
    tx_id: String,
    context: &EvalContext,
    params: &HashMap<String, f64>,
) -> Result<ReleaseDecision, EvalError> {
    use crate::policy::tree::types::ActionType;

    // Verify this is an action node
    let (action, action_params) = match action_node {
        TreeNode::Action {
            action, parameters, ..
        } => (action, parameters),
        TreeNode::Condition { .. } => {
            return Err(EvalError::ExpectedActionNode);
        }
    };

    // Convert ActionType to ReleaseDecision
    match action {
        ActionType::Release => {
            // Phase 3.2: Parse optional RTGS flags

            // Parse priority_flag parameter (optional)
            let priority_override = if let Some(priority_flag_value) = action_params.get("priority_flag") {
                // Extract string value from ValueOrCompute
                use crate::policy::tree::types::ValueOrCompute;
                match priority_flag_value {
                    ValueOrCompute::Direct { value } => {
                        if let Some(flag_str) = value.as_str() {
                            // Map priority string to numeric value
                            let priority = match flag_str {
                                "HIGH" => 10,
                                "MEDIUM" => 5,
                                "LOW" => 1,
                                _ => 5, // Default to MEDIUM for invalid values
                            };
                            Some(priority)
                        } else {
                            None
                        }
                    }
                    _ => None,
                }
            } else {
                None
            };

            // Parse timed_for_tick parameter (optional)
            let target_tick = if action_params.contains_key("timed_for_tick") {
                let tick_f64 = evaluate_action_parameter(action_params, "timed_for_tick", context, params)?;
                Some(tick_f64 as usize)
            } else {
                None
            };

            Ok(ReleaseDecision::SubmitFull {
                tx_id,
                priority_override,
                target_tick,
            })
        }

        ActionType::ReleaseWithCredit => {
            // Same as Release - credit usage is handled by settlement engine
            // Parse RTGS flags same as Release
            use crate::policy::tree::types::ValueOrCompute;

            let priority_override = if let Some(priority_flag_value) = action_params.get("priority_flag") {
                match priority_flag_value {
                    ValueOrCompute::Direct { value } => {
                        if let Some(flag_str) = value.as_str() {
                            let priority = match flag_str {
                                "HIGH" => 10,
                                "MEDIUM" => 5,
                                "LOW" => 1,
                                _ => 5,
                            };
                            Some(priority)
                        } else {
                            None
                        }
                    }
                    _ => None,
                }
            } else {
                None
            };

            let target_tick = if action_params.contains_key("timed_for_tick") {
                let tick_f64 = evaluate_action_parameter(action_params, "timed_for_tick", context, params)?;
                Some(tick_f64 as usize)
            } else {
                None
            };

            Ok(ReleaseDecision::SubmitFull {
                tx_id,
                priority_override,
                target_tick,
            })
        }

        ActionType::PaceAndRelease => {
            // Need num_splits parameter
            let num_splits =
                evaluate_action_parameter(action_params, "num_splits", context, params)?;
            let num_splits_usize = num_splits as usize;

            if num_splits_usize < 2 {
                return Err(EvalError::InvalidActionParameter(
                    "num_splits must be >= 2".to_string(),
                ));
            }

            Ok(ReleaseDecision::SubmitPartial {
                tx_id,
                num_splits: num_splits_usize,
            })
        }

        ActionType::Split => {
            // Same as PaceAndRelease - split transaction into num_splits parts
            let num_splits =
                evaluate_action_parameter(action_params, "num_splits", context, params)?;
            let num_splits_usize = num_splits as usize;

            if num_splits_usize < 2 {
                return Err(EvalError::InvalidActionParameter(
                    "num_splits must be >= 2".to_string(),
                ));
            }

            Ok(ReleaseDecision::SubmitPartial {
                tx_id,
                num_splits: num_splits_usize,
            })
        }

        ActionType::StaggerSplit => {
            // Phase 3.1: Split with staggered timing
            let num_splits =
                evaluate_action_parameter(action_params, "num_splits", context, params)?;
            let num_splits_usize = num_splits as usize;

            let stagger_first_now =
                evaluate_action_parameter(action_params, "stagger_first_now", context, params)?;
            let stagger_first_now_usize = stagger_first_now as usize;

            let stagger_gap_ticks =
                evaluate_action_parameter(action_params, "stagger_gap_ticks", context, params)?;
            let stagger_gap_ticks_usize = stagger_gap_ticks as usize;

            let priority_boost_children = evaluate_action_parameter(
                action_params,
                "priority_boost_children",
                context,
                params,
            )?;
            let priority_boost_u8 = if priority_boost_children < 0.0 {
                0
            } else if priority_boost_children > 255.0 {
                255
            } else {
                priority_boost_children as u8
            };

            // Validation
            if num_splits_usize < 2 {
                return Err(EvalError::InvalidActionParameter(
                    "num_splits must be >= 2".to_string(),
                ));
            }

            if stagger_first_now_usize > num_splits_usize {
                return Err(EvalError::InvalidActionParameter(
                    "stagger_first_now cannot exceed num_splits".to_string(),
                ));
            }

            Ok(ReleaseDecision::StaggerSplit {
                tx_id,
                num_splits: num_splits_usize,
                stagger_first_now: stagger_first_now_usize,
                stagger_gap_ticks: stagger_gap_ticks_usize,
                priority_boost_children: priority_boost_u8,
            })
        }

        ActionType::Hold => {
            use crate::policy::tree::types::ValueOrCompute;

            // Parse reason parameter if provided
            let reason = if let Some(reason_value) = action_params.get("reason") {
                // Extract string from ValueOrCompute
                match reason_value {
                    ValueOrCompute::Direct { value } => {
                        if let Some(reason_str) = value.as_str() {
                            match reason_str {
                                "InsufficientLiquidity" => HoldReason::InsufficientLiquidity,
                                "AwaitingInflows" => HoldReason::AwaitingInflows,
                                "LowPriority" => HoldReason::LowPriority,
                                "NearDeadline" => {
                                    // Get ticks_remaining from context
                                    let ticks_remaining = context
                                        .get_field("ticks_to_deadline")
                                        .unwrap_or(0.0)
                                        .max(0.0)
                                        as usize;
                                    HoldReason::NearDeadline { ticks_remaining }
                                }
                                other => HoldReason::Custom(other.to_string()),
                            }
                        } else {
                            HoldReason::Custom("Policy decision".to_string())
                        }
                    }
                    _ => HoldReason::Custom("Policy decision".to_string()),
                }
            } else {
                HoldReason::Custom("Policy decision".to_string())
            };

            Ok(ReleaseDecision::Hold { tx_id, reason })
        }

        ActionType::Drop => Ok(ReleaseDecision::Drop { tx_id }),

        ActionType::Reprioritize => {
            // Phase 4: Extract new_priority parameter
            let new_priority_f64 =
                evaluate_action_parameter(action_params, "new_priority", context, params)?;

            // Convert to u8, capping at 255 (u8::MAX)
            let new_priority = if new_priority_f64 < 0.0 {
                0
            } else if new_priority_f64 > 255.0 {
                255
            } else {
                new_priority_f64 as u8
            };

            Ok(ReleaseDecision::Reprioritize {
                tx_id,
                new_priority,
            })
        }

        // Phase 3.3: Bank-level actions are not valid in payment decision context
        ActionType::SetReleaseBudget => Err(EvalError::InvalidActionType(format!(
            "Bank-level action {:?} cannot be used in payment release decision tree. \
             Bank-level actions require bank_tree evaluation.",
            action
        ))),

        // Phase 8: Collateral actions are not valid in payment decision context
        // These should only appear in collateral-specific decision trees
        ActionType::PostCollateral
        | ActionType::WithdrawCollateral
        | ActionType::HoldCollateral => Err(EvalError::InvalidActionType(format!(
            "Collateral action {:?} cannot be used in payment release decision tree. \
             Collateral actions require separate tree evaluation.",
            action
        ))),
    }
}

/// Build a CollateralDecision from an action node (Phase 8.2)
///
/// Converts collateral ActionType and its parameters into a collateral decision.
/// Action parameters are evaluated using the context.
///
/// # Arguments
///
/// * `action_node` - Action node from tree traversal
/// * `context` - Evaluation context
/// * `params` - Tree parameters
///
/// # Returns
///
/// Ok(CollateralDecision) if conversion succeeds, Err otherwise
pub fn build_collateral_decision(
    action_node: &TreeNode,
    context: &EvalContext,
    params: &HashMap<String, f64>,
) -> Result<crate::policy::CollateralDecision, EvalError> {
    use crate::policy::tree::types::ActionType;
    use crate::policy::{CollateralDecision, CollateralReason};

    // Verify this is an action node
    let (action, action_params) = match action_node {
        TreeNode::Action {
            action, parameters, ..
        } => (action, parameters),
        TreeNode::Condition { .. } => {
            return Err(EvalError::ExpectedActionNode);
        }
    };

    // Convert ActionType to CollateralDecision
    match action {
        ActionType::PostCollateral => {
            // Extract amount parameter (required)
            let amount = evaluate_action_parameter(action_params, "amount", context, params)?;
            let amount_i64 = amount as i64;

            // If amount is zero or negative, treat as no-op (hold)
            if amount_i64 <= 0 {
                return Ok(CollateralDecision::Hold);
            }

            // Extract reason parameter (required)
            let reason = extract_collateral_reason(action_params, context)?;

            // Extract optional auto_withdraw_after_ticks parameter (Phase 3.4)
            let auto_withdraw_after_ticks = if action_params.contains_key("auto_withdraw_after_ticks") {
                let ticks = evaluate_action_parameter(action_params, "auto_withdraw_after_ticks", context, params)?;
                if ticks > 0.0 {
                    Some(ticks as usize)
                } else {
                    None
                }
            } else {
                None
            };

            Ok(CollateralDecision::Post {
                amount: amount_i64,
                reason,
                auto_withdraw_after_ticks,
            })
        }

        ActionType::WithdrawCollateral => {
            // Extract amount parameter (required)
            let amount = evaluate_action_parameter(action_params, "amount", context, params)?;
            let amount_i64 = amount as i64;

            // If amount is zero or negative, treat as no-op (hold)
            if amount_i64 <= 0 {
                return Ok(CollateralDecision::Hold);
            }

            // Extract reason parameter (required)
            let reason = extract_collateral_reason(action_params, context)?;

            Ok(CollateralDecision::Withdraw {
                amount: amount_i64,
                reason,
            })
        }

        ActionType::HoldCollateral => {
            // No parameters needed
            Ok(CollateralDecision::Hold)
        }

        // Payment and bank actions are not valid in collateral decision context
        ActionType::Release
        | ActionType::ReleaseWithCredit
        | ActionType::PaceAndRelease
        | ActionType::Split
        | ActionType::StaggerSplit
        | ActionType::Hold
        | ActionType::Drop
        | ActionType::Reprioritize
        | ActionType::SetReleaseBudget => Err(EvalError::InvalidActionType(format!(
            "Payment/bank action {:?} cannot be used in collateral decision tree. \
             These actions require separate tree evaluation.",
            action
        ))),
    }
}

/// Build a BankDecision from an action node (Phase 3.3: Policy Enhancements V2)
///
/// Converts bank-level ActionType and its parameters into a bank decision.
/// Action parameters are evaluated using the context.
///
/// # Arguments
///
/// * `action_node` - Action node from tree traversal
/// * `context` - Evaluation context
/// * `params` - Tree parameters
///
/// # Returns
///
/// Ok(BankDecision) if conversion succeeds, Err otherwise
///
/// # Example
///
/// ```rust
/// use payment_simulator_core_rs::policy::tree::{TreeNode, ActionType, EvalContext};
/// use payment_simulator_core_rs::policy::BankDecision;
/// use payment_simulator_core_rs::{Agent, SimulationState};
/// use payment_simulator_core_rs::orchestrator::CostRates;
/// use std::collections::HashMap;
///
/// # fn main() -> Result<(), Box<dyn std::error::Error>> {
/// let agent = Agent::new("BANK_A".to_string(), 500_000, 0);
/// let state = SimulationState::new(vec![agent.clone()]);
/// let costs = CostRates::default();
/// let context = EvalContext::bank_level(&agent, &state, 0, &costs, 100, 0.95);
///
/// // Action node with SetReleaseBudget
/// let action_node = TreeNode::Action {
///     node_id: "A1".to_string(),
///     action: ActionType::SetReleaseBudget,
///     parameters: {
///         let mut params = HashMap::new();
///         params.insert(
///             "max_value_to_release".to_string(),
///             payment_simulator_core_rs::policy::tree::types::ValueOrCompute::Direct {
///                 value: serde_json::json!(100_000.0),
///             },
///         );
///         params
///     },
/// };
///
/// let bank_decision = payment_simulator_core_rs::policy::tree::interpreter::build_bank_decision(
///     &action_node,
///     &context,
///     &HashMap::new(),
/// )?;
///
/// match bank_decision {
///     BankDecision::SetReleaseBudget { max_value_to_release, .. } => {
///         assert_eq!(max_value_to_release, 100_000);
///     }
///     _ => panic!("Expected SetReleaseBudget"),
/// }
/// # Ok(())
/// # }
/// ```
pub fn build_bank_decision(
    action_node: &TreeNode,
    context: &EvalContext,
    params: &HashMap<String, f64>,
) -> Result<crate::policy::BankDecision, EvalError> {
    use crate::policy::tree::types::ActionType;
    use crate::policy::BankDecision;

    // Verify this is an action node
    let (action, action_params) = match action_node {
        TreeNode::Action {
            action, parameters, ..
        } => (action, parameters),
        TreeNode::Condition { .. } => {
            return Err(EvalError::ExpectedActionNode);
        }
    };

    // Convert ActionType to BankDecision
    match action {
        ActionType::SetReleaseBudget => {
            // Extract max_value_to_release parameter (required)
            let max_value_f64 = evaluate_action_parameter(
                action_params,
                "max_value_to_release",
                context,
                params,
            )?;
            let max_value_to_release = max_value_f64 as i64;

            // Extract focus_counterparties parameter (optional)
            // This should be a list of counterparty IDs
            let focus_counterparties = if let Some(focus_value) = action_params.get("focus_counterparties") {
                use crate::policy::tree::types::ValueOrCompute;
                match focus_value {
                    ValueOrCompute::Direct { value } => {
                        // Expect a JSON array of strings
                        if let Some(array) = value.as_array() {
                            let counterparties: Vec<String> = array
                                .iter()
                                .filter_map(|v| v.as_str())
                                .map(|s| s.to_string())
                                .collect();
                            if counterparties.is_empty() {
                                None
                            } else {
                                Some(counterparties)
                            }
                        } else {
                            None
                        }
                    }
                    _ => None,
                }
            } else {
                None
            };

            // Extract max_per_counterparty parameter (optional)
            let max_per_counterparty = if action_params.contains_key("max_per_counterparty") {
                let value_f64 = evaluate_action_parameter(
                    action_params,
                    "max_per_counterparty",
                    context,
                    params,
                )?;
                Some(value_f64 as i64)
            } else {
                None
            };

            Ok(BankDecision::SetReleaseBudget {
                max_value_to_release,
                focus_counterparties,
                max_per_counterparty,
            })
        }

        // All other actions are not valid in bank decision context
        _ => {
            // Bank tree can have NoAction nodes (do nothing this tick)
            // Any action that's not SetReleaseBudget becomes NoAction
            Ok(BankDecision::NoAction)
        }
    }
}

/// Extract CollateralReason from action parameters
fn extract_collateral_reason(
    action_params: &HashMap<String, ValueOrCompute>,
    _context: &EvalContext,
) -> Result<crate::policy::CollateralReason, EvalError> {
    use crate::policy::tree::types::ValueOrCompute;
    use crate::policy::CollateralReason;

    let reason = if let Some(reason_value) = action_params.get("reason") {
        match reason_value {
            ValueOrCompute::Direct { value } => {
                if let Some(reason_str) = value.as_str() {
                    match reason_str {
                        "UrgentLiquidityNeed" => CollateralReason::UrgentLiquidityNeed,
                        "PreemptivePosting" => CollateralReason::PreemptivePosting,
                        "LiquidityRestored" => CollateralReason::LiquidityRestored,
                        "EndOfDayCleanup" => CollateralReason::EndOfDayCleanup,
                        "DeadlineEmergency" => CollateralReason::DeadlineEmergency,
                        "CostOptimization" => CollateralReason::CostOptimization,
                        _ => CollateralReason::UrgentLiquidityNeed, // Default
                    }
                } else {
                    CollateralReason::UrgentLiquidityNeed // Default
                }
            }
            _ => CollateralReason::UrgentLiquidityNeed, // Default
        }
    } else {
        // Reason is optional, default to UrgentLiquidityNeed
        CollateralReason::UrgentLiquidityNeed
    };

    Ok(reason)
}

/// Evaluate an action parameter value
///
/// Action parameters can be literals, field references, param references, or computations.
fn evaluate_action_parameter(
    action_params: &HashMap<String, ValueOrCompute>,
    param_name: &str,
    context: &EvalContext,
    params: &HashMap<String, f64>,
) -> Result<f64, EvalError> {
    let value_or_compute = action_params
        .get(param_name)
        .ok_or_else(|| EvalError::MissingActionParameter(param_name.to_string()))?;

    match value_or_compute {
        ValueOrCompute::Direct { value } => {
            // Direct literal value
            if let Some(num) = value.as_f64() {
                Ok(num)
            } else if let Some(int) = value.as_i64() {
                Ok(int as f64)
            } else {
                Err(EvalError::InvalidActionParameter(param_name.to_string()))
            }
        }

        ValueOrCompute::Field { field } => {
            // Field reference
            context
                .get_field(field)
                .map_err(|_| EvalError::FieldNotFound(field.clone()))
        }

        ValueOrCompute::Param { param } => {
            // Parameter reference
            params
                .get(param)
                .copied()
                .ok_or_else(|| EvalError::ParameterNotFound(param.clone()))
        }

        ValueOrCompute::Compute { compute } => {
            // Computation
            evaluate_computation(compute, context, params)
        }
    }
}

// ============================================================================
// TESTS - Phase 6.3, 6.4, 6.5, 6.6, 6.7, 6.8
// ============================================================================

#[cfg(test)]
mod tests {
    use super::*;
    use crate::policy::tree::types::Value;
    use crate::orchestrator::CostRates;
    use crate::{Agent, SimulationState, Transaction};
    use serde_json::json;

    fn create_test_context() -> (EvalContext, HashMap<String, f64>) {
        let tx = Transaction::new("BANK_A".to_string(), "BANK_B".to_string(), 100_000, 0, 50);
        let agent = Agent::new("BANK_A".to_string(), 500_000, 200_000);
        let state = SimulationState::new(vec![agent.clone()]);
        let cost_rates = CostRates::default();

        let context = EvalContext::build(&tx, &agent, &state, 10, &cost_rates, 100, 0.8);

        let mut params = HashMap::new();
        params.insert("threshold".to_string(), 100_000.0);
        params.insert("multiplier".to_string(), 1.5);

        (context, params)
    }

    // ========================================================================
    // Phase 6.3: Value Evaluation Tests
    // ========================================================================

    #[test]
    fn test_eval_field_reference() {
        let (context, params) = create_test_context();
        let value = Value::Field {
            field: "balance".to_string(),
        };

        let result = evaluate_value(&value, &context, &params).unwrap();
        assert_eq!(result, 500_000.0);
    }

    #[test]
    fn test_eval_param_reference() {
        let (context, params) = create_test_context();
        let value = Value::Param {
            param: "threshold".to_string(),
        };

        let result = evaluate_value(&value, &context, &params).unwrap();
        assert_eq!(result, 100_000.0);
    }

    #[test]
    fn test_eval_literal_number() {
        let (context, params) = create_test_context();
        let value = Value::Literal { value: json!(42.0) };

        let result = evaluate_value(&value, &context, &params).unwrap();
        assert_eq!(result, 42.0);
    }

    #[test]
    fn test_eval_literal_integer() {
        let (context, params) = create_test_context();
        let value = Value::Literal { value: json!(42) };

        let result = evaluate_value(&value, &context, &params).unwrap();
        assert_eq!(result, 42.0);
    }

    #[test]
    fn test_eval_literal_boolean() {
        let (context, params) = create_test_context();

        let value_true = Value::Literal { value: json!(true) };
        let result_true = evaluate_value(&value_true, &context, &params).unwrap();
        assert_eq!(result_true, 1.0);

        let value_false = Value::Literal {
            value: json!(false),
        };
        let result_false = evaluate_value(&value_false, &context, &params).unwrap();
        assert_eq!(result_false, 0.0);
    }

    #[test]
    fn test_eval_missing_field_error() {
        let (context, params) = create_test_context();
        let value = Value::Field {
            field: "nonexistent_field".to_string(),
        };

        let result = evaluate_value(&value, &context, &params);
        assert!(result.is_err());

        match result {
            Err(EvalError::FieldNotFound(field)) => {
                assert_eq!(field, "nonexistent_field");
            }
            _ => panic!("Expected FieldNotFound error"),
        }
    }

    #[test]
    fn test_eval_missing_param_error() {
        let (context, params) = create_test_context();
        let value = Value::Param {
            param: "nonexistent_param".to_string(),
        };

        let result = evaluate_value(&value, &context, &params);
        assert!(result.is_err());

        match result {
            Err(EvalError::ParameterNotFound(param)) => {
                assert_eq!(param, "nonexistent_param");
            }
            _ => panic!("Expected ParameterNotFound error"),
        }
    }

    // ========================================================================
    // Phase 6.4: Computation Evaluation Tests
    // ========================================================================

    #[test]
    fn test_eval_add_computation() {
        let (context, params) = create_test_context();
        let computation = Computation::Add {
            left: Value::Literal { value: json!(10) },
            right: Value::Literal { value: json!(20) },
        };

        let result = evaluate_computation(&computation, &context, &params).unwrap();
        assert_eq!(result, 30.0);
    }

    #[test]
    fn test_eval_subtract_computation() {
        let (context, params) = create_test_context();
        let computation = Computation::Subtract {
            left: Value::Literal { value: json!(50) },
            right: Value::Literal { value: json!(30) },
        };

        let result = evaluate_computation(&computation, &context, &params).unwrap();
        assert_eq!(result, 20.0);
    }

    #[test]
    fn test_eval_multiply_computation() {
        let (context, params) = create_test_context();
        let computation = Computation::Multiply {
            left: Value::Literal { value: json!(5) },
            right: Value::Literal { value: json!(7) },
        };

        let result = evaluate_computation(&computation, &context, &params).unwrap();
        assert_eq!(result, 35.0);
    }

    #[test]
    fn test_eval_divide_computation() {
        let (context, params) = create_test_context();
        let computation = Computation::Divide {
            left: Value::Literal { value: json!(100) },
            right: Value::Literal { value: json!(4) },
        };

        let result = evaluate_computation(&computation, &context, &params).unwrap();
        assert_eq!(result, 25.0);
    }

    #[test]
    fn test_eval_divide_by_zero_error() {
        let (context, params) = create_test_context();
        let computation = Computation::Divide {
            left: Value::Literal { value: json!(100) },
            right: Value::Literal { value: json!(0) },
        };

        let result = evaluate_computation(&computation, &context, &params);
        assert!(result.is_err());

        match result {
            Err(EvalError::DivisionByZero) => {}
            _ => panic!("Expected DivisionByZero error"),
        }
    }

    #[test]
    fn test_eval_max_computation() {
        let (context, params) = create_test_context();
        let computation = Computation::Max {
            values: vec![
                Value::Literal { value: json!(10) },
                Value::Literal { value: json!(50) },
                Value::Literal { value: json!(30) },
            ],
        };

        let result = evaluate_computation(&computation, &context, &params).unwrap();
        assert_eq!(result, 50.0);
    }

    #[test]
    fn test_eval_min_computation() {
        let (context, params) = create_test_context();
        let computation = Computation::Min {
            values: vec![
                Value::Literal { value: json!(10) },
                Value::Literal { value: json!(50) },
                Value::Literal { value: json!(30) },
            ],
        };

        let result = evaluate_computation(&computation, &context, &params).unwrap();
        assert_eq!(result, 10.0);
    }

    #[test]
    fn test_eval_empty_max_error() {
        let (context, params) = create_test_context();
        let computation = Computation::Max { values: vec![] };

        let result = evaluate_computation(&computation, &context, &params);
        assert!(result.is_err());

        match result {
            Err(EvalError::EmptyValueList) => {}
            _ => panic!("Expected EmptyValueList error"),
        }
    }

    #[test]
    fn test_eval_computation_with_field_reference() {
        let (context, params) = create_test_context();

        // balance + 100000
        let computation = Computation::Add {
            left: Value::Field {
                field: "balance".to_string(),
            },
            right: Value::Literal {
                value: json!(100_000),
            },
        };

        let result = evaluate_computation(&computation, &context, &params).unwrap();
        assert_eq!(result, 600_000.0); // 500000 + 100000
    }

    #[test]
    fn test_eval_nested_computation() {
        let (context, params) = create_test_context();

        // (balance + credit_limit) / 2
        let computation = Computation::Divide {
            left: Value::Compute {
                compute: Box::new(Computation::Add {
                    left: Value::Field {
                        field: "balance".to_string(),
                    },
                    right: Value::Field {
                        field: "credit_limit".to_string(),
                    },
                }),
            },
            right: Value::Literal { value: json!(2) },
        };

        let result = evaluate_computation(&computation, &context, &params).unwrap();
        assert_eq!(result, 350_000.0); // (500000 + 200000) / 2
    }

    // ========================================================================
    // Phase 6.5: Comparison Expression Tests
    // ========================================================================

    #[test]
    fn test_eval_equal_expression() {
        let (context, params) = create_test_context();

        // balance == 500000 (should be true)
        let expr = Expression::Equal {
            left: Value::Field {
                field: "balance".to_string(),
            },
            right: Value::Literal {
                value: json!(500_000),
            },
        };

        let result = evaluate_expression(&expr, &context, &params).unwrap();
        assert!(result);
    }

    #[test]
    fn test_eval_not_equal_expression() {
        let (context, params) = create_test_context();

        // balance != 1000000 (should be true)
        let expr = Expression::NotEqual {
            left: Value::Field {
                field: "balance".to_string(),
            },
            right: Value::Literal {
                value: json!(1_000_000),
            },
        };

        let result = evaluate_expression(&expr, &context, &params).unwrap();
        assert!(result);
    }

    #[test]
    fn test_eval_less_than_expression() {
        let (context, params) = create_test_context();

        // amount < balance (100000 < 500000, should be true)
        let expr = Expression::LessThan {
            left: Value::Field {
                field: "amount".to_string(),
            },
            right: Value::Field {
                field: "balance".to_string(),
            },
        };

        let result = evaluate_expression(&expr, &context, &params).unwrap();
        assert!(result);
    }

    #[test]
    fn test_eval_less_or_equal_expression() {
        let (context, params) = create_test_context();

        // amount <= amount (should be true)
        let expr = Expression::LessOrEqual {
            left: Value::Field {
                field: "amount".to_string(),
            },
            right: Value::Field {
                field: "amount".to_string(),
            },
        };

        let result = evaluate_expression(&expr, &context, &params).unwrap();
        assert!(result);
    }

    #[test]
    fn test_eval_greater_than_expression() {
        let (context, params) = create_test_context();

        // balance > amount (500000 > 100000, should be true)
        let expr = Expression::GreaterThan {
            left: Value::Field {
                field: "balance".to_string(),
            },
            right: Value::Field {
                field: "amount".to_string(),
            },
        };

        let result = evaluate_expression(&expr, &context, &params).unwrap();
        assert!(result);
    }

    #[test]
    fn test_eval_greater_or_equal_expression() {
        let (context, params) = create_test_context();

        // balance >= balance (should be true)
        let expr = Expression::GreaterOrEqual {
            left: Value::Field {
                field: "balance".to_string(),
            },
            right: Value::Field {
                field: "balance".to_string(),
            },
        };

        let result = evaluate_expression(&expr, &context, &params).unwrap();
        assert!(result);
    }

    #[test]
    fn test_eval_comparison_with_epsilon() {
        let (context, params) = create_test_context();

        // Test that very close float values are considered equal
        // 500000.0 == 500000.0000000001 (within epsilon)
        let expr = Expression::Equal {
            left: Value::Literal {
                value: json!(500_000.0),
            },
            right: Value::Literal {
                value: json!(500_000.0000000001),
            },
        };

        let result = evaluate_expression(&expr, &context, &params).unwrap();
        assert!(result);
    }

    // ========================================================================
    // Phase 6.6: Logical Expression Tests
    // ========================================================================

    #[test]
    fn test_eval_and_expression() {
        let (context, params) = create_test_context();

        // balance > 0 && amount < 1000000
        let expr = Expression::And {
            conditions: vec![
                Expression::GreaterThan {
                    left: Value::Field {
                        field: "balance".to_string(),
                    },
                    right: Value::Literal { value: json!(0) },
                },
                Expression::LessThan {
                    left: Value::Field {
                        field: "amount".to_string(),
                    },
                    right: Value::Literal {
                        value: json!(1_000_000),
                    },
                },
            ],
        };

        let result = evaluate_expression(&expr, &context, &params).unwrap();
        assert!(result);
    }

    #[test]
    fn test_eval_or_expression() {
        let (context, params) = create_test_context();

        // balance > 1000000 || amount < 1000000 (first false, second true)
        let expr = Expression::Or {
            conditions: vec![
                Expression::GreaterThan {
                    left: Value::Field {
                        field: "balance".to_string(),
                    },
                    right: Value::Literal {
                        value: json!(1_000_000),
                    },
                },
                Expression::LessThan {
                    left: Value::Field {
                        field: "amount".to_string(),
                    },
                    right: Value::Literal {
                        value: json!(1_000_000),
                    },
                },
            ],
        };

        let result = evaluate_expression(&expr, &context, &params).unwrap();
        assert!(result);
    }

    #[test]
    fn test_eval_not_expression() {
        let (context, params) = create_test_context();

        // !(balance > 1000000) (balance is 500000, so > 1000000 is false, NOT false is true)
        let expr = Expression::Not {
            condition: Box::new(Expression::GreaterThan {
                left: Value::Field {
                    field: "balance".to_string(),
                },
                right: Value::Literal {
                    value: json!(1_000_000),
                },
            }),
        };

        let result = evaluate_expression(&expr, &context, &params).unwrap();
        assert!(result);
    }

    #[test]
    fn test_eval_short_circuit_and() {
        let (context, params) = create_test_context();

        // balance < 0 && (nonexistent_field > 0)
        // First condition is false, so second should not be evaluated (and not error)
        let expr = Expression::And {
            conditions: vec![
                Expression::LessThan {
                    left: Value::Field {
                        field: "balance".to_string(),
                    },
                    right: Value::Literal { value: json!(0) },
                },
                // This would error if evaluated (field doesn't exist)
                Expression::GreaterThan {
                    left: Value::Field {
                        field: "nonexistent_field".to_string(),
                    },
                    right: Value::Literal { value: json!(0) },
                },
            ],
        };

        let result = evaluate_expression(&expr, &context, &params).unwrap();
        assert!(!result); // Should be false, not error
    }

    #[test]
    fn test_eval_short_circuit_or() {
        let (context, params) = create_test_context();

        // balance > 0 || (nonexistent_field > 0)
        // First condition is true, so second should not be evaluated (and not error)
        let expr = Expression::Or {
            conditions: vec![
                Expression::GreaterThan {
                    left: Value::Field {
                        field: "balance".to_string(),
                    },
                    right: Value::Literal { value: json!(0) },
                },
                // This would error if evaluated (field doesn't exist)
                Expression::GreaterThan {
                    left: Value::Field {
                        field: "nonexistent_field".to_string(),
                    },
                    right: Value::Literal { value: json!(0) },
                },
            ],
        };

        let result = evaluate_expression(&expr, &context, &params).unwrap();
        assert!(result); // Should be true, not error
    }

    #[test]
    fn test_eval_nested_logical() {
        let (context, params) = create_test_context();

        // (balance > 0 && amount < 1000000) || (balance < 0 && amount > 1000000)
        // First part true (balance=500000, amount=100000), so entire expression true
        let expr = Expression::Or {
            conditions: vec![
                Expression::And {
                    conditions: vec![
                        Expression::GreaterThan {
                            left: Value::Field {
                                field: "balance".to_string(),
                            },
                            right: Value::Literal { value: json!(0) },
                        },
                        Expression::LessThan {
                            left: Value::Field {
                                field: "amount".to_string(),
                            },
                            right: Value::Literal {
                                value: json!(1_000_000),
                            },
                        },
                    ],
                },
                Expression::And {
                    conditions: vec![
                        Expression::LessThan {
                            left: Value::Field {
                                field: "balance".to_string(),
                            },
                            right: Value::Literal { value: json!(0) },
                        },
                        Expression::GreaterThan {
                            left: Value::Field {
                                field: "amount".to_string(),
                            },
                            right: Value::Literal {
                                value: json!(1_000_000),
                            },
                        },
                    ],
                },
            ],
        };

        let result = evaluate_expression(&expr, &context, &params).unwrap();
        assert!(result);
    }

    // ========================================================================
    // Phase 6.7: Tree Traversal Tests
    // ========================================================================

    use crate::policy::tree::types::{ActionType, DecisionTreeDef, TreeNode};

    #[test]
    fn test_traverse_simple_tree() {
        let (context, _params) = create_test_context();

        // Simple tree: if balance > amount then Release else Hold
        let tree = DecisionTreeDef {
            version: "1.0".to_string(),
            policy_id: "simple_test".to_string(),
            description: None,
            bank_tree: None,
            payment_tree: Some(TreeNode::Condition {
                node_id: "N1".to_string(),
                description: "Check if balance > amount".to_string(),
                condition: Expression::GreaterThan {
                    left: Value::Field {
                        field: "balance".to_string(),
                    },
                    right: Value::Field {
                        field: "amount".to_string(),
                    },
                },
                on_true: Box::new(TreeNode::Action {
                    node_id: "A1".to_string(),
                    action: ActionType::Release,
                    parameters: HashMap::new(),
                }),
                on_false: Box::new(TreeNode::Action {
                    node_id: "A2".to_string(),
                    action: ActionType::Hold,
                    parameters: HashMap::new(),
                }),
            }),
            strategic_collateral_tree: None,
            end_of_tick_collateral_tree: None,
            parameters: HashMap::new(),
        };

        let result = traverse_tree(&tree, &context).unwrap();

        // balance (500000) > amount (100000), so should reach Release action
        assert!(result.is_action());
        if let TreeNode::Action { action, .. } = result {
            assert!(matches!(action, ActionType::Release));
        } else {
            panic!("Expected action node");
        }
    }

    #[test]
    fn test_traverse_nested_tree() {
        let (context, _params) = create_test_context();

        // Nested tree:
        // if ticks_to_deadline <= 5:
        //   Release
        // else:
        //   if balance >= amount:
        //     Release
        //   else:
        //     Hold

        let tree = DecisionTreeDef {
            version: "1.0".to_string(),
            policy_id: "nested_test".to_string(),
            description: None,
            bank_tree: None,
            payment_tree: Some(TreeNode::Condition {
                node_id: "N1".to_string(),
                description: "Check urgency".to_string(),
                condition: Expression::LessOrEqual {
                    left: Value::Field {
                        field: "ticks_to_deadline".to_string(),
                    },
                    right: Value::Literal { value: json!(5) },
                },
                on_true: Box::new(TreeNode::Action {
                    node_id: "A1".to_string(),
                    action: ActionType::Release,
                    parameters: HashMap::new(),
                }),
                on_false: Box::new(TreeNode::Condition {
                    node_id: "N2".to_string(),
                    description: "Check liquidity".to_string(),
                    condition: Expression::GreaterOrEqual {
                        left: Value::Field {
                            field: "balance".to_string(),
                        },
                        right: Value::Field {
                            field: "amount".to_string(),
                        },
                    },
                    on_true: Box::new(TreeNode::Action {
                        node_id: "A2".to_string(),
                        action: ActionType::Release,
                        parameters: HashMap::new(),
                    }),
                    on_false: Box::new(TreeNode::Action {
                        node_id: "A3".to_string(),
                        action: ActionType::Hold,
                        parameters: HashMap::new(),
                    }),
                }),
            }),
            strategic_collateral_tree: None,
            end_of_tick_collateral_tree: None,
            parameters: HashMap::new(),
        };

        let result = traverse_tree(&tree, &context).unwrap();

        // ticks_to_deadline = 40 (not <= 5), balance (500000) >= amount (100000)
        // Should reach A2 (Release)
        assert!(result.is_action());
        if let TreeNode::Action {
            node_id, action, ..
        } = result
        {
            assert_eq!(node_id, "A2");
            assert!(matches!(action, ActionType::Release));
        } else {
            panic!("Expected action node");
        }
    }

    #[test]
    fn test_traverse_reaches_correct_action() {
        let (context, _params) = create_test_context();

        // Test that when condition is false, we take the correct branch
        // if balance < amount then ReleaseWithCredit else Hold

        let tree = DecisionTreeDef {
            version: "1.0".to_string(),
            policy_id: "branch_test".to_string(),
            description: None,
            bank_tree: None,
            payment_tree: Some(TreeNode::Condition {
                node_id: "N1".to_string(),
                description: "Check if insufficient liquidity".to_string(),
                condition: Expression::LessThan {
                    left: Value::Field {
                        field: "balance".to_string(),
                    },
                    right: Value::Field {
                        field: "amount".to_string(),
                    },
                },
                on_true: Box::new(TreeNode::Action {
                    node_id: "A1".to_string(),
                    action: ActionType::ReleaseWithCredit,
                    parameters: HashMap::new(),
                }),
                on_false: Box::new(TreeNode::Action {
                    node_id: "A2".to_string(),
                    action: ActionType::Hold,
                    parameters: HashMap::new(),
                }),
            }),
            strategic_collateral_tree: None,
            end_of_tick_collateral_tree: None,
            parameters: HashMap::new(),
        };

        let result = traverse_tree(&tree, &context).unwrap();

        // balance (500000) NOT < amount (100000), so should reach Hold action
        assert!(result.is_action());
        if let TreeNode::Action { action, .. } = result {
            assert!(matches!(action, ActionType::Hold));
        } else {
            panic!("Expected action node");
        }
    }

    #[test]
    fn test_traverse_with_complex_conditions() {
        let (context, _params) = create_test_context();

        // Test with AND/OR expressions
        // if (balance > 0 AND amount < 1000000) OR (credit_used == 0) then Release else Drop

        let tree = DecisionTreeDef {
            version: "1.0".to_string(),
            policy_id: "complex_test".to_string(),
            description: None,
            bank_tree: None,
            payment_tree: Some(TreeNode::Condition {
                node_id: "N1".to_string(),
                description: "Complex liquidity check".to_string(),
                condition: Expression::Or {
                    conditions: vec![
                        Expression::And {
                            conditions: vec![
                                Expression::GreaterThan {
                                    left: Value::Field {
                                        field: "balance".to_string(),
                                    },
                                    right: Value::Literal { value: json!(0) },
                                },
                                Expression::LessThan {
                                    left: Value::Field {
                                        field: "amount".to_string(),
                                    },
                                    right: Value::Literal {
                                        value: json!(1_000_000),
                                    },
                                },
                            ],
                        },
                        Expression::Equal {
                            left: Value::Field {
                                field: "credit_used".to_string(),
                            },
                            right: Value::Literal { value: json!(0) },
                        },
                    ],
                },
                on_true: Box::new(TreeNode::Action {
                    node_id: "A1".to_string(),
                    action: ActionType::Release,
                    parameters: HashMap::new(),
                }),
                on_false: Box::new(TreeNode::Action {
                    node_id: "A2".to_string(),
                    action: ActionType::Drop,
                    parameters: HashMap::new(),
                }),
            }),
            strategic_collateral_tree: None,
            end_of_tick_collateral_tree: None,
            parameters: HashMap::new(),
        };

        let result = traverse_tree(&tree, &context).unwrap();

        // Both parts of OR are true (balance=500000>0 AND amount=100000<1000000, credit_used=0)
        // Should reach Release action
        assert!(result.is_action());
        if let TreeNode::Action { action, .. } = result {
            assert!(matches!(action, ActionType::Release));
        } else {
            panic!("Expected action node");
        }
    }

    #[test]
    fn test_traverse_with_parameters() {
        let (context, _) = create_test_context();

        // Test with named parameters
        let mut params = HashMap::new();
        params.insert("urgency_threshold".to_string(), 10.0);

        let tree = DecisionTreeDef {
            version: "1.0".to_string(),
            policy_id: "param_test".to_string(),
            description: None,
            bank_tree: None,
            payment_tree: Some(TreeNode::Condition {
                node_id: "N1".to_string(),
                description: "Check if urgent".to_string(),
                condition: Expression::LessOrEqual {
                    left: Value::Field {
                        field: "ticks_to_deadline".to_string(),
                    },
                    right: Value::Param {
                        param: "urgency_threshold".to_string(),
                    },
                },
                on_true: Box::new(TreeNode::Action {
                    node_id: "A1".to_string(),
                    action: ActionType::Release,
                    parameters: HashMap::new(),
                }),
                on_false: Box::new(TreeNode::Action {
                    node_id: "A2".to_string(),
                    action: ActionType::Hold,
                    parameters: HashMap::new(),
                }),
            }),
            strategic_collateral_tree: None,
            end_of_tick_collateral_tree: None,
            parameters: params,
        };

        let result = traverse_tree(&tree, &context).unwrap();

        // ticks_to_deadline = 40, urgency_threshold = 10, so 40 > 10
        // Should reach Hold action
        assert!(result.is_action());
        if let TreeNode::Action { action, .. } = result {
            assert!(matches!(action, ActionType::Hold));
        } else {
            panic!("Expected action node");
        }
    }

    // ========================================================================
    // Phase 6.8: Action Building Tests
    // ========================================================================

    #[test]
    fn test_build_release_decision() {
        let (context, params) = create_test_context();

        let action_node = TreeNode::Action {
            node_id: "A1".to_string(),
            action: ActionType::Release,
            parameters: HashMap::new(),
        };

        let decision =
            build_decision(&action_node, "tx_001".to_string(), &context, &params).unwrap();

        assert!(matches!(
            decision,
            ReleaseDecision::SubmitFull { tx_id, .. } if tx_id == "tx_001"
        ));
    }

    #[test]
    fn test_build_hold_decision_with_reason() {
        let (context, params) = create_test_context();

        let action_node = TreeNode::Action {
            node_id: "A1".to_string(),
            action: ActionType::Hold,
            parameters: HashMap::new(),
        };

        let decision =
            build_decision(&action_node, "tx_001".to_string(), &context, &params).unwrap();

        match decision {
            ReleaseDecision::Hold { tx_id, reason } => {
                assert_eq!(tx_id, "tx_001");
                assert!(matches!(reason, HoldReason::Custom(_)));
            }
            _ => panic!("Expected Hold decision"),
        }
    }

    #[test]
    fn test_build_submit_partial_with_num_splits() {
        let (context, params) = create_test_context();

        let mut action_params = HashMap::new();
        action_params.insert(
            "num_splits".to_string(),
            ValueOrCompute::Direct { value: json!(3) },
        );

        let action_node = TreeNode::Action {
            node_id: "A1".to_string(),
            action: ActionType::PaceAndRelease,
            parameters: action_params,
        };

        let decision =
            build_decision(&action_node, "tx_001".to_string(), &context, &params).unwrap();

        match decision {
            ReleaseDecision::SubmitPartial { tx_id, num_splits } => {
                assert_eq!(tx_id, "tx_001");
                assert_eq!(num_splits, 3);
            }
            _ => panic!("Expected SubmitPartial decision"),
        }
    }

    #[test]
    fn test_build_drop_decision() {
        let (context, params) = create_test_context();

        let action_node = TreeNode::Action {
            node_id: "A1".to_string(),
            action: ActionType::Drop,
            parameters: HashMap::new(),
        };

        let decision =
            build_decision(&action_node, "tx_001".to_string(), &context, &params).unwrap();

        assert!(matches!(
            decision,
            ReleaseDecision::Drop { tx_id } if tx_id == "tx_001"
        ));
    }

    #[test]
    fn test_action_parameters_evaluated_from_computation() {
        let (context, params) = create_test_context();

        // num_splits computed from expression: min(5, 10) = 5
        let mut action_params = HashMap::new();
        action_params.insert(
            "num_splits".to_string(),
            ValueOrCompute::Compute {
                compute: Computation::Min {
                    values: vec![
                        Value::Literal { value: json!(5) },
                        Value::Literal { value: json!(10) },
                    ],
                },
            },
        );

        let action_node = TreeNode::Action {
            node_id: "A1".to_string(),
            action: ActionType::PaceAndRelease,
            parameters: action_params,
        };

        let decision =
            build_decision(&action_node, "tx_001".to_string(), &context, &params).unwrap();

        match decision {
            ReleaseDecision::SubmitPartial { tx_id, num_splits } => {
                assert_eq!(tx_id, "tx_001");
                assert_eq!(num_splits, 5);
            }
            _ => panic!("Expected SubmitPartial decision"),
        }
    }

    #[test]
    fn test_action_parameters_from_field_reference() {
        let (context, params) = create_test_context();

        // num_splits from field reference (using priority field = 5, the default)
        let mut action_params = HashMap::new();
        action_params.insert(
            "num_splits".to_string(),
            ValueOrCompute::Field {
                field: "priority".to_string(),
            },
        );

        let action_node = TreeNode::Action {
            node_id: "A1".to_string(),
            action: ActionType::PaceAndRelease,
            parameters: action_params,
        };

        let decision =
            build_decision(&action_node, "tx_001".to_string(), &context, &params).unwrap();

        match decision {
            ReleaseDecision::SubmitPartial { tx_id, num_splits } => {
                assert_eq!(tx_id, "tx_001");
                assert_eq!(num_splits, 5); // priority = 5 (default)
            }
            _ => panic!("Expected SubmitPartial decision"),
        }
    }

    #[test]
    fn test_build_decision_missing_parameter() {
        let (context, params) = create_test_context();

        // PaceAndRelease without num_splits parameter should error
        let action_node = TreeNode::Action {
            node_id: "A1".to_string(),
            action: ActionType::PaceAndRelease,
            parameters: HashMap::new(),
        };

        let result = build_decision(&action_node, "tx_001".to_string(), &context, &params);
        assert!(result.is_err());

        match result {
            Err(EvalError::MissingActionParameter(param)) => {
                assert_eq!(param, "num_splits");
            }
            _ => panic!("Expected MissingActionParameter error"),
        }
    }

    #[test]
    fn test_build_decision_invalid_num_splits() {
        let (context, params) = create_test_context();

        // num_splits < 2 should error
        let mut action_params = HashMap::new();
        action_params.insert(
            "num_splits".to_string(),
            ValueOrCompute::Direct { value: json!(1) },
        );

        let action_node = TreeNode::Action {
            node_id: "A1".to_string(),
            action: ActionType::PaceAndRelease,
            parameters: action_params,
        };

        let result = build_decision(&action_node, "tx_001".to_string(), &context, &params);
        assert!(result.is_err());

        match result {
            Err(EvalError::InvalidActionParameter(_)) => {}
            _ => panic!("Expected InvalidActionParameter error"),
        }
    }

    // ============================================================================
    // PHASE 8.2: Collateral Decision Building (TDD Cycle 3)
    // ============================================================================

    #[test]
    fn test_build_collateral_decision_post() {
        use crate::policy::CollateralDecision;
        let (context, params) = create_test_context();

        // PostCollateral with amount and reason
        let mut action_params = HashMap::new();
        action_params.insert(
            "amount".to_string(),
            ValueOrCompute::Direct {
                value: json!(100000),
            },
        );
        action_params.insert(
            "reason".to_string(),
            ValueOrCompute::Direct {
                value: json!("UrgentLiquidityNeed"),
            },
        );

        let action_node = TreeNode::Action {
            node_id: "C1".to_string(),
            action: ActionType::PostCollateral,
            parameters: action_params,
        };

        let result = build_collateral_decision(&action_node, &context, &params);
        assert!(
            result.is_ok(),
            "Failed to build PostCollateral decision: {:?}",
            result.err()
        );

        match result.unwrap() {
            CollateralDecision::Post { amount, reason, .. } => {
                assert_eq!(amount, 100000);
                assert_eq!(format!("{:?}", reason), "UrgentLiquidityNeed");
            }
            _ => panic!("Expected Post decision"),
        }
    }

    #[test]
    fn test_build_collateral_decision_withdraw() {
        use crate::policy::CollateralDecision;

        // Create a test context with posted collateral
        let tx = Transaction::new("BANK_A".to_string(), "BANK_B".to_string(), 100_000, 0, 50);
        let mut agent = Agent::new("BANK_A".to_string(), 500_000, 200_000);
        agent.set_posted_collateral(150_000); // Set some posted collateral
        let state = SimulationState::new(vec![agent.clone()]);
        let cost_rates = CostRates::default();
        let context = EvalContext::build(&tx, &agent, &state, 10, &cost_rates, 100, 0.8);
        let params = HashMap::new();

        // WithdrawCollateral with amount from field
        let mut action_params = HashMap::new();
        action_params.insert(
            "amount".to_string(),
            ValueOrCompute::Field {
                field: "posted_collateral".to_string(),
            },
        );
        action_params.insert(
            "reason".to_string(),
            ValueOrCompute::Direct {
                value: json!("LiquidityRestored"),
            },
        );

        let action_node = TreeNode::Action {
            node_id: "C2".to_string(),
            action: ActionType::WithdrawCollateral,
            parameters: action_params,
        };

        let result = build_collateral_decision(&action_node, &context, &params);
        assert!(
            result.is_ok(),
            "Failed to build WithdrawCollateral decision: {:?}",
            result.err()
        );

        match result.unwrap() {
            CollateralDecision::Withdraw { amount, .. } => {
                // Should match the posted_collateral amount
                assert_eq!(amount, 150_000);
            }
            _ => panic!("Expected Withdraw decision"),
        }
    }

    #[test]
    fn test_build_collateral_decision_hold() {
        use crate::policy::CollateralDecision;
        let (context, params) = create_test_context();

        // HoldCollateral (no parameters needed)
        let action_node = TreeNode::Action {
            node_id: "C3".to_string(),
            action: ActionType::HoldCollateral,
            parameters: HashMap::new(),
        };

        let result = build_collateral_decision(&action_node, &context, &params);
        assert!(
            result.is_ok(),
            "Failed to build HoldCollateral decision: {:?}",
            result.err()
        );

        assert!(matches!(result.unwrap(), CollateralDecision::Hold));
    }

    #[test]
    fn test_build_collateral_decision_computed_amount() {
        use crate::policy::CollateralDecision;

        // Create a test context with a liquidity gap
        let tx = Transaction::new("BANK_A".to_string(), "BANK_B".to_string(), 100_000, 0, 50);
        let mut agent = Agent::new("BANK_A".to_string(), 50_000, 0); // Low balance, no credit

        // Create a state with the agent
        let mut state = SimulationState::new(vec![
            agent.clone(),
            Agent::new("BANK_C".to_string(), 1_000_000, 0),
        ]);

        // Add a transaction to the queue to create a liquidity gap
        let queued_tx = Transaction::new("BANK_A".to_string(), "BANK_C".to_string(), 200_000, 0, 50);
        let queued_tx_id = queued_tx.id().to_string();
        state.add_transaction(queued_tx);
        agent.queue_outgoing(queued_tx_id);

        let cost_rates = CostRates::default();
        let context = EvalContext::build(&tx, &agent, &state, 10, &cost_rates, 100, 0.8);
        let params = HashMap::new();

        // PostCollateral with computed amount (liquidity gap)
        let mut action_params = HashMap::new();
        action_params.insert(
            "amount".to_string(),
            ValueOrCompute::Compute {
                compute: Computation::Max {
                    values: vec![
                        Value::Field {
                            field: "queue1_liquidity_gap".to_string(),
                        },
                        Value::Literal { value: json!(0) },
                    ],
                },
            },
        );
        action_params.insert(
            "reason".to_string(),
            ValueOrCompute::Direct {
                value: json!("UrgentLiquidityNeed"),
            },
        );

        let action_node = TreeNode::Action {
            node_id: "C4".to_string(),
            action: ActionType::PostCollateral,
            parameters: action_params,
        };

        let result = build_collateral_decision(&action_node, &context, &params);
        assert!(
            result.is_ok(),
            "Failed to build PostCollateral with computed amount: {:?}",
            result.err()
        );

        // Should compute max(queue1_liquidity_gap, 0)
        // Agent has 50k available, 200k queued, so gap = 150k
        match result.unwrap() {
            CollateralDecision::Post { amount, .. } => {
                assert_eq!(amount, 150_000, "Amount should equal the liquidity gap");
            }
            _ => panic!("Expected Post decision"),
        }
    }

    #[test]
    fn test_build_collateral_decision_missing_amount() {
        let (context, params) = create_test_context();

        // PostCollateral without amount parameter should error
        let mut action_params = HashMap::new();
        action_params.insert(
            "reason".to_string(),
            ValueOrCompute::Direct {
                value: json!("UrgentLiquidityNeed"),
            },
        );

        let action_node = TreeNode::Action {
            node_id: "C5".to_string(),
            action: ActionType::PostCollateral,
            parameters: action_params,
        };

        let result = build_collateral_decision(&action_node, &context, &params);
        assert!(result.is_err(), "Should error when amount is missing");

        match result {
            Err(EvalError::MissingActionParameter(param)) => {
                assert_eq!(param, "amount");
            }
            _ => panic!("Expected MissingActionParameter error"),
        }
    }

    // ============================================================================
    // PHASE 4: Reprioritize Action Tests (TDD)
    // ============================================================================

    #[test]
    fn test_build_reprioritize_decision_with_literal_priority() {
        let (context, params) = create_test_context();

        // Reprioritize with literal new_priority = 10
        let mut action_params = HashMap::new();
        action_params.insert(
            "new_priority".to_string(),
            ValueOrCompute::Direct { value: json!(10) },
        );

        let action_node = TreeNode::Action {
            node_id: "R1".to_string(),
            action: ActionType::Reprioritize,
            parameters: action_params,
        };

        let decision =
            build_decision(&action_node, "tx_001".to_string(), &context, &params).unwrap();

        match decision {
            ReleaseDecision::Reprioritize { tx_id, new_priority } => {
                assert_eq!(tx_id, "tx_001");
                assert_eq!(new_priority, 10);
            }
            _ => panic!("Expected Reprioritize decision"),
        }
    }

    #[test]
    fn test_build_reprioritize_decision_with_computed_priority() {
        let (context, params) = create_test_context();

        // Reprioritize with computed priority: min(is_overdue * 10, 10)
        let mut action_params = HashMap::new();
        action_params.insert(
            "new_priority".to_string(),
            ValueOrCompute::Compute {
                compute: Computation::Min {
                    values: vec![
                        Value::Compute {
                            compute: Box::new(Computation::Multiply {
                                left: Value::Field {
                                    field: "is_overdue".to_string(),
                                },
                                right: Value::Literal { value: json!(10) },
                            }),
                        },
                        Value::Literal { value: json!(10) },
                    ],
                },
            },
        );

        let action_node = TreeNode::Action {
            node_id: "R2".to_string(),
            action: ActionType::Reprioritize,
            parameters: action_params,
        };

        let decision =
            build_decision(&action_node, "tx_001".to_string(), &context, &params).unwrap();

        match decision {
            ReleaseDecision::Reprioritize { tx_id, new_priority } => {
                assert_eq!(tx_id, "tx_001");
                // is_overdue is 0 for this transaction, so 0 * 10 = 0
                assert_eq!(new_priority, 0);
            }
            _ => panic!("Expected Reprioritize decision"),
        }
    }

    #[test]
    fn test_build_reprioritize_decision_caps_priority_at_255() {
        let (context, params) = create_test_context();

        // Reprioritize with priority > 255 should be capped at 255
        let mut action_params = HashMap::new();
        action_params.insert(
            "new_priority".to_string(),
            ValueOrCompute::Direct { value: json!(300) },
        );

        let action_node = TreeNode::Action {
            node_id: "R3".to_string(),
            action: ActionType::Reprioritize,
            parameters: action_params,
        };

        let decision =
            build_decision(&action_node, "tx_001".to_string(), &context, &params).unwrap();

        match decision {
            ReleaseDecision::Reprioritize { tx_id, new_priority } => {
                assert_eq!(tx_id, "tx_001");
                // u8 max is 255, should be capped
                assert_eq!(new_priority, 255);
            }
            _ => panic!("Expected Reprioritize decision"),
        }
    }

    #[test]
    fn test_build_reprioritize_decision_from_field() {
        let (context, params) = create_test_context();

        // Reprioritize with priority from field (overdue_duration)
        let mut action_params = HashMap::new();
        action_params.insert(
            "new_priority".to_string(),
            ValueOrCompute::Field {
                field: "priority".to_string(),
            },
        );

        let action_node = TreeNode::Action {
            node_id: "R4".to_string(),
            action: ActionType::Reprioritize,
            parameters: action_params,
        };

        let decision =
            build_decision(&action_node, "tx_001".to_string(), &context, &params).unwrap();

        match decision {
            ReleaseDecision::Reprioritize { tx_id, new_priority } => {
                assert_eq!(tx_id, "tx_001");
                // priority field = 5 (default)
                assert_eq!(new_priority, 5);
            }
            _ => panic!("Expected Reprioritize decision"),
        }
    }

    #[test]
    fn test_build_reprioritize_decision_missing_parameter() {
        let (context, params) = create_test_context();

        // Reprioritize without new_priority parameter should error
        let action_node = TreeNode::Action {
            node_id: "R5".to_string(),
            action: ActionType::Reprioritize,
            parameters: HashMap::new(),
        };

        let result = build_decision(&action_node, "tx_001".to_string(), &context, &params);
        assert!(result.is_err(), "Should error when new_priority is missing");

        match result {
            Err(EvalError::MissingActionParameter(param)) => {
                assert_eq!(param, "new_priority");
            }
            _ => panic!("Expected MissingActionParameter error"),
        }
    }
}
