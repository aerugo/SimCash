// Phase 6: Decision Tree Validation
//
// Pre-execution safety checks to ensure decision trees are well-formed:
// - Node ID uniqueness
// - Tree depth limits
// - Field reference validity
// - Parameter reference validity
// - Division-by-zero safety
// - Action reachability

use crate::policy::tree::context::EvalContext;
use crate::policy::tree::types::{
    Computation, DecisionTreeDef, Expression, TreeNode, Value, ValueOrCompute,
};
use std::collections::{HashMap, HashSet};
use thiserror::Error;

/// Validation errors
#[derive(Debug, Error, PartialEq)]
pub enum ValidationError {
    #[error("Duplicate node ID: {0}")]
    DuplicateNodeId(String),

    #[error("Tree depth {actual} exceeds maximum {max}")]
    ExcessiveDepth { actual: usize, max: usize },

    #[error("Field reference '{0}' not found in context")]
    InvalidFieldReference(String),

    #[error("Parameter reference '{0}' not found in tree parameters")]
    InvalidParameterReference(String),

    #[error("Potential division by zero in computation at node {0}")]
    DivisionByZeroRisk(String),

    #[error("Unreachable action node: {0}")]
    UnreachableAction(String),
}

/// Validation result
pub type ValidationResult = Result<(), Vec<ValidationError>>;

/// Maximum allowed tree depth
const MAX_TREE_DEPTH: usize = 100;

/// Validate a decision tree before execution
///
/// Runs all validation checks and returns all errors found.
///
/// # Arguments
///
/// * `tree` - Decision tree to validate
/// * `sample_context` - Sample evaluation context for field validation
///
/// # Returns
///
/// Ok(()) if all checks pass, Err(errors) otherwise
///
/// # Example
///
/// ```rust
/// use payment_simulator_core_rs::policy::tree::{DecisionTreeDef, EvalContext, validate_tree};
/// use payment_simulator_core_rs::{Agent, Transaction, SimulationState};
/// use payment_simulator_core_rs::orchestrator::CostRates;
///
/// # fn main() -> Result<(), Box<dyn std::error::Error>> {
/// let agent = Agent::new("BANK_A".to_string(), 1_000_000);
/// let tx = Transaction::new("BANK_A".to_string(), "BANK_B".to_string(), 100_000, 0, 100);
/// let state = SimulationState::new(vec![agent.clone()]);
/// let cost_rates = CostRates::default();
/// let sample_context = EvalContext::build(&tx, &agent, &state, 0, &cost_rates, 100, 0.8);
///
/// let json = r#"{
///   "version": "1.0",
///   "policy_id": "valid_policy",
///   "payment_tree": {
///     "type": "action",
///     "node_id": "A1",
///     "action": "Release"
///   },
///   "strategic_collateral_tree": null,
///   "end_of_tick_collateral_tree": null,
///   "parameters": {}
/// }"#;
/// let tree: DecisionTreeDef = serde_json::from_str(json)?;
///
/// // validate_tree returns Result<(), Vec<ValidationError>>
/// match validate_tree(&tree, &sample_context) {
///     Ok(()) => println!("Tree is valid"),
///     Err(errors) => panic!("Validation failed: {} errors", errors.len()),
/// }
/// # Ok(())
/// # }
/// ```
pub fn validate_tree(tree: &DecisionTreeDef, sample_context: &EvalContext) -> ValidationResult {
    let mut errors = Vec::new();

    // Phase 6.9: Node ID uniqueness
    if let Err(e) = validate_node_id_uniqueness(tree) {
        errors.extend(e);
    }

    // Phase 6.10: Tree depth limits
    if let Err(e) = validate_tree_depth(tree) {
        errors.extend(e);
    }

    // Phase 6.11: Field references
    if let Err(e) = validate_field_references(tree, sample_context) {
        errors.extend(e);
    }

    // Phase 6.12: Parameter references
    if let Err(e) = validate_parameter_references(tree) {
        errors.extend(e);
    }

    // Phase 6.13: Division safety
    if let Err(e) = validate_division_safety(tree) {
        errors.extend(e);
    }

    // Phase 6.14: Action reachability (optional warning, not critical)
    // Note: This is a best-effort static analysis
    if let Err(e) = validate_action_reachability(tree) {
        errors.extend(e);
    }

    if errors.is_empty() {
        Ok(())
    } else {
        Err(errors)
    }
}

// ============================================================================
// Phase 6.9: Node ID Uniqueness
// ============================================================================

/// Validate that all node IDs are unique across all three trees
fn validate_node_id_uniqueness(tree: &DecisionTreeDef) -> ValidationResult {
    let mut seen = HashSet::new();
    let mut errors = Vec::new();

    // Validate payment tree
    if let Some(ref payment_tree) = tree.payment_tree {
        collect_node_ids(payment_tree, &mut seen, &mut errors);
    }

    // Validate strategic collateral tree
    if let Some(ref strategic_tree) = tree.strategic_collateral_tree {
        collect_node_ids(strategic_tree, &mut seen, &mut errors);
    }

    // Validate end-of-tick collateral tree
    if let Some(ref eot_tree) = tree.end_of_tick_collateral_tree {
        collect_node_ids(eot_tree, &mut seen, &mut errors);
    }

    if errors.is_empty() {
        Ok(())
    } else {
        Err(errors)
    }
}

fn collect_node_ids(
    node: &TreeNode,
    seen: &mut HashSet<String>,
    errors: &mut Vec<ValidationError>,
) {
    let node_id = node.node_id();

    if !seen.insert(node_id.to_string()) {
        errors.push(ValidationError::DuplicateNodeId(node_id.to_string()));
    }

    // Recurse into child nodes
    if let TreeNode::Condition {
        on_true, on_false, ..
    } = node
    {
        collect_node_ids(on_true, seen, errors);
        collect_node_ids(on_false, seen, errors);
    }
}

// ============================================================================
// Phase 6.10: Tree Depth Limits
// ============================================================================

/// Validate that tree depth does not exceed maximum for all three trees
fn validate_tree_depth(tree: &DecisionTreeDef) -> ValidationResult {
    let mut max_depth = 0;

    // Check payment tree
    if let Some(ref payment_tree) = tree.payment_tree {
        max_depth = max_depth.max(compute_tree_depth(payment_tree, 0));
    }

    // Check strategic collateral tree
    if let Some(ref strategic_tree) = tree.strategic_collateral_tree {
        max_depth = max_depth.max(compute_tree_depth(strategic_tree, 0));
    }

    // Check end-of-tick collateral tree
    if let Some(ref eot_tree) = tree.end_of_tick_collateral_tree {
        max_depth = max_depth.max(compute_tree_depth(eot_tree, 0));
    }

    if max_depth > MAX_TREE_DEPTH {
        Err(vec![ValidationError::ExcessiveDepth {
            actual: max_depth,
            max: MAX_TREE_DEPTH,
        }])
    } else {
        Ok(())
    }
}

fn compute_tree_depth(node: &TreeNode, current_depth: usize) -> usize {
    match node {
        TreeNode::Action { .. } => current_depth,
        TreeNode::Condition {
            on_true, on_false, ..
        } => {
            let true_depth = compute_tree_depth(on_true, current_depth + 1);
            let false_depth = compute_tree_depth(on_false, current_depth + 1);
            true_depth.max(false_depth)
        }
    }
}

// ============================================================================
// Phase 6.11: Field References
// ============================================================================

/// Validate that all field references are appropriate for each tree context
///
/// Different tree types have access to different fields:
/// - payment_tree: transaction fields + bank fields + state registers (bank_state_*)
/// - bank_tree: bank fields + state registers (bank_state_*)
/// - collateral trees: bank fields only (no transactions, no state registers)
fn validate_field_references(
    tree: &DecisionTreeDef,
    sample_context: &EvalContext,
) -> ValidationResult {
    let mut errors = Vec::new();

    // Validate payment tree (has transaction context)
    if let Some(ref payment_tree) = tree.payment_tree {
        let mut fields = HashSet::new();
        collect_field_references(payment_tree, &mut fields);
        for field in fields {
            // Payment tree can access: transaction fields, bank fields, and state registers
            // Don't validate against sample_context because it might be a dummy context
            // Just check that fields are either transaction-only, bank-level, or state registers
            if !field.starts_with("bank_state_")
                && !is_transaction_only_field(&field)
                && !is_bank_level_field(&field) {
                errors.push(ValidationError::InvalidFieldReference(field));
            }
        }
    }

    // Validate bank tree (has bank-level context)
    if let Some(ref bank_tree) = tree.bank_tree {
        let mut fields = HashSet::new();
        collect_field_references(bank_tree, &mut fields);
        for field in fields {
            // Bank tree can access: bank fields and state registers
            // But NOT transaction-specific fields
            if is_transaction_only_field(&field) {
                errors.push(ValidationError::InvalidFieldReference(field));
            } else if !field.starts_with("bank_state_") && !is_bank_level_field(&field) {
                errors.push(ValidationError::InvalidFieldReference(field));
            }
        }
    }

    // Validate strategic collateral tree (has bank-level context WITH state registers)
    // Uses EvalContext::build() which includes state registers and bank-level fields
    if let Some(ref strategic_tree) = tree.strategic_collateral_tree {
        let mut fields = HashSet::new();
        collect_field_references(strategic_tree, &mut fields);
        for field in fields {
            // Collateral trees can access:
            // - bank-level fields
            // - state registers (bank_state_*)
            // But NOT transaction-specific fields
            if is_transaction_only_field(&field) {
                errors.push(ValidationError::InvalidFieldReference(field));
            } else if !field.starts_with("bank_state_") && !is_bank_level_field(&field) {
                // Field is not bank-level or state register - it's invalid
                errors.push(ValidationError::InvalidFieldReference(field));
            }
        }
    }

    // Validate end-of-tick collateral tree (has bank-level context WITH state registers)
    // Uses EvalContext::build() which includes state registers and bank-level fields
    if let Some(ref eot_tree) = tree.end_of_tick_collateral_tree {
        let mut fields = HashSet::new();
        collect_field_references(eot_tree, &mut fields);
        for field in fields {
            // Collateral trees can access:
            // - bank-level fields
            // - state registers (bank_state_*)
            // But NOT transaction-specific fields
            if is_transaction_only_field(&field) {
                errors.push(ValidationError::InvalidFieldReference(field));
            } else if !field.starts_with("bank_state_") && !is_bank_level_field(&field) {
                // Field is not bank-level or state register - it's invalid
                errors.push(ValidationError::InvalidFieldReference(field));
            }
        }
    }

    if errors.is_empty() {
        Ok(())
    } else {
        Err(errors)
    }
}

/// Check if a field is transaction-specific (not available in bank/collateral contexts)
fn is_transaction_only_field(field: &str) -> bool {
    matches!(
        field,
        "amount"
            | "remaining_amount"
            | "settled_amount"
            | "arrival_tick"
            | "deadline_tick"
            | "priority"
            | "is_split"
            | "is_past_deadline"
            | "is_overdue"
            | "is_in_queue2"
            | "overdue_duration"
            | "ticks_to_deadline"
            | "queue_age"
            | "time_in_queue"
            | "cost_delay_so_far"
            | "cost_if_settled_now"
            | "cost_if_held_one_tick"
            | "cost_urgency"
            // Phase 9.5.1: Transaction-specific cost fields
            // These use the transaction's remaining_amount, so only available in payment_tree
            | "cost_delay_this_tx_one_tick"
            | "cost_overdraft_this_amount_one_tick"
    )
}

/// Check if a field is available in bank-level contexts (bank_tree and collateral trees)
/// These fields come from EvalContext::bank_level() - see context.rs:574
fn is_bank_level_field(field: &str) -> bool {
    matches!(
        field,
        // Agent fields
        "balance"
            | "credit_limit"
            | "available_liquidity"
            | "credit_used"
            | "effective_liquidity"
            | "credit_headroom"
            | "is_using_credit"
            | "liquidity_buffer"
            | "outgoing_queue_size"
            | "incoming_expected_count"
            | "liquidity_pressure"
            | "is_overdraft_capped"
            // Queue 1 metrics
            | "queue1_total_value"
            | "queue1_liquidity_gap"
            | "headroom"
            // System fields
            | "current_tick"
            | "rtgs_queue_size"
            | "rtgs_queue_value"
            | "total_agents"
            // Collateral fields
            | "posted_collateral"
            | "max_collateral_capacity"
            | "remaining_collateral_capacity"
            | "collateral_utilization"
            | "required_collateral_for_usage"
            | "excess_collateral"
            | "overdraft_utilization"
            | "overdraft_headroom"
            | "collateral_haircut"
            | "unsecured_cap"
            | "allowed_overdraft_limit"
            // Queue 2 metrics
            | "queue2_size"
            | "queue2_count_for_agent"
            | "queue2_nearest_deadline"
            | "ticks_to_nearest_queue2_deadline"
            // Cost fields
            | "cost_overdraft_bps_per_tick"
            | "cost_delay_per_tick_per_cent"
            | "cost_collateral_bps_per_tick"
            | "cost_split_friction"
            | "cost_deadline_penalty"
            | "cost_eod_penalty"
            // Time/day fields
            | "system_ticks_per_day"
            | "system_current_day"
            | "system_tick_in_day"
            | "ticks_remaining_in_day"
            | "day_progress_fraction"
            | "is_eod_rush"
            // Public signal fields
            | "system_queue2_pressure_index"
            | "my_throughput_fraction_today"
            | "expected_throughput_fraction_by_now"
            | "throughput_gap"
    )
}

fn collect_field_references(node: &TreeNode, fields: &mut HashSet<String>) {
    match node {
        TreeNode::Condition {
            condition,
            on_true,
            on_false,
            ..
        } => {
            collect_fields_from_expression(condition, fields);
            collect_field_references(on_true, fields);
            collect_field_references(on_false, fields);
        }
        TreeNode::Action { parameters, .. } => {
            for value_or_compute in parameters.values() {
                collect_fields_from_value_or_compute(value_or_compute, fields);
            }
        }
    }
}

fn collect_fields_from_expression(expr: &Expression, fields: &mut HashSet<String>) {
    match expr {
        Expression::Equal { left, right }
        | Expression::NotEqual { left, right }
        | Expression::LessThan { left, right }
        | Expression::LessOrEqual { left, right }
        | Expression::GreaterThan { left, right }
        | Expression::GreaterOrEqual { left, right } => {
            collect_fields_from_value(left, fields);
            collect_fields_from_value(right, fields);
        }
        Expression::And { conditions } | Expression::Or { conditions } => {
            for cond in conditions {
                collect_fields_from_expression(cond, fields);
            }
        }
        Expression::Not { condition } => {
            collect_fields_from_expression(condition, fields);
        }
    }
}

fn collect_fields_from_value(value: &Value, fields: &mut HashSet<String>) {
    match value {
        Value::Field { field } => {
            fields.insert(field.clone());
        }
        Value::Compute { compute } => {
            collect_fields_from_computation(compute, fields);
        }
        _ => {}
    }
}

fn collect_fields_from_computation(comp: &Computation, fields: &mut HashSet<String>) {
    match comp {
        Computation::Add { left, right }
        | Computation::Subtract { left, right }
        | Computation::Multiply { left, right }
        | Computation::Divide { left, right } => {
            collect_fields_from_value(left, fields);
            collect_fields_from_value(right, fields);
        }
        Computation::Max { values } | Computation::Min { values } => {
            for value in values {
                collect_fields_from_value(value, fields);
            }
        }
        // Phase 2.3: Math helper functions
        Computation::Ceil { value }
        | Computation::Floor { value }
        | Computation::Round { value }
        | Computation::Abs { value } => {
            collect_fields_from_value(value, fields);
        }
        Computation::Clamp { value, min, max } => {
            collect_fields_from_value(value, fields);
            collect_fields_from_value(min, fields);
            collect_fields_from_value(max, fields);
        }
        Computation::SafeDiv {
            numerator,
            denominator,
            default,
        } => {
            collect_fields_from_value(numerator, fields);
            collect_fields_from_value(denominator, fields);
            collect_fields_from_value(default, fields);
        }
    }
}

fn collect_fields_from_value_or_compute(voc: &ValueOrCompute, fields: &mut HashSet<String>) {
    match voc {
        ValueOrCompute::Field { field } => {
            fields.insert(field.clone());
        }
        ValueOrCompute::Compute { compute } => {
            collect_fields_from_computation(compute, fields);
        }
        _ => {}
    }
}

// ============================================================================
// Phase 6.12: Parameter References
// ============================================================================

/// Validate that all parameter references exist in tree parameters across all three trees
fn validate_parameter_references(tree: &DecisionTreeDef) -> ValidationResult {
    let mut errors = Vec::new();
    let mut referenced_params = HashSet::new();

    // Collect all parameter references from payment tree
    if let Some(ref payment_tree) = tree.payment_tree {
        collect_parameter_references(payment_tree, &mut referenced_params);
    }

    // Collect all parameter references from strategic collateral tree
    if let Some(ref strategic_tree) = tree.strategic_collateral_tree {
        collect_parameter_references(strategic_tree, &mut referenced_params);
    }

    // Collect all parameter references from end-of-tick collateral tree
    if let Some(ref eot_tree) = tree.end_of_tick_collateral_tree {
        collect_parameter_references(eot_tree, &mut referenced_params);
    }

    // Check each parameter against tree.parameters
    for param in referenced_params {
        if !tree.parameters.contains_key(&param) {
            errors.push(ValidationError::InvalidParameterReference(param));
        }
    }

    if errors.is_empty() {
        Ok(())
    } else {
        Err(errors)
    }
}

fn collect_parameter_references(node: &TreeNode, params: &mut HashSet<String>) {
    match node {
        TreeNode::Condition {
            condition,
            on_true,
            on_false,
            ..
        } => {
            collect_params_from_expression(condition, params);
            collect_parameter_references(on_true, params);
            collect_parameter_references(on_false, params);
        }
        TreeNode::Action { parameters, .. } => {
            for value_or_compute in parameters.values() {
                collect_params_from_value_or_compute(value_or_compute, params);
            }
        }
    }
}

fn collect_params_from_expression(expr: &Expression, params: &mut HashSet<String>) {
    match expr {
        Expression::Equal { left, right }
        | Expression::NotEqual { left, right }
        | Expression::LessThan { left, right }
        | Expression::LessOrEqual { left, right }
        | Expression::GreaterThan { left, right }
        | Expression::GreaterOrEqual { left, right } => {
            collect_params_from_value(left, params);
            collect_params_from_value(right, params);
        }
        Expression::And { conditions } | Expression::Or { conditions } => {
            for cond in conditions {
                collect_params_from_expression(cond, params);
            }
        }
        Expression::Not { condition } => {
            collect_params_from_expression(condition, params);
        }
    }
}

fn collect_params_from_value(value: &Value, params: &mut HashSet<String>) {
    match value {
        Value::Param { param } => {
            params.insert(param.clone());
        }
        Value::Compute { compute } => {
            collect_params_from_computation(compute, params);
        }
        _ => {}
    }
}

fn collect_params_from_computation(comp: &Computation, params: &mut HashSet<String>) {
    match comp {
        Computation::Add { left, right }
        | Computation::Subtract { left, right }
        | Computation::Multiply { left, right }
        | Computation::Divide { left, right } => {
            collect_params_from_value(left, params);
            collect_params_from_value(right, params);
        }
        Computation::Max { values } | Computation::Min { values } => {
            for value in values {
                collect_params_from_value(value, params);
            }
        }
        // Phase 2.3: Math helper functions
        Computation::Ceil { value }
        | Computation::Floor { value }
        | Computation::Round { value }
        | Computation::Abs { value } => {
            collect_params_from_value(value, params);
        }
        Computation::Clamp { value, min, max } => {
            collect_params_from_value(value, params);
            collect_params_from_value(min, params);
            collect_params_from_value(max, params);
        }
        Computation::SafeDiv {
            numerator,
            denominator,
            default,
        } => {
            collect_params_from_value(numerator, params);
            collect_params_from_value(denominator, params);
            collect_params_from_value(default, params);
        }
    }
}

fn collect_params_from_value_or_compute(voc: &ValueOrCompute, params: &mut HashSet<String>) {
    match voc {
        ValueOrCompute::Param { param } => {
            params.insert(param.clone());
        }
        ValueOrCompute::Compute { compute } => {
            collect_params_from_computation(compute, params);
        }
        _ => {}
    }
}

// ============================================================================
// Phase 6.13: Division Safety
// ============================================================================

/// Validate that no division operations have literal zero divisors across all three trees
///
/// Note: This is static analysis only. Runtime division by zero is still
/// caught by the interpreter's divide-by-zero check.
fn validate_division_safety(tree: &DecisionTreeDef) -> ValidationResult {
    let mut errors = Vec::new();

    // Check payment tree
    if let Some(ref payment_tree) = tree.payment_tree {
        check_division_safety_in_node(payment_tree, &mut errors);
    }

    // Check strategic collateral tree
    if let Some(ref strategic_tree) = tree.strategic_collateral_tree {
        check_division_safety_in_node(strategic_tree, &mut errors);
    }

    // Check end-of-tick collateral tree
    if let Some(ref eot_tree) = tree.end_of_tick_collateral_tree {
        check_division_safety_in_node(eot_tree, &mut errors);
    }

    if errors.is_empty() {
        Ok(())
    } else {
        Err(errors)
    }
}

fn check_division_safety_in_node(node: &TreeNode, errors: &mut Vec<ValidationError>) {
    match node {
        TreeNode::Condition {
            condition,
            on_true,
            on_false,
            ..
        } => {
            check_division_in_expression(condition, node.node_id(), errors);
            check_division_safety_in_node(on_true, errors);
            check_division_safety_in_node(on_false, errors);
        }
        TreeNode::Action { parameters, .. } => {
            for value_or_compute in parameters.values() {
                if let ValueOrCompute::Compute { compute } = value_or_compute {
                    check_division_in_computation(compute, node.node_id(), errors);
                }
            }
        }
    }
}

fn check_division_in_expression(
    expr: &Expression,
    node_id: &str,
    errors: &mut Vec<ValidationError>,
) {
    match expr {
        Expression::Equal { left, right }
        | Expression::NotEqual { left, right }
        | Expression::LessThan { left, right }
        | Expression::LessOrEqual { left, right }
        | Expression::GreaterThan { left, right }
        | Expression::GreaterOrEqual { left, right } => {
            if let Value::Compute { compute } = left {
                check_division_in_computation(compute, node_id, errors);
            }
            if let Value::Compute { compute } = right {
                check_division_in_computation(compute, node_id, errors);
            }
        }
        Expression::And { conditions } | Expression::Or { conditions } => {
            for cond in conditions {
                check_division_in_expression(cond, node_id, errors);
            }
        }
        Expression::Not { condition } => {
            check_division_in_expression(condition, node_id, errors);
        }
    }
}

fn check_division_in_computation(
    comp: &Computation,
    node_id: &str,
    errors: &mut Vec<ValidationError>,
) {
    match comp {
        Computation::Divide { left: _, right } => {
            // Check if right is a literal zero
            if is_literal_zero(right) {
                errors.push(ValidationError::DivisionByZeroRisk(node_id.to_string()));
            }
            // Recurse into nested computations
            if let Value::Compute { compute } = right {
                check_division_in_computation(compute, node_id, errors);
            }
        }
        Computation::Add { left, right }
        | Computation::Subtract { left, right }
        | Computation::Multiply { left, right } => {
            if let Value::Compute { compute } = left {
                check_division_in_computation(compute, node_id, errors);
            }
            if let Value::Compute { compute } = right {
                check_division_in_computation(compute, node_id, errors);
            }
        }
        Computation::Max { values } | Computation::Min { values } => {
            for value in values {
                if let Value::Compute { compute } = value {
                    check_division_in_computation(compute, node_id, errors);
                }
            }
        }
        // Phase 2.3: Math helper functions
        Computation::Ceil { value }
        | Computation::Floor { value }
        | Computation::Round { value }
        | Computation::Abs { value } => {
            if let Value::Compute { compute } = value {
                check_division_in_computation(compute, node_id, errors);
            }
        }
        Computation::Clamp { value, min, max } => {
            if let Value::Compute { compute } = value {
                check_division_in_computation(compute, node_id, errors);
            }
            if let Value::Compute { compute } = min {
                check_division_in_computation(compute, node_id, errors);
            }
            if let Value::Compute { compute } = max {
                check_division_in_computation(compute, node_id, errors);
            }
        }
        Computation::SafeDiv {
            numerator,
            denominator,
            default,
        } => {
            // SafeDiv doesn't error on divide-by-zero, so no need to check
            // But recurse into nested computations
            if let Value::Compute { compute } = numerator {
                check_division_in_computation(compute, node_id, errors);
            }
            if let Value::Compute { compute } = denominator {
                check_division_in_computation(compute, node_id, errors);
            }
            if let Value::Compute { compute } = default {
                check_division_in_computation(compute, node_id, errors);
            }
        }
    }
}

fn is_literal_zero(value: &Value) -> bool {
    match value {
        Value::Literal { value } => {
            if let Some(num) = value.as_f64() {
                num.abs() < f64::EPSILON
            } else if let Some(int) = value.as_i64() {
                int == 0
            } else {
                false
            }
        }
        _ => false,
    }
}

// ============================================================================
// Phase 6.14: Action Reachability
// ============================================================================

/// Validate that all action nodes are potentially reachable across all three trees
///
/// This is a best-effort static analysis. We check for obviously unreachable
/// actions (e.g., both branches lead to same action, conditions always false).
fn validate_action_reachability(tree: &DecisionTreeDef) -> ValidationResult {
    let mut all_actions = HashSet::new();
    let mut reachable_actions = HashSet::new();

    // Collect all action nodes from payment tree
    if let Some(ref payment_tree) = tree.payment_tree {
        collect_all_actions(payment_tree, &mut all_actions);
        mark_reachable_actions(payment_tree, &mut reachable_actions);
    }

    // Collect all action nodes from strategic collateral tree
    if let Some(ref strategic_tree) = tree.strategic_collateral_tree {
        collect_all_actions(strategic_tree, &mut all_actions);
        mark_reachable_actions(strategic_tree, &mut reachable_actions);
    }

    // Collect all action nodes from end-of-tick collateral tree
    if let Some(ref eot_tree) = tree.end_of_tick_collateral_tree {
        collect_all_actions(eot_tree, &mut all_actions);
        mark_reachable_actions(eot_tree, &mut reachable_actions);
    }

    // Find unreachable actions
    let mut errors = Vec::new();
    for action_id in &all_actions {
        if !reachable_actions.contains(action_id) {
            errors.push(ValidationError::UnreachableAction(action_id.clone()));
        }
    }

    if errors.is_empty() {
        Ok(())
    } else {
        Err(errors)
    }
}

fn collect_all_actions(node: &TreeNode, actions: &mut HashSet<String>) {
    match node {
        TreeNode::Action { node_id, .. } => {
            actions.insert(node_id.clone());
        }
        TreeNode::Condition {
            on_true, on_false, ..
        } => {
            collect_all_actions(on_true, actions);
            collect_all_actions(on_false, actions);
        }
    }
}

fn mark_reachable_actions(node: &TreeNode, reachable: &mut HashSet<String>) {
    match node {
        TreeNode::Action { node_id, .. } => {
            reachable.insert(node_id.clone());
        }
        TreeNode::Condition {
            on_true, on_false, ..
        } => {
            // Both branches are potentially reachable
            mark_reachable_actions(on_true, reachable);
            mark_reachable_actions(on_false, reachable);
        }
    }
}

// ============================================================================
// TESTS - Phase 6.9-6.14
// ============================================================================

#[cfg(test)]
mod tests {
    use super::*;
    use crate::policy::tree::types::{ActionType, Expression, TreeNode, Value};
    use crate::{Agent, SimulationState, Transaction};
    use serde_json::json;

    fn create_sample_context() -> EvalContext {
        let tx = Transaction::new("BANK_A".to_string(), "BANK_B".to_string(), 100_000, 0, 50);
        let agent = Agent::new("BANK_A".to_string(), 500_000);
        let state = SimulationState::new(vec![agent.clone()]);
        let cost_rates = crate::orchestrator::CostRates::default();
        EvalContext::build(&tx, &agent, &state, 10, &cost_rates, 100, 0.8)
    }

    // ========================================================================
    // Phase 6.9: Node ID Uniqueness Tests
    // ========================================================================

    #[test]
    fn test_validate_unique_node_ids() {
        let context = create_sample_context();

        let tree = DecisionTreeDef {
            version: "1.0".to_string(),
            policy_id: "test".to_string(),
            description: None,
            bank_tree: None,
            payment_tree: Some(TreeNode::Condition {
                node_id: "N1".to_string(),
                description: String::new(),
                condition: Expression::GreaterThan {
                    left: Value::Field {
                        field: "balance".to_string(),
                    },
                    right: Value::Literal { value: json!(0) },
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

        let result = validate_tree(&tree, &context);
        assert!(result.is_ok());
    }

    #[test]
    fn test_reject_duplicate_node_ids() {
        let context = create_sample_context();

        let tree = DecisionTreeDef {
            version: "1.0".to_string(),
            policy_id: "test".to_string(),
            description: None,
            bank_tree: None,
            payment_tree: Some(TreeNode::Condition {
                node_id: "N1".to_string(),
                description: String::new(),
                condition: Expression::GreaterThan {
                    left: Value::Field {
                        field: "balance".to_string(),
                    },
                    right: Value::Literal { value: json!(0) },
                },
                on_true: Box::new(TreeNode::Action {
                    node_id: "A1".to_string(), // DUPLICATE
                    action: ActionType::Release,
                    parameters: HashMap::new(),
                }),
                on_false: Box::new(TreeNode::Action {
                    node_id: "A1".to_string(), // DUPLICATE
                    action: ActionType::Hold,
                    parameters: HashMap::new(),
                }),
            }),
            strategic_collateral_tree: None,
            end_of_tick_collateral_tree: None,
            parameters: HashMap::new(),
        };

        let result = validate_tree(&tree, &context);
        assert!(result.is_err());

        let errors = result.unwrap_err();
        assert!(errors
            .iter()
            .any(|e| matches!(e, ValidationError::DuplicateNodeId(_))));
    }

    // ========================================================================
    // Phase 6.10: Tree Depth Tests
    // ========================================================================

    #[test]
    fn test_validate_tree_depth_ok() {
        let context = create_sample_context();

        // Create a reasonably deep tree (10 levels)
        fn build_nested_tree(depth: usize) -> TreeNode {
            if depth == 0 {
                TreeNode::Action {
                    node_id: "A_leaf".to_string(),
                    action: ActionType::Release,
                    parameters: HashMap::new(),
                }
            } else {
                TreeNode::Condition {
                    node_id: format!("N_{}", depth),
                    description: String::new(),
                    condition: Expression::GreaterThan {
                        left: Value::Field {
                            field: "balance".to_string(),
                        },
                        right: Value::Literal { value: json!(0) },
                    },
                    on_true: Box::new(build_nested_tree(depth - 1)),
                    on_false: Box::new(TreeNode::Action {
                        node_id: format!("A_{}", depth),
                        action: ActionType::Hold,
                        parameters: HashMap::new(),
                    }),
                }
            }
        }

        let tree = DecisionTreeDef {
            version: "1.0".to_string(),
            policy_id: "test".to_string(),
            description: None,
            bank_tree: None,
            payment_tree: Some(build_nested_tree(10)),
            strategic_collateral_tree: None,
            end_of_tick_collateral_tree: None,
            parameters: HashMap::new(),
        };

        let result = validate_tree(&tree, &context);
        assert!(result.is_ok());
    }

    // ========================================================================
    // Phase 6.11: Field Reference Tests
    // ========================================================================

    #[test]
    fn test_validate_valid_field_references() {
        let context = create_sample_context();

        let tree = DecisionTreeDef {
            version: "1.0".to_string(),
            policy_id: "test".to_string(),
            description: None,
            bank_tree: None,
            payment_tree: Some(TreeNode::Condition {
                node_id: "N1".to_string(),
                description: String::new(),
                condition: Expression::GreaterThan {
                    left: Value::Field {
                        field: "balance".to_string(), // Valid field
                    },
                    right: Value::Field {
                        field: "amount".to_string(), // Valid field
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

        let result = validate_tree(&tree, &context);
        assert!(result.is_ok());
    }

    #[test]
    fn test_reject_invalid_field_references() {
        let context = create_sample_context();

        let tree = DecisionTreeDef {
            version: "1.0".to_string(),
            policy_id: "test".to_string(),
            description: None,
            bank_tree: None,
            payment_tree: Some(TreeNode::Condition {
                node_id: "N1".to_string(),
                description: String::new(),
                condition: Expression::GreaterThan {
                    left: Value::Field {
                        field: "nonexistent_field".to_string(), // INVALID
                    },
                    right: Value::Literal { value: json!(0) },
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

        let result = validate_tree(&tree, &context);
        assert!(result.is_err());

        let errors = result.unwrap_err();
        assert!(errors
            .iter()
            .any(|e| matches!(e, ValidationError::InvalidFieldReference(_))));
    }

    // ========================================================================
    // Phase 6.12: Parameter Reference Tests
    // ========================================================================

    #[test]
    fn test_validate_valid_parameter_references() {
        let context = create_sample_context();

        let mut params = HashMap::new();
        params.insert("threshold".to_string(), 100_000.0);

        let tree = DecisionTreeDef {
            version: "1.0".to_string(),
            policy_id: "test".to_string(),
            description: None,
            bank_tree: None,
            payment_tree: Some(TreeNode::Condition {
                node_id: "N1".to_string(),
                description: String::new(),
                condition: Expression::GreaterThan {
                    left: Value::Field {
                        field: "balance".to_string(),
                    },
                    right: Value::Param {
                        param: "threshold".to_string(), // Valid param
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

        let result = validate_tree(&tree, &context);
        assert!(result.is_ok());
    }

    #[test]
    fn test_reject_invalid_parameter_references() {
        let context = create_sample_context();

        let tree = DecisionTreeDef {
            version: "1.0".to_string(),
            policy_id: "test".to_string(),
            description: None,
            bank_tree: None,
            payment_tree: Some(TreeNode::Condition {
                node_id: "N1".to_string(),
                description: String::new(),
                condition: Expression::GreaterThan {
                    left: Value::Field {
                        field: "balance".to_string(),
                    },
                    right: Value::Param {
                        param: "nonexistent_param".to_string(), // INVALID
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
            parameters: HashMap::new(), // Missing parameter
        };

        let result = validate_tree(&tree, &context);
        assert!(result.is_err());

        let errors = result.unwrap_err();
        assert!(errors
            .iter()
            .any(|e| matches!(e, ValidationError::InvalidParameterReference(_))));
    }

    // ========================================================================
    // Phase 6.13: Division Safety Tests
    // ========================================================================

    #[test]
    fn test_reject_division_by_literal_zero() {
        let context = create_sample_context();

        let tree = DecisionTreeDef {
            version: "1.0".to_string(),
            policy_id: "test".to_string(),
            description: None,
            bank_tree: None,
            payment_tree: Some(TreeNode::Condition {
                node_id: "N1".to_string(),
                description: String::new(),
                condition: Expression::GreaterThan {
                    left: Value::Compute {
                        compute: Box::new(Computation::Divide {
                            left: Value::Field {
                                field: "balance".to_string(),
                            },
                            right: Value::Literal { value: json!(0) }, // DIVISION BY ZERO
                        }),
                    },
                    right: Value::Literal { value: json!(100) },
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

        let result = validate_tree(&tree, &context);
        assert!(result.is_err());

        let errors = result.unwrap_err();
        assert!(errors
            .iter()
            .any(|e| matches!(e, ValidationError::DivisionByZeroRisk(_))));
    }

    #[test]
    fn test_allow_division_by_field_reference() {
        let context = create_sample_context();

        let tree = DecisionTreeDef {
            version: "1.0".to_string(),
            policy_id: "test".to_string(),
            description: None,
            bank_tree: None,
            payment_tree: Some(TreeNode::Condition {
                node_id: "N1".to_string(),
                description: String::new(),
                condition: Expression::GreaterThan {
                    left: Value::Compute {
                        compute: Box::new(Computation::Divide {
                            left: Value::Field {
                                field: "balance".to_string(),
                            },
                            right: Value::Field {
                                field: "amount".to_string(), // OK: field reference (runtime check)
                            },
                        }),
                    },
                    right: Value::Literal { value: json!(1) },
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

        let result = validate_tree(&tree, &context);
        assert!(result.is_ok());
    }

    // ========================================================================
    // Collateral Tree Field Access Tests
    // ========================================================================

    #[test]
    fn test_collateral_tree_can_access_state_registers() {
        let context = create_sample_context();

        // Strategic collateral tree should accept bank_state_* fields
        // because it uses EvalContext::build() which includes state registers
        let tree = DecisionTreeDef {
            version: "1.0".to_string(),
            policy_id: "test".to_string(),
            description: None,
            bank_tree: None,
            payment_tree: None,
            strategic_collateral_tree: Some(TreeNode::Condition {
                node_id: "SC1".to_string(),
                description: String::new(),
                condition: Expression::GreaterThan {
                    left: Value::Field {
                        field: "bank_state_stress".to_string(), // State register
                    },
                    right: Value::Literal { value: json!(0.5) },
                },
                on_true: Box::new(TreeNode::Action {
                    node_id: "SCA1".to_string(),
                    action: ActionType::PostCollateral,
                    parameters: HashMap::new(),
                }),
                on_false: Box::new(TreeNode::Action {
                    node_id: "SCA2".to_string(),
                    action: ActionType::HoldCollateral,
                    parameters: HashMap::new(),
                }),
            }),
            end_of_tick_collateral_tree: None,
            parameters: HashMap::new(),
        };

        let result = validate_tree(&tree, &context);
        assert!(result.is_ok(), "Collateral trees should accept bank_state_* fields");
    }

    #[test]
    fn test_collateral_tree_can_access_excess_collateral() {
        let context = create_sample_context();

        // Strategic collateral tree should accept excess_collateral field
        // because it's provided by EvalContext::build()
        let tree = DecisionTreeDef {
            version: "1.0".to_string(),
            policy_id: "test".to_string(),
            description: None,
            bank_tree: None,
            payment_tree: None,
            strategic_collateral_tree: Some(TreeNode::Condition {
                node_id: "SC1".to_string(),
                description: String::new(),
                condition: Expression::GreaterThan {
                    left: Value::Field {
                        field: "excess_collateral".to_string(), // Derived collateral field
                    },
                    right: Value::Literal { value: json!(0) },
                },
                on_true: Box::new(TreeNode::Action {
                    node_id: "SCA1".to_string(),
                    action: ActionType::WithdrawCollateral,
                    parameters: HashMap::new(),
                }),
                on_false: Box::new(TreeNode::Action {
                    node_id: "SCA2".to_string(),
                    action: ActionType::HoldCollateral,
                    parameters: HashMap::new(),
                }),
            }),
            end_of_tick_collateral_tree: None,
            parameters: HashMap::new(),
        };

        let result = validate_tree(&tree, &context);
        assert!(result.is_ok(), "Collateral trees should accept excess_collateral field");
    }

    #[test]
    fn test_end_of_tick_collateral_tree_can_access_bank_state() {
        let context = create_sample_context();

        // End-of-tick collateral tree should also accept state registers
        let tree = DecisionTreeDef {
            version: "1.0".to_string(),
            policy_id: "test".to_string(),
            description: None,
            bank_tree: None,
            payment_tree: None,
            strategic_collateral_tree: None,
            end_of_tick_collateral_tree: Some(TreeNode::Condition {
                node_id: "EC1".to_string(),
                description: String::new(),
                condition: Expression::GreaterThan {
                    left: Value::Field {
                        field: "bank_state_cooldown".to_string(), // State register
                    },
                    right: Value::Literal { value: json!(0) },
                },
                on_true: Box::new(TreeNode::Action {
                    node_id: "ECA1".to_string(),
                    action: ActionType::HoldCollateral,
                    parameters: HashMap::new(),
                }),
                on_false: Box::new(TreeNode::Action {
                    node_id: "ECA2".to_string(),
                    action: ActionType::WithdrawCollateral,
                    parameters: HashMap::new(),
                }),
            }),
            parameters: HashMap::new(),
        };

        let result = validate_tree(&tree, &context);
        assert!(result.is_ok(), "End-of-tick collateral trees should accept bank_state_* fields");
    }

    #[test]
    fn test_collateral_tree_can_access_required_collateral_for_usage() {
        let context = create_sample_context();

        // Test another derived collateral field
        let tree = DecisionTreeDef {
            version: "1.0".to_string(),
            policy_id: "test".to_string(),
            description: None,
            bank_tree: None,
            payment_tree: None,
            strategic_collateral_tree: Some(TreeNode::Condition {
                node_id: "SC1".to_string(),
                description: String::new(),
                condition: Expression::GreaterThan {
                    left: Value::Field {
                        field: "required_collateral_for_usage".to_string(),
                    },
                    right: Value::Field {
                        field: "posted_collateral".to_string(),
                    },
                },
                on_true: Box::new(TreeNode::Action {
                    node_id: "SCA1".to_string(),
                    action: ActionType::PostCollateral,
                    parameters: HashMap::new(),
                }),
                on_false: Box::new(TreeNode::Action {
                    node_id: "SCA2".to_string(),
                    action: ActionType::HoldCollateral,
                    parameters: HashMap::new(),
                }),
            }),
            end_of_tick_collateral_tree: None,
            parameters: HashMap::new(),
        };

        let result = validate_tree(&tree, &context);
        assert!(result.is_ok(), "Collateral trees should accept required_collateral_for_usage field");
    }

    #[test]
    fn test_collateral_tree_can_access_overdraft_utilization() {
        let context = create_sample_context();

        // Test overdraft_utilization field
        let tree = DecisionTreeDef {
            version: "1.0".to_string(),
            policy_id: "test".to_string(),
            description: None,
            bank_tree: None,
            payment_tree: None,
            strategic_collateral_tree: Some(TreeNode::Condition {
                node_id: "SC1".to_string(),
                description: String::new(),
                condition: Expression::GreaterThan {
                    left: Value::Field {
                        field: "overdraft_utilization".to_string(),
                    },
                    right: Value::Literal { value: json!(0.8) },
                },
                on_true: Box::new(TreeNode::Action {
                    node_id: "SCA1".to_string(),
                    action: ActionType::PostCollateral,
                    parameters: HashMap::new(),
                }),
                on_false: Box::new(TreeNode::Action {
                    node_id: "SCA2".to_string(),
                    action: ActionType::HoldCollateral,
                    parameters: HashMap::new(),
                }),
            }),
            end_of_tick_collateral_tree: None,
            parameters: HashMap::new(),
        };

        let result = validate_tree(&tree, &context);
        assert!(result.is_ok(), "Collateral trees should accept overdraft_utilization field");
    }
}
