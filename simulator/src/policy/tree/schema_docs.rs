//! Policy Schema Documentation
//!
//! Self-documenting schema system for policy DSL elements.
//! Generates documentation from code metadata for CLI tool consumption.

use serde::{Deserialize, Serialize};

// ============================================================================
// DATA STRUCTURES
// ============================================================================

/// Category for grouping schema elements
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq, Hash)]
pub enum SchemaCategory {
    // Expression categories
    ComparisonOperator,
    LogicalOperator,

    // Computation categories
    BinaryArithmetic,
    NaryArithmetic,
    UnaryMath,
    TernaryMath,

    // Value categories
    ValueType,

    // Action categories
    PaymentAction,
    BankAction,
    CollateralAction,
    RtgsAction,

    // Field categories
    TransactionField,
    AgentField,
    QueueField,
    CollateralField,
    CostField,
    TimeField,
    LsmField,
    ThroughputField,
    StateRegisterField,
    SystemField,
    DerivedField,

    // Node categories
    NodeType,

    // Tree categories
    TreeType,
}

/// Documentation for an action parameter
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct ParameterDoc {
    pub name: String,
    pub param_type: String,
    pub required: bool,
    pub description: String,
    pub example: Option<serde_json::Value>,
    pub valid_values: Option<Vec<String>>,
}

/// Documentation for a single schema element
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct SchemaElement {
    pub name: String,
    pub json_key: String,
    pub category: SchemaCategory,
    pub description: String,
    pub semantics: Option<String>,
    pub parameters: Vec<ParameterDoc>,
    pub valid_in_trees: Vec<String>,
    pub example_json: Option<serde_json::Value>,
    pub source_location: String,
    pub see_also: Vec<String>,
    pub data_type: Option<String>,
    pub unit: Option<String>,
    pub added_in: Option<String>,
}

/// Complete schema documentation
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PolicySchemaDoc {
    pub version: String,
    pub generated_at: String,
    pub tree_types: Vec<SchemaElement>,
    pub node_types: Vec<SchemaElement>,
    pub expressions: Vec<SchemaElement>,
    pub values: Vec<SchemaElement>,
    pub computations: Vec<SchemaElement>,
    pub actions: Vec<SchemaElement>,
    pub fields: Vec<SchemaElement>,
}

/// Trait for types that can provide schema documentation
pub trait SchemaDocumented {
    fn schema_docs() -> Vec<SchemaElement>;
}

// ============================================================================
// IMPLEMENTATIONS
// ============================================================================

use super::types::{ActionType, Computation, Expression, Value};

/// All tree types for expressions (valid in all trees)
fn all_trees() -> Vec<String> {
    vec![
        "payment_tree".to_string(),
        "bank_tree".to_string(),
        "strategic_collateral_tree".to_string(),
        "end_of_tick_collateral_tree".to_string(),
    ]
}

impl SchemaDocumented for Expression {
    fn schema_docs() -> Vec<SchemaElement> {
        vec![
            // Comparison operators
            SchemaElement {
                name: "Equal".to_string(),
                json_key: "==".to_string(),
                category: SchemaCategory::ComparisonOperator,
                description: "Tests if two values are equal (with epsilon tolerance for floats)".to_string(),
                semantics: Some("Returns true if left == right within floating point tolerance".to_string()),
                parameters: vec![],
                valid_in_trees: all_trees(),
                example_json: Some(serde_json::json!({
                    "op": "==",
                    "left": {"field": "priority"},
                    "right": {"value": 10}
                })),
                source_location: "simulator/src/policy/tree/types.rs:117".to_string(),
                see_also: vec!["NotEqual".to_string()],
                data_type: None,
                unit: None,
                added_in: Some("1.0".to_string()),
            },
            SchemaElement {
                name: "NotEqual".to_string(),
                json_key: "!=".to_string(),
                category: SchemaCategory::ComparisonOperator,
                description: "Tests if two values are not equal".to_string(),
                semantics: Some("Returns true if left != right".to_string()),
                parameters: vec![],
                valid_in_trees: all_trees(),
                example_json: Some(serde_json::json!({
                    "op": "!=",
                    "left": {"field": "is_split"},
                    "right": {"value": 1}
                })),
                source_location: "simulator/src/policy/tree/types.rs:121".to_string(),
                see_also: vec!["Equal".to_string()],
                data_type: None,
                unit: None,
                added_in: Some("1.0".to_string()),
            },
            SchemaElement {
                name: "LessThan".to_string(),
                json_key: "<".to_string(),
                category: SchemaCategory::ComparisonOperator,
                description: "Tests if left value is strictly less than right value".to_string(),
                semantics: Some("Returns true if left < right".to_string()),
                parameters: vec![],
                valid_in_trees: all_trees(),
                example_json: Some(serde_json::json!({
                    "op": "<",
                    "left": {"field": "ticks_to_deadline"},
                    "right": {"value": 5}
                })),
                source_location: "simulator/src/policy/tree/types.rs:125".to_string(),
                see_also: vec!["LessOrEqual".to_string(), "GreaterThan".to_string()],
                data_type: None,
                unit: None,
                added_in: Some("1.0".to_string()),
            },
            SchemaElement {
                name: "LessOrEqual".to_string(),
                json_key: "<=".to_string(),
                category: SchemaCategory::ComparisonOperator,
                description: "Tests if left value is less than or equal to right value".to_string(),
                semantics: Some("Returns true if left <= right".to_string()),
                parameters: vec![],
                valid_in_trees: all_trees(),
                example_json: Some(serde_json::json!({
                    "op": "<=",
                    "left": {"field": "queue_age"},
                    "right": {"param": "max_wait_ticks"}
                })),
                source_location: "simulator/src/policy/tree/types.rs:129".to_string(),
                see_also: vec!["LessThan".to_string(), "GreaterOrEqual".to_string()],
                data_type: None,
                unit: None,
                added_in: Some("1.0".to_string()),
            },
            SchemaElement {
                name: "GreaterThan".to_string(),
                json_key: ">".to_string(),
                category: SchemaCategory::ComparisonOperator,
                description: "Tests if left value is strictly greater than right value".to_string(),
                semantics: Some("Returns true if left > right".to_string()),
                parameters: vec![],
                valid_in_trees: all_trees(),
                example_json: Some(serde_json::json!({
                    "op": ">",
                    "left": {"field": "effective_liquidity"},
                    "right": {"field": "remaining_amount"}
                })),
                source_location: "simulator/src/policy/tree/types.rs:133".to_string(),
                see_also: vec!["GreaterOrEqual".to_string(), "LessThan".to_string()],
                data_type: None,
                unit: None,
                added_in: Some("1.0".to_string()),
            },
            SchemaElement {
                name: "GreaterOrEqual".to_string(),
                json_key: ">=".to_string(),
                category: SchemaCategory::ComparisonOperator,
                description: "Tests if left value is greater than or equal to right value".to_string(),
                semantics: Some("Returns true if left >= right".to_string()),
                parameters: vec![],
                valid_in_trees: all_trees(),
                example_json: Some(serde_json::json!({
                    "op": ">=",
                    "left": {"field": "balance"},
                    "right": {"field": "amount"}
                })),
                source_location: "simulator/src/policy/tree/types.rs:137".to_string(),
                see_also: vec!["GreaterThan".to_string(), "LessOrEqual".to_string()],
                data_type: None,
                unit: None,
                added_in: Some("1.0".to_string()),
            },
            // Logical operators
            SchemaElement {
                name: "And".to_string(),
                json_key: "and".to_string(),
                category: SchemaCategory::LogicalOperator,
                description: "Logical AND of multiple conditions (short-circuit evaluation)".to_string(),
                semantics: Some("Returns true only if ALL conditions are true. Stops evaluating on first false.".to_string()),
                parameters: vec![],
                valid_in_trees: all_trees(),
                example_json: Some(serde_json::json!({
                    "op": "and",
                    "conditions": [
                        {"op": ">", "left": {"field": "balance"}, "right": {"value": 0}},
                        {"op": "<", "left": {"field": "amount"}, "right": {"value": 1000000}}
                    ]
                })),
                source_location: "simulator/src/policy/tree/types.rs:142".to_string(),
                see_also: vec!["Or".to_string(), "Not".to_string()],
                data_type: None,
                unit: None,
                added_in: Some("1.0".to_string()),
            },
            SchemaElement {
                name: "Or".to_string(),
                json_key: "or".to_string(),
                category: SchemaCategory::LogicalOperator,
                description: "Logical OR of multiple conditions (short-circuit evaluation)".to_string(),
                semantics: Some("Returns true if ANY condition is true. Stops evaluating on first true.".to_string()),
                parameters: vec![],
                valid_in_trees: all_trees(),
                example_json: Some(serde_json::json!({
                    "op": "or",
                    "conditions": [
                        {"op": "==", "left": {"field": "is_overdue"}, "right": {"value": 1}},
                        {"op": "<", "left": {"field": "ticks_to_deadline"}, "right": {"value": 3}}
                    ]
                })),
                source_location: "simulator/src/policy/tree/types.rs:146".to_string(),
                see_also: vec!["And".to_string(), "Not".to_string()],
                data_type: None,
                unit: None,
                added_in: Some("1.0".to_string()),
            },
            SchemaElement {
                name: "Not".to_string(),
                json_key: "not".to_string(),
                category: SchemaCategory::LogicalOperator,
                description: "Logical NOT (negation) of a condition".to_string(),
                semantics: Some("Returns true if condition is false, and vice versa.".to_string()),
                parameters: vec![],
                valid_in_trees: all_trees(),
                example_json: Some(serde_json::json!({
                    "op": "not",
                    "condition": {"op": "==", "left": {"field": "is_split"}, "right": {"value": 1}}
                })),
                source_location: "simulator/src/policy/tree/types.rs:150".to_string(),
                see_also: vec!["And".to_string(), "Or".to_string()],
                data_type: None,
                unit: None,
                added_in: Some("1.0".to_string()),
            },
        ]
    }
}

impl SchemaDocumented for Computation {
    fn schema_docs() -> Vec<SchemaElement> {
        vec![
            // Binary arithmetic
            SchemaElement {
                name: "Add".to_string(),
                json_key: "+".to_string(),
                category: SchemaCategory::BinaryArithmetic,
                description: "Addition of two values".to_string(),
                semantics: Some("Returns left + right".to_string()),
                parameters: vec![],
                valid_in_trees: all_trees(),
                example_json: Some(serde_json::json!({
                    "compute": {"op": "+", "left": {"field": "balance"}, "right": {"field": "credit_limit"}}
                })),
                source_location: "simulator/src/policy/tree/types.rs:210".to_string(),
                see_also: vec!["Subtract".to_string()],
                data_type: Some("f64".to_string()),
                unit: None,
                added_in: Some("1.0".to_string()),
            },
            SchemaElement {
                name: "Subtract".to_string(),
                json_key: "-".to_string(),
                category: SchemaCategory::BinaryArithmetic,
                description: "Subtraction of two values".to_string(),
                semantics: Some("Returns left - right".to_string()),
                parameters: vec![],
                valid_in_trees: all_trees(),
                example_json: Some(serde_json::json!({
                    "compute": {"op": "-", "left": {"field": "balance"}, "right": {"field": "amount"}}
                })),
                source_location: "simulator/src/policy/tree/types.rs:214".to_string(),
                see_also: vec!["Add".to_string()],
                data_type: Some("f64".to_string()),
                unit: None,
                added_in: Some("1.0".to_string()),
            },
            SchemaElement {
                name: "Multiply".to_string(),
                json_key: "*".to_string(),
                category: SchemaCategory::BinaryArithmetic,
                description: "Multiplication of two values".to_string(),
                semantics: Some("Returns left * right".to_string()),
                parameters: vec![],
                valid_in_trees: all_trees(),
                example_json: Some(serde_json::json!({
                    "compute": {"op": "*", "left": {"field": "amount"}, "right": {"value": 0.5}}
                })),
                source_location: "simulator/src/policy/tree/types.rs:218".to_string(),
                see_also: vec!["Divide".to_string()],
                data_type: Some("f64".to_string()),
                unit: None,
                added_in: Some("1.0".to_string()),
            },
            SchemaElement {
                name: "Divide".to_string(),
                json_key: "/".to_string(),
                category: SchemaCategory::BinaryArithmetic,
                description: "Division of two values (checked for divide-by-zero)".to_string(),
                semantics: Some("Returns left / right. Errors on division by zero.".to_string()),
                parameters: vec![],
                valid_in_trees: all_trees(),
                example_json: Some(serde_json::json!({
                    "compute": {"op": "/", "left": {"field": "amount"}, "right": {"param": "num_splits"}}
                })),
                source_location: "simulator/src/policy/tree/types.rs:222".to_string(),
                see_also: vec!["SafeDiv".to_string(), "Multiply".to_string()],
                data_type: Some("f64".to_string()),
                unit: None,
                added_in: Some("1.0".to_string()),
            },
            // N-ary arithmetic
            SchemaElement {
                name: "Max".to_string(),
                json_key: "max".to_string(),
                category: SchemaCategory::NaryArithmetic,
                description: "Maximum of multiple values".to_string(),
                semantics: Some("Returns the largest value from the list".to_string()),
                parameters: vec![],
                valid_in_trees: all_trees(),
                example_json: Some(serde_json::json!({
                    "compute": {"op": "max", "values": [{"field": "balance"}, {"value": 0}]}
                })),
                source_location: "simulator/src/policy/tree/types.rs:227".to_string(),
                see_also: vec!["Min".to_string(), "Clamp".to_string()],
                data_type: Some("f64".to_string()),
                unit: None,
                added_in: Some("1.0".to_string()),
            },
            SchemaElement {
                name: "Min".to_string(),
                json_key: "min".to_string(),
                category: SchemaCategory::NaryArithmetic,
                description: "Minimum of multiple values".to_string(),
                semantics: Some("Returns the smallest value from the list".to_string()),
                parameters: vec![],
                valid_in_trees: all_trees(),
                example_json: Some(serde_json::json!({
                    "compute": {"op": "min", "values": [{"field": "amount"}, {"field": "balance"}]}
                })),
                source_location: "simulator/src/policy/tree/types.rs:231".to_string(),
                see_also: vec!["Max".to_string(), "Clamp".to_string()],
                data_type: Some("f64".to_string()),
                unit: None,
                added_in: Some("1.0".to_string()),
            },
            // Unary math
            SchemaElement {
                name: "Ceil".to_string(),
                json_key: "ceil".to_string(),
                category: SchemaCategory::UnaryMath,
                description: "Ceiling - round up to nearest integer".to_string(),
                semantics: Some("Returns the smallest integer >= value".to_string()),
                parameters: vec![],
                valid_in_trees: all_trees(),
                example_json: Some(serde_json::json!({
                    "compute": {"op": "ceil", "value": {"field": "ratio"}}
                })),
                source_location: "simulator/src/policy/tree/types.rs:236".to_string(),
                see_also: vec!["Floor".to_string(), "Round".to_string()],
                data_type: Some("f64".to_string()),
                unit: None,
                added_in: Some("1.0".to_string()),
            },
            SchemaElement {
                name: "Floor".to_string(),
                json_key: "floor".to_string(),
                category: SchemaCategory::UnaryMath,
                description: "Floor - round down to nearest integer".to_string(),
                semantics: Some("Returns the largest integer <= value".to_string()),
                parameters: vec![],
                valid_in_trees: all_trees(),
                example_json: Some(serde_json::json!({
                    "compute": {"op": "floor", "value": {"field": "ratio"}}
                })),
                source_location: "simulator/src/policy/tree/types.rs:240".to_string(),
                see_also: vec!["Ceil".to_string(), "Round".to_string()],
                data_type: Some("f64".to_string()),
                unit: None,
                added_in: Some("1.0".to_string()),
            },
            SchemaElement {
                name: "Round".to_string(),
                json_key: "round".to_string(),
                category: SchemaCategory::UnaryMath,
                description: "Round to nearest integer".to_string(),
                semantics: Some("Returns the nearest integer (0.5 rounds up)".to_string()),
                parameters: vec![],
                valid_in_trees: all_trees(),
                example_json: Some(serde_json::json!({
                    "compute": {"op": "round", "value": {"field": "ratio"}}
                })),
                source_location: "simulator/src/policy/tree/types.rs:244".to_string(),
                see_also: vec!["Ceil".to_string(), "Floor".to_string()],
                data_type: Some("f64".to_string()),
                unit: None,
                added_in: Some("1.0".to_string()),
            },
            SchemaElement {
                name: "Abs".to_string(),
                json_key: "abs".to_string(),
                category: SchemaCategory::UnaryMath,
                description: "Absolute value".to_string(),
                semantics: Some("Returns |value| (non-negative)".to_string()),
                parameters: vec![],
                valid_in_trees: all_trees(),
                example_json: Some(serde_json::json!({
                    "compute": {"op": "abs", "value": {"field": "net_position"}}
                })),
                source_location: "simulator/src/policy/tree/types.rs:248".to_string(),
                see_also: vec![],
                data_type: Some("f64".to_string()),
                unit: None,
                added_in: Some("1.0".to_string()),
            },
            // Ternary math
            SchemaElement {
                name: "Clamp".to_string(),
                json_key: "clamp".to_string(),
                category: SchemaCategory::TernaryMath,
                description: "Clamp value to range [min, max]".to_string(),
                semantics: Some("Returns min if value < min, max if value > max, else value".to_string()),
                parameters: vec![],
                valid_in_trees: all_trees(),
                example_json: Some(serde_json::json!({
                    "compute": {"op": "clamp", "value": {"field": "priority"}, "min": {"value": 1}, "max": {"value": 10}}
                })),
                source_location: "simulator/src/policy/tree/types.rs:252".to_string(),
                see_also: vec!["Min".to_string(), "Max".to_string()],
                data_type: Some("f64".to_string()),
                unit: None,
                added_in: Some("1.0".to_string()),
            },
            SchemaElement {
                name: "SafeDiv".to_string(),
                json_key: "div0".to_string(),
                category: SchemaCategory::TernaryMath,
                description: "Safe division - return default if denominator is zero".to_string(),
                semantics: Some("Returns numerator/denominator, or default if denominator is zero or near-zero".to_string()),
                parameters: vec![],
                valid_in_trees: all_trees(),
                example_json: Some(serde_json::json!({
                    "compute": {"op": "div0", "numerator": {"field": "amount"}, "denominator": {"field": "count"}, "default": {"value": 0}}
                })),
                source_location: "simulator/src/policy/tree/types.rs:260".to_string(),
                see_also: vec!["Divide".to_string()],
                data_type: Some("f64".to_string()),
                unit: None,
                added_in: Some("1.0".to_string()),
            },
        ]
    }
}

impl SchemaDocumented for Value {
    fn schema_docs() -> Vec<SchemaElement> {
        vec![
            SchemaElement {
                name: "Field".to_string(),
                json_key: "field".to_string(),
                category: SchemaCategory::ValueType,
                description: "Reference to a field in the evaluation context".to_string(),
                semantics: Some("Retrieves the current value of a simulation field (e.g., balance, amount)".to_string()),
                parameters: vec![],
                valid_in_trees: all_trees(),
                example_json: Some(serde_json::json!({"field": "balance"})),
                source_location: "simulator/src/policy/tree/types.rs:166".to_string(),
                see_also: vec!["Param".to_string()],
                data_type: Some("f64".to_string()),
                unit: None,
                added_in: Some("1.0".to_string()),
            },
            SchemaElement {
                name: "Param".to_string(),
                json_key: "param".to_string(),
                category: SchemaCategory::ValueType,
                description: "Reference to a named parameter from the policy definition".to_string(),
                semantics: Some("Retrieves the value of a parameter defined in the policy's parameters section".to_string()),
                parameters: vec![],
                valid_in_trees: all_trees(),
                example_json: Some(serde_json::json!({"param": "urgency_threshold"})),
                source_location: "simulator/src/policy/tree/types.rs:170".to_string(),
                see_also: vec!["Field".to_string()],
                data_type: Some("f64".to_string()),
                unit: None,
                added_in: Some("1.0".to_string()),
            },
            SchemaElement {
                name: "Literal".to_string(),
                json_key: "value".to_string(),
                category: SchemaCategory::ValueType,
                description: "Literal value (number, string, or boolean)".to_string(),
                semantics: Some("A constant value embedded directly in the policy".to_string()),
                parameters: vec![],
                valid_in_trees: all_trees(),
                example_json: Some(serde_json::json!({"value": 100000})),
                source_location: "simulator/src/policy/tree/types.rs:173".to_string(),
                see_also: vec![],
                data_type: Some("any".to_string()),
                unit: None,
                added_in: Some("1.0".to_string()),
            },
            SchemaElement {
                name: "Compute".to_string(),
                json_key: "compute".to_string(),
                category: SchemaCategory::ValueType,
                description: "Computed value (arithmetic expression)".to_string(),
                semantics: Some("A value computed from other values using arithmetic operations".to_string()),
                parameters: vec![],
                valid_in_trees: all_trees(),
                example_json: Some(serde_json::json!({"compute": {"op": "+", "left": {"field": "balance"}, "right": {"field": "credit_limit"}}})),
                source_location: "simulator/src/policy/tree/types.rs:176".to_string(),
                see_also: vec!["Add".to_string(), "Subtract".to_string(), "Multiply".to_string(), "Divide".to_string()],
                data_type: Some("f64".to_string()),
                unit: None,
                added_in: Some("1.0".to_string()),
            },
        ]
    }
}

impl SchemaDocumented for ActionType {
    fn schema_docs() -> Vec<SchemaElement> {
        let payment_tree = vec!["payment_tree".to_string()];
        let bank_tree = vec!["bank_tree".to_string()];
        let collateral_trees = vec![
            "strategic_collateral_tree".to_string(),
            "end_of_tick_collateral_tree".to_string(),
        ];

        vec![
            // Payment actions (valid in payment_tree)
            SchemaElement {
                name: "Release".to_string(),
                json_key: "Release".to_string(),
                category: SchemaCategory::PaymentAction,
                description: "Submit transaction in full to RTGS Queue 2 for settlement".to_string(),
                semantics: Some("Moves transaction from Queue 1 to RTGS Queue 2. May settle immediately if liquidity is sufficient.".to_string()),
                parameters: vec![
                    ParameterDoc {
                        name: "priority_flag".to_string(),
                        param_type: "string".to_string(),
                        required: false,
                        description: "Optional priority override for RTGS queue".to_string(),
                        example: Some(serde_json::json!("HIGH")),
                        valid_values: Some(vec!["HIGH".to_string(), "MEDIUM".to_string(), "LOW".to_string()]),
                    },
                ],
                valid_in_trees: payment_tree.clone(),
                example_json: Some(serde_json::json!({"type": "action", "node_id": "A1", "action": "Release"})),
                source_location: "simulator/src/policy/tree/types.rs:279".to_string(),
                see_also: vec!["ReleaseWithCredit".to_string(), "Hold".to_string()],
                data_type: None,
                unit: None,
                added_in: Some("1.0".to_string()),
            },
            SchemaElement {
                name: "ReleaseWithCredit".to_string(),
                json_key: "ReleaseWithCredit".to_string(),
                category: SchemaCategory::PaymentAction,
                description: "Submit transaction using credit if balance is insufficient".to_string(),
                semantics: Some("Like Release, but uses available credit limit to cover shortfall".to_string()),
                parameters: vec![],
                valid_in_trees: payment_tree.clone(),
                example_json: Some(serde_json::json!({"type": "action", "node_id": "A2", "action": "ReleaseWithCredit"})),
                source_location: "simulator/src/policy/tree/types.rs:282".to_string(),
                see_also: vec!["Release".to_string()],
                data_type: None,
                unit: None,
                added_in: Some("1.0".to_string()),
            },
            SchemaElement {
                name: "PaceAndRelease".to_string(),
                json_key: "PaceAndRelease".to_string(),
                category: SchemaCategory::PaymentAction,
                description: "Split and pace transaction release over multiple ticks".to_string(),
                semantics: Some("Splits transaction and releases parts gradually to smooth liquidity impact".to_string()),
                parameters: vec![
                    ParameterDoc {
                        name: "num_splits".to_string(),
                        param_type: "number".to_string(),
                        required: true,
                        description: "Number of parts to split into".to_string(),
                        example: Some(serde_json::json!(4)),
                        valid_values: None,
                    },
                ],
                valid_in_trees: payment_tree.clone(),
                example_json: Some(serde_json::json!({"type": "action", "node_id": "A3", "action": "PaceAndRelease", "parameters": {"num_splits": {"value": 4}}})),
                source_location: "simulator/src/policy/tree/types.rs:285".to_string(),
                see_also: vec!["Split".to_string(), "StaggerSplit".to_string()],
                data_type: None,
                unit: None,
                added_in: Some("1.0".to_string()),
            },
            SchemaElement {
                name: "Split".to_string(),
                json_key: "Split".to_string(),
                category: SchemaCategory::PaymentAction,
                description: "Split transaction into multiple equal parts".to_string(),
                semantics: Some("Divides transaction into N parts, releasing first part immediately".to_string()),
                parameters: vec![
                    ParameterDoc {
                        name: "num_splits".to_string(),
                        param_type: "number".to_string(),
                        required: true,
                        description: "Number of parts to split into".to_string(),
                        example: Some(serde_json::json!(4)),
                        valid_values: None,
                    },
                ],
                valid_in_trees: payment_tree.clone(),
                example_json: Some(serde_json::json!({"type": "action", "node_id": "A4", "action": "Split", "parameters": {"num_splits": {"value": 4}}})),
                source_location: "simulator/src/policy/tree/types.rs:288".to_string(),
                see_also: vec!["StaggerSplit".to_string(), "PaceAndRelease".to_string()],
                data_type: None,
                unit: None,
                added_in: Some("1.0".to_string()),
            },
            SchemaElement {
                name: "StaggerSplit".to_string(),
                json_key: "StaggerSplit".to_string(),
                category: SchemaCategory::PaymentAction,
                description: "Split transaction with staggered release timing".to_string(),
                semantics: Some("Splits transaction and releases parts with configurable delays between each".to_string()),
                parameters: vec![
                    ParameterDoc {
                        name: "num_splits".to_string(),
                        param_type: "number".to_string(),
                        required: true,
                        description: "Number of parts to split into".to_string(),
                        example: Some(serde_json::json!(4)),
                        valid_values: None,
                    },
                    ParameterDoc {
                        name: "interval_ticks".to_string(),
                        param_type: "number".to_string(),
                        required: false,
                        description: "Ticks between each release (default: 1)".to_string(),
                        example: Some(serde_json::json!(2)),
                        valid_values: None,
                    },
                ],
                valid_in_trees: payment_tree.clone(),
                example_json: Some(serde_json::json!({"type": "action", "node_id": "A5", "action": "StaggerSplit", "parameters": {"num_splits": {"value": 4}, "interval_ticks": {"value": 2}}})),
                source_location: "simulator/src/policy/tree/types.rs:291".to_string(),
                see_also: vec!["Split".to_string()],
                data_type: None,
                unit: None,
                added_in: Some("1.0".to_string()),
            },
            SchemaElement {
                name: "Hold".to_string(),
                json_key: "Hold".to_string(),
                category: SchemaCategory::PaymentAction,
                description: "Hold transaction in Queue 1 for later processing".to_string(),
                semantics: Some("Transaction remains in policy queue, will be re-evaluated next tick".to_string()),
                parameters: vec![],
                valid_in_trees: payment_tree.clone(),
                example_json: Some(serde_json::json!({"type": "action", "node_id": "A6", "action": "Hold"})),
                source_location: "simulator/src/policy/tree/types.rs:294".to_string(),
                see_also: vec!["Release".to_string(), "Drop".to_string()],
                data_type: None,
                unit: None,
                added_in: Some("1.0".to_string()),
            },
            SchemaElement {
                name: "Drop".to_string(),
                json_key: "Drop".to_string(),
                category: SchemaCategory::PaymentAction,
                description: "Drop transaction (expired or unviable)".to_string(),
                semantics: Some("Transaction is removed from processing. Use for expired or impossible transactions.".to_string()),
                parameters: vec![],
                valid_in_trees: payment_tree.clone(),
                example_json: Some(serde_json::json!({"type": "action", "node_id": "A7", "action": "Drop"})),
                source_location: "simulator/src/policy/tree/types.rs:297".to_string(),
                see_also: vec!["Hold".to_string()],
                data_type: None,
                unit: None,
                added_in: Some("1.0".to_string()),
            },
            SchemaElement {
                name: "Reprioritize".to_string(),
                json_key: "Reprioritize".to_string(),
                category: SchemaCategory::PaymentAction,
                description: "Change transaction priority without releasing".to_string(),
                semantics: Some("Updates priority for processing order while keeping in Queue 1".to_string()),
                parameters: vec![
                    ParameterDoc {
                        name: "new_priority".to_string(),
                        param_type: "number".to_string(),
                        required: true,
                        description: "New priority value (0-10)".to_string(),
                        example: Some(serde_json::json!(8)),
                        valid_values: None,
                    },
                ],
                valid_in_trees: payment_tree.clone(),
                example_json: Some(serde_json::json!({"type": "action", "node_id": "A8", "action": "Reprioritize", "parameters": {"new_priority": {"value": 8}}})),
                source_location: "simulator/src/policy/tree/types.rs:301".to_string(),
                see_also: vec!["Hold".to_string()],
                data_type: None,
                unit: None,
                added_in: Some("1.0".to_string()),
            },
            // Bank actions (valid in bank_tree)
            SchemaElement {
                name: "SetReleaseBudget".to_string(),
                json_key: "SetReleaseBudget".to_string(),
                category: SchemaCategory::BankAction,
                description: "Set release budget for this tick".to_string(),
                semantics: Some("Controls total value that can be released this tick. Evaluated once before processing transactions.".to_string()),
                parameters: vec![
                    ParameterDoc {
                        name: "budget".to_string(),
                        param_type: "number".to_string(),
                        required: true,
                        description: "Maximum total value to release this tick (cents)".to_string(),
                        example: Some(serde_json::json!(1000000)),
                        valid_values: None,
                    },
                ],
                valid_in_trees: bank_tree.clone(),
                example_json: Some(serde_json::json!({"type": "action", "node_id": "B1", "action": "SetReleaseBudget", "parameters": {"budget": {"field": "balance"}}})),
                source_location: "simulator/src/policy/tree/types.rs:307".to_string(),
                see_also: vec!["SetState".to_string()],
                data_type: None,
                unit: None,
                added_in: Some("1.0".to_string()),
            },
            SchemaElement {
                name: "SetState".to_string(),
                json_key: "SetState".to_string(),
                category: SchemaCategory::BankAction,
                description: "Set a state register value (policy memory)".to_string(),
                semantics: Some("Stores a value that persists across ticks within a day. Keys must start with 'bank_state_' prefix.".to_string()),
                parameters: vec![
                    ParameterDoc {
                        name: "key".to_string(),
                        param_type: "string".to_string(),
                        required: true,
                        description: "State register key (must start with 'bank_state_')".to_string(),
                        example: Some(serde_json::json!("bank_state_release_count")),
                        valid_values: None,
                    },
                    ParameterDoc {
                        name: "value".to_string(),
                        param_type: "number".to_string(),
                        required: true,
                        description: "Value to store".to_string(),
                        example: Some(serde_json::json!(0)),
                        valid_values: None,
                    },
                ],
                valid_in_trees: bank_tree.clone(),
                example_json: Some(serde_json::json!({"type": "action", "node_id": "B2", "action": "SetState", "parameters": {"key": {"value": "bank_state_counter"}, "value": {"value": 0}}})),
                source_location: "simulator/src/policy/tree/types.rs:315".to_string(),
                see_also: vec!["AddState".to_string()],
                data_type: None,
                unit: None,
                added_in: Some("1.0".to_string()),
            },
            SchemaElement {
                name: "AddState".to_string(),
                json_key: "AddState".to_string(),
                category: SchemaCategory::BankAction,
                description: "Add to a state register value (increment/decrement)".to_string(),
                semantics: Some("Increments or decrements a state register. Useful for counters.".to_string()),
                parameters: vec![
                    ParameterDoc {
                        name: "key".to_string(),
                        param_type: "string".to_string(),
                        required: true,
                        description: "State register key (must start with 'bank_state_')".to_string(),
                        example: Some(serde_json::json!("bank_state_release_count")),
                        valid_values: None,
                    },
                    ParameterDoc {
                        name: "delta".to_string(),
                        param_type: "number".to_string(),
                        required: true,
                        description: "Amount to add (can be negative)".to_string(),
                        example: Some(serde_json::json!(1)),
                        valid_values: None,
                    },
                ],
                valid_in_trees: bank_tree.clone(),
                example_json: Some(serde_json::json!({"type": "action", "node_id": "B3", "action": "AddState", "parameters": {"key": {"value": "bank_state_counter"}, "delta": {"value": 1}}})),
                source_location: "simulator/src/policy/tree/types.rs:321".to_string(),
                see_also: vec!["SetState".to_string()],
                data_type: None,
                unit: None,
                added_in: Some("1.0".to_string()),
            },
            // Collateral actions
            SchemaElement {
                name: "PostCollateral".to_string(),
                json_key: "PostCollateral".to_string(),
                category: SchemaCategory::CollateralAction,
                description: "Post collateral to increase available liquidity".to_string(),
                semantics: Some("Posts collateral to central bank, increasing credit limit".to_string()),
                parameters: vec![
                    ParameterDoc {
                        name: "amount".to_string(),
                        param_type: "number".to_string(),
                        required: true,
                        description: "Amount of collateral to post (cents)".to_string(),
                        example: Some(serde_json::json!(500000)),
                        valid_values: None,
                    },
                ],
                valid_in_trees: collateral_trees.clone(),
                example_json: Some(serde_json::json!({"type": "action", "node_id": "C1", "action": "PostCollateral", "parameters": {"amount": {"value": 500000}}})),
                source_location: "simulator/src/policy/tree/types.rs:325".to_string(),
                see_also: vec!["WithdrawCollateral".to_string(), "HoldCollateral".to_string()],
                data_type: None,
                unit: None,
                added_in: Some("1.0".to_string()),
            },
            SchemaElement {
                name: "WithdrawCollateral".to_string(),
                json_key: "WithdrawCollateral".to_string(),
                category: SchemaCategory::CollateralAction,
                description: "Withdraw collateral to reduce opportunity costs".to_string(),
                semantics: Some("Withdraws collateral from central bank, reducing credit limit".to_string()),
                parameters: vec![
                    ParameterDoc {
                        name: "amount".to_string(),
                        param_type: "number".to_string(),
                        required: true,
                        description: "Amount of collateral to withdraw (cents)".to_string(),
                        example: Some(serde_json::json!(200000)),
                        valid_values: None,
                    },
                ],
                valid_in_trees: collateral_trees.clone(),
                example_json: Some(serde_json::json!({"type": "action", "node_id": "C2", "action": "WithdrawCollateral", "parameters": {"amount": {"value": 200000}}})),
                source_location: "simulator/src/policy/tree/types.rs:328".to_string(),
                see_also: vec!["PostCollateral".to_string(), "HoldCollateral".to_string()],
                data_type: None,
                unit: None,
                added_in: Some("1.0".to_string()),
            },
            SchemaElement {
                name: "HoldCollateral".to_string(),
                json_key: "HoldCollateral".to_string(),
                category: SchemaCategory::CollateralAction,
                description: "Take no action on collateral".to_string(),
                semantics: Some("Keeps current collateral level unchanged".to_string()),
                parameters: vec![],
                valid_in_trees: collateral_trees.clone(),
                example_json: Some(serde_json::json!({"type": "action", "node_id": "C3", "action": "HoldCollateral"})),
                source_location: "simulator/src/policy/tree/types.rs:331".to_string(),
                see_also: vec!["PostCollateral".to_string(), "WithdrawCollateral".to_string()],
                data_type: None,
                unit: None,
                added_in: Some("1.0".to_string()),
            },
            // RTGS Queue 2 actions
            SchemaElement {
                name: "WithdrawFromRtgs".to_string(),
                json_key: "WithdrawFromRtgs".to_string(),
                category: SchemaCategory::RtgsAction,
                description: "Withdraw transaction from RTGS Queue 2".to_string(),
                semantics: Some("Removes transaction from RTGS queue, returns to policy control in Queue 1".to_string()),
                parameters: vec![],
                valid_in_trees: payment_tree.clone(),
                example_json: Some(serde_json::json!({"type": "action", "node_id": "R1", "action": "WithdrawFromRtgs"})),
                source_location: "simulator/src/policy/tree/types.rs:339".to_string(),
                see_also: vec!["ResubmitToRtgs".to_string(), "Release".to_string()],
                data_type: None,
                unit: None,
                added_in: Some("1.0".to_string()),
            },
            SchemaElement {
                name: "ResubmitToRtgs".to_string(),
                json_key: "ResubmitToRtgs".to_string(),
                category: SchemaCategory::RtgsAction,
                description: "Resubmit transaction to RTGS with new priority".to_string(),
                semantics: Some("Changes RTGS priority of a transaction in Queue 2. Loses FIFO position.".to_string()),
                parameters: vec![
                    ParameterDoc {
                        name: "rtgs_priority".to_string(),
                        param_type: "string".to_string(),
                        required: true,
                        description: "New RTGS priority level".to_string(),
                        example: Some(serde_json::json!("HighlyUrgent")),
                        valid_values: Some(vec!["HighlyUrgent".to_string(), "Urgent".to_string(), "Normal".to_string()]),
                    },
                ],
                valid_in_trees: payment_tree.clone(),
                example_json: Some(serde_json::json!({"type": "action", "node_id": "R2", "action": "ResubmitToRtgs", "parameters": {"rtgs_priority": {"value": "HighlyUrgent"}}})),
                source_location: "simulator/src/policy/tree/types.rs:346".to_string(),
                see_also: vec!["WithdrawFromRtgs".to_string()],
                data_type: None,
                unit: None,
                added_in: Some("1.0".to_string()),
            },
        ]
    }
}

/// Generate complete policy schema documentation as JSON string
pub fn get_policy_schema() -> String {
    let schema = PolicySchemaDoc {
        version: "1.0".to_string(),
        generated_at: "2025-01-01T00:00:00Z".to_string(), // Static for determinism
        tree_types: vec![],  // TODO: Add tree type docs
        node_types: vec![],  // TODO: Add node type docs
        expressions: Expression::schema_docs(),
        values: Value::schema_docs(),
        computations: Computation::schema_docs(),
        actions: ActionType::schema_docs(),
        fields: vec![],  // TODO: Add field docs
    };

    serde_json::to_string_pretty(&schema).expect("Schema serialization should not fail")
}

// ============================================================================
// TESTS - Written FIRST (TDD)
// ============================================================================

#[cfg(test)]
mod tests {
    use super::*;

    // -------------------------------------------------------------------------
    // Step 1.1: Data structure tests
    // -------------------------------------------------------------------------

    #[test]
    fn test_schema_category_serializes_to_json() {
        let cat = SchemaCategory::PaymentAction;
        let json = serde_json::to_string(&cat).unwrap();
        assert_eq!(json, "\"PaymentAction\"");
    }

    #[test]
    fn test_schema_category_deserializes_from_json() {
        let cat: SchemaCategory = serde_json::from_str("\"ComparisonOperator\"").unwrap();
        assert_eq!(cat, SchemaCategory::ComparisonOperator);
    }

    #[test]
    fn test_parameter_doc_serializes_roundtrip() {
        let param = ParameterDoc {
            name: "num_splits".to_string(),
            param_type: "number".to_string(),
            required: true,
            description: "Number of splits".to_string(),
            example: Some(serde_json::json!(4)),
            valid_values: None,
        };

        let json = serde_json::to_string(&param).unwrap();
        let restored: ParameterDoc = serde_json::from_str(&json).unwrap();
        assert_eq!(param, restored);
    }

    #[test]
    fn test_schema_element_serializes_roundtrip() {
        let elem = SchemaElement {
            name: "Release".to_string(),
            json_key: "Release".to_string(),
            category: SchemaCategory::PaymentAction,
            description: "Submit transaction to RTGS".to_string(),
            semantics: Some("Moves from Q1 to Q2".to_string()),
            parameters: vec![],
            valid_in_trees: vec!["payment_tree".to_string()],
            example_json: Some(serde_json::json!({"action": "Release"})),
            source_location: "types.rs:278".to_string(),
            see_also: vec!["Hold".to_string()],
            data_type: None,
            unit: None,
            added_in: Some("1.0".to_string()),
        };

        let json = serde_json::to_string(&elem).unwrap();
        let restored: SchemaElement = serde_json::from_str(&json).unwrap();
        assert_eq!(elem, restored);
    }

    #[test]
    fn test_policy_schema_doc_serializes_to_json() {
        let schema = PolicySchemaDoc {
            version: "1.0".to_string(),
            generated_at: "2025-01-01T00:00:00Z".to_string(),
            tree_types: vec![],
            node_types: vec![],
            expressions: vec![],
            values: vec![],
            computations: vec![],
            actions: vec![],
            fields: vec![],
        };

        let json = serde_json::to_string_pretty(&schema).unwrap();
        assert!(json.contains("\"version\": \"1.0\""));
        assert!(json.contains("\"tree_types\": []"));
    }

    // -------------------------------------------------------------------------
    // Step 1.2: Expression documentation tests (TDD - written first)
    // -------------------------------------------------------------------------

    #[test]
    fn test_expression_schema_docs_returns_all_operators() {
        use super::super::types::Expression;

        let docs = Expression::schema_docs();

        // Must have all 6 comparison + 3 logical = 9 operators
        assert_eq!(docs.len(), 9, "Expected 9 expression operators");

        let names: Vec<&str> = docs.iter().map(|d| d.name.as_str()).collect();

        // Comparison operators
        assert!(names.contains(&"Equal"), "Missing Equal");
        assert!(names.contains(&"NotEqual"), "Missing NotEqual");
        assert!(names.contains(&"LessThan"), "Missing LessThan");
        assert!(names.contains(&"LessOrEqual"), "Missing LessOrEqual");
        assert!(names.contains(&"GreaterThan"), "Missing GreaterThan");
        assert!(names.contains(&"GreaterOrEqual"), "Missing GreaterOrEqual");

        // Logical operators
        assert!(names.contains(&"And"), "Missing And");
        assert!(names.contains(&"Or"), "Missing Or");
        assert!(names.contains(&"Not"), "Missing Not");
    }

    #[test]
    fn test_expression_schema_docs_has_correct_json_keys() {
        use super::super::types::Expression;

        let docs = Expression::schema_docs();

        let equal = docs.iter().find(|d| d.name == "Equal").unwrap();
        assert_eq!(equal.json_key, "==");

        let and = docs.iter().find(|d| d.name == "And").unwrap();
        assert_eq!(and.json_key, "and");
    }

    #[test]
    fn test_expression_schema_docs_has_correct_categories() {
        use super::super::types::Expression;

        let docs = Expression::schema_docs();

        let equal = docs.iter().find(|d| d.name == "Equal").unwrap();
        assert_eq!(equal.category, SchemaCategory::ComparisonOperator);

        let and = docs.iter().find(|d| d.name == "And").unwrap();
        assert_eq!(and.category, SchemaCategory::LogicalOperator);
    }

    #[test]
    fn test_expression_schema_docs_has_descriptions() {
        use super::super::types::Expression;

        let docs = Expression::schema_docs();

        for doc in &docs {
            assert!(!doc.description.is_empty(), "{} has empty description", doc.name);
        }
    }

    #[test]
    fn test_expression_schema_docs_has_valid_trees() {
        use super::super::types::Expression;

        let docs = Expression::schema_docs();

        for doc in &docs {
            assert!(!doc.valid_in_trees.is_empty(), "{} has no valid_in_trees", doc.name);
            // Expressions are valid in all trees
            assert!(doc.valid_in_trees.contains(&"payment_tree".to_string()));
        }
    }

    // -------------------------------------------------------------------------
    // Step 1.3: Computation documentation tests (TDD - written first)
    // -------------------------------------------------------------------------

    #[test]
    fn test_computation_schema_docs_returns_all_operations() {
        use super::super::types::Computation;

        let docs = Computation::schema_docs();

        // 4 binary + 2 n-ary + 4 unary + 2 ternary = 12 operations
        assert_eq!(docs.len(), 12, "Expected 12 computation operations");

        let names: Vec<&str> = docs.iter().map(|d| d.name.as_str()).collect();

        // Binary arithmetic
        assert!(names.contains(&"Add"), "Missing Add");
        assert!(names.contains(&"Subtract"), "Missing Subtract");
        assert!(names.contains(&"Multiply"), "Missing Multiply");
        assert!(names.contains(&"Divide"), "Missing Divide");

        // N-ary arithmetic
        assert!(names.contains(&"Max"), "Missing Max");
        assert!(names.contains(&"Min"), "Missing Min");

        // Unary math
        assert!(names.contains(&"Ceil"), "Missing Ceil");
        assert!(names.contains(&"Floor"), "Missing Floor");
        assert!(names.contains(&"Round"), "Missing Round");
        assert!(names.contains(&"Abs"), "Missing Abs");

        // Ternary math
        assert!(names.contains(&"Clamp"), "Missing Clamp");
        assert!(names.contains(&"SafeDiv"), "Missing SafeDiv");
    }

    #[test]
    fn test_computation_schema_docs_has_correct_categories() {
        use super::super::types::Computation;

        let docs = Computation::schema_docs();

        let add = docs.iter().find(|d| d.name == "Add").unwrap();
        assert_eq!(add.category, SchemaCategory::BinaryArithmetic);

        let max = docs.iter().find(|d| d.name == "Max").unwrap();
        assert_eq!(max.category, SchemaCategory::NaryArithmetic);

        let ceil = docs.iter().find(|d| d.name == "Ceil").unwrap();
        assert_eq!(ceil.category, SchemaCategory::UnaryMath);

        let clamp = docs.iter().find(|d| d.name == "Clamp").unwrap();
        assert_eq!(clamp.category, SchemaCategory::TernaryMath);
    }

    // -------------------------------------------------------------------------
    // Step 1.4: ActionType documentation tests (TDD - written first)
    // -------------------------------------------------------------------------

    #[test]
    fn test_action_schema_docs_returns_all_actions() {
        use super::super::types::ActionType;

        let docs = ActionType::schema_docs();

        // 8 payment + 3 bank + 3 collateral + 2 RTGS = 16 actions
        assert_eq!(docs.len(), 16, "Expected 16 action types, got {}", docs.len());

        let names: Vec<&str> = docs.iter().map(|d| d.name.as_str()).collect();

        // Payment actions
        assert!(names.contains(&"Release"), "Missing Release");
        assert!(names.contains(&"Hold"), "Missing Hold");
        assert!(names.contains(&"Drop"), "Missing Drop");
        assert!(names.contains(&"Split"), "Missing Split");
        assert!(names.contains(&"StaggerSplit"), "Missing StaggerSplit");

        // Bank actions
        assert!(names.contains(&"SetReleaseBudget"), "Missing SetReleaseBudget");
        assert!(names.contains(&"SetState"), "Missing SetState");

        // Collateral actions
        assert!(names.contains(&"PostCollateral"), "Missing PostCollateral");
        assert!(names.contains(&"WithdrawCollateral"), "Missing WithdrawCollateral");
    }

    #[test]
    fn test_action_schema_docs_payment_actions_valid_only_in_payment_tree() {
        use super::super::types::ActionType;

        let docs = ActionType::schema_docs();

        let release = docs.iter().find(|d| d.name == "Release").unwrap();
        assert_eq!(release.category, SchemaCategory::PaymentAction);
        assert!(release.valid_in_trees.contains(&"payment_tree".to_string()));
        assert!(!release.valid_in_trees.contains(&"bank_tree".to_string()));
    }

    #[test]
    fn test_action_schema_docs_bank_actions_valid_only_in_bank_tree() {
        use super::super::types::ActionType;

        let docs = ActionType::schema_docs();

        let set_budget = docs.iter().find(|d| d.name == "SetReleaseBudget").unwrap();
        assert_eq!(set_budget.category, SchemaCategory::BankAction);
        assert!(set_budget.valid_in_trees.contains(&"bank_tree".to_string()));
        assert!(!set_budget.valid_in_trees.contains(&"payment_tree".to_string()));
    }

    // -------------------------------------------------------------------------
    // Step 1.5: Value documentation tests (TDD - written first)
    // -------------------------------------------------------------------------

    #[test]
    fn test_value_schema_docs_returns_all_value_types() {
        use super::super::types::Value;

        let docs = Value::schema_docs();

        assert_eq!(docs.len(), 4, "Expected 4 value types");

        let names: Vec<&str> = docs.iter().map(|d| d.name.as_str()).collect();
        assert!(names.contains(&"Field"), "Missing Field");
        assert!(names.contains(&"Param"), "Missing Param");
        assert!(names.contains(&"Literal"), "Missing Literal");
        assert!(names.contains(&"Compute"), "Missing Compute");
    }

    // -------------------------------------------------------------------------
    // Step 1.6: Complete schema tests (TDD - written first)
    // -------------------------------------------------------------------------

    #[test]
    fn test_get_policy_schema_returns_valid_json() {
        let schema = super::get_policy_schema();
        let parsed: serde_json::Value = serde_json::from_str(&schema).unwrap();

        assert!(parsed.get("version").is_some());
        assert!(parsed.get("generated_at").is_some());
        assert!(parsed.get("expressions").is_some());
        assert!(parsed.get("computations").is_some());
        assert!(parsed.get("actions").is_some());
    }

    #[test]
    fn test_get_policy_schema_expressions_count() {
        let schema = super::get_policy_schema();
        let parsed: PolicySchemaDoc = serde_json::from_str(&schema).unwrap();

        assert_eq!(parsed.expressions.len(), 9);
    }

    #[test]
    fn test_get_policy_schema_computations_count() {
        let schema = super::get_policy_schema();
        let parsed: PolicySchemaDoc = serde_json::from_str(&schema).unwrap();

        assert_eq!(parsed.computations.len(), 12);
    }

    #[test]
    fn test_get_policy_schema_actions_count() {
        let schema = super::get_policy_schema();
        let parsed: PolicySchemaDoc = serde_json::from_str(&schema).unwrap();

        assert_eq!(parsed.actions.len(), 16);
    }

    #[test]
    fn test_get_policy_schema_values_count() {
        let schema = super::get_policy_schema();
        let parsed: PolicySchemaDoc = serde_json::from_str(&schema).unwrap();

        assert_eq!(parsed.values.len(), 4);
    }
}
