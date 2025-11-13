// Phase 6: Policy DSL - Type Definitions
//
// JSON decision tree format for LLM-editable policies.
// All types are designed to deserialize safely from JSON with validation.

use serde::{Deserialize, Serialize};
use std::collections::HashMap;

// ============================================================================
// DECISION TREE DEFINITION
// ============================================================================

/// Complete decision tree definition
///
/// This is the root object deserialized from JSON policy files.
/// Phase 8.2: Extended to support three separate decision trees:
/// - payment_tree: Payment release decisions (Queue 1 → Queue 2)
/// - strategic_collateral_tree: Strategic collateral decisions (STEP 2.5)
/// - end_of_tick_collateral_tree: Reactive collateral cleanup (STEP 8)
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DecisionTreeDef {
    /// Schema version (currently "1.0")
    pub version: String,

    /// Unique identifier for this policy
    pub policy_id: String,

    /// Optional human-readable description
    #[serde(default)]
    pub description: Option<String>,

    /// Payment release decision tree (Queue 1 → Queue 2 decisions)
    /// Optional to allow collateral-only policies
    #[serde(default)]
    pub payment_tree: Option<TreeNode>,

    /// Strategic collateral decision tree (Layer 1, STEP 2.5)
    /// Runs before settlements, forward-looking, policy-based
    #[serde(default)]
    pub strategic_collateral_tree: Option<TreeNode>,

    /// End-of-tick collateral decision tree (Layer 2, STEP 8)
    /// Runs after settlements, reactive cleanup
    #[serde(default)]
    pub end_of_tick_collateral_tree: Option<TreeNode>,

    /// Named parameters (thresholds, constants)
    #[serde(default)]
    pub parameters: HashMap<String, f64>,
}

// ============================================================================
// TREE NODES
// ============================================================================

/// A node in the decision tree
///
/// Two variants:
/// - Condition: Evaluate expression, branch based on result
/// - Action: Terminal node that returns a decision
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(tag = "type", rename_all = "lowercase")]
pub enum TreeNode {
    /// Conditional branch node
    Condition {
        /// Unique node identifier
        node_id: String,

        /// Optional human-readable description
        #[serde(default)]
        description: String,

        /// Boolean expression to evaluate
        condition: Expression,

        /// Node to visit if condition is true
        on_true: Box<TreeNode>,

        /// Node to visit if condition is false
        on_false: Box<TreeNode>,
    },

    /// Terminal action node
    Action {
        /// Unique node identifier
        node_id: String,

        /// Action to take
        action: ActionType,

        /// Optional action parameters
        #[serde(default)]
        parameters: HashMap<String, ValueOrCompute>,
    },
}

// ============================================================================
// EXPRESSIONS
// ============================================================================

/// Boolean expression
///
/// Evaluates to true or false based on simulation state.
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(tag = "op")]
pub enum Expression {
    // Comparison operators
    /// Equal (with epsilon tolerance for floats)
    #[serde(rename = "==")]
    Equal { left: Value, right: Value },

    /// Not equal
    #[serde(rename = "!=")]
    NotEqual { left: Value, right: Value },

    /// Less than
    #[serde(rename = "<")]
    LessThan { left: Value, right: Value },

    /// Less than or equal
    #[serde(rename = "<=")]
    LessOrEqual { left: Value, right: Value },

    /// Greater than
    #[serde(rename = ">")]
    GreaterThan { left: Value, right: Value },

    /// Greater than or equal
    #[serde(rename = ">=")]
    GreaterOrEqual { left: Value, right: Value },

    // Logical operators
    /// Logical AND (short-circuit evaluation)
    #[serde(rename = "and")]
    And { conditions: Vec<Expression> },

    /// Logical OR (short-circuit evaluation)
    #[serde(rename = "or")]
    Or { conditions: Vec<Expression> },

    /// Logical NOT
    #[serde(rename = "not")]
    Not { condition: Box<Expression> },
}

// ============================================================================
// VALUES
// ============================================================================

/// A value in an expression
///
/// Can be a field reference, parameter, literal, or computed value.
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(untagged)]
pub enum Value {
    /// Reference to a field in the evaluation context
    /// Examples: "balance", "amount", "ticks_to_deadline"
    Field { field: String },

    /// Reference to a named parameter
    /// Examples: "urgency_threshold", "liquidity_buffer"
    Param { param: String },

    /// Literal value (number, string, boolean)
    Literal { value: serde_json::Value },

    /// Computed value (arithmetic expression)
    Compute { compute: Box<Computation> },
}

/// A value or computation for action parameters
///
/// Similar to Value but used in action parameter contexts.
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(untagged)]
pub enum ValueOrCompute {
    /// Direct literal value
    Direct { value: serde_json::Value },

    /// Field reference
    Field { field: String },

    /// Parameter reference
    Param { param: String },

    /// Computed value
    Compute { compute: Computation },
}

// ============================================================================
// COMPUTATIONS
// ============================================================================

/// Arithmetic computation
///
/// Evaluates to a numeric value.
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(tag = "op")]
pub enum Computation {
    // Binary operators
    /// Addition
    #[serde(rename = "+")]
    Add { left: Value, right: Value },

    /// Subtraction
    #[serde(rename = "-")]
    Subtract { left: Value, right: Value },

    /// Multiplication
    #[serde(rename = "*")]
    Multiply { left: Value, right: Value },

    /// Division (checked for divide-by-zero at runtime)
    #[serde(rename = "/")]
    Divide { left: Value, right: Value },

    // N-ary operators
    /// Maximum of multiple values
    #[serde(rename = "max")]
    Max { values: Vec<Value> },

    /// Minimum of multiple values
    #[serde(rename = "min")]
    Min { values: Vec<Value> },

    // Phase 2.3: Math Helper Functions (Policy Enhancements V2)
    /// Ceiling - round up to nearest integer
    #[serde(rename = "ceil")]
    Ceil { value: Value },

    /// Floor - round down to nearest integer
    #[serde(rename = "floor")]
    Floor { value: Value },

    /// Round - round to nearest integer
    #[serde(rename = "round")]
    Round { value: Value },

    /// Absolute value
    #[serde(rename = "abs")]
    Abs { value: Value },

    /// Clamp value to range [min, max]
    #[serde(rename = "clamp")]
    Clamp {
        value: Value,
        min: Value,
        max: Value,
    },

    /// Safe division - return default if denominator is zero or near-zero
    #[serde(rename = "div0")]
    SafeDiv {
        numerator: Value,
        denominator: Value,
        default: Value,
    },
}

// ============================================================================
// ACTIONS
// ============================================================================

/// Action type for terminal nodes
///
/// Maps to ReleaseDecision variants in the policy system.
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "PascalCase")]
pub enum ActionType {
    /// Submit transaction in full to RTGS
    Release,

    /// Submit transaction using credit if needed
    ReleaseWithCredit,

    /// Split and pace transaction (Phase 5)
    PaceAndRelease,

    /// Split transaction into multiple parts (Phase 5)
    Split,

    /// Hold transaction in Queue 1 for later
    Hold,

    /// Drop transaction (expired or unviable)
    Drop,

    /// Reprioritize transaction (Phase 4: Overdue Handling)
    /// Change transaction priority without moving from Queue 1
    Reprioritize,

    // Phase 8: Collateral Management Actions
    /// Post collateral to increase available liquidity
    PostCollateral,

    /// Withdraw collateral to reduce opportunity costs
    WithdrawCollateral,

    /// Take no action on collateral (keep current level)
    HoldCollateral,
}

// ============================================================================
// HELPER METHODS
// ============================================================================

impl TreeNode {
    /// Get the node ID
    pub fn node_id(&self) -> &str {
        match self {
            TreeNode::Condition { node_id, .. } => node_id,
            TreeNode::Action { node_id, .. } => node_id,
        }
    }

    /// Check if this is a condition node
    pub fn is_condition(&self) -> bool {
        matches!(self, TreeNode::Condition { .. })
    }

    /// Check if this is an action node
    pub fn is_action(&self) -> bool {
        matches!(self, TreeNode::Action { .. })
    }
}

// ============================================================================
// TESTS
// ============================================================================

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_node_id_accessor() {
        let action = TreeNode::Action {
            node_id: "A1".to_string(),
            action: ActionType::Release,
            parameters: HashMap::new(),
        };
        assert_eq!(action.node_id(), "A1");
        assert!(action.is_action());
        assert!(!action.is_condition());
    }

    #[test]
    fn test_tree_def_deserialization_simple() {
        let json = r#"{
            "version": "1.0",
            "policy_id": "test",
            "payment_tree": {
                "node_id": "A1",
                "type": "action",
                "action": "Release"
            }
        }"#;

        let tree: DecisionTreeDef = serde_json::from_str(json).unwrap();
        assert_eq!(tree.version, "1.0");
        assert_eq!(tree.policy_id, "test");
        assert!(tree.payment_tree.is_some());
        assert!(tree.payment_tree.unwrap().is_action());
    }

    // ============================================================================
    // PHASE 6.1: Type System & Deserialization Tests
    // ============================================================================

    #[test]
    fn test_parse_minimal_tree() {
        // Simplest valid tree: single condition, two actions
        let json = r#"{
            "version": "1.0",
            "policy_id": "minimal_test",
            "payment_tree": {
                "node_id": "N1",
                "type": "condition",
                "condition": {
                    "op": ">",
                    "left": {"field": "balance"},
                    "right": {"field": "amount"}
                },
                "on_true": {
                    "node_id": "A1",
                    "type": "action",
                    "action": "Release"
                },
                "on_false": {
                    "node_id": "A2",
                    "type": "action",
                    "action": "Hold"
                }
            },
            "parameters": {}
        }"#;

        let tree: Result<DecisionTreeDef, _> = serde_json::from_str(json);
        assert!(
            tree.is_ok(),
            "Failed to parse minimal tree: {:?}",
            tree.err()
        );

        let tree = tree.unwrap();
        assert_eq!(tree.version, "1.0");
        assert_eq!(tree.policy_id, "minimal_test");
        assert!(tree.payment_tree.is_some());
        assert!(matches!(
            tree.payment_tree.as_ref().unwrap(),
            TreeNode::Condition { .. }
        ));
    }

    #[test]
    fn test_parse_nested_conditions() {
        // Multi-level tree with nested conditions
        let json = r#"{
            "version": "1.0",
            "policy_id": "nested_test",
            "payment_tree": {
                "node_id": "N1",
                "type": "condition",
                "condition": {
                    "op": "<=",
                    "left": {"field": "ticks_to_deadline"},
                    "right": {"value": 5}
                },
                "on_true": {
                    "node_id": "A1",
                    "type": "action",
                    "action": "Release"
                },
                "on_false": {
                    "node_id": "N2",
                    "type": "condition",
                    "condition": {
                        "op": ">=",
                        "left": {"field": "balance"},
                        "right": {"field": "amount"}
                    },
                    "on_true": {
                        "node_id": "A2",
                        "type": "action",
                        "action": "Release"
                    },
                    "on_false": {
                        "node_id": "A3",
                        "type": "action",
                        "action": "Hold"
                    }
                }
            }
        }"#;

        let tree: Result<DecisionTreeDef, _> = serde_json::from_str(json);
        assert!(
            tree.is_ok(),
            "Failed to parse nested tree: {:?}",
            tree.err()
        );
    }

    #[test]
    fn test_parse_with_computations() {
        // Tree with arithmetic computations in conditions
        let json = r#"{
            "version": "1.0",
            "policy_id": "computation_test",
            "payment_tree": {
                "node_id": "N1",
                "type": "condition",
                "condition": {
                    "op": ">",
                    "left": {
                        "compute": {
                            "op": "+",
                            "left": {"field": "balance"},
                            "right": {"field": "credit"}
                        }
                    },
                    "right": {"field": "amount"}
                },
                "on_true": {
                    "node_id": "A1",
                    "type": "action",
                    "action": "Release"
                },
                "on_false": {
                    "node_id": "A2",
                    "type": "action",
                    "action": "Hold"
                }
            }
        }"#;

        let tree: Result<DecisionTreeDef, _> = serde_json::from_str(json);
        assert!(
            tree.is_ok(),
            "Failed to parse tree with computations: {:?}",
            tree.err()
        );
    }

    #[test]
    fn test_reject_invalid_json() {
        // Missing required field 'version'
        let json = r#"{
            "policy_id": "invalid",
            "payment_tree": {
                "node_id": "N1",
                "type": "action",
                "action": "Hold"
            }
        }"#;

        let tree: Result<DecisionTreeDef, _> = serde_json::from_str(json);
        assert!(tree.is_err(), "Should reject JSON missing required field");
    }

    #[test]
    fn test_parse_all_expression_types() {
        // Test all comparison operators
        let operators = vec![
            ("==", "Equal"),
            ("!=", "NotEqual"),
            ("<", "LessThan"),
            ("<=", "LessOrEqual"),
            (">", "GreaterThan"),
            (">=", "GreaterOrEqual"),
        ];

        for (op, _name) in operators {
            let json = format!(
                r#"{{
                "version": "1.0",
                "policy_id": "test_{}",
                "payment_tree": {{
                    "node_id": "N1",
                    "type": "condition",
                    "condition": {{
                        "op": "{}",
                        "left": {{"field": "balance"}},
                        "right": {{"field": "amount"}}
                    }},
                    "on_true": {{"node_id": "A1", "type": "action", "action": "Release"}},
                    "on_false": {{"node_id": "A2", "type": "action", "action": "Hold"}}
                }}
            }}"#,
                op, op
            );

            let tree: Result<DecisionTreeDef, _> = serde_json::from_str(&json);
            assert!(
                tree.is_ok(),
                "Failed to parse {} operator: {:?}",
                op,
                tree.err()
            );
        }

        // Test logical operators
        let logical_json = r#"{
            "version": "1.0",
            "policy_id": "logical_test",
            "payment_tree": {
                "node_id": "N1",
                "type": "condition",
                "condition": {
                    "op": "and",
                    "conditions": [
                        {"op": ">", "left": {"field": "balance"}, "right": {"value": 0}},
                        {"op": "<", "left": {"field": "amount"}, "right": {"value": 1000}}
                    ]
                },
                "on_true": {"node_id": "A1", "type": "action", "action": "Release"},
                "on_false": {"node_id": "A2", "type": "action", "action": "Hold"}
            }
        }"#;

        let tree: Result<DecisionTreeDef, _> = serde_json::from_str(logical_json);
        assert!(
            tree.is_ok(),
            "Failed to parse AND operator: {:?}",
            tree.err()
        );
    }

    #[test]
    fn test_parse_all_value_types() {
        // Test field reference
        let field_json = r#"{"field": "balance"}"#;
        let val: Result<Value, _> = serde_json::from_str(field_json);
        assert!(val.is_ok(), "Failed to parse field value");
        assert!(matches!(val.unwrap(), Value::Field { .. }));

        // Test parameter reference
        let param_json = r#"{"param": "threshold"}"#;
        let val: Result<Value, _> = serde_json::from_str(param_json);
        assert!(val.is_ok(), "Failed to parse param value");
        assert!(matches!(val.unwrap(), Value::Param { .. }));

        // Test literal
        let literal_json = r#"{"value": 100}"#;
        let val: Result<Value, _> = serde_json::from_str(literal_json);
        assert!(val.is_ok(), "Failed to parse literal value");
        assert!(matches!(val.unwrap(), Value::Literal { .. }));

        // Test computation
        let compute_json = r#"{
            "compute": {
                "op": "+",
                "left": {"field": "balance"},
                "right": {"field": "credit"}
            }
        }"#;
        let val: Result<Value, _> = serde_json::from_str(compute_json);
        assert!(val.is_ok(), "Failed to parse compute value");
        assert!(matches!(val.unwrap(), Value::Compute { .. }));
    }

    #[test]
    fn test_parse_all_action_types() {
        let actions = vec![
            "Release",
            "Hold",
            "Drop",
            "ReleaseWithCredit",
            "PaceAndRelease",
        ];

        for action in actions {
            let json = format!(
                r#"{{
                "version": "1.0",
                "policy_id": "action_test_{}",
                "payment_tree": {{
                    "node_id": "A1",
                    "type": "action",
                    "action": "{}"
                }}
            }}"#,
                action, action
            );

            let tree: Result<DecisionTreeDef, _> = serde_json::from_str(&json);
            assert!(
                tree.is_ok(),
                "Failed to parse action {}: {:?}",
                action,
                tree.err()
            );
        }
    }
}
